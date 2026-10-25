"""Decode public POD5 signals, check chemistry, and freeze pilot membership."""

import csv
import hashlib
import json
import math
from pathlib import Path

import pod5

root = Path(__file__).resolve().parents[1]
assets = [asset for asset in json.loads((root / "config/assets.json").read_text())
          if asset["role"] in ("development", "validation", "sealed_test")]
if {asset["role"] for asset in assets} != {"development", "validation", "sealed_test"}:
    raise ValueError("The pilot requires development, validation, and sealed_test signal assets")
out = root / "data/splits"
out.mkdir(parents=True, exist_ok=True)
seen = set()
summaries = []
rows = []
for asset in assets:
    read_ids = []
    sample_counts = []
    acquisition_ids = set()
    sample_ids = set()
    starts = []
    channels = set()
    with pod5.Reader(root / asset["path"]) as reader:
        for read in reader.reads():
            read_id = str(read.read_id)
            if read_id in seen:
                raise ValueError(f"Duplicate read UUID across pilot partitions: {read_id}")
            seen.add(read_id)
            run = read.run_info
            if run.sample_rate != 5000 or run.flow_cell_id != asset["flowcell"]:
                raise ValueError(f"Unexpected sample rate or flowcell: {read_id}")
            if run.sequencing_kit != "sqk-lsk114":
                raise ValueError(f"Unexpected kit {run.sequencing_kit}: {read_id}")
            signal = read.signal
            if len(signal) == 0 or len(signal) != read.num_samples:
                raise ValueError(f"Empty or inconsistent signal: {read_id}")
            if (not math.isfinite(read.calibration.scale)
                    or not math.isfinite(read.calibration.offset)
                    or read.calibration.scale <= 0):
                raise ValueError(f"Invalid physical-current calibration: {read_id}")
            read_ids.append(read_id)
            sample_counts.append(len(signal))
            acquisition_ids.add(run.acquisition_id)
            sample_ids.add(run.sample_id)
            starts.append(read.start_sample / run.sample_rate)
            channels.add(read.pore.channel)
            rows.append([asset["role"], asset["sample"], asset["flowcell"], read_id,
                         run.acquisition_id, read.pore.channel, read.pore.well,
                         read.read_number, read.start_sample, len(signal),
                         run.sample_rate, read.calibration.offset, read.calibration.scale,
                         int(signal.min()), int(signal.max())])
    if not read_ids:
        raise ValueError(f"No reads in {asset['id']}")
    membership = "".join(value + "\n" for value in sorted(read_ids))
    target = out / (asset["role"] + ".txt")
    if target.exists() and target.read_text() != membership:
        raise ValueError(f"Frozen membership changed: {target}")
    target.write_text(membership)
    sorted_counts = sorted(sample_counts)
    summaries.append({
        "id": asset["id"], "role": asset["role"], "sample": asset["sample"],
        "flowcell": asset["flowcell"], "reads": len(read_ids),
        "signal_samples": sum(sample_counts), "sample_rate": 5000,
        "signal_seconds": sum(sample_counts) / 5000,
        "read_seconds_min": min(sample_counts) / 5000,
        "read_seconds_median": sorted_counts[len(sorted_counts) // 2] / 5000,
        "read_seconds_max": max(sample_counts) / 5000,
        "start_seconds_min": min(starts), "start_seconds_max": max(starts),
        "channels": len(channels), "acquisition_ids": sorted(acquisition_ids),
        "pod5_sample_ids": sorted(sample_ids),
        "membership_sha256": hashlib.sha256(membership.encode()).hexdigest(),
    })
development = (out / "development.txt").read_text().splitlines()
ranked = sorted(development, key=lambda value: hashlib.sha256(
    ("nanopore-pilot-smoke-v1:" + value).encode()).hexdigest())
smoke = ranked[:32]
(out / "smoke.txt").write_text("".join(value + "\n" for value in smoke))
(out / "benchmark.txt").write_text("".join(value + "\n" for value in ranked[:256]))
with (out / "read-inventory.tsv").open("w") as handle:
    writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
    writer.writerow(["role", "sample", "flowcell", "read_id", "acquisition_id", "channel",
                     "well", "read_number", "start_sample", "num_samples", "sample_rate",
                     "calibration_offset", "calibration_scale", "signal_adc_min", "signal_adc_max"])
    writer.writerows(rows)
(root / "provenance/signal-inventory.json").write_text(json.dumps(summaries, indent=2) + "\n")
print(json.dumps(summaries, indent=2))
