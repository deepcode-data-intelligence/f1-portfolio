# f1-sim-driver

**Case 8 — Scripted lap executor.** Plays an AI-authored **lap script** into the F1 game.
The AI never drives in real time: it analyses a recorded lap, writes the next lap as a script
(steering, throttle, brake, gear **indexed by lap distance**), and this component executes it.
The result goes back into the `box-box` historian and the loop repeats. Best valid lap wins.

> Status: scaffold — lap-script format, distance-indexed executor with position hold, segment
> edits, CLI and unit tests. UDP state reader and gamepad output adapters land next.

## Why distance, not time

Replaying inputs against time drifts: one frame of USB jitter at the first braking point
compounds into the gravel by turn 4. Indexing by the game's `lapDistance` removes timing
drift. A small, capped steering correction toward the scripted position (the *position
hold*) absorbs the rest. The executor has no car model and no planning; all driving
intelligence is in the script.

## Components

| Module | Role |
|---|---|
| `script.py` | `LapScript` / `ControlPoint`: the exchange format between lap editor and executor |
| `executor.py` | interpolation by distance + proportional, capped position hold |
| `edits.py` | the lap editor's vocabulary: shift a segment, scale a channel, offset laterally |
| `cli.py` | `f1-driver info`, `f1-driver validate <script.json>` |

Output adapters (next iteration): a virtual gamepad on Windows PC (ViGEm) and, for the PS5, a
passthrough adapter that keeps a licensed controller attached for authentication. They are
platform-specific and will live behind an `InputSink` interface, outside the core dependencies.

## Run

```bash
docker compose --profile driver up sim-driver
uv sync && uv run f1-driver info
uv run pytest
```

Environment: `DRIVER_UDP_PORT` (default `20778`), `DRIVER_BOXBOX_URL`,
`DRIVER_POSITION_HOLD_GAIN`, `DRIVER_POSITION_HOLD_MAX`.

## Competition protocol (summary)

Same track, car, tyres, fuel and assists. Time trial, offline. Each agent starts from the same
reference lap and gets N iterations; a lap invalidated by track limits counts as a failure.
Full protocol in the repository `FOUNDATIONS.md`.

Unofficial project, not affiliated with Formula 1 or EA.
