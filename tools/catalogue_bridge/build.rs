use std::{
    env, fs, io,
    path::{Path, PathBuf},
};
fn sources(root: &Path, paths: &mut Vec<PathBuf>) -> io::Result<()> {
    for entry in fs::read_dir(root)? {
        let p = entry?.path();
        if p.is_dir() {
            sources(&p, paths)?;
        } else if p.extension().is_some_and(|s| s == "rs") {
            paths.push(fs::canonicalize(p)?);
        }
    }
    Ok(())
}
fn main() -> io::Result<()> {
    let own = PathBuf::from(
        env::var_os("CARGO_MANIFEST_DIR").ok_or_else(|| io::Error::other("manifest missing"))?,
    );
    let mut paths = Vec::new();
    for root in [
        own.clone(),
        own.join("../graph_prior"),
        own.join("../graph_frontier"),
        own.join("../accuracy"),
    ] {
        for name in ["Cargo.toml", "Cargo.lock", "build.rs"] {
            let p = root.join(name);
            if p.exists() {
                paths.push(fs::canonicalize(p)?);
            }
        }
        sources(&root.join("src"), &mut paths)?;
        println!("cargo:rerun-if-changed={}", root.join("src").display());
    }
    for name in [
        "input.json",
        "prerequisites.json",
        "../../scripts/catalogue-bridge.py",
        "../../config/compound-frontier-v1.json",
    ] {
        paths.push(fs::canonicalize(own.join(name))?);
    }
    paths.sort();
    paths.dedup();
    let mut generated = String::from("const COMPILED_SOURCES: &[(&str, &[u8])] = &[\n");
    for p in paths {
        let p = p
            .to_str()
            .ok_or_else(|| io::Error::other("UTF8 path required"))?;
        println!("cargo:rerun-if-changed={p}");
        generated.push_str(&format!("({p:?}, include_bytes!({p:?})),\n"));
    }
    generated.push_str("];\n");
    let out =
        PathBuf::from(env::var_os("OUT_DIR").ok_or_else(|| io::Error::other("OUT_DIR missing"))?);
    fs::write(out.join("compiled_sources.rs"), generated)
}
