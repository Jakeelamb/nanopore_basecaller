use anyhow::{ensure, Context, Result};
use flank_prior::*;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};
#[derive(Clone, Deserialize, Serialize)]
struct Window {
    query_index: usize,
    read_id: String,
    contig: String,
    ref_start: usize,
    ref_end: usize,
    core_start: usize,
    core_end: usize,
    read_start: usize,
    read_end: usize,
    reverse: bool,
    stock: String,
}
#[derive(Deserialize)]
struct Query {
    contig: String,
    start: usize,
    end: usize,
}
#[derive(Deserialize)]
struct Reference {
    start: usize,
    end: usize,
    sequence: String,
}
#[derive(Deserialize)]
struct Walk {
    both_anchors: bool,
    cigar: String,
    sequence: String,
}
#[derive(Deserialize)]
struct Graph {
    query_index: usize,
    query: Query,
    reference: Reference,
    walks: Vec<Walk>,
}
#[derive(Clone)]
struct Sam {
    id: String,
    reverse: bool,
    contig: String,
    start: usize,
    cigar: String,
    aligned: String,
    seq: String,
    qual: String,
}
fn read(path: &Path) -> Result<Value> {
    Ok(serde_json::from_reader(fs::File::open(path)?)?)
}
fn write(path: &Path, v: &Value) -> Result<()> {
    let mut f = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(path)?;
    serde_json::to_writer_pretty(&mut f, v)?;
    f.write_all(b"\n")?;
    Ok(())
}
fn pin(path: &Path) -> Result<Value> {
    let bytes = fs::read(path)?;
    Ok(json!({"path":fs::canonicalize(path)?,"size":bytes.len(),"sha256":hash(&bytes)}))
}
fn checked(v: &Value) -> Result<PathBuf> {
    let p = PathBuf::from(v["path"].as_str().context("pin path")?);
    ensure!(pin(&p)? == *v, "pin mismatch {}", p.display());
    Ok(p)
}
fn lines<T: serde::de::DeserializeOwned>(p: &Path) -> Result<Vec<T>> {
    BufReader::new(fs::File::open(p)?)
        .lines()
        .map(|x| Ok(serde_json::from_str(&x?)?))
        .collect()
}
fn sams(path: &Path, ids: &BTreeSet<String>) -> Result<BTreeMap<String, Sam>> {
    let mut out = BTreeMap::new();
    for line in BufReader::new(fs::File::open(path)?).lines() {
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
        ensure!(f[9] != "*" && f[9].len() == f[10].len(), "full SAM SEQ/Q");
        let reverse = flag & 16 != 0;
        let aligned = f[9].to_ascii_uppercase();
        let seq = if reverse {
            revcomp(&aligned)?
        } else {
            aligned.clone()
        };
        let qual = if reverse {
            f[10].chars().rev().collect()
        } else {
            f[10].into()
        };
        let s = Sam {
            id: f[0].into(),
            reverse,
            contig: f[2].into(),
            start: f[3].parse::<usize>()?.saturating_sub(1),
            cigar: f[5].into(),
            aligned,
            seq,
            qual,
        };
        ensure!(out.insert(s.id.clone(), s).is_none(), "duplicate primary");
    }
    ensure!(out.len() == ids.len(), "parent completeness");
    Ok(out)
}
fn plan(
    w: &Window,
    g: &Graph,
    s: &Sam,
    all: &[Window],
    mapped_hash: &str,
    window_hash: &str,
) -> Result<Value> {
    ensure!(
        s.reverse == w.reverse
            && s.contig == w.contig
            && s.seq.get(w.read_start..w.read_end) == Some(w.stock.as_str()),
        "window/native mismatch"
    );
    ensure!(
        g.query_index == w.query_index
            && g.query.contig == w.contig
            && g.query.start == w.ref_start
            && g.query.end == w.ref_end,
        "graph query mismatch"
    );
    let refs = [
        Span {
            start: w
                .ref_start
                .checked_sub(100)
                .context("left reference underflow")?,
            end: w.ref_start.checked_sub(50).context("guard underflow")?,
        },
        Span {
            start: w.ref_end + 50,
            end: w.ref_end + 100,
        },
    ];
    let mut extracted = Vec::new();
    let mut reads = Vec::new();
    for span in &refs {
        let (seq, q) = extract(&s.aligned, &s.cigar, s.start, span)?;
        ensure!(seq.len() <= 64, "native flank length cap");
        let q = if w.reverse {
            Span {
                start: s.seq.len() - q.end,
                end: s.seq.len() - q.start,
            }
        } else {
            q
        };
        for other in all.iter().filter(|x| x.read_id == w.read_id) {
            ensure!(
                !span.overlaps(&Span {
                    start: other.core_start,
                    end: other.core_end
                }),
                "reference flank overlaps planned edit {}",
                other.query_index
            );
            ensure!(
                !q.overlaps(&Span {
                    start: other.read_start + 10,
                    end: other.read_end - 10
                }),
                "read flank overlaps planned edit {}",
                other.query_index
            );
        }
        extracted.push(seq);
        reads.push(q);
    }
    let evidence = FlankEvidence {
        left: extracted[0].clone(),
        right: extracted[1].clone(),
        reference_intervals: refs.clone(),
        read_intervals: [reads[0].clone(), reads[1].clone()],
        mapped_sam_sha256: mapped_hash.into(),
        window_sha256: window_hash.into(),
    };
    ensure!(
        g.reference.end - g.reference.start == g.reference.sequence.len(),
        "graph reference span"
    );
    let forward = if w.reverse {
        revcomp(&w.stock)?
    } else {
        w.stock.clone()
    };
    let mut distinct = BTreeMap::<(String, String, String), WalkPrototype>::new();
    let mut panel = BTreeSet::new();
    for walk in g.walks.iter().filter(|x| x.both_anchors) {
        let (center, _) = extract(
            &walk.sequence,
            &walk.cigar,
            g.reference.start,
            &Span {
                start: w.ref_start,
                end: w.ref_end,
            },
        )?;
        ensure!(
            center.len() >= 20 && center.len() - 20 <= 32 && (center.len() - 20).abs_diff(21) <= 5,
            "panel core bounds"
        );
        ensure!(
            center[..10] == forward[..10]
                && center[center.len() - 10..] == forward[forward.len() - 10..],
            "panel anchor mismatch"
        );
        for i in 0..10 {
            let (l, _) = extract(
                &walk.sequence,
                &walk.cigar,
                g.reference.start,
                &Span {
                    start: w.ref_start + i,
                    end: w.ref_start + i + 1,
                },
            )?;
            let (r, _) = extract(
                &walk.sequence,
                &walk.cigar,
                g.reference.start,
                &Span {
                    start: w.ref_end - 10 + i,
                    end: w.ref_end - 9 + i,
                },
            )?;
            ensure!(l.len() == 1 && r.len() == 1, "gapped panel anchor");
        }
        let center = if w.reverse { revcomp(&center)? } else { center };
        panel.insert(center.clone());
        let (left, _) = extract(&walk.sequence, &walk.cigar, g.reference.start, &refs[0])?;
        let (right, _) = extract(&walk.sequence, &walk.cigar, g.reference.start, &refs[1])?;
        ensure!(
            left.len() <= 64 && right.len() <= 64,
            "graph flank length cap"
        );
        let source = hash(&serde_json::to_vec(
            &json!({"sequence":walk.sequence,"cigar":walk.cigar,"reference_start":g.reference.start}),
        )?);
        let p = WalkPrototype {
            left: left.clone(),
            center: center.clone(),
            right: right.clone(),
            source_walk_sha256: source,
            source_cigar: walk.cigar.clone(),
        };
        let key = (left, center, right);
        if let Some(old) = distinct.get_mut(&key) {
            if p.source_walk_sha256 < old.source_walk_sha256 {
                *old = p;
            }
        } else {
            distinct.insert(key, p);
        }
    }
    ensure!(
        !panel.is_empty() && panel.len() <= 16,
        "original panel cardinality"
    );
    ensure!(distinct.len() <= 256, "prototype cap");
    let prototypes: Vec<_> = distinct.into_values().collect();
    let comp = compatibility(&evidence, &prototypes)?;
    let informative =
        comp.mode == "conditioned" && comp.bonuses.values().any(|x| *x < 1.0) && panel.len() > 1;
    Ok(
        json!({"schema":"flank-prior-plan/1","query_index":w.query_index,"read_id":w.read_id,"reverse":w.reverse,"status":"eligible","informative":informative,"panel":panel,"evidence":evidence,"prototypes":prototypes,"compatibility":comp}),
    )
}
fn diagnostic(config: &Value, output: &Path, count: usize) -> Result<Value> {
    ensure!(count == 32 || count == 451, "predeclared index sets only");
    fs::create_dir(output)?;
    let cohort_path = Path::new(config["cohort"].as_str().context("cohort")?);
    let cohort = read(cohort_path)?;
    ensure!(cohort["role"] == "development", "development only");
    let windows_path = checked(&cohort["pins"]["windows"])?;
    let graph_path = checked(&cohort["pins"]["graph_walks"])?;
    let native_path = checked(&cohort["pins"]["native_sam"])?;
    let parents_path = checked(&cohort["pins"]["parents"])?;
    let receipt_path = Path::new(
        config["windows_receipt"]
            .as_str()
            .context("window receipt")?,
    );
    let receipt = read(receipt_path)?;
    let argv = receipt["argv"].as_array().context("argv")?;
    let si = argv
        .iter()
        .position(|v| v == "--sam")
        .context("mapped --sam")?;
    let mapped_path = Path::new(
        argv.get(si + 1)
            .and_then(Value::as_str)
            .context("mapped path")?,
    );
    let mapped_pin = pin(mapped_path)?;
    ensure!(
        mapped_pin["sha256"] == config["mapped_sam_sha256"],
        "mapped SAM pin"
    );
    let ids: BTreeSet<_> = fs::read_to_string(&parents_path)?
        .lines()
        .map(str::to_owned)
        .collect();
    ensure!(ids.len() == 64, "64 parents");
    let mapped = sams(mapped_path, &ids)?;
    let native = sams(&native_path, &ids)?;
    for (id, s) in &mapped {
        let n = native.get(id).context("native parent")?;
        ensure!(
            s.seq == n.seq && s.qual == n.qual,
            "mapped/source SEQ/Q mismatch"
        );
    }
    let all: Vec<Window> = lines(&windows_path)?;
    ensure!(all.len() == 451, "full planned windows");
    let mut window_hashes = BTreeMap::new();
    for line in BufReader::new(fs::File::open(&windows_path)?).lines() {
        let line = line?;
        let w: Window = serde_json::from_str(&line)?;
        ensure!(
            window_hashes
                .insert(w.query_index, hash(line.as_bytes()))
                .is_none(),
            "duplicate source window"
        );
    }
    let graphs: Vec<Graph> = lines(&graph_path)?;
    let mut graph = BTreeMap::new();
    for g in graphs {
        ensure!(
            graph.insert(g.query_index, g).is_none(),
            "duplicate graph index"
        );
    }
    let mut rows = Vec::new();
    let mut reasons = BTreeMap::<String, usize>::new();
    let mut eligible = 0;
    let mut informative = 0;
    let mut multicenter = 0;
    for index in 0..count {
        let result = (|| {
            let w = all
                .iter()
                .find(|w| w.query_index == index)
                .context("missing window")?;
            let g = graph.get(&index).context("missing graph")?;
            plan(
                w,
                g,
                mapped.get(&w.read_id).context("missing parent")?,
                &all,
                mapped_pin["sha256"].as_str().context("mapped hash")?,
                window_hashes.get(&index).context("window hash")?,
            )
        })();
        let row = match result {
            Ok(row) => {
                eligible += 1;
                if row["informative"] == true {
                    informative += 1
                }
                if row["panel"].as_array().is_some_and(|p| p.len() > 1) {
                    multicenter += 1
                }
                row
            }
            Err(e) => {
                let reason = e.to_string();
                *reasons.entry(reason.clone()).or_default() += 1;
                json!({"schema":"flank-prior-plan/1","query_index":index,"status":"abstain-binary","reason":reason})
            }
        };
        rows.push(row);
    }
    let mut f = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(output.join("plans.jsonl"))?;
    for row in &rows {
        serde_json::to_writer(&mut f, row)?;
        f.write_all(b"\n")?;
    }
    let result = json!({"schema":"flank-prior-diagnostic/1","query_indices":[0,count-1],"requested":count,"observed":rows.len(),"eligible":eligible,"eligible_multicenter":multicenter,"informative":informative,"abstained":count-eligible,"reasons":reasons,"parents_checked":64,"mapped_native_seq_q_equal":true,"inputs":{"cohort":pin(cohort_path)?,"mapped_sam":mapped_pin,"windows_receipt":pin(receipt_path)?,"graph":cohort["pins"]["graph_walks"],"windows":cohort["pins"]["windows"],"native":cohort["pins"]["native_sam"],"parents":cohort["pins"]["parents"]},"plans":pin(&output.join("plans.jsonl"))?});
    write(&output.join("summary.json"), &result)?;
    Ok(result)
}
#[derive(Clone)]
struct Change {
    start: usize,
    end: usize,
    insert: String,
}
fn oracle(stock: &str, h: &[Hypothesis], bonuses: &BTreeMap<String, f64>) -> Result<Value> {
    let mut rows: Vec<_> = h.iter().collect();
    let score = |x: &Hypothesis| x.likelihood + bonuses.get(&x.sequence).copied().unwrap_or(0.0);
    rows.sort_by(|a, b| {
        (if score(a) == score(b) {
            std::cmp::Ordering::Equal
        } else {
            score(b).total_cmp(&score(a))
        })
        .then_with(|| (b.sequence == stock).cmp(&(a.sequence == stock)))
        .then_with(|| a.sequence.cmp(&b.sequence))
    });
    let winner = rows.first().context("oracle empty")?;
    let n = h
        .iter()
        .find(|x| x.sequence == stock)
        .context("oracle native")?;
    let margin = score(winner) - score(n);
    let delta = winner.likelihood - n.likelihood;
    let gate = if winner.sequence == stock {
        "native"
    } else if margin < 0.5 {
        "objective_margin"
    } else if delta < -0.5 {
        "neural_deficit"
    } else {
        "edit"
    };
    Ok(
        json!({"winner":winner.sequence,"edited":gate=="edit","gate":gate,"objective_margin":margin,"neural_delta":delta}),
    )
}
fn splice_forward(s: &Sam, changes: &[Change]) -> Result<(String, String)> {
    let mut seq = s.seq.clone();
    let mut qual = s.qual.clone();
    let mut changes = changes.to_vec();
    changes.sort_by_key(|e| e.start);
    let mut cursor = 0;
    for e in &changes {
        ensure!(
            cursor <= e.start && e.start <= e.end && e.end <= s.seq.len(),
            "overlapping or invalid edit"
        );
        cursor = e.end;
    }
    for e in changes.iter().rev() {
        seq.replace_range(e.start..e.end, &e.insert);
        qual.replace_range(e.start..e.end, &"!".repeat(e.insert.len()));
    }
    Ok((seq, qual))
}
fn splice_independent(s: &Sam, changes: &[Change]) -> Result<(String, String)> {
    let mut sorted = changes.to_vec();
    sorted.sort_by_key(|e| e.start);
    let (mut seq, mut qual) = (String::new(), String::new());
    let mut cursor = 0;
    for e in sorted {
        ensure!(
            cursor <= e.start && e.end <= s.seq.len(),
            "independent splice bounds"
        );
        seq.push_str(&s.seq[cursor..e.start]);
        seq.push_str(&e.insert);
        qual.push_str(&s.qual[cursor..e.start]);
        qual.push_str(&"!".repeat(e.insert.len()));
        cursor = e.end;
    }
    seq.push_str(&s.seq[cursor..]);
    qual.push_str(&s.qual[cursor..]);
    Ok((seq, qual))
}
fn emit(config: &Value, output: &Path, plans_path: &Path) -> Result<Value> {
    fs::create_dir(output)?;
    let cohort_path = Path::new(config["cohort"].as_str().context("cohort")?);
    let cohort = read(cohort_path)?;
    ensure!(cohort["role"] == "development", "development only");
    let bridge_path = Path::new(
        config["bridge_completion"]
            .as_str()
            .context("bridge completion")?,
    );
    ensure!(
        pin(bridge_path)?["sha256"] == config["bridge_completion_sha256"],
        "reviewed bridge completion changed"
    );
    let bridge = read(bridge_path)?;
    ensure!(
        bridge["complete"] == true && bridge["full_cohort"] == true,
        "bridge incomplete"
    );
    checked(&bridge["producer_receipt"])?;
    let transform = read(&checked(&bridge["transform_completion"])?)?;
    let decisions = checked(&cohort["pins"]["decisions"])?;
    ensure!(
        transform["decisions"] == cohort["pins"]["decisions"],
        "bridge decision ancestry"
    );
    let parents_path = checked(&cohort["pins"]["parents"])?;
    let native_path = checked(&cohort["pins"]["native_sam"])?;
    let windows_path = checked(&cohort["pins"]["windows"])?;
    let ids: BTreeSet<_> = fs::read_to_string(&parents_path)?
        .lines()
        .map(str::to_owned)
        .collect();
    ensure!(ids.len() == 64, "full parent inventory");
    let native = sams(&native_path, &ids)?;
    let all: Vec<Window> = lines(&windows_path)?;
    let windows: BTreeMap<_, _> = all.iter().map(|w| (w.query_index, w)).collect();
    ensure!(windows.len() == 451, "window inventory");
    let diagnostic_summary = read(&plans_path.with_file_name("summary.json"))?;
    let diagnostic_completion = read(&plans_path.with_file_name("complete.json"))?;
    checked(&diagnostic_completion["summary"])?;
    ensure!(
        diagnostic_summary["plans"] == pin(plans_path)?
            && diagnostic_summary["requested"] == 451
            && diagnostic_summary["parents_checked"] == 64
            && diagnostic_summary["mapped_native_seq_q_equal"] == true
            && diagnostic_summary["inputs"]["cohort"] == pin(cohort_path)?,
        "unqualified full diagnostic"
    );
    let rows: Vec<Value> = lines(plans_path)?;
    ensure!(rows.len() == 451, "complete451 plan inventory");
    let mut plans = BTreeMap::new();
    for p in rows {
        let index = p["query_index"].as_u64().context("plan index")? as usize;
        ensure!(plans.insert(index, p).is_none(), "duplicate plan");
    }
    let arm_names = [
        "native",
        "reference-free",
        "binary-panel",
        "flank-conditioned",
    ];
    let mut changes = BTreeMap::<String, BTreeMap<String, Vec<Change>>>::new();
    let mut counts = BTreeMap::<String, usize>::new();
    let mut inventory = Vec::new();
    let mut file = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(output.join("decisions.jsonl"))?;
    let (mut scored, mut excluded, mut hypotheses, mut informative, mut changed) = (0, 0, 0, 0, 0);
    let mut seen = BTreeSet::new();
    for line in BufReader::new(fs::File::open(&decisions)?).lines() {
        let line = line?;
        let row: Value = serde_json::from_str(&line)?;
        let index = row["query_index"].as_u64().context("decision index")? as usize;
        ensure!(seen.insert(index), "duplicate decision");
        let w = windows.get(&index).context("foreign decision")?;
        ensure!(row["read_id"] == w.read_id, "decision UUID");
        let plan = plans.get(&index).context("missing plan")?;
        if row["status"] == "excluded" {
            excluded += 1;
            for name in arm_names {
                serde_json::to_writer(
                    &mut file,
                    &json!({"query_index":index,"read_id":w.read_id,"policy_id":name,"status":"excluded","source_reason":row["reason"]}),
                )?;
                file.write_all(b"\n")?;
            }
            continue;
        }
        ensure!(row["status"] == "scored", "unknown decision status");
        scored += 1;
        let mut h = Vec::new();
        let mut panel = BTreeMap::new();
        let mut seen_h = BTreeSet::new();
        for x in row["hypotheses"].as_array().context("hypotheses")? {
            let s = x["sequence"].as_str().context("sequence")?;
            ensure!(
                s.len() >= 20
                    && s[..10] == w.stock[..10]
                    && s[s.len() - 10..] == w.stock[w.stock.len() - 10..],
                "hypothesis anchors"
            );
            ensure!(seen_h.insert(s.to_owned()), "duplicate H");
            if x["graph_presence"] == true {
                panel.insert(s.to_owned(), 1.0);
            }
            let likelihood = if x["likelihood"].is_null() {
                f64::NEG_INFINITY
            } else {
                x["likelihood"].as_f64().context("likelihood")?
            };
            h.push(Hypothesis {
                sequence: s.into(),
                likelihood,
            });
        }
        hypotheses += h.len();
        ensure!(
            h.iter()
                .find(|x| x.sequence == w.stock)
                .is_some_and(|x| Some(x.likelihood) == row["stock_likelihood"].as_f64()),
            "native score pin"
        );
        let mut bonuses = panel.clone();
        let mut mode = "extraction-abstain-binary".to_owned();
        if plan["status"] == "eligible" {
            let evidence: FlankEvidence = serde_json::from_value(plan["evidence"].clone())?;
            let prototypes: Vec<WalkPrototype> =
                serde_json::from_value(plan["prototypes"].clone())?;
            let c = compatibility(&evidence, &prototypes)?;
            ensure!(
                serde_json::to_value(&c)? == plan["compatibility"],
                "frozen compatibility mismatch"
            );
            ensure!(
                c.bonuses.keys().collect::<BTreeSet<_>>() == panel.keys().collect::<BTreeSet<_>>(),
                "admitted panel membership mismatch"
            );
            bonuses = c.bonuses;
            mode = c.mode;
            if plan["informative"] == true {
                informative += 1
            }
        }
        let neutral = BTreeMap::new();
        let mut outcomes = Vec::new();
        for name in arm_names {
            let b = match name {
                "native" | "reference-free" => &neutral,
                "binary-panel" => &panel,
                _ => &bonuses,
            };
            let mut d = choose(&w.stock, &h, b)?;
            let oracle = oracle(&w.stock, &h, b)?;
            ensure!(
                oracle["winner"] == d.winner
                    && oracle["gate"] == d.gate
                    && oracle["objective_margin"].as_f64() == Some(d.objective_margin),
                "independent argmax/gate mismatch"
            );
            if name == "native" {
                d.edited = false;
                d.gate = "disabled-edit-identity".into();
            }
            if d.edited {
                *counts.entry(name.into()).or_default() += 1;
                let insert = d.winner[10..d.winner.len() - 10].to_owned();
                changes
                    .entry(name.into())
                    .or_default()
                    .entry(w.read_id.clone())
                    .or_default()
                    .push(Change {
                        start: w.read_start + 10,
                        end: w.read_end - 10,
                        insert,
                    });
            }
            let call = if d.edited {
                d.winner.clone()
            } else {
                w.stock.clone()
            };
            outcomes.push(call);
            serde_json::to_writer(
                &mut file,
                &json!({"schema":"flank-prior-decision/1","query_index":index,"read_id":w.read_id,"policy_id":name,"status":"scored","conditioning_mode":mode,"hypotheses":h.len(),"source_row_sha256":hash(line.as_bytes()),"decision":d}),
            )?;
            file.write_all(b"\n")?;
        }
        if outcomes[2] != outcomes[3] {
            changed += 1
        }
        inventory.push(json!({"query_index":index,"hypotheses":h.len(),"source_row_sha256":hash(line.as_bytes()),"source_hypotheses_sha256":hash(&serde_json::to_vec(&row["hypotheses"])?),"complete_H_retained":true}));
    }
    ensure!(
        seen.len() == 451 && scored == 331 && excluded == 120 && hypotheses == 3118978,
        "expanded-H completeness"
    );
    file.sync_all()?;
    let mut arms = Vec::new();
    for name in arm_names {
        let path = output.join(format!("{name}.sam"));
        let mut out = fs::OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&path)?;
        writeln!(out, "@HD\tVN:1.6\tSO:unknown")?;
        let mut parent_checks = Vec::new();
        for (id, s) in &native {
            let edits = changes
                .get(name)
                .and_then(|x| x.get(id))
                .cloned()
                .unwrap_or_default();
            let a = splice_forward(s, &edits)?;
            ensure!(
                a == splice_independent(s, &edits)?,
                "independent complete parent splice mismatch"
            );
            ensure!(a.0.len() == a.1.len(), "full parent SEQ/Q length");
            if name == "native" {
                ensure!(a.0 == s.seq && a.1 == s.qual, "disabled identity mismatch");
            }
            writeln!(out, "{id}\t4\t*\t0\t0\t*\t*\t0\t0\t{}\t{}", a.0, a.1)?;
            parent_checks.push(json!({"read_id":id,"edits":edits.len(),"sequence_sha256":hash(a.0.as_bytes()),"quality_sha256":hash(a.1.as_bytes()),"length":a.0.len(),"independent_splice_equal":true}));
        }
        out.sync_all()?;
        let parsed = sams(&path, &ids)?;
        for check in &parent_checks {
            let s = parsed
                .get(check["read_id"].as_str().context("parent check")?)
                .context("missing emitted parent")?;
            ensure!(
                check["sequence_sha256"] == hash(s.seq.as_bytes())
                    && check["quality_sha256"] == hash(s.qual.as_bytes()),
                "readback SEQ/Q mismatch"
            );
        }
        arms.push(json!({"id":name,"sam":pin(&path)?,"edited_windows":counts.get(name).copied().unwrap_or(0),"parents":parent_checks}));
    }
    checked(&cohort["pins"]["decisions"])?;
    let old_summary = read(&checked(
        bridge["emitter_seal"]["files"]
            .as_array()
            .context("bridge files")?
            .iter()
            .find(|v| {
                v["path"]
                    .as_str()
                    .is_some_and(|s| s.ends_with("/summary.json"))
            })
            .context("bridge summary")?,
    )?)?;
    let mut original_parity = Vec::new();
    for (ours, old) in [
        ("native", "native-preservation"),
        ("reference-free", "compound-reference-free"),
        ("binary-panel", "compound-panel-100"),
    ] {
        let old_arm = old_summary["arms"]
            .as_array()
            .context("old arms")?
            .iter()
            .find(|v| v["id"] == old)
            .context("old arm")?;
        let prior = sams(&checked(&old_arm["sam"])?, &ids)?;
        let current = sams(&output.join(format!("{ours}.sam")), &ids)?;
        for id in &ids {
            ensure!(
                prior[id].seq == current[id].seq && prior[id].qual == current[id].qual,
                "complete original arm parity {ours} {id}"
            );
        }
        original_parity
            .push(json!({"arm":ours,"original":old_arm["sam"],"full64_seq_q_equal":true}));
    }
    let summary = json!({"schema":"flank-prior-emission/1","role":"development","parents":64,"windows":451,"scored":scored,"excluded":excluded,"hypotheses":hypotheses,"informative_admitted_windows":informative,"flank_vs_binary_changed_windows":changed,"complete_H_retained":true,"full_parent_seq_q_readback":true,"disabled_edit_identity":true,"original_arm_parity":original_parity,"independent_splice_checks":true,"independent_argmax_gate_checks":true,"arms":arms,"inputs":{"cohort":pin(cohort_path)?,"bridge_completion":pin(bridge_path)?,"decisions":cohort["pins"]["decisions"],"plans":pin(plans_path)?,"windows":cohort["pins"]["windows"],"native":cohort["pins"]["native_sam"]},"row_inventory":inventory,"quality":"edited bases ! are uncalibrated","biological_claim":"unobserved; call changes are not accuracy evidence"});
    write(&output.join("summary.json"), &summary)?;
    Ok(summary)
}

