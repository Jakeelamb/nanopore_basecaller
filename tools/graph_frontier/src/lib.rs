mod decision;
mod input;

use anyhow::{ensure, Context, Result};
use decision::{choose, events, representatives, symbolic_terminal, Policy, Prior};
use input::{admit, pin, read_json, Admitted, Parent, Pin, Protocol};
use serde::Serialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Write,
    path::Path,
};

#[derive(Clone, Debug)]
struct Edit {
    start: usize,
    end: usize,
    sequence: String,
}

fn splice(parent: &Parent, edits: &mut [Edit]) -> Result<Parent> {
    edits.sort_by_key(|e| e.start);
    let mut seq = String::new();
    let mut qual = String::new();
    let mut cursor = 0;
    for e in edits {
        ensure!(
            cursor <= e.start && e.start <= e.end && e.end <= parent.seq.len(),
            "overlapping/out-of-bounds edits"
        );
        seq.push_str(&parent.seq[cursor..e.start]);
        qual.push_str(&parent.qual[cursor..e.start]);
        seq.push_str(&e.sequence);
        qual.extend(std::iter::repeat_n('!', e.sequence.len()));
        cursor = e.end;
    }
    seq.push_str(&parent.seq[cursor..]);
    qual.push_str(&parent.qual[cursor..]);
    Ok(Parent {
        seq,
        qual,
        reverse: false,
    })
}

fn complete_sam(cohort: &Admitted, mut edits: BTreeMap<String, Vec<Edit>>) -> Result<Vec<u8>> {
    let mut sam = Vec::new();
    writeln!(sam, "@HD\tVN:1.6\tSO:unknown")?;
    for id in &cohort.ids {
        let native = &cohort.parents[id];
        let parent = if let Some(e) = edits.get_mut(id) {
            splice(native, e)?
        } else {
            native.clone()
        };
        writeln!(
            sam,
            "{}\t4\t*\t0\t0\t*\t*\t0\t0\t{}\t{}",
            id, parent.seq, parent.qual
        )?;
    }
    Ok(sam)
}

fn fresh_write(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut f = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    f.write_all(bytes)?;
    f.sync_all()?;
    Ok(())
}
fn write_json(path: &Path, value: &impl Serialize) -> Result<()> {
    fresh_write(path, &serde_json::to_vec_pretty(value)?)
}

const HISTORICAL: [(&str, f64); 4] = [
    ("neutral", 0.0),
    ("graph-025", 0.25),
    ("graph-050", 0.5),
    ("graph-100", 1.0),
];

