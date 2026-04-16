import datetime
from typing import List

import config
from content_extraction.extractor_logic import (
    apply_digit_buffer,
    billing_started,
    build_billing_blocker_support_prefix,
    build_callback_closing,
    digits_to_tts,
    email_fragment_restart_requested,
    extract_and_store,
    extract_callback_phrase,
    extract_digits,
    has_specific_callback_phrase,
    has_callback_request,
    looks_like_email_fragment,
    merge_spoken_email_fragments,
)

from .actions import ACTION_MAP
from .intents import Intent
from .session import CallSession
from .states import State
from .turn_parser import TurnFrame, detect_billing_blocker_reason, parse_turn
from .transitions import AUTO_TRANSITIONS, GLOBAL_OVERRIDES, TRANSITIONS

TERMINAL_OR_AUTO_STATES = {
    State.PRE_CLOSING,
    State.REFERRAL_DECLINE_NUDGE,
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
        State.CONFIRM_WHATSAPP_NUMBER,
        "WhatsApp number",
        10,
    ),
    State.COLLECT_ALTERNATE_NUMBER: (
        "alternate_digit_buffer",
        "awaiting_alternate_confirmation",
        "alternate_number",
        State.CONFIRM_ALTERNATE_NUMBER,
        "alternate number",
        10,
    ),
    State.COLLECT_REFERRAL_NUMBER: (
        "referral_digit_buffer",
        "awaiting_referral_confirmation",
        "referral_number",
        State.CONFIRM_REFERRAL_NUMBER,
        "referral number",
        10,
    ),
}

PHONE_CONFIRMATION_STATES: dict[State, tuple[str, str, str, State, State, str, int]] = {
    State.CONFIRM_WHATSAPP_NUMBER: (
        "whatsapp_digit_buffer",
        "awaiting_whatsapp_confirmation",
        "whatsapp_number",
        State.ASK_ALTERNATE_NUMBER,
        State.COLLECT_WHATSAPP_NUMBER,
        "WhatsApp number",
        10,
    ),
    State.CONFIRM_ALTERNATE_NUMBER: (
        "alternate_digit_buffer",
        "awaiting_alternate_confirmation",
        "alternate_number",
        State.VERIFY_PINCODE,
        State.COLLECT_ALTERNATE_NUMBER,
        "alternate number",
        10,
    ),
    State.CONFIRM_REFERRAL_NUMBER: (
        "referral_digit_buffer",
        "awaiting_referral_confirmation",
        "referral_number",
        State.PRE_CLOSING,
        State.COLLECT_REFERRAL_NUMBER,
        "referral number",
        10,
    ),
}

EMAIL_STATES = {
    State.VERIFY_EMAIL,
    State.COLLECT_EMAIL_CORRECTION,
    State.CONFIRM_EMAIL_CORRECTION,
}

PRE_COLLECTION_PHONE_STATES: dict[State, tuple[str, str, str, State, State, str, int]] = {
    State.VERIFY_WHATSAPP: (
        "whatsapp_digit_buffer",
        "awaiting_whatsapp_confirmation",
        "whatsapp_number",
        State.COLLECT_WHATSAPP_NUMBER,
        State.CONFIRM_WHATSAPP_NUMBER,
        "WhatsApp number",
        10,
    ),
    State.ASK_ALTERNATE_NUMBER: (
        "alternate_digit_buffer",
        "awaiting_alternate_confirmation",
        "alternate_number",
        State.COLLECT_ALTERNATE_NUMBER,
        State.CONFIRM_ALTERNATE_NUMBER,
        "alternate number",
        10,
    ),
}

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _set_callback_closing(session: CallSession, transcript: str) -> State:
    session.callback_requested = True
    if session.current_state == State.ASK_CALLBACK_TIME:
        normalized = " ".join(transcript.split())
        session.callback_time_phrase = extract_callback_phrase(transcript) or normalized
        if session.callback_time_phrase:
            session.callback_closing_text = (
                f"जी बिल्कुल, मैं आपको {session.callback_time_phrase} call करती हूँ। "
                "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे."
            )
        else:
            session.callback_closing_text = build_callback_closing(transcript)
    else:
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


