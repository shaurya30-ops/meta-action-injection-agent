import re
from state_machine.session import CallSession
from state_machine.states import State

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

ROMAN_HINDI_DIGIT_WORDS = {
    "sifar": "0",
    "shunya": "0",
    "sunya": "0",
    "ek": "1",
    "do": "2",
    "teen": "3",
    "char": "4",
    "chaar": "4",
    "paanch": "5",
    "panch": "5",
    "cheh": "6",
    "chhe": "6",
    "saat": "7",
    "aath": "8",
    "ath": "8",
    "nau": "9",
    "nav": "9",
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

HINDI_NUMBER_WORDS = {
    "शून्य": "0",
    "सिफर": "0",
    "एक": "1",
    "दो": "2",
    "तीन": "3",
    "चार": "4",
    "पांच": "5",
    "पाँच": "5",
    "छह": "6",
    "छः": "6",
    "सात": "7",
    "आठ": "8",
    "नौ": "9",
    "दस": "10",
    "ग्यारह": "11",
    "बारह": "12",
    "तेरह": "13",
    "चौदह": "14",
    "पंद्रह": "15",
    "पन्द्रह": "15",
    "सोलह": "16",
    "सत्रह": "17",
    "अठारह": "18",
    "उन्नीस": "19",
    "बीस": "20",
    "इक्कीस": "21",
    "इकिस": "21",
    "बाईस": "22",
    "तेईस": "23",
    "चौबीस": "24",
    "पच्चीस": "25",
    "छब्बीस": "26",
    "सत्ताईस": "27",
    "अट्ठाईस": "28",
    "अठाईस": "28",
    "उनतीस": "29",
    "तीस": "30",
    "इकतीस": "31",
    "बत्तीस": "32",
    "तैंतीस": "33",
    "चौंतीस": "34",
    "चौतीस": "34",
    "पैंतीस": "35",
    "छत्तीस": "36",
    "सैंतीस": "37",
    "अड़तीस": "38",
    "अडतीस": "38",
    "उनतालीस": "39",
    "चालीस": "40",
    "इकतालीस": "41",
    "बयालीस": "42",
    "तैंतालीस": "43",
    "चवालीस": "44",
    "चौवालीस": "44",
    "पैंतालीस": "45",
    "छियालीस": "46",
    "सैंतालीस": "47",
    "अड़तालीस": "48",
    "अडतालीस": "48",
    "उनचास": "49",
    "पचास": "50",
    "इक्यावन": "51",
    "बावन": "52",
    "तिरपन": "53",
    "चौवन": "54",
    "पचपन": "55",
    "छप्पन": "56",
    "सत्तावन": "57",
    "अट्ठावन": "58",
    "अठावन": "58",
    "उनसठ": "59",
    "साठ": "60",
    "इकसठ": "61",
    "बासठ": "62",
    "तिरसठ": "63",
    "चौंसठ": "64",
    "चौसठ": "64",
    "पैंसठ": "65",
    "छियासठ": "66",
    "सड़सठ": "67",
    "सडसठ": "67",
    "अड़सठ": "68",
    "अडसठ": "68",
    "उनहत्तर": "69",
    "सत्तर": "70",
    "इकहत्तर": "71",
    "बहत्तर": "72",
    "तिहत्तर": "73",
    "चौहत्तर": "74",
    "पचहत्तर": "75",
    "छिहत्तर": "76",
    "सतहत्तर": "77",
    "अठहत्तर": "78",
    "उन्नासी": "79",
    "उन्यासी": "79",
    "अस्सी": "80",
    "इक्यासी": "81",
    "बयासी": "82",
    "तिरासी": "83",
    "चौरासी": "84",
    "पचासी": "85",
    "छियासी": "86",
    "सत्तासी": "87",
    "अठासी": "88",
    "नवासी": "89",
    "नब्बे": "90",
    "इक्यानवे": "91",
    "बानवे": "92",
    "तिरानवे": "93",
    "चौरानवे": "94",
    "पंचानवे": "95",
    "छियानवे": "96",
    "सत्तानवे": "97",
    "अट्ठानवे": "98",
    "अठानवे": "98",
    "निन्यानवे": "99",
    "सौ": "100",
    "एक सौ": "100",
}

SPOKEN_NUMBER_WORDS = {
    **DIGIT_WORDS,
    **ROMAN_HINDI_DIGIT_WORDS,
    **HINDI_NUMBER_WORDS,
}

REPEAT_MARKERS = {
    "double": 2,
    "dubble": 2,
    "डबल": 2,
    "triple": 3,
    "tripple": 3,
    "ट्रिपल": 3,
}

NUMBER_TOKEN_PATTERN = re.compile(r"[A-Za-z]+|[\u0900-\u097F]+|\d+|[०-९]+")
DEVANAGARI_NUMBER_TOKEN = re.compile(r"^[०-९]+$")

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
    "pharmacy": "Pharma",
    "medicine": "Medical",
    "medicines": "Medical",
    "chemist": "Medical",
    "surgical": "Medical",
    "grocery": "Grocery",
    "kirana": "Grocery",
    "garment": "Garment",
    "textile": "Textile",
    "hardware": "Hardware",
    "electrical": "Electronics",
    "cosmetic": "Cosmetics",
    "fmcg": "FMCG",
    "electronics": "Electronics",
    "mobile": "Electronics",
    "medical": "Medical",
}

MEDICAL_BUSINESS_TYPE_VALUES = {
    "pharma",
    "medical",
    "medicine",
    "medicines",
    "pharmaceutical",
    "pharmacy",
    "chemist",
    "surgical",
    "pharma / medical",
}

BUSINESS_TRADE_KEYWORDS = {
    "wholesaler": "Wholesaler",
    "wholesale": "Wholesaler",
    "trader": "Trader",
    "dealer": "Dealer",
    "retailer": "Retailer",
    "retail": "Retailer",
    "distributor": "Distributor",
    "distribution": "Distributor",
    "stockist": "Stockist",
    "super stockist": "Stockist",
    "manufacturer": "Manufacturer",
    "manufacturing": "Manufacturer",
}

EMAIL_FRAGMENT_HINTS = (
    "@",
    "at the rate",
    "dot",
    "underscore",
    "dash",
    "gmail",
    "yahoo",
    "outlook",
    "hotmail",
    "rediff",
    "icloud",
    "proton",
    "mail",
    "email",
)

