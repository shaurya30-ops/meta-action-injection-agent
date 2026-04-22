from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="VERIFY_BUSINESS_DETAILS",
    description="Business-type and trade confirmation.",
    ordered_rules=(
        GrammarRule(
            rule_id="business_details_corrected",
            patterns=(
                r"नहीं.*business\s+type",
                r"trade\s+wholesaler",
                r"trade\s+retailer",
                r"business\s+type\s+pharma",
                r"business\s+type\s+medical",
                r"wholesaler",
                r"retailer",
                r"distributor",
            ),
            emits=("INFORM",),
            notes="Business profile is being corrected.",
        ),
        GrammarRule(
            rule_id="business_details_confirmed",
            patterns=(
                r"^हाँ$",
                r"^हां$",
                r"^हाँ\s*जी$",
                r"^हां\s*जी$",
                r"यही\s+है",
                r"सही\s+है",
            ),
            emits=("AFFIRM",),
            notes="Recorded business profile confirmed.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user answers with a broad product-support complaint instead of confirming the business profile.",
    ),
)
