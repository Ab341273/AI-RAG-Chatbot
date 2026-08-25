"""Performance monitoring and timing utilities"""

import time
from services.logging_service import get_logger

logger = get_logger(__name__)

class PerformanceMonitor:
    """Track and log timing of different operations"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.checkpoints = {}

    def start(self):
        """Start timing"""
        self.start_time = time.time()
        logger.info(f"[PERF] {self.operation_name} started")

    def checkpoint(self, name: str):
        """Mark a checkpoint"""
        if self.start_time is None:
            return

        elapsed = time.time() - self.start_time
        self.checkpoints[name] = elapsed
        logger.info(f"[PERF] {self.operation_name} → {name}: {elapsed:.2f}s")

    def end(self):
        """End timing and log total"""
        if self.start_time is None:
            return

        total = time.time() - self.start_time
        logger.info(f"[PERF] {self.operation_name} TOTAL: {total:.2f}s")

        # Print breakdown
        logger.info("[PERF] ━━━ BREAKDOWN ━━━")
        prev_time = 0
        for checkpoint, elapsed in self.checkpoints.items():
            delta = elapsed - prev_time
            logger.info(f"[PERF]   {checkpoint}: {delta:.2f}s (cumulative: {elapsed:.2f}s)")
            prev_time = elapsed

        return total

    def get_summary(self) -> dict:
        """Get timing summary as dict"""
        if self.start_time is None:
            return {}

        total = time.time() - self.start_time
        return {
            "operation": self.operation_name,
            "total_time": total,
            "checkpoints": self.checkpoints,
        }