def _ensure_turn_frame(
    session: CallSession,
    turn_or_intent: TurnFrame | Intent,
    transcript: str | None,
) -> TurnFrame:
    if isinstance(turn_or_intent, TurnFrame):
        return turn_or_intent
    return parse_turn(session, turn_or_intent, transcript or "")


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


def _build_phone_collection_followup(
    session: CallSession,
    *,
    label: str,
    digits: str,
    total_digits: int,
    awaiting_confirmation: bool,
) -> str:
    if session.current_state == State.COLLECT_REFERRAL_NUMBER and session.referral_name:
        if awaiting_confirmation and digits:
            return (
                f"अभी मैंने {session.referral_name} जी का referral number — {digits_to_tts(digits)} — load किया है। "
                "अगर यही सही है तो हाँ कहिए, वरना दोबारा बताइए।"
            )
        if digits:
            remaining = max(total_digits - len(digits), 0)
            return (
                f"अभी मैंने {session.referral_name} जी के referral number में {len(digits)} digit load की हैं — "
                f"{digits_to_tts(digits)}। कुल {total_digits} digit चाहिए, बाकी {remaining} digit बताइए।"
            )
        return f"अभी मैंने {session.referral_name} जी का कोई number load नहीं किया है। कृपया पूरा contact number बताइए।"

    return _build_collection_status_prompt(
        label=label,
        digits=digits,
        total_digits=total_digits,
        awaiting_confirmation=awaiting_confirmation,
    )


def _should_interrupt_for_query(session: CallSession, turn: TurnFrame) -> bool:
    if turn.query_type == "none":
        return False
    if session.current_state == State.ANSWER_USER_QUERY:
        return False
    if session.current_state == State.ASK_BILLING_STATUS and turn.workflow_answer in {"billing_started", "billing_not_started"}:
        return False
    if turn.workflow_answer == "collection_status_request":
        return False
    if turn.query_type == "general" and turn.speech_act not in {
        Intent.ASK,
        Intent.REQUEST,
        Intent.UNCLEAR,
        Intent.ESCALATE,
        Intent.OUT_OF_SCOPE,
    }:
        return False
    if turn.workflow_answer not in {"unknown", "user_query", "collection_status_request"} and turn.query_type == "general":
        return False
    return True


def _affect_prefix(turn: TurnFrame) -> str:
    if turn.affect == "frustrated":
        return "जी, मैं समझ सकती हूँ — बार-बार call आना थोड़ा disturbing लगता है."
    if turn.affect == "complaint":
        return "जी, अच्छा किया आपने बताया."
    if turn.affect == "confused":
        return "जी, मैं आसान तरीके से बताती हूँ."
    if turn.affect == "hurried":
        return "बिल्कुल, मैं short में रखती हूँ."
    if turn.affect == "positive":
        return "बहुत अच्छा."
    if turn.affect == "disengaged":
        return "ठीक है जी."

    if turn.speech_act == Intent.THANK:
        return "जी, धन्यवाद."
    if turn.speech_act == Intent.AFFIRM:
        return "जी, ठीक है."
    if turn.speech_act in {Intent.INFORM, Intent.ELABORATE}:
        return "अच्छा, समझ गई."
    if turn.speech_act in {Intent.DENY, Intent.OBJECT}:
        return "ठीक है जी."
    return ""


