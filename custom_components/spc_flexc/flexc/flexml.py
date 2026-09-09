"""FLEXML command builders and parsers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import quoteattr


class FlexMLError(Exception):
    """Base FLEXML exception."""


class FlexMLReplyError(FlexMLError):
    """FLEXML command returned an error."""


@dataclass(frozen=True, slots=True)
class FlexMLDiscoveryResult:
    """Result of a discovery status batch."""

    statuses: list[dict[str, str]]
    boundary_reached: bool = False


def _build_command_envelope(commands: str, username: str, password: str) -> str:
    """Build an authenticated FLEXML command envelope."""
    return (
        '<FLEXML_CMD VER="1.0" '
        f"PANEL_USERNAME={quoteattr(username)} "
        f"PANEL_PASSWORD={quoteattr(password)}>"
        f"{commands}"
        "</FLEXML_CMD>"
    )


def build_panel_summary_command(username: str, password: str) -> str:
    """Build CMD_GET_PANEL_SUMMARY."""
    return _build_command_envelope("<CMD_GET_PANEL_SUMMARY />", username, password)


def build_zone_status_command(zone_id: int, username: str, password: str) -> str:
    """Build one CMD_GET_ZONE_STATUS command."""
    return _build_command_envelope(
        f'<CMD_GET_ZONE_STATUS ZONE_ID="{zone_id}" />', username, password
    )


def build_zone_status_batch(zone_ids: Iterable[int], username: str, password: str) -> str:
    """Build a batch of CMD_GET_ZONE_STATUS commands."""
    body = "".join(f'<CMD_GET_ZONE_STATUS ZONE_ID="{zone_id}" />' for zone_id in zone_ids)
    return _build_command_envelope(body, username, password)


def build_zone_control_command(zone_id: int, action: int, username: str, password: str) -> str:
    """Build validated CMD_ZONE_CONTROL (0=inhibit, 1=deinhibit)."""
    if action not in (0, 1):
        raise ValueError("Only validated zone actions 0 (inhibit) and 1 (deinhibit) are supported")
    return _build_command_envelope(
        f'<CMD_ZONE_CONTROL ZONE_ID="{zone_id}" ACTION="{action}" />', username, password
    )


def build_area_status_command(area_id: int, username: str, password: str) -> str:
    """Build one CMD_GET_AREA_STATUS command."""
    return _build_command_envelope(f'<CMD_GET_AREA_STATUS AREA_ID="{area_id}" />', username, password)


def build_area_status_batch(area_ids: Iterable[int], username: str, password: str) -> str:
    """Build a batch of CMD_GET_AREA_STATUS commands."""
    body = "".join(f'<CMD_GET_AREA_STATUS AREA_ID="{area_id}" />' for area_id in area_ids)
    return _build_command_envelope(body, username, password)


def build_door_status_batch(door_ids: Iterable[int], username: str, password: str) -> str:
    """Build a batch of CMD_GET_DOOR_STATUS commands."""
    body = "".join(f'<CMD_GET_DOOR_STATUS DOOR_ID="{door_id}" />' for door_id in door_ids)
    return _build_command_envelope(body, username, password)


def build_door_control_command(door_id: int, action: int, username: str, password: str) -> str:
    """Build CMD_DOOR_CONTROL using actions recovered from Vanderbilt SPCLink."""
    if action not in (5, 6, 7, 8):
        raise ValueError("Door action must be 5 (open temporarily), 6 (open permanently), 7 (set normal), or 8 (lock)")
    return _build_command_envelope(
        f'<CMD_DOOR_CONTROL DOOR_ID="{door_id}" ACTION="{action}" />', username, password
    )


def build_mg_status_command(username: str, password: str) -> str:
    """Build aggregate Mapping Gate discovery/status command."""
    return _build_command_envelope('<CMD_GET_MG_STATUS MG_ID="0" />', username, password)


def build_mg_control_command(mg_id: int, action: int, username: str, password: str) -> str:
    """Build validated Mapping Gate control command (0=off, 1=on)."""
    if action not in (0, 1):
        raise ValueError("Mapping Gate action must be 0 (off) or 1 (on)")
    return _build_command_envelope(
        f'<CMD_MG_CONTROL MG_ID="{mg_id}" ACTION="{action}" />', username, password
    )


def build_alert_status_command(username: str, password: str) -> str:
    """Build CMD_GET_ALERT_STATUS."""
    return _build_command_envelope("<CMD_GET_ALERT_STATUS />", username, password)


def _parse_reply_root(response: str) -> ET.Element:
    """Parse and validate a FLEXML_REPLY root element."""
    try:
        root = ET.fromstring(response)
    except ET.ParseError as err:
        raise FlexMLError("Invalid FLEXML reply") from err
    if root.tag != "FLEXML_REPLY":
        raise FlexMLError(f"Expected FLEXML_REPLY, received {root.tag}")
    return root


def _validate_reply(reply: ET.Element, expected_tag: str) -> None:
    """Validate RESULT and CMD_RESULT on a reply element."""
    if reply.tag != expected_tag:
        raise FlexMLError(f"Expected {expected_tag}, received {reply.tag}")
    result = reply.get("RESULT")
    command_result = reply.get("CMD_RESULT")
    if result != "0" or command_result != "OK":
        raise FlexMLReplyError(f"{expected_tag} failed: RESULT={result!r}, CMD_RESULT={command_result!r}")


def _parse_status_discovery(response: str, reply_tag: str, status_tag: str) -> FlexMLDiscoveryResult:
    """Parse a discovery batch while preserving the RESULT=102 boundary."""
    root = _parse_reply_root(response)
    statuses: list[dict[str, str]] = []
    boundary_reached = False
    for reply in root.findall(reply_tag):
        if reply.get("RESULT") == "102":
            boundary_reached = True
            continue
        _validate_reply(reply, reply_tag)
        status = reply.find(status_tag)
        if status is not None:
            statuses.append(dict(status.attrib))
    return FlexMLDiscoveryResult(statuses, boundary_reached)


def parse_panel_summary(response: str) -> dict[str, str]:
    """Parse REPLY_GET_PANEL_SUMMARY."""
    root = _parse_reply_root(response)
    reply = root.find("REPLY_GET_PANEL_SUMMARY")
    if reply is None:
        raise FlexMLError("REPLY_GET_PANEL_SUMMARY not found")
    _validate_reply(reply, "REPLY_GET_PANEL_SUMMARY")
    summary = reply.find("PANEL_SUMMARY")
    if summary is None:
        raise FlexMLError("PANEL_SUMMARY not found")
    return dict(summary.attrib)


def parse_zone_status_discovery(response: str) -> FlexMLDiscoveryResult:
    return _parse_status_discovery(response, "REPLY_GET_ZONE_STATUS", "ZONE_STATUS")


def parse_zone_status(response: str) -> list[dict[str, str]]:
    return parse_zone_status_discovery(response).statuses


def parse_zone_control(response: str, zone_id: int) -> None:
    root = _parse_reply_root(response)
    reply = root.find("REPLY_ZONE_CONTROL")
    if reply is None:
        raise FlexMLError("REPLY_ZONE_CONTROL not found")
    _validate_reply(reply, "REPLY_ZONE_CONTROL")
    result = reply.find("ZONE_CONTROL")
    if result is None:
        raise FlexMLError("ZONE_CONTROL not found")
    returned_zone_id = result.get("ZONE_ID")
    if returned_zone_id != str(zone_id):
        raise FlexMLError(f"ZONE_CONTROL returned unexpected ZONE_ID={returned_zone_id!r}")
    if result.get("RESULT") != "0":
        raise FlexMLReplyError(f"ZONE_CONTROL failed: RESULT={result.get('RESULT')!r}")


def parse_area_status_discovery(response: str) -> FlexMLDiscoveryResult:
    return _parse_status_discovery(response, "REPLY_GET_AREA_STATUS", "AREA_STATUS")


def parse_area_status(response: str) -> list[dict[str, str]]:
    return parse_area_status_discovery(response).statuses


def parse_door_status_discovery(response: str) -> FlexMLDiscoveryResult:
    return _parse_status_discovery(response, "REPLY_GET_DOOR_STATUS", "DOOR_STATUS")


def parse_door_status(response: str) -> list[dict[str, str]]:
    return parse_door_status_discovery(response).statuses


def parse_door_control(response: str) -> None:
    root = _parse_reply_root(response)
    reply = root.find("REPLY_DOOR_CONTROL")
    if reply is None:
        raise FlexMLError("REPLY_DOOR_CONTROL not found")
    _validate_reply(reply, "REPLY_DOOR_CONTROL")


def parse_mg_status(response: str) -> list[dict[str, str]]:
    """Parse all Mapping Gates returned by aggregate MG_ID=0 status."""
    root = _parse_reply_root(response)
    reply = root.find("REPLY_GET_MG_STATUS")
    if reply is None:
        raise FlexMLError("REPLY_GET_MG_STATUS not found")
    _validate_reply(reply, "REPLY_GET_MG_STATUS")
    return [dict(status.attrib) for status in reply.findall("MG_STATUS")]


def parse_mg_control(response: str, mg_id: int) -> None:
    """Validate a real-panel REPLY_MG_CONTROL response."""
    root = _parse_reply_root(response)
    reply = root.find("REPLY_MG_CONTROL")
    if reply is None:
        raise FlexMLError("REPLY_MG_CONTROL not found")
    _validate_reply(reply, "REPLY_MG_CONTROL")
    result = reply.find("MG_CONTROL")
    if result is None:
        raise FlexMLError("MG_CONTROL not found")
    if result.get("MG_ID") != str(mg_id):
        raise FlexMLError(f"MG_CONTROL returned unexpected MG_ID={result.get('MG_ID')!r}")
    if result.get("RESULT") != "0":
        raise FlexMLReplyError(f"MG_CONTROL failed: RESULT={result.get('RESULT')!r}")


def build_flexc_ats_status_command(ats_id: int, username: str, password: str) -> str:
    return _build_command_envelope(f'<CMD_GET_FLEXC_ATS_STATUS ATS_ID="{ats_id}" />', username, password)


def parse_flexc_ats_status(response: str) -> dict[str, Any]:
    root = _parse_reply_root(response)
    reply = root.find("REPLY_GET_FLEXC_ATS_STATUS")
    if reply is None:
        raise FlexMLError("REPLY_GET_FLEXC_ATS_STATUS not found")
    _validate_reply(reply, "REPLY_GET_FLEXC_ATS_STATUS")
    status = reply.find("FLEXC_ATS_STATUS")
    if status is None:
        raise FlexMLError("FLEXC_ATS_STATUS not found")
    result: dict[str, Any] = {"ats": dict(status.attrib), "atps": []}
    for atp in status.findall("FLEXC_ATP_STATUS"):
        result["atps"].append(dict(atp.attrib))
    return result


def parse_alert_status(response: str) -> list[dict[str, str]]:
    root = _parse_reply_root(response)
    reply = root.find("REPLY_GET_ALERT_STATUS")
    if reply is None:
        raise FlexMLError("REPLY_GET_ALERT_STATUS not found")
    _validate_reply(reply, "REPLY_GET_ALERT_STATUS")
    return [dict(element.attrib) for element in reply if element.attrib]
