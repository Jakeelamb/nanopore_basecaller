use anyhow::{bail, ensure, Context, Result};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

pub fn kv(path: &Path) -> Result<BTreeMap<String, String>> {
    let mut m = BTreeMap::new();
    for line in fs::read_to_string(path)?.lines() {
        let (k, v) = line.split_once('\t').context("metadata TSV")?;
        ensure!(
            !v.contains('\t') && m.insert(k.to_owned(), v.to_owned()).is_none(),
            "duplicate/malformed metadata key"
        );
    }
    Ok(m)
}
pub fn value<'a>(m: &'a BTreeMap<String, String>, k: &str) -> Result<&'a str> {
    m.get(k)
        .map(String::as_str)
        .with_context(|| format!("missing metadata {k}"))
}
pub fn num(m: &BTreeMap<String, String>, k: &str) -> Result<usize> {
    Ok(value(m, k)?.parse()?)
}
pub fn revcomp(s: &str) -> Result<String> {
    s.bytes()
        .rev()
        .map(|b| {
            Ok(match b {
                b'A' => 'T',
                b'C' => 'G',
                b'G' => 'C',
                b'T' => 'A',
                b'N' => 'N',
                b'R' => 'Y',
                b'Y' => 'R',
                b'S' => 'S',
                b'W' => 'W',
                b'K' => 'M',
                b'M' => 'K',
                b'B' => 'V',
                b'V' => 'B',
                b'D' => 'H',
                b'H' => 'D',
                _ => bail!("invalid DNA"),
            })
        })
        .collect()
}
pub fn cigar(s: &str) -> Result<Vec<(usize, u8)>> {
    ensure!(s != "*" && !s.is_empty(), "missing CIGAR");
    let mut n = 0usize;
    let mut out = Vec::new();
    for b in s.bytes() {
        if b.is_ascii_digit() {
            n = n
                .checked_mul(10)
                .and_then(|n| n.checked_add((b - b'0') as usize))
                .context("CIGAR overflow")?;
        } else {
            ensure!(n > 0 && b"MIDNSHP=X".contains(&b), "invalid CIGAR");
            out.push((n, b));
            n = 0;
        }
    }
    ensure!(n == 0 && !out.is_empty(), "unfinished CIGAR");
    Ok(out)
}
#[derive(Clone, Debug)]
pub struct Sam {
    pub id: String,
    pub flag: u16,
    pub contig: String,
    pub pos: usize,
    pub mapq: u8,
    pub cigar: String,
    pub aligned: String,
    pub seq: String,
    pub qual: String,
}
impl Sam {
    pub fn reverse(&self) -> bool {
        self.flag & 16 != 0
    }
}
pub fn parents(path: &Path) -> Result<Vec<String>> {
    let mut seen = BTreeSet::new();
    let mut v = Vec::new();
    for l in fs::read_to_string(path)?.lines().filter(|l| !l.is_empty()) {
        ensure!(
            !l.contains(char::is_whitespace)
                && l.len() <= 128
                && l.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-'),
            "invalid parent ID"
        );
        ensure!(seen.insert(l.to_owned()), "duplicate requested UUID");
        v.push(l.to_owned());
    }
    ensure!(!v.is_empty(), "empty parent set");
    ensure!(v.len() <= 64, "parent cohort exceeds 64");
    Ok(v)
}
pub fn sam(path: &Path, ids: &[String]) -> Result<BTreeMap<String, Sam>> {
    use std::io::BufRead;
    let ids: BTreeSet<_> = ids.iter().map(String::as_str).collect();
    let mut out = BTreeMap::new();
    for line in std::io::BufReader::new(fs::File::open(path)?).lines() {
        let line = line?;
        if line.starts_with('@') {
            continue;
        }
        let f: Vec<_> = line.split('\t').collect();
        ensure!(f.len() >= 11, "SAM columns");
        if !ids.contains(f[0]) {
            continue;
        }
        let flag: u16 = f[1].parse()?;
        if flag & (256 | 2048) != 0 {
            continue;
        }
        ensure!(!out.contains_key(f[0]), "duplicate primary for {}", f[0]);
        ensure!(
            f[9] != "*"
                && f[10] != "*"
                && f[9].len() == f[10].len()
                && f[9].is_ascii()
                && f[10].bytes().all(|b| (33..=126).contains(&b)),
            "full SEQ/Q required"
        );
        let aligned = f[9].to_ascii_uppercase();
        let reverse = flag & 16 != 0;
        let seq = if reverse {
            revcomp(&aligned)?
        } else {
            aligned.clone()
        };
        let qual = if reverse {
            f[10].chars().rev().collect()
        } else {
            f[10].to_owned()
        };
        let pos = f[3].parse::<usize>()?.saturating_sub(1);
        out.insert(
            f[0].to_owned(),
            Sam {
                id: f[0].to_owned(),
                flag,
                contig: f[2].to_owned(),
                pos,
                mapq: f[4].parse()?,
                cigar: f[5].to_owned(),
                aligned,
                seq,
                qual,
            },
        );
    }
    ensure!(out.len() == ids.len(), "missing requested primary parent");
    Ok(out)
}
#[derive(Debug, Clone)]
pub struct Chunk {
    pub index: usize,
    pub offset: usize,
    pub raw: usize,
    pub granularity: usize,
    pub variable: bool,
    pub signal: usize,
    pub trimmed: usize,
    pub seq: String,
    pub qual: String,
    pub moves: Vec<u8>,
    pub score_file: String,
}
#[derive(Debug, Clone)]
pub struct Retained {
    pub chunk: Chunk,
    pub t_start: usize,
    pub t_end: usize,
    pub chunk_base_start: usize,
    pub parent_base_start: usize,
    pub parent_base_end: usize,
}
#[derive(Debug)]
pub struct Export {
    pub retained: Vec<Retained>,
}
pub type ChunkMetadata = (String, BTreeMap<String, String>);
pub type Inventory = BTreeMap<String, Vec<ChunkMetadata>>;
fn moves(m: &BTreeMap<String, String>) -> Result<Vec<u8>> {
    value(m, "MOVES")?
        .bytes()
        .map(|b| {
            ensure!(b == b'0' || b == b'1', "nonbinary moves");
            Ok(b - b'0')
        })
        .collect()
}
fn validate_seq(m: &BTreeMap<String, String>) -> Result<(String, String, Vec<u8>)> {
    let seq = value(m, "SEQ")?.to_owned();
    let q = value(m, "Q")?.to_owned();
    let mv = moves(m)?;
    ensure!(
        seq.is_ascii()
            && seq.bytes().all(|b| b"ACGT".contains(&b))
            && seq.len() == q.len()
            && q.bytes().all(|b| (33..=126).contains(&b))
            && mv.iter().map(|&b| b as usize).sum::<usize>() == seq.len(),
        "metadata SEQ/Q/MOVES inconsistent"
    );
    Ok((seq, q, mv))
}
pub fn inventory(dir: &Path, ids: &[String]) -> Result<Inventory> {
    let mut out: BTreeMap<_, Vec<_>> = ids.iter().cloned().map(|i| (i, Vec::new())).collect();
    let mut accepted_files = BTreeSet::new();
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        let name = path
            .file_name()
            .and_then(|s| s.to_str())
            .context("export filename")?
            .to_owned();
        if !name.ends_with(".scores.meta.tsv") {
            continue;
        }
        let m = kv(&path)?;
        ensure!(value(&m, "format")? == "DGM1", "metadata format");
        if let Some(v) = out.get_mut(value(&m, "read_id")?) {
            let score_file = value(&m, "score_file")?;
            ensure!(
                name == format!("{score_file}.meta.tsv"),
                "metadata/score filename mismatch"
            );
            ensure!(
                accepted_files.insert(score_file.to_owned()),
                "score artifact bound to multiple accepted chunks"
            );
            v.push((name, m));
        }
    }
    Ok(out)
}
pub fn reconstruct(
    dir: &Path,
    sam: &Sam,
    entries: &[(String, BTreeMap<String, String>)],
) -> Result<Export> {
    let parent = kv(&dir.join(format!("{}.parent.tsv", sam.id)))?;
    ensure!(
        value(&parent, "format")? == "DGP1"
            && value(&parent, "read_id")? == sam.id
            && num(&parent, "stride")? == 6,
        "parent identity/stride"
    );
    let count = num(&parent, "chunk_count")?;
    ensure!(
        count > 0 && entries.len() == count,
        "missing/duplicate accepted chunk"
    );
    let signal = num(&parent, "signal_samples")?;
    let trim = num(&parent, "num_trimmed_samples")?;
    let variable = match value(&parent, "variable_chunk_sizes")? {
        "0" => false,
        "1" => true,
        _ => bail!("invalid variable chunk flag"),
    };
    let mut chunks = BTreeMap::new();
    let mut tokens = BTreeSet::new();
    for (_, m) in entries {
        ensure!(
            value(m, "read_id")? == sam.id && num(m, "chunk_count")? == count,
            "chunk parent identity"
        );
        let idx = num(m, "chunk_index")?;
        ensure!(idx < count, "chunk index bounds");
        let name = value(m, "score_file")?;
        ensure!(
            Path::new(name).file_name().and_then(|s| s.to_str()) == Some(name),
            "score path traversal"
        );
        let h = crate::scores::header(&dir.join(name))?;
        ensure!(
            h.token == value(m, "token")?
                && h.offset == num(m, "time_offset")?
                && h.t == num(m, "T")?
                && h.c == num(m, "C")?,
            "score metadata identity"
        );
        ensure!(
            tokens.insert((h.token, h.slot)),
            "duplicate accepted token/slot"
        );
        let (seq, qual, mv) = validate_seq(m)?;
        ensure!(mv.len() == h.t, "moves/score timestep count");
        ensure!(
            num(m, "signal_samples")? == signal
                && num(m, "num_trimmed_samples")? == trim
                && num(m, "original_signal_samples")?
                    == signal.checked_add(trim).context("signal overflow")?,
            "chunk sample provenance"
        );
        ensure!(
            value(m, "variable_chunk_sizes")? == if variable { "1" } else { "0" },
            "chunk VCS mismatch"
        );
        let chunk = Chunk {
            index: idx,
            offset: num(m, "input_offset")?,
            raw: num(m, "raw_chunk_size")?,
            granularity: num(m, "chunk_size_granularity")?,
            variable,
            signal,
            trimmed: trim,
            seq,
            qual,
            moves: mv,
            score_file: name.to_owned(),
        };
        ensure!(
            chunk.raw > 0 && chunk.granularity > 0 && chunk.offset < signal,
            "chunk signal bounds"
        );
        // Match Dorado's round-closest(pad_to(raw,granularity)/moves) assertion.
        let padded = chunk
            .raw
            .div_ceil(chunk.granularity)
            .checked_mul(chunk.granularity)
            .context("padded chunk overflow")?;
        ensure!(
            padded
                .checked_add(chunk.moves.len() / 2)
                .context("chunk stride overflow")?
                / chunk.moves.len()
                == 6,
            "native chunk stride mismatch"
        );
        ensure!(
            chunks.insert(idx, chunk).is_none(),
            "duplicate accepted chunk index"
        );
    }
    let chunks: Vec<_> = chunks.into_values().collect();
    ensure!(chunks[0].offset == 0, "missing first chunk");
    let mut retained = Vec::new();
    let mut front = 0usize;
    let mut seq = String::new();
    let mut qual = String::new();
    let mut mv = Vec::new();
    for (i, c) in chunks.iter().enumerate() {
        let (end, nextfront) = if let Some(next) = chunks.get(i + 1) {
            ensure!(next.offset > c.offset, "chunk offsets order");
            let overlap = c
                .offset
                .checked_add(c.raw)
                .and_then(|e| e.checked_sub(next.offset))
                .context("negative/overflow overlap")?;
            ensure!(overlap % 6 == 0, "non-stride overlap");
            let o = overlap / 6;
            let rear = o / 2;
            (
                c.moves
                    .len()
                    .checked_sub(rear)
                    .context("overlap exceeds chunk")?,
                o - rear,
            )
        } else if count == 1 || variable {
            (signal.min(c.raw).div_ceil(6), 0)
        } else {
            (c.moves.len(), 0)
        };
        ensure!(
            front <= end && end <= c.moves.len(),
            "invalid native retained range"
        );
        let a = c.moves[..front].iter().map(|&x| x as usize).sum::<usize>();
        let b = a + c.moves[front..end]
            .iter()
            .map(|&x| x as usize)
            .sum::<usize>();
        let p = seq.len();
        seq.push_str(&c.seq[a..b]);
        qual.push_str(&c.qual[a..b]);
        mv.extend_from_slice(&c.moves[front..end]);
        retained.push(Retained {
            chunk: c.clone(),
            t_start: front,
            t_end: end,
            chunk_base_start: a,
            parent_base_start: p,
            parent_base_end: seq.len(),
        });
        front = nextfront;
    }
    if mv.len() > signal / 6 {
        let last = mv.pop().context("empty partial overhang")?;
        if last == 1 {
            seq.pop();
            qual.pop();
        }
        let r = retained.last_mut().context("no retained chunk")?;
        r.t_end -= 1;
        r.parent_base_end = seq.len();
    }
    let (pseq, pqual, pmv) = validate_seq(&parent)?;
    ensure!(
        seq == pseq && qual == pqual && mv == pmv,
        "native stitch reconstruction mismatch"
    );
    ensure!(
        seq == sam.seq && qual == sam.qual,
        "export/native primary parent SEQ/Q mismatch"
    );
    Ok(Export { retained })
}
