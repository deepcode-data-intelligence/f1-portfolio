"""Command-line entry point: ``f1-data backfill | stage | build | check | run``."""

import logging

import typer

from f1_data_platform import __version__
from f1_data_platform.config import Settings
from f1_data_platform.extract import ALL_ENTITIES, backfill
from f1_data_platform.jolpica import JolpicaClient
from f1_data_platform.marts import build
from f1_data_platform.quality import run_checks
from f1_data_platform.raw import RawStore
from f1_data_platform.staging import stage_all

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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging."),
) -> None:
    """F1 history ETL."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _seasons(start: int | None, end: int | None) -> list[int] | None:
    if start is None and end is None:
        return None
    return list(range(start or 1950, (end or start or 1950) + 1))


@app.command()
def info() -> None:
    """Show the effective configuration."""
    s = Settings()
    typer.echo(f"f1-data-platform {__version__}")
    typer.echo(f"data dir: {s.data_dir.resolve()}")
    typer.echo(f"api: {s.jolpica_base_url} ({s.hourly_limit}/h, burst {s.burst_per_second}/s)")


@app.command("backfill")
def backfill_cmd(
    start: int | None = typer.Option(None, "--from", help="First season (default: all)."),
    end: int | None = typer.Option(None, "--to", help="Last season (default: all)."),
    entity: list[str] = typer.Option(list(ALL_ENTITIES), "--entity", "-e"),  # noqa: B008
    refresh: list[int] = typer.Option(  # noqa: B008
        [], "--refresh", help="Seasons to reload even if complete (default: current year)."
    ),
) -> None:
    """Load raw API pages. Resumable: complete partitions are skipped."""
    s = Settings()
    stats = backfill(
        JolpicaClient(s),
        RawStore(s.raw_dir),
        seasons=_seasons(start, end),
        entities=entity,
        refresh=refresh or None,
    )
    span = f"{stats.seasons[0]}..{stats.seasons[-1]}" if stats.seasons else "-"
    typer.echo(
        f"seasons {span} · loaded {stats.partitions_loaded} partitions "
        f"({stats.pages} pages, {stats.requests} requests) · skipped {stats.partitions_skipped}"
    )


@app.command("stage")
def stage_cmd() -> None:
    """Raw JSON -> typed, deduplicated Parquet."""
    s = Settings()
    for entity, rows in stage_all(RawStore(s.raw_dir), s.staging_dir).items():
        typer.echo(f"{entity:24s} {rows:>8d} rows")


@app.command("build")
def build_cmd() -> None:
    """Staging Parquet -> DuckDB tables and views."""
    s = Settings()
    for table, rows in build(s.duckdb_path, s.staging_dir).items():
        typer.echo(f"{table:24s} {rows:>8d} rows")
    typer.echo(f"-> {s.duckdb_path}")


@app.command("check")
def check_cmd() -> None:
    """Run data-quality checks; exit 1 on any failure."""
    s = Settings()
    results = run_checks(s.duckdb_path)
    for r in results:
        typer.echo(f"{'PASS' if r.passed else 'FAIL':4s} {r.name} ({r.offending_rows})")
    failed = [r for r in results if not r.passed]
    typer.echo(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        raise typer.Exit(code=1)


@app.command("run")
def run_cmd(
    start: int | None = typer.Option(None, "--from"),
    end: int | None = typer.Option(None, "--to"),
) -> None:
    """backfill -> stage -> build -> check."""
    backfill_cmd(start=start, end=end, entity=list(ALL_ENTITIES), refresh=[])
    stage_cmd()
    build_cmd()
    check_cmd()
