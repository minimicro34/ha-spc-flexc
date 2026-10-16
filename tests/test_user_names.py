"""Tests for safe SPC user display aliases."""

import pytest

from custom_components.spc_flexc.user_names import (
    display_user_name,
    parse_user_aliases,
)


def test_parse_user_aliases():
    assert parse_user_aliases("9995=Home Assistant\n1=Nicolas\n") == {
        "9995": "Home Assistant",
        "1": "Nicolas",
    }


@pytest.mark.parametrize("value", ["wrong", "foo=Name", "1=", "1=" + "x" * 101])
def test_invalid_aliases(value):
    with pytest.raises(ValueError):
        parse_user_aliases(value)


def test_display_name_priority():
    aliases = {"9995": "Home Assistant"}
    assert display_user_name(9995, "Utilis.Profil Co", aliases) == "Home Assistant"
    assert (
        display_user_name(1, "Event name", aliases, {1: "Panel name"}) == "Panel name"
    )
    assert display_user_name(2, "Event name", aliases) == "Event name"
    assert display_user_name(None, "Unknown", aliases) == "Unknown"


def test_read_only_user_name_parser_discards_sensitive_fields():
    from custom_components.spc_flexc.flexc.flexml import (
        build_user_config_command,
        parse_user_config_name,
    )

    command = build_user_config_command(1, "account", "secret")
    assert '<CMD_GET_USER_CONFIG USER_ID="1" />' in command
    response = (
        '<FLEXML_REPLY><REPLY_GET_USER_CONFIG RESULT="0">'
        '<USER_CONFIG USER_ID="1" USER_NAME="Nicolas" PIN="1234" '
        'CARD_NUMBER="sensitive" />'
        "</REPLY_GET_USER_CONFIG></FLEXML_REPLY>"
    )
    assert parse_user_config_name(response) == "Nicolas"
    assert (
        parse_user_config_name(
            '<FLEXML_REPLY><REPLY_GET_USER_CONFIG RESULT="102" /></FLEXML_REPLY>'
        )
        is None
    )


def test_aliases_skip_blank_lines_and_normalize_numeric_ids():
    assert parse_user_aliases("  \n0001 = Nicolas\n\n9995 = Home Assistant") == {
        "1": "Nicolas",
        "9995": "Home Assistant",
    }


def test_user_name_parser_ignores_missing_name_and_wrong_reply():
    from custom_components.spc_flexc.flexc.flexml import parse_user_config_name

    assert (
        parse_user_config_name(
            '<FLEXML_REPLY><REPLY_GET_USER_CONFIG RESULT="0">'
            '<USER_CONFIG USER_ID="1" PIN="secret" />'
            "</REPLY_GET_USER_CONFIG></FLEXML_REPLY>"
        )
        is None
    )
    assert (
        parse_user_config_name(
            '<FLEXML_REPLY><REPLY_GET_PANEL_SUMMARY RESULT="0" /></FLEXML_REPLY>'
        )
        is None
    )


@pytest.mark.asyncio
async def test_client_user_lookup_returns_name_only():
    """The client must not retain the raw user config containing credentials."""
    from unittest.mock import AsyncMock

    from custom_components.spc_flexc.flexc.connection import FlexCClient

    client = object.__new__(FlexCClient)
    client.command_username = "account"
    client.command_password = "secret"
    client.async_send_flexml = AsyncMock(
        return_value=(
            '<FLEXML_REPLY><REPLY_GET_USER_CONFIG RESULT="0">'
            '<USER_CONFIG USER_ID="1" USER_NAME="Nicolas" PIN="private" />'
            "</REPLY_GET_USER_CONFIG></FLEXML_REPLY>"
        )
    )
    assert await client.async_get_user_name(1) == "Nicolas"
    client.async_send_flexml.assert_awaited_once()
    assert 'USER_ID="1"' in client.async_send_flexml.await_args.args[0]


@pytest.mark.asyncio
async def test_client_user_lookup_handles_unknown_user():
    from unittest.mock import AsyncMock

    from custom_components.spc_flexc.flexc.connection import FlexCClient

    client = object.__new__(FlexCClient)
    client.command_username = "account"
    client.command_password = "secret"
    client.async_send_flexml = AsyncMock(
        return_value=(
            '<FLEXML_REPLY><REPLY_GET_USER_CONFIG RESULT="102" />'
            "</FLEXML_REPLY>"
        )
    )
    assert await client.async_get_user_name(9995) is None


@pytest.mark.parametrize("user_id", [0, -1, 10000])
def test_user_config_rejects_out_of_range_ids(user_id):
    from custom_components.spc_flexc.flexc.flexml import build_user_config_command

    with pytest.raises(ValueError):
        build_user_config_command(user_id, "account", "secret")
