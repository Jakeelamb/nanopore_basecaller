"""The genuine old frame must pass and each named corruption must reach its guard."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sample_feedback_test_boundary', ROOT/'tools/context_sample_feedback/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
o = b.module('sample_test_emitter', ROOT/'tools/context_sample_feedback/observe.py')
FRAME = b.ORIGINAL/'results/context-feedback/v2-query0-2/frames/ordinary-0/frame.tsv'
FRAME_HASH = '55ce28de79ba13281cb00011940fb3c9b906eca0900b95600a4645e634541b32'


def fields(path):
    lines = Path(path).read_text(encoding='ascii').splitlines()
    return lines[0], dict(line.split('\t',1) for line in lines[1:])


def write_fields(path, schema, values):
    path.write_text(schema+'\n'+''.join(key+'\t'+str(value)+'\n' for key,value in sorted(values.items())), encoding='ascii')
    return b.c.pin(path)


def repin(values, prefix, pin):
    values.update({prefix+'_'+key:str(value) for key,value in pin.items()})


def synthetic_json(path, value):
    path.write_text(json.dumps(value), encoding='ascii')
    return b.c.pin(path)


def synthetic_recovery(root, name):
    directory = root/'logs'/('sample-supervisor-'+name)
    directory.mkdir(parents=True)
    output = root/'results'/name
    grant = dict(id=name, output=str(output), cgroup='/synthetic/'+name, scope='query0',
                 config=dict(path=str(root/'config.json')), case_id='ordinary/0/ordinary',
                 source_audit=None, arm=None, recovery=None, qualification=None, inputs=[])
    admission = synthetic_json(root/(name+'-grant.json'), grant)
    unit = 'context-sample-feedback-'+name+'.service'
    intake = dict(grant_id=name, unit=unit, admission=admission['path'], description='synthetic '+name)
    synthetic_json(directory/'intake.json', intake)
    observation = dict(exit=0, argv=['systemctl', '--user', 'show', unit],
                       properties=dict(ControlGroup=grant['cgroup'], Description=intake['description']))
    worker = dict(verified=True, parent_lock_retained=True, admission=admission, observation=observation)
    argv = ['systemd-run', '--unit='+unit, '--description='+intake['description'], '--working-directory='+str(ROOT),
            '--', '/synthetic/uv', 'run', '--no-sync', 'python', str(ROOT/'scripts/context-sample-feedback.py'), 'infer',
            '--scope', 'query0', '--config', grant['config']['path'], '--output', str(output),
            '--admission', admission['path'], '--worker-intake', str(directory/'intake.json'), '--case-id', grant['case_id']]
    command = synthetic_json(directory/'command.json', dict(grant=grant, argv=argv, cwd=str(ROOT)))
    (directory/'command.sh').write_text(b.shlex.join(argv)+'\n')
    (directory/'cwd.txt').write_text(str(ROOT)+'\n')
    proof = dict(observation, properties=dict(observation['properties'], MainPID='0', ControlPID='0', ActiveState='failed'))
    terminal = synthetic_json(directory/'terminal.json', dict(proof=proof, owned_cgroup_terminal=True, canonical_lock_retained=True))
    launcher = root/'logs'/('synthetic-producer-'+name)
    launcher.mkdir()
    native = output/'native-case'
    producer = dict(launcher=str(launcher), admission_id=name, name='sample-infer',
                    argv=['/synthetic/binary', 'infer', '--output', str(native)])
    synthetic_json(launcher/'launch.json', dict(admission=grant, cwd=str(ROOT),
        argv=[str(root/'logs/recorder-root/scripts/record-command.sh'), producer['name'], *producer['argv']]))
    return dict(producer=synthetic_json(launcher/'finish.json', producer), outer_command=command, outer_terminal=terminal,
                worker_intake=synthetic_json(directory/'worker-intake.json', worker),
                launcher_cleanup=synthetic_json(directory/'launcher-cleanup.json', dict(terminal=True)), native_directory=str(native))


def synthetic_qualification(root, closure_change=None):
    root.mkdir()
    closure = {}
    for key in ('compiler', 'formatter', 'cache', 'compile_commands', 'binary', 'library', 'observer'):
        path = root/key
        path.write_text('synthetic '+key)
        closure[key] = b.c.pin(path)
    observer = closure.pop('observer')
    closure['runtime_libraries'] = [closure.pop('library')]
    binary = closure['binary']
    if closure_change is not None: closure_change(closure)
    synthetic_json(root/'build-closure.json', closure)
    raw = root/'raw'
    raw.mkdir()
    argv = ['/synthetic/compiler']
    values = {'command.sh': b.shlex.join(argv)+'\n', 'cwd.txt': str(ROOT)+'\n',
              'start.txt': '2026-10-24T00:00:00Z\n', 'end.txt': '2026-10-24T00:00:01Z\n',
              'exit-status.txt': '0\n', 'stdout': '', 'stderr': '',
              'time.txt': '\tExit status: 0\n\tCommand being timed: "/synthetic/compiler"\n'
                          '\tUser time (seconds): 0\n\tSystem time (seconds): 0\n'
                          '\tMaximum resident set size (kbytes): 1\n\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:01\n'}
    for name, value in values.items(): (raw/name).write_text(value)
    stage = dict(schema='context-feedback-stage/1', exit=0, failure=None, projection_error=None, argv=argv,
                 terminal=synthetic_json(root/'stage-terminal.json', dict(exit=0, failure=None, argv=argv)),
                 group_cleanup=synthetic_json(root/'stage-cleanup.json', dict(terminal=True)),
                 raw={name:b.c.pin(raw/name) for name in values}, missing_raw=[])
    summary = dict(phase='qualify', binary=binary, observer_binary=observer, native=[],
                   stages=[synthetic_json(root/'stage.json', stage)])
    synthetic_json(root/'summary.json', summary)
    worker = dict(complete=True, phase='qualify', sources_sha256=b.identity([]),
                  files=[b.c.pin(root/name) for name in ('build-closure.json', 'summary.json')])
    terminal = dict(error=None, exit=0, owned_cgroup_terminal=True,
                    proof=dict(properties=dict(MainPID='0', ControlPID='0', Result='success', ActiveState='inactive')))
    outer = dict(complete=True, phase='qualify', whole_worker_cgroup_terminal=True,
                 worker=synthetic_json(root/'complete.json', worker),
                 worker_intake=synthetic_json(root/'worker-intake.json', dict(verified=True)),
                 terminal=synthetic_json(root/'terminal.json', terminal),
                 files=[synthetic_json(root/'launcher-cleanup.json', dict(terminal=True))])
    synthetic_json(root/'execution-complete.json', outer)
    return closure, outer


class SampleFeedbackControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ['CONTEXT_SAMPLE_FEEDBACK_BINARY']
        b.c.require(Path(cls.binary).is_absolute() and Path(cls.binary).is_file(), 'Qualified binary is required, never skip consumed-frame tests')

    def consume(self, frame, digest, directory):
        return subprocess.run([self.binary, 'consume-frame', '--frame', str(frame), '--frame-sha256', digest,
            '--output', str(Path(directory)/'native')], text=True, capture_output=True, timeout=60)

    def mutant(self, key, value, message, base=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema, guard = fields(FRAME)
            if base:
                base_schema, source = fields(guard['base_frame_path'])
                source[key] = value
                repin(guard, 'base_frame', write_fields(root/'base.tsv', base_schema, source))
            else:
                guard[key] = value
            frame = write_fields(root/'frame.tsv', schema, guard)
            result = self.consume(frame['path'], frame['sha256'], root)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(message, result.stderr)

    def test_genuine_frame_executes_exact_rust_scalar_comparisons(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.consume(FRAME, FRAME_HASH, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            seal = json.loads(Path(json.loads(result.stdout)['completion']['path']).read_text())
            report = json.loads(Path(seal['result']['path']).read_text())
            self.assertGreater(report['scalar_comparisons'], 0)

    def test_manifest_pin_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.consume(FRAME, '0'*64, directory)
            self.assertEqual(result.returncode, 2)
            self.assertIn('manifest pin mismatch', result.stderr)

    def test_native_center_guard(self):
        self.mutant('native_center', 'A', 'declared guards/center differ')

    def test_expanded_interval_guard(self):
        self.mutant('expanded_t_end', '328', 'expanded interval differs')

    def test_owned_geometry_guard(self):
        self.mutant('owned_start', '12344', 'native parent span/owned center mismatch')

    def test_initial_state_guard(self):
        self.mutant('initial_state', '75', 'initial', base=True)

    def test_orientation_guard(self):
        self.mutant('reverse', '2', 'invalid orientation', base=True)

    def test_exact_scalar_value_guard_after_repin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema, guard = fields(FRAME)
            base_schema, base = fields(guard['base_frame_path'])
            scalar = Path(base['scalar_controls_path']).read_text(encoding='ascii').splitlines()
            sequence, _ = scalar[0].split('\t')
            scalar[0] = sequence+'\t0'
            path = root/'scalar.tsv'
            path.write_text('\n'.join(scalar)+'\n', encoding='ascii')
            repin(base, 'scalar_controls', b.c.pin(path))
            repin(guard, 'base_frame', write_fields(root/'base.tsv', base_schema, base))
            frame = write_fields(root/'frame.tsv', schema, guard)
            result = self.consume(frame['path'], frame['sha256'], root)
            self.assertEqual(result.returncode, 2)
            self.assertIn('retained unchanged Rust scalar bit parity failed', result.stderr)

    def test_empty_scalar_controls_guard_after_repin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema, guard = fields(FRAME)
            base_schema, base = fields(guard['base_frame_path'])
            path = root/'scalar.tsv'; path.write_text('', encoding='ascii')
            repin(base, 'scalar_controls', b.c.pin(path))
            repin(guard, 'base_frame', write_fields(root/'base.tsv', base_schema, base))
            frame = write_fields(root/'frame.tsv', schema, guard)
            result = self.consume(frame['path'], frame['sha256'], root)
            self.assertEqual(result.returncode, 2)
            self.assertIn('incomplete scalar controls', result.stderr)

    def test_disjoint_numeric_scopes(self):
        b.check_scope('query0', 'ordinary/0/ordinary')
        b.check_scope('first32', 'ordinary/31/ordinary')
        b.check_scope('remaining', 'private/0/withheld')
        for scope, case in (('first32','ordinary/0/ordinary'), ('remaining','ordinary/31/ordinary'), ('query0','private/0/ordinary')):
            with self.assertRaises(ValueError): b.check_scope(scope, case)

    def test_lossless_trace_archive_rejects_wrong_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sample-trace.bin'
            path.write_bytes(bytes(range(256))*4)
            rows = b.archive_traces(directory)
            self.assertFalse(path.exists())
            b.check_archive(rows[0])
            rows[0]['original']['sha256'] = '0'*64
            with self.assertRaises(ValueError): b.check_archive(rows[0])

    def test_source_inventory_keeps_original_locations(self):
        paths = {pin['path'] for pin in b.sources()}
        self.assertIn(str(b.ORIGINAL/'tools/context_decoder/src/guarded_io.cpp'), paths)
        self.assertIn(str(b.STUDY/'src/packet.cpp'), paths)
        self.assertNotIn(str(ROOT/'tools/context_decoder/src/guarded.cpp'), paths)

    def choice_fixture(self):
        case = dict(case_id='ordinary/0/ordinary', domain='ordinary')
        row = dict(case, arm='sample')
        for role in ('baseline','proposed','accepted'):
            row[role] = 'C'; row[role+'_sha256'] = o.dna_digest('C')
            row[role+'_likelihood'] = '-1'; row[role+'_origins'] = '8'
        nn = dict(row, arm='nn_u')
        return case, row, nn

    def test_wrong_nn_baseline_rejected_without_truth(self):
        case, row, nn = self.choice_fixture()
        o.validate_choice(case, row, nn)
        row['baseline'] = 'A'; row['baseline_sha256'] = o.dna_digest('A')
        with self.assertRaisesRegex(ValueError, 'common-U NN baseline'): o.validate_choice(case, row, nn)

    def test_mismatched_choice_case_rejected_without_truth(self):
        case, row, nn = self.choice_fixture()
        row['case_id'] = 'ordinary/1/ordinary'
        with self.assertRaisesRegex(ValueError, 'case/domain'): o.validate_choice(case, row, nn)

    def test_mismatched_choice_digest_rejected_without_truth(self):
        case, row, nn = self.choice_fixture()
        row['accepted_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'DNA digest'): o.validate_choice(case, row, nn)

    def test_recovery_source_identity_rejected_before_payload(self):
        value = dict(schema='context-sample-feedback-recovery/1', case_id='ordinary/0/ordinary', scope='query0', source_identity='a'*64)
        b.recovery_header(value, 'ordinary/0/ordinary', 'query0', 'a'*64)
        with self.assertRaisesRegex(ValueError, 'source/case/scope'):
            b.recovery_header(value, 'ordinary/0/ordinary', 'query0', 'b'*64)

    def test_recovery_scope_rejected_before_payload(self):
        value = dict(schema='context-sample-feedback-recovery/1', case_id='ordinary/0/ordinary', scope='first32', source_identity='a'*64)
        with self.assertRaisesRegex(ValueError, 'disjoint frozen scope'):
            b.recovery_header(value, 'ordinary/0/ordinary', 'first32', 'a'*64)

    def test_synthetic_recovery_rejects_transposed_successful_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(b.w, 'LOGS', root/'logs'), mock.patch.object(b.w, 'RESULTS', root/'results'):
                first, second = (synthetic_recovery(root, name) for name in ('first', 'second'))
                b.recovery_original(first)
                b.recovery_original(second)
                first.update(producer=second['producer'], native_directory=second['native_directory'])
                with self.assertRaisesRegex(ValueError, 'producer original admission'):
                    b.recovery_original(first)

    def test_synthetic_recovery_rejects_transposed_supervisor_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(b.w, 'LOGS', root/'logs'), mock.patch.object(b.w, 'RESULTS', root/'results'):
                first, second = (synthetic_recovery(root, name) for name in ('first', 'second'))
                for key in ('outer_terminal', 'launcher_cleanup', 'worker_intake'):
                    with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'supervisor membership'):
                        b.recovery_original(dict(first, **{key:second[key]}))

    def test_synthetic_recovery_rejects_wrong_intake_admission_or_cgroup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(b.w, 'LOGS', root/'logs'), mock.patch.object(b.w, 'RESULTS', root/'results'):
                first, second = (synthetic_recovery(root, name) for name in ('first', 'second'))
                original = b.c.read(first['worker_intake']['path'])
                for key in ('admission', 'observation'):
                    worker = dict(original, **{key:b.c.read(second['worker_intake']['path'])[key]})
                    changed = dict(first, worker_intake=synthetic_json(Path(first['worker_intake']['path']), worker))
                    with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'intake/admission|worker cgroup'):
                        b.recovery_original(changed)

    def test_synthetic_recovery_rejects_wrong_original_native_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(b.w, 'LOGS', root/'logs'), mock.patch.object(b.w, 'RESULTS', root/'results'):
                first = synthetic_recovery(root, 'first')
                first['native_directory'] = str(root/'results/other/native-case')
                with self.assertRaisesRegex(ValueError, 'original native directory'):
                    b.recovery_original(first)

    def test_synthetic_completed_rechecks_every_nested_build_pin(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(b, 'sources', return_value=[]):
            for key in ('compiler', 'formatter', 'cache', 'compile_commands', 'binary', 'runtime_libraries'):
                root = Path(directory)/key
                closure, _ = synthetic_qualification(root)
                b.completed(root, 'qualify')
                pin = closure[key][0] if key == 'runtime_libraries' else closure[key]
                Path(pin['path']).write_text('changed synthetic bytes')
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Changed file'):
                    b.completed(root, 'qualify')

    def test_synthetic_completed_rejects_empty_runtime_or_different_binary(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(b, 'sources', return_value=[]):
            for key in ('runtime_libraries', 'binary'):
                def change(closure):
                    closure[key] = [] if key == 'runtime_libraries' else closure['compiler']
                root = Path(directory)/key
                synthetic_qualification(root, change)
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'runtime closure is empty|build/runtime binary'):
                    b.completed(root, 'qualify')

    def test_synthetic_completed_requires_original_success_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(b, 'sources', return_value=[]):
            for key in ('terminal', 'raw'):
                root = Path(directory)/key
                _, outer = synthetic_qualification(root)
                if key == 'terminal':
                    terminal = b.c.read(outer['terminal']['path'])
                    terminal['exit'] = 1
                    outer['terminal'] = synthetic_json(root/'terminal.json', terminal)
                    synthetic_json(root/'execution-complete.json', outer)
                else:
                    (root/'raw/exit-status.txt').write_text('1\n')
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'whole unit failed|Changed file'):
                    b.completed(root, 'qualify')


if __name__ == '__main__':
    unittest.main()
