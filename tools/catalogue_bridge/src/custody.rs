use anyhow::{ensure, Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Pin {
    pub path: PathBuf,
    pub size: u64,
    pub sha256: String,
}
pub fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
pub fn pin(path: &Path) -> Result<Pin> {
    let path = fs::canonicalize(path)?;
    let mut f = fs::File::open(&path)?;
    let mut h = Sha256::new();
    let mut size = 0;
    let mut buf = [0u8; 65536];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
        size += n as u64;
    }
    Ok(Pin {
        path,
        size,
        sha256: format!("{:x}", h.finalize()),
    })
}
pub fn check(p: &Pin) -> Result<()> {
    ensure!(p.path.is_absolute(), "absolute pin required");
    ensure!(pin(&p.path)? == *p, "pin changed {}", p.path.display());
    Ok(())
}
pub fn read(path: &Path) -> Result<Value> {
    serde_json::from_slice(&fs::read(path)?).with_context(|| format!("JSON {}", path.display()))
}
pub fn value_pin(v: &Value) -> Result<Pin> {
    Ok(serde_json::from_value(v.clone())?)
}
pub fn checked(v: &Value) -> Result<Pin> {
    let p = value_pin(v)?;
    check(&p)?;
    Ok(p)
}
pub fn fresh(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut f = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    f.write_all(bytes)?;
    f.sync_all()?;
    Ok(())
}
pub fn write(path: &Path, v: &Value) -> Result<()> {
    fresh(path, &serde_json::to_vec_pretty(v)?)
}
pub fn collect(v: &Value, out: &mut BTreeMap<PathBuf, Pin>) -> Result<()> {
    match v {
        Value::Object(m) => {
            if m.contains_key("path") && m.contains_key("size") && m.contains_key("sha256") {
                let p = Pin {
                    path: PathBuf::from(v["path"].as_str().context("pin path")?),
                    size: v["size"].as_u64().context("pin size")?,
                    sha256: v["sha256"].as_str().context("pin hash")?.into(),
                };
                if let Some(previous) = out.insert(p.path.clone(), p.clone()) {
                    ensure!(previous == p, "conflicting registered pin");
                }
            }
            for child in m.values() {
                collect(child, out)?;
            }
        }
        Value::Array(a) => {
            for child in a {
                collect(child, out)?;
            }
        }
        _ => {}
    };
    Ok(())
}
pub fn verify_pin_tree(v: &Value) -> Result<()> {
    let mut pins = BTreeMap::new();
    collect(v, &mut pins)?;
    for p in pins.values() {
        check(p)?;
    }
    Ok(())
}

pub fn verify_seal(path: &Path, schema: &str) -> Result<Value> {
    let v = read(path)?;
    ensure!(
        v["schema"] == schema && v["complete"] == true,
        "incomplete/wrong seal"
    );
    verify_pin_tree(&v)?;
    Ok(v)
}

pub fn recorder(v: &Value, expected_argv: &Value, completion: &Pin) -> Result<()> {
    ensure!(
        v["schema"] == "catalogue-bridge-recorder/1" && v["status"] == "finished" && v["exit"] == 0,
        "unsuccessful bridge recorder"
    );
    ensure!(
        v["argv"] == *expected_argv,
        "recorder command does not produce intended output"
    );
    verify_pin_tree(&v["files"])?;
    let files = &v["files"];
    let text =
        |key: &str| -> Result<String> { Ok(fs::read_to_string(value_pin(&files[key])?.path)?) };
    ensure!(text("exit-status.txt")?.trim() == "0", "raw producer exit");
    ensure!(
        text("start.txt")?.trim() == v["started_utc"].as_str().context("start clock")?
            && text("end.txt")?.trim() == v["ended_utc"].as_str().context("end clock")?,
        "clock mismatch"
    );
    ensure!(
        v["started_utc"].as_str() < v["ended_utc"].as_str(),
        "invalid recorder clocks"
    );
    let command: Value = serde_json::from_str(&text("command.json")?)?;
    ensure!(command == *expected_argv, "raw command differs");
    let stdout: Value = serde_json::from_str(&text("stdout")?)?;
    ensure!(
        stdout == json!({"completion":completion}),
        "recorder stdout completion binding failed"
    );
    let executable = checked(&v["executable"])?;
    ensure!(
        expected_argv[0].as_str() == executable.path.to_str(),
        "wrong executable"
    );
    Ok(())
}

