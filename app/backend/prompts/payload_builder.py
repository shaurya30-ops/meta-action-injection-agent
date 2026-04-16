from content_extraction.extractor_logic import build_render_context
from state_machine.actions import ACTION_MAP
from state_machine.session import CallSession
from state_machine.states import State

import config

from .persona import आकृति_SYSTEM_PROMPT
from .template_renderer import render_template


PREFIX_EXEMPT_STATES = {
    State.OPENING_GREETING,
    State.CALLBACK_CLOSING,
    State.INVALID_REGISTRATION,
    State.WARM_CLOSING,
    State.END,
}


def _apply_response_prefix(session: CallSession, text: str) -> str:
    if session.current_state in PREFIX_EXEMPT_STATES:
        return text.strip()

    prefix = session.pending_response_prefix.strip()
    if not prefix:
        return text.strip()
    return f"{prefix} {text}".strip()


def build_action_text(session: CallSession, action_override: str | None = None) -> str | None:
    if action_override is not None:
        text = action_override.strip()
        return _apply_response_prefix(session, text) if text else None

    action_template = ACTION_MAP.get(session.current_state)
    if action_template is None:
        return None
    rendered = render_template(action_template, build_render_context(session))
    return _apply_response_prefix(session, rendered)


def build_llm_payload(session: CallSession, action_override: str | None = None) -> list[dict]:
    part1 = {"role": "system", "content": आकृति_SYSTEM_PROMPT}

    recent = session.transcript[-config.TRANSCRIPT_WINDOW_SIZE :]
    part2 = []
    for entry in recent:
        role = "user" if entry["role"] == "user" else "assistant"
        part2.append({"role": role, "content": entry["text"]})

    action_text = build_action_text(session, action_override=action_override)
    if action_text is None:
        return []

    part3 = {"role": "system", "content": f"तत्काल निर्देश: {action_text}"}
    return [part1] + part2 + [part3]
