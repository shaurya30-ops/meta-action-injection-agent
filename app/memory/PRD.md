# Akash Voice Agent — PRD

## Problem Statement
Build a high-performance, real-time voice agent (Akash) for Marg ERP Solutions. Deterministic state machine architecture where LLM acts as a linguistic rendering engine.

## Architecture
- STT: Deepgram Nova-3 (Hinglish)
- Intent Classifier: Qwen2.5-0.5B-Instruct (LoRA fine-tuned, 15 generic speech-act labels)
- State Machine: Deterministic Python logic matrix (38 states, 120 transitions)
- LLM: gpt-5.4-nano (rendering engine, 3-part sandwich payload)
- TTS: Sarvam Bulbul v3 (Devanagari danda-aware chunking)
- Orchestration: LiveKit Agents Framework

## What's Been Implemented (Jan 2026)
- Complete state machine: 38 states, 15 intents, **247 transitions** (hardened with soft transitions), 9 auto-advances, 3 global overrides
- **State-aware keyword correction** for ASK_BILLING_STATUS (catches AFFIRM↔INFORM misroute)
- **Soft transitions** added to all verification/callback/reference states — any intent leads to acceptable outcome
- **Tightened regex fallback** — priority-ordered, catches GOODBYE/ESCALATE first, anchored GREET/AFFIRM patterns
- 3 programmatic decision nodes (sentiment eligibility, price retry, callback routing)
- Intent classifier with LoRA adapter loading + regex fallback
- Content extraction layer (phone, email, pincode, business, datetime, free text)
- Akash persona prompt (male, Devanagari Hindi + Latin English, brand-compliant)
- 3-part sandwich payload builder with action_override for auto-chains
- Devanagari danda-aware TTS chunking
- Sentiment tracker (sticky negative, D-SAT flag)
- Disposition system (8 main dispositions, 40+ sub-dispositions)
- Call logging (JSONL, ready for MongoDB migration)
- Pipeline logger (structured latency tracking per stage)
- Training data: 1,126 Hinglish utterances across 15 intents
- Complete LoRA training script for Jupyter/L4 GPU
- All 7 agent.py bugs + 3 resolver.py bugs fixed
- **12 call path simulations verified** including misclassification resilience tests

## Verified Call Paths
1. Happy Path: Billing started -> Details verification -> Positive satisfaction -> Reference pitch -> Close
2. Customer Busy: Callback scheduling
3. D-SAT: Escalation -> Urgent flag -> Close without reference pitch

## Backlog (P0)
- Upload trained LoRA adapter to models/akash-intent-classifier/
- Test on LiveKit Playground with real API keys
- Add Hinglish datetime parser (currently stores raw text)
- Add spoken email normalizer improvements

## Backlog (P1)
- Test suite (transitions, auto-chains, extractors, e2e paths)
- Silence/disconnect detection (10s timeout)
- LLM timeout/retry layer
- MongoDB integration for call logs
- Prompt caching optimization (pad to 1024 tokens)

## Backlog (P2)
- Speculative classification (interim STT results)
- Multi-language support
- Dashboard for call analytics
