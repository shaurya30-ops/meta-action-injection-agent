"""
आकृति Voice Agent — LiveKit Entrypoint
Marg ई आर पी Solutions Welcome Call

Architecture: Deterministic State Machine + LLM as Rendering Engine
Pipeline: Deepgram STT → Qwen2.5-0.5B (Intent) → State Machine → gpt-5.4-nano → Sarvam TTS
"""

import os
from dotenv import load_dotenv
load_dotenv()

import sys
import json
import asyncio
import contextlib
import logging
import re
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any, AsyncIterable

import livekit.rtc as rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, TurnHandlingOptions, ModelSettings
from livekit.agents import llm as lk_llm
from livekit.plugins import deepgram, openai, sarvam, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Ensure backend root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_machine.session import CallSession
from state_machine.states import State
from state_machine.intents import Intent
from state_machine.actions import ACTION_MAP
from state_machine.transitions import AUTO_TRANSITIONS
from state_machine.resolver import resolve_next_state, post_transition, execute_auto_chain
from state_machine.programmatic import resolve_programmatic
from intent_classifier.classifier import IntentClassifier
from prompts.persona import आकृति_SYSTEM_PROMPT
from prompts.payload_builder import build_llm_payload
from prompts.template_renderer import render_template
from content_extraction.extractor_logic import build_render_context
from dispositions.resolver import compute_disposition
from dispositions.logger import log_call
from utils.logger import pipeline_logger, log_metric
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("आकृति.agent")
CALL_SESSION_FIELDS = {field.name for field in fields(CallSession)}
CRM_FIELD_ALIASES = {
    "name": "customer_name",
    "customer name": "customer_name",
    "company name": "company_name",
    "firm name": "firm_name",
    "phone number": "primary_phone",
    "mobile number": "primary_phone",
    "primary phone": "primary_phone",
    "email id": "crm_email",
    "email": "crm_email",
    "pin code": "crm_pincode",
    "pincode": "crm_pincode",
    "business type": "crm_business_type",
    "business trade": "crm_business_trade",
}


def _normalize_metadata_key(key: str) -> str:
    return " ".join(str(key).replace("_", " ").replace("-", " ").split()).strip().lower()


def _metadata_excerpt(raw: Any, limit: int = 200) -> str:
    text = str(raw).strip()
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def _parse_metadata_value(raw_value: str) -> Any:
    value = raw_value.strip().rstrip(",")
    if not value:
        return ""

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None

    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)

    return value


def _parse_metadata_object(raw_metadata: Any, source: str) -> dict[str, Any]:
    if raw_metadata is None:
        return {}

    if isinstance(raw_metadata, dict):
        return raw_metadata

    raw_text = str(raw_metadata).strip()
    if not raw_text:
        return {}

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed

        logger.warning(
            "[SESSION] Metadata from %s parsed as %s instead of object",
            source,
            type(parsed).__name__,
        )
        return {}
    except json.JSONDecodeError as exc:
        logger.warning(
            "[SESSION] Strict JSON parse failed for %s: %s | raw=%s",
            source,
            exc,
            _metadata_excerpt(raw_text),
        )

    # Tolerate playground input that looks like an object but is missing commas
    # or uses bare keys such as `primary_phone: "123"`.
    stripped = raw_text
    if stripped.startswith("{") and stripped.endswith("}"):
        stripped = stripped[1:-1]

    parsed: dict[str, Any] = {}
    for line_no, raw_line in enumerate(stripped.splitlines(), start=1):
        line = raw_line.strip().rstrip(",")
        if not line or line == "{" or line == "}":
            continue
        if ":" not in line:
            logger.warning(f"[SESSION] Skipping malformed metadata line: {raw_line!r}")
            continue

        raw_key, raw_value = line.split(":", 1)
        key = raw_key.strip().strip('"').strip("'")
        if not key:
            raise ValueError(f"Metadata line {line_no} from {source!r} has an empty key")

        parsed[key] = _parse_metadata_value(raw_value)

    if parsed:
        logger.info(
            "[SESSION] Parsed CRM metadata from %s using tolerant parser. keys=%s",
            source,
            sorted(parsed.keys()),
        )

    return parsed


