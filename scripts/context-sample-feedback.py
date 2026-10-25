#!/usr/bin/env python3
"""Run admitted CPU units for the separate feasible-candidate sample experiment."""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_sample_feedback_boundary', ROOT/'tools/context_sample_feedback/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
c, w = b.c, b.w
CONFIG = ROOT/'config/context-sample-feedback-v1.json'
PHASES = ('format', 'qualify', 'prepare', 'price', 'infer', 'recover', 'checkpoint', 'emit', 'observe', 'map', 'measure', 'report')
sources, identity, native = b.sources, b.identity, b.native


def grant(args, verify=True):
    value = c.read(args.admission)
    required = {'schema', 'id', 'phase', 'scope', 'config', 'sources_sha256', 'output', 'qualification',
                'inputs', 'not_before_utc', 'expires_utc', 'maximum_wall_seconds', 'maximum_output_bytes',
                'maximum_growth_bytes', 'memory_bytes', 'address_space_bytes', 'swap_bytes', 'cpu_quota', 'cgroup',
                'case_id', 'source_audit', 'arm', 'recovery'}
    c.require(set(value) == required and value['schema'] == 'context-sample-feedback-admission/1', 'Sample grant schema differs')
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['id']) is not None, 'Unsafe sample identity')
    c.require(value['phase'] == args.phase and value['scope'] == args.scope and value['case_id'] == args.case_id
              and value['arm'] == args.arm
              and value['output'] == str(args.output.resolve()), 'Sample phase/case/output grant differs')
    if verify:
        c.require(value['source_audit'] == (None if args.source_audit is None else c.pin(args.source_audit))
                  and value['recovery'] == (None if args.recovery is None else c.pin(args.recovery))
                  and value['config'] == c.pin(args.config) and value['sources_sha256'] == identity(sources()),
                  'Sample source/config/audit grant differs')
        c.require(value['qualification'] == (None if args.qualification is None else c.pin(args.qualification.resolve()/'execution-complete.json'))
                  and value['inputs'] == [c.pin(path.resolve()/'execution-complete.json') for path in args.input], 'Sample prerequisite grant differs')
    now = datetime.now(timezone.utc)
    start, end = (datetime.fromisoformat(value[key]) for key in ('not_before_utc', 'expires_utc'))
    c.require(start <= now < end and 5 < (end-now).total_seconds() <= 300
              and 0 < (end-start).total_seconds() <= 300, 'Expired/unbounded sample grant')
    caps = dict(maximum_wall_seconds=300, maximum_output_bytes=4*1024**3, maximum_growth_bytes=100*1024**2,
                memory_bytes=4*1024**3, address_space_bytes=8*1024**3, cpu_quota=2)
    if args.phase == 'map':
        caps.update(maximum_growth_bytes=512*1024**2, memory_bytes=16*1024**3, address_space_bytes=24*1024**3)
    if verify:
        config = b.configuration(args.config)
        expected = dict(config['execution'])
        if args.phase == 'map': expected.update(config['mapper_execution'])
        c.require(caps.items() <= expected.items(), 'Frozen unit caps differ')
    for key in ('maximum_wall_seconds', 'maximum_output_bytes', 'maximum_growth_bytes', 'memory_bytes',
                'address_space_bytes', 'cpu_quota'):
        c.require(0 < value[key] <= caps[key], 'Sample grant exceeds '+key)
    c.require(value['swap_bytes'] == 0 and value['cgroup'] ==
              '/user.slice/user-1000.slice/user@1000.service/app.slice/context-sample-feedback-'+value['id']+'.service',
              'Sample cgroup/swap differs')
    c.require(args.output.resolve().is_relative_to(w.RESULTS) and args.output.resolve() != w.RESULTS,
              'Sample output outside owned results')
    return value


class Execution(w.Execution):
    def __init__(self, value, output, pins):
        super().__init__(value, output, pins)
        self.initial_bytes = w.owned_bytes()

    def budget(self):
        super().budget()
        c.require(w.owned_bytes() - self.initial_bytes <= self.grant['maximum_growth_bytes'],
                  'Sample new-output growth cap reached')


