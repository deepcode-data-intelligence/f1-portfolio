"""Command-line entry point."""

import typer

from f1_sim_connector import __version__
from f1_sim_connector.config import settings

app = typer.Typer(help="F1 game UDP telemetry -> box-box historian.", no_args_is_help=True)


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
    """Edge connector for live game telemetry."""


@app.command()
def info() -> None:
    """Show the effective configuration."""
    typer.echo(f"f1-sim-connector {__version__}")
    typer.echo(f"udp: {settings.udp_host}:{settings.udp_port}")
    typer.echo(f"historian: {settings.boxbox_url}")
