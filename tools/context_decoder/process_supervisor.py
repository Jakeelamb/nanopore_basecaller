"""Keep the host lock outside the whole-unit worker cgroup until terminal proof."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')
LOGS = ROOT / 'logs/context-feedback'
PROPERTIES = ('LoadState', 'Description', 'ActiveState', 'SubState', 'ControlGroup', 'MainPID',
              'ControlPID', 'KillMode', 'ExitType', 'SendSIGKILL', 'FinalKillSignal', 'Type',
              'RuntimeMaxUSec', 'TimeoutStopUSec', 'ExecMainStatus', 'Result', 'CollectMode')


def utc():
    return datetime.now(timezone.utc).isoformat()


def process_start(pid):
    return (Path('/proc') / str(pid) / 'stat').read_text().rsplit(') ', 1)[1].split()[19]


def show(unit):
    result = subprocess.run(['systemctl', '--user', 'show', unit,
                             '--property=' + ','.join(PROPERTIES)], capture_output=True, text=True, timeout=3)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    return dict(argv=result.args, exit=result.returncode, stdout=result.stdout, stderr=result.stderr,
                properties=values, observed_utc=utc())


def duration(text):
    scales = {'us': 1e-6, 'ms': 1e-3, 's': 1, 'min': 60, 'h': 3600}
    parts = re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|min|s|h)', text)
    if not parts or ''.join(n + u for n, u in parts) != text.replace(' ', ''):
        raise ValueError('Unqualified systemd time property ' + text)
    return sum(float(n) * scales[u] for n, u in parts)


def worker_intake(path, grant, boundary):
    intake = boundary.read(path)
    boundary.require(intake['grant_id'] == grant['id'] and intake['parent_pid'] != os.getpid(), 'Wrong outer controller identity')
    boundary.require(process_start(intake['parent_pid']) == intake['parent_start'], 'Outer controller PID changed')
    fd = Path('/proc') / str(intake['parent_pid']) / 'fd' / str(intake['lock_fd'])
    info = fd.parent.parent / 'fdinfo' / str(intake['lock_fd'])
    boundary.require(fd.resolve() == LOCK and 'FLOCK' in info.read_text() and 'WRITE' in info.read_text(),
                     'Outer controller does not retain the canonical exclusive lock')
    observed = show(intake['unit'])
    values = observed['properties']
    boundary.require(observed['exit'] == 0 and values['Description'] == intake['description']
                     and values['ControlGroup'] == grant['cgroup'], 'Worker unit identity differs')
    boundary.require(values['KillMode'] == 'control-group' and values['ExitType'] == 'cgroup'
                     and values['CollectMode'] == 'inactive'
                     and values['SendSIGKILL'] == 'yes' and values['FinalKillSignal'] == '9'
                     and values['Type'] == 'exec' and 0 < duration(values['RuntimeMaxUSec']) <= grant['maximum_wall_seconds']
                     and duration(values['TimeoutStopUSec']) <= 1, 'Whole-unit hard supervisor policy is not enforced')
    boundary.fresh(Path(path).parent / 'worker-intake.json', dict(verified=True, observation=observed,
                    admission=boundary.pin(intake['admission']), worker_pid=os.getpid(),
                    parent_lock_retained=True, source=boundary.pin(__file__)))
    return intake


def terminal(observation, expected_group):
    p = observation['properties']
    if observation['exit'] != 0 or p.get('ActiveState') not in ('inactive', 'failed'):
        return False
    if p.get('MainPID', '0') != '0' or p.get('ControlPID', '0') != '0':
        return False
    group = p.get('ControlGroup', '')
    if group not in ('', expected_group):
        return False
    path = Path('/sys/fs/cgroup') / expected_group.lstrip('/') / 'cgroup.events'
    if path.exists():
        events = dict(line.split() for line in path.read_text().splitlines())
        return events.get('populated') == '0'
    return True


def unloaded_terminal(observation, expected_group):
    group = Path('/sys/fs/cgroup') / expected_group.lstrip('/')
    return (observation['exit'] == 0
            and observation['properties'].get('LoadState') == 'not-found'
            and not group.exists())


def supervise(phase, config, output, admission, qualification, query0, boundary, process_guard, checkpoint=None):
    boundary.require(admission is not None, 'SOURCE ONLY: fresh external admission is required')
    grant = boundary.read(admission)
    boundary.require(grant['schema'] == 'context-feedback-admission/1' and grant['phase'] == phase
                     and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', grant['id']) is not None, 'Invalid supervisor intake')
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(grant['not_before_utc'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(grant['expires_utc'].replace('Z', '+00:00'))
    remaining = min(float(grant['maximum_wall_seconds']), (end - now).total_seconds()) - 3
    boundary.require(start <= now < end and 1 < remaining <= 297, 'No bounded worker interval remains')
    boundary.require(grant['cpu_quota'] <= 2 and grant['memory_bytes'] <= 4 * 1024**3
                     and grant['address_space_bytes'] <= 8 * 1024**3 and grant['swap_bytes'] == 0,
                     'Supervisor caps exceed the source unit')
    LOGS.mkdir(parents=True, exist_ok=True)
    directory = LOGS / ('supervisor-' + grant['id'])
    directory.mkdir()
    unit = 'context-feedback-' + grant['id'] + '.service'
    description = 'Context feedback ' + grant['id'] + ' ' + uuid.uuid4().hex
    process_guard.adopt_orphans()
    with LOCK.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            boundary.fresh(directory / 'refused.json', dict(reason='canonical lock held', grant=grant, utc=utc()))
            raise ValueError('Canonical lock refused before any worker launch')
        intake_path = directory / 'intake.json'
        boundary.fresh(intake_path, dict(grant_id=grant['id'], admission=str(Path(admission).resolve()),
                         parent_pid=os.getpid(), parent_start=process_start(os.getpid()), lock_fd=lock.fileno(),
                         unit=unit, description=description, canonical_lock=str(LOCK), entered_utc=utc()))
        command = ['systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit,
                   '--description=' + description, '--working-directory=' + str(ROOT),
                   '--property=Type=exec', '--property=ExitType=cgroup', '--property=KillMode=control-group',
                   '--property=CollectMode=inactive',
                   '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL',
                   '--property=TimeoutStartSec=2s', '--property=TimeoutStopSec=1s',
                   '--property=RuntimeMaxSec=' + str(remaining) + 's', '--property=Restart=no',
                   '--property=Slice=app.slice', '--property=CPUQuota=' + str(grant['cpu_quota'] * 100) + '%',
                   '--property=MemoryMax=' + str(grant['memory_bytes']), '--property=MemorySwapMax=0',
                   '--property=LimitAS=' + str(grant['address_space_bytes'])]
        if os.environ.get('UV_PROJECT_ENVIRONMENT'):
            command += ['--setenv=UV_PROJECT_ENVIRONMENT=' + os.environ['UV_PROJECT_ENVIRONMENT']]
        command += ['--', 'uv', 'run', '--project', str(ROOT), '--no-sync', 'python',
                    str(ROOT / 'scripts/context-feedback.py'), phase, '--config', str(Path(config).resolve()),
                    '--output', str(Path(output).resolve()), '--admission', str(Path(admission).resolve()),
                    '--worker-intake', str(intake_path)]
        if qualification:
            command += ['--qualification', str(Path(qualification).resolve())]
        if query0:
            command += ['--query0', str(Path(query0).resolve())]
        if checkpoint:
            command += ['--checkpoint', str(Path(checkpoint).resolve())]
        boundary.fresh(directory / 'command.json', dict(argv=command, grant=grant, source=boundary.pin(__file__)))
        process = None
        error = None
        terminal_proof = None
        stopping = False
        stopped_for_limit = False
        try:
            with (directory / 'stdout').open('xb') as stdout, (directory / 'stderr').open('xb') as stderr:
                process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
                while process.poll() is None:
                    owned_bytes = 0
                    vanished = 0
                    for base in (ROOT / 'results/context-feedback', LOGS):
                        for path in base.rglob('*'):
                            try:
                                if path.is_file() and not path.is_symlink():
                                    owned_bytes += path.stat().st_size
                            except FileNotFoundError:
                                vanished += 1
                    free_bytes = shutil.disk_usage(ROOT).free
                    with (directory / 'resources.jsonl').open('a') as stream:
                        stream.write(json.dumps(dict(utc=utc(), owned_bytes=owned_bytes,
                                     free_bytes=free_bytes, vanished_build_files=vanished)) + '\n')
                    if datetime.now(timezone.utc) >= end - __import__('datetime').timedelta(seconds=1) or owned_bytes > grant['maximum_output_bytes'] or free_bytes < 30 * 1024**3:
                        error = 'outer deadline/output/disk boundary reached'
                        stopped_for_limit = True
                        break
                    time.sleep(0.2)
        except BaseException as caught:
            error = type(caught).__name__ + ': ' + str(caught)
        finally:
            sample = 0
            if process is None:
                terminal_proof = dict(no_launcher_created=True, error=error)
            while terminal_proof is None:
                sample += 1
                try:
                    observed = show(unit)
                    boundary.fresh(directory / ('terminal-' + str(sample) + '.json'), observed)
                    properties = observed['properties']
                    if properties.get('Description') == description:
                        if terminal(observed, grant['cgroup']):
                            terminal_proof = observed
                            if properties.get('Result') != 'success' or properties.get('ActiveState') != 'inactive':
                                error = error or 'worker service failed despite terminal process tree'
                            break
                        if not stopping:
                            result = subprocess.run(['systemctl', '--user', 'stop', '--no-block', unit],
                                                    capture_output=True, text=True, timeout=3)
                            boundary.fresh(directory / 'stop.json', dict(argv=result.args, exit=result.returncode,
                                            stdout=result.stdout, stderr=result.stderr, utc=utc()))
                            stopping = True
                    elif process is not None and process.poll() is not None and unloaded_terminal(observed, grant['cgroup']):
                        terminal_proof = dict(unit_unloaded_and_cgroup_absent=True, observation=observed,
                                              worker_intake_verified=(directory / 'worker-intake.json').exists())
                        if not (directory / 'worker-intake.json').exists():
                            error = error or 'worker did not reach verified intake'
                        break
                except BaseException as caught:
                    boundary.fresh(directory / ('terminal-error-' + str(sample) + '.json'),
                                   dict(error=repr(caught), utc=utc(), canonical_lock_retained=True))
                time.sleep(0.2)
            if process is not None:
                while True:
                    try:
                        cleanup = process_guard.stop_group(process, process.pid)
                        boundary.fresh(directory / 'launcher-cleanup.json', cleanup)
                        break
                    except BaseException as caught:
                        sample += 1
                        boundary.fresh(directory / ('launcher-cleanup-error-' + str(sample) + '.json'),
                                       dict(error=repr(caught), canonical_lock_retained=True, utc=utc()))
                        time.sleep(0.2)
            boundary.fresh(directory / 'terminal-proof.json', dict(unit=unit, proof=terminal_proof,
                            error=error, worker_exit=None if process is None else process.returncode,
                            released_after_empty_cgroup=True, observed_utc=utc()))
        boundary.require(error is None and process is not None and process.returncode == 0,
                         'Supervised unit failed; retained at ' + str(directory))
        worker = boundary.pin(Path(output) / 'complete.json')
        boundary.require(boundary.read(directory / 'stdout') == dict(completion=worker), 'Worker completion stdout differs')
        outer = Path(output) / 'execution-complete.json'
        boundary.fresh(outer, dict(schema='context-feedback-execution/1', complete=True, phase=phase,
                worker_completion=worker, terminal=boundary.pin(directory / 'terminal-proof.json'),
                files=[boundary.pin(directory / name) for name in ('command.json', 'intake.json', 'worker-intake.json',
                       'stdout', 'stderr', 'resources.jsonl', 'terminal-proof.json', 'launcher-cleanup.json')],
                whole_unit_limits_enforced=True, whole_worker_cgroup_terminal=True,
                stopped_for_limit=stopped_for_limit, source=boundary.pin(__file__)))
        descriptor = os.open(Path(output), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        print(json.dumps(dict(completion=boundary.pin(outer))))
