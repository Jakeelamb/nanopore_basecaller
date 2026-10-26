"""Tiny genuine C++ producer/consumer controls; no missing-binary skips."""
from __future__ import annotations

import hashlib
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


if __name__ == "__main__":
    unittest.main()
