"""Mapping Gate coordinator extensions for SPC FlexC."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import MG_POLL_INTERVAL, MG_POLL_PHASE
from .coordinator import poll_delay_for_phase
from .flexc.connection import FlexCCommandTimeout, FlexCError
from .flexc.flexml import (
    FlexMLError,
    build_mg_control_command,
    build_mg_status_command,
    parse_mg_control,
    parse_mg_status,
)
from .flexc.read_retry import async_retry_read_once
from .models import MappingGateState
from .zone_control_coordinator import SpcFlexCZoneControlCoordinator

_LOGGER = logging.getLogger(__name__)


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
            response = await async_retry_read_once(
                lambda: self.client.async_send_flexml(command),
                description="reading Mapping Gate status",
            )
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
                await asyncio.sleep(
                    poll_delay_for_phase(MG_POLL_PHASE, MG_POLL_INTERVAL)
                )
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
        except asyncio.CancelledError:
            _LOGGER.warning(
                "SPC Mapping Gate polling cancelled: entry_state=%s hass_state=%s discovery_requested=%s",
                self.entry.state,
                self.hass.state,
                self._discovery_requested,
            )
            raise
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
        """Set one Mapping Gate and verify/recover the requested state."""
        if mg_id not in self.state.mapping_gates:
            raise ValueError(f"Unknown SPC Mapping Gate {mg_id}")

        requested = "ON" if state else "OFF"
        action = 1 if state else 0
        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            command = build_mg_control_command(
                mg_id,
                action,
                self.client.command_username,
                self.client.command_password,
            )
            status_command = build_mg_status_command(
                self.client.command_username,
                self.client.command_password,
            )
            _LOGGER.info("Mapping Gate %d control requested: %s", mg_id, requested)

            control_timed_out = False
            try:
                response = await self.client.async_send_flexml(command)
                parse_mg_control(response, mg_id)
                _LOGGER.info(
                    "Mapping Gate %d control accepted by SPC: %s", mg_id, requested
                )
            except FlexCCommandTimeout:
                control_timed_out = True
                _LOGGER.warning(
                    "Mapping Gate %d control timed out; recovering FlexC session "
                    "(requested=%s)",
                    mg_id,
                    requested,
                )
                await self.client.async_recover_session()

            if control_timed_out:
                status_response = await async_retry_read_once(
                    lambda: self.client.async_send_flexml(status_command),
                    description=f"checking Mapping Gate {mg_id} after timeout",
                )
            else:
                try:
                    status_response = await async_retry_read_once(
                        lambda: self.client.async_send_flexml(status_command),
                        description=f"refreshing Mapping Gate {mg_id} after control",
                    )
                except FlexCCommandTimeout:
                    _LOGGER.warning(
                        "Mapping Gate %d verification timed out after SPC accepted "
                        "control; recovering FlexC session (requested=%s)",
                        mg_id,
                        requested,
                    )
                    await self.client.async_recover_session()
                    status_response = await async_retry_read_once(
                        lambda: self.client.async_send_flexml(status_command),
                        description=(
                            f"checking Mapping Gate {mg_id} after verification timeout"
                        ),
                    )

            raw_mapping_gates = parse_mg_status(status_response)
            self._update_mapping_gate_states(raw_mapping_gates)
            refreshed = self.state.mapping_gates.get(mg_id)
            current = (
                "UNKNOWN"
                if refreshed is None or refreshed.state is None
                else "ON"
                if refreshed.state
                else "OFF"
            )
            _LOGGER.info(
                "Mapping Gate %d verified status: requested=%s current=%s",
                mg_id,
                requested,
                current,
            )

            if refreshed is not None and refreshed.state is state:
                _LOGGER.info(
                    "Mapping Gate %d state confirmed: %s", mg_id, requested
                )
                self.async_set_updated_data(self.state)
                return

            if refreshed is None or refreshed.state is None:
                _LOGGER.error(
                    "Mapping Gate %d outcome is unknown after recovery; command "
                    "was not retried",
                    mg_id,
                )
                raise ValueError(
                    f"SPC Mapping Gate {mg_id} state is unknown after recovery"
                )

            _LOGGER.warning(
                "Mapping Gate %d remains %s while %s was requested; retrying "
                "control once",
                mg_id,
                current,
                requested,
            )
            response = await self.client.async_send_flexml(command)
            parse_mg_control(response, mg_id)
            _LOGGER.info(
                "Mapping Gate %d retry accepted by SPC; verifying final status",
                mg_id,
            )
            status_response = await async_retry_read_once(
                lambda: self.client.async_send_flexml(status_command),
                description=f"refreshing Mapping Gate {mg_id} after retry",
            )
            raw_mapping_gates = parse_mg_status(status_response)
            self._update_mapping_gate_states(raw_mapping_gates)
            refreshed = self.state.mapping_gates.get(mg_id)
            if refreshed is None or refreshed.state is not state:
                raise ValueError(
                    f"SPC Mapping Gate {mg_id} did not confirm the requested "
                    "state after retry"
                )
            _LOGGER.info(
                "Mapping Gate %d final status confirmed: %s", mg_id, requested
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
