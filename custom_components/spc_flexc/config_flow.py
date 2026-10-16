"""Config flow for SPC FlexC."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector

from .const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
    CONF_PORT,
    CONF_USER_ALIASES,
    DEFAULT_PORT,
    DOMAIN,
)


def _config_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Return the SPC FlexC configuration schema."""
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=defaults.get(CONF_HOST, ""),
            ): str,
            vol.Optional(
                CONF_PORT,
                default=defaults.get(CONF_PORT, DEFAULT_PORT),
            ): int,
            vol.Required(
                CONF_KEY,
                default=defaults.get(CONF_KEY, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            ),
            vol.Required(
                CONF_COMMAND_USERNAME,
                default=defaults.get(CONF_COMMAND_USERNAME, ""),
            ): str,
            vol.Required(
                CONF_COMMAND_PASSWORD,
                default=defaults.get(CONF_COMMAND_PASSWORD, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            ),
        }
    )


class SpcFlexCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SPC FlexC."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SpcFlexCOptionsFlow:
        """Expose display-name overrides in integration options."""
        return SpcFlexCOptionsFlow()

    def _host_is_configured(
        self,
        host: str,
        *,
        exclude_entry_id: str | None = None,
    ) -> bool:
        """Return whether the SPC host is already configured."""
        return any(
            entry.entry_id != exclude_entry_id and entry.data.get(CONF_HOST) == host
            for entry in self._async_current_entries()
        )

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial configuration step."""
        if user_input is not None:
            if self._host_is_configured(user_input[CONF_HOST]):
                return self.async_abort(reason="already_configured")

            # Do not use the IP address as the config entry unique_id.
            # A stable panel identifier (serial number) is assigned after
            # PANEL_SUMMARY is successfully retrieved during setup.
            return self.async_create_entry(
                title=f"SPC {user_input[CONF_HOST]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema(),
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of an existing SPC FlexC entry."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            if self._host_is_configured(
                user_input[CONF_HOST],
                exclude_entry_id=entry.entry_id,
            ):
                return self.async_abort(reason="already_configured")

            return self.async_update_reload_and_abort(
                entry,
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_config_schema(dict(entry.data)),
        )


class SpcFlexCOptionsFlow(config_entries.OptionsFlow):
    """User-facing display name overrides; never change SPC credentials."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure one alias per line in USER_ID=Display name format."""
        if user_input is not None:
            from .user_names import parse_user_aliases

            try:
                aliases = parse_user_aliases(user_input.get(CONF_USER_ALIASES, ""))
            except ValueError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(user_input.get(CONF_USER_ALIASES, "")),
                    errors={"base": "invalid_aliases"},
                )
            return self.async_create_entry(
                title="",
                data={CONF_USER_ALIASES: aliases},
            )
        existing = self.config_entry.options.get(CONF_USER_ALIASES, {})
        default = "\n".join(
            f"{user_id}={name}" for user_id, name in sorted(existing.items())
        )
        return self.async_show_form(step_id="init", data_schema=self._schema(default))

    @staticmethod
    def _schema(default: str) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(CONF_USER_ALIASES, default=default): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                )
            }
        )
