//! HTTP surface over the historian.
//!
//! | Method | Path | Purpose |
//! |---|---|---|
//! | GET | `/health` | liveness, version, uptime |
//! | POST | `/ingest` | `{"samples":[...]}`; acknowledged after WAL commit |
//! | GET | `/sessions` | stats for every session |
//! | GET | `/sessions/{id}` | stats for one session |
//! | GET | `/sessions/{id}/tags` | tags, units, compression settings, row counts |
//! | POST | `/sessions/{id}/flush` | archive held points and write a Parquet segment |
//! | GET | `/query` | `session`, `tags` (comma list), `from`, `to`, `max_points`, `agg` |
//! | GET | `/interpolate` | `session`, `tag`, `ts`: linear value at time |
//! | GET | `/metrics` | Prometheus text |

use std::sync::Arc;

use axum::extract::{DefaultBodyLimit, Path, Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::{Deserialize, Serialize};

use crate::downsample::{downsample, Agg};
use crate::historian::{Historian, HistorianError, IngestReport, SessionStats, TagInfo};
use crate::model::{IncomingSample, Point};

pub type Shared = Arc<Historian>;

const MAX_BODY_BYTES: usize = 64 * 1024 * 1024;
const DEFAULT_MAX_POINTS: usize = 2_000;
const MAX_MAX_POINTS: usize = 500_000;

pub struct ApiError(StatusCode, String);

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.0, Json(serde_json::json!({ "error": self.1 }))).into_response()
    }
}

impl From<HistorianError> for ApiError {
    fn from(e: HistorianError) -> Self {
        let status = match e {
            HistorianError::UnknownSession | HistorianError::UnknownTag => StatusCode::NOT_FOUND,
            HistorianError::InvalidSessionId => StatusCode::BAD_REQUEST,
            HistorianError::Io(_) => StatusCode::INTERNAL_SERVER_ERROR,
        };
        if status.is_server_error() {
            tracing::error!(error = %e, "historian failure");
        }
        ApiError(status, e.to_string())
    }
}

impl From<tokio::task::JoinError> for ApiError {
    fn from(e: tokio::task::JoinError) -> Self {
        ApiError(StatusCode::INTERNAL_SERVER_ERROR, e.to_string())
    }
}

#[derive(Serialize)]
pub struct Health {
    pub status: &'static str,
    pub version: &'static str,
    pub uptime_secs: u64,
    pub sessions: usize,
}

async fn health(State(h): State<Shared>) -> Json<Health> {
    Json(Health {
        status: "ok",
        version: crate::VERSION,
        uptime_secs: h.uptime_secs(),
        sessions: h.sessions().len(),
    })
}

#[derive(Deserialize)]
pub struct IngestBody {
    pub samples: Vec<IncomingSample>,
}

async fn ingest(
    State(h): State<Shared>,
    Json(body): Json<IngestBody>,
) -> Result<Json<IngestReport>, ApiError> {
    let report = tokio::task::spawn_blocking(move || h.ingest(&body.samples)).await??;
    Ok(Json(report))
}

async fn sessions(State(h): State<Shared>) -> Json<Vec<SessionStats>> {
    Json(h.sessions())
}

async fn session(
    State(h): State<Shared>,
    Path(id): Path<String>,
) -> Result<Json<SessionStats>, ApiError> {
    Ok(Json(h.session(&id)?))
}

async fn tags(
    State(h): State<Shared>,
    Path(id): Path<String>,
) -> Result<Json<Vec<TagInfo>>, ApiError> {
    Ok(Json(h.tags(&id)?))
}

async fn flush(
    State(h): State<Shared>,
    Path(id): Path<String>,
) -> Result<Json<SessionStats>, ApiError> {
    Ok(Json(
        tokio::task::spawn_blocking(move || h.flush_session(&id)).await??,
    ))
}

#[derive(Deserialize)]
pub struct QueryParams {
    pub session: String,
    pub tags: String,
    pub from: Option<i64>,
    pub to: Option<i64>,
    pub max_points: Option<usize>,
    #[serde(default)]
    pub agg: Agg,
}

