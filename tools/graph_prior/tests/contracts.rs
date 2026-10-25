use graph_prior::{crf, decoder, graph, native, planner, scores};
use serde_json::json;
use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
};
static NEXT: AtomicUsize = AtomicUsize::new(0);
fn tmp() -> PathBuf {
    let p = std::env::temp_dir().join(format!(
        "graph-prior-contracts-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&p).expect("fresh fixture");
    p
}
fn enumerate(sc: &[f64], t: usize, k: usize, s: usize, y: &[u8], blank: f64) -> f64 {
    fn visit(sc: &[f64], t: usize, k: usize, s: usize, y: &[u8], blank: f64, weight: f64) -> f64 {
        if t == 0 {
            return if y.is_empty() { weight.exp() } else { 0.0 };
        }
        let c = 1 << (2 * (k + 1));
        let mut v = visit(&sc[c..], t - 1, k, s, y, blank, weight + blank);
        if let Some((&b, tail)) = y.split_first() {
            let (n, i) = crf::transition(s, b, k).expect("transition");
            v += visit(&sc[c..], t - 1, k, n, tail, blank, weight + sc[i]);
        }
        v
    }
    visit(sc, t, k, s, y, blank, 0.0).ln()
}
#[test]
fn exact_dp_matches_exhaustive_stay_step_paths() {
    for t in 0..=5 {
        let values: Vec<_> = (0..t * 16)
            .map(|i| ((i * 17 % 31) as f64 - 15.0) / 7.0)
            .collect();
        for s in 0..4 {
            for y in ["", "A", "AA", "AC", "GTA", "TTTT", "ACGTAC"] {
                let dp = crf::likelihood(&values, t, 1, s, y.as_bytes(), 0.4).expect("DP");
                let exhaustive = enumerate(&values, t, 1, s, y.as_bytes(), 0.4);
                assert!(
                    dp == exhaustive || (dp - exhaustive).abs() < 1e-11,
                    "T={t} state={s} y={y}: {dp} != {exhaustive}"
                );
            }
        }
    }
}
#[test]
fn transition_indices_match_native_encoding() {
    assert_eq!(
        crf::transition(27, b'T', 4).expect("ACGT -> CGTT"),
        (111, 444)
    );
    assert_eq!(
        crf::transition(111, b'G', 4).expect("CGTT -> GTTG"),
        (190, 761)
    );
    assert!(crf::state(b"AC", 4).is_err());
}
fn signal(target: &str, context: &str) -> Vec<f64> {
    let mut values = vec![-8.0; (target.len() + 2) * 1024];
    let mut state = crf::state(context.as_bytes(), 4).expect("context");
    for (t, b) in target.bytes().enumerate() {
        let (next, i) = crf::transition(state, b, 4).expect("step");
        values[t * 1024 + i] = 8.0;
        state = next;
    }
    values
}
#[test]
fn private_snv_insertion_deletion_escape_wrong_graph() {
    let stock = "ACGTACGTACTGCATGACTGACGTACGTACGTACGTACGTAC";
    let context = "TGCA";
    let mut wrong = stock.as_bytes().to_vec();
    wrong[19] = if wrong[19] == b'A' { b'C' } else { b'A' };
    let panel = BTreeSet::from([String::from_utf8(wrong).expect("DNA")]);
    let h = crf::hypotheses(stock, &panel).expect("H");
    let mut snv = stock.as_bytes().to_vec();
    snv[24] = if snv[24] == b'T' { b'G' } else { b'T' };
    let mut ins = stock.as_bytes().to_vec();
    ins.insert(20, b'C');
    let mut del = stock.as_bytes().to_vec();
    del.remove(20);
    for target in [snv, ins, del] {
        let target = String::from_utf8(target).expect("DNA");
        assert!(h.contains_key(&target));
        assert!(!panel.contains(&target));
        let values = signal(&target, context);
        let scored: Vec<_> = h
            .iter()
            .map(|(seq, g)| {
                (
                    seq.clone(),
                    *g,
                    crf::likelihood(
                        &values,
                        target.len() + 2,
                        4,
                        crf::state(context.as_bytes(), 4).expect("context"),
                        seq.as_bytes(),
                        0.0,
                    )
                    .expect("score"),
                )
            })
            .collect();
        for lambda in [0.0, 0.25, 0.5, 1.0] {
            let (winner, edited, _) = crf::choose(stock, &scored, lambda).expect("choose");
            assert_eq!(winner, target);
            assert!(edited);
        }
    }
}
#[test]
fn objective_gates_and_stock_ties() {
    let h = vec![("stock".into(), false, 3.0), ("panel".into(), true, 2.9)];
    assert!(!crf::choose("stock", &h, 1.0).expect("gate").1);
    let h = vec![("stock".into(), false, 3.0), ("panel".into(), true, 2.0)];
    assert_eq!(crf::choose("stock", &h, 1.0).expect("tie").0, "stock");
    let h = vec![("stock".into(), false, 3.0), ("new".into(), false, 3.49)];
    assert!(!crf::choose("stock", &h, 0.0).expect("margin").1);
}
fn write_score(path: &Path, t: usize, values: Option<&[f64]>) {
    let header = format!("DGS1\t{t}\t1024\t4\t6\t0\t32\t100\t1\t0\t0\t0\t0\tp1_b1\t0\n");
    let mut bytes = header.into_bytes();
    for i in 0..t * 1024 {
        let bits: u16 = match values.map(|v| v[i]).unwrap_or(0.0) {
            8.0 => 0x4800,
            -8.0 => 0xc800,
            _ => 0,
        };
        bytes.extend(bits.to_le_bytes());
    }
    fs::write(path, bytes).expect("scores");
}
#[test]
fn score_parser_rejects_truncation_wrong_c_nonfinite_and_tokens() {
    let p = tmp();
    let file = p.join("p1_b1_s0.scores");
    write_score(&file, 2, None);
    let parsed = scores::load(&file).expect("DGS1");
    assert_eq!(parsed.values.len(), 2048);
    assert_eq!(parsed.header.t, 2);
    let original = fs::read(&file).expect("bytes");
    fs::write(&file, &original[..original.len() - 1]).expect("truncate");
    assert!(scores::load(&file).is_err());
    let mut nonfinite = original.clone();
    let l = nonfinite.len();
    nonfinite[l - 2..].copy_from_slice(&0x7c00u16.to_le_bytes());
    fs::write(&file, nonfinite).expect("infinity");
    assert!(scores::load(&file).is_err());
    let header = "DGS1\t2\t1024\t4\t6\t0\t32\t100\t1\t0\t0\t0\t0\tp1_b1\t0\n";
    assert!(scores::parse_header(&header.replace("1024", "4096")).is_err());
    assert!(scores::parse_header(&header.replace("p1_b1", "../other")).is_err());
    assert!(scores::parse_header(&header.replace("\t100\t", "\tNaN\t")).is_err());
    fs::write(&file, &original).expect("restore");
    let renamed = p.join("p9_b1_s0.scores");
    fs::copy(&file, &renamed).expect("copy");
    assert!(scores::load(&renamed).is_err());
    assert_eq!(scores::half(0x3c00), 1.0);
    assert_eq!(scores::half(0x0001), 2f64.powi(-24));
    assert_eq!(scores::half(0xc500), -5.0);
}
struct Fixture {
    root: PathBuf,
    seq: String,
    rf: String,
}
fn fixture(reverse: bool) -> Fixture {
    let root = tmp();
    fs::create_dir(root.join("export")).expect("export");
    let mut n = 0x72616365u32;
    let rf: String = (0..220)
        .map(|_| {
            n ^= n << 13;
            n ^= n >> 17;
            n ^= n << 5;
            b"ACGT"[(n % 4) as usize] as char
        })
        .collect();
    let mut aligned = rf.as_bytes().to_vec();
    aligned[100] = if aligned[100] == b'A' { b'C' } else { b'A' };
    let aligned = String::from_utf8(aligned).expect("DNA");
    let seq = if reverse {
        native::revcomp(&aligned).expect("reverse")
    } else {
        aligned.clone()
    };
    let q = "I".repeat(seq.len());
    fs::write(root.join("ref.fa"), format!(">chr20\n{rf}\n")).expect("fasta");
    fs::write(root.join("parents.txt"), "read-1\n").expect("parents");
    fs::write(root.join("native.sam"),format!("@HD\tVN:1.6\nread-1\t{}\tchr20\t1\t60\t100=1X119=\t*\t0\t0\t{aligned}\t{q}\tNM:i:1\tmv:B:c,6\n",if reverse{16}else{0})).expect("sam");
    let t = seq.len();
    let mut values = vec![-8.0; t * 1024];
    let mut state = 0;
    for (time, b) in seq.bytes().enumerate() {
        let (next, index) = crf::transition(state, b, 4).expect("stock step");
        values[time * 1024 + index] = 8.0;
        state = next;
    }
    write_score(&root.join("export/p1_b1_s0.scores"), t, Some(&values));
    let mv = "1".repeat(t);
    let meta=format!("format\tDGM1\nscore_file\tp1_b1_s0.scores\ntoken\tp1_b1\ntime_offset\t0\nT\t{t}\nC\t1024\nread_id\tread-1\nchunk_index\t0\nchunk_count\t1\ninput_offset\t0\nraw_chunk_size\t{}\nchunk_size_granularity\t6\nnum_trimmed_samples\t10\nsignal_samples\t{}\noriginal_signal_samples\t{}\nmodel_path\t/pinned/hac\nvariable_chunk_sizes\t0\nSEQ\t{seq}\nQ\t{q}\nMOVES\t{mv}\n",t*6,t*6,t*6+10);
    fs::write(root.join("export/p1_b1_s0.scores.meta.tsv"), meta).expect("meta");
    fs::write(root.join("export/read-1.parent.tsv"),format!("format\tDGP1\nread_id\tread-1\nchunk_count\t1\nstride\t6\nnum_trimmed_samples\t10\nsignal_samples\t{}\nvariable_chunk_sizes\t0\nSEQ\t{seq}\nQ\t{q}\nMOVES\t{mv}\n",t*6)).expect("parent");
    Fixture { root, seq, rf }
}
fn run_plan(f: &Fixture) -> Vec<planner::Window> {
    planner::plan(
        &f.root.join("ref.fa"),
        &f.root.join("native.sam"),
        &f.root.join("export"),
        &f.root.join("parents.txt"),
        &f.root.join("plan"),
        "test-v1",
    )
    .expect("plan");
    planner::load_windows(&f.root.join("plan/windows.jsonl")).expect("windows")
}
fn write_graph(f: &Fixture, w: &planner::Window) {
    let sequence = &f.rf[w.ref_start..w.ref_end];
    fs::write(f.root.join("walks.jsonl"),format!("{}\n",json!({"schema":"hprc-local-paths/1","query_index":0,"query":{"sample":"GRCh38","contig":"chr20","start":w.ref_start,"end":w.ref_end},"reference":{"start":w.ref_start,"end":w.ref_end,"sequence":sequence},"boundary_nodes":[">1",">2"],"walks":[{"is_reference":true,"copy_count":100,"both_anchors":true,"cigar":"41M","sequence":sequence}]}))).expect("graph");
}
fn run_decode(f: &Fixture, out: &str) {
    decoder::decode(
        &f.root.join("ref.fa"),
        &f.root.join("native.sam"),
        &f.root.join("export"),
        &f.root.join("parents.txt"),
        &f.root.join("plan/windows.jsonl"),
        &f.root.join("walks.jsonl"),
        &f.root.join(out),
    )
    .expect("decode");
}
#[test]
fn full_pipeline_reverse_mapping_identity_and_context_unavailable() {
    for reverse in [false, true] {
        let f = fixture(reverse);
        let windows = run_plan(&f);
        assert_eq!(windows.len(), 1);
        let w = &windows[0];
        assert_eq!((w.ref_start, w.ref_end), (80, 121));
        assert_eq!(
            (w.read_start, w.read_end),
            if reverse { (99, 140) } else { (80, 121) }
        );
        assert_eq!(w.stock, &f.seq[w.read_start..w.read_end]);
        assert_eq!(
            fs::read_to_string(f.root.join("plan/queries.tsv")).expect("queries"),
            "GRCh38\tchr20\t80\t121\n"
        );
        write_graph(&f, w);
        run_decode(&f, "identity");
        // Explicit stock-supported scores preserve one complete native parent.
        for name in ["neutral.sam", "graph-025.sam"] {
            let s = fs::read_to_string(f.root.join("identity").join(name)).expect("output");
            let fields: Vec<_> = s.lines().nth(1).expect("record").split('\t').collect();
            assert_eq!(fields[1], "4");
            assert_eq!(fields[9], f.seq);
            assert_eq!(fields.len(), 11);
        }
        let mut g: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(f.root.join("walks.jsonl")).expect("graph"))
                .expect("json");
        g["reference"]["sequence"] = json!("A".repeat(41));
        fs::write(f.root.join("walks.jsonl"), format!("{g}\n")).expect("bad graph");
        run_decode(&f, "unavailable");
        let summary: serde_json::Value = serde_json::from_slice(
            &fs::read(f.root.join("unavailable/summary.json")).expect("summary"),
        )
        .expect("json");
        assert_eq!(summary["scored_windows"], 0);
        assert_eq!(summary["parents"], 1);
        assert_eq!(summary["excluded_windows"], 1);
    }
}
#[test]
fn no_outside_window_edits_and_changed_core_quality_uncalibrated() {
    for reverse in [false, true] {
        let f = fixture(reverse);
        let windows = run_plan(&f);
        let w = &windows[0];
        write_graph(&f, w);
        let target = if reverse {
            native::revcomp(&f.rf).expect("reverse")
        } else {
            f.rf.clone()
        };
        let mut values = vec![-8.0; 220 * 1024];
        let mut state = 0;
        for (t, b) in target.bytes().enumerate() {
            let (n, i) = crf::transition(state, b, 4).expect("step");
            values[t * 1024 + i] = 8.0;
            state = n;
        }
        write_score(&f.root.join("export/p1_b1_s0.scores"), 220, Some(&values));
        run_decode(&f, "edited");
        for arm in [
            "neutral.sam",
            "graph-025.sam",
            "graph-050.sam",
            "graph-100.sam",
        ] {
            let output = fs::read_to_string(f.root.join("edited").join(arm)).expect("SAM");
            let fields: Vec<_> = output.lines().nth(1).expect("record").split('\t').collect();
            assert_eq!(fields[9], target);
            assert_eq!(&fields[9][..w.read_start + 10], &f.seq[..w.read_start + 10]);
            assert_eq!(&fields[9][w.read_end - 10..], &f.seq[w.read_end - 10..]);
            let expected = format!(
                "{}{}{}",
                "I".repeat(w.read_start + 10),
                "!".repeat(21),
                "I".repeat(220 - (w.read_end - 10))
            );
            assert_eq!(fields[10], expected);
        }
    }
}
#[test]
fn parent_mismatch_and_duplicate_primary_are_rejected_safely() {
    let f = fixture(false);
    let p = f.root.join("export/read-1.parent.tsv");
    let mut txt = fs::read_to_string(&p).expect("parent");
    txt = txt.replace(
        &format!("SEQ\t{}", f.seq),
        &format!("SEQ\t{}", native::revcomp(&f.seq).expect("reverse")),
    );
    fs::write(p, txt).expect("mismatch");
    assert!(run_plan(&f).is_empty());
    let sam = f.root.join("native.sam");
    let text = fs::read_to_string(&sam).expect("SAM");
    fs::write(
        &sam,
        format!("{text}{}\n", text.lines().nth(1).expect("record")),
    )
    .expect("duplicate");
    assert!(native::sam(&sam, &["read-1".into()]).is_err());
}
#[test]
fn graph_presence_deduplicates_and_ignores_copy_counts() {
    let f = fixture(false);
    let ws = run_plan(&f);
    write_graph(&f, &ws[0]);
    let g = graph::load(&f.root.join("walks.jsonl")).expect("graph");
    let p = graph::panel(&ws[0], &g[&0], f.rf.as_bytes()).expect("panel");
    assert_eq!(p.len(), 1);
}
fn write_kv(path: &Path, m: &std::collections::BTreeMap<String, String>) {
    let text: String = m.iter().map(|(k, v)| format!("{k}\t{v}\n")).collect();
    fs::write(path, text).expect("metadata");
}
#[test]
fn native_odd_overlap_retention_and_single_chunk_partial_stride() {
    let f = fixture(false);
    let dir = f.root.join("export");
    let original = native::kv(&dir.join("p1_b1_s0.scores.meta.tsv")).expect("metadata");
    let mut parent = native::kv(&dir.join("read-1.parent.tsv")).expect("parent");
    let seq = &f.seq[..195];
    let q = format!("{}{}", "I".repeat(98), "J".repeat(97));
    for (index, (token, offset, start, quality)) in [("p1_b1", 0, 0, 'I'), ("p1_b2", 570, 95, 'J')]
        .into_iter()
        .enumerate()
    {
        let name = format!("{token}_s0.scores");
        let mut m = original.clone();
        for (k, v) in [
            ("score_file", name.clone()),
            ("token", token.into()),
            ("T", "100".into()),
            ("chunk_index", index.to_string()),
            ("chunk_count", "2".into()),
            ("input_offset", offset.to_string()),
            ("raw_chunk_size", "600".into()),
            ("signal_samples", "1170".into()),
            ("original_signal_samples", "1180".into()),
            ("SEQ", f.seq[start..start + 100].into()),
            ("Q", quality.to_string().repeat(100)),
            ("MOVES", "1".repeat(100)),
        ] {
            m.insert(k.into(), v);
        }
        write_kv(&dir.join(format!("{name}.meta.tsv")), &m);
        write_score(&dir.join(&name), 100, None);
        if token != "p1_b1" {
            let bytes = fs::read(dir.join(&name)).expect("scores");
            let header_end = bytes.iter().position(|&b| b == b'\n').expect("header");
            let header = String::from_utf8(bytes[..=header_end].to_vec())
                .expect("ASCII")
                .replace("p1_b1", token);
            let mut rewritten = header.into_bytes();
            rewritten.extend_from_slice(&bytes[header_end + 1..]);
            fs::write(dir.join(&name), rewritten).expect("token");
        }
    }
    for (k, v) in [
        ("chunk_count", "2".into()),
        ("signal_samples", "1170".into()),
        ("SEQ", seq.into()),
        ("Q", q.clone()),
        ("MOVES", "1".repeat(195)),
    ] {
        parent.insert(k.into(), v);
    }
    write_kv(&dir.join("read-1.parent.tsv"), &parent);
    let mut s = native::sam(&f.root.join("native.sam"), &["read-1".into()])
        .expect("SAM")
        .remove("read-1")
        .expect("record");
    s.seq = seq.into();
    s.qual = q;
    let inv = native::inventory(&dir, &["read-1".into()]).expect("inventory");
    let e = native::reconstruct(&dir, &s, &inv["read-1"]).expect("odd overlap reconstruction");
    assert_eq!(
        (
            e.retained[0].t_start,
            e.retained[0].t_end,
            e.retained[0].parent_base_end
        ),
        (0, 98, 98)
    );
    assert_eq!(
        (
            e.retained[1].t_start,
            e.retained[1].t_end,
            e.retained[1].parent_base_start
        ),
        (3, 100, 98)
    );
    // One fixed chunk is cropped to ceil(signal/stride), then its partial-stride overhang is removed.
    let f = fixture(false);
    let dir = f.root.join("export");
    let mut meta = native::kv(&dir.join("p1_b1_s0.scores.meta.tsv")).expect("metadata");
    let mut p = native::kv(&dir.join("read-1.parent.tsv")).expect("parent");
    for (k, v) in [
        ("signal_samples", "1318".into()),
        ("original_signal_samples", "1328".into()),
    ] {
        meta.insert(k.into(), v);
    }
    write_kv(&dir.join("p1_b1_s0.scores.meta.tsv"), &meta);
    for (k, v) in [
        ("signal_samples", "1318".into()),
        ("SEQ", f.seq[..219].into()),
        ("Q", "I".repeat(219)),
        ("MOVES", "1".repeat(219)),
    ] {
        p.insert(k.into(), v);
    }
    write_kv(&dir.join("read-1.parent.tsv"), &p);
    let mut s = native::sam(&f.root.join("native.sam"), &["read-1".into()])
        .expect("SAM")
        .remove("read-1")
        .expect("record");
    s.seq.truncate(219);
    s.qual.truncate(219);
    let inv = native::inventory(&dir, &["read-1".into()]).expect("inventory");
    let e = native::reconstruct(&dir, &s, &inv["read-1"]).expect("partial stride reconstruction");
    assert_eq!(e.retained[0].t_end, 219);
    assert_eq!(e.retained[0].parent_base_end, 219);
}
#[test]
fn complete_panel_is_never_silently_truncated_and_missing_context_is_identity() {
    let f = fixture(false);
    let ws = run_plan(&f);
    let w = &ws[0];
    write_graph(&f, w);
    let path = f.root.join("walks.jsonl");
    let original: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&path).expect("graph")).expect("JSON");
    let mut duplicate = original.clone();
    let mut walk = duplicate["walks"][0].clone();
    walk["copy_count"] = json!(999999);
    duplicate["walks"].as_array_mut().expect("walks").push(walk);
    fs::write(&path, format!("{duplicate}\n")).expect("duplicate graph");
    let g = graph::load(&path).expect("graph");
    assert_eq!(
        graph::panel(w, &g[&0], f.rf.as_bytes())
            .expect("dedup")
            .len(),
        1
    );
    let mut invalid = original.clone();
    let seq = invalid["walks"][0]["sequence"]
        .as_str()
        .expect("sequence")
        .to_owned();
    let mut long = seq.as_bytes().to_vec();
    long.splice(20..20, std::iter::repeat_n(b'A', 6));
    invalid["walks"].as_array_mut().expect("walks").push(json!({"is_reference":false,"both_anchors":true,"sequence":String::from_utf8(long).expect("DNA"),"cigar":"20M6I21M","copy_count":1}));
    fs::write(&path, format!("{invalid}\n")).expect("long graph");
    let g = graph::load(&path).expect("graph");
    assert!(graph::panel(w, &g[&0], f.rf.as_bytes()).is_err());
    let mut excessive = original.clone();
    for i in 0..16 {
        let mut alt = seq.as_bytes().to_vec();
        let p = 10 + i;
        alt[p] = if alt[p] == b'A' { b'C' } else { b'A' };
        excessive["walks"].as_array_mut().expect("walks").push(json!({"is_reference":false,"both_anchors":true,"sequence":String::from_utf8(alt).expect("DNA"),"cigar":"41M","copy_count":1}));
    }
    fs::write(&path, format!("{excessive}\n")).expect("excessive graph");
    let g = graph::load(&path).expect("graph");
    assert!(graph::panel(w, &g[&0], f.rf.as_bytes()).is_err());
    fs::write(path, "").expect("missing graph");
    run_decode(&f, "missing-context");
    let output = fs::read_to_string(f.root.join("missing-context/graph-100.sam")).expect("SAM");
    assert_eq!(
        output.lines().nth(1).expect("record").split('\t').nth(9),
        Some(f.seq.as_str())
    );
    fs::write(f.root.join("plan/windows.jsonl"), "").expect("zero windows");
    run_decode(&f, "zero-windows");
    let summary: serde_json::Value = serde_json::from_slice(
        &fs::read(f.root.join("zero-windows/summary.json")).expect("summary"),
    )
    .expect("JSON");
    assert_eq!(summary["planned_windows"], 0);
    assert_eq!(summary["parents"], 1);
}
