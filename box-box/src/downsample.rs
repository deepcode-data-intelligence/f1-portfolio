//! Reduce a point series for display without hiding peaks.
//!
//! `MinMax` keeps the minimum and maximum of each time bucket, so braking spikes and top
//! speeds survive; `Avg` returns one mean point per bucket; `Raw` never reduces.

use serde::Deserialize;

use crate::model::{Point, Quality};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Agg {
    #[default]
    MinMax,
    Avg,
    Raw,
}

/// Returns the (possibly reduced) series and whether it was reduced.
pub fn downsample(points: &[Point], max_points: usize, agg: Agg) -> (Vec<Point>, bool) {
    if points.len() <= max_points || max_points == 0 || agg == Agg::Raw {
        return (points.to_vec(), false);
    }
    let (first, last) = (points[0].ts, points[points.len() - 1].ts);
    let span = (last - first).max(1) as u128;
    let buckets = match agg {
        Agg::MinMax => (max_points / 2).max(1),
        Agg::Avg | Agg::Raw => max_points.max(1),
    } as u128;
    let bucket_of = |ts: i64| -> usize { (((ts - first) as u128 * buckets) / (span + 1)) as usize };

    let mut out = Vec::with_capacity(max_points);
    let mut start = 0usize;
    while start < points.len() {
        let b = bucket_of(points[start].ts);
        let mut end = start;
        while end < points.len() && bucket_of(points[end].ts) == b {
            end += 1;
        }
        let bucket = &points[start..end];
        match agg {
            Agg::MinMax => {
                let (mut lo, mut hi) = (0usize, 0usize);
                for (i, p) in bucket.iter().enumerate() {
                    if p.value < bucket[lo].value {
                        lo = i;
                    }
                    if p.value > bucket[hi].value {
                        hi = i;
                    }
                }
                if lo == hi {
                    out.push(bucket[lo]);
                } else {
                    out.push(bucket[lo.min(hi)]);
                    out.push(bucket[lo.max(hi)]);
                }
            }
            Agg::Avg => {
                let n = bucket.len() as f64;
                let value = bucket.iter().map(|p| p.value).sum::<f64>() / n;
                let ts = bucket[0].ts + (bucket[bucket.len() - 1].ts - bucket[0].ts) / 2;
                let quality = bucket
                    .iter()
                    .map(|p| p.quality)
                    .max_by_key(|q| q.as_u8())
                    .unwrap_or(Quality::Good);
                out.push(Point::new(ts, value, quality));
            }
            Agg::Raw => unreachable!(),
        }
        start = end;
    }
    (out, true)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn series(n: i64) -> Vec<Point> {
        (0..n)
            .map(|i| {
                Point::new(
                    i * 10,
                    if i % 50 == 25 { 300.0 } else { (i % 7) as f64 },
                    Quality::Good,
                )
            })
            .collect()
    }

    #[test]
    fn small_series_untouched() {
        let s = series(10);
        let (out, reduced) = downsample(&s, 100, Agg::MinMax);
        assert!(!reduced);
        assert_eq!(out, s);
    }

    #[test]
    fn minmax_keeps_peaks_and_order() {
        let s = series(1000);
        let (out, reduced) = downsample(&s, 100, Agg::MinMax);
        assert!(reduced);
        assert!(out.len() <= 100, "{}", out.len());
        assert_eq!(out.iter().filter(|p| p.value == 300.0).count(), 20);
        assert!(out.windows(2).all(|w| w[0].ts < w[1].ts));
    }

    #[test]
    fn avg_reduces_to_bucket_count() {
        let s: Vec<Point> = (0..1000)
            .map(|i| Point::new(i, 2.0, Quality::Good))
            .collect();
        let (out, _) = downsample(&s, 10, Agg::Avg);
        assert_eq!(out.len(), 10);
        assert!(out.iter().all(|p| (p.value - 2.0).abs() < 1e-12));
    }

    #[test]
    fn raw_never_reduces() {
        let s = series(1000);
        assert_eq!(downsample(&s, 10, Agg::Raw).0.len(), 1000);
    }
}