fn historical_parity(cohort: &Admitted) -> Result<serde_json::Value> {
    let mut counts = Vec::new();
    if !cohort.historical.is_empty() {
        ensure!(
            cohort.historical.len() == 4
                && HISTORICAL
                    .iter()
                    .all(|(name, _)| cohort.historical.contains_key(*name)),
            "historical SAM registry must contain the four original arms"
        );
    }
    for (name, lambda) in HISTORICAL {
        let policy = Policy {
            id: name.into(),
            prior: Prior::Panel,
            lambda,
            neural_deficit: Some(0.0),
            margin: 0.5,
        };
        let mut edits: BTreeMap<String, Vec<Edit>> = BTreeMap::new();
        let mut comparisons = 0;
        for e in cohort.windows.iter().filter(|e| e.exclusion.is_none()) {
            ensure!(
                e.historical.len() == 4
                    && e.historical
                        .iter()
                        .map(|a| a.arm.as_str())
                        .collect::<BTreeSet<_>>()
                        .len()
                        == 4,
                "duplicate/missing historical decision arms"
            );
            let saved = e
                .historical
                .iter()
                .find(|a| a.arm == format!("{name}.sam"))
                .context("missing historical arm")?;
            let d = choose(&e.window.stock, &e.hypotheses, &policy)?;
            ensure!(
                saved.lambda == lambda
                    && saved.winner == d.winner
                    && saved.winner_likelihood == d.winner_likelihood
                    && saved.winner_graph_presence == d.winner_graph_presence
                    && saved.objective_margin == d.objective_margin
                    && saved.edited == d.edited
                    && saved.edit_start == e.window.read_start + 10
                    && saved.edit_end == e.window.read_end - 10
                    && saved.edited_quality == "uncalibrated-!",
                "historical decision parity failed query {} arm {}: saved {:?}; computed {:?}",
                e.window.query_index,
                name,
                saved,
                d
            );
            comparisons += 1;
            if d.edited {
                edits
                    .entry(e.window.read_id.clone())
                    .or_default()
                    .push(Edit {
                        start: e.window.read_start + 10,
                        end: e.window.read_end - 10,
                        sequence: d.winner[10..d.winner.len() - 10].into(),
                    });
            }
        }
        let sam = complete_sam(cohort, edits)?;
        let mut sam_parents = 0;
        if let Some(saved) = cohort.historical.get(name) {
            for line in std::str::from_utf8(&sam)?.lines().skip(1) {
                let fields: Vec<_> = line.split('\t').collect();
                let p = &saved[fields[0]];
                ensure!(
                    p.seq == fields[9] && p.qual == fields[10],
                    "historical full-parent SEQ/Q parity failed {} {}",
                    name,
                    fields[0]
                );
                sam_parents += 1;
            }
        }
        counts.push(json!({"arm":name,"decision_comparisons":comparisons,"complete_parent_seq_q_comparisons":sam_parents,"sam_sha256":format!("{:x}",Sha256::digest(&sam))}));
    }
    Ok(
        json!({"schema":"graph-frontier-historical-parity/1","decision_parity":true,"complete_parent_seq_q_parity":cohort.historical.len()==4,"arms":counts}),
    )
}

fn policies(protocol: &Protocol, cohort: &Admitted) -> Result<(Vec<Policy>, serde_json::Value)> {
    ensure!(
        protocol.schema == "graph-frontier-protocol/1",
        "protocol schema"
    );
    let mut policies = protocol.policies.clone();
    let mut inventory = Vec::new();
    for p in &policies {
        p.validate()?;
    }
    if let Some(frontier) = &protocol.frontier {
        let check = Policy {
            id: "frontier-validation".into(),
            prior: Prior::None,
            lambda: 0.0,
            neural_deficit: frontier.neural_deficit,
            margin: frontier.margin,
        };
        check.validate()?;
        ensure!(
            frontier.priors.iter().all(|p| *p != Prior::None),
            "frontier requires binary linear/panel prior"
        );
        ensure!(
            frontier
                .priors
                .iter()
                .map(|p| format!("{p:?}"))
                .collect::<BTreeSet<_>>()
                .len()
                == frontier.priors.len(),
            "duplicate frontier prior"
        );
        if frontier.enabled {
            for &prior in &frontier.priors {
                let mut points = vec![0.0];
                for e in cohort.windows.iter().filter(|e| e.exclusion.is_none()) {
                    points.extend(events(
                        &e.window.stock,
                        &e.hypotheses,
                        prior,
                        frontier.margin,
                    )?);
                }
                points.sort_by(f64::total_cmp);
                points.dedup_by(|a, b| *a == *b);
                let samples = representatives(&points)?;
                let terminal_lambda = samples.last().context("missing terminal sample")?.0;
                let terminal_policy = Policy {
                    id: "terminal-check".into(),
                    prior,
                    lambda: terminal_lambda,
                    neural_deficit: frontier.neural_deficit,
                    margin: frontier.margin,
                };
                let mut terminal_checks = Vec::new();
                for e in cohort.windows.iter().filter(|e| e.exclusion.is_none()) {
                    let symbolic =
                        symbolic_terminal(&e.window.stock, &e.hypotheses, &terminal_policy)?;
                    let finite = choose(&e.window.stock, &e.hypotheses, &terminal_policy)?;
                    terminal_checks.push(json!({"query_index":e.window.query_index,"symbolic":symbolic,"finite_winner":finite.winner,"finite_edited":finite.edited,"matches":symbolic.winner==finite.winner && symbolic.edited==finite.edited}));
                }
                let mut arm_samples = Vec::new();
                for (index, (lambda, kind)) in samples.into_iter().enumerate() {
                    let name = match prior {
                        Prior::Linear => "linear",
                        Prior::Panel => "panel",
                        Prior::None => unreachable!(),
                    };
                    let id = format!("frontier-{name}-{index:05}-{kind}");
                    policies.push(Policy {
                        id: id.clone(),
                        prior,
                        lambda,
                        neural_deficit: frontier.neural_deficit,
                        margin: frontier.margin,
                    });
                    arm_samples.push(json!({"policy_id":id,"lambda":lambda,"state":kind}));
                }
                inventory.push(json!({"prior":prior,"events":points,"samples":arm_samples,"terminal_symbolic_checks":terminal_checks}));
            }
        }
    }
    ensure!(
        !policies.is_empty()
            && policies
                .iter()
                .map(|p| &p.id)
                .collect::<BTreeSet<_>>()
                .len()
                == policies.len(),
        "empty/duplicate policy registry"
    );
    Ok((
        policies,
        json!({"schema":"graph-frontier-event-inventory/1","priors":inventory,"arithmetic":"Events enumerate the real-arithmetic binary-prior winner and objective-margin family on retained H. Emission uses literal f64 v1 objective addition, argmax then gates, native-first ties then lexical. Extreme-lambda score collapse and near-boundary cancellation limit equivalence to the real-arithmetic coverage claim. Terminal samples are finite interval representatives, not symbolic infinity."}),
    ))
}

