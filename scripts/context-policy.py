#!/usr/bin/env python3
"""Run one externally supervised, already admitted pure-policy request."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def read_pinned(path: Path, expected: str, maximum: int) -> bytes:
    if not path.is_absolute():
        raise ValueError("input path must be absolute")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("input size or SHA256 changed")
    return data


def write_fresh(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def run(args: argparse.Namespace) -> None:
    # Root's outer unit owns the lock, kernel caps, process tree, and full time/stderr receipts.
    # This adapter does not admit itself or claim process supervision qualification.
    if not args.output.is_absolute() or args.output.exists():
        raise ValueError("output must be a fresh absolute directory")
    request_bytes = read_pinned(args.request, args.request_sha256, 8 * 1024 * 1024)
    request = json.loads(request_bytes)
    pin = request["batch_pin"]
    batch_bytes = read_pinned(Path(pin["path"]), pin["sha256"], 8 * 1024 * 1024)
    if len(batch_bytes) != pin["size"]:
        raise ValueError("candidate batch size changed")
    read_pinned(args.binary, args.binary_sha256, 16 * 1024 * 1024)
    args.output.mkdir(parents=False)
    argv = [str(args.binary), "decide", str(args.request), args.request_sha256]
    started = time.time_ns()
    with (args.output / "stdout").open("xb") as stdout, (args.output / "stderr").open("xb") as stderr:
        try:
            result = subprocess.run(argv, cwd=Path(__file__).resolve().parents[1], stdout=stdout,
                                    stderr=stderr, timeout=args.timeout, check=False)
            code = result.returncode
            terminal = "exited"
        except subprocess.TimeoutExpired:
            code = None
            terminal = "timeout_unqualified_process_tree"
        stdout.flush()
        stderr.flush()
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    ended = time.time_ns()
    receipt = {
        "schema": "context-policy-command/1", "argv": argv,
        "cwd": str(Path(__file__).resolve().parents[1]),
        "environment": {name: os.environ.get(name) for name in
                        ("UV_OFFLINE", "UV_PYTHON_DOWNLOADS", "PYTHONDONTWRITEBYTECODE")},
        "request_sha256": args.request_sha256, "batch_pin": pin,
        "binary_sha256": args.binary_sha256, "start_ns": started, "end_ns": ended,
        "exit_code": code, "terminal": terminal, "outer_admission_required": True,
        "kernel_caps_proven_by_this_adapter": False,
    }
    # A terminal command record survives parse/projection failure. Completion is written last.
    write_fresh(args.output / "command.json", receipt)
    if code != 0:
        raise RuntimeError(f"policy command failed: {terminal}, exit={code}")
    with (args.output / "stdout").open("rb") as stream:
        output_bytes = stream.read(1024 * 1024 + 1)
    if len(output_bytes) > 1024 * 1024:
        raise ValueError("policy output exceeds 1 MiB")
    decision = json.loads(output_bytes)
    if decision["batch_sha256"] != pin["sha256"] or decision["binding"] != request["expected_binding"]:
        raise ValueError("policy output binding changed")
    write_fresh(args.output / "complete.json", {
        "schema": "context-policy-observation/1", "batch_pin": pin,
        "selected_candidate_id": decision["selected_candidate_id"],
        "command_sha256": hashlib.sha256((args.output / "command.json").read_bytes()).hexdigest(),
        "decision_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "confidence": decision["confidence"], "engineering_only": True,
        "native_science_qualified": False,
    })
    directory = os.open(args.output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "request", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--binary-sha256", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if not 0 < args.timeout <= 30:
        parser.error("timeout must be in (0,30]")
    run(args)


if __name__ == "__main__":
    main()
