from __future__ import annotations

from dataclasses import dataclass, field, replace
import re

from content_extraction.extractor_logic import (
    billing_started,
    extract_business_details,
    extract_digits,
    extract_email_candidate,
    extract_name_fragment,
    extract_named_digit_slots,
    extract_callback_phrase,
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
    phone_digits: str = ""
    pincode_digits: str = ""
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
    r"रहने दो",
    r"rehne do",
    r"छोड़ो",
    r"chhodo",
]

_OPENING_WRONG_REGISTRATION_PATTERNS = [
    r"\bwrong\s+number\b",
    r"\bwrong\s+person\b",
    r"\bwrong\s+company\b",
    r"\u0917\u0932\u0924\s+(?:number|\u0928\u0902\u092c\u0930)",
    r"\u0917\u0932\u0924\s+\u0906\u0926\u092e\u0940",
    r"\u0917\u0932\u0924\s+\u0935\u094d\u092f\u0915\u094d\u0924\u093f",
    r"\u092f\u0939\s+\u0917\u0932\u0924\s+\u091c\u0917\u0939",
    r"\u092f\u0939\u093e\u0901\s+\u0910\u0938\u093e\s+\u0915\u094b\u0908\s+\u0928\u0939\u0940\u0902",
    r"\u092f\u0939\u093e\u0901\s+\u0909\u0924\u094d\u0915\u0930\u094d\u0937\s+\u0928\u0939\u0940\u0902",
    r"\u092f\u0939\s+techladder\s+\u0928\u0939\u0940\u0902",
    r"\u092f\u0947\s+techladder\s+\u0928\u0939\u0940\u0902",
]

_CONTACT_UNAVAILABLE_PATTERNS = [
    r"\u092c\u093e\u0939\u0930\s+\u0939\u0948",
    r"\u092c\u093e\u0939\u0930\s+\u0939\u0948\u0902",
    r"\u092c\u093e\u0939\u0930\s+\u0917\u090f",
    r"\u0905\u092d\u0940\s+\u0928\u0939\u0940\u0902\s+\u0939\u0948",
    r"\u0905\u092d\u0940\s+\u0928\u0939\u0940\u0902\s+\u0939\u0948\u0902",
    r"\u0905\u092d\u0940\s+\u0909\u092a\u0932\u092c\u094d\u0927\s+\u0928\u0939\u0940\u0902",
    r"\u0932\u095c\u0915\u093e\s+\u092c\u093e\u0939\u0930",
    r"\u0913\u0928\u0930\s+\u0928\u0939\u0940\u0902",
    r"\u092e\u093e\u0932\u093f\u0915\s+\u0928\u0939\u0940\u0902",
    r"\u0938\u0930\s+\u0928\u0939\u0940\u0902",
    r"\u092e\u0948\u092e\s+\u0928\u0939\u0940\u0902",
    r"\u0909\u0924\u094d\u0915\u0930\u094d\u0937\s+\u0928\u0939\u0940\u0902",
    r"\b(?:owner|sir|madam|maam|mam|staff|employee|accountant|boy)\b.*\b(?:not|nahi|nahin|available|bahar)\b",
]

_CONCERNED_PERSON_REDIRECT_PATTERNS = [
    r"उससे\s+(?:call|बात)\s+करो",
    r"उसको\s+(?:call|बात)\s+करो",
    r"उन्हें\s+(?:call|बात)\s+करो",
    r"जो\s+software\s+संभाल",
    r"software\s+वो\s+देख",
    r"वही\s+software\s+देख",
    r"दूसरा\s+लड़का\s+संभाल",
    r"दूसरा\s+boy\s+संभाल",
    r"accountant\s+संभाल",
    r"operator\s+संभाल",
    r"billing\s+वही\s+कर",
    r"मैं\s+तो\s+मालिक\s+हूं",
    r"main\s+to\s+owner",
]

_SAME_NUMBER_CONTACT_PATTERNS = [
    r"इसी\s+(?:number|नंबर)",
    r"यही\s+(?:number|नंबर)",
    r"same\s+number",
    r"isi\s+number",
]

