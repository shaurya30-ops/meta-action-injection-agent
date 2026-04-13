import re
import logging
from state_machine.states import State
from state_machine.session import CallSession

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
# Extractor configs per state
# ══════════════════════════════════════════

EXTRACTORS = {
    State.VERIFY_WHATSAPP: {"field": "whatsapp_number", "type": "phone"},
    State.COLLECT_ALTERNATE_NUMBER: {"field": "alternate_number", "type": "phone"},
    State.VERIFY_PINCODE: {"field": "pincode", "type": "pincode", "fallback_field": "city"},
    State.VERIFY_BUSINESS_TRADE: {"field": "business_trade", "type": "business"},
    State.VERIFY_EMAIL: {"field": "email", "type": "email"},
    State.ASK_PRICE: {"field": "price_confirmed", "type": "number"},
    State.CAPTURE_ISSUE_SUMMARY: {"field": "issue_description", "type": "free_text"},
    State.CAPTURE_ISSUE_CALLBACK: {"field": "issue_description", "type": "free_text"},
    State.CAPTURE_CALLBACK_TIME: {"field": "callback_datetime", "type": "free_text"},
    State.CALLBACK_SCHEDULING: {"field": "callback_datetime", "type": "free_text"},
    State.CAPTURE_CALLBACK_DATETIME: {"field": "callback_datetime", "type": "free_text"},
    State.CAPTURE_REFERENCE: {"field": "reference_name", "type": "reference"},
    State.DELAY_REASON_PROBE: {"field": "delay_subreason", "type": "delay_reason"},
    State.WILL_NOT_USE_PROBE: {"field": "will_not_use_reason", "type": "will_not_use_reason"},
}

PHONE_PATTERN = re.compile(r"(\d{10})")
PINCODE_PATTERN = re.compile(r"(\d{6})")
EMAIL_PATTERN = re.compile(r"[\w.+-]+\s*(?:at the rate|at|@)\s*[\w.-]+\s*(?:dot|\.)\s*\w+", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"(\d[\d,\.]*)")

BUSINESS_KEYWORDS = {
    "pharmaceutical": "Pharmaceutical", "pharma": "Pharmaceutical",
    "grocery": "Grocery", "kirana": "Grocery",
    "retail": "Retail", "distribution": "Distribution", "distributor": "Distribution",
    "manufacturing": "Manufacturing", "garment": "Garments", "fashion": "Garments",
    "hardware": "Hardware", "electronics": "Electronics", "fmcg": "FMCG",
    "textile": "Textile", "auto parts": "Auto Parts", "cosmetic": "Cosmetics",
    "food": "Food", "stockist": "Distribution", "wholesaler": "Wholesale",
}

DELAY_KEYWORDS = {
    "data migration": "DATA_MIGRATION", "data": "DATA_MIGRATION", "migrate": "DATA_MIGRATION",
    "demo": "DEMO_PERIOD", "trial": "DEMO_PERIOD",
    "install": "INSTALLATION_PENDING", "setup": "INSTALLATION_PENDING",
    "training": "TRAINING_PERIOD", "sikhna": "TRAINING_PERIOD", "seekh": "TRAINING_PERIOD",
    "technical": "TECHNICAL_ISSUE", "error": "TECHNICAL_ISSUE", "bug": "TECHNICAL_ISSUE",
    "system": "SYSTEM_ISSUE", "computer": "SYSTEM_ISSUE",
    "stock": "STOCK_MANAGEMENT", "inventory": "STOCK_MANAGEMENT",
    "personal": "PERSONAL_ISSUE", "health": "PERSONAL_ISSUE",
    "operator": "NEED_OPERATOR", "staff": "NEED_OPERATOR",
    "next fy": "NEXT_FY", "financial year": "NEXT_FY",
    "chutti": "PERSONAL_ISSUE", "leave": "PERSONAL_ISSUE",
}

