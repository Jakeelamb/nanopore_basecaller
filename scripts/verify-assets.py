"""Check acquired assets against upstream checksums and the frozen local lock."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--freeze", action="store_true", help="Create the initial local hash lock")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
assets = json.loads((root / "config/assets.json").read_text())
records = []
for asset in assets:
    path = root / asset["path"]
    if path.stat().st_size != asset["bytes"]:
        raise ValueError(f"Wrong byte size: {path}")
    checks = {name: hashlib.new(name) for name in ("sha256", "md5")}
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024**2), b""):
            for check in checks.values():
                check.update(block)
    for name, check in checks.items():
        if asset.get(name) and asset[name] != check.hexdigest():
            raise ValueError(f"Upstream {name} mismatch: {path}")
    records.append({**asset, **{name: check.hexdigest() for name, check in checks.items()}})
    print(f"PASS {asset['id']} {path.stat().st_size} bytes", flush=True)
head = subprocess.check_output(["git", "-C", str(root / "software/dorado-src"),
                                "rev-parse", "HEAD"], text=True).strip()
if head != "8b8fc5d36a9c0baab262a743cb175b5878e38ca6":
    raise ValueError("Stock Dorado source is not pinned to the expected commit")
dirty = subprocess.check_output(["git", "-C", str(root / "software/dorado-src"),
                                 "status", "--porcelain", "--ignore-submodules=none"], text=True)
if dirty:
    raise ValueError("Stock Dorado source checkout has changes")
submodules = subprocess.check_output(["git", "-C", str(root / "software/dorado-src"),
                                      "submodule", "status", "--recursive"], text=True)
if any(line and line[0] in "-+U" for line in submodules.splitlines()):
    raise ValueError("Stock Dorado submodules are incomplete or differ from their pinned revisions")
lock = root / "provenance/assets.lock.json"
if args.freeze:
    with lock.open("x") as handle:
        handle.write(json.dumps(records, indent=2) + "\n")
else:
    if json.loads(lock.read_text()) != records:
        raise ValueError("Asset manifest or acquired bytes differ from the frozen lock")
print(f"PASS {len(records)} assets and unmodified stock source")
