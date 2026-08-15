from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_PANEL_INTERVAL, DOMAIN
from .flexc.connection import FlexCClient
from .models import SpcState


class SpcFlexCCoordinator(DataUpdateCoordinator[SpcState]):
    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_PANEL_INTERVAL),
        )
        self.entry = entry
        self.state = SpcState()
        self.client = FlexCClient(entry.data)

    async def _async_update_data(self):
        # Phase 1: connect + PANEL_SUMMARY.
        # Phase 2: continuous AREA/ZONE batch polling and EVENT 0x60 listener.
        await self.client.async_ensure_connected()
        panel = await self.client.async_get_panel_summary()
        if panel:
            self.state.panel = panel
        return self.state

    async def async_shutdown(self):
        await self.client.async_close()
