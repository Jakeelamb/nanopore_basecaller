use sha2::{Digest, Sha256};
use std::{env, error::Error, fs, path::PathBuf, process::Command};

fn main() -> Result<(), Box<dyn Error>> {
    let paths = [
        "Cargo.toml",
        "Cargo.lock",
        "rust-toolchain.toml",
        "build.rs",
        "src/main.rs",
        "src/lib.rs",
        "src/contract.rs",
        "src/input.rs",
        "vendor/crf.rs",
        "vendor/scores.rs",
        "vendor/PROVENANCE.md",
    ];
    let mut pins = Vec::new();
    for path in paths {
        println!("cargo:rerun-if-changed={path}");
        let hash = format!("{:x}", Sha256::digest(fs::read(path)?));
        let expected = match path {
            "vendor/crf.rs" => {
                Some("3171343d81477d4d967e300466e9ba3e3d770164f34438dcedd0867ca5ea8a99")
            }
            "vendor/scores.rs" => {
                Some("2122831be9c1fad80e953268cf2138909665f703b697b5f803604b9450f0fa2e")
            }
            _ => None,
        };
        if expected.is_some_and(|expected| expected != hash) {
            return Err(format!("unchanged vendor source differs: {path}").into());
        }
        pins.push((path.to_owned(), hash));
    }
    let rustc = PathBuf::from(env::var_os("RUSTC").ok_or("RUSTC absent")?);
    if !rustc.is_absolute() {
        return Err("RUSTC must be an absolute compiler path".into());
    }
    let compiler = fs::canonicalize(rustc)?;
    let version = Command::new(&compiler).arg("-vV").output()?;
    if !version.status.success() {
        return Err("compiler identity command failed".into());
    }
    let version = String::from_utf8(version.stdout)?;
    if !version.contains("-nightly") {
        return Err("nightly compiler required".into());
    }
    let compiler_sha = format!("{:x}", Sha256::digest(fs::read(&compiler)?));
    let generated = format!(
        "pub const SOURCE_PINS: &[(&str, &str)] = &{pins:?};\npub const COMPILER_PATH: &str = {:?};\npub const COMPILER_SHA256: &str = {compiler_sha:?};\npub const COMPILER_VERSION: &str = {version:?};\n",
        compiler.to_str().ok_or("compiler path is not UTF-8")?,
    );
    fs::write(
        PathBuf::from(env::var_os("OUT_DIR").ok_or("OUT_DIR absent")?).join("identity.rs"),
        generated,
    )?;
    Ok(())
}
