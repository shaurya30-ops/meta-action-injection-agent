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
from state_machine.transitions import TRANSITIONS
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

    def test_verification_chain_keeps_required_order(self):
        self.assertEqual(
            TRANSITIONS[(State.VERIFY_WHATSAPP, Intent.DENY)],
            State.COLLECT_WHATSAPP_NUMBER,
        )
        self.assertEqual(
            TRANSITIONS[(State.ASK_ALTERNATE_NUMBER, Intent.DENY)],
            State.VERIFY_PINCODE,
        )
        self.assertEqual(
            TRANSITIONS[(State.VERIFY_EMAIL, Intent.AFFIRM)],
            State.ASK_PURCHASE_AMOUNT,
        )
        self.assertEqual(
            TRANSITIONS[(State.SUPPORT_AND_REFERRAL, Intent.DENY)],
            State.WARM_CLOSING,
        )


class ResolverFlowTests(unittest.TestCase):
    def advance(self, session: CallSession, intent: Intent, transcript: str) -> State:
        next_state = resolve_next_state(session, intent, transcript)
        post_transition(session, intent, transcript, next_state)
        return next_state

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

    def test_whatsapp_buffer_confirms_only_after_ten_digits(self):
        session = CallSession(current_state=State.COLLECT_WHATSAPP_NUMBER)

        self.advance(session, Intent.INFORM, "one two three four")
        self.assertEqual(session.current_state, State.COLLECT_WHATSAPP_NUMBER)
        self.assertEqual(session.whatsapp_digit_buffer, "1234")
        self.assertFalse(session.awaiting_whatsapp_confirmation)

        self.advance(session, Intent.INFORM, "five six seven eight")
        self.assertEqual(session.whatsapp_digit_buffer, "12345678")
        self.assertFalse(session.awaiting_whatsapp_confirmation)

        self.advance(session, Intent.INFORM, "nine zero")
        self.assertEqual(session.current_state, State.COLLECT_WHATSAPP_NUMBER)
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

    def test_direct_alternate_digits_are_captured_on_ask_state(self):
        session = CallSession(current_state=State.ASK_ALTERNATE_NUMBER)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "alternate number 9876543210",
        )

        self.assertEqual(next_state, State.COLLECT_ALTERNATE_NUMBER)
        self.assertEqual(session.current_state, State.COLLECT_ALTERNATE_NUMBER)
        self.assertEqual(session.alternate_digit_buffer, "9876543210")
        self.assertTrue(session.awaiting_alternate_confirmation)

    def test_verify_pincode_inline_digits_preload_confirmation(self):
        session = CallSession(current_state=State.VERIFY_PINCODE)

        next_state = self.advance(
            session,
            Intent.INFORM,
            "नहीं दूसरा pin code है one one zero zero one two.",
        )

        self.assertEqual(next_state, State.COLLECT_PINCODE)
        self.assertEqual(session.current_state, State.COLLECT_PINCODE)
        self.assertEqual(session.pincode_digit_buffer, "110012")
        self.assertTrue(session.awaiting_pincode_confirmation)


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
