//! End-to-end HTTP tests over an in-process router.

use std::sync::Arc;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use boxbox::historian::{Config, Historian};
use http_body_util::BodyExt;
use serde_json::{json, Value};
use tower::ServiceExt;

fn app(dir: &std::path::Path, flush_rows: usize) -> axum::Router {
    let mut cfg = Config::new(dir);
    cfg.fsync = false;
    cfg.flush_rows = flush_rows;
    cfg.default_door.max_interval_ns = None;
    boxbox::api::router(Arc::new(Historian::open(cfg).unwrap()))
}

async fn call(app: &axum::Router, req: Request<Body>) -> (StatusCode, Value) {
    let res = app.clone().oneshot(req).await.unwrap();
    let status = res.status();
    let bytes = res.into_body().collect().await.unwrap().to_bytes();
    let body = if bytes.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&bytes)
            .unwrap_or(Value::String(String::from_utf8_lossy(&bytes).into()))
    };
    (status, body)
}

fn post_json(path: &str, body: Value) -> Request<Body> {
    Request::post(path)
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap()
}

fn get(path: &str) -> Request<Body> {
    Request::get(path).body(Body::empty()).unwrap()
}

#[tokio::test]
async fn health_returns_ok() {
    let dir = tempfile::tempdir().unwrap();
    let (status, body) = call(&app(dir.path(), 1000), get("/health")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["status"], "ok");
    assert_eq!(body["version"], boxbox::VERSION);
}

#[tokio::test]
async fn ingest_then_query_and_metrics() {
    let dir = tempfile::tempdir().unwrap();
    let app = app(dir.path(), 1000);

    // A sawtooth, which swinging door cannot compress, plus one bad sample.
    let now_ns = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos() as i64;
    let samples: Vec<Value> = (0..100)
        .map(|i| {
            json!({"session": "sim:test", "tag": "SIM.CAR0.SPEED", "ts": i * 16_666_667,
                   "value": (i % 2) as f64 * 100.0, "unit": "km/h", "recv_ts": now_ns - 5_000_000})
        })
        .chain(std::iter::once(
            json!({"session": "sim:test", "tag": "x y", "ts": 1, "value": 1.0}),
        ))
        .collect();
    let (status, body) = call(&app, post_json("/ingest", json!({ "samples": samples }))).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["offered"], 101);
    assert_eq!(body["accepted"], 100);
    assert_eq!(body["archived"], 99, "last point is held in the door");
    assert_eq!(body["rejected"][0]["reason"], "invalid_tag");

    let (status, body) = call(&app, get("/sessions/sim:test")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["pending"], 1);
    assert_eq!(body["counters"]["persisted"], 99);

    let (status, body) = call(&app, get("/sessions/sim:test/tags")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body[0]["tag"], "SIM.CAR0.SPEED");
    assert_eq!(body[0]["unit"], "km/h");

    let (status, body) = call(&app, post_json("/sessions/sim:test/flush", Value::Null)).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["pending"], 0);
    assert_eq!(body["rows_on_disk"], 100);

    let (status, body) = call(
        &app,
        get("/query?session=sim:test&tags=SIM.CAR0.SPEED,SIM.CAR0.MISSING&from=0&to=1000000000"),
    )
    .await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");

    let (status, body) = call(
        &app,
        get("/query?session=sim:test&tags=SIM.CAR0.SPEED&max_points=20"),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{body}");
    let s = &body["series"][0];
    assert_eq!(s["raw_count"], 100);
    assert_eq!(s["downsampled"], true);
    assert!(s["count"].as_u64().unwrap() <= 20);
    assert_eq!(s["points"][0][2], "good");

    let (status, body) = call(
        &app,
        get("/query?session=sim:test&tags=SIM.CAR0.SPEED&max_points=20&agg=raw"),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    let (status, body) = call(
        &app,
        get("/interpolate?session=sim:test&tag=SIM.CAR0.SPEED&ts=8333333"),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert!((body["value"].as_f64().unwrap() - 50.0).abs() < 1e-3);

    let res = app.clone().oneshot(get("/metrics")).await.unwrap();
    assert_eq!(res.status(), StatusCode::OK);
    let text =
        String::from_utf8(res.into_body().collect().await.unwrap().to_bytes().to_vec()).unwrap();
    assert!(text.contains("boxbox_samples_total{session=\"sim:test\",stage=\"accepted\"} 100"));
    assert!(text.contains("boxbox_recv_latency_ns{session=\"sim:test\",stat=\"max\"}"));
}

#[tokio::test]
async fn unknown_session_is_404_and_bad_json_is_4xx() {
    let dir = tempfile::tempdir().unwrap();
    let app = app(dir.path(), 1000);
    let (status, _) = call(&app, get("/sessions/none")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    let (status, _) = call(&app, get("/query?session=none&tags=A")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    let (status, _) = call(&app, get("/query?session=none")).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    let (status, _) = call(
        &app,
        post_json("/ingest", json!({"samples": [{"tag": "A"}]})),
    )
    .await;
    assert!(status.is_client_error());
}
