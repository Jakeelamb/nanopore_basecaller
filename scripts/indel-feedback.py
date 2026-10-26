#!/usr/bin/env python3
"""Launch the C++ F3 consumer inside a coordinator-admitted process unit."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("classify", "propose", "nominate-prefix", "controls", "prefix-controls"))
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.binary.is_absolute() or not args.binary.is_file():
        parser.error("--binary must name the admitted absolute C++ executable")
    argv = [str(args.binary), args.command]
    if args.command not in ("controls", "prefix-controls"):
        if not args.request or not args.request_sha256 or not args.output:
            parser.error("consumer commands require request, independent request hash and new output")
        argv.extend((str(args.request), args.request_sha256, str(args.output)))
    # Resource supervision, admission, receipts, and lock ownership belong to Root/F4.
    return subprocess.run(argv, cwd=Path(__file__).resolve().parents[1],
                          env=os.environ.copy(), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
