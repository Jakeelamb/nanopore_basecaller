"""Actual subprocess handoffs inside a fresh externally enforced F4 unit.

No sibling imports, lock, service, neural scoring, or default integration skips.
"""
import copy
import importlib.util
from pathlib import Path
import bounded_cli as io
import qualification


class Stages:
    def __init__(self, output, sources):
        self.root = Path(output)
        self.root.mkdir()
        self.sources = sources
        io.check(io.GUARD)
        spec = importlib.util.spec_from_file_location("prefix_joint_original_guard", io.GUARD["path"])
        self.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.guard)
        self.guard.adopt_orphans()
        self.env = dict(io.ENVIRONMENT, TMPDIR=str(self.root / "tmp"))
        Path(self.env["TMPDIR"]).mkdir()
        self.number = 0
        self.receipts = []

    def run(self, binary, argv, cwd, inputs=(), outputs=(), expected_exit=0):
        io.check(binary)
        directory = self.root / ("stage-" + str(self.number))
        self.number += 1
        terminal = qualification.stage(argv, directory, self.guard, self.env, cwd,
                                       inputs, self.sources, expected_exit)
        value = dict(schema="prefix-stage-receipt/1", complete=expected_exit == 0,
            binary=binary, command=io.pin(directory / "command.json"), terminal=terminal,
            outputs=[io.pin(path) for path in outputs], stdout=io.pin(directory / "stdout"),
            stderr=io.pin(directory / "stderr"), time=io.pin(directory / "time.txt"))
        io.fresh(directory / "receipt.json", value)
        result = io.pin(directory / "receipt.json")
        self.receipts.append(result)
        return result, value

    def f1(self, binary, mode, request, output, names, accepted=True):
        path = self.root / ("request-" + str(self.number) + ".json")
        io.fresh(path, request)
        argv = [binary["path"], mode, "--request", str(path), "--request-sha256",
                io.pin(path)["sha256"], "--output", str(output)]
        return self.run(binary, argv, io.ROOT, [io.pin(path)],
                        [Path(output) / name for name in names] if accepted else [],
                        0 if accepted else 2)


def free_fixture(stages, binary, source, output):
    """Generate pinned toy scores in C++, then consume the real advance/emission."""
    output = Path(output)
    output.mkdir()
    fixture = output / "fixture"
    stages.f1(binary, "bridge-fixture", dict(schema="prefix-bridge-fixture/1", source_sha256=source),
              fixture, ("released.dgs", "release.json", "advance.json", "complete.json"))
    advance = output / "advance"
    producer, _ = stages.f1(binary, "advance", io.read(fixture / "advance.json"), advance,
                             ("state.json", "snapshot.json", "complete.json"))
    request = dict(schema="prefix-emit-free-input/1", source_sha256=source,
        state=io.pin(advance / "state.json"), snapshot=io.pin(advance / "snapshot.json"),
        advance_complete=io.pin(advance / "complete.json"), producer=producer,
        expected_producer=producer, parent_index=0)
    emitted = output / "emitted"
    emission_producer, _ = stages.f1(binary, "emit-free-input", request, emitted,
        ("tensor.dgs", "panels.json", "identity.json", "emission.json", "complete.json"))
    emission = io.read(emitted / "emission.json")
    normalize = dict(schema="prefix-normalize/1", source_sha256=source,
        emission=io.pin(emitted / "emission.json"), producer=emission_producer,
        expected_producer=emission_producer, expected_binding=emission["binding"])
    normalized = output / "normalized"
    stages.f1(binary, "normalize", normalize, normalized,
              ("batch.json", "descriptor.json", "report.json", "complete.json"))
    return normalize, normalized, emission


