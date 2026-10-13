use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Context;
use boxbox::historian::{Config, Historian, TagRules};
use tracing_subscriber::EnvFilter;

fn env_or(name: &str, default: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| default.into())
}

fn config_from_env() -> anyhow::Result<Config> {
    let mut cfg = Config::new(PathBuf::from(env_or("BOXBOX_DATA_DIR", "./data")));
    cfg.fsync = env_or("BOXBOX_FSYNC", "true") != "false";
    cfg.default_door.deviation = env_or("BOXBOX_DEVIATION", "0")
        .parse()
        .context("BOXBOX_DEVIATION")?;
    let max_ms: i64 = env_or("BOXBOX_MAX_INTERVAL_MS", "1000")
        .parse()
        .context("BOXBOX_MAX_INTERVAL_MS")?;
    cfg.default_door.max_interval_ns = (max_ms > 0).then_some(max_ms * 1_000_000);
    cfg.flush_rows = env_or("BOXBOX_FLUSH_ROWS", "100000")
        .parse()
        .context("BOXBOX_FLUSH_ROWS")?;
    if let Ok(path) = std::env::var("BOXBOX_TAG_RULES") {
        let text = std::fs::read_to_string(&path).with_context(|| format!("reading {path}"))?;
        cfg.rules =
            serde_json::from_str::<TagRules>(&text).with_context(|| format!("parsing {path}"))?;
    }
    Ok(cfg)
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let cfg = config_from_env()?;
    tracing::info!(
        data_dir = %cfg.data_dir.display(),
        fsync = cfg.fsync,
        deviation = cfg.default_door.deviation,
        max_interval_ns = ?cfg.default_door.max_interval_ns,
        flush_rows = cfg.flush_rows,
        rules = cfg.rules.tags.len(),
        "configuration"
    );
    let historian = Arc::new(Historian::open(cfg).context("opening data directory")?);

    let bind = env_or("BOXBOX_BIND", "0.0.0.0:8081");
    let listener = tokio::net::TcpListener::bind(&bind)
        .await
        .with_context(|| format!("binding {bind}"))?;
    tracing::info!(%bind, version = boxbox::VERSION, "box-box historian listening");

    let shutdown_historian = historian.clone();
    axum::serve(listener, boxbox::api::router(historian))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
            tracing::info!("shutdown requested");
        })
        .await?;

    let flushed = tokio::task::spawn_blocking(move || shutdown_historian.flush_all()).await??;
    tracing::info!(flushed, "sessions flushed on shutdown");
    Ok(())
}
