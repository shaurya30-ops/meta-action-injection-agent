from __future__ import annotations

import logging
import re

from state_machine.intents import Intent

from .fallback import RegexFallbackClassifier

logger = logging.getLogger(__name__)

_ASK_PATTERNS = [
    r"क्या\s+लिखा",
    r"क्या\s+बोला",
    r"क्या\s+कहा",
    r"नाम\s+क्या",
    r"\b(?:क्या|क्यों|कैसे|कब|कहां|कहाँ|कौन|किस|कितना|कितनी|कितने|what|why|how|when|where|who|which)\b",
]

_AFFIRM_PATTERNS = [
    r"^(?:हाँ|हां)(?:\s|$|[?.!,])",
    r"^जी(?:\s|$|[?.!,])",
    r"^(?:हाँ|हां)\s+जी(?:\s|$|[?.!,])",
    r"^बिल्कुल(?:\s|$|[?.!,])",
    r"^(?:yes|ok|okay)(?:\s|$|[?.!,])",
    r"^ठीक\s+है(?:\s|$|[?.!,])",
    r"^सही\s+है(?:\s|$|[?.!,])",
]

_DENY_PATTERNS = [
    r"^(?:नहीं|ना)(?:\s|$|[?.!,])",
    r"^(?:no|nahi)(?:\s|$|[?.!,])",
    r"^जी\s+नहीं(?:\s|$|[?.!,])",
    r"पता\s+नहीं",
    r"याद\s+नहीं",
]


class IntentClassifier:
    """Deterministic speech-act classifier for the hot path.

    The previous Qwen/LoRA process pool has been retired. We keep this thin
    wrapper so the rest of the runtime can continue to call the same async
    interface without booting a local model at worker startup.
    """

    def __init__(self) -> None:
        self._fallback = RegexFallbackClassifier()

    def warmup(self) -> None:
        """No-op kept for compatibility with older startup hooks."""
        return None

    async def classify(self, transcript: str) -> Intent:
        normalized = " ".join((transcript or "").split())
        if not normalized:
            return Intent.UNCLEAR

        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _ASK_PATTERNS):
            return Intent.ASK
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _AFFIRM_PATTERNS):
            return Intent.AFFIRM
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _DENY_PATTERNS):
            return Intent.DENY
        if re.search(r"\d{6,}", normalized) or re.search(r"@|at the rate", normalized, re.IGNORECASE):
            return Intent.INFORM

        intent = self._fallback.classify(normalized)
        logger.debug("Deterministic classifier matched %s", intent.value)
        return intent
