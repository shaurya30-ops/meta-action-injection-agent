"""
Akash Voice Agent — LiveKit Entrypoint
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
import logging
from datetime import datetime, timezone
from typing import AsyncIterable

import livekit.rtc as rtc
from livekit.agents import Agent, AgentSession, AgentServer, TurnHandlingOptions, ModelSettings
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
from prompts.persona import AKASH_SYSTEM_PROMPT
from prompts.payload_builder import build_llm_payload
from prompts.template_renderer import render_template
from tts.danda_splitter import split_at_danda, async_iter
from dispositions.resolver import compute_disposition
from dispositions.logger import log_call
from utils.logger import pipeline_logger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("akash.agent")


def combine_chain_actions(chain: list[State], session_data: CallSession) -> str:
    """Combine ACTION_MAP entries for an auto-advance chain into one directive."""
    combined = []
    for state in chain:
        action = ACTION_MAP.get(state)
        if action:
            rendered = render_template(action, session_data.__dict__)
            combined.append(rendered)
    return "\n".join(combined)


class AkashAgent(Agent):
    def __init__(self, crm_data: dict):
        super().__init__(instructions="")
        self.session_data = CallSession(**crm_data)
        self.classifier = IntentClassifier()
        self._init_greeting_done = False

    # ── Agent joins room — speak first ──
    async def on_enter(self) -> None:
        """Akash initiates the call. Customer doesn't speak first."""
        # Execute auto-chain: OPENING_GREETING (AUTO) → CONFIRM_IDENTITY (WAIT)
        auto_chain = execute_auto_chain(self.session_data, State.OPENING_GREETING)
        combined_action = combine_chain_actions(auto_chain, self.session_data)
        pipeline_logger.log_auto_chain(auto_chain)

        # Build full greeting instruction with persona
        greeting_instruction = f"{AKASH_SYSTEM_PROMPT}\n\nतत्काल निर्देश: {combined_action}"
        await self.session.generate_reply(instructions=greeting_instruction)
        self._init_greeting_done = True

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
            async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
                if chunk.delta and chunk.delta.content:
                    response_buffer.append(chunk.delta.content)
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
                combined_action = render_template(action, self.session_data.__dict__)
            else:
                combined_action = None

        # ── STAGE 5: BUILD 3-PART PAYLOAD & GENERATE ──
        if combined_action and self.session_data.current_state != State.END:
            payload = build_llm_payload(self.session_data, action_override=combined_action)

            controlled_ctx = lk_llm.ChatContext()
            for msg in payload:
                controlled_ctx.add_message(role=msg["role"], content=msg["content"])

            pipeline_logger.start("LLM")
            response_buffer = []
            async for chunk in Agent.default.llm_node(self, controlled_ctx, [], model_settings):
                if chunk.delta and chunk.delta.content:
                    response_buffer.append(chunk.delta.content)
                yield chunk

            pipeline_logger.end("LLM", tokens=len(response_buffer))

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
            await self.session.room.disconnect()
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    # ── Custom TTS: Devanagari Danda-Aware Chunking ──
    async def tts_node(
        self,
        text: AsyncIterable[str],
        model_settings: ModelSettings,
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Split LLM output at danda (।) boundaries before sending to Sarvam TTS."""
        buffer = ""
        async for chunk in text:
            buffer += chunk

            segments = split_at_danda(buffer)
            if len(segments) > 1:
                for segment in segments[:-1]:
                    if segment.strip():
                        async for frame in Agent.default.tts_node(
                            self, async_iter(segment), model_settings
                        ):
                            yield frame
                buffer = segments[-1]

        # Flush remaining
        if buffer.strip():
            async for frame in Agent.default.tts_node(
                self, async_iter(buffer), model_settings
            ):
                yield frame


# ══════════════════════════════════════════════════════════════════════
# LIVEKIT SERVER SETUP
# ══════════════════════════════════════════════════════════════════════

server = AgentServer()


@server.rtc_session(agent_name="akash-welcome-call")
async def entrypoint(ctx):
    """LiveKit room session entrypoint."""
    # Pull CRM data from room metadata
    crm_data = json.loads(ctx.room.metadata or "{}")
    if not crm_data:
        # Fallback: check first participant's metadata
        for p in ctx.room.remote_participants.values():
            if p.metadata:
                try:
                    crm_data = json.loads(p.metadata)
                    break
                except json.JSONDecodeError:
                    continue

    logger.info(f"[SESSION] New call. CRM: {crm_data.get('customer_name', 'Unknown')}")

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
            speaker="aditya",
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

    await session.start(
        agent=AkashAgent(crm_data=crm_data),
        room=ctx.room,
    )


if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(server)
