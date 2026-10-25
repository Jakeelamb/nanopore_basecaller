"""Run only the separately pinned retained-union diagnostic units."""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision')
spec = importlib.util.spec_from_file_location('union_controller_boundary', ROOT/'tools/context_decision/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
c, w = b.c, b.w
OWNED = ROOT/'tools/context_decision_union'
SELF = Path(__file__).resolve()
FROZEN = ROOT/'logs/context-decision/source-ready/post-format-sources.json'
FROZEN_ID = '6357128e0c6c5151001866a1f8e1fe1603807747ed38cd39919c29a42017c6ff'
PHASES = ('format', 'qualify', 'diagnose')
ENV = dict(UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv',
           UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1')


def source_pins():
    frozen = c.read(FROZEN)
    c.require(b.identity(frozen) == FROZEN_ID and len(frozen) == 52, 'Frozen decision identity differs')
    for pin in frozen:
        c.check(pin)
    paths = [(OWNED/name).resolve(strict=True) for name in c.read(OWNED/'source-files.json')]
    c.require(len(paths) == len(set(paths)) and all(path.is_relative_to(OWNED) for path in paths),
              'Union owned census differs')
    cpp = {path for path in OWNED.rglob('*') if path.suffix in ('.cpp', '.h')}
    c.require(cpp == {path for path in paths if path.suffix in ('.cpp', '.h')}, 'Union C++ census incomplete')
    return [c.pin(path) for path in sorted({Path(pin['path']) for pin in frozen} | set(paths) | {SELF, FROZEN})]


def owned_bytes():
    total = 0
    for base in (ROOT/'results', ROOT/'logs'):
        for path in base.rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():
                    total += path.stat().st_size
            except FileNotFoundError:
                pass
    return total


def budget(value, initial):
    size = owned_bytes()
    c.require(size <= value['maximum_output_bytes'] and size-initial <= value['maximum_growth_bytes'],
              'Union cumulative output or growth limit reached')
    c.require(shutil.disk_usage(ROOT).free >= value['disk_floor_bytes'], 'Union disk floor reached')
    return dict(owned_bytes=size, growth_bytes=size-initial, free_bytes=shutil.disk_usage(ROOT).free)


def grant(args):
    value = c.read(args.admission)
    c.require(value['schema'] == 'context-decision-union-admission/1'
              and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['id']) is not None,
              'Union admission identity differs')
    c.require(value['phase'] == args.phase and value['sources_sha256'] == b.identity(source_pins())
              and value['output'] == str(args.output.resolve())
              and value['qualification'] == (None if args.qualification is None else c.pin(args.qualification/'execution-complete.json')),
              'Union source/output/phase/qualification admission differs')
    now = datetime.now(timezone.utc)
    start, end = (datetime.fromisoformat(value[key]) for key in ('not_before_utc', 'expires_utc'))
    c.require(start <= now < end and 0 < (end-start).total_seconds() <= 300
              and 5 < (end-now).total_seconds() <= 300 and value['maximum_wall_seconds'] == 300,
              'Union admission expired or unbounded')
    expected = dict(cpu_quota=2, memory_bytes=4*1024**3, address_space_bytes=8*1024**3, swap_bytes=0,
                    maximum_output_bytes=4*1024**3, maximum_growth_bytes=100*1024**2,
                    disk_floor_bytes=30*1024**3)
    c.require(all(value[key] == item for key, item in expected.items()), 'Union resource envelope differs')
    unit = 'context-decision-union-'+value['id']+'.service'
    c.require(value['cgroup'] == '/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit,
              'Union admitted cgroup differs')
    c.require(args.output.resolve().is_relative_to(w.RESULTS) and args.output.resolve() != w.RESULTS,
              'Union output outside owned results')
    c.require(all(os.environ.get(key) == item for key, item in ENV.items()), 'Union Python environment differs')
    return value


def actual_formatter(output, expected):
    entries = {}
    for line in (output/'build/CMakeCache.txt').read_text().splitlines():
        for key in ('UNION_CLANG_FORMAT', 'STUDY_CLANG_FORMAT'):
            if re.match(r'^'+key+r':(?:FILEPATH|STRING)=', line):
                c.require(key not in entries, 'Duplicate actual formatter cache entry')
                entries[key] = line.split('=', 1)[1]
    c.require(set(entries) == {'UNION_CLANG_FORMAT', 'STUDY_CLANG_FORMAT'}
              and all(path == expected['path'] and c.pin(path) == expected for path in entries.values()),
              'Actual union/study CMake formatter differs from configured exact pin')
    return entries


def native(target, stage, compiled, toolchain):
    completion = c.read(stage['raw']['stdout']['path'])['completion']
    c.check(completion)
    c.require(completion['path'] == str(target/'complete.json'), 'Union native completion path differs')
    value = c.read(completion['path'])
    c.require(value['schema'] == 'context-decision-union-complete/1' and value['complete'] is True,
              'Union native completion schema differs')
    for pin in [value['attempt'], value['result'], *value['inputs'], *value['files']]:
        c.check(pin)
    attempt = c.read(value['attempt']['path'])
    c.require(attempt['argv'] == stage['argv'] and attempt['binary'] == c.pin(stage['argv'][0])
              and attempt['source'] == value['source'] and value['source']['compiled_sources'] == compiled,
              'Union native command, binary, or source closure differs')
    for role in ('compiler', 'formatter'):
        expected = toolchain[role]
        c.require(value['source'][role+'_path'] == expected['path']
                  and value['source'][role+'_sha256'] == expected['sha256']
                  and c.pin(value['source'][role+'_path']) == expected,
                  'Actual native union '+role+' witness differs from configured exact pin')
    return completion


def compiled_pins():
    paths = set()
    for root in (OWNED, b.STUDY):
        paths.update((root/name).resolve(strict=True) for name in c.read(root/'source-files.json'))
    return [c.pin(path) for path in sorted(paths)]


def completed(path, phase):
    value = c.read(path/'execution-complete.json')
    c.require(value['schema'] == 'context-decision-union-execution/1' and value['complete'] is True
              and value['phase'] == phase and value['whole_worker_cgroup_terminal'] is True,
              'Union outer completion differs')
    for pin in [value['worker'], value['terminal'], *value['files']]:
        c.check(pin)
    terminal = c.read(value['terminal']['path'])
    c.require(terminal['exit'] == 0 and terminal['error'] is None and terminal['launcher_terminal'] is True
              and terminal['whole_worker_cgroup_terminal'] is True, 'Union terminal evidence differs')
    worker = c.read(value['worker']['path'])
    c.require(worker['schema'] == 'context-decision-union-unit/1' and worker['phase'] == phase
              and worker['complete'] is True and worker['sources_sha256'] == b.identity(source_pins()),
              'Union worker source identity differs')
    for pin in worker['files']:
        c.check(pin)
    summary = c.read(path/'summary.json')
    for stage in summary['stages']:
        w.evidence.stage(stage, c)
    if phase == 'qualify':
        c.check(summary['binary'])
        actual_formatter(path, b.configuration(ROOT/'config/context-decision-v1.json')['toolchain']['formatter'])
        closure = c.read(path/'build-closure.json')
        for pin in [closure['compiler'], closure['formatter'], closure['cache'], closure['compile_commands'],
                    *closure['runtime_libraries']]:
            c.check(pin)
    return summary


def worker(args):
    value = grant(args)
    w.pg.adopt_orphans()
    w.supervisor.worker_intake(args.worker_intake, value, c)
    w.cgroup_limits(value)
    output = args.output.resolve()
    output.mkdir()
    initial = c.read(args.worker_intake)['initial_bytes']
    pins = source_pins()
    stable = [pin for pin in pins if args.phase != 'format' or not (Path(pin['path']).is_relative_to(OWNED)
              and Path(pin['path']).suffix in ('.cpp', '.h'))]

    class Execution(w.Execution):
        def budget(self):
            super().budget()
            budget(value, initial)

    execution = Execution(value, output, stable)
    config = b.configuration(ROOT/'config/context-decision-v1.json')
    summary = dict(phase=args.phase, source_before=pins, native=[])
    if args.phase == 'format':
        cpp = [pin['path'] for pin in compiled_pins() if Path(pin['path']).is_relative_to(OWNED)
               and Path(pin['path']).suffix in ('.cpp', '.h')]
        execution.stage('union-format', [config['toolchain']['formatter']['path'], '-i', *cpp])
        execution.stage('union-format-check', [config['toolchain']['formatter']['path'], '--dry-run', '--Werror', *cpp])
    elif args.phase == 'qualify':
        execution.stage('union-cmake-configure', ['cmake', '-S', OWNED, '-B', output/'build',
                        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=ON',
                        '-DCMAKE_CXX_COMPILER='+config['toolchain']['compiler']['path'],
                        '-DUNION_CLANG_FORMAT:FILEPATH='+config['toolchain']['formatter']['path'],
                        '-DSTUDY_CLANG_FORMAT:FILEPATH='+config['toolchain']['formatter']['path']])
        summary['actual_formatter_cache'] = actual_formatter(output, config['toolchain']['formatter'])
        execution.stage('union-cmake-build', ['cmake', '--build', output/'build', '--parallel', '2'])
        execution.stage('union-format-check', ['cmake', '--build', output/'build', '--target', 'format-check'])
        execution.stage('union-ctest', ['ctest', '--test-dir', output/'build', '--output-on-failure',
                        '--parallel', '1', '--output-junit', output/'ctest.xml'])
        tests = list(ET.parse(output/'ctest.xml').getroot().iter('testcase'))
        c.require(len(tests) == 1 and tests[0].get('name') == 'retained_union_controls'
                  and not any(tests[0].find(name) is not None for name in ('failure', 'error', 'skipped')),
                  'Union structured CTest controls did not all pass')
        binary = c.pin(output/'build/context-decision-union')
        stage = execution.stage('union-native-controls', [binary['path'], 'qualify', '--output', output/'native-controls'])
        summary['native'].append(native(output/'native-controls', stage, compiled_pins(), config['toolchain']))
        b.build_closure(output, execution, binary, config)
        summary['binary'] = binary
    else:
        c.require(args.qualification is not None, 'Qualified union binary required')
        prior = completed(args.qualification.resolve(), 'qualify')
        _, producer, packet = b.qualified_packet(config)
        summary.update(binary=prior['binary'], qualified_packet=producer['outer'])
        target = output/'native-diagnostic'
        stage = execution.stage('union-diagnose', [prior['binary']['path'], 'diagnose', '--cases', packet['path'],
                        '--cases-sha256', packet['sha256'], '--output', target])
        summary['native'].append(native(target, stage, compiled_pins(), config['toolchain']))
    for stage in execution.receipts:
        w.evidence.stage(stage, c)
    w.cgroup_limits(value)
    execution.budget()
    summary.update(source_after=source_pins(), stages=execution.receipts, final_budget=budget(value, initial))
    c.fresh(output/'summary.json', summary)
    files = [c.pin(path) for path in sorted(output.iterdir()) if path.is_file()]
    c.fresh(output/'complete.json', dict(schema='context-decision-union-unit/1', complete=True, phase=args.phase,
            sources_sha256=b.identity(source_pins()), files=files, admission=c.pin(args.admission)))
    execution.budget()
    return c.pin(output/'complete.json')


def supervise(args):
    value = grant(args)
    directory = ROOT/'logs/context-decision/program'/('union-'+value['id'])
    directory.mkdir()
    unit = 'context-decision-union-'+value['id']+'.service'
    description = 'Union diagnostic '+uuid.uuid4().hex
    end = datetime.fromisoformat(value['expires_utc'])
    deadline = min(time.monotonic()+300, time.monotonic()+(end-datetime.now(timezone.utc)).total_seconds())
    w.pg.adopt_orphans()
    with w.LOCK.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            c.fresh(directory/'refused.json', dict(reason='canonical lock held', utc=w.supervisor.utc()))
            raise
        preflight = w.supervisor.show(unit)
        c.require(preflight['properties'].get('LoadState') == 'not-found', 'Union service name already exists')
        initial = owned_bytes()
        c.fresh(directory/'intake.json', dict(grant_id=value['id'], admission=str(args.admission.resolve()),
                parent_pid=os.getpid(), parent_start=w.supervisor.process_start(os.getpid()), lock_fd=lock.fileno(),
                unit=unit, description=description, initial_bytes=initial))
        remaining = deadline-time.monotonic()-3
        c.require(remaining > 1, 'No bounded union interval remains')
        argv = ['systemd-run', '--user', '--wait', '--pipe', '--unit='+unit, '--description='+description,
            '--working-directory='+str(ROOT), '--property=Type=exec', '--property=ExitType=cgroup',
            '--property=KillMode=control-group', '--property=Slice=app.slice', '--property=CollectMode=inactive',
            '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL', '--property=TimeoutStopSec=1s',
            '--property=RuntimeMaxSec='+str(remaining)+'s', '--property=CPUQuota=200%',
            '--property=MemoryMax='+str(value['memory_bytes']), '--property=MemorySwapMax=0',
            '--property=LimitAS='+str(value['address_space_bytes'])]
        argv += ['--setenv='+key+'='+item for key, item in ENV.items()]
        argv += ['--', shutil.which('uv'), 'run', '--no-sync', 'python', str(SELF), args.phase,
                 '--output', str(args.output.resolve()), '--admission', str(args.admission.resolve()),
                 '--worker-intake', str(directory/'intake.json')]
        if args.qualification is not None:
            argv += ['--qualification', str(args.qualification.resolve())]
        c.fresh(directory/'command.json', dict(argv=argv, cwd=str(ROOT), grant=value, controller=c.pin(SELF),
                utc=w.supervisor.utc(), preflight=preflight, initial_budget=budget(value, initial)))
        process, error, proof, cleanup = None, None, None, None
        started = w.supervisor.utc()
        try:
            with (directory/'stdout').open('xb') as out, (directory/'stderr').open('xb') as err:
                process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    c.require(time.monotonic() < deadline, 'Union outer wall boundary reached')
                    budget(value, initial)
                    time.sleep(.2)
                budget(value, initial)
        except BaseException as caught:
            error = repr(caught)
        finally:
            index = 0
            while proof is None:
                try:
                    state = w.supervisor.show(unit)
                    if state['properties'].get('Description') == description:
                        if w.supervisor.terminal(state, value['cgroup']):
                            proof = state
                            if state['properties'].get('Result') != 'success':
                                error = error or 'Union service failed'
                        else:
                            subprocess.run(['systemctl', '--user', 'stop', '--no-block', unit],
                                           capture_output=True, timeout=3)
                    elif (process is None or process.poll() is not None) and w.supervisor.unloaded_terminal(state, value['cgroup']):
                        proof = state
                except BaseException as caught:
                    index += 1
                    c.fresh(directory/('terminal-error-'+str(index)+'.json'), dict(error=repr(caught), lock_retained=True))
                if proof is None:
                    time.sleep(.2)
            if process is not None:
                while cleanup is None:
                    try:
                        cleanup = w.pg.stop_group(process, process.pid)
                        c.fresh(directory/'launcher-cleanup.json', cleanup)
                    except BaseException as caught:
                        index += 1
                        c.fresh(directory/('launcher-error-'+str(index)+'.json'), dict(error=repr(caught), lock_retained=True))
                        time.sleep(.2)
            try:
                final_budget = budget(value, initial)
                c.require(time.monotonic() <= deadline, 'Union final wall boundary reached')
            except BaseException as caught:
                final_budget = dict(error=repr(caught))
                error = error or repr(caught)
            c.fresh(directory/'terminal.json', dict(started_utc=started, ended_utc=w.supervisor.utc(),
                    exit=None if process is None else process.returncode, error=error, proof=proof,
                    final_budget=final_budget, whole_worker_cgroup_terminal=True,
                    launcher_terminal=cleanup is not None and cleanup['terminal'] is True, canonical_lock_retained=True))
        c.require(error is None and process is not None and process.returncode == 0,
                  'Union execution failed; retained '+str(directory))
        c.require(c.read(directory/'worker-intake.json')['verified'] is True, 'Missing union worker intake')
        completion = c.read(directory/'stdout')['completion']
        c.check(completion)
        c.require(completion['path'] == str(args.output.resolve()/'complete.json'), 'Union worker path differs')
        seal = c.read(completion['path'])
        c.require(seal['complete'] is True and seal['phase'] == args.phase
                  and seal['sources_sha256'] == b.identity(source_pins()), 'Union final source/phase differs')
        for pin in seal['files']:
            c.check(pin)
        summary = c.read(args.output/'summary.json')
        for stage in summary['stages']:
            w.evidence.stage(stage, c)
        files = [c.pin(directory/name) for name in ('command.json', 'intake.json', 'worker-intake.json',
                 'stdout', 'stderr', 'launcher-cleanup.json')]
        c.fresh(args.output/'execution-complete.json', dict(schema='context-decision-union-execution/1',
                complete=True, phase=args.phase, worker=completion, terminal=c.pin(directory/'terminal.json'),
                files=files, whole_worker_cgroup_terminal=True))
        print(json.dumps(dict(completion=c.pin(args.output/'execution-complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=(*PHASES, 'source-inventory'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--worker-intake', type=Path)
    args = parser.parse_args()
    if args.phase == 'source-inventory':
        pins = source_pins()
        print(json.dumps(dict(sources=pins, sources_sha256=b.identity(pins), compiled_sources=compiled_pins())))
        return
    c.require(args.output is not None and args.admission is not None, 'Explicit union admission/output required')
    if args.worker_intake is None:
        supervise(args)
    else:
        print(json.dumps(dict(completion=worker(args))))


if __name__ == '__main__':
    main()
