import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dispositions.resolver import compute_disposition
from content_extraction.extractor_logic import build_render_context, extract_digits
from intent_classifier.classifier import _load_worker_tokenizer
from intent_classifier.fallback import RegexFallbackClassifier
from prompts.payload_builder import build_action_text
from state_machine.intents import Intent
from state_machine.resolver import post_transition, resolve_next_state
from state_machine.session import CallSession
from state_machine.states import State
from state_machine.turn_parser import parse_turn
from state_machine.transitions import AUTO_TRANSITIONS, TRANSITIONS
from utils.transcript import sanitize_user_transcript


class RegexFallbackClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = RegexFallbackClassifier()

    def test_module_fragments_are_inform(self):
        self.assertEqual(self.classifier.classify("Billing"), Intent.INFORM)
        self.assertEqual(self.classifier.classify("back end"), Intent.INFORM)

    def test_boliye_is_request(self):
        self.assertEqual(self.classifier.classify("haan ji boliye"), Intent.REQUEST)

    def test_busy_callback_phrase_is_defer(self):
        self.assertEqual(
            self.classifier.classify("जी आप मुझे पांच minute बाद call करो."),
            Intent.DEFER,
        )

    def test_hindi_clarification_question_is_ask(self):
        self.assertEqual(
            self.classifier.classify("हां जी उसका नाम क्या लिखा आपने?"),
            Intent.ASK,
        )


class IntentClassifierLoaderTests(unittest.TestCase):
    @patch("intent_classifier.classifier._is_local_source", return_value=False)
    @patch("transformers.AutoTokenizer.from_pretrained")
    def test_broken_adapter_tokenizer_falls_back_to_base_source(
        self,
        mocked_from_pretrained,
        _mocked_is_local_source,
    ):
        mocked_from_pretrained.side_effect = [
            Exception("broken adapter tokenizer"),
            "base-tokenizer",
        ]

        tokenizer = _load_worker_tokenizer(
            "adapter-dir",
            "Qwen/Qwen2.5-0.5B-Instruct",
        )

        self.assertEqual(tokenizer, "base-tokenizer")
        self.assertEqual(mocked_from_pretrained.call_count, 2)
        self.assertEqual(mocked_from_pretrained.call_args_list[0].args[0], "adapter-dir")
        self.assertTrue(mocked_from_pretrained.call_args_list[0].kwargs["local_files_only"])
        self.assertEqual(
            mocked_from_pretrained.call_args_list[1].args[0],
            "Qwen/Qwen2.5-0.5B-Instruct",
        )
        self.assertFalse(mocked_from_pretrained.call_args_list[1].kwargs["local_files_only"])


class TranscriptSanitizerTests(unittest.TestCase):
    def test_chat_markup_keeps_latest_user_utterance(self):
        raw = (
            '<|im_end|>\n<|im_start|>assistant\nजी आगे बताइए<|im_end|>\n'
            '<|im_start|>user\nnumber कहां तक load हुआ है"}'
        )
        self.assertEqual(
            sanitize_user_transcript(raw),
            "number कहां तक load हुआ है",
        )


class StrictFlowTransitionTests(unittest.TestCase):
    def test_opening_advances_to_availability_then_billing(self):
        self.assertEqual(
            TRANSITIONS[(State.OPENING_GREETING, Intent.AFFIRM)],
            State.CHECK_AVAILABILITY,
        )
        self.assertEqual(
            TRANSITIONS[(State.CHECK_AVAILABILITY, Intent.AFFIRM)],
            State.ASK_BILLING_STATUS,
        )

    def test_verification_chain_uses_explicit_confirmation_states(self):
        self.assertEqual(
            TRANSITIONS[(State.VERIFY_WHATSAPP, Intent.DENY)],
            State.COLLECT_WHATSAPP_NUMBER,
        )
        self.assertEqual(
            TRANSITIONS[(State.CONFIRM_WHATSAPP_NUMBER, Intent.AFFIRM)],
            State.ASK_ALTERNATE_NUMBER,
        )
        self.assertEqual(
            TRANSITIONS[(State.CONFIRM_PINCODE, Intent.AFFIRM)],
            State.VERIFY_BUSINESS_DETAILS,
        )
        self.assertEqual(
            TRANSITIONS[(State.SUPPORT_AND_REFERRAL, Intent.DENY)],
            State.REFERRAL_DECLINE_NUDGE,
        )
        self.assertEqual(
            TRANSITIONS[(State.VERIFY_EMAIL, Intent.DENY)],
            State.COLLECT_EMAIL_CORRECTION,
        )
        self.assertEqual(
            AUTO_TRANSITIONS[State.PRE_CLOSING],
            State.FIXED_CLOSING,
        )


