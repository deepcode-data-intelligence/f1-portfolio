//! box-box — a minimal industrial historian for F1 telemetry.
//!
//! Module map (filled in case by case):
//! - `model`: tags and time-series samples (timestamp, value, quality)
//! - `compression`: swinging-door (exception/compression deviation)
//! - `storage`: partitioned Parquet via arrow-rs
//! - `api`: axum HTTP query API (range, downsampling, interpolation) and streaming ingestion

pub mod api;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