#[derive(Serialize)]
struct Artifact {
    id: String,
    sam: Pin,
}

fn build_sources() -> Vec<Pin> {
    [
        ("Cargo.toml", include_bytes!("../Cargo.toml").as_slice()),
        ("Cargo.lock", include_bytes!("../Cargo.lock").as_slice()),
        ("src/main.rs", include_bytes!("main.rs").as_slice()),
        ("src/lib.rs", include_bytes!("lib.rs").as_slice()),
        ("src/input.rs", include_bytes!("input.rs").as_slice()),
        ("src/decision.rs", include_bytes!("decision.rs").as_slice()),
    ]
    .into_iter()
    .map(|(name, bytes)| Pin {
        path: Path::new(env!("CARGO_MANIFEST_DIR")).join(name),
        size: bytes.len() as u64,
        sha256: format!("{:x}", Sha256::digest(bytes)),
    })
    .collect()
}

pub fn emit(cohort_path: &Path, protocol_path: &Path, output: &Path) -> Result<serde_json::Value> {
    fs::create_dir(output).with_context(|| format!("exclusive new output {}", output.display()))?;
    let output = fs::canonicalize(output)?;
    let input_pin = pin(cohort_path)?;
    let protocol_pin = pin(protocol_path)?;
    write_json(
        &output.join("attempt.json"),
        &json!({"schema":"graph-frontier-attempt/1","cohort":input_pin,"protocol":protocol_pin,"binary":pin(&std::env::current_exe()?)?,"compiled_source_pins":build_sources()}),
    )?;
    let protocol: Protocol = read_json(protocol_path)?;
    let cohort = admit(cohort_path)?;
    let parity = historical_parity(&cohort)?;
    write_json(&output.join("parity.json"), &parity)?;
    let (policies, inventory) = policies(&protocol, &cohort)?;
    write_json(&output.join("frontier.json"), &inventory)?;
    let mut decisions = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(output.join("decisions.jsonl"))?;
    let mut arms = Vec::new();
    let mut artifacts: Vec<Artifact> = Vec::new();
    let mut dedup: BTreeMap<String, usize> = BTreeMap::new();
    let mut diagnostics = Vec::new();
    for policy in policies {
        let mut edits: BTreeMap<String, Vec<Edit>> = BTreeMap::new();
        let mut edited_windows = 0;
        let mut gates: BTreeMap<&str, usize> = BTreeMap::new();
        let mut masked = 0;
        let mut native_ties = 0;
        for e in &cohort.windows {
            if let Some(reason) = &e.exclusion {
                *gates.entry("excluded").or_default() += 1;
                serde_json::to_writer(
                    &mut decisions,
                    &json!({"policy_id":policy.id,"query_index":e.window.query_index,"read_id":e.window.read_id,"status":"excluded","reason":reason}),
                )?;
                writeln!(decisions)?;
                continue;
            }
            let d = choose(&e.window.stock, &e.hypotheses, &policy)?;
            *gates.entry(d.gate).or_default() += 1;
            masked += d.masked_feasible;
            native_ties += usize::from(d.gate == "native" && d.native_exact_ties > 0);
            if d.edited {
                edited_windows += 1;
                edits
                    .entry(e.window.read_id.clone())
                    .or_default()
                    .push(Edit {
                        start: e.window.read_start + 10,
                        end: e.window.read_end - 10,
                        sequence: d.winner[10..d.winner.len() - 10].into(),
                    });
            }
            serde_json::to_writer(
                &mut decisions,
                &json!({"policy_id":policy.id,"query_index":e.window.query_index,"read_id":e.window.read_id,"chunk_index":e.window.chunk_index,"status":"scored","decision":d}),
            )?;
            writeln!(decisions)?;
        }
        let edited_parents = edits.len();
        let sam = complete_sam(&cohort, edits)?;
        let hash = format!("{:x}", Sha256::digest(&sam));
        let index = if let Some(&index) = dedup.get(&hash) {
            index
        } else {
            let index = artifacts.len();
            let id = format!("seq-q-{hash}");
            let path = output.join(format!("{id}.sam"));
            fresh_write(&path, &sam)?;
            artifacts.push(Artifact {
                id,
                sam: pin(&path)?,
            });
            dedup.insert(hash, index);
            index
        };
        let artifact = &artifacts[index];
        diagnostics
            .push(json!({"policy_id":policy.id,"gates":gates,"masked_feasible_hypotheses":masked,"native_exact_tie_windows":native_ties}));
        arms.push(json!({"id":policy.id,"prior":policy.prior,"lambda":policy.lambda,"neural_deficit":policy.neural_deficit,"margin":policy.margin,"artifact_id":artifact.id,"sam":artifact.sam,"edited_windows":edited_windows,"edited_parents":edited_parents}));
    }
    decisions.sync_all()?;
    write_json(
        &output.join("diagnostics.json"),
        &json!({"schema":"graph-frontier-diagnostics/1","planned_windows":cohort.windows.len(),"scored_windows":cohort.windows.iter().filter(|e| e.exclusion.is_none()).count(),"excluded_windows":cohort.windows.iter().filter(|e| e.exclusion.is_some()).count(),"hypotheses":cohort.windows.iter().map(|e| e.hypotheses.len()).sum::<usize>(),"finite_hypotheses":cohort.windows.iter().flat_map(|e| &e.hypotheses).filter(|h| h.likelihood.is_finite()).count(),"arms":diagnostics}),
    )?;
    write_json(
        &output.join("summary.json"),
        &json!({"schema":"graph-frontier-batch/1","role":cohort.cohort.role,"parents":cohort.ids.len(),"parent_ids":cohort.ids,"arms":arms,"artifacts":artifacts,"cohort":input_pin,"protocol":protocol_pin,"input_pins":cohort.cohort,"input_custody":{"mode":"generic-pinned-inputs","producer_output_binding_verified":false,"qualification":"The coordinator must bind these pins to genuine producer outputs. The emitter checks provided hashes and successful receipt status, not that a producer emitted the pinned payloads."},"parity":pin(&output.join("parity.json"))?,"complete":true}),
    )?;
    let seals = [
        "attempt.json",
        "parity.json",
        "frontier.json",
        "decisions.jsonl",
        "diagnostics.json",
        "summary.json",
    ]
    .iter()
    .map(|name| pin(&output.join(name)))
    .collect::<Result<Vec<_>>>()?;
    write_json(
        &output.join("complete.json"),
        &json!({"schema":"graph-frontier-completion/1","complete":true,"files":seals,"artifacts":artifacts}),
    )?;
    Ok(json!({"completion":pin(&output.join("complete.json"))?}))
}

#[cfg(test)]
mod tests;
