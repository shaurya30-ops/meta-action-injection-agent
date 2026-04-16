from __future__ import annotations

from dataclasses import dataclass, field, replace
import re

from content_extraction.extractor_logic import (
    billing_started,
    extract_business_details,
    extract_digits,
    extract_email_candidate,
    extract_name_fragment,
    has_callback_request,
)

from .intents import Intent
from .session import CallSession
from .states import State


QUERY_NONE = "none"
QUERY_TECHNICAL_SUPPORT = "technical_support"
QUERY_PRICING = "pricing"
QUERY_CLARIFICATION = "clarification"
QUERY_DEALER_SETUP = "dealer_setup"
QUERY_GENERAL = "general"

CLARIFICATION_NONE = "none"
CLARIFICATION_MEANING = "meaning"
CLARIFICATION_REPEAT = "repeat"
CLARIFICATION_REASON = "reason"
CLARIFICATION_RECORDED_VALUE = "recorded_value"

AFFECT_NEUTRAL = "neutral"
AFFECT_POSITIVE = "positive"
AFFECT_FRUSTRATED = "frustrated"
AFFECT_CONFUSED = "confused"
AFFECT_HURRIED = "hurried"
AFFECT_DISENGAGED = "disengaged"
AFFECT_COMPLAINT = "complaint"

WORKFLOW_UNKNOWN = "unknown"


@dataclass
class TurnEntities:
    digits: str = ""
    email: str = ""
    business_type: str = ""
    business_trade: str = ""
    referral_name: str = ""
    amount_text: str = ""


@dataclass
class TurnFrame:
    speech_act: Intent
    workflow_answer: str = WORKFLOW_UNKNOWN
    query_type: str = QUERY_NONE
    clarification_kind: str = CLARIFICATION_NONE
    affect: str = AFFECT_NEUTRAL
    entities: TurnEntities = field(default_factory=TurnEntities)
    callback_request: bool = False
    wants_resume: bool = False
    wants_closure: bool = False
    transcript: str = ""


_FRUSTRATION_PATTERNS = [
    r"बार[- ]बार call",
    r"बार बार call",
    r"baar[- ]baar call",
    r"baar baar call",
    r"phir se call",
    r"फिर से call",
    r"kitni baar",
    r"kya kaam tha",
    r"क्या काम है",
    r"क्यों call",
    r"disturb",
    r"परेशान",
]

_CONFUSION_PATTERNS = [
    r"समझ नहीं",
    r"samajh नहीं",
    r"samajh nahi",
    r"क्या मतलब",
    r"matlab",
    r"कैसी call",
    r"कौन बोल",
]

_HURRY_PATTERNS = [
    r"जल्दी",
    r"jaldi",
    r"short में",
    r"busy",
    r"अभी time नहीं",
    r"थोड़ा जल्दी",
    r"thoda jaldi",
    r"short me",
    r"jaldi batao",
]

_POSITIVE_PATTERNS = [
    r"बहुत अच्छा",
    r"सब ठीक",
    r"koi problem nahi",
    r"कोई problem नहीं",
    r"theek hai",
    r"बढ़िया",
]

_DISENGAGED_PATTERNS = [
    r"जो भी",
    r"ठीक है बस",
    r"haan haan",
    r"हाँ हाँ",
]

_PRICING_PATTERNS = [
    r"renewal",
    r"charge",
    r"price",
    r"pricing",
    r"cost",
    r"amount",
    r"kitna lagega",
    r"kitne ka",
]

_TECHNICAL_PATTERNS = [
    r"error",
    r"problem",
    r"issue",
    r"login",
    r"ticket",
    r"help",
    r"support",
    r"काम नहीं कर",
    r"नहीं चल",
    r"nahi chal",
    r"kam nahi kar",
    r"set nahi hua",
]

_DEALER_SETUP_PATTERNS = [
    r"dealer",
    r"setup",
    r"install",
    r"training",
    r"configure",
    r"onboard",
    r"demo nahi",
]