_SAME_WHATSAPP_PATTERNS = [
    r"(?:same|यही|इसी|isi|yahi|primary)\s*(?:ही\s*)?(?:number|नंबर|है)?",
    r"नहीं\s*नहीं.*(?:same|यही|इसी|isi|yahi)",
    r"actually\s+same",
]

_ALTERNATE_SAME_AS_WHATSAPP_PATTERNS = [
    r"(?:same|यही|इसी|isi|yahi)\s+(?:as\s+)?(?:whatsapp|व्हाट्सऐप)",
    r"whatsapp\s+(?:वाला|wali|number)\s+(?:same|यही|इसी)",
    r"(?:whatsapp|व्हाट्सऐप)\s+ही",
]

_AUDIO_CHECK_PATTERNS = [
    r"^hello\??$",
    r"hello\?$",
    r"awaaz\s+aa\s+rahi\s+hai",
    r"आवाज\s+आ\s+रही\s+है",
    r"आवाज़\s+आ\s+रही\s+है",
    r"can\s+you\s+hear\s+me",
    r"meri\s+awaaz\s+aa\s+rahi",
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

_DETAIL_REFUSAL_PATTERNS = [
    r"नहीं\s+बता",
    r"नहीं\s+दे\s+सक",
    r"details?\s+नहीं",
    r"share\s+नहीं",
    r"comfortable\s+नहीं",
    r"skip\s+कर",
    r"nahi\s+bata",
    r"nahi\s+de\s+sak",
    r"detail[s]?\s+nahi",
    r"share\s+nahi",
    r"comfortable\s+nahi",
]

_ABUSIVE_PATTERNS = [
    r"\bbakwaas\b",
    r"बेकार",
    r"चुप\s+रहो",
    r"dimag\s+mat\s+khao",
    r"\bfaltu\b",
    r"\bidiot\b",
    r"\bstupid\b",
    r"shut\s+up",
]

_PARTNER_NON_RESPONSIVE_PATTERNS = [
    r"partner.*(?:reply|response)",
    r"partner.*(?:नहीं|nahi|nahin).*(?:उठा|बताया|आया|कर)",
    r"payment.*partner",
    r"engineer.*(?:नहीं|nahi|nahin).*(?:आया|किया)",
]

_SWITCHED_SOFTWARE_PATTERNS = [
    r"\btally\b",
    r"\bbusy\b",
    r"\bvyapar\b",
    r"दूसरा\s+software",
    r"switch\s+कर",
    r"already\s+le\s+liya",
]

_BUSINESS_CLOSED_PATTERNS = [
    r"business\s+band",
    r"shop\s+band",
    r"dukan\s+band",
    r"दुकान\s+बंद",
    r"business\s+closed",
    r"use\s+नहीं\s+कर",
]

_MIGRATION_DELAY_PATTERNS = [
    r"migration",
    r"data\s+entry",
    r"old\s+data",
    r"stock\s+entry",
    r"data\s+load",
    r"master\s+ban",
]

_COLLECTION_STATUS_PATTERNS = [
    r"कहाँ तक load",
    r"कहां तक load",
    "\u0915\u0939\u093e\u0901 \u0924\u0915 \u0932\u093f\u0916\u093e",
    "\u0915\u0939\u093e\u0902 \u0924\u0915 \u0932\u093f\u0916\u093e",
    r"kitna load",
    "\u0915\u093f\u0924\u0928\u093e \u0932\u093f\u0916\u093e",
    "\u0915\u094d\u092f\u093e note",
    "\u0915\u094d\u092f\u093e \u0928\u094b\u091f",
    "\u0915\u093f\u0924\u0928\u0940 digit",
    "\u0915\u093f\u0924\u0928\u093e \u0939\u0941\u0906",
    "\u0926\u0938 number",
    "\u092a\u0942\u0930\u093e number",
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
    if re.search(
        "setup\\s+\u0939\u0940\\s+\u0915\u0930|abhi\\s+setup|setup\\s+\u0928\u0939\u0940\u0902\\s+\u0915\u093f\u092f\u093e|setup\\s+ho\\s+raha|"
        "setup\\s+kar\\s+raha|\u0932\u095c\u0915\u093e\\s+\u092c\u093e\u0939\u0930|ladka\\s+bahar|engineer\\s+\u092c\u093e\u0939\u0930|\u092c\u093e\u0939\u0930\\s+\u0939\u0948",
        lowered,
        re.IGNORECASE,
    ):
        return "setup_in_progress"
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
        State.COLLECT_CONCERNED_PERSON_NUMBER,
        State.COLLECT_WHATSAPP_NUMBER,
        State.COLLECT_ALTERNATE_NUMBER,
        State.COLLECT_PINCODE,
        State.COLLECT_REFERRAL_NUMBER,
    }:
        return False
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _COLLECTION_STATUS_PATTERNS)


