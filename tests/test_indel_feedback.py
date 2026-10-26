"""Tiny genuine C++ producer/consumer controls; no missing-binary skips."""
from __future__ import annotations

import hashlib
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get("INDEL_FEEDBACK_BINARY", ROOT / "results/indel-feedback/qualification/build/indel-feedback"))


def pin(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path: Path, value: dict) -> dict:
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return pin(path)


class IndelFeedbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_absolute() or not BINARY.is_file():
            raise RuntimeError("admitted C++ binary missing; consumed controls cannot be skipped")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="indel-control-")
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.serial = 0

    def run_request(self, command: str, request: dict, success: bool = True, hash_override=None):
        self.serial += 1
        path = self.directory / f"request-{self.serial}.json"
        request_pin = write_json(path, request)
        output = self.directory / f"output-{self.serial}.json"
        result = subprocess.run([str(BINARY), command, str(path), hash_override or request_pin["sha256"], str(output)],
                                cwd=ROOT, text=True, capture_output=True, timeout=60, check=False)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            return json.loads(output.read_text())
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(output.exists())
        return result.stderr

    def classifier_request(self):
        parents = [f"00000000-0000-0000-0000-{i:012d}" for i in range(64)]
        first = parents[0]
        reference = self.directory / "reference.fa"
        reference.write_text(">chr1\nACG\n")
        sam = self.directory / "calls.sam"
        sam.write_text(f"@SQ\tSN:chr1\tLN:3\n{first}\t16\tchr1\t1\t60\t1=1I1D1=\t*\t0\t0\tATG\t123\tNM:i:2\n")
        ledger = self.directory / "parents.txt"
        ledger.write_text("\n".join(parents) + "\n")
        domain = self.directory / "matched.bed"
        domain.write_text(f"chr1\t0\t3\t{first}\n")
        paired = self.directory / "pair-parents.tsv"
        paired.write_text("parent\trefexposure\tright_m\tright_x\tright_i\tright_d\n" +
                          f"{first}\t3\t2\t0\t1\t1\n" +
                          "".join(f"{parent}\t0\t0\t0\t0\t0\n" for parent in parents[1:]))
        return {"schema": "indel-classification-request/1", "side": "right", "expected_parent_count": 64,
                "sam": pin(sam), "reference": pin(reference), "parents": pin(ledger),
                "matched_bed": pin(domain), "pair_parents": pin(paired)}

    def proposal_request(self):
        tensor = self.directory / "fixture_s0.scores"
        header = "DGS1\t9\t1024\t4\t6\t-8\t0\t0\t0\t0\t0\t0\t0\tfixture\t0\n"
        row = struct.pack("<e", 3) + struct.pack("<e", -20) * 1023
        tensor.write_bytes(header.encode() + row * 9)
        metadata = self.directory / "metadata.tsv"
        metadata.write_text("format\tDGM1\nread_id\tread-1\nchunk_index\t0\nscore_file\tfixture_s0.scores\n"
                            "token\tfixture\ntime_offset\t0\nT\t9\nC\t1024\nSEQ\tAAAAAAAA\nMOVES\t111111101\n")
        producer = self.directory / "synthetic-producer.json"
        write_json(producer, {"scope": "synthetic engineering fixture, no independent F1 free-search claim"})
        identity = self.directory / "identity.json"
        write_json(identity, {"read_id": "read-1", "chunk_index": 0, "sequence": "AAA", "quality": "123", "query_begin": 4, "query_end": 7})
        binding = {"source_sha256": "1" * 64, "plan_sha256": "2" * 64, "input_tensor": pin(tensor),
                   "read_id": "read-1", "parent_index": 0, "chunk_index": 0, "block_index": 0,
                   "availability": {"kind": "released-score-block", "row_begin": 4, "row_end": 8,
                                    "available_row_end": 9, "chunk_lookahead": "whole_chunk", "signal_geometry": None},
                   "previous_state_sha256": "3" * 64, "prefix_sha256": "4" * 64, "prefix_length": 7,
                   "orientation": "forward", "location_producer": pin(producer),
                   "reference_free_producer": pin(producer), "identity_input": pin(identity)}
        # Known exact single sequence mass: four paths with one stay and three emissions.
        # The decimal is a fixture constant; Python performs no sequence scoring.
        batch = {"schema": "feedback-next/1", "kind": "candidate-batch", "binding": binding,
                 "native": {"sequence": "AAA", "quality": "123", "scope": "available_input_segment"},
                 "reference_free_candidate_id": "synthetic-free", "union_nn_candidate_id": "synthetic-free", "locations": [],
                 "candidates": [{"id": "synthetic-free", "sequence": "AAA", "neural_log_likelihood": 2.386294361119891,
                                 "context_cost": 0, "location_ids": [], "edits": [], "eligibility_reasons": []}]}
        batch_path = self.directory / "batch.json"
        batch_pin = write_json(batch_path, batch)
        return {"schema": "indel-proposal-request/1", "batch_pin": batch_pin, "expected_batch_sha256": batch_pin["sha256"],
                "expected_binding": binding, "tensor_metadata": pin(metadata), "initial_context": "AAAA",
                "native_query_begin": 4, "native_query_end": 7}

    def test_classification_retains_all_64_and_zero_exposure(self):
        result = self.run_request("classify", self.classifier_request())
        self.assertEqual(result["counts"], {"m": 2, "x": 0, "i": 1, "d": 1})
        self.assertEqual(len(result["parents"]), 64)
        self.assertEqual(result["zero_exposure_parents"], 63)
        self.assertTrue(result["native_pairer_reconciled_every_parent"])
        self.assertTrue(all(event["reverse"] for event in result["events"]))

    def test_pairer_counter_corruption_rejects(self):
        request = self.classifier_request()
        path = Path(request["pair_parents"]["path"])
        path.write_text(path.read_text().replace("\t3\t2\t0\t1\t1", "\t3\t2\t0\t2\t1"))
        request["pair_parents"] = pin(path)
        self.assertIn("counters differ", self.run_request("classify", request, False))

    def test_foreign_parent_rejects_after_rehash(self):
        request = self.classifier_request()
        path = Path(request["sam"]["path"])
        path.write_text(path.read_text().replace("00000000-0000-0000-0000-000000000000", "foreign"))
        request["sam"] = pin(path)
        self.assertIn("foreign", self.run_request("classify", request, False))

    def test_proposal_consumes_real_dgs_rows_and_reconstructs(self):
        request = self.proposal_request()
        result = self.run_request("propose", request)
        candidate = next(item for item in result["new_candidates"] if item["sequence"] == "AAAA")
        self.assertEqual(candidate["neural_log_likelihood"], 12)
        self.assertEqual(result["reference_free_candidate_id"], "synthetic-free")
        self.assertFalse(result["raw_current_dwell_claim"])
        self.assertEqual(result["original_candidates_unchanged"][0]["sequence"], "AAA")

    def test_foreign_chunk_and_tensor_binding_rejects(self):
        for field, value in (("chunk_index", 1), ("read_id", "foreign")):
            request = self.proposal_request()
            batch_path = Path(request["batch_pin"]["path"])
            batch = json.loads(batch_path.read_text())
            batch["binding"][field] = value
            request["batch_pin"] = write_json(batch_path, batch)
            request["expected_batch_sha256"] = request["batch_pin"]["sha256"]
            self.assertIn("binding", self.run_request("propose", request, False))
        request = self.proposal_request()
        Path(request["expected_binding"]["input_tensor"]["path"]).write_bytes(b"foreign")
        self.assertIn("FilePin", self.run_request("propose", request, False))

    def test_unavailable_rows_and_initial_context_reject(self):
        request = self.proposal_request()
        request["initial_context"] = "CCCC"
        self.assertIn("context", self.run_request("propose", request, False))
        request = self.proposal_request()
        batch_path = Path(request["batch_pin"]["path"])
        batch = json.loads(batch_path.read_text())
        batch["binding"]["availability"]["available_row_end"] = 7
        request["expected_binding"] = batch["binding"]
        request["batch_pin"] = write_json(batch_path, batch)
        request["expected_batch_sha256"] = request["batch_pin"]["sha256"]
        self.assertIn("rows", self.run_request("propose", request, False))

    def test_independent_request_and_batch_hash_rejections(self):
        request = self.proposal_request()
        self.assertIn("request hash", self.run_request("propose", request, False, "0" * 64))
        request["expected_batch_sha256"] = "0" * 64
        self.assertIn("batch hash", self.run_request("propose", request, False))