_CLARIFICATION_PATTERNS = [
    r"क्या मतलब",
    r"समझ नहीं",
    r"samajh nahi",
    r"matlab",
    r"clear नहीं",
    r"क्या लिखा",
    r"क्या बोला",
    r"क्या कहा",
    r"नाम क्या",
    r"kya likha",
    r"kya bola",
    r"kya kaha",
    r"naam kya",
]

_CLARIFICATION_RECORDED_PATTERNS = [
    r"क्या लिखा",
    r"क्या note",
    r"क्या नोट",
    r"क्या सुना",
    r"नाम क्या लिखा",
    r"number क्या लिखा",
    r"कौन सा नाम",
    r"कौन सा number",
    r"kya likha",
    r"kya note",
    r"kya suna",
    r"naam kya likha",
    r"number kya likha",
]

_CLARIFICATION_REASON_PATTERNS = [
    r"क्यों",
    r"किसलिए",
    r"क्यों पूछ",
    r"kyun",
    r"kisliye",
    r"why",
    r"what for",
]

_CLARIFICATION_REPEAT_PATTERNS = [
    r"फिर से",
    r"दुबारा",
    r"दोबारा",
    r"एक बार और",
    r"repeat",
    r"again",
    r"dubara",
    r"dobara",
    r"क्या पूछा",
    r"क्या कहा",
    r"क्या बोला",
    r"phir se",
]

_CLARIFICATION_MEANING_PATTERNS = [
    r"क्या मतलब",
    r"समझ नहीं",
    r"samajh nahi",
    r"matlab",
    r"clear नहीं",
    r"कैसी call",
    r"कौन बोल",
]

_CLOSURE_PATTERNS = [
    r"\bbye\b",
    r"ठीक है bye",
    r"चलो ठीक है",
    r"रखता हूँ",
    r"रखती हूँ",
]

_NOT_STARTED_PATTERNS = [
    r"अभी नहीं",
    r"नहीं हुई",
    r"start नहीं",
    r"स्टार्ट नहीं",
    r"शुरू नहीं",
    r"समय नहीं मिला",
    r"time नहीं",
    r"time nahi",
]

_COLLECTION_STATUS_PATTERNS = [
    r"कहाँ तक load",
    r"कहां तक load",
    r"kitna load",
    r"कितनी digit",
    r"कितना हुआ",
]


def _normalized_text(text: str) -> str:
    return " ".join(text.strip().split())


def detect_query_type(transcript: str) -> str:
    lowered = transcript.lower()

    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _DEALER_SETUP_PATTERNS):
        return QUERY_DEALER_SETUP
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _PRICING_PATTERNS):
        return QUERY_PRICING
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _TECHNICAL_PATTERNS):
        return QUERY_TECHNICAL_SUPPORT
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _CLARIFICATION_PATTERNS):
        return QUERY_CLARIFICATION

    if re.search(
        r"(?:\b(?:kaise|kyun|kya|how|why|what|when|where|who|which|kitna|kitni|kitne|kaun)\b|क्या|कैसे|क्यों|कब|कहाँ|कहां|कौन|किस|कितना|कितनी|कितने)",
        transcript,
        re.IGNORECASE,
    ):
        return QUERY_GENERAL

    return QUERY_NONE


def detect_clarification_kind(transcript: str) -> str:
    lowered = transcript.lower()

    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _CLARIFICATION_RECORDED_PATTERNS):
        return CLARIFICATION_RECORDED_VALUE
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _CLARIFICATION_REASON_PATTERNS):
        return CLARIFICATION_REASON
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _CLARIFICATION_REPEAT_PATTERNS):
        return CLARIFICATION_REPEAT
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _CLARIFICATION_MEANING_PATTERNS):
        return CLARIFICATION_MEANING
    return CLARIFICATION_NONE


