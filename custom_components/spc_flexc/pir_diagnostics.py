"""Bounded, in-memory PIR slow-read diagnostics."""

from collections import deque
from datetime import UTC, datetime
import logging
from time import monotonic

SLOW_READ_MS = 1000.0
HISTORY_SECONDS = 3600.0
BURST_SECONDS = 60.0
WARNING_COOLDOWN_SECONDS = 600.0
MAX_HISTORY = 240


def slow_read_log_level(read_ms: float) -> int | None:
    """Classify actual zone-read time, independently of resync or lock waits."""
    if read_ms >= 2000:
        return logging.WARNING
    if read_ms >= 1500:
        return logging.INFO
    if read_ms >= SLOW_READ_MS:
        return logging.DEBUG
    return None


class PirSlowReadHistory:
    """Store slow reads and detect recurring slow batches without I/O."""

    def __init__(self) -> None:
        self._reads: deque[tuple[float, dict]] = deque(maxlen=MAX_HISTORY)
        self._last_burst_warning: float | None = None

    def prune(self, now: float | None = None) -> None:
        """Remove entries outside the trailing hour."""
        now = monotonic() if now is None else now
        while self._reads and now - self._reads[0][0] >= HISTORY_SECONDS:
            self._reads.popleft()

    def record(
        self,
        read_ms: float,
        *,
        interval_ms: float | None,
        lock_wait_ms: float,
        resync_wait_ms: float,
        batches: list[tuple[int, int, float]],
        now: float | None = None,
    ) -> tuple[int, float] | None:
        """Record a slow read; return (burst count, max ms) if warning is due."""
        now = monotonic() if now is None else now
        self.prune(now)
        if read_ms < SLOW_READ_MS:
            return None
        self._reads.append(
            (
                now,
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "read_ms": round(read_ms, 1),
                    "interval_ms": round(interval_ms, 1)
                    if interval_ms is not None
                    else None,
                    "lock_wait_ms": round(lock_wait_ms, 1),
                    "resync_wait_ms": round(resync_wait_ms, 1),
                    "batches": [list(batch) for batch in batches],
                },
            )
        )
        burst = [
            item["read_ms"]
            for recorded_at, item in self._reads
            if now - recorded_at < BURST_SECONDS
        ]
        if len(burst) < 3:
            return None
        if (
            self._last_burst_warning is not None
            and now - self._last_burst_warning < WARNING_COOLDOWN_SECONDS
        ):
            return None
        self._last_burst_warning = now
        return len(burst), max(burst)

    def snapshot(self, now: float | None = None) -> dict:
        """Return the rolling count, maximum and newest-first event history."""
        self.prune(now)
        reads = [item for _, item in reversed(self._reads)]
        return {
            "count": len(reads),
            "max_read_ms": max((item["read_ms"] for item in reads), default=None),
            "slow_reads": reads,
        }
