//! Sessions, per-tag state and the counters that make loss accounting explicit.
//!
//! One `Historian` owns every session. Ingest validates each sample, enforces monotonic
//! timestamps per tag, runs the swinging door and appends the archived points to the
//! session WAL; the batch is acknowledged only after the WAL commit. When the in-memory tail
//! reaches `flush_rows` it is folded into a Parquet segment. Queries merge segments and tail.
//!
//! What is *not* durable: the candidate point each swinging door is still holding. On a
//! crash, per tag, the samples after the last archived point are lost; `max_interval`
//! bounds that window and a graceful shutdown or `flush` archives them.

use std::collections::BTreeMap;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::compression::{interpolate, SwingingDoor, SwingingDoorConfig};
use crate::model::{valid_session_id, valid_tag, IncomingSample, Point};
use crate::storage::SessionStore;

pub const SESSIONS_DIR: &str = "sessions";

/// Per-tag compression override. `pattern` supports `*` wildcards (`SIM.CAR*.SPEED`).
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct TagRule {
    pub pattern: String,
    #[serde(default)]
    pub deviation: Option<f64>,
    /// Milliseconds; `0` disables the heartbeat for matching tags.
    #[serde(default)]
    pub max_interval_ms: Option<i64>,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct TagRules {
    #[serde(default)]
    pub tags: Vec<TagRule>,
}

#[derive(Clone, Debug)]
pub struct Config {
    pub data_dir: PathBuf,
    /// fsync the WAL on every acknowledged batch and every segment.
    pub fsync: bool,
    pub default_door: SwingingDoorConfig,
    pub rules: TagRules,
    /// Fold the in-memory tail into a Parquet segment once it holds this many rows.
    pub flush_rows: usize,
}

impl Config {
    pub fn new(data_dir: impl Into<PathBuf>) -> Config {
        Config {
            data_dir: data_dir.into(),
            fsync: true,
            default_door: SwingingDoorConfig::default(),
            rules: TagRules::default(),
            flush_rows: 100_000,
        }
    }

    pub fn door_for(&self, tag: &str) -> SwingingDoorConfig {
        let mut cfg = self.default_door;
        for rule in self
            .rules
            .tags
            .iter()
            .filter(|r| glob_match(&r.pattern, tag))
        {
            if let Some(d) = rule.deviation {
                cfg.deviation = d;
            }
            if let Some(ms) = rule.max_interval_ms {
                cfg.max_interval_ns = (ms > 0).then_some(ms * 1_000_000);
            }
        }
        cfg
    }
}

/// `*` matches any run of characters; everything else is literal.
pub fn glob_match(pattern: &str, text: &str) -> bool {
    fn rec(p: &[u8], t: &[u8]) -> bool {
        match p.split_first() {
            None => t.is_empty(),
            Some((b'*', rest)) => (0..=t.len()).any(|i| rec(rest, &t[i..])),
            Some((c, rest)) => t.first() == Some(c) && rec(rest, &t[1..]),
        }
    }
    rec(pattern.as_bytes(), text.as_bytes())
}

#[derive(Clone, Copy, Debug, Default, Serialize)]
pub struct Counters {
    /// Samples received by `ingest`.
    pub offered: u64,
    /// Samples that passed validation and ordering checks.
    pub accepted: u64,
    pub rejected: u64,
    pub duplicate: u64,
    pub out_of_order: u64,
    /// Points emitted by the swinging doors.
    pub archived: u64,
    /// Points whose WAL write was committed (acknowledged to the client).
    pub persisted: u64,
    /// Points folded into Parquet segments.
    pub flushed: u64,
    pub latency_samples: u64,
    pub latency_sum_ns: u64,
    pub latency_max_ns: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct TagInfo {
    pub tag: String,
    pub unit: Option<String>,
    pub deviation: f64,
    pub max_interval_ns: Option<i64>,
    pub rows_on_disk: i64,
    pub rows_in_tail: usize,
    pub pending: bool,
    pub last_ts: Option<i64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct SessionStats {
    pub session: String,
    pub tags: usize,
    /// Points held in swinging doors, not yet archived (lost on crash).
    pub pending: usize,
    pub rows_on_disk: i64,
    pub rows_in_tail: usize,
    pub segments: usize,
    pub bytes_on_disk: u64,
    pub first_ts: Option<i64>,
    pub last_ts: Option<i64>,
    pub counters: Counters,
}

#[derive(Clone, Debug, Serialize)]
pub struct Rejection {
    pub index: usize,
    pub reason: &'static str,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct IngestReport {
    pub offered: usize,
    pub accepted: usize,
    pub archived: usize,
    pub persisted: usize,
    pub rejected: Vec<Rejection>,
}

#[derive(Debug, Error)]
pub enum HistorianError {
    #[error("unknown session")]
    UnknownSession,
    #[error("unknown tag")]
    UnknownTag,
    #[error("invalid session id")]
    InvalidSessionId,
    #[error("storage error: {0}")]
    Io(#[from] io::Error),
}

struct TagState {
    door: SwingingDoor,
    tail: Vec<Point>,
    last_ts: Option<i64>,
    unit: Option<String>,
    rows_on_disk: i64,
}

struct Session {
    store: SessionStore,
    tags: BTreeMap<String, TagState>,
    counters: Counters,
    tail_rows: usize,
    first_ts: Option<i64>,
    last_ts: Option<i64>,
}

impl Session {
    fn flush_segment(&mut self) -> io::Result<usize> {
        let mut rows = Vec::with_capacity(self.tail_rows);
        for (tag, st) in &mut self.tags {
            st.rows_on_disk += st.tail.len() as i64;
            rows.extend(st.tail.drain(..).map(|p| (tag.clone(), p)));
        }
        let n = rows.len();
        self.store.write_segment(rows)?;
        self.tail_rows = 0;
        self.counters.flushed += n as u64;
        Ok(n)
    }

    /// Archive every held point and commit. Returns the number of points archived.
    fn close_doors(&mut self) -> io::Result<usize> {
        let mut n = 0;
        for (tag, st) in &mut self.tags {
            if let Some(p) = st.door.flush() {
                self.store.append(tag, &p)?;
                st.tail.push(p);
                n += 1;
            }
        }
        if n > 0 {
            self.store.commit()?;
            self.tail_rows += n;
            self.counters.archived += n as u64;
            self.counters.persisted += n as u64;
        }
        Ok(n)
    }

    fn stats(&self, id: &str) -> SessionStats {
        SessionStats {
            session: id.to_string(),
            tags: self.tags.len(),
            pending: self.tags.values().filter(|t| t.door.has_pending()).count(),
            rows_on_disk: self.store.rows_on_disk(),
            rows_in_tail: self.tail_rows,
            segments: self.store.segments().len(),
            bytes_on_disk: self.store.bytes_on_disk(),
            first_ts: self.first_ts,
            last_ts: self.last_ts,
            counters: self.counters,
        }
    }
}

pub struct Historian {
    cfg: Config,
    started: Instant,
    sessions: Mutex<BTreeMap<String, Session>>,
}

fn now_ns() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as i64)
        .unwrap_or(0)
}

impl Historian {
    /// Open the data directory, reopening every session found on disk and replaying WALs.
    pub fn open(cfg: Config) -> io::Result<Historian> {
        let root = cfg.data_dir.join(SESSIONS_DIR);
        fs::create_dir_all(&root)?;
        let mut sessions = BTreeMap::new();
        for entry in fs::read_dir(&root)? {
            let path = entry?.path();
            if !path.is_dir() {
                continue;
            }
            let Some(id) = path
                .file_name()
                .and_then(|n| n.to_str())
                .map(str::to_string)
            else {
                continue;
            };
            let session = Self::open_session(&cfg, &path)?;
            tracing::info!(
                session = %id,
                segments = session.store.segments().len(),
                rows_on_disk = session.store.rows_on_disk(),
                replayed = session.tail_rows,
                "session reopened"
            );
            sessions.insert(id, session);
        }
        Ok(Historian {
            cfg,
            started: Instant::now(),
            sessions: Mutex::new(sessions),
        })
    }

    fn open_session(cfg: &Config, dir: &Path) -> io::Result<Session> {
        let store = SessionStore::open(dir, cfg.fsync)?;
        let mut tags: BTreeMap<String, TagState> = BTreeMap::new();
        for (tag, rows) in store.tags_on_disk()? {
            tags.insert(
                tag.clone(),
                TagState {
                    door: SwingingDoor::new(cfg.door_for(&tag)),
                    tail: Vec::new(),
                    last_ts: None,
                    unit: None,
                    rows_on_disk: rows,
                },
            );
        }
        for (tag, ts) in store.last_ts_per_tag()? {
            if let Some(st) = tags.get_mut(&tag) {
                st.last_ts = Some(ts);
            }
        }
        let mut tail_rows = 0;
        for (tag, p) in store.replay_wal()? {
            let st = tags.entry(tag.clone()).or_insert_with(|| TagState {
                door: SwingingDoor::new(cfg.door_for(&tag)),
                tail: Vec::new(),
                last_ts: None,
                unit: None,
                rows_on_disk: 0,
            });
            // Duplicates of already-segmented rows (crash between segment write and WAL
            // truncation) are dropped here.
            if st.last_ts.is_some_and(|last| p.ts <= last) {
                continue;
            }
            st.last_ts = Some(p.ts);
            st.tail.push(p);
            tail_rows += 1;
        }
        let last_ts = tags.values().filter_map(|t| t.last_ts).max();
        Ok(Session {
            store,
            tags,
            counters: Counters::default(),
            tail_rows,
            first_ts: None,
            last_ts,
        })
    }

    pub fn config(&self) -> &Config {
        &self.cfg
    }

    pub fn uptime_secs(&self) -> u64 {
        self.started.elapsed().as_secs()
    }

    /// Validate, compress and durably append a batch. Rejections are per sample; an I/O
    /// error fails the whole call and nothing in the batch should be considered acknowledged.
    pub fn ingest(&self, samples: &[IncomingSample]) -> Result<IngestReport, HistorianError> {
        let mut report = IngestReport {
            offered: samples.len(),
            ..Default::default()
        };
        let mut by_session: BTreeMap<&str, Vec<usize>> = BTreeMap::new();
        for (i, s) in samples.iter().enumerate() {
            by_session.entry(s.session.as_str()).or_default().push(i);
        }

        let now = now_ns();
        let mut sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        for (session_id, indices) in by_session {
            if !valid_session_id(session_id) {
                for i in indices {
                    report.rejected.push(Rejection {
                        index: i,
                        reason: "invalid_session",
                    });
                }
                continue;
            }
            if !sessions.contains_key(session_id) {
                let dir = self.cfg.data_dir.join(SESSIONS_DIR).join(session_id);
                sessions.insert(session_id.to_string(), Self::open_session(&self.cfg, &dir)?);
                tracing::info!(session = %session_id, "session opened");
            }
            let session = sessions.get_mut(session_id).expect("just inserted");
            let mut archived_in_batch = 0usize;

            for i in indices {
                let s = &samples[i];
                session.counters.offered += 1;
                let reason = if !valid_tag(&s.tag) {
                    Some("invalid_tag")
                } else if !s.value.is_finite() {
                    Some("non_finite_value")
                } else if s.ts < 0 {
                    Some("negative_ts")
                } else {
                    None
                };
                if let Some(reason) = reason {
                    session.counters.rejected += 1;
                    report.rejected.push(Rejection { index: i, reason });
                    continue;
                }
                let st = session
                    .tags
                    .entry(s.tag.clone())
                    .or_insert_with(|| TagState {
                        door: SwingingDoor::new(self.cfg.door_for(&s.tag)),
                        tail: Vec::new(),
                        last_ts: None,
                        unit: None,
                        rows_on_disk: 0,
                    });
                if let Some(last) = st.last_ts {
                    if s.ts == last {
                        session.counters.duplicate += 1;
                        report.rejected.push(Rejection {
                            index: i,
                            reason: "duplicate",
                        });
                        continue;
                    }
                    if s.ts < last {
                        session.counters.out_of_order += 1;
                        report.rejected.push(Rejection {
                            index: i,
                            reason: "out_of_order",
                        });
                        continue;
                    }
                }
                st.last_ts = Some(s.ts);
                if st.unit.is_none() {
                    st.unit = s.unit.clone();
                }
                session.counters.accepted += 1;
                report.accepted += 1;
                session.first_ts = Some(session.first_ts.map_or(s.ts, |t| t.min(s.ts)));
                session.last_ts = Some(session.last_ts.map_or(s.ts, |t| t.max(s.ts)));
                if let Some(recv) = s.recv_ts {
                    let lat = (now - recv).max(0) as u64;
                    session.counters.latency_samples += 1;
                    session.counters.latency_sum_ns =
                        session.counters.latency_sum_ns.saturating_add(lat);
                    session.counters.latency_max_ns = session.counters.latency_max_ns.max(lat);
                }
                for p in st.door.offer(Point::new(s.ts, s.value, s.quality)) {
                    session.store.append(&s.tag, &p)?;
                    st.tail.push(p);
                    archived_in_batch += 1;
                }
            }

            if archived_in_batch > 0 {
                session.store.commit()?;
                session.tail_rows += archived_in_batch;
                session.counters.archived += archived_in_batch as u64;
                session.counters.persisted += archived_in_batch as u64;
                report.archived += archived_in_batch;
                report.persisted += archived_in_batch;
            }
            if session.tail_rows >= self.cfg.flush_rows {
                let n = session.flush_segment()?;
                tracing::info!(session = %session_id, rows = n, "segment written");
            }
        }
        report.rejected.sort_by_key(|r| r.index);
        Ok(report)
    }

    /// Archive held points and fold the tail into a segment. Returns the updated stats.
    pub fn flush_session(&self, id: &str) -> Result<SessionStats, HistorianError> {
        let mut sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        let session = sessions.get_mut(id).ok_or(HistorianError::UnknownSession)?;
        session.close_doors()?;
        session.flush_segment()?;
        Ok(session.stats(id))
    }

    /// Flush every session; used on graceful shutdown.
    pub fn flush_all(&self) -> io::Result<usize> {
        let mut sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        let mut n = 0;
        for session in sessions.values_mut() {
            session.close_doors()?;
            n += session.flush_segment()?;
        }
        Ok(n)
    }

    pub fn sessions(&self) -> Vec<SessionStats> {
        let sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        sessions.iter().map(|(id, s)| s.stats(id)).collect()
    }

    pub fn session(&self, id: &str) -> Result<SessionStats, HistorianError> {
        let sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        sessions
            .get(id)
            .map(|s| s.stats(id))
            .ok_or(HistorianError::UnknownSession)
    }

    pub fn tags(&self, id: &str) -> Result<Vec<TagInfo>, HistorianError> {
        let sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        let session = sessions.get(id).ok_or(HistorianError::UnknownSession)?;
        Ok(session
            .tags
            .iter()
            .map(|(tag, st)| {
                let cfg = st.door.config();
                TagInfo {
                    tag: tag.clone(),
                    unit: st.unit.clone(),
                    deviation: cfg.deviation,
                    max_interval_ns: cfg.max_interval_ns,
                    rows_on_disk: st.rows_on_disk,
                    rows_in_tail: st.tail.len(),
                    pending: st.door.has_pending(),
                    last_ts: st.last_ts,
                }
            })
            .collect())
    }

    /// Archived points for `tag` in `[from, to]`, merged from segments and tail, sorted and
    /// deduplicated by timestamp. Parquet is read outside the historian lock.
    pub fn query(
        &self,
        id: &str,
        tag: &str,
        from: i64,
        to: i64,
    ) -> Result<Vec<Point>, HistorianError> {
        let (segments, mut tail) = {
            let sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
            let session = sessions.get(id).ok_or(HistorianError::UnknownSession)?;
            let st = session.tags.get(tag).ok_or(HistorianError::UnknownTag)?;
            let segments: Vec<PathBuf> = session
                .store
                .segments()
                .iter()
                .map(|s| s.path.clone())
                .collect();
            let tail: Vec<Point> = st
                .tail
                .iter()
                .copied()
                .filter(|p| p.ts >= from && p.ts <= to)
                .collect();
            (segments, tail)
        };
        let mut points =
            crate::storage::read_tag_from(segments.iter().map(PathBuf::as_path), tag, from, to)?;
        points.append(&mut tail);
        points.sort_by_key(|p| p.ts);
        points.dedup_by_key(|p| p.ts);
        Ok(points)
    }

    /// Linear interpolation of `tag` at `ts`, the historian's "value at time" primitive.
    pub fn value_at(&self, id: &str, tag: &str, ts: i64) -> Result<Option<f64>, HistorianError> {
        // A bracket of the two nearest archived points is enough; scan a window first and
        // widen to the whole series only when needed.
        let window = 5_000_000_000;
        let pts = self.query(id, tag, ts - window, ts + window)?;
        if let Some(v) = interpolate(&pts, ts) {
            return Ok(Some(v));
        }
        let pts = self.query(id, tag, i64::MIN, i64::MAX)?;
        Ok(interpolate(&pts, ts))
    }

    /// Unit recorded for `tag`, if any sample carried one.
    pub fn unit(&self, id: &str, tag: &str) -> Option<String> {
        let sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        sessions.get(id)?.tags.get(tag)?.unit.clone()
    }

    /// Prometheus text exposition of the per-session counters.
    pub fn metrics_text(&self) -> String {
        use std::fmt::Write;
        let mut out = String::new();
        let _ = writeln!(out, "# TYPE boxbox_up gauge\nboxbox_up 1");
        let _ = writeln!(
            out,
            "# TYPE boxbox_uptime_seconds counter\nboxbox_uptime_seconds {}",
            self.uptime_secs()
        );
        let _ = writeln!(out, "# TYPE boxbox_samples_total counter");
        let _ = writeln!(out, "# TYPE boxbox_pending_points gauge");
        let _ = writeln!(out, "# TYPE boxbox_tags gauge");
        let _ = writeln!(out, "# TYPE boxbox_bytes_on_disk gauge");
        let _ = writeln!(out, "# TYPE boxbox_recv_latency_ns gauge");
        for s in self.sessions() {
            let c = s.counters;
            for (stage, v) in [
                ("offered", c.offered),
                ("accepted", c.accepted),
                ("rejected", c.rejected),
                ("duplicate", c.duplicate),
                ("out_of_order", c.out_of_order),
                ("archived", c.archived),
                ("persisted", c.persisted),
                ("flushed", c.flushed),
            ] {
                let _ = writeln!(
                    out,
                    "boxbox_samples_total{{session=\"{}\",stage=\"{stage}\"}} {v}",
                    s.session
                );
            }
            let _ = writeln!(
                out,
                "boxbox_pending_points{{session=\"{}\"}} {}",
                s.session, s.pending
            );
            let _ = writeln!(out, "boxbox_tags{{session=\"{}\"}} {}", s.session, s.tags);
            let _ = writeln!(
                out,
                "boxbox_bytes_on_disk{{session=\"{}\"}} {}",
                s.session, s.bytes_on_disk
            );
            if let Some(mean) = c.latency_sum_ns.checked_div(c.latency_samples) {
                let _ = writeln!(
                    out,
                    "boxbox_recv_latency_ns{{session=\"{}\",stat=\"mean\"}} {}",
                    s.session, mean
                );
                let _ = writeln!(
                    out,
                    "boxbox_recv_latency_ns{{session=\"{}\",stat=\"max\"}} {}",
                    s.session, c.latency_max_ns
                );
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::Quality;

    fn sample(session: &str, tag: &str, ts: i64, value: f64) -> IncomingSample {
        IncomingSample {
            session: session.into(),
            tag: tag.into(),
            ts,
            value,
            quality: Quality::Good,
            seq: None,
            recv_ts: None,
            unit: Some("km/h".into()),
        }
    }

    fn historian(dir: &Path, flush_rows: usize) -> Historian {
        let mut cfg = Config::new(dir);
        cfg.fsync = false;
        cfg.flush_rows = flush_rows;
        cfg.default_door.max_interval_ns = None;
        Historian::open(cfg).unwrap()
    }

    #[test]
    fn glob() {
        assert!(glob_match("SIM.CAR*.SPEED", "SIM.CAR12.SPEED"));
        assert!(glob_match("*", "anything"));
        assert!(!glob_match("SIM.CAR*.SPEED", "SIM.CAR12.GEAR"));
        assert!(glob_match("A*B*C", "AxxByyC"));
        assert!(!glob_match("A*B*C", "AxxByyCd"));
    }

    #[test]
    fn rules_override_defaults() {
        let mut cfg = Config::new("/tmp/x");
        cfg.rules.tags.push(TagRule {
            pattern: "SIM.CAR*.SPEED".into(),
            deviation: Some(0.5),
            max_interval_ms: Some(0),
        });
        let d = cfg.door_for("SIM.CAR0.SPEED");
        assert_eq!(d.deviation, 0.5);
        assert_eq!(d.max_interval_ns, None);
        assert_eq!(cfg.door_for("SIM.CAR0.GEAR"), SwingingDoorConfig::default());
    }

    #[test]
    fn ingest_validates_orders_and_counts() {
        let dir = tempfile::tempdir().unwrap();
        let h = historian(dir.path(), 1_000_000);
        let batch = vec![
            sample("s1", "A", 10, 1.0),
            sample("s1", "A", 20, 2.0),
            sample("s1", "A", 20, 2.5), // duplicate
            sample("s1", "A", 15, 9.0), // out of order
            sample("s1", "bad tag", 30, 1.0),
            sample("s1", "A", 30, f64::NAN),
            sample("../x", "A", 40, 1.0),
            sample("s1", "A", 40, 4.0),
        ];
        let r = h.ingest(&batch).unwrap();
        assert_eq!((r.offered, r.accepted), (8, 3));
        let reasons: Vec<_> = r.rejected.iter().map(|x| (x.index, x.reason)).collect();
        assert_eq!(
            reasons,
            vec![
                (2, "duplicate"),
                (3, "out_of_order"),
                (4, "invalid_tag"),
                (5, "non_finite_value"),
                (6, "invalid_session")
            ]
        );
        let stats = h.session("s1").unwrap();
        assert_eq!(stats.counters.accepted, 3);
        assert_eq!(stats.counters.duplicate, 1);
        assert_eq!(stats.counters.out_of_order, 1);
        assert_eq!(stats.counters.rejected, 2);
        // 10, 20, 40 is a straight line: only the first point is archived, 40 is held.
        assert_eq!(stats.counters.archived, 1);
        assert_eq!(stats.pending, 1);
        assert_eq!(h.unit("s1", "A").as_deref(), Some("km/h"));
        assert!(h.session("../x").is_err());
    }

    #[test]
    fn query_merges_segments_and_tail_and_flush_archives_pending() {
        let dir = tempfile::tempdir().unwrap();
        let h = historian(dir.path(), 4);
        let batch: Vec<IncomingSample> = [1.0, 5.0, 1.0, 5.0, 1.0, 5.0, 1.0]
            .iter()
            .enumerate()
            .map(|(i, v)| sample("s", "A", i as i64 * 10, *v))
            .collect();
        h.ingest(&batch).unwrap();
        let stats = h.session("s").unwrap();
        // A zig-zag never compresses: six points are archived, the seventh is held. The
        // segment flush runs after the batch, so the whole tail is on disk.
        assert_eq!(
            (stats.rows_on_disk, stats.rows_in_tail, stats.pending),
            (6, 0, 1)
        );

        let before = h.query("s", "A", i64::MIN, i64::MAX).unwrap();
        assert_eq!(before.len(), 6);
        let stats = h.flush_session("s").unwrap();
        assert_eq!(
            (stats.pending, stats.rows_in_tail, stats.rows_on_disk),
            (0, 0, 7)
        );
        let after = h.query("s", "A", 20, 40).unwrap();
        assert_eq!(
            after.iter().map(|p| p.ts).collect::<Vec<_>>(),
            vec![20, 30, 40]
        );
        assert_eq!(h.value_at("s", "A", 25).unwrap(), Some(3.0));
        assert!(matches!(
            h.query("s", "Z", 0, 1),
            Err(HistorianError::UnknownTag)
        ));
        assert!(matches!(
            h.query("nope", "A", 0, 1),
            Err(HistorianError::UnknownSession)
        ));
    }

    #[test]
    fn restart_replays_wal_and_keeps_ordering() {
        let dir = tempfile::tempdir().unwrap();
        {
            let h = historian(dir.path(), 1_000_000);
            let batch: Vec<IncomingSample> = [1.0, 5.0, 1.0, 5.0]
                .iter()
                .enumerate()
                .map(|(i, v)| sample("s", "A", i as i64 * 10, *v))
                .collect();
            h.ingest(&batch).unwrap();
            // Dropped without flush: three archived points are in the WAL, one is pending.
        }
        let h = historian(dir.path(), 1_000_000);
        let stats = h.session("s").unwrap();
        assert_eq!(
            (stats.rows_on_disk, stats.rows_in_tail, stats.pending),
            (0, 3, 0)
        );
        let pts = h.query("s", "A", i64::MIN, i64::MAX).unwrap();
        assert_eq!(
            pts.iter().map(|p| p.ts).collect::<Vec<_>>(),
            vec![0, 10, 20]
        );
        // Ordering is still enforced against replayed data.
        let r = h
            .ingest(&[sample("s", "A", 15, 1.0), sample("s", "A", 40, 1.0)])
            .unwrap();
        assert_eq!(r.rejected[0].reason, "out_of_order");
        assert_eq!(r.accepted, 1);
        h.flush_all().unwrap();
        let h = historian(dir.path(), 1_000_000);
        assert_eq!(h.session("s").unwrap().rows_on_disk, 4);
        assert!(h.metrics_text().contains("boxbox_tags{session=\"s\"} 1"));
    }
}
