use anyhow::{ensure, Context, Result};
use std::{collections::BTreeMap, path::Path};
fn run() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let command=args.next().context("usage: graph-prior plan|decode --reference FASTA --sam SAM --export DIR --parents IDS [--windows JSONL --graph JSONL] --output NEWDIR")?;
    if command == "--help" || command == "-h" {
        println!("graph-prior plan|decode --reference FASTA --sam SAM --export DIR --parents IDS [--namespace graph-prior-v1] [--windows JSONL --graph JSONL] --output NEWDIR");
        return Ok(());
    }
    let mut opts = BTreeMap::new();
    while let Some(k) = args.next() {
        ensure!(k.starts_with("--"), "unexpected positional argument");
        let v = args.next().context("missing option value")?;
        ensure!(opts.insert(k, v).is_none(), "duplicate option");
    }
    ensure!(
        matches!(command.as_str(), "plan" | "decode"),
        "unknown command"
    );
    for k in opts.keys() {
        ensure!(
            ["--reference", "--sam", "--export", "--parents", "--output"].contains(&k.as_str())
                || (command == "plan" && k == "--namespace")
                || (command == "decode" && ["--windows", "--graph"].contains(&k.as_str())),
            "unknown option {k}"
        );
    }
    let p = |k: &str| -> Result<&Path> {
        Ok(Path::new(
            opts.get(k).with_context(|| format!("missing {k}"))?,
        ))
    };
    if command == "plan" {
        graph_prior::planner::plan(
            p("--reference")?,
            p("--sam")?,
            p("--export")?,
            p("--parents")?,
            p("--output")?,
            opts.get("--namespace")
                .map(String::as_str)
                .unwrap_or("graph-prior-v1"),
        )
    } else {
        graph_prior::decoder::decode(
            p("--reference")?,
            p("--sam")?,
            p("--export")?,
            p("--parents")?,
            p("--windows")?,
            p("--graph")?,
            p("--output")?,
        )
    }
}
fn main() {
    if let Err(e) = run() {
        eprintln!("graph-prior: {e:#}");
        std::process::exit(1);
    }
}
