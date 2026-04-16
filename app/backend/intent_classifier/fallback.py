import re
import logging
from state_machine.intents import Intent

logger = logging.getLogger(__name__)


class RegexFallbackClassifier:
    """
    Keyword/regex-based fallback classifier.
    Used when LoRA model is unavailable or fails.

    Hardened against the 5 critical misroute patterns from the 73% model:
    1. GOODBYE missed (classified as AFFIRM/GREET)
    2. ESCALATE missed (classified as DEFER/COMPLAIN)
    3. COMPLAIN confused with DEFER
    4. AFFIRM confused with INFORM at billing status
    5. GREET absorbing short phrases
    """

    # Order matters — checked top to bottom, first match wins.
    # GOODBYE and ESCALATE are checked first (global overrides depend on them).
    PATTERNS: list[tuple[Intent, list[str]]] = [
        # ── GOODBYE: Must catch before GREET/AFFIRM ──
        (Intent.GOODBYE, [
            r"\bbye\b",
            r"\balvida\b", r"\u0905\u0932\u0935\u093f\u0926\u093e",
            r"\u0930\u0916\u0924\u093e\s+\u0939\u0942", r"\u0930\u0916\u0924\u0940\s+\u0939\u0942",
            r"phone\s+\u0930\u0916", r"call\s+\u0930\u0916",
            r"\u092c\u0902\u0926\s+\u0915\u0930", r"disconnect",
            r"\u092e\u093f\u0932\u0924\u0947\s+\u0939\u0948\u0902",
            r"\u091a\u0932\u0924\u0947\s+\u0939\u0948\u0902",
            r"\u091a\u0932\u094b\s+\u092b\u093f\u0930",
            r"tata\b", r"good\s*bye",
        ]),

        # ── ESCALATE: Must catch before COMPLAIN/OBJECT ──
        (Intent.ESCALATE, [
            r"\bmanager\b", r"\u092e\u0948\u0928\u0947\u091c\u0930",
            r"consumer\s+forum", r"consumer\s+court",
            r"\blegal\b", r"\bcourt\b",
            r"\brefund\b", r"\u0930\u093f\u092b\u0902\u0921",
            r"\u092a\u0948\u0938\u093e\s+\u0935\u093e\u092a\u0938", r"paisa\s+wapas",
            r"\bfraud\b", r"\u0927\u094b\u0916\u093e\u0927\u0921\u093c\u0940",
            r"\bloot\b", r"\u0932\u0942\u091f",
            r"\bscam\b",
            r"senior\s+", r"higher\s+authority",
            r"social\s+media", r"google\s+review",
            r"\u0936\u0930\u094d\u092e\s+\u0928\u0939\u0940\u0902\s+\u0906\u0924\u0940",
            r"\u0927\u0902\u0927\u093e\s+\u092c\u0902\u0926",
            r"compensation",
            r"police",
            r"\u092a\u0948\u0938\u0947\s+\u0921\u0942\u092c", r"\u092a\u0948\u0938\u0947\s+\u092c\u0930\u094d\u092c\u093e\u0926",
        ]),

        # ── DEFER: Temporal postponement ──
        (Intent.DEFER, [
            r"\bbusy\s+\u0939\u0942", r"\bbusy\b",
            r"\u092c\u093e\u0926\s+\u092e\u0947\u0902",
            r"\u0915\u0932\s+call", r"kal\s+call",
            r"\u0905\u092d\u0940\s+time\s+\u0928\u0939\u0940\u0902",
            r"\u0905\u092d\u0940\s+\u0928\u0939\u0940\u0902\s+\u0939\u094b\s+\u092a\u093e\u090f\u0917\u093e",
            r"meeting\s+\u092e\u0947\u0902",
            r"\u0917\u093e\u0921\u093c\u0940\s+\u091a\u0932\u093e",
            r"driving",
            r"\u0925\u094b\u0921\u093c\u093e\s+\u092c\u093e\u0926\s+\u092e\u0947\u0902",
            r"minute\s+\u092c\u093e\u0926",
        ]),

        # ── COMPLAIN: Problem reporting ──
        (Intent.COMPLAIN, [
            r"\bproblem\b", r"\berror\b", r"\bcrash\b", r"\bbug\b",
            r"\u0926\u093f\u0915\u094d\u0915\u0924", r"\u092a\u0930\u0947\u0936\u093e\u0928",
            r"\u0916\u093c\u0930\u093e\u092c",
            r"\u0917\u0932\u0924", r"galat",
            r"\bslow\b", r"\bhang\b",
            r"\u0920\u0940\u0915\s+\u0928\u0939\u0940\u0902",
            r"down\s+\u0939\u094b",
            r"\u0915\u093e\u092e\s+\u0928\u0939\u0940\u0902\s+\u0915\u0930\s+\u0930\u0939\u093e",
        ]),

        # ── THANK: Positive sentiment ──
        (Intent.THANK, [
            r"\bthank", r"\bthanks\b",
            r"\u0927\u0928\u094d\u092f\u0935\u093e\u0926",
            r"\u0936\u0941\u0915\u094d\u0930\u093f\u092f\u093e",
            r"\bsatisfied\b", r"\bhappy\b",
            r"\u092c\u0939\u0941\u0924\s+\u0905\u091a\u094d\u091b",
            r"\u092c\u0922\u093c\u093f\u092f\u093e\s+software",
            r"helpful",
        ]),

        # ── OBJECT: Pushback with reason ──
        (Intent.OBJECT, [
            r"\u0928\u0939\u0940\u0902\s+\u091a\u093e\u0939\u093f\u090f",
            r"use\s+\u0928\u0939\u0940\u0902", r"use\s+nahi",
            r"interest\s+\u0928\u0939\u0940\u0902", r"interest\s+nahi",
            r"\breturn\b", r"\bswitch\b",
            r"\btally\b",
            r"\u092c\u0947\u0915\u093e\u0930",
            r"\u091c\u093c\u0930\u0942\u0930\u0924\s+\u0928\u0939\u0940\u0902",
            r"remove\s+\u0915\u0930\u094b",
            r"DND",
        ]),

        # ── GREET: Opening phrases ONLY (anchored to start) ──
        (Intent.GREET, [
            r"^hello\b", r"^hi\b",
            r"^\u0928\u092e\u0938\u094d\u0924\u0947",
            r"^\u0928\u092e\u0938\u094d\u0915\u093e\u0930",
            r"^\u092a\u094d\u0930\u0923\u093e\u092e",
            r"^good\s+morning", r"^good\s+afternoon", r"^good\s+evening",
            r"^\u0930\u093e\u092e\s+\u0930\u093e\u092e",
        ]),

        # -- ASK: Clarification / information-seeking questions --
        (Intent.ASK, [
            r"\u0915\u094d\u092f\u093e\s+\u0932\u093f\u0916\u093e",
            r"\u0915\u094d\u092f\u093e\s+\u092c\u094b\u0932\u093e",
            r"\u0915\u094d\u092f\u093e\s+\u0915\u0939\u093e",
            r"\u0928\u093e\u092e\s+\u0915\u094d\u092f\u093e",
            r"kya\s+likha",
            r"kya\s+bola",
            r"kya\s+kaha",
            r"naam\s+kya",
            r"\b(?:kaise|kyun|kya|what|why|how|when|where|who|which|kitna|kitni|kitne|kaun)\b",
            r"\u0915\u094c\u0928",
            r"\u0915\u0948\u0938\u0947",
            r"\u0915\u094d\u092f\u094b\u0902",
            r"\u0915\u093f\u0924\u0928\u093e",
            r"\u0915\u093f\u0924\u0928\u0940",
            r"\u0915\u093f\u0924\u0928\u0947",
        ]),

        # ── AFFIRM: Short positive responses ONLY ──
        (Intent.AFFIRM, [
            r"^\u0939\u093e\u0902", r"^\u091c\u0940",
            r"^\u0939\u093e\u0902\s+\u091c\u0940",
            r"^\u092c\u093f\u0932\u094d\u0915\u0941\u0932",
            r"^yes", r"^ok", r"^okay",
            r"^\u0920\u0940\u0915\s+\u0939\u0948",
            r"^\u0938\u0939\u0940\s+\u0939\u0948",
            r"^\u0939\u093e\u0902\s+\u0939\u093e\u0902",
        ]),

        # ── DENY: Short negative responses ──
        (Intent.DENY, [
            r"^\u0928\u0939\u0940\u0902", r"^\u0928\u093e",
            r"^no", r"^nahi",
            r"^\u091c\u0940\s+\u0928\u0939\u0940\u0902",
            r"\u092a\u0924\u093e\s+\u0928\u0939\u0940\u0902",
            r"\u092f\u093e\u0926\s+\u0928\u0939\u0940\u0902",
            r"\u0928\u0939\u0940\u0902\s+\u092c\u0924\u093e\u0928\u093e",
            r"\u0928\u0939\u0940\u0902\s+\u0926\u0947\u0928\u093e",
        ]),

        # ── REQUEST: Action demands ──
        (Intent.REQUEST, [
            r"\u092c\u093e\u0924\s+\u0915\u0930\u0935\u093e\s+\u0926\u094b",
            r"connect\s+\u0915\u0930\u093e",
            r"arrange\s+\u0915\u0930",
            r"\bhelp\s+\u091a\u093e\u0939\u093f\u090f",
            r"\u092d\u0947\u091c\s+\u0926\u094b",
            r"send\s+\u0915\u0930\s+\u0926\u094b",
            r"fix\s+\u0915\u0930\u094b",
            r"^\u0939\u093e\u0902\s+\u091c\u0940\s+\u092c\u094b\u0932",
            r"^\u0939\u093e\u0902\s+\u092c\u094b\u0932\u094b",
            r"^\u0939\u093e\u0902\s+\u091c\u0940\s+\u092c\u0924\u093e",
            r"^\u0939\u093e\u0902\s+\u0915\u0939\u093f\u090f",
            r"^haan\s+ji\s+bol",
            r"^haan\s+bolo",
            r"^haan\s+ji\s+bata",
            r"^haan\s+kahiye",
            r"^bol(?:iye|ie|o)\b",
        ]),

        # -- INFORM: Short module/topic fragments should not collapse into GREET/UNCLEAR --
        (Intent.INFORM, [
            r"\bbilling\b",
            r"\bbackend\b", r"back\s*end",
            r"\binvoice\b",
            r"\bpayment\b",
            r"\bgst\b",
            r"\blogin\b",
            r"\bstock\b",
            r"\breport\b",
            r"\bpurchase\b",
            r"\bsale\b",
            r"\bprint(?:ing)?\b",
        ]),
    ]

    def __init__(self):
        self._compiled = [
            (intent, [re.compile(p, re.IGNORECASE) for p in patterns])
            for intent, patterns in self.PATTERNS
        ]

    def classify(self, transcript: str) -> Intent:
        transcript = transcript.strip()
        if not transcript:
            return Intent.UNCLEAR

        for intent, patterns in self._compiled:
            for pattern in patterns:
                if pattern.search(transcript):
                    return intent

        # Check if it looks like data (numbers, emails)
        if re.search(r"\d{6,}", transcript):
            return Intent.INFORM
        if re.search(r"@|at the rate", transcript, re.IGNORECASE):
            return Intent.INFORM

        return Intent.UNCLEAR
