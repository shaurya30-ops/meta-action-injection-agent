from state_machine.intents import Intent
from state_machine.session import CallSession
from state_machine.states import State


def update_sentiment(session: CallSession, intent: Intent, state: State) -> None:
    """Legacy hook retained for compatibility with older imports."""
    return None