class ResolverFlowTests(unittest.TestCase):
    def advance(self, session: CallSession, intent: Intent, transcript: str) -> State:
        next_state = resolve_next_state(session, intent, transcript)
        post_transition(session, intent, transcript, next_state)
        return next_state

    def test_opening_affirm_with_question_mark_does_not_trigger_query_mode(self):
        session = CallSession(current_state=State.OPENING_GREETING)

        next_state = self.advance(session, Intent.AFFIRM, "हाँ जी हो रही है?")

        self.assertEqual(next_state, State.CHECK_AVAILABILITY)
        self.assertEqual(session.current_state, State.CHECK_AVAILABILITY)
        self.assertEqual(
            build_action_text(session),
            "ठीक है जी, ये एक post-sale feedback और verification call है Marg ई आर पी software की तरफ से। क्या अभी दो मिनट बात हो सकती है?",
        )

    def test_callback_request_nudges_before_time_confirmation(self):
        session = CallSession(current_state=State.CHECK_AVAILABILITY)

        next_state = self.advance(session, Intent.REQUEST, "जी आप मुझे पांच minute बाद call करो.")

        self.assertEqual(next_state, State.BUSY_NUDGE)
        self.assertEqual(session.current_state, State.BUSY_NUDGE)
        self.assertIn("verification बहुत ज़रूरी", build_action_text(session))

        next_state = self.advance(session, Intent.DEFER, "जी पांच minute बाद call करो.")

        self.assertEqual(next_state, State.CONFIRM_CALLBACK_TIME)
        self.assertEqual(session.callback_time_phrase, "पांच minute बाद")
        self.assertIn("पांच minute बाद", build_action_text(session))

    def test_callback_without_specific_time_asks_for_schedule_after_busy_nudge(self):
        session = CallSession(current_state=State.CHECK_AVAILABILITY)

        next_state = self.advance(
            session,
            Intent.DEFER,
            "नहीं आप बाद में call करो.",
        )

        self.assertEqual(next_state, State.BUSY_NUDGE)
        self.assertEqual(
            build_action_text(session),
            "जी, मैं समझ सकती हूँ आप busy हैं। लेकिन ये verification बहुत ज़रूरी है ताकि आपकी details updated रहें, और ये सिर्फ 2 minute लेगा। क्या हम जल्दी से complete कर लें?",
        )

        next_state = self.advance(
            session,
            Intent.DEFER,
            "कल सुबह 11 बजे call करना.",
        )

        self.assertEqual(next_state, State.CONFIRM_CALLBACK_TIME)
        self.assertIn("कल सुबह 11 बजे", build_action_text(session))

        next_state = self.advance(session, Intent.AFFIRM, "हाँ")

        self.assertEqual(next_state, State.FIXED_CLOSING)
        self.assertEqual(
            build_action_text(session),
            "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे.",
        )

    def test_callback_time_unclear_gets_one_retry_then_generic_close(self):
        session = CallSession(current_state=State.CHECK_AVAILABILITY)

        first_state = self.advance(
            session,
            Intent.DEFER,
            "बाद में call करो.",
        )

        self.assertEqual(first_state, State.BUSY_NUDGE)

        second_state = self.advance(
            session,
            Intent.DEFER,
            "बाद में call करो.",
        )

        self.assertEqual(second_state, State.ASK_CALLBACK_TIME)

        third_state = self.advance(
            session,
            Intent.UNCLEAR,
            "अभी नहीं पता.",
        )

        self.assertEqual(third_state, State.ASK_CALLBACK_TIME)
        self.assertIn("सिर्फ time या दिन", build_action_text(session))

        fourth_state = self.advance(
            session,
            Intent.UNCLEAR,
            "पता नहीं.",
        )

        self.assertEqual(fourth_state, State.CALLBACK_CLOSING)
        self.assertEqual(session.callback_closing_text, "जी बिल्कुल, मैं थोड़ी देर बाद call करती हूँ।")

    def test_owner_redirects_to_concerned_person_instead_of_generic_callback_pitch(self):
        session = CallSession(current_state=State.CHECK_AVAILABILITY)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "madam यह दूसरा लड़का संभालता है. मैं तो मालिक हूं. उससे call करो.",
        )

        self.assertEqual(next_state, State.ASK_CONCERNED_PERSON_CONTACT)
        rendered = build_action_text(session)
        self.assertIn("जो person software संभालते हैं", rendered)
        self.assertIn("contact number दे सकते हैं", rendered)
        self.assertNotIn("बहुत short में एक minute", rendered)

    def test_concerned_person_same_number_without_time_asks_targeted_callback_time(self):
        session = CallSession(current_state=State.ASK_CONCERNED_PERSON_CONTACT)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "इसी number पर बात हो जाएगी.",
        )

        self.assertEqual(next_state, State.ASK_CALLBACK_TIME)
        rendered = build_action_text(session)
        self.assertIn("उनसे बात करने के लिए", rendered)
        self.assertIn("किस time", rendered)

    def test_concerned_person_number_flows_to_confirmation_and_handoff_close(self):
        session = CallSession(current_state=State.ASK_CONCERNED_PERSON_CONTACT)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "उनका number 9876543210 है.",
        )

        self.assertEqual(next_state, State.CONFIRM_CONCERNED_PERSON_NUMBER)
        self.assertEqual(session.concerned_person_digit_buffer, "9876543210")

        next_state = self.advance(session, Intent.AFFIRM, "हाँ")

        self.assertEqual(next_state, State.WARM_CLOSING)
        self.assertEqual(session.concerned_person_number, "9876543210")
        rendered = build_action_text(session)
        self.assertIn("software संभालने वाले person से बात करने की कोशिश", rendered)

    def test_opening_unavailable_contact_routes_to_callback_schedule(self):
        session = CallSession(current_state=State.OPENING_GREETING)

        next_state = self.advance(
            session,
            Intent.DENY,
            "नहीं, वो अभी बाहर हैं.",
        )

        self.assertEqual(next_state, State.ASK_CALLBACK_TIME)
        self.assertTrue(session.callback_requested)
        self.assertIn("convenient time", build_action_text(session))

    def test_opening_wrong_number_routes_to_invalid_registration(self):
        session = CallSession(current_state=State.OPENING_GREETING)

        next_state = self.advance(
            session,
            Intent.DENY,
            "नहीं, आपने wrong number लगाया है.",
        )

        self.assertEqual(next_state, State.ASK_WRONG_CONTACT_COMPANY)
        rendered = build_action_text(session)
        self.assertIn("आप कहाँ से बोल रहे हैं", rendered)

    def test_wrong_contact_capture_closes_after_company_trade_and_type(self):
        session = CallSession(current_state=State.ASK_WRONG_CONTACT_COMPANY)

        next_state = self.advance(session, Intent.INFORM, "हम Tech Ladder से बोल रहे हैं.")
        self.assertEqual(next_state, State.ASK_WRONG_CONTACT_TRADE)

        next_state = self.advance(session, Intent.INFORM, "wholesale trade है.")
        self.assertEqual(next_state, State.ASK_WRONG_CONTACT_TYPE)

        next_state = self.advance(session, Intent.INFORM, "retailer है.")
        self.assertEqual(next_state, State.WARM_CLOSING)
        rendered = build_action_text(session)
        self.assertEqual(session.wrong_contact_company, "Tech Ladder")
        self.assertIn("wholesale", session.wrong_contact_trade.lower())
        self.assertEqual(session.wrong_contact_type, "Retailer")
        self.assertIn("records update", rendered)

    def test_user_requested_stop_gets_acknowledged_before_warm_close(self):
        session = CallSession(current_state=State.ASK_PURCHASE_AMOUNT)

        next_state = self.advance(
            session,
            Intent.AFFIRM,
            "ठीक है madam रहने दो.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        rendered = build_action_text(session)
        self.assertIn("आगे continue नहीं करना चाहते", rendered)
        self.assertIn("call यहीं close", rendered)
        self.assertNotIn("Marg में बने रहने के लिए आपका धन्यवाद", rendered)

    def test_whatsapp_buffer_moves_to_confirm_state_after_ten_digits(self):
        session = CallSession(current_state=State.COLLECT_WHATSAPP_NUMBER)

        self.advance(session, Intent.INFORM, "one two three four")
        self.assertEqual(session.current_state, State.COLLECT_WHATSAPP_NUMBER)
        self.assertEqual(session.whatsapp_digit_buffer, "1234")
        self.assertFalse(session.awaiting_whatsapp_confirmation)

        self.advance(session, Intent.INFORM, "five six seven eight")
        self.assertEqual(session.whatsapp_digit_buffer, "12345678")
        self.assertFalse(session.awaiting_whatsapp_confirmation)

        self.advance(session, Intent.INFORM, "nine zero")
        self.assertEqual(session.current_state, State.CONFIRM_WHATSAPP_NUMBER)
        self.assertEqual(session.whatsapp_digit_buffer, "1234567890")
        self.assertTrue(session.awaiting_whatsapp_confirmation)

        self.advance(session, Intent.AFFIRM, "हाँ")
        self.assertEqual(session.current_state, State.ASK_ALTERNATE_NUMBER)
        self.assertEqual(session.whatsapp_number, "1234567890")
        self.assertEqual(session.whatsapp_digit_buffer, "")

    def test_whatsapp_buffer_accepts_double_and_triple_digit_phrases(self):
        session = CallSession(current_state=State.COLLECT_WHATSAPP_NUMBER)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "nine eight three seven eight nine double two six two",
        )

        self.assertEqual(next_state, State.CONFIRM_WHATSAPP_NUMBER)
        self.assertEqual(session.whatsapp_digit_buffer, "9837892262")

        session = CallSession(current_state=State.COLLECT_PINCODE)
        next_state = self.advance(
            session,
            Intent.INFORM,
            "one triple three double zero",
        )

        self.assertEqual(next_state, State.CONFIRM_PINCODE)
        self.assertEqual(session.pincode_digit_buffer, "133300")

    def test_pincode_overflow_resets_buffer(self):
        session = CallSession(current_state=State.COLLECT_PINCODE)

        self.advance(session, Intent.INFORM, "one two")
        self.assertEqual(session.pincode_digit_buffer, "12")
        self.assertFalse(session.awaiting_pincode_confirmation)

        self.advance(session, Intent.INFORM, "three four five six seven")
        self.assertEqual(session.current_state, State.COLLECT_PINCODE)
        self.assertEqual(session.pincode_digit_buffer, "")
        self.assertFalse(session.awaiting_pincode_confirmation)

    def test_alternate_refusal_inform_skips_to_pincode(self):
        session = CallSession(current_state=State.ASK_ALTERNATE_NUMBER)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नई जी कोई alternate number नहीं है.",
        )

        self.assertEqual(next_state, State.VERIFY_PINCODE)
        self.assertEqual(session.current_state, State.VERIFY_PINCODE)

    def test_collection_ask_reports_loaded_digits(self):
        session = CallSession(
            current_state=State.COLLECT_ALTERNATE_NUMBER,
            alternate_digit_buffer="9876",
        )

        next_state = self.advance(
            session,
            Intent.ASK,
            "number कहां तक load हुआ है",
        )

        self.assertEqual(next_state, State.COLLECT_ALTERNATE_NUMBER)
        context = build_render_context(session)
        self.assertIn("4 digit load", context["alternate_collection_prompt"])
        self.assertIn("कुल 10 digit", context["alternate_collection_prompt"])

    def test_direct_alternate_digits_can_skip_to_confirm_state(self):
        session = CallSession(current_state=State.ASK_ALTERNATE_NUMBER)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "alternate number 9876543210",
        )

        self.assertEqual(next_state, State.CONFIRM_ALTERNATE_NUMBER)
        self.assertEqual(session.current_state, State.CONFIRM_ALTERNATE_NUMBER)
        self.assertEqual(session.alternate_digit_buffer, "9876543210")
        self.assertTrue(session.awaiting_alternate_confirmation)

    def test_same_whatsapp_after_initial_no_still_skips_collection(self):
        session = CallSession(current_state=State.VERIFY_WHATSAPP)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं नहीं same ही है.",
        )

        self.assertEqual(next_state, State.ASK_ALTERNATE_NUMBER)
        self.assertEqual(session.current_state, State.ASK_ALTERNATE_NUMBER)

    def test_alternate_same_as_whatsapp_duplicates_verified_number(self):
        session = CallSession(
            current_state=State.ASK_ALTERNATE_NUMBER,
            whatsapp_number="9876543210",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "same as WhatsApp ही रख लीजिए.",
        )

        self.assertEqual(next_state, State.VERIFY_PINCODE)
        self.assertEqual(session.current_state, State.VERIFY_PINCODE)
        self.assertEqual(session.alternate_number, "9876543210")

    def test_audio_check_replies_with_ack_and_repeats_current_question(self):
        session = CallSession(current_state=State.VERIFY_WHATSAPP)

        next_state = self.advance(
            session,
            Intent.ASK,
            "Awaaz aa rahi hai?",
        )

        self.assertEqual(next_state, State.VERIFY_WHATSAPP)
        rendered = build_action_text(session)
        self.assertIn("हाँ जी, मुझे आपकी आवाज़ आ रही है।", rendered)
        self.assertIn("WhatsApp", rendered)

    def test_escalate_intent_routes_to_team_contact_close(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.ESCALATE,
            "मुझे senior se baat karni hai.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        rendered = build_action_text(session)
        self.assertIn("हमारी team आपसे जल्द contact करेगी", rendered)

    def test_verify_pincode_inline_digits_preload_confirmation(self):
        session = CallSession(current_state=State.VERIFY_PINCODE)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं दूसरा pin code है one one zero zero one two.",
        )

        self.assertEqual(next_state, State.CONFIRM_PINCODE)
        self.assertEqual(session.current_state, State.CONFIRM_PINCODE)
        self.assertEqual(session.pincode_digit_buffer, "110012")
        self.assertTrue(session.awaiting_pincode_confirmation)

    def test_no_alternate_with_inline_pincode_preloads_pincode_confirmation(self):
        session = CallSession(current_state=State.ASK_ALTERNATE_NUMBER)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं कोई alternate नहीं है, pin one one zero zero one one.",
        )

        self.assertEqual(next_state, State.VERIFY_PINCODE)
        self.assertEqual(session.current_state, State.CONFIRM_PINCODE)
        self.assertEqual(session.pincode_digit_buffer, "110011")

    def test_billing_setup_in_progress_moves_forward_with_guidance(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं अभी setup ही कर रहा हूं.",
        )

        self.assertEqual(next_state, State.ASK_BILLING_START_TIMELINE)
        self.assertEqual(session.current_state, State.ASK_BILLING_START_TIMELINE)
        self.assertEqual(session.billing_started, "NOT_STARTED")
        self.assertEqual(session.billing_blocker_reason, "setup_in_progress")

        next_state = self.advance(
            session,
            Intent.INFORM,
            "कल तक start कर दूँगा.",
        )

        self.assertEqual(next_state, State.DETOUR_ANYTHING_ELSE)
        rendered = build_action_text(session)
        self.assertIn("setup पूरा होने", rendered)
        self.assertIn("कोई और बात", rendered)

        next_state = self.advance(session, Intent.DENY, "नहीं.")
        self.assertEqual(next_state, State.VERIFY_WHATSAPP)

    def test_partner_non_responsive_collects_payment_date_and_partner_name_then_closes(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.COMPLAIN,
            "payment कर दी है लेकिन partner response नहीं दे रहा.",
        )

        self.assertEqual(next_state, State.ESCALATE_PAYMENT_DATE)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "दो दिन पहले payment की थी.",
        )

        self.assertEqual(next_state, State.ESCALATE_PARTNER_NAME)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "partner राहुल है.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        self.assertIn("दो दिन पहले", session.partner_payment_date)
        self.assertIn("राहुल", session.partner_name)
        rendered = build_action_text(session)
        self.assertIn("partner से contact करेंगे", rendered)
        self.assertIn("20 से 48 घंटों", rendered)

    def test_switched_software_collects_name_and_reason_then_alt_closes(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.OBJECT,
            "हमने दूसरा software ले लिया.",
        )

        self.assertEqual(next_state, State.ESCALATE_SWITCHED_SOFTWARE)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "Tally लिया है.",
        )

        self.assertEqual(next_state, State.ESCALATE_SWITCH_REASON)
        self.assertEqual(session.switched_software_name, "Tally")

        next_state = self.advance(
            session,
            Intent.INFORM,
            "क्योंकि team उसी पर comfortable है.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        self.assertIn("comfortable", session.switched_software_reason)

    def test_business_closed_collects_feedback_then_alt_closes(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.OBJECT,
            "अब use नहीं करना.",
        )

        self.assertEqual(next_state, State.ESCALATE_CLOSURE_REASON)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "दुकान बंद हो गई.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        self.assertIn("दुकान बंद", session.business_closed_reason)

    def test_training_pending_collects_pincode_then_resumes_after_anything_else(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.COMPLAIN,
            "training pending है अभी.",
        )

        self.assertEqual(next_state, State.COLLECT_TRAINING_PINCODE)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "pin code 110011",
        )

        self.assertEqual(next_state, State.DETOUR_ANYTHING_ELSE)
        self.assertEqual(session.training_area_pincode, "110011")
        rendered = build_action_text(session)
        self.assertIn("24 से 48 घंटों", rendered)
        self.assertIn("क्या कोई और बात है", rendered)

        next_state = self.advance(
            session,
            Intent.DENY,
            "नहीं बस.",
        )

        self.assertEqual(next_state, State.VERIFY_WHATSAPP)

    def test_migration_delay_collects_timeline_then_resumes_after_anything_else(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "data migration चल रही है अभी.",
        )

        self.assertEqual(next_state, State.ASK_BILLING_START_TIMELINE)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "तीन दिन में complete हो जाएगी.",
        )

        self.assertEqual(next_state, State.DETOUR_ANYTHING_ELSE)
        rendered = build_action_text(session)
        self.assertIn("migration", rendered.lower())
        self.assertIn("क्या कोई और बात है", rendered)

        next_state = self.advance(
            session,
            Intent.DENY,
            "नहीं.",
        )

        self.assertEqual(next_state, State.VERIFY_WHATSAPP)

    def test_generic_complaint_collects_detail_and_routes_by_severity(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.COMPLAIN,
            "मैं satisfied नहीं हूँ.",
        )

        self.assertEqual(next_state, State.COLLECT_COMPLAINT_DETAIL)

        next_state = self.advance(
            session,
            Intent.COMPLAIN,
            "software crash हो रहा है.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        rendered = build_action_text(session)
        self.assertIn("24 घंटों के अंदर", rendered)

    def test_abusive_turn_immediately_routes_to_escalation_close(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.UNCLEAR,
            "बेकार call है, चुप रहो.",
        )

        self.assertEqual(next_state, State.WARM_CLOSING)
        rendered = build_action_text(session)
        self.assertIn("हमारी team आपसे जल्द contact करेगी", rendered)

    def test_embedded_query_resume_accepts_billing_started_without_reasking(self):
        session = CallSession(
            current_state=State.ANSWER_USER_QUERY,
            resume_state=State.ASK_BILLING_STATUS,
            query_resume_embedded=True,
            query_resolution_pending=True,
            last_user_query_type="clarification",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "हां setup हो गया है, billing start हो गई है.",
        )

        self.assertEqual(next_state, State.VERIFY_WHATSAPP)
        self.assertEqual(session.current_state, State.VERIFY_WHATSAPP)
        self.assertIsNone(session.resume_state)

    def test_business_detail_correction_stays_in_confirmation_cluster(self):
        session = CallSession(
            current_state=State.VERIFY_BUSINESS_DETAILS,
            crm_business_type="Medical",
            crm_business_trade="Retailer",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं, business type pharma है और trade wholesaler है.",
        )

        self.assertEqual(next_state, State.CONFIRM_BUSINESS_DETAILS)
        self.assertEqual(session.current_state, State.CONFIRM_BUSINESS_DETAILS)
        self.assertEqual(session.business_type, "Pharma")
        self.assertEqual(session.business_trade, "Wholesaler")
        self.assertIn("Pharma / Medical", build_action_text(session))

    def test_email_correction_requires_confirmation(self):
        session = CallSession(
            current_state=State.VERIFY_EMAIL,
            crm_email="old@example.com",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नई, मेरी email है utkarsh dot soni at the rate gmail dot com",
        )

        self.assertEqual(next_state, State.CONFIRM_EMAIL_CORRECTION)
        self.assertEqual(session.current_state, State.CONFIRM_EMAIL_CORRECTION)
        self.assertEqual(session.email, "utkarsh.soni@gmail.com")

    def test_split_email_correction_is_buffered_across_turns(self):
        session = CallSession(
            current_state=State.VERIFY_EMAIL,
            crm_email="old@example.com",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं, उत्कर्ष one two",
        )

        self.assertEqual(next_state, State.COLLECT_EMAIL_CORRECTION)
        self.assertEqual(session.current_state, State.COLLECT_EMAIL_CORRECTION)
        self.assertEqual(session.email_fragment_buffer, "नहीं, उत्कर्ष one two")

        next_state = self.advance(
            session,
            Intent.INFORM,
            "four at the rate Gmail dot com.",
        )

        self.assertEqual(next_state, State.CONFIRM_EMAIL_CORRECTION)
        self.assertEqual(session.current_state, State.CONFIRM_EMAIL_CORRECTION)
        self.assertEqual(session.email, "उत्कर्ष124@gmail.com")

        rendered = build_action_text(session)
        self.assertIn(
            "उत्कर्ष one two four at the rate gmail dot com",
            rendered,
        )

    def test_query_interrupts_and_resumes_same_workflow_step(self):
        session = CallSession(current_state=State.VERIFY_PINCODE, crm_pincode="110011")

        next_state = self.advance(
            session,
            Intent.ASK,
            "renewal का charge कितना होगा?",
        )

        self.assertEqual(next_state, State.ANSWER_USER_QUERY)
        self.assertEqual(session.current_state, State.ANSWER_USER_QUERY)
        self.assertEqual(session.resume_state, State.VERIFY_PINCODE)
        self.assertEqual(session.last_user_query_type, "pricing")
        self.assertEqual(session.dialog_mode, "HANDLE_QUERY")
        self.assertEqual(session.expected_slot, "query_resolution")

        resumed_state = self.advance(session, Intent.AFFIRM, "हाँ clear है")
        self.assertEqual(resumed_state, State.VERIFY_PINCODE)
        self.assertEqual(session.current_state, State.VERIFY_PINCODE)
        self.assertIsNone(session.resume_state)
        self.assertEqual(session.expected_slot, "pincode")

    def test_clarification_reasks_step_and_accepts_direct_answer(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.ASK,
            "billing से आपका क्या मतलब है?",
        )

        self.assertEqual(next_state, State.ANSWER_USER_QUERY)
        self.assertTrue(session.query_resume_embedded)
        self.assertEqual(session.resume_state, State.ASK_BILLING_STATUS)
        self.assertEqual(session.expected_slot, "billing_status")

        clarification_text = build_action_text(session)
        self.assertEqual(
            clarification_text,
            "जी, मेरा मतलब था — क्या आपने software में billing या invoice बनाना start किया है?",
        )

        resumed_state = self.advance(session, Intent.AFFIRM, "हाँ हो गई है.")
        self.assertEqual(resumed_state, State.VERIFY_WHATSAPP)
        self.assertEqual(session.current_state, State.VERIFY_WHATSAPP)
        self.assertFalse(session.query_resume_embedded)
        self.assertIsNone(session.resume_state)

    def test_busy_nudge_can_resume_same_business_step(self):
        session = CallSession(current_state=State.VERIFY_WHATSAPP)

        next_state = self.advance(
            session,
            Intent.DEFER,
            "अभी busy हूँ, बाद में call करना.",
        )

        self.assertEqual(next_state, State.BUSY_NUDGE)
        self.assertEqual(session.current_state, State.BUSY_NUDGE)

        next_state = self.advance(
            session,
            Intent.AFFIRM,
            "ठीक है, जल्दी पूछिए.",
        )

        self.assertEqual(next_state, State.VERIFY_WHATSAPP)
        self.assertEqual(session.current_state, State.VERIFY_WHATSAPP)

    def test_purchase_amount_refusal_uses_one_nudge_then_skips_forward(self):
        session = CallSession(current_state=State.ASK_PURCHASE_AMOUNT)

        first = self.advance(session, Intent.OBJECT, "मैं amount नहीं बता सकता.")
        self.assertEqual(first, State.ASK_PURCHASE_AMOUNT)
        self.assertIn("database clean", build_action_text(session))

        second = self.advance(session, Intent.OBJECT, "नहीं बता सकता.")
        self.assertEqual(second, State.SUPPORT_AND_REFERRAL)
        rendered = build_action_text(session)
        self.assertIn("मैं इसे skip कर देती हूँ", rendered)
        self.assertIn("Marg Help", rendered)

    def test_email_refusal_uses_two_nudges_then_skips_to_purchase_amount(self):
        session = CallSession(current_state=State.VERIFY_EMAIL, crm_email="")

        first = self.advance(session, Intent.OBJECT, "मैं email नहीं बता सकता.")
        self.assertEqual(first, State.COLLECT_EMAIL_CORRECTION)
        self.assertIn("records को update रखने", build_action_text(session))

        second = self.advance(session, Intent.OBJECT, "share नहीं करूँगा.")
        self.assertEqual(second, State.COLLECT_EMAIL_CORRECTION)
        self.assertIn("verification के लिए", build_action_text(session))

        third = self.advance(session, Intent.OBJECT, "skip करो.")
        self.assertEqual(third, State.ASK_PURCHASE_AMOUNT)
        self.assertIn("मैं इसे skip कर देती हूँ", build_action_text(session))

    def test_referral_decline_nudge_waits_once_then_closes(self):
        session = CallSession(current_state=State.SUPPORT_AND_REFERRAL)

        first = self.advance(session, Intent.DENY, "नहीं, कोई नहीं है.")
        self.assertEqual(first, State.REFERRAL_DECLINE_NUDGE)
        self.assertIn("future में कोई याद आए", build_action_text(session))

        second = self.advance(session, Intent.DENY, "नहीं.")
        self.assertEqual(second, State.WARM_CLOSING)
        self.assertIn("suitable time", build_action_text(session))

    def test_confirmed_alternate_number_does_not_use_no_problem_prefix(self):
        session = CallSession(
            current_state=State.CONFIRM_ALTERNATE_NUMBER,
            alternate_digit_buffer="8529152168",
            awaiting_alternate_confirmation=True,
        )

        next_state = self.advance(session, Intent.AFFIRM, "हाँ")

        self.assertEqual(next_state, State.VERIFY_PINCODE)
        rendered = build_action_text(session)
        self.assertIn("noted", rendered)
        self.assertNotIn("कोई बात नहीं", rendered)

    def test_missing_crm_pincode_renders_gentle_fresh_prompt(self):
        session = CallSession(current_state=State.VERIFY_PINCODE)

        rendered = build_action_text(session)

        self.assertIn("pin code available नहीं दिख रहा", rendered)
        self.assertIn("अपना area pin code बता दीजिए", rendered)

    def test_pincode_unknown_skips_forward_with_empathy(self):
        session = CallSession(current_state=State.VERIFY_PINCODE)

        next_state = self.advance(
            session,
            Intent.DENY,
            "जी मुझे नहीं पता.",
        )

        self.assertEqual(next_state, State.VERIFY_BUSINESS_DETAILS)
        rendered = build_action_text(session)
        self.assertIn("अगर अभी pin code याद नहीं है", rendered)

    def test_referral_clarification_prompt_reads_back_recorded_detail(self):
        session = CallSession(
            current_state=State.ANSWER_USER_QUERY,
            resume_state=State.CONFIRM_REFERRAL_NUMBER,
            last_user_query_type="clarification",
            last_clarification_kind="recorded_value",
            referral_name="राहुल",
            referral_digit_buffer="9876543210",
        )

        rendered = build_action_text(session)

        self.assertIn("मैंने नाम राहुल जी note किया है", rendered)
        self.assertIn("nine eight seven six five four three two one zero", rendered)
        self.assertTrue(rendered.endswith("क्या यही सही है?"))

    def test_confirm_referral_question_interrupts_instead_of_closing(self):
        session = CallSession(
            current_state=State.CONFIRM_REFERRAL_NUMBER,
            referral_digit_buffer="9876543210",
            awaiting_referral_confirmation=True,
            referral_name="राहुल",
        )
        transcript = "हां जी उसका नाम क्या लिखा आपने?"
        turn = parse_turn(session, Intent.ASK, transcript)

        next_state = resolve_next_state(session, turn, transcript)
        post_transition(session, turn, transcript, next_state)

        self.assertEqual(next_state, State.ANSWER_USER_QUERY)
        self.assertEqual(session.current_state, State.ANSWER_USER_QUERY)
        self.assertEqual(session.resume_state, State.CONFIRM_REFERRAL_NUMBER)
        self.assertEqual(session.last_user_query_type, "clarification")

    def test_referral_collection_status_reads_back_loaded_digits_and_name(self):
        session = CallSession(
            current_state=State.COLLECT_REFERRAL_NUMBER,
            referral_name="शौर्य",
            referral_digit_buffer="85291521",
        )

        next_state = self.advance(
            session,
            Intent.ASK,
            "कहाँ तक लिखा है आपने?",
        )

        self.assertEqual(next_state, State.COLLECT_REFERRAL_NUMBER)
        rendered = build_action_text(session)
        self.assertIn("शौर्य", rendered)
        self.assertIn("8 digit load", rendered)
        self.assertIn("eight five two nine one five two one", rendered)

    def test_referral_meta_reply_keeps_existing_name_and_reads_status(self):
        session = CallSession(
            current_state=State.COLLECT_REFERRAL_NUMBER,
            referral_name="शौर्य",
            referral_digit_buffer="85291521",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "बताया तो ma'am दस number.",
        )

        self.assertEqual(next_state, State.COLLECT_REFERRAL_NUMBER)
        self.assertEqual(session.referral_name, "शौर्य")
        rendered = build_action_text(session)
        self.assertIn("शौर्य", rendered)
        self.assertIn("बाकी 2 digit", rendered)

    def test_referral_name_clarification_answers_name_without_pollution(self):
        session = CallSession(
            current_state=State.COLLECT_REFERRAL_NUMBER,
            referral_name="शौर्य",
            referral_digit_buffer="85291521",
        )

        next_state = self.advance(
            session,
            Intent.ASK,
            "Referral वाले का नाम क्या लिखा है आपने?",
        )

        self.assertEqual(next_state, State.ANSWER_USER_QUERY)
        rendered = build_action_text(session)
        self.assertIn("नाम शौर्य जी", rendered)
        self.assertNotIn("दस जी", rendered)


class PromptRenderingTests(unittest.TestCase):
    def test_extract_digits_supports_hindi_numbers_and_repeat_markers(self):
        self.assertEqual(extract_digits("बाईस"), "22")
        self.assertEqual(extract_digits("पचासी"), "85")
        self.assertEqual(extract_digits("double zero one"), "001")
        self.assertEqual(extract_digits("triple three"), "333")

    def test_build_action_text_preserves_exact_rendered_dialogue(self):
        session = CallSession(
            current_state=State.VERIFY_PINCODE,
            crm_pincode="110011",
        )

        rendered = build_action_text(session)

        self.assertEqual(
            rendered,
            "आपका area pin code — one one zero zero one one — यही है?",
        )

    def test_build_action_text_renders_corrected_email_confirmation(self):
        session = CallSession(
            current_state=State.CONFIRM_EMAIL_CORRECTION,
            email="utkarsh.soni@gmail.com",
        )

        rendered = build_action_text(session)

        self.assertEqual(
            rendered,
            "तो आपकी email ID — utkarsh dot soni at the rate gmail dot com — यही है?",
        )

    def test_build_action_text_handles_missing_crm_email_gracefully(self):
        session = CallSession(current_state=State.VERIFY_EMAIL)

        rendered = build_action_text(session)

        self.assertIn("email ID available नहीं दिख रही", rendered)
        self.assertIn("अपनी email ID बता दीजिए", rendered)

    def test_build_action_text_groups_pharma_and_medical_labels(self):
        session = CallSession(
            current_state=State.VERIFY_BUSINESS_DETAILS,
            crm_business_type="medicine",
            crm_business_trade="Retailer",
        )

        rendered = build_action_text(session)

        self.assertIn("Pharma / Medical", rendered)
        self.assertNotIn("business type medicine", rendered)

    def test_build_action_text_renders_fixed_closing_exactly(self):
        session = CallSession(current_state=State.FIXED_CLOSING)

        rendered = build_action_text(session)

        self.assertEqual(
            rendered,
            "Marg में बने रहने के लिए आपका धन्यवाद. आपका दिन शुभ रहे.",
        )

    def test_build_action_text_renders_alternate_fixed_closing_when_requested(self):
        session = CallSession(
            current_state=State.FIXED_CLOSING,
            fixed_closing_variant="alternate",
        )

        rendered = build_action_text(session)

        self.assertEqual(
            rendered,
            "अपना समय देने के लिए धन्यवाद। आपका दिन शुभ रहे।",
        )


class DispositionTests(unittest.TestCase):
    def test_callback_disposition(self):
        session = CallSession(callback_requested=True)
        self.assertEqual(compute_disposition(session), ("Call Back", "Customer Busy"))

    def test_started_billing_disposition(self):
        session = CallSession(billing_started="STARTED")
        self.assertEqual(compute_disposition(session), ("Start Successfully", "Closed"))

    def test_invalid_registration_disposition(self):
        session = CallSession(states_visited=[State.INVALID_REGISTRATION])
        self.assertEqual(
            compute_disposition(session),
            ("Invalid Reg Details", "Wrong Details of Customer"),
        )


if __name__ == "__main__":
    unittest.main()
