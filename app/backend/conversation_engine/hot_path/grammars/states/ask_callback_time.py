from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="ASK_CALLBACK_TIME",
    description="Callback scheduling time capture.",
    ordered_rules=(
        GrammarRule(
            rule_id="callback_time_provided",
            patterns=(
                r"minute\s+बाद",
                r"मिनट\s+बाद",
                r"घंटे\s+बाद",
                r"घंटा\s+बाद",
                r"कल\s+सुबह",
                r"कल\s+शाम",
                r"आज\s+शाम",
                r"कल\s+\d{1,2}\s*बजे",
                r"\d{1,2}\s*बजे\s+तक",
                r"(?:^|\s)\d{1,2}\s*बजे(?:\s|$)",
            ),
            emits=("CALLBACK_REQUESTED", "INFORM"),
            notes="Specific callback slot spoken.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user gives a vague business narrative instead of a callback window.",
    ),
)
