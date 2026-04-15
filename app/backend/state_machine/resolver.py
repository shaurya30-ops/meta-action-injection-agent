import datetime
from typing import List

import config
from content_extraction.extractor_logic import (
    apply_digit_buffer,
    billing_started,
    build_callback_closing,
    digits_to_tts,
    extract_and_store,
    extract_callback_phrase,
    extract_digits,
    has_callback_request,
)

from .actions import ACTION_MAP
from .intents import Intent
from .session import CallSession
from .states import State
from .transitions import AUTO_TRANSITIONS, GLOBAL_OVERRIDES, TRANSITIONS

TERMINAL_OR_AUTO_STATES = {
    State.CALLBACK_CLOSING,
    State.INVALID_REGISTRATION,
    State.WARM_CLOSING,
    State.LOG_DISPOSITION,
    State.END,
}

PHONE_COLLECTION_STATES: dict[State, tuple[str, str, str, State, str, int]] = {
    State.COLLECT_WHATSAPP_NUMBER: (
        "whatsapp_digit_buffer",
        "awaiting_whatsapp_confirmation",
        "whatsapp_number",
        State.ASK_ALTERNATE_NUMBER,
        "WhatsApp number",
        10,
    ),
    State.COLLECT_ALTERNATE_NUMBER: (
        "alternate_digit_buffer",
        "awaiting_alternate_confirmation",
        "alternate_number",
        State.VERIFY_PINCODE,
        "alternate number",
        10,
    ),
    State.COLLECT_REFERRAL: (
        "referral_digit_buffer",
        "awaiting_referral_confirmation",
        "referral_number",
        State.WARM_CLOSING,
        "referral number",
        10,
    ),
}

PRE_COLLECTION_PHONE_STATES: dict[State, tuple[str, str, str, State, str, int]] = {
    State.VERIFY_WHATSAPP: (
        "whatsapp_digit_buffer",
        "awaiting_whatsapp_confirmation",
        "whatsapp_number",
        State.COLLECT_WHATSAPP_NUMBER,
        "WhatsApp number",
        10,
    ),
    State.ASK_ALTERNATE_NUMBER: (
        "alternate_digit_buffer",
        "awaiting_alternate_confirmation",
        "alternate_number",
        State.COLLECT_ALTERNATE_NUMBER,
        "alternate number",
        10,
    ),
}

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _set_callback_closing(session: CallSession, transcript: str) -> State:
    session.callback_requested = True
    session.callback_time_phrase = extract_callback_phrase(transcript)
    session.callback_closing_text = build_callback_closing(transcript)
    return State.CALLBACK_CLOSING


def _store_user_turn(session: CallSession, state: State, intent: Intent, transcript: str) -> None:
    session.transcript.append(
        {
            "role": "user",
            "text": transcript,
            "intent": intent.value,
            "state": state.value,
            "ts": _now(),
        }
    )


def _reset_phone_collection(
    session: CallSession,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
) -> None:
    setattr(session, buffer_attr, "")
    setattr(session, awaiting_attr, False)
    setattr(session, value_attr, "")


def _declines_optional_number(transcript: str) -> bool:
    if extract_digits(transcript):
        return False
    normalized = transcript.strip().lower()
    negative_markers = (
        "नहीं",
        "नही",
        "नई",
        "जी नहीं",
        "no",
        "nahi",
        "nahin",
        "nhi",
    )
    return any(marker in normalized for marker in negative_markers)


def _build_collection_status_prompt(
    label: str,
    digits: str,
    total_digits: int,
    awaiting_confirmation: bool,
) -> str:
    if awaiting_confirmation and digits:
        return (
            f"अभी मैंने {label} के लिए — {digits_to_tts(digits)} — load किया है। "
            "अगर यही सही है तो हाँ कहिए, वरना दोबारा बताइए।"
        )

    if digits:
        remaining = max(total_digits - len(digits), 0)
        return (
            f"अभी {len(digits)} digit load हुई हैं — {digits_to_tts(digits)}। "
            f"कुल {total_digits} digit चाहिए, बाकी {remaining} digit बताइए।"
        )

    return f"अभी कोई digit load नहीं हुई है। कृपया पूरा {label} बताइए।"


