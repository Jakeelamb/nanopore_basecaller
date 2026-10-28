use anyhow::{ensure, Context, Result};
use prefix_scalar_oracle::{
    contract::{
        ComparisonTolerance, CompilerIdentity, Completion, FilePin, Request, Response, SourcePin,
    },
    digest, identity, input, score, verify_sources,
};
use std::{fs, io::Write, path::Path};

fn fresh(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    Ok(())
}

fn main() -> Result<()> {
    let args: Vec<_> = std::env::args().collect();
    ensure!(
        args.len() == 8
            && args[1] == "score"
            && args[2] == "--request"
            && args[4] == "--request-sha256"
            && args[6] == "--output",
        "score --request ABS --request-sha256 SHA --output ABS_FRESH_DIR"
    );
    let request_path = Path::new(&args[3]);
    let output = Path::new(&args[7]);
    ensure!(
        request_path.is_absolute() && output.is_absolute() && !output.exists(),
        "absolute request/fresh output required"
    );
    let parent = output.parent().context("output parent required")?;
    let canonical_parent = fs::canonicalize(parent)?;
    ensure!(
        canonical_parent == parent,
        "absolute canonical output parent required"
    );
    let output_name = output.file_name().context("output directory name required")?;
    let output_path = canonical_parent.join(output_name);
    let output = output_path.as_path();
    let request_pin = FilePin {
        path: request_path.to_owned(),
        size: fs::metadata(request_path)?.len(),
        sha256: args[5].clone(),
    };
    let request_bytes = input::read_pinned(&request_pin, 1_048_576)?;
    let request: Request = serde_json::from_slice(&request_bytes)?;
    verify_sources()?;
    let consumed = input::load(&request)?;
    let scores = score(&consumed, &request.queries)?;
    let executable = input::pin(&fs::canonicalize(std::env::current_exe()?)?)?;
    input::read_pinned(&request_pin, 1_048_576)?;
    verify_sources()?;
    let result = Response {
        schema: "prefix-scalar-scores/1".into(), request, request_pin: request_pin.clone(),
        interpretation: "logsumexp over fixed initial states 0..255 minus ln(256); all consumed rows; unconstrained final state; no normalization or anchor".into(),
        comparison_tolerance: ComparisonTolerance { absolute: 1e-8, relative: 1e-10,
            rule: "abs_error <= absolute + relative * max(abs(cpp),abs(rust)); impossible statuses agree".into() },
        compiled_sources: identity::SOURCE_PINS.iter().map(|(path, sha256)| SourcePin { path: (*path).into(), sha256: (*sha256).into() }).collect(),
        compiled_source_root: env!("CARGO_MANIFEST_DIR").into(),
        compiler: CompilerIdentity { path: identity::COMPILER_PATH.into(), sha256: identity::COMPILER_SHA256.into(), version: identity::COMPILER_VERSION.into() },
        executable: executable.clone(), consumed_payload_sha256: consumed.payload_sha256,
        segment_payload_sha256: consumed.segment_payload_sha256, scores,
        limits: "FilePins establish file custody only; no producer biology, genotype or genuine parity acceptance".into(),
    };
    fs::create_dir(output)?;
    fresh(&output.join("request.json"), &request_bytes)?;
    fresh(
        &output.join("scores.json"),
        &serde_json::to_vec_pretty(&result)?,
    )?;
    let completion = Completion {
        schema: "prefix-scalar-complete/1".into(),
        request: request_pin,
        request_copy: input::pin(&output.join("request.json"))?,
        scores: input::pin(&output.join("scores.json"))?,
        executable,
    };
    fresh(
        &output.join("complete.json"),
        &serde_json::to_vec_pretty(&completion)?,
    )?;
    fs::File::open(output)?.sync_all()?;
    println!("{}", digest(&fs::read(output.join("complete.json"))?));
    Ok(())
}
