# Centralized constants for the Akash Voice Agent
# Every tunable parameter lives here — no magic numbers in other files.

MAX_FALLBACKS_PER_STATE = 3
MAX_TOTAL_TRANSITIONS = 50
MAX_CALL_DURATION_SECONDS = 600
TRANSCRIPT_WINDOW_SIZE = 6       # Last 3 turns (user + agent = 6 messages)
MAX_PRICE_ATTEMPTS = 2
SILENCE_TIMEOUT_SECONDS = 10
SILENCE_MAX_RETRIES = 2
LLM_TIMEOUT_SECONDS = 5
LLM_MAX_RETRIES = 1
CLASSIFIER_TIMEOUT_MS = 60
AUTO_CALLBACK_HOURS = (24, 48)

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
ADAPTER_PATH = "./models/akash-intent-classifier"
