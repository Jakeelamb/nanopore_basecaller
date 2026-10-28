use prefix_scalar_oracle::{contract::*, crf, digest, input, uniform};
use serde_json::{json, Value};
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicUsize, Ordering},
};

static NEXT: AtomicUsize = AtomicUsize::new(0);
const UUID: &str = "01234567-89ab-cdef-0123-456789abcdef";

#[test]
fn analytic_empty_impossible_and_binomial_paths() {
    for n in 0..=5 {
        let values = vec![0.0; n * 1024];
        let (empty, _) = uniform(&values, n, 2.0, b"").expect("empty");
        assert!((empty - 2.0 * n as f64).abs() < 1e-12);
        let mut choose = 1.0_f64;
        for length in 0..=n {
            if length > 0 {
                choose *= (n + 1 - length) as f64 / length as f64;
            }
            for sequence in [
                "A".repeat(length),
                "T".repeat(length),
                "ACGTA"[..length].to_owned(),
            ] {
                let (value, _) = uniform(&values, n, 0.0, sequence.as_bytes()).expect("binomial");
                assert!(
                    (value - choose.ln()).abs() < 1e-12,
                    "{n} {sequence} {value}"
                );
            }
        }
        let (impossible, states) =
            uniform(&values, n, 0.0, "A".repeat(n + 1).as_bytes()).expect("impossible");
        assert_eq!(impossible, f64::NEG_INFINITY);
        assert!(states.iter().all(|&v| v == f64::NEG_INFINITY));
    }
}

#[test]
fn state_dependent_mixture_separates_fixed_state_control() {
    let mut values = vec![0.0; 1024];
    values[0] = 8.0;
    let (mixture, states) = uniform(&values, 1, 0.0, b"A").expect("mixture");
    let analytic = ((8f64.exp() + 255.0) / 256.0).ln();
    let fixed = crf::likelihood(&values, 1, 4, 0, b"A", 0.0).expect("conditional control");
    let tolerance = 1e-8 + 1e-10 * analytic.abs().max(mixture.abs());
    assert!((mixture - analytic).abs() <= tolerance);
    assert!((mixture - fixed).abs() > 1e-8 + 1e-10 * mixture.abs().max(fixed.abs()));
    assert_eq!(states[0], 8.0);
    assert_eq!(states.iter().filter(|&&v| v == 0.0).count(), 255);
}

