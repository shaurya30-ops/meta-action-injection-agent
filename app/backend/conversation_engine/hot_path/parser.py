from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re

from conversation_engine.hot_path.grammars.base import GrammarRule
from conversation_engine.hot_path.grammars.registry import get_state_grammar
from conversation_engine.hot_path.normalization import normalize_transcript


@lru_cache(maxsize=1024)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


@dataclass(slots=True)
class GrammarMatch:
    state_name: str
    transcript: str
    normalized_text: str
    rule: GrammarRule | None = None

    @property
    def emitted(self) -> tuple[str, ...]:
        return self.rule.emits if self.rule else ()


def match_state_grammar(state_name: str, transcript: str) -> GrammarMatch:
    normalized_text = normalize_transcript(transcript)
    grammar = get_state_grammar(state_name)
    if grammar is None:
        return GrammarMatch(state_name=state_name, transcript=transcript, normalized_text=normalized_text, rule=None)

    for rule in grammar.ordered_rules:
        if any(_compile_pattern(pattern).search(normalized_text) for pattern in rule.patterns):
            return GrammarMatch(state_name=state_name, transcript=transcript, normalized_text=normalized_text, rule=rule)

    return GrammarMatch(state_name=state_name, transcript=transcript, normalized_text=normalized_text, rule=None)


def parse_turn_event(state_name: str, transcript: str) -> GrammarMatch:
    return match_state_grammar(state_name, transcript)


__all__ = ["GrammarMatch", "match_state_grammar", "parse_turn_event"]
