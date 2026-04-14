# Centralized constants for the Akash Voice Agent
# Every tunable parameter lives here — no magic numbers in other files.

from pathlib import Path

MAX_FALLBACKS_PER_STATE = 3
MAX_TOTAL_TRANSITIONS = 50
MAX_CALL_DURATION_SECONDS = 600  # Enforced by the entrypoint watchdog.
TRANSCRIPT_WINDOW_SIZE = 6  # Slices transcript[-6:] = last 3 turn pairs.
MAX_PRICE_ATTEMPTS = 2
SILENCE_TIMEOUT_SECONDS = 10  # TODO: wire into a silence watchdog.
SILENCE_MAX_RETRIES = 2  # TODO: wire into a silence watchdog.
CLASSIFIER_TIMEOUT_SECONDS = 5.0  # Increased from 0.060s to allow Qwen enough time (takes ~3.7s)
LLM_TIMEOUT_SECONDS = 5.0
LLM_MAX_RETRIES = 1
AUTO_CALLBACK_RETRY_HOURS: tuple[int, int] = (24, 48)

VALID_INTENTS = [
    "AFFIRM", "DENY", "INFORM", "REQUEST", "ASK",
    "OBJECT", "COMPLAIN", "ESCALATE", "DEFER", "ELABORATE",
    "GREET", "THANK", "GOODBYE", "OUT_OF_SCOPE", "UNCLEAR",
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
ADAPTER_PATH = str(_THIS_DIR / "models" / "akash-intent-classifier")
