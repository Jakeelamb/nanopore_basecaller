#!/usr/bin/env python3
"""Emit complete matched parents and coordinate the unchanged biological observer."""
import argparse
import fcntl
from datetime import datetime, timezone
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import uuid
import shutil

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('context_feedback', ROOT / 'scripts/context-feedback.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
c = w.c
SOURCE = c.pin(__file__)
SNAPSHOT = Path('/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json')
SNAPSHOT_HASH = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'


def splice(sequence, quality, edits):
    cursor = 0
    seq, qual = [], []
    for edit in sorted(edits, key=lambda e: e['start']):
        a, b, replacement = edit['start'], edit['end'], edit['replacement']
        c.require(cursor <= a < b <= len(sequence), 'Overlapping/out-of-range parent edits')
        c.require(sequence[a:b] == edit['stock'], 'Edit/native attachment mismatch')
        c.require(replacement and set(replacement) <= set('ACGT'), 'Invalid replacement DNA')
        seq += [sequence[cursor:a], replacement]
        qual += [quality[cursor:a], '!' * len(replacement)]
        cursor = b
    return ''.join(seq) + sequence[cursor:], ''.join(qual) + quality[cursor:]


def independent_splice(sequence, quality, edits):
    for edit in sorted(edits, key=lambda e: e['start'], reverse=True):
        a, b = edit['start'], edit['end']
        sequence = sequence[:a] + edit['replacement'] + sequence[b:]
        quality = quality[:a] + '!' * len(edit['replacement']) + quality[b:]
    return sequence, quality


def completed_producer(manifest, command):
    manifest = Path(manifest).resolve()
    outer = c.read(manifest.parent / 'execution-complete.json')
    for key in ('worker', 'source', 'terminal', 'command', 'worker_intake', 'stdout', 'stderr'):
        c.check(outer[key])
    c.require(outer['complete'] is True and outer['worker'] == c.pin(manifest)
              and outer['source'] == SOURCE, 'Producer outer completion/source differs')
    terminal = c.read(outer['terminal']['path'])
    c.require(terminal['error'] is None and terminal['exit'] == 0, 'Producer outer execution failed')
    c.require(c.read(outer['worker_intake']['path'])['verified'] is True, 'Producer worker intake not verified')
    c.require(c.read(outer['stdout']['path']) == dict(completion=c.pin(manifest)), 'Producer stdout differs')
    launch = c.read(outer['command']['path'])
    c.require(launch['grant']['source'] == SOURCE and launch['grant']['command'] == command
              and launch['grant']['output'] == str(manifest.parent), 'Producer intended command/source differs')
    c.require(str(Path(__file__).resolve()) in launch['argv']
              and launch['argv'][launch['argv'].index(str(Path(__file__).resolve())) + 1] == command,
              'Producer launch command differs')
    return c.read(manifest)


def prepare(checkpoint, output):
    c.require(c.pin(SNAPSHOT)['sha256'] == SNAPSHOT_HASH, 'Observer seam snapshot changed')
    snapshot = c.read(SNAPSHOT)
    source = w.inventory_hash(w.sources())
    qualified = w.evidence.completed(checkpoint, 'checkpoint', source, c)
    summary = c.read(Path(checkpoint) / 'summary.json')
    admitted = c.inputs(w.configuration(ROOT / 'config/context-feedback-dev-v1.json'))
    c.check(snapshot['parents'])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    c.require(len(parents) == len(set(parents)) == 64, 'Original parent census changed')
    c.check(snapshot['native'])
    original = {parent: c.mapped(snapshot['native']['path'], parent) for parent in parents}
    ledger = {arm: [] for arm in ('reference_free', 'selected')}
    for outcome in summary['outcomes']:
        if 'native' not in outcome:
            c.require(outcome['status'] == 'original_excluded', 'Unaccounted selected query')
            continue
        target = Path(outcome['native']['completion']['path']).parent
        result = c.read(target / 'result.json')
        window = admitted['plan'][outcome['query_index']]
        c.require(window['read_id'] == outcome['read_id'] == result['binding']['parent'], 'Decoded parent/plan differs')
        c.require(result['outcome']['native']['sequence'] == window['stock'], 'Native/window mismatch')
        for arm in ledger:
            replacement = result['outcome'][arm]['sequence']
            if replacement != window['stock']:
                ledger[arm].append(dict(parent=window['read_id'], query=window['query_index'],
                        start=window['read_start'], end=window['read_end'], stock=window['stock'],
                        replacement=replacement, native_result=c.pin(target / 'result.json')))
    directory = Path(output).resolve()
    directory.mkdir()
    c.fresh(directory / 'controls.json', controls())
    arms = []
    for arm, edits in ledger.items():
        lines = ['@HD\tVN:1.6\tSO:unknown']
        for parent in parents:
            native = original[parent]
            changes = [e for e in edits if e['parent'] == parent]
            seq, qual = splice(native['sequence'], native['quality'], changes)
            c.require((seq, qual) == independent_splice(native['sequence'], native['quality'], changes),
                      'Independent complete parent reconstruction differs')
            lines.append('\t'.join((parent, '4', '*', '0', '0', '*', '*', '0', '0', seq, qual)))
        path = directory / (arm + '.sam')
        with path.open('x') as stream:
            stream.write('\n'.join(lines) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        parsed = [line.split('\t') for line in path.read_text().splitlines() if not line.startswith('@')]
        c.require([p[0] for p in parsed] == parents, 'Emitted parent census/order differs')
        for row in parsed:
            native = original[row[0]]
            expected = independent_splice(native['sequence'], native['quality'], [e for e in edits if e['parent'] == row[0]])
            c.require((row[9], row[10]) == expected, 'Actual emitted SEQ/Q differs')
        arms.append(dict(arm=arm, sam=c.pin(path), edits=edits, parents=64))
    c.check(SOURCE)
    c.fresh(directory / 'complete.json', dict(schema='context-feedback-parent-emission/1', complete=True,
            source=SOURCE, decoder=qualified, snapshot=c.pin(SNAPSHOT), arms=arms,
            controls=c.pin(directory / 'controls.json'),
            policy='Replace the complete decoded saved interval literally; all outside-window SEQ/Q unchanged. No anchor trimming or outcome-dependent repair.',
            quality='Changed full windows carry uncalibrated ! qualities; unchanged windows preserve original qualities.',
            original_exclusions_retained=True, exploratory_development=True, biological_claim=False))
    return c.pin(directory / 'complete.json')


def worker(manifest, arm, output, grant):
    w.pg.adopt_orphans()
    seal = completed_producer(manifest, 'prepare')
    c.require(seal['complete'] and seal['source'] == SOURCE, 'Emission source differs')
    c.check(seal['controls'])
    w.evidence.completed(Path(seal['decoder']['execution']['path']).parent, 'checkpoint', w.inventory_hash(w.sources()), c)
    c.check(seal['snapshot'])
    snapshot = c.read(seal['snapshot']['path'])
    selected = next(a for a in seal['arms'] if a['arm'] == arm)
    c.check(selected['sam'])
    directory = Path(output).resolve()
    directory.mkdir()
    c.fresh(directory / 'controls.json', controls())
    execution = w.Execution(grant, directory, w.sources() + [c.pin(__file__)])
    def stage(name, argv):
        result = execution.stage('biology-' + arm + '-' + name, argv)
        return result['raw']['stdout']['path']
    tools = snapshot['tools']
    c.fresh(directory / 'start.json', dict(manifest=c.pin(manifest), arm=arm, source=c.pin(__file__),
                                          snapshot=seal['snapshot'], grant=grant, tools=tools))
    for key in ('pairer', 'observer', 'parents', 'native', 'truth', 'confident'):
        c.check(snapshot[key])
    for p in snapshot['eligible'].values():
        c.check(p)
    for p in tools.values():
        if isinstance(p, dict) and {'path', 'sha256', 'size'} <= set(p):
            c.check(p)
    samtools = tools['samtools']['path']
    dorado = tools['dorado']['path']
    index = tools['index']['path']
    c.check(snapshot['reference'])
    bam = stage('sam-to-bam', [samtools, 'view', '-b', selected['sam']['path']])
    aligned = stage('align', [dorado, 'aligner', index, bam, '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
    mapped = stage('mapped-sam', [samtools, 'view', '-h', aligned])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    for parent in parents:
        observed = c.mapped(mapped, parent)
        emitted = c.mapped(selected['sam']['path'], parent)
        c.require((observed['sequence'], observed['quality']) == (emitted['sequence'], emitted['quality']), 'Mapper changed complete parent SEQ/Q')
    lefts = dict(native=snapshot['native']['path'])
    if arm == 'selected':
        other_directory = directory.parent / 'reference_free'
        other = completed_producer(other_directory / 'complete.json', 'arm')
        c.require(other['manifest'] == c.pin(manifest) and other['arm'] == 'reference_free'
                  and other['source'] == SOURCE, 'Reference-free comparator producer differs')
        for item in other['outputs']:
            c.check(item)
        stages = [w.evidence.stage(item, c) for item in other['stages']]
        free = next(a for a in seal['arms'] if a['arm'] == 'reference_free')
        c.check(free['sam'])
        c.require(stages[0]['argv'] == [samtools, 'view', '-b', free['sam']['path']]
                  and stages[1]['argv'] == [dorado, 'aligner', index, stages[0]['raw']['stdout']['path'], '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y']
                  and stages[2]['argv'] == [samtools, 'view', '-h', stages[1]['raw']['stdout']['path']]
                  and other['mapped'] == stages[2]['raw']['stdout'], 'Reference-free mapping/input chain differs')
        c.check(other['mapped'])
        lefts['reference_free'] = other['mapped']['path']
    for name, left in lefts.items():
        for domain, eligible in snapshot['eligible'].items():
            pairs = directory / ('pair-' + name + '-' + domain)
            stage('pair-' + name + '-' + domain, [snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'], '--eligible', eligible['path'], '--left', left, '--right', mapped, '--parents', snapshot['parents']['path'], '--output', pairs])
            stage('summary-' + name + '-' + domain, [snapshot['pairer']['path'], 'summarize', '--pairs', pairs, '--selected', 'all', '--output', directory / ('summary-' + name + '-' + domain)])
    stage('observe', [snapshot['observer']['path'], 'observe', '--reference', snapshot['reference']['path'], '--vcf', snapshot['truth']['path'], '--confident', snapshot['confident']['path'], '--sam', mapped, '--parents', snapshot['parents']['path'], '--output', directory / 'alleles'])
    stage('compare', [snapshot['observer']['path'], 'compare', '--baseline', snapshot['baseline_observations'], '--candidate', directory / 'alleles', '--output', directory / 'comparison'])
    for p in snapshot['baseline_observation_pins']:
        c.check(p)
    c.check(SOURCE)
    c.fresh(directory / 'complete.json', dict(schema='context-feedback-observation/1', complete=True,
            source=SOURCE, manifest=c.pin(manifest), arm=arm, mapped=c.pin(mapped),
            stages=execution.receipts, outputs=[c.pin(p) for p in sorted(directory.rglob('*')) if p.is_file()],
            exploratory_development=True, candidate_promoted=False))
    return c.pin(directory / 'complete.json')


def controls():
    sequence, quality = 'ACGTTACG', 'ABCDEFGH'
    for edits, expected in [([], (sequence, quality)),
            ([dict(start=1, end=3, stock='CG', replacement='T')], ('ATTTACG', 'A!DEFGH')),
            ([dict(start=1, end=2, stock='C', replacement='GG'), dict(start=5, end=7, stock='AC', replacement='T')], ('AGGGTTTG', 'A!!CDE!H'))]:
        c.require(splice(sequence, quality, edits) == expected, 'Splice fixture differs')
        c.require(splice(sequence, quality, edits) == independent_splice(sequence, quality, edits), 'Independent splice differs')
    for edits in [[dict(start=1, end=3, stock='XX', replacement='A')],
                  [dict(start=1, end=3, stock='CG', replacement='A'), dict(start=2, end=4, stock='GT', replacement='C')]]:
        try:
            splice(sequence, quality, edits)
        except ValueError:
            continue
        raise ValueError('Invalid splice did not reject')
    c.require(c.reverse_complement('ACGTTACG') == 'CGTAACGT', 'Orientation control differs')
    return dict(complete=True, independent_reconstruction=True, overlap_and_attachment_reject=True)


def supervise(args):
    grant = c.read(args.admission)
    now = datetime.now(timezone.utc)
    end = datetime.fromisoformat(grant['expires_utc'])
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', grant['id']) is not None, 'Unsafe observation identity')
    expected_group = '/user.slice/user-1000.slice/user@1000.service/app.slice/context-feedback-' + grant['id'] + '.service'
    c.require(grant['schema'] == 'context-feedback-observation-admission/1'
              and grant['cgroup'] == expected_group
              and grant['source'] == SOURCE and grant['command'] == args.command
              and grant['arm'] == args.arm and grant['output'] == str(args.output.resolve())
              and grant['manifest'] == (None if args.manifest is None else c.pin(args.manifest)), 'Wrong observation admission')
    c.require(datetime.fromisoformat(grant['not_before_utc']) <= now < end
              and 5 < (end - now).total_seconds() <= 300 and grant['maximum_wall_seconds'] <= 300
              and 0 < grant['cpu_quota'] <= 2 and 0 < grant['memory_bytes'] <= 16 * 1024**3
              and 0 < grant['address_space_bytes'] <= 24 * 1024**3 and grant['swap_bytes'] == 0
              and 0 < grant['maximum_output_bytes'] <= 100 * 1024**2, 'Observation caps exceed admitted ceiling')
    c.require(args.output.resolve().is_relative_to(w.RESULTS), 'Observation output outside owned tree')
    directory = w.LOGS / ('supervisor-' + grant['id'])
    directory.mkdir()
    unit = 'context-feedback-' + grant['id'] + '.service'
    description = 'Context observation ' + uuid.uuid4().hex
    w.pg.adopt_orphans()
    with w.LOCK.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            c.fresh(directory / 'refused.json', dict(reason='canonical lock held'))
            raise
        intake = directory / 'intake.json'
        c.fresh(intake, dict(grant_id=grant['id'], admission=str(args.admission.resolve()), parent_pid=os.getpid(),
                    parent_start=w.supervisor.process_start(os.getpid()), lock_fd=lock.fileno(), unit=unit, description=description))
        command = ['systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit,
                   '--description=' + description, '--working-directory=' + str(ROOT),
                   '--property=Type=exec', '--property=ExitType=cgroup', '--property=KillMode=control-group',
                   '--property=Slice=app.slice',
                   '--property=CollectMode=inactive', '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL',
                   '--property=TimeoutStopSec=1s', '--property=RuntimeMaxSec=' + str((end-now).total_seconds()-3) + 's',
                   '--property=CPUQuota=' + str(grant['cpu_quota'] * 100) + '%', '--property=MemoryMax=' + str(grant['memory_bytes']),
                   '--property=MemorySwapMax=0', '--property=LimitAS=' + str(grant['address_space_bytes']),
                   '--setenv=UV_PROJECT_ENVIRONMENT=' + os.environ['UV_PROJECT_ENVIRONMENT'], '--', shutil.which('uv'),
                   'run', '--no-sync', 'python', str(Path(__file__).resolve()), args.command, '--output', str(args.output.resolve()),
                   '--admission', str(args.admission.resolve()), '--worker-intake', str(intake)]
        for key in ('checkpoint', 'manifest', 'arm'):
            value = getattr(args, key)
            if value is not None:
                command += ['--' + key, str(value.resolve() if isinstance(value, Path) else value)]
        c.fresh(directory / 'command.json', dict(argv=command, grant=grant, utc=now.isoformat()))
        process = None
        error = None
        proof = None
        try:
            with (directory / 'stdout').open('xb') as out, (directory / 'stderr').open('xb') as err:
                process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    if time.time() >= end.timestamp()-1 or w.owned_bytes() > grant['maximum_output_bytes'] or shutil.disk_usage(ROOT).free < 30*1024**3:
                        raise ValueError('Observation wall/output/disk boundary reached')
                    time.sleep(.2)
        except BaseException as caught:
            error = repr(caught)
        finally:
            sample = 0
            while proof is None:
                try:
                    observation = w.supervisor.show(unit)
                    if observation['properties'].get('Description') == description:
                        if w.supervisor.terminal(observation, grant['cgroup']):
                            proof = observation
                            if observation['properties'].get('Result') != 'success':
                                error = error or 'Service failed'
                        else:
                            subprocess.run(['systemctl', '--user', 'stop', '--no-block', unit], capture_output=True, timeout=3)
                    elif process is None or (process.poll() is not None and w.supervisor.unloaded_terminal(observation, grant['cgroup'])):
                        proof = dict(unloaded_empty_group=observation)
                except BaseException as caught:
                    sample += 1
                    c.fresh(directory / ('termination-observation-error-' + str(sample) + '.json'),
                            dict(error=repr(caught), canonical_lock_retained=True))
                if proof is None:
                    time.sleep(.2)
            if process is not None:
                while True:
                    try:
                        cleanup = w.pg.stop_group(process, process.pid)
                        c.fresh(directory / 'launcher-cleanup.json', cleanup)
                        break
                    except BaseException as caught:
                        sample += 1
                        c.fresh(directory / ('launcher-cleanup-error-' + str(sample) + '.json'),
                                dict(error=repr(caught), canonical_lock_retained=True))
                        time.sleep(.2)
            c.fresh(directory / 'terminal.json', dict(proof=proof, error=error,
                    exit=None if process is None else process.returncode, utc=datetime.now(timezone.utc).isoformat()))
        c.require(error is None and process is not None and process.returncode == 0, 'Observation unit failed; retained ' + str(directory))
        result = c.read(directory / 'stdout')['completion']
        c.check(result)
        c.require(result['path'] == str(args.output.resolve() / 'complete.json'), 'Worker completion path differs')
        c.check(SOURCE)
        c.fresh(args.output / 'execution-complete.json', dict(complete=True, worker=result, source=SOURCE,
                terminal=c.pin(directory / 'terminal.json'), command=c.pin(directory / 'command.json'),
                worker_intake=c.pin(directory / 'worker-intake.json'), stdout=c.pin(directory / 'stdout'), stderr=c.pin(directory / 'stderr')))
        print(json.dumps(dict(completion=c.pin(args.output / 'execution-complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'arm'))
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=('reference_free', 'selected'))
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--worker-intake', type=Path)
    args = parser.parse_args()
    if args.worker_intake is None:
        supervise(args)
        return
    grant = c.read(args.admission)
    w.supervisor.worker_intake(args.worker_intake, grant, c)
    w.cgroup_limits(grant)
    if args.command == 'prepare':
        result = prepare(args.checkpoint, args.output)
    else:
        result = worker(args.manifest, args.arm, args.output, grant)
    print(json.dumps(dict(completion=result)))


if __name__ == '__main__':
    main()