def detect_affect(transcript: str, speech_act: Intent, query_type: str) -> str:
    lowered = transcript.lower()

    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _HURRY_PATTERNS):
        return AFFECT_HURRIED
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _FRUSTRATION_PATTERNS):
        return AFFECT_FRUSTRATED
    if speech_act in {Intent.COMPLAIN, Intent.OBJECT} or query_type == QUERY_TECHNICAL_SUPPORT:
        return AFFECT_COMPLAINT
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _CONFUSION_PATTERNS):
        return AFFECT_CONFUSED
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _DISENGAGED_PATTERNS):
        return AFFECT_DISENGAGED
    if speech_act in {Intent.THANK, Intent.GREET} or any(
        re.search(pattern, lowered, re.IGNORECASE) for pattern in _POSITIVE_PATTERNS
    ):
        return AFFECT_POSITIVE
    return AFFECT_NEUTRAL


def detect_billing_blocker_reason(transcript: str) -> str:
    lowered = transcript.lower()
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _TECHNICAL_PATTERNS):
        return "technical_issue"
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _DEALER_SETUP_PATTERNS):
        return "dealer_setup"
    if re.search(r"time नहीं|time nahi|समय नहीं|busy", lowered, re.IGNORECASE):
        return "no_time"
    if re.search(r"समझ नहीं|training|सीखा नहीं", lowered, re.IGNORECASE):
        return "training_gap"
    return "unknown"


def _looks_like_collection_status_request(state: State, transcript: str) -> bool:
    if state not in {
        State.COLLECT_WHATSAPP_NUMBER,
        State.COLLECT_ALTERNATE_NUMBER,
        State.COLLECT_PINCODE,
        State.COLLECT_REFERRAL_NUMBER,
    }:
        return False
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _COLLECTION_STATUS_PATTERNS)


def _is_not_started(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _NOT_STARTED_PATTERNS)


def map_workflow_answer(
    session: CallSession,
    speech_act: Intent,
    transcript: str,
    entities: TurnEntities,
    query_type: str,
) -> str:
    state = session.current_state
    lowered = transcript.lower()

    if _looks_like_collection_status_request(state, transcript):
        return "collection_status_request"

    if state == State.ASK_BILLING_STATUS:
        if billing_started(transcript) or speech_act == Intent.AFFIRM:
            return "billing_started"
        if _is_not_started(transcript) or speech_act in {
            Intent.DENY,
            Intent.OBJECT,
            Intent.COMPLAIN,
            Intent.ELABORATE,
            Intent.INFORM,
        }:
            return "billing_not_started"

    if state == State.VERIFY_WHATSAPP:
        if entities.digits or re.search(r"नहीं|नही|nahi|दूसरा|different", lowered, re.IGNORECASE):
            return "other_whatsapp"
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "same_whatsapp"

    if state == State.ASK_ALTERNATE_NUMBER:
        if entities.digits or speech_act in {Intent.AFFIRM, Intent.REQUEST, Intent.INFORM, Intent.ELABORATE}:
            return "provide_alternate"
        if speech_act in {Intent.DENY, Intent.OBJECT, Intent.THANK} or re.search(
            r"नहीं|नही|none|no", lowered, re.IGNORECASE
        ):
            return "no_alternate"

    if state == State.VERIFY_PINCODE:
        if entities.digits or speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "corrected_pincode"
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "confirm_existing_pincode"

    if state == State.VERIFY_BUSINESS_DETAILS:
        if speech_act == Intent.AFFIRM and not entities.business_type and not entities.business_trade:
            return "business_details_confirmed"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "business_details_corrected"

    if state == State.CONFIRM_BUSINESS_DETAILS:
        if speech_act in {Intent.AFFIRM, Intent.THANK} and not entities.business_type and not entities.business_trade:
            return "business_details_confirmed"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "business_details_corrected"

    if state == State.VERIFY_EMAIL:
        if query_type != QUERY_NONE and not entities.email:
            return "user_query"
        if entities.email:
            return "email_corrected"
        if speech_act == Intent.AFFIRM:
            return "email_confirmed"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "email_correction_attempt"

    if state == State.COLLECT_EMAIL_CORRECTION:
        if query_type != QUERY_NONE and not entities.email:
            return "user_query"
        if entities.email:
            return "email_corrected"
        if speech_act in {Intent.ASK, Intent.UNCLEAR}:
            return "email_needs_repeat"

    if state == State.CONFIRM_EMAIL_CORRECTION:
        if query_type != QUERY_NONE and not entities.email:
            return "user_query"
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "email_confirmed"
        if entities.email:
            return "email_corrected"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "email_correction_attempt"

    if state == State.ASK_PURCHASE_AMOUNT:
        if re.search(r"याद नहीं|yaad nahi|नहीं पता|pata nahi", lowered, re.IGNORECASE):
            return "purchase_amount_unknown"
        if transcript.strip():
            return "purchase_amount_provided"

    if state == State.SUPPORT_AND_REFERRAL:
        if speech_act in {Intent.DENY, Intent.OBJECT}:
            return "referral_declined"
        if entities.digits or entities.referral_name or speech_act in {
            Intent.AFFIRM,
            Intent.INFORM,
            Intent.ELABORATE,
            Intent.REQUEST,
            Intent.THANK,
            Intent.GREET,
        }:
            return "referral_accepted"

    if state == State.COLLECT_REFERRAL_NAME:
        if entities.referral_name:
            return "referral_name_provided"

    if state in {
        State.COLLECT_WHATSAPP_NUMBER,
        State.CONFIRM_WHATSAPP_NUMBER,
        State.COLLECT_ALTERNATE_NUMBER,
        State.CONFIRM_ALTERNATE_NUMBER,
        State.COLLECT_PINCODE,
        State.CONFIRM_PINCODE,
        State.COLLECT_REFERRAL_NUMBER,
        State.CONFIRM_REFERRAL_NUMBER,
    } and entities.digits:
        return "digits_provided"

    if state in {
        State.CONFIRM_WHATSAPP_NUMBER,
        State.CONFIRM_ALTERNATE_NUMBER,
        State.CONFIRM_PINCODE,
        State.CONFIRM_REFERRAL_NUMBER,
    }:
        if query_type != QUERY_NONE and not entities.digits:
            return "user_query"
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "digits_confirmed"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "digits_rejected"

    if query_type != QUERY_NONE:
        return "user_query"

    return WORKFLOW_UNKNOWN


