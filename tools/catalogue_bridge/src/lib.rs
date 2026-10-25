pub mod custody;
use anyhow::{ensure, Context, Result};
use custody::{check, checked, digest, fresh, pin, read, value_pin, verify_seal, write, Pin};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{BufRead, BufReader, Write},
    path::Path,
};
include!(concat!(env!("OUT_DIR"), "/compiled_sources.rs"));
const RULES: [(&str, f64); 4] = [
    ("neutral.sam", 0.0),
    ("graph-025.sam", 0.25),
    ("graph-050.sam", 0.5),
    ("graph-100.sam", 1.0),
];

pub fn sources() -> Result<Vec<Pin>> {
    COMPILED_SOURCES
        .iter()
        .map(|(p, b)| {
            let expected = Pin {
                path: Path::new(p).into(),
                size: b.len() as u64,
                sha256: digest(b),
            };
            check(&expected)?;
            Ok(expected)
        })
        .collect()
}
fn lines(path: &Path) -> Result<Vec<Value>> {
    BufReader::new(fs::File::open(path)?)
        .lines()
        .map(|l| Ok(serde_json::from_str(&l?)?))
        .collect()
}
fn index(rows: Vec<Value>) -> Result<BTreeMap<u64, Value>> {
    let mut out = BTreeMap::new();
    for row in rows {
        let i = row["query_index"].as_u64().context("query index")?;
        ensure!(out.insert(i, row).is_none(), "duplicate query index");
    }
    Ok(out)
}
fn row_hash(row: &Value) -> Result<String> {
    let mut v = row.clone();
    v.as_object_mut().context("decision object")?.remove("arms");
    Ok(digest(&serde_json::to_vec(&v)?))
}
fn update_inventory(hash: &mut Sha256, row: &Value) -> Result<()> {
    let mut v = row.clone();
    v.as_object_mut().context("row object")?.remove("arms");
    hash.update(serde_json::to_vec(&v)?);
    hash.update(b"\n");
    Ok(())
}
fn canonical_inventory(rows: &[Value]) -> Result<String> {
    Ok(digest(&serde_json::to_vec(rows)?))
}
fn hypothesis(row: &Value, stock: &str) -> Result<Vec<(String, bool, f64)>> {
    let mut seen = BTreeSet::new();
    let mut h = Vec::new();
    for v in row["hypotheses"].as_array().context("hypotheses missing")? {
        let seq = v["sequence"].as_str().context("sequence")?;
        ensure!(
            seq.len() >= 20
                && seq.bytes().all(|b| b"ACGT".contains(&b))
                && seq[..10] == stock[..10]
                && seq[seq.len() - 10..] == stock[stock.len() - 10..],
            "hypothesis sequence/anchors"
        );
        ensure!(seen.insert(seq.to_owned()), "duplicate hypothesis");
        let score = if v["likelihood"].is_null() {
            f64::NEG_INFINITY
        } else {
            v["likelihood"].as_f64().context("likelihood")?
        };
        ensure!(
            score == f64::NEG_INFINITY || score.is_finite(),
            "nonfinite likelihood"
        );
        h.push((
            seq.to_owned(),
            v["graph_presence"].as_bool().context("presence")?,
            score,
        ));
    }
    let native = h.iter().find(|x| x.0 == stock).context("native missing")?;
    ensure!(
        native.2.is_finite() && row["stock_likelihood"].as_f64() == Some(native.2),
        "invalid native likelihood"
    );
    Ok(h)
}
fn oracle<'a>(
    stock: &str,
    h: &'a [(String, bool, f64)],
    lambda: f64,
) -> Result<(&'a str, bool, f64)> {
    let native = h.iter().find(|v| v.0 == stock).context("oracle native")?;
    let objective = |v: &(String, bool, f64)| v.2 + if v.1 { lambda } else { 0.0 };
    let mut ranks: Vec<_> = h.iter().collect();
    ranks.sort_by(|a, b| {
        (if objective(a) == objective(b) {
            std::cmp::Ordering::Equal
        } else {
            objective(b).total_cmp(&objective(a))
        })
        .then_with(|| (b.0 == stock).cmp(&(a.0 == stock)))
        .then_with(|| a.0.cmp(&b.0))
    });
    let winner = ranks.first().context("empty H")?;
    let margin = objective(winner) - objective(native);
    Ok((
        &winner.0,
        winner.0 != stock && margin >= 0.5 && winner.2 >= native.2,
        margin,
    ))
}
fn arms(row: &Value, window: &Value) -> Result<Value> {
    let stock = window["stock"].as_str().context("stock")?;
    ensure!(stock.len() >= 20, "short stock");
    let h = hypothesis(row, stock)?;
    let mut out = Vec::new();
    for (name, lambda) in RULES {
        let (winner, edited, margin) = graph_prior::crf::choose(stock, &h, lambda)?;
        let independent = oracle(stock, &h, lambda)?;
        ensure!(
            (winner, edited, margin) == independent,
            "independent four-rule mismatch"
        );
        let selected = h
            .iter()
            .find(|v| v.0 == winner)
            .context("selected hypothesis")?;
        ensure!(
            selected.2.is_finite() && margin.is_finite(),
            "nonfinite winner/margin"
        );
        out.push(json!({"arm":name,"lambda":lambda,"winner":winner,"winner_likelihood":selected.2,"winner_graph_presence":selected.1,"objective_margin":margin,"edited":edited,"edited_quality":"uncalibrated-!","edit_start":window["read_start"].as_u64().context("start")?+10,"edit_end":window["read_end"].as_u64().context("end")?.checked_sub(10).context("end anchor")?}));
    }
    Ok(Value::Array(out))
}
fn prerequisites(manifest: &Value) -> Result<Value> {
    let p = checked(&manifest["prerequisites"])?;
    let v = read(&p.path)?;
    for pair in v["files"].as_array().context("prerequisites")? {
        let origin = checked(&pair["origin"])?;
        let snapshot = checked(&pair["snapshot"])?;
        ensure!(
            origin.size == snapshot.size && origin.sha256 == snapshot.sha256,
            "prerequisite snapshot changed"
        );
    }
    Ok(json!({"manifest":p,"closure":v}))
}
fn verify_manifest(path: &Path) -> Result<(Value, Value, Value, Value)> {
    sources()?;
    let manifest = read(path)?;
    ensure!(
        manifest["schema"] == "catalogue-bridge-input/1",
        "manifest schema"
    );
    let (cohort, original) = custody::original(&manifest)?;
    let catalogue = custody::catalogue(&manifest, &cohort)?;
    prerequisites(&manifest)?;
    Ok((manifest, cohort, original, catalogue))
}

