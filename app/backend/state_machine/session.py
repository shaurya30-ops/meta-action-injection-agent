from dataclasses import dataclass, field
from typing import Optional
from .states import State


@dataclass
class CallSession:
    current_state: State = State.OPENING_GREETING
    previous_state: Optional[State] = None
    states_visited: list[State] = field(default_factory=list)
    fallback_count: int = 0

    customer_name: str = ""
    company_name: str = ""
    firm_name: str = ""
    primary_phone: str = ""
    crm_email: str = ""
    crm_pincode: str = ""
    crm_business_type: str = ""
    crm_business_trade: str = ""

    whatsapp_number: str = ""
    alternate_number: str = ""
    pincode: str = ""
    business_trade: str = ""
    business_type: str = ""
    email: str = ""
    purchase_amount: str = ""
    referral_name: str = ""
    referral_number: str = ""

    whatsapp_digit_buffer: str = ""
    alternate_digit_buffer: str = ""
    pincode_digit_buffer: str = ""
    referral_digit_buffer: str = ""

    awaiting_whatsapp_confirmation: bool = False
    awaiting_alternate_confirmation: bool = False
    awaiting_pincode_confirmation: bool = False
    awaiting_referral_confirmation: bool = False

    callback_requested: bool = False
    callback_time_phrase: str = ""
    callback_closing_text: str = ""
    closing_emitted: bool = False
    collection_followup_prompt: str = ""

    transcript: list = field(default_factory=list)

    billing_started: str = ""
    main_disposition: str = ""
    sub_disposition: str = ""

    call_id: str = ""
    call_start_time: str = ""
