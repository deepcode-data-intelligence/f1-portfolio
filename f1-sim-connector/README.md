# f1-sim-connector

Case 7: Python edge-connector prototypes for game telemetry. The target path is capture/fan-out → protocol validation → tags/quality → filtering → durable delivery → box-box.

## Present implementation

Header parser, tag scheme, exception filter, bounded in-memory buffer and unit-test files. Packet-body decoding, UDP listener and historian client are not yet implemented. The queue can evict old samples and loses contents on restart; it is not a lossless store-and-forward system.

## Local inspection

From this component directory:

```bash
uv sync
uv run f1-sim info
uv run pytest
```

The Compose service exposes UDP port 20777, but its current default command shows CLI help. It does not listen for game telemetry. Environment names and port mappings are configuration scaffolding, not functioning integration.

## Next gates

Decode captured packet bodies with versioned fixtures; include session UID, sequence/frame, source and receive time, units and quality. Implement one capture/fan-out point for storage and control consumers. Add a durable bounded spool, explicit overflow/drop counters, restart recovery and delivery semantics. Define per-signal filtering and maximum-silence handling; retain raw captures to measure combined edge/historian error.

See [foundations](../FOUNDATIONS.md) and [validation](../docs/VALIDATION.md). Game data is intended to originate from the author's own sessions; no affiliation with Formula 1 or EA.
