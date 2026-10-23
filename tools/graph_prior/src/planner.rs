use crate::native::{self, Export, Sam};
use anyhow::{ensure, Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Write,
    path::Path,
};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Window {
    pub schema: String,
    pub query_index: usize,
    pub read_id: String,
    pub contig: String,
    pub ref_start: usize,
    pub ref_end: usize,
    pub core_start: usize,
    pub core_end: usize,
    pub read_start: usize,
    pub read_end: usize,
    pub chunk_index: usize,
    pub chunk_start: usize,
    pub chunk_end: usize,
    pub t_start: usize,
    pub t_end: usize,
    pub reverse: bool,
    pub stock: String,
    pub context: String,
    pub score_file: String,
}
#[derive(Default, Serialize)]
pub struct Diagnostics {
    pub parents: usize,
    pub proposals: usize,
    pub frozen_before_runtime: usize,
    pub windows: usize,
    pub exclusions: Vec<serde_json::Value>,
}
pub fn reason(d: &mut Diagnostics, id: &str, locus: Option<usize>, why: impl ToString) {
    d.exclusions
        .push(serde_json::json!({"read_id":id,"core_start":locus,"reason":why.to_string()}));
}
struct Alignment {
    map: BTreeMap<usize, usize>,
    centers: BTreeSet<usize>,
}
fn alignment(s: &Sam) -> Result<Alignment> {
    let ops = native::cigar(&s.cigar)?;
    let mut r = s.pos;
    let mut q = 0usize;
    let mut map = BTreeMap::new();
    let mut centers = BTreeSet::new();
    for (n, op) in ops {
        ensure!(n <= 10_000_000, "CIGAR operation cap");
        match op {
            b'=' | b'X' => {
                for _ in 0..n {
                    map.insert(r, q);
                    if op == b'X' {
                        centers.insert(r);
                    }
                    r += 1;
                    q += 1;
                }
            }
            b'I' => {
                centers.insert(r);
                q += n;
            }
            b'D' => {
                for _ in 0..n {
                    centers.insert(r);
                    r += 1;
                }
            }
            b'S' => q += n,
            b'P' => {}
            _ => anyhow::bail!("EQX without hardclips/skips required"),
        }
    }
    ensure!(q == s.aligned.len(), "CIGAR/SEQ length mismatch");
    Ok(Alignment { map, centers })
}
fn proposal(s: &Sam, al: &Alignment, rf: &[u8], center: usize) -> Result<Window> {
    let core_start = center.checked_sub(10).context("core before reference")?;
    let core_end = core_start.checked_add(21).context("core overflow")?;
    let start = core_start
        .checked_sub(10)
        .context("left flank before reference")?;
    let end = core_end + 10;
    ensure!(end <= rf.len(), "right flank outside reference");
    let qs = *al.map.get(&start).context("left anchor absent")?;
    let qe = al.map.get(&(end - 1)).context("right anchor absent")? + 1;
    ensure!(
        qe <= s.aligned.len() && qe >= qs + 20,
        "stock window bounds"
    );
    let core_len = qe - qs - 20;
    ensure!(
        core_len <= 32 && core_len.abs_diff(21) <= 5,
        "stock core length delta"
    );
    for i in 0..10 {
        ensure!(
            al.map.get(&(start + i)) == Some(&(qs + i))
                && al.map.get(&(end - 10 + i)) == Some(&(qe - 10 + i)),
            "gapped anchor"
        );
    }
    ensure!(
        s.aligned.as_bytes()[qs..qs + 10] == rf[start..start + 10]
            && s.aligned.as_bytes()[qe - 10..qe] == rf[end - 10..end],
        "inexact anchor"
    );
    ensure!(
        rf[start..end].iter().all(|b| accuracy::canonical(*b)),
        "noncanonical reference window"
    );
    let (a, b) = if s.reverse() {
        (s.seq.len() - qe, s.seq.len() - qs)
    } else {
        (qs, qe)
    };
    let stock = s.seq[a..b].to_owned();
    ensure!(stock.bytes().all(accuracy::canonical), "noncanonical stock");
    Ok(Window {
        schema: "graph-prior-window/1".to_owned(),
        query_index: 0,
        read_id: s.id.clone(),
        contig: s.contig.clone(),
        ref_start: start,
        ref_end: end,
        core_start,
        core_end,
        read_start: a,
        read_end: b,
        chunk_index: 0,
        chunk_start: 0,
        chunk_end: 0,
        t_start: 0,
        t_end: 0,
        reverse: s.reverse(),
        stock,
        context: String::new(),
        score_file: String::new(),
    })
}
pub fn attach(w: &mut Window, e: &Export) -> Result<()> {
    let r = e
        .retained
        .iter()
        .find(|r| w.read_start >= r.parent_base_start + 25 && w.read_end + 25 <= r.parent_base_end)
        .context("window lacks 25 retained bases at both chunk edges")?;
    let a = r.chunk_base_start + w.read_start - r.parent_base_start;
    let b = a + w.stock.len();
    ensure!(
        a >= 4 && r.chunk.seq[a..b] == w.stock,
        "chunk stock/context mismatch"
    );
    let mut emissions = Vec::new();
    for (t, &m) in r.chunk.moves.iter().enumerate() {
        if m == 1 {
            emissions.push(t);
        }
    }
    let ta = *emissions.get(a).context("missing first emission")?;
    let tb = emissions.get(b).copied().unwrap_or(r.t_end);
    ensure!(
        ta >= r.t_start && tb <= r.t_end && ta < tb && tb - ta <= 256,
        "time interval invalid or over cap"
    );
    w.chunk_index = r.chunk.index;
    w.chunk_start = a;
    w.chunk_end = b;
    w.t_start = ta;
    w.t_end = tb;
    w.context = r.chunk.seq[a - 4..a].to_owned();
    w.score_file = r.chunk.score_file.clone();
    Ok(())
}
pub fn plan(
    reference: &Path,
    sam_path: &Path,
    export: &Path,
    parents: &Path,
    out: &Path,
    namespace: &str,
) -> Result<()> {
    let ids = native::parents(parents)?;
    let sams = native::sam(sam_path, &ids)?;
    let rf = accuracy::Reference::load(reference)?;
    let inv = native::inventory(export, &ids)?;
    let mut d = Diagnostics {
        parents: ids.len(),
        ..Default::default()
    };
    let mut proposals = Vec::new();
    for id in &ids {
        let s = &sams[id];
        if s.flag & 4 != 0 || !accuracy::autosome(&s.contig) || !(30..=254).contains(&s.mapq) {
            reason(&mut d, id, None, "primary alignment eligibility");
            continue;
        }
        let al = match alignment(s) {
            Ok(a) => a,
            Err(e) => {
                reason(&mut d, id, None, e);
                continue;
            }
        };
        let seq = rf
            .seq
            .get(&s.contig)
            .context("SAM contig missing from reference")?;
        for center in &al.centers {
            d.proposals += 1;
            match proposal(s, &al, seq, *center) {
                Ok(w) => {
                    let hash = Sha256::digest(
                        format!("{namespace}/{}/{}/{}", id, w.contig, w.core_start).as_bytes(),
                    );
                    proposals.push((hash.to_vec(), w));
                }
                Err(e) => reason(&mut d, id, Some(*center), e),
            }
        }
    }
    proposals.sort_by(|a, b| {
        a.0.cmp(&b.0)
            .then(a.1.read_id.cmp(&b.1.read_id))
            .then(a.1.core_start.cmp(&b.1.core_start))
    });
    let mut frozen: Vec<Window> = Vec::new();
    for (_, w) in proposals {
        if frozen.iter().any(|p| {
            p.read_id == w.read_id && p.read_start < w.read_end && w.read_start < p.read_end
        }) {
            reason(
                &mut d,
                &w.read_id,
                Some(w.core_start),
                "overlapping frozen window",
            );
            continue;
        }
        if frozen.len() == 512 {
            reason(&mut d, &w.read_id, Some(w.core_start), "frozen window cap");
            continue;
        }
        frozen.push(w);
    }
    d.frozen_before_runtime = frozen.len();
    let mut valid = BTreeMap::new();
    for id in &ids {
        let entries = inv.get(id).context("inventory absent")?;
        match native::reconstruct(export, &sams[id], entries) {
            Ok(e) => {
                valid.insert(id.clone(), e);
            }
            Err(e) => reason(&mut d, id, None, e),
        }
    }
    let mut windows = Vec::new();
    for mut w in frozen {
        if let Some(e) = valid.get(&w.read_id) {
            match attach(&mut w, e) {
                Ok(()) => {
                    w.query_index = windows.len();
                    windows.push(w);
                }
                Err(e) => reason(&mut d, &w.read_id, Some(w.core_start), e),
            }
        } else {
            reason(
                &mut d,
                &w.read_id,
                Some(w.core_start),
                "parent export custody unavailable",
            );
        }
    }
    d.windows = windows.len();
    fs::create_dir(out)?;
    let mut wf = fs::File::create(out.join("windows.jsonl"))?;
    let mut qf = fs::File::create(out.join("queries.tsv"))?;
    for w in windows {
        serde_json::to_writer(&mut wf, &w)?;
        writeln!(wf)?;
        writeln!(qf, "GRCh38\t{}\t{}\t{}", w.contig, w.ref_start, w.ref_end)?;
    }
    fs::write(out.join("diagnostics.json"), serde_json::to_vec_pretty(&d)?)?;
    Ok(())
}
pub fn load_windows(path: &Path) -> Result<Vec<Window>> {
    let mut out = Vec::new();
    for line in fs::read_to_string(path)?.lines() {
        if !line.is_empty() {
            let w: Window = serde_json::from_str(line)?;
            ensure!(
                w.schema == "graph-prior-window/1" && w.query_index == out.len(),
                "window schema/index"
            );
            out.push(w);
        }
    }
    ensure!(out.len() <= 512, "window cap");
    Ok(out)
}
pub fn validate_window(w: &Window, s: &Sam, rf: &[u8], e: &Export) -> Result<()> {
    ensure!(
        s.flag & 4 == 0 && accuracy::autosome(&s.contig) && (30..=254).contains(&s.mapq),
        "window primary eligibility"
    );
    let al = alignment(s)?;
    let center = w
        .core_start
        .checked_add(10)
        .context("window core overflow")?;
    ensure!(
        al.centers.contains(&center),
        "window not a native X/I/D proposal"
    );
    let mut expected = proposal(s, &al, rf, center)?;
    attach(&mut expected, e)?;
    expected.query_index = w.query_index;
    ensure!(
        w == &expected,
        "saved window differs from native-derived window"
    );
    Ok(())
}
