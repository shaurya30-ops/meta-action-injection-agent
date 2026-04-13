from .states import State
from .intents import Intent

# ══════════════════════════════════════════════════════════════════════
# AUTO TRANSITIONS — Agent speaks then immediately advances (no user input)
# ══════════════════════════════════════════════════════════════════════
AUTO_TRANSITIONS: dict[State, State] = {
    State.OPENING_GREETING:           State.CONFIRM_IDENTITY,
    State.EXPLAIN_PURPOSE:            State.ASK_BILLING_STATUS,
    State.DETAILS_VERIFICATION_INTRO: State.VERIFY_WHATSAPP,
    State.URGENT_ESCALATION_FLAG:     State.CAPTURE_CALLBACK_TIME,
    State.SUPPORT_GUIDANCE:           State.EXPLAIN_MARG_HELP,
    State.EXPLAIN_MARG_HELP:          State.EXPLAIN_TICKET_SYSTEM,
    State.HELPLINE_REMINDER:          State.CHECK_SENTIMENT_ELIGIBILITY,
    State.WARM_CLOSING:               State.LOG_DISPOSITION,
    State.LOG_DISPOSITION:            State.END,
}

# ══════════════════════════════════════════════════════════════════════
# GLOBAL OVERRIDES — Fire from ANY state (with suppression list)
# Format: (intent, target_state, set_of_states_where_override_is_SUPPRESSED)
# Checked BEFORE state-specific transitions.
# ══════════════════════════════════════════════════════════════════════
GLOBAL_OVERRIDES: list[tuple[Intent, State, set[State]]] = [
    (
        Intent.GOODBYE,
        State.WARM_CLOSING,
        {State.WARM_CLOSING, State.LOG_DISPOSITION, State.END},
    ),
    (
        Intent.ESCALATE,
        State.DSAT_ESCALATION,
        {State.DSAT_ESCALATION, State.URGENT_ESCALATION_FLAG, State.CAPTURE_CALLBACK_TIME},
    ),
    (
        Intent.DEFER,
        State.CALLBACK_SCHEDULING,
        {State.CALLBACK_SCHEDULING, State.CAPTURE_CALLBACK_DATETIME, State.CAPTURE_CALLBACK_TIME},
    ),
]

