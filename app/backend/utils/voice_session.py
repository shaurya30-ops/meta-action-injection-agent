"""Runtime tuning for real-time voice turn handling."""

from __future__ import annotations

from livekit.agents import APIConnectOptions
from livekit.agents.voice.agent_session import SessionConnectOptions

import config


def build_turn_handling_options() -> dict[str, object]:
    return {
        "turn_detection": config.TURN_DETECTION_MODE,
        "endpointing": {
            "mode": config.TURN_ENDPOINTING_MODE,
            "min_delay": config.TURN_ENDPOINTING_MIN_DELAY_SECONDS,
            "max_delay": config.TURN_ENDPOINTING_MAX_DELAY_SECONDS,
        },
        "interruption": {
            "enabled": True,
            "mode": config.TURN_INTERRUPTION_MODE,
            "discard_audio_if_uninterruptible": config.DISCARD_AUDIO_IF_UNINTERRUPTIBLE,
            "min_duration": config.TURN_INTERRUPTION_MIN_DURATION_SECONDS,
            "min_words": config.TURN_INTERRUPTION_MIN_WORDS,
            "resume_false_interruption": True,
            "false_interruption_timeout": config.TURN_FALSE_INTERRUPTION_TIMEOUT_SECONDS,
        },
    }


def build_session_runtime_options() -> dict[str, object]:
    return {
        "preemptive_generation": config.PREEMPTIVE_GENERATION_ENABLED,
        "min_consecutive_speech_delay": config.MIN_CONSECUTIVE_SPEECH_DELAY_SECONDS,
        "aec_warmup_duration": config.AEC_WARMUP_DURATION_SECONDS,
    }


def build_session_connect_options() -> SessionConnectOptions:
    return SessionConnectOptions(
        tts_conn_options=APIConnectOptions(
            max_retry=config.TTS_MAX_RETRIES,
            retry_interval=config.TTS_RETRY_INTERVAL_SECONDS,
            timeout=config.TTS_TIMEOUT_SECONDS,
        ),
        max_unrecoverable_errors=config.MEDIA_MAX_UNRECOVERABLE_ERRORS,
    )
