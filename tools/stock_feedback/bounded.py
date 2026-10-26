"""One externally admitted command, original process guard, systemd whole-unit limits."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import time

LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')
GUARD = {'path': '/tmp/nanopore-frontier/private-raw-case/cpu-qualification-prep-v1/process_guard.py',
         'size': 3443, 'sha256': 'dd90a7c50cd1b3044178e3ee248e7f5e948840496b1ad0cee3b99dadad6a14e9'}
PROFILES = {'engineering': (4 * 1024**3, 8 * 1024**3),
            'mapping': (16 * 1024**3, 24 * 1024**3)}
RAW = ('command.json', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')


def require(value, message):
    if not value:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 8 * 1024**2, 'metadata exceeds 8MiB: ' + str(path))
    return json.loads(path.read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def pin(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return dict(path=str(path), size=path.stat().st_size, sha256=digest.hexdigest())


def check(item):
    require(pin(item['path']) == item, 'pin differs: ' + item['path'])
    return item


def guard():
    check(GUARD)
    spec = importlib.util.spec_from_file_location('qualified_original_process_guard', GUARD['path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(request, now=None):
    require(request['schema'] == 'bounded-command/1', 'request schema differs')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', request['id']) is not None, 'invalid unit id')
    now = now or datetime.now(timezone.utc)
    start = datetime.fromisoformat(request['not_before_utc'])
    end = datetime.fromisoformat(request['expires_utc'])
    require(start <= now < end, 'stale or future grant')
    require(3 < request['wall_seconds'] <= 300, 'wall cap differs')
    require(request['profile'] in PROFILES, 'unknown resource profile')
    require((request['memory_bytes'], request['address_space_bytes']) == PROFILES[request['profile']],
            'driver profile/kernel caps mismatch')
    require(request['cpus'] == 2 and request['swap_bytes'] == 0, 'CPU/swap caps differ')
    require(0 < request['growth_bytes'] <= 100 * 1024**2
            and request['aggregate_bytes'] == 4 * 1024**3
            and request['reserve_bytes'] == 30 * 1024**3, 'disk caps differ')
    root = Path(request['root']).resolve(strict=True)
    require(Path(request['root']) == root and Path(request['cwd']).resolve(strict=True) == root,
            'admitted cwd/root differs')
    require(request['argv'] and all(isinstance(x, str) and x for x in request['argv']), 'argv differs')
    require(Path(request['argv'][0]).is_absolute(), 'absolute executable required')
    require(request['source_pins'] and request['input_pins'] is not None, 'source/input closure missing')
    roles = request['roles']
    require(re.fullmatch(r'F[1-4]/[a-z][a-z0-9-]{0,40}', roles['unit']) is not None,
            'unit role binding missing')
    require(sorted(roles['inputs'].values()) == list(range(len(request['input_pins']))),
            'input role binding differs')
    require(sorted(roles['outputs'].values()) == sorted(request['expected_files']),
            'output role binding differs')
    require(any(p['path'] == str(Path(__file__).resolve()) for p in request['source_pins']), 'adapter source pin missing')
    require(any(p['path'] == str(Path(request['argv'][0]).resolve()) for p in request['source_pins']),
            'executable pin missing')
    require(any(p['path'] == str(Path('/usr/bin/time').resolve()) for p in request['source_pins']),
            'recorder executable pin missing')
    require(request['expected_files'] and all(Path(p).is_absolute() for p in request['expected_files']),
            'linked result closure missing')
    require(request['env'].get('UV_OFFLINE') == '1'
            and request['env'].get('UV_PYTHON_DOWNLOADS') == 'never'
            and request['env'].get('PYTHONDONTWRITEBYTECODE') == '1', 'fixed UV environment missing')
    return min(request['wall_seconds'], (end - now).total_seconds())


def show(unit):
    result = subprocess.run(['/usr/bin/systemctl', '--user', 'show', unit], capture_output=True,
                            text=True, timeout=3)
    return dict(exit=result.returncode, stdout=result.stdout, stderr=result.stderr,
                properties=dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line))


def terminal(observed, group):
    p = observed['properties']
    path = Path('/sys/fs/cgroup') / group.lstrip('/')
    if p.get('LoadState') == 'not-found':
        return observed['exit'] in (0, 1) and not path.exists()
    if observed['exit'] != 0:
        return False
    if p.get('ActiveState') not in ('inactive', 'failed') or p.get('MainPID', '0') != '0' or p.get('ControlPID', '0') != '0':
        return False
    if p.get('ControlGroup', '') not in ('', group):
        return False
    return not path.exists() or 'populated 0' in (path / 'cgroup.events').read_text().splitlines()


def owned_bytes(roots):
    total = 0
    for root in roots:
        for path in Path(root).rglob('*'):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
    return total


def kernel_check(request):
    rows = Path('/proc/self/cgroup').read_text().splitlines()
    group = next(row[3:] for row in rows if row.startswith('0::'))
    require(group.endswith('/feedback-next-' + request['id'] + '.service'), 'worker outside admitted unit')
    base = Path('/sys/fs/cgroup') / group.lstrip('/')
    values = {name: (base / name).read_text().strip() for name in
              ('memory.max', 'memory.swap.max', 'cpu.max')}
    quota, period = map(int, values['cpu.max'].split())
    require(int(values['memory.max']) == request['memory_bytes']
            and values['memory.swap.max'] == '0' and quota == request['cpus'] * period,
            'actual cgroup caps differ')
    require(resource.getrlimit(resource.RLIMIT_AS) == (request['address_space_bytes'],) * 2,
            'actual address-space caps differ')
    require(Path.cwd() == Path(request['cwd']), 'actual worker cwd differs')
    return dict(cgroup=group, values=values, address_space=resource.getrlimit(resource.RLIMIT_AS))


def linked_files(paths):
    require(all(Path(p).is_file() for p in paths), 'missing success-linked file or recorder')
    return [pin(p) for p in paths]


def worker(request_path, request_sha, output):
    output = Path(output)
    started = utc()
    process = None
    cleanup = None
    error = None
    exit_code = None
    def stopped(_signal, _frame):
        raise RuntimeError('whole-unit termination requested')
    signal.signal(signal.SIGTERM, stopped)
    try:
        require(pin(request_path)['sha256'] == request_sha, 'admission hash differs')
        request = read(request_path)
        validate(request)
        caps = kernel_check(request)
        write(output / 'kernel.json', caps)
        for item in request['source_pins'] + request['input_pins'] + [GUARD]:
            check(item)
        pg = guard()
        pg.adopt_orphans()
        write(output / 'command.json', dict(argv=request['argv'], cwd=request['cwd'], env=request['env'],
                                          source_pins=request['source_pins'], input_pins=request['input_pins'],
                                          roles=request['roles']))
        (output / 'cwd.txt').write_text(request['cwd'] + '\n')
        (output / 'start.txt').write_text(started + '\n')
        command = ['/usr/bin/time', '-v', '-o', str(output / 'time.txt'), '--', *request['argv']]
        with (output / 'stdout').open('xb') as stdout, (output / 'stderr').open('xb') as stderr:
            process = subprocess.Popen(command, cwd=request['cwd'], env=request['env'], stdout=stdout,
                                       stderr=stderr, start_new_session=True)
            exit_code = process.wait()
        cleanup = pg.stop_group(process, process.pid)
        require(exit_code == 0, 'command failed')
    except BaseException as caught:
        error = repr(caught)
    finally:
        if process is not None and cleanup is None:
            try:
                cleanup = pg.stop_group(process, process.pid)
            except BaseException as caught:
                error = error or repr(caught)
        ended = utc()
        (output / 'end.txt').write_text(ended + '\n')
        (output / 'exit-status.txt').write_text(str(exit_code) + '\n')
        write(output / 'terminal.json', dict(start=started, end=ended, exit=exit_code, error=error,
                                            cleanup=cleanup, projection_pending=error is None))
    if error is not None:
        raise ValueError(error)
    # Projection may fail after a successful producer. Never run the producer again to repair it.
    try:
        linked = linked_files(request['expected_files'])
        raw = linked_files([str(output / name) for name in RAW])
        write(output / 'complete.json', dict(schema='bounded-command-result/1', complete=True,
                    admission=pin(request_path), linked=linked, raw=raw, terminal=pin(output / 'terminal.json')))
    except BaseException as caught:
        write(output / 'projection-failed.json', dict(error=repr(caught), native_exit=exit_code,
                                                     producer_replay_permitted=False, utc=utc()))
        raise


def cleanup_outer(process, pg, unit, group, output):
    """Single post-launch cleanup path. Caller retains flock until both proofs return."""
    output = Path(output)
    failures = []
    launcher = None
    while True:
        # No wait/poll shortcut: the leader can be dead while its adopted group is still live.
        try:
            if process is not None:
                if launcher is None or pg.group_exists(process.pid):
                    launcher = pg.stop_group(process, process.pid)
                require(launcher['terminal'] and not pg.group_exists(process.pid), 'launcher group still live')
            stop = subprocess.run(['/usr/bin/systemctl', '--user', 'stop', '--no-block', unit],
                                  capture_output=True, text=True, timeout=3)
            if not (output / 'stop.json').exists():
                write(output / 'stop.json', dict(exit=stop.returncode, stdout=stop.stdout, stderr=stop.stderr))
            observed = show(unit)
            if terminal(observed, group) and (process is None or not pg.group_exists(process.pid)):
                return dict(launcher=launcher, service=observed, cgroup=group,
                            launcher_group_empty=True, service_cgroup_empty=True, failures=failures)
        except BaseException as caught:
            # Receipt failure is not permission to unwind while either owned tree may survive.
            if not failures:
                failures.append(dict(error=repr(caught), utc=utc(), lock_retained=True))
                try:
                    write(output / 'cleanup-failure.json', failures[0])
                except BaseException:
                    pass
        time.sleep(0.1)


def supervise(request_path, request_sha, output):
    # Only bounded metadata intake precedes systemd. All full hashes and synchronous prep are inside it.
    request = read(request_path)
    remaining = validate(request) - 2
    output = Path(output).resolve()
    require(not output.exists(), 'attempt already exists')
    require(output.is_relative_to(Path(request['root'])) and output.parent.exists(), 'output outside admitted root')
    require(Path.cwd() == Path(request['cwd']), 'outer cwd differs')
    roots = request['output_roots']
    require(str(output.parent) in roots and len(set(roots)) == len(roots), 'output roots differ')
    require(all(Path(p).is_absolute() and Path(p).is_relative_to(Path(request['root'])) for p in roots),
            'output root outside admitted root')
    output.mkdir()
    unit = 'feedback-next-' + request['id'] + '.service'
    group = '/user.slice/user-' + str(os.getuid()) + '.slice/user@' + str(os.getuid()) + '.service/app.slice/' + unit
    initial = show(unit)
    require(initial['properties'].get('LoadState') == 'not-found'
            and not (Path('/sys/fs/cgroup') / group.lstrip('/')).exists(), 'unit id already exists')
    command = ['/usr/bin/systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit,
               '--working-directory=' + request['cwd'], '--property=Type=exec', '--property=ExitType=cgroup',
               '--property=KillMode=control-group', '--property=CollectMode=inactive',
               '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL',
               '--property=TimeoutStopSec=1s', '--property=RuntimeMaxSec=' + str(remaining) + 's',
               '--property=Restart=no', '--property=Slice=app.slice', '--property=CPUQuota=200%',
               '--property=MemoryMax=' + str(request['memory_bytes']), '--property=MemorySwapMax=0',
               '--property=LimitAS=' + str(request['address_space_bytes'])]
    command += ['--setenv=' + k + '=' + v for k, v in request['env'].items()]
    command += ['--', sys.executable, str(Path(__file__).resolve()), 'worker', '--request', str(request_path),
                '--request-sha256', request_sha, '--output', str(output)]
    write(output / 'outer-command.json', dict(argv=command, cwd=str(Path.cwd()), start=utc()))
    # Checked 3443-byte original guard is the sole outer bootstrap source dependency.
    # Every admitted workload/source/input hash still runs inside the bounded service.
    pg = guard()
    pg.adopt_orphans()
    with LOCK.open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Defers interruption until cgroup terminal proof; an early Python unwind releases flock.
        stop_requested = []
        previous_term = signal.signal(signal.SIGTERM, lambda sig, _f: stop_requested.append(sig))
        previous_int = signal.signal(signal.SIGINT, lambda sig, _f: stop_requested.append(sig))
        baseline = owned_bytes(roots)
        process = None
        error = None
        try:
            with (output / 'outer.stdout').open('xb') as stdout, (output / 'outer.stderr').open('xb') as stderr:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
                start = time.monotonic()
                while process.poll() is None:
                    require(not stop_requested, 'outer termination requested')
                    size = owned_bytes(roots)
                    require(time.monotonic() - start < remaining + 1, 'whole-unit wall boundary')
                    require(size - baseline <= request['growth_bytes'] and size <= request['aggregate_bytes']
                            and shutil.disk_usage(output).free >= request['reserve_bytes'], 'whole-unit output/disk boundary')
                    time.sleep(0.1)
                size = owned_bytes(roots)
                require(size - baseline <= request['growth_bytes'] and size <= request['aggregate_bytes']
                        and shutil.disk_usage(output).free >= request['reserve_bytes'], 'final output/disk boundary')
        except BaseException as caught:
            error = repr(caught)
        finally:
            proof = cleanup_outer(process, pg, unit, group, output)
            error = error or ('outer cleanup observed a failure' if proof['failures'] else None)
            write(output / 'outer-terminal.json', dict(end=utc(), error=error, proof=proof,
                       empty_before_unlock=True, exit=None if process is None else process.returncode))
            signal.signal(signal.SIGTERM, previous_term)
            signal.signal(signal.SIGINT, previous_int)
        require(error is None and process is not None and process.returncode == 0, 'unit failed; retained ' + str(output))
        require((output / 'complete.json').is_file(), 'worker completion missing')
    return output / 'complete.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('run', 'worker'))
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.phase == 'worker':
        worker(args.request, args.request_sha256, args.output)
    else:
        supervise(args.request, args.request_sha256, args.output)


if __name__ == '__main__':
    main()
