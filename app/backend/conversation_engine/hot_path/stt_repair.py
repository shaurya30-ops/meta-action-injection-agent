from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RepairDecision:
    should_repair: bool
    reason: str


def needs_transcript_repair(text: str) -> RepairDecision:
    compact = (text or "").strip()
    if not compact:
        return RepairDecision(should_repair=True, reason="empty_transcript")
    if len(compact) <= 1:
        return RepairDecision(should_repair=True, reason="too_short")
    return RepairDecision(should_repair=False, reason="not_needed")


__all__ = ["RepairDecision", "needs_transcript_repair"]