pub fn original(manifest: &Value) -> Result<(Value, Value)> {
    let p = checked(&manifest["original_cohort"])?;
    ensure!(
        p.sha256 == "ac14c13bf51865af3bb9c69ce8266694efa7e7a9e84d17454946ea3febefa814",
        "unregistered original cohort"
    );
    let report = checked(&manifest["pilot_report"])?;
    ensure!(
        report.sha256 == "e3f008ec03e56a836c6dbb07e5fbf81deae8cb1e2ac45093d88a3306055dc8b5",
        "unregistered pilot report"
    );
    let mut registry = BTreeMap::new();
    collect(&read(&report.path)?, &mut registry)?;
    let artifacts: Vec<_> = registry
        .values()
        .filter(|p| {
            p.path.to_string_lossy().contains("/artifacts/")
                && p.path.extension().is_some_and(|s| s == "json")
        })
        .cloned()
        .collect();
    for p in artifacts {
        check(&p)?;
        collect(&read(&p.path)?, &mut registry)?;
    }
    let cohort = read(&p.path)?;
    ensure!(
        cohort["schema"] == "graph-frontier-cohort/1" && cohort["role"] == "development",
        "development cohort required"
    );
    let mut wanted = BTreeMap::new();
    collect(&cohort, &mut wanted)?;
    for p in wanted.values() {
        ensure!(
            registry.get(&p.path) == Some(p),
            "cohort lacks registered ancestry {}",
            p.path.display()
        );
        check(p)?;
    }
    let producer = read(&value_pin(&cohort["producer_receipt"])?.path)?;
    ensure!(
        producer["status"] == "finished" && producer["exit"] == 0,
        "original producer failed"
    );
    verify_pin_tree(&producer["pins"])?;
    let argv = producer["argv"].as_array().context("original argv")?;
    ensure!(argv[1] == "decode", "wrong likelihood producer");
    let arg = |key: &str| -> Result<PathBuf> {
        let i = argv.iter().position(|v| v == key).context("original arg")?;
        Ok(PathBuf::from(
            argv.get(i + 1)
                .and_then(Value::as_str)
                .context("arg value")?,
        ))
    };
    for (key, field) in [
        ("--parents", "parents"),
        ("--windows", "windows"),
        ("--graph", "graph_walks"),
    ] {
        ensure!(
            arg(key)? == value_pin(&cohort["pins"][field])?.path,
            "original producer/cohort mismatch"
        );
    }
    ensure!(
        arg("--output")?.join("decisions.jsonl") == value_pin(&cohort["pins"]["decisions"])?.path,
        "original decision output mismatch"
    );
    let recorder = PathBuf::from(producer["recorder"].as_str().context("original recorder")?);
    ensure!(
        fs::read_to_string(recorder.join("exit-status.txt"))?.trim() == "0",
        "original raw exit"
    );
    let raw = fs::read_to_string(recorder.join("command.sh"))?;
    ensure!(
        raw.split_whitespace().collect::<Vec<_>>()
            == argv
                .iter()
                .map(|v| v.as_str().context("argv string"))
                .collect::<Result<Vec<_>>>()?,
        "original command binding"
    );
    let baseline = pin(&arg("--sam")?)?;
    let candidates: Vec<_> = registry
        .values()
        .filter(|p| {
            p.path
                .to_string_lossy()
                .contains("/development/stages/native-sam/")
                && p.path.file_name().is_some_and(|n| n == "finish.json")
        })
        .cloned()
        .collect();
    let mut baseline_producers = Vec::new();
    for p in candidates {
        check(&p)?;
        let native = read(&p.path)?;
        if native["stdout"].as_str() == baseline.path.to_str() {
            ensure!(
                native["status"] == "finished" && native["exit"] == 0,
                "native SAM producer incomplete"
            );
            verify_pin_tree(&native["pins"])?;
            collect(&native, &mut registry)?;
            baseline_producers.push(p);
        }
    }
    ensure!(
        baseline_producers.len() == 1 && registry.get(&baseline.path) == Some(&baseline),
        "scoring baseline lacks registered ancestry"
    );
    Ok((
        cohort,
        json!({"cohort":p,"frozen_pilot_report":report,"likelihood_producer":producer,"scoring_baseline_sam":baseline,"scoring_baseline_producers":baseline_producers}),
    ))
}

