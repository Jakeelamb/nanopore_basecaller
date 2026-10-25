"""Window selection/projection controls before native execution and truth access."""
import unittest
from pathlib import Path
import tempfile

import prepare as p


class PrepareTests(unittest.TestCase):
    def row(self):
        return dict(qname='prefix', parent=p.loc.UUID, horizon=4096,
                    sequence='A'*100, quality='I'*100, moves='10'*100)

    def located(self, reverse=False):
        anchor = dict(query_begin=0, query_end=100, reference_begin=1000, reference_end=1100,
                      reverse=reverse)
        return dict(status='located', usable_primary=dict(anchors=[anchor], contig='chr1', reverse=reverse))

    def test_minimum_quality_predeclared(self):
        row = self.row()
        row['quality'] = 'I'*30+'!'*20+'I'*50
        value = p.choose(row, self.located())
        self.assertEqual((value['core_begin'], value['core_end']), (30, 50))

    def test_ties_deterministic(self):
        self.assertEqual(p.choose(self.row(), self.located()), p.choose(self.row(), self.located()))

    def test_unknown_never_reference(self):
        self.assertEqual(p.choose(self.row(), dict(status='unknown'))['status'], 'abstained')

    def test_multimap_never_reference(self):
        self.assertEqual(p.choose(self.row(), dict(status='multimap'))['status'], 'abstained')

    def test_no54base_anchor(self):
        value = self.located()
        value['usable_primary']['anchors'][0]['query_end'] = 53
        self.assertEqual(p.choose(self.row(), value)['status'], 'abstained')

    def test_forward_projection(self):
        anchor = self.located()['usable_primary']['anchors'][0]
        self.assertEqual(p.project(anchor, 20, 40), (1020, 1040))

    def test_reverse_projection(self):
        anchor = self.located(True)['usable_primary']['anchors'][0]
        self.assertEqual(p.project(anchor, 20, 40), (1060, 1080))

    def test_projection_crossing_gap_rejected(self):
        anchor = self.located()['usable_primary']['anchors'][0]
        with self.assertRaisesRegex(ValueError, 'gap'):
            p.project(anchor, -1, 20)

    def test_dense_rows_excluded(self):
        row = self.row()
        row['moves'] = '10000'*100
        self.assertEqual(p.choose(row, self.located())['status'], 'abstained')

    def test_padding_rows_excluded(self):
        row = self.row()
        row['horizon'] = 110
        self.assertEqual(p.choose(row, self.located())['status'], 'abstained')

    def test_missing_fai_rejected_before_native_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'FAI required before faidx'):
                p.reference_index(Path(directory)/'reference.fa')


if __name__ == '__main__':
    unittest.main()
