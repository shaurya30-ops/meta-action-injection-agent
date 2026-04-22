from .states import State


ACTION_MAP: dict[State, str | None] = {
    State.OPENING_GREETING: (
        "नमस्ते, मैं आकृती बोल रही हूँ Marg ERP Delhi head office से. "
        "क्या मेरी बात {{company_name}} में हो रही है?"
    ),
    State.CONFIRM_IDENTITY: "जी, क्या मेरी बात {{company_name}} में हो रही है?",
    State.CHECK_AVAILABILITY: (
        "बहुत बहुत स्वागत है आपका Marg परिवार में! "
        "आप हमारे नए member हैं — और हम चाहते हैं कि आपकी शुरुआत बिल्कुल smooth हो. "
        "बस two minute में कुछ details verify करना चाहती थी और आपको कुछ ज़रूरी जानकारी भी देना चाहूंगी. "
        "क्या अभी बात की जा सकती है?"
    ),
    State.ASK_WRONG_CONTACT_COMPANY: "{{wrong_contact_company_prompt}}",
    State.ASK_WRONG_CONTACT_TRADE: "{{wrong_contact_trade_prompt}}",
    State.ASK_WRONG_CONTACT_TYPE: "{{wrong_contact_type_prompt}}",
    State.ASK_WRONG_CONTACT_NAME: "{{wrong_contact_name_prompt}}",
    State.COLLECT_WRONG_CONTACT_NUMBER: "{{wrong_contact_number_prompt}}",
    State.CONFIRM_WRONG_CONTACT_NUMBER: "तो आपका सही contact number है — {{spoken_wrong_contact_digits}} — सही है?",
    State.WRONG_NUMBER_PITCH: "{{wrong_number_pitch_prompt}}",
    State.WRONG_NUMBER_HELP_CHECK: "{{wrong_number_help_check_prompt}}",
    State.WRONG_NUMBER_CLOSING: "{{wrong_number_closing_prompt}}",
    State.ASK_CONCERNED_PERSON_CONTACT: "{{concerned_person_handoff_prompt}}",
    State.COLLECT_CONCERNED_PERSON_NUMBER: "{{concerned_person_collection_prompt}}",
    State.CONFIRM_CONCERNED_PERSON_NUMBER: (
        "तो {{concerned_person_label}} का contact number है — {{spoken_concerned_person_digits}} — सही है?"
    ),
    State.ASK_BILLING_STATUS: "जी धन्यवाद। क्या आपके software में billing start हो गई है?",
    State.EXPLORE_BILLING_BLOCKER: "{{billing_blocker_prompt}}",
    State.COLLECT_COMPLAINT_DETAIL: "{{complaint_detail_prompt}}",
    State.ESCALATE_PAYMENT_DATE: "{{payment_date_prompt}}",
    State.ESCALATE_PARTNER_NAME: "{{partner_name_prompt}}",
    State.ESCALATE_SWITCHED_SOFTWARE: "{{switched_software_prompt}}",
    State.ESCALATE_SWITCH_REASON: "{{switch_reason_prompt}}",
    State.ESCALATE_CLOSURE_REASON: "{{closure_reason_prompt}}",
    State.ESCALATE_TECHNICAL_ISSUE: "{{technical_issue_prompt}}",
    State.ESCALATION_HELP_CHECK: "क्या मैं आपकी किसी और तरह सहायता कर सकती हूँ?",
    State.COLLECT_TICKET_NUMBER: "जी, ज़रूर। आप ticket number बता दीजिए — मैं check कर लेती हूँ।",
    State.TICKET_ESCALATION_ACK: "जी, ठीक है. मैंने ticket number {{ticket_number}} note कर लिया है. मैं senior team को escalate कर रही हूँ, वो आपको soonest update देंगे।",
    State.TICKET_HELP_CHECK: "क्या इसके अलावा training या billing में कोई और help चाहिए?",
    State.TRAINING_PENDING_ACK: "जी, आपकी training अभी pending है — ये होनी चाहिए थी।",
    State.ASK_TRAINING_PENDING_DURATION: "क्या आप बता सकते हैं — कितने time से pending है?",
    State.COLLECT_TRAINING_PINCODE: "{{training_pincode_prompt}}",
    State.CONFIRM_TRAINING_PINCODE: "तो आपका area pin code है — {{spoken_training_pincode_digits}} — सही है?",
    State.TRAINING_REASSURANCE: (
        "ठीक है — मैंने note कर लिया है. "
        "हमारी team 24 से 48 घंटों में operator से time confirm करके आपको वापस contact करेगी।"
    ),
    State.TRAINING_HELP_CHECK: "क्या मैं आपकी किसी और तरह से help कर सकती हूँ?",
    State.ASK_BILLING_START_TIMELINE: "{{billing_start_timeline_prompt}}",
    State.DETOUR_ANYTHING_ELSE: "{{detour_anything_else_prompt}}",
    State.VERIFY_WHATSAPP: "जिस register number से बात हो रही है — वो WhatsApp पर available है?",
    State.COLLECT_WHATSAPP_NUMBER: "{{whatsapp_collection_prompt}}",
    State.CONFIRM_WHATSAPP_NUMBER: "तो आपका WhatsApp number है — {{spoken_whatsapp_digits}} — सही है?",
    State.ASK_ALTERNATE_NUMBER: "क्या आप कोई alternate number भी देना चाहेंगे?",
    State.COLLECT_ALTERNATE_NUMBER: "{{alternate_collection_prompt}}",
    State.CONFIRM_ALTERNATE_NUMBER: "तो आपका alternate number है — {{spoken_alternate_digits}} — सही है?",
    State.VERIFY_PINCODE: "{{verify_pincode_prompt}}",
    State.COLLECT_PINCODE: "{{pincode_collection_prompt}}",
    State.CONFIRM_PINCODE: "तो आपका pin code है — {{spoken_pincode_digits}} — सही है?",
    State.VERIFY_BUSINESS_DETAILS: (
        "आपका business {{display_business_type}} में है — और आप {{display_business_trade}} हैं?"
    ),
    State.CONFIRM_BUSINESS_DETAILS: (
        "जी, तो आप {{display_business_type}} में {{display_business_trade}} हैं — noted. "
        "आगे बढ़ते हैं।"
    ),
    State.VERIFY_EMAIL: "{{verify_email_prompt}}",
    State.COLLECT_EMAIL_CORRECTION: "{{email_collection_prompt}}",
    State.CONFIRM_EMAIL_CORRECTION: "तो आपकी email ID — {{spoken_current_email}} — यही है?",
    State.ASK_PURCHASE_AMOUNT: "{{purchase_amount_prompt}}",
    State.SUPPORT_AND_REFERRAL: "{{support_and_referral_prompt}}",
    State.COLLECT_REFERRAL_NAME: "उनका नाम क्या है?",
    State.COLLECT_REFERRAL_NUMBER: "{{referral_collection_prompt}}",
    State.CONFIRM_REFERRAL_NUMBER: "तो referral का number है — {{spoken_referral_digits}} — सही है?",
    State.COLLECT_REFERRAL_PINCODE: "और उनका area pin code?",
    State.CONFIRM_REFERRAL_DETAILS: (
        "मैं note कर रही हूँ — नाम: {{display_referral_name}}, number: {{spoken_referral_digits}}, "
        "pin code: {{spoken_referral_pincode_digits}} — क्या यह सही है?"
    ),
    State.REFERRAL_DECLINE_NUDGE: "{{referral_nudge_prompt}}",
    State.COLLECT_MOBILE_UPDATE_NUMBER: "नया number बताइए।",
    State.CONFIRM_MOBILE_UPDATE_NUMBER: "तो नया number है — {{spoken_mobile_update_digits}} — सही है?",
    State.MOBILE_UPDATE_CONFIRMED: "{{mobile_update_confirmation_prompt}}",
    State.REDIRECT_COLLECT_NUMBER: "जी, ठीक है. उनसे बात करने के लिए किस number पर call करना सही रहेगा?",
    State.REDIRECT_CONFIRM_NUMBER: "तो number है {{spoken_redirect_digits}} — सही है?",
    State.REDIRECT_CLOSING: (
        "जी, ठीक है. मैं इस number पर call arrange करवाती हूँ. "
        "आपने अपना कीमती समय निकाला, उसके लिए बहुत बहुत धन्यवाद। Have a great day!"
    ),
    State.ANSWER_USER_QUERY: "{{query_response_prompt}}",
    State.PRE_CLOSING: None,
    State.BUSY_NUDGE: "{{busy_nudge_prompt}}",
    State.ASK_CALLBACK_TIME: "{{callback_time_prompt}}",
    State.CONFIRM_CALLBACK_TIME: "{{callback_confirmation_prompt}}",
    State.CALLBACK_CLOSING: "{{callback_closing_text}}",
    State.INVALID_REGISTRATION: "{{terminal_closing_text}}",
    State.WARM_CLOSING: "{{terminal_closing_text}}",
    State.FIXED_CLOSING: "{{fixed_closing_text}}",
    State.LOG_DISPOSITION: None,
    State.END: None,
}
