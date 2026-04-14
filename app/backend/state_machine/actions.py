from .states import State

ACTION_MAP: dict[State, str | None] = {
    State.OPENING_GREETING: (
        "Hello, मैं आकृति बोल रही हूँ Marg ई आर पी software Delhi head office से. "
        "क्या मेरी बात {{company_name}} मैं हो रही है?"
    ),
    State.CONFIRM_IDENTITY: "जी, क्या मेरी बात {{company_name}} मैं हो रही है?",
    State.CHECK_AVAILABILITY: (
        "ठीक है जी, ये एक post-sale feedback और verification call है Marg ई आर पी software की तरफ से। "
        "क्या अभी दो मिनट बात हो सकती है?"
    ),
    State.ASK_BILLING_STATUS: "जी धन्यवाद। क्या आपके software में billing start हो गई है?",
    State.VERIFY_WHATSAPP: "जिस number से अभी बात हो रही है — वो क्या WhatsApp पर available है?",
    State.COLLECT_WHATSAPP_NUMBER: "{{whatsapp_collection_prompt}}",
    State.ASK_ALTERNATE_NUMBER: "क्या आप कोई alternate number भी देना चाहेंगे?",
    State.COLLECT_ALTERNATE_NUMBER: "{{alternate_collection_prompt}}",
    State.VERIFY_PINCODE: "आपका area pin code — {{spoken_crm_pincode}} — यही है?",
    State.COLLECT_PINCODE: "{{pincode_collection_prompt}}",
    State.VERIFY_BUSINESS_DETAILS: (
        "आपका business type {{display_business_type}} है — और trade {{display_business_trade}} है — यही सही है?"
    ),
    State.VERIFY_EMAIL: "आपकी email ID — {{spoken_crm_email}} — यही है?",
    State.ASK_PURCHASE_AMOUNT: "आप बता सकते हैं — आपने जो software purchase किया था, वो किस amount पर था?",
    State.SUPPORT_AND_REFERRAL: (
        "आपकी जानकारी के लिए — अगर software में कोई भी problem आए, तो software के home page के top पर 'Marg Help' का option है, "
        "वहाँ images और videos के through help मिल जाएगी। और उसी के साथ 'Ticket' का option भी है — license number डालकर "
        "ticket raise करें, तो हमारी side से call आ जाएगी। साथ ही Marg की तरफ से free software demo भी arrange किया जा रहा है — "
        "अगर आपके known में कोई person billing software लेने में interested हो, तो क्या आप उनका नाम और contact number share कर सकते हैं?"
    ),
    State.COLLECT_REFERRAL: "{{referral_collection_prompt}}",
    State.CALLBACK_CLOSING: "{{callback_closing_text}}",
    State.INVALID_REGISTRATION: "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे.",
    State.WARM_CLOSING: "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे.",
    State.LOG_DISPOSITION: None,
    State.END: None,
}
