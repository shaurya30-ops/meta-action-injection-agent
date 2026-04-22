# Conversation Engine

This package establishes the new runtime layout for the call flow architecture:

- `hot_path/`: deterministic event parsing, routing, and state grammars
- `cold_path/`: structured LLM fallbacks and heavier semantic recovery
- `schemas/`: shared event and payload contracts
- `evaluation/`: transcript fixtures and parser test assets

The current restructure is compatibility-first:

- legacy runtime modules remain in place
- new entry points can import through `conversation_engine`
- future transcript-driven parsers can be added under `hot_path/grammars/states/`

Migration target:

1. Deterministic event parser on the hot path
2. Structured LLM only on the cold path
3. Transcript fixtures drive parser coverage before model usage expands

