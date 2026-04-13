import datetime
import re
from typing import List

from .states import State
from .intents import Intent
from .session import CallSession
from .transitions import TRANSITIONS, AUTO_TRANSITIONS, GLOBAL_OVERRIDES
from .programmatic import PROGRAMMATIC_DECISIONS
from .actions import ACTION_MAP
from content_extraction.extractor_logic import extract_and_store
from sentiment.tracker import update_sentiment
import config

# ══════════════════════════════════════════════════════════════════════
# STATE-AWARE KEYWORD CORRECTION
# Overrides the classifier's intent for specific (state, keyword) pairs
# where the model's known confusion patterns cause critical misroutes.
# This is the "hardened edge" — catches the 5 most dangerous errors.
# ══════════════════════════════════════════════════════════════════════

_BILLING_STARTED_PATTERNS = re.compile(
    r"billing\s*start|bill\s*ban[a\u093e]|invoice\s*ban[a\u093e]|"
    r"\u092c\u093f\u0932\u093f\u0902\u0917\s*\u0938\u094d\u091f\u093e\u0930\u094d\u091f|"
    r"\u092c\u093f\u0932\s*\u092c\u0928\u093e|"
    r"\u0939\u094b\s*\u0917\u0908|\u0939\u094b\s*\u091a\u0941\u0915\u0940|\u0939\u094b\s+\u091a\u0941\u0915\u0940|"
    r"\u0936\u0941\u0930\u0942\s*\u0915\u0930\s*\u0926\u093f|"
    r"billing\s*ho\s*chuki|billing\s*ho\s*gayi|"
    r"start\s*ho\s*gayi|start\s*ho\s*chuki",
    re.IGNORECASE,
)

_GOODBYE_PATTERNS = re.compile(
    r"\bbye\b|\u0905\u0932\u0935\u093f\u0926\u093e|"
    r"\u0930\u0916\u0924\u093e\s*\u0939\u0942\u0901|\u0930\u0916\u0924\u0940\s*\u0939\u0942\u0901|"
    r"phone\s*\u0930\u0916|\u092e\u093f\u0932\u0924\u0947\s*\u0939\u0948\u0902|"
    r"\u092c\u0902\u0926\s*\u0915\u0930",
    re.IGNORECASE,
)

STATE_KEYWORD_CORRECTIONS: dict[State, list[tuple[re.Pattern, Intent]]] = {
    # If at ASK_BILLING_STATUS and transcript says billing started → force AFFIRM
    State.ASK_BILLING_STATUS: [
        (_BILLING_STARTED_PATTERNS, Intent.AFFIRM),
    ],
    # If at any verification state and model says GOODBYE but text has no bye signals → ignore
    # (handled by soft transitions instead)
}


def _apply_keyword_correction(state: State, intent: Intent, transcript: str) -> Intent:
    """Check if a state-specific keyword pattern should override the classified intent."""
    corrections = STATE_KEYWORD_CORRECTIONS.get(state)
    if not corrections:
        return intent

    for pattern, forced_intent in corrections:
        if pattern.search(transcript):
            return forced_intent

    return intent


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolve_next_state(session: CallSession, intent: Intent, transcript: str) -> State:
    """
    5-priority resolution algorithm:
    1. Global overrides (GOODBYE/ESCALATE/DEFER from any state)
    2. Programmatic decisions (data-driven, not intent-driven)
    3. Transition table lookup
    4. Auto-advance check
    5. Fallback (stay in current state)
    """

    # Safety cap: max total transitions
    if len(session.states_visited) >= config.MAX_TOTAL_TRANSITIONS:
        return State.WARM_CLOSING

    # PRIORITY 0.5: STATE-AWARE KEYWORD CORRECTION
    # Catches the 5 most dangerous classifier confusion patterns.
    intent = _apply_keyword_correction(session.current_state, intent, transcript)

    # PRIORITY 1: GLOBAL OVERRIDES
    for override_intent, target, suppressed in GLOBAL_OVERRIDES:
        if intent == override_intent and session.current_state not in suppressed:
            return target

    # PRIORITY 2: PROGRAMMATIC DECISIONS
    if session.current_state in PROGRAMMATIC_DECISIONS:
        prog_rule = PROGRAMMATIC_DECISIONS[session.current_state]
        trigger = prog_rule.get("trigger_on")

        should_trigger = False
        if trigger is None:
            should_trigger = True
        elif isinstance(trigger, list):
            should_trigger = intent in trigger
        else:
            should_trigger = intent == trigger

        if should_trigger:
            if "side_effect" in prog_rule:
                prog_rule["side_effect"](session)
            if prog_rule["evaluate"](session):
                return prog_rule["if_true"]
            else:
                return prog_rule["if_false"]

    # PRIORITY 3: TRANSITION TABLE LOOKUP
    key = (session.current_state, intent)
    if key in TRANSITIONS:
        return TRANSITIONS[key]

    # PRIORITY 4: AUTO-ADVANCE CHECK
    if session.current_state in AUTO_TRANSITIONS:
        return AUTO_TRANSITIONS[session.current_state]

    # PRIORITY 5: FALLBACK — stay in current state
    session.fallback_count += 1
    if session.fallback_count >= config.MAX_FALLBACKS_PER_STATE:
        session.fallback_count = 0
        return State.WARM_CLOSING
    return session.current_state


def post_transition(session: CallSession, intent: Intent, transcript: str, next_state: State):
    """Post-transition hooks: update navigation, sentiment, flags, extractors, counters, transcript."""
    previous_state = session.current_state

    # 1. Update navigation
    session.previous_state = previous_state
    session.current_state = next_state
    session.states_visited.append(next_state)

    # Only reset fallback on successful transition
    if next_state != previous_state:
        session.fallback_count = 0

    # 2. Update sentiment
    update_sentiment(session, intent, previous_state)

    # 3. Flow tracking flags
    if next_state == State.DSAT_ESCALATION:
        session.dsat_flag = True
        session.came_from_dsat = True
    if next_state == State.ISSUE_HANDLING:
        session.came_from_issue = True
    if previous_state == State.ASK_BILLING_STATUS:
        if intent == Intent.AFFIRM:
            session.billing_status = "STARTED"
        elif intent in (Intent.DENY, Intent.INFORM, Intent.DEFER):
            session.billing_status = "WILL_USE_SOON"
        elif intent == Intent.OBJECT:
            session.billing_status = "WILL_NOT_USE"

    # 4. Content extraction
    if intent in (Intent.INFORM, Intent.ELABORATE):
        extract_and_store(session, previous_state, transcript)

    # 5. Counters
    if previous_state == State.ASK_PRICE and intent == Intent.DENY:
        session.price_attempt_count += 1

    # 6. Store user transcript
    session.transcript.append({
        "role": "user",
        "text": transcript,
        "intent": intent.value,
        "state": previous_state.value,
        "ts": _now(),
    })


def execute_auto_chain(session: CallSession, start_state: State) -> List[State]:
    """
    Walk AUTO_TRANSITIONS from start_state until hitting a WAIT/TERMINAL state.
    Returns all states in the chain (including the final WAIT state).
    Updates session.current_state and states_visited along the way.
    """
    chain = []
    current = start_state

    while current in AUTO_TRANSITIONS:
        if ACTION_MAP.get(current) is not None:
            chain.append(current)
        current = AUTO_TRANSITIONS[current]
        session.current_state = current
        session.states_visited.append(current)

    # Current is now a WAIT/TERMINAL/PROGRAMMATIC state
    if ACTION_MAP.get(current) is not None:
        chain.append(current)

    return chain
