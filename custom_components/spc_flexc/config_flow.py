import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from .const import DOMAIN, CONF_PORT, CONF_KEY, DEFAULT_PORT

class SpcFlexCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"SPC {user_input[CONF_HOST]}", data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_KEY): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema)
