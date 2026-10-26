"""Hermetic wire controls consume the real C++ producer. No default skips."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

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
        previous = None if state is None else DRIVER.read(Path(state["path"]).parent / "batch.json")["state_sha256"]
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
            return output, DRIVER.read(output / "batch.json")
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
        raw = DRIVER.pin(output / "batch.json")
        self.assertEqual(raw["size"], (output / "batch.json").stat().st_size)
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


if __name__ == "__main__":
    unittest.main()
