//! Swinging-door trending (SDT), the compression test used by industrial historians.
//!
//! The filter keeps the last *archived* point and a *held* candidate. Each new sample narrows
//! a pair of slopes ("doors") drawn from the archived point through `value ± deviation`.
//! While the doors stay open every sample since the archived point can be reconstructed by
//! linear interpolation within `deviation`. When they cross, the held point is archived and
//! the doors restart from it. A quality change or the configured maximum interval also
//! forces an archive, so silence and heartbeat behaviour are explicit.
//!
//! The classic test only bounds the reconstruction error by *twice* the door width: the
//! stored segment runs through the held point, not through the best line inside the doors.
//! The doors are therefore opened with `deviation / 2`, so that the error of linear
//! interpolation between archived points is at most `deviation`, which is the number a
//! user cares about. With `deviation == 0` only exactly collinear points are dropped and
//! reconstruction is exact.

use crate::model::Point;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SwingingDoorConfig {
    /// Absolute deviation allowed between the original signal and its reconstruction.
    pub deviation: f64,
    /// Archive at least one point per interval (nanoseconds) even when the signal is flat.
    pub max_interval_ns: Option<i64>,
}

impl Default for SwingingDoorConfig {
    fn default() -> Self {
        SwingingDoorConfig {
            deviation: 0.0,
            max_interval_ns: Some(1_000_000_000),
        }
    }
}

#[derive(Debug)]
pub struct SwingingDoor {
    cfg: SwingingDoorConfig,
    /// Half of the configured deviation; see the module documentation.
    half_dev: f64,
    archived: Option<Point>,
    held: Option<Point>,
    slope_max: f64,
    slope_min: f64,
}

impl SwingingDoor {
    pub fn new(cfg: SwingingDoorConfig) -> SwingingDoor {
        SwingingDoor {
            cfg,
            half_dev: cfg.deviation.max(0.0) / 2.0,
            archived: None,
            held: None,
            slope_max: f64::INFINITY,
            slope_min: f64::NEG_INFINITY,
        }
    }

    pub fn config(&self) -> SwingingDoorConfig {
        self.cfg
    }

    /// Is there a candidate point that has been seen but not archived yet?
    pub fn has_pending(&self) -> bool {
        self.held.is_some()
    }

    /// Timestamp of the last archived point, if any.
    pub fn last_archived_ts(&self) -> Option<i64> {
        self.archived.map(|p| p.ts)
    }

    /// Offer a sample. Timestamps must be strictly increasing per filter instance; the
    /// caller enforces that. Returns the points to archive (zero, one or two).
    pub fn offer(&mut self, p: Point) -> Vec<Point> {
        let Some(archived) = self.archived else {
            self.archive(p);
            return vec![p];
        };

        let quality_changed =
            p.quality != archived.quality || self.held.is_some_and(|h| h.quality != p.quality);
        let interval_exceeded = self
            .cfg
            .max_interval_ns
            .is_some_and(|max| p.ts - archived.ts >= max);

        if quality_changed {
            // Close the current segment on the held point, then start a new one on `p`.
            let mut out = Vec::with_capacity(2);
            if let Some(h) = self.held.take() {
                out.push(h);
            }
            self.archive(p);
            out.push(p);
            return out;
        }

        if interval_exceeded {
            // Bound the gap: the held point becomes the anchor and `p` the new candidate.
            // With nothing held, `p` itself is archived.
            return match self.held.take() {
                Some(h) => {
                    self.restart_from(h, p);
                    vec![h]
                }
                None => {
                    self.archive(p);
                    vec![p]
                }
            };
        }

        let dt = (p.ts - archived.ts) as f64;
        let up = (p.value + self.half_dev - archived.value) / dt;
        let low = (p.value - self.half_dev - archived.value) / dt;

        let Some(held) = self.held else {
            self.held = Some(p);
            self.slope_max = up;
            self.slope_min = low;
            return Vec::new();
        };

        let slope_max = self.slope_max.min(up);
        let slope_min = self.slope_min.max(low);
        if slope_min > slope_max {
            // Doors crossed: the held point becomes the new anchor, `p` is the new candidate.
            self.restart_from(held, p);
            vec![held]
        } else {
            self.slope_max = slope_max;
            self.slope_min = slope_min;
            self.held = Some(p);
            Vec::new()
        }
    }

    /// Archive the held point, if any. Called on session flush and shutdown.
    pub fn flush(&mut self) -> Option<Point> {
        let held = self.held.take()?;
        self.archived = Some(held);
        self.slope_max = f64::INFINITY;
        self.slope_min = f64::NEG_INFINITY;
        Some(held)
    }

    /// Make `anchor` the archived point and `candidate` the held point.
    fn restart_from(&mut self, anchor: Point, candidate: Point) {
        self.archived = Some(anchor);
        self.held = Some(candidate);
        let dt = (candidate.ts - anchor.ts) as f64;
        self.slope_max = (candidate.value + self.half_dev - anchor.value) / dt;
        self.slope_min = (candidate.value - self.half_dev - anchor.value) / dt;
    }

