"""Bound the unchanged feasible-decision measurement worker as one native unit."""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision')
SELF = Path(__file__).resolve()
WORKER = ROOT/'tools/context_decision/measure.py'
spec = importlib.util.spec_from_file_location('bounded_decision_measure_worker', WORKER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b, c, w = m.b, m.c, m.w
ENV = dict(UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv',
           UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1')
USER_ENV_NAMES = ('HOME', 'USER', 'LOGNAME', 'PATH', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
                  'LD_LIBRARY_PATH', 'LD_PRELOAD', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')
RAW_NAMES = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')
EXPECTED = {
    WORKER: 'c10f8a6c1f61a7a2fb2f4b5c37304ab85fdf1ec28b8cc446d8a13ab554a92414',
    ROOT/'tools/context_decision/tests/test_measure.py': '364ff74978347c78b7d15f016532d2d44edc43f4d64a7fc5a91f741530d5e281',
    m.HELPER: 'e05619d9a04501d7f740daa0cda10f02bb853d122b257743c023575d62366f1c',
}


def source_pins():
    pins = m.source_pins()
    c.require(len(pins) == 55 and b.identity(b.sources()) ==
              '6357128e0c6c5151001866a1f8e1fe1603807747ed38cd39919c29a42017c6ff',
              'Frozen52/measurement55 source census differs')
    for path, expected in EXPECTED.items():
        c.require(c.pin(path)['sha256'] == expected, 'Unchanged measurement source differs '+str(path))
    return pins


def recorder():
    path = ROOT/'logs/context-feedback/recorder-root/scripts/record-command.sh'
    c.require(path.is_file() and path.resolve() == ROOT/'scripts/record-command.sh',
              'Maintained recorder alias differs')
    return path


def user_environment():
    return {key: os.environ[key] for key in USER_ENV_NAMES if key in os.environ}


def user_identity():
    return dict(uid=os.getuid(), euid=os.geteuid(), gid=os.getgid(), egid=os.getegid())


def path_transform(outer):
    prefix = ENV['UV_PROJECT_ENVIRONMENT']+'/bin'
    head, separator, underlying = outer.partition(os.pathsep)
    if head != prefix or not separator:
        raise ValueError('Outer uv PATH lacks its exact known venv prefix')
    return dict(venv_bin=prefix, outer=outer, launch=underlying,
                expected_worker=prefix+os.pathsep+underlying)


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


def budget(value):
    size, free = owned_bytes(), shutil.disk_usage(ROOT).free
    c.require(size <= 512*1024**2 and free >= 30*1024**3,
              'Native measurement aggregate512MiB or disk30GiB boundary reached')
    c.require(datetime.now(timezone.utc) < datetime.fromisoformat(value['expires_utc']),
              'Native measurement grant expired')
    return dict(owned_bytes=size, disk_free_bytes=free, utc=w.supervisor.utc())


def grant(args):
    value = m.admission(args)
    c.require(value['sources_sha256'] == b.identity(source_pins()) and value['controller'] == c.pin(SELF)
              and value['recorder'] == c.pin(recorder()) and value['uv'] == c.pin(shutil.which('uv'))
              and value['environment'] == ENV and all(os.environ.get(k) == v for k, v in ENV.items())
              and value['user_environment'] == user_environment() and value['user_identity'] == user_identity()
              and value['path_transform'] == path_transform(value['user_environment']['PATH'])
              and os.environ['PATH'] == value['path_transform']['expected_worker'],
              'Measurement source/controller/recorder/launcher/environment differs')
    unit = 'context-decision-measure-'+value['id']+'.service'
    c.require(value['cgroup'] == '/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit
              and value['maximum_wall_seconds'] == 300 and value['disk_floor_bytes'] == 30*1024**3,
              'Measurement exact cgroup/wall/disk envelope differs')
    return value


def kernel(value):
    w.cgroup_limits(value)
    path = Path('/sys/fs/cgroup')/value['cgroup'].lstrip('/')
    files = {name: (path/name).read_text() for name in
             ('cpu.max', 'memory.max', 'memory.swap.max', 'memory.current', 'memory.events', 'cgroup.events')}
    address = resource.getrlimit(resource.RLIMIT_AS)
    quota, period = files['cpu.max'].split()
    c.require(address == (24*1024**3, 24*1024**3) and int(quota) == 2*int(period)
              and files['memory.max'].strip() == str(16*1024**3) and files['memory.swap.max'].strip() == '0',
              'Actual native CPU/memory/swap/address-space limits differ')
    return dict(cgroup=value['cgroup'], files=files, address_space=list(address),
                file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)), utc=w.supervisor.utc())


def worker(args):
    value = grant(args)
    start = kernel(value)
    budget(value)
    result = m.worker(args)
    c.check(result)
    seal = c.read(result['path'])
    c.require(seal['schema'] == 'context-decision-measurement/1' and seal['complete'] is True
              and seal['sources'] == source_pins() and seal['sources_sha256'] == value['sources_sha256']
              and seal['admission'] == c.pin(args.admission) and seal['arm'] == args.arm
              and seal['emission'] == value['emission'], 'Native measurement completion differs')
    for pin in [*seal['sources'], *seal['files'], seal['result']]:
        c.check(pin)
    for pin in seal['stages']:
        w.evidence.stage(pin, c)
    measured = c.read(seal['result']['path'])
    c.require(measured['schema'] == 'context-decision-native-measurement/1' and measured['parents'] == 64
              and measured['arm'] == args.arm and set(measured['aliases']) == {'feasible_escape', 'feasible_partial'}
              and measured['candidate_promoted'] is False and measured['biological_qualification'] is False,
              'Native measurement scope or alias census differs')
    end = kernel(value)
    final = budget(value)
    intake = c.read(Path(args.worker_intake).parent/'worker-intake.json')
    c.require(intake['verified'] is True, 'Maintained native worker intake was not verified')
    c.require(c.pin(SELF) == value['controller'], 'Admitted measurement controller changed before worker completion')
    envelope = args.output/'controller-worker-complete.json'
    c.fresh(envelope, dict(schema='context-decision-measure-controller-worker/1', complete=True,
            worker=result, controller=value['controller'], sources_sha256=value['sources_sha256'],
            emission=value['emission'], arm=args.arm, intake=intake, kernel_start=start,
            kernel_end=end, final_budget=final, result=seal['result']))
    budget(value)
    return c.pin(envelope)


def raw_projection(directory, label, expected_argv):
    candidates = list((ROOT/'logs/context-feedback/recorder-root/logs').glob('*-'+label+'-*'))
    c.require(len(candidates) == 1, 'Whole native worker lacks exactly one genuine recorder directory')
    raw = candidates[0]
    c.require(all((raw/name).stat().st_size <= 1024*1024 for name in RAW_NAMES if (raw/name).is_file()),
              'Whole native worker raw metadata unexpectedly exceeds1MiB')
    present = {name: c.pin(raw/name) for name in RAW_NAMES if (raw/name).is_file()}
    missing = [name for name in RAW_NAMES if name not in present]
    terminal = c.read(directory/'terminal.json')
    value = dict(schema='context-feedback-stage/1', name=label, path=str(raw), raw=present,
                 missing_raw=missing, exit=terminal['exit'], failure=terminal['error'], projection_error=None,
                 argv=expected_argv, terminal=c.pin(directory/'worker-terminal.json'),
                 group_cleanup=c.pin(directory/'launcher-cleanup.json'))
    c.fresh(directory/'raw-projection.json', value)
    w.evidence.stage(c.pin(directory/'raw-projection.json'), c)
    return value


def supervise(args):
    value = grant(args)
    directory = ROOT/'logs/context-decision/program'/('measure-'+value['id'])
    directory.mkdir()
    unit = 'context-decision-measure-'+value['id']+'.service'
    description = 'Feasible native measurement '+uuid.uuid4().hex
    label = 'native-measure-'+value['id']
    expiry = datetime.fromisoformat(value['expires_utc'])
    deadline = min(time.monotonic()+300, time.monotonic()+(expiry-datetime.now(timezone.utc)).total_seconds())
    w.pg.adopt_orphans()
    with w.LOCK.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            c.fresh(directory/'refused.json', dict(reason='canonical lock held', utc=w.supervisor.utc()))
            raise
        preflight = w.supervisor.show(unit)
        c.require(preflight['properties'].get('LoadState') == 'not-found', 'Native measurement service already exists')
        c.fresh(directory/'intake.json', dict(grant_id=value['id'], admission=str(args.admission.resolve()),
                parent_pid=os.getpid(), parent_start=w.supervisor.process_start(os.getpid()), lock_fd=lock.fileno(),
                unit=unit, description=description))
        remaining = deadline-time.monotonic()-3
        c.require(remaining > 1, 'No bounded native measurement interval remains')
        child = [value['uv']['path'], 'run', '--no-sync', 'python', str(SELF), 'run', '--arm', args.arm,
                 '--emission', str(args.emission.resolve()), '--output', str(args.output.resolve()),
                 '--admission', str(args.admission.resolve()), '--worker-intake', str(directory/'intake.json')]
        argv = ['systemd-run', '--user', '--wait', '--pipe', '--unit='+unit, '--description='+description,
            '--working-directory='+str(ROOT), '--property=Type=exec', '--property=ExitType=cgroup',
            '--property=KillMode=control-group', '--property=Slice=app.slice', '--property=CollectMode=inactive',
            '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL', '--property=TimeoutStopSec=1s',
            '--property=RuntimeMaxSec='+str(remaining)+'s', '--property=CPUQuota=200%',
            '--property=MemoryMax='+str(16*1024**3), '--property=MemorySwapMax=0',
            '--property=LimitAS='+str(24*1024**3)]
        argv += ['--setenv='+key+'='+item for key, item in ENV.items()]
        launch_environment = dict(value['user_environment'], PATH=value['path_transform']['launch'])
        argv += ['--setenv='+key+'='+item for key, item in launch_environment.items()]
        argv += ['--', str(recorder()), label, *child]
        c.fresh(directory/'command.json', dict(argv=argv, cwd=str(ROOT), grant=value, source=c.pin(SELF),
                worker=c.pin(WORKER), recorder=c.pin(recorder()), utc=w.supervisor.utc(),
                preflight=preflight, initial_budget=budget(value), path_transform=value['path_transform']))
        process, error, proof, cleanup = None, None, None, None
        started = w.supervisor.utc()
        try:
            with (directory/'stdout').open('xb') as out, (directory/'stderr').open('xb') as err:
                process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    c.require(time.monotonic() < deadline, 'Native measurement outer wall boundary reached')
                    sample = budget(value)
                    with (directory/'resources.jsonl').open('a') as stream:
                        stream.write(json.dumps(sample)+'\n')
                    time.sleep(.2)
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
                                error = error or 'Native measurement service failed'
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
                final_budget = budget(value)
                c.require(time.monotonic() <= deadline, 'Native measurement final wall boundary reached')
            except BaseException as caught:
                final_budget = dict(error=repr(caught))
                error = error or repr(caught)
            c.fresh(directory/'terminal.json', dict(started_utc=started, ended_utc=w.supervisor.utc(),
                    exit=None if process is None else process.returncode, error=error, proof=proof,
                    final_budget=final_budget, whole_worker_cgroup_terminal=True,
                    launcher_terminal=cleanup is not None and cleanup['terminal'] is True, canonical_lock_retained=True))
            c.fresh(directory/'worker-terminal.json', dict(argv=child, exit=None if process is None else process.returncode,
                    failure=error, started_utc=started, ended_utc=w.supervisor.utc()))
        try:
            raw = raw_projection(directory, label, child)
        except BaseException as caught:
            c.fresh(directory/'projection-error.json', dict(error=repr(caught), execution_not_repeated=True))
            raise
        c.require(error is None and process is not None and process.returncode == 0,
                  'Native measurement unit failed; retained '+str(directory))
        c.require(c.read(directory/'worker-intake.json')['verified'] is True, 'Native worker intake missing')
        envelope = c.read(raw['raw']['stdout']['path'])['completion']
        c.require(envelope['path'] == str(args.output.resolve()/'controller-worker-complete.json')
                  and envelope['size'] < 1024*1024, 'Native worker envelope path/size differs')
        c.require(Path(envelope['path']).stat().st_size == envelope['size'], 'Native worker envelope actual size differs')
        c.check(envelope)
        sealed = c.read(envelope['path'])
        c.require(sealed['schema'] == 'context-decision-measure-controller-worker/1' and sealed['complete'] is True
                  and sealed['controller'] == value['controller'] and c.pin(SELF) == value['controller']
                  and sealed['sources_sha256'] == value['sources_sha256']
                  and sealed['emission'] == value['emission'] and sealed['arm'] == args.arm,
                  'Native worker envelope source/input/arm differs')
        files = [c.pin(directory/name) for name in ('command.json', 'intake.json', 'worker-intake.json',
                 'stdout', 'stderr', 'resources.jsonl', 'launcher-cleanup.json', 'raw-projection.json', 'worker-terminal.json')]
        budget(value)
        c.require(c.pin(SELF) == value['controller'], 'Admitted measurement controller changed before outer completion')
        c.fresh(args.output/'execution-complete.json', dict(schema='context-decision-measure-execution/1',
                complete=True, worker=sealed['worker'], controller_worker=envelope, sources_sha256=value['sources_sha256'],
                arm=args.arm, emission=value['emission'], terminal=c.pin(directory/'terminal.json'), files=files,
                whole_worker_cgroup_terminal=True, launcher_tree_terminal=True))
        budget(value)
        c.require(time.monotonic() <= deadline, 'Native measurement final projection wall boundary reached')
        print(json.dumps(dict(completion=c.pin(args.output/'execution-complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('source-inventory', 'run'))
    parser.add_argument('--arm', choices=('feasible_escape', 'feasible_partial'))
    parser.add_argument('--emission', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--worker-intake', type=Path)
    args = parser.parse_args()
    if args.command == 'source-inventory':
        pins = source_pins()
        print(json.dumps(dict(sources=pins, sources_sha256=b.identity(pins), controller=c.pin(SELF),
                             recorder=c.pin(recorder()), uv=c.pin(shutil.which('uv')), environment=ENV,
                             user_environment=user_environment(), user_identity=user_identity(),
                             path_transform=path_transform(os.environ['PATH']))))
        return
    c.require(all(getattr(args, name) is not None for name in ('arm', 'emission', 'output', 'admission')),
              'Explicit native measurement source/input/output/admission required')
    if args.worker_intake is None:
        supervise(args)
    else:
        print(json.dumps(dict(completion=worker(args))))


if __name__ == '__main__':
    main()
