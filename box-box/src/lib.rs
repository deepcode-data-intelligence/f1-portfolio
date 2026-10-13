//! box-box: a minimal industrial historian for F1 telemetry.
//!
//! Data flows `ingest -> validate -> swinging door -> WAL -> Parquet`, and queries merge
//! the Parquet segments with the in-memory tail. Every stage keeps counters so that
//! offered, accepted, archived, persisted, flushed, rejected and pending samples can be
//! reconciled (see `docs/VALIDATION.md` at the repository root).
//!
//! Module map:
//! - `model`: samples, points and quality
//! - `compression`: swinging-door trending per tag
//! - `storage`: per-session write-ahead log and Parquet segments
//! - `historian`: sessions, tag state, counters and the query path
//! - `downsample`: min/max and average bucketing for large ranges
//! - `api`: axum HTTP surface

pub mod api;
pub mod compression;
pub mod downsample;
pub mod historian;
pub mod model;
pub mod storage;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