pub fn catalogue(manifest: &Value, cohort: &Value) -> Result<Value> {
    let completion = checked(&manifest["catalogue_completion"])?;
    ensure!(
        completion.sha256 == "949ad1b4528f968b77abc5bf2971e53de540ac40bf02c18d96ad094bdd871efc",
        "unregistered catalogue completion"
    );
    let seal = verify_seal(&completion.path, "frontier-catalogue-complete/1")?;
    ensure!(seal["kind"] == "full", "full catalogue required");
    ensure!(
        seal["decisions"]["sha256"]
            == "59e2885e4c657f8c2421c14b7deb562721e4494ce629057db12f1d2946fb0ef1",
        "wrong producer decisions"
    );
    let summary = read(&value_pin(&seal["summary"])?.path)?;
    ensure!(
        summary["complete"] == true
            && summary["cohort_pin"] == manifest["original_cohort"]
            && summary["input_pins"] == *cohort,
        "original-cohort mismatch"
    );
    for (key, n) in [
        ("planned_windows", 451),
        ("scored_windows", 331),
        ("original_excluded_windows", 120),
        ("parents", 64),
        ("deduplicated", 3118978),
    ] {
        ensure!(summary[key] == n, "wrong producer accounting {key}");
    }
    let attempt_pin = checked(&manifest["catalogue_attempt"])?;
    ensure!(
        attempt_pin.path
            == completion
                .path
                .parent()
                .context("completion parent")?
                .join("attempt.json"),
        "wrong catalogue attempt"
    );
    let attempt = read(&attempt_pin.path)?;
    ensure!(
        attempt["cohort_pin"] == manifest["original_cohort"]
            && attempt["compiled_source_pins"] == summary["compiled_source_pins"],
        "producer compiled closure mismatch"
    );
    verify_pin_tree(&summary["compiled_source_pins"])?;
    verify_pin_tree(&attempt["source_pins"])?;
    let binary = checked(&summary["final_binary_pin"])?;
    ensure!(
        binary.sha256 == "b56b4791c61ef05479328810ba26d854cac5be23795b5d50af093b70796045e0",
        "wrong producer binary"
    );
    let files = &manifest["catalogue_recorder"];
    verify_pin_tree(files)?;
    let raw =
        |name: &str| -> Result<String> { Ok(fs::read_to_string(value_pin(&files[name])?.path)?) };
    ensure!(raw("exit-status.txt")?.trim() == "0", "catalogue raw exit");
    ensure!(
        raw("cwd.txt")?.trim()
            == manifest["catalogue_cwd"]
                .as_str()
                .context("catalogue cwd")?,
        "catalogue cwd mismatch"
    );
    let argv = attempt["argv"].as_array().context("catalogue argv")?;
    let argv = argv
        .iter()
        .map(|v| v.as_str().context("argv string"))
        .collect::<Result<Vec<_>>>()?;
    let expected = [
        "tools/frontier_catalogue/target/release/frontier-catalogue",
        "catalogue",
        "--cohort",
        "results/reference-frontier/decision-v2/development-cohort.json",
        "--export",
        "results/graph-prior/pilot-v1/development/native-export",
        "--output",
        "results/reference-frontier/catalogue-v1/full-roundtrip",
        "--checkpoint",
        "results/reference-frontier/catalogue-v1/checkpoint-roundtrip",
    ];
    ensure!(argv == expected, "wrong catalogue native argv");
    let wrapper=format!("flock -w 60 /home/jake/Projects/nanopore_basecaller/results/stock/host.lock /usr/bin/time -v {} \n",argv.join(" "));
    ensure!(
        raw("command.sh")? == wrapper && manifest["catalogue_command"] == wrapper,
        "wrong catalogue wrapper/native argv"
    );
    let cwd = PathBuf::from(manifest["catalogue_cwd"].as_str().context("cwd")?);
    ensure!(
        fs::canonicalize(cwd.join(argv[0]))? == binary.path
            && fs::canonicalize(cwd.join(argv[7]))?
                == completion.path.parent().context("parent")?,
        "catalogue command output/binary mismatch"
    );
    let stdout: Value = serde_json::from_str(&raw("stdout")?)?;
    ensure!(
        stdout == json!({"completion":completion,"partial":false}),
        "catalogue stdout binding failed"
    );
    let start = raw("start.txt")?;
    let end = raw("end.txt")?;
    ensure!(
        start.trim().ends_with('Z') && start < end,
        "invalid catalogue clocks"
    );
    let cp = checked(&manifest["checkpoint_completion"])?;
    ensure!(
        cp.path == fs::canonicalize(cwd.join(argv[9]))?.join("complete.json"),
        "wrong checkpoint"
    );
    let checkpoint = read(&cp.path)?;
    ensure!(
        checkpoint["kind"] == "checkpoint" && checkpoint["complete"] == false,
        "checkpoint incomplete"
    );
    verify_pin_tree(&checkpoint)?;
    Ok(
        json!({"completion":completion,"seal":seal,"attempt":attempt_pin,"compiled_source_pins":summary["compiled_source_pins"],"binary":binary,"checkpoint_completion":cp,"raw_recorder":files,"native_argv":argv,"wrapper":wrapper,"derived_admission":true,"retained_observations_not_replayed":true}),
    )
}
