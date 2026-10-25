#[allow(dead_code)]
#[path = "../../graph_frontier/src/decision.rs"]
mod decision;
#[allow(dead_code)]
#[path = "../../graph_frontier/src/input.rs"]
mod input;
use anyhow::{ensure, Context, Result};
use decision::{choose, Hypothesis, Policy, Prior};
use input::{pin, read_json, read_sam, Admitted, Parent};
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{BufRead, BufReader, Write},
    path::Path,
};

#[derive(Deserialize)]
struct SavedH {
    sequence: String,
    graph_presence: bool,
    likelihood: Option<f64>,
}
#[derive(Deserialize)]
struct Row {
    query_index: usize,
    read_id: String,
    status: String,
    stock_likelihood: Option<f64>,
    score_sha256: Option<String>,
    hypotheses: Option<Vec<SavedH>>,
    reason: Option<String>,
}
#[derive(Clone)]
struct Edit {
    start: usize,
    end: usize,
    sequence: String,
}
type Edits = BTreeMap<String, Vec<Edit>>;
fn inherited(old: &[Hypothesis], new: &[Hypothesis]) -> Result<()> {
    let by_seq: BTreeMap<_, _> = new.iter().map(|h| (h.sequence.as_str(), h)).collect();
    ensure!(by_seq.len() == new.len(), "duplicate expanded sequence");
    for h in old {
        let n = by_seq
            .get(h.sequence.as_str())
            .context("missing inherited sequence")?;
        ensure!(
            h.panel == n.panel && h.likelihood.to_bits() == n.likelihood.to_bits(),
            "changed inherited presence/likelihood {}",
            h.sequence
        );
    }
    Ok(())
}
fn best<'a>(
    h: &'a [Hypothesis],
    native: &str,
    class: bool,
    linear: bool,
) -> Option<&'a Hypothesis> {
    let mut winner: Option<&Hypothesis> = None;
    for x in h.iter().filter(|x| {
        if linear {
            x.linear == class
        } else {
            x.panel == class
        }
    }) {
        if winner.is_none_or(|w| {
            x.likelihood > w.likelihood
                || (x.likelihood == w.likelihood
                    && w.sequence != native
                    && (x.sequence == native || x.sequence < w.sequence))
        }) {
            winner = Some(x);
        }
    }
    winner
}
fn best_json(h: Option<&Hypothesis>, native_score: f64) -> Value {
    h.map_or(Value::Null, |x| json!({"sequence":x.sequence,"likelihood":x.likelihood,"native_gap":x.likelihood-native_score}))
}
fn add_edit(edits: &mut Edits, w: &input::Window, d: &decision::Decision) {
    if d.edited {
        edits.entry(w.read_id.clone()).or_default().push(Edit {
            start: w.read_start + 10,
            end: w.read_end - 10,
            sequence: d.winner[10..d.winner.len() - 10].into(),
        });
    }
}
fn output(
    cohort: &Admitted,
    parents: &BTreeMap<String, Parent>,
    edits: &Edits,
) -> Result<BTreeMap<String, Parent>> {
    let mut out = BTreeMap::new();
    for id in &cohort.ids {
        let p = &parents[id];
        let mut seq = String::new();
        let mut qual = String::new();
        let mut cursor = 0;
        let mut es = edits.get(id).cloned().unwrap_or_default();
        es.sort_by_key(|e| e.start);
        for e in es {
            ensure!(
                cursor <= e.start && e.start <= e.end && e.end <= p.seq.len(),
                "overlap/bounds"
            );
            seq.push_str(&p.seq[cursor..e.start]);
            qual.push_str(&p.qual[cursor..e.start]);
            seq.push_str(&e.sequence);
            qual.extend(std::iter::repeat_n('!', e.sequence.len()));
            cursor = e.end;
        }
        seq.push_str(&p.seq[cursor..]);
        qual.push_str(&p.qual[cursor..]);
        out.insert(
            id.clone(),
            Parent {
                seq,
                qual,
                reverse: false,
            },
        );
    }
    Ok(out)
}
fn identity(p: &BTreeMap<String, Parent>) -> String {
    let mut hash = Sha256::new();
    for (id, x) in p {
        for s in [id, &x.seq, &x.qual] {
            hash.update((s.len() as u64).to_le_bytes());
            hash.update(s.as_bytes());
        }
    }
    format!("{:x}", hash.finalize())
}
fn differences(a: &BTreeMap<String, Parent>, b: &BTreeMap<String, Parent>) -> Vec<String> {
    a.iter()
        .filter(|(id, x)| {
            b.get(*id)
                .is_none_or(|y| x.seq != y.seq || x.qual != y.qual)
        })
        .map(|(id, _)| id.clone())
        .collect()
}
fn verify_pins(v: &Value, seen: &mut BTreeMap<String, input::Pin>) -> Result<()> {
    if v.is_object() && v["path"].is_string() && v["size"].is_u64() && v["sha256"].is_string() {
        let expected: input::Pin = serde_json::from_value(v.clone())?;
        let key = expected.path.to_string_lossy().into_owned();
        if let Some(previous) = seen.get(&key) {
            ensure!(previous == &expected, "conflicting pin");
        } else {
            let actual = pin(&expected.path)?;
            ensure!(actual == expected, "pin mismatch {}", key);
            seen.insert(key, actual);
        }
    } else {
        match v {
            Value::Object(o) => {
                for x in o.values() {
                    verify_pins(x, seen)?
                }
            }
            Value::Array(a) => {
                for x in a {
                    verify_pins(x, seen)?
                }
            }
            _ => {}
        }
    }
    Ok(())
}
fn load(path: &str) -> Result<Value> {
    read_json(Path::new(path))
}
fn main() -> Result<()> {
    let args: Vec<_> = std::env::args().collect();
    ensure!(args.len() == 3, "usage: hypothesis-coverage CONFIG OUTPUT");
    let cfg = load(&args[1])?;
    let dst = Path::new(&args[2]);
    fs::create_dir(dst)?;
    let field = |k: &str| -> Result<&str> { cfg[k].as_str().context("missing config path") };
    let old = input::admit(Path::new(field("cohort")?))?;
    ensure!(old.cohort.role == "development", "development only");
    let completion = load(field("admission")?)?;
    let admission_root = Path::new(field("admission")?)
        .parent()
        .context("admission parent")?;
    let bridge = read_json::<Value>(&admission_root.join("bridge-admission.json"))?;
    let mut pins = BTreeMap::new();
    for v in [
        &completion,
        &bridge,
        &load(field("catalogue")?)?,
        &load(field("cohort")?)?,
    ] {
        verify_pins(v, &mut pins)?;
    }
    for p in [
        field("cohort")?,
        field("admission")?,
        field("catalogue")?,
        field("protocol")?,
        field("source_policy_summary")?,
        field("scoring_baseline")?,
    ] {
        let p = pin(Path::new(p))?;
        pins.insert(p.path.to_string_lossy().into_owned(), p);
    }
    let expanded_cohort = read_json::<Value>(&admission_root.join("cohort.json"))?;
    for k in ["parents", "native_sam", "windows", "graph_walks"] {
        ensure!(
            expanded_cohort["pins"][k] == serde_json::to_value(&old.cohort)?["pins"][k],
            "ancestry mismatch {k}"
        );
    }
    let protocol: input::Protocol = read_json(Path::new(field("protocol")?))?;
    let registered: Value = read_json(&admission_root.join("protocol.json"))?;
    ensure!(
        registered == load(field("protocol")?)?,
        "registered policy mismatch"
    );
    ensure!(protocol.policies.len() == 4, "four policies required");
    let mut old_edits = vec![Edits::new(); 4];
    let mut new_edits = old_edits.clone();
    let mut hist_edits = old_edits.clone();
    let mut changes = vec![[0usize; 3]; 4];
    let mut classes = [[0usize; 2]; 2];
    let mut class_score_changes = [[0usize; 2]; 2];
    let mut changed_maxima = Vec::new();
    let mut changed_winners = Vec::new();
    let mut total_old = 0;
    let mut total_new = 0;
    let mut added_panel = 0;
    let mut excluded = 0;
    let mut scored = 0;
    let mut rows = fs::File::create(dst.join("windows.jsonl"))?;
    let mut original_rows = BufReader::new(fs::File::open(
        load(field("catalogue")?)?["decisions"]["path"]
            .as_str()
            .context("catalogue decisions")?,
    )?)
    .lines();
    let mut observed = BTreeSet::new();
    let old_rows = BufReader::new(fs::File::open(&old.cohort.pins.decisions.path)?)
        .lines()
        .map(|line| -> Result<_> {
            let r: Row = serde_json::from_str(&line?)?;
            Ok((r.query_index, r))
        })
        .collect::<Result<BTreeMap<_, _>>>()?;
    for line in BufReader::new(fs::File::open(
        expanded_cohort["pins"]["decisions"]["path"]
            .as_str()
            .context("expanded decisions")?,
    )?)
    .lines()
    {
        let line = line?;
        let r: Row = serde_json::from_str(&line)?;
        let original_line = original_rows.next().context("missing catalogue row")??;
        let c: Row = serde_json::from_str(&original_line)?;
        ensure!(
            r.query_index == c.query_index
                && r.read_id == c.read_id
                && r.status == c.status
                && r.reason == c.reason
                && r.score_sha256 == c.score_sha256
                && r.stock_likelihood.map(f64::to_bits) == c.stock_likelihood.map(f64::to_bits),
            "catalogue row changed"
        );
        ensure!(observed.insert(r.query_index), "duplicate query");
        let e = old
            .windows
            .iter()
            .find(|e| e.window.query_index == r.query_index)
            .context("foreign query")?;
        let original_h = old_rows.get(&r.query_index).context("missing old-H row")?;
        ensure!(
            r.read_id == original_h.read_id
                && r.status == original_h.status
                && r.reason == original_h.reason
                && r.score_sha256 == original_h.score_sha256
                && r.stock_likelihood.map(f64::to_bits)
                    == original_h.stock_likelihood.map(f64::to_bits),
            "original-H metadata changed"
        );
        let w = &e.window;
        ensure!(r.read_id == w.read_id, "UUID join");
        if r.status == "excluded" {
            ensure!(
                e.exclusion == r.reason && r.hypotheses.is_none(),
                "exclusion changed"
            );
            excluded += 1;
            continue;
        }
        ensure!(
            r.status == "scored" && e.exclusion.is_none(),
            "status changed"
        );
        let linear = e
            .hypotheses
            .iter()
            .find(|x| x.linear)
            .context("linear absent")?
            .sequence
            .as_str();
        let new: Vec<_> = r
            .hypotheses
            .context("hypotheses absent")?
            .into_iter()
            .map(|h| Hypothesis {
                linear: h.sequence == linear,
                sequence: h.sequence,
                panel: h.graph_presence,
                likelihood: h.likelihood.unwrap_or(f64::NEG_INFINITY),
            })
            .collect();
        let ch = c.hypotheses.context("catalogue hypotheses")?;
        ensure!(
            new.len() == ch.len()
                && new.iter().zip(ch).all(|(a, b)| a.sequence == b.sequence
                    && a.panel == b.graph_presence
                    && a.likelihood.to_bits()
                        == b.likelihood.unwrap_or(f64::NEG_INFINITY).to_bits()),
            "catalogue hypotheses changed"
        );
        inherited(&e.hypotheses, &new).with_context(|| format!("query {}", w.query_index))?;
        let native = e
            .hypotheses
            .iter()
            .find(|h| h.sequence == w.stock)
            .context("native")?
            .likelihood;
        ensure!(
            r.stock_likelihood.map(f64::to_bits) == Some(native.to_bits()),
            "native mismatch"
        );
        let old_set: BTreeSet<_> = e.hypotheses.iter().map(|x| x.sequence.as_str()).collect();
        let added = new
            .iter()
            .filter(|h| !old_set.contains(h.sequence.as_str()))
            .collect::<Vec<_>>();
        added_panel += added.iter().filter(|h| h.panel).count();
        let mut maxima = Vec::new();
        for (prior_i, linear) in [false, true].into_iter().enumerate() {
            for class in [false, true] {
                let a = best(&e.hypotheses, &w.stock, class, linear);
                let b = best(&new, &w.stock, class, linear);
                let score_changed =
                    a.map(|x| x.likelihood.to_bits()) != b.map(|x| x.likelihood.to_bits());
                let sequence_changed = a.map(|x| &x.sequence) != b.map(|x| &x.sequence);
                classes[prior_i][0] += usize::from(score_changed);
                classes[prior_i][1] += usize::from(sequence_changed);
                class_score_changes[prior_i][usize::from(class)] += usize::from(score_changed);
                if score_changed {
                    changed_maxima.push(json!({"query_index":w.query_index,"prior":if linear{"linear"}else{"panel"},"class_present":class,"old":best_json(a,native),"expanded":best_json(b,native)}));
                }
                maxima.push(json!({"prior":if linear{"linear"}else{"panel"},"class_present":class,"old":best_json(a,native),"expanded":best_json(b,native),"score_changed":score_changed,"sequence_changed":sequence_changed}));
            }
        }
        let mut choices = Vec::new();
        for (i, p) in protocol.policies.iter().enumerate() {
            let a = choose(&w.stock, &e.hypotheses, p)?;
            let b = choose(&w.stock, &new, p)?;
            if a.winner != b.winner {
                changed_winners
                    .push(json!({"query_index":w.query_index,"policy":p.id,"old":a,"expanded":b}));
            }
            changes[i][0] += usize::from(a.winner != b.winner);
            changes[i][1] += usize::from(a.edited != b.edited);
            changes[i][2] += usize::from(
                (if a.edited { &a.winner } else { &w.stock })
                    != (if b.edited { &b.winner } else { &w.stock }),
            );
            add_edit(&mut old_edits[i], w, &a);
            add_edit(&mut new_edits[i], w, &b);
            choices.push(json!({"policy":p.id,"old":a,"expanded":b}));
        }
        for (i, lambda) in [0.0, 0.25, 0.5, 1.0].into_iter().enumerate() {
            let p = Policy {
                id: "historical".into(),
                prior: Prior::Panel,
                lambda,
                neural_deficit: Some(0.0),
                margin: 0.5,
            };
            let d = choose(&w.stock, &e.hypotheses, &p)?;
            let h = &e.historical[i];
            ensure!(
                h.winner == d.winner
                    && h.edited == d.edited
                    && h.objective_margin.to_bits() == d.objective_margin.to_bits(),
                "historical decision mismatch"
            );
            add_edit(&mut hist_edits[i], w, &d);
        }
        writeln!(
            rows,
            "{}",
            json!({"query_index":w.query_index,"read_id":w.read_id,"native":w.stock,"native_likelihood":native,"old_count":e.hypotheses.len(),"expanded_count":new.len(),"added":added.len(),"added_panel":added.iter().filter(|h|h.panel).count(),"maxima":maxima,"policies":choices})
        )?;
        total_old += e.hypotheses.len();
        total_new += new.len();
        scored += 1;
    }
    ensure!(
        original_rows.next().is_none()
            && observed.len() == old.windows.len()
            && scored == 331
            && excluded == 120,
        "row accounting"
    );
    let baseline = read_sam(Path::new(field("scoring_baseline")?), &old.ids)?;
    let baseline_differences = differences(&old.parents, &baseline);
    let summary: Value = read_json(&admission_root.join("candidates/summary.json"))?;
    let mut outputs = Vec::new();
    let mut output_maps = Vec::new();
    for (i, p) in protocol.policies.iter().enumerate() {
        let a = output(&old, &old.parents, &old_edits[i])?;
        let b = output(&old, &old.parents, &new_edits[i])?;
        let saved_arm = summary["arms"]
            .as_array()
            .context("arms")?
            .iter()
            .find(|x| x["id"] == p.id)
            .context("policy arm")?;
        let saved = read_sam(
            Path::new(saved_arm["sam"]["path"].as_str().context("SAM path")?),
            &old.ids,
        )?;
        ensure!(
            differences(&b, &saved).is_empty(),
            "expanded emitted output mismatch"
        );
        let inventory:Vec<_>=b.iter().map(|(id,x)|json!({"uuid":id,"seq_length":x.seq.len(),"seq_sha256":format!("{:x}",Sha256::digest(x.seq.as_bytes())),"q_sha256":format!("{:x}",Sha256::digest(x.qual.as_bytes()))})).collect();
        let historical_comparison = match p.prior {
            Prior::None => Some("neutral"),
            Prior::Panel => Some("graph-100"),
            Prior::Linear => None,
        };
        let historical_differences = historical_comparison.map(|name| json!({"arm":name,"different_ids":differences(&b,&old.historical[name]),"qualification":"Historical arms use a zero neural deficit; registered finite policies use their declared rules."}));
        outputs.push(json!({"policy":p.id,"old_identity":identity(&a),"expanded_identity":identity(&b),"different_parent_ids":differences(&a,&b),"winner_changes":changes[i][0],"edit_flag_changes":changes[i][1],"emitted_window_changes":changes[i][2],"actual_expanded_output_verified":true,"historical_comparison":historical_differences,"parent_inventory":inventory}));
        output_maps.push(b);
    }
    let mut historical = Vec::new();
    for (i, name) in ["neutral", "graph-025", "graph-050", "graph-100"]
        .into_iter()
        .enumerate()
    {
        let a = output(&old, &old.parents, &hist_edits[i])?;
        let b = output(&old, &baseline, &hist_edits[i])?;
        let saved = &old.historical[name];
        historical.push(json!({"arm":name,"cohort_baseline_different_ids":differences(&a,saved),"scoring_baseline_different_ids":differences(&b,saved),"original_identity":identity(saved)}));
    }
    let sources = load(field("source_policy_summary")?)?;
    verify_pins(&sources["cohort"], &mut pins)?;
    verify_pins(&sources["protocol"], &mut pins)?;
    let mut reuse = Vec::new();
    let mut checked = 0;
    for artifact in sources["artifacts"]
        .as_array()
        .context("source artifacts")?
    {
        verify_pins(&artifact["sam"], &mut pins)?;
        let source = read_sam(
            Path::new(artifact["sam"]["path"].as_str().context("source SAM")?),
            &old.ids,
        )?;
        let id = identity(&source);
        checked += 1;
        let matched: Vec<_> = output_maps
            .iter()
            .enumerate()
            .filter(|(_, p)| differences(p, &source).is_empty())
            .map(|(i, _)| protocol.policies[i].id.clone())
            .collect();
        if !matched.is_empty() {
            let arms: Vec<_> = sources["arms"]
                .as_array()
                .context("source arms")?
                .iter()
                .filter(|a| a["artifact_id"] == artifact["id"])
                .map(|a| a["id"].clone())
                .collect();
            reuse.push(json!({"artifact":artifact["id"],"identity":id,"matching_compound_policies":matched,"source_policies":arms,"sam":artifact["sam"]}));
        }
    }
    for p in [
        Path::new(&args[1]).to_path_buf(),
        std::env::current_exe()?,
        Path::new("tools/hypothesis_coverage/src/main.rs").to_path_buf(),
        Path::new("tools/hypothesis_coverage/Cargo.toml").to_path_buf(),
        Path::new("tools/hypothesis_coverage/Cargo.lock").to_path_buf(),
        Path::new("tools/graph_frontier/src/input.rs").to_path_buf(),
        Path::new("tools/graph_frontier/src/decision.rs").to_path_buf(),
    ] {
        let p = pin(&p)?;
        pins.insert(p.path.to_string_lossy().into_owned(), p);
    }
    let result = json!({"schema":"hypothesis-rank-result/1","scored":scored,"excluded":excluded,"old_hypotheses":total_old,"expanded_hypotheses":total_new,"added":total_new-total_old,"added_panel":added_panel,"inheritance_exact":true,"class_change_counts_panel_linear":classes,"score_change_counts_prior_then_absent_present":class_score_changes,"changed_maxima":changed_maxima,"changed_winners":changed_winners,"policies":outputs,"historical_output_checks":historical,"cohort_vs_scoring_baseline_different_ids":baseline_differences,"source_artifacts_checked":checked,"source_identity_matches":reuse,"verified_pins":pins.len()});
    fs::write(dst.join("result.json"), serde_json::to_vec_pretty(&result)?)?;
    fs::write(dst.join("pins.json"), serde_json::to_vec_pretty(&pins)?)?;
    println!(
        "{}",
        json!({"scored":scored,"excluded":excluded,"old_hypotheses":total_old,"expanded_hypotheses":total_new,"added_panel":added_panel,"class_change_counts_panel_linear":classes,"policy_changes":changes,"source_artifacts_checked":checked,"verified_pins":pins.len()})
    );
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    fn h(s: &str, panel: bool, l: f64) -> Hypothesis {
        Hypothesis {
            sequence: s.into(),
            panel,
            linear: false,
            likelihood: l,
        }
    }
    fn policy() -> Policy {
        Policy {
            id: "test".into(),
            prior: Prior::Panel,
            lambda: 1.0,
            neural_deficit: Some(0.5),
            margin: 0.5,
        }
    }
    #[test]
    fn improving_added_panel_and_nonpanel() {
        let old = vec![h("N", false, 0.0), h("G", true, -0.25)];
        let mut new = old.clone();
        new.push(h("P", true, 0.75));
        assert_eq!(
            best(&new, "N", true, false).map(|h| h.sequence.as_str()),
            Some("P")
        );
        assert_eq!(choose("N", &new, &policy()).expect("choice").winner, "P");
        new.push(h("A", false, 2.0));
        assert_eq!(
            best(&new, "N", false, false).map(|h| h.sequence.as_str()),
            Some("A")
        );
        assert_eq!(choose("N", &new, &policy()).expect("choice").winner, "A");
        assert!(inherited(&old, &new).is_ok());
    }
    #[test]
    fn native_then_lexical_ties() {
        let p = Policy {
            lambda: 0.0,
            ..policy()
        };
        let tied = vec![h("Z", false, 0.0), h("A", false, 0.0)];
        assert_eq!(choose("Z", &tied, &p).expect("choice").winner, "Z");
        assert_eq!(
            best(&tied, "Z", false, false).map(|h| h.sequence.as_str()),
            Some("Z")
        );
        let tied = vec![h("Z", false, 0.0), h("B", true, 2.0), h("A", true, 2.0)];
        assert_eq!(choose("Z", &tied, &p).expect("choice").winner, "A");
        assert_eq!(
            best(&tied, "Z", true, false).map(|h| h.sequence.as_str()),
            Some("A")
        );
    }
    #[test]
    fn changed_inheritance_rejected() {
        let old = vec![h("N", false, 0.0)];
        let new = vec![h("N", false, f64::from_bits(1))];
        assert!(inherited(&old, &new).is_err());
    }
}