# ══════════════════════════════════════════════════════════════════════
# INTENT-DRIVEN TRANSITIONS — (current_state, intent) -> next_state
# ══════════════════════════════════════════════════════════════════════
TRANSITIONS: dict[tuple[State, Intent], State] = {

    # ── Section 1: Identity & Availability ──
    (State.CONFIRM_IDENTITY, Intent.AFFIRM):     State.CHECK_AVAILABILITY,
    (State.CONFIRM_IDENTITY, Intent.INFORM):     State.CHECK_AVAILABILITY,
    (State.CONFIRM_IDENTITY, Intent.GREET):      State.CHECK_AVAILABILITY,
    (State.CONFIRM_IDENTITY, Intent.DENY):       State.INVALID_REGISTRATION,
    (State.CONFIRM_IDENTITY, Intent.ASK):        State.CONFIRM_IDENTITY,
    (State.CONFIRM_IDENTITY, Intent.UNCLEAR):    State.CONFIRM_IDENTITY,
    # Soft: model confuses THANK/ELABORATE/REQUEST with AFFIRM here
    (State.CONFIRM_IDENTITY, Intent.THANK):      State.CHECK_AVAILABILITY,
    (State.CONFIRM_IDENTITY, Intent.ELABORATE):  State.CHECK_AVAILABILITY,
    (State.CONFIRM_IDENTITY, Intent.REQUEST):    State.CONFIRM_IDENTITY,
    (State.CONFIRM_IDENTITY, Intent.OUT_OF_SCOPE): State.CONFIRM_IDENTITY,

    (State.CHECK_AVAILABILITY, Intent.AFFIRM):   State.FIRM_BUSINESS_CONFIRM,
    (State.CHECK_AVAILABILITY, Intent.INFORM):   State.FIRM_BUSINESS_CONFIRM,
    (State.CHECK_AVAILABILITY, Intent.DENY):     State.CALLBACK_SCHEDULING,
    (State.CHECK_AVAILABILITY, Intent.DEFER):    State.CALLBACK_SCHEDULING,
    (State.CHECK_AVAILABILITY, Intent.UNCLEAR):  State.CHECK_AVAILABILITY,
    # Soft
    (State.CHECK_AVAILABILITY, Intent.GREET):    State.FIRM_BUSINESS_CONFIRM,
    (State.CHECK_AVAILABILITY, Intent.THANK):    State.FIRM_BUSINESS_CONFIRM,
    (State.CHECK_AVAILABILITY, Intent.OBJECT):   State.CALLBACK_SCHEDULING,
    (State.CHECK_AVAILABILITY, Intent.COMPLAIN): State.CALLBACK_SCHEDULING,
    (State.CHECK_AVAILABILITY, Intent.REQUEST):  State.CHECK_AVAILABILITY,
    (State.CHECK_AVAILABILITY, Intent.OUT_OF_SCOPE): State.CHECK_AVAILABILITY,

    (State.FIRM_BUSINESS_CONFIRM, Intent.AFFIRM): State.EXPLAIN_PURPOSE,
    (State.FIRM_BUSINESS_CONFIRM, Intent.INFORM): State.EXPLAIN_PURPOSE,
    (State.FIRM_BUSINESS_CONFIRM, Intent.DENY):   State.INVALID_REGISTRATION,
    (State.FIRM_BUSINESS_CONFIRM, Intent.ASK):    State.FIRM_BUSINESS_CONFIRM,
    (State.FIRM_BUSINESS_CONFIRM, Intent.UNCLEAR): State.FIRM_BUSINESS_CONFIRM,
    # Soft
    (State.FIRM_BUSINESS_CONFIRM, Intent.GREET):  State.EXPLAIN_PURPOSE,
    (State.FIRM_BUSINESS_CONFIRM, Intent.THANK):  State.EXPLAIN_PURPOSE,
    (State.FIRM_BUSINESS_CONFIRM, Intent.ELABORATE): State.EXPLAIN_PURPOSE,
    (State.FIRM_BUSINESS_CONFIRM, Intent.REQUEST): State.FIRM_BUSINESS_CONFIRM,
    (State.FIRM_BUSINESS_CONFIRM, Intent.OUT_OF_SCOPE): State.FIRM_BUSINESS_CONFIRM,

    # ── Section 2: Billing Status (the big fork) ──
    (State.ASK_BILLING_STATUS, Intent.AFFIRM):   State.DETAILS_VERIFICATION_INTRO,
    (State.ASK_BILLING_STATUS, Intent.INFORM):   State.DELAY_REASON_PROBE,
    (State.ASK_BILLING_STATUS, Intent.DENY):     State.DELAY_REASON_PROBE,
    (State.ASK_BILLING_STATUS, Intent.OBJECT):   State.WILL_NOT_USE_PROBE,
    (State.ASK_BILLING_STATUS, Intent.DEFER):    State.DELAY_REASON_PROBE,
    (State.ASK_BILLING_STATUS, Intent.COMPLAIN): State.ISSUE_HANDLING,
    (State.ASK_BILLING_STATUS, Intent.ESCALATE): State.DSAT_ESCALATION,
    (State.ASK_BILLING_STATUS, Intent.UNCLEAR):  State.ASK_BILLING_STATUS,
    # Soft: model confuses THANK/GREET with AFFIRM here
    (State.ASK_BILLING_STATUS, Intent.THANK):    State.DETAILS_VERIFICATION_INTRO,
    (State.ASK_BILLING_STATUS, Intent.GREET):    State.ASK_BILLING_STATUS,
    (State.ASK_BILLING_STATUS, Intent.ELABORATE): State.DELAY_REASON_PROBE,
    (State.ASK_BILLING_STATUS, Intent.REQUEST):  State.ASK_BILLING_STATUS,
    (State.ASK_BILLING_STATUS, Intent.OUT_OF_SCOPE): State.ASK_BILLING_STATUS,

    # ── Section 2.3: Delay Reason Probe ──
    (State.DELAY_REASON_PROBE, Intent.INFORM):     State.SUPPORT_GUIDANCE,
    (State.DELAY_REASON_PROBE, Intent.ELABORATE):  State.SUPPORT_GUIDANCE,
    (State.DELAY_REASON_PROBE, Intent.AFFIRM):     State.SUPPORT_GUIDANCE,
    (State.DELAY_REASON_PROBE, Intent.COMPLAIN):   State.ISSUE_HANDLING,
    (State.DELAY_REASON_PROBE, Intent.OBJECT):     State.WILL_NOT_USE_PROBE,
    (State.DELAY_REASON_PROBE, Intent.DENY):       State.SUPPORT_GUIDANCE,
    (State.DELAY_REASON_PROBE, Intent.UNCLEAR):    State.DELAY_REASON_PROBE,
    (State.DELAY_REASON_PROBE, Intent.ESCALATE):   State.DSAT_ESCALATION,

    # ── Section 2.4: Will Not Use Probe ──
    (State.WILL_NOT_USE_PROBE, Intent.INFORM):     State.OFFER_SUPPORT_CALLBACK,
    (State.WILL_NOT_USE_PROBE, Intent.ELABORATE):  State.OFFER_SUPPORT_CALLBACK,
    (State.WILL_NOT_USE_PROBE, Intent.COMPLAIN):   State.OFFER_SUPPORT_CALLBACK,
    (State.WILL_NOT_USE_PROBE, Intent.DENY):       State.RECORD_REASON_POLITE_CLOSE,
    (State.WILL_NOT_USE_PROBE, Intent.OBJECT):     State.RECORD_REASON_POLITE_CLOSE,
    (State.WILL_NOT_USE_PROBE, Intent.ESCALATE):   State.DSAT_ESCALATION,
    (State.WILL_NOT_USE_PROBE, Intent.AFFIRM):     State.RECORD_REASON_POLITE_CLOSE,
    (State.WILL_NOT_USE_PROBE, Intent.UNCLEAR):    State.WILL_NOT_USE_PROBE,

    (State.OFFER_SUPPORT_CALLBACK, Intent.AFFIRM):  State.CAPTURE_CALLBACK_TIME,
    (State.OFFER_SUPPORT_CALLBACK, Intent.INFORM):  State.CAPTURE_CALLBACK_TIME,
    (State.OFFER_SUPPORT_CALLBACK, Intent.DENY):    State.RECORD_REASON_POLITE_CLOSE,
    (State.OFFER_SUPPORT_CALLBACK, Intent.OBJECT):  State.RECORD_REASON_POLITE_CLOSE,
    (State.OFFER_SUPPORT_CALLBACK, Intent.UNCLEAR): State.OFFER_SUPPORT_CALLBACK,

    # ── Section 3: Details Verification Chain ──
    # Every verification state accepts GREET/THANK/REQUEST/ELABORATE/OUT_OF_SCOPE/COMPLAIN
    # as "advance" or "re-ask" to prevent fallback accumulation from misclassifications.

    (State.VERIFY_WHATSAPP, Intent.AFFIRM):           State.COLLECT_ALTERNATE_NUMBER,
    (State.VERIFY_WHATSAPP, Intent.INFORM):           State.COLLECT_ALTERNATE_NUMBER,
    (State.VERIFY_WHATSAPP, Intent.DENY):             State.COLLECT_ALTERNATE_NUMBER,
    (State.VERIFY_WHATSAPP, Intent.UNCLEAR):          State.VERIFY_WHATSAPP,
    (State.VERIFY_WHATSAPP, Intent.GREET):            State.COLLECT_ALTERNATE_NUMBER,
    (State.VERIFY_WHATSAPP, Intent.THANK):            State.COLLECT_ALTERNATE_NUMBER,
    (State.VERIFY_WHATSAPP, Intent.ELABORATE):        State.COLLECT_ALTERNATE_NUMBER,
    (State.VERIFY_WHATSAPP, Intent.REQUEST):          State.VERIFY_WHATSAPP,
    (State.VERIFY_WHATSAPP, Intent.OUT_OF_SCOPE):     State.VERIFY_WHATSAPP,
    (State.VERIFY_WHATSAPP, Intent.COMPLAIN):         State.ISSUE_HANDLING,
    (State.VERIFY_WHATSAPP, Intent.OBJECT):           State.COLLECT_ALTERNATE_NUMBER,

    (State.COLLECT_ALTERNATE_NUMBER, Intent.INFORM):  State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.DENY):    State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.AFFIRM):  State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.UNCLEAR):  State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.GREET):   State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.THANK):   State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.OBJECT):  State.VERIFY_PINCODE,
    (State.COLLECT_ALTERNATE_NUMBER, Intent.OUT_OF_SCOPE): State.VERIFY_PINCODE,

    (State.VERIFY_PINCODE, Intent.AFFIRM):            State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_PINCODE, Intent.INFORM):            State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_PINCODE, Intent.DENY):              State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_PINCODE, Intent.UNCLEAR):           State.VERIFY_PINCODE,
    (State.VERIFY_PINCODE, Intent.GREET):             State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_PINCODE, Intent.ELABORATE):         State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_PINCODE, Intent.OUT_OF_SCOPE):      State.VERIFY_PINCODE,
    (State.VERIFY_PINCODE, Intent.COMPLAIN):          State.ISSUE_HANDLING,

    (State.VERIFY_BUSINESS_TRADE, Intent.INFORM):     State.VERIFY_EMAIL,
    (State.VERIFY_BUSINESS_TRADE, Intent.AFFIRM):     State.VERIFY_EMAIL,
    (State.VERIFY_BUSINESS_TRADE, Intent.UNCLEAR):    State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_BUSINESS_TRADE, Intent.GREET):      State.VERIFY_EMAIL,
    (State.VERIFY_BUSINESS_TRADE, Intent.DENY):       State.VERIFY_EMAIL,
    (State.VERIFY_BUSINESS_TRADE, Intent.ELABORATE):  State.VERIFY_EMAIL,
    (State.VERIFY_BUSINESS_TRADE, Intent.OUT_OF_SCOPE): State.VERIFY_BUSINESS_TRADE,
    (State.VERIFY_BUSINESS_TRADE, Intent.COMPLAIN):   State.ISSUE_HANDLING,

    (State.VERIFY_EMAIL, Intent.INFORM):              State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.AFFIRM):              State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.DENY):                State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.UNCLEAR):             State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.GREET):               State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.ELABORATE):           State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.OUT_OF_SCOPE):        State.ASK_PRICE,
    (State.VERIFY_EMAIL, Intent.COMPLAIN):            State.ISSUE_HANDLING,
    (State.VERIFY_EMAIL, Intent.OBJECT):              State.ASK_PRICE,

    # ASK_PRICE: DENY is handled by programmatic node (attempt counter)
    (State.ASK_PRICE, Intent.INFORM):                 State.SATISFACTION_CHECK,
    (State.ASK_PRICE, Intent.AFFIRM):                 State.SATISFACTION_CHECK,
    (State.ASK_PRICE, Intent.UNCLEAR):                State.ASK_PRICE,
    (State.ASK_PRICE, Intent.GREET):                  State.ASK_PRICE,
    (State.ASK_PRICE, Intent.ELABORATE):              State.SATISFACTION_CHECK,
    (State.ASK_PRICE, Intent.OUT_OF_SCOPE):           State.ASK_PRICE,
    (State.ASK_PRICE, Intent.OBJECT):                 State.SATISFACTION_CHECK,
    (State.ASK_PRICE, Intent.COMPLAIN):               State.ISSUE_HANDLING,

    # ── Section 4: Satisfaction Check ──
    (State.SATISFACTION_CHECK, Intent.AFFIRM):     State.SUPPORT_GUIDANCE,
    (State.SATISFACTION_CHECK, Intent.INFORM):     State.SUPPORT_GUIDANCE,
    (State.SATISFACTION_CHECK, Intent.THANK):      State.SUPPORT_GUIDANCE,
    (State.SATISFACTION_CHECK, Intent.ELABORATE):  State.SUPPORT_GUIDANCE,
    (State.SATISFACTION_CHECK, Intent.COMPLAIN):   State.ISSUE_HANDLING,
    (State.SATISFACTION_CHECK, Intent.ESCALATE):   State.DSAT_ESCALATION,
    (State.SATISFACTION_CHECK, Intent.DENY):       State.ISSUE_HANDLING,
    (State.SATISFACTION_CHECK, Intent.UNCLEAR):    State.SATISFACTION_CHECK,
    # Soft: OBJECT/ASK = negative, GREET/REQUEST = neutral positive
    (State.SATISFACTION_CHECK, Intent.OBJECT):     State.ISSUE_HANDLING,
    (State.SATISFACTION_CHECK, Intent.GREET):      State.SUPPORT_GUIDANCE,
    (State.SATISFACTION_CHECK, Intent.REQUEST):    State.SUPPORT_GUIDANCE,
    (State.SATISFACTION_CHECK, Intent.ASK):        State.SATISFACTION_CHECK,
    (State.SATISFACTION_CHECK, Intent.OUT_OF_SCOPE): State.SATISFACTION_CHECK,

    # ── Section 6A: Issue Handling ──
    (State.ISSUE_HANDLING, Intent.INFORM):     State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.ELABORATE):  State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.COMPLAIN):   State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.UNCLEAR):    State.ISSUE_HANDLING,
    # Soft: any response = customer is talking about issue = capture
    (State.ISSUE_HANDLING, Intent.AFFIRM):     State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.OBJECT):     State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.REQUEST):    State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.DENY):       State.CAPTURE_ISSUE_SUMMARY,
    (State.ISSUE_HANDLING, Intent.OUT_OF_SCOPE): State.ISSUE_HANDLING,

    (State.CAPTURE_ISSUE_SUMMARY, Intent.AFFIRM):    State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.INFORM):    State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.DENY):      State.ISSUE_HANDLING,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.ELABORATE):  State.CAPTURE_CALLBACK_TIME,
    # Soft
    (State.CAPTURE_ISSUE_SUMMARY, Intent.THANK):     State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.GREET):     State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.COMPLAIN):  State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.REQUEST):   State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_ISSUE_SUMMARY, Intent.UNCLEAR):   State.CAPTURE_ISSUE_SUMMARY,

    # ── Section 6B: D-SAT Escalation ──
    # ANY response advances — let the customer vent, then escalate
    (State.DSAT_ESCALATION, Intent.INFORM):    State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.ELABORATE): State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.COMPLAIN):  State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.ESCALATE):  State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.AFFIRM):    State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.DENY):      State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.OBJECT):    State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.REQUEST):   State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.ASK):       State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.THANK):     State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.GREET):     State.URGENT_ESCALATION_FLAG,
    (State.DSAT_ESCALATION, Intent.UNCLEAR):   State.DSAT_ESCALATION,
    (State.DSAT_ESCALATION, Intent.OUT_OF_SCOPE): State.URGENT_ESCALATION_FLAG,

    # ── Section 7: Callback Scheduling ──
    # ANY response = customer gave a time or acknowledged = advance
    (State.CALLBACK_SCHEDULING, Intent.INFORM):   State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.AFFIRM):   State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.DENY):     State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.DEFER):    State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.UNCLEAR):  State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.ELABORATE): State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.REQUEST):  State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.GREET):    State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.THANK):    State.CAPTURE_CALLBACK_DATETIME,
    (State.CALLBACK_SCHEDULING, Intent.OUT_OF_SCOPE): State.CAPTURE_CALLBACK_DATETIME,

    (State.CAPTURE_CALLBACK_DATETIME, Intent.AFFIRM): State.WARM_CLOSING,
    (State.CAPTURE_CALLBACK_DATETIME, Intent.INFORM): State.WARM_CLOSING,
    (State.CAPTURE_CALLBACK_DATETIME, Intent.DENY):   State.CALLBACK_SCHEDULING,
    # Soft: most responses = accept and close
    (State.CAPTURE_CALLBACK_DATETIME, Intent.THANK):  State.WARM_CLOSING,
    (State.CAPTURE_CALLBACK_DATETIME, Intent.GREET):  State.WARM_CLOSING,
    (State.CAPTURE_CALLBACK_DATETIME, Intent.ELABORATE): State.WARM_CLOSING,
    (State.CAPTURE_CALLBACK_DATETIME, Intent.UNCLEAR): State.WARM_CLOSING,

    # ── Capture Callback Time (from issue/D-SAT) ──
    # Most responses = customer acknowledged or gave time = advance
    (State.CAPTURE_CALLBACK_TIME, Intent.INFORM):     State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.AFFIRM):     State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.DENY):       State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.UNCLEAR):    State.CAPTURE_CALLBACK_TIME,
    (State.CAPTURE_CALLBACK_TIME, Intent.ELABORATE):  State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.GREET):      State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.THANK):      State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.REQUEST):    State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.COMPLAIN):   State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.OBJECT):     State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.OUT_OF_SCOPE): State.SUPPORT_GUIDANCE,
    (State.CAPTURE_CALLBACK_TIME, Intent.ASK):        State.CAPTURE_CALLBACK_TIME,

    # ── Support Guidance sub-flow ──
    (State.EXPLAIN_TICKET_SYSTEM, Intent.AFFIRM):  State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.INFORM):  State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.ASK):     State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.THANK):   State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.UNCLEAR):  State.CHECK_LICENSE_NUMBER,
    # Soft: anything positive/neutral = advance
    (State.EXPLAIN_TICKET_SYSTEM, Intent.GREET):   State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.DENY):    State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.ELABORATE): State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.REQUEST):  State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.OUT_OF_SCOPE): State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.COMPLAIN): State.CHECK_LICENSE_NUMBER,
    (State.EXPLAIN_TICKET_SYSTEM, Intent.OBJECT):  State.CHECK_LICENSE_NUMBER,

    (State.CHECK_LICENSE_NUMBER, Intent.AFFIRM):   State.HELPLINE_REMINDER,
    (State.CHECK_LICENSE_NUMBER, Intent.INFORM):   State.HELPLINE_REMINDER,
    (State.CHECK_LICENSE_NUMBER, Intent.DENY):     State.CAPTURE_ISSUE_CALLBACK,
    # Soft: most responses = advance
    (State.CHECK_LICENSE_NUMBER, Intent.GREET):    State.HELPLINE_REMINDER,
    (State.CHECK_LICENSE_NUMBER, Intent.THANK):    State.HELPLINE_REMINDER,
    (State.CHECK_LICENSE_NUMBER, Intent.ELABORATE): State.HELPLINE_REMINDER,
    (State.CHECK_LICENSE_NUMBER, Intent.UNCLEAR):  State.CHECK_LICENSE_NUMBER,
    (State.CHECK_LICENSE_NUMBER, Intent.OBJECT):   State.CAPTURE_ISSUE_CALLBACK,
    (State.CHECK_LICENSE_NUMBER, Intent.COMPLAIN): State.CAPTURE_ISSUE_CALLBACK,
    (State.CHECK_LICENSE_NUMBER, Intent.REQUEST):  State.CAPTURE_ISSUE_CALLBACK,
    (State.CHECK_LICENSE_NUMBER, Intent.OUT_OF_SCOPE): State.CHECK_LICENSE_NUMBER,

    (State.CAPTURE_ISSUE_CALLBACK, Intent.INFORM):    State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.AFFIRM):    State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.ELABORATE):  State.HELPLINE_REMINDER,
    # Soft
    (State.CAPTURE_ISSUE_CALLBACK, Intent.COMPLAIN):  State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.DENY):      State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.GREET):     State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.THANK):     State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.REQUEST):   State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.UNCLEAR):   State.CAPTURE_ISSUE_CALLBACK,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.OBJECT):    State.HELPLINE_REMINDER,
    (State.CAPTURE_ISSUE_CALLBACK, Intent.OUT_OF_SCOPE): State.HELPLINE_REMINDER,

    # ── Section 8: Reference Pitch ──
    (State.REFERENCE_PITCH, Intent.AFFIRM):   State.CAPTURE_REFERENCE,
    (State.REFERENCE_PITCH, Intent.INFORM):   State.CAPTURE_REFERENCE,
    (State.REFERENCE_PITCH, Intent.DENY):     State.WARM_CLOSING,
    (State.REFERENCE_PITCH, Intent.OBJECT):   State.WARM_CLOSING,
    (State.REFERENCE_PITCH, Intent.UNCLEAR):  State.WARM_CLOSING,
    # Soft: any positive = willing to refer, any negative = close
    (State.REFERENCE_PITCH, Intent.ELABORATE): State.CAPTURE_REFERENCE,
    (State.REFERENCE_PITCH, Intent.THANK):    State.CAPTURE_REFERENCE,
    (State.REFERENCE_PITCH, Intent.GREET):    State.CAPTURE_REFERENCE,
    (State.REFERENCE_PITCH, Intent.REQUEST):  State.WARM_CLOSING,
    (State.REFERENCE_PITCH, Intent.COMPLAIN): State.WARM_CLOSING,
    (State.REFERENCE_PITCH, Intent.OUT_OF_SCOPE): State.WARM_CLOSING,
    (State.REFERENCE_PITCH, Intent.ASK):      State.REFERENCE_PITCH,

    (State.CAPTURE_REFERENCE, Intent.INFORM):  State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.AFFIRM):  State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.DENY):    State.WARM_CLOSING,
    # Soft: any response after giving reference = close
    (State.CAPTURE_REFERENCE, Intent.ELABORATE): State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.THANK):   State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.GREET):   State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.UNCLEAR):  State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.OUT_OF_SCOPE): State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.REQUEST):  State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.COMPLAIN): State.WARM_CLOSING,
    (State.CAPTURE_REFERENCE, Intent.OBJECT):   State.WARM_CLOSING,
}
