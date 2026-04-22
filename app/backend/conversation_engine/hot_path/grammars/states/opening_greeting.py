from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="OPENING_GREETING",
    description="Opening identity confirmation from transcript-backed live calls.",
    ordered_rules=(
        GrammarRule(
            rule_id="opening_wrong_person",
            patterns=(
                r"गलत\s+(?:number|नंबर|नम्बर)",
                r"wrong\s+number",
                r"wrong\s+person",
                r"यहाँ\s+(?:ऐसा\s+कोई|वो)\s+नहीं",
                r"आप\s+गलत\s+जगह\s+बात\s+कर\s+रहे",
            ),
            emits=("WRONG_PERSON",),
            notes="Wrong destination confirmed.",
        ),
        GrammarRule(
            rule_id="opening_identity_echo_question",
            patterns=(
                r"^हो\s+रही\s+है\??$",
                r"कौन\??$",
                r"कहाँ\s+से\??$",
                r"किससे\s+बात\s+करनी\s+है",
                r"कौन\s+बोल\s+रहे",
            ),
            emits=("ASK",),
            notes="User is repeating the identity question back.",
        ),
        GrammarRule(
            rule_id="opening_identity_affirm",
            patterns=(
                r"(?:हाँ|हां)\s*जी.*(?:हो\s+रही\s+है|बताइए|बताओ|बोलिए)",
                r"जी\s+हो\s+रही\s+है",
                r"जी\s+बोल\s+रहा\s+हूँ\s+बताइए",
                r"^हो\s+रही\s+है$",
                r"(?:हाँ|हां)\s*जी$",
            ),
            emits=("AFFIRM",),
            notes="Business identity confirmed.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user answers with a fragmented identity claim that does not map cleanly to affirm, ask, or wrong person.",
    ),
)
