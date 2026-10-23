use crate::{crf, graph, native, planner, scores};
use anyhow::{ensure, Context, Result};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, fs, io::Write, path::Path};
const ARMS: [(&str, f64); 4] = [
    ("neutral.sam", 0.0),
    ("graph-025.sam", 0.25),
    ("graph-050.sam", 0.5),
    ("graph-100.sam", 1.0),
];
#[derive(Clone)]
struct Edit {
    start: usize,
    end: usize,
    seq: String,
}
fn apply(seq: &str, qual: &str, edits: &mut [Edit]) -> Result<(String, String)> {
    edits.sort_by_key(|e| e.start);
    let mut s = String::new();
    let mut q = String::new();
    let mut p = 0;
    for e in edits {
        ensure!(
            p <= e.start && e.start <= e.end && e.end <= seq.len(),
            "overlapping/out-of-bounds edits"
        );
        s.push_str(&seq[p..e.start]);
        q.push_str(&qual[p..e.start]);
        s.push_str(&e.seq);
        q.extend(std::iter::repeat_n('!', e.seq.len()));
        p = e.end;
    }
    s.push_str(&seq[p..]);
    q.push_str(&qual[p..]);
    Ok((s, q))
}
#[allow(clippy::too_many_arguments)]
pub fn decode(
    reference: &Path,
    sam_path: &Path,
    export: &Path,
    parents: &Path,
    windows: &Path,
    graph_path: &Path,
    out: &Path,
) -> Result<()> {
    let ids = native::parents(parents)?;
    let sams = native::sam(sam_path, &ids)?;
    let rf = accuracy::Reference::load(reference)?;
    let inv = native::inventory(export, &ids)?;
    let ws = planner::load_windows(windows)?;
    let graphs = graph::load(graph_path)?;
    ensure!(
        graphs.keys().all(|&i| i < ws.len()),
        "graph query index outside plan"
    );
    let mut export_ok = BTreeMap::new();
    let mut export_bad = BTreeMap::new();
    for id in &ids {
        match native::reconstruct(export, &sams[id], &inv[id]) {
            Ok(e) => {
                export_ok.insert(id.clone(), e);
            }
            Err(e) => {
                export_bad.insert(id.clone(), e.to_string());
            }
        }
    }
    let mut decisions = Vec::new();
    let mut arm_edits: [BTreeMap<String, Vec<Edit>>; 4] = Default::default();
    let mut intervals: BTreeMap<String, Vec<(usize, usize)>> = BTreeMap::new();
    let mut previous_score = String::new();
    let mut saved: Option<scores::Scores> = None;
    let mut score_hash = String::new();
    let mut admitted = 0usize;
    for w in &ws {
        let s = sams
            .get(&w.read_id)
            .context("window UUID absent from requested parents")?;
        let ranges = intervals.entry(w.read_id.clone()).or_default();
        ensure!(
            !ranges
                .iter()
                .any(|&(a, b)| a < w.read_end && w.read_start < b),
            "overlapping planned windows"
        );
        ranges.push((w.read_start, w.read_end));
        let e = match export_ok.get(&w.read_id) {
            Some(e) => e,
            None => {
                decisions.push(json!({"query_index":w.query_index,"read_id":w.read_id,"status":"excluded","reason":export_bad.get(&w.read_id)}));
                continue;
            }
        };
        let reference = rf.seq.get(&w.contig).context("window contig absent")?;
        planner::validate_window(w, s, reference, e)?;
        let Some(interval) = graphs.get(&w.query_index) else {
            decisions.push(json!({"query_index":w.query_index,"read_id":w.read_id,"status":"excluded","reason":"graph interval unavailable"}));
            continue;
        };
        let panel = match graph::panel(w, interval, reference) {
            Ok(p) => p,
            Err(e) => {
                decisions.push(json!({"query_index":w.query_index,"read_id":w.read_id,"status":"excluded","reason":e.to_string()}));
                continue;
            }
        };
        let hs = crf::hypotheses(&w.stock, &panel)?;
        if previous_score != w.score_file {
            saved = Some(scores::load(&export.join(&w.score_file))?);
            score_hash = format!(
                "{:x}",
                Sha256::digest(fs::read(export.join(&w.score_file))?)
            );
            previous_score = w.score_file.clone();
        }
        let score = saved.as_ref().context("no loaded score")?;
        ensure!(
            w.t_start < w.t_end && w.t_end <= score.header.t && w.t_end - w.t_start <= 256,
            "score window bounds"
        );
        let slice = &score.values[w.t_start * 1024..w.t_end * 1024];
        let initial = crf::state(w.context.as_bytes(), 4)?;
        let scorer =
            crf::ScoreWindow::new(slice, w.t_end - w.t_start, 4, initial, score.header.blank)?;
        let terminal = crf::state(w.stock.as_bytes(), 4)?;
        let mut likelihoods = Vec::new();
        for (seq, g) in hs {
            ensure!(
                crf::state(seq.as_bytes(), 4)? == terminal,
                "hypothesis terminal state mismatch"
            );
            let l = scorer.likelihood(seq.as_bytes())?;
            likelihoods.push((seq, g, l));
        }
        let stock_l = likelihoods
            .iter()
            .find(|x| x.0 == w.stock)
            .context("stock absent")?
            .2;
        // An impossible stock interval cannot support a stable objective margin.
        if !stock_l.is_finite() {
            decisions.push(json!({"query_index":w.query_index,"read_id":w.read_id,"status":"excluded","reason":"stock likelihood is impossible"}));
            continue;
        }
        admitted += 1;
        let mut arms = Vec::new();
        for (i, (name, lambda)) in ARMS.iter().enumerate() {
            let (winner, edit, margin) = crf::choose(&w.stock, &likelihoods, *lambda)?;
            if edit {
                arm_edits[i]
                    .entry(w.read_id.clone())
                    .or_default()
                    .push(Edit {
                        start: w.read_start + 10,
                        end: w.read_end - 10,
                        seq: winner[10..winner.len() - 10].to_owned(),
                    });
            }
            let selected = likelihoods
                .iter()
                .find(|x| x.0 == winner)
                .context("selected hypothesis absent")?;
            arms.push(json!({"arm":name,"lambda":lambda,"winner":winner,"winner_likelihood":selected.2,"winner_graph_presence":selected.1,"objective_margin":margin,"edited":edit,"edited_quality":"uncalibrated-!","edit_start":w.read_start+10,"edit_end":w.read_end-10}));
        }
        let serialized:Vec<_>=likelihoods.iter().map(|(seq,g,l)|json!({"sequence":seq,"graph_presence":g,"likelihood":if l.is_finite(){Some(*l)}else{None}})).collect();
        decisions.push(json!({"query_index":w.query_index,"read_id":w.read_id,"status":"scored","stock_likelihood":stock_l,"score_sha256":score_hash,"hypotheses":serialized,"arms":arms}));
    }
    fs::create_dir(out)?;
    let mut summaries = Vec::new();
    for (i, (name, lambda)) in ARMS.iter().enumerate() {
        let mut f = fs::File::create(out.join(name))?;
        writeln!(f, "@HD\tVN:1.6\tSO:unknown")?;
        let mut edited_parents = 0;
        let mut edits = 0;
        for id in &ids {
            let s = &sams[id];
            let (seq, qual) = if let Some(changes) = arm_edits[i].get_mut(id) {
                edited_parents += 1;
                edits += changes.len();
                apply(&s.seq, &s.qual, changes)?
            } else {
                (s.seq.clone(), s.qual.clone())
            };
            writeln!(f, "{}\t4\t*\t0\t0\t*\t*\t0\t0\t{}\t{}", id, seq, qual)?;
        }
        summaries.push(json!({"arm":name,"lambda":lambda,"parents":ids.len(),"edited_parents":edited_parents,"edited_windows":edits,"qualities":"changed cores uncalibrated (!); other bases retain original native Q"}));
    }
    let mut f = fs::File::create(out.join("decisions.jsonl"))?;
    for d in &decisions {
        serde_json::to_writer(&mut f, d)?;
        writeln!(f)?;
    }
    fs::write(
        out.join("summary.json"),
        serde_json::to_vec_pretty(
            &json!({"schema":"graph-prior-summary/1","parents":ids.len(),"planned_windows":ws.len(),"scored_windows":admitted,"excluded_windows":ws.len()-admitted,"parent_export_exclusions":export_bad,"arms":summaries,"limits":"local finite-hypothesis reranker; qualities uncalibrated; no native replay, biological accuracy, whole-genome or performance claim"}),
        )?,
    )?;
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn edits_preserve_outside_and_quality() {
        let mut e = vec![
            Edit {
                start: 2,
                end: 4,
                seq: "G".into(),
            },
            Edit {
                start: 6,
                end: 7,
                seq: "TT".into(),
            },
        ];
        let (s, q) = apply("AACCGGTT", "12345678", &mut e).expect("apply");
        assert_eq!(s, "AAGGGTTT");
        assert_eq!(q, "12!56!!8");
    }
}
