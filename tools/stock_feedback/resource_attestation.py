"""Fresh resource byte/equivalence verification over honest legacy metadata; no resource production."""
import argparse
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

import bounded as b
import legacy

SUPERVISOR_SHA = '8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4'
RESOURCE_ROLES = ('compressed', 'reference', 'mmi', 'fai', 'publisher_fai', 'registered_fai')


def absolute(item, root):
    return dict(item, path=str((Path(root) / item['path']).resolve()))


def admitted_inputs(spec):
    """Exact full pins, deduplicated across current resource and old raw aliases."""
    reader = legacy.Metadata()
    build = reader.read(spec['registries']['index_built'])
    fai = reader.read(spec['registries']['fai_finish'])
    index_dir = str(Path(spec['legacy_root']) / build['producer_run'])
    values = [*spec['resources'].values(), *spec['registries'].values(), *spec['decompress_raw']]
    values += [absolute(p, spec['legacy_root']) for p in build['producer_pins']
               if str(Path(absolute(p, spec['legacy_root'])['path']).parent) == index_dir
               and Path(p['path']).name in legacy.RAW]
    values += [p for p in fai['pins'] if str(Path(p['path']).parent) == fai['recorder']
               and Path(p['path']).name in legacy.RAW]
    unique = {}
    for value in values:
        b.require(value['path'] not in unique or unique[value['path']] == value, 'conflicting input pin alias')
        unique[value['path']] = value
    return list(unique.values())


def legacy_custody(spec, reader):
    resources = spec['resources']
    root = Path(spec['legacy_root'])
    build = reader.read(spec['registries']['index_built'])
    qualified = reader.read(spec['registries']['reference_qualified'])
    registered = absolute(build['pins'][0], root)
    b.require(len(build['pins']) == 1 and registered == resources['mmi'], 'registered final MMI pin differs')
    b.require(build['reference_sha256'] == resources['compressed']['sha256'], 'registered compressed input differs')
    index_qualified = reader.read(spec['registries']['index_qualified'])
    b.require(index_qualified['status'] == 'verified' and index_qualified['build'] == build
              and resources['mmi'] in [absolute(p, root) for p in index_qualified['pins']],
              'registered index build/parity metadata differs')
    b.require(qualified['status'] == 'verified'
              and resources['compressed'] in [absolute(p, root) for p in qualified['pins']]
              and resources['publisher_fai'] in [absolute(p, root) for p in qualified['pins']],
              'registered reference/FAI pins differ')
    index_dir = root / build['producer_run']
    index_pins = [absolute(p, root) for p in build['producer_pins']]
    argv = spec['index_argv']
    b.require(argv[-1] == resources['compressed']['path'] and '-d' in argv
              and any(p['path'] == argv[0] for p in index_pins), 'legacy index command/input/tool differs')
    index_raw = legacy.raw_closure(reader, index_pins, index_dir, argv, str(root))
    decomp_dir = Path(spec['decompress_raw'][0]['path']).parent
    decomp_argv = spec['decompress_argv']
    b.require(decomp_argv[:2] == ['gzip', '-cd'] and len(decomp_argv) == 3
              and str((root / decomp_argv[2]).resolve()) == resources['compressed']['path'],
              'legacy decompressor command/input differs')
    decomp_raw = legacy.raw_closure(reader, spec['decompress_raw'], decomp_dir, decomp_argv, str(root))
    b.require(decomp_raw['stdout'] == resources['reference'], 'legacy decompressor output pin differs')
    fai = legacy.stock_finish(reader, spec['registries']['fai_finish'], spec['fai_cwd'])
    b.require(fai['argv'] == [spec['samtools_path'], 'faidx', '--fai-idx', resources['registered_fai']['path'],
                              resources['reference']['path']], 'legacy FAI command/output/reference differs')
    names = {}
    for line in reader.text(resources['fai']).splitlines():
        row = line.split('\t')
        b.require(len(row) == 5 and row[0] not in names, 'malformed/duplicate FAI metadata')
        length, offset, line_bases, line_bytes = map(int, row[1:])
        b.require(length > 0 and 0 <= offset < resources['reference']['size'] and 0 < line_bases <= line_bytes,
                  'invalid FAI lengths/offsets')
        names[row[0]] = length
    b.require(names == qualified['dictionary'] and len(names) == qualified['contigs']
              and sum(names.values()) == qualified['reference_bases'], 'full FAI contig map differs')
    b.require(all(resources[key]['sha256'] == resources['publisher_fai']['sha256']
                  and resources[key]['size'] == resources['publisher_fai']['size']
                  for key in ('fai', 'registered_fai')), 'FAI alias bytes differ from registered FAI')
    return dict(index_build=spec['registries']['index_built'], reference_registration=spec['registries']['reference_qualified'],
                index_argv=argv, index_raw=index_raw, registered_final_output=registered,
                registered_compressed_input=resources['compressed'], registered_tool=[p for p in index_pins if p['path'] == argv[0]][0],
                decompress_argv=decomp_argv, decompress_raw=decomp_raw, fai=fai,
                historical_index_terminal=False, historical_admission_requalified=False,
                historical_index_controller_source_pin=None, historical_index_controller_source_qualified=False,
                missing_now=[str(p) for p in (Path(argv[argv.index('-d') + 1]), index_dir / 'terminal.json',
                                             index_dir / 'outer-terminal.json') if not p.exists()],
                contigs=len(names), reference_bases=sum(names.values()), contig_names_lengths=names)


