import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('measurement_controls', ROOT/'tools/context_decoder/model_measure.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
c = m.load('measurement_control_boundary', ROOT/'tools/context_decoder/context_inputs.py')


class Measurement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def sam(self, name, records):
        path = self.root/name
        path.write_text(''.join(records))
        return path

    def record(self, parent='p', flag=0, sequence='ACGT', quality='IIII', cigar='4='):
        return f'{parent}\t{flag}\tchr1\t11\t60\t{cigar}\t*\t0\t0\t{sequence}\t{quality}\n'

    def summary(self):
        counts = dict(m=90, x=5, i=3, d=2)
        candidate = dict(m=92, x=3, i=3, d=2)
        return dict(complete=True, parents=64, selected_parents=64, selection='all', zero_exposure_parents=11,
                    conservation=dict(blocks_equal_parents=True, same_reference_exposure_both_arms=True),
                    metrics=dict(left_counts=counts, candidate_counts=candidate, left_error_fraction=.1,
                                 candidate_error_fraction=.08, relative_error_reduction=.2, positive_denominator_parents=53),
                    parent_bootstrap=dict(status='available', candidate_minus_left_error_fraction_95_percentile=[-.03, -.01]),
                    genomic_1mb_block_bootstrap=dict(status='available', candidate_minus_left_error_fraction_95_percentile=[-.03, -.01]))

    def test_primary_and_supplementary_complete_sequence(self):
        original = self.sam('original', [self.record()])
        mapped = self.sam('mapped', [self.record(), self.record(flag=2048)])
        m.custody(original, mapped, ['p'], c)

    def test_foreign_record_rejected(self):
        path = self.sam('foreign', [self.record(), self.record(parent='other')])
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            m.sam_census(path, ['p'], c)

    def test_missing_parent_rejected(self):
        path = self.sam('missing', [self.record()])
        with self.assertRaisesRegex(ValueError, 'census'):
            m.sam_census(path, ['p', 'q'], c)

    def test_duplicate_primary_rejected(self):
        path = self.sam('duplicate', [self.record(), self.record()])
        with self.assertRaisesRegex(ValueError, 'census'):
            m.sam_census(path, ['p'], c)

    def test_changed_quality_rejected(self):
        original = self.sam('original', [self.record()])
        mapped = self.sam('mapped', [self.record(quality='I!II')])
        with self.assertRaisesRegex(ValueError, 'SEQ/Q'):
            m.custody(original, mapped, ['p'], c)

    def test_changed_sequence_rejected(self):
        original = self.sam('original', [self.record()])
        mapped = self.sam('mapped', [self.record(sequence='ACTT')])
        with self.assertRaisesRegex(ValueError, 'SEQ/Q'):
            m.custody(original, mapped, ['p'], c)

    def test_reverse_orientation_custody(self):
        original = self.sam('original', [self.record(sequence='AAGC', quality='ABCD')])
        mapped = self.sam('mapped', [self.record(flag=16, sequence='GCTT', quality='DCBA')])
        m.custody(original, mapped, ['p'], c)

    def test_error_denominator_includes_insertions(self):
        checked = m.summary_check(self.summary())
        self.assertEqual(checked['denominators'], dict(left=100, candidate=100))
        self.assertTrue(checked['one_percent'])

    def test_wrong_rate_rejected(self):
        summary = self.summary()
        summary['metrics']['candidate_error_fraction'] = .07
        with self.assertRaisesRegex(ValueError, 'denominator'):
            m.summary_check(summary)

    def test_wrong_reduction_rejected(self):
        summary = self.summary()
        summary['metrics']['relative_error_reduction'] = .3
        with self.assertRaisesRegex(ValueError, 'Relative'):
            m.summary_check(summary)

    def test_incomplete_parent_accounting_rejected(self):
        summary = self.summary()
        summary['zero_exposure_parents'] = 10
        with self.assertRaisesRegex(ValueError, 'accounting'):
            m.summary_check(summary)

    def test_positive_uncertainty_is_failed_gate(self):
        summary = self.summary()
        summary['parent_bootstrap']['candidate_minus_left_error_fraction_95_percentile'][1] = .01
        self.assertFalse(m.summary_check(summary)['technical_upper_negative']['parent_bootstrap'])

    def test_subthreshold_gain_is_failed_gate(self):
        summary = self.summary()
        summary['metrics']['candidate_counts'] = dict(m=9001, x=500, i=300, d=199)
        summary['metrics']['candidate_error_fraction'] = .0999
        summary['metrics']['relative_error_reduction'] = .001
        self.assertFalse(m.summary_check(summary)['one_percent'])

    def test_forward_footprint_includes_flanks(self):
        path = self.sam('original', [self.record()])
        original = c.mapped(path, 'p')
        self.assertEqual(m.edit_footprint(original, dict(start=1, end=2), c), dict(contig='chr1', start0=10, end0=13))

    def test_reverse_footprint_uses_native_query_coordinates(self):
        path = self.sam('original', [self.record(flag=16)])
        original = c.mapped(path, 'p')
        self.assertEqual(m.edit_footprint(original, dict(start=0, end=1), c), dict(contig='chr1', start0=12, end0=14))

    def test_unmapped_footprint_is_unavailable(self):
        path = self.sam('original', [self.record(flag=4)])
        self.assertIsNone(m.edit_footprint(c.mapped(path, 'p'), dict(start=0, end=1), c))

    def test_deletion_footprint_is_conservative(self):
        path = self.sam('original', [self.record(cigar='2=3D2=')])
        original = c.mapped(path, 'p')
        self.assertEqual(m.edit_footprint(original, dict(start=1, end=2), c), dict(contig='chr1', start0=10, end0=16))


if __name__ == '__main__':
    unittest.main()
