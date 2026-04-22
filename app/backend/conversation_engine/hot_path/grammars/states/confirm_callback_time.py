from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="CONFIRM_CALLBACK_TIME",
    description="Confirmation or update of the callback slot.",
    ordered_rules=(
        GrammarRule(
            rule_id="callback_time_updated",
            patterns=(
                r"minute\s+बाद",
                r"मिनट\s+बाद",
                r"घंटे\s+बाद",
                r"घंटा\s+बाद",
                r"कल\s+सुबह",
                r"कल\s+शाम",
                r"आज\s+शाम",
                r"\b\d{1,2}\s*बजे\b",
            ),
            emits=("CALLBACK_REQUESTED", "INFORM"),
            notes="User updates the callback timing.",
        ),
        GrammarRule(
            rule_id="callback_time_confirmed",
            patterns=(
                r"^हाँ$",
                r"^हां$",
                r"^हाँ\s*जी$",
                r"^हां\s*जी$",
                r"सही\s+है",
                r"ठीक\s+है\s+जी",
            ),
            emits=("AFFIRM",),
            notes="Callback timing confirmed.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user asks to continue the business flow instead of confirming the callback window.",
    ),
)
