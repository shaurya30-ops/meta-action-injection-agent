from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StructuredFallbackRequest:
    state_name: str
    transcript: str
    conversation_window: list[str] = field(default_factory=list)
    allowed_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructuredFallbackResult:
    chosen_event: str
    confidence: float
    reason: str
    extracted_slots: dict[str, str] = field(default_factory=dict)


class StructuredFallbackResolver:
    """
    Placeholder interface for the cold-path structured LLM resolver.

    This stays intentionally thin until transcript-derived parser coverage is in
    place and we promote a concrete implementation.
    """

    def resolve(self, request: StructuredFallbackRequest) -> StructuredFallbackResult:
        return StructuredFallbackResult(
            chosen_event="UNCLEAR",
            confidence=0.0,
            reason="structured_llm_not_implemented",
            extracted_slots={},
        )

