"""Synthetic producer/CLI controls. These tests do not assert scientific accuracy."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get("CONTEXT_POLICY_BINARY", ROOT / "results/context-policy/qualification/build/context-policy"))


def raw(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture() -> dict:
    pin = {"path": "/synthetic/input", "size": 8, "sha256": "a" * 64}
    binding = {
        "source_sha256": "a" * 64, "plan_sha256": "b" * 64,
        "input_tensor": pin, "read_id": "synthetic-read", "parent_index": 0,
        "chunk_index": 0, "block_index": 0,
        "availability": {"kind": "released-score-block", "row_begin": 0, "row_end": 8,
                         "available_row_end": 8, "chunk_lookahead": "whole_chunk", "signal_geometry": None},
        "previous_state_sha256": "c" * 64, "prefix_sha256": "d" * 64,
        "prefix_length": 4, "orientation": "forward", "location_producer": pin,
        "reference_free_producer": pin, "identity_input": pin,
    }
    candidates = []
    for name, sequence, likelihood, cost in (
        ("native", "AAAA", -2.0, 4.0), ("free", "AAAC", 0.0, 4.0), ("ref", "AAAT", -0.25, 0.0)
    ):
        edits = [] if name == "native" else [{"operation": "SNV", "query_position": 3,
                                               "reference": "A", "alternate": sequence[-1]}]
        candidates.append({"id": name, "sequence": sequence, "neural_log_likelihood": likelihood,
                           "context_cost": cost, "location_ids": ["L0"], "edits": edits,
                           "eligibility_reasons": []})
    return {
        "schema": "feedback-next/1", "kind": "candidate-batch", "binding": binding,
        "native": {"sequence": "AAAA", "quality": "IIII", "scope": "available_input_segment"},
        "reference_free_candidate_id": "free", "union_nn_candidate_id": "free",
        "locations": [{"id": "L0", "contig": "chr1", "strand": "+", "query_begin": 0,
                       "query_end": 4, "reference_begin": 100, "reference_end": 104,
                       "confidence": {"feature": "declared-location-support", "value": 1.0,
                                      "meaning": "bounded_support_not_probability"}}],
        "candidates": candidates,
    }


class PolicyCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_file():
            raise RuntimeError(f"required admitted C++ build is absent: {BINARY}")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="context-policy-", dir=ROOT / "results/context-policy")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def prepare(self, batch=None, mode="adaptive"):
        batch = fixture() if batch is None else batch
        self.batch_path = self.directory / "batch.json"
        data = raw(batch)
        self.batch_path.write_bytes(data)
        self.request = {
            "schema": "feedback-next/1",
            "batch_pin": {"path": str(self.batch_path), "size": len(data), "sha256": sha(data)},
            "expected_binding": copy.deepcopy(batch["binding"]), "expected_batch_sha256": sha(data),
            "policy": {"mode": mode, "maximum_context_weight": 0.5, "maximum_neural_deficit": 0.5,
                       "minimum_objective_margin": 0.5 if mode == "fixed" else 0.0,
                       "parameter_status": "predeclared_unfitted", "quality_status": "uncalibrated"},
        }
        return self.request

    def invoke(self, expected_hash=None):
        path = self.directory / "request.json"
        data = raw(self.request)
        path.write_bytes(data)
        return subprocess.run([str(BINARY), "decide", str(path), expected_hash or sha(data)],
                              cwd=ROOT, capture_output=True, check=False, timeout=15)

    def assert_rejected(self, result, message):
        self.assertEqual(result.returncode, 2, result.stderr.decode())
        self.assertEqual(result.stdout, b"")
        self.assertIn(message, result.stderr.decode())

    def test_producer_consumer_and_matched_arms(self):
        batch = fixture()
        observed = {}
        pins = []
        for mode in ("disabled", "prior-none", "fixed", "adaptive"):
            self.prepare(batch, mode)
            pins.append(self.request["batch_pin"])
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            decision = json.loads(result.stdout)
            self.assertEqual(decision["batch_sha256"], self.request["expected_batch_sha256"])
            self.assertEqual(decision["binding"], self.request["expected_binding"])
            self.assertEqual(decision["confidence"], "uncalibrated")
            observed[mode] = decision["selected_candidate_id"]
        self.assertTrue(all(pin == pins[0] for pin in pins))
        self.assertEqual(observed, {"disabled": "native", "prior-none": "free", "fixed": "ref", "adaptive": "ref"})

    def test_request_hash_rejection(self):
        self.prepare()
        self.assert_rejected(self.invoke("0" * 64), "request input hash changed")

    def test_source_root_rejection_is_separate(self):
        self.prepare()
        self.invoke()
        path = self.directory / "request.json"
        result = subprocess.run([str(BINARY), "decide", str(path), sha(path.read_bytes())],
                                cwd=self.directory, capture_output=True, check=False, timeout=15)
        self.assert_rejected(result, "source root differs from cwd")

    def test_stale_batch_hash_rejection(self):
        self.prepare()
        self.batch_path.write_bytes(self.batch_path.read_bytes() + b" ")
        self.assert_rejected(self.invoke(), "candidate batch hash")

    def test_foreign_state_even_after_rehash(self):
        batch = fixture()
        self.prepare(batch)
        expected = copy.deepcopy(self.request["expected_binding"])
        batch["binding"]["previous_state_sha256"] = "e" * 64
        self.prepare(batch)
        self.request["expected_binding"] = expected
        self.assert_rejected(self.invoke(), "foreign or stale batch binding")

    def test_missing_and_nonfinite_inputs(self):
        batch = fixture()
        del batch["candidates"][0]["edits"]
        self.prepare(batch)
        self.assert_rejected(self.invoke(), "field census")
        self.prepare()
        data = self.batch_path.read_bytes().replace(b'"neural_log_likelihood": -2.0',
                                                    b'"neural_log_likelihood": null')
        self.batch_path.write_bytes(data)
        self.request["batch_pin"].update(size=len(data), sha256=sha(data))
        self.request["expected_batch_sha256"] = sha(data)
        self.assert_rejected(self.invoke(), "expected real number")

    def test_unavailable_prefix_and_endpoint(self):
        batch = fixture()
        batch["locations"][0]["query_end"] = 5
        self.prepare(batch)
        self.assert_rejected(self.invoke(), "unavailable prefix")
        batch = fixture()
        batch["binding"]["availability"]["row_end"] = 9
        self.prepare(batch)
        self.assert_rejected(self.invoke(), "unavailable score endpoint")

    def test_permuted_candidates_and_locations(self):
        batch = fixture()
        second = copy.deepcopy(batch["locations"][0])
        second["id"] = "L1"
        second["confidence"]["value"] = 0.75
        batch["locations"].append(second)
        for item in batch["candidates"]:
            item["location_ids"].append("L1")
        self.prepare(batch)
        before = json.loads(self.invoke().stdout)
        batch["candidates"].reverse()
        batch["locations"].reverse()
        for item in batch["candidates"]:
            item["location_ids"].reverse()
        self.prepare(batch)
        after = json.loads(self.invoke().stdout)
        self.assertEqual(before["selected_candidate_id"], after["selected_candidate_id"])
        self.assertEqual(before["assessments"], after["assessments"])
        self.assertNotEqual(before["batch_sha256"], after["batch_sha256"])

    def test_edit_reconstruction(self):
        batch = fixture()
        batch["candidates"][1]["edits"][0]["alternate"] = "G"
        self.prepare(batch)
        self.assert_rejected(self.invoke(), "does not reconstruct")

    def test_wrapper_consumes_producer_and_retains_terminal_receipt(self):
        self.prepare()
        self.invoke()
        path = self.directory / "request.json"
        output = self.directory / "observation"
        command = [sys.executable, str(ROOT / "scripts/context-policy.py"), "--binary", str(BINARY),
                   "--binary-sha256", sha(BINARY.read_bytes()), "--request", str(path),
                   "--request-sha256", sha(path.read_bytes()), "--output", str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        receipt = json.loads((output / "command.json").read_text())
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["cwd"], str(ROOT))
        self.assertLessEqual(receipt["start_ns"], receipt["end_ns"])
        self.assertFalse(receipt["kernel_caps_proven_by_this_adapter"])
        completion = json.loads((output / "complete.json").read_text())
        self.assertEqual(completion["selected_candidate_id"], "ref")
        self.assertFalse(completion["native_science_qualified"])
        bad = fixture()
        bad["binding"]["availability"]["row_end"] = 9
        self.prepare(bad)
        self.invoke()
        failed_output = self.directory / "failed-observation"
        command[command.index("--request-sha256") + 1] = sha(path.read_bytes())
        command[command.index("--output") + 1] = str(failed_output)
        failed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False, timeout=25)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(json.loads((failed_output / "command.json").read_text())["exit_code"], 2)
        self.assertFalse((failed_output / "complete.json").exists())


if __name__ == "__main__":
    unittest.main()
