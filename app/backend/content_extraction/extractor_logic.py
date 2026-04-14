import re
from state_machine.session import CallSession

DIGIT_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

DEVANAGARI_DIGITS = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}

DIGIT_TO_WORD = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

BUSINESS_TYPE_KEYWORDS = {
    "pharma": "Pharma",
    "pharmaceutical": "Pharma",
    "grocery": "Grocery",
    "kirana": "Grocery",
    "garment": "Garment",
    "textile": "Textile",
    "hardware": "Hardware",
    "cosmetic": "Cosmetics",
    "fmcg": "FMCG",
    "electronics": "Electronics",
    "medical": "Medical",
}

BUSINESS_TRADE_KEYWORDS = {
    "wholesaler": "Wholesaler",
    "wholesale": "Wholesaler",
    "retailer": "Retailer",
    "retail": "Retailer",
    "distributor": "Distributor",
    "distribution": "Distributor",
    "stockist": "Stockist",
    "manufacturer": "Manufacturer",
    "manufacturing": "Manufacturer",
}

CALLBACK_PATTERNS = [
    re.compile(r"बाद में\s*call", re.IGNORECASE),
    re.compile(r"अभी\s*busy", re.IGNORECASE),
    re.compile(r"minute\s+बाद", re.IGNORECASE),
    re.compile(r"मिनट\s+बाद", re.IGNORECASE),
    re.compile(r"थोड़ी\s+देर\s+बाद", re.IGNORECASE),
    re.compile(r"अभी\s*वक्त\s*नहीं", re.IGNORECASE),
    re.compile(r"call\s*करो", re.IGNORECASE),
]

CALLBACK_TIME_PATTERNS = [
    re.compile(r"(आधे\s+घंटे\s+बाद)", re.IGNORECASE),
    re.compile(r"(थोड़ी\s+देर\s+बाद)", re.IGNORECASE),
    re.compile(r"(बाद\s+में)", re.IGNORECASE),
]

BILLING_STARTED_PATTERNS = [
    re.compile(r"billing\s*start", re.IGNORECASE),
    re.compile(r"billing\s*ho\s*gayi", re.IGNORECASE),
    re.compile(r"billing\s*ho\s*chuki", re.IGNORECASE),
    re.compile(r"बिलिंग\s*स्टार्ट", re.IGNORECASE),
    re.compile(r"हो\s*गई", re.IGNORECASE),
    re.compile(r"शुरू\s*कर\s*दी", re.IGNORECASE),
]


def extract_digits(text: str) -> str:
    parts = re.findall(r"[A-Za-z]+|\d|[०-९]", text.lower())
    digits: list[str] = []
    for part in parts:
        if part in DIGIT_WORDS:
            digits.append(DIGIT_WORDS[part])
        elif part in DEVANAGARI_DIGITS:
            digits.append(DEVANAGARI_DIGITS[part])
        elif part.isdigit():
            digits.append(part)
    return "".join(digits)


def digits_to_tts(digits: str) -> str:
    return " ".join(DIGIT_TO_WORD[d] for d in digits if d in DIGIT_TO_WORD)


def normalize_email(text: str) -> str:
    candidate = text.lower()
    candidate = re.sub(r"\s*at the rate\s*", "@", candidate)
    candidate = re.sub(r"\s*@\s*", "@", candidate)
    candidate = re.sub(r"\s*dot\s*", ".", candidate)
    candidate = re.sub(r"\s*underscore\s*", "_", candidate)
    candidate = re.sub(r"\s*dash\s*", "-", candidate)
    for word, digit in DIGIT_WORDS.items():
        candidate = re.sub(rf"\b{word}\b", digit, candidate)
    candidate = re.sub(r"\s+", "", candidate)
    match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", candidate)
    return match.group(0) if match else ""


def email_to_tts(email: str) -> str:
    if not email:
        return ""

    parts = re.findall(r"[A-Za-z]+|\d|[@._-]", email)
    spoken: list[str] = []
    for part in parts:
        if part == "@":
            spoken.append("at the rate")
        elif part == ".":
            spoken.append("dot")
        elif part == "_":
            spoken.append("underscore")
        elif part == "-":
            spoken.append("dash")
        elif part.isdigit():
            spoken.append(DIGIT_TO_WORD[part])
        else:
            spoken.append(part.lower())
    return " ".join(spoken)


def has_callback_request(text: str) -> bool:
    return any(pattern.search(text) for pattern in CALLBACK_PATTERNS)


def extract_callback_phrase(text: str) -> str:
    normalized = " ".join(text.split())
    token_match = re.search(r"(\S+\s+(?:minute|मिनट)\s+बाद)", normalized, re.IGNORECASE)
    if token_match:
        return token_match.group(1)

    for pattern in CALLBACK_TIME_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return " ".join(match.group(1).split())
    return ""


def build_callback_closing(text: str) -> str:
    phrase = extract_callback_phrase(text)
    if phrase:
        return (
            f"जी बिल्कुल, मैं आपको {phrase} call करती हूँ। "
            "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे."
        )
    return "जी बिल्कुल, मैं थोड़ी देर बाद call करती हूँ। Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे."


