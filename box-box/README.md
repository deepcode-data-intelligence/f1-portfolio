# box-box

> Status clarification — 13 October 2026: The table below is the target v1 scope; only the health scaffold is implemented. FastF1 software licensing does not grant blanket data redistribution rights. See [validation gates](../docs/VALIDATION.md).

**Case 2 — Industrial historian in Rust.** A minimal **PIMS** (Process Information
Management System) inspired by industrial historians (AVEVA PI), applied to F1 telemetry.
"Box, box" is the radio call for a pit stop: the moment the car comes in and the data goes out.

> Status: scaffold (`/health` only).

## Planned v1 scope

| Concept | Implementation |
|---|---|
| Data model | tags (`VER.speed`, `HAM.brake`, …) × samples (timestamp, value, quality) |
| Ingestion | FastF1 session importer (batch) **and** streaming endpoint with session replay |
| Storage | partitioned Parquet (session / tag / time window) via `arrow-rs` |
| Compression | **swinging-door** (exception + compression deviation), with reported ratio |
| Query API | HTTP (axum): tag + range, downsampling (avg/min/max per window), interpolation |

## Run

```bash
docker compose up box-box                # http://localhost:8081/health
cargo run                                # local, same port
cargo test && cargo clippy --all-targets -- -D warnings
```

Environment: `BOXBOX_BIND` (default `0.0.0.0:8081`), `BOXBOX_DATA_DIR` (default `/data`).

FastF1 software is MIT licensed; underlying data terms are separate. Unofficial project, not affiliated with Formula 1.
