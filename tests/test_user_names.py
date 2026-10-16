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
    assert display_user_name(1, "Event name", aliases, {1: "Panel name"}) == "Panel name"
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
        '</REPLY_GET_USER_CONFIG></FLEXML_REPLY>'
    )
    assert parse_user_config_name(response) == "Nicolas"
    assert parse_user_config_name(
        '<FLEXML_REPLY><REPLY_GET_USER_CONFIG RESULT="102" />'
        '</FLEXML_REPLY>'
    ) is None
