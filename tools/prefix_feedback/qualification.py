"""Hermetic engineering stages inside one externally enforced F4 unit."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import bounded_cli as io


def utc():
    return datetime.now(timezone.utc).isoformat()


def stage(argv, output, guard, env, cwd=None, input_pins=(), source_pins=(), expected_exit=0):
    output.mkdir()
    cwd = io.ROOT if cwd is None else Path(cwd)
    io.fresh(output / "command.json", dict(argv=argv, cwd=str(cwd), env=env,
             input_pins=list(input_pins), source_pins=list(source_pins)))
    started = utc()
    process = None
    cleanup = None
    failure = None
    exit_code = None
    try:
        with (output / "stdout").open("xb") as stdout, (output / "stderr").open("xb") as stderr:
            process = subprocess.Popen(["/usr/bin/time", "-v", "-o", str(output / "time.txt"), "--", *argv],
                cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            exit_code = process.wait()
    except BaseException as error:
        failure = repr(error)
    finally:
        if process is not None:
            try:
                cleanup = guard.stop_group(process, process.pid)
                exit_code = process.poll()
            except BaseException as error:
                failure = failure or repr(error)
        # Retain native clocks, exit and failure before any success projection.
        io.fresh(output / "terminal.json", dict(start=started, end=utc(), exit=exit_code,
                 exit_known=exit_code is not None, failure=failure, cleanup=cleanup,
                 command=io.pin(output / "command.json")))
    io.require(exit_code == expected_exit and failure is None and cleanup["terminal"], "engineering stage failed; retained " + str(output))
    return io.pin(output / "terminal.json")


def qualify(output):
    io.admitted_worker()
    output = Path(output)
    io.require(output.is_relative_to(io.ROOT / "results/prefix-feedback"), "qualification output outside F1")
    output.mkdir()
    io.check(io.GUARD)
    spec = importlib.util.spec_from_file_location("prefix_original_guard", io.GUARD["path"])
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.adopt_orphans()
    build = output / "build"
    env = dict(io.ENVIRONMENT, TMPDIR=str(output / "tmp"))
    Path(env["TMPDIR"]).mkdir()
    commands = [
        ["/usr/bin/cmake", "-S", str(io.ROOT / "tools/prefix_feedback"), "-B", str(build),
         "-DCMAKE_BUILD_TYPE=Release", "-DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results",
         "-DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format", "-DCMAKE_CXX_COMPILER=/usr/bin/c++"],
        ["/usr/bin/cmake", "--build", str(build), "--parallel", "2"],
        ["/usr/bin/cmake", "--build", str(build), "--target", "format-check", "--parallel", "1"],
        ["/usr/bin/ctest", "--test-dir", str(build), "--parallel", "1", "--output-on-failure", "--no-tests=error", "--output-junit", str(output / "ctest.xml")],
        [io.UV, "run", "--project", io.RETRIEVAL, "--no-sync", "python", "-m", "unittest", "discover",
         "-s", str(io.ROOT / "tests"), "-p", "test_prefix_feedback.py", "-v"],
    ]
    stages = []
    try:
        for index, argv in enumerate(commands):
            if index == 4:
                env["PREFIX_FEEDBACK_BINARY"] = str(build / "prefix-feedback")
            stages.append(stage(argv, output / ("stage-" + str(index)), guard, env))
        junit = ET.parse(output / "ctest.xml").getroot()
        suites = [junit] if junit.tag == "testsuite" else list(junit.iter("testsuite"))
        io.require(sum(int(value.get("tests", "0")) for value in suites) == 2
                   and all(int(value.get(key, "0")) == 0 for value in suites for key in ("failures", "errors", "skipped")),
                   "CTest did not execute clean skipped-zero tests")
        log = (build / "Testing/Temporary/LastTest.log").read_text()
        counters = []
        bridge = []
        for line in log.splitlines():
            try:
                value = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict) and "executed" in value:
                counters.append(value)
            if isinstance(value, dict) and "bridge_executed" in value:
                bridge.append(value)
        io.require(len(counters) == 1 and counters[0]["executed"] == 13
                   and counters[0]["failed"] == 0 and counters[0]["skipped"] == 0,
                   "actual C++ control census/skip count differs")
        io.require(len(bridge) == 1 and bridge[0]["bridge_executed"] == 8
                   and bridge[0]["failed"] == 0 and bridge[0]["skipped"] == 0,
                   "actual bridge control census/skip count differs")
        python_log = (output / "stage-4/stderr").read_text()
        count = re.search(r"^Ran ([0-9]+) tests? in ", python_log, re.M)
        io.require(count and int(count[1]) == 20 and re.search(r"^OK$", python_log, re.M)
                   and "skipped=" not in python_log and "FAILED" not in python_log,
                   "consumed Python tests did not execute clean skipped-zero tests")
        bridge_receipts = [io.pin(path) for path in sorted(Path(env["TMPDIR"]).glob("bridge-control-*/records/stage-*/receipt.json"))]
        io.require(len(bridge_receipts) == 26, "actual retained F1 bridge stage census differs")
        io.fresh(output / "complete.json", dict(schema="prefix-engineering/1", complete=True,
            stages=stages, binary=io.pin(build / "prefix-feedback"), ctest=io.pin(output / "ctest.xml"),
            actual_cpp_controls=counters[0], actual_bridge_controls=bridge[0], actual_python_tests=int(count[1]), skipped=0,
            actual_bridge_stage_receipts=bridge_receipts,
            hermetic_only=True, genuine_mapper_qualified=False, biological_qualified=False))
    except BaseException as error:
        io.fresh(output / "failed.json", dict(error=repr(error), completed_stages=stages,
                 producer_replay_permitted=False, utc=utc()))
        raise
