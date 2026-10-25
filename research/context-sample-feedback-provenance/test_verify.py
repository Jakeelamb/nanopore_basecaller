import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import verify


class SnapshotControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.live = self.root/'original.py'
        self.live.write_bytes(b'fixture source\n')
        self.copy = self.root/'snapshot.py'
        self.copy.write_bytes(self.live.read_bytes())
        self.pin = dict(path=str(self.live), size=self.live.stat().st_size,
                        sha256=hashlib.sha256(self.live.read_bytes()).hexdigest())
        self.manifest = dict(schema='context-sample-feedback-published-source-snapshots/1',
            snapshots=[dict(snapshot='snapshot.py', original=self.pin)],
            compiled_sources=[], compiled_source_identity='fixture')
        self.save()

    def tearDown(self):
        self.temporary.cleanup()

    def save(self):
        (self.root/'manifest.json').write_text(json.dumps(self.manifest))

    def test_snapshot_and_live_positive(self):
        self.assertTrue(verify.verify(self.root)['complete'])
        self.assertTrue(verify.verify(self.root, live=True)['live_sources_checked'])

    def test_corrupt_snapshot(self):
        self.copy.write_bytes(b'changed\n')
        with self.assertRaises(ValueError):
            verify.verify(self.root)

    def test_corrupt_live_source(self):
        self.live.write_bytes(b'changed\n')
        self.assertTrue(verify.verify(self.root)['complete'])
        with self.assertRaises(ValueError):
            verify.verify(self.root, live=True)

    def test_duplicate_path(self):
        self.manifest['snapshots'] *= 2
        self.save()
        with self.assertRaises(ValueError):
            verify.verify(self.root)

    def test_absolute_escape(self):
        self.manifest['snapshots'][0]['snapshot'] = '/etc/hostname'
        self.save()
        with self.assertRaises(ValueError):
            verify.verify(self.root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
