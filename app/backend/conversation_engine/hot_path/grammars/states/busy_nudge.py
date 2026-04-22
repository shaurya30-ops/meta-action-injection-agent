from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="BUSY_NUDGE",
    description="Resolve whether the user accepts the nudge or still wants a callback.",
    ordered_rules=(
        GrammarRule(
            rule_id="busy_nudge_callback_time",
            patterns=(
                r"पांच\s+minute\s+बाद",
                r"पाँच\s+minute\s+बाद",
                r"थोड़ी\s+देर\s+बाद",
                r"कल\s+सुबह",
                r"कल\s+शाम",
                r"\b\d{1,2}\s*बजे\b",
            ),
            emits=("CALLBACK_REQUESTED", "INFORM"),
            notes="User gives a time window after the nudge.",
        ),
        GrammarRule(
            rule_id="busy_nudge_defer",
            patterns=(
                r"अभी\s+नहीं",
                r"बाद\s+में",
                r"फिर\s+कभी",
                r"समय\s+नहीं\s+है",
                r"call\s+करो",
            ),
            emits=("DEFER", "CALLBACK_REQUESTED"),
            notes="User still wants to defer after the nudge.",
        ),
        GrammarRule(
            rule_id="busy_nudge_affirm",
            patterns=(
                r"^हाँ$",
                r"^हां$",
                r"^ठीक\s+है$",
                r"^हाँ\s*जी$",
                r"ठीक\s+है\s+जल्दी\s+पूछिए",
                r"चलो\s+बोलो",
                r"हाँ\s+बोलिए",
            ),
            emits=("AFFIRM",),
            notes="User accepts the nudge and continues.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user both accepts and schedules a different slot in the same turn.",
    ),
)