EMAIL_FRAGMENT_STOPWORDS = {
    "email",
    "id",
    "emailid",
    "meri",
    "mera",
    "my",
    "hai",
    "is",
    "the",
    "rate",
    "at",
}

CALLBACK_PATTERNS = [
    re.compile(r"बाद में\s*call", re.IGNORECASE),
    re.compile(r"अभी\s*busy", re.IGNORECASE),
    re.compile(r"abhi\s*busy", re.IGNORECASE),
    re.compile(r"minute\s+बाद", re.IGNORECASE),
    re.compile(r"मिनट\s+बाद", re.IGNORECASE),
    re.compile(r"थोड़ी\s+देर\s+बाद", re.IGNORECASE),
    re.compile(r"thodi\s*der\s*baad", re.IGNORECASE),
    re.compile(r"अभी\s*वक्त\s*नहीं", re.IGNORECASE),
    re.compile(r"abhi\s*time\s*nahi", re.IGNORECASE),
    re.compile(r"call\s*करो", re.IGNORECASE),
    re.compile(r"baad\s*mein\s*baat", re.IGNORECASE),
]

CALLBACK_TIME_PATTERNS = [
    re.compile(r"(\S+\s+(?:minute|minutes|mins?|मिनट)\s+बाद)", re.IGNORECASE),
    re.compile(r"(\S+\s+(?:hour|hours|घंटे?|घंटा)\s+बाद)", re.IGNORECASE),
    re.compile(r"(आधे\s+घंटे\s+बाद)", re.IGNORECASE),
    re.compile(r"((?:आज|कल|परसों|today|tomorrow)\s+(?:सुबह|शाम|दोपहर|रात|morning|evening|afternoon|night)\s+\S+\s*बजे)", re.IGNORECASE),
    re.compile(r"(थोड़ी\s+देर\s+बाद)", re.IGNORECASE),
    re.compile(r"((?:आज|कल|परसों|today|tomorrow)(?:\s+(?:सुबह|शाम|दोपहर|रात|morning|evening|afternoon|night))?)", re.IGNORECASE),
    re.compile(r"(\S+\s*बजे)", re.IGNORECASE),
    re.compile(r"(\d{1,2}\s*(?:am|pm))", re.IGNORECASE),
    re.compile(r"(बाद\s+में)", re.IGNORECASE),
]

GENERIC_CALLBACK_PHRASES = {
    "बाद में",
    "थोड़ी देर बाद",
}

FIXED_CLOSING_STANDARD_LINE = "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे."
FIXED_CLOSING_ALTERNATE_LINE = "अपना समय देने के लिए धन्यवाद। आपका दिन शुभ रहे।"

BILLING_STARTED_PATTERNS = [
    re.compile(r"billing\s*start", re.IGNORECASE),
    re.compile(r"billing\s*ho\s*gayi", re.IGNORECASE),
    re.compile(r"billing\s*ho\s*chuki", re.IGNORECASE),
    re.compile(r"billing\s*chal\s*rahi", re.IGNORECASE),
    re.compile(r"invoice\s*ban", re.IGNORECASE),
    re.compile(r"बिलिंग\s*स्टार्ट", re.IGNORECASE),
    re.compile(r"हो\s*गई", re.IGNORECASE),
    re.compile(r"शुरू\s*कर\s*दी", re.IGNORECASE),
]


def _consume_number_phrase(tokens: list[str], start: int) -> tuple[str, int]:
    if start >= len(tokens):
        return "", 0

    max_span = min(3, len(tokens) - start)
    for span in range(max_span, 0, -1):
        phrase = " ".join(tokens[start : start + span])
        if phrase in SPOKEN_NUMBER_WORDS:
            return SPOKEN_NUMBER_WORDS[phrase], span

    token = tokens[start]
    if token.isdigit():
        return token, 1
    if DEVANAGARI_NUMBER_TOKEN.fullmatch(token):
        return "".join(DEVANAGARI_DIGITS[char] for char in token), 1
    return "", 0


def extract_digits(text: str) -> str:
    parts = [part.lower() for part in NUMBER_TOKEN_PATTERN.findall(text)]
    digits: list[str] = []
    index = 0

    while index < len(parts):
        repeat = REPEAT_MARKERS.get(parts[index])
        if repeat:
            repeated_digit, consumed = _consume_number_phrase(parts, index + 1)
            if repeated_digit and len(repeated_digit) == 1:
                digits.append(repeated_digit * repeat)
                index += consumed + 1
                continue

        part_digits, consumed = _consume_number_phrase(parts, index)
        if part_digits:
            digits.append(part_digits)
            index += consumed
            continue

        index += 1
    return "".join(digits)


def extract_named_digit_slots(text: str) -> dict[str, str]:
    slots = {"phone": "", "pincode": ""}
    normalized = " ".join(text.strip().split())
    if not normalized:
        return slots

    segments = [
        segment.strip(" ,.;:-")
        for segment in re.split(r"\b(?:aur|and)\b|[;,]", normalized, flags=re.IGNORECASE)
        if segment.strip(" ,.;:-")
    ]
    if not segments:
        segments = [normalized]

    for segment in segments:
        lowered = segment.lower()
        digits = extract_digits(segment)
        if not digits:
            continue
        if re.search(r"\b(?:pin\s*code|pincode|pin)\b|पिन\s*कोड|पिन", lowered, re.IGNORECASE):
            slots["pincode"] = digits
            continue
        if re.search(
            r"\b(?:whatsapp|alternate|contact|mobile|phone|number)\b|व्हाट्सऐप|अल्टरनेट|नंबर|मोबाइल|फोन",
            lowered,
            re.IGNORECASE,
        ) and not slots["phone"]:
            slots["phone"] = digits

    if not slots["phone"] and slots["pincode"]:
        residual_text = re.sub(
            r"\b(?:pin\s*code|pincode|pin)\b|पिन\s*कोड|पिन",
            " ",
            normalized,
            flags=re.IGNORECASE,
        )
        residual_digits = extract_digits(residual_text)
        if residual_digits and residual_digits != slots["pincode"]:
            slots["phone"] = residual_digits

    return slots


def digits_to_tts(digits: str) -> str:
    return " ".join(DIGIT_TO_WORD[d] for d in digits if d in DIGIT_TO_WORD)


