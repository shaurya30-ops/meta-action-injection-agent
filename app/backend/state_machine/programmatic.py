from .states import State
from .intents import Intent
from .session import CallSession

PROGRAMMATIC_DECISIONS: dict[State, dict] = {}


def resolve_programmatic(session: CallSession) -> State:
    """No programmatic states are used in the strict scripted flow."""
    return session.current_state