def _apply_phone_digits(
    session: CallSession,
    transcript: str,
    *,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
    total_digits: int,
) -> State:
    existing = getattr(session, buffer_attr)
    fresh_digits = extract_digits(transcript)

    if not fresh_digits:
        return session.current_state

    if len(existing) + len(fresh_digits) > total_digits:
        if len(fresh_digits) == total_digits:
            setattr(session, buffer_attr, fresh_digits)
            setattr(session, awaiting_attr, True)
            setattr(session, value_attr, "")
            return session.current_state

        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
        return session.current_state

    combined, status = apply_digit_buffer(existing, transcript, total_digits)
    setattr(session, buffer_attr, combined)

    if status == "complete":
        setattr(session, awaiting_attr, True)
        setattr(session, value_attr, "")
    else:
        setattr(session, awaiting_attr, False)

    return session.current_state


def _resolve_phone_collection(
    session: CallSession,
    intent: Intent,
    transcript: str,
    *,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
    success_state: State,
    label: str,
    total_digits: int,
) -> State:
    if intent == Intent.ASK and not extract_digits(transcript):
        session.collection_followup_prompt = _build_collection_status_prompt(
            label=label,
            digits=getattr(session, buffer_attr),
            total_digits=total_digits,
            awaiting_confirmation=getattr(session, awaiting_attr),
        )
        return session.current_state

    if getattr(session, awaiting_attr):
        if intent == Intent.AFFIRM:
            confirmed = getattr(session, buffer_attr)
            setattr(session, value_attr, confirmed)
            setattr(session, buffer_attr, "")
            setattr(session, awaiting_attr, False)
            return success_state

        if intent == Intent.DENY:
            _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
            return session.current_state

        fresh_digits = extract_digits(transcript)
        if not fresh_digits:
            return session.current_state

        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)

    return _apply_phone_digits(
        session,
        transcript,
        buffer_attr=buffer_attr,
        awaiting_attr=awaiting_attr,
        value_attr=value_attr,
        total_digits=total_digits,
    )


def _prime_phone_collection(
    session: CallSession,
    transcript: str,
    *,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
    target_state: State,
    total_digits: int,
) -> State:
    _apply_phone_digits(
        session,
        transcript,
        buffer_attr=buffer_attr,
        awaiting_attr=awaiting_attr,
        value_attr=value_attr,
        total_digits=total_digits,
    )
    return target_state


def _resolve_pincode_collection(session: CallSession, intent: Intent, transcript: str) -> State:
    if intent == Intent.ASK and not extract_digits(transcript):
        session.collection_followup_prompt = _build_collection_status_prompt(
            label="pin code",
            digits=session.pincode_digit_buffer,
            total_digits=6,
            awaiting_confirmation=session.awaiting_pincode_confirmation,
        )
        return State.COLLECT_PINCODE

    if session.awaiting_pincode_confirmation:
        if intent == Intent.AFFIRM:
            session.pincode = session.pincode_digit_buffer
            session.pincode_digit_buffer = ""
            session.awaiting_pincode_confirmation = False
            return State.VERIFY_BUSINESS_DETAILS

        if intent == Intent.DENY:
            session.pincode = ""
            session.pincode_digit_buffer = ""
            session.awaiting_pincode_confirmation = False
            return State.COLLECT_PINCODE

        if not extract_digits(transcript):
            return State.COLLECT_PINCODE

        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False

    combined, status = apply_digit_buffer(
        session.pincode_digit_buffer,
        transcript,
        6,
        hard_limit=True,
    )

    if status == "overflow":
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return State.COLLECT_PINCODE

    if status == "no_digits":
        return State.COLLECT_PINCODE

    session.pincode_digit_buffer = combined
    session.awaiting_pincode_confirmation = status == "complete"
    if status != "complete":
        session.pincode = ""
    return State.COLLECT_PINCODE


