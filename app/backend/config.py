from pathlib import Path

# Centralized constants for the Aakriti voice agent.

MAX_FALLBACKS_PER_STATE = 3
MAX_TOTAL_TRANSITIONS = 50
MAX_CALL_DURATION_SECONDS = 600
TRANSCRIPT_WINDOW_SIZE = 6
MAX_PRICE_ATTEMPTS = 2
SILENCE_TIMEOUT_SECONDS = 10
SILENCE_MAX_RETRIES = 2
CLASSIFIER_TIMEOUT_SECONDS = 0.75
LLM_TIMEOUT_SECONDS = 5.0
LLM_MAX_RETRIES = 1
AUTO_CALLBACK_RETRY_HOURS: tuple[int, int] = (24, 48)

VALID_INTENTS = [
    "AFFIRM",
    "DENY",
    "INFORM",
    "REQUEST",
    "ASK",
    "OBJECT",
    "COMPLAIN",
    "ESCALATE",
    "DEFER",
    "ELABORATE",
    "GREET",
    "THANK",
    "GOODBYE",
    "OUT_OF_SCOPE",
    "UNCLEAR",
]

SYSTEM_PROMPT_FOR_CLASSIFIER = (
    "Classify the speech act of the given Hindi-English transcript. "
    "Output EXACTLY one label from: "
    "AFFIRM, DENY, INFORM, REQUEST, ASK, OBJECT, COMPLAIN, "
    "ESCALATE, DEFER, ELABORATE, GREET, THANK, GOODBYE, "
    "OUT_OF_SCOPE, UNCLEAR"
)

BASE_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
_THIS_DIR = Path(__file__).resolve().parent
_PREFERRED_ADAPTER_DIR = _THIS_DIR / "models" / "आकृति-intent-classifier"
_LEGACY_ADAPTER_DIR = _THIS_DIR / "models" / "akash-intent-classifier"
ADAPTER_PATH = str(_PREFERRED_ADAPTER_DIR if _PREFERRED_ADAPTER_DIR.exists() else _LEGACY_ADAPTER_DIR)