def _sanitize_crm_data(crm_data: dict[str, Any], source: str) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    ignored: list[str] = []

    for key, value in crm_data.items():
        target_key = key if key in CALL_SESSION_FIELDS else CRM_FIELD_ALIASES.get(_normalize_metadata_key(key))
        if target_key is None:
            ignored.append(key)
            continue
        sanitized[target_key] = value

    if ignored:
        logger.warning("[SESSION] Ignoring unknown CRM metadata keys from %s: %s", source, ignored)

    for key, value in list(sanitized.items()):
        if value is None:
            sanitized[key] = ""
        elif not isinstance(value, str):
            sanitized[key] = str(value)

    return sanitized


async def _resolve_crm_data(
    ctx: JobContext, participant: rtc.RemoteParticipant
) -> dict[str, Any]:
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        logger.info("[SESSION] Metadata resolution attempt %s/%s", attempt, max_attempts)

        sources: list[tuple[str, Any]] = [
            ("job.metadata", getattr(getattr(ctx, "job", None), "metadata", None)),
            ("participant.metadata", getattr(participant, "metadata", None)),
        ]

        for remote in ctx.room.remote_participants.values():
            if remote.identity == participant.identity:
                continue
            sources.append((f"remote_participant[{remote.identity}].metadata", remote.metadata))

        sources.append(("room.metadata", getattr(ctx.room, "metadata", None)))

        for source_name, raw_metadata in sources:
            if not raw_metadata:
                continue

            logger.info(
                "[SESSION] Trying metadata source=%s chars=%s",
                source_name,
                len(str(raw_metadata)),
            )
            try:
                parsed = _parse_metadata_object(raw_metadata, source_name)
            except Exception as exc:
                logger.warning(
                    "[SESSION] Failed to parse metadata from %s: %s | raw=%s",
                    source_name,
                    exc,
                    _metadata_excerpt(raw_metadata),
                )
                continue

            if parsed:
                sanitized = _sanitize_crm_data(parsed, source_name)
                if not sanitized:
                    logger.warning(
                        "[SESSION] Parsed metadata from %s but no supported CRM keys were found",
                        source_name,
                    )
                    continue
                logger.info(
                    "[SESSION] Using CRM metadata from %s. keys=%s",
                    source_name,
                    sorted(sanitized.keys()),
                )
                return sanitized

        if attempt < max_attempts:
            await asyncio.sleep(0.25)

    logger.warning("[SESSION] No usable CRM metadata found in job, participant, or room metadata")
    return {}


def combine_chain_actions(chain: list[State], session_data: CallSession) -> str:
    """Combine ACTION_MAP entries for an auto-advance chain into one directive."""
    combined = []
    for state in chain:
        action = ACTION_MAP.get(state)
        if action:
            rendered = render_template(action, build_render_context(session_data))
            combined.append(rendered)
    return "\n".join(combined)


