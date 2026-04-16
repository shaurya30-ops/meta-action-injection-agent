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
    for word, digit in DIGIT_WORDS.items():
        candidate = re.sub(rf"\b{word}\b", digit, candidate)
    candidate = re.sub(r"\s+", "", candidate)
    match = re.search(r"[^\s@,;:!?।]+@[^\s@,;:!?।]+\.[A-Za-z]{2,}", candidate)
    return match.group(0) if match else ""


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


def extract_and_store(session: CallSession, state, transcript: str):
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
    business_type = session.business_type or session.crm_business_type or "records में available detail"
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
                f"क्या मेरी बात {company_name} मैं हो रही है?"
            )
        return (
            f"जी, मैं आकृति बोल रही हूँ Marg ई आर पी software Delhi head office से. "
            f"क्या मेरी बात {company_name} मैं हो रही है?"
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


def build_billing_blocker_support_prefix(session: CallSession) -> str:
    reason = session.billing_blocker_reason or session.last_blocker_reason
    if reason == "setup_in_progress":
        return (
            "जी, बिल्कुल समझ सकती हूँ — setup पूरा होने में थोड़ा time लग सकता है. "
            "जब setup complete हो जाए, Marg Help section में step-by-step guidance मिल जाएगी."
        )
    if reason == "technical_issue":
        return (
            "जी, समझ सकती हूँ — technical issue आए तो start करना मुश्किल हो जाता है. "
            "Marg Help section और Ticket option इसमें useful रहेंगे."
        )
    if reason == "dealer_setup":
        return (
            "जी, ये सुनकर अच्छा नहीं लगा. अगर dealer-side setup help pending है, तो "
            "Marg Help section से guidance मिल जाएगी, और Ticket option से हमारी side से call भी आ जाएगी."
        )
    if reason == "no_time":
        return (
            "जी, बिल्कुल समझ सकती हूँ — busy schedule में time निकालना मुश्किल होता है. "
            "जब भी start करें, Marg Help section में step-by-step guide मिल जाएगी."
        )
    if reason == "training_gap":
        return (
            "जी, कोई बात नहीं — शुरू में थोड़ा guidance चाहिए होता है. "
            "Marg Help section और Ticket option इसमें मदद करेंगे."
        )
    return "जी, noted."


def build_render_context(session: CallSession) -> dict:
    company_name = session.company_name or session.firm_name or session.customer_name or "आपकी company"
    crm_pincode = session.pincode or session.crm_pincode
    crm_email = session.crm_email
    current_email = session.email or session.crm_email
    business_type = session.business_type or session.crm_business_type or "records में उपलब्ध नहीं"
    business_trade = session.business_trade or session.crm_business_trade or "records में उपलब्ध नहीं"

    whatsapp_digits = session.whatsapp_number or session.whatsapp_digit_buffer
    alternate_digits = session.alternate_number or session.alternate_digit_buffer
    pincode_digits = session.pincode or session.pincode_digit_buffer
    referral_digits = session.referral_number or session.referral_digit_buffer
    followup_prompt = session.collection_followup_prompt

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

    if session.current_state.name == "COLLECT_EMAIL_CORRECTION" and session.email_fragment_buffer:
        email_prompt = "जी, आगे बताइए।"
    else:
        email_prompt = "ठीक है जी — कृपया अपनी corrected email ID बताइए।"

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
            "spoken_pincode_digits": digits_to_tts(pincode_digits),
            "spoken_referral_digits": digits_to_tts(referral_digits),
            "display_business_type": business_type,
            "display_business_trade": business_trade,
            "email_collection_prompt": email_prompt,
            "verify_pincode_prompt": verify_pincode_prompt,
            "verify_email_prompt": verify_email_prompt,
            "whatsapp_collection_prompt": whatsapp_prompt,
            "alternate_collection_prompt": alternate_prompt,
            "pincode_collection_prompt": pincode_prompt,
            "referral_collection_prompt": referral_prompt,
            "query_response_prompt": build_query_response_prompt(session),
            "billing_blocker_support_prefix": build_billing_blocker_support_prefix(session),
        }
    )
    return context
