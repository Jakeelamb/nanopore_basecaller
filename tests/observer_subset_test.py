import argparse
import copy
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('subset_controls',ROOT/'tools/context_decoder/observe_subset.py')
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
c=s.c


class SubsetControls(unittest.TestCase):
    def test_native_identity_handles_both_orientations_and_quality(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            native=directory/'native.sam'
            candidate=directory/'candidate.sam'
            native.write_text('one\t16\tx\t1\t60\t5=\t*\t0\t0\tAACGT\tedcba\n'
                              'two\t0\tx\t10\t60\t3=\t*\t0\t0\tGGT\tzzz\n')
            candidate.write_text('two\t4\t*\t0\t0\t*\t*\t0\t0\tGGT\tzzz\n'
                                 'one\t4\t*\t0\t0\t*\t*\t0\t0\tACGTT\tabcde\n')
            proof=s.native_identity(candidate,native,['one','two'])
            self.assertEqual([p['length'] for p in proof],[5,3])
            candidate.write_text(candidate.read_text().replace('abcde','abcdf'))
            with self.assertRaisesRegex(ValueError,'SEQ/Q differs'):
                s.native_identity(candidate,native,['one','two'])
            with self.assertRaisesRegex(ValueError,'census'):
                s.native_identity(candidate,native,['one'])

    def test_context_alias_requires_exact_complete_sam_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            arms=[]
            for name in s.o.ARMS:
                path=directory/(name+'.sam')
                path.write_text('same complete SAM bytes\n')
                arms.append(dict(arm=name,sam=c.pin(path)))
            self.assertEqual(set(s.context_identity(arms)),set(s.o.ARMS))
            path=directory/'selected.sam'
            path.write_text('different bytes\n')
            arms[-1]['sam']=c.pin(path)
            with self.assertRaisesRegex(ValueError,'SAM bytes differ'):
                s.context_identity(arms)
            with self.assertRaisesRegex(ValueError,'arm census'):
                s.context_identity(arms[:2])

    def test_grant_requires_exact_source_phase_inputs_and_caps(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            manifest=directory/'complete.json'
            manifest.write_text('{"synthetic":true}\n')
            args=argparse.Namespace(manifest=manifest,output=s.w.RESULTS/'subset-hermetic-control')
            now=datetime.now(timezone.utc)
            grant=dict(schema='context-feedback-subset-observation-admission/1',id='subset-test',phase='checkpoint',
                source=s.SOURCE,observer_source=s.o.SOURCE,controller=c.pin(s.CONTROLLER),
                source_inventory_sha256=s.w.inventory_hash(s.w.sources()),manifest=c.pin(manifest),output=str(args.output),
                not_before_utc=(now-timedelta(seconds=1)).isoformat(),expires_utc=(now+timedelta(seconds=100)).isoformat(),
                maximum_wall_seconds=100,maximum_output_bytes=4*1024**3,memory_bytes=16*1024**3,address_space_bytes=24*1024**3,
                swap_bytes=0,cpu_quota=2,cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-feedback-subset-test.service')
            s.validate_grant(args,grant,now)
            for key,value in [('phase','full'),('source_inventory_sha256','0'*64),('memory_bytes',16*1024**3+1),
                    ('address_space_bytes',24*1024**3+1),('maximum_output_bytes',4*1024**3+1),('cpu_quota',3),
                    ('swap_bytes',1),('output',str(directory/'escape')),('expires_utc',(now-timedelta(seconds=1)).isoformat())]:
                with self.subTest(key=key),self.assertRaises(ValueError):
                    s.validate_grant(args,dict(grant,**{key:value}),now)
            for key in ('source','observer_source','controller','manifest'):
                invalid=copy.deepcopy(grant)
                invalid[key]['sha256']='0'*64
                with self.subTest(key=key),self.assertRaises(ValueError):
                    s.validate_grant(args,invalid,now)


if __name__=='__main__':
    unittest.main()
