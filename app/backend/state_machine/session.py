from dataclasses import dataclass, field
from typing import Optional
from .states import State


@dataclass
class CallSession:
    # Navigation
    current_state: State = State.OPENING_GREETING
    previous_state: Optional[State] = None
    states_visited: list = field(default_factory=list)
    fallback_count: int = 0

    # CRM pre-filled (from room metadata)
    customer_name: str = ""
    firm_name: str = ""
    primary_phone: str = ""
    software_version: str = ""
    license_date: str = ""
    operator_name: str = ""
    crm_whatsapp: str = ""
    crm_pincode: str = ""
    crm_business_trade: str = ""
    crm_email: str = ""

    # Collected on call
    whatsapp_number: str = ""
    alternate_number: str = ""
    pincode: str = ""
    city: str = ""
    business_trade: str = ""
    business_type: str = ""
    email: str = ""
    price_confirmed: str = ""
    license_number: str = ""

    # Issue tracking
    issue_description: str = ""
    callback_datetime: str = ""

    # Reference
    reference_name: str = ""
    reference_number: str = ""

    # Delay / Will Not Use
    billing_status: str = ""
    delay_subreason: str = ""
    will_not_use_reason: str = ""

    # Sentiment & Flags
    sentiment: str = "NEUTRAL"
    dsat_flag: bool = False
    escalation_priority: str = ""
    came_from_dsat: bool = False
    came_from_issue: bool = False

    # Counters
    price_attempt_count: int = 0

    # Transcript
    transcript: list = field(default_factory=list)

    # Disposition (computed at end)
    main_disposition: str = ""
    sub_disposition: str = ""

    # Call metadata
    call_id: str = ""
    call_start_time: str = ""
