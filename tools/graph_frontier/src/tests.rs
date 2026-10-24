use super::*;
use decision::Hypothesis;
use std::{
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
};

fn h(seq: &str, panel: bool, likelihood: f64) -> Hypothesis {
    Hypothesis {
        sequence: seq.into(),
        panel,
        linear: panel,
        likelihood,
    }
}
fn policy(lambda: f64, deficit: Option<f64>, margin: f64) -> Policy {
    Policy {
        id: "test".into(),
        prior: Prior::Panel,
        lambda,
        neural_deficit: deficit,
        margin,
    }
}

#[test]
fn native_first_then_lexical_ties() {
    let hs = vec![h("G", false, 0.0), h("A", true, -1.0), h("C", true, -1.0)];
    assert_eq!(
        choose("G", &hs, &policy(1.0, None, 0.0))
            .expect("choose")
            .native_exact_ties,
        2
    );
    assert_eq!(
        choose("G", &hs, &policy(1.0, None, 0.0))
            .expect("choose")
            .winner,
        "G"
    );
    assert_eq!(
        choose("G", &hs, &policy(2.0, None, 0.0))
            .expect("choose")
            .winner,
        "A"
    );
}
#[test]
fn neural_rescue_and_margin_boundaries() {
    let hs = vec![h("G", false, 0.0), h("A", true, -0.5)];
    assert!(
        !choose("G", &hs, &policy(1.0, Some(0.0), 0.5))
            .expect("choose")
            .edited
    );
    assert!(
        choose("G", &hs, &policy(1.0, Some(0.5), 0.5))
            .expect("choose")
            .edited
    );
    assert!(
        !choose("G", &hs, &policy(1.0_f64.next_down(), Some(0.5), 0.5))
            .expect("choose")
            .edited
    );
    assert!(
        choose("G", &hs, &policy(1.0, Some(0.5), 0.5))
            .expect("choose")
            .edited
    );
    assert!(
        !choose("G", &hs, &policy(0.75, Some(0.5), 0.5))
            .expect("choose")
            .edited
    );
    assert!(
        choose("G", &hs, &policy(0.75, Some(0.5), 0.1))
            .expect("choose")
            .edited
    );
}
#[test]
fn argmax_precedes_guard_and_reports_masking() {
    let hs = vec![h("G", false, 0.0), h("A", true, -1.0), h("C", false, 0.75)];
    let d = choose("G", &hs, &policy(2.0, Some(0.0), 0.5)).expect("choose");
    assert_eq!(d.winner, "A");
    assert!(!d.edited);
    assert_eq!(d.masked_feasible, 1);
}
#[test]
fn impossible_and_nonfinite_rejection() {
    let hs = vec![h("G", false, 0.0), h("A", true, f64::NEG_INFINITY)];
    assert_eq!(
        choose("G", &hs, &policy(10.0, None, 0.5))
            .expect("choose")
            .winner,
        "G"
    );
    for invalid in [f64::NAN, f64::INFINITY] {
        assert!(choose(
            "G",
            &[h("G", false, 0.0), h("A", true, invalid)],
            &policy(0.0, None, 0.5)
        )
        .is_err());
    }
    assert!(choose(
        "G",
        &[h("G", false, f64::NEG_INFINITY)],
        &policy(0.0, None, 0.5)
    )
    .is_err());
    assert!(policy(f64::INFINITY, None, 0.5).validate().is_err());
}
#[test]
fn indels_preserve_original_coordinates_and_outside_quality() {
    let native = Parent {
        seq: "AACCGGTT".into(),
        qual: "12345678".into(),
        reverse: false,
    };
    let mut edits = [
        Edit {
            start: 6,
            end: 7,
            sequence: "TT".into(),
        },
        Edit {
            start: 2,
            end: 4,
            sequence: "G".into(),
        },
    ];
    let out = splice(&native, &mut edits).expect("splice");
    assert_eq!(out.seq, "AAGGGTTT");
    assert_eq!(out.qual, "12!56!!8");
    assert!(splice(
        &native,
        &mut [
            Edit {
                start: 1,
                end: 4,
                sequence: "A".into()
            },
            Edit {
                start: 3,
                end: 5,
                sequence: "A".into()
            }
        ]
    )
    .is_err());
}
#[test]
fn margin_events_capture_output_missed_by_grid() {
    let a = events(
        "G",
        &[h("G", false, 0.0), h("A", true, -0.75)],
        Prior::Panel,
        0.5,
    )
    .expect("events");
    let b = events(
        "G",
        &[h("G", false, 0.0), h("A", true, -1.0)],
        Prior::Panel,
        0.5,
    )
    .expect("events");
    assert!(a.contains(&1.25) && b.contains(&1.5));
}
#[test]
fn frontier_interval_coverage_against_dense_random_scan() {
    let mut seed = 8141u64;
    for _ in 0..100 {
        let mut hs = vec![h("G", seed & 2 == 2, 0.0)];
        for seq in ["A", "C", "T"] {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            hs.push(h(
                seq,
                seed & 1 == 1,
                ((seed >> 32) % 2000) as f64 / 100.0 - 10.0,
            ));
        }
        let points = events("G", &hs, Prior::Panel, 0.5).expect("events");
        let samples = representatives(&points).expect("representatives");
        let states: BTreeSet<_> = samples
            .iter()
            .map(|(l, _)| {
                let d = choose("G", &hs, &policy(*l, None, 0.5)).expect("choose");
                (d.winner, d.edited)
            })
            .collect();
        for i in 0..4001 {
            let lambda = i as f64 / 100.0;
            let d = choose("G", &hs, &policy(lambda, None, 0.5)).expect("choose");
            assert!(states.contains(&(d.winner.clone(), d.edited)));
            if points.iter().all(|p| (lambda - p).abs() > 1e-10) {
                let left = points
                    .iter()
                    .copied()
                    .rfind(|p| *p < lambda)
                    .expect("left event");
                let right = points.iter().copied().find(|p| *p > lambda);
                let representative = samples
                    .iter()
                    .find(|(p, kind)| {
                        *kind != "boundary" && *p > left && right.is_none_or(|r| *p < r)
                    })
                    .expect("interval representative")
                    .0;
                let interval =
                    choose("G", &hs, &policy(representative, None, 0.5)).expect("interval choose");
                assert_eq!((d.winner, d.edited), (interval.winner, interval.edited));
            }
        }
    }
}
#[test]
fn numerical_domain_is_explicit() {
    let hs = [h("G", true, 0.0), h("A", true, -1.0)];
    assert_eq!(
        choose("G", &hs, &policy(1e20, None, 0.0))
            .expect("choose")
            .winner,
        "G"
    );
    let hs = [h("G", false, 0.0), h("T", true, 0.0), h("A", true, -1.0)];
    assert_eq!(
        choose("G", &hs, &policy(1.0, None, 0.5))
            .expect("choose")
            .winner,
        "T"
    );
    assert_eq!(
        choose("G", &hs, &policy(1e20, None, 0.5))
            .expect("choose")
            .winner,
        "A"
    );
    let symbolic =
        symbolic_terminal("G", &hs, &policy(1e20, None, 0.5)).expect("symbolic terminal");
    assert_eq!(symbolic.winner, "T");
    assert!(symbolic.edited);
    let hs = [h("G", false, -10000.0), h("A", true, -10000.5)];
    assert!(!choose("G", &hs, &policy(1.0_f64.next_down(), None, 0.5))
        .expect("choose")
        .objective_margin
        .is_nan());
    assert!(
        representatives(&[0.0, 1e10])
            .expect("representatives")
            .last()
            .expect("terminal")
            .0
            > 1e10
    );
}