def _build_response_prefix(
    session: CallSession,
    previous_state: State,
    turn: TurnFrame,
    next_state: State,
) -> str:
    if next_state == State.ANSWER_USER_QUERY:
        return ""

    if next_state in {
        State.ASK_CALLBACK_TIME,
        State.CALLBACK_CLOSING,
        State.INVALID_REGISTRATION,
        State.WARM_CLOSING,
        State.END,
    }:
        return ""

    if previous_state == State.ANSWER_USER_QUERY and next_state != State.ANSWER_USER_QUERY:
        return "ठीक है जी — तो मैं वापस आती हूँ जहाँ हम थे."

    if previous_state == State.CHECK_AVAILABILITY and next_state == State.ASK_BILLING_STATUS:
        return ""

    if previous_state == State.ASK_BILLING_STATUS and next_state == State.VERIFY_WHATSAPP:
        if turn.workflow_answer == "billing_started":
            return "ये तो अच्छी बात है."
        return build_billing_blocker_support_prefix(session)

    if previous_state == State.EXPLORE_BILLING_BLOCKER and next_state == State.VERIFY_WHATSAPP:
        return build_billing_blocker_support_prefix(session)

    if previous_state in {State.VERIFY_WHATSAPP, State.CONFIRM_WHATSAPP_NUMBER} and next_state == State.ASK_ALTERNATE_NUMBER:
        return "जी, noted."

    if previous_state in {State.ASK_ALTERNATE_NUMBER, State.CONFIRM_ALTERNATE_NUMBER} and next_state == State.VERIFY_PINCODE:
        if previous_state == State.CONFIRM_ALTERNATE_NUMBER and turn.workflow_answer == "digits_confirmed":
            return "जी, noted."
        return "जी, कोई बात नहीं."

    if previous_state in {State.VERIFY_PINCODE, State.COLLECT_PINCODE, State.CONFIRM_PINCODE} and next_state == State.VERIFY_BUSINESS_DETAILS:
        if turn.workflow_answer == "pincode_unknown":
            return "जी, कोई बात नहीं — अगर अभी pin code याद नहीं है तो हम इसे बाद में update कर लेंगे."
        return "जी, समझ गई."

    if next_state == State.CONFIRM_BUSINESS_DETAILS and turn.workflow_answer == "business_details_corrected":
        return "जी, noted. मैं details update कर रही हूँ."

    if previous_state == State.CONFIRM_BUSINESS_DETAILS and next_state == State.VERIFY_EMAIL:
        return "बिल्कुल."

    if next_state == State.CONFIRM_EMAIL_CORRECTION and turn.workflow_answer == "email_corrected":
        return "जी, मैं corrected email confirm कर रही हूँ."

    if previous_state == State.CONFIRM_EMAIL_CORRECTION and next_state == State.ASK_PURCHASE_AMOUNT:
        return "जी, सही कर लिया."

    if previous_state == State.ASK_PURCHASE_AMOUNT and turn.workflow_answer == "purchase_amount_unknown":
        return "ठीक है जी, अगर exact amount याद न हो तो कोई बात नहीं."

    if previous_state == State.ASK_PURCHASE_AMOUNT and next_state == State.SUPPORT_AND_REFERRAL:
        return "अच्छा, noted."

    if previous_state == State.SUPPORT_AND_REFERRAL and next_state == State.COLLECT_REFERRAL_NAME:
        return ""

    return _affect_prefix(turn)


def _expected_slot_for_state(state: State) -> str:
    if state == State.CHECK_AVAILABILITY:
        return "talk_window"
    if state == State.ASK_BILLING_STATUS:
        return "billing_status"
    if state in {State.VERIFY_WHATSAPP, State.COLLECT_WHATSAPP_NUMBER, State.CONFIRM_WHATSAPP_NUMBER}:
        return "whatsapp_number"
    if state in {State.ASK_ALTERNATE_NUMBER, State.COLLECT_ALTERNATE_NUMBER, State.CONFIRM_ALTERNATE_NUMBER}:
        return "alternate_number"
    if state in {State.VERIFY_PINCODE, State.COLLECT_PINCODE, State.CONFIRM_PINCODE}:
        return "pincode"
    if state in {State.VERIFY_BUSINESS_DETAILS, State.CONFIRM_BUSINESS_DETAILS}:
        return "business_details"
    if state in {State.VERIFY_EMAIL, State.COLLECT_EMAIL_CORRECTION, State.CONFIRM_EMAIL_CORRECTION}:
        return "email"
    if state == State.ASK_PURCHASE_AMOUNT:
        return "purchase_amount"
    if state == State.SUPPORT_AND_REFERRAL:
        return "referral_interest"
    if state == State.COLLECT_REFERRAL_NAME:
        return "referral_name"
    if state in {State.COLLECT_REFERRAL_NUMBER, State.CONFIRM_REFERRAL_NUMBER}:
        return "referral_number"
    if state == State.ANSWER_USER_QUERY:
        return "query_resolution"
    if state == State.ASK_CALLBACK_TIME:
        return "callback_time"
    if state in {
        State.PRE_CLOSING,
        State.REFERRAL_DECLINE_NUDGE,
        State.CALLBACK_CLOSING,
        State.INVALID_REGISTRATION,
        State.WARM_CLOSING,
        State.LOG_DISPOSITION,
        State.END,
    }:
        return "none"
    return ""


