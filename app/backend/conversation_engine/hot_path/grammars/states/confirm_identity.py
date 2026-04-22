from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="CONFIRM_IDENTITY",
    description="Follow-up identity clarification after a weak opener response.",
    ordered_rules=(
        GrammarRule(
            rule_id="confirm_identity_wrong_person",
            patterns=(
                r"गलत\s+(?:number|नंबर|नम्बर)",
                r"wrong\s+number",
                r"नहीं\s+हो\s+रही",
                r"वो\s+यहाँ\s+नहीं",
            ),
            emits=("WRONG_PERSON",),
            notes="Clarified as wrong person or wrong destination.",
        ),
        GrammarRule(
            rule_id="confirm_identity_soft_continue",
            patterns=(
                r"^जी\s+बताइए$",
                r"^बताइए$",
                r"^कहिए$",
            ),
            emits=("ASK",),
            notes="Allows continuation without a fully explicit identity restatement.",
        ),
        GrammarRule(
            rule_id="confirm_identity_affirm",
            patterns=(
                r"(?:हाँ|हां)\s*जी.*हो\s+रही\s+है",
                r"जी\s+हो\s+रही\s+है",
                r"(?:हाँ|हां)\s*जी$",
                r"^हाँ$",
                r"^हां$",
            ),
            emits=("AFFIRM",),
            notes="Identity confirmed after re-ask.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user gives a multi-party transfer answer instead of confirming identity.",
    ),
)
