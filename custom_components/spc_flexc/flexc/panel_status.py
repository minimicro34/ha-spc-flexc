"""CMD_STATUS_PANEL: panel power, system alert masks and Ethernet (read-only).

``SYSALERT`` carries four 32-bit hex masks (``INPUT``, ``ALERT``, ``INHIBIT``,
``ISOLATE``) and per-bit ``INHIBIT_ALLOWED_<bit value>`` /
``ISOLATE_ALLOWED_<bit value>`` flags. The bit of each alert is not its alert
ID; the table below was mapped on an SPC4300 (firmware 3.14.1) by inhibiting
each alert in turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .flexml import (
    FlexMLError,
    _build_command_envelope,
    _parse_reply_root,
    _validate_reply,
)


@dataclass(frozen=True)
class SystemAlertInfo:
    """One system alert: the panel's alert ID, its SYSALERT bit and a key."""

    alert_id: int
    bit: int
    key: str


SYSTEM_ALERTS: tuple[SystemAlertInfo, ...] = (
    SystemAlertInfo(0, 0, "mains_fault"),
    SystemAlertInfo(1, 1, "battery_fault"),
    SystemAlertInfo(2, 21, "psu_fault"),
    SystemAlertInfo(3, 2, "aux_fuse_fault"),
    SystemAlertInfo(4, 3, "external_bell_fuse_fault"),
    SystemAlertInfo(5, 4, "internal_bell_fuse_fault"),
    SystemAlertInfo(6, 5, "bell_tamper"),
    SystemAlertInfo(7, 6, "cabinet_tamper"),
    SystemAlertInfo(8, 7, "aux_tamper_1"),
    SystemAlertInfo(9, 8, "aux_tamper_2"),
    SystemAlertInfo(10, 9, "antenna_tamper"),
    SystemAlertInfo(11, 10, "rf_jamming"),
    SystemAlertInfo(16, 16, "fail_to_communicate"),
    SystemAlertInfo(20, 15, "xbus_cable_fault"),
    SystemAlertInfo(36, 22, "code_tamper"),
    SystemAlertInfo(37, 23, "ethernet_link"),
    SystemAlertInfo(38, 24, "network_fault"),
)


# Event-driven panel faults (FaultState fields) and the system alert that
# reports the same condition in CMD_STATUS_PANEL.
PANEL_FAULT_ALERTS: dict[str, str] = {
    "mains_fault": "mains_fault",
    "battery_fault": "battery_fault",
    "panel_tamper": "cabinet_tamper",
}


@dataclass(frozen=True)
class SystemAlertState:
    """Flags of one system alert from the SYSALERT masks."""

    active: bool
    alerted: bool
    inhibited: bool
    isolated: bool
    inhibit_allowed: bool | None
    isolate_allowed: bool | None


@dataclass
class PanelStatus:
    """Parsed CMD_STATUS_PANEL reply."""

    alerts: dict[str, SystemAlertState] = field(default_factory=dict)
    ethernet: dict[str, str] = field(default_factory=dict)


def build_status_panel_command(username: str, password: str) -> str:
    """Build CMD_STATUS_PANEL."""
    return _build_command_envelope("<CMD_STATUS_PANEL />", username, password)


def _mask(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def _flag(attributes: dict[str, str], name: str) -> bool | None:
    value = attributes.get(name)
    return None if value is None else value == "1"


def parse_status_panel(response: str) -> PanelStatus:
    """Parse REPLY_STATUS_PANEL into system alert states and Ethernet info."""
    root = _parse_reply_root(response)
    reply = root.find("REPLY_STATUS_PANEL")
    if reply is None:
        raise FlexMLError("REPLY_STATUS_PANEL not found")
    _validate_reply(reply, "REPLY_STATUS_PANEL")
    status = PanelStatus()
    sysalert = reply.find("SYSALERT")
    if sysalert is not None:
        attributes = dict(sysalert.attrib)
        parsed = [
            _mask(attributes.get(name))
            for name in ("INPUT", "ALERT", "INHIBIT", "ISOLATE")
        ]
        masks = [mask for mask in parsed if mask is not None]
        if len(masks) == 4:
            for alert in SYSTEM_ALERTS:
                bit = 1 << alert.bit
                active, alerted, inhibited, isolated = (
                    bool(mask & bit) for mask in masks
                )
                status.alerts[alert.key] = SystemAlertState(
                    active=active,
                    alerted=alerted,
                    inhibited=inhibited,
                    isolated=isolated,
                    inhibit_allowed=_flag(attributes, f"INHIBIT_ALLOWED_{bit}"),
                    isolate_allowed=_flag(attributes, f"ISOLATE_ALLOWED_{bit}"),
                )
    ethernet = reply.find("ETHERNETINFO")
    if ethernet is not None:
        status.ethernet = dict(ethernet.attrib)
    return status
