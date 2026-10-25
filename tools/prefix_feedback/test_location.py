"""Contract controls using small synthetic SAM records, never truth or native tools."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prefix_location', Path(__file__).with_name('location.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class LocationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'mapped.sam'
        self.row = dict(qname='prefix-H4096', parent=m.UUID, horizon=4096,
                        sequence='A'*60, quality='I'*60)

    def record(self, flag=0, mapq=60, cigar='60=', seq=None, quality=None):
        return '\t'.join((self.row['qname'], str(flag), 'chr1' if not flag & 4 else '*', '101',
                          str(mapq), cigar if not flag & 4 else '*', '*', '0', '0',
                          seq or self.row['sequence'], quality or self.row['quality']))+'\n'

    def result(self, text):
        self.path.write_text(text)
        return m.sam_locations(self.path, [self.row])[0]

    def test_unique_primary_location(self):
        self.assertEqual(self.result(self.record())['status'], 'located')

    def test_unknown_unmapped(self):
        self.assertEqual(self.result(self.record(flag=4, mapq=0))['status'], 'unknown')

    def test_mapq_bounds(self):
        for mapq in (0, 29, 255):
            self.assertEqual(self.result(self.record(mapq=mapq))['status'], 'unknown')
        for mapq in (30, 254):
            self.assertEqual(self.result(self.record(mapq=mapq))['status'], 'located')

    def test_multimap_retains_secondary(self):
        value = self.result(self.record()+self.record(flag=256, seq='*', quality='*'))
        self.assertEqual(value['status'], 'multimap')
        self.assertEqual(len(value['alignments']), 2)

    def test_supplementary_forces_abstention(self):
        self.assertEqual(self.result(self.record()+self.record(flag=2048))['status'], 'multimap')

    def test_quality_custody_rejected(self):
        with self.assertRaisesRegex(ValueError, 'custody'):
            self.result(self.record(quality='H'*60))

    def test_reverse_original_query_coordinates(self):
        value = self.result(self.record(flag=16, seq='T'*60))
        self.assertEqual(value['status'], 'located')
        self.assertEqual(value['usable_primary']['anchors'][0]['query_begin'], 0)

    def test_fragmented_anchor_abstains(self):
        self.assertEqual(self.result(self.record(cigar='30=1D30='))['status'], 'insufficient_continuous_anchor')

    def test_duplicate_primary_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.result(self.record()+self.record())

    def test_foreign_name_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            self.result(self.record().replace('prefix-H4096', 'other'))

    def test_hardclip_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Hard-clipped'):
            self.result(self.record(cigar='1H60='))

    def test_bad_query_span_rejected(self):
        with self.assertRaisesRegex(ValueError, 'query span'):
            self.result(self.record(cigar='59='))


if __name__ == '__main__':
    unittest.main()