def worker(args):
    value = grant(args)
    w.pg.adopt_orphans()
    w.supervisor.worker_intake(args.worker_intake, value, c)
    w.cgroup_limits(value)
    output = args.output.resolve()
    output.mkdir()
    config, pins = b.configuration(args.config), sources()
    c.fresh(output/'start.json', dict(phase=args.phase, scope=args.scope, grant=c.pin(args.admission),
            config=c.pin(args.config), sources=pins))
    checked = [pin for pin in pins if not pin['path'].endswith(('.cpp', '.h'))] if args.phase == 'format' else pins
    execution = Execution(value, output, checked)
    summary = dict(phase=args.phase, scope=args.scope, case_id=args.case_id, arm=args.arm, native=[])
    if args.phase == 'format':
        cpp = sorted(str(path) for path in b.OWNED.rglob('*') if path.suffix in ('.cpp', '.h'))
        execution.stage('sample-format-only', [config['toolchain']['formatter']['path'], '-i', *cpp])
        execution.stage('sample-format-dry-run', [config['toolchain']['formatter']['path'], '--dry-run', '--Werror', *cpp])
        summary['before_sources'] = pins
        summary['after_sources'] = sources()
    elif args.phase == 'qualify':
        strict = '-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off'
        execution.stage('sample-cmake-configure', ['cmake', '-S', b.OWNED, '-B', output/'build',
            '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=ON', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DCMAKE_CXX_COMPILER='+config['toolchain']['compiler']['path'], '-DCMAKE_CXX_FLAGS='+strict])
        execution.stage('sample-cmake-build', ['cmake', '--build', output/'build', '--parallel', '2'])
        execution.stage('sample-format-check', ['cmake', '--build', output/'build', '--target', 'sample-format-check'])
        execution.stage('sample-ctest', ['ctest', '--test-dir', output/'build', '--output-on-failure',
                        '--parallel', '1', '--output-junit', output/'ctest.xml'])
        b.ctest_counts(output/'ctest.xml')
        binary = c.pin(output/'build/context-sample-feedback')
        stage = execution.stage('sample-native-controls', [binary['path'], 'qualify', '--output', output/'native-controls'])
        summary['native'].append(native(output/'native-controls', stage, pins))
        result = execution.stage('sample-python-controls', ['uv', 'run', '--no-sync', 'python', '-m', 'unittest',
            'test_context_sample_feedback', '-v'], env=dict(PYTHONPATH=str(ROOT/'tests'), CONTEXT_SAMPLE_FEEDBACK_BINARY=binary['path']))
        b.unittest_counts(Path(result['raw']['stderr']['path']).read_text(), 24)
        b.build_closure(output, execution, binary, config)
        summary['binary'] = binary
        summary['observer_binary'] = c.pin(output/'build/context-sample-feedback-observe')
    else:
        c.require(args.qualification is not None, 'Qualified sample binary required')
        qualification = b.completed(args.qualification, 'qualify')
        binary = qualification['binary']
        summary['binary'] = binary
        if args.phase == 'prepare':
            summary['prepared'] = b.prepare(config, output, args.source_audit)
        elif args.phase == 'recover':
            summary = b.recover(args, output, config, qualification, execution)
        elif args.phase in ('price', 'infer'):
            c.require(len(args.input) >= 1 and args.case_id is not None, 'Prepared unit and exact case ID required')
            preparation = b.completed(args.input[0], 'prepare')['prepared']
            for pin in (preparation['frames'], preparation['handshake']): c.check(pin)
            b.check_scope(args.scope, args.case_id)
            if args.phase == 'infer': b.check_prior(args, config)
            target = output/'native-case'
            argv = [binary['path'], args.phase, '--cases', config['packet']['path'], '--cases-sha256', config['packet']['sha256'],
                    '--frames', preparation['frames']['path'], '--frames-sha256', preparation['frames']['sha256'],
                    '--source-cases', config['source_cases']['path'], '--source-cases-sha256', config['source_cases']['sha256'],
                    '--contexts', config['contexts']['path'], '--contexts-sha256', config['contexts']['sha256'],
                    '--handshake', preparation['handshake']['path'], '--handshake-sha256', preparation['handshake']['sha256'],
                    '--case-id', args.case_id, '--allow-exploratory', '1', '--output', target]
            stage = execution.stage('sample-'+args.phase, argv)
            if args.phase == 'infer': b.archive_traces(target)
            summary['native'].append(native(target, stage, pins))
            summary['prepared'] = preparation
        elif args.phase == 'checkpoint':
            summary['checkpoint'] = b.checkpoint(args, output, config)
        elif args.phase == 'emit':
            observer = b.module('context_sample_feedback_observer', b.OWNED/'observe.py')
            summaries = [b.completed(path, 'infer') for path in args.input]
            observer.emit(args.input, summaries, output, config)
        elif args.phase == 'observe':
            c.require(len(args.input) == 1, 'Exactly one complete emission required')
            b.completed(args.input[0], 'emit')
            choices = c.pin(args.input[0]/'all-choices.tsv')
            b.check_pin(config['truth'])
            target = output/'native-observer'
            stage = execution.stage('sample-observer', [qualification['observer_binary']['path'], 'evaluate',
                '--cases', config['packet']['path'], '--cases-sha256', config['packet']['sha256'],
                '--truth', config['truth']['path'], '--truth-sha256', config['truth']['sha256'],
                '--choices', choices['path'], '--choices-sha256', choices['sha256'], '--output', target])
            summary['native'].append(native(target, stage, pins))
        else:
            measure = b.module('sample_measurement', b.OWNED/'measure.py')
            if args.phase == 'map': summary['mapping'] = measure.map_arm(args, output, config, execution)
            elif args.phase == 'measure': summary['measurement'] = measure.measure_arm(args, output, config, execution)
            else: summary['report'] = measure.report(args, output, config)
    execution.budget()
    summary['stages'] = execution.receipts
    c.fresh(output/'summary.json', summary)
    files = [c.pin(path) for path in sorted(output.iterdir()) if path.is_file()]
    c.fresh(output/'complete.json', dict(schema='context-sample-feedback-unit/1', complete=True, phase=args.phase,
            scope=args.scope, sources_sha256=identity(sources()), files=files,
            qualification=value['qualification'], inputs=value['inputs']))
    print(json.dumps(dict(completion=c.pin(output/'complete.json'))))


def supervise(args):
    value = grant(args, verify=False)
    end = datetime.fromisoformat(value['expires_utc'])
    directory = w.LOGS/('sample-supervisor-'+value['id'])
    directory.mkdir(parents=True)
    unit = 'context-sample-feedback-'+value['id']+'.service'
    description = 'Context sample '+uuid.uuid4().hex
    w.pg.adopt_orphans()
    tree_path = w.RESULTS/'sample-tree.lock'
    tree_path.parent.mkdir(parents=True, exist_ok=True)
    with w.LOCK.open('r') as lock, tree_path.open('a+') as tree_lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(tree_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            c.fresh(directory/'refused.json', dict(reason='canonical/tree lock held', grant=value))
            raise
        intake = directory/'intake.json'
        c.fresh(intake, dict(grant_id=value['id'], admission=str(args.admission.resolve()), parent_pid=os.getpid(),
                parent_start=w.supervisor.process_start(os.getpid()), lock_fd=lock.fileno(), unit=unit, description=description))
        remaining = min(value['maximum_wall_seconds'], (end-datetime.now(timezone.utc)).total_seconds())-3
        c.require(remaining > 1, 'No bounded sample interval remains')
        argv = ['systemd-run', '--user', '--wait', '--pipe', '--unit='+unit, '--description='+description,
            '--working-directory='+str(ROOT), '--property=Type=exec', '--property=ExitType=cgroup',
            '--property=KillMode=control-group', '--property=Slice=app.slice', '--property=CollectMode=inactive',
            '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL', '--property=TimeoutStopSec=1s',
            '--property=RuntimeMaxSec='+str(remaining)+'s', '--property=CPUQuota='+str(value['cpu_quota']*100)+'%',
            '--property=MemoryMax='+str(value['memory_bytes']), '--property=MemorySwapMax=0',
            '--property=LimitAS='+str(value['address_space_bytes'])]
        for name in ('UV_PROJECT_ENVIRONMENT', 'UV_OFFLINE', 'UV_PYTHON_DOWNLOADS', 'PYTHONDONTWRITEBYTECODE'):
            argv += ['--setenv='+name+'='+os.environ[name]]
        argv += ['--', shutil.which('uv'), 'run', '--no-sync', 'python', str(Path(__file__).resolve()), args.phase,
                 '--scope', args.scope, '--config', str(args.config.resolve()), '--output', str(args.output.resolve()),
                 '--admission', str(args.admission.resolve()), '--worker-intake', str(intake)]
        if args.case_id is not None:
            argv += ['--case-id', args.case_id]
        if args.source_audit is not None:
            argv += ['--source-audit', str(args.source_audit.resolve())]
        if args.arm is not None:
            argv += ['--arm', args.arm]
        if args.recovery is not None:
            argv += ['--recovery', str(args.recovery.resolve())]
        if args.qualification is not None:
            argv += ['--qualification', str(args.qualification.resolve())]
        for path in args.input:
            argv += ['--input', str(path.resolve())]
        c.fresh(directory/'command.json', dict(argv=argv, grant=value, cwd=str(ROOT), utc=datetime.now(timezone.utc).isoformat()))
        (directory/'command.sh').write_text(shlex.join(argv)+'\n')
        (directory/'cwd.txt').write_text(str(ROOT)+'\n')
        (directory/'start.txt').write_text(datetime.now(timezone.utc).isoformat()+'\n')
        process, error, proof = None, None, None
        initial_bytes = w.owned_bytes()
        try:
            with (directory/'stdout').open('xb') as out, (directory/'stderr').open('xb') as err:
                process = subprocess.Popen(['/usr/bin/time', '-v', '-o', str(directory/'time.txt'), '--', *argv],
                                           cwd=ROOT, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    if (time.time() >= end.timestamp()-1 or w.owned_bytes() > value['maximum_output_bytes']
                        or w.owned_bytes()-initial_bytes > value['maximum_growth_bytes']
                        or shutil.disk_usage(ROOT).free < 30*1024**3):
                        raise ValueError('Sample wall/output/disk boundary reached')
                    time.sleep(.2)
        except BaseException as caught:
            error = repr(caught)
        finally:
            index = 0
            while proof is None:
                try:
                    observed = w.supervisor.show(unit)
                    if observed['properties'].get('Description') == description:
                        if w.supervisor.terminal(observed, value['cgroup']):
                            proof = observed
                            if observed['properties'].get('Result') != 'success':
                                error = error or 'Sample service failed'
                        else:
                            subprocess.run(['systemctl', '--user', 'stop', '--no-block', unit], capture_output=True, timeout=3)
                    elif process is None or (process.poll() is not None and w.supervisor.unloaded_terminal(observed, value['cgroup'])):
                        proof = dict(unloaded_empty_group=observed)
                except BaseException as caught:
                    index += 1
                    c.fresh(directory/('termination-error-'+str(index)+'.json'), dict(error=repr(caught), canonical_lock_retained=True))
                if proof is None:
                    time.sleep(.2)
            if process is not None:
                while True:
                    try:
                        c.fresh(directory/'launcher-cleanup.json', w.pg.stop_group(process, process.pid))
                        break
                    except BaseException as caught:
                        index += 1
                        c.fresh(directory/('launcher-error-'+str(index)+'.json'), dict(error=repr(caught), canonical_lock_retained=True))
                        time.sleep(.2)
            c.fresh(directory/'terminal.json', dict(error=error, exit=None if process is None else process.returncode,
                    utc=datetime.now(timezone.utc).isoformat(), proof=proof, owned_cgroup_terminal=True, canonical_lock_retained=True))
            (directory/'end.txt').write_text(datetime.now(timezone.utc).isoformat()+'\n')
            (directory/'exit-status.txt').write_text(str(None if process is None else process.returncode)+'\n')
        c.require(error is None and process is not None and process.returncode == 0, 'Sample unit failed; retained '+str(directory))
        c.require(c.read(directory/'worker-intake.json')['verified'] is True, 'Missing verified worker intake')
        result = c.read(directory/'stdout')['completion']
        c.check(result)
        c.require(result['path'] == str(args.output.resolve()/'complete.json'), 'Worker completion path differs')
        seal = c.read(result['path'])
        c.require((args.phase == 'format' or seal['sources_sha256'] == value['sources_sha256']) and seal['phase'] == args.phase and seal['complete'] is True,
                  'Sample source/phase completion differs')
        files = [c.pin(directory/name) for name in ('command.json', 'intake.json', 'worker-intake.json',
                 'stdout', 'stderr', 'launcher-cleanup.json', 'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'time.txt')]
        c.fresh(args.output/'execution-complete.json', dict(schema='context-sample-feedback-execution/1', complete=True,
                phase=args.phase, worker=result, worker_intake=c.pin(directory/'worker-intake.json'),
                terminal=c.pin(directory/'terminal.json'), files=files, whole_worker_cgroup_terminal=True))
        print(json.dumps(dict(completion=c.pin(args.output/'execution-complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=PHASES+('source-inventory',))
    parser.add_argument('--scope', choices=('query0', 'first32', 'remaining', 'all'), default='all')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--input', type=Path, action='append', default=[])
    parser.add_argument('--worker-intake', type=Path)
    parser.add_argument('--case-id')
    parser.add_argument('--source-audit', type=Path)
    parser.add_argument('--arm', choices=b.ARMS)
    parser.add_argument('--recovery', type=Path)
    args = parser.parse_args()
    if args.phase == 'source-inventory':
        pins = sources()
        print(json.dumps(dict(sources=pins, sha256=identity(pins))))
    else:
        c.require(args.output is not None and args.admission is not None, 'Explicit fresh CPU admission required')
        if args.worker_intake is None:
            supervise(args)
        else:
            worker(args)


if __name__ == '__main__':
    main()
