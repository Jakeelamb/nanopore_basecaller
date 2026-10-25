import unittest

import verify_counts


class CountControls(unittest.TestCase):
    def setUp(self):
        self.metrics = dict(candidate_counts=dict(m=90,x=5,i=3,d=2), left_counts=dict(m=89,x=6,i=3,d=2),
            candidate_error_fraction=.1, left_error_fraction=.11, relative_error_reduction=1/11)
        self.checks = dict(denominators=dict(candidate=100,left=100), one_percent=True)

    def test_positive(self):
        result = verify_counts.endpoint(self.metrics,self.checks)
        self.assertEqual(result['candidate_error_fraction_exact'], '1/10')
        self.assertEqual(result['relative_reduction_exact'], '1/11')

    def test_transposed_counts(self):
        self.metrics['candidate_counts']['x'] += 1
        with self.assertRaises(ValueError):
            verify_counts.endpoint(self.metrics,self.checks)

    def test_wrong_denominator(self):
        self.checks['denominators']['candidate'] = 99
        with self.assertRaises(ValueError):
            verify_counts.endpoint(self.metrics,self.checks)

    def test_wrong_gate(self):
        self.checks['one_percent'] = False
        with self.assertRaises(ValueError):
            verify_counts.endpoint(self.metrics,self.checks)

    def test_invalid_counts(self):
        for counts in ({'m':0,'x':0,'i':0,'d':0}, {'m':-1,'x':1,'i':1,'d':1}, {'m':True,'x':1,'i':1,'d':1}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                verify_counts.ratio(counts)


if __name__ == '__main__':
    unittest.main(verbosity=2)
