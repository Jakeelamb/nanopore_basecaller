"""Exercise the diagnostic inference process and its evidence admission boundary."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('private_allele', ROOT / 'scripts/private-allele-challenge.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BINARY = ROOT / 'results/private-allele/target/release/private-allele-challenge'


class ChallengeContracts(unittest.TestCase):
    def report_fixture(self):
        case = dict(case_id='synthetic', reference_window='ACG', alt_haplotype='C',
                    truth_window_start_in_reference_window=1,
                    truth_window_end_in_reference_window=2, reverse=False,
                    dataset='synthetic', natural_panel_absent=False, stratum='snv',
                    variant='chr1:2 T>C', parent='parent')
        decisions = [dict(case_id='synthetic', arm=arm, emitted='ACG',
                          decision=dict(winner='ACG', edited=False))
                     for arm in ['neutral', 'ordinary_panel', 'withheld_panel',
                                 'ordinary_flank', 'withheld_flank']]
        return [case], decisions

    def run_report(self, cases, decisions, error=None):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source, choices, output = [directory / name for name in
                                       ['cases.jsonl', 'decisions.jsonl', 'report.json']]
            source.write_text(''.join(json.dumps(row) + '\n' for row in cases))
            choices.write_text(''.join(json.dumps(row) + '\n' for row in decisions))
            result = subprocess.run([BINARY, 'report', source, choices, output],
                                    capture_output=True, text=True)
            if error is not None:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)
                self.assertFalse(output.exists())
                return None
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(output.read_text())

    def test_report_accepts_complete_five_arm_case(self):
        cases, decisions = self.report_fixture()
        report = self.run_report(cases, decisions)
        self.assertEqual(len(report['rows']), 5)
        self.assertEqual(sum(group['cores'] for group in report['groups'].values()), 5)
        self.assertTrue(all(row['native_alt_retained'] for row in report['rows']))

    def test_report_rejects_missing_arm(self):
        cases, decisions = self.report_fixture()
        self.run_report(cases, decisions[:-1], 'missing decision case/arm')

    def test_report_rejects_duplicate_arm_even_with_expected_row_count(self):
        cases, decisions = self.report_fixture()
        decisions[-1] = decisions[0]
        self.run_report(cases, decisions, 'duplicate decision case/arm')

    def test_report_rejects_foreign_arm(self):
        cases, decisions = self.report_fixture()
        decisions[-1]['arm'] = 'unregistered'
        self.run_report(cases, decisions, 'foreign decision arm')

    def test_report_rejects_foreign_case(self):
        cases, decisions = self.report_fixture()
        decisions[-1]['case_id'] = 'foreign'
        self.run_report(cases, decisions, 'foreign decision case')

    def test_report_rejects_duplicate_case_labels(self):
        cases, decisions = self.report_fixture()
        self.run_report(cases + cases, decisions, 'duplicate case id')

    def test_report_rejects_empty_case_label(self):
        cases, decisions = self.report_fixture()
        cases[0]['case_id'] = ''
        self.run_report(cases, decisions, 'empty case id')

    def test_withheld_alt_loss_uses_unchanged_scores_and_all_hypotheses(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            case = dict(schema='private-allele-inference/1', case_id='synthetic', stock='A', hypotheses=[
                dict(sequence='A', likelihood=10.0, ordinary=True, withheld=False),
                dict(sequence='C', likelihood=9.75, ordinary=True, withheld=True),
                dict(sequence='G', likelihood=None, ordinary=False, withheld=False)])
            source = directory / 'input.jsonl'
            source.write_text(json.dumps(case) + '\n')
            output = directory / 'decisions.jsonl'
            result = subprocess.run([BINARY, 'infer', source, output], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {row['arm']: row for row in map(json.loads, output.read_text().splitlines())}
            self.assertEqual(rows['neutral']['emitted'], 'A')
            self.assertEqual(rows['ordinary_panel']['emitted'], 'A')
            self.assertEqual(rows['withheld_panel']['emitted'], 'C')
            self.assertEqual(rows['withheld_panel']['decision']['neural_delta'], -0.25)
            self.assertEqual(json.loads(source.read_text()), case)

    def test_truth_field_is_rejected_by_inference_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / 'input.jsonl'
            source.write_text(json.dumps(dict(schema='private-allele-inference/1', case_id='corrupt', stock='A', hypotheses=[], genotype='0/1')) + '\n')
            result = subprocess.run([BINARY, 'infer', source, directory / 'output'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unknown field', result.stderr)

    def test_changed_saved_score_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'score.jsonl'
            source.write_text('{"likelihood":10.0}\n')
            expected = MODULE.pin(source)
            source.write_text('{"likelihood":10.1}\n')
            with self.assertRaisesRegex(ValueError, 'Changed pin'):
                MODULE.check(expected)


if __name__ == '__main__':
    unittest.main()
