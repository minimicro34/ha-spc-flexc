"""Mapping Gate coordinator extensions for SPC FlexC."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .flexc.connection import FlexCError
from .flexc.flexml import (
    FlexMLError,
    build_mg_control_command,
    build_mg_status_command,
    parse_mg_control,
    parse_mg_status,
)
from .models import MappingGateState
from .zone_control_coordinator import SpcFlexCZoneControlCoordinator

_LOGGER = logging.getLogger(__name__)
MG_POLL_INTERVAL = 1.0


class SpcFlexCMappingGateCoordinator(SpcFlexCZoneControlCoordinator):
    """SPC coordinator with Mapping Gate discovery, status and control."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Mapping Gate support."""
        super().__init__(hass, entry)
        self._mg_discovery_complete = False
        self._mg_poll_task: asyncio.Task[None] | None = None

    async def _async_discover_panel_objects(self) -> None:
        """Run standard discovery then discover configured Mapping Gates."""
        await super()._async_discover_panel_objects()
        try:
            raw_mapping_gates = await self._async_read_mapping_gates()
        except (FlexCError, FlexMLError) as err:
            _LOGGER.debug("SPC Mapping Gate discovery failed: %s", err)
            return

        self._update_mapping_gate_states(raw_mapping_gates)
        self._mg_discovery_complete = True
        _LOGGER.info(
            "FlexC Mapping Gates discovered: %s",
            sorted(self.state.mapping_gates),
        )
        self.async_set_updated_data(self.state)
        self._schedule_mg_polling()

    async def _async_read_mapping_gates(self) -> list[dict[str, str]]:
        """Read all configured Mapping Gates using aggregate MG_ID=0."""
        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            command = build_mg_status_command(
                self.client.command_username,
                self.client.command_password,
            )
            response = await self.client.async_send_flexml(command)
        return parse_mg_status(response)

    def _update_mapping_gate_states(
        self, raw_mapping_gates: list[dict[str, str]]
    ) -> bool:
        """Store Mapping Gate states and return whether anything changed."""
        changed = False
        seen: set[int] = set()
        for raw_mg in raw_mapping_gates:
            mg_id = int(raw_mg["MG_ID"])
            seen.add(mg_id)
            raw_state = raw_mg.get("STATE")
            state = None if raw_state not in ("0", "1") else raw_state == "1"
            mapping_gate = MappingGateState(
                mg_id=mg_id,
                name=raw_mg.get("MG_NAME") or raw_mg.get("NAME"),
                state=state,
                raw=dict(raw_mg),
                updated_at=datetime.now(UTC),
            )
            previous = self.state.mapping_gates.get(mg_id)
            if previous is None or previous.raw != mapping_gate.raw:
                changed = True
            self.state.mapping_gates[mg_id] = mapping_gate

        removed = set(self.state.mapping_gates) - seen
        if removed:
            changed = True
            for mg_id in removed:
                del self.state.mapping_gates[mg_id]
        return changed

    def _schedule_mg_polling(self) -> None:
        """Start live polling after Mapping Gate discovery."""
        if not self._mg_discovery_complete:
            return
        if self._mg_poll_task is not None and not self._mg_poll_task.done():
            return
        self._mg_poll_task = self.entry.async_create_background_task(
            self.hass,
            self._async_mg_poll_loop(),
            name="spc_flexc mapping gate polling",
            eager_start=False,
        )

    async def _async_mg_poll_loop(self) -> None:
        """Poll Mapping Gates so panel-side changes are reflected in HA."""
        _LOGGER.debug("SPC Mapping Gate polling started")
        try:
            while True:
                await asyncio.sleep(MG_POLL_INTERVAL)
                try:
                    raw_mapping_gates = await self._async_read_mapping_gates()
                    if self._update_mapping_gate_states(raw_mapping_gates):
                        self.async_set_updated_data(self.state)
                except asyncio.CancelledError:
                    raise
                except (FlexCError, FlexMLError) as err:
                    _LOGGER.debug("SPC Mapping Gate polling failed: %s", err)
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while polling SPC Mapping Gates; polling will continue"
                    )
        finally:
            _LOGGER.debug("SPC Mapping Gate polling stopped")
            current_task = asyncio.current_task()
            if self._mg_poll_task is current_task:
                self._mg_poll_task = None
                if self._discovery_requested:
                    _LOGGER.warning(
                        "SPC Mapping Gate polling stopped unexpectedly; restarting"
                    )
                    self._schedule_mg_polling()

    async def async_set_mapping_gate(self, mg_id: int, state: bool) -> None:
        """Set one Mapping Gate and immediately verify its state."""
        if mg_id not in self.state.mapping_gates:
            raise ValueError(f"Unknown SPC Mapping Gate {mg_id}")

        action = 1 if state else 0
        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            command = build_mg_control_command(
                mg_id,
                action,
                self.client.command_username,
                self.client.command_password,
            )
            response = await self.client.async_send_flexml(command)
            parse_mg_control(response, mg_id)
            status_command = build_mg_status_command(
                self.client.command_username,
                self.client.command_password,
            )
            status_response = await self.client.async_send_flexml(status_command)

        raw_mapping_gates = parse_mg_status(status_response)
        self._update_mapping_gate_states(raw_mapping_gates)
        refreshed = self.state.mapping_gates.get(mg_id)
        if refreshed is None or refreshed.state is not state:
            raise ValueError(
                f"SPC Mapping Gate {mg_id} did not confirm the requested state"
            )
        self.async_set_updated_data(self.state)

    async def async_shutdown(self) -> None:
        """Stop Mapping Gate polling and shut down the base coordinator."""
        self._discovery_requested = False
        mg_task = self._mg_poll_task
        self._mg_poll_task = None
        if mg_task is not None and not mg_task.done():
            mg_task.cancel()
            with suppress(asyncio.CancelledError):
                await mg_task
        await super().async_shutdown()
