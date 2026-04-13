import logging
import time

logger = logging.getLogger("akash.pipeline")


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
