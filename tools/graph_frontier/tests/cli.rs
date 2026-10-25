use serde_json::json;
use sha2::{Digest, Sha256};
use std::{path::PathBuf, process::Command};

#[test]
fn help_describes_real_emit_interface() {
    let output = Command::new(env!("CARGO_BIN_EXE_graph-frontier"))
        .arg("--help")
        .output()
        .expect("run help");
    assert!(output.status.success());
    let text = String::from_utf8(output.stdout).expect("help text");
    assert!(text.contains("emit --cohort COHORT_JSON --protocol PROTOCOL_JSON --output NEWDIR"));
    assert!(text.contains("complete.json"));
}

#[test]
fn malformed_command_and_missing_evidence_fail_without_completion() {
    let binary = env!("CARGO_BIN_EXE_graph-frontier");
    assert!(!Command::new(binary)
        .args(["emit", "--cohort", "a", "--cohort", "b", "--output", "c"])
        .output()
        .expect("duplicate options")
        .status
        .success());
    let output: PathBuf =
        std::env::temp_dir().join(format!("graph-frontier-cli-failure-{}", std::process::id()));
    let status = Command::new(binary)
        .args([
            "emit",
            "--cohort",
            "/missing-frontier-cohort",
            "--protocol",
            "/missing-frontier-protocol",
            "--output",
        ])
        .arg(&output)
        .output()
        .expect("run failure");
    assert!(!status.status.success());
    assert!(status.stdout.is_empty());
    assert!(output.is_dir());
    assert!(!output.join("complete.json").exists());
    std::fs::remove_dir_all(output).expect("remove test output");
}

#[test]
fn successful_process_prints_only_final_completion_pin() {
    let root =
        std::env::temp_dir().join(format!("graph-frontier-cli-success-{}", std::process::id()));
    std::fs::create_dir(&root).expect("fixture directory");
    for (name, data) in [
        ("parents", "parent-1\n"),
        ("sam", "parent-1\t4\t*\t0\t0\t*\t*\t0\t0\tA\tI\n"),
        ("windows", ""),
        ("decisions", ""),
        ("graph", ""),
    ] {
        std::fs::write(root.join(name), data).expect("fixture file");
    }
    let pin = |name: &str| {
        let path = root.join(name);
        let bytes = std::fs::read(&path).expect("read fixture");
        json!({"path":path,"size":bytes.len(),"sha256":format!("{:x}",Sha256::digest(bytes))})
    };
    let cohort = json!({"schema":"graph-frontier-cohort/1","role":"development","pins":{"parents":pin("parents"),"native_sam":pin("sam"),"windows":pin("windows"),"decisions":pin("decisions"),"graph_walks":pin("graph")}});
    std::fs::write(
        root.join("cohort"),
        serde_json::to_vec(&cohort).expect("cohort"),
    )
    .expect("write cohort");
    std::fs::write(root.join("protocol"),serde_json::to_vec(&json!({"schema":"graph-frontier-protocol/1","policies":[{"id":"native","prior":"none","lambda":0,"margin":0.5,"neural_deficit":0}]})).expect("protocol")).expect("write protocol");
    let output = Command::new(env!("CARGO_BIN_EXE_graph-frontier"))
        .args(["emit", "--cohort"])
        .arg(root.join("cohort"))
        .arg("--protocol")
        .arg(root.join("protocol"))
        .arg("--output")
        .arg(root.join("out"))
        .output()
        .expect("emit process");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let text = String::from_utf8(output.stdout).expect("stdout");
    assert_eq!(text.lines().count(), 1);
    let value: serde_json::Value = serde_json::from_str(&text).expect("completion JSON");
    assert_eq!(value.as_object().expect("object").len(), 1);
    assert_eq!(value["completion"], pin("out/complete.json"));
    let summary: serde_json::Value =
        serde_json::from_slice(&std::fs::read(root.join("out/summary.json")).expect("summary"))
            .expect("summary JSON");
    assert_eq!(
        summary["input_custody"]["producer_output_binding_verified"],
        false
    );
    std::fs::remove_dir_all(root).expect("remove fixture");
}
