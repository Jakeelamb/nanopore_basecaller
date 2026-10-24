"""Genuine retained-producer admission and coherent-corruption controls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalogue_bridge_glue', ROOT / 'scripts/catalogue-bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeReceiptTests(unittest.TestCase):
    def test_pin_observes_actual_bytes(self):
        path = ROOT / 'config/compound-frontier-v1.json'
        self.assertEqual(bridge.pin(path)['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_registered_protocol_has_matched_comparisons_and_no_frontier(self):
        value = json.loads((ROOT / 'config/compound-frontier-v1.json').read_text())
        self.assertFalse(value['frontier']['enabled'])
        arms = {v['id']: v for v in value['policies']}
        control = arms['compound-reference-free']
        for name in ('compound-panel-100', 'compound-linear-100'):
            self.assertEqual(arms[name]['margin'], control['margin'])
            self.assertEqual(arms[name]['neural_deficit'], control['neural_deficit'])
        self.assertEqual(set(v['prior'] for v in arms.values()), {'none', 'panel', 'linear'})


@unittest.skipUnless(os.environ.get('CATALOGUE_BRIDGE_ATTEMPT'), 'Genuine checkpoint/full admission required')
class GenuineAdmissionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attempt = Path(os.environ['CATALOGUE_BRIDGE_ATTEMPT']).resolve()
        cls.binary = ROOT / 'results/compound-frontier/build/release/catalogue-bridge'
        cls.manifest = json.loads((ROOT / 'tools/catalogue_bridge/input.json').read_text())
        cls.transform = cls.attempt / 'transform'
        cls.completion = json.loads((cls.attempt / 'admission/complete.json').read_text())
        cls.receipt_path = Path(cls.completion['producer_receipt']['path'])
        cls.receipt = json.loads(cls.receipt_path.read_text())
        cls.fixtures = ROOT / 'results/compound-frontier/python-controls' / uuid.uuid4().hex
        cls.fixtures.mkdir(parents=True)

    def fixture(self, name):
        directory = self.fixtures / (name + '-' + uuid.uuid4().hex[:8])
        directory.mkdir()
        return directory

    def reject(self, directory, *, manifest=None, transform=None, receipt=None, expected):
        manifest_path = ROOT / 'tools/catalogue_bridge/input.json'
        if manifest is not None:
            manifest_path = directory / 'input.json'
            bridge.fresh(manifest_path, manifest)
        receipt_path = self.receipt_path
        if receipt is not None:
            receipt_path = directory / 'finish.json'
            bridge.fresh(receipt_path, receipt)
        argv = [str(self.binary), 'admit', '--manifest', str(manifest_path),
                '--transform', str(transform or self.transform), '--producer', str(receipt_path),
                '--protocol', str(ROOT / 'config/compound-frontier-v1.json'), '--output', str(directory / 'admission')]
        bridge.fresh(directory / 'argv.json', argv)
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
        (directory / 'stdout').write_bytes(result.stdout)
        (directory / 'stderr').write_bytes(result.stderr)
        (directory / 'exit-status.txt').write_text(str(result.returncode) + '\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertFalse((directory / 'admission/complete.json').exists())
        self.assertIn(expected, result.stderr.decode())

    def test_genuine_complete_parent_outputs_and_expanded_consistency(self):
        value = json.loads((self.attempt / 'admission/bridge-admission.json').read_text())
        count = 331 if self.completion['full_cohort'] else 8
        self.assertEqual(value['rules']['consistency_comparisons'], count * 4)
        self.assertEqual(value['preservation']['original_exclusions'], 120)
        self.assertFalse(value['rules']['original_H_complete_parent_SAM_parity_claimed'])
        self.assertFalse(value['scope']['admissible_candidate'])
        for arm in value['complete_parent_output_checks']:
            self.assertEqual(arm['parents'], 64)
            self.assertTrue(arm['complete_SEQ_Q_equal_independent_splice'])
        native = next(v for v in value['neutral_checks'] if v['policy_id'] == 'native-preservation')
        self.assertEqual(native['different_from_cohort_native'], [])

    def test_corrupted_completion_rejected(self):
        d = self.fixture('completion')
        seal = json.loads((self.transform / 'complete.json').read_text())
        seal['complete'] = False
        bridge.fresh(d / 'complete.json', seal)
        self.reject(d, transform=d, expected='incomplete/wrong seal')

    def test_recorder_stdout_coherently_repinned_rejected(self):
        d = self.fixture('stdout')
        receipt = copy.deepcopy(self.receipt)
        (d / 'false-stdout').write_text('{"completion":null}\n')
        receipt['files']['stdout'] = bridge.pin(d / 'false-stdout')
        self.reject(d, receipt=receipt, expected='recorder stdout completion binding failed')

    def test_unrelated_successful_command_rejected(self):
        d = self.fixture('argv')
        receipt = copy.deepcopy(self.receipt)
        receipt['argv'][-1] = '0'
        self.reject(d, receipt=receipt, expected='recorder command does not produce intended output')

    def test_incomplete_attempt_rejected(self):
        d = self.fixture('incomplete')
        receipt = copy.deepcopy(self.receipt)
        receipt['status'] = 'started'
        self.reject(d, receipt=receipt, expected='unsuccessful bridge recorder')

    def test_original_cohort_mismatch_rejected(self):
        d = self.fixture('cohort')
        manifest = copy.deepcopy(self.manifest)
        cohort = json.loads(Path(manifest['original_cohort']['path']).read_text())
        cohort['role'] = 'validation'
        bridge.fresh(d / 'cohort.json', cohort)
        manifest['original_cohort'] = bridge.pin(d / 'cohort.json')
        self.reject(d, manifest=manifest, expected='unregistered original cohort')

    def test_producer_output_repin_does_not_create_ancestry(self):
        d = self.fixture('producer-output')
        manifest = copy.deepcopy(self.manifest)
        seal = json.loads(Path(manifest['catalogue_completion']['path']).read_text())
        (d / 'false-decisions').write_text('{}\n')
        seal['decisions'] = bridge.pin(d / 'false-decisions')
        bridge.fresh(d / 'catalogue-complete.json', seal)
        manifest['catalogue_completion'] = bridge.pin(d / 'catalogue-complete.json')
        self.reject(d, manifest=manifest, expected='unregistered catalogue completion')

    def test_catalogue_source_identity_rejected(self):
        d = self.fixture('source')
        manifest = copy.deepcopy(self.manifest)
        attempt = json.loads(Path(manifest['catalogue_attempt']['path']).read_text())
        attempt['compiled_source_pins'][0]['sha256'] = '0' * 64
        bridge.fresh(d / 'attempt.json', attempt)
        manifest['catalogue_attempt'] = bridge.pin(d / 'attempt.json')
        self.reject(d, manifest=manifest, expected='wrong catalogue attempt')

    def test_catalogue_binary_identity_rejected(self):
        d = self.fixture('binary')
        manifest = copy.deepcopy(self.manifest)
        seal = json.loads(Path(manifest['catalogue_completion']['path']).read_text())
        summary = json.loads(Path(seal['summary']['path']).read_text())
        summary['final_binary_pin']['sha256'] = '0' * 64
        bridge.fresh(d / 'summary.json', summary)
        seal['summary'] = bridge.pin(d / 'summary.json')
        bridge.fresh(d / 'complete.json', seal)
        manifest['catalogue_completion'] = bridge.pin(d / 'complete.json')
        self.reject(d, manifest=manifest, expected='unregistered catalogue completion')


if __name__ == '__main__':
    unittest.main()
