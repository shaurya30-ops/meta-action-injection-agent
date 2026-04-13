from state_machine.states import State
from state_machine.session import CallSession


SUBREASON_MAP = {
    "DATA_MIGRATION": "Data Migration Pending",
    "DEMO_PERIOD": "Demo Period Ongoing",
    "INSTALLATION_PENDING": "Installation Pending",
    "TRAINING_PERIOD": "Training Period / Ongoing Training",
    "TECHNICAL_ISSUE": "System Issue",
    "SYSTEM_ISSUE": "System Issue",
    "STOCK_MANAGEMENT": "Stock Maintains",
    "PERSONAL_ISSUE": "Business Issue",
    "NEED_OPERATOR": "Need Software Operator",
    "NEXT_FY": "Operate from Next FY",
    "OTHER": "Implementation in Business",
}


def compute_disposition(session: CallSession) -> tuple[str, str]:
    """Deterministic disposition from call path."""

    # Priority 1: Invalid Registration
    if State.INVALID_REGISTRATION in session.states_visited:
        return ("Invalid Reg Details", "Wrong Details of Customer")

    # Priority 2: D-SAT
    if session.dsat_flag:
        issue = (session.issue_description or "").lower()
        if "partner" in issue:
            return ("Dis-Satisfied (D-SAT)", "From Partner")
        return ("Dis-Satisfied (D-SAT)", "From Marg HO")

    # Priority 3: Will Not Use
    if session.billing_status == "WILL_NOT_USE":
        sub = session.will_not_use_reason or "Does Not Want to Share Reason"
        return ("Will Not Use", sub)

    # Priority 4: Will Use Soon
    if session.billing_status == "WILL_USE_SOON":
        sub = session.delay_subreason or "OTHER"
        return ("Will Use Soon", SUBREASON_MAP.get(sub, sub))

    # Priority 5: Callback (not billing-started)
    if State.CALLBACK_SCHEDULING in session.states_visited and session.billing_status != "STARTED":
        return ("Call Back", "Customer Busy")

    # Priority 6: Happy path
    if session.billing_status == "STARTED":
        return ("Start Successfully", "Closed")

    # Fallback
    return ("Call Back", "Concern Person Not Available")