def _apply_phone_digits(
    session: CallSession,
    transcript: str,
    *,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
    confirm_state: State,
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
            return confirm_state

        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
        return session.current_state

    combined, status = apply_digit_buffer(existing, transcript, total_digits)
    setattr(session, buffer_attr, combined)

    if status == "complete":
        setattr(session, awaiting_attr, True)
        setattr(session, value_attr, "")
        return confirm_state

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
    confirm_state: State,
    label: str,
    total_digits: int,
) -> State:
    if intent == Intent.ASK and not extract_digits(transcript):
        session.collection_followup_prompt = _build_phone_collection_followup(
            session,
            label=label,
            digits=getattr(session, buffer_attr),
            total_digits=total_digits,
            awaiting_confirmation=getattr(session, awaiting_attr),
        )
        return session.current_state

    return _apply_phone_digits(
        session,
        transcript,
        buffer_attr=buffer_attr,
        awaiting_attr=awaiting_attr,
        value_attr=value_attr,
        confirm_state=confirm_state,
        total_digits=total_digits,
    )


def _resolve_phone_confirmation(
    session: CallSession,
    intent: Intent,
    transcript: str,
    *,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
    success_state: State,
    collect_state: State,
    total_digits: int,
) -> State:
    if intent == Intent.AFFIRM:
        confirmed = getattr(session, buffer_attr)
        setattr(session, value_attr, confirmed)
        setattr(session, buffer_attr, "")
        setattr(session, awaiting_attr, False)
        return success_state

    if intent == Intent.DENY and not extract_digits(transcript):
        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
        return collect_state

    if extract_digits(transcript):
        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
        return _apply_phone_digits(
            session,
            transcript,
            buffer_attr=buffer_attr,
            awaiting_attr=awaiting_attr,
            value_attr=value_attr,
            confirm_state=session.current_state,
            total_digits=total_digits,
        )

    return session.current_state


def _prime_phone_collection(
    session: CallSession,
    transcript: str,
    *,
    buffer_attr: str,
    awaiting_attr: str,
    value_attr: str,
    target_state: State,
    confirm_state: State,
    total_digits: int,
) -> State:
    next_state = _apply_phone_digits(
        session,
        transcript,
        buffer_attr=buffer_attr,
        awaiting_attr=awaiting_attr,
        value_attr=value_attr,
        confirm_state=confirm_state,
        total_digits=total_digits,
    )
    if next_state == confirm_state:
        return confirm_state
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
    return State.CONFIRM_PINCODE


def _resolve_pincode_confirmation(session: CallSession, intent: Intent, transcript: str) -> State:
    if intent == Intent.AFFIRM:
        session.pincode = session.pincode_digit_buffer
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return State.VERIFY_BUSINESS_DETAILS

    if intent == Intent.DENY and not extract_digits(transcript):
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return State.COLLECT_PINCODE

    if extract_digits(transcript):
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return _resolve_pincode_collection(session, intent, transcript)

    return State.CONFIRM_PINCODE


