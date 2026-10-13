"""Command-line entry point."""

from pathlib import Path

import typer

from f1_sim_driver import __version__
from f1_sim_driver.config import Settings
from f1_sim_driver.script import LapScript

app = typer.Typer(help="Play AI-authored lap scripts into the F1 game.", no_args_is_help=True)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_print_version, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """Scripted lap executor."""


@app.command()
def info() -> None:
    """Show the effective configuration."""
    s = Settings()
    typer.echo(f"f1-sim-driver {__version__}")
    typer.echo(f"udp: {s.udp_host}:{s.udp_port} · historian: {s.boxbox_url}")
    typer.echo(f"position hold: gain={s.position_hold_gain} max={s.position_hold_max}")


@app.command()
def validate(path: Path) -> None:
    """Validate a lap-script JSON file and print a summary."""
    script = LapScript.model_validate_json(path.read_text())
    typer.echo(
        f"{script.track} · {script.author}#{script.iteration} · "
        f"{len(script.points)} points · {script.length_m:.0f} m"
    )
