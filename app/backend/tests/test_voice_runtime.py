import asyncio
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from intent_classifier.classifier import IntentClassifier
from state_machine.intents import Intent
from state_machine.session import CallSession
from state_machine.states import State
from utils.stable_sarvam import NoReuseConnectionPool, StableSarvamTTS
from utils.voice_session import (
    build_session_connect_options,
    build_session_runtime_options,
    build_turn_handling_options,
)

try:
    from agent import prepare_direct_action
    AGENT_IMPORT_ERROR = None
except Exception as exc:
    prepare_direct_action = None
    AGENT_IMPORT_ERROR = exc


class IntentClassifierDeterministicTests(unittest.TestCase):
    def test_short_affirm_uses_deterministic_matcher(self):
        classifier = IntentClassifier()

        result = asyncio.run(classifier.classify("हाँ जी हो रही है?"))

        self.assertEqual(result, Intent.AFFIRM)

    def test_numeric_payload_routes_to_inform(self):
        classifier = IntentClassifier()

        result = asyncio.run(classifier.classify("9876543210"))

        self.assertEqual(result, Intent.INFORM)

    def test_clarification_question_routes_to_ask(self):
        classifier = IntentClassifier()

        result = asyncio.run(classifier.classify("हाँ जी उसका नाम क्या लिखा आपने?"))

        self.assertEqual(result, Intent.ASK)

    def test_warmup_is_a_noop(self):
        classifier = IntentClassifier()

        self.assertIsNone(classifier.warmup())


class VoiceSessionConfigTests(unittest.TestCase):
    def test_turn_handling_prefers_vad_and_short_interruptions(self):
        turn_handling = build_turn_handling_options()

        self.assertEqual(turn_handling["turn_detection"], "vad")
        self.assertEqual(turn_handling["endpointing"]["mode"], "fixed")
        self.assertEqual(turn_handling["endpointing"]["min_delay"], 0.45)
        self.assertEqual(turn_handling["endpointing"]["max_delay"], 1.8)
        self.assertEqual(turn_handling["interruption"]["mode"], "vad")
        self.assertFalse(turn_handling["interruption"]["discard_audio_if_uninterruptible"])
        self.assertEqual(turn_handling["interruption"]["min_duration"], 0.25)

    def test_runtime_options_disable_preemptive_generation(self):
        runtime_options = build_session_runtime_options()

        self.assertFalse(runtime_options["preemptive_generation"])
        self.assertEqual(runtime_options["aec_warmup_duration"], 1.0)

    def test_session_connect_options_harden_tts_runtime(self):
        conn_options = build_session_connect_options()

        self.assertIsNotNone(conn_options.tts_conn_options.timeout)
        self.assertGreaterEqual(conn_options.tts_conn_options.max_retry, 0)


class StableSarvamRuntimeTests(unittest.TestCase):
    def test_no_reuse_pool_drops_returned_connection(self):
        created: list[object] = []

        async def connect_cb(_timeout: float) -> object:
            conn = object()
            created.append(conn)
            return conn

        pool = NoReuseConnectionPool[object](connect_cb=connect_cb)

        async def run() -> tuple[object, object]:
            first = await pool.get(timeout=1.0)
            pool.put(first)
            second = await pool.get(timeout=1.0)
            return first, second

        first, second = asyncio.run(run())

        self.assertIsNot(first, second)
        self.assertEqual(len(created), 2)

    def test_connect_ws_enables_heartbeat(self):
        captured: dict[str, object] = {}

        class FakeSession:
            async def ws_connect(self, url, **kwargs):
                captured["url"] = url
                captured.update(kwargs)
                return "ws"

        tts = StableSarvamTTS.__new__(StableSarvamTTS)
        tts._opts = SimpleNamespace(
            api_key="test-key",
            ws_url="wss://example.test/ws",
            model="bulbul:v3",
            send_completion_event=True,
        )
        tts._ensure_session = lambda: FakeSession()

        ws = asyncio.run(tts._connect_ws(timeout=1.0))

        self.assertEqual(ws, "ws")
        self.assertEqual(captured["heartbeat"], 10.0)
        self.assertTrue(captured["autoping"])
        self.assertTrue(captured["autoclose"])


@unittest.skipIf(
    prepare_direct_action is None,
    f"agent import unavailable in this environment: {AGENT_IMPORT_ERROR}",
)
class AgentRenderRuntimeTests(unittest.TestCase):
    def test_prepare_direct_action_keeps_callback_closing_renderable_after_auto_chain(self):
        session = CallSession(
            current_state=State.CALLBACK_CLOSING,
            callback_closing_text="जी बिल्कुल, मैं आपको शाम पाँच बजे call करती हूँ।",
        )

        combined_action, render_state = prepare_direct_action(session)

        self.assertEqual(render_state, State.FIXED_CLOSING)
        self.assertEqual(session.current_state, State.END)
        self.assertIn("शाम पाँच बजे", combined_action)
        self.assertIn("Marg में बने रहने के लिए आपका धन्यवाद", combined_action)


if __name__ == "__main__":
    unittest.main()
