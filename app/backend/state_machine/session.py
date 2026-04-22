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

    wrong_contact_company: str = ""
    wrong_contact_trade: str = ""
    wrong_contact_type: str = ""
    wrong_contact_name: str = ""
    wrong_contact_number: str = ""

    partner_payment_date: str = ""
    partner_name: str = ""
    switched_software_name: str = ""
    switched_software_reason: str = ""
    business_closed_reason: str = ""
    technical_issue_detail: str = ""
    training_pending_duration: str = ""
    training_area_pincode: str = ""
    complaint_detail: str = ""

    whatsapp_number: str = ""
    alternate_number: str = ""
    concerned_person_name: str = ""
    concerned_person_number: str = ""
    pincode: str = ""
    business_trade: str = ""
    business_type: str = ""
    email: str = ""
    email_fragment_buffer: str = ""
    purchase_amount: str = ""
    billing_start_timeline: str = ""

    referral_name: str = ""
    referral_number: str = ""
    referral_pincode: str = ""
    pending_pincode_digits: str = ""

    whatsapp_digit_buffer: str = ""
    alternate_digit_buffer: str = ""
    concerned_person_digit_buffer: str = ""
    pincode_digit_buffer: str = ""
    referral_digit_buffer: str = ""
    referral_pincode_digit_buffer: str = ""
    wrong_contact_digit_buffer: str = ""
    mobile_update_digit_buffer: str = ""
    redirect_digit_buffer: str = ""

    awaiting_whatsapp_confirmation: bool = False
    awaiting_alternate_confirmation: bool = False
    awaiting_concerned_person_confirmation: bool = False
    awaiting_pincode_confirmation: bool = False
    awaiting_referral_confirmation: bool = False
    awaiting_referral_pincode_confirmation: bool = False
    awaiting_wrong_contact_confirmation: bool = False
    awaiting_mobile_update_confirmation: bool = False
    awaiting_training_pincode_confirmation: bool = False
    awaiting_redirect_confirmation: bool = False

    callback_requested: bool = False
    callback_time_phrase: str = ""
    callback_closing_text: str = ""
    callback_prompt_override: str = ""
    callback_time_attempts: int = 0
    callback_target_label: str = ""
    callback_resume_state: Optional[State] = None

    closing_emitted: bool = False
    collection_followup_prompt: str = ""
    pending_response_prefix: str = ""
    terminal_ack_text: str = ""
    fixed_closing_variant: str = "standard"

    billing_resume_state: Optional[State] = None
    blocker_owner: str = ""

    dialog_mode: str = "NORMAL"
    affect_state: str = "NEUTRAL"
    resume_state: Optional[State] = None
    resume_reason: str = ""
    expected_slot: str = ""
    last_user_query_type: str = "none"
    last_user_query_text: str = ""
    last_clarification_kind: str = "none"
    last_turn_workflow_answer: str = "unknown"
    last_blocker_reason: str = ""
    billing_blocker_reason: str = ""

    busy_but_continuing: bool = False
    user_disengagement_count: int = 0
    query_resolution_pending: bool = False
    business_correction_pending: bool = False
    email_correction_pending: bool = False

    billing_blocker_refusal_count: int = 0
    purchase_amount_refusal_count: int = 0
    email_refusal_count: int = 0
    referral_refusal_count: int = 0
    busy_refusal_count: int = 0

    referral_declined_once: bool = False
    referral_resume_state: Optional[State] = None
    query_resume_embedded: bool = False
    hard_stop_after_closing: bool = False

    mobile_update_number: str = ""
    number_change_resume_state: Optional[State] = None

    ticket_number: str = ""
    ticket_resume_state: Optional[State] = None

    redirect_number: str = ""

    transcript: list = field(default_factory=list)

    billing_started: str = ""
    main_disposition: str = ""
    sub_disposition: str = ""

    call_id: str = ""
    call_start_time: str = ""