def native_pipeline(spec, output):
    """Native gzip and SHA perform transformation/digest; this pump only counts and forwards bytes."""
    tools = spec['tools']
    pg = b.guard()
    pg.adopt_orphans()
    processes = {}
    cleanup = {}
    exits = {}
    starts = {}
    count = 0
    error = None
    previous = signal.getsignal(signal.SIGTERM)
    def stopped(_signal, _frame):
        raise RuntimeError('resource verification termination requested')
    signal.signal(signal.SIGTERM, stopped)
    commands = {'gzip': [tools['gzip']['path'], '-cd', '--', spec['resources']['compressed']['path']],
                'sha256': [tools['sha256sum']['path']]}
    try:
        for name, argv in commands.items():
            directory = output / name
            directory.mkdir()
            command = [tools['time']['path'], '-v', '-o', str(directory / 'time.txt'), '--', *argv]
            b.write(directory / 'command.json', dict(argv=command, native_argv=argv, cwd=str(Path.cwd()),
                                                     env={'LC_ALL': 'C'}, tool=tools['gzip' if name == 'gzip' else 'sha256sum']))
            starts[name] = b.utc()
            (directory / 'cwd.txt').write_text(str(Path.cwd()) + '\n')
            (directory / 'start.txt').write_text(starts[name] + '\n')
            with (directory / 'stderr').open('xb') as stderr:
                if name == 'gzip':
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr,
                                               env={'LC_ALL': 'C'}, start_new_session=True)
                else:
                    with (directory / 'stdout').open('xb') as stdout:
                        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                                   env={'LC_ALL': 'C'}, start_new_session=True)
            processes[name] = process
        gzip = processes['gzip']
        sha = processes['sha256']
        for block in iter(lambda: gzip.stdout.read(1024**2), b''):
            count += len(block)
            b.require(count <= spec['resources']['reference']['size'], 'gzip stream exceeds current reference byte count')
            b.require(sha.stdin.write(block) == len(block), 'short native SHA input write')
        gzip.stdout.close()
        sha.stdin.close()
        exits['gzip'] = gzip.wait()
        exits['sha256'] = sha.wait()
        b.require(all(code == 0 for code in exits.values()), 'native gzip/SHA pipeline failed')
    except BaseException as caught:
        error = repr(caught)
    finally:
        for name, process in processes.items():
            try:
                cleanup[name] = pg.stop_group(process, process.pid)
                if process.poll() is not None:
                    exits[name] = process.returncode
            except BaseException as caught:
                error = error or repr(caught)
            directory = output / name
            for stream in (process.stdin, process.stdout):
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except BaseException as caught:
                        error = error or repr(caught)
            ended = b.utc()
            (directory / 'end.txt').write_text(ended + '\n')
            (directory / 'exit-status.txt').write_text(str(exits.get(name)) + '\n')
            try:
                for path in directory.iterdir():
                    with path.open('rb') as raw:
                        os.fsync(raw.fileno())
            except BaseException as caught:
                error = error or repr(caught)
            b.write(directory / 'terminal.json', dict(start=starts[name], end=ended, recorder_exit=exits.get(name),
                    exit_known=exits.get(name) is not None, cleanup=cleanup.get(name), error=error,
                    stdout_mode='streamed-and-counted' if name == 'gzip' else 'digest-only'))
        signal.signal(signal.SIGTERM, previous)
    b.require(error is None and len(exits) == 2 and all(code == 0 for code in exits.values()),
              'native pipeline execution failed: ' + str(error))
    path = output / 'sha256/stdout'
    b.require(path.stat().st_size <= 128, 'native digest output exceeds bound')
    text = path.read_text()
    b.require(re.fullmatch(r'[0-9a-f]{64}  -\n', text) is not None, 'invalid native digest output')
    raw = {}
    for name in processes:
        files = ['command.json', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'time.txt', 'stderr', 'terminal.json']
        if name == 'sha256':
            files.append('stdout')
        b.require(all((output / name / filename).stat().st_size <= 8 * 1024**2 for filename in files),
                  'native receipt metadata exceeds bound')
        b.require('\tExit status: 0\n' in (output / name / 'time.txt').read_text(), 'native time exit receipt missing')
        raw[name] = [b.pin(output / name / filename) for filename in files]
    return dict(sha256=text[:64], bytes=count, exits=exits, cleanup=cleanup,
                raw=raw,
                terminal_pins={name: b.pin(output / name / 'terminal.json') for name in processes})


