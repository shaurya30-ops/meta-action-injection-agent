from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="CHECK_AVAILABILITY",
    description="Availability gate before verification begins.",
    ordered_rules=(
        GrammarRule(
            rule_id="availability_system_noise",
            patterns=(
                r"this\s+call\s+is\s+now\s+being\s+recorded",
            ),
            emits=("SYSTEM_NOISE",),
            notes="Carrier or recorder announcement.",
        ),
        GrammarRule(
            rule_id="availability_defer_or_callback",
            patterns=(
                r"बाद\s+में\s+call",
                r"call\s+करो",
                r"अभी\s+busy",
                r"अभी\s+नहीं",
                r"थोड़ी\s+देर\s+बाद",
                r"पांच\s+minute\s+बाद",
                r"पाँच\s+minute\s+बाद",
                r"कल\s+सुबह",
                r"कल\s+शाम",
                r"\d{1,2}\s*बजे",
            ),
            emits=("DEFER", "CALLBACK_REQUESTED"),
            notes="User is not ready now and is pushing for a callback window.",
        ),
        GrammarRule(
            rule_id="availability_affirm_with_purpose_query",
            patterns=(
                r"बात\s+कर\s+सकते\s+हैं.*आगे\s+क्या\s+काम\s+है",
                r"बताओ\s+ना\s+आगे\s+क्या\s+काम\s+है",
            ),
            emits=("AFFIRM", "ASK"),
            notes="User agrees to continue while asking the purpose.",
        ),
        GrammarRule(
            rule_id="availability_ask_purpose",
            patterns=(
                r"क्या\s+बात\s+है",
                r"किस\s+बारे\s+में",
                r"पहले\s+बताओ",
                r"आगे\s+क्या\s+काम\s+है",
                r"क्या\s+काम\s+है",
            ),
            emits=("ASK",),
            notes="Purpose or context requested before time commitment.",
        ),
        GrammarRule(
            rule_id="availability_affirm",
            patterns=(
                r"^बताइए$",
                r"^बताओ$",
                r"^बोलिए$",
                r"बताइए\s+बताइए",
                r"चलो\s+(?:हाँ|हां)\s*जी\s+बताइए",
                r"(?:हाँ|हां)\s*जी\s+हो\s+सकती\s+है\s+बताइए",
                r"हो\s+जाएगी\s*(?:तो)?\s*(?:बताओ|बोलो)",
                r"हो\s+जाएगा\s*(?:तो)?\s*(?:बताओ|बोलो)",
                r"^(?:हाँ|हां)\s+बोलो$",
                r"^(?:हाँ|हां)\s+(?:हाँ|हां)\s+बोलो(?:\s+बोलो)?$",
                r"^बोलो(?:\s+बोलो)?$",
                r"^हाँ$",
                r"^हां$",
                r"^हाँ\s*जी$",
                r"^हां\s*जी$",
            ),
            emits=("AFFIRM",),
            notes="User is ready to proceed now.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user mixes an off-script complaint with a partial availability signal.",
    ),
)