pub fn transform(manifest_path: &Path, output: &Path, limit: usize) -> Result<Value> {
    ensure!(
        limit == 8 || limit == 331,
        "only eight-window checkpoint or full admission"
    );
    fs::create_dir(output)?;
    let output = fs::canonicalize(output)?;
    let compiled = sources()?;
    write(
        &output.join("attempt.json"),
        &json!({"schema":"catalogue-bridge-attempt/1","manifest":pin(manifest_path)?,"binary":pin(&std::env::current_exe()?)?,"argv":std::env::args().collect::<Vec<_>>(),"compiled_source_pins":compiled,"limit":limit}),
    )?;
    let (manifest, cohort, original, catalogue) = verify_manifest(manifest_path)?;
    let old = index(lines(&value_pin(&cohort["pins"]["decisions"])?.path)?)?;
    let windows = index(lines(&value_pin(&cohort["pins"]["windows"])?.path)?)?;
    ensure!(
        old.len() == 451 && windows.len() == 451,
        "original inventory count"
    );
    let selected: BTreeSet<u64> = if limit == 8 {
        let attempt = read(&value_pin(&manifest["catalogue_attempt"])?.path)?;
        attempt["checkpoint_order"]
            .as_array()
            .context("checkpoint order")?
            .iter()
            .map(|v| v.as_u64().context("checkpoint query"))
            .collect::<Result<_>>()?
    } else {
        old.iter()
            .filter(|(_, v)| v["status"] == "scored")
            .map(|(i, _)| *i)
            .collect()
    };
    ensure!(selected.len() == limit, "checkpoint membership");
    let mut out = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(output.join("decisions.jsonl"))?;
    let source = value_pin(&catalogue["seal"]["decisions"])?;
    let mut inventory = Vec::new();
    let mut original_inventory = Sha256::new();
    let mut transformed_inventory = Sha256::new();
    let mut scored = 0;
    let mut excluded = 0;
    let mut hypotheses = 0;
    let mut omitted = 0;
    let mut seen = BTreeSet::new();
    for line in BufReader::new(fs::File::open(&source.path)?).lines() {
        let line = line?;
        let mut row: Value = serde_json::from_str(&line)?;
        let query = row["query_index"].as_u64().context("query")?;
        ensure!(seen.insert(query), "duplicate catalogue query");
        let w = windows.get(&query).context("foreign catalogue query")?;
        let old = old.get(&query).context("missing original decision")?;
        ensure!(
            row["read_id"] == w["read_id"] && row["read_id"] == old["read_id"],
            "query/UUID mismatch"
        );
        let before = row_hash(&row)?;
        update_inventory(&mut original_inventory, &row)?;
        if row["status"] == "excluded" {
            ensure!(row == *old, "original exclusion changed");
            excluded += 1;
        } else {
            ensure!(
                row["status"] == "scored" && old["status"] == "scored" && row["arms"] == json!([]),
                "malformed catalogue scored row"
            );
            if selected.contains(&query) {
                hypotheses += row["hypotheses"].as_array().context("H")?.len();
                row["arms"] = arms(&row, w)?;
                scored += 1;
            } else {
                row = json!({"query_index":query,"read_id":row["read_id"],"status":"excluded","reason":"bridge_checkpoint_not_admitted"});
                omitted += 1;
            }
        }
        let after = row_hash(&row)?;
        update_inventory(&mut transformed_inventory, &row)?;
        ensure!(
            before == after
                || !selected.contains(&query) && row["reason"] == "bridge_checkpoint_not_admitted",
            "sequence/likelihood preservation failed"
        );
        inventory.push(json!({"query_index":query,"read_id":row["read_id"],"before_without_arms":before,"after_without_arms":after,"preserved":before==after}));
        serde_json::to_writer(&mut out, &row)?;
        writeln!(out)?;
    }
    out.sync_all()?;
    ensure!(
        seen.len() == 451 && scored == limit && excluded == 120 && omitted == 331 - limit,
        "incomplete transformed inventory"
    );
    if limit == 331 {
        ensure!(hypotheses == 3118978, "hypothesis accounting");
    }
    check(&source)?;
    let inventory_digest = canonical_inventory(&inventory)?;
    let evidence = json!({"schema":"catalogue-bridge-consistency/1","interpretation":"expanded-H policy consistency","original_H_complete_parent_parity_claimed":false,"rows":451,"scored":scored,"original_exclusions":excluded,"checkpoint_omissions":omitted,"parents":64,"hypotheses":hypotheses,"comparisons":scored*4,"weights":[0,0.25,0.5,1],"objective_margin":0.5,"neural_deficit":0,"quality":"uncalibrated-!","canonicalization":"serde_json sorted object keys, float_roundtrip f64; remove only arms; SHA256 of compact UTF8 JSON; inventory is ordered row digest records","original_inventory_sha256":format!("{:x}",original_inventory.finalize()),"transformed_inventory_sha256":format!("{:x}",transformed_inventory.finalize()),"inventory_digest":inventory_digest,"inventory":inventory});
    write(&output.join("consistency.json"), &evidence)?;
    write(
        &output.join("provenance.json"),
        &json!({"original":original,"catalogue":catalogue,"prerequisites":prerequisites(&manifest)?}),
    )?;
    let files = [
        "attempt.json",
        "decisions.jsonl",
        "consistency.json",
        "provenance.json",
    ]
    .iter()
    .map(|n| pin(&output.join(n)))
    .collect::<Result<Vec<_>>>()?;
    write(
        &output.join("complete.json"),
        &json!({"schema":"catalogue-bridge-transform/1","complete":true,"full_cohort":limit==331,"files":files,"decisions":pin(&output.join("decisions.jsonl"))?,"consistency":pin(&output.join("consistency.json"))?,"manifest":pin(manifest_path)?}),
    )?;
    fs::File::open(&output)?.sync_all()?;
    Ok(json!({"completion":pin(&output.join("complete.json"))?}))
}

