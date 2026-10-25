use accuracy::{score, truth, Reference, SpanningPolicy, TruthSources};
use anyhow::{bail, ensure, Context, Result};
use std::{collections::BTreeMap, path::Path};
fn main() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let command = args
        .next()
        .context("usage: accuracy truth|score --key value ...")?;
    let mut opts: BTreeMap<String, Vec<String>> = BTreeMap::new();
    while let Some(k) = args.next() {
        ensure!(k.starts_with("--"), "expected --option");
        let v = args.next().context("missing option value")?;
        opts.entry(k).or_default().push(v);
    }
    let allowed = match command.as_str() {
        "truth" => vec![
            "reference",
            "vcf",
            "original-footprints",
            "spanning-policy",
            "confident",
            "sample",
            "exclusions",
            "padding",
            "output",
        ],
        "score" => vec![
            "reference",
            "eligible",
            "sam",
            "parents",
            "output",
            "min-mapq",
        ],
        _ => bail!("unknown command"),
    };
    for (k, v) in &opts {
        ensure!(
            allowed.iter().any(|a| k == &format!("--{a}")),
            "unknown option {k}"
        );
        ensure!(k == "--exclusions" || v.len() == 1, "duplicate option {k}");
    }
    let get = |k: &str| -> Result<&str> {
        opts.get(&format!("--{k}"))
            .and_then(|v| v.first())
            .map(String::as_str)
            .with_context(|| format!("missing --{k}"))
    };
    let reference = Reference::load(Path::new(get("reference")?))?;
    let output = Path::new(get("output")?);
    ensure!(
        !output
            .join(if command == "truth" {
                "truth.json"
            } else {
                "score.json"
            })
            .exists(),
        "completed output exists; use a fresh output directory"
    );
    match command.as_str() {
        "truth" => {
            let empty = Vec::new();
            truth(
                &reference,
                TruthSources {
                    vcf: Path::new(get("vcf")?),
                    confident: Path::new(get("confident")?),
                    original_footprints: Some(Path::new(get("original-footprints")?)),
                    spanning_policy: match get("spanning-policy")? {
                        "reject" => SpanningPolicy::Reject,
                        "exclude-confidence-neighborhood" => {
                            SpanningPolicy::ExcludeConfidenceNeighborhood
                        }
                        _ => bail!("unsupported spanning policy"),
                    },
                },
                get("sample")?,
                opts.get("--exclusions").unwrap_or(&empty),
                get("padding")?.parse()?,
                output,
            )?;
        }
        "score" => {
            let min = opts
                .get("--min-mapq")
                .and_then(|v| v.first())
                .map(|v| v.parse())
                .transpose()?
                .unwrap_or(30);
            ensure!(min < 255, "min MAPQ must be <255");
            score(
                &reference,
                Path::new(get("eligible")?),
                Path::new(get("sam")?),
                Path::new(get("parents")?),
                output,
                min,
            )?;
        }
        _ => bail!("unknown command"),
    };
    Ok(())
}
