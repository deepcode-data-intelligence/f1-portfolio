//! HTTP surface. Only `/health` for now.

use axum::{routing::get, Json, Router};
use serde::Serialize;

#[derive(Serialize)]
pub struct Health {
    pub status: &'static str,
    pub version: &'static str,
}

async fn health() -> Json<Health> {
    Json(Health {
        status: "ok",
        version: crate::VERSION,
    })
}

pub fn router() -> Router {
    Router::new().route("/health", get(health))
}