WILL_NOT_USE_KEYWORDS = {
    "business closed": "BUSINESS_CLOSED", "band": "BUSINESS_CLOSED",
    "manual": "CONTINUE_MANUAL", "haath se": "CONTINUE_MANUAL",
    "competitor": "SHIFTED_COMPETITOR", "tally": "SHIFTED_COMPETITOR", "busy software": "SHIFTED_COMPETITOR",
    "price": "PRICE_ISSUE", "mehnga": "PRICE_ISSUE", "costly": "PRICE_ISSUE", "expensive": "PRICE_ISSUE",
}


def _normalize_email(text: str) -> str:
    """Normalize spoken email: 'xyz at the rate gmail dot com' -> 'xyz@gmail.com'"""
    t = text.lower()
    t = re.sub(r"\s*at the rate\s*", "@", t)
    t = re.sub(r"\s*at\s*(?=\w+\s*(?:dot|\.))", "@", t)
    t = re.sub(r"\s*dot\s*", ".", t)
    # Convert spoken numbers
    number_words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                    "six": "6", "seven": "7", "eight": "8", "nine": "9", "zero": "0"}
    for word, digit in number_words.items():
        t = t.replace(word, digit)
    t = re.sub(r"\s+", "", t)  # Remove remaining spaces
    match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", t)
    return match.group(0) if match else ""


def _extract_phone(transcript: str) -> str:
    # Convert spoken digits to numbers
    digit_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "double": "", "triple": "",
    }
    t = transcript.lower()
    for word, digit in digit_words.items():
        t = t.replace(word, digit)
    # Handle "double X" -> "XX"
    t = re.sub(r"\s+", "", t)
    match = PHONE_PATTERN.search(t)
    return match.group(1) if match else ""


def _match_keywords(transcript: str, keyword_map: dict) -> str:
    t = transcript.lower()
    for keyword, value in keyword_map.items():
        if keyword in t:
            return value
    return ""


def extract_and_store(session: CallSession, state: State, transcript: str):
    """Extract data from transcript based on current state and store in session."""
    if state not in EXTRACTORS:
        return

    cfg = EXTRACTORS[state]
    field = cfg["field"]
    extract_type = cfg["type"]

    try:
        if extract_type == "phone":
            value = _extract_phone(transcript)
            if value:
                setattr(session, field, value)

        elif extract_type == "pincode":
            match = PINCODE_PATTERN.search(transcript)
            if match:
                setattr(session, field, match.group(1))
            else:
                fallback = cfg.get("fallback_field")
                if fallback:
                    setattr(session, fallback, transcript.strip())

        elif extract_type == "email":
            value = _normalize_email(transcript)
            if value:
                setattr(session, field, value)

        elif extract_type == "number":
            match = NUMBER_PATTERN.search(transcript)
            if match:
                setattr(session, field, match.group(1).replace(",", ""))

        elif extract_type == "business":
            value = _match_keywords(transcript, BUSINESS_KEYWORDS)
            if value:
                setattr(session, field, value)
            else:
                setattr(session, field, transcript.strip())

        elif extract_type == "delay_reason":
            value = _match_keywords(transcript, DELAY_KEYWORDS)
            setattr(session, field, value or "OTHER")

        elif extract_type == "will_not_use_reason":
            value = _match_keywords(transcript, WILL_NOT_USE_KEYWORDS)
            setattr(session, field, value or "DOES_NOT_WANT_TO_SHARE")

        elif extract_type == "reference":
            setattr(session, "reference_name", transcript.strip())
            phone = _extract_phone(transcript)
            if phone:
                session.reference_number = phone

        elif extract_type == "free_text":
            current = getattr(session, field, "")
            if current:
                setattr(session, field, current + " " + transcript.strip())
            else:
                setattr(session, field, transcript.strip())

    except Exception as e:
        logger.error(f"Extraction failed for state={state}, type={extract_type}: {e}")
