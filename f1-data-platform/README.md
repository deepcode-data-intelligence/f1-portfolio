# f1-data-platform

**Case 1 — Data engineering.** Layered ETL of the complete Formula 1 history
(1950–today) from the [Jolpica-F1](https://github.com/jolpica/jolpica-f1) API into
**DuckDB + Parquet**, with data-quality checks, idempotent and resumable loads, and a
rate-limit-aware backfill.

> Status: 🚧 in progress. The full pipeline runs end to end (backfill → stage → build → check)
> and is verified live against the API. Next: full-history backfill, lap-level entities.

## Architecture

```
Jolpica-F1 API ──▶ raw ─────────────▶ staging ───────────────▶ marts
                   JSON pages,         typed Parquet,           DuckDB tables + views
                   one file per page   one file per entity      (f1.duckdb)
                   _COMPLETE markers   explicit Arrow schemas   consumed by f1-history-agent
                   resumable           deduplicated on keys     and f1-strategy-ml
```

| Layer | Module | What it guarantees |
|---|---|---|
| Client | `jolpica.py`, `ratelimit.py` | Pagination; both API limits honoured client-side (burst 4/s, 500/h); retries with backoff on 429/5xx |
| Raw | `raw.py`, `extract.py` | Pages stored as fetched under `raw/<entity>/season=<YYYY>/`; a partition is visible downstream only after its `_COMPLETE` marker; complete partitions are skipped on re-run (current season refreshed by default) |
| Staging | `staging.py` | Flat rows with explicit Arrow schemas, deduplicated on natural keys, written as zstd Parquet |
| Marts | `marts.py` | One DuckDB table per entity plus views: `race_summary`, `driver_season_summary`, `constructor_season_summary`, `champions` |
| Quality | `quality.py` | Uniqueness, referential integrity and sanity checks; `f1-data check` exits non-zero on failure |

Entities: seasons, circuits, races, drivers, constructors, results, sprint results,
driver standings, constructor standings. Lap times and pit stops belong to the telemetry
side of the platform (`box-box`).

## Run

```bash
# canonical (from repo root): full history, ~850 requests, about two hours at 500 req/h
docker compose --profile etl run etl run

# local development
uv sync
uv run f1-data run --from 2024 --to 2024     # one season end to end (≈12 requests)
uv run f1-data backfill                      # resumable; safe to interrupt and re-run
uv run f1-data stage && uv run f1-data build && uv run f1-data check
uv run pytest
```

`F1_DATA_DIR` (default `./data`) holds `raw/`, `staging/` and `f1.duckdb`.

## Querying

```sql
-- duckdb data/f1.duckdb
SELECT season, driver, driver_points, constructor FROM champions ORDER BY season DESC LIMIT 5;
SELECT code, wins, podiums, poles, points FROM driver_season_summary WHERE season = 2024 ORDER BY points DESC;
```

## Data & attribution

Jolpica-F1 (CC BY 4.0). Unofficial project, not affiliated with Formula 1.
