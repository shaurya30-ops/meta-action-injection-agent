from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from langdetect import DetectorFactory
from livekit import agents

# Set seed for reproducible results
DetectorFactory.seed = 0

ROOT_DIR = Path(__file__).resolve().parents[3]
RUNTIME_LOG_DIR = ROOT_DIR / "runtime_logs"
RAW_METRICS_PATH = RUNTIME_LOG_DIR / "raw_metrics.jsonl"
TURN_METRICS_PATH = RUNTIME_LOG_DIR / "turn_metrics.jsonl"
SESSION_USAGE_PATH = RUNTIME_LOG_DIR / "session_usage.jsonl"
CALL_SUMMARY_PATH = RUNTIME_LOG_DIR / "call_logs.jsonl"
CONVERSATION_LOG_DIR = RUNTIME_LOG_DIR / "conversations"

_FILE_LOCK = threading.Lock()

logger = logging.getLogger("आकृति.pipeline")


class PipelineLogger:
    """Structured logging for each pipeline stage with latency tracking."""

    def __init__(self):
        self._timers: dict[str, float] = {}

    def start(self, stage: str):
        self._timers[stage] = time.perf_counter()

    def end(self, stage: str, **extra):
        elapsed_ms = (time.perf_counter() - self._timers.pop(stage, time.perf_counter())) * 1000
        parts = [f"[{stage}] {elapsed_ms:.1f}ms"]
        for key, value in extra.items():
            parts.append(f"{key}={value}")
        logger.info(" | ".join(parts))
        return elapsed_ms

    def log_transition(self, prev_state, intent, next_state):
        logger.info(f"[TRANSITION] {prev_state} + {intent} -> {next_state}")

    def log_auto_chain(self, chain):
        logger.info(f"[AUTO-CHAIN] {' -> '.join(str(state) for state in chain)}")

    def log_fallback(self, state, count):
        logger.warning(f"[FALLBACK] State={state}, count={count}")

    def log_error(self, stage: str, error: Exception):
        logger.error(f"[{stage}] ERROR: {error}")