fn parents(path: &Path, ids: &BTreeSet<String>) -> Result<BTreeMap<String, (String, String)>> {
    let mut rows = BTreeMap::new();
    for l in BufReader::new(fs::File::open(path)?).lines() {
        let l = l?;
        if l.starts_with('@') {
            continue;
        }
        let f: Vec<_> = l.split('\t').collect();
        ensure!(f.len() >= 11, "short SAM");
        ensure!(ids.contains(f[0]), "foreign parent");
        let flag: u16 = f[1].parse()?;
        if flag & 0x900 != 0 {
            continue;
        }
        ensure!(
            f[9] != "*"
                && !f[9].is_empty()
                && f[9].len() == f[10].len()
                && f[10].bytes().all(|b| (33..=126).contains(&b)),
            "incomplete parent SEQ/Q"
        );
        let mut seq = f[9].to_ascii_uppercase();
        let mut qual = f[10].to_owned();
        if flag & 16 != 0 {
            seq = seq
                .bytes()
                .rev()
                .map(|b| match b {
                    b'A' => Ok('T'),
                    b'C' => Ok('G'),
                    b'G' => Ok('C'),
                    b'T' => Ok('A'),
                    b'N' => Ok('N'),
                    _ => anyhow::bail!("invalid reverse DNA"),
                })
                .collect::<Result<String>>()?;
            qual = qual.chars().rev().collect();
        }
        ensure!(
            rows.insert(f[0].into(), (seq, qual)).is_none(),
            "duplicate primary parent"
        );
    }
    ensure!(
        rows.keys().cloned().collect::<BTreeSet<_>>() == *ids,
        "missing parents"
    );
    Ok(rows)
}
fn verify_preservation(source: &Path, transformed: &Path, consistency: &Value) -> Result<()> {
    let mut before = BufReader::new(fs::File::open(source)?).lines();
    let mut after = BufReader::new(fs::File::open(transformed)?).lines();
    let inventory = consistency["inventory"].as_array().context("inventory")?;
    let mut original_inventory = Sha256::new();
    let mut transformed_inventory = Sha256::new();
    for record in inventory {
        let a: Value = serde_json::from_str(&before.next().context("missing producer row")??)?;
        let b: Value = serde_json::from_str(&after.next().context("missing bridge row")??)?;
        ensure!(
            a["query_index"] == record["query_index"] && b["query_index"] == record["query_index"],
            "row order changed"
        );
        update_inventory(&mut original_inventory, &a)?;
        update_inventory(&mut transformed_inventory, &b)?;
        let ah = row_hash(&a)?;
        let bh = row_hash(&b)?;
        ensure!(
            record["before_without_arms"] == ah && record["after_without_arms"] == bh,
            "preservation digest mismatch"
        );
        ensure!(
            ah == bh
                || b["reason"] == "bridge_checkpoint_not_admitted"
                    && consistency["checkpoint_omissions"]
                        .as_u64()
                        .is_some_and(|n| n > 0),
            "changed likelihood/sequence"
        );
    }
    ensure!(
        before.next().is_none() && after.next().is_none(),
        "extra rows"
    );
    ensure!(
        consistency["inventory_digest"] == canonical_inventory(inventory)?,
        "whole inventory digest mismatch"
    );
    ensure!(
        consistency["original_inventory_sha256"] == format!("{:x}", original_inventory.finalize())
            && consistency["transformed_inventory_sha256"]
                == format!("{:x}", transformed_inventory.finalize()),
        "canonical inventory changed"
    );
    Ok(())
}

