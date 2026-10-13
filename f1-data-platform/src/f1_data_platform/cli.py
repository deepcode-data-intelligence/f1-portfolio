"""Command-line entry point. Pipelines are added case by case."""

import typer

from f1_data_platform import __version__

app = typer.Typer(help="F1 history ETL: Jolpica-F1 API -> DuckDB/Parquet.", no_args_is_help=True)


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
    """F1 history ETL."""


@app.command()
def info() -> None:
    """Show build information."""
    typer.echo(f"f1-data-platform {__version__}")
