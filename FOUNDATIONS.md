# F1 Portfolio — Project Foundations

Planning baseline updated 13 October 2026. [Implementation map](README.md) · [Validation protocol](docs/VALIDATION.md). This document describes the intended system; acceptance requires evidence, not a completed checklist alone.

## Purpose

Demonstrate industrial data engineering, applied AI and architecture through a public motorsport lab. Connect public historical/post-session sources to a separate stream of game-generated telemetry. The project is personal work; it does not claim professional F1 employment or equivalence to a team's private telemetry.

## Eight cases

1. **f1-data-platform** — Python ETL from Jolpica into raw JSON, typed staging Parquet and DuckDB marts. Resumability, pagination, rate-limit handling and quality checks are core concerns. Full-history runtime must be measured; it depends on entity scope, API limits and network behavior. The component README is actively maintained alongside implementation.
2. **box-box** — planned Rust historian: streaming ingestion, batch import, Parquet storage, swinging-door compression, range queries and downsampling via HTTP. The current service is a health scaffold. Batch rows into appropriately sized files/row groups; do not assume a file per tag at streaming frequency is efficient.
3. **f1-telemetry-lab** — Streamlit dashboards over the historian API. Compare speed, throttle and braking by lap distance. Label any direct FastF1 fallback so it cannot be mistaken for successful historian integration. Label source, units, quality and replay mode.
4. **f1-history-agent** — read-only statistics tools over DuckDB plus retrieval for narrative. Version a golden question set including unanswerable and ambiguous questions. Query limits, allowlisted access, timeouts, provenance and abstention are required. A headless model adapter is an implementation option; provider authentication, usage limits, cost and terms still apply. No model request may write game controls directly.
5. **f1-strategy-ml** — later degradation/pit-window experiments. Use chronological splits and separate simulator data from real-world sources. Known simulator settings are useful experimental controls, not proof of transfer to real racing.
6. **f1-mobile** — later Flutter client over stable query APIs; offline caching and a live pit-wall view remain planned.
7. **f1-sim-connector** — Python edge ingestion, protocol validation, tag mapping, filtering, quality flags and delivery. Header parsing/filter/buffer prototypes exist; packet bodies, live capture, durable spool and integration remain gates. The present in-memory queue can evict old samples and does not survive process restart.
8. **f1-sim-driver** — Python distance-indexed lap-script schema, interpolation, bounded position correction and local edits. Connected control and model-assisted optimisation are not implemented. The executor needs validated state handling, control stability and platform adapters before it can be used as an experimental driver.

## Telemetry path and contracts

Game UDP or an immutable packet capture → one capture/fan-out layer → connector → box-box → dashboard. The fan-out also supplies low-latency state to the controller independently of storage availability. Do not assume a console configured for one UDP endpoint feeds two different Compose ports automatically. Record configured versus measured packet rates rather than promising a fixed 60 Hz for every packet type.

A sample contract should identify origin, game/protocol version, session UID, stream/car, frame/sequence, tag, unit, event time, receive time and quality. Keep session and replay identities separate; specify handling of duplicate/out-of-order packets, session resets and missing frames. A tag such as SIM.CAR0.SPEED alone is not a unique identity across sessions.

Preserve an immutable raw reference capture for validation. Edge exception filtering and historian compression have a shared fidelity budget: include maximum silence/heartbeat handling, per-signal deviations, event timing error and total reconstruction error. Durable buffering needs bounded disk use, explicit overflow policy, restart recovery and observable loss counters. Never call the current in-memory buffer lossless.

## AI lap experiments

The LLM acts as an offline lap editor. It reads bounded telemetry summaries and proposes one or two local changes. A validator rejects invalid ranges and unsupported operations. A deterministic controller executes accepted scripts; telemetry, validity and failures are archived with the script and diff. A human can stop the experiment.

Distance indexing reduces sensitivity to timing drift, but does not guarantee control stability. Establish a baseline with speed/heading-aware state handling as needed, lap resets, stale telemetry behavior, command limits and repeatability. The present lateral-offset edit changes metadata that the executor does not consume. Segment shifts can move multiple controls and create collisions; validate semantics and continuity before claiming braking-point optimisation.