#[derive(Serialize)]
pub struct Series {
    pub tag: String,
    pub unit: Option<String>,
    pub raw_count: usize,
    pub count: usize,
    pub downsampled: bool,
    pub points: Vec<Point>,
}

#[derive(Serialize)]
pub struct QueryResponse {
    pub session: String,
    pub from: i64,
    pub to: i64,
    pub max_points: usize,
    pub agg: &'static str,
    pub series: Vec<Series>,
}

async fn query(
    State(h): State<Shared>,
    Query(q): Query<QueryParams>,
) -> Result<Json<QueryResponse>, ApiError> {
    let from = q.from.unwrap_or(i64::MIN);
    let to = q.to.unwrap_or(i64::MAX);
    if from > to {
        return Err(ApiError(
            StatusCode::BAD_REQUEST,
            "from must be <= to".into(),
        ));
    }
    let max_points = q
        .max_points
        .unwrap_or(DEFAULT_MAX_POINTS)
        .min(MAX_MAX_POINTS);
    let tag_list: Vec<String> = q
        .tags
        .split(',')
        .map(str::trim)
        .filter(|t| !t.is_empty())
        .map(String::from)
        .collect();
    if tag_list.is_empty() {
        return Err(ApiError(StatusCode::BAD_REQUEST, "tags is required".into()));
    }
    let session_id = q.session.clone();
    let agg = q.agg;
    let series = tokio::task::spawn_blocking(move || -> Result<Vec<Series>, HistorianError> {
        tag_list
            .into_iter()
            .map(|tag| {
                let raw = h.query(&session_id, &tag, from, to)?;
                let (points, downsampled) = downsample(&raw, max_points, agg);
                Ok(Series {
                    unit: h.unit(&session_id, &tag),
                    tag,
                    raw_count: raw.len(),
                    count: points.len(),
                    downsampled,
                    points,
                })
            })
            .collect()
    })
    .await??;
    if agg == Agg::Raw && series.iter().any(|s| s.count > max_points) {
        return Err(ApiError(
            StatusCode::BAD_REQUEST,
            format!(
                "more than max_points={max_points} raw points; raise max_points or use agg=minmax"
            ),
        ));
    }
    Ok(Json(QueryResponse {
        session: q.session,
        from,
        to,
        max_points,
        agg: match agg {
            Agg::MinMax => "minmax",
            Agg::Avg => "avg",
            Agg::Raw => "raw",
        },
        series,
    }))
}

#[derive(Deserialize)]
pub struct InterpolateParams {
    pub session: String,
    pub tag: String,
    pub ts: i64,
}

#[derive(Serialize)]
pub struct InterpolateResponse {
    pub session: String,
    pub tag: String,
    pub ts: i64,
    pub value: Option<f64>,
}

async fn interpolate(
    State(h): State<Shared>,
    Query(q): Query<InterpolateParams>,
) -> Result<Json<InterpolateResponse>, ApiError> {
    let (session, tag, ts) = (q.session.clone(), q.tag.clone(), q.ts);
    let value = tokio::task::spawn_blocking(move || h.value_at(&session, &tag, ts)).await??;
    Ok(Json(InterpolateResponse {
        session: q.session,
        tag: q.tag,
        ts: q.ts,
        value,
    }))
}

async fn metrics(State(h): State<Shared>) -> impl IntoResponse {
    (
        [(
            header::CONTENT_TYPE,
            "text/plain; version=0.0.4; charset=utf-8",
        )],
        h.metrics_text(),
    )
}

pub fn router(historian: Shared) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/ingest", post(ingest))
        .route("/sessions", get(sessions))
        .route("/sessions/:id", get(session))
        .route("/sessions/:id/tags", get(tags))
        .route("/sessions/:id/flush", post(flush))
        .route("/query", get(query))
        .route("/interpolate", get(interpolate))
        .route("/metrics", get(metrics))
        .layer(DefaultBodyLimit::max(MAX_BODY_BYTES))
        .with_state(historian)
}
