use super::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{BufWriter, Write};

fn revcomp(s: &str) -> Result<String> {
    s.bytes()
        .rev()
        .map(|b| {
            Ok(match b {
                b'A' => 'T',
                b'C' => 'G',
                b'G' => 'C',
                b'T' => 'A',
                _ => anyhow::bail!("noncanonical DNA"),
            })
        })
        .collect()
}
fn orientation(s: &str, reverse: bool) -> Result<String> {
    if reverse {
        revcomp(s)
    } else {
        Ok(s.into())
    }
}

#[derive(Debug, PartialEq, Eq)]
enum Support {
    Alt,
    Other,
    Ambiguous,
}
fn projection(
    query: &str,
    reference: &str,
    start: usize,
    end: usize,
    alt: &str,
) -> Result<Support> {
    ensure!(
        query.is_ascii() && reference.is_ascii() && start < end && end <= reference.len(),
        "projection bounds"
    );
    if !query.contains(alt) {
        return Ok(Support::Other);
    }
    let (r, q) = (reference.as_bytes(), query.as_bytes());
    let (m, n) = (r.len(), q.len());
    let ix = |i: usize, j: usize| i * (n + 1) + j;
    let mut f = vec![0usize; (m + 1) * (n + 1)];
    let mut b = f.clone();
    for i in 0..=m {
        f[ix(i, 0)] = i;
        b[ix(i, n)] = m - i;
    }
    for j in 0..=n {
        f[ix(0, j)] = j;
        b[ix(m, j)] = n - j;
    }
    for i in 1..=m {
        for j in 1..=n {
            f[ix(i, j)] = (f[ix(i - 1, j)] + 1)
                .min(f[ix(i, j - 1)] + 1)
                .min(f[ix(i - 1, j - 1)] + usize::from(r[i - 1] != q[j - 1]));
        }
    }
    for i in (0..m).rev() {
        for j in (0..n).rev() {
            b[ix(i, j)] = (b[ix(i + 1, j)] + 1)
                .min(b[ix(i, j + 1)] + 1)
                .min(b[ix(i + 1, j + 1)] + usize::from(r[i] != q[j]));
        }
    }
    let optimal = f[ix(m, n)];
    let cuts = |i| {
        (0..=n)
            .filter(|&j| f[ix(i, j)] + b[ix(i, j)] == optimal)
            .collect::<Vec<_>>()
    };
    let (a, z) = (cuts(start), cuts(end));
    if a.len() != 1 || z.len() != 1 {
        return Ok(Support::Ambiguous);
    }
    ensure!(a[0] <= z[0], "nonmonotonic optimal projection");
    Ok(if &query[a[0]..z[0]] == alt {
        Support::Alt
    } else {
        Support::Other
    })
}
fn trim(walk: &Value, g: &Value, w: &Window) -> Result<String> {
    let seq = walk["sequence"].as_str().context("walk DNA")?;
    let mut rp = g["reference"]["start"].as_u64().context("graph start")? as usize;
    let mut qp = 0usize;
    let mut count = 0usize;
    let mut map = BTreeMap::new();
    for b in walk["cigar"].as_str().context("walk cigar")?.bytes() {
        if b.is_ascii_digit() {
            count = count
                .checked_mul(10)
                .and_then(|v| v.checked_add((b - b'0') as usize))
                .context("cigar overflow")?;
            continue;
        }
        ensure!(count > 0, "zero cigar");
        match b {
            b'M' | b'=' | b'X' => {
                for _ in 0..count {
                    map.insert(rp, qp);
                    rp += 1;
                    qp += 1;
                }
            }
            b'I' => qp += count,
            b'D' => rp += count,
            _ => anyhow::bail!("unsupported graph cigar"),
        };
        count = 0;
    }
    ensure!(
        count == 0
            && qp == seq.len()
            && rp == g["reference"]["end"].as_u64().context("graph end")? as usize,
        "graph span corruption"
    );
    let a = *map.get(&w.ref_start).context("left graph anchor")?;
    let z = map.get(&(w.ref_end - 1)).context("right graph anchor")? + 1;
    ensure!(z >= a + 20 && z <= seq.len(), "graph trim bounds");
    for k in 0..10 {
        ensure!(
            map.get(&(w.ref_start + k)) == Some(&(a + k))
                && map.get(&(w.ref_end - 10 + k)) == Some(&(z - 10 + k)),
            "graph gapped anchors"
        );
    }
    orientation(&seq[a..z], w.reverse)
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct SavedHypothesis {
    sequence: String,
    graph_presence: bool,
    likelihood: Option<f64>,
}
#[derive(Debug, Deserialize)]
struct SavedRow {
    status: String,
    query_index: usize,
    read_id: String,
    hypotheses: Option<Vec<SavedHypothesis>>,
    stock_likelihood: Option<f64>,
    score_sha256: Option<String>,
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct InferenceHypothesis {
    sequence: String,
    likelihood: Option<f64>,
    ordinary: bool,
    withheld: bool,
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct InferenceCase {
    schema: String,
    case_id: String,
    stock: String,
    hypotheses: Vec<InferenceHypothesis>,
    #[serde(default)]
    ordinary_flank: BTreeMap<String, f64>,
    #[serde(default)]
    withheld_flank: BTreeMap<String, f64>,
}
fn write_line(w: &mut impl Write, v: &impl Serialize) -> Result<()> {
    serde_json::to_writer(&mut *w, v)?;
    w.write_all(b"\n")?;
    Ok(())
}

pub(super) fn build(
    root: &Path,
    out: &Path,
    windows: &[Window],
    variants: &[Variant],
    observations: &BTreeMap<(String, String), String>,
    extra: bool,
) -> Result<()> {
    let pilot = root.join("results/graph-prior/pilot-v1/development");
    let graphs_path = if extra {
        Path::new("/home/jake/Projects/nanopore_basecaller-private/results/private-allele/additional-graph-v1/graph/walks.jsonl").to_owned()
    } else {
        pilot.join("graph/walks.jsonl")
    };
    let graphs: BTreeMap<usize, Value> = load_jsonl::<Value>(&graphs_path)?
        .into_iter()
        .map(|v| {
            Ok((
                v["query_index"].as_u64().context("graph query")? as usize,
                v,
            ))
        })
        .collect::<Result<_>>()?;
    let plans: BTreeMap<usize, Value> = if extra {
        windows.iter().map(|w|(w.query_index,json!({"status":"abstain-binary","reason":"new diagnostic frame has no qualified disjoint flank plans"}))).collect()
    } else {
        load_jsonl::<Value>(Path::new("/home/jake/Projects/nanopore_basecaller-flank/results/flank-prior/20261023T165826Z-eligibility/plans.jsonl"))?.into_iter().map(|p|Ok((p["query_index"].as_u64().context("flank query")? as usize,p))).collect::<Result<_>>()?
    };
    let mut cases = BufWriter::new(File::create(out.join("cases.jsonl"))?);
    let mut inference = BufWriter::new(File::create(out.join("inference.jsonl"))?);
    let mut exclusions = Vec::new();
    let mut eligible = 0;
    let mut original_h: BTreeMap<usize, BTreeMap<String, (bool, Option<f64>)>> = BTreeMap::new();
    let datasets = if extra {
        vec![("additional_original",Path::new("/home/jake/Projects/nanopore_basecaller-private/results/private-allele/additional-original-score-v2/candidates/decisions.jsonl").to_owned())]
    } else {
        vec![
            ("original", pilot.join("candidates/decisions.jsonl")),
            (
                "expanded",
                root.join("results/reference-frontier/catalogue-v1/full-roundtrip/decisions.jsonl"),
            ),
        ]
    };
    for (dataset, path) in datasets {
        let mut seen = BTreeSet::new();
        for line in BufReader::new(File::open(&path)?).lines() {
            let line = line?;
            let row: SavedRow = serde_json::from_str(&line)?;
            ensure!(seen.insert(row.query_index), "duplicate score row");
            let w = windows
                .iter()
                .find(|w| w.query_index == row.query_index)
                .context("foreign score query")?;
            ensure!(row.read_id == w.read_id, "score parent mismatch");
            if row.status != "scored" {
                ensure!(
                    row.status == "excluded" && row.hypotheses.is_none(),
                    "invalid excluded score"
                );
                continue;
            }
            let hs = row.hypotheses.context("missing scored H")?;
            let mut hmap = BTreeMap::new();
            for h in &hs {
                ensure!(
                    h.likelihood.is_none_or(f64::is_finite),
                    "invalid likelihood"
                );
                ensure!(
                    hmap.insert(h.sequence.clone(), (h.graph_presence, h.likelihood))
                        .is_none(),
                    "duplicate H"
                );
            }
            ensure!(
                hmap.get(&w.stock)
                    .is_some_and(|h| h.1.is_some() && h.1 == row.stock_likelihood),
                "native absent or likelihood mismatch"
            );
            if dataset != "expanded" {
                original_h.insert(row.query_index, hmap.clone());
            } else {
                for (s, h) in original_h
                    .get(&row.query_index)
                    .context("expanded lost original scored row")?
                {
                    ensure!(
                        hmap.get(s) == Some(h),
                        "expanded altered original hypothesis or score"
                    );
                }
            }
            let locals: Vec<_> = variants
                .iter()
                .filter(|v| {
                    overlaps(v, w)
                        && observations
                            .get(&(w.read_id.clone(), v.id.clone()))
                            .is_some_and(|c| c == "alt")
                })
                .collect();
            if locals.is_empty() {
                continue;
            }
            let g = graphs.get(&w.query_index).context("graph missing")?;
            let gs = g["reference"]["start"]
                .as_u64()
                .context("reference graph start")? as usize;
            let gr = g["reference"]["sequence"]
                .as_str()
                .context("reference graph DNA")?;
            ensure!(
                gs <= w.ref_start && w.ref_end - gs <= gr.len(),
                "reference context bounds"
            );
            let rf = &gr[w.ref_start - gs..w.ref_end - gs];
            let panel: BTreeSet<_> = hs
                .iter()
                .filter(|h| h.graph_presence)
                .map(|h| h.sequence.clone())
                .collect();
            let mut prototypes = Vec::new();
            for walk in g["walks"]
                .as_array()
                .context("walk array")?
                .iter()
                .filter(|p| p["both_anchors"] == true)
            {
                let center = trim(walk, g, w)?;
                ensure!(
                    panel.contains(&center),
                    "prototype missing from admitted panel"
                );
                prototypes.push((
                    center,
                    format!(
                        "{:x}",
                        Sha256::digest(walk["sequence"].as_str().context("walk seq")?.as_bytes())
                    ),
                ));
            }
            ensure!(
                panel == prototypes.iter().map(|p| p.0.clone()).collect(),
                "admitted panel differs from complete prototypes"
            );
            for v in locals {
                let cid = format!("{dataset}/{}", w.query_index);
                if !(w.ref_start <= v.start && v.end <= w.ref_end) {
                    exclusions.push(json!({"case_id":cid,"variant":v.id,"reason":"truth_window_outside_saved_window"}));
                    continue;
                }
                let (s, e) = (v.start - w.ref_start, v.end - w.ref_start);
                let stock_forward = orientation(&w.stock, w.reverse)?;
                if projection(&stock_forward, rf, s, e, &v.alt_hap)? != Support::Alt {
                    exclusions.push(json!({"case_id":cid,"variant":v.id,"reason":"native_hypothesis_projection_ambiguous_or_other"}));
                    continue;
                }
                let mut removed = BTreeSet::new();
                let mut ambiguous = false;
                for p in &panel {
                    match projection(&orientation(p, w.reverse)?, rf, s, e, &v.alt_hap)? {
                        Support::Alt => {
                            removed.insert(p.clone());
                        }
                        Support::Ambiguous => ambiguous = true,
                        Support::Other => {}
                    }
                }
                if ambiguous {
                    exclusions.push(json!({"case_id":cid,"variant":v.id,"reason":"panel_representation_ambiguous"}));
                    continue;
                }
                let retained: BTreeSet<_> = panel.difference(&removed).cloned().collect();
                let mut alt_h = 0;
                let mut impossible_alt_h = 0;
                let mut ambiguous_h = 0;
                for h in &hs {
                    match projection(&orientation(&h.sequence, w.reverse)?, rf, s, e, &v.alt_hap)? {
                        Support::Alt => {
                            if h.likelihood.is_some() {
                                alt_h += 1;
                            } else {
                                impossible_alt_h += 1;
                            }
                        }
                        Support::Ambiguous => ambiguous_h += 1,
                        Support::Other => {}
                    }
                }
                ensure!(alt_h > 0, "native ALT disappeared");
                let plan = plans.get(&w.query_index).context("missing flank plan")?;
                let (ordinary_flank, withheld_flank, flank_detail) = if plan["status"] == "eligible"
                {
                    let evidence: flank_snapshot::FlankEvidence =
                        serde_json::from_value(plan["evidence"].clone())?;
                    ensure!(
                        evidence.mapped_sam_sha256
                            == "db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe",
                        "flank original SAM mismatch"
                    );
                    let ps: Vec<flank_snapshot::WalkPrototype> =
                        serde_json::from_value(plan["prototypes"].clone())?;
                    ensure!(
                        ps.iter().map(|p| p.center.clone()).collect::<BTreeSet<_>>() == panel,
                        "flank prototype panel differs"
                    );
                    let ablated: Vec<_> = ps
                        .iter()
                        .filter(|p| !removed.contains(&p.center))
                        .cloned()
                        .collect();
                    let ordinary = flank_snapshot::compatibility(&evidence, &ps)?;
                    ensure!(
                        serde_json::to_value(&ordinary)? == plan["compatibility"],
                        "flank compatibility drift"
                    );
                    let withheld = flank_snapshot::compatibility(&evidence, &ablated)?;
                    let detail = json!({"source_status":"eligible","original_prototypes":ps.len(),"retained_prototypes":ablated.len(),"ordinary":ordinary,"withheld":withheld});
                    (ordinary.bonuses, withheld.bonuses, detail)
                } else {
                    ensure!(
                        plan["status"] == "abstain-binary",
                        "unknown flank plan status"
                    );
                    (
                        panel.iter().map(|s| (s.clone(), 1.0)).collect(),
                        retained.iter().map(|s| (s.clone(), 1.0)).collect(),
                        json!({"source_status":"abstain-binary","source_reason":plan["reason"]}),
                    )
                };
                let flank_binary_differences = hs
                    .iter()
                    .filter(|h| {
                        ordinary_flank.get(&h.sequence).copied().unwrap_or(0.0)
                            != f64::from(panel.contains(&h.sequence))
                            || withheld_flank.get(&h.sequence).copied().unwrap_or(0.0)
                                != f64::from(retained.contains(&h.sequence))
                    })
                    .count();
                let infer = InferenceCase {
                    schema: "private-allele-inference/1".into(),
                    case_id: cid.clone(),
                    stock: w.stock.clone(),
                    hypotheses: hs
                        .iter()
                        .map(|h| InferenceHypothesis {
                            sequence: h.sequence.clone(),
                            likelihood: h.likelihood,
                            ordinary: panel.contains(&h.sequence),
                            withheld: retained.contains(&h.sequence),
                        })
                        .collect(),
                    ordinary_flank,
                    withheld_flank,
                };
                write_line(&mut inference, &infer)?;
                write_line(
                    &mut cases,
                    &json!({"case_id":cid,"dataset":dataset,"query_index":w.query_index,"parent":w.read_id,"variant":v.id,"stratum":v.kind,"reverse":w.reverse,"reference_window":rf,"truth_window_start_in_reference_window":s,"truth_window_end_in_reference_window":e,"alt_haplotype":v.alt_hap,"stock":w.stock,"natural_panel_absent":removed.is_empty(),"removed_panel_centers":removed,"retained_panel_centers":retained,"prototypes":prototypes.iter().map(|(center,hash)|json!({"center":center,"full_sequence_sha256":hash,"removed":removed.contains(center)})).collect::<Vec<_>>(),"all_hypotheses":hs.len(),"finite_alt_hypotheses":alt_h,"impossible_alt_hypotheses":impossible_alt_h,"ambiguous_hypotheses":ambiguous_h,"saved_scores_file":path,"saved_row_sha256":format!("{:x}",Sha256::digest(line.as_bytes())),"tensor_sha256":row.score_sha256,"truth_inference_use":false,"flank":flank_detail,"flank_binary_hypothesis_bonus_differences":flank_binary_differences}),
                )?;
                eligible += 1;
            }
        }
        ensure!(seen.len() == windows.len(), "missing score rows");
    }
    inference.flush()?;
    cases.flush()?;
    fs::write(
        out.join("challenge-build.json"),
        serde_json::to_vec_pretty(
            &json!({"eligible_cases":eligible,"exclusions":exclusions,"thresholds":{"weight":1.0,"margin":0.5,"maximum_neural_deficit":0.5},"score_recomputation":false}),
        )?,
    )?;
    if !extra {
        additional(root, out, windows, variants, observations)?;
        attach::run(root, out)?;
    }
    Ok(())
}

fn additional(
    root: &Path,
    out: &Path,
    windows: &[Window],
    variants: &[Variant],
    observations: &BTreeMap<(String, String), String>,
) -> Result<()> {
    let full: BTreeSet<String> =
        fs::read_to_string("/home/jake/Projects/nanopore_basecaller/data/splits/development.txt")?
            .lines()
            .map(String::from)
            .collect();
    ensure!(full.len() == 2608, "wrong frozen full-development universe");
    let mut selected = Vec::new();
    let mut parents = BTreeSet::new();
    let mut strata = BTreeMap::new();
    for kind in ["snv", "insertion", "deletion"] {
        let mut options = Vec::new();
        for v in variants.iter().filter(|v| v.kind == kind) {
            for ((parent, id), call) in observations {
                if id != &v.id
                    || call != "alt"
                    || windows
                        .iter()
                        .any(|w| w.read_id == *parent && overlaps(v, w))
                {
                    continue;
                }
                let (s, e) = event(v);
                if e - s > 21 {
                    continue;
                }
                ensure!(full.contains(parent), "foreign proposed parent");
                options.push((v.id.clone(), parent.clone(), v, s, e));
            }
        }
        options.sort_by(|a, b| (&a.0, &a.1).cmp(&(&b.0, &b.1)));
        let available = options.len();
        let take = 20.min(available);
        for (id, parent, v, s, e) in options.into_iter().take(take) {
            let center = s + (e - s) / 2;
            parents.insert(parent.clone());
            selected.push(json!({"source_uuid":parent,"variant":id,"stratum":kind,"contig":v.contig,"event_start0":s,"event_end0":e,"proposed_core_start0":center.saturating_sub(10),"proposed_core_end0":center+11,"baseline_support":"qualified_original_mapped_native_exact_ALT","outside_existing_planned_cores":true,"truth_informed_diagnostic_only":true}));
        }
        strata.insert(
            kind,
            json!({"available_outside_planned_core_observations":available,"selected":take}),
        );
    }
    fs::write(
        out.join("additional-parents.ids"),
        parents.iter().map(|p| format!("{p}\n")).collect::<String>(),
    )?;
    fs::write(
        out.join("additional-windows.json"),
        serde_json::to_vec_pretty(
            &json!({"schema":"private-allele-additional-windows/1","role":"development","admissible_candidate":false,"source_parent_universe":2608,"selected_parents":parents.len(),"selected_windows":selected.len(),"ordering":"stratum then variant identifier then parent UUID","strata":strata,"targets":selected,"existing_export":root.join("results/graph-prior/pilot-v1/development/native-export"),"native_export_required_before_scoring":false,"custom_truth_centered_planner_qualified":false,"new_gpu_admitted":false}),
        )?,
    )?;
    Ok(())
}

pub(super) fn infer(input: &Path, out: &Path) -> Result<()> {
    let mut writer = BufWriter::new(File::create(out)?);
    let mut seen = BTreeSet::new();
    for line in BufReader::new(File::open(input)?).lines() {
        let case: InferenceCase = serde_json::from_str(&line?)?;
        ensure!(
            case.schema == "private-allele-inference/1" && seen.insert(case.case_id.clone()),
            "invalid/duplicate inference case"
        );
        let mut seqs = BTreeSet::new();
        for h in &case.hypotheses {
            ensure!(seqs.insert(&h.sequence), "duplicate hypothesis");
            ensure!(!h.withheld || h.ordinary, "withheld added panel membership");
            ensure!(
                h.likelihood.is_none_or(f64::is_finite),
                "invalid saved score"
            );
        }
        for bonuses in [&case.ordinary_flank, &case.withheld_flank] {
            ensure!(
                bonuses
                    .iter()
                    .all(|(s, b)| seqs.contains(s) && b.is_finite() && (0.0..=1.0).contains(b)),
                "invalid flank bonus"
            );
        }
        for (arm, prior, withheld) in [
            ("neutral", decision::Prior::None, false),
            ("ordinary_panel", decision::Prior::Panel, false),
            ("withheld_panel", decision::Prior::Panel, true),
        ] {
            let hs: Vec<_> = case
                .hypotheses
                .iter()
                .map(|h| decision::Hypothesis {
                    sequence: h.sequence.clone(),
                    likelihood: h.likelihood.unwrap_or(f64::NEG_INFINITY),
                    panel: if withheld { h.withheld } else { h.ordinary },
                    linear: false,
                })
                .collect();
            let policy = decision::Policy {
                id: arm.into(),
                prior,
                lambda: if prior == decision::Prior::None {
                    0.0
                } else {
                    1.0
                },
                neural_deficit: Some(0.5),
                margin: 0.5,
            };
            let d = decision::choose(&case.stock, &hs, &policy)?;
            let emitted = if d.edited { &d.winner } else { &case.stock };
            write_line(
                &mut writer,
                &json!({"case_id":case.case_id,"arm":arm,"decision":d,"emitted":emitted}),
            )?;
        }
        let hs: Vec<_> = case
            .hypotheses
            .iter()
            .map(|h| flank_snapshot::Hypothesis {
                sequence: h.sequence.clone(),
                likelihood: h.likelihood.unwrap_or(f64::NEG_INFINITY),
            })
            .collect();
        for (arm, bonuses) in [
            ("ordinary_flank", &case.ordinary_flank),
            ("withheld_flank", &case.withheld_flank),
        ] {
            let d = flank_snapshot::choose(&case.stock, &hs, bonuses)?;
            let emitted = if d.edited { &d.winner } else { &case.stock };
            write_line(
                &mut writer,
                &json!({"case_id":case.case_id,"arm":arm,"decision":d,"emitted":emitted}),
            )?;
        }
    }
    writer.flush()?;
    Ok(())
}

pub(super) fn report(cases: &Path, decisions: &Path, out: &Path) -> Result<()> {
    const ARMS: [&str; 5] = [
        "neutral",
        "ordinary_panel",
        "withheld_panel",
        "ordinary_flank",
        "withheld_flank",
    ];
    let mut labels = BTreeMap::new();
    for case in load_jsonl::<Value>(cases)? {
        let id = case["case_id"].as_str().context("case id")?.to_owned();
        ensure!(!id.is_empty(), "empty case id");
        ensure!(labels.insert(id, case).is_none(), "duplicate case id");
    }
    let mut seen = BTreeSet::new();
    let mut rows = Vec::new();
    let mut counts: BTreeMap<String, Value> = BTreeMap::new();
    for d in load_jsonl::<Value>(decisions)? {
        let id = d["case_id"].as_str().context("case id")?;
        let case = labels.get(id).context("foreign decision case")?;
        let arm = d["arm"].as_str().context("arm")?;
        ensure!(ARMS.contains(&arm), "foreign decision arm");
        ensure!(
            seen.insert((id.to_owned(), arm.to_owned())),
            "duplicate decision case/arm"
        );
        let rf = case["reference_window"].as_str().context("reference")?;
        let alt = case["alt_haplotype"].as_str().context("alt")?;
        let s = case["truth_window_start_in_reference_window"]
            .as_u64()
            .context("start")? as usize;
        let e = case["truth_window_end_in_reference_window"]
            .as_u64()
            .context("end")? as usize;
        let reverse = case["reverse"].as_bool().context("reverse")?;
        let emitted = orientation(d["emitted"].as_str().context("emitted")?, reverse)?;
        let winner = orientation(d["decision"]["winner"].as_str().context("winner")?, reverse)?;
        let retained = projection(&emitted, rf, s, e, alt)? == Support::Alt;
        let winner_alt = projection(&winner, rf, s, e, alt)? == Support::Alt;
        let group = format!(
            "{}/{}/{}/{}",
            case["dataset"].as_str().context("dataset")?,
            if case["natural_panel_absent"] == true {
                "natural_absent"
            } else {
                "engineered_withheld"
            },
            case["stratum"].as_str().context("stratum")?,
            d["arm"].as_str().context("arm")?
        );
        let c=counts.entry(group).or_insert(json!({"cores":0,"edited_cores":0,"alt_retained":0,"alt_lost":0,"edited_alt_lost":0,"alt_pregate_winner":0}));
        for (key, yes) in [
            ("cores", true),
            ("edited_cores", d["decision"]["edited"] == true),
            ("alt_retained", retained),
            ("alt_lost", !retained),
            (
                "edited_alt_lost",
                !retained && d["decision"]["edited"] == true,
            ),
            ("alt_pregate_winner", winner_alt),
        ] {
            if yes {
                c[key] = json!(c[key].as_u64().context("counter")? + 1);
            }
        }
        rows.push(json!({"case_id":d["case_id"],"variant":case["variant"],"parent":case["parent"],"stratum":case["stratum"],"arm":d["arm"],"edited":d["decision"]["edited"],"gate":d["decision"]["gate"],"native_alt_retained":retained,"pregate_winner_alt":winner_alt,"objective_margin":d["decision"]["objective_margin"],"neural_delta":d["decision"]["neural_delta"]}));
    }
    for id in labels.keys() {
        for arm in ARMS {
            ensure!(
                seen.contains(&(id.clone(), arm.to_owned())),
                "missing decision case/arm: {id}/{arm}"
            );
        }
    }
    fs::write(
        out,
        serde_json::to_vec_pretty(
            &json!({"schema":"private-allele-report/1","role":"development","admissible_candidate":false,"groups":counts,"rows":rows}),
        )?,
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shifted_indel_representation_matches_haplotype() {
        assert_eq!(
            projection("GCTAAAAATCG", "GCTAAAATCG", 1, 9, "CTAAAAATC").expect("valid"),
            Support::Alt
        );
    }
    #[test]
    fn uncertain_repeat_boundary_is_excluded() {
        assert_eq!(
            projection("AAAAA", "AAAA", 1, 3, "AAA").expect("valid"),
            Support::Ambiguous
        );
    }
    #[test]
    fn reverse_complement_is_involution() {
        for s in ["ACGT", "ATTTGC", "GGGACCC"] {
            assert_eq!(revcomp(&revcomp(s).expect("valid")).expect("valid"), s);
        }
    }
    #[test]
    fn inference_rejects_genotype_and_extra_fields() {
        assert!(serde_json::from_str::<InferenceCase>(r#"{"schema":"private-allele-inference/1","case_id":"x","stock":"A","hypotheses":[],"gt":"0/1"}"#).is_err());
    }
    #[test]
    fn ablation_changes_membership_without_dropping_hypotheses() {
        use decision::*;
        let h = vec![
            Hypothesis {
                sequence: "A".into(),
                panel: true,
                linear: false,
                likelihood: 1.0,
            },
            Hypothesis {
                sequence: "C".into(),
                panel: true,
                linear: false,
                likelihood: 0.75,
            },
        ];
        let p = Policy {
            id: "p".into(),
            prior: Prior::Panel,
            lambda: 1.0,
            margin: 0.5,
            neural_deficit: Some(0.5),
        };
        assert!(!choose("A", &h, &p).expect("valid").edited);
        let mut ablated = h.clone();
        ablated[0].panel = false;
        let d = choose("A", &ablated, &p).expect("valid");
        assert!(d.edited);
        assert_eq!(d.winner, "C");
        assert_eq!(h.len(), ablated.len());
        assert_eq!(h[0].likelihood.to_bits(), ablated[0].likelihood.to_bits());
    }
}
