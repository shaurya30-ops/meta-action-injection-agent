import asyncio
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import config
from intent_classifier.classifier import IntentClassifier
from state_machine.intents import Intent
from utils.stable_sarvam import NoReuseConnectionPool, StableSarvamTTS
from utils.voice_session import (
    build_session_connect_options,
    build_session_runtime_options,
    build_turn_handling_options,
)


class IntentClassifierFastPathTests(unittest.TestCase):
    @patch("intent_classifier.classifier._get_global_pool")
    @patch("intent_classifier.classifier.asyncio.get_running_loop")
    def test_short_affirm_uses_fast_path(
        self,
        mocked_get_running_loop,
        _mocked_get_global_pool,
    ):
        classifier = IntentClassifier()

        result = asyncio.run(classifier.classify("हां जी हो रही है?"))

        self.assertEqual(result, Intent.AFFIRM)
        mocked_get_running_loop.assert_not_called()

    @patch("intent_classifier.classifier._get_global_pool")
    @patch("intent_classifier.classifier.asyncio.get_running_loop")
    def test_numeric_payload_uses_fast_path(
        self,
        mocked_get_running_loop,
        _mocked_get_global_pool,
    ):
        classifier = IntentClassifier()

        result = asyncio.run(classifier.classify("9876543210"))

        self.assertEqual(result, Intent.INFORM)
        mocked_get_running_loop.assert_not_called()


class VoiceSessionConfigTests(unittest.TestCase):
    def test_turn_handling_prefers_vad_and_short_interruptions(self):
        turn_handling = build_turn_handling_options()

        self.assertEqual(turn_handling["turn_detection"], "vad")
        self.assertEqual(turn_handling["endpointing"]["mode"], "fixed")
        self.assertEqual(turn_handling["interruption"]["mode"], "vad")
        self.assertFalse(turn_handling["interruption"]["discard_audio_if_uninterruptible"])
        self.assertEqual(turn_handling["interruption"]["min_duration"], 0.25)
        self.assertGreaterEqual(turn_handling["endpointing"]["min_delay"], 0.45)

    def test_runtime_options_disable_preemptive_generation(self):
        runtime_options = build_session_runtime_options()

        self.assertFalse(runtime_options["preemptive_generation"])
        self.assertEqual(runtime_options["aec_warmup_duration"], 1.0)
        self.assertGreater(config.CLASSIFIER_TIMEOUT_SECONDS, 2.0)

    def test_session_connect_options_harden_tts_runtime(self):
        conn_options = build_session_connect_options()

        self.assertEqual(conn_options.tts_conn_options.timeout, config.TTS_TIMEOUT_SECONDS)
        self.assertEqual(conn_options.tts_conn_options.max_retry, config.TTS_MAX_RETRIES)
        self.assertEqual(
            conn_options.max_unrecoverable_errors,
            config.MEDIA_MAX_UNRECOVERABLE_ERRORS,
        )


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
        self.assertEqual(captured["heartbeat"], config.SARVAM_WS_HEARTBEAT_SECONDS)
        self.assertTrue(captured["autoping"])
        self.assertTrue(captured["autoclose"])


if __name__ == "__main__":
    unittest.main()
