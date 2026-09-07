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


def _build_command_envelope(
    commands: str,
    username: str,
    password: str,
) -> str:
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


def build_zone_status_command(
    zone_id: int,
    username: str,
    password: str,
) -> str:
    """Build one CMD_GET_ZONE_STATUS command."""
    return _build_command_envelope(
        f'<CMD_GET_ZONE_STATUS ZONE_ID="{zone_id}" />', username, password
    )


def build_zone_status_batch(
    zone_ids: Iterable[int],
    username: str,
    password: str,
) -> str:
    """Build a batch of CMD_GET_ZONE_STATUS commands."""
    body = "".join(
        f'<CMD_GET_ZONE_STATUS ZONE_ID="{zone_id}" />' for zone_id in zone_ids
    )
    return _build_command_envelope(body, username, password)


def build_area_status_command(
    area_id: int,
    username: str,
    password: str,
) -> str:
    """Build one CMD_GET_AREA_STATUS command."""
    return _build_command_envelope(
        f'<CMD_GET_AREA_STATUS AREA_ID="{area_id}" />', username, password
    )


def build_area_status_batch(
    area_ids: Iterable[int],
    username: str,
    password: str,
) -> str:
    """Build a batch of CMD_GET_AREA_STATUS commands."""
    body = "".join(
        f'<CMD_GET_AREA_STATUS AREA_ID="{area_id}" />' for area_id in area_ids
    )
    return _build_command_envelope(body, username, password)


def build_door_status_batch(
    door_ids: Iterable[int],
    username: str,
    password: str,
) -> str:
    """Build a batch of CMD_GET_DOOR_STATUS commands."""
    body = "".join(
        f'<CMD_GET_DOOR_STATUS DOOR_ID="{door_id}" />' for door_id in door_ids
    )
    return _build_command_envelope(body, username, password)


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
        raise FlexMLReplyError(
            f"{expected_tag} failed: RESULT={result!r}, CMD_RESULT={command_result!r}"
        )


def _parse_status_discovery(
    response: str,
    reply_tag: str,
    status_tag: str,
) -> FlexMLDiscoveryResult:
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
    """Parse zone status discovery replies."""
    return _parse_status_discovery(response, "REPLY_GET_ZONE_STATUS", "ZONE_STATUS")


def parse_zone_status(response: str) -> list[dict[str, str]]:
    """Parse one or more REPLY_GET_ZONE_STATUS elements."""
    return parse_zone_status_discovery(response).statuses


def parse_area_status_discovery(response: str) -> FlexMLDiscoveryResult:
    """Parse area status discovery replies."""
    return _parse_status_discovery(response, "REPLY_GET_AREA_STATUS", "AREA_STATUS")


def parse_area_status(response: str) -> list[dict[str, str]]:
    """Parse valid REPLY_GET_AREA_STATUS elements."""
    return parse_area_status_discovery(response).statuses


def parse_door_status_discovery(response: str) -> FlexMLDiscoveryResult:
    """Parse door status discovery replies."""
    return _parse_status_discovery(response, "REPLY_GET_DOOR_STATUS", "DOOR_STATUS")


def parse_door_status(response: str) -> list[dict[str, str]]:
    """Parse valid REPLY_GET_DOOR_STATUS elements."""
    return parse_door_status_discovery(response).statuses


def build_flexc_ats_status_command(
    ats_id: int,
    username: str,
    password: str,
) -> str:
    """Build CMD_GET_FLEXC_ATS_STATUS."""
    return _build_command_envelope(
        f'<CMD_GET_FLEXC_ATS_STATUS ATS_ID="{ats_id}" />', username, password
    )


def parse_flexc_ats_status(response: str) -> dict[str, Any]:
    """Parse REPLY_GET_FLEXC_ATS_STATUS."""
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
    """Parse current SPC alert objects."""
    root = _parse_reply_root(response)
    reply = root.find("REPLY_GET_ALERT_STATUS")
    if reply is None:
        raise FlexMLError("REPLY_GET_ALERT_STATUS not found")

    _validate_reply(reply, "REPLY_GET_ALERT_STATUS")
    return [dict(element.attrib) for element in reply if element.attrib]
