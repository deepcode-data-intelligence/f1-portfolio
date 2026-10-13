# f1-data-platform

**Case 1 — Data engineering.** Layered ETL of the complete Formula 1 history
(1950–today) from the [Jolpica-F1](https://github.com/jolpica/jolpica-f1) API into
**DuckDB + Parquet**, with data-quality tests, idempotent loads and a rate-limit-aware
backfill.

> Status: scaffold. Pipelines land next.

## Architecture

```
Jolpica-F1 API ──▶ raw (JSON, as fetched) ──▶ staging (typed Parquet) ──▶ marts (DuckDB views/tables)
                   idempotent, resumable        schema-validated            consumed by f1-history-agent
```

Entities in scope: seasons, races, drivers, constructors, results, standings.
Lap times and pit stops belong to the telemetry side (`box-box`).

## Run

```bash
# canonical (from repo root)
docker compose --profile etl run etl --help

# local development
uv sync && uv run f1-data --help
uv run pytest
```

## Data & attribution

Jolpica-F1 (CC BY 4.0). Unofficial project, not affiliated with Formula 1.
