"""Own a sample CPU service and retain the canonical lock through final evidence projection."""
import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def verified_active_intake(output, intake_pin, description, group):
    """Caps come from the retained live worker, never unloaded-unit defaults."""
    value = s.pin(output / 'worker-intake.json')
    worker = s.read(value)
    properties = worker['observation']['properties']
    quota, period = worker['kernel']['cpu.max'].split()
    s.require(worker['verified'] is True and worker['intake'] == intake_pin
              and worker['parent_lock_retained'] is True and worker['observation']['exit'] == 0
              and properties['LoadState'] == 'loaded' and properties['ActiveState'] == 'active'
              and properties['Description'] == description and properties['ControlGroup'] == group
              and properties['Type'] == 'exec' and properties['ExitType'] == 'cgroup'
              and properties['KillMode'] == 'control-group' and properties['CollectMode'] == 'inactive'
              and properties['SendSIGKILL'] == 'yes' and properties['FinalKillSignal'] == '9'
              and 0 < s.supervisor.duration(properties['RuntimeMaxUSec']) <= 295
              and s.supervisor.duration(properties['TimeoutStopUSec']) <= 1
              and quota != 'max' and 0 < int(quota) <= 2 * int(period)
              and worker['kernel']['memory.max'] != 'max'
              and int(worker['kernel']['memory.max']) <= 4 * s.GIB
              and worker['kernel']['memory.swap.max'] == '0'
              and worker['rlimit_as'] == [8 * s.GIB, 8 * s.GIB],
              'Retained live worker intake/caps differ')
    for source in worker['sources']:
        s.check(source)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('price', type=Path)
    parser.add_argument('--price-sha256', required=True)
    args = parser.parse_args()
    s.require(Path.cwd().resolve() == s.ROOT, 'Wrong outer cwd')
    price_pin = s.pin(args.price)
    s.require(price_pin['sha256'] == args.price_sha256, 'Price pin differs')
    price = s.read(price_pin)
    required = {'schema', 'id', 'phase', 'worker', 'priced_new_bytes', 'maximum_new_bytes',
                'maximum_cumulative_bytes', 'scientific_work', 'worker_arguments'}
    s.require(set(price) == required and price['schema'] == 'sample-context-bounded-price/1'
              and re.fullmatch('sample-[A-Za-z0-9_-]{1,64}', price['id']) is not None
              and price['phase'] in ('format', 'engineering', 'plan', 'reference', 'assemble', 'pilot', 'decode', 'packet', 'tables')
              and type(price['scientific_work']) is bool and isinstance(price['worker_arguments'], list)
              and all(isinstance(value, str) for value in price['worker_arguments']), 'Explicit phase price required')
    s.require(all(type(price[key]) is int for key in ('priced_new_bytes', 'maximum_new_bytes', 'maximum_cumulative_bytes'))
              and 0 < price['priced_new_bytes'] <= price['maximum_new_bytes'] <= 2 * s.GIB
              and price['maximum_cumulative_bytes'] == 2 * s.GIB
              and (price['phase'] not in ('format', 'engineering') or price['maximum_new_bytes'] <= 100 * s.MIB),
              'Price exceeds engineering/new-growth/cumulative ceilings')
    worker = s.check(price['worker'])
    s.require(worker.parent == HERE and worker.name.startswith('sample-') and worker.suffix == '.py',
              'Worker is outside assigned helper scope')
    identity = price['id']
    directory = HERE / ('run-' + identity)
    directory.mkdir()
    output = s.RESULTS / identity
    s.require(not output.exists(), 'Fresh sample unit output required')
    unit = 'sample-context-' + identity + '.service'
    group = '/user.slice/user-1000.slice/user@1000.service/app.slice/' + unit
    description = 'Sample context ' + identity + ' ' + uuid.uuid4().hex
    s.pg.adopt_orphans()
    with s.LOCK.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            s.fresh(directory / 'refused.json', dict(reason='canonical lock held', price=price_pin, utc=s.utc()))
            raise ValueError('Canonical lock refused before any worker launch')
        preflight = s.supervisor.show(unit)
        s.fresh(directory / 'preflight.json', preflight)
        s.require(s.supervisor.unloaded_terminal(preflight, group),
                  'Service name or cgroup exists; no foreign unit will be stopped')
        baseline = s.census()
        sample = s.bytes_now(baseline)
        s.require(sample['cumulative_bytes'] + price['priced_new_bytes'] <= price['maximum_cumulative_bytes']
                  and sample['free_bytes'] >= 30 * s.GIB + price['priced_new_bytes'], 'Cumulative price/disk reserve unavailable')
        output.mkdir(parents=True)
        (output / 'tmp').mkdir()
        (output / 'recorder-root/scripts').mkdir(parents=True)
        (output / 'recorder-root/logs').mkdir()
        recorder = output / 'recorder-root/scripts/record-command.sh'
        recorder.symlink_to(s.ROOT / 'scripts/record-command.sh')
        s.sync(output)
        sources = s.source_closure(worker) + [s.pin(__file__)]
        deadline = time.monotonic() + 294
        intake = output / 'outer-intake.json'
        s.fresh(intake, dict(price=price_pin, output=str(output), unit=unit, cgroup=group, description=description,
                parent_pid=os.getpid(), parent_start=s.supervisor.process_start(os.getpid()), lock_fd=lock.fileno(),
                canonical_lock=str(s.LOCK), monotonic_deadline=deadline, baseline=baseline, sources=sources))
        worker_argv = [str(s.UV), 'run', '--no-sync', 'python', str(worker), identity,
                       '--intake', str(intake), '--intake-sha256', s.pin(intake)['sha256'], *price['worker_arguments']]
        command = ['systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit, '--description=' + description,
                   '--working-directory=' + str(s.ROOT), '--property=Slice=app.slice', '--property=Type=exec',
                   '--property=ExitType=cgroup', '--property=KillMode=control-group', '--property=CollectMode=inactive',
                   '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL', '--property=Restart=no',
                   '--property=RuntimeMaxSec=295s', '--property=TimeoutStartSec=2s', '--property=TimeoutStopSec=1s',
                   '--property=CPUQuota=200%', '--property=MemoryMax=4294967296', '--property=MemorySwapMax=0',
                   '--property=LimitAS=8589934592']
        for key, value in dict(s.ENV, TMPDIR=str(output / 'tmp')).items():
            command.append('--setenv=' + key + '=' + value)
        command += ['--', str(recorder), identity, *worker_argv]
        s.fresh(directory / 'start.json', dict(argv=command, worker_argv=worker_argv, cwd=str(s.ROOT), utc=s.utc(),
                price=price_pin, worker=s.pin(worker), controller=s.pin(__file__), runtime=s.pin(HERE / 'sample-runtime.py'),
                recorder=s.pin(recorder), lock=str(s.LOCK), sources=sources, intake=s.pin(intake),
                caps=dict(wall_seconds=300, service_seconds=295, cpu=2, memory=4*s.GIB, address_space=8*s.GIB,
                          swap=0, maximum_new_bytes=price['maximum_new_bytes'], maximum_cumulative_bytes=2*s.GIB)))
        start_pin = s.pin(directory / 'start.json')
        error, process, proof, stopped, active_intake = None, None, None, False, None
        try:
            with (directory / 'stdout').open('xb') as out, (directory / 'stderr').open('xb') as err:
                process = subprocess.Popen(command, cwd=s.ROOT, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    sample = s.bytes_now(baseline)
                    with (directory / 'resources.jsonl').open('a') as stream:
                        stream.write(__import__('json').dumps(dict(utc=s.utc(), **sample)) + '\n')
                    s.require(time.monotonic() < deadline and sample['new_bytes'] <= price['maximum_new_bytes']
                              and sample['cumulative_bytes'] <= 2*s.GIB and sample['free_bytes'] >= 30*s.GIB,
                              'Outer wall/output/disk boundary reached')
                    time.sleep(.2)
        except BaseException as caught:
            error = repr(caught)
        finally:
            index = 0
            while proof is None:
                index += 1
                try:
                    observed = s.supervisor.show(unit)
                    properties = observed['properties']
                    if properties.get('Description') == description:
                        if s.supervisor.terminal(observed, group):
                            proof = observed
                            if properties.get('Result') != 'success' or properties.get('ActiveState') != 'inactive':
                                error = error or 'Owned service failed'
                        elif not stopped:
                            stop = subprocess.run(['systemctl', '--user', 'stop', '--no-block', unit],
                                                  capture_output=True, text=True, timeout=3)
                            s.fresh(directory / 'stop.json', dict(argv=stop.args, exit=stop.returncode,
                                    stdout=stop.stdout, stderr=stop.stderr, utc=s.utc()))
                            stopped = True
                    elif (process is None or process.poll() is not None) and s.supervisor.unloaded_terminal(observed, group):
                        if process is not None and process.returncode == 0:
                            try:
                                active_intake = verified_active_intake(output, s.pin(intake), description, group)
                            except BaseException as caught:
                                error = error or repr(caught)
                        else:
                            error = error or 'Owned service unloaded without successful launcher'
                        proof = observed
                    else:
                        error = error or 'Owned service identity changed; refusing foreign stop'
                except BaseException as caught:
                    s.fresh(directory / ('observation-error-' + str(index) + '.json'),
                            dict(error=repr(caught), lock_retained=True, utc=s.utc()))
                if proof is None:
                    time.sleep(.2)
            if process is not None:
                cleanup = None
                while cleanup is None:
                    try:
                        cleanup = s.pg.stop_group(process, process.pid)
                    except BaseException as caught:
                        index += 1
                        s.fresh(directory / ('launcher-cleanup-error-' + str(index) + '.json'),
                                dict(error=repr(caught), lock_retained=True, utc=s.utc()))
                s.fresh(directory / 'launcher-cleanup.json', cleanup)
            s.fresh(directory / 'terminal.json', dict(utc=s.utc(), exit=None if process is None else process.returncode,
                    error=error, proof=proof, unit=unit, expected_cgroup=group,
                    live_worker_intake=active_intake, lock_retained_during_projection=True))
            projection_error, raw = None, None
            try:
                raw_directory = Path((directory / 'stdout').read_text().strip())
                s.require(raw_directory.parent == output / 'recorder-root/logs', 'Outer raw recorder location differs')
                raw = s.verify_raw(raw_directory, worker_argv, process.returncode)
                if process.returncode == 0:
                    completion = s.pin(output / 'complete.json')
                    s.require(__import__('json').loads(Path(raw['stdout']['path']).read_text()) == dict(completion=completion),
                              'Outer raw stdout does not bind worker completion')
                s.check(start_pin)
                for source in sources:
                    s.check(source)
            except BaseException as caught:
                projection_error = repr(caught)
            s.fresh(directory / 'outer-evidence.json', dict(raw=raw, projection_error=projection_error,
                    start=start_pin, terminal=s.pin(directory / 'terminal.json'),
                    launcher_cleanup=None if process is None else s.pin(directory / 'launcher-cleanup.json'),
                    recorder=s.pin(recorder), final_resources=s.bytes_now(baseline), lock_retained=True))
            s.sync(directory)
        s.require(error is None and projection_error is None and process is not None and process.returncode == 0,
                  'Sample unit failed; retained at ' + str(directory))
        print(__import__('json').dumps(dict(completion=s.pin(output / 'complete.json'), outer=s.pin(directory / 'outer-evidence.json'))))


if __name__ == '__main__':
    main()