def _is_not_started(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _NOT_STARTED_PATTERNS)


def _is_opening_wrong_registration(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _OPENING_WRONG_REGISTRATION_PATTERNS)


def _is_contact_unavailable(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _CONTACT_UNAVAILABLE_PATTERNS)


def _is_concerned_person_redirect(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _CONCERNED_PERSON_REDIRECT_PATTERNS)


def _is_same_number_contact(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _SAME_NUMBER_CONTACT_PATTERNS)


def _is_same_whatsapp(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _SAME_WHATSAPP_PATTERNS)


def _is_same_as_whatsapp_for_alternate(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _ALTERNATE_SAME_AS_WHATSAPP_PATTERNS)


def _is_detail_refusal(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _DETAIL_REFUSAL_PATTERNS)


def _is_audio_check(transcript: str) -> bool:
    return any(re.search(pattern, transcript, re.IGNORECASE) for pattern in _AUDIO_CHECK_PATTERNS)


def detect_prompt_exception_reason(transcript: str) -> str:
    lowered = transcript.lower()
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _ABUSIVE_PATTERNS):
        return "abusive_language"
    if re.search(r"\b(crash|bug|hang)\b", lowered, re.IGNORECASE):
        return "technical_issue"
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _PARTNER_NON_RESPONSIVE_PATTERNS):
        return "partner_non_responsive"
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _SWITCHED_SOFTWARE_PATTERNS):
        return "switched_software"
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _BUSINESS_CLOSED_PATTERNS):
        return "business_closed"
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _MIGRATION_DELAY_PATTERNS):
        return "migration_delay"

    reason = detect_billing_blocker_reason(transcript)
    if reason == "training_gap":
        return "training_pending"
    return reason


