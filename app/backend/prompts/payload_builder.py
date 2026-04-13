from .persona import AKASH_SYSTEM_PROMPT
from .template_renderer import render_template
from state_machine.session import CallSession
from state_machine.actions import ACTION_MAP
import config


def build_llm_payload(session: CallSession, action_override: str = None) -> list[dict]:
    """
    Build the 3-part sandwich payload for gpt-5.4-nano.
    
    Part 1: Static persona prompt (cacheable)
    Part 2: Rolling transcript window (last N messages)
    Part 3: Tactical command for current state
    
    Args:
        session: Current call session
        action_override: If provided, use this instead of ACTION_MAP lookup.
                         Used for auto-advance chains where multiple state actions
                         are combined into one directive.
    """
    # Part 1: Static persona
    part1 = {"role": "system", "content": AKASH_SYSTEM_PROMPT}

    # Part 2: Rolling transcript (last 3 turn pairs = 6 messages)
    recent = session.transcript[-config.TRANSCRIPT_WINDOW_SIZE:]
    part2 = []
    for entry in recent:
        role = "user" if entry["role"] == "user" else "assistant"
        part2.append({"role": role, "content": entry["text"]})

    # Part 3: Tactical command
    if action_override:
        action_text = action_override
    else:
        action_template = ACTION_MAP.get(session.current_state)
        if action_template is None:
            return []  # Programmatic/system state, no LLM call needed
        action_text = render_template(action_template, session.__dict__)

    part3 = {"role": "system", "content": f"तत्काल निर्देश: {action_text}"}

    return [part1] + part2 + [part3]
