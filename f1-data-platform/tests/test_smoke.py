from typer.testing import CliRunner

from f1_data_platform import __version__
from f1_data_platform.cli import app


def test_version_flag() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_info_command() -> None:
    result = CliRunner().invoke(app, ["info"])
    assert result.exit_code == 0
    assert __version__ in result.output
