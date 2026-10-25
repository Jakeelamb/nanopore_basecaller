"""Bound two explicit metadata continuations; never impersonate source63 units."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
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

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
HERE = Path(__file__).resolve().parent
CONFIG = ROOT/'config/context-sample-feedback-v1.json'
spec = importlib.util.spec_from_file_location('sample_compiled_63_cli', ROOT/'scripts/context-sample-feedback.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
b, c, w = base.b, base.c, base.w
spec = importlib.util.spec_from_file_location('sample_decision_reuse_core', HERE/'core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
CAPS = dict(maximum_wall_seconds=300, maximum_output_bytes=4294967296,
            maximum_growth_bytes=104857600, memory_bytes=4294967296,
            address_space_bytes=8589934592, swap_bytes=0, cpu_quota=2)


def sources():
    paths = [HERE/name for name in ('run.py', 'core.py', 'plan.json', 'test_core.py')]
    plan = c.read(HERE/'plan.json')
    paths += [Path(value['path']) for value in plan['partial_trace']['files']]
    paths.append(Path(plan['partial_ready']['path']))
    return [c.pin(path) for path in sorted(set(paths))]


def identity(pins):
    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def grant(args, verify=True):
    value = c.read(args.admission)
    required = {'schema', 'id', 'phase', 'scope', 'config', 'sources_sha256', 'compiled_sources_sha256',
                'output', 'qualification', 'inputs', 'not_before_utc', 'expires_utc',
                'maximum_wall_seconds', 'maximum_output_bytes', 'maximum_growth_bytes', 'memory_bytes',
                'address_space_bytes', 'swap_bytes', 'cpu_quota', 'cgroup', 'case_id', 'source_audit', 'arm', 'recovery'}
    c.require(set(value) == required and value['schema'] == 'context-sample-feedback-continuation-admission/1', 'Continuation grant schema differs')
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['id']) is not None, 'Unsafe continuation identity')
    c.require(value['phase'] == args.phase and value['scope'] == args.scope == 'all'
              and value['case_id'] is value['source_audit'] is value['arm'] is value['recovery'] is None
              and value['output'] == str(args.output.resolve()), 'Continuation phase/scope/output differs')
    c.require(value['compiled_sources_sha256'] == core.SAMPLE_SOURCE, 'Original compiled source differs')
    now = datetime.now(timezone.utc)
    start, end = (datetime.fromisoformat(value[key]) for key in ('not_before_utc', 'expires_utc'))
    c.require(start <= now < end and 5 < (end-now).total_seconds() <= 300 and 0 < (end-start).total_seconds() <= 300, 'Expired/unbounded continuation grant')
    c.require(all(0 < value[key] <= maximum for key, maximum in CAPS.items() if key != 'swap_bytes') and value['swap_bytes'] == 0, 'Continuation caps differ')
    c.require(value['cgroup'] == '/user.slice/user-1000.slice/user@1000.service/app.slice/context-sample-feedback-'+value['id']+'.service', 'Continuation cgroup differs')
    c.require(args.output.resolve().is_relative_to(w.RESULTS) and args.output.resolve() != w.RESULTS, 'Continuation output outside owned results')
    if verify:
        plan = c.read(HERE/'plan.json')
        c.require(value['sources_sha256'] == identity(sources()) and base.identity(base.sources()) == core.SAMPLE_SOURCE, 'New orchestration or original compiled sources changed')
        c.require(value['config'] == c.pin(args.config) and value['qualification'] == c.pin(args.qualification/'execution-complete.json')
                  and value['inputs'] == [c.pin(path/'execution-complete.json') for path in args.input], 'Continuation exact inputs differ')
        c.require(value['config'] == plan['configuration'] and value['qualification'] == plan['qualification'], 'Frozen configuration/qualification differs')
        expected = [str(Path(pin['path']).parent) for pin in plan['reuse_inputs']] if args.phase == 'reuse-population' else plan['report_input_paths']
        c.require([str(path.resolve()) for path in args.input] == expected, 'Fixed continuation input paths differ')
    return value


def completed_own(directory, phase):
    directory = Path(directory).resolve()
    outer = c.read(directory/'execution-complete.json')
    c.require(outer['schema'] == 'context-sample-feedback-continuation-execution/1' and outer['complete'] and outer['phase'] == phase and outer['whole_worker_cgroup_terminal'], 'Typed continuation outer differs')
    for value in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]:
        c.check(value)
    terminal = c.read(outer['terminal']['path'])
    c.require(terminal['exit'] == 0 and terminal['error'] is None and terminal['owned_cgroup_terminal'] and terminal['canonical_lock_retained'], 'Typed continuation failed')
    properties = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    c.require(properties.get('MainPID', '0') == properties.get('ControlPID', '0') == '0' and properties['Result'] == 'success' and properties['ActiveState'] == 'inactive', 'Typed continuation worker not terminal')
    launcher = next(value for value in outer['files'] if value['path'].endswith('/launcher-cleanup.json'))
    c.require(c.read(launcher['path'])['terminal'], 'Typed continuation launcher not terminal')
    intake = c.read(outer['worker_intake']['path'])
    c.require(intake['verified'] and intake['parent_lock_retained'], 'Typed intake differs')
    c.check(intake['admission'])
    admission = c.read(intake['admission']['path'])
    plan = c.read(HERE/'plan.json')
    c.require(admission['schema'] == 'context-sample-feedback-continuation-admission/1' and admission['sources_sha256'] == identity(sources()) and admission['compiled_sources_sha256'] == core.SAMPLE_SOURCE and admission['phase'] == phase and admission['scope'] == 'all' and admission['output'] == str(directory)
              and admission['config'] == plan['configuration'] and admission['qualification'] == plan['qualification'], 'Typed admission lineage differs')
    worker_value = c.read(outer['worker']['path'])
    c.require(worker_value['schema'] == 'context-sample-feedback-continuation-unit/1' and worker_value['complete'] and worker_value['phase'] == phase and worker_value['scope'] == 'all' and worker_value['sources_sha256'] == identity(sources()) and worker_value['compiled_sources_sha256'] == core.SAMPLE_SOURCE and worker_value['inputs'] == admission['inputs'] and worker_value['qualification'] == admission['qualification'], 'Typed worker lineage differs')
    for value in worker_value['files']:
        c.check(value)
    summary = c.read(directory/'summary.json')
    c.require(summary['schema'] == 'context-sample-feedback-continuation-summary/1' and summary['phase'] == phase
              and summary['scope'] == 'all' and summary['compiled_sources_sha256'] == core.SAMPLE_SOURCE
              and summary['orchestration_sources_sha256'] == identity(sources()) and summary['native_producers_launched'] == 0,
              'Typed summary scope/source differs')
    for stage in summary['stages']:
        w.evidence.stage(stage, c)
    if phase == 'reuse-population':
        c.require(summary['reuse']['kind'] == 'decision-population-reuse' and summary['reuse']['new_scientific_producers'] == 0
                  and summary['reuse']['decision_measurement_source'] == core.DECISION_SOURCE
                  and summary['reuse']['decision_emission_compiled_source'] == core.DECISION_EMISSION_SOURCE
                  and summary['reuse']['sample_compiled_source'] == core.SAMPLE_SOURCE, 'Typed reuse lineage differs')
        for key in ('mapping', 'measurement', 'partial_trace'):
            c.check(summary['reuse'][key])
    return summary


def worker(args):
    value = grant(args)
    w.pg.adopt_orphans()
    w.supervisor.worker_intake(args.worker_intake, value, c)
    w.cgroup_limits(value)
    b.completed(args.qualification, 'qualify')
    output = args.output.resolve()
    output.mkdir()
    pinned = sources()
    compiled = base.sources()
    c.fresh(output/'start.json', dict(phase=args.phase, scope='all', grant=c.pin(args.admission), orchestration_sources=pinned, compiled_sources=compiled))
    execution = base.Execution(value, output, pinned+compiled)
    summary = dict(schema='context-sample-feedback-continuation-summary/1', phase=args.phase, scope='all', compiled_sources_sha256=core.SAMPLE_SOURCE, orchestration_sources_sha256=identity(pinned), native_producers_launched=0)
    if args.phase == 'reuse-population':
        controls = execution.stage('continuation-source-controls', ['uv', 'run', '--no-sync', 'python', str(HERE/'test_core.py')])
        b.unittest_counts(Path(controls['raw']['stderr']['path']).read_text(), 28)
        summary['reuse'] = core.qualify_reuse(args.input, output, execution)
    else:
        plan = c.read(HERE/'plan.json')
        summary['report'] = core.report(args.input, output, dict(emission=plan['emission'], configuration=b.configuration(args.config)), completed_own)
    execution.budget()
    summary['stages'] = execution.receipts
    c.fresh(output/'summary.json', summary)
    files = [c.pin(path) for path in sorted(output.iterdir()) if path.is_file()]
    c.fresh(output/'complete.json', dict(schema='context-sample-feedback-continuation-unit/1', complete=True,
        phase=args.phase, scope='all', sources_sha256=identity(pinned), compiled_sources_sha256=core.SAMPLE_SOURCE,
        files=files, qualification=value['qualification'], inputs=value['inputs']))
    print(json.dumps(dict(completion=c.pin(output/'complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('reuse-population', 'report'))
    parser.add_argument('--scope', choices=('all',), default='all')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--input', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--worker-intake', type=Path)
    parser.set_defaults(case_id=None, source_audit=None, arm=None, recovery=None)
    args = parser.parse_args()
    if args.worker_intake is None:
        supervise(args)
    else:
        worker(args)


def supervise(args):
    value = grant(args, verify=False)
    end = datetime.fromisoformat(value['expires_utc'])
    directory = w.LOGS/('continuation-supervisor-'+value['id'])
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
        c.fresh(args.output/'execution-complete.json', dict(schema='context-sample-feedback-continuation-execution/1', complete=True,
                phase=args.phase, worker=result, worker_intake=c.pin(directory/'worker-intake.json'),
                terminal=c.pin(directory/'terminal.json'), files=files, whole_worker_cgroup_terminal=True))
        print(json.dumps(dict(completion=c.pin(args.output/'execution-complete.json'))))


if __name__ == '__main__':
    main()
