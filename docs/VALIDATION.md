# Validation and evidence protocol

No benchmark values are claimed here. Fill results from reproducible runs and retain unsuccessful runs. Gates may progress independently; the integrated milestone is not complete until all required paths are demonstrated.

| Gate | Required demonstration | Evidence to retain |
|---|---|---|
| Historical slice | Re-run a small known ETL input without unintended duplication; check entities and keys | Commands, source timestamps, raw fixture hashes, quality results, row counts |
| Capture/decode | Decode supported packets; reject truncated/unsupported packets; distinguish sessions and resets | Versioned fixtures, protocol version, expected fields and units |
| Integrated replay | Recorded packets reach connector, historian and dashboard through documented APIs | Capture hash, commit, config, exact commands, labelled screen recording |
| Recovery | Stop historian, restart connector, exhaust buffer capacity, then recover | Accepted/persisted/dropped counts, disk/RAM use, ordering and deduplication observations |
| Fidelity | Compare raw, edge-filtered and historian-compressed signals | Per-channel error, timing shifts at braking events, maximum gaps, compression ratio |
| Driver baseline | Validate adapter and repeat unchanged laps with stale/reset/disconnect tests | Hardware/game versions, settings, lap validity, times and dispersion |
| AI edits | Reject malformed/unsupported edits; evaluate against unchanged and non-LLM baselines | Script lineage, prompts/model versions, budgets, every attempt and outcome |
| History agent | Answer factual/narrative/ambiguous/unanswerable questions with provenance | Versioned golden set, SQL/results, citations, failures and latency/cost |

## Measurement definitions

- Throughput: distinguish received packets, decoded samples, accepted samples and durably persisted samples per second.
- Latency: report capture-to-acceptance and capture-to-query-visible separately, with clock assumptions; use p50/p95/p99 where sample size supports them.
- Durability: a successful in-memory enqueue is not durable acknowledgment. Reconcile offered, persisted, deduplicated, rejected, dropped and pending counts.
- Resource use: peak RSS, CPU, disk growth and backlog/drain behavior for a stated run duration and machine.
- Compression: report bytes and sample counts, plus maximum/mean reconstruction error, peak preservation and event timing. Compare both compression stages jointly.
- Queries: state data volume, query shape, result size, concurrency and warm/cold cache state.
- Driving: valid-lap rate, median and spread, best valid lap, off-track/disconnect failures and intervention count. Retain failed trials.
- AI: model/version, tool access, prompt, observed data, token/time/cost budget and repeated-trial results. Do not infer a win from a single best lap.

## Known prototype limitations to resolve

1. Connector buffer is bounded RAM and can drop old samples; durable spool is absent.
2. Exception filtering requires a defined heartbeat/maximum-silence policy and per-signal error budget.
3. Driver lateral-offset edits currently do not affect executor behavior.
4. Segment-shift semantics and continuity need validation; distance replay alone does not establish stable control.
5. Connector/driver CLI containers are not live listeners/controllers. UDP fan-out and adapters remain pending.
6. The history agent health check is a scaffold, not functioning AI. The historian (box-box v1) ingests, persists and queries; its evidence so far is synthetic and single-client (see `evidence/2026-10-13-box-box-v1.md`).

## Evidence record template

```text
Milestone / question:
Code commit and uncommitted diff hash:
Date, machine, OS, runtime, game/protocol/model versions:
Input origin, applicable terms and fixture hash:
Configuration, controls and baseline:
Exact setup/run/verification commands:
Expected versus observed behavior:
Results, units, sample size and failed attempts:
Logs, traces, raw output and screenshot/video paths:
Limitations and next decision:
```

Store raw evidence separately from edited content. A public demo must state whether it uses live data, replay, a fixture or a mock. Do not publish credentials or proprietary client materials.
