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
    extract_name_fragment,
    has_specific_callback_phrase,
    has_callback_request,
    looks_like_email_fragment,
    merge_spoken_email_fragments,
)

from .actions import ACTION_MAP
from .intents import Intent
from .session import CallSession
from .states import State
from .turn_parser import TurnFrame, detect_prompt_exception_reason, parse_turn
from .transitions import AUTO_TRANSITIONS, GLOBAL_OVERRIDES, TRANSITIONS

TERMINAL_OR_AUTO_STATES = {
    State.PRE_CLOSING,
    State.REFERRAL_DECLINE_NUDGE,
    State.CALLBACK_CLOSING,
    State.INVALID_REGISTRATION,
    State.WARM_CLOSING,
    State.FIXED_CLOSING,
    State.LOG_DISPOSITION,
    State.END,
}

PHONE_COLLECTION_STATES: dict[State, tuple[str, str, str, State, str, int]] = {
    State.COLLECT_CONCERNED_PERSON_NUMBER: (
        "concerned_person_digit_buffer",
        "awaiting_concerned_person_confirmation",
        "concerned_person_number",
        State.CONFIRM_CONCERNED_PERSON_NUMBER,
        "concerned person contact number",
        10,
    ),
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
    State.ASK_CONCERNED_PERSON_CONTACT: (
        "concerned_person_digit_buffer",
        "awaiting_concerned_person_confirmation",
        "concerned_person_number",
        State.COLLECT_CONCERNED_PERSON_NUMBER,
        State.CONFIRM_CONCERNED_PERSON_NUMBER,
        "concerned person contact number",
        10,
    ),
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
    session.fixed_closing_variant = "standard"
    session.terminal_ack_text = ""
    session.callback_prompt_override = ""
    session.callback_time_attempts = 0
    if session.current_state == State.ASK_CALLBACK_TIME:
        session.callback_time_phrase = extract_callback_phrase(transcript)
        session.callback_closing_text = build_callback_closing(session.callback_time_phrase)
    else:
        session.callback_time_phrase = extract_callback_phrase(transcript)
        session.callback_closing_text = build_callback_closing(transcript)
    return State.CALLBACK_CLOSING


def _set_callback_confirmation(session: CallSession, transcript: str) -> State:
    session.callback_requested = True
    session.fixed_closing_variant = "standard"
    session.terminal_ack_text = ""
    session.callback_prompt_override = ""
    session.callback_time_attempts = 0
    session.callback_time_phrase = extract_callback_phrase(transcript) or session.callback_time_phrase or "थोड़ी देर बाद"
    session.callback_closing_text = build_callback_closing(session.callback_time_phrase)
    return State.CONFIRM_CALLBACK_TIME


def _start_callback_scheduling(
    session: CallSession,
    prompt_override: str = "",
    *,
    resume_state: State | None = None,
) -> State:
    session.callback_requested = True
    session.fixed_closing_variant = "standard"
    session.terminal_ack_text = ""
    session.callback_time_phrase = ""
    session.callback_closing_text = ""
    session.callback_prompt_override = prompt_override
    session.callback_time_attempts = 0
    session.callback_resume_state = resume_state
    return State.ASK_CALLBACK_TIME


def _close_with_generic_callback(session: CallSession) -> State:
    session.callback_requested = True
    session.fixed_closing_variant = "standard"
    session.terminal_ack_text = ""
    session.callback_time_phrase = "थोड़ी देर बाद"
    session.callback_closing_text = build_callback_closing("")
    session.callback_prompt_override = ""
    session.callback_time_attempts = 0
    return State.CALLBACK_CLOSING


def _close_with_acknowledgement(
    session: CallSession,
    target_state: State,
    acknowledgement: str,
) -> State:
    session.terminal_ack_text = " ".join(acknowledgement.strip().split())
    session.fixed_closing_variant = (
        "alternate"
        if target_state in {State.INVALID_REGISTRATION, State.WARM_CLOSING}
        else "standard"
    )
    return target_state


def _resolve_prompt_exception_reason(transcript: str) -> str:
    return detect_prompt_exception_reason(transcript)


def _resume_after_detour(session: CallSession) -> State:
    return session.billing_resume_state or State.VERIFY_WHATSAPP


def _route_billing_exception(session: CallSession, transcript: str, *, from_complaint: bool = False) -> State:
    reason = _resolve_prompt_exception_reason(transcript)
    if reason == "unknown" and from_complaint:
        return State.COLLECT_COMPLAINT_DETAIL

    session.billing_blocker_reason = reason
    session.last_blocker_reason = reason
    session.billing_resume_state = State.VERIFY_WHATSAPP

    if reason == "abusive_language":
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "जी, मैं आपकी बात note कर रही हूँ. हमारी team आपसे जल्द contact करेगी।",
        )
    if reason == "partner_non_responsive":
        session.blocker_owner = "partner"
        return State.ESCALATE_PAYMENT_DATE
    if reason == "switched_software":
        session.blocker_owner = "customer"
        return State.ESCALATE_SWITCHED_SOFTWARE
    if reason == "business_closed":
        session.blocker_owner = "customer"
        return State.ESCALATE_CLOSURE_REASON
    if reason in {"training_pending", "dealer_setup"}:
        session.blocker_owner = "partner"
        return State.COLLECT_TRAINING_PINCODE
    if reason == "technical_issue":
        session.blocker_owner = "support"
        if from_complaint:
            session.technical_issue_detail = transcript.strip()
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, issue note कर लिया है. Marg Help और Ticket option available हैं. हमारी team 24 घंटों के अंदर contact करेगी।",
            )
        return State.ESCALATE_TECHNICAL_ISSUE
    if reason in {"migration_delay", "setup_in_progress", "no_time"}:
        session.blocker_owner = "customer"
        return State.ASK_BILLING_START_TIMELINE
    return State.EXPLORE_BILLING_BLOCKER


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


