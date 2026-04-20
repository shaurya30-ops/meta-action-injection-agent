from .states import State

ACTION_MAP: dict[State, str | None] = {
    State.OPENING_GREETING: (
        "Hello, मैं आकृति बोल रही हूँ Marg ई आर पी software Delhi head office से. "
        "क्या मेरी बात {{company_name}} में हो रही है?"
    ),
    State.CONFIRM_IDENTITY: "जी, क्या मेरी बात {{company_name}} में हो रही है?",
    State.CHECK_AVAILABILITY: (
        "ठीक है जी, ये एक post-sale feedback और verification call है Marg ई आर पी software की तरफ से। "
        "क्या अभी दो मिनट बात हो सकती है?"
    ),
    State.ASK_WRONG_CONTACT_COMPANY: "{{wrong_contact_company_prompt}}",
    State.ASK_WRONG_CONTACT_TRADE: "{{wrong_contact_trade_prompt}}",
    State.ASK_WRONG_CONTACT_TYPE: "{{wrong_contact_type_prompt}}",
    State.ASK_WRONG_CONTACT_NAME: "{{wrong_contact_name_prompt}}",
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
    State.COLLECT_TRAINING_PINCODE: "{{training_pincode_prompt}}",
    State.ASK_BILLING_START_TIMELINE: "{{billing_start_timeline_prompt}}",
    State.DETOUR_ANYTHING_ELSE: "{{detour_anything_else_prompt}}",
    State.VERIFY_WHATSAPP: "जिस number से अभी बात हो रही है — वो क्या WhatsApp पर available है?",
    State.COLLECT_WHATSAPP_NUMBER: "{{whatsapp_collection_prompt}}",
    State.CONFIRM_WHATSAPP_NUMBER: "तो आपका WhatsApp number है — {{spoken_whatsapp_digits}} — सही है?",
    State.ASK_ALTERNATE_NUMBER: "क्या आप कोई alternate number भी देना चाहेंगे?",
    State.COLLECT_ALTERNATE_NUMBER: "{{alternate_collection_prompt}}",
    State.CONFIRM_ALTERNATE_NUMBER: "तो आपका alternate number है — {{spoken_alternate_digits}} — सही है?",
    State.VERIFY_PINCODE: "{{verify_pincode_prompt}}",
    State.COLLECT_PINCODE: "{{pincode_collection_prompt}}",
    State.CONFIRM_PINCODE: "तो आपका pin code है — {{spoken_pincode_digits}} — सही है?",
    State.VERIFY_BUSINESS_DETAILS: (
        "आपका business type {{display_business_type}} है — और trade {{display_business_trade}} है — यही सही है?"
    ),
    State.CONFIRM_BUSINESS_DETAILS: (
        "तो आपका business type {{display_business_type}} है — और trade {{display_business_trade}} है — यही सही है?"
    ),
    State.VERIFY_EMAIL: "{{verify_email_prompt}}",
    State.COLLECT_EMAIL_CORRECTION: "{{email_collection_prompt}}",
    State.CONFIRM_EMAIL_CORRECTION: "तो आपकी email ID — {{spoken_current_email}} — यही है?",
    State.ASK_PURCHASE_AMOUNT: "{{purchase_amount_prompt}}",
    State.SUPPORT_AND_REFERRAL: (
        "आपकी जानकारी के लिए — अगर software में कोई भी problem आए, तो software के home page के top पर 'Marg Help' का option है, "
        "वहाँ images और videos के through help मिल जाएगी। और उसी के साथ 'Ticket' का option भी है — license number डालकर "
        "ticket raise करें, तो हमारी side से call आ जाएगी। साथ ही Marg की तरफ से free software demo भी arrange किया जा रहा है — "
        "अगर आपके known में कोई person billing software लेने में interested हो, तो क्या आप उनका नाम और contact number share कर सकते हैं?"
    ),
    State.COLLECT_REFERRAL_NAME: "बहुत अच्छा जी — कृपया उनका नाम बताइए?",
    State.COLLECT_REFERRAL_NUMBER: "{{referral_collection_prompt}}",
    State.CONFIRM_REFERRAL_NUMBER: "तो referral का number है — {{spoken_referral_digits}} — सही है?",
    State.REFERRAL_DECLINE_NUDGE: "{{referral_nudge_prompt}}",
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