**Hardware feasibility is an early spike.** Verify a currently supported Windows input mechanism and PS5 adapter/controller compatibility on the intended game and hardware. ViGEm is end-of-life; do not commit to it as a maintained dependency. No current claim of PS5 automated control. All proposed control experiments are offline simulator sessions.

Compare model-assisted editors to unchanged replay and a simple non-LLM edit/search baseline. Hold track, car, setup, fuel, tyres, assists, weather, game version and observations constant where possible. Randomise order, repeat trials and retain invalid laps. Report median/spread, valid-lap rate, failures, latency and cost in addition to best lap. Log model versions, prompts, budgets and seeds where available. Equal iteration counts alone do not establish a fair comparison. See VALIDATION.md.

## Real versus simulator data and motion

Distance-aligned overlays are exploratory: different physics, settings, sampling and conditions prevent a direct equivalence claim. Test generalisation rather than asserting it.

A motion rig is an optional later component. Live motion cues would use low-latency telemetry fan-out; historical replay could estimate cues from public position/speed signals. Differentiation and coordinate assumptions can amplify noise. Estimated cues do not reproduce actual driver forces. Independent hardware limits, an emergency stop and validated cueing would be required before physical motion; these are not part of the first software release.

## Delivery order

1. Preserve the ongoing ETL implementation and expose a small, verifiable historical slice. In parallel, check packet and input-adapter feasibility.
2. Complete one recorded-session path through capture, connector, historian and dashboard. Do not require full historical backfill to demonstrate this slice.
3. Demonstrate restart/outage recovery, data-quality semantics and bounded resource usage.
4. Measure raw versus filtered/compressed fidelity, throughput and query behavior with reproducible fixtures.
5. Establish repeatable non-LLM control before introducing model-generated edits.
6. Add history-agent evaluations and controlled lap-edit experiments as separate testable capabilities.
7. Expand to strategy ML, mobile and optional motion research after the underlying APIs and evidence are stable.

## Repository standards

- English code, identifiers, comments, documentation, commit messages and CI. Public website and creator content have separate EN/PT versions.
- One monorepo, one folder per case; shared Compose for runnable services. Scaffold containers are not evidence of working integration.
- Python with uv, Ruff and pytest; Rust with cargo fmt, clippy and tests. Keep tests tied to requirements and actual failure modes.
- Every milestone includes run instructions, fixture/source provenance, limitations and evidence. CI definitions alone do not prove passing runs.
- Use rodrigo@deepcode.com.br for commits. No Claude co-authorship or generated-by attribution in commits or PRs.
- MIT source code; third-party data retains its own terms. Jolpica data: CC BY-NC-SA 4.0. FastF1's software license does not relicense its underlying data.

## Public communication

The author is Rodrigo Manso, supported by DeepCode. Produce separate English and Portuguese videos from the same technical evidence. Publish milestones and failures, not promised performance. The current résumé may describe prototype implementation; it must not claim an integrated live platform, AI lap gains or motion-rig results before validation. No channel handle is assumed available.

## Decision history

2026-10-12: monorepo scaffold, box-box naming and proposed eight-case foundation (initially six cases).
2026-10-13: connector and driver prototypes extend the scope to eight cases; telemetry reliability and reproducible AI evaluation become the delivery gates. Motion remains optional. The previous unconditional control, lossless buffering, no-cost inference and real-force replay claims are superseded by this baseline.

## References

- [Jolpica data terms](https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md)
- [ViGEm end-of-life notice](https://docs.nefarius.at/projects/ViGEm/End-of-Life/)

## Role-aligned stack plan

[STACK-ALIGNMENT.md](docs/STACK-ALIGNMENT.md) records the target language allocation against the Williams and EPAM roles. Add a C++20 driver runtime while keeping Python for script authoring and reference tests; retain Rust for box-box. Prioritise a future React/TypeScript web client over the deferred Flutter client. These are planned changes; current Python prototypes and implementation status remain unchanged.
