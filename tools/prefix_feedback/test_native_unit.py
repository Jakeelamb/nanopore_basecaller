"""Prior-session and CTest observation guards, without native execution."""
import unittest

import native_unit as n


MARKERS = '\n'.join(('"reset_monotonic_commit_controls":true',
                      '"actual_session_input_controls":true',
                      '"independent_state_dependent_rank_comparisons":1',
                      '"disabled_exact_bits_and_trace":true', '"strong_private_snv_ins_del":true'))
XML = '<testsuite tests="1" failures="0" skipped="0"><testcase name="causal_prefix_controls" status="run"/></testsuite>'


class NativeUnitTests(unittest.TestCase):
    def result(self):
        return dict(schema='prefix-feedback-result/1', parent=n.loc.UUID, qname=n.loc.UUID+'__H4096',
                    horizon=4096, encoder_reset=True, irreversible_commits=0,
                    session=dict(schema='prefix-feedback-session/1', parent=n.loc.UUID, horizon=4096,
                                 encoder_reset=True, policy='bounded_reset_zero_commits', revision='ACGT',
                                 committed_prefix='', committed_quality=''))

    def test_named_executed_ctest(self):
        n.ctest_report(XML, MARKERS)

    def test_zero_tests_rejected(self):
        with self.assertRaises(ValueError):
            n.ctest_report('<testsuite tests="0"/>', MARKERS)

    def test_skipped_ctest_rejected(self):
        with self.assertRaises(ValueError):
            n.ctest_report(XML.replace('/>', '><skipped/></testcase>'), MARKERS)

    def test_wrong_name_rejected(self):
        with self.assertRaises(ValueError):
            n.ctest_report(XML.replace('causal_prefix_controls', 'other'), MARKERS)

    def test_missing_native_markers_rejected(self):
        with self.assertRaises(ValueError):
            n.ctest_report(XML, '')

    def test_valid_prior_actual_revision(self):
        self.assertEqual(n.validate_prior_result(self.result(), n.loc.UUID, 'ACGT')['revision'], 'ACGT')

    def test_swapped_horizon_rejected(self):
        result = self.result()
        result['horizon'] = result['session']['horizon'] = 12288
        with self.assertRaises(ValueError):
            n.validate_prior_result(result, n.loc.UUID, 'ACGT')

    def test_foreign_parent_rejected(self):
        result = self.result()
        result['parent'] = result['session']['parent'] = '00000000-0000-0000-0000-000000000000'
        with self.assertRaises(ValueError):
            n.validate_prior_result(result, n.loc.UUID, 'ACGT')

    def test_changed_actual_revision_rejected(self):
        with self.assertRaises(ValueError):
            n.validate_prior_result(self.result(), n.loc.UUID, 'TGCA')

    def test_prior_commit_rejected_by_explicit_zero_policy(self):
        result = self.result()
        result['session']['committed_prefix'], result['session']['committed_quality'] = 'A', '!'
        with self.assertRaises(ValueError):
            n.validate_prior_result(result, n.loc.UUID, 'ACGT')


if __name__ == '__main__':
    unittest.main()