#[test]
fn terminal_state_handles_native_prior_and_impossible_class() {
    let hs = [h("G", true, 0.0), h("A", true, 1.0), h("C", false, 2.0)];
    let d = symbolic_terminal("G", &hs, &policy(100.0, Some(0.0), 0.5)).expect("terminal");
    assert_eq!(d.winner, "A");
    assert!(d.edited);
    let hs = [
        h("G", false, 0.0),
        h("A", true, f64::NEG_INFINITY),
        h("C", false, 1.0),
    ];
    let d = symbolic_terminal("G", &hs, &policy(100.0, None, 0.5)).expect("terminal");
    assert_eq!(d.winner, "C");
    assert!(d.edited);
}

#[test]
fn saved_decimal_scores_round_trip_without_margin_tolerance() {
    let likelihoods: [f64; 2] = [194.943_638_381_66, 194.821_362_865_089];
    let encoded = serde_json::to_vec(&likelihoods).expect("serialize");
    let decoded: [f64; 2] = serde_json::from_slice(&encoded).expect("deserialize");
    assert_eq!(decoded.map(f64::to_bits), likelihoods.map(f64::to_bits));
    assert_eq!(decoded[0] - decoded[1], likelihoods[0] - likelihoods[1]);
}

struct Fixture {
    root: PathBuf,
    cohort: PathBuf,
    protocol: PathBuf,
}
impl Fixture {
    fn new(reverse: bool, excluded: bool) -> Self {
        static INDEX: AtomicUsize = AtomicUsize::new(0);
        let root = std::env::temp_dir().join(format!(
            "graph-frontier-test-{}-{}",
            std::process::id(),
            INDEX.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).expect("fixture directory");
        let stock = "AAAAAAAAAACCCCCCCCCCCGGGGGGGGGG";
        let alt = "AAAAAAAAAATCCCCCCCCCCGGGGGGGGGG";
        fs::write(root.join("parents"), "parent-1\n").expect("parents");
        fs::write(
            root.join("native.sam"),
            format!(
                "parent-1\t4\t*\t0\t0\t*\t*\t0\t0\t{stock}\t{}\n",
                "I".repeat(stock.len())
            ),
        )
        .expect("sam");
        let window = json!({"schema":"graph-prior-window/1","query_index":0,"read_id":"parent-1","contig":"chr1","ref_start":100,"ref_end":131,"core_start":110,"core_end":121,"read_start":0,"read_end":31,"chunk_index":0,"chunk_start":0,"chunk_end":31,"t_start":0,"t_end":80,"reverse":reverse,"stock":stock,"context":"AAAA","score_file":"a.scores"});
        fs::write(root.join("windows"), format!("{window}\n")).expect("windows");
        let forward = if reverse {
            input::revcomp(alt).expect("reverse")
        } else {
            alt.into()
        };
        let graph = json!({"schema":"hprc-local-paths/1","query_index":0,"query":{"sample":"GRCh38","contig":"chr1","start":100,"end":131},"reference":{"start":99,"end":132,"sequence":format!("A{forward}T")},"boundary_nodes":[],"walks":[{"is_reference":true,"copy_count":1,"cigar":"33M","sequence":format!("A{forward}T"),"both_anchors":true}]});
        fs::write(root.join("graph"), format!("{graph}\n")).expect("graph");
        let hs = vec![h(stock, false, 0.0), h(alt, true, -0.5)];
        let arms:Vec<_>=HISTORICAL.iter().map(|(name,lambda)| { let d=choose(stock,&hs,&policy(*lambda,Some(0.0),0.5)).expect("choose"); json!({"arm":format!("{name}.sam"),"lambda":lambda,"winner":d.winner,"winner_likelihood":d.winner_likelihood,"winner_graph_presence":d.winner_graph_presence,"objective_margin":d.objective_margin,"edited":d.edited,"edited_quality":"uncalibrated-!","edit_start":10,"edit_end":21}) }).collect();
        let decision = if excluded {
            json!({"query_index":0,"read_id":"parent-1","status":"excluded","reason":"fixture exclusion"})
        } else {
            json!({"query_index":0,"read_id":"parent-1","status":"scored","stock_likelihood":0.0,"score_sha256":"0".repeat(64),"hypotheses":[{"sequence":stock,"graph_presence":false,"likelihood":0.0},{"sequence":alt,"graph_presence":true,"likelihood":-0.5}],"arms":arms})
        };
        fs::write(root.join("decisions"), format!("{decision}\n")).expect("decisions");
        let cohort = root.join("cohort.json");
        let value = json!({"schema":"graph-frontier-cohort/1","role":"development","pins":{"parents":pin(&root.join("parents")).expect("pin"),"native_sam":pin(&root.join("native.sam")).expect("pin"),"windows":pin(&root.join("windows")).expect("pin"),"decisions":pin(&root.join("decisions")).expect("pin"),"graph_walks":pin(&root.join("graph")).expect("pin")}});
        fs::write(&cohort, serde_json::to_vec(&value).expect("serialize")).expect("cohort");
        let protocol = root.join("protocol.json");
        fs::write(&protocol,serde_json::to_vec(&json!({"schema":"graph-frontier-protocol/1","policies":[{"id":"linear","prior":"linear","lambda":1.0,"neural_deficit":null,"margin":0.5}],"frontier":{"enabled":true,"priors":["linear","panel"],"margin":0.5,"neural_deficit":null}})).expect("serialize")).expect("protocol");
        Self {
            root,
            cohort,
            protocol,
        }
    }
    fn repin(&self, field: &str, file: &str) {
        let mut c: serde_json::Value = read_json(&self.cohort).expect("cohort");
        c["pins"][field] =
            serde_json::to_value(pin(&self.root.join(file)).expect("pin")).expect("value");
        fs::write(&self.cohort, serde_json::to_vec(&c).expect("serialize")).expect("cohort");
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

#[test]
fn genuine_cli_contract_linear_forward_reverse_and_aliases() {
    for reverse in [false, true] {
        let f = Fixture::new(reverse, false);
        let out = f.root.join("out");
        emit(&f.cohort, &f.protocol, &out).expect("emit");
        assert!(out.join("complete.json").exists());
        let summary: serde_json::Value = read_json(&out.join("summary.json")).expect("summary");
        assert_eq!(summary["schema"], "graph-frontier-batch/1");
        assert_eq!(summary["parents"], 1);
        assert_eq!(summary["arms"][0]["edited_windows"], 1);
        assert_eq!(summary["artifacts"].as_array().expect("artifacts").len(), 2);
        let path = PathBuf::from(summary["arms"][0]["sam"]["path"].as_str().expect("path"));
        let sam = fs::read_to_string(path).expect("sam");
        assert!(sam.contains("AAAAAAAAAATCCCCCCCCCCGGGGGGGGGG"));
        assert!(sam.contains("IIIIIIIIII!!!!!!!!!!!IIIIIIIIII"));
        assert!(emit(&f.cohort, &f.protocol, &out).is_err());
    }
}
#[test]
fn excluded_windows_keep_original() {
    let f = Fixture::new(false, true);
    let out = f.root.join("out");
    emit(&f.cohort, &f.protocol, &out).expect("emit");
    let summary: serde_json::Value = read_json(&out.join("summary.json")).expect("summary");
    assert_eq!(summary["arms"][0]["edited_windows"], 0);
    assert_eq!(summary["artifacts"].as_array().expect("artifacts").len(), 1);
}
#[test]
fn corruption_retains_incomplete_attempt() {
    let f = Fixture::new(false, false);
    fs::write(f.root.join("decisions"), "altered").expect("corrupt");
    let out = f.root.join("out");
    assert!(emit(&f.cohort, &f.protocol, &out).is_err());
    assert!(out.join("attempt.json").exists());
    assert!(!out.join("complete.json").exists());
    assert!(!out.join("summary.json").exists());
}

#[test]
fn failed_producer_receipt_is_rejected() {
    let f = Fixture::new(false, false);
    fs::write(f.root.join("receipt"), br#"{"status":"finished","exit":1}"#).expect("receipt");
    let mut cohort: serde_json::Value = read_json(&f.cohort).expect("cohort");
    cohort["producer_receipt"] =
        serde_json::to_value(pin(&f.root.join("receipt")).expect("pin")).expect("value");
    fs::write(&f.cohort, serde_json::to_vec(&cohort).expect("serialize")).expect("write cohort");
    assert!(admit(&f.cohort).is_err());
}
#[test]
fn duplicate_missing_and_foreign_parents_rejected() {
    for contents in [
        "parent-1\nparent-1\n",
        "parent-1\nmissing-parent\n",
        "foreign\n",
    ] {
        let f = Fixture::new(false, false);
        fs::write(f.root.join("parents"), contents).expect("parents");
        f.repin("parents", "parents");
        assert!(admit(&f.cohort).is_err());
    }
}
#[test]
fn malformed_decision_null_native_and_foreign_schema_rejected() {
    for change in [
        "null-native",
        "null-alternative",
        "duplicate",
        "foreign",
        "nonfinite",
    ] {
        let f = Fixture::new(false, false);
        let mut d: serde_json::Value = read_json(&f.root.join("decisions")).expect("decision");
        match change {
            "null-native" => d["hypotheses"][0]["likelihood"] = serde_json::Value::Null,
            "null-alternative" => d["hypotheses"][1]["likelihood"] = serde_json::Value::Null,
            "duplicate" => {
                let h = d["hypotheses"][0].clone();
                d["hypotheses"].as_array_mut().expect("array").push(h);
            }
            "foreign" => d["read_id"] = json!("foreign"),
            _ => d["hypotheses"][0]["likelihood"] = json!("NaN"),
        };
        fs::write(
            f.root.join("decisions"),
            serde_json::to_vec(&d).expect("serialize"),
        )
        .expect("decision");
        f.repin("decisions", "decisions");
        if change == "null-alternative" {
            assert!(admit(&f.cohort).is_ok());
        } else {
            assert!(admit(&f.cohort).is_err());
        }
    }
}
