from content_extraction.extractor_logic import build_render_context
from state_machine.actions import ACTION_MAP
from state_machine.session import CallSession

import config

from .persona import आकृति_SYSTEM_PROMPT
from .template_renderer import render_template


def build_action_text(session: CallSession, action_override: str | None = None) -> str | None:
    if action_override is not None:
        text = action_override.strip()
        return text or None

    action_template = ACTION_MAP.get(session.current_state)
    if action_template is None:
        return None
    return render_template(action_template, build_render_context(session))


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
