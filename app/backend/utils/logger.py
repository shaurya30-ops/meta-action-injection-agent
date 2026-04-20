import logging
import time

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
        for k, v in extra.items():
            parts.append(f"{k}={v}")
        logger.info(" | ".join(parts))
        return elapsed_ms

    def log_transition(self, prev_state, intent, next_state):
        logger.info(f"[TRANSITION] {prev_state} + {intent} -> {next_state}")

    def log_auto_chain(self, chain):
        logger.info(f"[AUTO-CHAIN] {' -> '.join(str(s) for s in chain)}")

    def log_fallback(self, state, count):
        logger.warning(f"[FALLBACK] State={state}, count={count}")

    def log_error(self, stage: str, error: Exception):
        logger.error(f"[{stage}] ERROR: {error}")


pipeline_logger = PipelineLogger()

import json
from pathlib import Path

# Setup metrics logger that writes ONLY to logs.log
metrics_logger = logging.getLogger("आकृति.metrics")
metrics_logger.setLevel(logging.INFO)
metrics_logger.propagate = False  # Don't pass up to terminal logger

logs_file_path = Path(__file__).resolve().parents[3] / "logs.log"
metrics_handler = logging.FileHandler(logs_file_path, encoding="utf-8")
metrics_handler.setFormatter(logging.Formatter("%(message)s"))
if not metrics_logger.handlers:
    metrics_logger.addHandler(metrics_handler)

def log_metric(agent_metric):
    """Log an AgentMetric to logs.log"""
    if hasattr(agent_metric, "dict"):
        data = agent_metric.dict()
    elif hasattr(agent_metric, "model_dump"):
        data = agent_metric.model_dump()
    else:
        data = vars(agent_metric)
        
    metrics_logger.info(json.dumps(data, ensure_ascii=False))


import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from langdetect import detect_langs, DetectorFactory

# Set seed for reproducible results
DetectorFactory.seed = 0

