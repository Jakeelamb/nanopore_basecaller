"""Controls for the separate measurement boundary, using immutable generic helpers."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('decision_measurement_controls', ROOT/'tools/context_decision/measure.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MeasurementControls(unittest.TestCase):
    def test_primary_parent_census_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sample.sam'
            path.write_text('p\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\n'*2)
            with self.assertRaises(ValueError): m.helper.sam_census(path, ['p'], m.c)

    def test_mapper_quality_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory)/'left.sam', Path(directory)/'right.sam'
            left.write_text('p\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\n')
            right.write_text('p\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!#\n')
            with self.assertRaises(ValueError): m.helper.custody(left, right, ['p'], m.c)

    def test_mapper_unchanged_bytes_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sample.sam'
            path.write_text('p\t4\t*\t0\t0\t*\t*\t0\t0\tAC\t!!\n')
            m.helper.custody(path, path, ['p'], m.c)

    def test_source_inventory_pins_actual_generic_helper(self):
        paths = {pin['path'] for pin in m.source_pins()}
        self.assertIn(str(m.HELPER), paths)
        self.assertIn(str(ROOT/'tools/context_decision/measure.py'), paths)

    def test_unmapped_edit_footprint_is_unavailable(self):
        self.assertIsNone(m.helper.edit_footprint(dict(flag=4), dict(start=0, end=1), m.c))

    def test_hard_clipped_edit_footprint_rejected(self):
        original = dict(flag=0, reverse=False, sequence='ACGT', start=0, fields=['p','0','chr1','1','60','2H4M'])
        with self.assertRaises(ValueError):
            m.helper.edit_footprint(original, dict(start=0, end=1), m.c)


if __name__ == '__main__':
    unittest.main()
