from state_machine.intents import Intent
from state_machine.states import State
from state_machine.session import CallSession


def update_sentiment(session: CallSession, intent: Intent, state: State):
    """
    Accumulate sentiment across the call.
    NEGATIVE is sticky (once D-SAT, stays negative).
    """
    if intent == Intent.ESCALATE:
        session.sentiment = "NEGATIVE"
        session.dsat_flag = True
        session.escalation_priority = "HIGH"
        return

    if intent == Intent.COMPLAIN:
        session.sentiment = "NEGATIVE"
        session.came_from_issue = True
        return

    if intent == Intent.THANK:
        if not session.dsat_flag:
            session.sentiment = "POSITIVE"
        return

    if intent == Intent.AFFIRM and state == State.SATISFACTION_CHECK:
        if not session.dsat_flag:
            session.sentiment = "POSITIVE"
        return

    if intent == Intent.DENY and state == State.SATISFACTION_CHECK:
        session.sentiment = "NEGATIVE"
        return
