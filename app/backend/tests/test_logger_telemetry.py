import unittest
from unittest.mock import patch
import sys
from pathlib import Path

from livekit.agents.llm.chat_context import ChatMessage

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from state_machine.session import CallSession
from state_machine.states import State
from utils.logger import TurnTelemetryTracker


class TurnTelemetryTrackerTests(unittest.TestCase):
    def test_tracker_emits_turn_record_with_transcripts_and_latency_fields(self):
        session = CallSession(
            current_state=State.ASK_BILLING_STATUS,
            customer_name="shaurya",
            primary_phone="8529152168",
        )
        tracker = TurnTelemetryTracker(session)
        writes = []

        with patch("utils.logger.append_jsonl_record", side_effect=lambda path, payload: writes.append((path, payload))):
            tracker.note_user_transcript(
                "हां बोलो",
                language="hi",
                state=State.CHECK_AVAILABILITY.value,
            )
            tracker.note_metric(
                {
                    "type": "llm_metrics",
                    "ttft": 0.18,
                    "duration": 0.92,
                    "prompt_tokens": 54,
                    "prompt_cached_tokens": 2,
                    "completion_tokens": 12,
                    "total_tokens": 66,
                }
            )
            tracker.note_metric(
                {
                    "type": "tts_metrics",
                    "ttfb": 0.33,
                    "duration": 1.24,
                }
            )
            tracker.note_conversation_item(
                ChatMessage(
                    role="assistant",
                    content=["जी धन्यवाद। क्या आपके software में billing start हो गई है?"],
                    metrics={
                        "llm_node_ttft": 0.18,
                        "tts_node_ttfb": 0.33,
                        "e2e_latency": 0.81,
                    },
                )
            )

        self.assertEqual(len(writes), 1)
        record = writes[0][1]
        self.assertEqual(record["user_transcript"], "हां बोलो")
        self.assertEqual(
            record["agent_transcript"],
            "जी धन्यवाद। क्या आपके software में billing start हो गई है?",
        )
        self.assertEqual(record["ttft_seconds"], 0.18)
        self.assertEqual(record["tttfb_seconds"], 0.33)
        self.assertEqual(record["latency_seconds"], 0.81)
        self.assertEqual(record["input_prompt_tokens"], 54)
        self.assertEqual(record["completion_tokens"], 12)
        self.assertEqual(record["state"], State.ASK_BILLING_STATUS.value)

    def test_tracker_summary_reports_averages(self):
        session = CallSession(current_state=State.VERIFY_WHATSAPP)
        tracker = TurnTelemetryTracker(session)

        with patch("utils.logger.append_jsonl_record"):
            tracker.note_user_transcript("हाँ है", language="hi", state=State.VERIFY_WHATSAPP.value)
            tracker.note_metric(
                {
                    "type": "llm_metrics",
                    "ttft": 0.2,
                    "duration": 0.8,
                    "prompt_tokens": 40,
                    "prompt_cached_tokens": 0,
                    "completion_tokens": 10,
                    "total_tokens": 50,
                }
            )
            tracker.note_metric({"type": "tts_metrics", "ttfb": 0.4, "duration": 1.0})
            tracker.note_conversation_item(
                ChatMessage(
                    role="assistant",
                    content=["जी, noted. क्या आप कोई alternate number भी देना चाहेंगे?"],
                    metrics={
                        "llm_node_ttft": 0.2,
                        "tts_node_ttfb": 0.4,
                        "e2e_latency": 0.9,
                    },
                )
            )

        summary = tracker.summary()
        self.assertEqual(summary["turn_count"], 1)
        self.assertEqual(summary["with_user_transcript"], 1)
        self.assertEqual(summary["with_agent_transcript"], 1)
        self.assertEqual(summary["total_prompt_tokens"], 40)
        self.assertEqual(summary["avg_ttft_seconds"], 0.2)
        self.assertEqual(summary["avg_tttfb_seconds"], 0.4)
        self.assertEqual(summary["avg_latency_seconds"], 0.9)
        self.assertTrue(summary["turn_metrics_path"].endswith("turn_metrics.jsonl"))


if __name__ == "__main__":
    unittest.main()
