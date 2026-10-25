#!/usr/bin/env python3
"""Record isolated catalogue admission commands under the shared host lock."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')
RESULTS = ROOT / 'results/compound-frontier'
LOGS = ROOT / 'logs/compound-frontier'
BINARY = RESULTS / 'build/release/catalogue-bridge'
INPUT = ROOT / 'tools/catalogue_bridge/input.json'
PROTOCOL = ROOT / 'config/compound-frontier-v1.json'


def pin(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def fresh(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write('\n')
        handle.flush()
        import os
        os.fsync(handle.fileno())


def budget():
    if shutil.disk_usage(ROOT).free < 30 * 1024**3:
        raise ValueError('30 GiB reserve required')
    size = sum(p.stat().st_size for root in (RESULTS, LOGS) for p in root.rglob('*') if p.is_file())
    if size >= 10 * 1024**3:
        raise ValueError('10 GiB owned-output cap reached')


def record(label, argv):
    budget()
    LOGS.mkdir(parents=True, exist_ok=True)
    directory = LOGS / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + label + '-' + uuid.uuid4().hex[:8])
    directory.mkdir()
    argv = list(map(str, argv))
    executable = pin(shutil.which(argv[0]) or argv[0])
    fresh(directory / 'command.json', argv)
    launch = ['flock', '-w', '10', str(LOCK), '/usr/bin/time', '-v', '-o', str(directory / 'time.txt'), '--', *argv]
    fresh(directory / 'launch.json', launch)
    (directory / 'cwd.txt').write_text(str(ROOT) + '\n')
    started = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    (directory / 'start.txt').write_text(started + '\n')
    with (directory / 'stdout').open('xb') as stdout, (directory / 'stderr').open('xb') as stderr:
        result = subprocess.run(launch, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
    ended = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    (directory / 'end.txt').write_text(ended + '\n')
    (directory / 'exit-status.txt').write_text(str(result.returncode) + '\n')
    value = dict(schema='catalogue-bridge-recorder/1', argv=argv, executable=executable,
                 status='finished' if result.returncode == 0 else 'failed', exit=result.returncode,
                 started_utc=started, ended_utc=ended, recorder=str(directory),
                 recorder_source=pin(__file__), files={p.name: pin(p) for p in sorted(directory.iterdir()) if p.is_file()})
    fresh(directory / 'finish.json', value)
    print(json.dumps(dict(receipt=str(directory / 'finish.json'), exit=result.returncode)), flush=True)
    if result.returncode:
        print((directory / 'stderr').read_text()[-8000:], file=sys.stderr)
        raise SystemExit(result.returncode)
    budget()
    return directory / 'finish.json'


def run(limit):
    RESULTS.mkdir(parents=True, exist_ok=True)
    attempt = RESULTS / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + ('-checkpoint-' if limit == 8 else '-full-') + uuid.uuid4().hex[:8])
    attempt.mkdir()
    transform = attempt / 'transform'
    producer = record('transform', [BINARY, 'transform', '--manifest', INPUT, '--output', transform, '--limit', limit])
    record('admit', [BINARY, 'admit', '--manifest', INPUT, '--transform', transform,
                     '--producer', producer, '--protocol', PROTOCOL, '--output', attempt / 'admission'])
    print(json.dumps(dict(admission=str(attempt / 'admission/bridge-admission.json'), completion=pin(attempt / 'admission/complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('record')
    p.add_argument('label')
    p.add_argument('argv', nargs=argparse.REMAINDER)
    p = sub.add_parser('run')
    p.add_argument('--limit', type=int, choices=(8, 331), required=True)
    args = parser.parse_args()
    if args.command == 'record':
        argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
        if not argv:
            parser.error('command required')
        record(args.label, argv)
    else:
        run(args.limit)


if __name__ == '__main__':
    main()
