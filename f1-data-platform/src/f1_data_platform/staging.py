"""Staging layer: raw API pages -> typed, deduplicated Parquet, one file per entity.

Every parser takes an ``MRData`` page and returns flat rows. Rows are deduplicated on the
entity's natural key (drivers and constructors appear once per season in the raw layer) and
written with an explicit Arrow schema so types are stable across loads.
"""

import logging
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from f1_data_platform.raw import RawStore

log = logging.getLogger(__name__)


def _int(v: str | None) -> int | None:
    return int(v) if v not in (None, "") else None


def _float(v: str | None) -> float | None:
    return float(v) if v not in (None, "") else None


def _date(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


# ---------- parsers (one MRData page -> rows) ----------


def parse_seasons(mrdata: dict) -> list[dict]:
    return [
        {"season": int(s["season"]), "url": s.get("url")} for s in mrdata["SeasonTable"]["Seasons"]
    ]


def parse_circuits(mrdata: dict) -> list[dict]:
    rows = []
    for race in mrdata["RaceTable"]["Races"]:
        c, loc = race["Circuit"], race["Circuit"]["Location"]
        rows.append(
            {
                "circuit_id": c["circuitId"],
                "name": c["circuitName"],
                "locality": loc.get("locality"),
                "country": loc.get("country"),
                "lat": _float(loc.get("lat")),
                "lng": _float(loc.get("long")),
                "url": c.get("url"),
            }
        )
    return rows


def parse_races(mrdata: dict) -> list[dict]:
    rows = []
    for race in mrdata["RaceTable"]["Races"]:
        rows.append(
            {
                "season": int(race["season"]),
                "round": int(race["round"]),
                "name": race["raceName"],
                "circuit_id": race["Circuit"]["circuitId"],
                "date": _date(race.get("date")),
                "time": race.get("time"),
                "has_sprint": "Sprint" in race,
                "url": race.get("url"),
            }
        )
    return rows


def _driver(d: dict) -> dict:
    return {
        "driver_id": d["driverId"],
        "code": d.get("code"),
        "permanent_number": _int(d.get("permanentNumber")),
        "given_name": d["givenName"],
        "family_name": d["familyName"],
        "date_of_birth": _date(d.get("dateOfBirth")),
        "nationality": d.get("nationality"),
        "url": d.get("url"),
    }


def _constructor(c: dict) -> dict:
    return {
        "constructor_id": c["constructorId"],
        "name": c["name"],
        "nationality": c.get("nationality"),
        "url": c.get("url"),
    }


def parse_drivers(mrdata: dict) -> list[dict]:
    return [_driver(d) for d in mrdata["DriverTable"]["Drivers"]]


def parse_constructors(mrdata: dict) -> list[dict]:
    return [_constructor(c) for c in mrdata["ConstructorTable"]["Constructors"]]


def _parse_classification(mrdata: dict, key: str) -> list[dict]:
    rows = []
    for race in mrdata["RaceTable"]["Races"]:
        season, rnd = int(race["season"]), int(race["round"])
        for r in race.get(key, []):
            fastest = r.get("FastestLap") or {}
            rows.append(
                {
                    "season": season,
                    "round": rnd,
                    "driver_id": r["Driver"]["driverId"],
                    "constructor_id": r["Constructor"]["constructorId"],
                    "car_number": _int(r.get("number")),
                    "grid": _int(r.get("grid")),
                    "position": _int(r.get("position")),
                    "position_text": r.get("positionText"),
                    "points": _float(r.get("points")),
                    "laps": _int(r.get("laps")),
                    "status": r.get("status"),
                    "time_millis": _int((r.get("Time") or {}).get("millis")),
                    "time_text": (r.get("Time") or {}).get("time"),
                    "fastest_lap_rank": _int(fastest.get("rank")),
                    "fastest_lap_number": _int(fastest.get("lap")),
                    "fastest_lap_time": (fastest.get("Time") or {}).get("time"),
                    "fastest_lap_speed_kph": _float(
                        (fastest.get("AverageSpeed") or {}).get("speed")
                    ),
                }
            )
    return rows


def parse_results(mrdata: dict) -> list[dict]:
    return _parse_classification(mrdata, "Results")


def parse_sprint_results(mrdata: dict) -> list[dict]:
    """Sprint classifications (2021+); earlier seasons return an empty page."""
    return _parse_classification(mrdata, "SprintResults")


def parse_driver_standings(mrdata: dict) -> list[dict]:
    rows = []
    for sl in mrdata["StandingsTable"]["StandingsLists"]:
        season, rnd = int(sl["season"]), int(sl["round"])
        for s in sl.get("DriverStandings", []):
            constructors = s.get("Constructors") or []
            rows.append(
                {
                    "season": season,
                    "round": rnd,
                    "position": _int(s.get("position")),
                    "position_text": s.get("positionText"),
                    "points": _float(s.get("points")),
                    "wins": _int(s.get("wins")),
                    "driver_id": s["Driver"]["driverId"],
                    "constructor_id": constructors[-1]["constructorId"] if constructors else None,
                }
            )
    return rows


def parse_constructor_standings(mrdata: dict) -> list[dict]:
    rows = []
    for sl in mrdata["StandingsTable"]["StandingsLists"]:
        season, rnd = int(sl["season"]), int(sl["round"])
        for s in sl.get("ConstructorStandings", []):
            rows.append(
                {
                    "season": season,
                    "round": rnd,
                    "position": _int(s.get("position")),
                    "position_text": s.get("positionText"),
                    "points": _float(s.get("points")),
                    "wins": _int(s.get("wins")),
                    "constructor_id": s["Constructor"]["constructorId"],
                }
            )
    return rows


# ---------- schemas, keys and the staging plan ----------

SCHEMAS: dict[str, pa.Schema] = {
    "seasons": pa.schema([("season", pa.int32()), ("url", pa.string())]),
    "circuits": pa.schema(
        [
            ("circuit_id", pa.string()),
            ("name", pa.string()),
            ("locality", pa.string()),
            ("country", pa.string()),
            ("lat", pa.float64()),
            ("lng", pa.float64()),
            ("url", pa.string()),
        ]
    ),
    "races": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("name", pa.string()),
            ("circuit_id", pa.string()),
            ("date", pa.date32()),
            ("time", pa.string()),
            ("has_sprint", pa.bool_()),
            ("url", pa.string()),
        ]
    ),
    "drivers": pa.schema(
        [
            ("driver_id", pa.string()),
            ("code", pa.string()),
            ("permanent_number", pa.int32()),
            ("given_name", pa.string()),
            ("family_name", pa.string()),
            ("date_of_birth", pa.date32()),
            ("nationality", pa.string()),
            ("url", pa.string()),
        ]
    ),
    "constructors": pa.schema(
        [
            ("constructor_id", pa.string()),
            ("name", pa.string()),
            ("nationality", pa.string()),
            ("url", pa.string()),
        ]
    ),
    "results": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("driver_id", pa.string()),
            ("constructor_id", pa.string()),
            ("car_number", pa.int32()),
            ("grid", pa.int32()),
            ("position", pa.int32()),
            ("position_text", pa.string()),
            ("points", pa.float64()),
            ("laps", pa.int32()),
            ("status", pa.string()),
            ("time_millis", pa.int64()),
            ("time_text", pa.string()),
            ("fastest_lap_rank", pa.int32()),
            ("fastest_lap_number", pa.int32()),
            ("fastest_lap_time", pa.string()),
            ("fastest_lap_speed_kph", pa.float64()),
        ]
    ),
    "driver_standings": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("position", pa.int32()),
            ("position_text", pa.string()),
            ("points", pa.float64()),
            ("wins", pa.int32()),
            ("driver_id", pa.string()),
            ("constructor_id", pa.string()),
        ]
    ),
    "constructor_standings": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("position", pa.int32()),
            ("position_text", pa.string()),
            ("points", pa.float64()),
            ("wins", pa.int32()),
            ("constructor_id", pa.string()),
        ]
    ),
}
SCHEMAS["sprint_results"] = SCHEMAS["results"]

