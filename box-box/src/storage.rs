//! Per-session durable storage: an append-only write-ahead log (WAL) for every archived
//! point, periodically folded into Parquet segments.
//!
//! Layout under the data directory:
//!
//! ```text
//! sessions/<session>/wal.log            tab-separated: tag, ts, value, quality
//! sessions/<session>/seg-000001.parquet columns: tag, ts (ns, UTC), value, quality (u8)
//! ```
//!
//! A segment is written to a temporary file, fsynced and renamed before the WAL is
//! truncated. A crash between those two steps leaves duplicates (same tag and timestamp)
//! across WAL and segment; the query path deduplicates them. A truncated last WAL line
//! (crash mid-write) is skipped on replay.

use std::collections::HashMap;
use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use arrow::array::{
    ArrayRef, AsArray, Float64Array, StringArray, TimestampNanosecondArray, UInt8Array,
};
use arrow::datatypes::{
    DataType, Field, Float64Type, Schema, SchemaRef, TimeUnit, TimestampNanosecondType, UInt8Type,
};
use arrow::record_batch::RecordBatch;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use parquet::arrow::ArrowWriter;
use parquet::basic::{Compression, ZstdLevel};
use parquet::file::properties::WriterProperties;

use crate::model::{Point, Quality};

pub const WAL_FILE: &str = "wal.log";
const SEGMENT_PREFIX: &str = "seg-";
const ROW_GROUP_SIZE: usize = 64 * 1024;

pub fn schema() -> SchemaRef {
    Arc::new(Schema::new(vec![
        Field::new("tag", DataType::Utf8, false),
        Field::new(
            "ts",
            DataType::Timestamp(TimeUnit::Nanosecond, Some("UTC".into())),
            false,
        ),
        Field::new("value", DataType::Float64, false),
        Field::new("quality", DataType::UInt8, false),
    ]))
}

#[derive(Debug, Clone, Default)]
pub struct SegmentInfo {
    pub path: PathBuf,
    pub rows: i64,
    pub bytes: u64,
}

pub struct SessionStore {
    dir: PathBuf,
    wal_path: PathBuf,
    wal: BufWriter<File>,
    segments: Vec<SegmentInfo>,
    fsync: bool,
}

fn other<E: std::error::Error + Send + Sync + 'static>(e: E) -> io::Error {
    io::Error::other(e)
}

fn open_wal(path: &Path) -> io::Result<BufWriter<File>> {
    Ok(BufWriter::new(
        OpenOptions::new().create(true).append(true).open(path)?,
    ))
}

fn segment_info(path: PathBuf) -> io::Result<SegmentInfo> {
    let file = File::open(&path)?;
    let bytes = file.metadata()?.len();
    let builder = ParquetRecordBatchReaderBuilder::try_new(file).map_err(other)?;
    let rows = builder.metadata().file_metadata().num_rows();
    Ok(SegmentInfo { path, rows, bytes })
}

impl SessionStore {
    pub fn open(dir: &Path, fsync: bool) -> io::Result<SessionStore> {
        fs::create_dir_all(dir)?;
        let mut segments = Vec::new();
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if name.starts_with(SEGMENT_PREFIX) && name.ends_with(".parquet") {
                segments.push(segment_info(path)?);
            }
        }
        segments.sort_by(|a, b| a.path.cmp(&b.path));
        let wal_path = dir.join(WAL_FILE);
        Ok(SessionStore {
            wal: open_wal(&wal_path)?,
            dir: dir.to_path_buf(),
            wal_path,
            segments,
            fsync,
        })
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    pub fn segments(&self) -> &[SegmentInfo] {
        &self.segments
    }

    pub fn rows_on_disk(&self) -> i64 {
        self.segments.iter().map(|s| s.rows).sum()
    }

    pub fn bytes_on_disk(&self) -> u64 {
        self.segments.iter().map(|s| s.bytes).sum::<u64>()
            + fs::metadata(&self.wal_path).map(|m| m.len()).unwrap_or(0)
    }

    /// Append one archived point to the WAL. Not durable until [`commit`](Self::commit).
    pub fn append(&mut self, tag: &str, p: &Point) -> io::Result<()> {
        writeln!(
            self.wal,
            "{tag}\t{}\t{}\t{}",
            p.ts,
            p.value,
            p.quality.as_u8()
        )
    }

    /// Flush buffered WAL writes to the OS and, when configured, to the device.
    pub fn commit(&mut self) -> io::Result<()> {
        self.wal.flush()?;
        if self.fsync {
            self.wal.get_ref().sync_data()?;
        }
        Ok(())
    }

