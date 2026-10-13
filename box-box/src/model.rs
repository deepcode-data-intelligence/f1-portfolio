//! Samples as they arrive, points as they are stored, and the quality that travels with them.

use serde::{Deserialize, Serialize, Serializer};

/// Trust level attached to every value, following the industrial historian convention.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Quality {
    #[default]
    Good,
    /// Parse error, out of range, or flagged invalid by the source.
    Bad,
    /// No fresh value within the expected interval; the last value was repeated.
    Stale,
    /// Value filled in by an intermediate component (e.g. interpolation).
    Substituted,
}

impl Quality {
    pub const fn as_u8(self) -> u8 {
        match self {
            Quality::Good => 0,
            Quality::Bad => 1,
            Quality::Stale => 2,
            Quality::Substituted => 3,
        }
    }

    pub const fn from_u8(code: u8) -> Quality {
        match code {
            1 => Quality::Bad,
            2 => Quality::Stale,
            3 => Quality::Substituted,
            _ => Quality::Good,
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Quality::Good => "good",
            Quality::Bad => "bad",
            Quality::Stale => "stale",
            Quality::Substituted => "substituted",
        }
    }
}

/// One sample as offered to `POST /ingest`.
///
/// `ts` and `recv_ts` are nanoseconds since the Unix epoch, UTC. `ts` is the event time
/// assigned by the source (game frame); `recv_ts` is when the connector received the packet
/// and is used only for latency accounting. `seq` lets duplicates be told apart from
/// out-of-order samples. `unit` is tag metadata and is kept from the first sample that
/// carries it.
#[derive(Clone, Debug, Deserialize)]
pub struct IncomingSample {
    pub session: String,
    pub tag: String,
    pub ts: i64,
    pub value: f64,
    #[serde(default)]
    pub quality: Quality,
    #[serde(default)]
    pub seq: Option<u64>,
    #[serde(default)]
    pub recv_ts: Option<i64>,
    #[serde(default)]
    pub unit: Option<String>,
}

/// A stored point. Serialized compactly as `[ts, value, quality]`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Point {
    pub ts: i64,
    pub value: f64,
    pub quality: Quality,
}

impl Point {
    pub const fn new(ts: i64, value: f64, quality: Quality) -> Point {
        Point { ts, value, quality }
    }
}

impl Serialize for Point {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        (self.ts, self.value, self.quality.as_str()).serialize(serializer)
    }
}

const MAX_ID_LEN: usize = 128;

fn valid_id(id: &str, extra: &[char]) -> bool {
    !id.is_empty()
        && id.len() <= MAX_ID_LEN
        && id.chars().all(|c| {
            c.is_ascii_alphanumeric() || c == '.' || c == '_' || c == '-' || extra.contains(&c)
        })
        && !id.starts_with('.')
}

/// Session ids become directory names, so they are restricted to a safe alphabet.
pub fn valid_session_id(id: &str) -> bool {
    valid_id(id, &[':'])
}

/// Tag names: dotted, e.g. `SIM.CAR0.SPEED` or `VER.speed`.
pub fn valid_tag(tag: &str) -> bool {
    valid_id(tag, &[])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quality_roundtrips_through_u8() {
        for q in [
            Quality::Good,
            Quality::Bad,
            Quality::Stale,
            Quality::Substituted,
        ] {
            assert_eq!(Quality::from_u8(q.as_u8()), q);
        }
    }

    #[test]
    fn ids_are_restricted() {
        assert!(valid_session_id("sim:2024-10-13T20:01:02Z:ABC123"));
        assert!(valid_tag("SIM.CAR0.TYRE.FL.TEMP"));
        assert!(!valid_tag(""));
        assert!(!valid_tag("../etc"));
        assert!(!valid_session_id("a/b"));
        assert!(!valid_tag("has space"));
    }

    #[test]
    fn point_serializes_as_triple() {
        let json = serde_json::to_string(&Point::new(10, 1.5, Quality::Stale)).unwrap();
        assert_eq!(json, "[10,1.5,\"stale\"]");
    }

    #[test]
    fn incoming_sample_defaults() {
        let s: IncomingSample =
            serde_json::from_str(r#"{"session":"s","tag":"t","ts":1,"value":2.0}"#).unwrap();
        assert_eq!(s.quality, Quality::Good);
        assert!(s.seq.is_none() && s.recv_ts.is_none() && s.unit.is_none());
    }
}
