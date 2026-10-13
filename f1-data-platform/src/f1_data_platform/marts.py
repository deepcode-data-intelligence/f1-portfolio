"""Marts layer: a DuckDB file with one table per staged entity plus analytical views.

The DuckDB file is the contract consumed by ``f1-history-agent`` (SQL tool-calling and the
``/stats`` API) and by ``f1-strategy-ml``.
"""

import logging
from pathlib import Path

import duckdb

from f1_data_platform.staging import PLAN

log = logging.getLogger(__name__)

VIEWS: dict[str, str] = {
    # One row per race with the winner, pole sitter and fastest lap.
    "race_summary": """
        SELECT r.season, r.round, r.name AS race_name, r.date, c.name AS circuit_name, c.country,
               w.driver_id   AS winner_id,
               w.constructor_id AS winner_constructor_id,
               p.driver_id   AS pole_id,
               f.driver_id   AS fastest_lap_id
        FROM races r
        JOIN circuits c USING (circuit_id)
        LEFT JOIN results w ON w.season = r.season AND w.round = r.round AND w.position = 1
        LEFT JOIN results p ON p.season = r.season AND p.round = r.round AND p.grid = 1
        LEFT JOIN results f ON f.season = r.season AND f.round = r.round AND f.fastest_lap_rank = 1
    """,
    # Season totals per driver, derived from classifications (not from the standings feed).
    # ``points`` = grand prix + sprint points; reconciles with driver_standings from 2010 on.
    "driver_season_summary": """
        WITH gp AS (
            SELECT season, driver_id,
                   count(*)                                   AS starts,
                   sum(CASE WHEN position = 1 THEN 1 ELSE 0 END) AS wins,
                   sum(CASE WHEN position <= 3 THEN 1 ELSE 0 END) AS podiums,
                   sum(CASE WHEN grid = 1 THEN 1 ELSE 0 END) AS poles,
                   sum(CASE WHEN fastest_lap_rank = 1 THEN 1 ELSE 0 END) AS fastest_laps,
                   sum(points)                                AS gp_points
            FROM results GROUP BY ALL
        ), sprint AS (
            SELECT season, driver_id, sum(points) AS sprint_points FROM sprint_results GROUP BY ALL
        )
        SELECT gp.season, gp.driver_id, d.code, d.given_name || ' ' || d.family_name AS driver,
               gp.starts, gp.wins, gp.podiums, gp.poles, gp.fastest_laps,
               gp.gp_points, coalesce(sprint.sprint_points, 0) AS sprint_points,
               gp.gp_points + coalesce(sprint.sprint_points, 0) AS points
        FROM gp
        JOIN drivers d USING (driver_id)
        LEFT JOIN sprint USING (season, driver_id)
    """,
    "constructor_season_summary": """
        WITH gp AS (
            SELECT season, constructor_id,
                   count(*)                                   AS entries,
                   sum(CASE WHEN position = 1 THEN 1 ELSE 0 END) AS wins,
                   sum(CASE WHEN position <= 3 THEN 1 ELSE 0 END) AS podiums,
                   sum(points)                                AS gp_points
            FROM results GROUP BY ALL
        ), sprint AS (
            SELECT season, constructor_id, sum(points) AS sprint_points
            FROM sprint_results GROUP BY ALL
        )
        SELECT gp.season, gp.constructor_id, c.name AS constructor,
               gp.entries, gp.wins, gp.podiums,
               gp.gp_points, coalesce(sprint.sprint_points, 0) AS sprint_points,
               gp.gp_points + coalesce(sprint.sprint_points, 0) AS points
        FROM gp
        JOIN constructors c USING (constructor_id)
        LEFT JOIN sprint USING (season, constructor_id)
    """,
    # Official champions from the final standings of each season.
    "champions": """
        SELECT ds.season,
               ds.driver_id, d.given_name || ' ' || d.family_name AS driver,
               ds.points AS driver_points,
               cs.constructor_id, c.name AS constructor, cs.points AS constructor_points
        FROM driver_standings ds
        JOIN drivers d USING (driver_id)
        LEFT JOIN constructor_standings cs ON cs.season = ds.season AND cs.position = 1
        LEFT JOIN constructors c ON c.constructor_id = cs.constructor_id
        WHERE ds.position = 1
    """,
}


def build(duckdb_path: Path, staging_dir: Path) -> dict[str, int]:
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect(str(duckdb_path)) as con:
        for entity in PLAN:
            parquet = (staging_dir / f"{entity}.parquet").resolve()
            con.execute(
                f"CREATE OR REPLACE TABLE {entity} AS SELECT * FROM read_parquet(?)", [str(parquet)]
            )
            counts[entity] = con.execute(f"SELECT count(*) FROM {entity}").fetchone()[0]
        for name, sql in VIEWS.items():
            con.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")
    log.info("built %s: %s", duckdb_path, counts)
    return counts