    /// Rows currently in the WAL, in append order. Malformed or truncated lines are skipped.
    pub fn replay_wal(&self) -> io::Result<Vec<(String, Point)>> {
        let file = match File::open(&self.wal_path) {
            Ok(f) => f,
            Err(e) if e.kind() == io::ErrorKind::NotFound => return Ok(Vec::new()),
            Err(e) => return Err(e),
        };
        let mut rows = Vec::new();
        let mut skipped = 0usize;
        for line in BufReader::new(file).lines() {
            let line = line?;
            match parse_wal_line(&line) {
                Some(row) => rows.push(row),
                None => skipped += 1,
            }
        }
        if skipped > 0 {
            tracing::warn!(session_dir = %self.dir.display(), skipped, "skipped malformed WAL lines");
        }
        Ok(rows)
    }

    /// Fold `rows` into a new Parquet segment and truncate the WAL.
    pub fn write_segment(
        &mut self,
        mut rows: Vec<(String, Point)>,
    ) -> io::Result<Option<SegmentInfo>> {
        if rows.is_empty() {
            return Ok(None);
        }
        rows.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.ts.cmp(&b.1.ts)));
        let next = self
            .segments
            .last()
            .and_then(|s| {
                s.path
                    .file_stem()?
                    .to_str()?
                    .strip_prefix(SEGMENT_PREFIX)?
                    .parse::<u32>()
                    .ok()
            })
            .unwrap_or(0)
            + 1;
        let final_path = self.dir.join(format!("{SEGMENT_PREFIX}{next:06}.parquet"));
        let tmp_path = self
            .dir
            .join(format!("{SEGMENT_PREFIX}{next:06}.parquet.tmp"));

        let batch = to_batch(&rows).map_err(other)?;
        let props = WriterProperties::builder()
            .set_compression(Compression::ZSTD(ZstdLevel::default()))
            .set_max_row_group_row_count(Some(ROW_GROUP_SIZE))
            .build();
        let file = File::create(&tmp_path)?;
        let mut writer = ArrowWriter::try_new(file, schema(), Some(props)).map_err(other)?;
        writer.write(&batch).map_err(other)?;
        let file = writer.into_inner().map_err(other)?;
        if self.fsync {
            file.sync_all()?;
        }
        drop(file);
        fs::rename(&tmp_path, &final_path)?;
        if self.fsync {
            File::open(&self.dir)?.sync_all()?;
        }

        // The segment is durable; the WAL can start over.
        self.wal.flush()?;
        self.wal = BufWriter::new(
            OpenOptions::new()
                .write(true)
                .truncate(true)
                .open(&self.wal_path)?,
        );
        if self.fsync {
            self.wal.get_ref().sync_data()?;
        }

        let info = segment_info(final_path)?;
        self.segments.push(info.clone());
        Ok(Some(info))
    }

    /// Points for `tag` within `[from, to]` across all segments, sorted by timestamp.
    pub fn read_tag(&self, tag: &str, from: i64, to: i64) -> io::Result<Vec<Point>> {
        read_tag_from(
            self.segments.iter().map(|s| s.path.as_path()),
            tag,
            from,
            to,
        )
    }

    /// Latest timestamp per tag across all segments; used to enforce monotonic ingest
    /// after a restart.
    pub fn last_ts_per_tag(&self) -> io::Result<HashMap<String, i64>> {
        let mut out: HashMap<String, i64> = HashMap::new();
        for seg in &self.segments {
            for_each_row(&seg.path, |tag, p| {
                out.entry(tag.to_string())
                    .and_modify(|t| *t = (*t).max(p.ts))
                    .or_insert(p.ts);
            })?;
        }
        Ok(out)
    }

    /// Tags present in the segments, with their row counts.
    pub fn tags_on_disk(&self) -> io::Result<HashMap<String, i64>> {
        let mut out: HashMap<String, i64> = HashMap::new();
        for seg in &self.segments {
            for_each_row(&seg.path, |tag, _| {
                *out.entry(tag.to_string()).or_default() += 1
            })?;
        }
        Ok(out)
    }
}

/// Read `tag` within `[from, to]` from the given segment files. Public so that the query
/// path can run against a snapshot of segment paths without holding the historian lock.
pub fn read_tag_from<'a>(
    segments: impl Iterator<Item = &'a Path>,
    tag: &str,
    from: i64,
    to: i64,
) -> io::Result<Vec<Point>> {
    let mut out = Vec::new();
    for path in segments {
        for_each_row(path, |t, p| {
            if t == tag && p.ts >= from && p.ts <= to {
                out.push(p);
            }
        })?;
    }
    out.sort_by_key(|p| p.ts);
    Ok(out)
}

