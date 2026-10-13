"""Staging -> marts -> quality, end to end on the fixture raw store."""

import duckdb
import pyarrow.parquet as pq

from f1_data_platform.marts import VIEWS, build
from f1_data_platform.quality import run_checks
from f1_data_platform.staging import PLAN, SCHEMAS, parse_results, stage_all
from tests import fixtures


def test_parse_results_flattens_nested_objects() -> None:
    rows = parse_results(fixtures.RESULTS_2024_P0)
    assert len(rows) == 2
    winner = rows[0]
    assert winner["driver_id"] == "max_verstappen"
    assert winner["points"] == 26.0
    assert winner["time_millis"] == 5504742
    assert winner["fastest_lap_speed_kph"] == 210.383


def test_stage_writes_typed_deduplicated_parquet(raw_store, settings) -> None:
    counts = stage_all(raw_store, settings.staging_dir)
    assert counts == {
        "seasons": 2,
        "circuits": 2,
        "races": 2,
        "drivers": 2,
        "constructors": 2,
        "results": 4,
        "sprint_results": 1,
        "driver_standings": 2,
        "constructor_standings": 2,
    }
    for entity in PLAN:
        table = pq.read_table(settings.staging_dir / f"{entity}.parquet")
        assert table.schema.equals(SCHEMAS[entity], check_metadata=False)


def test_build_creates_tables_and_views(raw_store, settings) -> None:
    stage_all(raw_store, settings.staging_dir)
    counts = build(settings.duckdb_path, settings.staging_dir)
    assert counts["results"] == 4
    with duckdb.connect(str(settings.duckdb_path), read_only=True) as con:
        views = {
            r[0]
            for r in con.execute(
                "SELECT view_name FROM duckdb_views() WHERE NOT internal"
            ).fetchall()
        }
        assert set(VIEWS) <= views
        summary = con.execute(
            "SELECT driver_id, wins, points FROM driver_season_summary "
            "WHERE season = 2024 ORDER BY points DESC"
        ).fetchall()
        assert summary == [("max_verstappen", 1, 53.0), ("norris", 1, 43.0)]
        champion = con.execute(
            "SELECT driver, constructor FROM champions WHERE season = 2024"
        ).fetchone()
        assert champion == ("Max Verstappen", "Red Bull")
        race = con.execute("SELECT winner_id, pole_id FROM race_summary WHERE round = 2").fetchone()
        assert race == ("norris", "max_verstappen")


def test_quality_checks_pass_on_consistent_data(raw_store, settings) -> None:
    stage_all(raw_store, settings.staging_dir)
    build(settings.duckdb_path, settings.staging_dir)
    results = run_checks(settings.duckdb_path)
    assert results and all(r.passed for r in results), [r for r in results if not r.passed]


def test_quality_checks_catch_orphans(raw_store, settings) -> None:
    stage_all(raw_store, settings.staging_dir)
    build(settings.duckdb_path, settings.staging_dir)
    with duckdb.connect(str(settings.duckdb_path)) as con:
        con.execute("DELETE FROM drivers WHERE driver_id = 'norris'")
    failed = {r.name for r in run_checks(settings.duckdb_path) if not r.passed}
    assert failed == {"results -> drivers", "driver_standings -> drivers"}
