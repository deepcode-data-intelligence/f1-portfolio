# Stack alignment with target roles

Decision baseline: 13 October 2026. This is an implementation plan, not a claim that the planned stack already exists. It supplements FOUNDATIONS.md; the current implementation map remains accurate until code and validation evidence are updated.

## Role evidence

Official listings checked on 13 October 2026:

- [Williams Lead Software Engineer R14209](https://careers.williamsf1.com/job/lead-software-engineer-in-grove-wantage-jid-562): performance-critical C++ **or** Rust; Python; distributed systems and streaming; persistence; CI/CD, containers and infrastructure as code. Technical leadership is central. Both languages are not a combined mandatory requirement.
- [Williams Senior Software Engineer R14213](https://careers.williamsf1.com/job/senior-software-engineer-in-grove-wantage-jid-559): strong experience in one or more of C#, Go, Java, C++, Python or TypeScript. Its estate includes React, C#/C++ desktop applications, Python and C# services. Azure DevOps/Git and communication matter; observability and time-series storage are useful additional evidence.
- [EPAM Senior AI Engineer](https://careers.epam.com/en/vacancy/senior-ai-engineer-bltfe8ig9f73e6bbrzk_en): Python and TypeScript, delivered AI products, evaluation, monitoring and mentoring. Listed as remote in Brazil; the Williams roles list Grove, UK. Portfolio alignment does not resolve relocation, degree or work-authorisation questions.

## Target allocation

| Component | Current | Target decision | Proof needed |
|---|---|---|---|
| box-box | Rust health scaffold | Keep Rust for ingestion, historian persistence, compression and queries | Working storage/query path; profiling; bounded resource use; restart recovery and fidelity tests |
| f1-sim-connector | Python prototypes | Keep Python for the first complete capture/decode/replay path; consider Rust only if profiling identifies a constraint | Versioned packet fixtures, loss accounting, durable delivery and measured throughput |
| f1-sim-driver | Python scripts/interpolation/edit prototypes | Add a C++20 execution runtime; retain Python for script authoring, AI edits and a test reference | Cross-language parity; stable control baseline; state/reset/stale-input handling; supported input adapter |
| f1-data-platform | Python ETL | Keep Python, DuckDB and Parquet | Idempotency, quality checks and reproducible runs |
| f1-history-agent / strategy-ml | Python scaffolds | Keep Python for RAG, SQL tools, experiments and model evaluation | Versioned evaluations, provenance, abstention, quality and latency/cost measurements |
| f1-telemetry-lab | Streamlit scaffold | Use Streamlit for the first demonstrable slice; build a React/TypeScript web client once API contracts are stable | Typed API contracts, visible stream quality, reconnection, downsampling and usable charts |
| f1-mobile | Flutter scaffold | Defer native mobile; prioritise the responsive React/TypeScript interface | A demonstrated need for native/offline capabilities before restarting Flutter work |
| Cross-cutting platform | Existing CI/container scaffolds | Working CI, metrics/traces and one reproducible deployment; add infrastructure as code when a deployment target is selected | CI runs, fault tests, measured results and repeatable provisioning |

C#/.NET remains supported by substantial professional experience. An ASP.NET Core gateway is optional if session management, authentication or API composition creates a real need. Do not add another service just to mirror the job listing. Likewise, Kafka and F# are not requirements to add to the first release: use a bounded streaming path and explain its tradeoffs; add a broker only when durable multi-consumer processing warrants one.

## C++ runtime boundary

Start with a C++20 library and CLI using CMake/CTest. Python produces a versioned lap-script JSON artifact; the C++ runtime loads and validates it before execution. Keep model calls and historian requests outside the control loop. Avoid in-process Python/C++ bindings until a measured integration need warrants that complexity.

1. Port pure interpolation and input-bound logic first, with language-neutral fixtures and tolerances.
2. Preserve the existing Python implementation as a comparison reference, but use independently specified expected values too: matching two implementations does not prove either correct.
3. Resolve known lateral-offset and segment-shift semantics before porting them. An ignored edit must be rejected or implemented explicitly.
4. Add telemetry state handling and the input adapter after offline parity passes. Define behavior for stale data, disconnects, lap resets and malformed scripts.
5. Use compiler warnings, static analysis and memory/undefined-behavior sanitizers where supported; isolate threading checks when concurrent code is added. Exercise the intended Windows adapter and the portable core separately.
6. Measure latency distribution, scheduling jitter, allocations, CPU, memory and control outcomes on a stated machine. A C++ implementation is not automatically faster, stable or hard real-time. A nominal 60 Hz stream alone does not justify a language migration.

C++20 is a project choice, not a requirement stated by these job descriptions. The purpose is to build a bounded, defensible example of systems programming that complements the Rust historian and existing C# career.

## Execution priorities

1. Finish the smallest trustworthy Python capture → Rust historian → dashboard slice while the historical ETL progresses.
2. Build and validate the C++ execution core against shared fixtures; investigate input hardware compatibility early.
3. Demonstrate reliability, profiling and control repeatability. Publish the failures and limitations.
4. Add React/TypeScript when the data contracts are stable, keeping Python analysis tools useful.
5. Complete controlled AI evaluations and a reproducible deployment. Keep mobile and motion research behind these gates.

Do not delay suitable applications until the entire platform exists. For rapid hiring, production .NET/data/AI/security experience remains the strongest evidence; this project strengthens the portfolio over time.

## Résumé and content rules

Do not add C++ proficiency or completed C++ delivery to the résumé yet. After a working contribution, describe its precise scope and measured results as personal-project experience. Keep Rust experience distinguished from years of production work in other languages.

Extend the existing video series with: “Why Rust for the historian?”, “Porting a Python executor to C++ with parity tests”, “What profiling changed”, and “A typed React client over stable telemetry APIs”. These are milestone topics, not completed demonstrations. Record separate EN/PT versions under Rodrigo Manso with DeepCode support.
