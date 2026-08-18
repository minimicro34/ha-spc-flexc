from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelState,
)

from custom_components.spc_flexc.alarm_control_panel import (
    MODE_LABELS,
)


def test_area_mode_labels() -> None:
    assert MODE_LABELS == {
        0: "Unset",
        1: "PartSetA",
        2: "PartSetB",
        3: "Set",
    }


def test_expected_home_assistant_mode_mapping() -> None:
    mapping = {
        0: AlarmControlPanelState.DISARMED,
        1: AlarmControlPanelState.ARMED_AWAY,
        2: AlarmControlPanelState.ARMED_HOME,
        3: AlarmControlPanelState.ARMED_NIGHT,
    }

    assert mapping[0] is AlarmControlPanelState.DISARMED
    assert mapping[1] is AlarmControlPanelState.ARMED_AWAY
    assert mapping[2] is AlarmControlPanelState.ARMED_HOME
    assert mapping[3] is AlarmControlPanelState.ARMED_NIGHT