fn output_parity(
    directory: &Path,
    windows: &BTreeMap<u64, Value>,
    native: &BTreeMap<String, (String, String)>,
    ids: &BTreeSet<String>,
    arms: &[Value],
) -> Result<Value> {
    type Edit = (usize, usize, String);
    let mut edits: BTreeMap<String, BTreeMap<String, Vec<Edit>>> = BTreeMap::new();
    let mut exclusions: BTreeMap<String, usize> = BTreeMap::new();
    let mut seen = BTreeSet::new();
    for row in lines(&directory.join("decisions.jsonl"))? {
        let policy = row["policy_id"].as_str().context("policy id")?;
        let query = row["query_index"].as_u64().context("query")?;
        ensure!(
            seen.insert((policy.to_owned(), query)),
            "duplicate emitted decision"
        );
        let w = windows.get(&query).context("foreign emitted query")?;
        ensure!(
            row["read_id"] == w["read_id"],
            "emitted decision UUID mismatch"
        );
        if row["status"] == "excluded" {
            *exclusions.entry(policy.into()).or_default() += 1;
            continue;
        }
        if row["decision"]["edited"] == true {
            let winner = row["decision"]["winner"].as_str().context("winner")?;
            let start = w["read_start"].as_u64().context("read start")? as usize + 10;
            let end = w["read_end"].as_u64().context("read end")? as usize - 10;
            ensure!(winner.len() >= 20, "short winner");
            edits
                .entry(policy.into())
                .or_default()
                .entry(w["read_id"].as_str().context("parent")?.into())
                .or_default()
                .push((start, end, winner[10..winner.len() - 10].into()));
        }
    }
    ensure!(
        seen.len() == arms.len() * windows.len(),
        "incomplete policy/window ledger"
    );
    let mut checks = Vec::new();
    for arm in arms {
        let id = arm["id"].as_str().context("arm id")?;
        let observed = parents(&value_pin(&arm["sam"])?.path, ids)?;
        let mut expected = native.clone();
        if let Some(changes) = edits.get_mut(id) {
            for (parent, replacements) in changes {
                replacements.sort_by_key(|v| v.0);
                let original = native.get(parent).context("edit parent")?;
                let mut sequence = String::new();
                let mut quality = String::new();
                let mut cursor = 0;
                for (start, end, insert) in replacements {
                    ensure!(
                        cursor <= *start && *start <= *end && *end <= original.0.len(),
                        "overlapping parent edit"
                    );
                    sequence.push_str(&original.0[cursor..*start]);
                    quality.push_str(&original.1[cursor..*start]);
                    sequence.push_str(insert);
                    quality.extend(std::iter::repeat_n('!', insert.len()));
                    cursor = *end;
                }
                sequence.push_str(&original.0[cursor..]);
                quality.push_str(&original.1[cursor..]);
                expected.insert(parent.clone(), (sequence, quality));
            }
        }
        ensure!(
            expected == observed,
            "complete-parent SEQ/Q or excluded fallback differs {id}"
        );
        checks.push(json!({"policy_id":id,"parents":observed.len(),"complete_SEQ_Q_equal_independent_splice":true,"excluded_fallbacks":exclusions.get(id).copied().unwrap_or(0)}));
    }
    Ok(json!(checks))
}

