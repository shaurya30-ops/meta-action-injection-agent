from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="COLLECT_EMAIL_CORRECTION",
    description="Collect a corrected email ID in one or more spoken fragments.",
    ordered_rules=(
        GrammarRule(
            rule_id="email_correction_fragment",
            patterns=(
                r"at\s+the\s+rate",
                r"dot",
                r"underscore",
                r"dash",
                r"gmail",
                r"yahoo",
                r"outlook",
                r"hotmail",
                r"icloud",
                r"mail\s+id",
            ),
            emits=("INFORM",),
            notes="Spoken email fragment or full email correction.",
        ),
        GrammarRule(
            rule_id="email_refused",
            patterns=(
                r"email\s+नहीं\s+बता",
                r"share\s+नहीं",
                r"comfortable\s+नहीं",
                r"skip\s+कर",
            ),
            emits=("DENY",),
            notes="User refuses to provide an email address.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user starts dictating a non-email identifier in the email slot.",
    ),
)
