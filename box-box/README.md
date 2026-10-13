# box-box

**Case 2 — Industrial historian in Rust.** A minimal **PIMS** (Process Information
Management System) inspired by industrial historians (AVEVA PI), applied to F1 telemetry.
"Box, box" is the radio call for a pit stop: the moment the car comes in and the data goes out.

> Status (13 October 2026): v1 implemented and exercised locally: HTTP ingest with
> per-sample validation, swinging-door compression per tag, write-ahead log plus Parquet
> segments, restart recovery, range queries with downsampling, interpolation and metrics.
> Evidence from a synthetic load, a SIGKILL recovery and a fidelity comparison is recorded in
> [docs/evidence/2026-10-13-box-box-v1.md](../docs/evidence/2026-10-13-box-box-v1.md).
> Not yet done: a FastF1 batch importer, per-tag retention, authentication, and any run
> against real game packets (that path depends on `f1-sim-connector`).

## What it does

```
POST /ingest ─▶ validate ─▶ swinging door (per tag) ─▶ WAL append ─▶ fsync ─▶ ack
                                                            │
                                   tail (RAM) ──flush_rows──┴─▶ seg-NNNNNN.parquet
GET /query ◀── merge(segments, tail) ─▶ dedupe ─▶ downsample (min/max | avg | raw)
```

| Concern | Implementation |
|---|---|
| Data model | session × tag × point `(ts ns UTC, value f64, quality)`; quality ∈ good, bad, stale, substituted |
| Validation | session and tag alphabets, finite values, strictly increasing timestamps per tag; `duplicate` and `out_of_order` are counted separately from other rejections |
| Compression | swinging-door trending per tag; `deviation` is the guaranteed bound on linear-reconstruction error (doors use `deviation / 2`); quality changes and `max_interval` (heartbeat, default 1 s) force archiving |
| Durability | every archived point is appended to a per-session WAL; the batch is acknowledged after `fsync` (`BOXBOX_FSYNC=false` keeps only the OS flush). WAL is folded into zstd Parquet segments every `BOXBOX_FLUSH_ROWS` rows, on `/flush` and on graceful shutdown |
| Recovery | on start, segments are indexed, the WAL is replayed and per-tag ordering is restored. Points still *held* in a swinging door at crash time are lost: at most one archived gap per tag, bounded by `max_interval` |
| Query | `/query` merges segments and tail, deduplicates by timestamp and downsamples with min/max buckets (peaks survive), average, or raw with a cap; `/interpolate` gives the value at a time |
| Observability | per-session counters `offered, accepted, rejected, duplicate, out_of_order, archived, persisted, flushed, pending` and receive-to-accept latency on `/metrics` (Prometheus text) and `/sessions/{id}` |
| Interop | segments are plain Parquet (`tag, ts, value, quality`), readable by DuckDB, pandas or Polars without the service |

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, version, uptime, session count |
| POST | `/ingest` | `{"samples": [{"session", "tag", "ts", "value", "quality"?, "seq"?, "recv_ts"?, "unit"?}]}` → per-sample rejections and counts |
| GET | `/sessions` · `/sessions/{id}` | stats and counters |
| GET | `/sessions/{id}/tags` | tags, units, deviation, heartbeat, row counts, pending flag |
| POST | `/sessions/{id}/flush` | archive held points and write a segment |
| GET | `/query?session=&tags=a,b&from=&to=&max_points=2000&agg=minmax\|avg\|raw` | points as `[ts, value, quality]` per tag |
| GET | `/interpolate?session=&tag=&ts=` | linear value at time |
| GET | `/metrics` | Prometheus exposition |

Timestamps are nanoseconds since the Unix epoch, UTC. A sample's `ts` is the source event
time (game frame); `recv_ts` is when the edge received it and feeds the latency metric only.

## Run

```bash
docker compose up box-box                # http://localhost:8081/health
cargo run --release                      # local, same port, data in ./data
cargo test && cargo clippy --all-targets -- -D warnings
```

| Variable | Default | Meaning |
|---|---|---|
| `BOXBOX_BIND` | `0.0.0.0:8081` | listen address |
| `BOXBOX_DATA_DIR` | `./data` (`/data` in Docker) | `sessions/<id>/{wal.log, seg-*.parquet}` |
| `BOXBOX_FSYNC` | `true` | fsync WAL on every acknowledged batch and each segment |
| `BOXBOX_DEVIATION` | `0` | default swinging-door deviation (0 = drop only collinear points) |
| `BOXBOX_MAX_INTERVAL_MS` | `1000` | heartbeat: archive at least one point per interval (0 disables) |
| `BOXBOX_FLUSH_ROWS` | `100000` | tail rows per session before a Parquet segment is written |
| `BOXBOX_TAG_RULES` | unset | JSON file: `{"tags": [{"pattern": "SIM.CAR*.SPEED", "deviation": 0.5, "max_interval_ms": 1000}]}` |

Quick smoke test:

```bash
curl -s -X POST localhost:8081/ingest -H 'content-type: application/json' -d '{"samples":[
  {"session":"demo","tag":"SIM.CAR0.SPEED","ts":1000000000,"value":100,"unit":"km/h"},
  {"session":"demo","tag":"SIM.CAR0.SPEED","ts":2000000000,"value":110},
  {"session":"demo","tag":"SIM.CAR0.SPEED","ts":3000000000,"value":90}]}'
curl -s 'localhost:8081/query?session=demo&tags=SIM.CAR0.SPEED'
curl -s 'localhost:8081/interpolate?session=demo&tag=SIM.CAR0.SPEED&ts=1500000000'
```

## Known limits of v1

- One process, one mutex around session state; Parquet reads happen outside it, but a
  segment flush runs inside an ingest call and shows up as a latency spike on that request.
- Queries scan whole segments for a tag (no row-group pruning yet); fine for session-sized
  data, not for months of history.
- No retention, deletion, authentication or TLS. Put it behind a reverse proxy if exposed.
- The compression ratio reported in the evidence file comes from a smooth synthetic signal;
  expect much lower ratios on real telemetry. The fidelity bound, not the ratio, is the claim.

FastF1 software is MIT licensed; underlying data terms are separate. Unofficial project, not affiliated with Formula 1.
