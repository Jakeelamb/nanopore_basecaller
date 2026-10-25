"""Check analysis-only naming and candidate SEQ/Q splicing without truth access."""
from pathlib import Path
import tempfile
import unittest

import evaluate as e


class EvaluationTests(unittest.TestCase):
    def synthetic_completion(self, directory, name, schema, **fields):
        path = Path(directory)/(name+'.json')
        attempt = Path(directory)/(name+'-attempt.json')
        e.loc.fresh(attempt, dict(argv=['synthetic-control'], complete=True))
        e.loc.fresh(path, dict(schema=schema, complete=True, sources=[], files=[], stages=[],
                              attempt=e.loc.pin(attempt), synthetic_control=True, identity=name, **fields))
        return e.loc.pin(path)

    def row(self):
        return dict(sequence='ACGTACGT', quality='ABCDEFGH')

    def test_identity_preserves_real_quality(self):
        self.assertEqual(e.arm_sequence(self.row(), dict(core_begin=2, core_end=6), 'GTAC'),
                         ('ACGTACGT', 'ABCDEFGH'))

    def test_substitution_gets_uncalibrated_quality(self):
        self.assertEqual(e.arm_sequence(self.row(), dict(core_begin=2, core_end=6), 'AAAA'),
                         ('ACAAAAGT', 'AB!!!!GH'))

    def test_insertion_gets_matching_quality_length(self):
        sequence, quality = e.arm_sequence(self.row(), dict(core_begin=2, core_end=6), 'GTTAC')
        self.assertEqual((sequence, quality), ('ACGTTACGT', 'AB!!!!!GH'))

    def test_deletion_gets_matching_quality_length(self):
        sequence, quality = e.arm_sequence(self.row(), dict(core_begin=2, core_end=6), 'GAC')
        self.assertEqual((sequence, quality), ('ACGACGT', 'AB!!!GH'))

    def test_foreign_base_rejected(self):
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            e.arm_sequence(self.row(), dict(core_begin=2, core_end=6), 'NNNN')

    def test_analysis_rename_preserves_all_remaining_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'original.sam', Path(directory)/'renamed.sam'
            record = 'prefix-H4096\t0\tchr1\t1\t60\t8=\t*\t0\t0\tACGTACGT\tABCDEFGH\n'
            source.write_text('@HD\tVN:1.6\n'+record)
            e.rename_native(source, target, 'prefix-H4096')
            fields = target.read_text().splitlines()[1].split('\t')
            self.assertEqual(fields[0], e.loc.UUID)
            self.assertEqual(fields[1:], record.strip().split('\t')[1:])

    def test_other_horizon_not_pooled(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'original.sam', Path(directory)/'renamed.sam'
            record = '\t4\t*\t0\t0\t*\t*\t0\t0\tACGT\tIIII\n'
            source.write_text('H4096'+record+'H12288'+record)
            e.rename_native(source, target, 'H4096')
            self.assertEqual(len(target.read_text().splitlines()), 1)

    def test_missing_horizon_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'original.sam', Path(directory)/'renamed.sam'
            source.write_text('@HD\tVN:1.6\n')
            with self.assertRaisesRegex(ValueError, 'no prefix records'):
                e.rename_native(source, target, 'absent')

    def test_valid_linked_successes(self):
        with tempfile.TemporaryDirectory() as directory:
            location = self.synthetic_completion(directory, 'locationA', 'prefix-location-complete/1')
            prepared = dict(location_complete=location)
            prepared_pin = self.synthetic_completion(directory, 'preparedA', 'prefix-feedback-prepared/1', **prepared)
            e.validate_emission_join(dict(prepared=prepared_pin), prepared, prepared_pin, location)
            emitted = self.synthetic_completion(directory, 'emittedA', 'prefix-feedback-evaluation-emit/1')
            e.validate_mapping_join(dict(emitted=emitted, horizon=4096, arm='reference_free'), emitted, 4096, 'reference_free')

    def test_same_horizon_wrong_repinned_prepared_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            location = self.synthetic_completion(directory, 'locationA', 'prefix-location-complete/1')
            prepared = dict(location_complete=location, horizon=4096)
            original = self.synthetic_completion(directory, 'preparedA', 'prefix-feedback-prepared/1', **prepared)
            other = self.synthetic_completion(directory, 'preparedB', 'prefix-feedback-prepared/1', **prepared)
            e.loc.check(original)
            e.loc.check(other)
            with self.assertRaisesRegex(ValueError, 'different prepared'):
                e.validate_emission_join(dict(prepared=original), prepared, other, location)

    def test_same_horizon_wrong_repinned_location_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            original = self.synthetic_completion(directory, 'locationA', 'prefix-location-complete/1', horizon=4096)
            other = self.synthetic_completion(directory, 'locationB', 'prefix-location-complete/1', horizon=4096)
            prepared = dict(location_complete=original)
            prepared_pin = self.synthetic_completion(directory, 'preparedA', 'prefix-feedback-prepared/1', **prepared)
            e.loc.check(other)
            with self.assertRaisesRegex(ValueError, 'different location'):
                e.validate_emission_join(dict(prepared=prepared_pin), prepared, prepared_pin, other)

    def test_same_horizon_arm_wrong_repinned_emission_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            original = self.synthetic_completion(directory, 'emittedA', 'prefix-feedback-evaluation-emit/1', horizon=4096)
            other = self.synthetic_completion(directory, 'emittedB', 'prefix-feedback-evaluation-emit/1', horizon=4096)
            e.loc.check(original)
            e.loc.check(other)
            with self.assertRaisesRegex(ValueError, 'different emitted'):
                e.validate_mapping_join(dict(emitted=original, horizon=4096, arm='reference_free'), other, 4096, 'reference_free')


if __name__ == '__main__':
    unittest.main()
