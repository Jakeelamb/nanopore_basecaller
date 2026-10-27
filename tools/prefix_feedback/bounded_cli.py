"""Consume F4's frozen public CLI and retained receipts. Never own a host lock."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETRIEVAL = "/home/jake/Projects/nanopore_basecaller-retrieval"
UV = "/home/jake/.local/bin/uv"
F4 = dict(path="/home/jake/Projects/nanopore_basecaller-next-stock-compare/tools/stock_feedback/bounded.py",
          size=18293, sha256="8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4")
GUARD = dict(path="/tmp/nanopore-frontier/private-raw-case/cpu-qualification-prep-v1/process_guard.py",
             size=3443, sha256="dd90a7c50cd1b3044178e3ee248e7f5e948840496b1ad0cee3b99dadad6a14e9")
ENVIRONMENT = dict(LC_ALL="C", PATH="/usr/bin:/bin", HOME="/home/jake", UV_OFFLINE="1",
                   UV_PYTHON_DOWNLOADS="never", UV_PROJECT_ENVIRONMENT=RETRIEVAL + "/.venv",
                   PYTHONDONTWRITEBYTECODE="1")
RAW = ("command.json", "cwd.txt", "start.txt", "end.txt", "exit-status.txt", "stdout", "stderr", "time.txt")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(path):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "absolute regular nonsymlink pin required")
    with path.open("rb") as stream:
        result = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=result)


def check(value):
    require(pin(value["path"]) == value, "consumed pin differs: " + value["path"])


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 8 * 1024**2, "JSON metadata bound")
    return json.loads(path.read_text())


def fresh_bytes(path, value):
    with Path(path).open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fresh(path, value):
    fresh_bytes(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())


def same_json(path, value):
    if Path(path).exists():
        require(read(path) == value, "retained proposal/projection differs")
    else:
        fresh(path, value)


def same_bytes(path, value):
    if Path(path).exists():
        require(Path(path).read_bytes() == value, "retained query differs")
    else:
        fresh_bytes(path, value)


def admitted_worker():
    """Fail before body work outside the externally enforced F4 unit."""
    rows = Path("/proc/self/cgroup").read_text().splitlines()
    require(Path.cwd() == ROOT, "F1 worker cwd differs")
    require(any(row.startswith("0::") and "/feedback-next-" in row and row.endswith(".service") for row in rows),
            "whole-unit F4 admission required before worker body work")


def launch_argv(admission, expected_sha256, output):
    # Only bounded request/source metadata is read before exec. F4 checks all
    # executable, input and workload hashes inside its service, never here.
    require(Path(admission).stat().st_size <= 8 * 1024**2, "admission metadata bound")
    require(pin(admission)["sha256"] == expected_sha256, "external Root grant hash differs")
    request = read(admission)
    require(request["schema"] == "bounded-command/1" and request["root"] == str(ROOT)
            and request["cwd"] == str(ROOT) and Path.cwd() == ROOT, "Root/cwd grant differs")
    require(F4 in request["source_pins"], "frozen public F4 adapter pin absent")
    check(F4)
    return [UV, "run", "--project", RETRIEVAL, "--no-sync", "python", F4["path"], "run",
            "--request", str(admission), "--request-sha256", expected_sha256, "--output", str(output)]


class PendingCommand(Exception):
    def __init__(self, proposal):
        super().__init__("fresh Root grant required for next exact command")
        self.proposal = proposal


def proposal(argv, inputs, attempt, role, binding, sources, outputs):
    attempt = Path(attempt)
    require(attempt.is_absolute() and attempt.is_relative_to(ROOT), "proposal attempt outside F1")
    all_outputs = list(outputs) + [str(attempt / name) for name in ("stdout", "stderr", "time.txt")]
    names = {"prefix-location": ("query-fasta", "mapper-executable", "reference-index"),
             "reference-continuation": ("reference-fasta", "reference-fai", "samtools-executable"),
             "prefix-decoder": ("decoder-executable", "decoder-request")}[role]
    require(len(names) == len(inputs), "semantic input census differs")
    request = dict(root=str(ROOT), cwd=str(ROOT), argv=argv, env=ENVIRONMENT,
                   source_pins=sources, input_pins=inputs, expected_files=all_outputs,
                   roles=dict(unit={"prefix-location": "F1/mapper", "reference-continuation": "F1/samtools",
                                    "prefix-decoder": "F1/decoder"}[role],
                              inputs={name: index for index, name in enumerate(names)},
                              outputs={Path(path).name.replace(".", "-"): path for path in all_outputs}),
                   output_roots=list(dict.fromkeys((str(attempt.parent), str(ROOT / "results/prefix-feedback")))),
                   profile="mapping" if role == "prefix-location" else "engineering",
                   wall_seconds=300, cpus=2, swap_bytes=0, growth_bytes=104857600,
                   aggregate_bytes=4294967296, reserve_bytes=32212254720)
    request["memory_bytes"], request["address_space_bytes"] = (17179869184, 25769803776) if request["profile"] == "mapping" else (4294967296, 8589934592)
    return dict(schema="prefix-command-proposal/1", request=request, role=role, binding=binding,
                attempt=str(attempt), payload_outputs=list(outputs), authorization=False)


def normalize(complete_pin, expected, common_sources, output):
    """Run only as an admitted consumer. Preserve producer files, including failures."""
    check(complete_pin)
    complete = read(complete_pin["path"])
    require(complete["schema"] == "bounded-command-result/1" and complete["complete"] is True, "F4 completion differs")
    check(complete["admission"])
    grant = read(complete["admission"]["path"])
    require(grant["schema"] == "bounded-command/1" and all(grant[key] == value for key, value in expected["request"].items()),
            "Root grant does not bind the proposed exact command")
    attempt = Path(expected["attempt"])
    require(Path(complete_pin["path"]) == attempt / "complete.json", "foreign F4 attempt")
    terminal_pin = complete["terminal"]
    check(terminal_pin)
    terminal = read(terminal_pin["path"])
    require(terminal["exit_known"] is True and terminal["exit"] == 0 and terminal["error"] is None
            and terminal["cleanup"]["terminal"] is True, "F4 worker failed or exit unknown; producer replay prohibited")
    outer_pin = pin(attempt / "outer-terminal.json")
    outer = read(outer_pin["path"])
    proof = outer["proof"]
    require(outer["exit"] == 0 and outer["error"] is None and outer["worker_complete"] is True
            and outer["missing_worker_records"] == [] and outer["empty_before_unlock"] is True
            and proof["launcher_group_empty"] is True and proof["service_cgroup_empty"] is True
            and proof["launcher"]["terminal"] is True and proof["failures"] == [], "F4 outer terminal proof differs")
    for item in complete["linked"] + complete["raw"] + grant["source_pins"] + grant["input_pins"]:
        check(item)
    raw = {Path(item["path"]).name: item for item in complete["raw"]}
    require(set(raw) == set(RAW), "F4 raw command census differs")
    command = read(raw["command.json"]["path"])
    require(command == {key: grant[key] for key in ("argv", "cwd", "env", "source_pins", "input_pins", "roles")}, "F4 actual command differs")
    require({item["path"] for item in complete["linked"]} == set(grant["expected_files"]), "F4 successful output census differs")
    require(all(source in grant["source_pins"] for source in common_sources), "common frozen producer source absent")
    output = Path(output)
    output.mkdir(exist_ok=True)
    value = dict(role=expected["role"], argv=grant["argv"], cwd=grant["cwd"], environment=grant["env"],
                 inputs=grant["input_pins"], source_pins=common_sources,
                 produced_files=[item for item in complete["linked"] if item["path"] in expected["payload_outputs"]],
                 binding=expected["binding"], complete=True, exit_status=0, terminal=True,
                 stdout=raw["stdout"], stderr=raw["stderr"], time=raw["time.txt"])
    identity = {key: value[key] for key in ("role", "argv", "cwd", "environment", "inputs", "binding", "source_pins", "stdout", "produced_files")}
    same_json(output / "terminal.json", dict(group_empty=True, cgroup_empty=True, reaped=True, command=identity,
              f4_complete=complete_pin, f4_worker_terminal=terminal_pin, f4_outer_terminal=outer_pin))
    value["terminal_proof"] = pin(output / "terminal.json")
    value["f4_complete"] = complete_pin
    same_json(output / "receipt.json", value)
    return pin(output / "receipt.json"), value


class RetainedCommands:
    """Resume exact successful producers; propose a missing stage without running it."""
    def __init__(self, index, common_sources):
        self.index = index
        self.common_sources = common_sources
        require(index["schema"] == "prefix-command-index/1", "execution index schema differs")
        require(F4 in index["source_pins"], "frozen F4 source missing from command closure")

    def run(self, argv, inputs, output, role, binding, expected_files=()):
        executable = next((item for item in self.index["source_pins"] if item["path"] == argv[0]), None)
        require(executable is not None, "exact executable is absent from frozen execution closure")
        expected = proposal(argv, inputs, output, role, binding, self.index["source_pins"], expected_files)
        path = Path(output).parent / (Path(output).name + "-proposal.json")
        same_json(path, expected)
        expected_pin = pin(path)
        matches = [item for item in self.index["commands"] if item["proposal"] == expected_pin]
        require(len(matches) <= 1, "duplicate exact producer receipt")
        if not matches:
            require(not Path(output).exists(), "retained attempt has no accepted receipt; no automatic producer replay")
            raise PendingCommand(expected_pin)
        return normalize(matches[0]["complete"], expected, self.common_sources,
                         Path(output).parent / (Path(output).name + "-projection"))