pub fn admit(
    manifest_path: &Path,
    transform_dir: &Path,
    receipt_path: &Path,
    protocol: &Path,
    output: &Path,
) -> Result<Value> {
    fs::create_dir(output)?;
    let output = fs::canonicalize(output)?;
    let (manifest, mut cohort, original, catalogue) = verify_manifest(manifest_path)?;
    let complete = transform_dir.join("complete.json");
    let seal = verify_seal(&complete, "catalogue-bridge-transform/1")?;
    ensure!(
        seal["manifest"] == serde_json::to_value(pin(manifest_path)?)?,
        "transform manifest mismatch"
    );
    let attempt = read(&transform_dir.join("attempt.json"))?;
    ensure!(
        attempt["manifest"] == seal["manifest"]
            && attempt["compiled_source_pins"] == serde_json::to_value(sources()?)?,
        "transform source closure mismatch"
    );
    ensure!(
        checked(&attempt["binary"])? == pin(&std::env::current_exe()?)?,
        "transform binary mismatch"
    );
    let limit = if seal["full_cohort"] == true { 331 } else { 8 };
    let expected = json!([
        std::env::current_exe()?.to_string_lossy(),
        "transform",
        "--manifest",
        manifest_path.to_string_lossy(),
        "--output",
        transform_dir.to_string_lossy(),
        "--limit",
        limit.to_string()
    ]);
    let receipt = read(receipt_path)?;
    custody::recorder(&receipt, &expected, &pin(&complete)?)?;
    ensure!(attempt["argv"] == expected, "transform invocation mismatch");
    let consistency = read(&value_pin(&seal["consistency"])?.path)?;
    ensure!(
        consistency["comparisons"] == limit * 4 && consistency["scored"] == limit,
        "consistency count"
    );
    verify_preservation(
        &value_pin(&catalogue["seal"]["decisions"])?.path,
        &value_pin(&seal["decisions"])?.path,
        &consistency,
    )?;
    cohort["pins"]["decisions"] = seal["decisions"].clone();
    cohort["pins"]
        .as_object_mut()
        .context("cohort pins")?
        .remove("producer_receipt");
    cohort["producer_receipt"] = serde_json::to_value(pin(receipt_path)?)?;
    cohort["historical_sams"] = json!({});
    write(&output.join("cohort.json"), &cohort)?;
    let protocol_value = read(protocol)?;
    ensure!(
        protocol_value
            == serde_json::from_slice::<Value>(include_bytes!(
                "../../../config/compound-frontier-v1.json"
            ))?,
        "unregistered policy protocol"
    );
    fresh(&output.join("protocol.json"), &fs::read(protocol)?)?;
    let emitted = graph_frontier::emit(
        &output.join("cohort.json"),
        &output.join("protocol.json"),
        &output.join("candidates"),
    )?;
    let emitted_seal = verify_seal(
        &value_pin(&emitted["completion"])?.path,
        "graph-frontier-completion/1",
    )?;
    let summary = read(&output.join("candidates/summary.json"))?;
    let ids: BTreeSet<String> = fs::read_to_string(value_pin(&cohort["pins"]["parents"])?.path)?
        .lines()
        .map(str::to_owned)
        .collect();
    ensure!(ids.len() == 64, "parent universe");
    let native = parents(&value_pin(&cohort["pins"]["native_sam"])?.path, &ids)?;
    let baseline = parents(&value_pin(&original["scoring_baseline_sam"])?.path, &ids)?;
    let window_map = index(lines(&value_pin(&cohort["pins"]["windows"])?.path)?)?;
    let output_checks = output_parity(
        &output.join("candidates"),
        &window_map,
        &native,
        &ids,
        summary["arms"].as_array().context("arms")?,
    )?;
    let mut neutral = Vec::new();
    for arm in summary["arms"].as_array().context("emitted arms")? {
        let candidates = parents(&value_pin(&arm["sam"])?.path, &ids)?;
        if arm["prior"] == "none" {
            let diffs: Vec<_> = ids
                .iter()
                .filter(|id| native[*id] != candidates[*id])
                .cloned()
                .collect();
            if arm["id"] == "native-preservation" {
                ensure!(diffs.is_empty(), "native preservation changed SEQ/Q");
            }
            neutral.push(json!({"policy_id":arm["id"],"compared_parents":64,"different_from_cohort_native":diffs,"different_from_decoder_baseline":ids.iter().filter(|id|baseline[*id]!=candidates[*id]).collect::<Vec<_>>(),"explanation":"Expanded-H reference-free argmax may edit native cores. Native-preservation has a finite maximum margin to retain exact original parent SEQ/Q. All edits carry uncalibrated ! quality."}));
        }
    }
    let rule_pin = pin(&Path::new(env!("CARGO_MANIFEST_DIR")).join("../graph_prior/src/crf.rs"))?;
    let admission = json!({"schema":"compound-frontier-admission/1","scope":{"role":"development","parent_universe":"original registered HG002 development","admissible_candidate":false,"validation_or_HG005_selection":false,"full_cohort":seal["full_cohort"]},"original":original,"catalogue":catalogue,"bridge_producer":{"receipt":pin(receipt_path)?,"raw":receipt,"executable":attempt["binary"],"compiled_source_pins":sources()?,"manifest":pin(manifest_path)?},"outputs":{"cohort":pin(&output.join("cohort.json"))?,"decisions":seal["decisions"],"consistency":seal["consistency"],"bridge_completion":pin(&complete)?,"emitter_completion":emitted["completion"],"protocol":pin(&output.join("protocol.json"))?},"preservation":consistency,"rules":{"weights":[0,0.25,0.5,1],"choose_source":rule_pin,"consistency_comparisons":limit*4,"interpretation":"expanded-H policy consistency","original_H_complete_parent_SAM_parity_claimed":false},"prerequisites":prerequisites(&manifest)?,"neutral_checks":neutral,"complete_parent_output_checks":output_checks,"resource_receipts":receipt["files"],"downstream_batch_admission":"pending reference owner confirmation","engineering_only":true});
    write(&output.join("bridge-admission.json"), &admission)?;
    let files = ["cohort.json", "protocol.json", "bridge-admission.json"]
        .iter()
        .map(|n| pin(&output.join(n)))
        .collect::<Result<Vec<_>>>()?;
    write(
        &output.join("complete.json"),
        &json!({"schema":"compound-frontier-completion/1","complete":true,"full_cohort":seal["full_cohort"],"files":files,"emitter_completion":emitted["completion"],"emitter_seal":emitted_seal,"producer_receipt":pin(receipt_path)?,"transform_completion":pin(&complete)?}),
    )?;
    fs::File::open(&output)?.sync_all()?;
    Ok(json!({"completion":pin(&output.join("complete.json"))?}))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn independent_rules_ties_impossible_and_deficit() -> Result<()> {
        let native = "AAAAAAAAAAAAAAAAAAAA";
        for h in [
            vec![
                (native.into(), false, 2.0),
                ("AAAAAAAAAACAAAAAAAAA".into(), true, 2.0),
                ("AAAAAAAAAAGAAAAAAAAA".into(), true, f64::NEG_INFINITY),
            ],
            vec![
                (native.into(), false, 2.0),
                ("AAAAAAAAAACAAAAAAAAA".into(), true, 1.8),
                ("AAAAAAAAAAGAAAAAAAAA".into(), false, 2.7),
            ],
            vec![
                (native.into(), true, 2.0),
                ("AAAAAAAAAACAAAAAAAAA".into(), true, 2.0),
            ],
        ] {
            for (_, lambda) in RULES {
                assert_eq!(
                    graph_prior::crf::choose(native, &h, lambda)?,
                    oracle(native, &h, lambda)?
                );
            }
        }
        Ok(())
    }
    #[test]
    fn preservation_detects_one_ulp_and_sequence() -> Result<()> {
        let a = json!({"hypotheses":[{"sequence":"A","likelihood":1.0}],"arms":[]});
        let mut b = a.clone();
        b["arms"] = json!([1]);
        assert_eq!(row_hash(&a)?, row_hash(&b)?);
        b["hypotheses"][0]["likelihood"] = json!(f64::from_bits(1.0f64.to_bits() + 1));
        assert_ne!(row_hash(&a)?, row_hash(&b)?);
        b = a.clone();
        b["hypotheses"][0]["sequence"] = json!("T");
        assert_ne!(row_hash(&a)?, row_hash(&b)?);
        Ok(())
    }
}

