"""Native recorder and immutable-input contracts for accuracy orchestration."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('accuracy_orchestration', ROOT / 'scripts/accuracy.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class AccuracyReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / 'logs').mkdir(exist_ok=True)
        result = subprocess.run([str(ROOT / 'scripts/record-command.sh'), 'accuracy-native-contract',
                                 '/usr/bin/printf', 'native producer\n'], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        cls.run_path = Path(result.stdout.strip())
        cls.argv = ['/usr/bin/printf', 'native producer\n']

    def test_genuine_native_receipt_adopts_exact_command_and_pins(self):
        receipt = a.adopt(self.run_path, self.argv)
        self.assertEqual(receipt['status'], 'finished')
        self.assertEqual(Path(receipt['stdout']).read_text(), 'native producer\n')
        a.b.check_pins(receipt['pins'])
        self.assertEqual(len(receipt['pins']), 8)

    def test_different_native_command_cannot_be_adopted(self):
        with self.assertRaisesRegex(ValueError, 'command mismatch'):
            a.adopt(self.run_path, ['/usr/bin/printf', 'different\n'])

    def test_missing_exit_or_resource_clock_cannot_qualify(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / 'receipt'
            shutil.copytree(self.run_path, copied)
            (copied / 'exit-status.txt').write_text('1\n')
            with self.assertRaisesRegex(ValueError, 'producer failed'):
                a.adopt(copied, self.argv)
            (copied / 'exit-status.txt').write_text('0\n')
            (copied / 'time.txt').write_text('')
            with self.assertRaisesRegex(ValueError, 'resource clock'):
                a.adopt(copied, self.argv)

    def test_changed_retained_bytes_and_immutable_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'evidence'
            path.write_text('original')
            pins = [a.b.pin(path)]
            path.write_text('changed')
            with self.assertRaises(ValueError):
                a.b.check_pins(pins)
            frozen = Path(temp) / 'inputs.json'
            a.frozen(frozen, {'identity': 'original'})
            a.frozen(frozen, {'identity': 'original'})
            with self.assertRaisesRegex(ValueError, 'Changed immutable'):
                a.frozen(frozen, {'identity': 'changed'})

    def test_scoring_selects_observation_bound_decoder_and_rejects_changed_output(self):
        with tempfile.TemporaryDirectory() as temp:
            unit = Path(temp) / 'unit'
            first = unit / 'aligned-decode' / '001' / 'finish.json'
            first.parent.mkdir(parents=True)
            sam = Path(temp) / 'accepted.sam'
            sam.write_text('genuine producer output')
            a.b.write(first, {'stdout': str(sam), 'pins': [a.b.pin(sam)]})
            observation = {'pins': [a.b.pin(first), a.b.pin(sam)]}
            rogue = unit / 'aligned-decode' / '999' / 'finish.json'
            rogue.parent.mkdir(parents=True)
            a.b.write(rogue, {'stdout': '/unrelated/decoder'})
            selected, _ = a.observation_stage(observation, unit, 'aligned-decode')
            self.assertEqual(selected, first)
            sam.write_text('changed sequence')
            with self.assertRaisesRegex(ValueError, 'not bound'):
                a.observation_stage(observation, unit, 'aligned-decode')

    def test_retained_executable_survives_later_build_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer = root / 'build' / 'tool'
            producer.parent.mkdir()
            producer.write_text('#!/bin/sh\nprintf original\n')
            producer.chmod(0o755)
            original = a.b.pin(producer)
            binary, retained = a.retain_sources(root / 'analysis', [original], producer)
            producer.write_text('#!/bin/sh\nprintf replaced\n')
            a.b.check_pins(retained)
            self.assertEqual(subprocess.check_output([binary], text=True), 'original')
            with self.assertRaises(ValueError):
                a.b.check_pins([original])


if __name__ == '__main__':
    unittest.main()