def run(spec_path, expected_sha256, output):
    io.admitted_worker()
    io.require(io.pin(spec_path)["sha256"] == expected_sha256, "independent joint spec differs")
    spec = io.read(spec_path)
    io.require(set(spec) == {"schema", "f1", "f2", "f3", "f2_cwd", "f3_cwd",
        "source_pins", "f3_source_files", "fixture", "rejections"}
        and spec["schema"] == "prefix-joint-spec/1"
        and spec["fixture"] == "uniform-binary16-t4-k1-beam1-v1" and spec["rejections"] is True,
        "joint external manifest fields differ")
    io.require(spec["f2_cwd"] == "/home/jake/Projects/nanopore_basecaller-next-context-policy"
        and spec["f3_cwd"] == "/home/jake/Projects/nanopore_basecaller-next-indel-decoder",
        "frozen sibling cwd differs")
    for value in spec["source_pins"] + spec["f3_source_files"]:
        io.check(value)
    output = Path(output)
    io.require(output.is_absolute() and output.is_relative_to(io.ROOT / "results/prefix-feedback"), "joint output outside F1")
    stages = Stages(output, spec["source_pins"])
    outcomes = []
    try:
        _, witness = stages.run(spec["f1"], [spec["f1"]["path"], "witness"], io.ROOT)
        source = io.read(witness["stdout"]["path"])["source_sha256"]
        normalize, directory, emission = free_fixture(stages, spec["f1"], source, output / "positive")
        batch_pin = io.pin(directory / "batch.json")
        original = io.read(batch_pin["path"])
        descriptor = io.read(directory / "descriptor.json")
        nomination = dict(schema="indel-prefix-nomination-request/1", mode="consumed-prefix-unscored-v1",
            batch_pin=batch_pin, expected_batch_sha256=batch_pin["sha256"],
            expected_binding=emission["binding"], scoring_descriptor=descriptor,
            expected_scoring_descriptor=descriptor)
        request_path = output / "nominate.json"
        io.fresh(request_path, nomination)
        sidecar_path = output / "sidecar.json"
        sidecar_producer, _ = stages.run(spec["f3"], [spec["f3"]["path"], "nominate-prefix",
            str(request_path), io.pin(request_path)["sha256"], str(sidecar_path)], spec["f3_cwd"],
            [io.pin(request_path), batch_pin], [sidecar_path])
        merged = output / "merged"
        merge = dict(normalize, schema="prefix-merge-indels/1", batch=batch_pin,
            sidecar=io.pin(sidecar_path), sidecar_producer=sidecar_producer,
            expected_sidecar_producer=sidecar_producer, sidecar_binary=spec["f3"],
            sidecar_source_files=spec["f3_source_files"])
        stages.f1(spec["f1"], "merge-indels", merge, merged,
            ("batch.json", "descriptor.json", "report.json", "complete.json"))
        final_pin = io.pin(merged / "batch.json")
        final = io.read(final_pin["path"])
        io.require(final["reference_free_candidate_id"] == original["reference_free_candidate_id"]
            and final["union_nn_candidate_id"] != final["reference_free_candidate_id"]
            and final["union_nn_candidate_id"] not in {item["id"] for item in original["candidates"]},
            "actual merge did not preserve H and add a distinct neural winner")
        outcomes.append("actual-F1-F3-F1-new-indel-H-distinct-U")

        def decide(batch, pin_value, mode, expected_sequence, expected_quality=None):
            policy = dict(mode=mode, maximum_context_weight=0.5, maximum_neural_deficit=0.5,
                minimum_objective_margin=0.5 if mode == "fixed" else 0.0,
                parameter_status="predeclared_unfitted", quality_status="uncalibrated")
            request = dict(schema="feedback-next/1", batch_pin=pin_value,
                expected_binding=batch["binding"], expected_batch_sha256=pin_value["sha256"], policy=policy)
            path = output / ("decision-" + str(stages.number) + ".json")
            io.fresh(path, request)
            _, records = stages.run(spec["f2"], [spec["f2"]["path"], "decide", str(path), io.pin(path)["sha256"]],
                spec["f2_cwd"], [io.pin(path), pin_value])
            decision = io.read(records["stdout"]["path"])
            io.require(decision["sequence"] == expected_sequence and decision["binding"] == batch["binding"]
                and decision["batch_sha256"] == pin_value["sha256"], "actual F2 decision differs")
            if expected_quality is not None:
                io.require(decision["quality"] == expected_quality, "disabled identity Q differs")

        free_sequence = final["native"]["sequence"]
        union_sequence = next(item["sequence"] for item in final["candidates"] if item["id"] == final["union_nn_candidate_id"])
        decide(final, final_pin, "prior-none", union_sequence)
        for mode in ("disabled", "fixed", "adaptive"):
            decide(final, final_pin, mode, free_sequence, final["native"]["quality"] if mode == "disabled" else None)
        outcomes.append("actual-F2-prior-none-U-disabled-identity-no-context-free-escape")
        permuted = copy.deepcopy(final)
        permuted["candidates"].reverse()
        permuted["locations"].reverse()
        path = output / "permuted-batch.json"
        io.fresh(path, permuted)
        decide(permuted, io.pin(path), "prior-none", union_sequence)
        outcomes.append("actual-F2-resealed-candidate-permutation-invariant")

        def reject_f3(value, label):
            path = output / ("reject-" + str(stages.number) + ".json")
            io.fresh(path, value)
            stages.run(spec["f3"], [spec["f3"]["path"], "nominate-prefix", str(path),
                io.pin(path)["sha256"], str(output / ("rejected-sidecar-" + str(stages.number) + ".json"))],
                spec["f3_cwd"], [io.pin(path)], expected_exit=1)
            outcomes.append(label)

        bad = copy.deepcopy(nomination); bad["expected_binding"]["read_id"] = "foreign"
        reject_f3(bad, "foreign-binding-rejected")
        bad = copy.deepcopy(nomination); bad["expected_batch_sha256"] = "0" * 64
        reject_f3(bad, "stale-batch-hash-rejected")
        bad = copy.deepcopy(nomination)
        for field in ("scoring_descriptor", "expected_scoring_descriptor"):
            bad[field]["prior"] = "conditional-native-context"
        reject_f3(bad, "false-prior-rejected")
        bad = copy.deepcopy(nomination); bad["future_whole_SEQ"] = "AAAAFUTURE"
        reject_f3(bad, "future-whole-SEQ-field-rejected")
        bad = copy.deepcopy(nomination)
        for field in ("scoring_descriptor", "expected_scoring_descriptor"):
            bad[field]["row_end"] += 1
        reject_f3(bad, "unavailable-tail-descriptor-rejected")
        bad = copy.deepcopy(normalize); bad["expected_binding"]["previous_state_sha256"] = "0" * 64
        stages.f1(spec["f1"], "normalize", bad, output / "reject-normalize", (), False)
        outcomes.append("F1-independent-state-binding-rejected")
        bad = copy.deepcopy(merge); bad["sidecar"]["sha256"] = "0" * 64
        stages.f1(spec["f1"], "merge-indels", bad, output / "reject-sidecar", (), False)
        outcomes.append("F1-corrupt-sidecar-pin-rejected")

        for label in ("missing-H", "whole-native-scope", "stale-hash"):
            bad = copy.deepcopy(final)
            if label == "missing-H":
                bad["candidates"] = [item for item in bad["candidates"] if item["id"] != bad["reference_free_candidate_id"]]
            if label == "whole-native-scope":
                bad["native"]["scope"] = "completed_whole_read"
            path = output / ("rejected-F2-batch-" + label + ".json")
            io.fresh(path, bad)
            batch_input = io.pin(path)
            policy = dict(mode="fixed", maximum_context_weight=0.5, maximum_neural_deficit=0.5,
                minimum_objective_margin=0.5, parameter_status="predeclared_unfitted", quality_status="uncalibrated")
            request = dict(schema="feedback-next/1", batch_pin=batch_input, expected_binding=final["binding"],
                expected_batch_sha256="0" * 64 if label == "stale-hash" else batch_input["sha256"], policy=policy)
            path = output / ("rejected-F2-request-" + label + ".json")
            io.fresh(path, request)
            stages.run(spec["f2"], [spec["f2"]["path"], "decide", str(path), io.pin(path)["sha256"]],
                spec["f2_cwd"], [io.pin(path), batch_input], expected_exit=2)
            outcomes.append("actual-F2-" + label + "-rejected")

        # These constants are policy counterfactuals, not F1 neural evidence.
        # The actual F1-scored chain above supplies the integration positive.
        for operation, alternate in (("SNV", "CAAA"), ("INS", "AAAAA"), ("DEL", "AAA")):
            value = copy.deepcopy(original)
            free = copy.deepcopy(value["candidates"][0])
            free["neural_log_likelihood"] = 0.0; free["context_cost"] = 1.0; free["location_ids"] = ["private"]
            competitor = copy.deepcopy(free)
            competitor.update(id="private-" + operation, sequence=alternate, neural_log_likelihood=-0.75, context_cost=0.0)
            edit = {"SNV": dict(operation="SNV", query_position=0, reference="A", alternate="C"),
                    "INS": dict(operation="INS", query_position=4, reference="", alternate="A"),
                    "DEL": dict(operation="DEL", query_position=3, reference="A", alternate="")}[operation]
            competitor["edits"] = [edit]
            value["candidates"] = [free, competitor]
            value["locations"] = [dict(id="private", contig="chr1", strand="+", query_begin=0, query_end=4,
                reference_begin=0, reference_end=4, confidence=dict(feature="declared-location-support",
                value=1.0, meaning="bounded_support_not_probability"))]
            path = output / ("private-policy-" + operation + ".json")
            io.fresh(path, value)
            decide(value, io.pin(path), "adaptive", free_sequence)
            outcomes.append("synthetic-policy-private-" + operation + "-fallback-not-neural-evidence")
        io.require(len(outcomes) == 16 and len(stages.receipts) == 25, "actual joint control/stage census differs")
        io.fresh(output / "complete.json", dict(schema="prefix-joint-controls/1", complete=True,
            spec=io.pin(spec_path), stages=stages.receipts, controls=outcomes, skipped=0,
            genuine_inputs=False, scientific_qualified=False, native_stock_Q=False))
    except BaseException as error:
        io.fresh(output / "failed.json", dict(error=repr(error), stages=stages.receipts,
            controls=outcomes, producer_replay_permitted=False))
        raise