#[cfg(test)]
mod rejection_tests {
    use super::*;
    fn directory(label: &str) -> Result<std::path::PathBuf> {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        let p = Path::new(env!("CARGO_MANIFEST_DIR")).join(format!(
            "../../results/compound-frontier/test-fixtures/{label}-{}-{stamp}",
            std::process::id()
        ));
        fs::create_dir_all(&p)?;
        Ok(fs::canonicalize(p)?)
    }
    #[test]
    fn complete_parent_orientation_and_invalid_membership() -> Result<()> {
        let d = directory("parents")?;
        let p = d.join("native.sam");
        let ids = BTreeSet::from(["parent".to_owned()]);
        fresh(&p, b"parent\t16\t*\t0\t0\t*\t*\t0\t0\tACGTTA\t!#$%&'\n")?;
        assert_eq!(
            parents(&p, &ids)?["parent"],
            ("TAACGT".into(), "'&%$#!".into())
        );
        for (name,bytes) in [("missing",&b"@HD\tVN:1.6\n"[..]),("foreign",&b"other\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\n"[..]),("quality",&b"parent\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!\n"[..]),("duplicate",&b"parent\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\nparent\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\n"[..])] {
            let p=d.join(name);fresh(&p,bytes)?;assert!(parents(&p,&ids).is_err(),"{name}");
        }
        Ok(())
    }
    #[test]
    fn invalid_native_and_impossible_alternative() -> Result<()> {
        let stock = "AAAAAAAAAAAAAAAAAAAA";
        let row = json!({"stock_likelihood":1.0,"hypotheses":[{"sequence":stock,"graph_presence":false,"likelihood":1.0},{"sequence":"AAAAAAAAAACAAAAAAAAAA","graph_presence":false,"likelihood":null}]});
        assert_eq!(hypothesis(&row, stock)?.len(), 2);
        let mut bad = row.clone();
        bad["hypotheses"][0]["likelihood"] = Value::Null;
        assert!(hypothesis(&bad, stock).is_err());
        bad = row.clone();
        bad["hypotheses"][0]["sequence"] = json!("TTTTTTTTTTTTTTTTTTTT");
        assert!(hypothesis(&bad, stock).is_err());
        Ok(())
    }
    #[test]
    fn coherently_repinned_sequence_and_score_changes_rejected() -> Result<()> {
        let d = directory("preservation")?;
        let source = json!({"query_index":0,"status":"scored","hypotheses":[{"sequence":"A","likelihood":1.0}],"arms":[]});
        let src = d.join("source.jsonl");
        fresh(&src, format!("{source}\n").as_bytes())?;
        for (name, mutation) in [
            ("sequence", json!("T")),
            ("likelihood", json!(f64::from_bits(1.0f64.to_bits() + 1))),
        ] {
            let mut changed = source.clone();
            changed["hypotheses"][0][name] = mutation;
            let dst = d.join(name);
            fresh(&dst, format!("{changed}\n").as_bytes())?;
            let inventory = vec![
                json!({"query_index":0,"before_without_arms":row_hash(&source)?,"after_without_arms":row_hash(&changed)?}),
            ];
            let evidence = json!({"inventory_digest":canonical_inventory(&inventory)?,"inventory":inventory,"checkpoint_omissions":0});
            assert!(verify_preservation(&src, &dst, &evidence).is_err());
        }
        Ok(())
    }
    #[test]
    fn incomplete_and_corrupted_completion_rejected() -> Result<()> {
        let d = directory("seal")?;
        let data = d.join("data");
        fresh(&data, b"original")?;
        let incomplete = d.join("incomplete");
        write(
            &incomplete,
            &json!({"schema":"test/1","complete":false,"data":pin(&data)?}),
        )?;
        assert!(verify_seal(&incomplete, "test/1").is_err());
        let complete = d.join("complete");
        write(
            &complete,
            &json!({"schema":"test/1","complete":true,"data":pin(&data)?}),
        )?;
        assert!(verify_seal(&complete, "test/1").is_ok());
        fs::write(data, b"corrupted")?;
        assert!(verify_seal(&complete, "test/1").is_err());
        Ok(())
    }
    #[test]
    fn excluded_fallback_preserves_every_quality() -> Result<()> {
        let d = directory("excluded")?;
        let sam = d.join("candidate.sam");
        fresh(&sam, b"parent\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!#\n")?;
        fresh(&d.join("decisions.jsonl"),b"{\"query_index\":0,\"read_id\":\"parent\",\"policy_id\":\"neutral\",\"status\":\"excluded\"}\n")?;
        let windows = BTreeMap::from([(0, json!({"read_id":"parent"}))]);
        let ids = BTreeSet::from(["parent".to_owned()]);
        let native = BTreeMap::from([("parent".to_owned(), ("AC".to_owned(), "!#".to_owned()))]);
        let arms = vec![json!({"id":"neutral","sam":pin(&sam)?})];
        assert!(output_parity(&d, &windows, &native, &ids, &arms).is_ok());
        fs::write(&sam, b"parent\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\n")?;
        let changed = vec![json!({"id":"neutral","sam":pin(&sam)?})];
        assert!(output_parity(&d, &windows, &native, &ids, &changed).is_err());
        Ok(())
    }
}
