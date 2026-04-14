from state_machine.session import CallSession
from state_machine.states import State


def compute_disposition(session: CallSession) -> tuple[str, str]:
    visited = set(session.states_visited)

    if State.INVALID_REGISTRATION in visited:
        return ("Invalid Reg Details", "Wrong Details of Customer")

    if session.callback_requested or State.CALLBACK_CLOSING in visited:
        return ("Call Back", "Customer Busy")

    if session.billing_started == "STARTED":
        return ("Start Successfully", "Closed")

    if session.billing_started == "NOT_STARTED":
        return ("Call Back", "Billing Not Started")

    return ("Call Back", "Concern Person Not Available")
