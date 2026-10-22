"""Acquire a manifest asset with restartable, checked HTTP ranges."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("asset", help="Asset ID in config/assets.json")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
assets = json.loads((root / "config/assets.json").read_text())
asset = next(item for item in assets if item["id"] == args.asset)
target = root / asset["path"]
size = asset["bytes"]
target.parent.mkdir(parents=True, exist_ok=True)
if shutil.disk_usage(root).free < size * 2 + 30 * 1024**3 and not target.exists():
    raise SystemExit("Insufficient space to preserve the 30 GiB reserve")
parts = target.with_name(target.name + ".parts")
parts.mkdir(exist_ok=True)
chunk_size = 64 * 1024**2
ranges = [(i, min(i + chunk_size, size) - 1) for i in range(0, size, chunk_size)]


def response_range(path):
    blocks = [block for block in path.read_text().lower().replace("\r", "").split("\n\n")
              if block.lstrip().startswith("http/")]
    lines = blocks[-1].strip().splitlines() if blocks else []
    if not lines or lines[0].split()[1:2] != ["206"]:
        raise ValueError(f"Unverified partial HTTP response: {path}")
    values = [line.strip() for line in lines if line.startswith("content-range:")]
    match = re.fullmatch(r"content-range:\s*bytes (\d+)-(\d+)/(\d+)", values[0]) if len(values) == 1 else None
    if match is None:
        raise ValueError(f"Invalid range header: {path}")
    return tuple(map(int, match.groups()))


def absorb_remainder(temporary, remainder, headers, start, end):
    if not remainder.exists():
        return
    received = remainder.stat().st_size
    if received == 0:
        remainder.unlink()
        return
    first, last, total = response_range(headers)
    if last != end or total != size or not 0 < received <= last - first + 1:
        raise ValueError(f"Unverified cached remainder: {remainder}")
    offset = temporary.stat().st_size
    if first == start + offset:
        combined = temporary.with_suffix(".merge")
        with combined.open("wb") as output:
            for source_path in (temporary, remainder):
                with source_path.open("rb") as source:
                    shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        combined.replace(temporary)
    elif first + received == start + offset:
        with temporary.open("rb") as source:
            source.seek(-received, os.SEEK_END)
            if source.read() != remainder.read_bytes():
                raise ValueError("Interrupted merge contains inconsistent bytes")
    else:
        raise ValueError("Cached remainder does not follow the verified prefix")
    remainder.unlink()


def fetch(bounds):
    start, end = bounds
    part = parts / str(start)
    if part.exists() and part.stat().st_size == end - start + 1:
        return part
    temporary = part.with_suffix(".partial")
    headers = part.with_suffix(".headers")
    offset = 0
    if temporary.exists() and temporary.stat().st_size:
        if response_range(headers) != (start, end, size):
            raise ValueError(f"Unverified partial range for {asset['id']} at {start}")
        absorb_remainder(temporary, part.with_suffix(".remainder"),
                         part.with_suffix(".remainder-headers"), start, end)
        offset = temporary.stat().st_size
        if offset > end - start + 1:
            raise ValueError("Partial range exceeds its declared size")
    if offset == end - start + 1:
        temporary.replace(part)
        return part
    remainder = part.with_suffix(".remainder") if offset else temporary
    response_headers = part.with_suffix(".remainder-headers") if offset else headers
    condition = ["--header", f"If-Match: \"{asset['etag']}\""] if asset.get("etag") else []
    subprocess.run([
        "curl", "--fail", "--silent", "--show-error", "--location", "--retry", "5", "--retry-all-errors",
        "--connect-timeout", "30", "--max-time", "3600", "--speed-limit", "1024",
        "--speed-time", "60", "--range", f"{start + offset}-{end}",
        "--dump-header", str(response_headers), "--output", str(remainder), *condition, asset["url"],
    ], check=True)
    if response_range(response_headers) != (start + offset, end, size) or remainder.stat().st_size != end - start + 1 - offset:
        raise ValueError(f"Invalid range response for {asset['id']} at {start}")
    if offset:
        absorb_remainder(temporary, remainder, response_headers, start, end)
    temporary.replace(part)
    print(f"{asset['id']} completed bytes {start}-{end} of {size}", flush=True)
    return part


candidate = target
if not target.exists():
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        downloaded = list(pool.map(fetch, ranges))
    temporary = target.with_name(target.name + ".partial")
    with temporary.open("wb") as output:
        for part in downloaded:
            with part.open("rb") as source:
                shutil.copyfileobj(source, output)
        output.flush()
        os.fsync(output.fileno())
    candidate = temporary
if candidate.stat().st_size != size:
    raise SystemExit(f"Wrong size for {target}")
checks = {name: hashlib.new(name) for name in ("sha256", "md5")}
with candidate.open("rb") as source:
    for block in iter(lambda: source.read(8 * 1024**2), b""):
        for check in checks.values():
            check.update(block)
for name in checks:
    if asset.get(name) and checks[name].hexdigest() != asset[name]:
        raise SystemExit(f"{name} mismatch for {target}")
print(json.dumps({"id": asset["id"], "bytes": size, **{k: v.hexdigest() for k, v in checks.items()}}))
if candidate != target:
    candidate.replace(target)
shutil.rmtree(parts)