def verify(spec, output, admission=None):
    output = Path(output)
    output.mkdir()
    started = b.utc()
    error = None
    checks = dict(current_pins_verified=False, legacy_custody_verified=False,
                  stream_size_verified=False, stream_digest_verified=False)
    stream = None
    history = None
    phase = 'current-pins'
    previous = signal.getsignal(signal.SIGTERM)
    def stopped(_signal, _frame):
        raise RuntimeError('resource verification termination requested')
    signal.signal(signal.SIGTERM, stopped)
    try:
        b.require(spec['schema'] == 'prefix-legacy-resource-request/1'
                  and spec['purpose'] in ('current-resource', 'hermetic-control'), 'resource request schema/purpose differs')
        b.require(b.pin(b.__file__)['sha256'] == SUPERVISOR_SHA, 'frozen supervisor source changed')
        for key in RESOURCE_ROLES:
            b.check(spec['resources'][key])
        for item in spec['tools'].values():
            b.check(item)
        checks['current_pins_verified'] = True
        phase = 'legacy-custody'
        history = legacy_custody(spec, legacy.Metadata())
        checks['legacy_custody_verified'] = True
        phase = 'native-pipeline'
        stream = native_pipeline(spec, output)
        phase = 'equivalence'
        b.require(stream['bytes'] == spec['resources']['reference']['size'], 'gzip stream byte count differs from current reference')
        checks['stream_size_verified'] = True
        b.require(stream['sha256'] == spec['resources']['reference']['sha256'], 'gzip stream digest differs from current reference')
        checks['stream_digest_verified'] = True
    except BaseException as caught:
        error = repr(caught)
    finally:
        b.write(output / 'terminal.json', dict(start=started, end=b.utc(), error=error, phase=phase, checks=checks,
                                               stream=stream, projection_pending=error is None))
        signal.signal(signal.SIGTERM, previous)
    if error is not None:
        b.write(output / 'failed.json', dict(error=error, phase=phase, checks=checks, producer_replay_permitted=False))
        raise ValueError(error)
    proof = dict(schema='prefix-legacy-resource-attestation/1', complete=True, purpose=spec['purpose'],
                 resources=spec['resources'], legacy=history, stream=stream, checks=checks,
                 current_resource_verification=True, historical_index_terminal=False,
                 historical_admission_requalified=False, historical_index_controller_source_pin=None,
                 historical_index_controller_source_qualified=False, new_index_built=False, new_fai_built=False,
                 source=b.pin(__file__), supervisor=b.pin(b.__file__), tools=spec['tools'],
                 terminal=b.pin(output / 'terminal.json'), admission=admission,
                 external_worker_and_outer_completion_required=True)
    b.write(output / 'complete.json', proof)
    descriptor = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return proof


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('verify',))
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--grant', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    grant = b.read(args.grant)
    b.validate(grant)
    b.kernel_check(grant)
    expected = ['/home/jake/.local/bin/uv', 'run', '--project', '/home/jake/Projects/nanopore_basecaller-retrieval',
                '--no-sync', 'python', str(Path(__file__).resolve()), *sys.argv[1:]]
    b.require(grant['argv'] == expected and grant['roles']['unit'] == 'F4/resource-attestation',
              'verifier command/role differs from admitted unit')
    spec = b.read(args.spec)
    for item in [b.pin(args.spec), *admitted_inputs(spec)]:
        b.require(item in grant['input_pins'], 'attestation input is not admitted: ' + item['path'])
    b.require(str(args.output.resolve()).startswith(grant['root'] + '/')
              and str(args.output.resolve() / 'complete.json') in grant['expected_files'], 'attestation output is not admitted')
    verify(spec, args.output, admission=b.pin(args.grant))


if __name__ == '__main__':
    main()
