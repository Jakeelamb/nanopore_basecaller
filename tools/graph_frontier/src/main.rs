use anyhow::{bail, Context, Result};
use std::path::PathBuf;

fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args == ["--help"] || args == ["-h"] || args == ["emit", "--help"] {
        println!("graph-frontier emit --cohort COHORT_JSON --protocol PROTOCOL_JSON --output NEWDIR\n\nRe-rank pinned retained likelihoods and emit complete native-orientation parent SAMs.\nOutput must not exist. Errors retain partial output without complete.json.\nNo truth, tensor inference, mapping, or biological scoring is performed.");
        return Ok(());
    }
    if args.first().map(String::as_str) != Some("emit") || args.len() != 7 {
        bail!("usage: graph-frontier emit --cohort COHORT_JSON --protocol PROTOCOL_JSON --output NEWDIR");
    }
    let mut paths = std::collections::BTreeMap::new();
    for pair in args[1..].chunks_exact(2) {
        if !["--cohort", "--protocol", "--output"].contains(&pair[0].as_str())
            || paths
                .insert(pair[0].as_str(), PathBuf::from(&pair[1]))
                .is_some()
        {
            bail!("unknown or duplicate option {}", pair[0]);
        }
    }
    let completion = graph_frontier::emit(
        paths.get("--cohort").context("missing --cohort")?,
        paths.get("--protocol").context("missing --protocol")?,
        paths.get("--output").context("missing --output")?,
    )?;
    println!("{completion}");
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("graph-frontier: {error:#}");
        std::process::exit(1);
    }
}
