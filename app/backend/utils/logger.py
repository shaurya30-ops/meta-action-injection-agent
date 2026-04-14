import logging
import time

logger = logging.getLogger("आकृति.pipeline")


class PipelineLogger:
    """Structured logging for each pipeline stage with latency tracking."""

    def __init__(self):
        self._timers: dict[str, float] = {}

    def start(self, stage: str):
        self._timers[stage] = time.perf_counter()

    def end(self, stage: str, **extra):
        elapsed_ms = (time.perf_counter() - self._timers.pop(stage, time.perf_counter())) * 1000
        parts = [f"[{stage}] {elapsed_ms:.1f}ms"]
        for k, v in extra.items():
            parts.append(f"{k}={v}")
        logger.info(" | ".join(parts))
        return elapsed_ms

    def log_transition(self, prev_state, intent, next_state):
        logger.info(f"[TRANSITION] {prev_state} + {intent} -> {next_state}")

    def log_auto_chain(self, chain):
        logger.info(f"[AUTO-CHAIN] {' -> '.join(str(s) for s in chain)}")

    def log_fallback(self, state, count):
        logger.warning(f"[FALLBACK] State={state}, count={count}")

    def log_error(self, stage: str, error: Exception):
        logger.error(f"[{stage}] ERROR: {error}")


pipeline_logger = PipelineLogger()

import json
from pathlib import Path

# Setup metrics logger that writes ONLY to logs.log
metrics_logger = logging.getLogger("आकृति.metrics")
metrics_logger.setLevel(logging.INFO)
metrics_logger.propagate = False  # Don't pass up to terminal logger

logs_file_path = Path(__file__).resolve().parents[3] / "logs.log"
metrics_handler = logging.FileHandler(logs_file_path, encoding="utf-8")
metrics_handler.setFormatter(logging.Formatter("%(message)s"))
if not metrics_logger.handlers:
    metrics_logger.addHandler(metrics_handler)

def log_metric(agent_metric):
    """Log an AgentMetric to logs.log"""
    if hasattr(agent_metric, "dict"):
        data = agent_metric.dict()
    elif hasattr(agent_metric, "model_dump"):
        data = agent_metric.model_dump()
    else:
        data = vars(agent_metric)
        
    metrics_logger.info(json.dumps(data, ensure_ascii=False))
