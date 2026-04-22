from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="REFERRAL_DECLINE_NUDGE",
    description="Final referral nudge after an initial decline.",
    ordered_rules=(
        GrammarRule(
            rule_id="referral_still_declined",
            patterns=(
                r"कोई\s+नहीं",
                r"नहीं",
                r"अभी\s+नहीं",
                r"छोड़िए",
            ),
            emits=("DENY",),
            notes="User declines even after the nudge.",
        ),
        GrammarRule(
            rule_id="referral_after_nudge_accept",
            patterns=(
                r"हाँ",
                r"हां",
                r"एक\s+व्यक्ति\s+है",
                r"लिखिएगा",
                r"बताता\s+हूँ",
            ),
            emits=("AFFIRM",),
            notes="User agrees after the nudge.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user starts describing product issues instead of closing or sharing a referral.",
    ),
)