def parse_turn(
    session: CallSession,
    speech_act: Intent,
    transcript: str,
    *,
    state_override: State | None = None,
) -> TurnFrame:
    active_session = replace(session, current_state=state_override) if state_override else session
    normalized = _normalized_text(transcript)
    business_type, business_trade = extract_business_details(
        normalized,
        fallback_type="",
        fallback_trade="",
    )
    entities = TurnEntities(
        digits=extract_digits(normalized),
        email=extract_email_candidate(active_session, normalized),
        business_type=business_type,
        business_trade=business_trade,
        referral_name=extract_name_fragment(normalized),
        amount_text=normalized if active_session.current_state == State.ASK_PURCHASE_AMOUNT else "",
    )

    clarification_kind = detect_clarification_kind(normalized)
    query_type = detect_query_type(normalized)
    if clarification_kind != CLARIFICATION_NONE:
        query_type = QUERY_CLARIFICATION
    affect = detect_affect(normalized, speech_act, query_type)
    wants_closure = speech_act == Intent.GOODBYE or any(
        re.search(pattern, normalized, re.IGNORECASE) for pattern in _CLOSURE_PATTERNS
    )
    wants_resume = bool(
        re.search(r"clear|ठीक है|समझ गया|समझ गई|haan|हाँ|yes", normalized, re.IGNORECASE)
    )

    return TurnFrame(
        speech_act=speech_act,
        workflow_answer=map_workflow_answer(active_session, speech_act, normalized, entities, query_type),
        query_type=query_type,
        clarification_kind=clarification_kind,
        affect=affect,
        entities=entities,
        callback_request=has_callback_request(normalized) or speech_act == Intent.DEFER,
        wants_resume=wants_resume,
        wants_closure=wants_closure,
        transcript=normalized,
    )
