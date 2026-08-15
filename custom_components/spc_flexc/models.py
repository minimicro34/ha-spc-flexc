from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class PanelState:
    battery_voltage: float | None = None
    aux_voltage: float | None = None
    aux_current: float | None = None
    ac_frequency: float | None = None
    rf_type: int | None = None
    rf_version: str | None = None
    internal_bells: bool | None = None
    external_bells: bool | None = None
    engineer_mode: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None

@dataclass
class FaultState:
    modem_1_fault: bool | None = None
    modem_1_line_fault: bool | None = None
    modem_2_fault: bool | None = None
    modem_2_line_fault: bool | None = None
    rf_jamming: bool | None = None
    xbus_mains_fault: bool | None = None
    xbus_battery_fault: bool | None = None
    last_event: dict[str, Any] | None = None

@dataclass
class SpcState:
    panel: PanelState = field(default_factory=PanelState)
    faults: FaultState = field(default_factory=FaultState)
    areas: dict[int, dict[str, Any]] = field(default_factory=dict)
    zones: dict[int, dict[str, Any]] = field(default_factory=dict)
