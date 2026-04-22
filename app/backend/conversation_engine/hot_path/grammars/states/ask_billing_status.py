from conversation_engine.hot_path.grammars.base import GrammarRule, StateGrammar


GRAMMAR = StateGrammar(
    state_name="ASK_BILLING_STATUS",
    description="Deterministic billing-status detection with training and installation interrupts.",
    ordered_rules=(
        GrammarRule(
            rule_id="billing_started_training_pending",
            patterns=(
                r"बिलिंग\s+तो\s+(?:स्टार्ट|start|शुरू)\s+हो\s+गई\s+है\s+पर\s+(?:training|ट्रेनिंग)\s+नहीं\s+हुई\s+है",
                r"(?:बिलिंग|billing)\s+(?:तो\s+)?start\s+हो\s+गई\s+है\s+पर\s+(?:training|ट्रेनिंग)\s+नहीं\s+हुई\s+है",
                r"(?:बिलिंग|billing)\s+(?:तो\s+)?(?:स्टार्ट|start|शुरू)\s+हो\s+गई\s+है\s+लेकिन\s+(?:training|ट्रेनिंग)\s+नहीं\s+हुई\s+है",
                r"बिलिंग\s+चालू\s+है\s+लेकिन\s+(?:training|ट्रेनिंग)\s+नहीं\s+हुई",
                r"बिलिंग\s+हो\s+रही\s+है\s+पर\s+(?:training|ट्रेनिंग)\s+बाकी\s+है",
            ),
            emits=("BILLING_STARTED", "TRAINING_PENDING"),
            notes="Training interrupt must win even though billing has started.",
        ),
        GrammarRule(
            rule_id="billing_not_started_installation_pending",
            patterns=(
                r"software\s+ही\s+install\s+नहीं\s+हुआ\s+है",
                r"अभी\s+तक\s+install\s+नहीं\s+हुआ\s+है",
                r"system\s+में\s+install\s+नहीं\s+हुआ\s+है",
                r"अभी\s+तक\s+तो\s+अपना\s+software\s+ही\s+install\s+नहीं\s+हुआ\s+है",
            ),
            emits=("BILLING_NOT_STARTED", "INSTALLATION_PENDING"),
            notes="Installation blocker is explicit and should bypass generic probing.",
        ),
        GrammarRule(
            rule_id="billing_started",
            patterns=(
                r"billing\s+start\s+हो\s+गई\s+है",
                r"बिलिंग\s+(?:स्टार्ट|शुरू)\s+हो\s+गई\s+है",
                r"बिलिंग\s+चालू\s+है",
                r"हाँ\s+बिलिंग\s+हो\s+रही\s+है",
                r"madam\s+हो\s+गई\s+है\s+billing\s+start",
            ),
            emits=("BILLING_STARTED", "INFORM"),
            notes="Billing is active.",
        ),
        GrammarRule(
            rule_id="billing_not_started",
            patterns=(
                r"बिलिंग\s+(?:मैम\s+)?start\s+नहीं\s+हुई\s+है",
                r"बिलिंग\s+स्टार्ट\s+नहीं\s+हुई\s+है",
                r"बिलिंग\s+शुरू\s+नहीं\s+हुई",
                r"अभी\s+तक\s+नहीं\s+हुई",
                r"अभी\s+चालू\s+नहीं\s+है",
                r"नहीं\s+मैम\s+अभी\s+तो\s+billing\s+मैंने\s+start\s+नहीं\s+करी\s+है",
            ),
            emits=("BILLING_NOT_STARTED", "DENY"),
            notes="Billing has not started yet.",
        ),
    ),
    cold_path_trigger_notes=(
        "Route to cold path if the user gives multiple blockers and no primary ownership signal is visible.",
    ),
)
