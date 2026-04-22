from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="CONFIRM_BUSINESS_DETAILS",
    description="Confirmation loop after business details were corrected.",
    ordered_rules=(
        GrammarRule(
            rule_id="business_details_recorrected",
            patterns=(
                r"नहीं",
                r"गलत",
                r"wholesaler",
                r"retailer",
                r"distributor",
                r"pharma",
                r"medical",
            ),
            emits=("INFORM",),
            notes="User is still correcting the recorded business profile.",
        ),
        GrammarRule(
            rule_id="business_details_confirmed",
            patterns=(
                r"^हाँ$",
                r"^हां$",
                r"^हाँ\s*जी$",
                r"^हां\s*जी$",
                r"सही\s+है",
                r"यही\s+है",
            ),
            emits=("AFFIRM",),
            notes="Corrected business profile confirmed.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user starts a new support detour instead of confirming the corrected profile.",
    ),
)
