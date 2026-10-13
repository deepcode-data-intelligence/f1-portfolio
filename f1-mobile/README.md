# f1-mobile

> Status clarification — 13 October 2026: Later phase. A connected mobile application is not yet demonstrated; stabilise the backend API contracts first. See [validation gates](../docs/VALIDATION.md).

**Case 6 — Mobile client (phase 2).** Flutter/Dart app for Android and iOS:
natural-language Q&A (`f1-history-agent /ask`), stats explorer (`/stats/*`),
telemetry charts (`box-box` Query API), offline-first cache (drift/SQLite).

Starts after the APIs of cases 2 and 4 stabilise. The Flutter build is native;
the services it consumes come up with `docker compose up` at the repo root.
