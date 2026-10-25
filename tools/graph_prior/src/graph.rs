use crate::{native, planner::Window};
use anyhow::{ensure, Context, Result};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};
#[derive(Debug, Deserialize)]
pub struct Query {
    pub sample: String,
    pub contig: String,
    pub start: usize,
    pub end: usize,
}
#[derive(Debug, Deserialize)]
pub struct Reference {
    pub start: usize,
    pub end: usize,
    pub sequence: String,
}
#[derive(Debug, Deserialize)]
pub struct Walk {
    pub is_reference: bool,
    pub cigar: String,
    pub sequence: String,
    pub both_anchors: bool,
}
#[derive(Debug, Deserialize)]
pub struct Interval {
    pub schema: String,
    pub query_index: usize,
    pub query: Query,
    pub reference: Reference,
    pub walks: Vec<Walk>,
}
pub fn load(path: &Path) -> Result<BTreeMap<usize, Interval>> {
    let mut out = BTreeMap::new();
    for line in fs::read_to_string(path)?.lines().filter(|l| !l.is_empty()) {
        let g: Interval = serde_json::from_str(line)?;
        ensure!(g.schema == "hprc-local-paths/1", "graph schema");
        ensure!(
            out.insert(g.query_index, g).is_none(),
            "duplicate graph query index"
        );
    }
    Ok(out)
}
fn trim(walk: &Walk, reference: &Reference, start: usize, end: usize) -> Result<String> {
    ensure!(
        walk.sequence.is_ascii() && walk.sequence.bytes().all(accuracy::canonical),
        "noncanonical graph traversal"
    );
    let mut r = reference.start;
    let mut q = 0usize;
    let mut map = BTreeMap::new();
    for (n, op) in native::cigar(&walk.cigar)? {
        ensure!(
            n <= reference.sequence.len() + walk.sequence.len(),
            "graph CIGAR operation bounds"
        );
        match op {
            b'M' | b'=' | b'X' => {
                for _ in 0..n {
                    map.insert(r, q);
                    r += 1;
                    q += 1;
                }
            }
            b'I' => q += n,
            b'D' => r += n,
            _ => anyhow::bail!("unsupported graph CIGAR"),
        }
    }
    ensure!(
        r == reference.end && q == walk.sequence.len(),
        "graph CIGAR span mismatch"
    );
    let a = *map.get(&start).context("graph left anchor absent")?;
    let b = map.get(&(end - 1)).context("graph right anchor absent")? + 1;
    ensure!(b >= a + 20 && b <= q, "graph core bounds");
    for i in 0..10 {
        ensure!(
            map.get(&(start + i)) == Some(&(a + i))
                && map.get(&(end - 10 + i)) == Some(&(b - 10 + i)),
            "gapped graph anchor"
        );
    }
    Ok(walk.sequence[a..b].to_owned())
}
pub fn panel(w: &Window, g: &Interval, rf: &[u8]) -> Result<BTreeSet<String>> {
    ensure!(
        g.query_index == w.query_index
            && g.query.sample == "GRCh38"
            && g.query.contig == w.contig
            && g.query.start == w.ref_start
            && g.query.end == w.ref_end,
        "graph query/window mismatch"
    );
    let r = &g.reference;
    ensure!(
        r.start <= w.ref_start
            && r.end >= w.ref_end
            && r.end <= rf.len()
            && r.start < r.end
            && r.sequence.as_bytes() == &rf[r.start..r.end],
        "full extracted reference/FASTA mismatch"
    );
    ensure!(
        g.walks.iter().any(|p| p.is_reference
            && p.both_anchors
            && p.sequence == r.sequence
            && p.cigar == format!("{}M", r.sequence.len())),
        "complete exact reference traversal absent"
    );
    let forward_stock = if w.reverse {
        native::revcomp(&w.stock)?
    } else {
        w.stock.clone()
    };
    let mut panel = BTreeSet::new();
    for p in &g.walks {
        if !p.both_anchors {
            continue;
        }
        // Every complete traversal must fit; dropping one would change panel support.
        let seq = trim(p, r, w.ref_start, w.ref_end)?;
        ensure!(
            seq.len() >= 20 && seq.len() - 20 <= 32 && (seq.len() - 20).abs_diff(21) <= 5,
            "complete graph traversal core outside bounds"
        );
        ensure!(
            seq.as_bytes()[..10] == forward_stock.as_bytes()[..10]
                && seq.as_bytes()[seq.len() - 10..]
                    == forward_stock.as_bytes()[forward_stock.len() - 10..],
            "complete graph traversal lacks exact stock anchors"
        );
        panel.insert(if w.reverse {
            native::revcomp(&seq)?
        } else {
            seq
        });
    }
    ensure!(!panel.is_empty(), "no complete graph context");
    ensure!(
        panel.len() <= 16,
        "more than 16 complete distinct panel strings"
    );
    Ok(panel)
}
