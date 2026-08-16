"""Config flow for SPC FlexC."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector

from .const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)


class SpcFlexCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SPC FlexC."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial configuration step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"SPC {user_input[CONF_HOST]}",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
                vol.Required(CONF_COMMAND_USERNAME): str,
                vol.Required(CONF_COMMAND_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
