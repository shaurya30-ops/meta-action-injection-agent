from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="ASK_ALTERNATE_NUMBER",
    description="Optional alternate-number offer.",
    ordered_rules=(
        GrammarRule(
            rule_id="alternate_same_as_whatsapp",
            patterns=(
                r"same\s+as\s+whatsapp",
                r"whatsapp\s+वाला\s+ही",
                r"व्हाट्सऐप\s+वाला\s+ही",
                r"यही\s+same",
            ),
            emits=("AFFIRM",),
            notes="Alternate is explicitly the same as WhatsApp number.",
        ),
        GrammarRule(
            rule_id="alternate_declined",
            patterns=(
                r"कोई\s+alternate\s+number\s+नहीं",
                r"alternate\s+number\s+नहीं\s+है",
                r"^नहीं\b",
                r"^नहीं\s+मैम\b",
                r"^नहीं$",
                r"^नई$",
                r"^नही$",
                r"नहीं\s+जी",
                r"no\s+alternate",
            ),
            emits=("DENY",),
            notes="User declines to provide an alternate number.",
        ),
        GrammarRule(
            rule_id="alternate_accept",
            patterns=(
                r"हाँ",
                r"हां",
                r"दे\s+सकते",
                r"बताता\s+हूँ",
            ),
            emits=("AFFIRM",),
            notes="User is willing to provide an alternate number.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks for a registered number update instead of answering the alternate-number prompt.",
    ),
)