def map_workflow_answer(
    session: CallSession,
    speech_act: Intent,
    transcript: str,
    entities: TurnEntities,
    query_type: str,
) -> str:
    state = session.current_state
    lowered = transcript.lower()

    if _is_audio_check(transcript):
        return "audio_check"

    if state in {State.OPENING_GREETING, State.CONFIRM_IDENTITY}:
        if _is_opening_wrong_registration(transcript):
            return "opening_wrong_registration"
        if _is_contact_unavailable(transcript):
            return "contact_unavailable"
        if speech_act in {Intent.DENY, Intent.OBJECT}:
            return "opening_wrong_registration"
        if speech_act in {Intent.AFFIRM, Intent.INFORM, Intent.REQUEST, Intent.GREET, Intent.THANK, Intent.ELABORATE, Intent.COMPLAIN}:
            return "opening_confirmed"

    if state == State.CHECK_AVAILABILITY and _is_contact_unavailable(transcript):
        return "contact_unavailable"

    if (
        state
        not in {
            State.ASK_CALLBACK_TIME,
            State.CONFIRM_CALLBACK_TIME,
            State.CALLBACK_CLOSING,
            State.INVALID_REGISTRATION,
            State.WARM_CLOSING,
            State.FIXED_CLOSING,
            State.LOG_DISPOSITION,
            State.END,
        }
        and _is_concerned_person_redirect(transcript)
    ):
        return "concerned_person_redirect"

    if _looks_like_collection_status_request(state, transcript):
        return "collection_status_request"

    if state == State.ASK_CONCERNED_PERSON_CONTACT:
        if entities.phone_digits:
            return "concerned_person_number_provided"
        if _is_same_number_contact(transcript):
            return "concerned_person_same_number"

    if state == State.ASK_WRONG_CONTACT_COMPANY and transcript.strip():
        return "wrong_contact_company_provided"

    if state == State.ASK_WRONG_CONTACT_TRADE and transcript.strip():
        return "wrong_contact_trade_provided"

    if state == State.ASK_WRONG_CONTACT_TYPE and transcript.strip():
        return "wrong_contact_type_provided"

    if state == State.ASK_WRONG_CONTACT_NAME and transcript.strip():
        return "wrong_contact_name_provided"

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

    if state == State.COLLECT_COMPLAINT_DETAIL and transcript.strip():
        return "complaint_detail_provided"

    if state == State.EXPLORE_BILLING_BLOCKER:
        if _is_detail_refusal(transcript):
            return "billing_blocker_refused"
        if transcript.strip():
            return "billing_blocker_reason_provided"

    if state == State.ESCALATE_PAYMENT_DATE and transcript.strip():
        return "payment_date_provided"

    if state == State.ESCALATE_PARTNER_NAME and transcript.strip():
        return "partner_name_provided"

    if state == State.ESCALATE_SWITCHED_SOFTWARE and transcript.strip():
        return "switched_software_provided"

    if state == State.ESCALATE_SWITCH_REASON and transcript.strip():
        return "switch_reason_provided"

    if state == State.ESCALATE_CLOSURE_REASON and transcript.strip():
        return "closure_reason_provided"

    if state == State.ESCALATE_TECHNICAL_ISSUE and transcript.strip():
        return "technical_issue_detail_provided"

    if state == State.COLLECT_TRAINING_PINCODE:
        if entities.pincode_digits or entities.digits:
            return "training_pincode_provided"
        if transcript.strip():
            return "training_pincode_missing"

    if state == State.ASK_BILLING_START_TIMELINE:
        if query_type != QUERY_NONE:
            return "user_query"
        if transcript.strip():
            return "billing_timeline_provided"

    if state == State.DETOUR_ANYTHING_ELSE and transcript.strip():
        return "detour_response_provided"

    if state == State.VERIFY_WHATSAPP:
        if _is_same_whatsapp(transcript):
            return "same_whatsapp"
        if entities.phone_digits or re.search(r"नहीं|नही|nahi|दूसरा|different", lowered, re.IGNORECASE):
            return "other_whatsapp"
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "same_whatsapp"

    if state == State.ASK_ALTERNATE_NUMBER:
        if _is_same_as_whatsapp_for_alternate(transcript):
            return "same_as_whatsapp"
        if speech_act in {Intent.DENY, Intent.OBJECT, Intent.THANK} or re.search(
            r"नहीं|नही|none|no", lowered, re.IGNORECASE
        ):
            return "no_alternate"
        if entities.phone_digits or speech_act in {Intent.AFFIRM, Intent.REQUEST, Intent.INFORM, Intent.ELABORATE}:
            return "provide_alternate"

    if state == State.VERIFY_PINCODE:
        if re.search(
            "\u092e\u0941\u091d\u0947 \u0928\u0939\u0940\u0902 \u092a\u0924\u093e|\u092a\u0924\u093e \u0928\u0939\u0940\u0902|"
            "\u092f\u093e\u0926 \u0928\u0939\u0940\u0902|maloom nahi|pata nahi|yaad nahi",
            lowered,
            re.IGNORECASE,
        ):
            return "pincode_unknown"
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
        if _is_detail_refusal(transcript):
            return "email_refused"
        if speech_act == Intent.AFFIRM:
            return "email_confirmed"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "email_correction_attempt"

    if state == State.COLLECT_EMAIL_CORRECTION:
        if query_type != QUERY_NONE and not entities.email:
            return "user_query"
        if entities.email:
            return "email_corrected"
        if _is_detail_refusal(transcript):
            return "email_refused"
        if speech_act in {Intent.ASK, Intent.UNCLEAR}:
            return "email_needs_repeat"

    if state == State.CONFIRM_EMAIL_CORRECTION:
        if query_type != QUERY_NONE and not entities.email:
            return "user_query"
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "email_confirmed"
        if entities.email:
            return "email_corrected"
        if _is_detail_refusal(transcript):
            return "email_refused"
        if speech_act in {Intent.DENY, Intent.INFORM, Intent.ELABORATE, Intent.REQUEST, Intent.OBJECT}:
            return "email_correction_attempt"

    if state == State.ASK_PURCHASE_AMOUNT:
        if _is_detail_refusal(transcript):
            return "purchase_amount_refused"
        if re.search(r"याद नहीं|yaad nahi|नहीं पता|pata nahi", lowered, re.IGNORECASE):
            return "purchase_amount_unknown"
        if transcript.strip():
            return "purchase_amount_provided"

    if state == State.SUPPORT_AND_REFERRAL:
        if speech_act in {Intent.DENY, Intent.OBJECT}:
            return "referral_declined"
        if entities.phone_digits or entities.referral_name or speech_act in {
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
        if _is_detail_refusal(transcript):
            return "referral_refused"

    if state == State.COLLECT_REFERRAL_NUMBER and _is_detail_refusal(transcript):
        return "referral_refused"

    if state == State.REFERRAL_DECLINE_NUDGE:
        if speech_act in {Intent.DENY, Intent.OBJECT} or _is_detail_refusal(transcript):
            return "referral_declined"
        if entities.referral_name or entities.phone_digits or speech_act in {
            Intent.AFFIRM,
            Intent.INFORM,
            Intent.ELABORATE,
            Intent.REQUEST,
            Intent.THANK,
            Intent.GREET,
        }:
            return "referral_accepted"

    if state == State.ASK_CALLBACK_TIME:
        if has_callback_request(transcript) and not extract_callback_phrase(transcript):
            return "callback_time_unspecified"
        if has_callback_request(transcript) or extract_callback_phrase(transcript):
            return "callback_time_provided"

    if state == State.CONFIRM_CALLBACK_TIME:
        if speech_act in {Intent.AFFIRM, Intent.THANK}:
            return "callback_time_confirmed"
        if has_callback_request(transcript) or extract_callback_phrase(transcript):
            return "callback_time_updated"

    if state in {State.COLLECT_PINCODE, State.CONFIRM_PINCODE} and re.search(
        "\u092e\u0941\u091d\u0947 \u0928\u0939\u0940\u0902 \u092a\u0924\u093e|\u092a\u0924\u093e \u0928\u0939\u0940\u0902|"
        "\u092f\u093e\u0926 \u0928\u0939\u0940\u0902|maloom nahi|pata nahi|yaad nahi",
        lowered,
        re.IGNORECASE,
    ):
        return "pincode_unknown"

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
        State.CONFIRM_CONCERNED_PERSON_NUMBER,
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
    named_digit_slots = extract_named_digit_slots(normalized)
    raw_digits = extract_digits(normalized)
    parsed_digits = raw_digits
    if named_digit_slots["phone"] and named_digit_slots["pincode"]:
        parsed_digits = named_digit_slots["phone"]
    elif named_digit_slots["phone"]:
        parsed_digits = named_digit_slots["phone"]
    elif named_digit_slots["pincode"]:
        parsed_digits = named_digit_slots["pincode"]
    business_type, business_trade = extract_business_details(
        normalized,
        fallback_type="",
        fallback_trade="",
    )
    entities = TurnEntities(
        digits=parsed_digits,
        phone_digits=named_digit_slots["phone"],
        pincode_digits=named_digit_slots["pincode"],
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
