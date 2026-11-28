"""Read-only FLEXML log commands: access, system, zone and FlexC ATS event logs.

Each log is read with one command and returned as a list of records. Only the
fields listed for a log are kept. Card data (card number, format, bit count)
and the panel's undecoded fields (the system log's ``RAW``, the ATP log's
``DATA``) are not returned, because their content cannot be checked. Free-text
fields are returned as the panel writes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any
from xml.sax.saxutils import quoteattr

from .flexml import (
    FlexMLError,
    _build_command_envelope,
    _parse_reply_root,
    _validate_reply,
)


class LogReadBusy(Exception):
    """Another log read for the same panel is still running."""


@dataclass(frozen=True)
class LogKind:
    """How to request and read one panel log."""

    command: str
    id_attribute: str | None
    reply_tag: str
    record_tag: str
    time_field: str
    # Panel attribute -> (output key, "int" | "str")
    fields: dict[str, tuple[str, str]]
    # Optional second attribute (the ATP within an ATS); defaults to 1.
    sub_id_attribute: str | None = None
    # Fixed attributes the panel needs but ignores.
    fixed_attributes: str = ""


_EVENT_FIELDS: dict[str, tuple[str, str]] = {
    "EV_ID": ("event_id", "int"),
    "EV_SEQ": ("sequence", "int"),
    "EV_GRP": ("event_group", "int"),
    "EV_DESC": ("text", "str"),
    "SIA_CODE": ("sia_code", "str"),
    "SIA_ADDRESS": ("sia_address", "str"),
    "CID_CODE": ("cid_code", "str"),
    "CID_QUAL": ("cid_qualifier", "str"),
    "AREA_ID": ("area_id", "int"),
    "AREA_NAME": ("area_name", "str"),
    "ZONE_ID": ("zone_id", "int"),
    "ZONE_NAME": ("zone_name", "str"),
    "DOOR_ID": ("door_id", "int"),
    "DOOR_NAME": ("door_name", "str"),
    "MG_ID": ("mapping_gate_id", "int"),
    "MG_NAME": ("mapping_gate_name", "str"),
    "KEYPAD_ID": ("keypad_id", "int"),
    "KEYPAD_NAME": ("keypad_name", "str"),
    "USER_ID": ("user_id", "int"),
    "USER_NAME": ("user_name", "str"),
    "ACC_DENIED_REASON": ("access_denied_reason", "int"),
}

LOG_KINDS: dict[str, LogKind] = {
    "access": LogKind(
        command="GET_ACCESS_LOG",
        id_attribute="DOOR_ID",
        reply_tag="REPLY_GET_ACCESS_LOG",
        record_tag="ACCESS_LOG_EVENT",
        time_field="TIME",
        fields={
            "TYPE": ("type", "int"),
            "DETAIL": ("detail", "int"),
            "DOOR_ID": ("door_id", "int"),
            "DOOR_NAME": ("door_name", "str"),
            "USER_ID": ("user_id", "int"),
            "USER_NAME": ("user_name", "str"),
            "LOG_TEXT": ("text", "str"),
        },
    ),
    "system": LogKind(
        command="GET_SYSTEM_LOG",
        id_attribute=None,
        reply_tag="REPLY_GET_SYSTEM_LOG",
        record_tag="SYSTEM_LOG_EVENT",
        time_field="TIME",
        fields={"TEXT": ("text", "str")},
    ),
    "zone": LogKind(
        command="GET_ZONE_LOG",
        id_attribute="ZONE_ID",
        reply_tag="REPLY_GET_ZONE_LOG",
        record_tag="ZONE_LOG_EVENT",
        time_field="TIME",
        fields={
            "ZONE_ID": ("zone_id", "int"),
            "INPUT": ("input", "int"),
            "RESISTANCE": ("resistance", "int"),
        },
    ),
    # The panel answers 102 without attributes; any SENSOR_ID returns the
    # whole wireless log (newest 30 lines of all sensors; checked on an
    # SPC4300 with its built-in receiver, 2026-11-11). SENSOR_ID in a record
    # is the sensor's radio ID.
    "wireless": LogKind(
        command="GET_WIRELESS_LOG",
        id_attribute=None,
        reply_tag="REPLY_GET_WIRELESS_LOG",
        record_tag="WIRELESS_LOG_EVENT",
        time_field="TIME",
        fields={
            "SENSOR_ID": ("radio_id", "str"),
            "STATUS": ("status", "int"),
            "BATTERY": ("battery", "int"),
            "SIGNAL": ("signal", "int"),
            "RECEIVER_ID": ("receiver_id", "int"),
        },
        fixed_attributes=' SENSOR_ID="1"',
    ),
    "ats": LogKind(
        command="GET_FLEXC_ATS_EVENT_LOG",
        id_attribute="ATS_ID",
        reply_tag="REPLY_GET_FLEXC_ATS_EVENT_LOG",
        record_tag="ATS_EVENT_LOG",
        time_field="TIMESTAMP",
        fields=_EVENT_FIELDS,
    ),
    "ats_network": LogKind(
        command="GET_FLEXC_ATS_NETWORK_LOG",
        id_attribute="ATS_ID",
        reply_tag="REPLY_GET_FLEXC_ATS_NETWORK_LOG",
        record_tag="ATS_NETWORK_LOG",
        time_field="TIMESTAMP",
        fields={
            "ATS_ID": ("ats_id", "int"),
            "MSG_ID": ("message_id", "int"),
            "NETWORK_LOG_MESSAGE": ("text", "str"),
        },
    ),
    "atp": LogKind(
        command="GET_FLEXC_ATP_LOG",
        id_attribute="ATS_ID",
        sub_id_attribute="ATP_SEQ_ID",
        reply_tag="REPLY_GET_FLEXC_ATP_LOG",
        record_tag="ATP_LOG",
        time_field="TIMESTAMP",
        fields={
            "ATS_ID": ("ats_id", "int"),
            "ATP_SEQ_ID": ("atp", "int"),
            "MSG_ID": ("message_id", "int"),
            "ATP_LOG_MESSAGE": ("text", "str"),
        },
    ),
    "atp_network": LogKind(
        command="GET_FLEXC_ATP_NETWORK_LOG",
        id_attribute="ATS_ID",
        sub_id_attribute="ATP_SEQ_ID",
        reply_tag="REPLY_GET_FLEXC_ATP_NETWORK_LOG",
        record_tag="ATP_NETWORK_LOG",
        time_field="TIMESTAMP",
        fields={
            "ATS_ID": ("ats_id", "int"),
            "ATP_SEQ_ID": ("atp", "int"),
            "MSG_ID": ("message_id", "int"),
            "NETWORK_LOG_MESSAGE": ("text", "str"),
        },
    ),
}

# Access log TYPE values seen on an SPC4300 (firmware 3.14.1), named as the
# panel web page's access log shows them.
ACCESS_LOG_TYPES: dict[int, str] = {
    1: "granted",
    2: "denied",
    5: "door_release",
    6: "door_left_open",
    8: "forced_open",
    9: "door_normal",
    10: "door_blocked",
    11: "door_unlocked",
    20: "invalid_format",
    # Mapped 2026-11-13 against the web page's access log. 25 is "Spärrad
    # pga felaktig kod" on the web page, although LOG_TEXT says granted.
    24: "unknown_card",
    25: "code_lockout",
}


def build_log_command(
    kind: str,
    object_id: int | None,
    username: str,
    password: str,
    sub_id: int | None = None,
) -> str:
    """Build the read command for one log."""
    log = LOG_KINDS[kind]
    attributes = ""
    if log.id_attribute is not None:
        if object_id is None:
            raise ValueError(f"The {kind} log needs {log.id_attribute}")
        attributes = f" {log.id_attribute}={quoteattr(str(int(object_id)))}"
    if log.sub_id_attribute is not None:
        attributes += f" {log.sub_id_attribute}={quoteattr(str(int(sub_id or 1)))}"
    attributes += log.fixed_attributes
    return _build_command_envelope(
        f"<CMD_{log.command}{attributes} />", username, password
    )


def _convert(value: str, kind: str) -> Any:
    if kind == "int":
        try:
            return int(value.strip())
        except ValueError:
            return None
    return value.strip()


def _panel_time(value: str | None, timezone: tzinfo) -> datetime | None:
    """Return a panel time stamp (``HHMMSSDDMMYYYY``) in ``timezone``.

    The panel's time stamps carry no time zone. They are read as local time in
    the time zone given (Home Assistant's), which assumes the panel's clock is
    set to the same local time. A missing or invalid time gives ``None``.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%H%M%S%d%m%Y").replace(tzinfo=timezone)
    except ValueError:
        return None


def parse_log(response: str, kind: str, timezone: tzinfo) -> list[dict[str, Any]]:
    """Return the records of one log, newest first, with whitelisted fields."""
    log = LOG_KINDS[kind]
    root = _parse_reply_root(response)
    reply = root.find(log.reply_tag)
    if reply is None:
        raise FlexMLError(f"{log.reply_tag} not found")
    _validate_reply(reply, log.reply_tag)
    records: list[tuple[datetime | None, int, dict[str, Any]]] = []
    for index, element in enumerate(reply.findall(log.record_tag)):
        time = _panel_time(element.get(log.time_field), timezone)
        record: dict[str, Any] = {"time": None if time is None else time.isoformat()}
        for source, (key, value_kind) in log.fields.items():
            if (value := element.get(source)) is not None:
                record[key] = _convert(value, value_kind)
        if kind == "access" and isinstance(record.get("type"), int):
            record["type_name"] = ACCESS_LOG_TYPES.get(record["type"])
        records.append((time, index, record))
    # Newest first; records without a time keep their panel order at the end.
    dated = sorted(
        (item for item in records if item[0] is not None),
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )
    undated = [item for item in records if item[0] is None]
    return [record for _, _, record in dated + undated]
