use crate::decision::{Hypothesis, Policy, Prior};
use anyhow::{bail, ensure, Context, Result};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{BufRead, Read},
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Pin {
    pub path: PathBuf,
    pub size: u64,
    pub sha256: String,
}

pub fn pin(path: &Path) -> Result<Pin> {
    let path = fs::canonicalize(path)?;
    let mut file = fs::File::open(&path)?;
    let mut hash = Sha256::new();
    let mut size = 0;
    let mut buffer = [0u8; 65536];
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        hash.update(&buffer[..n]);
        size += n as u64;
    }
    Ok(Pin {
        path,
        size,
        sha256: format!("{:x}", hash.finalize()),
    })
}

impl Pin {
    fn verify(&self) -> Result<()> {
        ensure!(self.path.is_absolute(), "pin paths must be absolute");
        let actual = pin(&self.path).with_context(|| format!("pin {}", self.path.display()))?;
        ensure!(
            actual.size == self.size && actual.sha256 == self.sha256,
            "size/hash mismatch for {}",
            self.path.display()
        );
        Ok(())
    }
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Pins {
    pub parents: Pin,
    pub native_sam: Pin,
    pub windows: Pin,
    pub decisions: Pin,
    pub graph_walks: Pin,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub producer_receipt: Option<Pin>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Cohort {
    pub schema: String,
    pub role: String,
    pub pins: Pins,
    #[serde(default)]
    pub historical_sams: BTreeMap<String, Pin>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub producer_receipt: Option<Pin>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Protocol {
    pub schema: String,
    pub policies: Vec<Policy>,
    pub frontier: Option<Frontier>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Frontier {
    pub enabled: bool,
    pub priors: Vec<Prior>,
    pub margin: f64,
    pub neural_deficit: Option<f64>,
}

#[derive(Debug, Deserialize)]
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
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Query {
    sample: String,
    contig: String,
    start: usize,
    end: usize,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Reference {
    start: usize,
    end: usize,
    sequence: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Walk {
    is_reference: bool,
    #[serde(rename = "copy_count")]
    _copy_count: serde_json::Value,
    cigar: String,
    sequence: String,
    both_anchors: bool,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Graph {
    schema: String,
    query_index: usize,
    query: Query,
    reference: Reference,
    #[serde(rename = "boundary_nodes")]
    _boundary_nodes: serde_json::Value,
    walks: Vec<Walk>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SavedHypothesis {
    sequence: String,
    graph_presence: bool,
    likelihood: Option<f64>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HistoricalArm {
    pub arm: String,
    pub lambda: f64,
    pub winner: String,
    pub winner_likelihood: f64,
    pub winner_graph_presence: bool,
    pub objective_margin: f64,
    pub edited: bool,
    pub edited_quality: String,
    pub edit_start: usize,
    pub edit_end: usize,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SavedDecision {
    query_index: usize,
    read_id: String,
    status: String,
    stock_likelihood: Option<f64>,
    score_sha256: Option<String>,
    hypotheses: Option<Vec<SavedHypothesis>>,
    arms: Option<Vec<HistoricalArm>>,
    reason: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Parent {
    pub seq: String,
    pub qual: String,
    pub reverse: bool,
}
pub struct Evidence {
    pub window: Window,
    pub hypotheses: Vec<Hypothesis>,
    pub historical: Vec<HistoricalArm>,
    pub exclusion: Option<String>,
}
pub struct Admitted {
    pub cohort: Cohort,
    pub ids: Vec<String>,
    pub parents: BTreeMap<String, Parent>,
    pub windows: Vec<Evidence>,
    pub historical: BTreeMap<String, BTreeMap<String, Parent>>,
}

pub fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T> {
    serde_json::from_slice(&fs::read(path)?).with_context(|| format!("JSON {}", path.display()))
}
fn read_lines<T: DeserializeOwned>(path: &Path) -> Result<Vec<T>> {
    fs::read_to_string(path)?
        .lines()
        .enumerate()
        .map(|(i, l)| {
            serde_json::from_str(l).with_context(|| format!("{} line {}", path.display(), i + 1))
        })
        .collect()
}
fn dna(s: &str) -> Result<()> {
    ensure!(
        !s.is_empty() && s.bytes().all(|b| b"ACGT".contains(&b)),
        "noncanonical DNA"
    );
    Ok(())
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
                _ => bail!("invalid SAM DNA"),
            })
        })
        .collect()
}

pub fn read_sam(path: &Path, ids: &[String]) -> Result<BTreeMap<String, Parent>> {
    let wanted: BTreeSet<_> = ids.iter().map(String::as_str).collect();
    let mut out = BTreeMap::new();
    for line in std::io::BufReader::new(fs::File::open(path)?).lines() {
        let line = line?;
        if line.starts_with('@') {
            continue;
        }
        let f: Vec<_> = line.split('\t').collect();
        ensure!(f.len() >= 11, "malformed SAM");
        ensure!(wanted.contains(f[0]), "foreign SAM parent {}", f[0]);
        let flag: u16 = f[1].parse()?;
        if flag & (256 | 2048) != 0 {
            continue;
        }
        ensure!(
            f[9] != "*"
                && f[9].is_ascii()
                && !f[9].is_empty()
                && f[9].len() == f[10].len()
                && f[10].bytes().all(|b| (33..=126).contains(&b)),
            "full SAM SEQ/Q required"
        );
        let reverse = flag & 16 != 0;
        let seq = f[9].to_ascii_uppercase();
        let parent = Parent {
            seq: if reverse {
                revcomp(&seq)?
            } else {
                revcomp(&revcomp(&seq)?)?
            },
            qual: if reverse {
                f[10].chars().rev().collect()
            } else {
                f[10].to_owned()
            },
            reverse,
        };
        ensure!(
            out.insert(f[0].to_owned(), parent).is_none(),
            "duplicate SAM primary"
        );
    }
    ensure!(out.len() == ids.len(), "missing SAM parent");
    Ok(out)
}

fn linear(w: &Window, g: &Graph) -> Result<String> {
    ensure!(
        g.schema == "hprc-local-paths/1"
            && g.query_index == w.query_index
            && g.query.sample == "GRCh38"
            && g.query.contig == w.contig
            && g.query.start == w.ref_start
            && g.query.end == w.ref_end,
        "graph/window mismatch"
    );
    let r = &g.reference;
    dna(&r.sequence)?;
    ensure!(
        r.start <= w.ref_start
            && w.ref_start < w.ref_end
            && w.ref_end <= r.end
            && r.end - r.start == r.sequence.len(),
        "expanded graph reference span mismatch"
    );
    ensure!(
        g.walks.iter().any(|p| p.is_reference
            && p.both_anchors
            && p.sequence == r.sequence
            && p.cigar == format!("{}M", r.sequence.len())),
        "exact expanded reference traversal absent"
    );
    let seq = &r.sequence[w.ref_start - r.start..w.ref_end - r.start];
    if w.reverse {
        revcomp(seq)
    } else {
        Ok(seq.to_owned())
    }
}

pub fn admit(path: &Path) -> Result<Admitted> {
    let cohort: Cohort = read_json(path)?;
    ensure!(
        cohort.schema == "graph-frontier-cohort/1"
            && ["development", "validation"].contains(&cohort.role.as_str()),
        "cohort schema/role"
    );
    let p = &cohort.pins;
    for pin in [
        &p.parents,
        &p.native_sam,
        &p.windows,
        &p.decisions,
        &p.graph_walks,
    ]
    .into_iter()
    .chain(p.producer_receipt.iter())
    .chain(cohort.producer_receipt.iter())
    .chain(cohort.historical_sams.values())
    {
        pin.verify()?;
    }
    for receipt in p
        .producer_receipt
        .iter()
        .chain(cohort.producer_receipt.iter())
    {
        let value: serde_json::Value = read_json(&receipt.path)?;
        ensure!(
            value["status"] == "finished" && value["exit"].as_i64() == Some(0),
            "producer receipt is not a successful finished command"
        );
    }
    let ids: Vec<_> = fs::read_to_string(&p.parents.path)?
        .lines()
        .map(str::to_owned)
        .collect();
    ensure!(
        !ids.is_empty() && ids.len() <= 64,
        "parent count must be 1..64"
    );
    ensure!(
        ids.iter().all(|id| !id.is_empty()
            && id.len() <= 128
            && id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-')),
        "malformed parent ID"
    );
    ensure!(
        ids.iter().collect::<BTreeSet<_>>().len() == ids.len(),
        "duplicate parent UUID"
    );
    let parents = read_sam(&p.native_sam.path, &ids)?;
    let ws: Vec<Window> = read_lines(&p.windows.path)?;
    let gs: Vec<Graph> = read_lines(&p.graph_walks.path)?;
    let ds: Vec<SavedDecision> = read_lines(&p.decisions.path)?;
    let mut graphs = BTreeMap::new();
    for g in gs {
        let index = g.query_index;
        ensure!(graphs.insert(index, g).is_none(), "duplicate graph query");
    }
    let mut decisions = BTreeMap::new();
    for d in ds {
        let index = d.query_index;
        ensure!(
            decisions.insert(index, d).is_none(),
            "duplicate decision query"
        );
    }
    ensure!(
        ws.len() == graphs.len() && ws.len() == decisions.len(),
        "missing/foreign graph or decision rows"
    );
    let mut seen = BTreeSet::new();
    let mut intervals: BTreeMap<String, Vec<(usize, usize)>> = BTreeMap::new();
    let mut tensor_hashes = BTreeMap::new();
    let mut windows = Vec::new();
    for w in ws {
        ensure!(seen.insert(w.query_index), "duplicate window query");
        ensure!(w.schema == "graph-prior-window/1", "window schema");
        let parent = parents.get(&w.read_id).context("foreign window parent")?;
        dna(&w.stock)?;
        dna(&w.context)?;
        ensure!(
            w.context.len() == 4
                && w.read_start <= w.read_end
                && w.read_end <= parent.seq.len()
                && w.stock == parent.seq[w.read_start..w.read_end]
                && w.stock.len() >= 20,
            "window/native sequence mismatch"
        );
        ensure!(
            w.ref_start < w.ref_end
                && w.ref_end - w.ref_start >= 20
                && w.core_start.checked_sub(w.ref_start) == Some(10)
                && w.core_end == w.ref_end - 10
                && w.chunk_start < w.chunk_end
                && w.chunk_end - w.chunk_start == w.stock.len()
                && w.t_start < w.t_end
                && w.t_end - w.t_start <= 256
                && !w.score_file.is_empty(),
            "invalid window coordinates"
        );
        let ranges = intervals.entry(w.read_id.clone()).or_default();
        ensure!(
            ranges
                .iter()
                .all(|&(a, b)| b <= w.read_start || w.read_end <= a),
            "overlapping windows"
        );
        ranges.push((w.read_start, w.read_end));
        let g = graphs
            .remove(&w.query_index)
            .context("missing graph query")?;
        ensure!(
            g.query_index == w.query_index
                && g.query.sample == "GRCh38"
                && g.query.contig == w.contig
                && g.query.start == w.ref_start
                && g.query.end == w.ref_end
                && g.schema == "hprc-local-paths/1",
            "graph/window join mismatch"
        );
        let d = decisions
            .remove(&w.query_index)
            .context("missing decision query")?;
        ensure!(d.read_id == w.read_id, "decision UUID/window mismatch");
        if d.status == "excluded" {
            ensure!(
                d.hypotheses.is_none()
                    && d.arms.is_none()
                    && d.stock_likelihood.is_none()
                    && d.score_sha256.is_none()
                    && d.reason.is_some(),
                "malformed excluded decision"
            );
            windows.push(Evidence {
                window: w,
                hypotheses: Vec::new(),
                historical: Vec::new(),
                exclusion: d.reason,
            });
            continue;
        }
        ensure!(
            d.status == "scored" && d.reason.is_none(),
            "unknown/malformed decision status"
        );
        let linear = linear(&w, &g)?;
        let score_hash = d.score_sha256.context("missing tensor hash")?;
        ensure!(
            score_hash.len() == 64
                && score_hash
                    .bytes()
                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
            "invalid tensor hash"
        );
        if let Some(previous) = tensor_hashes.insert(w.score_file.clone(), score_hash.clone()) {
            ensure!(
                previous == score_hash,
                "conflicting hashes for the same tensor"
            );
        }
        let mut hseen = BTreeSet::new();
        let mut hypotheses = Vec::new();
        for h in d.hypotheses.context("missing hypotheses")? {
            dna(&h.sequence)?;
            ensure!(hseen.insert(h.sequence.clone()), "duplicate hypothesis");
            ensure!(
                h.sequence.len() >= 20
                    && h.sequence[..10] == w.stock[..10]
                    && h.sequence[h.sequence.len() - 10..] == w.stock[w.stock.len() - 10..],
                "hypothesis anchors differ"
            );
            ensure!(
                h.likelihood.is_none_or(f64::is_finite),
                "nonfinite likelihood"
            );
            hypotheses.push(Hypothesis {
                linear: h.sequence == linear,
                sequence: h.sequence,
                panel: h.graph_presence,
                likelihood: h.likelihood.unwrap_or(f64::NEG_INFINITY),
            });
        }
        ensure!(
            hypotheses.iter().any(|h| h.linear && h.panel),
            "linear-reference hypothesis absent or not panel"
        );
        let native = hypotheses
            .iter()
            .find(|h| h.sequence == w.stock)
            .context("native hypothesis absent")?;
        ensure!(
            native.likelihood.is_finite() && d.stock_likelihood == Some(native.likelihood),
            "stock likelihood mismatch/impossible"
        );
        windows.push(Evidence {
            window: w,
            hypotheses,
            historical: d.arms.context("missing historical arms")?,
            exclusion: None,
        });
    }
    ensure!(
        graphs.is_empty() && decisions.is_empty(),
        "foreign query indices"
    );
    windows.sort_by_key(|e| e.window.query_index);
    let historical = cohort
        .historical_sams
        .iter()
        .map(|(name, p)| Ok((name.clone(), read_sam(&p.path, &ids)?)))
        .collect::<Result<_>>()?;
    Ok(Admitted {
        cohort,
        ids,
        parents,
        windows,
        historical,
    })
}