def normalize_email(text: str) -> str:
    candidate = text.lower()
    candidate = re.sub(r"^\s*(?:नहीं|नही|नई|no|nahi|nahin|wrong|गलत)\s*,?\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(
        r"^\s*(?:मेरी|मेरा|my)\s*email(?:\s*id)?\s*(?:है|hai|is)?\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"^\s*email(?:\s*id)?\s*(?:है|hai|is)?\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\s*at the rate\s*", "@", candidate)
    candidate = re.sub(r"\s*@\s*", "@", candidate)
    candidate = re.sub(r"\s*dot\s*", ".", candidate)
    candidate = re.sub(r"\s*underscore\s*", "_", candidate)
    candidate = re.sub(r"\s*dash\s*", "-", candidate)
    for repeat_word, repeat_count in REPEAT_MARKERS.items():
        for word, digit in DIGIT_WORDS.items():
            candidate = re.sub(
                rf"\b{repeat_word}\s+{word}\b",
                digit * repeat_count,
                candidate,
            )
    for word, digit in DIGIT_WORDS.items():
        candidate = re.sub(rf"\b{word}\b", digit, candidate)
    candidate = re.sub(r"\s+", "", candidate)
    match = re.search(r"[^\s@,;:!?।]+@[^\s@,;:!?।]+\.[A-Za-z]{2,}", candidate)
    return match.group(0) if match else ""


def normalize_business_type_for_speech(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in MEDICAL_BUSINESS_TYPE_VALUES:
        return "Pharma / Medical"
    return value


def email_to_tts(email: str) -> str:
    if not email:
        return ""

    parts: list[str] = []
    current: list[str] = []
    for char in email:
        if char in "@._-":
            if current:
                parts.append("".join(current))
                current = []
            parts.append(char)
            continue
        if char.isdigit():
            if current:
                parts.append("".join(current))
                current = []
            parts.append(char)
            continue
        current.append(char)

    if current:
        parts.append("".join(current))

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


def merge_spoken_email_fragments(existing: str, transcript: str, *, reset: bool = False) -> str:
    base = "" if reset else " ".join(existing.strip().split())
    fragment = " ".join(transcript.strip().split())
    if not fragment:
        return base
    if not base:
        return fragment
    return f"{base} {fragment}".strip()


def looks_like_email_fragment(text: str) -> bool:
    normalized = " ".join(text.strip().split()).lower()
    if not normalized:
        return False

    if normalize_email(normalized):
        return True

    if any(hint in normalized for hint in EMAIL_FRAGMENT_HINTS):
        return True

    ascii_tokens = re.findall(r"[A-Za-z]+|\d+|[०-९]+", normalized)
    useful_tokens = [token for token in ascii_tokens if token not in EMAIL_FRAGMENT_STOPWORDS]
    if not useful_tokens:
        return False

    return all(
        token in DIGIT_WORDS
        or token.isdigit()
        or re.fullmatch(r"[a-z]+", token) is not None
        for token in useful_tokens
    )


def email_fragment_restart_requested(text: str) -> bool:
    lowered = " ".join(text.strip().split()).lower()
    return bool(
        re.search(
            r"^(?:नहीं|नही|नई|no|nahi|nahin|wrong|गलत)\b",
            lowered,
            re.IGNORECASE,
        )
    )


def extract_email_candidate(session: CallSession, transcript: str) -> str:
    if session.current_state.name in {"VERIFY_EMAIL", "COLLECT_EMAIL_CORRECTION", "CONFIRM_EMAIL_CORRECTION"} and session.email_fragment_buffer:
        combined = merge_spoken_email_fragments(
            session.email_fragment_buffer,
            transcript,
            reset=email_fragment_restart_requested(transcript),
        )
        combined_email = normalize_email(combined)
        if combined_email:
            return combined_email

    direct_email = normalize_email(transcript)
    if direct_email:
        return direct_email

    return ""


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


def has_specific_callback_phrase(text: str) -> bool:
    phrase = extract_callback_phrase(text)
    return bool(phrase and phrase not in GENERIC_CALLBACK_PHRASES)


def build_callback_closing(text: str) -> str:
    phrase = extract_callback_phrase(text)
    if phrase:
        return f"जी बिल्कुल, मैं आपको {phrase} call करती हूँ।"
    return "जी बिल्कुल, मैं थोड़ी देर बाद call करती हूँ।"


def build_terminal_closing_text(session: CallSession) -> str:
    acknowledgement = " ".join(session.terminal_ack_text.strip().split())

    if session.current_state == State.INVALID_REGISTRATION:
        acknowledgement = acknowledgement or (
            "जी, धन्यवाद बताने के लिए. लगता है यह सही customer detail नहीं है, इसलिए मैं call यहीं close करती हूँ।"
        )

    return acknowledgement


def build_fixed_closing_text(session: CallSession) -> str:
    if session.fixed_closing_variant == "alternate":
        return FIXED_CLOSING_ALTERNATE_LINE
    return FIXED_CLOSING_STANDARD_LINE


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
    cleaned = re.sub(
        r"\b(?:जी|haan|हाँ|yes|number|contact|mobile|phone|hai|है|उसका|unka|उनका|referral|referal|वाले|वाला|"
        r"बताया|लिखो|लिखिए|note|करो|करिए|share|madam|ma'am|mam|मैम|तो|पूरा|दस|ten|"
        r"नाम|का|की|बताइए|बताओ|लिया|लिए)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_wrong_contact_company_fragment(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    for phrase in ("से बोल रहे हैं", "से बोल रही हैं", "से बोल रहा हूँ", "से बोल रही हूँ", "से रहे हैं"):
        cleaned = re.sub(phrase, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:जी|haan|हाँ|yes|नहीं|नही|नई|no|wrong|number|company|लगाया|यहाँ|वहाँ|से|बोल|रहे|रही|हैं|है|"
        r"main|mein|mai|hum|हम)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_wrong_contact_trade_fragment(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"\b(?:जी|haan|हाँ|yes|trade|business|का|की|क्या|बताइए|बताओ|है|hai)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_wrong_contact_type_fragment(text: str) -> str:
    lowered = text.lower()
    if "manufacturer" in lowered:
        return "Manufacturer"
    if "distributor" in lowered:
        return "Distributor"
    if "retailer" in lowered or "retail" in lowered:
        return "Retailer"

    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"\b(?:जी|haan|हाँ|yes|type|business|manufacturer|distributor|retailer|का|की|क्या|बताइए|बताओ|है|hai)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_software_name(text: str) -> str:
    match = re.search(r"\b(Tally|Busy|Vyapar|Marg(?:\s*ERP)?)\b", text, re.IGNORECASE)
    if match:
        software = match.group(1)
        return "Marg ERP" if software.lower().startswith("marg") else software.title()

    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"\b(?:जी|haan|हाँ|yes|software|liya|li|ले|लिया|switch|किया|कर|already|हमने|maine|main|हम)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_and_store(session: CallSession, state, transcript: str):
    if state.name == "ASK_WRONG_CONTACT_COMPANY":
        company = extract_wrong_contact_company_fragment(transcript)
        if company:
            session.wrong_contact_company = company
        return

    if state.name == "ASK_WRONG_CONTACT_TRADE":
        trade = extract_wrong_contact_trade_fragment(transcript)
        if trade:
            session.wrong_contact_trade = trade
        return

    if state.name == "ASK_WRONG_CONTACT_TYPE":
        business_type = extract_wrong_contact_type_fragment(transcript)
        if business_type:
            session.wrong_contact_type = business_type
        return

    if state.name == "ASK_WRONG_CONTACT_NAME":
        name = extract_name_fragment(transcript)
        if name:
            session.wrong_contact_name = name
        return

    if state.name == "COLLECT_COMPLAINT_DETAIL":
        cleaned = transcript.strip()
        if cleaned:
            session.complaint_detail = cleaned
        return

    if state.name == "ESCALATE_PAYMENT_DATE":
        cleaned = transcript.strip()
        if cleaned:
            session.partner_payment_date = cleaned
        return

    if state.name == "ESCALATE_PARTNER_NAME":
        name = extract_name_fragment(transcript)
        if name:
            session.partner_name = name
        return

    if state.name == "ESCALATE_SWITCHED_SOFTWARE":
        software_name = extract_software_name(transcript)
        if software_name:
            session.switched_software_name = software_name
        return

    if state.name == "ESCALATE_SWITCH_REASON":
        cleaned = transcript.strip()
        if cleaned:
            session.switched_software_reason = cleaned
        return

    if state.name == "ESCALATE_CLOSURE_REASON":
        cleaned = transcript.strip()
        if cleaned:
            session.business_closed_reason = cleaned
        return

    if state.name == "ESCALATE_TECHNICAL_ISSUE":
        cleaned = transcript.strip()
        if cleaned:
            session.technical_issue_detail = cleaned
        return

    if state.name == "COLLECT_TRAINING_PINCODE":
        digits = extract_digits(transcript)
        if digits:
            session.training_area_pincode = digits[:6]
        return

    if state.name in {"VERIFY_BUSINESS_DETAILS", "CONFIRM_BUSINESS_DETAILS"}:
        business_type, business_trade = extract_business_details(
            transcript,
            fallback_type=session.business_type or session.crm_business_type,
            fallback_trade=session.business_trade or session.crm_business_trade,
        )
        session.business_type = business_type
        session.business_trade = business_trade
        return

    if state.name in {"VERIFY_EMAIL", "COLLECT_EMAIL_CORRECTION", "CONFIRM_EMAIL_CORRECTION"}:
        email = extract_email_candidate(session, transcript)
        if email:
            session.email = email
        return

    if state.name == "ASK_PURCHASE_AMOUNT":
        cleaned = transcript.strip()
        if cleaned:
            session.purchase_amount = cleaned
        return

    if state.name == "ASK_BILLING_START_TIMELINE":
        cleaned = transcript.strip()
        if cleaned:
            session.billing_start_timeline = cleaned
        return

    if state.name in {"ASK_CONCERNED_PERSON_CONTACT", "COLLECT_CONCERNED_PERSON_NUMBER", "CONFIRM_CONCERNED_PERSON_NUMBER"}:
        name = extract_name_fragment(transcript)
        if name:
            session.concerned_person_name = name
        return

    if state.name in {"SUPPORT_AND_REFERRAL", "COLLECT_REFERRAL_NAME"}:
        name = extract_name_fragment(transcript)
        if name:
            session.referral_name = name
        return


def _clarification_target_state(session: CallSession) -> State | None:
    return session.resume_state or session.current_state


def _build_clarification_response_prompt(session: CallSession) -> str:
    state = _clarification_target_state(session)
    kind = session.last_clarification_kind or "meaning"
    query_text = (session.last_user_query_text or "").lower()

    company_name = session.company_name or session.firm_name or session.customer_name or "आपकी company"
    crm_pincode = session.pincode or session.crm_pincode
    crm_email = session.crm_email
    current_email = session.email or session.crm_email
    business_type = normalize_business_type_for_speech(
        session.business_type or session.crm_business_type or "records में available detail"
    )
    business_trade = session.business_trade or session.crm_business_trade or "records में available detail"
    whatsapp_digits = session.whatsapp_number or session.whatsapp_digit_buffer or session.primary_phone
    alternate_digits = session.alternate_number or session.alternate_digit_buffer
    pincode_digits = session.pincode or session.pincode_digit_buffer or session.crm_pincode
    referral_digits = session.referral_number or session.referral_digit_buffer
    referral_name = session.referral_name or "उस person"

    if state in {State.OPENING_GREETING, State.CONFIRM_IDENTITY}:
        if kind == "reason":
            return (
                f"जी, मैं आकृति बोल रही हूँ Marg ई आर पी software Delhi head office से, "
                f"और मैं {company_name} की call identity confirm कर रही हूँ. "
                f"क्या मेरी बात {company_name} में हो रही है?"
            )
        return (
            f"जी, मैं आकृति बोल रही हूँ Marg ई आर पी software Delhi head office से. "
            f"क्या मेरी बात {company_name} में हो रही है?"
        )

    if state == State.CHECK_AVAILABILITY:
        return (
            "जी, ये Marg ई आर पी software की तरफ से short post-sale feedback और verification call है. "
            "क्या अभी दो मिनट बात हो सकती है?"
        )

    if state == State.ASK_BILLING_STATUS:
        if kind == "reason":
            return (
                "जी, मैं इसलिए पूछ रही हूँ ताकि समझ सकूँ software smoothly start हुआ है या कहीं help की ज़रूरत है. "
                "क्या आपके software में billing start हो गई है?"
            )
        return "जी, मेरा मतलब था — क्या आपने software में billing या invoice बनाना start किया है?"

    if state == State.EXPLORE_BILLING_BLOCKER:
        if kind == "reason":
            return (
                "जी, मैं इसलिए पूछ रही हूँ ताकि अगर कहीं issue है तो सही help बता सकूँ. "
                "अभी billing start न होने की main वजह क्या है?"
            )
        return "जी, मेरा मतलब था — अभी billing start नहीं हुई, तो उसकी main वजह क्या है?"

    if state == State.ASK_BILLING_START_TIMELINE:
        return "जी, मेरा मतलब था — आप कब तक billing start करने की planning कर रहे हैं?"

    if state == State.VERIFY_WHATSAPP:
        if kind == "reason":
            return (
                "जी, मैं इसलिए पूछ रही हूँ ताकि support updates सही number पर पहुँचें. "
                "जिस number से अभी बात हो रही है — वो क्या WhatsApp पर available है?"
            )
        return (
            "जी, मैं यही confirm कर रही हूँ कि जिस number से अभी बात हो रही है, "
            "क्या वही WhatsApp पर available है?"
        )

    if state == State.COLLECT_WHATSAPP_NUMBER:
        return "जी, मैं आपका WhatsApp number note कर रही हूँ. कृपया number बताइए?"

    if state == State.CONFIRM_WHATSAPP_NUMBER:
        if kind == "recorded_value" and whatsapp_digits:
            return (
                f"जी, मैंने WhatsApp number — {digits_to_tts(whatsapp_digits)} — note किया है. "
                "क्या यही सही है?"
            )
        return f"जी, मैं वही WhatsApp number confirm कर रही हूँ — {digits_to_tts(whatsapp_digits)} — क्या यही सही है?"

    if state == State.ASK_ALTERNATE_NUMBER:
        if kind == "reason":
            return (
                "जी, मैं alternate contact इसलिए पूछ रही हूँ ताकि जरूरत पड़ने पर backup number रहे. "
                "क्या आप कोई alternate number भी देना चाहेंगे?"
            )
        return "जी, मेरा मतलब था — अगर कोई दूसरा contact number हो, तो क्या आप देना चाहेंगे?"

    if state == State.COLLECT_ALTERNATE_NUMBER:
        return "जी, मैं alternate number note कर रही हूँ. कृपया number बताइए?"

    if state == State.CONFIRM_ALTERNATE_NUMBER:
        if kind == "recorded_value" and alternate_digits:
            return (
                f"जी, मैंने alternate number — {digits_to_tts(alternate_digits)} — note किया है. "
                "क्या यही सही है?"
            )
        return f"जी, मैं वही alternate number confirm कर रही हूँ — {digits_to_tts(alternate_digits)} — क्या यही सही है?"

    if state == State.VERIFY_PINCODE:
        if kind == "recorded_value" and crm_pincode:
            return (
                f"जी, मेरे record में pin code — {digits_to_tts(crm_pincode)} — है. "
                "क्या यही सही है?"
            )
        if kind == "reason":
            return (
                "जी, मैं area details update रखने के लिए pin code confirm कर रही हूँ. "
                f"आपका area pin code — {digits_to_tts(crm_pincode)} — यही है?"
            )
        return f"जी, मैं आपके record का pin code confirm कर रही हूँ — {digits_to_tts(crm_pincode)} — क्या यही सही है?"

    if state == State.COLLECT_PINCODE:
        if kind == "recorded_value" and pincode_digits:
            return (
                f"जी, अभी मैंने pin code में — {digits_to_tts(pincode_digits)} — load किया है. "
                "अगर यही पूरा है तो हाँ कहिए, वरना बाकी digit बता दीजिए।"
            )
        return "जी, मैं नया pin code note कर रही हूँ. कृपया pin code बताइए?"

    if state == State.CONFIRM_PINCODE:
        if kind == "recorded_value" and pincode_digits:
            return (
                f"जी, मैंने pin code — {digits_to_tts(pincode_digits)} — note किया है. "
                "क्या यही सही है?"
            )
        return f"जी, मैं वही pin code confirm कर रही हूँ — {digits_to_tts(pincode_digits)} — क्या यही सही है?"

    if state == State.VERIFY_BUSINESS_DETAILS:
        if kind == "recorded_value":
            return (
                f"जी, मेरे record में business type {business_type} है और trade {business_trade} है. "
                "क्या यही सही है?"
            )
        if kind == "reason":
            return (
                "जी, मैं records सही रखने के लिए business type और trade confirm कर रही हूँ. "
                f"आपका business type {business_type} है — और trade {business_trade} है — यही सही है?"
            )
        return (
            f"जी, मैं आपके business details confirm कर रही हूँ — business type {business_type} और trade {business_trade}. "
            "क्या यही सही है?"
        )

    if state == State.CONFIRM_BUSINESS_DETAILS:
        return (
            f"जी, मैं corrected business details confirm कर रही हूँ — business type {business_type} और trade {business_trade}. "
            "क्या यही सही है?"
        )

    if state == State.VERIFY_EMAIL:
        if kind == "recorded_value" and crm_email:
            return (
                f"जी, मेरे record में email ID — {email_to_tts(crm_email)} — है. "
                "क्या यही सही है?"
            )
        if kind == "reason":
            return (
                "जी, मैं email इसलिए confirm कर रही हूँ ताकि future support updates सही address पर जाएँ. "
                f"आपकी email ID — {email_to_tts(crm_email)} — यही है?"
            )
        return f"जी, मैं आपकी email ID verify कर रही हूँ — {email_to_tts(crm_email)} — क्या यही सही है?"

    if state == State.COLLECT_EMAIL_CORRECTION:
        return "जी, मैं corrected email ID note कर रही हूँ. कृपया email ID बताइए?"

    if state == State.CONFIRM_EMAIL_CORRECTION:
        if kind == "recorded_value" and current_email:
            return (
                f"जी, मैंने corrected email ID — {email_to_tts(current_email)} — note की है. "
                "क्या यही सही है?"
            )
        return f"जी, मैं वही corrected email ID confirm कर रही हूँ — {email_to_tts(current_email)} — क्या यही सही है?"

    if state == State.ASK_PURCHASE_AMOUNT:
        if kind == "reason":
            return (
                "जी, मैं purchase detail note करने के लिए पूछ रही हूँ ताकि record complete रहे. "
                "आप बता सकते हैं — आपने जो software purchase किया था, वो किस amount पर था?"
            )
        return "जी, मेरा मतलब था — आपने software किस amount पर purchase किया था?"

    if state == State.SUPPORT_AND_REFERRAL:
        return (
            "जी, मेरा मतलब था — अगर software में कोई issue आए तो Marg Help और Ticket option available हैं. "
            "और अगर आपके known में कोई person billing software लेने में interested हो, तो क्या आप उनका नाम और contact number share कर सकते हैं?"
        )

    if state == State.COLLECT_REFERRAL_NAME:
        return "जी, मैं referral के लिए person का नाम note कर रही हूँ. कृपया उनका नाम बताइए?"

    if state == State.COLLECT_REFERRAL_NUMBER:
        if kind == "recorded_value":
            if "नाम" in query_text or "name" in query_text:
                if referral_digits:
                    return (
                        f"जी, मैंने referral में नाम {referral_name} जी note किया है, "
                        f"और number में अभी {digits_to_tts(referral_digits)} load किया है. "
                        "बाकी digit बता दीजिए।"
                    )
                return f"जी, मैंने referral में नाम {referral_name} जी note किया है. अब उनका contact number बताइए?"
            if referral_digits:
                return (
                    f"जी, मैंने referral में {referral_name} जी का number — {digits_to_tts(referral_digits)} — "
                    "अभी तक note किया है. अगर यही पूरा है तो हाँ कहिए, वरना बाकी digit बता दीजिए।"
                )
            return f"जी, मैंने referral में नाम {referral_name} जी note किया है. अब उनका contact number बताइए?"
        if kind == "reason":
            return f"जी, मैं {referral_name} जी का contact number note कर रही हूँ. कृपया number बताइए?"
        return f"जी, referral complete करने के लिए {referral_name} जी का contact number चाहिए. कृपया number बताइए?"

    if state == State.CONFIRM_REFERRAL_NUMBER:
        if kind == "recorded_value":
            return (
                f"जी, मैंने नाम {referral_name} जी note किया है "
                f"और number — {digits_to_tts(referral_digits)} — सुना है. क्या यही सही है?"
            )
        return (
            f"जी, मैं referral detail confirm कर रही हूँ — {referral_name} जी का number "
            f"{digits_to_tts(referral_digits)}. क्या यही सही है?"
        )

    return (
        "जी, मैं short में फिर से बता देती हूँ — ये एक verification call है और मैं आपकी details confirm कर रही हूँ. "
        "क्या अब आगे बढ़ें?"
    )


def build_query_response_prompt(session: CallSession) -> str:
    query_type = session.last_user_query_type
    target_state = session.resume_state or session.current_state

    if query_type in {"technical_support", "dealer_setup"}:
        if query_type == "dealer_setup":
            return (
                "जी, समझ सकती हूँ — setup phase में थोड़ा time लगता है. "
                "Software के home page पर 'Marg Help' में step-by-step images और videos मिल जाएँगे. "
                "और अगर setup complete कराने में help चाहिए, तो 'Ticket' option से हमारी team की side से call आ जाएगी. "
                "क्या इससे थोड़ी clarity मिली?"
            )
        return (
            "जी, अच्छा किया आपने बताया. इसके लिए software के home page पर 'Ticket' का option है — "
            "license number डालकर ticket raise करें, हमारी team की side से call आ जाएगी. "
            "क्या इससे आपका सवाल clear हो गया?"
        )

    if query_type == "pricing":
        return (
            "जी, इसकी exact pricing आपके plan पर depend करती है. इसके लिए आप ticket raise करें "
            "या Marg Help section देखें — हमारी team आपको सही detail बता देगी. "
            "क्या इससे आपका सवाल clear हो गया?"
        )

    if query_type == "clarification":
        return _build_clarification_response_prompt(session)

    if query_type == "general" and target_state == State.ASK_PURCHASE_AMOUNT:
        return (
            "जी, मेरे record में exact purchase amount अभी clearly visible नहीं है, इसलिए मैं आपसे confirm कर रही हूँ. "
            "अगर exact amount याद न हो तो भी कोई बात नहीं — आप अंदाज़ा amount बता सकते हैं. "
            "क्या इससे बात clear हुई?"
        )

    return (
        "जी, मैं short में बता देती हूँ. अगर detail support चाहिए, तो Marg Help section या Ticket option "
        "से हमारी team तक बात पहुँच जाएगी. क्या इससे आपका सवाल clear हो गया?"
    )


def build_callback_time_prompt(session: CallSession) -> str:
    if session.callback_prompt_override.strip():
        return session.callback_prompt_override.strip()

    if session.callback_time_attempts > 0:
        return (
            "जी, ताकि मैं सही time पर call करूँ, कृपया सिर्फ time या दिन बता दीजिए — "
            "जैसे आज शाम, कल सुबह, या 10 minute बाद."
        )

    return "तो मैं कब call करूँ — आप बताइए कौन सा time सही रहेगा?"


def build_callback_confirmation_prompt(session: CallSession) -> str:
    phrase = session.callback_time_phrase or "थोड़ी देर बाद"
    return f"जी, तो मैं {phrase} call करूँगी — सही है?"


def build_billing_blocker_support_prefix(session: CallSession) -> str:
    reason = session.billing_blocker_reason or session.last_blocker_reason
    if reason == "partner_non_responsive":
        return (
            "जी, मैंने detail note कर ली है. हम partner से contact करेंगे. "
            "20 से 48 घंटों के अंदर update मिल जाना चाहिए."
        )
    if reason == "setup_in_progress":
        return (
            "जी, बिल्कुल समझ सकती हूँ — setup पूरा होने में थोड़ा time लग सकता है. "
            "जब setup complete हो जाए, Marg Help section में step-by-step guidance मिल जाएगी."
        )
    if reason == "technical_issue":
        return (
            "जी, issue note कर लिया है. Marg Help और Ticket option भी available हैं. "
            "हमारी team 24 घंटों के अंदर contact करेगी."
        )
    if reason in {"dealer_setup", "training_pending"}:
        return (
            "जी, training request note कर ली है. 24 से 48 घंटों के अंदर हमारी team contact करेगी."
        )
    if reason == "migration_delay":
        return (
            "जी, ठीक है — migration complete होते ही billing start की जा सकती है."
        )
    if reason == "no_time":
        return (
            "जी, बिल्कुल समझ सकती हूँ — जैसे ही time मिलेगा, आप billing start कर सकते हैं."
        )
    if reason in {"switched_software", "business_closed", "abusive_language", "generic_escalation"}:
        return "हमारी team आपसे जल्द contact करेगी."
    return "जी, noted."


def build_complaint_detail_prompt(_session: CallSession) -> str:
    return "जी, अच्छा किया आपने बताया. कृपया short में बताइए issue क्या है?"


def build_payment_date_prompt(_session: CallSession) -> str:
    return "जी, payment आपने किस date को की थी?"


def build_partner_name_prompt(_session: CallSession) -> str:
    return "और partner का नाम क्या है?"


def build_switched_software_prompt(_session: CallSession) -> str:
    return "जी, आपने कौन सा software लिया है?"


def build_switch_reason_prompt(session: CallSession) -> str:
    if session.switched_software_name:
        return f"ठीक है जी. {session.switched_software_name} लेने की main वजह क्या रही?"
    return "ठीक है जी. switch करने की main वजह क्या रही?"


def build_closure_reason_prompt(_session: CallSession) -> str:
    return "जी, अगर आप बताना चाहें तो इसकी main वजह क्या रही?"


def build_technical_issue_prompt(_session: CallSession) -> str:
    return "जी, short में बताइए technical issue क्या आ रही है?"


def build_training_pincode_prompt(_session: CallSession) -> str:
    return "जी, training arrange कराने के लिए area pin code बता दीजिए?"


def build_billing_blocker_prompt(session: CallSession) -> str:
    if session.billing_blocker_refusal_count == 1:
        return "अच्छा — क्या कोई technical issue आ रही है, या कोई और वजह है? शायद मैं थोड़ी help कर सकती हूँ।"
    if session.billing_blocker_refusal_count >= 2:
        return "जी, ये जानना इसलिए ज़रूरी है ताकि अगर कोई problem हो तो हम solve कर सकें। क्या बता सकते हैं?"
    return "अच्छा, अभी billing start नहीं हुई — क्या कोई technical issue आ रही है, या कोई और वजह है?"


def build_billing_start_timeline_prompt(session: CallSession) -> str:
    reason = session.billing_blocker_reason or session.last_blocker_reason
    if reason == "migration_delay":
        return "तो data migration कब तक complete होने की संभावना है?"
    if reason == "no_time":
        return "तो आप कब तक time निकाल पाएँगे?"
    return "तो आप कब तक billing start करने की planning कर रहे हैं?"


def build_detour_anything_else_prompt(session: CallSession) -> str:
    return "क्या कोई और बात है?"


def build_purchase_amount_prompt(session: CallSession) -> str:
    if session.purchase_amount_refusal_count == 1:
        return "जी, ये amount database clean रहता है, इसलिए एक बार confirm कर रही हूँ। अगर याद हो तो बता दीजिए?"
    return "आप बता सकते हैं — आपने जो software purchase किया था, वो किस amount पर था?"


def build_email_collection_prompt(session: CallSession) -> str:
    if session.email_fragment_buffer and session.current_state.name == "COLLECT_EMAIL_CORRECTION":
        return "जी, आगे बताइए।"
    if session.email_refusal_count == 1:
        return "जी, ये details हमारे records को update रखने के लिए ज़रूरी हैं, और ये secure रहती हैं। क्या आप email ID बता सकते हैं?"
    if session.email_refusal_count >= 2:
        return "मैं समझ सकती हूँ अगर आप comfortable नहीं हैं — लेकिन ये सिर्फ verification के लिए है, payment के लिए नहीं। क्या एक बार बता देंगे?"
    if session.crm_email:
        return "जी, क्या आप अपनी पूरी email ID एक बार clearly बोल सकते हैं?"
    return "क्या आप अपनी email ID बता सकते हैं?"


def build_referral_nudge_prompt(session: CallSession) -> str:
    if session.referral_resume_state in {State.COLLECT_REFERRAL_NAME, State.COLLECT_REFERRAL_NUMBER}:
        if session.referral_refusal_count >= 2:
            return "बस एक नाम और number — जब उनको time suits होगा तब हम contact करेंगे।"
        return "जी, ये सिर्फ demo schedule करने के लिए है — कोई obligation नहीं है।"
    return "जी, कोई बात नहीं — अगर कभी future में कोई याद आए तो Marg का नाम ज़रूर suggest करें। हम free demo भी provide करते हैं।"


def build_busy_nudge_prompt(_session: CallSession) -> str:
    return (
        "जी, मैं समझ सकती हूँ आप busy हैं। लेकिन ये verification बहुत ज़रूरी है ताकि आपकी details updated रहें, "
        "और ये सिर्फ 2 minute लेगा। क्या हम जल्दी से complete कर लें?"
    )


def build_wrong_contact_company_prompt(_session: CallSession) -> str:
    return "जी, क्षमा करें — क्या मैं पूछ सकती हूँ आप कहाँ से बोल रहे हैं?"


def build_wrong_contact_trade_prompt(_session: CallSession) -> str:
    return "जी, धन्यवाद. उनका business trade क्या है?"


def build_wrong_contact_type_prompt(_session: CallSession) -> str:
    return "और business type manufacturer, distributor या retailer में से क्या है?"


def build_wrong_contact_name_prompt(_session: CallSession) -> str:
    return "जी, और आपका नाम क्या है? — ताकि हम अपने records update कर सकें और आपको बार-बार call न आए।"


def build_concerned_person_label(session: CallSession) -> str:
    if session.concerned_person_name:
        return f"{session.concerned_person_name} जी"
    return "जो person software संभालते हैं"


def build_render_context(session: CallSession) -> dict:
    company_name = session.company_name or session.firm_name or session.customer_name or "आपकी company"
    crm_pincode = session.pincode or session.crm_pincode
    crm_email = session.crm_email
    current_email = session.email or session.crm_email
    business_type = normalize_business_type_for_speech(
        session.business_type or session.crm_business_type or "records में उपलब्ध नहीं"
    )
    business_trade = session.business_trade or session.crm_business_trade or "records में उपलब्ध नहीं"

    whatsapp_digits = session.whatsapp_number or session.whatsapp_digit_buffer
    alternate_digits = session.alternate_number or session.alternate_digit_buffer
    concerned_person_digits = session.concerned_person_number or session.concerned_person_digit_buffer
    pincode_digits = session.pincode or session.pincode_digit_buffer
    referral_digits = session.referral_number or session.referral_digit_buffer
    followup_prompt = session.collection_followup_prompt
    concerned_person_label = build_concerned_person_label(session)

    if session.current_state.name == "CONFIRM_WHATSAPP_NUMBER" and whatsapp_digits:
        whatsapp_prompt = f"तो आपका WhatsApp number है — {digits_to_tts(whatsapp_digits)} — सही है?"
    elif followup_prompt and session.current_state.name == "COLLECT_WHATSAPP_NUMBER":
        whatsapp_prompt = followup_prompt
    elif session.whatsapp_digit_buffer:
        whatsapp_prompt = "जी, आगे बताइए।"
    else:
        whatsapp_prompt = "ठीक है जी — कृपया अपना WhatsApp number बताइए?"

    if session.current_state.name == "CONFIRM_ALTERNATE_NUMBER" and alternate_digits:
        alternate_prompt = f"तो आपका alternate number है — {digits_to_tts(alternate_digits)} — सही है?"
    elif followup_prompt and session.current_state.name == "COLLECT_ALTERNATE_NUMBER":
        alternate_prompt = followup_prompt
    elif session.alternate_digit_buffer:
        alternate_prompt = "जी, आगे बताइए।"
    else:
        alternate_prompt = "ठीक है जी — कृपया alternate number बताइए?"

    if session.current_state.name == "CONFIRM_CONCERNED_PERSON_NUMBER" and concerned_person_digits:
        concerned_person_prompt = (
            f"तो {concerned_person_label} का contact number है — {digits_to_tts(concerned_person_digits)} — सही है?"
        )
    elif followup_prompt and session.current_state.name == "COLLECT_CONCERNED_PERSON_NUMBER":
        concerned_person_prompt = followup_prompt
    elif session.concerned_person_digit_buffer:
        concerned_person_prompt = "जी, आगे बताइए।"
    else:
        concerned_person_prompt = f"जी, ठीक है. {concerned_person_label} का contact number बताइए?"

    concerned_person_handoff_prompt = (
        f"जी, समझ सकती हूँ — आप शायद software directly use नहीं कर रहे हैं। "
        f"क्या आप मुझे {concerned_person_label} का contact number दे सकते हैं?"
    )

    if session.current_state.name == "CONFIRM_PINCODE" and pincode_digits:
        pincode_prompt = f"तो आपका pin code है — {digits_to_tts(pincode_digits)} — सही है?"
    elif followup_prompt and session.current_state.name == "COLLECT_PINCODE":
        pincode_prompt = followup_prompt
    elif session.pincode_digit_buffer:
        pincode_prompt = "जी, आगे बताइए।"
    else:
        pincode_prompt = "जी, क्या आप अपना पूरा pin code एक बार में बता सकते हैं?"

    if session.current_state.name == "CONFIRM_REFERRAL_NUMBER" and referral_digits:
        referral_prompt = f"तो referral का number है — {digits_to_tts(referral_digits)} — सही है?"
    elif followup_prompt and session.current_state.name == "COLLECT_REFERRAL_NUMBER":
        referral_prompt = followup_prompt
    elif session.referral_digit_buffer:
        referral_prompt = "जी, आगे बताइए।"
    elif session.referral_name:
        referral_prompt = f"जी, {session.referral_name} जी का contact number बताइए।"
    else:
        referral_prompt = "जी, उनका contact number बताइए।"

    email_prompt = build_email_collection_prompt(session)

    if crm_pincode:
        verify_pincode_prompt = f"आपका area pin code — {digits_to_tts(crm_pincode)} — यही है?"
    else:
        verify_pincode_prompt = (
            "मेरे record में pin code available नहीं दिख रहा. "
            "अगर convenient हो तो अपना area pin code बता दीजिए?"
        )

    if crm_email:
        verify_email_prompt = f"आपकी email ID — {email_to_tts(crm_email)} — यही है?"
    else:
        verify_email_prompt = (
            "मेरे record में email ID available नहीं दिख रही. "
            "अगर convenient हो तो अपनी email ID बता दीजिए?"
        )

    context = dict(session.__dict__)
    context.update(
        {
            "company_name": company_name,
            "spoken_crm_pincode": digits_to_tts(crm_pincode),
            "spoken_crm_email": email_to_tts(crm_email),
            "spoken_current_email": email_to_tts(current_email),
            "spoken_whatsapp_digits": digits_to_tts(whatsapp_digits),
            "spoken_alternate_digits": digits_to_tts(alternate_digits),
            "spoken_concerned_person_digits": digits_to_tts(concerned_person_digits),
            "spoken_pincode_digits": digits_to_tts(pincode_digits),
            "spoken_referral_digits": digits_to_tts(referral_digits),
            "concerned_person_label": concerned_person_label,
            "wrong_contact_company_prompt": build_wrong_contact_company_prompt(session),
            "wrong_contact_trade_prompt": build_wrong_contact_trade_prompt(session),
            "wrong_contact_type_prompt": build_wrong_contact_type_prompt(session),
            "wrong_contact_name_prompt": build_wrong_contact_name_prompt(session),
            "concerned_person_handoff_prompt": concerned_person_handoff_prompt,
            "concerned_person_collection_prompt": concerned_person_prompt,
            "display_business_type": business_type,
            "display_business_trade": business_trade,
            "billing_blocker_prompt": build_billing_blocker_prompt(session),
            "complaint_detail_prompt": build_complaint_detail_prompt(session),
            "payment_date_prompt": build_payment_date_prompt(session),
            "partner_name_prompt": build_partner_name_prompt(session),
            "switched_software_prompt": build_switched_software_prompt(session),
            "switch_reason_prompt": build_switch_reason_prompt(session),
            "closure_reason_prompt": build_closure_reason_prompt(session),
            "technical_issue_prompt": build_technical_issue_prompt(session),
            "training_pincode_prompt": build_training_pincode_prompt(session),
            "billing_start_timeline_prompt": build_billing_start_timeline_prompt(session),
            "detour_anything_else_prompt": build_detour_anything_else_prompt(session),
            "email_collection_prompt": email_prompt,
            "purchase_amount_prompt": build_purchase_amount_prompt(session),
            "referral_nudge_prompt": build_referral_nudge_prompt(session),
            "busy_nudge_prompt": build_busy_nudge_prompt(session),
            "verify_pincode_prompt": verify_pincode_prompt,
            "verify_email_prompt": verify_email_prompt,
            "whatsapp_collection_prompt": whatsapp_prompt,
            "alternate_collection_prompt": alternate_prompt,
            "pincode_collection_prompt": pincode_prompt,
            "referral_collection_prompt": referral_prompt,
            "query_response_prompt": build_query_response_prompt(session),
            "callback_time_prompt": build_callback_time_prompt(session),
            "callback_confirmation_prompt": build_callback_confirmation_prompt(session),
            "terminal_closing_text": build_terminal_closing_text(session),
            "fixed_closing_text": build_fixed_closing_text(session),
            "billing_blocker_support_prefix": build_billing_blocker_support_prefix(session),
        }
    )
    return context
