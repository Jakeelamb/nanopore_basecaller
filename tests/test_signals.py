import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from uuid import UUID

import numpy as np
import pod5


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SignalInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in ("scripts", "config", "provenance", "data/raw"):
            (self.root / directory).mkdir(parents=True)
        shutil.copy2(
            PROJECT_ROOT / "scripts/inspect-signals.py",
            self.root / "scripts/inspect-signals.py",
        )
        self.assets = [
            {"id": "fixture-development", "role": "development", "sample": "HG002",
             "flowcell": "PAW70337", "path": "data/raw/development.pod5"},
            {"id": "fixture-validation", "role": "validation", "sample": "HG002",
             "flowcell": "PAW71238", "path": "data/raw/validation.pod5"},
            {"id": "fixture-sealed-test", "role": "sealed_test", "sample": "HG005",
             "flowcell": "PAW87816", "path": "data/raw/sealed_test.pod5"},
        ]
        (self.root / "config/assets.json").write_text(json.dumps(self.assets))
        # More than 32 development reads exercises the smoke cap as well as ordering.
        self.read_ids = {
            "development": [UUID(int=value) for value in range(40, 0, -1)],
            "validation": [UUID(int=102), UUID(int=101)],
            "sealed_test": [UUID(int=202), UUID(int=201)],
        }
        for asset in self.assets:
            self.write_pod5(asset)

    def write_pod5(self, asset, sample_rate=5000, scale=0.25, offset=-12.5):
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        run = pod5.RunInfo(
            acquisition_id=f"acquisition-{asset['role']}",
            acquisition_start_time=timestamp,
            adc_max=4095,
            adc_min=-4096,
            context_tags={},
            experiment_name="integration-fixture",
            flow_cell_id=asset["flowcell"],
            flow_cell_product_code="FLO-PRO114M",
            protocol_name="sequencing/sequencing_PRO114_DNA_e8_2_400K",
            protocol_run_id=f"protocol-{asset['role']}",
            protocol_start_time=timestamp,
            sample_id=asset["sample"],
            sample_rate=sample_rate,
            sequencing_kit="sqk-lsk114",
            sequencer_position="1A",
            sequencer_position_type="promethion",
            software="integration-fixture",
            system_name="fixture",
            system_type="PromethION",
            tracking_id={},
        )
        path = self.root / asset["path"]
        path.unlink(missing_ok=True)
        with pod5.Writer(path) as writer:
            for index, read_id in enumerate(self.read_ids[asset["role"]]):
                writer.add_read(pod5.Read(
                    read_id=read_id,
                    pore=pod5.Pore(channel=1 + index % 2, well=1, pore_type="not_set"),
                    calibration=pod5.Calibration(offset=offset, scale=scale),
                    read_number=index + 1,
                    start_sample=index * 5000 + 1250,
                    median_before=75.0,
                    end_reason=pod5.EndReason(pod5.EndReasonEnum.UNKNOWN, forced=False),
                    run_info=run,
                    signal=np.arange(index + 4, dtype=np.int16) - 10,
                ))

    def inspect_signals(self):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/inspect-signals.py")],
            cwd=self.root, capture_output=True, text=True, timeout=30,
        )

    def test_rejects_nonphysical_calibration(self):
        for scale, offset in [(float("nan"), -12.5), (float("inf"), -12.5),
                              (0.0, -12.5), (0.25, float("nan"))]:
            with self.subTest(scale=scale, offset=offset):
                self.write_pod5(self.assets[0], scale=scale, offset=offset)
                result = self.inspect_signals()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("physical-current calibration", result.stderr)
                self.assert_no_inventory()

    def assert_no_inventory(self):
        self.assertFalse((self.root / "provenance/signal-inventory.json").exists())
        self.assertFalse((self.root / "data/splits/read-inventory.tsv").exists())

    def test_decodes_real_signals_and_freezes_disjoint_membership(self):
        result = self.inspect_signals()

        self.assertEqual(result.returncode, 0, result.stderr)
        summaries = json.loads((self.root / "provenance/signal-inventory.json").read_text())
        self.assertEqual(json.loads(result.stdout), summaries)
        self.assertEqual(len(summaries), 3)
        partitions = []
        for asset, summary in zip(self.assets, summaries):
            role = asset["role"]
            ids = sorted(str(read_id) for read_id in self.read_ids[role])
            membership = "".join(read_id + "\n" for read_id in ids)
            self.assertEqual((self.root / f"data/splits/{role}.txt").read_text(), membership)
            self.assertEqual(summary["membership_sha256"], hashlib.sha256(membership.encode()).hexdigest())
            self.assertEqual(summary["id"], asset["id"])
            self.assertEqual(summary["sample"], asset["sample"])
            self.assertEqual(summary["flowcell"], asset["flowcell"])
            self.assertEqual(summary["role"], role)
            self.assertEqual(summary["reads"], len(ids))
            self.assertEqual(summary["sample_rate"], 5000)
            self.assertEqual(summary["channels"], 2)
            self.assertEqual(summary["acquisition_ids"], [f"acquisition-{role}"])
            self.assertEqual(summary["pod5_sample_ids"], [asset["sample"]])
            partitions.append(set(ids))
        self.assertTrue(partitions[0].isdisjoint(partitions[1]))
        self.assertTrue(partitions[0].isdisjoint(partitions[2]))
        self.assertTrue(partitions[1].isdisjoint(partitions[2]))
        self.assertEqual(summaries[0]["signal_samples"], 940)
        self.assertEqual(summaries[0]["signal_seconds"], 940 / 5000)
        self.assertEqual(summaries[0]["read_seconds_min"], 4 / 5000)
        self.assertEqual(summaries[0]["read_seconds_median"], 24 / 5000)
        self.assertEqual(summaries[0]["read_seconds_max"], 43 / 5000)
        self.assertEqual(summaries[0]["start_seconds_min"], 0.25)
        self.assertEqual(summaries[0]["start_seconds_max"], 39.25)

        smoke = (self.root / "data/splits/smoke.txt").read_text().splitlines()
        expected_smoke = sorted(partitions[0], key=lambda read_id: hashlib.sha256(
            ("nanopore-pilot-smoke-v1:" + read_id).encode()).hexdigest())[:32]
        self.assertEqual(smoke, expected_smoke)
        self.assertEqual(len(set(smoke)), 32)
        benchmark = (self.root / "data/splits/benchmark.txt").read_text().splitlines()
        self.assertEqual(len(benchmark), 40)
        self.assertEqual(set(benchmark), partitions[0])
        self.assertEqual(benchmark[:32], smoke)

        with (self.root / "data/splits/read-inventory.tsv").open() as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(rows), 44)
        self.assertEqual({row["read_id"] for row in rows}, set.union(*partitions))
        row_index = 0
        for asset in self.assets:
            for index, read_id in enumerate(self.read_ids[asset["role"]]):
                self.assertEqual(rows[row_index], {
                    "role": asset["role"], "sample": asset["sample"],
                    "flowcell": asset["flowcell"], "read_id": str(read_id),
                    "acquisition_id": f"acquisition-{asset['role']}",
                    "channel": str(1 + index % 2), "well": "1",
                    "read_number": str(index + 1), "start_sample": str(index * 5000 + 1250),
                    "num_samples": str(index + 4), "sample_rate": "5000",
                    "calibration_offset": "-12.5", "calibration_scale": "0.25",
                    "signal_adc_min": "-10", "signal_adc_max": str(index - 7),
                })
                row_index += 1

        evidence = {
            path: path.read_bytes()
            for path in (self.root / "data/splits").iterdir()
        }
        evidence[self.root / "provenance/signal-inventory.json"] = (
            self.root / "provenance/signal-inventory.json"
        ).read_bytes()
        repeated = self.inspect_signals()
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(repeated.stdout, result.stdout)
        for path, contents in evidence.items():
            self.assertEqual(path.read_bytes(), contents, str(path))

    def test_rejects_sample_rate_other_than_5khz(self):
        self.write_pod5(self.assets[0], sample_rate=4000)

        result = self.inspect_signals()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected sample rate or flowcell", result.stderr)
        self.assertIn(str(self.read_ids["development"][0]), result.stderr)
        self.assert_no_inventory()
        self.assertFalse((self.root / "data/splits/development.txt").exists())

    def test_rejects_duplicate_uuid_across_partitions(self):
        duplicate = self.read_ids["development"][0]
        self.read_ids["validation"][0] = duplicate
        self.write_pod5(self.assets[1])

        result = self.inspect_signals()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"Duplicate read UUID across pilot partitions: {duplicate}", result.stderr)
        self.assert_no_inventory()
        self.assertFalse((self.root / "data/splits/validation.txt").exists())

    def test_rejects_changed_frozen_membership_without_overwriting_evidence(self):
        initial = self.inspect_signals()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        evidence_paths = list((self.root / "data/splits").iterdir())
        evidence_paths.append(self.root / "provenance/signal-inventory.json")
        evidence = {path: path.read_bytes() for path in evidence_paths}
        self.read_ids["development"][0] = UUID(int=9000)
        self.write_pod5(self.assets[0])

        result = self.inspect_signals()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Frozen membership changed", result.stderr)
        self.assertIn(str(self.root / "data/splits/development.txt"), result.stderr)
        for path, contents in evidence.items():
            self.assertEqual(path.read_bytes(), contents, str(path))


if __name__ == "__main__":
    unittest.main()
