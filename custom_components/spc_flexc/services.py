"""Services of the SPC FlexC integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .flexc.connection import FlexCError
from .flexc.flexml import FlexMLError, FlexMLReplyError
from .flexc.logs import LOG_KINDS, LogReadBusy

if TYPE_CHECKING:
    from .coordinator import SpcFlexCCoordinator

SERVICE_GET_LOG = "get_log"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_LOG = "log"
ATTR_ID = "id"
ATTR_LIMIT = "limit"
ATTR_ATP = "atp"
DEFAULT_LIMIT = 100
# FlexML RESULT: the command is not ticked in the ATS's Command Profile.
RESULT_NOT_PERMITTED = "65"

GET_LOG_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_LOG): vol.In(sorted(LOG_KINDS)),
        vol.Optional(ATTR_ID): vol.All(vol.Coerce(int), vol.Range(min=1, max=999)),
        vol.Optional(ATTR_ATP): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
        vol.Optional(ATTR_LIMIT, default=DEFAULT_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=2000)
        ),
    }
)


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> SpcFlexCCoordinator:
    """Return the coordinator of the requested (or only) loaded SPC FlexC entry."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id is not None:
        entries = [entry for entry in entries if entry.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_loaded_entry"
        )
    if len(entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="several_entries"
        )
    return entries[0].runtime_data


async def _async_get_log(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    kind: str = call.data[ATTR_LOG]
    object_id: int | None = call.data.get(ATTR_ID)
    log = LOG_KINDS[kind]
    if log.id_attribute is not None and object_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="log_needs_id",
            translation_placeholders={"log": kind},
        )
    coordinator = _coordinator(hass, call)
    try:
        if log.sub_id_attribute is not None:
            records = await coordinator.async_read_log(
                kind, object_id, call.data.get(ATTR_ATP, 1)
            )
        else:
            records = await coordinator.async_read_log(
                kind, object_id if log.id_attribute is not None else None
            )
    except LogReadBusy as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="log_read_busy"
        ) from err
    except FlexMLReplyError as err:
        if err.code == RESULT_NOT_PERMITTED:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="log_not_permitted",
                translation_placeholders={"log": kind, "command": log.command},
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="log_read_failed",
            translation_placeholders={"log": kind, "error": str(err)},
        ) from err
    except (FlexCError, FlexMLError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="log_read_failed",
            translation_placeholders={"log": kind, "error": str(err)},
        ) from err
    # The panel always sends the whole log; the limit only shortens the result.
    entries: list[Any] = records[: call.data[ATTR_LIMIT]]
    return {
        "log": kind,
        "count": len(entries),
        "total": len(records),
        "entries": entries,
    }


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services (once).

    The panel logs hold who came and went and when, so reading them is limited
    to Home Assistant administrators.
    """
    if hass.services.has_service(DOMAIN, SERVICE_GET_LOG):
        return

    async def get_log(call: ServiceCall) -> ServiceResponse:
        return await _async_get_log(hass, call)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_GET_LOG,
        get_log,
        schema=GET_LOG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
