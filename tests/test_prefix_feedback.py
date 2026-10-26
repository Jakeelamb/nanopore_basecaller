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
                                    maximum_locations=32, context_weight=0.5))

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


if __name__ == "__main__":
    unittest.main()
