from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="VERIFY_EMAIL",
    description="Recorded email confirmation.",
    ordered_rules=(
        GrammarRule(
            rule_id="email_needs_correction",
            patterns=(
                r"same\s+ही\s+है\s+mail\s+id",
                r"mail\s+id\s+same\s+ही\s+है",
                r"नहीं.*email",
                r"गलत.*email",
                r"at\s+the\s+rate",
                r"@",
            ),
            emits=("INFORM",),
            notes="Email is being corrected or restated.",
        ),
        GrammarRule(
            rule_id="email_confirmed",
            patterns=(
                r"^हाँ$",
                r"^हां$",
                r"^हाँ\s*जी$",
                r"^हां\s*जी$",
                r"यही\s+है",
                r"same\s+है",
                r"same\s+ही\s+है",
            ),
            emits=("AFFIRM",),
            notes="Recorded email confirmed.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks a different account-support question instead of confirming the email.",
    ),
)
