from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="VERIFY_PINCODE",
    description="Recorded pincode confirmation.",
    ordered_rules=(
        GrammarRule(
            rule_id="pincode_unknown",
            patterns=(
                r"मुझे\s+नहीं\s+पता",
                r"पता\s+नहीं",
                r"याद\s+नहीं",
                r"maloom\s+nahi",
            ),
            emits=("UNCLEAR",),
            notes="User does not know the pincode.",
        ),
        GrammarRule(
            rule_id="pincode_confirmed",
            patterns=(
                r"सही\s+है\s+pin\s+code",
                r"हाँ\s*जी.*सही\s+है",
                r"यही\s+सही\s+है",
                r"हाँ\s*जी\s+ma'am\s+सही\s+है",
            ),
            emits=("AFFIRM",),
            notes="Recorded pincode confirmed.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user gives a location narrative instead of confirming or correcting the pincode.",
    ),
)
