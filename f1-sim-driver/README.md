# f1-sim-driver

Case 8: prototypes for distance-indexed lap scripts and controlled AI editing. The intended LLM loop runs **between laps**: inspect → propose a bounded edit → validate → execute deterministically → measure. No connected game-control loop is demonstrated.

## Present implementation

LapScript/ControlPoint schemas, interpolation by distance, proportional capped position correction, segment edits, CLI and unit-test files. UDP state capture and game-input adapters are pending. Distance indexing helps alignment but does not guarantee control stability.

Known limitations: lateral-offset edits update metadata that the executor does not consume; segment shifts move all affected control points and need validated collision/continuity semantics. These operations must not be described as demonstrated racing-line or braking-point optimisation.

## Local inspection

From this component directory:

```bash
uv sync
uv run f1-driver info
uv run f1-driver validate path/to/script.json
uv run pytest
```

Replace the script path with an existing fixture. The Docker default shows CLI help; the driver does not receive live UDP or generate gamepad output. Port 20778 does not receive a copy of port 20777 without an implemented fan-out.

## Baseline before AI

Validate supported input hardware/software early. ViGEm is end-of-life; a maintained alternative or explicitly bounded experiment must be chosen. PS5 adapter compatibility is unverified. Establish repeatable non-LLM laps, lap-reset/state handling, command limits and stale/disconnected telemetry behavior before model comparisons.

Hold environment/settings and available observations constant, repeat trials, randomise execution order and retain invalid laps. Compare to unchanged replay and a simple non-LLM edit/search baseline. Report valid-lap rate, median/spread, best lap, failures and inference budget; do not rank models from one best lap.

All proposed control experiments are offline simulator sessions. See [foundations](../FOUNDATIONS.md) and [validation protocol](../docs/VALIDATION.md). Unofficial; not affiliated with Formula 1 or EA.