def resolve_next_state(session: CallSession, intent: Intent, transcript: str) -> State:
    session.collection_followup_prompt = ""

    if session.current_state == State.END:
        return State.END

    if len(session.states_visited) >= config.MAX_TOTAL_TRANSITIONS:
        return State.WARM_CLOSING

    if session.current_state not in TERMINAL_OR_AUTO_STATES and has_callback_request(transcript):
        return _set_callback_closing(session, transcript)

    for override_intent, target_state, suppressed_states in GLOBAL_OVERRIDES:
        if intent == override_intent and session.current_state not in suppressed_states:
            if target_state == State.CALLBACK_CLOSING:
                return _set_callback_closing(session, transcript)
            return target_state

    if session.current_state == State.ASK_BILLING_STATUS:
        if intent == Intent.AFFIRM or billing_started(transcript):
            session.billing_started = "STARTED"
            return State.VERIFY_WHATSAPP
        if intent in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.OBJECT}:
            session.billing_started = "NOT_STARTED"
            return State.ASK_BILLING_STATUS

    if session.current_state == State.VERIFY_PINCODE and extract_digits(transcript):
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return _resolve_pincode_collection(session, intent, transcript)

    if session.current_state in PRE_COLLECTION_PHONE_STATES and extract_digits(transcript):
        (
            buffer_attr,
            awaiting_attr,
            value_attr,
            target_state,
            _label,
            total_digits,
        ) = PRE_COLLECTION_PHONE_STATES[session.current_state]
        return _prime_phone_collection(
            session,
            transcript,
            buffer_attr=buffer_attr,
            awaiting_attr=awaiting_attr,
            value_attr=value_attr,
            target_state=target_state,
            total_digits=total_digits,
        )

    if session.current_state == State.ASK_ALTERNATE_NUMBER and _declines_optional_number(transcript):
        return State.VERIFY_PINCODE

    if session.current_state in PHONE_COLLECTION_STATES:
        (
            buffer_attr,
            awaiting_attr,
            value_attr,
            success_state,
            label,
            total_digits,
        ) = PHONE_COLLECTION_STATES[
            session.current_state
        ]
        return _resolve_phone_collection(
            session,
            intent,
            transcript,
            buffer_attr=buffer_attr,
            awaiting_attr=awaiting_attr,
            value_attr=value_attr,
            success_state=success_state,
            label=label,
            total_digits=total_digits,
        )

    if session.current_state == State.COLLECT_PINCODE:
        return _resolve_pincode_collection(session, intent, transcript)

    next_state = TRANSITIONS.get((session.current_state, intent))
    if next_state is not None:
        return next_state

    auto_next = AUTO_TRANSITIONS.get(session.current_state)
    if auto_next is not None:
        return auto_next

    session.fallback_count += 1
    if session.fallback_count >= config.MAX_FALLBACKS_PER_STATE:
        session.fallback_count = 0
        return State.WARM_CLOSING
    return session.current_state


def post_transition(session: CallSession, intent: Intent, transcript: str, next_state: State) -> None:
    previous_state = session.current_state

    _store_user_turn(session, previous_state, intent, transcript)

    session.previous_state = previous_state
    session.current_state = next_state
    session.states_visited.append(next_state)

    if next_state != previous_state:
        session.fallback_count = 0

    if previous_state == State.VERIFY_BUSINESS_DETAILS and intent in {
        Intent.AFFIRM,
        Intent.DENY,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.OBJECT,
        Intent.THANK,
        Intent.GREET,
        Intent.COMPLAIN,
    }:
        extract_and_store(session, previous_state, transcript)
    elif previous_state == State.VERIFY_EMAIL and intent in {
        Intent.DENY,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.OBJECT,
    }:
        extract_and_store(session, previous_state, transcript)
    elif previous_state == State.ASK_PURCHASE_AMOUNT and intent in {
        Intent.AFFIRM,
        Intent.DENY,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.OBJECT,
    }:
        extract_and_store(session, previous_state, transcript)
    elif previous_state in {State.SUPPORT_AND_REFERRAL, State.COLLECT_REFERRAL} and intent in {
        Intent.AFFIRM,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.THANK,
        Intent.GREET,
    }:
        extract_and_store(session, previous_state, transcript)


def execute_auto_chain(session: CallSession, start_state: State) -> List[State]:
    chain: List[State] = []
    current = start_state

    while True:
        if ACTION_MAP.get(current) is not None:
            chain.append(current)

        next_state = AUTO_TRANSITIONS.get(current)
        if next_state is None:
            break

        session.previous_state = current
        session.current_state = next_state
        session.states_visited.append(next_state)
        current = next_state

    return chain
