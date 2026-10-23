"""Qualify the complete reference and a native minimap index with retained evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile

STOCK_VERSION = "2.1.2+8b8fc5d"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--parity-bam", action="append", default=[])
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
assets = json.loads((root / "config/assets.json").read_text())
reference = root / next(asset["path"] for asset in assets if asset["id"] == "grch38")
index = root / "references/GRCh38-lr-hq.mmi"
samtools = Path("/usr/bin/samtools")
attempt = Path(tempfile.mkdtemp(prefix="reference-", dir=root / "results"))
runs = []


def pin(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    md5 = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024**2), b""):
            digest.update(block)
            md5.update(block)
    relative = str(path.relative_to(root))
    declared = next((asset for asset in assets if asset["path"] == relative), None)
    if declared and (declared["bytes"] != path.stat().st_size
                     or declared.get("md5", md5.hexdigest()) != md5.hexdigest()
                     or declared.get("sha256", digest.hexdigest()) != digest.hexdigest()):
        raise ValueError(f"Acquired reference input differs from its upstream manifest: {relative}")
    return {"path": relative, "size": path.stat().st_size,
            "sha256": digest.hexdigest()}


def native(label, *command):
    result = subprocess.run([str(root / "scripts/record-command.sh"), label,
                             *map(str, command)], cwd=root, capture_output=True, text=True)
    run = Path(result.stdout.strip())
    if result.returncode:
        raise RuntimeError(f"{label} exited {result.returncode}; retained evidence {run}")
    runs.append(str(run.relative_to(root)))
    return run


def recorder_pins(run):
    run = Path(run)
    required = ("command.sh", "cwd.txt", "start.txt", "end.txt", "time.txt",
                "exit-status.txt", "stdout", "stderr")
    if (run / "exit-status.txt").read_text().strip() != "0":
        raise ValueError("Parity evidence requires a successful native producer")
    if not all((run / name).is_file() for name in required):
        raise ValueError("Incomplete native producer receipt")
    if not all((run / name).read_text().strip() for name in
               ("command.sh", "cwd.txt", "start.txt", "end.txt", "time.txt")):
        raise ValueError("Empty native producer execution evidence")
    return [pin(run / name) for name in required]


def unique_pins(entries):
    result = {}
    for entry in entries:
        prior = result.setdefault(entry["path"], entry)
        if prior != entry:
            raise ValueError("Evidence changed while preparing parity receipt")
    return list(result.values())


reference_inputs = [reference, Path(str(reference) + ".fai"), Path(str(reference) + ".gzi")]
reference_pins = [pin(path) for path in reference_inputs]
expected = {}
for line in reference_inputs[1].read_text().splitlines():
    fields = line.split("\t")
    if fields[0] in expected:
        raise ValueError("Duplicate reference contig in publisher FAI")
    expected[fields[0]] = int(fields[1])
native("reference-gzip-integrity", "gzip", "-t", reference)
dictionary_file = attempt / "reference.dict"
native("reference-dictionary", samtools, "dict", "-o", dictionary_file, reference)
dictionary = {}
for line in dictionary_file.read_text().splitlines():
    if line.startswith("@SQ\t"):
        tags = dict(field.split(":", 1) for field in line.split("\t")[1:])
        if tags["SN"] in dictionary:
            raise ValueError("Duplicate reference contig in native dictionary")
        dictionary[tags["SN"]] = int(tags["LN"])
if dictionary != expected or not dictionary:
    raise ValueError("Full native reference dictionary differs from publisher FAI")
regions = [region for name, length in dictionary.items()
           for region in (f"{name}:1-1", f"{name}:{length}-{length}")]
region_file = attempt / "edge-regions.txt"
region_file.write_text("".join(region + "\n" for region in regions))
access = native("reference-random-access", samtools, "faidx", "--region-file", region_file, reference)
observed = {}
name = None
for line in (access / "stdout").read_text().splitlines():
    if line.startswith(">"):
        name = line[1:]
        observed[name] = ""
    elif name is not None:
        observed[name] += line
if list(observed) != regions or any(len(sequence) != 1 for sequence in observed.values()):
    raise ValueError("Publisher FAI/GZI failed native access at contig boundaries")
if [pin(path) for path in reference_inputs] != reference_pins:
    raise ValueError("Native qualification changed publisher reference inputs")
reference_receipt = {"status": "verified", "pins": reference_pins + [pin(dictionary_file)],
                     "dictionary": dictionary, "contigs": len(dictionary),
                     "reference_bases": sum(dictionary.values()), "native_runs": runs.copy(),
                     "qualification": "Full native decode, complete dictionary, indexed contig boundaries"}
(root / "provenance/reference-qualified.json").write_text(json.dumps(reference_receipt, indent=2) + "\n")
print(f"Verified full reference: {len(dictionary)} contigs, {sum(dictionary.values())} bases", flush=True)
if not index.exists():
    if shutil.disk_usage(root).free < 50 * 1024**3:
        raise ValueError("Reference indexing needs a 20 GiB allowance above the 30 GiB reserve")
    output = attempt / "reference.mmi"
    build = native("reference-minimap-index", root / "software/bin/minimap2", "-x", "lr:hq",
                   "-I", "16G", "-t", "16", "-d", output, reference)
    if output.stat().st_size == 0:
        raise ValueError("Native index producer emitted an empty file")
    output.rename(index)
    build_receipt = {"status": "built; native Dorado parity pending", "pins": [pin(index)],
                     "producer_pins": recorder_pins(build) + [pin(root / "software/bin/minimap2")],
                     "reference_sha256": reference_pins[0]["sha256"],
                     "source_commit": "3c28777e7e2dcc90f825de1b9f17a89cca7d4452",
                     "ont_patches": "not applied; upstream nested source built separately",
                     "producer_run": str(build.relative_to(root))}
    (root / "provenance/index-built.json").write_text(json.dumps(build_receipt, indent=2) + "\n")
else:
    build_receipt = json.loads((root / "provenance/index-built.json").read_text())
    if build_receipt["pins"] != [pin(index)] or build_receipt["reference_sha256"] != reference_pins[0]["sha256"]:
        raise ValueError("Existing native index does not match its build provenance")
    expected_producer = recorder_pins(root / build_receipt["producer_run"]) + [
        pin(root / "software/bin/minimap2")]
    if build_receipt.get("producer_pins") != expected_producer:
        raise ValueError("Existing native index producer evidence changed")
parity = []
for bam_name in args.parity_bam:
    bam = Path(bam_name).resolve()
    producer = bam.parent
    producer_pins = recorder_pins(producer)
    command = shlex.split((producer / "command.sh").read_text())
    if (bam.name != "stdout" or len(command) < 4 or command[1] != "basecaller"
            or (root / command[0]).resolve() != (root / "software/bin/dorado").resolve()):
        raise ValueError("Parity input must come from a retained native Dorado basecaller run")
    parity_start = len(runs)
    input_decode = native("reference-parity-input", samtools, "view", "-h", bam)
    input_models = set()
    native_version = False
    input_records = 0
    for line in (input_decode / "stdout").read_text().splitlines():
        if line.startswith(("@PG\t", "@RG\t")):
            tags = dict(field.split(":", 1) for field in line.split("\t")[1:])
            if line.startswith("@PG\t"):
                native_version |= tags.get("PN") == "dorado" and tags.get("VN") == STOCK_VERSION
            else:
                input_models.update(field.split("=", 1)[1] for field in tags.get("DS", "").split()
                                    if field.startswith("basecall_model="))
        elif not line.startswith("@"):
            input_records += 1
    models = {tier: Path(value).name for tier, value in
              json.loads((root / "config/stock-benchmark.json").read_text())["models"].items()}
    tiers = [tier for tier, model in models.items() if input_models == {model}]
    if not native_version or not input_records or len(tiers) != 1:
        raise ValueError("Parity input lacks nonempty native Dorado 2.1.2+8b8fc5d stock model evidence")
    tier = tiers[0]
    if Path(command[2]).name != models[tier]:
        raise ValueError("Parity input model differs from retained native command")
    decoded = []
    outputs = []
    mapped_counts = []
    for target in (reference, index):
        aligned = native("reference-index-parity", root / "software/bin/dorado", "aligner",
                         target, bam, "--threads", "16", "--no-sort", "--mm2-opts",
                         "-x lr:hq -I 16G --eqx -Y")
        if "indexing parameters" in (aligned / "stderr").read_text().lower():
            raise ValueError("Native aligner reported an index-parameter mismatch")
        view = native("reference-parity-decode", samtools, "view", "-h", aligned / "stdout")
        current_dictionary = {}
        records = []
        mapped = 0
        for line in (view / "stdout").read_text().splitlines():
            fields = line.split("\t")
            if line.startswith("@SQ\t"):
                tags = dict(field.split(":", 1) for field in fields[1:])
                current_dictionary[tags["SN"]] = int(tags["LN"])
            elif not line.startswith("@"):
                mapped += int((int(fields[1]) & 4) == 0)
                records.append(tuple(fields[:11] + sorted(fields[11:])))
        if current_dictionary != dictionary or not records or not mapped:
            raise ValueError("Native parity handoff is empty, unmapped, or has wrong reference contigs")
        decoded.append(sorted(records))
        mapped_counts.append(mapped)
        outputs.extend([pin(aligned / "stdout"), pin(view / "stdout")])
    if decoded[0] != decoded[1]:
        raise ValueError("Native FASTA and MMI alignments differ")
    producer_runs = [str(producer.relative_to(root))] + runs[parity_start:]
    evidence = unique_pins([pin(bam), pin(input_decode / "stdout")] + outputs + producer_pins
                           + [item for relative in runs[parity_start:]
                              for item in recorder_pins(root / relative)])
    parity.append({"tier": tier, "model": models[tier], "input": pin(bam),
                   "input_decode": pin(input_decode / "stdout"), "outputs": outputs,
                   "status": "verified", "mapped_records": mapped_counts[0],
                   "producer_runs": producer_runs,
                   "input_producer_run": str(producer.relative_to(root)), "pins": evidence})
if parity:
    if len(parity) != 2 or {entry["tier"] for entry in parity} != {"hac", "sup"}:
        raise ValueError("Native index qualification requires both stock model tiers")
    all_pins = unique_pins([pin(index), pin(root / "software/bin/dorado"),
                           pin(root / "provenance/index-built.json"),
                           pin(root / "provenance/reference-qualified.json")]
                          + reference_receipt["pins"] + build_receipt["producer_pins"]
                          + [item for entry in parity for item in entry["pins"]])
    index_receipt = {"status": "verified", "pins": all_pins, "dictionary": dictionary,
                     "reference_sha256": reference_pins[0]["sha256"], "parity": parity,
                     "build": build_receipt, "native_runs": runs}
    (root / "provenance/index-qualified.json").write_text(json.dumps(index_receipt, indent=2) + "\n")
    print(f"Verified native FASTA/MMI parity for {len(parity)} genuine basecall BAMs")
else:
    print("Native index built. Dorado FASTA/MMI parity is pending.")
