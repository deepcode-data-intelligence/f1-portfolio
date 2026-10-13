# f1-telemetry-lab

> Status clarification — 13 October 2026: Dashboard scaffold only. Historian integration and real-vs-game overlays are planned; any fallback must visibly identify its data source. See [validation gates](../docs/VALIDATION.md).

**Case 3 — Telemetry dashboards.** PI-Vision-style comparative panels: driver vs driver
per lap (speed / throttle / brake by distance), gaps, stint degradation, positions.
Consumes the **`box-box` Query API** over HTTP (FastF1 direct read as fallback).

> Status: scaffold.

## Run

```bash
docker compose up telemetry-lab         # http://localhost:8501
uv sync && uv run streamlit run src/f1_telemetry_lab/app.py
```

`BOXBOX_URL` points to the historian (default `http://localhost:8081`).

FastF1 software is MIT licensed; underlying data terms are separate. Unofficial project, not affiliated with Formula 1.
