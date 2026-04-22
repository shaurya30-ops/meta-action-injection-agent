from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="CONFIRM_EMAIL_CORRECTION",
    description="Confirm a corrected email after the agent read it back.",
    ordered_rules=(
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
            notes="Corrected email confirmed.",
        ),
        GrammarRule(
            rule_id="email_corrected_again",
            patterns=(
                r"नहीं.*email",
                r"गलत.*email",
                r"at\s+the\s+rate",
                r"@",
            ),
            emits=("INFORM",),
            notes="User re-corrects the email.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks an unrelated support question while email confirmation is pending.",
    ),
)
