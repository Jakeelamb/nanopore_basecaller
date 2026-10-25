import argparse
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('context_program_controller',ROOT/'scripts/context-program.py')
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ProgramBoundaryTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'results/context-feedback').mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=ROOT/'results/context-feedback',prefix='program-control-')
        self.directory=Path(self.temporary.name)
        self.args=argparse.Namespace(phase='qualify',scope='all',config=p.CONFIG,output=self.directory/'out',
            admission=self.directory/'grant.json',qualification=None,prepared=None)
        self.now=datetime.now(timezone.utc)
        self.value=dict(schema='context-program-admission/1',id='fixture',phase='qualify',scope='all',config=p.c.pin(p.CONFIG),
            sources_sha256=p.identity(p.sources()),output=str(self.args.output),qualification=None,prepared=None,
            not_before_utc=self.now.isoformat(),expires_utc=(self.now+timedelta(seconds=299)).isoformat(),
            maximum_wall_seconds=299,maximum_output_bytes=4*1024**3,memory_bytes=4*1024**3,
            address_space_bytes=8*1024**3,swap_bytes=0,cpu_quota=2,
            cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-program-fixture.service')

    def tearDown(self):
        self.temporary.cleanup()

    def check_value(self,change=None,expected=None):
        value=dict(self.value)
        if change:
            change(value)
        p.c.fresh(self.args.admission,value)
        if expected:
            with self.assertRaisesRegex(ValueError,expected):
                p.grant(self.args,self.now)
        else:
            self.assertEqual(p.grant(self.args,self.now),value)

    def test_exact_fresh_source_grant_accepts(self):
        self.check_value()

    def test_source_drift_rejects(self):
        self.check_value(lambda x:x.update(sources_sha256='0'*64),'source/input/output')

    def test_wrong_cgroup_rejects(self):
        self.check_value(lambda x:x.update(cgroup='/unrelated.service'),'cgroup/output')

    def test_expired_lease_rejects(self):
        self.check_value(lambda x:x.update(expires_utc=(self.now-timedelta(seconds=1)).isoformat()),'expired/unbounded')

    def test_larger_memory_rejects(self):
        self.check_value(lambda x:x.update(memory_bytes=8*1024**3),'exceeds')

    def test_unrelated_scope_rejects(self):
        self.check_value(lambda x:x.update(scope='query0'),'source/input/output')

    def test_foreign_output_rejects(self):
        self.args.output=Path('/tmp/context-program-unowned')
        self.value['output']=str(self.args.output)
        self.check_value(expected='cgroup/output')

    def test_missing_prerequisite_pin_rejects(self):
        self.check_value(lambda x:x.update(qualification=dict(path='/missing',size=0,sha256='0'*64)),'prerequisite')

    def test_source_census_is_closed_and_unique(self):
        pins=p.sources()
        paths=[x['path'] for x in pins]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertIn(str(ROOT/'scripts/context-program.py'),paths)
        self.assertIn(str(ROOT/'tools/context_decoder/study/source-files.json'),paths)
        for item in pins:
            p.c.check(item)

    def test_native_command_projection_cannot_hide_mismatch(self):
        directory=self.directory/'native'
        directory.mkdir()
        p.c.fresh(directory/'attempt.json',dict(argv=['actual'],compiled_sources=p.sources()))
        p.c.fresh(directory/'result.json',dict(complete=True))
        p.c.fresh(directory/'complete.json',dict(complete=True,attempt=p.c.pin(directory/'attempt.json'),result=p.c.pin(directory/'result.json'),files=[]))
        p.c.fresh(self.directory/'stdout.json',dict(completion=p.c.pin(directory/'complete.json')))
        producer=dict(raw=dict(stdout=dict(path=str(self.directory/'stdout.json'))),argv=['claimed'])
        with self.assertRaisesRegex(ValueError,'attempt command'):
            p.native(directory,producer,p.sources())
