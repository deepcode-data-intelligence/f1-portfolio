# f1-history-agent

> Status clarification — 13 October 2026: Health scaffold only. RAG, SQL tools, statistics endpoints and evaluations remain planned. Model usage requires valid authentication and a checked usage/cost model. See [validation gates](../docs/VALIDATION.md).

**Case 4 — Applied AI / platform gateway.** Headless FastAPI service:

- `POST /ask` — hybrid agent: **tool-calling → SQL** on the `f1-data-platform` DuckDB for exact
  facts, **RAG** (Wikipedia, local embeddings) for narrative. Pluggable `LLMBackend`.
- `GET /stats/*` — read-only statistics API over the same DuckDB, consumed by `f1-mobile`.
- Automated evals: golden Q&A set with scoring.

> Status: scaffold (`/health` only).

## Run

```bash
docker compose up history-agent          # http://localhost:8080/docs
uv sync && uv run uvicorn f1_history_agent.main:app --reload --port 8080
```

`F1_DATA_DIR` must contain the `f1.duckdb` produced by `f1-data-platform`.

Wikipedia (CC BY-SA). Unofficial project, not affiliated with Formula 1.
