"""Data-quality checks run against the marts database.

Each check is a SQL statement that returns the number of offending rows; zero means pass.
"""

from dataclasses import dataclass
from pathlib import Path

import duckdb

from f1_data_platform.staging import KEYS


@dataclass(frozen=True)
class CheckResult:
    name: str
    offending_rows: int

    @property
    def passed(self) -> bool:
        return self.offending_rows == 0


def _uniqueness_checks() -> dict[str, str]:
    checks = {}
    for table, key in KEYS.items():
        cols = ", ".join(key)
        checks[f"{table}: unique ({cols})"] = (
            f"SELECT count(*) FROM (SELECT {cols} FROM {table} GROUP BY {cols} HAVING count(*) > 1)"
        )
    return checks


CHECKS: dict[str, str] = {
    **_uniqueness_checks(),
    "results -> drivers": (
        "SELECT count(*) FROM results r LEFT JOIN drivers d USING (driver_id) "
        "WHERE d.driver_id IS NULL"
    ),
    "results -> constructors": (
        "SELECT count(*) FROM results r LEFT JOIN constructors c USING (constructor_id) "
        "WHERE c.constructor_id IS NULL"
    ),
    "results -> races": (
        "SELECT count(*) FROM results r LEFT JOIN races ra USING (season, round) "
        "WHERE ra.name IS NULL"
    ),
    "races -> circuits": (
        "SELECT count(*) FROM races r LEFT JOIN circuits c USING (circuit_id) WHERE c.name IS NULL"
    ),
    "races -> seasons": (
        "SELECT count(*) FROM races r LEFT JOIN seasons s USING (season) WHERE s.season IS NULL"
    ),
    "driver_standings -> drivers": (
        "SELECT count(*) FROM driver_standings s LEFT JOIN drivers d USING (driver_id) "
        "WHERE d.driver_id IS NULL"
    ),
    "results: points are non-negative": "SELECT count(*) FROM results WHERE points < 0",
    "results: position within entries": (
        "SELECT count(*) FROM results WHERE position IS NOT NULL AND position < 1"
    ),
    "races: date within season": (
        "SELECT count(*) FROM races WHERE date IS NOT NULL AND year(date) <> season"
    ),
    # Dropped-score rules ended in 1990 and a few exclusions exist before 2010, so the
    # points reconciliation is asserted for the modern era only.
    "standings reconcile with results + sprints (2010+)": (
        "SELECT count(*) FROM driver_standings s "
        "JOIN driver_season_summary v USING (season, driver_id) "
        "WHERE s.season >= 2010 AND abs(s.points - v.points) > 0.01"
    ),
    "races: every race has results": (
        "SELECT count(*) FROM races r WHERE r.date < current_date "
        "AND NOT EXISTS (SELECT 1 FROM results x WHERE x.season = r.season AND x.round = r.round)"
    ),
}


def run_checks(duckdb_path: Path) -> list[CheckResult]:
    with duckdb.connect(str(duckdb_path), read_only=True) as con:
        return [CheckResult(name, con.execute(sql).fetchone()[0]) for name, sql in CHECKS.items()]
