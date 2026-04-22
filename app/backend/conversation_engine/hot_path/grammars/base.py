from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GrammarRule:
    rule_id: str
    patterns: tuple[str, ...]
    emits: tuple[str, ...]
    notes: str = ""


@dataclass(slots=True)
class StateGrammar:
    state_name: str
    description: str
    ordered_rules: tuple[GrammarRule, ...]
    cold_path_trigger_notes: tuple[str, ...] = field(default_factory=tuple)

