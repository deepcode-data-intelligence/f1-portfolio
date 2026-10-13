from f1_telemetry_lab import __version__
from f1_telemetry_lab.config import Settings


def test_version() -> None:
    assert __version__


def test_default_settings_point_to_local_historian() -> None:
    assert Settings().boxbox_url.startswith("http")