# Natural keys used for deduplication. Results are keyed on the entry (a driver may share a
# car in the 1950s, so the position alone is not unique).
KEYS: dict[str, tuple[str, ...]] = {
    "seasons": ("season",),
    "circuits": ("circuit_id",),
    "races": ("season", "round"),
    "drivers": ("driver_id",),
    "constructors": ("constructor_id",),
    "results": ("season", "round", "driver_id", "constructor_id"),
    "sprint_results": ("season", "round", "driver_id", "constructor_id"),
    "driver_standings": ("season", "driver_id"),
    "constructor_standings": ("season", "constructor_id"),
}

# Staging entity -> (raw entity it is derived from, parser).
PLAN: dict[str, tuple[str, Callable[[dict], list[dict]]]] = {
    "seasons": ("seasons", parse_seasons),
    "circuits": ("races", parse_circuits),
    "races": ("races", parse_races),
    "drivers": ("drivers", parse_drivers),
    "constructors": ("constructors", parse_constructors),
    "results": ("results", parse_results),
    "sprint_results": ("sprint_results", parse_sprint_results),
    "driver_standings": ("driver_standings", parse_driver_standings),
    "constructor_standings": ("constructor_standings", parse_constructor_standings),
}


def dedupe(rows: Iterable[dict], key: tuple[str, ...]) -> list[dict]:
    """Keep the last occurrence of each key (later seasons carry fresher driver metadata)."""
    seen: dict[tuple, dict] = {}
    for row in rows:
        seen[tuple(row[k] for k in key)] = row
    return list(seen.values())


def stage_entity(store: RawStore, staging_dir: Path, entity: str) -> int:
    raw_entity, parser = PLAN[entity]
    rows = dedupe(
        (r for _, page in store.iter_pages(raw_entity) for r in parser(page)), KEYS[entity]
    )
    table = pa.Table.from_pylist(rows, schema=SCHEMAS[entity])
    staging_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, staging_dir / f"{entity}.parquet", compression="zstd")
    log.info("staged %s: %d rows", entity, table.num_rows)
    return table.num_rows


def stage_all(store: RawStore, staging_dir: Path) -> dict[str, int]:
    return {entity: stage_entity(store, staging_dir, entity) for entity in PLAN}
