"""Exercise the public frozen-rule rejection boundary without sequencing fixtures."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'results/flank-prior/build/release/flank-prior'


class FlankBoundaryTests(unittest.TestCase):
    def test_rejects_weight_tuning_before_data_access(self):
        config=json.loads((ROOT/'config/flank-prior-dev-v1.json').read_text())
        for key in ['weight','margin','neural_deficit']:
            changed=dict(config)
            changed[key]=7
            with tempfile.TemporaryDirectory() as folder:
                folder=Path(folder)
                source=folder/'config.json'
                source.write_text(json.dumps(changed))
                output=folder/'output'
                result=subprocess.run([str(BINARY),'diagnostic',str(source),str(output),'32'],capture_output=True,text=True)
                self.assertEqual(result.returncode,1)
                self.assertIn('frozen protocol',result.stderr)
                self.assertFalse(output.exists())

    def test_rejects_unregistered_query_count(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'output'
            result=subprocess.run([str(BINARY),'diagnostic',str(ROOT/'config/flank-prior-dev-v1.json'),str(output),'31'],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertIn('predeclared index sets only',result.stderr)
            self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