class PrefixNominationTest(unittest.TestCase):
    setUp = IndelFeedbackTest.setUp
    run_request = IndelFeedbackTest.run_request

    @classmethod
    def setUpClass(cls):
        IndelFeedbackTest.setUpClass()

    def prefix_request(self, sequence="ACGTAA", rows=8, state_length=1):
        tensor = self.directory / "unopened.scores"
        tensor.write_text("synthetic unscored tensor role; no DGS scoring claim\n")
        producer = self.directory / "prefix-producer.json"
        write_json(producer, {"scope": "synthetic prefix metadata fixture; genuine F1 integration held"})
        identity_path = self.directory / "prefix-identity.json"
        binding = {"source_sha256": "1" * 64, "plan_sha256": "2" * 64,
                   "input_tensor": pin(tensor), "read_id": "prefix-read", "parent_index": 3,
                   "chunk_index": 0, "block_index": 1,
                   "availability": {"kind": "released-score-block", "row_begin": 0, "row_end": rows,
                                    "available_row_end": rows, "chunk_lookahead": "whole_chunk", "signal_geometry": None},
                   "previous_state_sha256": "3" * 64,
                   "prefix_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                   "prefix_length": len(sequence), "orientation": "forward",
                   "location_producer": pin(producer), "reference_free_producer": pin(producer)}
        identity = {key: copy.deepcopy(value) for key, value in binding.items()
                    if key not in ("location_producer", "reference_free_producer")}
        identity.update(schema="feedback-prefix-identity/1", kind="pipeline-free-input",
                        quality_status="uncalibrated", sequence=sequence, quality="!" * len(sequence))
        binding["identity_input"] = write_json(identity_path, identity)
        candidates = [
            {"id": "free-H", "sequence": sequence, "neural_log_likelihood": 0, "context_cost": 0,
             "location_ids": [], "edits": [], "eligibility_reasons": []},
            {"id": "union-U", "sequence": sequence + "C", "neural_log_likelihood": 1, "context_cost": 0,
             "location_ids": [], "edits": [{"operation": "INS", "query_position": len(sequence),
                                            "reference": "", "alternate": "C"}], "eligibility_reasons": []}]
        batch = {"schema": "feedback-next/1", "kind": "candidate-batch", "binding": binding,
                 "native": {"sequence": sequence, "quality": "!" * len(sequence), "scope": "available_input_segment"},
                 "reference_free_candidate_id": "free-H", "union_nn_candidate_id": "union-U",
                 "locations": [], "candidates": candidates}
        batch_pin = write_json(self.directory / "prefix-batch.json", batch)
        descriptor = {"schema": "consumed-prefix-descriptor/1", "prior": "uniform-all-states",
                      "state_length": state_length, "row_begin": 0, "row_end": rows, "available_row_end": rows,
                      "source_sha256": binding["source_sha256"], "plan_sha256": binding["plan_sha256"],
                      "input_tensor": binding["input_tensor"],
                      "producers": {key: binding[key] for key in
                                    ("location_producer", "reference_free_producer", "identity_input")}}
        return {"schema": "indel-prefix-nomination-request/1", "mode": "consumed-prefix-unscored-v1",
                "batch_pin": batch_pin, "expected_batch_sha256": batch_pin["sha256"],
                "expected_binding": copy.deepcopy(binding), "scoring_descriptor": descriptor,
                "expected_scoring_descriptor": copy.deepcopy(descriptor)}

    def reseal_prefix(self, request, batch=None, identity=None):
        path = Path(request["batch_pin"]["path"])
        batch = json.loads(path.read_text()) if batch is None else batch
        if identity is not None:
            identity_path = Path(batch["binding"]["identity_input"]["path"])
            batch["binding"]["identity_input"] = write_json(identity_path, identity)
        request["batch_pin"] = write_json(path, batch)
        request["expected_batch_sha256"] = request["batch_pin"]["sha256"]
        request["expected_binding"] = copy.deepcopy(batch["binding"])
        descriptor = request["scoring_descriptor"]
        for key in ("source_sha256", "plan_sha256", "input_tensor"):
            descriptor[key] = copy.deepcopy(batch["binding"][key])
        for key in ("row_begin", "row_end", "available_row_end"):
            descriptor[key] = batch["binding"]["availability"][key]
        for key in descriptor["producers"]:
            descriptor["producers"][key] = copy.deepcopy(batch["binding"][key])
        request["expected_scoring_descriptor"] = copy.deepcopy(descriptor)

    def test_prefix_unscored_full_reconstruction_and_preserved_H(self):
        sequence = "ACGT" * 10
        result = self.run_request("nominate-prefix", self.prefix_request(sequence, 64))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["reference_free_candidate"]["id"], "free-H")
        self.assertEqual(result["reference_free_candidate"]["sequence"], sequence)
        self.assertEqual(result["tail"]["query_begin"], 8)
        self.assertGreater(len(result["proposals"]), 0)
        for proposal in result["proposals"]:
            edit = proposal["edit"]
            self.assertEqual(sequence[edit["query_begin"]:edit["query_end"]], edit["reference"])
            self.assertEqual(sequence[:edit["query_begin"]] + edit["alternate"] + sequence[edit["query_end"]:], proposal["sequence"])
            self.assertEqual(proposal["sequence"][:8], sequence[:8])
        def keys(value):
            if isinstance(value, dict):
                return set(value).union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()
        self.assertFalse(keys(result) & {"neural_log_likelihood", "context_cost", "union_nn_candidate_id", "quality", "Q"})

    def test_prefix_original_candidate_permutation_is_invariant(self):
        request = self.prefix_request()
        first = self.run_request("nominate-prefix", request)
        batch = json.loads(Path(request["batch_pin"]["path"]).read_text())
        batch["candidates"].reverse()
        self.reseal_prefix(request, batch)
        second = self.run_request("nominate-prefix", request)
        for key in ("proposals", "counts", "exclusions", "arm_exclusions", "tail"):
            self.assertEqual(first[key], second[key])
        for key in ("id", "sequence"):
            self.assertEqual(first["reference_free_candidate"][key], second["reference_free_candidate"][key])

    def test_prefix_full_and_row_overruns_exclude_whole_arm(self):
        exact = self.run_request("nominate-prefix", self.prefix_request("A" * 512, 2048, 4))
        self.assertEqual(exact["status"], "ready")
        for sequence, rows in (("A" * 513, 2048), ("AC", 2049), ("AC", 0), ("", 1)):
            result = self.run_request("nominate-prefix", self.prefix_request(sequence, rows))
            self.assertEqual(result["status"], "excluded")
            self.assertEqual(result["proposals"], [])
            self.assertTrue(result["arm_exclusions"])
            self.assertEqual(result["counts"]["visited"], 0)

    def test_prefix_old_mode_and_future_metadata_fields_reject(self):
        for key in ("tensor_metadata", "initial_context", "MOVES", "future_SEQ"):
            request = self.prefix_request()
            request[key] = "forbidden"
            self.assertIn("field census", self.run_request("nominate-prefix", request, False))
        request = self.prefix_request()
        identity = json.loads(Path(request["expected_binding"]["identity_input"]["path"]).read_text())
        identity["kind"] = "completed-DGM-native"
        self.reseal_prefix(request, identity=identity)
        self.assertIn("identity schema", self.run_request("nominate-prefix", request, False))

    def test_prefix_prior_and_descriptor_endpoints_reject(self):
        for key, value in (("prior", "conditional-state"), ("state_length", 0), ("state_length", 5),
                           ("state_length", 1.5), ("row_end", 7), ("source_sha256", "a" * 64)):
            request = self.prefix_request()
            request["scoring_descriptor"][key] = value
            request["expected_scoring_descriptor"] = copy.deepcopy(request["scoring_descriptor"])
            self.run_request("nominate-prefix", request, False)

    def test_prefix_foreign_binding_and_independent_hashes_reject(self):
        request = self.prefix_request()
        request["expected_binding"]["previous_state_sha256"] = "a" * 64
        self.assertIn("expected binding", self.run_request("nominate-prefix", request, False))
        request = self.prefix_request()
        request["expected_batch_sha256"] = "0" * 64
        self.assertIn("batch hash", self.run_request("nominate-prefix", request, False))
        request = self.prefix_request()
        self.assertIn("request hash", self.run_request("nominate-prefix", request, False, "0" * 64))

    def test_prefix_identity_sequence_quality_and_endpoint_reject(self):
        for field, value in (("sequence", "ACGTAC"), ("quality", "IIIIII"), ("prefix_length", 7),
                             ("quality_status", "calibrated")):
            request = self.prefix_request()
            identity = json.loads(Path(request["expected_binding"]["identity_input"]["path"]).read_text())
            identity[field] = value
            self.reseal_prefix(request, identity=identity)
            self.assertIn("identity", self.run_request("nominate-prefix", request, False))

    def test_prefix_tail_open_run_and_empty_result_provenance(self):
        result = self.run_request("nominate-prefix", self.prefix_request("A" * 34, 40))
        self.assertTrue(any(item["reason"] == "left-open-run" for item in result["exclusions"]))
        self.assertFalse(any(item["mechanism"] == "run-length-plus-minus-two" for item in result["proposals"]))
        result = self.run_request("nominate-prefix", self.prefix_request("A", 1))
        self.assertTrue(any(item["reason"] == "empty-result" for item in result["exclusions"]))
        self.assertTrue(all(item["sequence"] for item in result["proposals"]))

    def test_prefix_does_not_open_tensor_or_other_producer_bodies(self):
        request = self.prefix_request()
        paths = {Path(request["expected_binding"][key]["path"]) for key in
                 ("input_tensor", "location_producer", "reference_free_producer")}
        try:
            for path in paths:
                path.chmod(0)
            self.assertEqual(self.run_request("nominate-prefix", request)["status"], "ready")
        finally:
            for path in paths:
                path.chmod(0o600)

    def test_prefix_stale_batch_and_identity_bytes_reject(self):
        for key in ("batch_pin", "identity_input"):
            request = self.prefix_request()
            item = request[key] if key == "batch_pin" else request["expected_binding"][key]
            path = Path(item["path"])
            path.write_bytes(path.read_bytes() + b" ")
            self.run_request("nominate-prefix", request, False)


if __name__ == "__main__":
    unittest.main()
