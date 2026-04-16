import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dispositions.resolver import compute_disposition
from content_extraction.extractor_logic import build_render_context
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
            State.WARM_CLOSING,
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

    def test_callback_request_closes_immediately_and_mirrors_time(self):
        session = CallSession(current_state=State.CHECK_AVAILABILITY)

        next_state = resolve_next_state(
            session,
            Intent.REQUEST,
            "जी आप मुझे पांच minute बाद call करो.",
        )

        self.assertEqual(next_state, State.CALLBACK_CLOSING)
        self.assertTrue(session.callback_requested)
        self.assertEqual(session.callback_time_phrase, "पांच minute बाद")
        self.assertIn("पांच minute बाद", session.callback_closing_text)

    def test_callback_without_specific_time_asks_for_schedule_first(self):
        session = CallSession(current_state=State.CHECK_AVAILABILITY)

        next_state = self.advance(
            session,
            Intent.DEFER,
            "नहीं आप बाद में call करो.",
        )

        self.assertEqual(next_state, State.ASK_CALLBACK_TIME)
        self.assertEqual(session.current_state, State.ASK_CALLBACK_TIME)
        self.assertEqual(
            build_action_text(session),
            "जी बिल्कुल. किस time या किस दिन call करना convenient रहेगा?",
        )

        next_state = self.advance(
            session,
            Intent.INFORM,
            "कल सुबह 11 बजे.",
        )

        self.assertEqual(next_state, State.CALLBACK_CLOSING)
        self.assertIn("कल सुबह 11 बजे", session.callback_closing_text)

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

    def test_billing_setup_in_progress_moves_forward_with_guidance(self):
        session = CallSession(current_state=State.ASK_BILLING_STATUS)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं अभी setup ही कर रहा हूं.",
        )

        self.assertEqual(next_state, State.VERIFY_WHATSAPP)
        self.assertEqual(session.current_state, State.VERIFY_WHATSAPP)
        self.assertEqual(session.billing_started, "NOT_STARTED")
        self.assertEqual(session.billing_blocker_reason, "setup_in_progress")
        rendered = build_action_text(session)
        self.assertIn("setup पूरा होने", rendered)
        self.assertIn("WhatsApp", rendered)

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