fn run() -> Result<()> {
    let a: Vec<_> = std::env::args().collect();
    ensure!(
        (a.len() == 5 && a[1] == "diagnostic") || (a.len() == 5 && a[1] == "emit"),
        "flank-prior diagnostic CONFIG NEWDIR 32|451; flank-prior emit CONFIG NEWDIR PLANS"
    );
    let config = read(Path::new(&a[2]))?;
    ensure!(
        config["schema"] == "flank-prior-protocol/1"
            && config["weight"] == 1.0
            && config["margin"] == 0.5
            && config["neural_deficit"] == 0.5
            && config["role"] == "development"
            && config["guard_reference_bases"] == 50
            && config["flank_reference_bases"] == 50
            && config["max_flank_bases"] == 64
            && config["max_prototypes"] == 256,
        "frozen protocol"
    );
    let output = Path::new(&a[3]);
    let v = if a[1] == "emit" {
        emit(&config, output, Path::new(&a[4]))?
    } else {
        diagnostic(&config, output, a[4].parse()?)?
    };
    write(
        &output.join("complete.json"),
        &json!({"schema":"flank-prior-producer-completion/1","unit":a[1],"complete":true,"summary":pin(&output.join("summary.json"))?,"binary":pin(&std::env::current_exe()?)?,"argv":a,"config":pin(Path::new(&a[2]))?,"compiled_sources":[{"path":"src/lib.rs","sha256":hash(include_bytes!("lib.rs"))},{"path":"src/main.rs","sha256":hash(include_bytes!("main.rs"))},{"path":"Cargo.toml","sha256":hash(include_bytes!("../Cargo.toml"))},{"path":"Cargo.lock","sha256":hash(include_bytes!("../Cargo.lock"))}]}),
    )?;
    println!(
        "{}",
        json!({"completion":pin(&output.join("complete.json"))?,"summary":pin(&output.join("summary.json"))?,"requested":v["requested"],"eligible":v["eligible"],"informative":v["informative"],"reasons":v["reasons"],"hypotheses":v["hypotheses"],"flank_vs_binary_changed_windows":v["flank_vs_binary_changed_windows"]})
    );
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("flank-prior: {e:#}");
        std::process::exit(1)
    }
}