def resolve_next_state(
    session: CallSession,
    turn_or_intent: TurnFrame | Intent,
    transcript: str | None = None,
) -> State:
    turn = _ensure_turn_frame(session, turn_or_intent, transcript)
    intent = turn.speech_act
    transcript = turn.transcript
    session.collection_followup_prompt = ""

    if session.current_state == State.END or session.hard_stop_after_closing:
        return State.END

    if len(session.states_visited) >= config.MAX_TOTAL_TRANSITIONS:
        return State.WARM_CLOSING

    if session.current_state not in TERMINAL_OR_AUTO_STATES and turn.callback_request:
        if session.current_state == State.ASK_CALLBACK_TIME:
            return _set_callback_closing(session, transcript)
        if has_specific_callback_phrase(transcript):
            return _set_callback_closing(session, transcript)
        session.callback_requested = True
        session.callback_time_phrase = ""
        session.callback_closing_text = ""
        return State.ASK_CALLBACK_TIME

    if session.current_state == State.ANSWER_USER_QUERY:
        if session.query_resume_embedded and session.resume_state:
            resumed_state = session.resume_state
            resumed_turn = parse_turn(
                session,
                intent,
                transcript,
                state_override=resumed_state,
            )
            original_state = session.current_state
            session.current_state = resumed_state
            try:
                return resolve_next_state(session, resumed_turn, transcript)
            finally:
                session.current_state = original_state
        if turn.query_type != "none":
            session.last_clarification_kind = turn.clarification_kind
            session.last_user_query_type = turn.query_type
            session.last_user_query_text = transcript
            return State.ANSWER_USER_QUERY
        if turn.wants_resume or intent in {Intent.AFFIRM, Intent.THANK}:
            return session.resume_state or State.ASK_BILLING_STATUS
        if intent in {Intent.DENY, Intent.ASK, Intent.REQUEST, Intent.UNCLEAR}:
            return State.ANSWER_USER_QUERY
        return session.resume_state or State.ASK_BILLING_STATUS

    if turn.wants_closure and session.current_state not in TERMINAL_OR_AUTO_STATES:
        return State.WARM_CLOSING

    if _should_interrupt_for_query(session, turn):
        session.resume_state = session.current_state
        session.resume_reason = session.current_state.value
        session.last_user_query_type = turn.query_type
        session.last_user_query_text = transcript
        session.query_resolution_pending = True
        return State.ANSWER_USER_QUERY

    for override_intent, target_state, suppressed_states in GLOBAL_OVERRIDES:
        if intent == override_intent and session.current_state not in suppressed_states:
            if target_state == State.CALLBACK_CLOSING:
                return _set_callback_closing(session, transcript)
            return target_state

    if session.current_state == State.ASK_BILLING_STATUS:
        if turn.workflow_answer == "billing_started":
            session.billing_started = "STARTED"
            session.billing_blocker_reason = ""
            return State.VERIFY_WHATSAPP
        if turn.workflow_answer == "billing_not_started":
            session.billing_started = "NOT_STARTED"
            session.billing_blocker_reason = detect_billing_blocker_reason(transcript)
            session.last_blocker_reason = session.billing_blocker_reason
            if session.billing_blocker_reason != "unknown":
                return State.VERIFY_WHATSAPP
            return State.EXPLORE_BILLING_BLOCKER

    if session.current_state == State.EXPLORE_BILLING_BLOCKER:
        session.billing_blocker_reason = detect_billing_blocker_reason(transcript)
        session.last_blocker_reason = session.billing_blocker_reason
        return State.VERIFY_WHATSAPP

    if session.current_state == State.ASK_CALLBACK_TIME:
        return _set_callback_closing(session, transcript)

    if session.current_state == State.VERIFY_WHATSAPP:
        if turn.workflow_answer == "same_whatsapp":
            return State.ASK_ALTERNATE_NUMBER
        if turn.workflow_answer == "other_whatsapp" and not turn.entities.digits:
            return State.COLLECT_WHATSAPP_NUMBER

    if session.current_state == State.ASK_ALTERNATE_NUMBER:
        if turn.workflow_answer == "no_alternate" or _declines_optional_number(transcript):
            return State.VERIFY_PINCODE
        if turn.workflow_answer == "provide_alternate" and not turn.entities.digits:
            return State.COLLECT_ALTERNATE_NUMBER

    if session.current_state == State.VERIFY_PINCODE and turn.workflow_answer == "pincode_unknown":
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return State.VERIFY_BUSINESS_DETAILS

    if session.current_state == State.VERIFY_PINCODE and extract_digits(transcript):
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return _resolve_pincode_collection(session, intent, transcript)

    if session.current_state == State.VERIFY_PINCODE and turn.workflow_answer == "confirm_existing_pincode":
        return State.VERIFY_BUSINESS_DETAILS

    if session.current_state in PRE_COLLECTION_PHONE_STATES and extract_digits(transcript):
        (
            buffer_attr,
            awaiting_attr,
            value_attr,
            target_state,
            confirm_state,
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
            confirm_state=confirm_state,
            total_digits=total_digits,
        )

    if session.current_state in PHONE_COLLECTION_STATES:
        (
            buffer_attr,
            awaiting_attr,
            value_attr,
            confirm_state,
            label,
            total_digits,
        ) = PHONE_COLLECTION_STATES[
            session.current_state
        ]
        if turn.workflow_answer == "collection_status_request":
            session.collection_followup_prompt = _build_phone_collection_followup(
                session,
                label=label,
                digits=getattr(session, buffer_attr),
                total_digits=total_digits,
                awaiting_confirmation=getattr(session, awaiting_attr),
            )
            return session.current_state
        return _resolve_phone_collection(
            session,
            intent,
            transcript,
            buffer_attr=buffer_attr,
            awaiting_attr=awaiting_attr,
            value_attr=value_attr,
            confirm_state=confirm_state,
            label=label,
            total_digits=total_digits,
        )

    if session.current_state in PHONE_CONFIRMATION_STATES:
        (
            buffer_attr,
            awaiting_attr,
            value_attr,
            success_state,
            collect_state,
            _label,
            total_digits,
        ) = PHONE_CONFIRMATION_STATES[session.current_state]
        return _resolve_phone_confirmation(
            session,
            intent,
            transcript,
            buffer_attr=buffer_attr,
            awaiting_attr=awaiting_attr,
            value_attr=value_attr,
            success_state=success_state,
            collect_state=collect_state,
            total_digits=total_digits,
        )

    if session.current_state == State.COLLECT_PINCODE:
        if turn.workflow_answer == "collection_status_request":
            session.collection_followup_prompt = _build_collection_status_prompt(
                label="pin code",
                digits=session.pincode_digit_buffer,
                total_digits=6,
                awaiting_confirmation=session.awaiting_pincode_confirmation,
            )
            return State.COLLECT_PINCODE
        if turn.workflow_answer == "pincode_unknown":
            session.pincode = ""
            session.pincode_digit_buffer = ""
            session.awaiting_pincode_confirmation = False
            return State.VERIFY_BUSINESS_DETAILS
        return _resolve_pincode_collection(session, intent, transcript)

    if session.current_state == State.CONFIRM_PINCODE:
        if turn.workflow_answer == "pincode_unknown":
            session.pincode = ""
            session.pincode_digit_buffer = ""
            session.awaiting_pincode_confirmation = False
            return State.VERIFY_BUSINESS_DETAILS
        return _resolve_pincode_confirmation(session, intent, transcript)

    if session.current_state == State.VERIFY_BUSINESS_DETAILS:
        if turn.workflow_answer == "business_details_confirmed":
            return State.VERIFY_EMAIL
        if turn.workflow_answer == "business_details_corrected":
            return State.CONFIRM_BUSINESS_DETAILS

    if session.current_state == State.CONFIRM_BUSINESS_DETAILS:
        if turn.workflow_answer == "business_details_confirmed":
            return State.VERIFY_EMAIL
        if turn.workflow_answer == "business_details_corrected":
            return State.CONFIRM_BUSINESS_DETAILS

    if session.current_state == State.VERIFY_EMAIL:
        if turn.workflow_answer == "email_confirmed":
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_corrected":
            return State.CONFIRM_EMAIL_CORRECTION
        if turn.workflow_answer == "email_correction_attempt":
            return State.COLLECT_EMAIL_CORRECTION

    if session.current_state == State.COLLECT_EMAIL_CORRECTION:
        if turn.workflow_answer == "email_corrected":
            return State.CONFIRM_EMAIL_CORRECTION
        return State.COLLECT_EMAIL_CORRECTION

    if session.current_state == State.CONFIRM_EMAIL_CORRECTION:
        if turn.workflow_answer == "email_confirmed":
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_corrected":
            return State.CONFIRM_EMAIL_CORRECTION
        if turn.workflow_answer == "email_correction_attempt":
            return State.COLLECT_EMAIL_CORRECTION

    if session.current_state == State.ASK_PURCHASE_AMOUNT:
        if turn.workflow_answer in {"purchase_amount_provided", "purchase_amount_unknown"}:
            return State.SUPPORT_AND_REFERRAL

    if session.current_state == State.SUPPORT_AND_REFERRAL:
        if turn.workflow_answer == "referral_declined":
            return State.REFERRAL_DECLINE_NUDGE
        if turn.workflow_answer == "referral_accepted":
            if turn.entities.digits:
                return _prime_phone_collection(
                    session,
                    transcript,
                    buffer_attr="referral_digit_buffer",
                    awaiting_attr="awaiting_referral_confirmation",
                    value_attr="referral_number",
                    target_state=State.COLLECT_REFERRAL_NUMBER,
                    confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                    total_digits=10,
                )
            if turn.entities.referral_name:
                return State.COLLECT_REFERRAL_NUMBER
            return State.COLLECT_REFERRAL_NAME

    if session.current_state == State.COLLECT_REFERRAL_NAME:
        if turn.entities.digits:
            return _prime_phone_collection(
                session,
                transcript,
                buffer_attr="referral_digit_buffer",
                awaiting_attr="awaiting_referral_confirmation",
                value_attr="referral_number",
                target_state=State.COLLECT_REFERRAL_NUMBER,
                confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                total_digits=10,
            )
        if turn.workflow_answer == "referral_name_provided":
            return State.COLLECT_REFERRAL_NUMBER
        if intent in {Intent.DENY, Intent.OBJECT, Intent.GOODBYE}:
            return State.PRE_CLOSING

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