def _turn_phone_digits(turn: TurnFrame) -> str:
    if turn.entities.phone_digits:
        return turn.entities.phone_digits
    if turn.entities.pincode_digits:
        return ""
    return turn.entities.digits


def _turn_pincode_digits(turn: TurnFrame) -> str:
    if turn.entities.pincode_digits:
        return turn.entities.pincode_digits
    if turn.entities.phone_digits:
        return ""
    return turn.entities.digits


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
    if turn.workflow_answer == "audio_check":
        return False
    if session.current_state in {
        State.COLLECT_COMPLAINT_DETAIL,
        State.ESCALATE_PAYMENT_DATE,
        State.ESCALATE_PARTNER_NAME,
        State.ESCALATE_SWITCHED_SOFTWARE,
        State.ESCALATE_SWITCH_REASON,
        State.ESCALATE_CLOSURE_REASON,
        State.ESCALATE_TECHNICAL_ISSUE,
        State.COLLECT_TRAINING_PINCODE,
        State.ASK_BILLING_START_TIMELINE,
        State.DETOUR_ANYTHING_ELSE,
    } and turn.workflow_answer not in {"unknown", "user_query"}:
        return False
    if session.current_state == State.ANSWER_USER_QUERY:
        return False
    if session.current_state == State.ASK_BILLING_STATUS and turn.workflow_answer in {"billing_started", "billing_not_started"}:
        return False
    if session.current_state == State.ASK_PURCHASE_AMOUNT and turn.workflow_answer in {
        "purchase_amount_provided",
        "purchase_amount_unknown",
        "purchase_amount_refused",
    }:
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
    if turn.workflow_answer == "audio_check":
        return "हाँ जी, मुझे आपकी आवाज़ आ रही है।"

    if next_state == State.ANSWER_USER_QUERY:
        return ""

    if next_state in {
        State.ASK_WRONG_CONTACT_COMPANY,
        State.ASK_WRONG_CONTACT_TRADE,
        State.ASK_WRONG_CONTACT_TYPE,
        State.ASK_WRONG_CONTACT_NAME,
        State.ASK_CONCERNED_PERSON_CONTACT,
        State.COLLECT_CONCERNED_PERSON_NUMBER,
        State.CONFIRM_CONCERNED_PERSON_NUMBER,
        State.COLLECT_COMPLAINT_DETAIL,
        State.ESCALATE_PAYMENT_DATE,
        State.ESCALATE_PARTNER_NAME,
        State.ESCALATE_SWITCHED_SOFTWARE,
        State.ESCALATE_SWITCH_REASON,
        State.ESCALATE_CLOSURE_REASON,
        State.ESCALATE_TECHNICAL_ISSUE,
        State.COLLECT_TRAINING_PINCODE,
        State.BUSY_NUDGE,
        State.ASK_CALLBACK_TIME,
        State.CONFIRM_CALLBACK_TIME,
        State.CALLBACK_CLOSING,
        State.INVALID_REGISTRATION,
        State.WARM_CLOSING,
        State.FIXED_CLOSING,
        State.END,
    }:
        return ""

    if previous_state == State.ANSWER_USER_QUERY and next_state != State.ANSWER_USER_QUERY:
        return "ठीक है जी — तो मैं वापस आती हूँ जहाँ हम थे."

    if previous_state in {State.OPENING_GREETING, State.CONFIRM_IDENTITY} and next_state == State.CHECK_AVAILABILITY:
        return ""

    if previous_state == State.CHECK_AVAILABILITY and next_state == State.ASK_BILLING_STATUS:
        return ""

    if previous_state == State.ASK_BILLING_STATUS and next_state == State.VERIFY_WHATSAPP:
        if turn.workflow_answer == "billing_started":
            return "ये तो अच्छी बात है."
        return build_billing_blocker_support_prefix(session)

    if previous_state == State.EXPLORE_BILLING_BLOCKER and next_state == State.VERIFY_WHATSAPP:
        return build_billing_blocker_support_prefix(session)

    if previous_state == State.EXPLORE_BILLING_BLOCKER and next_state == State.ASK_BILLING_START_TIMELINE:
        if session.billing_blocker_refusal_count > 2:
            return "कोई बात नहीं जी, शायद आपकी अभी planning चल रही हो."
        return "जी, समझ गई."

    if previous_state == State.ASK_BILLING_START_TIMELINE and next_state == State.DETOUR_ANYTHING_ELSE:
        if session.billing_blocker_reason and session.billing_blocker_reason != "unknown":
            return build_billing_blocker_support_prefix(session)
        return "जी, समझ गई."

    if previous_state == State.COLLECT_TRAINING_PINCODE and next_state == State.DETOUR_ANYTHING_ELSE:
        return build_billing_blocker_support_prefix(session)

    if previous_state == State.DETOUR_ANYTHING_ELSE and next_state == State.VERIFY_WHATSAPP:
        return "ठीक है जी — तो मैं verification continue करती हूँ."

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

    if previous_state in EMAIL_STATES and next_state == State.ASK_PURCHASE_AMOUNT and turn.workflow_answer == "email_refused":
        return "कोई बात नहीं जी, मैं इसे skip कर देती हूँ."

    if previous_state == State.ASK_PURCHASE_AMOUNT and turn.workflow_answer == "purchase_amount_unknown":
        return "ठीक है जी, अगर exact amount याद न हो तो कोई बात नहीं."

    if previous_state == State.ASK_PURCHASE_AMOUNT and next_state == State.SUPPORT_AND_REFERRAL and turn.workflow_answer == "purchase_amount_refused":
        return "कोई बात नहीं जी, मैं इसे skip कर देती हूँ."

    if previous_state == State.ASK_PURCHASE_AMOUNT and next_state == State.SUPPORT_AND_REFERRAL:
        return "अच्छा, noted."

    if previous_state == State.SUPPORT_AND_REFERRAL and next_state == State.COLLECT_REFERRAL_NAME:
        return ""

    return _affect_prefix(turn)