def billing_started(text: str) -> bool:
    return any(pattern.search(text) for pattern in BILLING_STARTED_PATTERNS)


def apply_digit_buffer(existing: str, transcript: str, target: int, *, hard_limit: bool = False) -> tuple[str, str]:
    fresh = extract_digits(transcript)
    if not fresh:
        return existing, "no_digits"

    combined = existing + fresh
    if hard_limit and len(combined) > target:
        return "", "overflow"
    if len(combined) < target:
        return combined, "partial"
    if len(combined) == target:
        return combined, "complete"
    return combined[:target], "complete"


def extract_business_details(text: str, fallback_type: str = "", fallback_trade: str = "") -> tuple[str, str]:
    lowered = text.lower()
    business_type = fallback_type
    business_trade = fallback_trade

    for keyword, value in BUSINESS_TYPE_KEYWORDS.items():
        if keyword in lowered:
            business_type = value
            break

    for keyword, value in BUSINESS_TRADE_KEYWORDS.items():
        if keyword in lowered:
            business_trade = value
            break

    return business_type, business_trade


def extract_name_fragment(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[0-9०-९]", " ", cleaned)
    cleaned = re.sub(r"\b(?:जी|haan|हाँ|yes|number|contact|mobile|phone|hai|है)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_and_store(session: CallSession, state, transcript: str):
    if state.name == "VERIFY_BUSINESS_DETAILS":
        business_type, business_trade = extract_business_details(
            transcript,
            fallback_type=session.business_type or session.crm_business_type,
            fallback_trade=session.business_trade or session.crm_business_trade,
        )
        session.business_type = business_type
        session.business_trade = business_trade
        return

    if state.name == "VERIFY_EMAIL":
        email = normalize_email(transcript)
        if email:
            session.email = email
        return

    if state.name == "ASK_PURCHASE_AMOUNT":
        cleaned = transcript.strip()
        if cleaned:
            session.purchase_amount = cleaned
        return

    if state.name in {"SUPPORT_AND_REFERRAL", "COLLECT_REFERRAL"}:
        name = extract_name_fragment(transcript)
        if name:
            session.referral_name = name
        return


def build_render_context(session: CallSession) -> dict:
    company_name = session.company_name or session.firm_name or session.customer_name or "आपकी company"
    crm_pincode = session.crm_pincode or session.pincode
    crm_email = session.crm_email or session.email
    business_type = session.business_type or session.crm_business_type or "records में उपलब्ध नहीं"
    business_trade = session.business_trade or session.crm_business_trade or "records में उपलब्ध नहीं"

    whatsapp_digits = session.whatsapp_number or session.whatsapp_digit_buffer
    alternate_digits = session.alternate_number or session.alternate_digit_buffer
    pincode_digits = session.pincode or session.pincode_digit_buffer
    referral_digits = session.referral_number or session.referral_digit_buffer

    if session.awaiting_whatsapp_confirmation and whatsapp_digits:
        whatsapp_prompt = f"तो आपका WhatsApp number है — {digits_to_tts(whatsapp_digits)} — सही है?"
    elif session.whatsapp_digit_buffer:
        whatsapp_prompt = "जी, आगे बताइए।"
    else:
        whatsapp_prompt = "ठीक है जी — कृपया अपना WhatsApp number बताइए?"

    if session.awaiting_alternate_confirmation and alternate_digits:
        alternate_prompt = f"तो आपका alternate number है — {digits_to_tts(alternate_digits)} — सही है?"
    elif session.alternate_digit_buffer:
        alternate_prompt = "जी, आगे बताइए।"
    else:
        alternate_prompt = "ठीक है जी — कृपया alternate number बताइए?"

    if session.awaiting_pincode_confirmation and pincode_digits:
        pincode_prompt = f"तो आपका pin code है — {digits_to_tts(pincode_digits)} — सही है?"
    elif session.pincode_digit_buffer:
        pincode_prompt = "जी, आगे बताइए।"
    else:
        pincode_prompt = "जी, क्या आप अपना पूरा pin code एक बार में बता सकते हैं?"

    if session.awaiting_referral_confirmation and referral_digits:
        referral_prompt = f"तो referral का number है — {digits_to_tts(referral_digits)} — सही है?"
    elif session.referral_digit_buffer:
        referral_prompt = "जी, आगे बताइए।"
    else:
        referral_prompt = "जी, उनका contact number बताइए।"

    context = dict(session.__dict__)
    context.update(
        {
            "company_name": company_name,
            "spoken_crm_pincode": digits_to_tts(crm_pincode),
            "spoken_crm_email": email_to_tts(crm_email),
            "display_business_type": business_type,
            "display_business_trade": business_trade,
            "whatsapp_collection_prompt": whatsapp_prompt,
            "alternate_collection_prompt": alternate_prompt,
            "pincode_collection_prompt": pincode_prompt,
            "referral_collection_prompt": referral_prompt,
        }
    )
    return context
