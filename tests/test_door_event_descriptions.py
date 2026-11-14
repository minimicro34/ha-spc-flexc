"""Regression tests for SPC door event diagnostic descriptions."""

import ast
from pathlib import Path


def test_door_event_descriptions_cover_spc_table():
    """All door event IDs 3000-3016 have the expected English labels."""
    source = Path("custom_components/spc_flexc/sensor.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    mapping = next(
        node.value
        for node in module.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "FLEXC_EVENT_DESCRIPTIONS"
    )
    labels = {
        ast.literal_eval(key): ast.literal_eval(value)
        for key, value in zip(mapping.keys, mapping.values, strict=True)
    }
    expected = {
        3000: "Entry granted",
        3001: "Entry denied",
        3002: "Exit granted",
        3003: "Exit denied",
        3004: "Door open too long",
        3005: "Door left open",
        3006: "Door forced",
        3007: "Door normal",
        3008: "Door locked (access denied)",
        3009: "Door unlocked (free access)",
        3010: "Door open too long",
        3011: "Door closed",
        3012: "Door release (DRS)",
        3013: "Door alarm restored",
        3014: "Unknown card",
        3015: "Reader locked",
        3016: "Reader unlocked",
    }
    assert {event_id: labels[event_id] for event_id in range(3000, 3017)} == expected