fn for_each_row(path: &Path, mut f: impl FnMut(&str, Point)) -> io::Result<()> {
    let file = File::open(path)?;
    let reader = ParquetRecordBatchReaderBuilder::try_new(file)
        .map_err(other)?
        .with_batch_size(ROW_GROUP_SIZE)
        .build()
        .map_err(other)?;
    for batch in reader {
        let batch = batch.map_err(other)?;
        let tags = batch.column(0).as_string::<i32>();
        let ts = batch.column(1).as_primitive::<TimestampNanosecondType>();
        let values = batch.column(2).as_primitive::<Float64Type>();
        let quality = batch.column(3).as_primitive::<UInt8Type>();
        for i in 0..batch.num_rows() {
            f(
                tags.value(i),
                Point::new(
                    ts.value(i),
                    values.value(i),
                    Quality::from_u8(quality.value(i)),
                ),
            );
        }
    }
    Ok(())
}

fn to_batch(rows: &[(String, Point)]) -> Result<RecordBatch, arrow::error::ArrowError> {
    let tags = StringArray::from_iter_values(rows.iter().map(|(t, _)| t.as_str()));
    let ts = TimestampNanosecondArray::from_iter_values(rows.iter().map(|(_, p)| p.ts))
        .with_timezone("UTC");
    let values = Float64Array::from_iter_values(rows.iter().map(|(_, p)| p.value));
    let quality = UInt8Array::from_iter_values(rows.iter().map(|(_, p)| p.quality.as_u8()));
    RecordBatch::try_new(
        schema(),
        vec![
            Arc::new(tags) as ArrayRef,
            Arc::new(ts),
            Arc::new(values),
            Arc::new(quality),
        ],
    )
}

fn parse_wal_line(line: &str) -> Option<(String, Point)> {
    let mut parts = line.split('\t');
    let tag = parts.next()?;
    let ts = parts.next()?.parse::<i64>().ok()?;
    let value = parts.next()?.parse::<f64>().ok()?;
    let quality = parts.next()?.parse::<u8>().ok()?;
    if parts.next().is_some() || tag.is_empty() || !value.is_finite() {
        return None;
    }
    Some((
        tag.to_string(),
        Point::new(ts, value, Quality::from_u8(quality)),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rows(n: i64) -> Vec<(String, Point)> {
        (0..n)
            .flat_map(|i| {
                [
                    ("A".to_string(), Point::new(i, i as f64, Quality::Good)),
                    ("B".to_string(), Point::new(i, -(i as f64), Quality::Stale)),
                ]
            })
            .collect()
    }

    #[test]
    fn wal_roundtrip_and_truncated_line() {
        let dir = tempfile::tempdir().unwrap();
        let mut store = SessionStore::open(dir.path(), false).unwrap();
        for (t, p) in rows(3) {
            store.append(&t, &p).unwrap();
        }
        store.commit().unwrap();
        // Simulate a crash mid-write.
        let mut f = OpenOptions::new()
            .append(true)
            .open(dir.path().join(WAL_FILE))
            .unwrap();
        write!(f, "A\t99\t1.").unwrap();
        drop(f);

        let replayed = SessionStore::open(dir.path(), false)
            .unwrap()
            .replay_wal()
            .unwrap();
        assert_eq!(replayed, rows(3));
    }

    #[test]
    fn segment_roundtrip_truncates_wal_and_survives_reopen() {
        let dir = tempfile::tempdir().unwrap();
        let mut store = SessionStore::open(dir.path(), true).unwrap();
        for (t, p) in rows(10) {
            store.append(&t, &p).unwrap();
        }
        store.commit().unwrap();
        let info = store.write_segment(rows(10)).unwrap().unwrap();
        assert_eq!(info.rows, 20);
        assert!(store.replay_wal().unwrap().is_empty());

        let reopened = SessionStore::open(dir.path(), true).unwrap();
        assert_eq!(reopened.segments().len(), 1);
        assert_eq!(reopened.rows_on_disk(), 20);
        let a = reopened.read_tag("A", 2, 4).unwrap();
        assert_eq!(a.iter().map(|p| p.ts).collect::<Vec<_>>(), vec![2, 3, 4]);
        let b = reopened.read_tag("B", i64::MIN, i64::MAX).unwrap();
        assert_eq!(b.len(), 10);
        assert!(b.iter().all(|p| p.quality == Quality::Stale));
        assert_eq!(reopened.last_ts_per_tag().unwrap()["A"], 9);

        // Second segment gets the next index.
        let mut reopened = reopened;
        let info2 = reopened.write_segment(rows(1)).unwrap().unwrap();
        assert!(info2.path.ends_with("seg-000002.parquet"));
    }

    #[test]
    fn parse_wal_rejects_garbage() {
        assert!(parse_wal_line("A\t1\tnan\t0").is_none());
        assert!(parse_wal_line("A\t1\t1.0").is_none());
        assert!(parse_wal_line("A\t1\t1.0\t0\textra").is_none());
        assert_eq!(
            parse_wal_line("A\t1\t1.5\t2"),
            Some(("A".into(), Point::new(1, 1.5, Quality::Stale)))
        );
    }
}
