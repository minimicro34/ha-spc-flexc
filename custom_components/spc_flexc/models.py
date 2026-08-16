from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AtpState:
    """Last known FlexC ATP state."""

    atp_id: int
    name: str | None = None
    uid: int | None = None

    status: int | None = None
    state: int | None = None
    connect_state: int | None = None

    last_tx_ok_timestamp: datetime | None = None

    @property
    def fault(self) -> bool | None:
        """Return the validated ATP fault state."""
        if self.status is None:
            return None

        if self.status == 1:
            return False

        if self.status == 2:
            return True

        return None

    @property
    def active(self) -> bool | None:
        """Return whether this ATP is an active/connected path."""
        if self.connect_state is None:
            return None

        if self.connect_state in (15, 16):
            return True

        if self.connect_state == 0:
            return False

        return None


@dataclass
class AtsState:
    """Last known FlexC ATS state."""

    ats_id: int
    name: str | None = None

    status: int | None = None
    state: int | None = None

    registration_id: str | None = None
    event_log_count: int | None = None

    atps: dict[int, AtpState] = field(default_factory=dict)

    updated_at: datetime | None = None


@dataclass
class PanelState:
    """Current SPC panel state."""

    battery_voltage: float | None = None
    aux_voltage: float | None = None
    aux_current: float | None = None
    ac_frequency: float | None = None

    rf_type: int | None = None
    rf_version: str | None = None

    internal_bells: bool | None = None
    external_bells: bool | None = None
    engineer_mode: bool | None = None

    installation_name: str | None = None
    spc_type: str | None = None
    spc_variant: str | None = None
    serial_number: str | None = None
    firmware_version: str | None = None
    hardware_version: str | None = None

    raw: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass
class FaultState:
    """Faults obtained from FlexC events or dedicated status commands."""

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
    """Complete SPC state."""

    panel: PanelState = field(default_factory=PanelState)
    faults: FaultState = field(default_factory=FaultState)

    areas: dict[int, dict[str, Any]] = field(default_factory=dict)
    zones: dict[int, dict[str, Any]] = field(default_factory=dict)
    ats: dict[int, AtsState] = field(default_factory=dict)
