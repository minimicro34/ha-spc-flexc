"""Guard against blocking timezone construction inside coordinator callbacks."""

from pathlib import Path

from custom_components.spc_flexc import coordinator


def test_coordinator_uses_cached_home_assistant_timezone() -> None:
    """All coordinator runtime timezone lookups use Home Assistant's helper."""
    source = Path(coordinator.__file__).read_text(encoding="utf-8")
    assert "ZoneInfo(self.hass.config.time_zone)" not in source
    assert source.count("dt_util.get_default_time_zone()") == 5
