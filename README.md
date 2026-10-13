# F1 Data Platform — an applied-engineering portfolio

An end-to-end data & AI platform built around Formula 1 public data, designed as a set of
integrated cases that demonstrate applied knowledge across **data engineering, industrial
time-series systems, real-time edge connectors, applied AI/RAG, dashboards, machine learning and mobile**.

> 🏗️ **Status: scaffolded.** Architecture and scope are defined (see below) and every case has
> its skeleton, CI and Docker image in this monorepo; implementation is happening case by case.
>
> 📄 Full solution overview (architecture, infrastructure, BPM process diagrams, glossary):
> **https://deepcode.com.br/f1/**

## Why F1?

Formula 1 generates rich public data (70+ years of history, modern telemetry) and its
engineering culture mirrors industrial operations: telemetry historians, real-time dashboards,
strategy models. This platform intentionally reuses patterns from regulated industrial
environments — where its author works daily (AVEVA PI System, GxP) — and rebuilds them
from scratch in the open.

## The platform

```mermaid
flowchart LR
    J[Jolpica-F1 API<br/>history 1950–today] --> DP[f1-data-platform<br/>Python ETL · DuckDB/Parquet]
    FF[FastF1<br/>post-session telemetry] --> PIMS[box-box<br/>Rust historian · Parquet<br/>swinging-door compression]
    PS5[F1 game on PS5<br/>UDP telemetry · 60 Hz] --> SIM[f1-sim-connector<br/>Python edge connector<br/>exception filter · store-and-forward]
    SIM --> PIMS
    PS5 -. real time .-> RIG[motion rig]
    PS5 --> DRV[f1-sim-driver<br/>scripted lap executor<br/>distance-indexed · position hold]
    PIMS --> ED[AI lap editor<br/>Claude · ChatGPT]
    ED -- lap script --> DRV
    DRV -- game inputs --> PS5
    PIMS -. replay · derived G-forces .-> RIG
    DP --> AG[f1-history-agent<br/>FastAPI · RAG + SQL tools<br/>+ /stats REST API]
    PIMS --> TL[f1-telemetry-lab<br/>Streamlit dashboards]
    DP --> ML[f1-strategy-ml<br/>tyre & pit-stop models]
    AG --> MOB[f1-mobile<br/>Flutter · Android/iOS]
    PIMS --> MOB
```

| # | Case | Focus | Stack | Status |
|---|------|-------|-------|--------|
| 1 | [`f1-data-platform`](f1-data-platform/) | Data engineering: layered ETL of full F1 history | Python, DuckDB, Parquet | 🚧 in progress |
| 2 | [`box-box`](box-box/) | A minimal industrial historian (PIMS) for telemetry: tag/time-series model, swinging-door compression, query API | Rust, Arrow/Parquet, axum | 🧱 scaffold |
| 3 | [`f1-telemetry-lab`](f1-telemetry-lab/) | PI-Vision-style comparative telemetry dashboards | Python, Streamlit, FastF1 | 🧱 scaffold |
| 4 | [`f1-history-agent`](f1-history-agent/) | Headless AI agent: RAG over F1 history + SQL tool-calling for exact stats, with automated evals | Python, FastAPI, local embeddings | 🧱 scaffold |
| 5 | [`f1-strategy-ml`](f1-strategy-ml/) | Tyre degradation & pit-window models | Python, scikit-learn | 📋 phase 2 |
| 6 | [`f1-mobile`](f1-mobile/) | Mobile client for the platform APIs: natural-language Q&A, stats explorer, telemetry charts, live pit wall, offline-first | Flutter/Dart | 📋 phase 2 |
| 7 | [`f1-sim-connector`](f1-sim-connector/) | Edge connector (PI Interface pattern) for the F1 game's live UDP telemetry: parser, tag mapping, edge exception compression, store-and-forward, quality flags | Python | 🧱 scaffold |
| 8 | [`f1-sim-driver`](f1-sim-driver/) | Scripted lap executor: an AI analyses a lap, writes the next one as a distance-indexed script, the executor plays it. Hosts the "AI race engineers" competition (Claude vs ChatGPT, best valid lap wins) | Python | 🧱 scaffold |

## Run the platform

```bash
docker compose up                      # box-box :8081 · history-agent :8080 · telemetry-lab :8501 · sim-connector udp/20777
docker compose --profile etl run etl   # one-shot history ETL (writes the shared DuckDB volume)
```

Each case folder has its own README with local-development instructions (`uv` for Python, `cargo` for Rust).

## Two classes of data

Public F1 sources are **historical or post-session** (Jolpica, FastF1). The F1 game's UDP stream adds
what an industrial historian exists to handle: **live telemetry at 60 Hz with a known car setup**.
That enables the platform's showcase features — overlaying your own game lap on a real driver's lap
aligned by distance, training tyre-degradation models in a controlled environment and testing them
against real data (domain shift), replaying a real lap on a motion rig using G-forces derived
from position and speed, and letting AI models compete as race engineers: analyse a lap, script the
next one, execute it, repeat.

## Design principles

- **Integration over isolation** — every case consumes or feeds another; the platform tells one architecture story.
- **The AI engineers, it does not drive** — LLM latency rules out real-time control; the AI writes the next lap as a script and a dumb executor plays it.
- **Exact numbers, never hallucinated** — the AI agent answers stats via SQL tool-calling; RAG is reserved for narrative.
- **Industrial patterns in the open** — the PIMS case implements the historian concepts (tags, compression deviation, downsampling) that usually live behind enterprise licenses.
- **Evaluation as a feature** — the agent ships with a golden Q&A eval set and automated scoring.
- **Docker-first** — every runnable case ships a `Dockerfile` and `docker-compose.yml`; `docker compose up` is the only requirement to bring it up. Local toolchains (uv, cargo) are optional, for development only.

## Author

**Rodrigo Manso** — AI Solutions Architect, founder of [DeepCode Inteligência de Dados](https://deepcode.com.br).
25 years building mission-critical systems for healthcare, government and the pharmaceutical
industry (GxP-regulated environments, AVEVA PI System). [LinkedIn](https://www.linkedin.com/in/rodrigolmanso/)

## Data sources & attribution

[Jolpica-F1](https://github.com/jolpica/jolpica-f1) (Ergast successor) · [FastF1](https://github.com/theOehrly/Fast-F1) (MIT) · Wikipedia (CC BY-SA) ·
game telemetry generated by the author's own sessions of EA's F1 game (track and car content belong to EA and Formula One Licensing B.V.).
This is an unofficial project and is not associated in any way with Formula 1 companies or EA. F1 and related marks are trademarks of Formula One Licensing B.V.

## License

MIT
