from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="VERIFY_WHATSAPP",
    description="Detect whether the current talking number is available on WhatsApp.",
    ordered_rules=(
        GrammarRule(
            rule_id="whatsapp_available_with_training_interrupt",
            patterns=(
                r"whatsapp\s+पे\s+available\s+है.*(?:training|ट्रेनिंग)\s+(?:की\s+requirement|नहीं\s+हुई|pending)",
                r"whatsapp\s+पर\s+available\s+है.*(?:training|ट्रेनिंग)\s+(?:की\s+requirement|नहीं\s+हुई|pending)",
            ),
            emits=("WHATSAPP_AVAILABLE", "TRAINING_PENDING"),
            notes="User confirms WhatsApp availability and raises training in the same turn.",
        ),
        GrammarRule(
            rule_id="whatsapp_unavailable",
            patterns=(
                r"whatsapp\s+पर\s+available\s+नहीं",
                r"whatsapp\s+पे\s+available\s+नहीं",
                r"दूसरा\s+number",
                r"different\s+number",
                r"whatsapp\s+नहीं\s+है",
            ),
            emits=("WHATSAPP_UNAVAILABLE", "DENY"),
            notes="Current number is not on WhatsApp.",
        ),
        GrammarRule(
            rule_id="whatsapp_available",
            patterns=(
                r"whatsapp\s+पे\s+available\s+है",
                r"whatsapp\s+पर\s+available\s+है",
                r"same\s+ही\s+है",
                r"same\s+है",
                r"यही\s+है",
                r"हाँ\s*जी\s+madam\s+है",
            ),
            emits=("WHATSAPP_AVAILABLE", "AFFIRM"),
            notes="Current number is available on WhatsApp.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks a product-support question before confirming WhatsApp availability.",
    ),
)
