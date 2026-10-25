import hashlib
import json
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINIMAP2 = PROJECT_ROOT / "software/bin/minimap2"
SAMTOOLS = Path("/usr/bin/samtools")


class ReferencePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("bgzip", "gzip", "bash") if not shutil.which(name)]
        missing.extend(str(path) for path in (SAMTOOLS, MINIMAP2, Path("/usr/bin/time"))
                       if not path.is_file())
        if missing:
            raise unittest.SkipTest("Required native tools unavailable: " + ", ".join(missing))

    def setUp(self):
        # Use the project filesystem so the real 50 GiB admission check still applies.
        self.temporary = tempfile.TemporaryDirectory(prefix=".reference-test-", dir=PROJECT_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in ("scripts", "config", "logs", "results", "provenance",
                          "references", "software/bin"):
            (self.root / directory).mkdir(parents=True)
        for name in ("prepare-reference.py", "record-command.sh"):
            shutil.copy2(PROJECT_ROOT / "scripts" / name, self.root / "scripts" / name)
        shutil.copy2(MINIMAP2, self.root / "software/bin/minimap2")
        generator = random.Random(20261022)
        # Cross multiple BGZF blocks, including a nonzero GZI offset at the second edge.
        self.sequences = {
            "fixture_one": "A" + "".join(generator.choices("ACGT", k=70011)) + "C",
            "fixture_two": "G" + "".join(generator.choices("ACGT", k=82017)) + "T",
        }
        self.fasta = self.root / "references/fixture.fasta"
        self.fasta.write_text("".join(
            f">{name}\n" + "".join(sequence[offset:offset + 61] + "\n"
                                      for offset in range(0, len(sequence), 61))
            for name, sequence in self.sequences.items()
        ))
        self.reference = Path(str(self.fasta) + ".gz")
        with self.reference.open("wb") as compressed:
            result = subprocess.run(["bgzip", "-c", str(self.fasta)], stdout=compressed,
                                    stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.native(SAMTOOLS, "faidx", self.reference)
        self.inputs = [self.reference, Path(str(self.reference) + ".fai"),
                       Path(str(self.reference) + ".gzi")]
        self.assets = [
            {"id": asset_id, "path": str(path.relative_to(self.root)),
             "bytes": path.stat().st_size, "md5": hashlib.md5(path.read_bytes()).hexdigest()}
            for asset_id, path in zip(("grch38", "grch38.fai", "grch38.gzi"), self.inputs)
        ]
        self.write_manifest()
        self.index = self.root / "references/GRCh38-lr-hq.mmi"

    def native(self, *command):
        result = subprocess.run(list(map(str, command)), cwd=self.root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def write_manifest(self):
        (self.root / "config/assets.json").write_text(json.dumps(self.assets))

    def refresh_manifest(self, path):
        asset = next(asset for asset in self.assets if self.root / asset["path"] == path)
        asset.update(bytes=path.stat().st_size, md5=hashlib.md5(path.read_bytes()).hexdigest())
        self.write_manifest()

    def prepare(self, *arguments):
        return subprocess.run([sys.executable, str(self.root / "scripts/prepare-reference.py"),
                               *map(str, arguments)],
                              cwd=self.root, capture_output=True, text=True, timeout=60)

    def receipt(self, name):
        return json.loads((self.root / "provenance" / name).read_text())

    def pin(self, path):
        return {"path": str(path.relative_to(self.root)), "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def assert_no_qualification(self):
        for name in ("reference-qualified.json", "index-built.json", "index-qualified.json"):
            self.assertFalse((self.root / "provenance" / name).exists(), name)
        self.assertFalse(self.index.exists())

    def recorded(self, relative, status=0):
        run = self.root / relative
        self.assertEqual((run / "exit-status.txt").read_text(), f"{status}\n")
        self.assertEqual((run / "cwd.txt").read_text().strip(), str(self.root))
        self.assertTrue((run / "start.txt").read_text().strip())
        self.assertTrue((run / "end.txt").read_text().strip())
        self.assertIn(f"Exit status: {status}", (run / "time.txt").read_text())
        return run, shlex.split((run / "command.sh").read_text())

    def test_qualifies_complete_reference_and_builds_usable_native_index_pending_parity(self):
        originals = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.inputs}

        result = self.prepare()

        self.assertEqual(result.returncode, 0, result.stderr)
        dictionary = {name: len(sequence) for name, sequence in self.sequences.items()}
        reference = self.receipt("reference-qualified.json")
        self.assertEqual(reference["status"], "verified")
        self.assertEqual(reference["dictionary"], dictionary)
        self.assertEqual(reference["contigs"], 2)
        self.assertEqual(reference["reference_bases"], sum(dictionary.values()))
        self.assertEqual(reference["pins"][:3], [self.pin(path) for path in self.inputs])
        self.assertEqual(len(reference["pins"]), 4)
        dictionary_path = self.root / reference["pins"][3]["path"]
        self.assertEqual(reference["pins"][3], self.pin(dictionary_path))
        self.assertEqual(len(reference["native_runs"]), 3)
        recorded = [self.recorded(relative) for relative in reference["native_runs"]]
        self.assertEqual(recorded[0][1], ["gzip", "-t", str(self.reference)])
        self.assertEqual(recorded[1][1], [str(SAMTOOLS), "dict", "-o",
                                        str(dictionary_path), str(self.reference)])
        access_run, access_command = recorded[2]
        regions = [f"{name}:{offset}-{offset}"
                   for name, length in dictionary.items() for offset in (1, length)]
        expected_edges = "".join(f">{name}:1-1\n{sequence[0]}\n"
                                 f">{name}:{len(sequence)}-{len(sequence)}\n{sequence[-1]}\n"
                                 for name, sequence in self.sequences.items())
        self.assertEqual((access_run / "stdout").read_text(), expected_edges)
        self.assertEqual(access_command[:3], [str(SAMTOOLS), "faidx", "--region-file"])
        self.assertEqual(Path(access_command[3]).read_text().splitlines(), regions)
        self.assertEqual(access_command[4], str(self.reference))
        for path, original in originals.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), original, str(path))

        build = self.receipt("index-built.json")
        self.assertEqual(build["status"], "built; native Dorado parity pending")
        self.assertEqual(build["pins"], [self.pin(self.index)])
        self.assertEqual(build["reference_sha256"], self.pin(self.reference)["sha256"])
        self.assertEqual(build["source_commit"], "3c28777e7e2dcc90f825de1b9f17a89cca7d4452")
        self.assertGreater(self.index.stat().st_size, 0)
        producer_run, producer_command = self.recorded(build["producer_run"])
        producer_files = [producer_run / name for name in
                          ("command.sh", "cwd.txt", "start.txt", "end.txt", "time.txt",
                           "exit-status.txt", "stdout", "stderr")]
        producer_files.append(self.root / "software/bin/minimap2")
        self.assertEqual(build["producer_pins"], [self.pin(path) for path in producer_files])
        self.assertEqual(producer_command,
                         [str(self.root / "software/bin/minimap2"), "-x", "lr:hq", "-I", "16G",
                          "-t", "16", "-d", str(dictionary_path.parent / "reference.mmi"),
                          str(self.reference)])
        version = self.native(MINIMAP2, "--version").stdout.strip()
        self.assertEqual(version, "2.31-r1302")
        self.assertIn(f"Version: {version}", (producer_run / "stderr").read_text())
        query = self.root / "query.fasta"
        query.write_text(">query\n" + self.sequences["fixture_one"][1000:2200] + "\n")
        alignment = self.native(MINIMAP2, "-a", "--eqx", self.index, query)
        records = [line.split("\t") for line in alignment.stdout.splitlines()
                   if not line.startswith("@")]
        self.assertEqual(len(records), 1, alignment.stdout)
        self.assertEqual(records[0][0:4], ["query", "0", "fixture_one", "1001"])
        self.assertEqual(records[0][5], "1200=")
        self.assertIn("Dorado FASTA/MMI parity is pending", result.stdout)
        self.assertFalse((self.root / "provenance/index-qualified.json").exists())

        index_before = (self.index.read_bytes(), self.index.stat().st_mtime_ns)
        repeated = self.prepare()
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(self.receipt("index-built.json"), build)
        self.assertEqual((self.index.read_bytes(), self.index.stat().st_mtime_ns), index_before)
        self.assertEqual(len(list((self.root / "logs").glob("*-reference-minimap-index-*"))), 1)
        self.assertFalse((self.root / "provenance/index-qualified.json").exists())

    def test_rejects_publisher_dictionary_mismatch_after_valid_manifest_check(self):
        fields = self.inputs[1].read_text().splitlines()
        first = fields[0].split("\t")
        first[1] = str(int(first[1]) + 1)
        fields[0] = "\t".join(first)
        self.inputs[1].write_text("\n".join(fields) + "\n")
        self.refresh_manifest(self.inputs[1])

        result = self.prepare()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Full native reference dictionary differs from publisher FAI", result.stderr)
        self.assertEqual(len(list((self.root / "logs").iterdir())), 2)
        for run in (self.root / "logs").iterdir():
            self.recorded(str(run.relative_to(self.root)))
        self.assert_no_qualification()

    def test_rejects_source_checksum_corruption_before_native_qualification(self):
        content = bytearray(self.reference.read_bytes())
        content[len(content) // 2] ^= 1
        self.reference.write_bytes(content)

        result = self.prepare()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Acquired reference input differs from its upstream manifest", result.stderr)
        self.assertEqual(list((self.root / "logs").iterdir()), [])
        self.assert_no_qualification()

    def test_rejects_truncated_compressed_reference_with_native_integrity_evidence(self):
        self.reference.write_bytes(self.reference.read_bytes()[:self.reference.stat().st_size // 2])
        self.refresh_manifest(self.reference)

        result = self.prepare()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reference-gzip-integrity exited 1", result.stderr)
        runs = list((self.root / "logs").iterdir())
        self.assertEqual(len(runs), 1)
        run, command = self.recorded(str(runs[0].relative_to(self.root)), status=1)
        self.assertEqual(command, ["gzip", "-t", str(self.reference)])
        self.assertIn("unexpected end of file", (run / "stderr").read_text().lower())
        self.assert_no_qualification()

    def test_rejects_corrupted_existing_index_instead_of_reusing_or_rebuilding(self):
        initial = self.prepare()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        original_receipt = (self.root / "provenance/index-built.json").read_bytes()
        content = bytearray(self.index.read_bytes())
        content[len(content) // 2] ^= 1
        self.index.write_bytes(content)

        result = self.prepare()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Existing native index does not match its build provenance", result.stderr)
        self.assertEqual(self.index.read_bytes(), content)
        self.assertEqual((self.root / "provenance/index-built.json").read_bytes(), original_receipt)
        self.assertEqual(len(list((self.root / "logs").glob("*-reference-minimap-index-*"))), 1)
        self.assertFalse((self.root / "provenance/index-qualified.json").exists())

    def test_rejects_changed_native_build_evidence_without_rebuilding(self):
        initial = self.prepare()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        build = self.receipt("index-built.json")
        receipt_bytes = (self.root / "provenance/index-built.json").read_bytes()
        index_bytes = self.index.read_bytes()

        for item in build["producer_pins"]:
            with self.subTest(producer_evidence=item["path"]):
                path = self.root / item["path"]
                original = path.read_bytes()
                path.write_bytes(original + b"\nchanged retained evidence\n")
                try:
                    result = self.prepare()

                    self.assertNotEqual(result.returncode, 0)
                    expected_error = ("Parity evidence requires a successful native producer"
                                      if path.name == "exit-status.txt" else
                                      "Existing native index producer evidence changed")
                    self.assertIn(expected_error, result.stderr)
                    self.assertEqual(path.read_bytes(), original + b"\nchanged retained evidence\n")
                    self.assertEqual(self.index.read_bytes(), index_bytes)
                    self.assertEqual((self.root / "provenance/index-built.json").read_bytes(),
                                     receipt_bytes)
                    self.assertFalse((self.root / "provenance/index-qualified.json").exists())
                finally:
                    path.write_bytes(original)
        self.assertEqual(len(list((self.root / "logs").glob("*-reference-minimap-index-*"))), 1)

    def test_rejects_removed_native_build_producer_pins(self):
        initial = self.prepare()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        build = self.receipt("index-built.json")
        build_path = self.root / "provenance/index-built.json"
        index_bytes = self.index.read_bytes()
        for pins in ([], build["producer_pins"][:-1], build["producer_pins"][1:]):
            with self.subTest(retained_paths=[item["path"] for item in pins]):
                build_path.write_text(json.dumps({**build, "producer_pins": pins}))

                result = self.prepare()

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("producer", result.stderr.lower())
                self.assertEqual(self.index.read_bytes(), index_bytes)
                self.assertFalse((self.root / "provenance/index-qualified.json").exists())
        self.assertEqual(len(list((self.root / "logs").glob("*-reference-minimap-index-*"))), 1)

    def test_rejects_native_samtools_bam_as_dorado_parity_input(self):
        sam = self.root / "synthetic-unmapped.sam"
        sam.write_text("@HD\tVN:1.6\nsynthetic-query\t4\t*\t0\t0\t*\t*\t0\t0\tACGT\t*\n")
        recorded = self.native(self.root / "scripts/record-command.sh", "samtools-only-input",
                               SAMTOOLS, "view", "-b", sam)
        run = Path(recorded.stdout.strip())
        self.recorded(str(run.relative_to(self.root)))
        bam = run / "stdout"
        self.assertEqual(self.native(SAMTOOLS, "view", "-c", bam).stdout.strip(), "1")

        result = self.prepare("--parity-bam", bam)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Parity input must come from a retained native Dorado basecaller run",
                      result.stderr)
        self.assertTrue((self.root / "provenance/index-built.json").exists())
        self.assertFalse((self.root / "provenance/index-qualified.json").exists())
        self.assertEqual(list((self.root / "logs").glob("*-reference-index-parity-*")), [])
        self.assertFalse((self.root / "software/bin/dorado").exists())

    def test_rejects_other_build_headers_in_retained_parity_input(self):
        config = json.loads((PROJECT_ROOT / "config/stock-benchmark.json").read_text())
        (self.root / "config/stock-benchmark.json").write_text(json.dumps(config))
        model = Path(config["models"]["hac"]).name
        sam = self.root / "other-build.sam"
        bam = self.root / "other-build.bam"
        dorado = self.root / "software/bin/dorado"
        dorado.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\nsys.stdout.buffer.write(Path({str(bam)!r}).read_bytes())\n")
        dorado.chmod(0o755)
        for version in ("2.1.2", "2.1.2+0000000", "2.1.20+8b8fc5d"):
            with self.subTest(version=version):
                sam.write_text(f"@HD\tVN:1.6\n@PG\tID:basecaller\tPN:dorado\tVN:{version}\n"
                               f"@RG\tID:fixture\tDS:basecall_model={model}\n"
                               "synthetic-query\t4\t*\t0\t0\t*\t*\t0\t0\tACGT\t*\tRG:Z:fixture\n")
                self.native(SAMTOOLS, "view", "-b", "-o", bam, sam)
                recorded = self.native(self.root / "scripts/record-command.sh", "other-build-input",
                                       dorado, "basecaller", self.root / config["models"]["hac"],
                                       "unused-signal-fixture")
                producer = Path(recorded.stdout.strip())

                result = self.prepare("--parity-bam", producer / "stdout")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Dorado 2.1.2+8b8fc5d stock model evidence", result.stderr)
                self.assertFalse((self.root / "provenance/index-qualified.json").exists())
                self.assertEqual(list((self.root / "logs").glob("*-reference-index-parity-*")), [])

    def test_rejects_failed_native_producer_as_parity_input(self):
        recorded = subprocess.run(
            [str(self.root / "scripts/record-command.sh"), "failed-samtools-input",
             str(SAMTOOLS), "view", "-b", str(self.root / "missing.sam")],
            cwd=self.root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(recorded.returncode, 1, recorded.stderr)
        run = Path(recorded.stdout.strip())
        self.recorded(str(run.relative_to(self.root)), status=1)
        self.assertIn("Failed to open", (run / "stderr").read_text())

        result = self.prepare("--parity-bam", run / "stdout")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Parity evidence requires a successful native producer", result.stderr)
        self.assertFalse((self.root / "provenance/index-qualified.json").exists())
        self.assertEqual(list((self.root / "logs").glob("*-reference-index-parity-*")), [])
        self.assertFalse((self.root / "software/bin/dorado").exists())


if __name__ == "__main__":
    unittest.main()