pipeline_logger = PipelineLogger()


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_for_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _serialize_for_json(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_for_json(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _serialize_for_json(value.model_dump(mode="json", exclude_none=True))
        except TypeError:
            return _serialize_for_json(value.model_dump(exclude_none=True))
    if hasattr(value, "dict"):
        return _serialize_for_json(value.dict())
    if hasattr(value, "__dict__"):
        return _serialize_for_json(vars(value))
    return str(value)


def append_jsonl_record(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent_dir(path)
    with _FILE_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _session_snapshot(session_data: Any | None) -> dict[str, Any]:
    if session_data is None:
        return {}
    current_state = getattr(session_data, "current_state", None)
    if hasattr(current_state, "value"):
        current_state = current_state.value
    return {
        "call_id": getattr(session_data, "call_id", ""),
        "customer_name": getattr(session_data, "customer_name", ""),
        "company_name": getattr(session_data, "company_name", ""),
        "firm_name": getattr(session_data, "firm_name", ""),
        "primary_phone": getattr(session_data, "primary_phone", ""),
        "current_state": current_state,
    }


def log_metric(agent_metric: Any, session_data: Any | None = None) -> None:
    """Append raw LiveKit metrics/events to an ignored JSONL artifact."""
    payload = {
        "timestamp": _utc_now_iso(),
        "session": _session_snapshot(session_data),
        "metric": _serialize_for_json(agent_metric),
    }
    append_jsonl_record(RAW_METRICS_PATH, payload)


def log_session_usage(usage: Any, session_data: Any | None = None) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "session": _session_snapshot(session_data),
        "usage": _serialize_for_json(usage),
    }
    append_jsonl_record(SESSION_USAGE_PATH, payload)


def _sanitize_for_filename(value: str) -> str:
    """Return a filesystem-safe version of the provided string."""
    safe_chars = []
    for char in str(value or "").strip():
        if char.isalnum():
            safe_chars.append(char)
        elif char in ("-", "_"):
            safe_chars.append(char)
    return "".join(safe_chars) or "user"


def clean_text_multilingual(text: str) -> str:
    text = re.sub(r'[^\w\s.,!?\'"]', "", str(text or ""), flags=re.UNICODE)
    text = text.replace("_", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def apply_post_llm_tts_text_processing(tts_instance: Any, timeline_logger: logging.Logger | None = None):
    if getattr(tts_instance, "_post_llm_cleaning_enabled", False):
        return tts_instance

    original_synthesize = tts_instance.synthesize
    original_stream = tts_instance.stream

    def synthesize_with_cleaning(text: str, **kwargs):
        cleaned = clean_text_multilingual(text)
        if not cleaned:
            cleaned = str(text or "").strip()
        return original_synthesize(cleaned, **kwargs)

    def stream_with_cleaning(**kwargs):
        stream = original_stream(**kwargs)
        original_push_text = stream.push_text

        def push_text_with_cleaning(token: str) -> None:
            cleaned = clean_text_multilingual(token)
            if cleaned:
                original_push_text(cleaned)

        stream.push_text = push_text_with_cleaning
        return stream

    tts_instance.synthesize = synthesize_with_cleaning
    tts_instance.stream = stream_with_cleaning
    setattr(tts_instance, "_post_llm_cleaning_enabled", True)
    if timeline_logger:
        timeline_logger.info("Enabled shared post-LLM multilingual text cleaning before TTS")
    return tts_instance


@dataclass
class PendingTurnMetrics:
    user_text: str = ""
    user_language: str | None = None
    user_state: str | None = None
    user_ts: str | None = None
    assistant_text: str = ""
    assistant_state: str | None = None
    assistant_ts: str | None = None
    assistant_interrupted: bool = False
    response_source: str = ""
    transcription_delay: float | None = None
    end_of_turn_delay: float | None = None
    on_user_turn_completed_delay: float | None = None
    llm_ttft: float | None = None
    llm_duration: float | None = None
    e2e_latency: float | None = None
    prompt_tokens: int = 0
    prompt_cached_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tts_ttfb: float | None = None
    tts_duration: float | None = None
    metric_types: list[str] = field(default_factory=list)


class TurnTelemetryTracker:
    """Collect lightweight per-turn telemetry without sending hot-path work through the LLM."""

    def __init__(self, session_data: Any | None = None):
        self.session_data = session_data
        self._pending = PendingTurnMetrics()
        self._turn_index = 0
        self._lock = threading.Lock()
        self._summary = {
            "turn_count": 0,
            "with_user_transcript": 0,
            "with_agent_transcript": 0,
            "llm_turns": 0,
            "tts_turns": 0,
            "latency_turns": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "sum_ttft": 0.0,
            "sum_tttfb": 0.0,
            "sum_latency": 0.0,
        }

    def bind_session(self, session_data: Any) -> None:
        self.session_data = session_data

    @staticmethod
    def _iso_from_timestamp(value: float | None) -> str | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()

    @staticmethod
    def _seconds_between(start_iso: str | None, end_iso: str | None) -> float | None:
        if not start_iso or not end_iso:
            return None
        try:
            start_dt = datetime.fromisoformat(start_iso)
            end_dt = datetime.fromisoformat(end_iso)
        except ValueError:
            return None
        return max((end_dt - start_dt).total_seconds(), 0.0)

    def _assistant_metrics_payload(self) -> dict[str, Any]:
        ttft = self._pending.llm_ttft
        tttfb = self._pending.tts_ttfb
        latency = self._pending.e2e_latency
        if latency is None:
            latency = self._seconds_between(self._pending.user_ts, self._pending.assistant_ts)
        return {
            "ttft_seconds": ttft,
            "tttfb_seconds": tttfb,
            "tts_ttfb_seconds": tttfb,
            "latency_seconds": latency,
            "llm_duration_seconds": self._pending.llm_duration,
            "tts_duration_seconds": self._pending.tts_duration,
            "transcription_delay_seconds": self._pending.transcription_delay,
            "end_of_turn_delay_seconds": self._pending.end_of_turn_delay,
            "on_user_turn_completed_delay_seconds": self._pending.on_user_turn_completed_delay,
        }

    def _build_turn_record(self) -> dict[str, Any]:
        metrics_payload = self._assistant_metrics_payload()
        current_state = getattr(getattr(self.session_data, "current_state", None), "value", None)
        resolved_state = self._pending.assistant_state or self._pending.user_state or current_state
        payload = {
            "timestamp": _utc_now_iso(),
            "turn_index": self._turn_index,
            "session": _session_snapshot(self.session_data),
            "state": resolved_state,
            "source": self._pending.response_source or "conversation_item",
            "user_transcript": self._pending.user_text or None,
            "user_language": self._pending.user_language,
            "agent_transcript": self._pending.assistant_text or None,
            "agent_interrupted": self._pending.assistant_interrupted or None,
            "input_prompt_tokens": self._pending.prompt_tokens or None,
            "prompt_cached_tokens": self._pending.prompt_cached_tokens or None,
            "completion_tokens": self._pending.completion_tokens or None,
            "total_tokens": self._pending.total_tokens or None,
            **metrics_payload,
            "user": {
                "transcript": self._pending.user_text or None,
                "language": self._pending.user_language,
                "state": self._pending.user_state,
                "timestamp": self._pending.user_ts,
            },
            "agent": {
                "transcript": self._pending.assistant_text or None,
                "state": self._pending.assistant_state,
                "timestamp": self._pending.assistant_ts,
                "interrupted": self._pending.assistant_interrupted,
            },
            "latency": {
                "ttft": metrics_payload["ttft_seconds"],
                "tttfb": metrics_payload["tttfb_seconds"],
                "tts_ttfb": metrics_payload["tts_ttfb_seconds"],
                "latency": metrics_payload["latency_seconds"],
                "llm_duration": metrics_payload["llm_duration_seconds"],
                "tts_duration": metrics_payload["tts_duration_seconds"],
                "transcription_delay": metrics_payload["transcription_delay_seconds"],
                "end_of_turn_delay": metrics_payload["end_of_turn_delay_seconds"],
                "on_user_turn_completed_delay": metrics_payload["on_user_turn_completed_delay_seconds"],
            },
            "usage": {
                "input_prompt_tokens": self._pending.prompt_tokens or None,
                "prompt_cached_tokens": self._pending.prompt_cached_tokens or None,
                "completion_tokens": self._pending.completion_tokens or None,
                "total_tokens": self._pending.total_tokens or None,
            },
            "metric_types": list(self._pending.metric_types),
        }
        return payload

    def _update_summary(self, record: dict[str, Any]) -> None:
        self._summary["turn_count"] += 1
        if record["user_transcript"]:
            self._summary["with_user_transcript"] += 1
        if record["agent_transcript"]:
            self._summary["with_agent_transcript"] += 1
        if record["input_prompt_tokens"] is not None:
            self._summary["llm_turns"] += 1
            self._summary["total_prompt_tokens"] += int(record["input_prompt_tokens"] or 0)
            self._summary["total_completion_tokens"] += int(record["completion_tokens"] or 0)
            self._summary["total_tokens"] += int(record["total_tokens"] or 0)
        if record["tttfb_seconds"] is not None:
            self._summary["tts_turns"] += 1
            self._summary["sum_tttfb"] += float(record["tttfb_seconds"])
        if record["ttft_seconds"] is not None:
            self._summary["sum_ttft"] += float(record["ttft_seconds"])
        if record["latency_seconds"] is not None:
            self._summary["latency_turns"] += 1
            self._summary["sum_latency"] += float(record["latency_seconds"])

    def _emit_locked(self) -> None:
        if not self._pending.user_text and not self._pending.assistant_text:
            return

        self._turn_index += 1
        record = self._build_turn_record()
        append_jsonl_record(TURN_METRICS_PATH, record)
        self._update_summary(record)
        self._pending = PendingTurnMetrics()

    def note_user_transcript(
        self,
        text: str,
        *,
        language: str | None = None,
        state: str | None = None,
    ) -> None:
        cleaned = str(text or "").strip()
        if not cleaned:
            return

        with self._lock:
            if self._pending.assistant_text:
                self._emit_locked()
            elif self._pending.user_text and self._pending.user_text != cleaned:
                self._emit_locked()

            self._pending.user_text = cleaned
            if language:
                self._pending.user_language = str(language)
            if state:
                self._pending.user_state = state
            self._pending.user_ts = _utc_now_iso()

    def note_metric(self, metric: Any) -> None:
        data = _serialize_for_json(metric)
        metric_type = data.get("type") if isinstance(data, dict) else None

        with self._lock:
            if metric_type:
                self._pending.metric_types.append(metric_type)

            if metric_type == "llm_metrics":
                self._pending.llm_ttft = data.get("ttft")
                self._pending.llm_duration = data.get("duration")
                self._pending.prompt_tokens += int(data.get("prompt_tokens") or 0)
                self._pending.prompt_cached_tokens += int(data.get("prompt_cached_tokens") or 0)
                self._pending.completion_tokens += int(data.get("completion_tokens") or 0)
                self._pending.total_tokens += int(data.get("total_tokens") or 0)
            elif metric_type == "tts_metrics":
                self._pending.tts_ttfb = data.get("ttfb")
                self._pending.tts_duration = data.get("duration")
            elif metric_type == "eou_metrics":
                self._pending.transcription_delay = data.get("transcription_delay")
                self._pending.end_of_turn_delay = data.get("end_of_utterance_delay")
                self._pending.on_user_turn_completed_delay = data.get("on_user_turn_completed_delay")

    def note_usage_update(self, usage: Any) -> None:
        log_session_usage(usage, self.session_data)

    def note_conversation_item(self, item: Any) -> None:
        role = getattr(item, "role", None)
        text = getattr(item, "text_content", None)
        metrics = _serialize_for_json(getattr(item, "metrics", {}) or {})
        current_state = getattr(getattr(self.session_data, "current_state", None), "value", None)

        with self._lock:
            if role == "user":
                if text:
                    self._pending.user_text = text
                if current_state:
                    self._pending.user_state = current_state
                if getattr(item, "created_at", None):
                    self._pending.user_ts = datetime.fromtimestamp(item.created_at, tz=timezone.utc).isoformat()
                self._pending.user_language = getattr(item, "extra", {}).get("language") or self._pending.user_language
                self._pending.transcription_delay = metrics.get("transcription_delay", self._pending.transcription_delay)
                self._pending.end_of_turn_delay = metrics.get("end_of_turn_delay", self._pending.end_of_turn_delay)
                self._pending.on_user_turn_completed_delay = metrics.get(
                    "on_user_turn_completed_delay",
                    self._pending.on_user_turn_completed_delay,
                )
                return

            if role != "assistant":
                return

            self._pending.assistant_text = text or ""
            self._pending.assistant_state = current_state
            self._pending.assistant_ts = self._iso_from_timestamp(getattr(item, "created_at", time.time()))
            self._pending.assistant_interrupted = bool(getattr(item, "interrupted", False))
            self._pending.response_source = "conversation_item"
            self._pending.llm_ttft = metrics.get("llm_node_ttft", self._pending.llm_ttft)
            self._pending.tts_ttfb = metrics.get("tts_node_ttfb", self._pending.tts_ttfb)
            self._pending.e2e_latency = metrics.get("e2e_latency", self._pending.e2e_latency)
            self._emit_locked()

    def finalize_pending_turn(self) -> None:
        with self._lock:
            self._emit_locked()

    def summary(self) -> dict[str, Any]:
        with self._lock:
            turn_count = self._summary["turn_count"]
            llm_turns = self._summary["llm_turns"]
            tts_turns = self._summary["tts_turns"]
            latency_turns = self._summary["latency_turns"]
            return {
                **self._summary,
                "avg_ttft_seconds": (self._summary["sum_ttft"] / llm_turns) if llm_turns else None,
                "avg_tttfb_seconds": (self._summary["sum_tttfb"] / tts_turns) if tts_turns else None,
                "avg_latency_seconds": (self._summary["sum_latency"] / latency_turns) if latency_turns else None,
                "pending_turn_open": bool(self._pending.user_text or self._pending.assistant_text),
                "turn_metrics_path": str(TURN_METRICS_PATH),
                "session_usage_path": str(SESSION_USAGE_PATH),
                "raw_metrics_path": str(RAW_METRICS_PATH),
                "conversation_log_dir": str(CONVERSATION_LOG_DIR),
            }


class LoggingLLMWrapperMixin:
    """Mixin wrapper around LLM to log all requests and responses."""

    def __init__(self, assistant: Any = None, client_name: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transcript_list = []
        self._request_counter = 0
        self.session: Any | None = None
        self._conversation_logger: logging.Logger | None = None
        self._log_filename: Path | None = None
        self._room_name: str | None = None

        self.assistant = assistant
        self.client_name = client_name

    def _apply_language_enforcement(self, chat_ctx):
        if self.client_name not in ["twiddles", "narayana"]:
            return

        if not self.assistant or not chat_ctx.items:
            return

        user_messages = [msg for msg in chat_ctx.items if hasattr(msg, "role") and msg.role == "user"]
        if not user_messages:
            return

        def detect_msg_lang(msg):
            content_str = ""
            if hasattr(msg, "content"):
                if isinstance(msg.content, str):
                    content_str = msg.content
                elif isinstance(msg.content, list):
                    for item in reversed(msg.content):
                        if isinstance(item, str):
                            content_str = item
                            break

            has_hindi = any("\u0900" <= ch <= "\u097F" for ch in content_str)
            return "hi" if has_hindi else "en"

        last_user_msg = user_messages[-1]
        final_decision = detect_msg_lang(last_user_msg)

        if final_decision == "hi":
            instruction = "\n\n[SYSTEM URGENT: The user just spoke HINDI. Please STOP speaking English. You MUST reply in Hinglish.]"
        else:
            instruction = "\n\n[SYSTEM URGENT: The user just spoke ENGLISH. Please STOP speaking Hinglish. You MUST reply in English.]"

        if hasattr(last_user_msg, "content"):
            if isinstance(last_user_msg.content, str):
                if instruction not in last_user_msg.content:
                    last_user_msg.content += instruction
            elif isinstance(last_user_msg.content, list):
                for index in range(len(last_user_msg.content) - 1, -1, -1):
                    if isinstance(last_user_msg.content[index], str):
                        if instruction not in last_user_msg.content[index]:
                            last_user_msg.content[index] += instruction
                        break

    def _initialize_logger(self, session: Any | None = None):
        if self._conversation_logger is not None and session is None:
            return self._conversation_logger

        if self._conversation_logger is not None and session is not None:
            for handler in self._conversation_logger.handlers[:]:
                self._conversation_logger.removeHandler(handler)
                handler.close()
            self._conversation_logger = None

        CONVERSATION_LOG_DIR.mkdir(parents=True, exist_ok=True)

        ist_timezone = ZoneInfo("Asia/Kolkata")
        timestamp = datetime.now(ist_timezone).strftime("%Y-%m-%d_%H-%M-%S")
        if session is not None:
            safe_name = _sanitize_for_filename(getattr(session, "customer_name", "unknown"))
            safe_phone = _sanitize_for_filename(getattr(session, "primary_phone", "unknown"))
            safe_company = _sanitize_for_filename(getattr(session, "company_name", "unknown"))
            self._log_filename = CONVERSATION_LOG_DIR / (
                f"llm_conversation_{timestamp}_{safe_name}_{safe_company}_{safe_phone}.log"
            )
        else:
            self._log_filename = CONVERSATION_LOG_DIR / f"llm_conversation_{timestamp}.log"

        conv_logger = logging.getLogger(f"llm_conversation_{id(self)}")
        conv_logger.setLevel(logging.INFO)
        conv_logger.propagate = False

        for handler in conv_logger.handlers[:]:
            conv_logger.removeHandler(handler)
            handler.close()

        conversation_handler = logging.FileHandler(self._log_filename, encoding="utf-8")
        conversation_handler.setLevel(logging.INFO)
        conversation_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

        conv_logger.addHandler(conversation_handler)
        self._conversation_logger = conv_logger

        logger.info("LLM conversation logs will be saved to: %s", self._log_filename)
        return self._conversation_logger

    def initialize_logger(self, session: Any | None = None):
        return self._initialize_logger(session)

    def add_custom_transcript_item(self, role: str, text: str) -> None:
        line = f"{role.lower()}: {text}"
        if line not in self._transcript_list:
            self._transcript_list.append(line)
            if self._conversation_logger:
                self._conversation_logger.info("  [%s]: %s (Manual/Custom)", role.upper(), text)

    def get_clean_transcript(self) -> str:
        return "\n".join(self._transcript_list)

    def set_session_and_room(self, session: Any, room_name: str) -> None:
        self.session = session
        self._room_name = room_name
        self._initialize_logger(session)
        self.log_session_start()

    def chat(self, *, chat_ctx, tools=None, conn_options=None, **kwargs):
        self._apply_language_enforcement(chat_ctx)
        self._request_counter += 1
        request_id = self._request_counter

        if self._conversation_logger is None:
            self.initialize_logger()

        conv_logger = self._conversation_logger
        conv_logger.info("=" * 80)
        conv_logger.info("LLM REQUEST #%s", request_id)
        conv_logger.info("=" * 80)

        try:
            conv_logger.info("(Raw = direct STT output, Corrected = Hinglish sent to LLM)")
            if hasattr(chat_ctx, "items") and chat_ctx.items:
                for item in chat_ctx.items:
                    if hasattr(item, "role") and hasattr(item, "content"):
                        role = str(item.role).upper()
                        content = item.content

                        if isinstance(content, str):
                            plain_text = content
                        elif isinstance(content, list):
                            parts = []
                            for value in content:
                                if isinstance(value, str):
                                    parts.append(value)
                                elif hasattr(value, "text"):
                                    parts.append(str(value.text))
                            plain_text = " ".join(parts).strip()
                        else:
                            plain_text = str(content)

                        if plain_text and role == "USER":
                            line = f"user: {plain_text}"
                            if line not in self._transcript_list:
                                self._transcript_list.append(line)

                        if plain_text:
                            conv_logger.info("  [%s]: %s", role, plain_text)
                    elif hasattr(item, "name") and hasattr(item, "arguments"):
                        conv_logger.info("  [FUNCTION_CALL]: %s(%s)", item.name, item.arguments)
                    elif hasattr(item, "output"):
                        conv_logger.info("  [FUNCTION_OUTPUT]: %s", item.output)
            else:
                conv_logger.info("  (No messages in context)")
        except Exception as exc:
            logger.error("Error logging chat context: %s", exc, exc_info=True)
            conv_logger.info("  (Error extracting messages: %s)", exc)

        if tools:
            try:
                tool_names = []
                for tool in tools:
                    if hasattr(tool, "function") and hasattr(tool.function, "name"):
                        tool_names.append(tool.function.name)
                    elif hasattr(tool, "name"):
                        tool_names.append(tool.name)
                    elif callable(tool) and hasattr(tool, "__name__"):
                        tool_names.append(tool.__name__)
                    else:
                        tool_names.append(str(type(tool).__name__))
                conv_logger.info("TOOLS: %s", tool_names)
            except Exception as exc:
                logger.error("Error logging tools: %s", exc)
                conv_logger.info("TOOLS: (error: %s)", exc)

        conv_logger.info("-" * 80)

        original_stream = super().chat(
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options or getattr(agents, "DEFAULT_API_CONNECT_OPTIONS", None),
            **kwargs,
        )

        conv_logger.info("[DEBUG] Stream created, wrapping for logging...")
        return LoggingLLMStreamWrapper(
            original_stream,
            request_id,
            conv_logger,
            llm_instance=self,
        )

    def log_session_start(self) -> None:
        if not is_logging_enabled() or self._conversation_logger is None:
            return
        conv_logger = self._conversation_logger
        customer_name = getattr(self.session, "customer_name", "N/A") if self.session else "N/A"
        primary_phone = getattr(self.session, "primary_phone", "N/A") if self.session else "N/A"

        conv_logger.info("\n" + "=" * 80)
        conv_logger.info("NEW CONVERSATION SESSION")
        conv_logger.info("Room: %s", self._room_name or "N/A")
        conv_logger.info("Session: customer=%s phone=%s", customer_name, primary_phone)
        conv_logger.info("=" * 80)

    def log_session_end(self, call_id: str) -> None:
        if not is_logging_enabled() or self._conversation_logger is None:
            return
        conv_logger = self._conversation_logger
        conv_logger.info("\n" + "=" * 80)
        conv_logger.info("CONVERSATION SESSION ENDED")
        conv_logger.info("Call ID: %s", call_id)
        conv_logger.info("Room: %s", self._room_name or "N/A")
        conv_logger.info("=" * 80 + "\n")


class LoggingLLMStreamWrapper:
    """Wrapper around LLMStream to log responses as they come in."""

    def __init__(self, original_stream, request_id, conversation_logger=None, llm_instance=None):
        self._original_stream = original_stream
        self._request_id = request_id
        self._accumulated_response = ""
        self._tool_calls = []
        self._logged_header = False
        self._response_logged = False
        self._conversation_logger = conversation_logger
        self._llm_instance = llm_instance

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk = await self._original_stream.__anext__()

            if not self._logged_header:
                self._conversation_logger.info("LLM RESPONSE #%s:", self._request_id)
                self._logged_header = True

            if chunk.delta:
                if chunk.delta.content:
                    self._accumulated_response += chunk.delta.content
                if chunk.delta.tool_calls:
                    self._tool_calls.extend(chunk.delta.tool_calls)

            return chunk
        except StopAsyncIteration:
            self._log_final_response()
            raise
        except Exception as exc:
            logger.error("Error in LLM stream wrapper: %s", exc, exc_info=True)
            self._log_final_response()
            raise

    def _log_final_response(self):
        if self._response_logged:
            return

        self._response_logged = True
        conv_logger = self._conversation_logger

        try:
            if self._accumulated_response:
                conv_logger.info("  [ASSISTANT]: %s", self._accumulated_response)
                if self._llm_instance:
                    line = f"assistant: {self._accumulated_response}"
                    if line not in self._llm_instance._transcript_list:
                        self._llm_instance._transcript_list.append(line)
            elif self._logged_header:
                conv_logger.info("  [ASSISTANT]: (no text content)")

            if self._tool_calls:
                conv_logger.info("  TOOL CALLS:")
                for tool_call in self._tool_calls:
                    conv_logger.info("    - %s: %s", tool_call.name, tool_call.arguments)

            conv_logger.info("=" * 80 + "\n")
        except Exception as exc:
            logger.error("Error logging final response: %s", exc)

    async def aclose(self):
        self._log_final_response()
        if hasattr(self._original_stream, "aclose"):
            await self._original_stream.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    def __del__(self):
        if not self._response_logged and (self._accumulated_response or self._tool_calls):
            self._log_final_response()

    @property
    def chat_ctx(self):
        return self._original_stream.chat_ctx

    @property
    def tools(self):
        return self._original_stream.tools


def create_llm(llm_class, assistant: Any = None, client_name: str = None, **kwargs):
    logger.info("LLM conversation logging ENABLED")

    class DynamicLoggingLLM(LoggingLLMWrapperMixin, llm_class):
        pass

    return DynamicLoggingLLM(assistant=assistant, client_name=client_name, **kwargs)


def create_llm_with_para(llm_class, assistant: Any = None, client_name: str = None, **kwargs):
    logger.info("LLM conversation logging ENABLED")

    class DynamicLoggingLLM(LoggingLLMWrapperMixin, llm_class):
        pass

    return DynamicLoggingLLM(assistant=assistant, client_name=client_name, **kwargs)


def is_logging_enabled() -> bool:
    return os.getenv("LLM_LOG_CONVERSATION", "false").lower() in ("true", "1", "yes")
