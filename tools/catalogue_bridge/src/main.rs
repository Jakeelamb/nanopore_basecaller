use anyhow::{bail, Context, Result};
use std::{collections::BTreeMap, path::PathBuf};
fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args == ["--help"] {
        println!("catalogue-bridge transform --manifest INPUT --output NEWDIR --limit 8|331\ncatalogue-bridge admit --manifest INPUT --transform DIR --producer RECEIPT --protocol JSON --output NEWDIR");
        return Ok(());
    }
    let command = args.first().context("command required")?;
    let mut options = BTreeMap::new();
    anyhow::ensure!(args.len() % 2 == 1, "option value missing");
    for pair in args[1..].chunks_exact(2) {
        anyhow::ensure!(
            options.insert(pair[0].as_str(), pair[1].as_str()).is_none(),
            "duplicate option"
        );
    }
    let path = |key: &str| -> Result<PathBuf> {
        Ok(PathBuf::from(options.get(key).context("missing option")?))
    };
    let result = match command.as_str() {
        "transform" => {
            anyhow::ensure!(options.len() == 3, "unknown option");
            catalogue_bridge::transform(
                &path("--manifest")?,
                &path("--output")?,
                options.get("--limit").context("limit")?.parse()?,
            )?
        }
        "admit" => {
            anyhow::ensure!(options.len() == 5, "unknown option");
            catalogue_bridge::admit(
                &path("--manifest")?,
                &path("--transform")?,
                &path("--producer")?,
                &path("--protocol")?,
                &path("--output")?,
            )?
        }
        _ => bail!("unknown command"),
    };
    println!("{result}");
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("catalogue-bridge: {error:#}");
        std::process::exit(1);
    }
}
