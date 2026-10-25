"""Behavior controls for decision custody, exact parent emission, and input rejection."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
b = module('decision_test_boundary', ROOT/'tools/context_decision/boundary.py')
o = module('decision_test_observer', ROOT/'tools/context_decision/observe.py')


class DecisionControls(unittest.TestCase):
    def test_native_controls_really_execute(self):
        binary = os.environ.get('CONTEXT_DECISION_BINARY')
        self.assertIsNotNone(binary, 'Qualified native test binary is required')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'native'
            result = subprocess.run([binary, 'qualify', '--output', output], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(b.c.read(output/'result.json')['passed'])
            self.assertGreater(b.c.read(output/'result.json')['controls'], 2900)

    def test_source_census_binds_new_policy_and_controller(self):
        paths = {pin['path'] for pin in b.sources()}
        self.assertIn(str(ROOT/'tools/context_decision/src/decision.cpp'), paths)
        self.assertIn(str(ROOT/'scripts/context-decision.py'), paths)
        self.assertIn(str(ROOT/'tools/context_decision/observe.py'), paths)

    def test_structured_ctest_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'tests.xml'
            path.write_text('<testsuite><testcase name="exhaustive_context_decision_controls"/></testsuite>')
            self.assertEqual(b.ctest_counts(path), 1)

    def test_structured_ctest_skipped_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'tests.xml'
            path.write_text('<testsuite><testcase name="exhaustive_context_decision_controls"><skipped/></testcase></testsuite>')
            with self.assertRaises(ValueError): b.ctest_counts(path)

    def test_unittest_method_named_skipped_is_not_a_skip(self):
        b.unittest_counts('test_skipped_rejected ... ok\n\nRan 12 tests in 0.001s\n\nOK\n', 12)

    def test_actual_unittest_skip_rejected(self):
        with self.assertRaises(ValueError):
            b.unittest_counts('test_x ... skipped reason\nRan 12 tests in 0.001s\nOK (skipped=1)\n', 12)

    def test_compiler_cache_string_type_supported_with_hash(self):
        pin = b.c.pin('/usr/bin/c++')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'CMakeCache.txt'
            path.write_text('CMAKE_CXX_COMPILER:STRING=/usr/bin/c++\n')
            self.assertEqual(b.compiler_from_cache(path, pin), pin)

    def test_compiler_cache_wrong_binary_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'CMakeCache.txt'
            path.write_text('CMAKE_CXX_COMPILER:FILEPATH=/usr/bin/true\n')
            with self.assertRaises(ValueError): b.compiler_from_cache(path, b.c.pin('/usr/bin/c++'))

    def test_noop_edit_ledger_rejected(self):
        with self.assertRaises(ValueError):
            o.validate_edits('ACGT', [dict(start=1, end=2, stock='C', replacement='C')])

    def test_overlap_edit_ledger_rejected(self):
        edits = [dict(start=0, end=2, stock='AC', replacement='G'),
                 dict(start=1, end=3, stock='CG', replacement='T')]
        with self.assertRaises(ValueError): o.validate_edits('ACGT', edits)

    def test_exact_sam_aliases_deduplicate_quality_too(self):
        canonical, aliases = o.deduplicate(dict(a=b'AC\t!!\n', b=b'AC\t!!\n', c=b'AC\t!#\n'))
        self.assertEqual(len(canonical), 2)
        self.assertEqual(aliases['a'], aliases['b'])
        self.assertNotEqual(aliases['a'], aliases['c'])

    def test_disabled_parent_preserves_seq_and_quality(self):
        observer = b.module('decision_test_original_splice', b.ORIGINAL/'tools/context_decoder/observe.py')
        data = o.sam_bytes(['parent'], dict(parent=dict(sequence='ACGT', quality='ABCD')), [], observer)
        self.assertEqual(data, b'@HD\tVN:1.6\tSO:unknown\nparent\t4\t*\t0\t0\t*\t*\t0\t0\tACGT\tABCD\n')


if __name__ == '__main__':
    unittest.main()