def _expected_slot_for_state(state: State) -> str:
    if state == State.CHECK_AVAILABILITY:
        return "talk_window"
    if state == State.ASK_WRONG_CONTACT_COMPANY:
        return "wrong_contact_company"
    if state == State.ASK_WRONG_CONTACT_TRADE:
        return "wrong_contact_trade"
    if state == State.ASK_WRONG_CONTACT_TYPE:
        return "wrong_contact_type"
    if state == State.ASK_WRONG_CONTACT_NAME:
        return "wrong_contact_name"
    if state in {State.ASK_CONCERNED_PERSON_CONTACT, State.COLLECT_CONCERNED_PERSON_NUMBER, State.CONFIRM_CONCERNED_PERSON_NUMBER}:
        return "concerned_person_contact"
    if state == State.ASK_BILLING_STATUS:
        return "billing_status"
    if state == State.COLLECT_COMPLAINT_DETAIL:
        return "complaint_detail"
    if state == State.ESCALATE_PAYMENT_DATE:
        return "payment_date"
    if state == State.ESCALATE_PARTNER_NAME:
        return "partner_name"
    if state == State.ESCALATE_SWITCHED_SOFTWARE:
        return "switched_software"
    if state == State.ESCALATE_SWITCH_REASON:
        return "switch_reason"
    if state == State.ESCALATE_CLOSURE_REASON:
        return "closure_reason"
    if state == State.ESCALATE_TECHNICAL_ISSUE:
        return "technical_issue"
    if state == State.COLLECT_TRAINING_PINCODE:
        return "training_pincode"
    if state in {State.EXPLORE_BILLING_BLOCKER, State.ASK_BILLING_START_TIMELINE}:
        return "billing_blocker"
    if state == State.DETOUR_ANYTHING_ELSE:
        return "detour_followup"
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
    if state in {State.BUSY_NUDGE}:
        return "talk_window"
    if state in {State.ASK_CALLBACK_TIME, State.CONFIRM_CALLBACK_TIME}:
        return "callback_time"
    if state in {
        State.PRE_CLOSING,
        State.REFERRAL_DECLINE_NUDGE,
        State.CALLBACK_CLOSING,
        State.INVALID_REGISTRATION,
        State.WARM_CLOSING,
        State.FIXED_CLOSING,
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
    digits_override: str | None = None,
) -> State:
    existing = getattr(session, buffer_attr)
    fresh_digits = digits_override if digits_override is not None else extract_digits(transcript)

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
    digits_override: str | None = None,
) -> State:
    if intent == Intent.ASK and not (digits_override if digits_override is not None else extract_digits(transcript)):
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
        digits_override=digits_override,
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
    digits_override: str | None = None,
) -> State:
    if intent == Intent.AFFIRM:
        confirmed = getattr(session, buffer_attr)
        setattr(session, value_attr, confirmed)
        setattr(session, buffer_attr, "")
        setattr(session, awaiting_attr, False)
        return success_state

    if intent == Intent.DENY and not (digits_override if digits_override is not None else extract_digits(transcript)):
        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
        return collect_state

    if digits_override if digits_override is not None else extract_digits(transcript):
        _reset_phone_collection(session, buffer_attr, awaiting_attr, value_attr)
        return _apply_phone_digits(
            session,
            transcript,
            buffer_attr=buffer_attr,
            awaiting_attr=awaiting_attr,
            value_attr=value_attr,
            confirm_state=session.current_state,
            total_digits=total_digits,
            digits_override=digits_override,
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
    digits_override: str | None = None,
) -> State:
    next_state = _apply_phone_digits(
        session,
        transcript,
        buffer_attr=buffer_attr,
        awaiting_attr=awaiting_attr,
        value_attr=value_attr,
        confirm_state=confirm_state,
        total_digits=total_digits,
        digits_override=digits_override,
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
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "जी, शायद अभी call properly complete नहीं हो पा रही, इसलिए मैं call यहीं close करती हूँ।",
        )

    if turn.workflow_answer == "audio_check":
        return session.current_state

    if _resolve_prompt_exception_reason(transcript) == "abusive_language" and session.current_state not in TERMINAL_OR_AUTO_STATES:
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "जी, मैं आपकी बात note कर रही हूँ. हमारी team आपसे जल्द contact करेगी।",
        )

    if intent == Intent.ESCALATE and session.current_state not in TERMINAL_OR_AUTO_STATES:
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "जी, आपकी बात note कर ली है. हमारी team आपसे जल्द contact करेगी।",
        )

    if session.current_state in {State.OPENING_GREETING, State.CONFIRM_IDENTITY, State.CHECK_AVAILABILITY}:
        if turn.workflow_answer == "opening_wrong_registration":
            return State.ASK_WRONG_CONTACT_COMPANY
        if turn.workflow_answer == "contact_unavailable":
            return _start_callback_scheduling(
                session,
                prompt_override=(
                    "जी, धन्यवाद बताने के लिए. क्या मैं उनसे बात करने के लिए कोई convenient time note कर लूँ?"
                ),
                resume_state=session.current_state,
            )

    if session.current_state == State.ASK_WRONG_CONTACT_COMPANY:
        if turn.workflow_answer == "wrong_contact_company_provided":
            return State.ASK_WRONG_CONTACT_TRADE
        return State.ASK_WRONG_CONTACT_COMPANY

    if session.current_state == State.ASK_WRONG_CONTACT_TRADE:
        if turn.workflow_answer == "wrong_contact_trade_provided":
            return State.ASK_WRONG_CONTACT_TYPE
        return State.ASK_WRONG_CONTACT_TRADE

    if session.current_state == State.ASK_WRONG_CONTACT_TYPE:
        if turn.workflow_answer == "wrong_contact_type_provided":
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, जानकारी देने के लिए धन्यवाद. हम अपने records update कर देंगे।",
            )
        return State.ASK_WRONG_CONTACT_TYPE

    if session.current_state == State.ASK_WRONG_CONTACT_NAME:
        if turn.workflow_answer == "wrong_contact_name_provided":
            name = extract_name_fragment(transcript)
            acknowledgement = "जी, आपका बहुत धन्यवाद। हम अपने records में update कर देंगे।"
            if name:
                acknowledgement = f"जी {name}, आपका बहुत धन्यवाद। हम अपने records में update कर देंगे।"
            return _close_with_acknowledgement(session, State.WARM_CLOSING, acknowledgement)
        return State.ASK_WRONG_CONTACT_NAME

    if (
        turn.workflow_answer == "concerned_person_redirect"
        and session.current_state not in TERMINAL_OR_AUTO_STATES
        and session.current_state not in {State.ASK_CALLBACK_TIME, State.CONFIRM_CALLBACK_TIME}
    ):
        return State.ASK_CONCERNED_PERSON_CONTACT

    if session.current_state == State.ASK_CONCERNED_PERSON_CONTACT:
        phone_digits = _turn_phone_digits(turn)
        if turn.workflow_answer == "concerned_person_number_provided" and phone_digits:
            return _prime_phone_collection(
                session,
                transcript,
                buffer_attr="concerned_person_digit_buffer",
                awaiting_attr="awaiting_concerned_person_confirmation",
                value_attr="concerned_person_number",
                target_state=State.COLLECT_CONCERNED_PERSON_NUMBER,
                confirm_state=State.CONFIRM_CONCERNED_PERSON_NUMBER,
                total_digits=10,
                digits_override=phone_digits,
            )
        if turn.workflow_answer == "concerned_person_same_number" or turn.callback_request:
            return _start_callback_scheduling(
                session,
                prompt_override=(
                    "जी, ठीक है. उनसे बात करने के लिए किस time या किस slot में call करना convenient रहेगा?"
                ),
                resume_state=State.ASK_CONCERNED_PERSON_CONTACT,
            )
        return State.ASK_CONCERNED_PERSON_CONTACT

    if (
        session.current_state not in TERMINAL_OR_AUTO_STATES
        and session.current_state not in {State.BUSY_NUDGE, State.ASK_CALLBACK_TIME, State.CONFIRM_CALLBACK_TIME}
        and turn.callback_request
    ):
        session.callback_resume_state = session.current_state
        return State.BUSY_NUDGE

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
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "जी, ठीक है — अगर अभी आप आगे continue नहीं करना चाहते, तो मैं call यहीं close करती हूँ।",
        )

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
            if target_state == State.WARM_CLOSING:
                return _close_with_acknowledgement(
                    session,
                    target_state,
                    "जी, ठीक है — मैं call यहीं close करती हूँ।",
                )
            if target_state == State.BUSY_NUDGE:
                session.callback_resume_state = session.current_state
            return target_state

    if session.current_state == State.ASK_BILLING_STATUS:
        if turn.workflow_answer == "billing_started":
            session.billing_started = "STARTED"
            session.billing_blocker_reason = ""
            session.billing_blocker_refusal_count = 0
            session.billing_resume_state = None
            return State.VERIFY_WHATSAPP
        if turn.workflow_answer == "billing_not_started":
            session.billing_started = "NOT_STARTED"
            session.billing_blocker_refusal_count = 0
            return _route_billing_exception(
                session,
                transcript,
                from_complaint=intent == Intent.COMPLAIN,
            )

    if session.current_state == State.COLLECT_COMPLAINT_DETAIL:
        if turn.workflow_answer == "complaint_detail_provided":
            return _route_billing_exception(session, transcript, from_complaint=True)
        return State.COLLECT_COMPLAINT_DETAIL

    if session.current_state == State.EXPLORE_BILLING_BLOCKER:
        if intent == Intent.GOODBYE:
            return _close_with_acknowledgement(session, State.WARM_CLOSING, "जी, ठीक है — मैं call यहीं close करती हूँ।")
        if turn.workflow_answer == "billing_blocker_refused":
            session.billing_blocker_refusal_count += 1
            if session.billing_blocker_refusal_count <= 2:
                return State.EXPLORE_BILLING_BLOCKER
            return State.ASK_BILLING_START_TIMELINE
        session.billing_blocker_refusal_count = 0
        return _route_billing_exception(session, transcript, from_complaint=intent == Intent.COMPLAIN)

    if session.current_state == State.ESCALATE_PAYMENT_DATE:
        if turn.workflow_answer == "payment_date_provided":
            return State.ESCALATE_PARTNER_NAME
        return State.ESCALATE_PAYMENT_DATE

    if session.current_state == State.ESCALATE_PARTNER_NAME:
        if turn.workflow_answer == "partner_name_provided":
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, payment detail और partner detail note कर ली है. हम partner से contact करेंगे. 20 से 48 घंटों के अंदर update मिल जाना चाहिए।",
            )
        return State.ESCALATE_PARTNER_NAME

    if session.current_state == State.ESCALATE_SWITCHED_SOFTWARE:
        if turn.workflow_answer == "switched_software_provided":
            return State.ESCALATE_SWITCH_REASON
        return State.ESCALATE_SWITCHED_SOFTWARE

    if session.current_state == State.ESCALATE_SWITCH_REASON:
        if turn.workflow_answer == "switch_reason_provided":
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, आपने जो feedback दिया वह मैंने note कर लिया है।",
            )
        return State.ESCALATE_SWITCH_REASON

    if session.current_state == State.ESCALATE_CLOSURE_REASON:
        if turn.workflow_answer == "closure_reason_provided":
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, आपने जो feedback दिया वह मैंने note कर लिया है।",
            )
        return State.ESCALATE_CLOSURE_REASON

    if session.current_state == State.ESCALATE_TECHNICAL_ISSUE:
        if turn.workflow_answer == "technical_issue_detail_provided":
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, issue note कर लिया है. Marg Help और Ticket option available हैं. हमारी team 24 घंटों के अंदर contact करेगी।",
            )
        return State.ESCALATE_TECHNICAL_ISSUE

    if session.current_state == State.COLLECT_TRAINING_PINCODE:
        if turn.workflow_answer == "training_pincode_provided":
            return State.DETOUR_ANYTHING_ELSE
        return State.COLLECT_TRAINING_PINCODE

    if session.current_state == State.ASK_BILLING_START_TIMELINE:
        if intent == Intent.GOODBYE:
            return _close_with_acknowledgement(session, State.WARM_CLOSING, "जी, ठीक है — मैं call यहीं close करती हूँ।")
        if turn.workflow_answer == "billing_timeline_provided":
            return State.DETOUR_ANYTHING_ELSE
        return State.ASK_BILLING_START_TIMELINE

    if session.current_state == State.DETOUR_ANYTHING_ELSE:
        if intent == Intent.GOODBYE:
            return _close_with_acknowledgement(session, State.WARM_CLOSING, "जी, ठीक है — मैं call यहीं close करती हूँ।")
        return _resume_after_detour(session)

    if session.current_state == State.BUSY_NUDGE:
        if intent == Intent.GOODBYE:
            return _close_with_acknowledgement(session, State.WARM_CLOSING, "जी, ठीक है — मैं call यहीं close करती हूँ।")
        if has_specific_callback_phrase(transcript):
            return _set_callback_confirmation(session, transcript)
        if turn.callback_request or intent in {Intent.DENY, Intent.OBJECT, Intent.DEFER}:
            session.busy_refusal_count += 1
            return _start_callback_scheduling(
                session,
                resume_state=session.callback_resume_state or session.current_state,
            )
        if session.callback_resume_state == State.CHECK_AVAILABILITY:
            return State.ASK_BILLING_STATUS
        return session.callback_resume_state or State.ASK_BILLING_STATUS

    if session.current_state == State.ASK_CALLBACK_TIME:
        if intent == Intent.GOODBYE:
            return _close_with_acknowledgement(session, State.WARM_CLOSING, "जी, ठीक है — मैं call यहीं close करती हूँ।")
        if has_specific_callback_phrase(transcript):
            return _set_callback_confirmation(session, transcript)
        if session.callback_time_attempts < 1:
            session.callback_time_attempts += 1
            session.callback_prompt_override = ""
            return State.ASK_CALLBACK_TIME
        return _close_with_generic_callback(session)

    if session.current_state == State.CONFIRM_CALLBACK_TIME:
        if intent == Intent.GOODBYE:
            return _close_with_acknowledgement(session, State.WARM_CLOSING, "जी, ठीक है — मैं call यहीं close करती हूँ।")
        if turn.workflow_answer == "callback_time_confirmed":
            return State.FIXED_CLOSING
        if turn.workflow_answer == "callback_time_updated" and has_specific_callback_phrase(transcript):
            return _set_callback_confirmation(session, transcript)
        return State.ASK_CALLBACK_TIME

    if session.current_state == State.VERIFY_WHATSAPP:
        if turn.workflow_answer == "same_whatsapp":
            if not session.whatsapp_number:
                session.whatsapp_number = session.primary_phone or session.whatsapp_digit_buffer
            return State.ASK_ALTERNATE_NUMBER
        if turn.workflow_answer == "other_whatsapp" and not _turn_phone_digits(turn):
            return State.COLLECT_WHATSAPP_NUMBER

    if session.current_state == State.ASK_ALTERNATE_NUMBER:
        if turn.workflow_answer == "same_as_whatsapp":
            session.alternate_number = session.whatsapp_number or session.whatsapp_digit_buffer or session.primary_phone
            session.alternate_digit_buffer = ""
            session.awaiting_alternate_confirmation = False
            return State.VERIFY_PINCODE
        if turn.workflow_answer == "no_alternate" or _declines_optional_number(transcript):
            return State.VERIFY_PINCODE
        if turn.workflow_answer == "provide_alternate" and not _turn_phone_digits(turn):
            return State.COLLECT_ALTERNATE_NUMBER

    if session.current_state == State.VERIFY_PINCODE and turn.workflow_answer == "pincode_unknown":
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return State.VERIFY_BUSINESS_DETAILS

    if session.current_state == State.VERIFY_PINCODE and _turn_pincode_digits(turn):
        session.pincode = ""
        session.pincode_digit_buffer = ""
        session.awaiting_pincode_confirmation = False
        return _resolve_pincode_collection(session, intent, _turn_pincode_digits(turn))

    if session.current_state == State.VERIFY_PINCODE and turn.workflow_answer == "confirm_existing_pincode":
        return State.VERIFY_BUSINESS_DETAILS

    if session.current_state in PRE_COLLECTION_PHONE_STATES and _turn_phone_digits(turn):
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
            digits_override=_turn_phone_digits(turn),
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
        phone_digits = _turn_phone_digits(turn)
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
            digits_override=phone_digits,
        )

    if session.current_state == State.CONFIRM_CONCERNED_PERSON_NUMBER:
        if intent == Intent.AFFIRM:
            session.concerned_person_number = session.concerned_person_digit_buffer
            session.concerned_person_digit_buffer = ""
            session.awaiting_concerned_person_confirmation = False
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "जी, ठीक है. मैं इसी detail पर software संभालने वाले person से बात करने की कोशिश करूँगी।",
            )

        phone_digits = _turn_phone_digits(turn)
        if intent == Intent.DENY and not phone_digits:
            _reset_phone_collection(
                session,
                "concerned_person_digit_buffer",
                "awaiting_concerned_person_confirmation",
                "concerned_person_number",
            )
            return State.COLLECT_CONCERNED_PERSON_NUMBER

        if phone_digits:
            _reset_phone_collection(
                session,
                "concerned_person_digit_buffer",
                "awaiting_concerned_person_confirmation",
                "concerned_person_number",
            )
            return _apply_phone_digits(
                session,
                transcript,
                buffer_attr="concerned_person_digit_buffer",
                awaiting_attr="awaiting_concerned_person_confirmation",
                value_attr="concerned_person_number",
                confirm_state=session.current_state,
                total_digits=10,
                digits_override=phone_digits,
            )

        return session.current_state

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
            digits_override=_turn_phone_digits(turn),
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
        return _resolve_pincode_collection(session, intent, _turn_pincode_digits(turn) or transcript)

    if session.current_state == State.CONFIRM_PINCODE:
        if turn.workflow_answer == "pincode_unknown":
            session.pincode = ""
            session.pincode_digit_buffer = ""
            session.awaiting_pincode_confirmation = False
            return State.VERIFY_BUSINESS_DETAILS
        return _resolve_pincode_confirmation(session, intent, _turn_pincode_digits(turn) or transcript)

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
        if turn.workflow_answer == "email_refused":
            session.email_refusal_count += 1
            if session.email_refusal_count <= 2:
                return State.COLLECT_EMAIL_CORRECTION
            session.email_refusal_count = 0
            session.email_fragment_buffer = ""
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_confirmed":
            session.email_refusal_count = 0
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_corrected":
            session.email_refusal_count = 0
            return State.CONFIRM_EMAIL_CORRECTION
        if turn.workflow_answer == "email_correction_attempt":
            return State.COLLECT_EMAIL_CORRECTION

    if session.current_state == State.COLLECT_EMAIL_CORRECTION:
        if turn.workflow_answer == "email_refused":
            session.email_refusal_count += 1
            if session.email_refusal_count <= 2:
                return State.COLLECT_EMAIL_CORRECTION
            session.email_refusal_count = 0
            session.email_fragment_buffer = ""
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_corrected":
            session.email_refusal_count = 0
            return State.CONFIRM_EMAIL_CORRECTION
        return State.COLLECT_EMAIL_CORRECTION

    if session.current_state == State.CONFIRM_EMAIL_CORRECTION:
        if turn.workflow_answer == "email_refused":
            session.email_refusal_count += 1
            if session.email_refusal_count <= 2:
                return State.COLLECT_EMAIL_CORRECTION
            session.email_refusal_count = 0
            session.email_fragment_buffer = ""
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_confirmed":
            session.email_refusal_count = 0
            return State.ASK_PURCHASE_AMOUNT
        if turn.workflow_answer == "email_corrected":
            session.email_refusal_count = 0
            return State.CONFIRM_EMAIL_CORRECTION
        if turn.workflow_answer == "email_correction_attempt":
            return State.COLLECT_EMAIL_CORRECTION

    if session.current_state == State.ASK_PURCHASE_AMOUNT:
        if turn.workflow_answer == "purchase_amount_refused":
            session.purchase_amount_refusal_count += 1
            if session.purchase_amount_refusal_count <= 1:
                return State.ASK_PURCHASE_AMOUNT
            session.purchase_amount_refusal_count = 0
            return State.SUPPORT_AND_REFERRAL
        if turn.workflow_answer in {"purchase_amount_provided", "purchase_amount_unknown"}:
            session.purchase_amount_refusal_count = 0
            return State.SUPPORT_AND_REFERRAL

    if session.current_state == State.SUPPORT_AND_REFERRAL:
        if turn.workflow_answer == "referral_declined":
            session.referral_resume_state = State.SUPPORT_AND_REFERRAL
            session.referral_refusal_count = 1
            return State.REFERRAL_DECLINE_NUDGE
        if turn.workflow_answer == "referral_accepted":
            session.referral_refusal_count = 0
            if _turn_phone_digits(turn):
                return _prime_phone_collection(
                    session,
                    transcript,
                    buffer_attr="referral_digit_buffer",
                    awaiting_attr="awaiting_referral_confirmation",
                    value_attr="referral_number",
                    target_state=State.COLLECT_REFERRAL_NUMBER,
                    confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                    total_digits=10,
                    digits_override=_turn_phone_digits(turn),
                )
            if turn.entities.referral_name:
                return State.COLLECT_REFERRAL_NUMBER
            return State.COLLECT_REFERRAL_NAME

    if session.current_state == State.COLLECT_REFERRAL_NAME:
        if turn.workflow_answer == "referral_refused":
            session.referral_resume_state = State.COLLECT_REFERRAL_NAME
            session.referral_refusal_count += 1
            if session.referral_refusal_count <= 2:
                return State.REFERRAL_DECLINE_NUDGE
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "कोई बात नहीं जी, शायद अभी suitable time नहीं है।",
            )
        if _turn_phone_digits(turn):
            return _prime_phone_collection(
                session,
                transcript,
                buffer_attr="referral_digit_buffer",
                awaiting_attr="awaiting_referral_confirmation",
                value_attr="referral_number",
                target_state=State.COLLECT_REFERRAL_NUMBER,
                confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                total_digits=10,
                digits_override=_turn_phone_digits(turn),
            )
        if turn.workflow_answer == "referral_name_provided":
            session.referral_refusal_count = 0
            return State.COLLECT_REFERRAL_NUMBER
        if intent in {Intent.DENY, Intent.OBJECT, Intent.GOODBYE}:
            return State.PRE_CLOSING

    if session.current_state == State.COLLECT_REFERRAL_NUMBER and turn.workflow_answer == "referral_refused":
        session.referral_resume_state = State.COLLECT_REFERRAL_NUMBER
        session.referral_refusal_count += 1
        if session.referral_refusal_count <= 2:
            return State.REFERRAL_DECLINE_NUDGE
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "कोई बात नहीं जी, शायद अभी suitable time नहीं है।",
        )

    if session.current_state == State.REFERRAL_DECLINE_NUDGE:
        if turn.workflow_answer == "referral_accepted":
            resume_state = session.referral_resume_state or State.SUPPORT_AND_REFERRAL
            if resume_state == State.SUPPORT_AND_REFERRAL:
                session.referral_refusal_count = 0
                if _turn_phone_digits(turn):
                    return _prime_phone_collection(
                        session,
                        transcript,
                        buffer_attr="referral_digit_buffer",
                        awaiting_attr="awaiting_referral_confirmation",
                        value_attr="referral_number",
                        target_state=State.COLLECT_REFERRAL_NUMBER,
                        confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                        total_digits=10,
                        digits_override=_turn_phone_digits(turn),
                    )
                if turn.entities.referral_name:
                    return State.COLLECT_REFERRAL_NUMBER
                return State.COLLECT_REFERRAL_NAME
            if resume_state == State.COLLECT_REFERRAL_NAME:
                if _turn_phone_digits(turn):
                    return _prime_phone_collection(
                        session,
                        transcript,
                        buffer_attr="referral_digit_buffer",
                        awaiting_attr="awaiting_referral_confirmation",
                        value_attr="referral_number",
                        target_state=State.COLLECT_REFERRAL_NUMBER,
                        confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                        total_digits=10,
                        digits_override=_turn_phone_digits(turn),
                    )
                if turn.entities.referral_name:
                    return State.COLLECT_REFERRAL_NUMBER
                return State.COLLECT_REFERRAL_NAME
            if resume_state == State.COLLECT_REFERRAL_NUMBER and _turn_phone_digits(turn):
                return _prime_phone_collection(
                    session,
                    transcript,
                    buffer_attr="referral_digit_buffer",
                    awaiting_attr="awaiting_referral_confirmation",
                    value_attr="referral_number",
                    target_state=State.COLLECT_REFERRAL_NUMBER,
                    confirm_state=State.CONFIRM_REFERRAL_NUMBER,
                    total_digits=10,
                    digits_override=_turn_phone_digits(turn),
                )
            return resume_state
        if turn.workflow_answer == "referral_declined":
            if session.referral_resume_state in {State.COLLECT_REFERRAL_NAME, State.COLLECT_REFERRAL_NUMBER} and session.referral_refusal_count < 2:
                session.referral_refusal_count += 1
                return State.REFERRAL_DECLINE_NUDGE
            return _close_with_acknowledgement(
                session,
                State.WARM_CLOSING,
                "कोई बात नहीं जी, शायद अभी suitable time नहीं है।",
            )

    next_state = TRANSITIONS.get((session.current_state, intent))
    if next_state is not None:
        return next_state

    auto_next = AUTO_TRANSITIONS.get(session.current_state)
    if auto_next is not None:
        return auto_next

    session.fallback_count += 1
    if session.fallback_count >= config.MAX_FALLBACKS_PER_STATE:
        session.fallback_count = 0
        return _close_with_acknowledgement(
            session,
            State.WARM_CLOSING,
            "जी, शायद अभी बात smoothly continue नहीं हो पा रही, इसलिए मैं call यहीं close करती हूँ।",
        )
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
        session.billing_blocker_reason = _resolve_prompt_exception_reason(transcript)
        session.last_blocker_reason = session.billing_blocker_reason

    if effective_previous_state in {
        State.ASK_WRONG_CONTACT_COMPANY,
        State.ASK_WRONG_CONTACT_TRADE,
        State.ASK_WRONG_CONTACT_TYPE,
        State.ASK_WRONG_CONTACT_NAME,
        State.COLLECT_COMPLAINT_DETAIL,
        State.ESCALATE_PAYMENT_DATE,
        State.ESCALATE_PARTNER_NAME,
        State.ESCALATE_SWITCHED_SOFTWARE,
        State.ESCALATE_SWITCH_REASON,
        State.ESCALATE_CLOSURE_REASON,
        State.ESCALATE_TECHNICAL_ISSUE,
        State.COLLECT_TRAINING_PINCODE,
        State.ASK_BILLING_START_TIMELINE,
        State.DETOUR_ANYTHING_ELSE,
    } and intent in {
        Intent.AFFIRM,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.THANK,
        Intent.GREET,
    }:
        extract_and_store(session, effective_previous_state, transcript)

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
        State.ASK_CONCERNED_PERSON_CONTACT,
        State.COLLECT_CONCERNED_PERSON_NUMBER,
        State.CONFIRM_CONCERNED_PERSON_NUMBER,
    } and intent in {
        Intent.AFFIRM,
        Intent.INFORM,
        Intent.ELABORATE,
        Intent.REQUEST,
        Intent.THANK,
        Intent.GREET,
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
        State.FIXED_CLOSING,
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
        State.ASK_WRONG_CONTACT_COMPANY,
        State.ASK_WRONG_CONTACT_TRADE,
        State.ASK_WRONG_CONTACT_TYPE,
        State.ASK_WRONG_CONTACT_NAME,
        State.ASK_CONCERNED_PERSON_CONTACT,
        State.COLLECT_CONCERNED_PERSON_NUMBER,
        State.CONFIRM_CONCERNED_PERSON_NUMBER,
        State.COLLECT_COMPLAINT_DETAIL,
        State.ESCALATE_PAYMENT_DATE,
        State.ESCALATE_PARTNER_NAME,
        State.ESCALATE_SWITCHED_SOFTWARE,
        State.ESCALATE_SWITCH_REASON,
        State.ESCALATE_CLOSURE_REASON,
        State.ESCALATE_TECHNICAL_ISSUE,
        State.COLLECT_TRAINING_PINCODE,
        State.DETOUR_ANYTHING_ELSE,
        State.BUSY_NUDGE,
        State.ASK_CALLBACK_TIME,
        State.CONFIRM_CALLBACK_TIME,
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

    if next_state not in {State.INVALID_REGISTRATION, State.WARM_CLOSING}:
        session.terminal_ack_text = ""

    session.previous_state = effective_previous_state
    session.current_state = next_state
    session.states_visited.append(next_state)

    if (
        effective_turn.entities.pincode_digits
        and effective_previous_state not in {State.VERIFY_PINCODE, State.COLLECT_PINCODE, State.CONFIRM_PINCODE}
    ):
        session.pending_pincode_digits = effective_turn.entities.pincode_digits

    if next_state == State.VERIFY_PINCODE and session.pending_pincode_digits:
        session.pincode = ""
        session.pincode_digit_buffer = session.pending_pincode_digits
        session.awaiting_pincode_confirmation = len(session.pending_pincode_digits) == 6
        session.current_state = State.CONFIRM_PINCODE if len(session.pending_pincode_digits) == 6 else State.COLLECT_PINCODE
        session.states_visited[-1] = session.current_state
        session.pending_pincode_digits = ""

    if next_state != State.ASK_CALLBACK_TIME:
        session.callback_prompt_override = ""
        session.callback_time_attempts = 0

    if next_state not in {State.BUSY_NUDGE, State.ASK_CALLBACK_TIME, State.CONFIRM_CALLBACK_TIME}:
        session.callback_resume_state = None
        session.busy_refusal_count = 0

    if next_state not in {
        State.COLLECT_COMPLAINT_DETAIL,
        State.EXPLORE_BILLING_BLOCKER,
        State.ESCALATE_PAYMENT_DATE,
        State.ESCALATE_PARTNER_NAME,
        State.ESCALATE_SWITCHED_SOFTWARE,
        State.ESCALATE_SWITCH_REASON,
        State.ESCALATE_CLOSURE_REASON,
        State.ESCALATE_TECHNICAL_ISSUE,
        State.COLLECT_TRAINING_PINCODE,
        State.ASK_BILLING_START_TIMELINE,
        State.DETOUR_ANYTHING_ELSE,
    }:
        session.billing_resume_state = None

    if next_state != State.REFERRAL_DECLINE_NUDGE and next_state not in {
        State.COLLECT_REFERRAL_NAME,
        State.COLLECT_REFERRAL_NUMBER,
        State.CONFIRM_REFERRAL_NUMBER,
        State.SUPPORT_AND_REFERRAL,
    }:
        session.referral_resume_state = None
        session.referral_refusal_count = 0

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