class आकृतिAgent(Agent):
    def __init__(self, crm_data: dict, ctx: JobContext):
        super().__init__(instructions="")
        self.session_data = CallSession(**crm_data)
        self.classifier = IntentClassifier()
        self._init_greeting_done = False
        self.ctx = ctx

    async def _stream_default_llm_with_retries(
        self,
        chat_ctx: lk_llm.ChatContext,
        tools: list[lk_llm.FunctionTool],
        model_settings: ModelSettings,
        response_buffer: list[str],
        stage_name: str,
    ) -> AsyncIterable[lk_llm.ChatChunk]:
        max_attempts = config.LLM_MAX_RETRIES + 1

        for attempt in range(max_attempts):
            response_buffer.clear()
            yielded_any = False
            stream = Agent.default.llm_node(self, chat_ctx, tools, model_settings)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + config.LLM_TIMEOUT_SECONDS

            try:
                while True:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError

                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=remaining)
                    if chunk.delta and chunk.delta.content:
                        response_buffer.append(chunk.delta.content)
                    yielded_any = True
                    yield chunk
            except StopAsyncIteration:
                return
            except asyncio.TimeoutError:
                logger.warning(
                    "[%s] Timeout on attempt %s/%s",
                    stage_name,
                    attempt + 1,
                    max_attempts,
                )
                if yielded_any:
                    logger.error(
                        "[%s] Timeout after partial output. Skipping retry to avoid duplicate audio.",
                        stage_name,
                    )
                    return
                if attempt == max_attempts - 1:
                    logger.error("[%s] All retries exhausted. Skipping turn.", stage_name)
                    return
            finally:
                with contextlib.suppress(Exception):
                    await stream.aclose()

    # ── Agent is initialized (greeting moved to entrypoint) ──

    # ── Core Pipeline: STT → Intent → State Machine → LLM Render ──
    async def llm_node(
        self,
        chat_ctx: lk_llm.ChatContext,
        tools: list[lk_llm.FunctionTool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[lk_llm.ChatChunk]:
        """
        Intercepts LiveKit's STT→LLM pipeline.
        Replaces the chat context with our controlled 3-part payload.
        """

        # Extract user messages
        user_messages = [m for m in chat_ctx.messages() if m.role == "user"]

        if not user_messages:
            # First turn (greeting) or programmatic generation
            # Delegate to default — the instructions from generate_reply carry the persona
            response_buffer = []
            async for chunk in self._stream_default_llm_with_retries(
                chat_ctx,
                tools,
                model_settings,
                response_buffer,
                "LLM",
            ):
                yield chunk

            # Capture agent response in transcript
            full_response = "".join(response_buffer)
            if full_response:
                self.session_data.transcript.append({
                    "role": "agent",
                    "text": full_response,
                    "state": self.session_data.current_state.value,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            return

        latest_transcript = user_messages[-1].text_content
        logger.info(f"[STT] {latest_transcript}")

        # ── STAGE 2: CLASSIFY INTENT ──
        pipeline_logger.start("CLASSIFY")
        intent = await self.classifier.classify(latest_transcript)
        classify_ms = pipeline_logger.end("CLASSIFY", intent=intent.value)

        # ── STAGE 3: STATE MACHINE TRANSITION ──
        pipeline_logger.start("TRANSITION")
        prev_state = self.session_data.current_state
        next_state = resolve_next_state(self.session_data, intent, latest_transcript)

        # ── STAGE 3.5: POST-TRANSITION HOOKS ──
        post_transition(self.session_data, intent, latest_transcript, next_state)
        pipeline_logger.end("TRANSITION")
        pipeline_logger.log_transition(prev_state.value, intent.value, next_state.value)

        # ── STAGE 4: BUILD ACTION ──
        # Handle programmatic states (no speech, just routing)
        current = self.session_data.current_state
        if ACTION_MAP.get(current) is None and current != State.END:
            resolved = resolve_programmatic(self.session_data)
            current = self.session_data.current_state
            logger.info(f"[PROGRAMMATIC] Resolved to {current.value}")

        # Handle auto-advance chains
        if current in AUTO_TRANSITIONS:
            chain = execute_auto_chain(self.session_data, current)
            combined_action = combine_chain_actions(chain, self.session_data)
            pipeline_logger.log_auto_chain(chain)
        else:
            action = ACTION_MAP.get(self.session_data.current_state)
            if action:
                combined_action = render_template(action, build_render_context(self.session_data))
            else:
                combined_action = None

        # ── STAGE 5: BUILD 3-PART PAYLOAD & GENERATE ──
        if combined_action and self.session_data.current_state != State.END:
            payload = build_llm_payload(self.session_data, action_override=combined_action)
            logger.info(f"[LLM_PROMPT] Full payload being sent to LLM:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

            controlled_ctx = lk_llm.ChatContext()
            for msg in payload:
                controlled_ctx.add_message(role=msg["role"], content=msg["content"])

            pipeline_logger.start("LLM")
            response_buffer = []
            prompt_tokens = 0
            
            async for chunk in self._stream_default_llm_with_retries(
                controlled_ctx,
                [],
                model_settings,
                response_buffer,
                "LLM",
            ):
                if getattr(chunk, "usage", None):
                    prompt_tokens = getattr(chunk.usage, "prompt_tokens", prompt_tokens)
                yield chunk

            if prompt_tokens == 0:
                # Fallback approximation if no usage stats returned
                prompt_tokens = sum(len(m.get("content", "")) // 4 for m in payload)
                
            pipeline_logger.end("LLM", tokens=prompt_tokens)

            # Capture agent response
            full_response = "".join(response_buffer)
            if full_response:
                self.session_data.transcript.append({
                    "role": "agent",
                    "text": full_response,
                    "state": self.session_data.current_state.value,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })

        # ── TERMINAL STATE: End call ──
        if self.session_data.current_state == State.END:
            self.session_data.main_disposition, self.session_data.sub_disposition = (
                compute_disposition(self.session_data)
            )
            await log_call(self.session_data)
            logger.info(
                f"[CALL END] Disposition: {self.session_data.main_disposition} / "
                f"{self.session_data.sub_disposition}"
            )
            # Delay disconnect to let final TTS audio play
            asyncio.create_task(self._delayed_disconnect())

    async def _delayed_disconnect(self):
        """Wait for TTS to finish playing, then disconnect."""
        await asyncio.sleep(4)
        try:
            await self.ctx.room.disconnect()
        except Exception as e:
            logger.error(f"Disconnect error: {e}")



# ══════════════════════════════════════════════════════════════════════
# LIVEKIT WORKER SETUP
# ══════════════════════════════════════════════════════════════════════

async def entrypoint(ctx: JobContext):
    """LiveKit room session entrypoint."""
    await ctx.connect()
    
    try:
        participant = await asyncio.wait_for(
            ctx.wait_for_participant(), timeout=30
        )
    except asyncio.TimeoutError:
        logger.error("[SESSION] Timeout waiting for participant")
        return

    crm_data = await _resolve_crm_data(ctx, participant)

    logger.info(f"[SESSION] New call. CRM: {crm_data.get('customer_name') or crm_data.get('company_name') or 'Unknown'}")

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
            interim_results=True,
            endpointing_ms=300,
            smart_format=True,
            punctuate=True,
        ),
        llm=openai.LLM(model="gpt-5.4-nano"),
        tts=sarvam.TTS(
            model="bulbul:v3",
            target_language_code="hi-IN",
            speaker="ritu",
            pace=1.0,
            temperature=0.6,
            min_buffer_size=50,
            max_chunk_length=150,
            speech_sample_rate=22050,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
        ),
    )

    @session.on("metrics_collected")
    def _on_metrics_collected(metrics):
        log_metric(metrics)

    agent = आकृतिAgent(crm_data=crm_data, ctx=ctx)
    await session.start(
        agent=agent,
        room=ctx.room,
    )
    
    # ── Greeting AFTER session.start ──
    async def _max_duration_watchdog():
        try:
            await asyncio.sleep(config.MAX_CALL_DURATION_SECONDS)
            logger.warning("[WATCHDOG] Max call duration reached. Forcing disconnect.")
            await ctx.room.disconnect()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"[WATCHDOG] Failed to disconnect room cleanly: {exc}")

    watchdog_task = asyncio.create_task(_max_duration_watchdog())

    async def _cancel_watchdog(_reason: str = ""):
        if watchdog_task.done():
            return

        watchdog_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watchdog_task

    ctx.add_shutdown_callback(_cancel_watchdog)

    await asyncio.sleep(1.0)
    
    # Execute auto-chain: OPENING_GREETING (AUTO) → CONFIRM_IDENTITY (WAIT)
    auto_chain = execute_auto_chain(agent.session_data, State.OPENING_GREETING)
    combined_action = combine_chain_actions(auto_chain, agent.session_data)
    pipeline_logger.log_auto_chain(auto_chain)

    # Build full greeting instruction with persona
    greeting_instruction = f"{आकृति_SYSTEM_PROMPT}\n\nतत्काल निर्देश: {combined_action}"
    await session.generate_reply(instructions=greeting_instruction)
    agent._init_greeting_done = True


if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="आकृति-welcome-call"
        )
    )

