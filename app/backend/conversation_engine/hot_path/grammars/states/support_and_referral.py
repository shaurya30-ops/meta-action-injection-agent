from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="SUPPORT_AND_REFERRAL",
    description="Referral offer acceptance or decline after support pitch.",
    ordered_rules=(
        GrammarRule(
            rule_id="referral_accept",
            patterns=(
                r"हाँ\s*जी\s+हाँ\s*जी\s+लिखिएगा",
                r"एक\s+व्यक्ति\s+है",
                r"एक\s+person\s+है",
                r"हाँ\s*जी\s+है",
                r"बताता\s+हूँ",
                r"दे\s+सकता\s+हूँ",
            ),
            emits=("AFFIRM",),
            notes="User agrees to share a referral.",
        ),
        GrammarRule(
            rule_id="referral_decline",
            patterns=(
                r"कोई\s+नहीं\s+है",
                r"नहीं\s+है",
                r"नहीं\s+madam",
                r"अभी\s+नहीं",
                r"नहीं",
            ),
            emits=("DENY",),
            notes="User declines referral sharing.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks a support follow-up instead of answering the referral offer.",
    ),
)