from livekit import agents

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

        user_messages = [msg for msg in chat_ctx.items if hasattr(msg, 'role') and msg.role == "user"]
        
        if not user_messages:
            return

        def detect_msg_lang(msg):
            content_str = ""
            if hasattr(msg, 'content'):
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
        last_lang = detect_msg_lang(last_user_msg)
        
        prev_lang = None
        if len(user_messages) >= 2:
            prev_lang = detect_msg_lang(user_messages[-2])

        if prev_lang is None:
            final_decision = last_lang
        else:
            final_decision = last_lang

        if final_decision == "hi":
            instruction = "\n\n[SYSTEM URGENT: The user just spoke HINDI. Please STOP speaking English. You MUST reply in Hinglish.]"
        else:
            instruction = "\n\n[SYSTEM URGENT: The user just spoke ENGLISH. Please STOP speaking Hinglish. You MUST reply in English.]"

        if hasattr(last_user_msg, 'content'):
            if isinstance(last_user_msg.content, str):
                if instruction not in last_user_msg.content:
                    last_user_msg.content += instruction
            elif isinstance(last_user_msg.content, list):
                for i in range(len(last_user_msg.content) - 1, -1, -1):
                    if isinstance(last_user_msg.content[i], str):
                        if instruction not in last_user_msg.content[i]:
                            last_user_msg.content[i] += instruction
                        break

    def _initialize_logger(self, session: Any | None = None):
        """Initialize the conversation logger only when needed."""
        if self._conversation_logger is not None and session is None:
            return self._conversation_logger

        if self._conversation_logger is not None and session is not None:
            for handler in self._conversation_logger.handlers[:]:
                self._conversation_logger.removeHandler(handler)
                handler.close()
            self._conversation_logger = None

        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        ist_timezone = ZoneInfo("Asia/Kolkata")
        timestamp = datetime.now(ist_timezone).strftime("%Y-%m-%d_%H-%M-%S")
        if session is not None:
            safe_name = _sanitize_for_filename(getattr(session, 'customer_name', 'unknown'))
            safe_phone = _sanitize_for_filename(getattr(session, 'primary_phone', 'unknown'))
            safe_client_name = _sanitize_for_filename(getattr(session, 'company_name', 'unknown'))
            self._log_filename = logs_dir / f"llm_conversation_{timestamp}_{safe_name}_{safe_client_name}_{safe_phone}.log"
        else:
            self._log_filename = logs_dir / f"llm_conversation_{timestamp}.log"

        conv_logger = logging.getLogger(f"llm_conversation_{id(self)}")
        conv_logger.setLevel(logging.INFO)
        conv_logger.propagate = False

        for handler in conv_logger.handlers[:]:
            conv_logger.removeHandler(handler)
            handler.close()

        conversation_handler = logging.FileHandler(self._log_filename, encoding="utf-8")
        conversation_handler.setLevel(logging.INFO)

        conversation_formatter = logging.Formatter('%(asctime)s - %(message)s')
        conversation_handler.setFormatter(conversation_formatter)

        conv_logger.addHandler(conversation_handler)
        self._conversation_logger = conv_logger

        logger.info(f"LLM conversation logs will be saved to: {self._log_filename}")
        return self._conversation_logger
    
    def initialize_logger(self, session: Any | None = None):
        return self._initialize_logger(session)

    def add_custom_transcript_item(self, role: str, text: str) -> None:
        line = f"{role.lower()}: {text}"
        if line not in self._transcript_list:
            self._transcript_list.append(line)
            if self._conversation_logger:
                self._conversation_logger.info(f"  [{role.upper()}]: {text} (Manual/Custom)")

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
        conv_logger.info("="*80)
        conv_logger.info(f"LLM REQUEST #{request_id}")
        conv_logger.info("="*80)
        
        try:
            logger.debug(f"Chat context type: {type(chat_ctx)}, has items: {hasattr(chat_ctx, 'items')}")
            conv_logger.info("(Raw = direct STT output, Corrected = Hinglish sent to LLM)")

            if hasattr(chat_ctx, 'items') and chat_ctx.items:
                for item in chat_ctx.items:
                    if hasattr(item, 'role') and hasattr(item, 'content'):
                        role = str(item.role).upper()
                        content = item.content

                        if isinstance(content, str):
                            plain_text = content
                        elif isinstance(content, list):
                            parts = []
                            for c in content:
                                if isinstance(c, str):
                                    parts.append(c)
                                elif hasattr(c, 'text'):
                                    parts.append(str(c.text))
                            plain_text = ' '.join(parts).strip()
                        else:
                            plain_text = str(content)                        
                       
                        if plain_text and role == "USER":
                            line = f"user: {plain_text}"
                            if line not in self._transcript_list:
                                self._transcript_list.append(line)                        
 
                        if plain_text:
                            conv_logger.info(f"  [{role}]: {plain_text}") 

                    elif hasattr(item, 'name') and hasattr(item, 'arguments'):
                        conv_logger.info(f"  [FUNCTION_CALL]: {item.name}({item.arguments})")
                    
                    elif hasattr(item, 'output'):
                        output_str = str(item.output)
                        conv_logger.info(f"  [FUNCTION_OUTPUT]: {output_str}")
            else:
                conv_logger.info("  (No messages in context)")
        except Exception as e:
            logger.error(f"Error logging chat context: {e}", exc_info=True)
            conv_logger.info(f"  (Error extracting messages: {e})")
        
        if tools:
            try:
                tool_names = []
                for t in tools:
                    if hasattr(t, 'function') and hasattr(t.function, 'name'):
                        tool_names.append(t.function.name)
                    elif hasattr(t, 'name'):
                        tool_names.append(t.name)
                    elif callable(t) and hasattr(t, '__name__'):
                        tool_names.append(t.__name__)
                    else:
                        tool_names.append(str(type(t).__name__))
                conv_logger.info(f"TOOLS: {tool_names}")
            except Exception as e:
                logger.error(f"Error logging tools: {e}")
                conv_logger.info(f"TOOLS: (error: {e})")
        
        conv_logger.info("-" * 80)
        
        original_stream = super().chat(
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options or getattr(agents, "DEFAULT_API_CONNECT_OPTIONS", None),
            **kwargs
        )
        
        conv_logger.info(f"[DEBUG] Stream created, wrapping for logging...")
        
        return LoggingLLMStreamWrapper(
            original_stream,
            request_id,
            conv_logger,
            llm_instance=self
        )        

    def log_session_start(self) -> None:
        if not is_logging_enabled():
            return
        if self._conversation_logger is None:
            return
        conv_logger = self._conversation_logger
        customer_name = getattr(self.session, 'customer_name', 'N/A') if self.session else 'N/A'
        primary_phone = getattr(self.session, 'primary_phone', 'N/A') if self.session else 'N/A'
        
        conv_logger.info("\n" + "="*80)
        conv_logger.info("NEW CONVERSATION SESSION")
        conv_logger.info(f"Room: {self._room_name or 'N/A'}")
        conv_logger.info(f"Session: customer={customer_name} phone={primary_phone}")
        conv_logger.info("="*80)

    def log_session_end(self, call_id: str) -> None:
        if not is_logging_enabled():
            return
        if self._conversation_logger is None:
            return
        conv_logger = self._conversation_logger
        conv_logger.info("\n" + "="*80)
        conv_logger.info("CONVERSATION SESSION ENDED")
        conv_logger.info(f"Call ID: {call_id}")
        conv_logger.info(f"Room: {self._room_name or 'N/A'}")
        conv_logger.info("="*80 + "\n")


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
                conv_logger = self._conversation_logger
                conv_logger.info(f"LLM RESPONSE #{self._request_id}:")
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
        except Exception as e:
            logger.error(f"Error in LLM stream wrapper: {e}", exc_info=True)
            self._log_final_response()
            raise
    
    def _log_final_response(self):
        if self._response_logged:
            return
        
        self._response_logged = True
        conv_logger = self._conversation_logger
        
        try:
            if self._accumulated_response:
                conv_logger.info(f"  [ASSISTANT]: {self._accumulated_response}")

                if self._llm_instance:
                    line = f"assistant: {self._accumulated_response}"
                    if line not in self._llm_instance._transcript_list:
                        self._llm_instance._transcript_list.append(line)

            elif self._logged_header:
                conv_logger.info(f"  [ASSISTANT]: (no text content)")
            
            if self._tool_calls:
                conv_logger.info("  TOOL CALLS:")
                for tool_call in self._tool_calls:
                    conv_logger.info(f"    - {tool_call.name}: {tool_call.arguments}")
            
            conv_logger.info("="*80 + "\n")
        except Exception as e:
            logger.error(f"Error logging final response: {e}")
    
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
