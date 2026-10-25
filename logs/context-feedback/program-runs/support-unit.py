import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
from unittest import mock

WORKER = Path(__file__).resolve()
ROOT = WORKER.parents[3]
RUNNER = WORKER.with_name('run-support-bounded.py')
spec = importlib.util.spec_from_file_location('support_execution', ROOT/'scripts/context-feedback.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
c = w.c
FILES = ('tools/support_context/transport.py', 'tools/support_context/source.json',
         'tests/test_support_transport.py', 'research/context-support-transport.md')
TEST_ARGV = ['uv', 'run', '--no-sync', 'python', '-m', 'unittest', 'discover',
             '-s', 'tests', '-p', 'test_support_transport.py', '-v']
RAW_NAMES = {'command.sh', 'cwd.txt', 'start.txt', 'end.txt',
             'exit-status.txt', 'stdout', 'stderr', 'time.txt'}
NEGATIVE_NAMES = {'empty_sources', 'empty_stages', 'empty_files', 'wrong_phase',
                  'missing_outer_raw_stdout', 'missing_inner_stage', 'missing_inner_raw_stderr',
                  'missing_launcher_cleanup', 'corrupt_outer_completion_pin'}


def source_pins():
    return [c.pin(ROOT/name) for name in FILES] + [c.pin(WORKER)]


def exact_pins(actual, expected, message):
    c.require(len(actual) == len(expected) and len({item['path'] for item in actual}) == len(actual)
              and {item['path']: item for item in actual} == {item['path']: item for item in expected}, message)
    for item in actual:
        c.check(item)


def raw_receipt(directory, argv):
    raw = {name: c.pin(directory/name) for name in RAW_NAMES}
    c.require(shlex.split((directory/'command.sh').read_text()) == argv
              and (directory/'cwd.txt').read_text().strip() == str(ROOT)
              and (directory/'exit-status.txt').read_text().strip() == '0', 'Outer raw command/cwd/exit differs')
    begin = (directory/'start.txt').read_text().strip()
    end = (directory/'end.txt').read_text().strip()
    c.require(begin.endswith('Z') and end.endswith('Z') and datetime.fromisoformat(begin) <= datetime.fromisoformat(end),
              'Outer raw clocks differ')
    times = {}
    for line in (directory/'time.txt').read_text().splitlines():
        if line.startswith('\t') and ': ' in line:
            key, value = line.strip().split(': ', 1)
            times[key] = value
    c.require(times.get('Exit status') == '0'
              and times.get('Command being timed') == '"'+' '.join(argv)+'"'
              and float(times['User time (seconds)']) >= 0 and float(times['System time (seconds)']) >= 0
              and int(times['Maximum resident set size (kbytes)']) > 0, 'Outer raw GNU time differs')
    wall = times['Elapsed (wall clock) time (h:mm:ss or m:ss)'].split(':')
    c.require(len(wall) in (2, 3) and all(float(part) >= 0 for part in wall), 'Outer raw wall time differs')
    return raw


def outer_receipt(identity, phase, qualification_id=None):
    c.require(re.fullmatch('[a-zA-Z0-9_-]+', identity) is not None, 'Bad qualification identity')
    directory = ROOT/'results/context-feedback'/identity
    outer = ROOT/'logs/context-feedback/program-runs'/('run-'+identity)
    start = c.read(outer/'start.json')
    c.require(start['cwd'] == str(ROOT) and start['lock'] == str(w.LOCK)
              and start['worker'] == c.pin(WORKER) and start['controller'] == c.pin(RUNNER),
              'Qualification outer source/cwd/lock differs')
    exact_pins([start['worker'], start['controller']], [c.pin(WORKER), c.pin(RUNNER)],
               'Qualification outer source census differs')
    expected = ['/home/jake/.local/bin/uv', 'run', '--no-sync', 'python', str(WORKER), phase, identity]
    if qualification_id is not None:
        expected += ['--qualification', qualification_id]
    command = start['argv']
    marker = command.index('--')
    recorder = ROOT/'logs/context-feedback/recorder-root/scripts/record-command.sh'
    c.require(command[marker+1:marker+3] == [str(recorder), identity] and command[marker+3:] == expected
              and recorder.resolve() == ROOT/'scripts/record-command.sh', 'Qualification outer launch differs')
    unit = 'context-'+identity+'.service'
    required = {'--unit='+unit, '--working-directory='+str(ROOT), '--property=Type=exec',
                '--property=ExitType=cgroup', '--property=KillMode=control-group', '--property=RuntimeMaxSec=290s',
                '--property=TimeoutStopSec=1s', '--property=CPUQuota=200%', '--property=MemoryMax=4294967296',
                '--property=MemorySwapMax=0', '--property=LimitAS=8589934592'}
    c.require(required <= set(command[:marker]) and start['caps'] == dict(wall_seconds=300, cpu=2,
              memory=4*1024**3, address_space=8*1024**3, swap=0, maximum_output_bytes=100*1024**2),
              'Qualification outer limits differ')
    terminal = c.read(outer/'terminal.json')
    proof = terminal['proof']
    group = '/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit
    c.require(terminal['error'] is None and terminal['exit'] == 0
              and proof['properties']['Result'] == 'success' and proof['properties']['ActiveState'] == 'inactive'
              and proof['argv'] == ['systemctl', '--user', 'show', unit, '--property='+','.join(w.supervisor.PROPERTIES)]
              and w.supervisor.terminal(proof, group), 'Successful outer qualification tree required')
    c.require(c.read(outer/'cleanup.json')['terminal'] is True, 'Qualification launcher group is not terminal')
    raw_directory = Path((outer/'stdout').read_text().strip())
    c.require(raw_directory.parent == ROOT/'logs/context-feedback/recorder-root/logs'
              and re.fullmatch(r'\d{8}T\d{6}Z-'+re.escape(identity)+r'-[A-Za-z0-9]{6}', raw_directory.name) is not None,
              'Qualification outer recorder location differs')
    raw = raw_receipt(raw_directory, expected)
    completion = c.pin(directory/'complete.json')
    c.require(c.read(raw['stdout']['path']) == dict(completion=completion),
              'Qualification completion is not bound to outer raw stdout')
    seal = c.read(completion['path'])
    c.require(set(seal) == {'schema', 'complete', 'phase', 'sources', 'stages', 'completion', 'files', 'biological_qualification'}
              and seal['schema'] == 'context-support-unit/1' and seal['complete'] is True
              and seal['phase'] == phase and seal['completion'] is None and seal['biological_qualification'] is False,
              'Qualification completion fields differ')
    return seal, dict(completion=completion, raw=raw,
                      outer=[c.pin(outer/name) for name in ('start.json', 'terminal.json', 'cleanup.json', 'stdout', 'stderr')])


def qualification(identity, pins):
    seal, observed = outer_receipt(identity, 'qualify')
    directory = ROOT/'results/context-feedback'/identity
    exact_pins(seal['sources'], pins, 'Qualification source census differs')
    exact_pins(seal['files'], [c.pin(directory/'start.json')], 'Qualification file census differs')
    worker_start = c.read(directory/'start.json')
    c.require(worker_start['phase'] == 'qualify' and worker_start['sources'] == pins
              and worker_start['grant']['id'] == identity, 'Qualification worker start differs')
    c.require(len(seal['stages']) == 1, 'Qualification test stage census differs')
    stage = w.evidence.stage(seal['stages'][0], c)
    c.require(stage['name'] == 'support-python-controls' and stage['argv'] == TEST_ARGV
              and stage['admission_id'] == identity, 'Qualification test command differs')
    text = Path(stage['raw']['stderr']['path']).read_text()
    c.require('Ran 20 tests' in text and 'skipped' not in text.lower() and text.count(' ... ok\n') == 20,
              'Exactly20 controls skipped0 required')
    return dict(observed, sources=pins, stage=seal['stages'][0])


def reuse_ready(identity, qualification_id, pins, qualified):
    seal, observed = outer_receipt(identity, 'reuse-controls', qualification_id)
    directory = ROOT/'results/context-feedback'/identity
    exact_pins(seal['sources'], pins, 'Reuse control source census differs')
    exact_pins(seal['files'], [c.pin(directory/'start.json'), c.pin(directory/'reuse-controls.json')],
               'Reuse control file census differs')
    start = c.read(directory/'start.json')
    c.require(start['phase'] == 'reuse-controls' and start['sources'] == pins
              and start['grant']['id'] == identity and seal['stages'] == [], 'Reuse control stage/start differs')
    result = c.read(directory/'reuse-controls.json')
    c.require(result['positive_handoff'] is True and result['readonly_observation_injections'] is True
              and result['requests_started'] is False and result['qualification'] == qualified
              and len(result['negative_controls']) == len(NEGATIVE_NAMES)
              and set(result['negative_controls']) == NEGATIVE_NAMES
              and set(result['rejections']) == NEGATIVE_NAMES, 'Successful reuse controls required before HTTP')
    return dict(observed, result=c.pin(directory/'reuse-controls.json'))


def reuse_controls(identity, pins):
    observed = qualification(identity, pins)
    completion_path = Path(observed['completion']['path'])
    original_read = c.read
    mutations = [('empty_sources', 'sources', [], 'Qualification source census differs'),
                 ('empty_stages', 'stages', [], 'Qualification test stage census differs'),
                 ('empty_files', 'files', [], 'Qualification file census differs'),
                 ('wrong_phase', 'phase', 'reuse-controls', 'Qualification completion fields differ')]
    passed = []
    rejections = {}
    for name, key, value, expected in mutations:
        def altered(path):
            result = original_read(path)
            if Path(path) == completion_path:
                result = deepcopy(result)
                result[key] = value
            return result
        with mock.patch.object(c, 'read', side_effect=altered):
            try:
                qualification(identity, pins)
            except ValueError as error:
                c.require(str(error) == expected, 'Unexpected reuse control rejection: '+name)
                rejections[name] = str(error)
                passed.append(name)
            else:
                raise ValueError('Reuse control was accepted: '+name)
    stage = original_read(observed['stage']['path'])
    missing = [('missing_outer_raw_stdout', Path(observed['raw']['stdout']['path'])),
               ('missing_inner_stage', Path(observed['stage']['path'])),
               ('missing_inner_raw_stderr', Path(stage['raw']['stderr']['path'])),
               ('missing_launcher_cleanup', Path(observed['outer'][2]['path']))]
    original_open = Path.open
    for name, target in missing:
        def opened(path, *args, **kwargs):
            if path == target:
                raise FileNotFoundError(str(path))
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', opened):
            try:
                qualification(identity, pins)
            except FileNotFoundError as error:
                c.require(str(target) in str(error), 'Unexpected missing-file rejection: '+name)
                rejections[name] = str(error)
                passed.append(name)
            else:
                raise ValueError('Reuse control was accepted: '+name)
    def corrupt(path):
        value = original_read(path)
        if Path(path) == Path(observed['raw']['stdout']['path']):
            value = dict(completion=dict(observed['completion'], sha256='0'*64))
        return value
    with mock.patch.object(c, 'read', side_effect=corrupt):
        try:
            qualification(identity, pins)
        except ValueError as error:
            c.require(str(error) == 'Qualification completion is not bound to outer raw stdout',
                      'Unexpected corrupt-completion rejection')
            rejections['corrupt_outer_completion_pin'] = str(error)
            passed.append('corrupt_outer_completion_pin')
        else:
            raise ValueError('Corrupt qualification completion pin was accepted')
    return dict(positive_handoff=True, negative_controls=passed, rejections=rejections,
                readonly_observation_injections=True, qualification=observed, requests_started=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('qualify', 'reuse-controls', 'inspect'))
    parser.add_argument('identity')
    parser.add_argument('--qualification', default='support-engineering-1')
    parser.add_argument('--reuse-controls', default='support-reuse-controls-1')
    args = parser.parse_args()
    c.require(Path.cwd().resolve() == ROOT and re.fullmatch('[a-zA-Z0-9_-]+', args.identity) is not None,
              'Bad worker cwd/identity')
    out = ROOT/'results/context-feedback'/args.identity
    out.mkdir()
    now = datetime.now(timezone.utc)
    pins = source_pins()
    grant = dict(id=args.identity, maximum_wall_seconds=280,
                 expires_utc=(now+timedelta(seconds=280)).isoformat(),
                 maximum_output_bytes=int(os.environ['CONTEXT_UNIT_MAX_OUTPUT']))
    c.fresh(out/'start.json', dict(sources=pins, phase=args.phase, grant=grant))
    execution = w.Execution(grant, out, pins)
    files = [c.pin(out/'start.json')]
    completion = None
    if args.phase == 'qualify':
        stage = execution.stage('support-python-controls', TEST_ARGV)
        text = Path(stage['raw']['stderr']['path']).read_text()
        c.require('Ran 20 tests' in text and 'skipped' not in text.lower() and text.count(' ... ok\n') == 20,
                  'Exactly20 controls skipped0 required')
    elif args.phase == 'reuse-controls':
        result = reuse_controls(args.qualification, pins)
        c.fresh(out/'reuse-controls.json', result)
        files.append(c.pin(out/'reuse-controls.json'))
    else:
        proof = qualification(args.qualification, pins)
        controls = reuse_ready(args.reuse_controls, args.qualification, pins, proof)
        c.fresh(out/'qualification.json', dict(qualification=proof, reuse_controls=controls))
        files.append(c.pin(out/'qualification.json'))
        samtools = c.pin('/usr/bin/samtools')
        c.require(samtools['sha256'] == 'e839773cc27090fa109588cae8b8240b0d48de816a25b962045867a4c3b7e1ff',
                  'Pinned samtools differs')
        stage = execution.stage('support-inspect', ['uv', 'run', '--no-sync', 'python',
            'tools/support_context/transport.py', 'inspect', '--output', 'results/support-context/paw71238-inspect-1',
            '--maximum-network-bytes', '8388608', '--samtools', samtools['path'], '--samtools-sha256', samtools['sha256']])
        completion = c.read(stage['raw']['stdout']['path'])['completion']
        c.check(completion)
        native = c.read(completion['path'])
        c.require(native['complete'] is True and native['reads_decoded'] is False, 'Support inspection scope differs')
        for item in native['files']:
            c.check(item)
    for item in execution.receipts:
        w.evidence.stage(item, c)
    execution.budget()
    c.fresh(out/'complete.json', dict(schema='context-support-unit/1', complete=True, phase=args.phase,
            sources=pins, stages=execution.receipts, completion=completion, files=files, biological_qualification=False))
    print(json.dumps(dict(completion=c.pin(out/'complete.json'))))


if __name__ == '__main__':
    main()
