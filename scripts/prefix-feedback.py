#!/usr/bin/env python3
"""Bind released score rows and genuine prefix mapper receipts to the C++ session.

All entry points are workers. Root's admitted whole-unit adapter must supervise
this process, including synchronous preparation/hashing. This file owns no lock.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/prefix_feedback"))
import bounded_cli as bounded
ENVIRONMENT = dict(LC_ALL="C", PATH="/usr/bin:/bin", HOME="/home/jake",
                   UV_OFFLINE="1", UV_PYTHON_DOWNLOADS="never",
                   UV_PROJECT_ENVIRONMENT="/home/jake/Projects/nanopore_basecaller-retrieval/.venv",
                   PYTHONDONTWRITEBYTECODE="1")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


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


def fields(path):
    require(Path(path).stat().st_size <= 8 * 1024**2, "metadata bound")
    result = {}
    for line in Path(path).read_text().splitlines():
        cells = line.split("\t")
        require(len(cells) == 2 and cells[0] not in result, "metadata field census")
        result[cells[0]] = cells[1]
    return result


def retained_rows(chunks, signal_samples, stride=6):
    """Timestep-only native midpoint ownership. No emitted-base/MOVES input."""
    result = []
    front = 0
    for index, meta in enumerate(chunks):
        count = int(meta["T"])
        end = count
        next_front = 0
        if index + 1 < len(chunks):
            overlap = int(meta["input_offset"]) + int(meta["raw_chunk_size"]) - int(chunks[index + 1]["input_offset"])
            require(overlap >= 0 and overlap % stride == 0, "stride overlap geometry")
            overlap //= stride
            end -= overlap // 2
            next_front = overlap - overlap // 2
        elif len(chunks) == 1 or meta["variable_chunk_sizes"] == "1":
            end = (min(signal_samples, int(meta["raw_chunk_size"])) + stride - 1) // stride
        require(0 <= front <= end <= count, "retained row bounds")
        result.append([front, end])
        front = next_front
    # Native stitch removes the final partial-stride row independent of MOVES.
    total = sum(end - begin for begin, end in result)
    if total > signal_samples // stride:
        require(total == signal_samples // stride + 1, "partial stride overhang")
        result[-1][1] -= 1
    return result


def prepare(config_path, output):
    config = read(config_path)
    require(config["schema"] == "prefix-feedback-config/1" and config["role"] == "development-HG002"
            and config["hg005_selection"] is False and config["truth_input"] is None, "development source contract")
    require(config["index_provenance"] is not None and config["producer_sources"],
            "qualified index/reference build lineage and producer source pins are required before preparation")
    check(config["manifest"])
    groups = {}
    for line in Path(config["manifest"]["path"]).read_text().splitlines():
        cells = line.split("\t")
        if cells[0] == "CHUNK":
            require(len(cells) == 10, "CHUNK manifest width")
            groups.setdefault(cells[2], []).append(dict(index=int(cells[3]),
                tensor=dict(path=cells[4], size=int(cells[5]), sha256=cells[6]),
                metadata=dict(path=cells[7], size=int(cells[8]), sha256=cells[9])))
    output = Path(output)
    output.mkdir()
    exclusions = []
    selected = None
    # Freeze before any reference, mapper or truth is opened. Do not refill after
    # a localization failure. This worker may open scientific metadata only under
    # its exact admitted preparation role.
    for parent in sorted(groups):
        chunks = sorted(groups[parent], key=lambda item: item["index"])
        require([item["index"] for item in chunks] == list(range(len(chunks))), "chunk census differs")
        metadata = []
        for item in chunks:
            check(item["metadata"])
            all_fields = fields(item["metadata"]["path"])
            # Completed calls are intentionally absent from the returned shape.
            allowed = ("T", "C", "read_id", "chunk_index", "chunk_count", "input_offset", "raw_chunk_size", "signal_samples", "variable_chunk_sizes", "token", "time_offset", "score_file")
            clean = {key: all_fields[key] for key in allowed}
            require(clean["read_id"] == parent and int(clean["chunk_index"]) == item["index"]
                    and int(clean["C"]) == 1024, "DGM parent/chunk/shape differs")
            metadata.append(clean)
        ownership = retained_rows(metadata, int(metadata[0]["signal_samples"]))
        begin, end = ownership[0]
        rows = end - begin
        release = config["releases"]
        if not release["minimum_rows"] <= rows <= release["maximum_rows"]:
            exclusions.append(dict(parent=parent, reason="first-retained-chunk-row-bound", rows=rows))
            continue
        cutoffs = [begin + rows * i // 4 for i in range(5)]
        require(all(0 < b - a <= release["maximum_rows_per_release"] for a, b in zip(cutoffs, cutoffs[1:])), "release geometry bound")
        selected = dict(parent=parent, chunks=chunks, geometry=metadata, ownership=ownership, cutoffs=cutoffs)
        break
    require(selected is not None, "no metadata-eligible development parent")
    # Scientific tensor/hash work begins only after the deterministic selection.
    tensor = selected["chunks"][0]["tensor"]
    check(tensor)
    meta = selected["geometry"][0]
    with Path(tensor["path"]).open("rb") as stream:
        header = stream.readline(4096)
        cells = header.decode().rstrip("\n").split("\t")
        require(len(cells) == 15 and cells[0] == "DGS1" and int(cells[1]) == int(meta["T"])
                and cells[2:5] == ["1024", "4", "6"] and cells[13] == meta["token"]
                and int(cells[12]) == int(meta["time_offset"]), "DGS/DGM tensor association differs")
        spec = dict(read_id=selected["parent"], plan_sha256=pin(config_path)["sha256"],
                    state_length=4, stay_score=float(cells[5]), policy=config["policy"], resource_manifest=None)
        blocks = []
        cursor = 0
        for index, (begin, end) in enumerate(zip(selected["cutoffs"], selected["cutoffs"][1:])):
            release_header = cells.copy()
            release_header[1] = str(end - begin)
            stream.seek(len(header) + begin * 1024 * 2)
            payload = stream.read((end - begin) * 1024 * 2)
            require(len(payload) == (end - begin) * 1024 * 2, "short released tensor")
            released = output / ("released-" + str(index) + ".dgs")
            fresh_bytes(released, ("\t".join(release_header) + "\n").encode() + payload)
            chunk_begin = int(meta["input_offset"])
            chunk_end = min(int(meta["signal_samples"]), chunk_begin + int(meta["raw_chunk_size"]))
            binding = dict(tensor=pin(released), read_id=selected["parent"], parent_id=selected["parent"],
                chunk_index=0, block_index=index, row_begin=cursor, row_end=cursor + end - begin,
                chunk_row_begin=begin, chunk_row_end=end, available_score_end=cursor + end - begin,
                available_signal_end=chunk_end, chunk_signal_begin=chunk_begin, chunk_signal_end=chunk_end,
                declared_chunk_lookahead=chunk_end - chunk_begin, orientation="signal-forward")
            receipt_path = output / ("release-" + str(index) + ".json")
            fresh(receipt_path, dict(schema="prefix-release/1", read_id=selected["parent"], tensor=binding["tensor"],
                binding=binding, original_tensor=tensor, metadata=selected["chunks"][0]["metadata"],
                original_row_begin=begin, original_row_end=end, recipe=config["releases"]["recipe"],
                signal_geometry_qualification="static-export-geometry-only-no-acquisition-clock"))
            binding["release_receipt"] = pin(receipt_path)
            blocks.append(binding)
            cursor = binding["row_end"]
    check(tensor)
    # These hashes must also be supervised and are frozen before native mapping.
    check(config["reference"])
    check(config["reference_index"])
    check(config["samtools"])
    check(config["index_provenance"])
    for source in config["producer_sources"]:
        check(source)
    resources = dict(mapper=pin(config["mapper_path"]), samtools=config["samtools"], reference=config["reference"],
        reference_index=config["reference_index"], reference_fai=pin(config["reference_fai_path"]),
        index_provenance=config["index_provenance"], producer_sources=config["producer_sources"])
    fresh(output / "resources.json", dict(schema="prefix-resources/1", plan_sha256=spec["plan_sha256"], resources=resources))
    spec["resource_manifest"] = pin(output / "resources.json")
    fresh(output / "plan.json", dict(schema="prefix-pilot-plan/1", config=pin(config_path), spec=spec,
        blocks=blocks, selected=selected, exclusions=exclusions,
        **resources,
        truth_opened=False, allow_refill=False, available_native_passthrough=None))


def native(executor, binary, mode, request, output):
    request_path = output.parent / (output.name + "-request.json")
    bounded.same_json(request_path, request)
    argv = [binary["path"], mode, "--request", str(request_path), "--request-sha256",
            pin(request_path)["sha256"], "--output", str(output)]
    expected_files = [str(output / name) for name in
                      (("state.json", "batch.json", "complete.json") if mode == "advance" else ("locations.json", "complete.json"))]
    return executor.run(argv, [binary, pin(request_path)], output.parent / (output.name + "-command"),
                        "prefix-decoder", dict(request=pin(request_path)), expected_files)


def locate(executor, binary, plan, batch, directory):
    directory.mkdir(exist_ok=True)
    prefix = batch["provisional_prefix"]
    require(prefix, "no provisional finalist; explicit abstention")
    query = directory / "query.fasta"
    bounded.same_bytes(query, (">prefix\n" + prefix + "\n").encode())
    binding = dict(state_sha256=batch["state_sha256"], query_sha256=digest(prefix.encode()),
                   available_score_end=batch["binding"]["row_end"],
                   available_signal_end=batch["binding"]["available_signal_end"])
    argv = [plan["mapper"]["path"], "-x", "map-ont", "-c", "--secondary=yes", "-N", "7", "-t", "2",
            plan["reference_index"]["path"], str(query)]
    producer, command = executor.run(argv, [pin(query), plan["mapper"], plan["reference_index"]],
                                      directory / "mapper", "prefix-location", binding)
    parse_request = dict(paf=command["stdout"], query=dict(length=len(prefix)))
    parsed_directory = directory / "parsed"
    native(executor, binary, "locations", parse_request, parsed_directory)
    locations = read(parsed_directory / "locations.json")
    require(len(locations) <= plan["spec"]["policy"]["maximum_locations"], "mapper output exceeds predeclared census cap")
    for index, location in enumerate(locations):
        horizon = plan["spec"]["policy"]["maximum_symbols"]
        if location["strand"] == "+":
            begin = location["reference_end"]
            end = min(location["reference_length"], begin + horizon)
        else:
            end = location["reference_begin"]
            begin = max(0, end - horizon)
        evidence = dict(confidence_feature="minimap2-MAPQ-not-posterior", continuation_orientation="signal-forward")
        continuation = ""
        if begin < end and location["query_end"] == location["query_length"]:
            region = location["contig"] + ":" + str(begin + 1) + "-" + str(end)
            ref_binding = dict(location_id=location["id"], contig=location["contig"], reference_begin=begin,
                               reference_end=end, strand=location["strand"])
            ref_receipt, ref_command = executor.run([plan["samtools"]["path"], "faidx", plan["reference"]["path"], region],
                [plan["reference"], plan["reference_fai"], plan["samtools"]], directory / ("reference-" + str(index)),
                "reference-continuation", ref_binding)
            # No numerical work. Read-oriented sequence transport only. C++
            # independently checks the source FASTA, interval and orientation.
            continuation = "".join(Path(ref_command["stdout"]["path"]).read_text().splitlines()[1:]).upper()
            if location["strand"] == "-":
                continuation = continuation.translate(str.maketrans("ACGT", "TGCA"))[::-1]
            require(set(continuation) <= set("ACGT"), "ambiguous reference continuation requires explicit exclusion")
            evidence.update(reference_receipt=ref_receipt, fasta=ref_command["stdout"], reference_begin=begin,
                            reference_end=end, reference=plan["reference"], reference_fai=plan["reference_fai"],
                            index_provenance=plan["index_provenance"], samtools=plan["samtools"])
        location.update(continuation=continuation, evidence=evidence)
    return dict(schema="prefix-location/1", source_sha256=batch["source_sha256"], plan_sha256=batch["plan_sha256"],
        read_id=batch["read_id"], state_sha256=batch["state_sha256"], query_sequence=prefix,
        query_sha256=digest(prefix.encode()), query_length=len(prefix), query=pin(query),
        available_score_end=binding["available_score_end"], available_signal_end=binding["available_signal_end"],
        orientation="signal-forward", producer_receipt=producer, paf=command["stdout"], locations=locations,
        mapper=plan["mapper"], reference_index=plan["reference_index"], resource_manifest=plan["spec"]["resource_manifest"])


def pilot(plan_path, binary, executor, source_sha256, output):
    plan = read(plan_path)
    require(plan["schema"] == "prefix-pilot-plan/1" and plan["truth_opened"] is False and plan["allow_refill"] is False,
            "frozen pilot plan differs")
    check(plan["config"])
    output = Path(output)
    output.mkdir(exist_ok=True)
    state = None
    previous_state_sha256 = None
    update = None
    batches = []
    for index, block in enumerate(plan["blocks"]):
        request = dict(schema="prefix-advance/1", source_sha256=source_sha256, spec=plan["spec"],
                       state=state, update=update, block=block,
                       expected_previous_state_sha256=previous_state_sha256)
        directory = output / ("block-" + str(index))
        native(executor, binary, "advance", request, directory)
        batch = read(directory / "batch.json")
        previous_state_sha256 = batch["state_sha256"]
        state = pin(directory / "state.json")
        batches.append(pin(directory / "batch.json"))
        if batch["abstained"] or not batch["mapper_request_eligible"]:
            fresh(output / "complete.json", dict(schema="prefix-pilot/1", complete=True, plan=pin(plan_path),
                binary=binary, batches=batches, final_state=state, abstained=True,
                mapper_updates=len(batch["location_updates"]),
                usable_update_count=sum(any(location["continuation"] for location in item["locations"]) for item in batch["location_updates"]),
                selected_parent=plan["selected"]["parent"], mechanism_qualified=False,
                accuracy_qualified=False, latency_qualified=False,
                reason="no-eligible-provisional-prefix; mapper and downstream decision are not requested"))
            return
        if index + 1 < len(plan["blocks"]):
            update = locate(executor, binary, plan, batch, output / ("location-" + str(index)))
            bounded.same_json(output / ("location-" + str(index) + ".json"), update)
    final = read(batches[-1]["path"])
    updates = final["location_updates"]
    require(len(updates) >= 3, "fewer than three genuine prefix-derived mapper updates")
    # No accuracy or latency promotion. Keep zero-location outcomes observable.
    fresh(output / "complete.json", dict(schema="prefix-pilot/1", complete=True, plan=pin(plan_path), binary=binary,
        batches=batches, final_state=state, mapper_updates=len(updates),
        usable_update_count=sum(any(location["continuation"] for location in item["locations"]) for item in updates),
        selected_parent=plan["selected"]["parent"],
        mechanism_qualified=False, accuracy_qualified=False, latency_qualified=False,
        reason="requires-independent-real-path-review-and-comparison; no gate inferred from worker completion"))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--config", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("pilot")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--binary", type=Path, required=True)
    run.add_argument("--source-sha256", required=True)
    run.add_argument("--execution-index", type=Path, required=True)
    run.add_argument("--execution-index-sha256", required=True)
    run.add_argument("--result", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    launch = sub.add_parser("launch")
    launch.add_argument("--request", type=Path, required=True)
    launch.add_argument("--request-sha256", required=True)
    launch.add_argument("--output", type=Path, required=True)
    qualify = sub.add_parser("qualify")
    qualify.add_argument("--output", type=Path, required=True)
    identity = sub.add_parser("disabled-identity")
    identity.add_argument("--request", type=Path, required=True)
    identity.add_argument("--request-sha256", required=True)
    identity.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "launch":
        argv = bounded.launch_argv(args.request.resolve(), args.request_sha256, args.output.resolve())
        os.execv(argv[0], argv)
    bounded.admitted_worker()
    if args.command == "prepare":
        prepare(args.config.resolve(), args.output.resolve())
    elif args.command == "qualify":
        import qualification
        qualification.qualify(args.output.resolve())
    elif args.command == "disabled-identity":
        import identity_control
        identity_control.run(args.request.resolve(), args.request_sha256, args.output.resolve())
    else:
        require(pin(args.execution_index.resolve())["sha256"] == args.execution_index_sha256, "execution index root differs")
        plan = read(args.plan.resolve())
        executor = bounded.RetainedCommands(read(args.execution_index.resolve()), plan["producer_sources"])
        try:
            pilot(args.plan.resolve(), pin(args.binary.resolve()), executor, args.source_sha256, args.output.resolve())
            fresh(args.result.resolve(), dict(status="completed-unqualified-pilot", complete=pin(args.output.resolve() / "complete.json")))
        except bounded.PendingCommand as pending:
            fresh(args.result.resolve(), dict(status="awaiting-fresh-Root-grant", proposal=pending.proposal,
                                              native_command_executed=False, producer_replay_permitted=False))


if __name__ == "__main__":
    main()