def post_transition(
    session: CallSession,
    turn_or_intent: TurnFrame | Intent,
    transcript: str,
    next_state: State,
) -> None:
    turn = _ensure_turn_frame(session, turn_or_intent, transcript)
    intent = turn.speech_act
    previous_state = session.current_state
    effective_previous_state = previous_state
    effective_turn = turn

    if (
        previous_state == State.ANSWER_USER_QUERY
        and session.query_resume_embedded
        and next_state != State.ANSWER_USER_QUERY
        and session.resume_state is not None
    ):
        effective_previous_state = session.resume_state
        effective_turn = parse_turn(
            session,
            intent,
            transcript,
            state_override=effective_previous_state,
        )

    _store_user_turn(session, effective_previous_state, intent, transcript)

    session.last_turn_workflow_answer = effective_turn.workflow_answer
    session.last_user_query_type = turn.query_type
    session.last_clarification_kind = turn.clarification_kind
    if turn.query_type != "none":
        session.last_user_query_text = transcript
    session.affect_state = effective_turn.affect.upper()
    if effective_turn.affect == "disengaged":
        session.user_disengagement_count += 1

    if effective_previous_state == State.EXPLORE_BILLING_BLOCKER:
        session.billing_blocker_reason = detect_billing_blocker_reason(transcript)
        session.last_blocker_reason = session.billing_blocker_reason

    if effective_previous_state in {State.VERIFY_BUSINESS_DETAILS, State.CONFIRM_BUSINESS_DETAILS} and effective_turn.workflow_answer == "business_details_corrected":
        extract_and_store(session, effective_previous_state, transcript)

    if effective_previous_state in EMAIL_STATES and effective_turn.workflow_answer in {"email_correction_attempt", "email_corrected"}:
        if looks_like_email_fragment(transcript):
            reset_buffer = (
                effective_previous_state in {State.VERIFY_EMAIL, State.CONFIRM_EMAIL_CORRECTION}
                or email_fragment_restart_requested(transcript)
            )
            session.email_fragment_buffer = merge_spoken_email_fragments(
                session.email_fragment_buffer,
                transcript,
                reset=reset_buffer,
            )

    if effective_previous_state in {State.VERIFY_EMAIL, State.COLLECT_EMAIL_CORRECTION, State.CONFIRM_EMAIL_CORRECTION} and effective_turn.workflow_answer == "email_corrected":
        extract_and_store(session, effective_previous_state, transcript)

    if effective_previous_state == State.ASK_PURCHASE_AMOUNT and effective_turn.workflow_answer in {
        "purchase_amount_provided",
        "purchase_amount_unknown",
    }:
        extract_and_store(session, effective_previous_state, transcript)

    if effective_previous_state in {
        State.SUPPORT_AND_REFERRAL,
        State.COLLECT_REFERRAL_NAME,
        State.COLLECT_REFERRAL_NUMBER,
        State.CONFIRM_REFERRAL_NUMBER,
    } and intent in {
        Intent.AFFIRM,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.THANK,
        Intent.GREET,
    }:
        extract_and_store(session, effective_previous_state, transcript)

    session.pending_response_prefix = _build_response_prefix(
        session,
        effective_previous_state,
        effective_turn,
        next_state,
    )

    session.busy_but_continuing = False
    if next_state == State.ANSWER_USER_QUERY:
        session.query_resume_embedded = turn.query_type == "clarification" and session.resume_state is not None
        session.dialog_mode = "HANDLE_QUERY"
        session.query_resolution_pending = True
    elif next_state in {
        State.PRE_CLOSING,
        State.REFERRAL_DECLINE_NUDGE,
        State.CALLBACK_CLOSING,
        State.INVALID_REGISTRATION,
        State.WARM_CLOSING,
        State.LOG_DISPOSITION,
        State.END,
    }:
        session.query_resume_embedded = False
        session.dialog_mode = "CLOSE_ONLY"
    elif effective_turn.affect == "frustrated":
        session.query_resume_embedded = False
        session.dialog_mode = "HANDLE_FRUSTRATION"
    elif effective_turn.affect == "complaint":
        session.query_resume_embedded = False
        session.dialog_mode = "HANDLE_COMPLAINT"
    elif effective_turn.affect == "confused":
        session.query_resume_embedded = False
        session.dialog_mode = "HANDLE_CONFUSION"
    elif effective_turn.affect == "hurried":
        session.query_resume_embedded = False
        session.dialog_mode = "HANDLE_HURRY"
        session.busy_but_continuing = True
    elif next_state in {
        State.COLLECT_WHATSAPP_NUMBER,
        State.CONFIRM_WHATSAPP_NUMBER,
        State.COLLECT_ALTERNATE_NUMBER,
        State.CONFIRM_ALTERNATE_NUMBER,
        State.COLLECT_PINCODE,
        State.CONFIRM_PINCODE,
        State.CONFIRM_BUSINESS_DETAILS,
        State.COLLECT_EMAIL_CORRECTION,
        State.CONFIRM_EMAIL_CORRECTION,
        State.COLLECT_REFERRAL_NAME,
        State.COLLECT_REFERRAL_NUMBER,
        State.CONFIRM_REFERRAL_NUMBER,
    }:
        session.query_resume_embedded = False
        session.dialog_mode = "REPAIR_INPUT"
    else:
        session.query_resume_embedded = False
        session.dialog_mode = "NORMAL"

    if next_state == State.ANSWER_USER_QUERY and session.query_resume_embedded and session.resume_state is not None:
        session.expected_slot = _expected_slot_for_state(session.resume_state)
    else:
        session.expected_slot = _expected_slot_for_state(next_state)

    session.business_correction_pending = (
        effective_previous_state in {State.VERIFY_BUSINESS_DETAILS, State.CONFIRM_BUSINESS_DETAILS}
        and effective_turn.workflow_answer == "business_details_corrected"
        and next_state == State.CONFIRM_BUSINESS_DETAILS
    )
    session.email_correction_pending = (
        effective_previous_state in {State.VERIFY_EMAIL, State.COLLECT_EMAIL_CORRECTION, State.CONFIRM_EMAIL_CORRECTION}
        and effective_turn.workflow_answer in {"email_corrected", "email_correction_attempt"}
        and next_state in {State.COLLECT_EMAIL_CORRECTION, State.CONFIRM_EMAIL_CORRECTION}
    )
    if next_state == State.REFERRAL_DECLINE_NUDGE:
        session.referral_declined_once = True

    if previous_state == State.ANSWER_USER_QUERY and next_state != State.ANSWER_USER_QUERY:
        session.dialog_mode = "NORMAL"
        session.query_resolution_pending = False
        session.resume_state = None
        session.resume_reason = ""
        session.last_clarification_kind = "none"
        session.query_resume_embedded = False

    session.previous_state = effective_previous_state
    session.current_state = next_state
    session.states_visited.append(next_state)

    if effective_previous_state in EMAIL_STATES and next_state not in EMAIL_STATES and next_state != State.ANSWER_USER_QUERY:
        session.email_fragment_buffer = ""

    if next_state != effective_previous_state:
        session.fallback_count = 0


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
