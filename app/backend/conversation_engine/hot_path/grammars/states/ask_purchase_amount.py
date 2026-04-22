from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="ASK_PURCHASE_AMOUNT",
    description="Purchase amount capture or polite refusal.",
    ordered_rules=(
        GrammarRule(
            rule_id="purchase_amount_refused",
            patterns=(
                r"याद\s+नहीं",
                r"नहीं\s+बता",
                r"skip\s+कर",
                r"पता\s+नहीं",
            ),
            emits=("DENY",),
            notes="User refuses or cannot recall the amount.",
        ),
        GrammarRule(
            rule_id="purchase_amount_provided",
            patterns=(
                r"₹\s*\d+",
                r"\b\d+[\d,]*\b",
                r"हजार",
                r"हज़ार",
                r"हज़ार",
                r"लाख",
            ),
            emits=("INFORM",),
            notes="Amount or amount-like figure was spoken.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks for pricing instead of answering their recorded purchase amount.",
    ),
)
