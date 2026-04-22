from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EventOrigin(str, Enum):
    HOT_PATH = "hot_path"
    COLD_PATH = "cold_path"
    SYSTEM = "system"


class EventType(str, Enum):
    AFFIRM = "AFFIRM"
    DENY = "DENY"
    ASK = "ASK"
    INFORM = "INFORM"
    DEFER = "DEFER"
    WRONG_PERSON = "WRONG_PERSON"
    TRAINING_PENDING = "TRAINING_PENDING"
    BILLING_STARTED = "BILLING_STARTED"
    BILLING_NOT_STARTED = "BILLING_NOT_STARTED"
    INSTALLATION_PENDING = "INSTALLATION_PENDING"
    WHATSAPP_AVAILABLE = "WHATSAPP_AVAILABLE"
    WHATSAPP_UNAVAILABLE = "WHATSAPP_UNAVAILABLE"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    SYSTEM_NOISE = "SYSTEM_NOISE"
    UNCLEAR = "UNCLEAR"


@dataclass(slots=True)
class EventConfidence:
    overall: float
    lexical: float = 0.0
    grammar: float = 0.0
    acoustic: float = 0.0


@dataclass(slots=True)
class ExtractedEntities:
    callback_time_text: str | None = None
    digits_spoken: str | None = None
    person_name: str | None = None
    company_name: str | None = None
    issue_hint: str | None = None
    raw_slots: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class CallControlPayload:
    can_interrupt: bool = True
    requires_cold_path: bool = False
    should_resume_previous_step: bool = False


@dataclass(slots=True)
class StateSignalPayload:
    source_state: str
    target_state: str | None = None
    matched_rule: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParserEvent:
    type: EventType
    text: str
    normalized_text: str
    origin: EventOrigin
    confidence: EventConfidence
    entities: ExtractedEntities = field(default_factory=ExtractedEntities)
    control: CallControlPayload = field(default_factory=CallControlPayload)
    state: StateSignalPayload | None = None