    fn archive(&mut self, p: Point) {
        self.archived = Some(p);
        self.held = None;
        self.slope_max = f64::INFINITY;
        self.slope_min = f64::NEG_INFINITY;
    }
}

/// Linear reconstruction of a compressed series at `ts`; `None` outside the covered range.
pub fn interpolate(points: &[Point], ts: i64) -> Option<f64> {
    let idx = points.partition_point(|p| p.ts <= ts);
    if idx == 0 {
        return (points.first()?.ts == ts).then(|| points[0].value);
    }
    let a = points[idx - 1];
    if a.ts == ts || idx == points.len() {
        return (a.ts == ts).then_some(a.value);
    }
    let b = points[idx];
    let f = (ts - a.ts) as f64 / (b.ts - a.ts) as f64;
    Some(a.value + f * (b.value - a.value))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::Quality;

    fn door(deviation: f64, max_interval_ns: Option<i64>) -> SwingingDoor {
        SwingingDoor::new(SwingingDoorConfig {
            deviation,
            max_interval_ns,
        })
    }

    fn run(door: &mut SwingingDoor, pts: &[Point]) -> Vec<Point> {
        let mut out: Vec<Point> = pts.iter().flat_map(|p| door.offer(*p)).collect();
        out.extend(door.flush());
        out
    }

    fn good(ts: i64, v: f64) -> Point {
        Point::new(ts, v, Quality::Good)
    }

    #[test]
    fn linear_ramp_collapses_to_endpoints() {
        let pts: Vec<Point> = (0..100).map(|i| good(i, i as f64 * 2.0)).collect();
        let out = run(&mut door(0.0, None), &pts);
        assert_eq!(out, vec![good(0, 0.0), good(99, 198.0)]);
    }

    #[test]
    fn step_is_preserved() {
        let pts = vec![
            good(0, 1.0),
            good(1, 1.0),
            good(2, 1.0),
            good(3, 5.0),
            good(4, 5.0),
        ];
        let out = run(&mut door(0.0, None), &pts);
        assert_eq!(
            out,
            vec![good(0, 1.0), good(2, 1.0), good(3, 5.0), good(4, 5.0)]
        );
    }

    #[test]
    fn reconstruction_stays_within_deviation() {
        // A speed-like trace: slow oscillation plus deterministic pseudo-random noise.
        let mut x = 0.5f64;
        let pts: Vec<Point> = (0..5000)
            .map(|i| {
                x = (x * 9301.0 + 49297.0) % 233280.0;
                let noise = (x / 233280.0 - 0.5) * 0.4;
                let v = 200.0 + 100.0 * (i as f64 / 200.0).sin() + noise;
                good(i * 16_666_667, v)
            })
            .collect();
        let mut kept = Vec::new();
        for dev in [0.0, 0.5, 2.0] {
            let out = run(&mut door(dev, None), &pts);
            let max_err = pts
                .iter()
                .map(|p| (interpolate(&out, p.ts).unwrap() - p.value).abs())
                .fold(0.0, f64::max);
            assert!(max_err <= dev + 1e-9, "dev={dev} max_err={max_err}");
            kept.push(out.len());
        }
        assert!(kept[0] <= pts.len());
        assert!(kept[1] < kept[0] / 2, "dev=0.5 kept {}", kept[1]);
        assert!(kept[2] < kept[1] / 2, "dev=2.0 kept {}", kept[2]);
    }

    #[test]
    fn quality_change_forces_archive() {
        let pts = vec![
            good(0, 1.0),
            good(1, 1.0),
            good(2, 1.0),
            Point::new(3, 1.0, Quality::Stale),
            Point::new(4, 1.0, Quality::Stale),
        ];
        let out = run(&mut door(0.0, None), &pts);
        assert_eq!(
            out,
            vec![
                good(0, 1.0),
                good(2, 1.0),
                Point::new(3, 1.0, Quality::Stale),
                Point::new(4, 1.0, Quality::Stale),
            ]
        );
    }

    #[test]
    fn max_interval_bounds_silence() {
        let pts: Vec<Point> = (0..10).map(|i| good(i * 100, 7.0)).collect();
        let out = run(&mut door(0.0, Some(300)), &pts);
        let ts: Vec<i64> = out.iter().map(|p| p.ts).collect();
        assert_eq!(ts, vec![0, 200, 400, 600, 800, 900]);
    }

    #[test]
    fn flush_emits_held_point_once() {
        let mut d = door(0.0, None);
        d.offer(good(0, 1.0));
        d.offer(good(1, 1.0));
        assert!(d.has_pending());
        assert_eq!(d.flush(), Some(good(1, 1.0)));
        assert!(!d.has_pending());
        assert_eq!(d.flush(), None);
    }

    #[test]
    fn interpolate_edges() {
        let pts = vec![good(10, 1.0), good(20, 3.0)];
        assert_eq!(interpolate(&pts, 5), None);
        assert_eq!(interpolate(&pts, 10), Some(1.0));
        assert_eq!(interpolate(&pts, 15), Some(2.0));
        assert_eq!(interpolate(&pts, 20), Some(3.0));
        assert_eq!(interpolate(&pts, 25), None);
    }
}
