"""Tests for SPC FlexC binary sensors."""

from unittest.mock import MagicMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.spc_flexc.binary_sensor import (
    ZONE_ACTIVITY_PULSE_SECONDS,
    SpcZoneBinarySensor,
    zone_device_class,
)
from custom_components.spc_flexc.models import SpcState, ZoneState


def _zone_sensor(
    *,
    logic_input: int = 0,
    actuations: int = 0,
    zone_type: int = 0,
) -> tuple[SpcZoneBinarySensor, MagicMock]:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.data = SpcState()
    coordinator.data.zones[1] = ZoneState(
        zone_id=1,
        name="PIR",
        zone_type=zone_type,
        logic_input=logic_input,
        actuations_since_last_read=actuations,
    )
    sensor = SpcZoneBinarySensor(coordinator, 1)
    sensor.async_write_ha_state = MagicMock()
    return sensor, coordinator


def test_zone_uses_live_logic_input() -> None:
    """Test a live SPC zone activation is exposed directly."""
    sensor, coordinator = _zone_sensor(logic_input=1)

    assert sensor.is_on is True
    assert coordinator.data.zones[1].logic_input == 1


def test_entry_exit_zone_types_use_generic_opening_class() -> None:
    """Test SPC entry/exit types are exposed as generic openings."""
    assert zone_device_class(1) == BinarySensorDeviceClass.OPENING
    assert zone_device_class(30) == BinarySensorDeviceClass.OPENING


def test_technical_zone_keeps_generic_binary_sensor_class() -> None:
    """Test an SPC technical zone is not given misleading HA semantics."""
    assert zone_device_class(9) is None


def test_autosurveillance_zone_uses_tamper_class() -> None:
    """Test an SPC autosurveillance zone is exposed as tamper."""
    assert zone_device_class(8) == BinarySensorDeviceClass.TAMPER


def test_missed_motion_starts_two_second_local_pulse() -> None:
    """Test an actuation missed between polls creates a local motion pulse."""
    sensor, coordinator = _zone_sensor(logic_input=0, actuations=3)
    loop = MagicMock()
    handle = MagicMock()
    loop.call_later.return_value = handle

    with (
        patch(
            "custom_components.spc_flexc.binary_sensor.asyncio.get_running_loop",
            return_value=loop,
        ),
        patch.object(CoordinatorEntity, "_handle_coordinator_update"),
    ):
        sensor._handle_coordinator_update()

    assert sensor.is_on is True
    assert coordinator.data.zones[1].logic_input == 0
    assert coordinator.data.zones[1].actuations_since_last_read == 3
    loop.call_later.assert_called_once_with(
        ZONE_ACTIVITY_PULSE_SECONDS,
        sensor._end_activity_pulse,
    )


def test_new_actuation_restarts_existing_activity_pulse() -> None:
    """Test another missed actuation extends the local pulse window."""
    sensor, _ = _zone_sensor(logic_input=0, actuations=1)
    loop = MagicMock()
    first_handle = MagicMock()
    second_handle = MagicMock()
    loop.call_later.side_effect = [first_handle, second_handle]

    with patch(
        "custom_components.spc_flexc.binary_sensor.asyncio.get_running_loop",
        return_value=loop,
    ):
        sensor._start_activity_pulse()
        sensor._start_activity_pulse()

    first_handle.cancel.assert_called_once_with()
    assert sensor._activity_pulse_handle is second_handle
    assert sensor.is_on is True


def test_activity_pulse_returns_to_raw_zone_state() -> None:
    """Test pulse expiry returns an idle PIR to its raw SPC state."""
    sensor, coordinator = _zone_sensor(logic_input=0, actuations=1)
    sensor._activity_pulse_active = True
    sensor._activity_pulse_handle = MagicMock()

    sensor._end_activity_pulse()

    assert sensor.is_on is False
    assert coordinator.data.zones[1].logic_input == 0
    assert sensor._activity_pulse_handle is None
    sensor.async_write_ha_state.assert_called_once_with()


def test_actuation_pulse_is_limited_to_motion_zones() -> None:
    """Test door and other zone classes are not held active by actuation counts."""
    sensor, _ = _zone_sensor(logic_input=0, actuations=1, zone_type=4)
    assert sensor._attr_device_class == BinarySensorDeviceClass.DOOR

    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        sensor._handle_coordinator_update()

    assert sensor.is_on is False
    assert sensor._activity_pulse_handle is None
