"""Record one sequential engineering chain inside Root's frozen F4 whole unit."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "/home/jake/Projects/nanopore_basecaller-retrieval"
UV = "/home/jake/.local/bin/uv"
TOOL = "indel-feedback"
BINARY_ENV = "INDEL_FEEDBACK_BINARY"
TEST_COUNT = 7
CTEST_NAMES = ["indel_controls"]
CONTROL_NAMES = ["tiny exhaustive census and total marginal mass","repeated paths aggregate instead of Viterbi","known run lengths two three four","nonrepeat insertion ambiguity","bounded deterministic nomination without truth","both terminal insertions excluded","two flank insertion and gap rejection","deletion boundaries and event base separation","adjacent insertion deletion","repeat annotation and chunk overlap are not partitions","zero exposure preserves no counted events","reverse SAM uses alignment oriented SEQ","full forward reverse and disabled SEQ Q","invalid score geometry alphabet CIGAR rejects"]
RAW = ("command.json", "cwd.txt", "start.txt", "end.txt", "exit-status.txt",
       "stdout", "stderr", "time.txt")


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    with path.open("x") as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def pin(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return dict(path=str(path), size=path.stat().st_size, sha256=digest.hexdigest())


def stage(output, name, argv, env):
    directory = output / name
    directory.mkdir()
    actual = ["/usr/bin/time", "--verbose", "--output", str(directory / "time.txt"), *argv]
    write(directory / "command.json", dict(argv=argv, recorder_argv=actual, cwd=str(ROOT), env=env))
    write(directory / "cwd.txt", str(ROOT) + "\n")
    write(directory / "start.txt", utc() + "\n")
    code, error = None, None
    try:
        with (directory / "stdout").open("xb") as stdout, (directory / "stderr").open("xb") as stderr:
            try:
                code = subprocess.run(actual, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                      check=False).returncode
            finally:
                for stream in (stdout, stderr):
                    stream.flush()
                    os.fsync(stream.fileno())
    except BaseException as caught:
        error = repr(caught)
        raise
    finally:
        write(directory / "end.txt", utc() + "\n")
        write(directory / "exit-status.txt", ("unknown" if code is None else str(code)) + "\n")
        write(directory / "terminal.json", dict(exit_code=code, error=error,
              missing_raw=[name for name in RAW if not (directory / name).is_file()],
              outer_process_cleanup_required=True))
    if code != 0:
        raise RuntimeError(f"{name} failed with exit {code}; retained {directory}")
    missing = [name for name in RAW if not (directory / name).is_file()]
    if missing or not (directory / "time.txt").stat().st_size:
        raise RuntimeError(f"{name} recorder incomplete: {missing}")
    write(directory / "complete.json", dict(raw=[pin(directory / name) for name in RAW]))


def unittest_report(path):
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_indel_feedback.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(tests=result.testsRun, failures=[test.id() for test, _ in result.failures],
                  errors=[test.id() for test, _ in result.errors],
                  skipped=[dict(test=test.id(), reason=reason) for test, reason in result.skipped],
                  expected_failures=[test.id() for test, _ in result.expectedFailures],
                  unexpected_successes=[test.id() for test in result.unexpectedSuccesses])
    write(path, report)
    return 0 if (result.wasSuccessful() and result.testsRun == TEST_COUNT
                 and not result.skipped and not result.expectedFailures) else 1


def junit_report(path):
    document = ET.parse(path)
    cases = document.findall(".//testcase")
    names = [case.attrib["name"] for case in cases]
    if sorted(names) != sorted(CTEST_NAMES) or any(
            case.find(tag) is not None for case in cases for tag in ("skipped", "failure", "error")):
        raise ValueError("CTest execution census/failure/skip differs")
    controls = []
    if CONTROL_NAMES:
        lines = [line.strip() for case in cases
                 for line in (case.findtext("system-out") or "").splitlines()]
        controls = [line[5:] for line in lines if line.startswith("PASS ")]
        if sorted(controls) != sorted(CONTROL_NAMES) or "controls_executed=14 skipped=0" not in lines:
            raise ValueError("F3 named control execution census differs")
    return dict(tests=len(cases), skipped=0, names=names, control_groups=controls)


def interrupted(signum, _frame):
    raise InterruptedError(f"whole-unit signal {signum}; outer F4 cleanup required")


def qualify(output):
    if Path.cwd() != ROOT or not output.is_absolute() or output.exists():
        raise ValueError("require admitted source cwd and fresh absolute output")
    env = os.environ.copy()
    required = dict(UV_PROJECT_ENVIRONMENT=PROJECT + "/.venv", UV_OFFLINE="1",
                    UV_PYTHON_DOWNLOADS="never", PYTHONDONTWRITEBYTECODE="1")
    if any(env.get(key) != value for key, value in required.items()):
        raise ValueError("fixed offline UV environment differs")
    output.mkdir(parents=True)
    build = output / "build"
    env[BINARY_ENV] = str(build / TOOL)
    stages = (
        ("configure", ["/usr/bin/cmake", "-S", str(ROOT / "tools/indel_feedback"), "-B", str(build),
                       "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_COMPILER=/usr/bin/c++",
                       "-DCMAKE_MAKE_PROGRAM=/usr/bin/make", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                       "-DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results",
                       "-DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format"]),
        ("build", ["/usr/bin/cmake", "--build", str(build), "--parallel", "2"]),
        ("format-check", ["/usr/bin/cmake", "--build", str(build), "--target", "format-check", "--parallel", "1"]),
        ("ctest", ["/usr/bin/ctest", "--test-dir", str(build), "--parallel", "1", "--output-on-failure",
                   "--no-tests=error", "--output-junit", str(output / "ctest.xml")]),
        ("uv-tests", [UV, "run", "--project", PROJECT, "--no-sync", "python", str(Path(__file__).resolve()),
                      "--unittest-report", str(output / "unittest.json")]),
    )
    error, completed = None, []
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    try:
        for name, argv in stages:
            stage(output, name, argv, env)
            completed.append(name)
        ctest = junit_report(output / "ctest.xml")
        python = json.loads((output / "unittest.json").read_text())
        if python["tests"] != TEST_COUNT or any(python[key] for key in
                ("skipped", "errors", "failures", "expected_failures", "unexpected_successes")):
            raise ValueError("UV unittest execution census/failure/skip differs")
        result = dict(schema="indel-feedback-engineering/1", engineering_only=True, ctest=ctest, python=python,
                      binary=pin(build / TOOL), compile_commands=pin(build / "compile_commands.json"),
                      outer_f4_terminal_proof_required=True, scientific_integration_qualified=False)
    except BaseException as caught:
        error = repr(caught)
        raise
    finally:
        write(output / "terminal.json", dict(end=utc(), error=error, completed_stages=completed))
    write(output / "complete.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--unittest-report", type=Path)
    args = parser.parse_args()
    if args.unittest_report:
        return unittest_report(args.unittest_report)
    qualify(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
