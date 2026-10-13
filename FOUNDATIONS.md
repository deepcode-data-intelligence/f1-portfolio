# F1 Portfolio — Project Foundations

> Public monorepo: https://github.com/rodrigolmanso/f1-portifolio — one directory per case. The README presents the platform; this document is the planning baseline.
> Solution page: https://deepcode.com.br/f1/
>
> Status: scaffold completed on 2026-10-12 (structure, CI, Docker and smoke tests for every case). `f1-sim-connector` added on 2026-10-13. Implementation starts with case 1.

## Vision

A public GitHub portfolio (`github.com/rodrigolmanso`) that demonstrates, on an F1 theme, the skills the CV claims: **data engineering, applied AI/RAG, telemetry dashboards, ML and industrial data systems**. The cases are not isolated projects — they form an **integrated platform** that tells one end-to-end architecture story:

```
                    ┌────────────────────┐
   Jolpica API ───▶ │  f1-data-platform   │──▶ f1.duckdb (history 1950–today)
   (history)        │  (Python ETL)       │         │
                    └────────────────────┘         ├──▶ f1-history-agent (RAG + tools + /stats API)
                                                   │        └──▶ f1-mobile (Flutter, phase 2)
                                                   └──▶ f1-strategy-ml (phase 2)
                    ┌────────────────────┐
   FastF1 ────────▶ │  box-box            │──▶ Parquet time-series (telemetry)
   (post-session)   │  (Rust historian)   │         │
                    └────────────────────┘         ├──▶ f1-telemetry-lab (dashboards)
                             ▲                     ├──▶ f1-strategy-ml · f1-history-agent · f1-mobile
                             │                     └──▶ motion rig (replay: G-forces derived from real laps)
                    ┌────────────────────┐
   PS5 F1 game ───▶ │  f1-sim-connector   │   (live UDP, 60 Hz, known car setup)
   (UDP telemetry)  │  (edge connector)   │
                    └────────┬───────────┘
                             └──────────────────────▶ motion rig (real time, reads UDP directly)
```

Data sources fall into two classes, and the platform deliberately covers both:

