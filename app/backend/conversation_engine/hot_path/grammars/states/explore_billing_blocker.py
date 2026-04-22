from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="EXPLORE_BILLING_BLOCKER",
    description="Reason capture after billing is not started or after a blocker-specific resume.",
    ordered_rules=(
        GrammarRule(
            rule_id="blocker_billing_started_now",
            patterns=(
                r"अब\s+billing\s+start\s+हो\s+गई\s+है",
                r"b(?:illing|िलिंग)\s+तो\s+start\s+हो\s+गई\s+है",
                r"building\s+start\s+हो\s+गई\s+है",
                r"madam\s+हो\s+गई\s+है\s+billing\s+start",
            ),
            emits=("BILLING_STARTED", "INFORM"),
            notes="User corrects earlier blocker and says billing has now started.",
        ),
        GrammarRule(
            rule_id="blocker_training_pending",
            patterns=(
                r"(?:training|ट्रेनिंग)\s+(?:नहीं\s+हुई|pending|बाकी|की\s+requirement)",
                r"software\s+समझ\s+नहीं\s+आ\s+रहा",
                r"(?:training|ट्रेनिंग)\s+दोबारा\s+चाहिए",
                r"use\s+नहीं\s+कर\s+पा\s+रहा",
            ),
            emits=("TRAINING_PENDING", "INFORM"),
            notes="Training gap explicitly described.",
        ),
        GrammarRule(
            rule_id="blocker_installation_pending",
            patterns=(
                r"install\s+नहीं\s+हुआ",
                r"installation\s+नहीं\s+हुआ",
                r"dealer\s+.*visit\s+नहीं\s+किया",
                r"local\s+(?:area\s+)?provider",
                r"partner\s+.*नहीं",
            ),
            emits=("INSTALLATION_PENDING", "INFORM"),
            notes="Installation or partner delay is the blocker.",
        ),
        GrammarRule(
            rule_id="blocker_data_migration",
            patterns=(
                r"stock\s+.*maintain",
                r"stock\s+entry",
                r"data\s+migration",
                r"old\s+data",
                r"excel\s+के\s+through",
                r"item\s+name\s+है\s+quantity\s+है",
            ),
            emits=("INFORM",),
            notes="Data loading or setup work is still pending.",
        ),
        GrammarRule(
            rule_id="blocker_planning_timeline",
            patterns=(
                r"15\s+दिन",
                r"दो\s+दिन",
                r"कल\s+हो\s+जाए",
                r"अभी\s+मैं\s+कुछ\s+भी\s+नहीं\s+कर\s+रहा",
                r"time\s+नहीं",
            ),
            emits=("INFORM",),
            notes="Customer-side planning or time constraint.",
        ),
        GrammarRule(
            rule_id="blocker_refusal",
            patterns=(
                r"नहीं\s+बताना",
                r"skip\s+कर",
                r"पता\s+नहीं",
            ),
            emits=("DENY",),
            notes="User refuses blocker detail.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the blocker explanation becomes a multi-question support conversation.",
    ),
)
