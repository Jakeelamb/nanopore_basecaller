"""Hermetic wire controls consume the real C++ producer. No default skips."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prefix_feedback_driver", ROOT / "scripts/prefix-feedback.py")
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)


class PrefixFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(os.environ["PREFIX_FEEDBACK_BINARY"]).resolve(strict=True)
        result = subprocess.run([str(cls.binary), "witness"], capture_output=True, text=True, check=True, timeout=10)
        cls.witness = json.loads(result.stdout)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.number = 0
        self.spec = dict(read_id="wire-read", plan_sha256="a" * 64, state_length=4, stay_score=0.0,
                        policy=dict(beam_width=32, maximum_symbols=16, minimum_symbols=1,
                                    maximum_locations=32, context_weight=0.5), resource_manifest=None)

    def tearDown(self):
        self.temporary.cleanup()

    def block(self, index=0, start=0, rows=2):
        tensor = self.directory / ("tensor-" + str(self.number) + ".dgs")
        self.number += 1
        header = f"DGS1\t{rows}\t1024\t4\t6\t0\t32\t100\t1\t0\t0\t0\t0\tp1_b1\t0\n".encode()
        DRIVER.fresh_bytes(tensor, header + struct.pack("<e", 0.0) * (rows * 1024))
        binding = dict(tensor=DRIVER.pin(tensor), read_id="wire-read", parent_id="wire-read", chunk_index=0,
                       block_index=index, row_begin=start, row_end=start + rows, chunk_row_begin=start,
                       chunk_row_end=start + rows, available_score_end=start + rows,
                       available_signal_end=12000, chunk_signal_begin=0, chunk_signal_end=12000,
                       declared_chunk_lookahead=12000, orientation="signal-forward")
        receipt = self.directory / ("release-" + str(self.number) + ".json")
        DRIVER.fresh(receipt, dict(schema="prefix-release/1", read_id="wire-read", tensor=binding["tensor"], binding=binding))
        binding["release_receipt"] = DRIVER.pin(receipt)
        return binding

    def request(self, block=None, state=None, update=None):
        previous = None if state is None else DRIVER.read(Path(state["path"]).parent / "snapshot.json")["state_sha256"]
        return dict(schema="prefix-advance/1", source_sha256=self.witness["source_sha256"], spec=self.spec,
                    state=state, update=update, block=block or self.block(), expected_previous_state_sha256=previous)

    def invoke(self, request, accepted=True):
        number = self.number
        self.number += 1
        path = self.directory / ("request-" + str(number) + ".json")
        output = self.directory / ("output-" + str(number))
        DRIVER.fresh(path, request)
        result = subprocess.run([str(self.binary), "advance", "--request", str(path), "--request-sha256",
                                 DRIVER.pin(path)["sha256"], "--output", str(output)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0 if accepted else 2, result.stderr)
        if accepted:
            return output, DRIVER.read(output / "snapshot.json")
        self.assertFalse((output / "complete.json").exists())
        return result.stderr

    def literal(self, name, contents):
        path = self.directory / (str(self.number) + "-" + name)
        self.number += 1
        DRIVER.fresh_bytes(path, contents.encode())
        return DRIVER.pin(path)

    def record(self, role, argv, inputs, stdout, binding, produced=None):
        terminal = self.directory / ("terminal-" + str(self.number) + ".json")
        self.number += 1
        command_identity = dict(role=role, argv=argv, cwd=str(ROOT), environment=dict(LC_ALL="C"),
                                inputs=inputs, binding=binding, source_pins=self.resources["producer_sources"],
                                stdout=stdout, produced_files=produced or [])
        DRIVER.fresh(terminal, dict(group_empty=True, cgroup_empty=True, reaped=True, command=command_identity,
                                    fixture_kind="synthetic-not-native-execution"))
        value = dict(role=role, argv=argv, cwd=str(ROOT), environment=dict(LC_ALL="C"),
                     inputs=inputs, produced_files=produced or [], binding=binding, complete=True,
                     exit_status=0, terminal=True, stdout=stdout, stderr=self.literal("stderr", ""),
                     time=self.literal("time", "synthetic fixture; no timing claim\n"),
                     terminal_proof=DRIVER.pin(terminal), source_pins=self.resources["producer_sources"],
                     fixture_kind="synthetic-not-native-execution")
        path = self.directory / ("receipt-" + str(self.number) + ".json")
        self.number += 1
        DRIVER.fresh(path, value)
        return DRIVER.pin(path)

    def resource_fixture(self):
        self.resources = dict(mapper=self.literal("mapper", "synthetic mapper, never executed\n"),
                              reference_index=self.literal("index", "synthetic mapper index\n"),
                              reference=self.literal("reference.fasta", ">chr1\n" + "A" * 4096 + "\n"),
                              reference_fai=self.literal("reference.fai", "chr1\t4096\t6\t4096\t4097\n"),
                              samtools=self.literal("samtools", "synthetic samtools, never executed\n"),
                              producer_sources=[self.literal("recorder", "synthetic receipt source\n")])
        resources = self.resources
        index_argv = [resources["mapper"]["path"], "-d", resources["reference_index"]["path"], resources["reference"]["path"]]
        fai_argv = [resources["samtools"]["path"], "faidx", resources["reference"]["path"]]
        stdout = self.literal("build.stdout", "")
        index_receipt = self.record("reference-index-build", index_argv,
            [resources["mapper"], resources["reference"]], stdout, {}, [resources["reference_index"]])
        fai_receipt = self.record("reference-fai-build", fai_argv,
            [resources["samtools"], resources["reference"]], stdout, {}, [resources["reference_fai"]])
        lineage = {key: value for key, value in resources.items() if key != "producer_sources"}
        lineage.update(schema="prefix-reference-lineage/1", complete=True)
        for role, receipt, argv in (("index_build", index_receipt, index_argv), ("fai_build", fai_receipt, fai_argv)):
            lineage[role] = dict(receipt=receipt, argv=argv, cwd=str(ROOT), environment=dict(LC_ALL="C"),
                                 producer_sources=resources["producer_sources"])
        path = self.directory / "lineage.json"
        DRIVER.fresh(path, lineage)
        resources["index_provenance"] = DRIVER.pin(path)
        path = self.directory / "resources.json"
        DRIVER.fresh(path, dict(schema="prefix-resources/1", plan_sha256=self.spec["plan_sha256"], resources=resources))
        self.spec["resource_manifest"] = DRIVER.pin(path)

    def update_fixture(self, batch, choices):
        sequence = batch["provisional_prefix"]
        length = len(sequence)
        self.assertGreater(length, 0)
        query = self.literal("query.fasta", ">prefix\n" + sequence + "\n")
        paf = "".join(f"prefix\t{length}\t0\t{length}\t{strand}\tchr1\t4096\t{position}\t{position + length}\t{length}\t{length}\t0\tcg:Z:{length}M\n"
                      for position, _, strand in choices)
        paf_pin = self.literal("mapper.paf", paf)
        request_path = self.directory / ("parse-" + str(self.number) + ".json")
        output = self.directory / ("parse-" + str(self.number))
        self.number += 1
        DRIVER.fresh(request_path, dict(paf=paf_pin, query=dict(length=length)))
        result = subprocess.run([str(self.binary), "locations", "--request", str(request_path),
                                 "--request-sha256", DRIVER.pin(request_path)["sha256"], "--output", str(output)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        locations = DRIVER.read(output / "locations.json")
        for location, (position, continuation, strand) in zip(locations, choices):
            begin = position + length if strand == "+" else position - len(continuation)
            end = begin + len(continuation)
            fasta_sequence = continuation if strand == "+" else continuation.translate(str.maketrans("ACGT", "TGCA"))[::-1]
            fasta = self.literal("continuation.fasta", ">synthetic-reference\n" + fasta_sequence + "\n")
            binding = dict(location_id=location["id"], contig="chr1", reference_begin=begin,
                           reference_end=end, strand=strand)
            argv = [self.resources["samtools"]["path"], "faidx", self.resources["reference"]["path"], f"chr1:{begin + 1}-{end}"]
            receipt = self.record("reference-continuation", argv,
                [self.resources["reference"], self.resources["reference_fai"], self.resources["samtools"]], fasta, binding)
            location.update(continuation=continuation, evidence=dict(confidence_feature="minimap2-MAPQ-not-posterior",
                continuation_orientation="signal-forward", reference_receipt=receipt, fasta=fasta,
                reference_begin=begin, reference_end=end, reference=self.resources["reference"],
                reference_fai=self.resources["reference_fai"], samtools=self.resources["samtools"],
                index_provenance=self.resources["index_provenance"]))
        binding = dict(state_sha256=batch["state_sha256"], query_sha256=DRIVER.digest(sequence.encode()),
                       available_score_end=batch["binding"]["row_end"], available_signal_end=12000)
        argv = [self.resources["mapper"]["path"], "-x", "map-ont", "-c", "--secondary=yes", "-N", "7", "-t", "2",
                self.resources["reference_index"]["path"], query["path"]]
        producer = self.record("prefix-location", argv,
            [query, self.resources["mapper"], self.resources["reference_index"]], paf_pin, binding)
        return dict(schema="prefix-location/1", source_sha256=self.witness["source_sha256"],
            plan_sha256=self.spec["plan_sha256"], read_id=self.spec["read_id"],
            state_sha256=batch["state_sha256"], query_sequence=sequence,
            query_sha256=DRIVER.digest(sequence.encode()), query_length=length, query=query,
            available_score_end=batch["binding"]["row_end"], available_signal_end=12000,
            orientation="signal-forward", producer_receipt=producer, paf=paf_pin, locations=locations,
            mapper=self.resources["mapper"], reference_index=self.resources["reference_index"],
            resource_manifest=self.spec["resource_manifest"])

    def test_real_producer_consumed_state_and_reference_free(self):
        output, first = self.invoke(self.request())
        next_output, second = self.invoke(self.request(self.block(1, 2), DRIVER.pin(output / "state.json")))
        self.assertEqual(second["previous_state_sha256"], first["state_sha256"])
        self.assertEqual(second["binding"]["row_end"], 4)
        self.assertEqual(second["initial_prior"], "uniform-all-CRF-states")
        self.assertEqual(second["location_updates"], [])
        self.assertIsNotNone(second["reference_free_candidate_id"])
        self.assertTrue((next_output / "complete.json").is_file())

    def test_foreign_and_unknown_request_fields(self):
        value = self.request()
        for key, changed in (("source_sha256", "f" * 64), ("right_guard", "ACGT")):
            request = copy.deepcopy(value)
            request[key] = changed
            self.invoke(request, False)

    def test_block_parent_endpoint_orientation_and_receipt_corruption(self):
        original = self.request()
        for key, changed in (("read_id", "foreign"), ("parent_id", "foreign"),
                             ("orientation", "reverse"), ("available_score_end", 99),
                             ("row_begin", 1), ("right_guard", "ACGT")):
            value = copy.deepcopy(original)
            value["block"][key] = changed
            self.invoke(value, False)
        value = copy.deepcopy(original)
        value["block"]["release_receipt"]["sha256"] = "f" * 64
        self.invoke(value, False)

    def test_missing_and_foreign_location_prefix_state_endpoint(self):
        output, batch = self.invoke(self.request())
        state = DRIVER.pin(output / "state.json")
        update = dict(schema="prefix-location/1", source_sha256=self.witness["source_sha256"],
                      plan_sha256=self.spec["plan_sha256"], read_id="wire-read",
                      state_sha256=batch["state_sha256"], query_sequence=batch["provisional_prefix"],
                      query_sha256=DRIVER.digest(batch["provisional_prefix"].encode()),
                      query_length=len(batch["provisional_prefix"]), available_score_end=2,
                      available_signal_end=12000, orientation="signal-forward")
        for key, changed in (("state_sha256", "f" * 64), ("query_sequence", "TTTT"),
                             ("query_sha256", "f" * 64), ("available_score_end", 3),
                             ("available_signal_end", 12001), ("orientation", "reverse")):
            value = copy.deepcopy(update)
            value[key] = changed
            self.invoke(self.request(self.block(1, 2), state, value), False)
        self.invoke(self.request(self.block(1, 2), state, update), False)

    def test_future_tail_byte_and_mapper_request_invariance(self):
        block = self.block()
        future = self.block(1, 2)
        value = self.request(block)
        _, before = self.invoke(value)
        path = Path(future["tensor"]["path"])
        with path.open("ab") as stream:
            stream.write(b"unavailable-future-only")
        _, after = self.invoke(value)
        self.assertEqual(before, after)
        self.assertEqual(before["provisional_prefix"], after["provisional_prefix"])
        self.assertEqual(before["state_sha256"], after["state_sha256"])

    def test_signal_geometry_never_mixes_units(self):
        _, batch = self.invoke(self.request())
        self.assertEqual(batch["binding"]["availability"]["kind"], "released-score-block")
        self.assertIsNone(batch["binding"]["availability"]["signal_geometry"])
        self.assertTrue(batch["binding"]["availability"]["whole_chunk_lookahead"])

    def test_midpoint_ownership_and_final_partial_stride(self):
        chunks = [dict(T=10, input_offset=0, raw_chunk_size=60, variable_chunk_sizes="0"),
                  dict(T=10, input_offset=42, raw_chunk_size=60, variable_chunk_sizes="0")]
        self.assertEqual(DRIVER.retained_rows(chunks, 102), [[0, 9], [2, 10]])
        self.assertEqual(DRIVER.retained_rows([dict(T=10, input_offset=0, raw_chunk_size=60, variable_chunk_sizes="0")], 59), [[0, 9]])
        with self.assertRaises(ValueError):
            DRIVER.retained_rows([chunks[0], dict(chunks[1], input_offset=43)], 102)

    def test_raw_batch_pin_is_external_contract(self):
        output, batch = self.invoke(self.request())
        raw = DRIVER.pin(output / "snapshot.json")
        self.assertEqual(raw["size"], (output / "snapshot.json").stat().st_size)
        self.assertNotEqual(raw["sha256"], batch["batch_sha256"])
        self.assertNotEqual(batch["reference_free_candidate_id"], None)
        self.assertIn(batch["union_nn_candidate_id"], {item["id"] for item in batch["candidates"]})

    def test_accepted_nonempty_revised_and_removed_location_updates(self):
        self.resource_fixture()
        output, batch = self.invoke(self.request())
        for index, choices in enumerate(([(100, "ATTA", "+"), (200, "TAAT", "-")], [(300, "CGTA", "+")], []), 1):
            update = self.update_fixture(batch, choices)
            output, batch = self.invoke(self.request(self.block(index, index * 2), DRIVER.pin(output / "state.json"), update))
            self.assertEqual(len(batch["location_updates"]), index)
            self.assertEqual(len(batch["locations"]), len(choices))
            self.assertIsNotNone(batch["reference_free_candidate_id"])
        self.assertEqual([len(item["locations"]) for item in batch["location_updates"]], [2, 1, 0])

    def test_continuation_pin_mutation_reaches_current_pin_guard(self):
        self.resource_fixture()
        output, batch = self.invoke(self.request())
        update = self.update_fixture(batch, [(100, "ATTA", "+")])
        for key in ("reference", "reference_fai", "samtools"):
            changed = copy.deepcopy(update)
            changed["locations"][0]["evidence"][key]["sha256"] = "f" * 64
            error = self.invoke(self.request(self.block(1, 2), DRIVER.pin(output / "state.json"), changed), False)
            self.assertIn("consumed input pin differs", error)
            self.assertNotIn("source-root", error)

    def test_valid_zero_symbol_and_absent_finalist_contracts(self):
        self.spec["policy"].update(maximum_symbols=0, minimum_symbols=0)
        _, empty = self.invoke(self.request())
        self.assertEqual(empty["candidates"], [])
        self.assertTrue(empty["abstained"])
        self.assertFalse(empty["mapper_request_eligible"])
        for key in ("reference_free_candidate_id", "signal_only_candidate_id", "provisional_candidate_id", "union_nn_candidate_id"):
            self.assertIsNone(empty[key])
        self.spec["policy"].update(maximum_symbols=16, minimum_symbols=3)
        _, absent = self.invoke(self.request())
        self.assertTrue(absent["abstained"])
        self.assertEqual(absent["candidates"], [])
        self.assertFalse(absent["mapper_request_eligible"])

    def identity_request(self):
        parents = []
        manifest = ""
        sam = "@HD\tVN:1.6\tSO:unknown\n"
        for name, sequence, quality, flag, observed, observed_q in (
                ("parent-plus", "ACGA", "!#$%", 0, "ACGA", "!#$%"),
                ("parent-minus", "ACGA", "&'()", 16, "TCGT", ")('&")):
            parent = self.literal(name + ".parent.tsv", f"format\tDGP1\nread_id\t{name}\nSEQ\t{sequence}\nQ\t{quality}\nMOVES\t1111\n")
            parents.append(parent)
            manifest += f"PARENT\t{name}\t{parent['path']}\t{parent['size']}\t{parent['sha256']}\n"
            sam += f"{name}\t{flag}\tchr1\t1\t60\t4M\t*\t0\t0\t{observed}\t{observed_q}\n"
        return dict(schema="prefix-disabled-identity/1", mode="disabled", edits=[], expected_parents=2,
                    manifest=self.literal("manifest.tsv", manifest), aligned_sam=self.literal("native.sam", sam))

    def test_disabled_full_parent_both_strands_and_exact_population(self):
        import identity_control
        request = self.identity_request()
        path = self.directory / "disabled-request.json"
        DRIVER.fresh(path, request)
        output = self.directory / "disabled"
        identity_control.run(path, DRIVER.pin(path)["sha256"], output)
        result = DRIVER.read(output / "complete.json")
        self.assertEqual(result["parent_count"], 2)
        self.assertTrue(result["full_seq_q_identity"] and result["full_sam_byte_identity"])
        self.assertEqual(result["output"]["sha256"], request["aligned_sam"]["sha256"])
        self.assertFalse(result["inference_inputs_exposed"])

    def test_disabled_rejects_edits_and_missing_population(self):
        import identity_control
        request = self.identity_request()
        for index, changed in enumerate((dict(request, edits=[dict(offset=0, ref="A", alt="T")]),
                                         dict(request, expected_parents=3))):
            path = self.directory / ("disabled-bad-" + str(index) + ".json")
            DRIVER.fresh(path, changed)
            with self.assertRaises(ValueError):
                identity_control.run(path, DRIVER.pin(path)["sha256"], self.directory / ("disabled-bad-" + str(index)))

    def test_frozen_public_cli_and_missing_stage_proposal(self):
        bounded = DRIVER.bounded
        request = dict(schema="bounded-command/1", root=str(ROOT), cwd=str(ROOT), source_pins=[bounded.F4])
        path = self.directory / "root-grant.json"
        DRIVER.fresh(path, request)
        argv = bounded.launch_argv(path, DRIVER.pin(path)["sha256"], ROOT / "results/prefix-feedback/future-attempt")
        self.assertEqual(argv[:6], [bounded.UV, "run", "--project", bounded.RETRIEVAL, "--no-sync", "python"])
        self.assertEqual(argv[6:8], [bounded.F4["path"], "run"])
        self.assertIn("--request-sha256", argv)
        with self.assertRaises(ValueError):
            bounded.launch_argv(path, "f" * 64, ROOT / "results/prefix-feedback/future-attempt")
        tool = self.literal("tool", "literal decoder, never executed\n")
        incoming = self.literal("request", "{}\n")
        with patch.object(bounded, "ROOT", self.directory):
            executor = bounded.RetainedCommands(dict(schema="prefix-command-index/1", source_pins=[bounded.F4, tool], commands=[]), [bounded.F4])
            with self.assertRaises(bounded.PendingCommand) as pending:
                executor.run([tool["path"], "literal"], [tool, incoming], self.directory / "attempt",
                             "prefix-decoder", dict(request=incoming), [str(self.directory / "payload.json")])
            proposal = DRIVER.read(pending.exception.proposal["path"])
            self.assertFalse(proposal["authorization"])
            self.assertEqual(proposal["request"]["roles"]["unit"], "F1/decoder")
            self.assertEqual(proposal["request"]["roles"]["inputs"], {"decoder-executable": 0, "decoder-request": 1})
            self.assertFalse((self.directory / "attempt").exists())

    def test_retained_f4_projection_and_foreign_grant_rejection(self):
        bounded = DRIVER.bounded
        tool = self.literal("tool", "literal decoder, never executed\n")
        incoming = self.literal("request", "{}\n")
        attempt = self.directory / "attempt"
        payload = self.literal("payload.json", "{}\n")
        with patch.object(bounded, "ROOT", self.directory):
            expected = bounded.proposal([tool["path"], "literal"], [tool, incoming], attempt, "prefix-decoder",
                                        dict(request=incoming), [bounded.F4, tool], [payload["path"]])
            grant = dict(expected["request"], schema="bounded-command/1", id="literal-not-executed")
            grant_path = self.directory / "grant.json"
            DRIVER.fresh(grant_path, grant)
            attempt.mkdir()
            command = {key: grant[key] for key in ("argv", "cwd", "env", "source_pins", "input_pins", "roles")}
            DRIVER.fresh(attempt / "command.json", command)
            for name in bounded.RAW[1:]:
                DRIVER.fresh_bytes(attempt / name, ("0\n" if name == "exit-status.txt" else "literal fixture\n").encode())
            terminal = dict(exit_known=True, exit=0, error=None, cleanup=dict(terminal=True))
            DRIVER.fresh(attempt / "terminal.json", terminal)
            DRIVER.fresh(attempt / "outer-terminal.json", dict(exit=0, error=None, worker_complete=True,
                missing_worker_records=[], empty_before_unlock=True,
                proof=dict(launcher_group_empty=True, service_cgroup_empty=True, launcher=dict(terminal=True), failures=[])))
            complete = dict(schema="bounded-command-result/1", complete=True, admission=DRIVER.pin(grant_path),
                terminal=DRIVER.pin(attempt / "terminal.json"),
                linked=[DRIVER.pin(path) for path in grant["expected_files"]],
                raw=[DRIVER.pin(attempt / name) for name in bounded.RAW])
            DRIVER.fresh(attempt / "complete.json", complete)
            receipt_pin, receipt = bounded.normalize(DRIVER.pin(attempt / "complete.json"), expected, [bounded.F4], self.directory / "projection")
            self.assertEqual(receipt["inputs"], [tool, incoming])
            self.assertTrue(DRIVER.read(receipt["terminal_proof"]["path"])["cgroup_empty"])
            self.assertEqual(DRIVER.read(receipt_pin["path"])["f4_complete"], DRIVER.pin(attempt / "complete.json"))
            changed = copy.deepcopy(expected)
            changed["request"]["argv"][1] = "foreign"
            with self.assertRaisesRegex(ValueError, "proposed exact command"):
                bounded.normalize(DRIVER.pin(attempt / "complete.json"), changed, [bounded.F4], self.directory / "bad-projection")


class PrefixBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(os.environ["PREFIX_FEEDBACK_BINARY"]).resolve(strict=True)
        result = subprocess.run([str(cls.binary), "witness"], capture_output=True, text=True, check=True, timeout=10)
        cls.witness = json.loads(result.stdout)

    def setUp(self):
        import joint
        self.joint = joint
        self.directory = Path(tempfile.mkdtemp(prefix="bridge-control-"))
        self.binary_pin = DRIVER.pin(self.binary)
        self.sources = [DRIVER.pin(value["path"]) for value in self.witness["source"]["sources"]]
        self.stages = joint.Stages(self.directory / "records", self.sources)

    def tearDown(self):
        # Retain actual stage receipts and their inputs on success and failure.
        pass

    def fixture(self):
        return self.joint.free_fixture(self.stages, self.binary_pin,
            self.witness["source_sha256"], self.directory / "fixture")

    def test_actual_advance_free_emission_and_strict_normalizer(self):
        request, output, emission = self.fixture()
        value = DRIVER.read(output / "batch.json")
        self.assertEqual(set(value), {"schema", "kind", "binding", "native", "reference_free_candidate_id",
            "union_nn_candidate_id", "locations", "candidates"})
        self.assertEqual(value["native"], dict(sequence="AAAA", quality="!!!!", scope="available_input_segment"))
        self.assertEqual(value["binding"], emission["binding"])
        self.assertEqual(value["binding"]["prefix_sha256"], DRIVER.digest(b"AAAA"))
        self.assertEqual(DRIVER.read(Path(request["emission"]["path"]).parent / "identity.json")["kind"], "pipeline-free-input")
        self.assertTrue(all(item["context_cost"] == 0 and item["location_ids"] == [] for item in value["candidates"]))

    def test_actual_nonempty_panel_normalization_both_strands(self):
        harness = PrefixFeedbackTests()
        harness.binary = self.binary
        harness.witness = self.witness
        harness.setUp()
        harness.directory = self.directory / "location-inputs"
        harness.directory.mkdir()
        try:
            harness.resource_fixture()
            first = self.directory / "first"
            self.stages.f1(self.binary_pin, "advance", harness.request(), first,
                ("state.json", "snapshot.json", "complete.json"))
            snapshot = DRIVER.read(first / "snapshot.json")
            update = harness.update_fixture(snapshot, [(100, "AAAA", "+"), (200, "TTTT", "-")])
            second = self.directory / "second"
            producer, _ = self.stages.f1(self.binary_pin, "advance",
                harness.request(harness.block(1, 2), DRIVER.pin(first / "state.json"), update), second,
                ("state.json", "snapshot.json", "complete.json"))
            emitted = self.directory / "emitted"
            producer, _ = self.stages.f1(self.binary_pin, "emit-free-input",
                dict(schema="prefix-emit-free-input/1", source_sha256=self.witness["source_sha256"],
                    state=DRIVER.pin(second / "state.json"), snapshot=DRIVER.pin(second / "snapshot.json"),
                    advance_complete=DRIVER.pin(second / "complete.json"), producer=producer,
                    expected_producer=producer, parent_index=0), emitted,
                ("tensor.dgs", "panels.json", "identity.json", "emission.json", "complete.json"))
            emission = DRIVER.read(emitted / "emission.json")
            output = self.directory / "normalized"
            self.stages.f1(self.binary_pin, "normalize", dict(schema="prefix-normalize/1",
                source_sha256=self.witness["source_sha256"], emission=DRIVER.pin(emitted / "emission.json"),
                producer=producer, expected_producer=producer, expected_binding=emission["binding"]), output,
                ("batch.json", "descriptor.json", "report.json", "complete.json"))
            batch = DRIVER.read(output / "batch.json")
            ids = {item["id"] for item in batch["locations"]}
            self.assertEqual({item["strand"] for item in batch["locations"]}, {"+", "-"})
            self.assertTrue(all(set(item["location_ids"]) == ids and math.isfinite(item["context_cost"])
                and item["context_cost"] >= 0 for item in batch["candidates"]))
            self.assertTrue(all(len(item["panels"]) == 2 for item in DRIVER.read(output / "report.json")["coverage"]))
        finally:
            harness.tearDown()

    def test_resealed_wrong_producer_outputs_reach_producer_guard(self):
        request, _, _ = self.fixture()
        original_request = copy.deepcopy(request)
        original_receipt = DRIVER.read(request["producer"]["path"])
        wrong = DRIVER.read(request["producer"]["path"])
        wrong["outputs"] = wrong["outputs"][1:]
        path = self.directory / "wrong-producer.json"
        DRIVER.fresh(path, wrong)
        request["producer"] = request["expected_producer"] = DRIVER.pin(path)
        _, record = self.stages.f1(self.binary_pin, "normalize", request, self.directory / "bad", (), False)
        self.assertIn("actual producer binary/output census differs", Path(record["stderr"]["path"]).read_text())
        original_command = DRIVER.read(original_receipt["command"]["path"])
        original_terminal = DRIVER.read(original_receipt["terminal"]["path"])
        complete = DRIVER.read(Path(original_request["emission"]["path"]).parent / "complete.json")
        foreign_request = self.directory / "foreign-emit-request.json"
        DRIVER.fresh(foreign_request, DRIVER.read(complete["request"]["path"]))
        foreign_output = self.directory / "foreign-emit-output"
        foreign_output.mkdir()
        for label in ("request", "hash", "output", "argc"):
            command = copy.deepcopy(original_command)
            if label == "request":
                command["argv"][3] = str(foreign_request)
            elif label == "hash":
                command["argv"][5] = "0" * 64
            elif label == "output":
                command["argv"][7] = str(foreign_output)
            else:
                command["argv"] = command["argv"][:2]
            command_path = self.directory / ("resealed-command-" + label + ".json")
            DRIVER.fresh(command_path, command)
            terminal = copy.deepcopy(original_terminal)
            terminal["command"] = DRIVER.pin(command_path)
            terminal_path = self.directory / ("resealed-terminal-" + label + ".json")
            DRIVER.fresh(terminal_path, terminal)
            receipt = copy.deepcopy(original_receipt)
            receipt["command"] = DRIVER.pin(command_path)
            receipt["terminal"] = DRIVER.pin(terminal_path)
            receipt_path = self.directory / ("resealed-receipt-" + label + ".json")
            DRIVER.fresh(receipt_path, receipt)
            bad = copy.deepcopy(original_request)
            bad["producer"] = bad["expected_producer"] = DRIVER.pin(receipt_path)
            _, record = self.stages.f1(self.binary_pin, "normalize", bad,
                self.directory / ("reject-resealed-" + label), (), False)
            self.assertIn("free emission request/cwd/output provenance differs",
                Path(record["stderr"]["path"]).read_text())

    def test_foreign_current_prefix_and_unavailable_endpoint_reject(self):
        request, _, _ = self.fixture()
        for field, value in (("prefix_sha256", "0" * 64), ("availability", dict(request["expected_binding"]["availability"], row_end=5))):
            bad = copy.deepcopy(request)
            bad["expected_binding"][field] = value
            self.stages.f1(self.binary_pin, "normalize", bad, self.directory / ("bad-" + field), (), False)
        bad = copy.deepcopy(request); bad["whole_native_SEQ"] = "AAAAFUTURE"
        self.stages.f1(self.binary_pin, "normalize", bad, self.directory / "future", (), False)

    def test_actual_abstained_free_branch_cannot_emit_identity(self):
        harness = PrefixFeedbackTests(); harness.binary = self.binary; harness.witness = self.witness
        harness.setUp()
        harness.directory = self.directory / "empty-inputs"
        harness.directory.mkdir()
        try:
            harness.spec["policy"]["maximum_symbols"] = 0
            harness.spec["policy"]["minimum_symbols"] = 0
            output = self.directory / "empty"
            producer, _ = self.stages.f1(self.binary_pin, "advance", harness.request(), output,
                ("state.json", "snapshot.json", "complete.json"))
            self.stages.f1(self.binary_pin, "emit-free-input", dict(schema="prefix-emit-free-input/1",
                source_sha256=self.witness["source_sha256"], state=DRIVER.pin(output / "state.json"),
                snapshot=DRIVER.pin(output / "snapshot.json"), advance_complete=DRIVER.pin(output / "complete.json"),
                producer=producer, expected_producer=producer, parent_index=0), self.directory / "identity", (), False)
        finally:
            harness.tearDown()


if __name__ == "__main__":
    unittest.main()