- **Historical / post-session** (Jolpica, FastF1): what the public F1 data world offers.
- **Live streaming** (the F1 game's UDP telemetry): what an industrial historian exists to handle — a 60 Hz stream with a *known* car setup, something real F1 public data never exposes.

## The cases

### 1. `f1-data-platform` — Data engineering (Python)
ETL of the complete F1 history (Jolpica-F1 API, the Ergast successor) → raw/staging/marts layers in **DuckDB + Parquet**. Data-quality tests, idempotency, rate limit respected (500 req/h → the full backfill runs in the background for ~2 h; incremental loads are cheap afterwards). Entity scope: seasons, races, drivers, constructors, results, standings (lap times / pit stops stay with the historian / FastF1).

### 2. `box-box` — Minimal historian in Rust + Parquet
*("Box, box": the radio call for a pit stop — the car comes in, the data goes out.)*
A **minimal PIMS (Process Information Management System)**, inspired by industrial historian architecture (AVEVA PI), applied to F1 telemetry:

- **Data model**: tags (e.g. `VER.speed`, `HAM.brake`, `SIM.CAR0.SPEED`, `SIM.CAR0.TYRE.FL.TEMP`) × time series (timestamp, value, quality) — the classic historian model.
- **Ingestion**: (a) FastF1 session importer (batch, via an intermediate export); (b) streaming ingestion endpoint used by `f1-sim-connector` for live data and by session replay — the OT → storage path.
- **Storage**: **partitioned Parquet** (session / tag / time window) written with the `arrow-rs` / `parquet` crates — columnar, natively compressed, readable by any engine (DuckDB, pandas, Spark).
- **Historian compression**: implementation of the **swinging-door** algorithm (exception / compression deviation — the same concept as PI Server) with the compression ratio reported. This is THE technical differentiator of the case; very few people outside the industrial world know it. With the sim connector it is exercised on live, noisy data.
- **Query API**: HTTP (axum) — tag + range lookup, downsampling / aggregations (avg/min/max per window), interpolation. Consumed by case 3.
- **Why Rust**: predictable performance and latency for continuous time-series writes plus memory safety — and it adds Rust to the portfolio without leaving the author's domain.

### 3. `f1-telemetry-lab` — Comparative dashboards (Python/Streamlit)
PI Vision-style panels: driver vs driver per lap (speed / throttle / brake by distance), gaps, stint degradation, positions. **Consumes the `box-box` Query API** (FastF1 direct read as fallback) — which turns two cases into one integrated architecture. Showcase panel: **overlay your own game lap on a real driver's lap** at the same circuit, aligned by distance travelled rather than time — braking point, minimum speed and throttle-on point side by side. Deployed to Streamlit Community Cloud.

### 4. `f1-history-agent` — RAG + headless agent (Python/FastAPI)
Internal hybrid API (`POST /ask`): **tool-calling → SQL** on the case 1 DuckDB for exact facts + **RAG** (Wikipedia, local embeddings, lightweight vector store) for narrative. Pluggable inference: `LLMBackend` with `ClaudeHeadlessBackend` (`claude -p`, no API cost) and `InternalAPIBackend` (the internal API the author will build). Automated eval with ~50 golden question/answer pairs. Also gains SQL tools over the user's own sim sessions ("which setup gave me my best sector 2 at Interlagos?") with exact numbers, following the project principle. Load the `claude-api` skill before coding this part.

### 5. `f1-strategy-ml` — Strategy ML (phase 2)
Tyre degradation / pit window with data from cases 1, 2 and 7. The game becomes a **controlled laboratory**: train the degradation model with known setup, fuel and compound, then test whether it generalises to real FastF1 data — a *domain shift* discussion nobody makes. Starts only after the first four cases are published.

### 6. `f1-mobile` — Android/iOS app in Flutter (phase 2)
Cross-platform app (**Flutter/Dart**) to interact with the platform's data from a phone:

- **Natural-language queries**: chat screen consuming the `f1-history-agent` API (`POST /ask`) — the RAG agent in your pocket.
- **Stats explorer**: browse seasons, drivers, constructors and results — consumes a **statistics REST API** (read-only endpoints over the case 1 DuckDB, exposed by the same FastAPI service as the agent, e.g. `GET /seasons/{year}/results`).
- **Telemetry**: simple comparative charts (speed by distance) consuming the `box-box` Query API.
- **Live pit wall**: real-time panel during a sim session, fed by the historian.
- **Offline-first**: local cache (SQLite/drift) of recent queries — a mature mobile pattern.
- App architecture: UI → state (Riverpod or Bloc) → repositories → API clients; DeepCode dark theme.
- **Why**: adds mobile to the portfolio and proves the platform is consumable by any client — the internal API becomes a public contract.

> Architecture implication: the case 4 service becomes the **platform gateway** (`/ask` + `/stats/*` endpoints), consumed by the website, the app and third parties.

### 7. `f1-sim-connector` — Edge connector for live game telemetry (Python)
The equivalent of a *PI Interface / PI Connector*. Receives the F1 game's UDP telemetry from the PS5 and feeds `box-box`:

- **UDP parser** for the game's packet format (versioned; packet header + car telemetry, car status, lap data, session, car setup).
- **Tag mapping** into the historian naming scheme: `SIM.CAR{idx}.SPEED`, `SIM.CAR{idx}.THROTTLE`, `SIM.CAR{idx}.TYRE.FL.TEMP`, …
- **Exception compression at the edge** (exception deviation per tag), so the historian receives only meaningful changes.
- **Store-and-forward buffer**: when the historian is unreachable, samples are buffered locally and flushed in order when it comes back.
- **Data quality marking**: every sample carries a quality (good / bad / stale / substituted), the industrial pattern for trusting a value downstream.
- Why it matters: this is the piece that tells the story of a *real-time system*, not just batch ETL, and it is the pattern the author knows from AVEVA PI.

### Motion rig (component, not a case)
A motion simulator **reads the UDP directly**, not the historian — latency matters. The historian still participates in two ways:

1. **Recording actuator commands** for analysis and audit (a GxP parallel).
2. **Replay**: FastF1 does not provide G-forces, but they can be derived from position and speed (lateral ≈ v² × curvature). The rig can therefore **play back a real driver's lap** — something that does not exist off the shelf.

Summary flow:

```
PS5 → UDP → f1-sim-connector → box-box → lab, ML, agent, mobile
PS5 → UDP → motion rig (real time)
FastF1 → box-box → derived G-forces → motion rig (replay)
```

## Execution order

| # | Case | Reason for the order |
|---|------|----------------------|
| 1 | `f1-data-platform` | Data foundation; the long backfill runs in the background |
| 2 | `box-box` (Rust) | Telemetry foundation; the most differentiated case |
| 3 | `f1-sim-connector` | Feeds the historian with live data; exercises streaming ingestion and swinging-door on real noise |
| 4 | `f1-telemetry-lab` | Consumes the historian — proves the integration; game-vs-real overlay |
| 5 | `f1-history-agent` | Consumes the DuckDB; closes the AI loop |
| 6 | `f1-strategy-ml` | Phase 2 |
| 7 | `f1-mobile` (Flutter) | Phase 2 — consumes the stabilised APIs of cases 2 and 5 |

## Standards shared by every case

- **English everywhere**: code, identifiers, comments, docstrings, documents (this file included), commit messages, PRs and CI. No Portuguese in the repository.
- README with a case narrative (problem → architecture with diagram → how to run → demo/screenshots); MIT LICENSE; GitHub Actions CI (tests + lint); disclaimer "unofficial, not affiliated with Formula 1"; source attribution (Jolpica CC BY, FastF1 MIT, Wikipedia CC BY-SA, and for game telemetry: data generated by the author's own sessions of EA's F1 game — track and car content belong to EA / Formula One Licensing B.V.).
- **Docker / Docker Compose is the requirement to bring the project up**: every runnable case (services, ETL, dashboards, connector) ships a `Dockerfile` and is wired into the root `docker-compose.yml`; `docker compose up` is the canonical, documented way to run — whoever clones does not need uv/rustup/Flutter installed (local toolchains remain a development option). Exception: `f1-mobile` (Flutter app) — the app build is native, but the services it consumes come up via compose.
- Commits use the identity `rodrigo@deepcode.com.br`. **Commit messages and PRs NEVER include Claude co-authorship or attribution** (no `Co-Authored-By`, no "Generated with Claude Code").
- Python: managed with `uv` (Python 3.12 pinned in each case's `.python-version`; `ruff` + `pytest`). Rust: stable toolchain via `rustup`, `cargo fmt` + `clippy -D warnings`.
- Cross-links between cases and deepcode.com.br; at the end, a GitHub profile README presenting the platform.

## Decisions taken

**2026-10-12**

1. **Structure**: monorepo `f1-portfolio`, one directory per case (not separate repos). CI with path filters; a single `docker-compose.yml` at the root.
2. **Historian name**: `box-box` (crate `boxbox`, binary `box-box`).
3. **box-box v1 scope**: swinging-door **in v1** + streaming ingestion / session replay **in v1** + HTTP Query API.
4. **Dashboards consume box-box over HTTP** (FastF1 direct read as fallback), never Parquet directly.
5. **Work order**: scaffold every case first (done), then implement in the order of the table above.

**2026-10-13**

6. **New case `f1-sim-connector`** (Python): edge connector for the F1 game's UDP telemetry — parser, tag mapping, edge exception compression, store-and-forward, quality flags. Inserted as step 3 of the execution order.
7. **Motion rig** is a component fed directly by UDP (real time) and by the historian (replay with derived G-forces); not a case of its own.
8. **Everything in English** — code, docs, comments, commits. FOUNDATIONS translated accordingly.

## Tooling prerequisites

- **Docker + Docker Compose** (⚠️ not yet installed on this machine — Docker Desktop, OrbStack or colima; required to bring any case up).
- `uv` (✅ installed via brew, Python 3.12 per project), `rustup`/`cargo` (✅ 1.98 + rustfmt/clippy), `gh` (✅ logged in as rodrigolmanso) — for local development outside containers only.
- PS5 with the F1 game and UDP telemetry enabled on the LAN (for `f1-sim-connector` live runs; packet captures are used for tests and offline development).