struct Fixture {
    root: PathBuf,
    request: Request,
}
fn fixture() -> Fixture {
    let root = std::env::temp_dir().join(format!(
        "prefix-scalar-control-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).expect("fresh fixture");
    let header = "DGS1\t4\t1024\t4\t6\t0\t32\t100\t1\t0\t0\t0\t0\tp1_b1\t0\n";
    let tensor = root.join("p1_b1_s0.scores");
    let mut original = header.as_bytes().to_vec();
    original.extend(vec![0; 4 * 2048]);
    fs::write(&tensor, original).expect("original");
    let meta = root.join("p1_b1_s0.scores.meta.tsv");
    fs::write(&meta, format!("format\tDGM1\nread_id\t{UUID}\nchunk_index\t0\nchunk_count\t1\ntoken\tp1_b1\ntime_offset\t0\nT\t4\nC\t1024\nscore_file\tp1_b1_s0.scores\ninput_offset\t0\nraw_chunk_size\t24\nsignal_samples\t24\nvariable_chunk_sizes\t0\nSEQ\tTT\nQ\tII\nMOVES\t0101\n")).expect("DGM");
    let tensor = input::pin(&tensor).expect("tensor pin");
    let metadata = input::pin(&meta).expect("metadata pin");
    let opaque = root.join("selection-and-query-receipt.json");
    fs::write(&opaque, b"{\"fixture\":true}\n").expect("selection fixture");
    let opaque = input::pin(&opaque).expect("opaque pin");
    let mut segments = Vec::new();
    for index in 0..2 {
        let path = root.join(format!("released-{index}.dgs"));
        let mut release = header.replacen("\t4\t", "\t2\t", 1).into_bytes();
        release.extend(vec![0; 2 * 2048]);
        fs::write(&path, release).expect("release");
        let binding = Binding {
            tensor: input::pin(&path).expect("release pin"),
            read_id: UUID.into(),
            parent_id: UUID.into(),
            chunk_index: 0,
            block_index: index,
            row_begin: 2 * index,
            row_end: 2 * index + 2,
            chunk_row_begin: 2 * index,
            chunk_row_end: 2 * index + 2,
            available_score_end: 2 * index + 2,
            available_signal_end: 24,
            chunk_signal_begin: 0,
            chunk_signal_end: 24,
            declared_chunk_lookahead: 24,
            orientation: "signal-forward".into(),
        };
        let receipt = ReleaseReceipt {
            schema: "prefix-release/1".into(),
            read_id: UUID.into(),
            tensor: binding.tensor.clone(),
            binding: binding.clone(),
            original_tensor: tensor.clone(),
            metadata: metadata.clone(),
            original_row_begin: 2 * index,
            original_row_end: 2 * index + 2,
            recipe: input::RECIPE.into(),
            signal_geometry_qualification: input::QUALIFICATION.into(),
        };
        let receipt_path = root.join(format!("release-{index}.json"));
        fs::write(&receipt_path, serde_json::to_vec(&receipt).expect("JSON")).expect("receipt");
        segments.push(Segment {
            binding,
            release_receipt: input::pin(&receipt_path).expect("receipt pin"),
        });
    }
    Fixture {
        root,
        request: Request {
            schema: "prefix-scalar-request/1".into(),
            prior: Prior::UniformAllStates,
            state_length: 4,
            stride: 6,
            channels: 1024,
            read_id: UUID.into(),
            chunk_index: 0,
            tensor,
            metadata,
            original_header: header.into(),
            row_begin: 0,
            row_end: 4,
            chunk_row_begin: 0,
            chunk_row_end: 4,
            selection_receipt: opaque.clone(),
            query_receipt: opaque,
            segments,
            queries: vec![
                Query {
                    id: "H".into(),
                    sequence: "AC".into(),
                },
                Query {
                    id: "empty".into(),
                    sequence: "".into(),
                },
                Query {
                    id: "long".into(),
                    sequence: "AAAAA".into(),
                },
            ],
        },
    }
}

fn run(f: &Fixture, request: &Value, name: &str, hash: Option<&str>) -> std::process::Output {
    run_to(f, request, name, name, hash)
}
fn run_to(
    f: &Fixture,
    request: &Value,
    name: &str,
    destination: &str,
    hash: Option<&str>,
) -> std::process::Output {
    let bytes = serde_json::to_vec(request).expect("request JSON");
    let path = f.root.join(format!("{name}-request.json"));
    fs::write(&path, &bytes).expect("request");
    let output = Command::new(env!("CARGO_BIN_EXE_prefix-scalar-oracle"))
        .args(["score", "--request"])
        .arg(&path)
        .arg("--request-sha256")
        .arg(hash.map(str::to_owned).unwrap_or_else(|| digest(&bytes)))
        .arg("--output")
        .arg(f.root.join(destination))
        .output()
        .expect("CLI");
    fs::write(f.root.join(format!("{name}.stdout")), &output.stdout).expect("stdout");
    fs::write(f.root.join(format!("{name}.stderr")), &output.stderr).expect("stderr");
    fs::write(
        f.root.join(format!("{name}.status")),
        output.status.to_string(),
    )
    .expect("status");
    output
}
fn reject(f: &Fixture, request: Value, name: &str, expected: &str) {
    let output = run(f, &request, name, None);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        !output.status.success() && stderr.contains(expected),
        "{name}: {stderr}"
    );
    assert!(!f.root.join(name).join("complete.json").exists());
}
fn reseal_receipt(segment: &mut Segment) {
    segment.release_receipt = input::pin(&segment.release_receipt.path).expect("reseal receipt");
}
fn read_json(path: &Path) -> Value {
    serde_json::from_slice(&fs::read(path).expect("file")).expect("JSON")
}

#[test]
fn cli_outputs_exact_query_identity_impossible_status_and_refuses_overwrite() {
    let f = fixture();
    let request = serde_json::to_value(&f.request).expect("request");
    let result = run(&f, &request, "accepted", None);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let scores = read_json(&f.root.join("accepted/scores.json"));
    assert_eq!(scores["scores"][0]["id"], "H");
    assert_eq!(scores["scores"][0]["sequence"], "AC");
    assert_eq!(
        scores["scores"][0]["per_initial_state"]
            .as_array()
            .expect("states")
            .len(),
        256
    );
    let decimal: f64 = scores["scores"][0]["score"]["decimal"]
        .as_str()
        .expect("decimal")
        .parse()
        .expect("f64");
    assert!((decimal - 6f64.ln()).abs() < 1e-12);
    assert_eq!(scores["scores"][2]["score"], json!({"status":"impossible"}));
    let complete = read_json(&f.root.join("accepted/complete.json"));
    let pin: FilePin = serde_json::from_value(complete["scores"].clone()).expect("score pin");
    input::read_pinned(&pin, 1_048_576).expect("completion output pin");
    assert!(!run_to(&f, &request, "overwrite", "accepted", None)
        .status
        .success());
    assert!(
        !run(&f, &request, "bad-request-hash", Some(&"0".repeat(64)))
            .status
            .success()
    );
}

#[test]
fn rejects_unknown_truth_prior_and_unsupported_geometry_without_refill() {
    let f = fixture();
    let base = serde_json::to_value(&f.request).expect("request");
    let mut unknown = base.clone();
    unknown["truth"] = json!("forbidden");
    reject(&f, unknown, "truth", "unknown field");
    let mut nested = base.clone();
    nested["queries"][0]["genotype"] = json!("forbidden");
    reject(&f, nested, "genotype", "unknown field");
    let mut prior = base.clone();
    prior["prior"] = json!("fixed-state");
    reject(&f, prior, "prior", "unknown variant");
    let mut geometry = base.clone();
    geometry["state_length"] = json!(3);
    reject(&f, geometry, "geometry", "only first-chunk");
    let mut long = base.clone();
    long["queries"][0]["sequence"] = json!("A".repeat(513));
    reject(&f, long, "query-cap", "query ID/string bound");
    let mut gap = base.clone();
    gap["segments"][1]["binding"]["row_begin"] = json!(3);
    reject(&f, gap, "gap", "release interval/order/geometry");
    let mut reordered = base;
    reordered["segments"]
        .as_array_mut()
        .expect("segments")
        .swap(0, 1);
    reject(
        &f,
        reordered,
        "reordered",
        "release interval/order/geometry",
    );
}

#[test]
fn rejects_corrupt_release_and_resealed_interval_header_and_payload() {
    let mut f = fixture();
    let segment = &mut f.request.segments[0];
    let mut bytes = fs::read(&segment.binding.tensor.path).expect("release");
    let last = bytes.len() - 1;
    bytes[last] ^= 1;
    fs::write(&segment.binding.tensor.path, &bytes).expect("corrupt");
    reject(
        &f,
        serde_json::to_value(&f.request).expect("request"),
        "corrupt",
        "input hash/size differs",
    );
    f.request.segments[0].binding.tensor =
        input::pin(&f.request.segments[0].binding.tensor.path).expect("reseal payload");
    let segment = &mut f.request.segments[0];
    let mut receipt = read_json(&segment.release_receipt.path);
    receipt["tensor"] = serde_json::to_value(&segment.binding.tensor).expect("pin");
    receipt["binding"]["tensor"] = receipt["tensor"].clone();
    fs::write(
        &segment.release_receipt.path,
        serde_json::to_vec(&receipt).expect("JSON"),
    )
    .expect("receipt");
    reseal_receipt(segment);
    reject(
        &f,
        serde_json::to_value(&f.request).expect("request"),
        "resealed-payload",
        "release original payload bytes differ",
    );
    let mut f = fixture();
    let segment = &mut f.request.segments[0];
    let mut receipt = read_json(&segment.release_receipt.path);
    receipt["original_row_end"] = json!(3);
    fs::write(
        &segment.release_receipt.path,
        serde_json::to_vec(&receipt).expect("JSON"),
    )
    .expect("receipt");
    reseal_receipt(segment);
    reject(
        &f,
        serde_json::to_value(&f.request).expect("request"),
        "resealed-interval",
        "release receipt binding differs",
    );
    let mut f = fixture();
    let segment = &mut f.request.segments[0];
    let bytes = fs::read(&segment.binding.tensor.path).expect("release");
    let end = bytes.iter().position(|&b| b == b'\n').expect("header") + 1;
    let text = std::str::from_utf8(&bytes[..end])
        .expect("header")
        .replace("\t100\t", "\t101\t");
    let mut changed = text.into_bytes();
    changed.extend_from_slice(&bytes[end..]);
    fs::write(&segment.binding.tensor.path, changed).expect("options");
    segment.binding.tensor = input::pin(&segment.binding.tensor.path).expect("reseal header");
    let mut receipt = read_json(&segment.release_receipt.path);
    receipt["tensor"] = serde_json::to_value(&segment.binding.tensor).expect("pin");
    receipt["binding"]["tensor"] = receipt["tensor"].clone();
    fs::write(
        &segment.release_receipt.path,
        serde_json::to_vec(&receipt).expect("JSON"),
    )
    .expect("receipt");
    reseal_receipt(segment);
    reject(
        &f,
        serde_json::to_value(&f.request).expect("request"),
        "resealed-header",
        "release header/options differ",
    );
}
