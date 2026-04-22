"""
Conversation engine package.

Architecture:
- hot_path: deterministic parsing and routing for low-latency turns
- cold_path: structured LLM and heavier fallback logic
- schemas: shared event contracts
- evaluation: transcript fixtures and parser validation assets
"""

