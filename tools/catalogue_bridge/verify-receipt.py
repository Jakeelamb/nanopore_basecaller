#!/usr/bin/env python3
"""Audit retained raw bridge launches without changing the executed producer."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = '/home/jake/Projects/nanopore_basecaller/results/stock/host.lock'
REQUIRED = {'command.json', 'launch.json', 'cwd.txt', 'start.txt', 'end.txt',
            'exit-status.txt', 'stdout', 'stderr', 'time.txt'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as handle:
        sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=sha)


def check(value):
    require(pin(value['path']) == value, 'Changed pin ' + value['path'])


def write(path, value):
    import os
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def audit(value, argv, completion, source):
    require(value['schema'] == 'catalogue-bridge-recorder/1'
            and value['status'] == 'finished' and value['exit'] == 0, 'Successful recorder required')
    require(value['argv'] == argv, 'Wrong native argv')
    files = value['files']
    require(set(files) == REQUIRED, 'Incomplete raw recorder file set')
    directory = Path(value['recorder'])
    for name, item in files.items():
        require(Path(item['path']) == directory / name, 'Raw recorder path differs from directory')
        check(item)
    require(value['recorder_source'] == source, 'Wrong recorder source')
    check(source)
    require(value['executable'] == pin(argv[0]), 'Wrong executed binary')
    require(read(files['command.json']['path']) == argv, 'Raw command differs')
    expected = ['flock', '-w', '10', LOCK, '/usr/bin/time', '-v', '-o',
                str(directory / 'time.txt'), '--', *argv]
    require(read(files['launch.json']['path']) == expected, 'Wrong lock/time launch wrapper')
    require(Path(files['cwd.txt']['path']).read_text() == str(ROOT) + '\n', 'Wrong cwd')
    start = Path(files['start.txt']['path']).read_text().strip()
    end = Path(files['end.txt']['path']).read_text().strip()
    require(start == value['started_utc'] and end == value['ended_utc'], 'Wrong UTC clock binding')
    require(start.endswith('Z') and end.endswith('Z')
            and datetime.fromisoformat(start) < datetime.fromisoformat(end), 'Invalid UTC clocks')
    require(Path(files['exit-status.txt']['path']).read_text() == '0\n', 'Wrong raw exit')
    check(completion)
    require(read(files['stdout']['path']) == dict(completion=completion), 'Wrong completion stdout')
    stderr_size = Path(files['stderr']['path']).stat().st_size
    times = {}
    for line in Path(files['time.txt']['path']).read_text().splitlines():
        if line.startswith('\t') and ': ' in line:
            key, val = line.strip().split(': ', 1)
            times[key] = val
    require(times.get('Command being timed') == '"' + ' '.join(argv) + '"', 'Wrong GNU time command')
    require(times.get('Exit status') == '0', 'Missing successful GNU time exit')
    require(float(times['User time (seconds)']) >= 0 and float(times['System time (seconds)']) >= 0,
            'Missing GNU time CPU receipts')
    wall = times['Elapsed (wall clock) time (h:mm:ss or m:ss)']
    parts = list(map(float, wall.split(':')))
    require(len(parts) in (2, 3) and all(v >= 0 for v in parts), 'Invalid GNU time wall receipt')
    wall_seconds = sum(v * 60**i for i, v in enumerate(reversed(parts)))
    rss = int(times['Maximum resident set size (kbytes)'])
    require(rss > 0, 'Missing GNU time RSS receipt')
    return dict(argv=argv, native_completion=completion, recorder_source=source,
                exact_lock_and_time_wrapper=True, exact_cwd=True, complete_raw_file_set=True,
                stderr_bytes=stderr_size, wall_seconds=wall_seconds, peak_rss_kib=rss)


def contract(package, admission_receipt):
    package = Path(package).resolve()
    seal = read(package / 'complete.json')
    require(seal['schema'] == 'compound-frontier-completion/1' and seal['complete'], 'Incomplete package')
    for p in seal['files']:
        check(p)
    admission = read(package / 'bridge-admission.json')
    producer = admission['bridge_producer']
    for item in producer['compiled_source_pins']:
        check(item)
    check(producer['executable'])
    source = next(p for p in producer['compiled_source_pins'] if p['path'].endswith('/scripts/catalogue-bridge.py'))
    protocol = next(p for p in producer['compiled_source_pins'] if p['path'].endswith('/config/compound-frontier-v1.json'))
    transform_completion = admission['outputs']['bridge_completion']
    transform_dir = str(Path(transform_completion['path']).parent)
    binary = producer['executable']['path']
    manifest = producer['manifest']['path']
    transform_argv = [binary, 'transform', '--manifest', manifest, '--output', transform_dir,
                      '--limit', str(admission['preservation']['scored'])]
    transform_receipt = producer['receipt']
    check(transform_receipt)
    first = audit(read(transform_receipt['path']), transform_argv, transform_completion, source)
    admit_argv = [binary, 'admit', '--manifest', manifest, '--transform', transform_dir,
                  '--producer', transform_receipt['path'], '--protocol', protocol['path'], '--output', str(package)]
    second = audit(read(admission_receipt), admit_argv, pin(package / 'complete.json'), source)
    return dict(schema='compound-frontier-raw-receipt-audit/1', package=pin(package / 'complete.json'),
                transform_receipt=transform_receipt, admission_receipt=pin(admission_receipt),
                transform=first, admission=second,
                guard_scope='Independent retained-artifact audit. The native recorder guard does not enforce every check listed here.',
                compiled_sources=producer['compiled_source_pins'], executed_binary=producer['executable'],
                source_revision_matches_executed_producer=True,
                verifier_source=pin(__file__), complete=True)


def controls(package, receipt, output):
    import copy
    output = Path(output)
    output.mkdir()
    c = contract(package, receipt)
    original = read(c['admission_receipt']['path'])
    argv = c['admission']['argv']
    completion = c['admission']['native_completion']
    source = c['admission']['recorder_source']
    cases = []
    for name in ('launch', 'cwd', 'source', 'time', 'stderr'):
        directory = output / name
        directory.mkdir()
        value = copy.deepcopy(original)
        value['recorder'] = str(directory.resolve())
        for file_name, item in original['files'].items():
            (directory / file_name).write_bytes(Path(item['path']).read_bytes())
        launch = read(directory / 'launch.json')
        launch[7] = str(directory.resolve() / 'time.txt')
        if name == 'launch':
            launch[2] = '0'
        (directory / 'launch.json').write_text(json.dumps(launch))
        if name == 'cwd':
            (directory / 'cwd.txt').write_text('/wrong\n')
        elif name == 'source':
            (directory / 'false-source.py').write_text('raise SystemExit(0)\n')
            value['recorder_source'] = pin(directory / 'false-source.py')
        elif name == 'time':
            (directory / 'time.txt').write_text('')
        value['files'] = {key: pin(directory / key) for key in REQUIRED if name != 'stderr' or key != 'stderr'}
        write(directory / 'fixture.json', value)
        try:
            audit(value, argv, completion, source)
        except (ValueError, KeyError) as error:
            expected = dict(launch='Wrong lock/time launch wrapper', cwd='Wrong cwd', source='Wrong recorder source', time='Wrong GNU time command', stderr='Incomplete raw recorder file set')[name]
            require(expected in str(error), 'Corruption did not reach intended audit guard ' + name + ' ' + str(error))
            cases.append(dict(case=name, rejected=True, reason=str(error), fixture=pin(directory / 'fixture.json')))
        else:
            raise ValueError('Corruption accepted ' + name)
    write(output / 'summary.json', dict(schema='compound-frontier-audit-controls/1', cases=cases, complete=True))
    return dict(audit=c, controls=pin(output / 'summary.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--admission-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--controls', type=Path)
    args = parser.parse_args()
    result = controls(args.package, args.admission_receipt, args.controls) if args.controls else contract(args.package, args.admission_receipt)
    write(args.output, result)
    print(json.dumps(dict(audit=pin(args.output))))


if __name__ == '__main__':
    main()
