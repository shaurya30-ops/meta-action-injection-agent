from __future__ import annotations

from conversation_engine.hot_path.grammars.base import StateGrammar
from conversation_engine.hot_path.grammars.states.ask_alternate_number import GRAMMAR as ASK_ALTERNATE_NUMBER
from conversation_engine.hot_path.grammars.states.ask_billing_status import GRAMMAR as ASK_BILLING_STATUS
from conversation_engine.hot_path.grammars.states.ask_callback_time import GRAMMAR as ASK_CALLBACK_TIME
from conversation_engine.hot_path.grammars.states.ask_purchase_amount import GRAMMAR as ASK_PURCHASE_AMOUNT
from conversation_engine.hot_path.grammars.states.busy_nudge import GRAMMAR as BUSY_NUDGE
from conversation_engine.hot_path.grammars.states.check_availability import GRAMMAR as CHECK_AVAILABILITY
from conversation_engine.hot_path.grammars.states.collect_email_correction import GRAMMAR as COLLECT_EMAIL_CORRECTION
from conversation_engine.hot_path.grammars.states.confirm_business_details import GRAMMAR as CONFIRM_BUSINESS_DETAILS
from conversation_engine.hot_path.grammars.states.confirm_callback_time import GRAMMAR as CONFIRM_CALLBACK_TIME
from conversation_engine.hot_path.grammars.states.confirm_email_correction import GRAMMAR as CONFIRM_EMAIL_CORRECTION
from conversation_engine.hot_path.grammars.states.confirm_identity import GRAMMAR as CONFIRM_IDENTITY
from conversation_engine.hot_path.grammars.states.explore_billing_blocker import GRAMMAR as EXPLORE_BILLING_BLOCKER
from conversation_engine.hot_path.grammars.states.opening_greeting import GRAMMAR as OPENING_GREETING
from conversation_engine.hot_path.grammars.states.referral_decline_nudge import GRAMMAR as REFERRAL_DECLINE_NUDGE
from conversation_engine.hot_path.grammars.states.support_and_referral import GRAMMAR as SUPPORT_AND_REFERRAL
from conversation_engine.hot_path.grammars.states.verify_business_details import GRAMMAR as VERIFY_BUSINESS_DETAILS
from conversation_engine.hot_path.grammars.states.verify_email import GRAMMAR as VERIFY_EMAIL
from conversation_engine.hot_path.grammars.states.verify_pincode import GRAMMAR as VERIFY_PINCODE
from conversation_engine.hot_path.grammars.states.verify_whatsapp import GRAMMAR as VERIFY_WHATSAPP


GRAMMAR_REGISTRY: dict[str, StateGrammar] = {
    OPENING_GREETING.state_name: OPENING_GREETING,
    CONFIRM_IDENTITY.state_name: CONFIRM_IDENTITY,
    CHECK_AVAILABILITY.state_name: CHECK_AVAILABILITY,
    BUSY_NUDGE.state_name: BUSY_NUDGE,
    ASK_BILLING_STATUS.state_name: ASK_BILLING_STATUS,
    EXPLORE_BILLING_BLOCKER.state_name: EXPLORE_BILLING_BLOCKER,
    VERIFY_WHATSAPP.state_name: VERIFY_WHATSAPP,
    ASK_ALTERNATE_NUMBER.state_name: ASK_ALTERNATE_NUMBER,
    VERIFY_PINCODE.state_name: VERIFY_PINCODE,
    VERIFY_BUSINESS_DETAILS.state_name: VERIFY_BUSINESS_DETAILS,
    CONFIRM_BUSINESS_DETAILS.state_name: CONFIRM_BUSINESS_DETAILS,
    VERIFY_EMAIL.state_name: VERIFY_EMAIL,
    COLLECT_EMAIL_CORRECTION.state_name: COLLECT_EMAIL_CORRECTION,
    CONFIRM_EMAIL_CORRECTION.state_name: CONFIRM_EMAIL_CORRECTION,
    ASK_PURCHASE_AMOUNT.state_name: ASK_PURCHASE_AMOUNT,
    SUPPORT_AND_REFERRAL.state_name: SUPPORT_AND_REFERRAL,
    REFERRAL_DECLINE_NUDGE.state_name: REFERRAL_DECLINE_NUDGE,
    ASK_CALLBACK_TIME.state_name: ASK_CALLBACK_TIME,
    CONFIRM_CALLBACK_TIME.state_name: CONFIRM_CALLBACK_TIME,
}


def get_state_grammar(state_name: str) -> StateGrammar | None:
    return GRAMMAR_REGISTRY.get(state_name)


__all__ = ["GRAMMAR_REGISTRY", "get_state_grammar"]
