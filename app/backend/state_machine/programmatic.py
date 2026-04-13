from .states import State
from .intents import Intent
from .session import CallSession
import config


PROGRAMMATIC_DECISIONS = {

    # Decision 1: Sentiment eligibility for reference pitch
    # After helpline reminder, decide: pitch referral or close.
    State.CHECK_SENTIMENT_ELIGIBILITY: {
        "trigger_on": None,   # Always fires (no user intent, programmatic only)
        "evaluate": lambda session: (
            session.sentiment == "POSITIVE"
            and not session.dsat_flag
            and not session.came_from_issue
            and session.billing_status == "STARTED"
        ),
        "if_true":  State.REFERENCE_PITCH,
        "if_false": State.WARM_CLOSING,
    },

    # Decision 2: ASK_PRICE retry logic (max 2 attempts)
    # Only triggers on DENY — if user gives info (INFORM), normal transition handles it.
    State.ASK_PRICE: {
        "trigger_on": Intent.DENY,
        "evaluate": lambda session: session.price_attempt_count < config.MAX_PRICE_ATTEMPTS,
        "if_true":  State.ASK_PRICE,
        "if_false": State.SATISFACTION_CHECK,
        "side_effect": lambda session: setattr(
            session, "price_attempt_count", session.price_attempt_count + 1
        ),
    },

    # Decision 3: Callback time routing depends on origin
    # From D-SAT -> close immediately (no reference pitch)
    # From normal issue -> continue to support guidance
    State.CAPTURE_CALLBACK_TIME: {
        "trigger_on": [Intent.INFORM, Intent.AFFIRM],
        "evaluate": lambda session: session.came_from_dsat,
        "if_true":  State.WARM_CLOSING,
        "if_false": State.SUPPORT_GUIDANCE,
    },
}


def resolve_programmatic(session: CallSession) -> State:
    """Resolve a programmatic decision node. Called when current_state has no speech."""
    if session.current_state in PROGRAMMATIC_DECISIONS:
        rule = PROGRAMMATIC_DECISIONS[session.current_state]
        if rule["evaluate"](session):
            next_state = rule["if_true"]
        else:
            next_state = rule["if_false"]
        session.current_state = next_state
        session.states_visited.append(next_state)
        return next_state
    return session.current_state
