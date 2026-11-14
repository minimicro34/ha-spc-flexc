"""Tests for PIR slow-read thresholds, history and warning cooldown."""

import logging

from custom_components.spc_flexc.pir_diagnostics import (
    PirSlowReadHistory,
    slow_read_log_level,
)


def test_slow_read_thresholds():
    assert slow_read_log_level(999.9) is None
    assert slow_read_log_level(1000) == logging.DEBUG
    assert slow_read_log_level(1499.9) == logging.DEBUG
    assert slow_read_log_level(1500) == logging.INFO
    assert slow_read_log_level(1999.9) == logging.INFO
    assert slow_read_log_level(2000) == logging.WARNING


def _record(history, now, duration=1100):
    return history.record(
        duration,
        now=now,
        interval_ms=1000,
        lock_wait_ms=0,
        resync_wait_ms=0,
        batches=[(1, 28, duration)],
    )


def test_burst_warning_and_cooldown():
    history = PirSlowReadHistory()
    assert _record(history, 100) is None
    assert _record(history, 120, 1250) is None
    assert _record(history, 140, 1700) == (3, 1700)
    assert _record(history, 150) is None
    assert _record(history, 741) is None
    assert _record(history, 742) is None
    assert _record(history, 743) == (3, 1100)


def test_hour_expiry_and_newest_first():
    history = PirSlowReadHistory()
    _record(history, 0, 1200)
    _record(history, 10, 1500)
    assert history.snapshot(now=10)["count"] == 2
    assert history.snapshot(now=10)["slow_reads"][0]["read_ms"] == 1500
    assert history.snapshot(now=3600)["count"] == 1
    assert history.snapshot(now=3610) == {
        "count": 0,
        "max_read_ms": None,
        "slow_reads": [],
    }


def test_fast_reads_are_not_recorded():
    history = PirSlowReadHistory()
    assert _record(history, 1, 999) is None
    assert history.snapshot(now=1)["count"] == 0
