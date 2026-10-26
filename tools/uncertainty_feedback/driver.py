#!/usr/bin/env python3
"""Record bounded native commands and seal their exact metadata handoffs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import subprocess
import sys
import time

UNIT = Path(__file__).resolve().parent
ROOT = UNIT.parents[1]
ORIGINAL = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v2')
RAW = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON field ' + key)
        result[key] = value
    return result


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 16 * 1024**2, 'JSON metadata byte bound')
    return json.loads(path.read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON ' + value)))


def pin(path):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), 'Absolute nonsymlink input required')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def check(value):
    require(set(value) == {'path', 'size', 'sha256'} and pin(value['path']) == value,
            'Missing or changed consumed input: ' + str(value.get('path')))
    return value


def fresh(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def utc():
    return datetime.now(timezone.utc).isoformat()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sources():
    return [pin((UNIT / relative).resolve(strict=True)) for relative in read(UNIT / 'source-files.json')]


def witness(value):
    result = value['source_witness']
    dependencies = read(UNIT / 'dependencies.json')
    header = {key: dependencies['nlohmann_json'][key] for key in ('path', 'size', 'sha256')}
    require(result == dict(compiled_sources=[header, *sources()], compiler=dependencies['cxx_compiler']),
            'Exact connector source/compiler witness differs')
    for item in result['compiled_sources'] + [result['compiler']]:
        check(item)
    return result


def completed(value, schema):
    require(value['schema'] == schema and value['complete'] is True, 'Completion schema/status differs')
    witness(value)
    if 'plan' in value:
        validate_plan(value['plan'])
        require(value['plan_sha256'] == value['plan']['plan_sha256'], 'Embedded authoritative plan identity differs')
    return value


def validate_plan(value):
    completed(value, 'uncertainty-feedback-plan/1')
    check(value['windows'])
    require(value['plan_sha256'] == value['windows']['sha256'], 'Declared plan differs from authoritative windows bytes')
    check(value['joins']); check(value['parents']); check(value['audit'])
    config = read(ROOT / 'config/uncertainty-feedback-v1.json')
    require(value['audit']['sha256'] == config['inputs']['audit_sha256'], 'Frozen nomination audit root differs')
    rows = read(value['joins']['path'])
    require(len(rows) == value['nomination_count'] == 512, 'Fixed plan census differs')
    canonical = ''
    for index, row in enumerate(rows):
        require(row['query_index'] == row['window']['query_index'] == index and row['window']['schema'] == 'graph-prior-window/1', 'Plan/window stable query join differs')
        canonical += json.dumps(row['window'], sort_keys=True, separators=(',', ':')) + '\n'
    require(Path(value['windows']['path']).read_text() == canonical, 'Plan join/windows bytes differ')


def command_environment():
    require(os.environ.get('HOME') == '/home/jake', 'Original home differs')
    return dict(HOME=os.environ['HOME'], PATH='/usr/bin:/bin', LC_ALL='C', UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv',
                UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1')


def original_scalar_witness():
    dependencies = read(UNIT / 'dependencies.json'); original = dependencies['original_scalar']
    check(original['source_manifest']); declared = read(original['source_manifest']['path'])
    require(len(declared) == 22, 'Original scalar connector source census differs')
    for item in declared:
        check(item)
    check(original['connector_witness']); observed = read(original['connector_witness']['path'])
    original_unit = Path(original['source_root']) / 'tools/uncertainty_feedback'
    compiled = [pin((original_unit / relative).resolve(strict=True)) for relative in read(original_unit / 'source-files.json')]
    require(all(item in declared for item in compiled), 'Original scalar compiled source absent from qualified manifest')
    header = {key: dependencies['nlohmann_json'][key] for key in ('path', 'size', 'sha256')}
    expected = dict(compiled_sources=[header, *compiled], compiler=dependencies['cxx_compiler'])
    require(observed['schema'] == 'uncertainty-feedback-controls/1' and observed['source_witness'] == expected,
            'Original scalar connector witness differs')
    check(header); check(expected['compiler'])
    return expected


def receipt_in_context(value, binary, argv, inputs, expected_witness, cwd):
    require(value['schema'] == 'uncertainty-feedback-command/1' and value['complete'] is True
            and value['source_witness'] == expected_witness, 'Actual producer completion/source context differs')
    require(value['binary'] == binary and value['argv'] == argv and value['inputs'] == inputs and value['exit_status'] == 0,
            'Exact actual producer binary/argv/input tuple/status differs')
    check(binary)
    for item in inputs:
        check(item)
    require(len(value['raw_files']) == len(RAW), 'Actual producer raw8 inventory differs')
    directory = Path(value['raw_files'][0]['path']).parent
    for name, item in zip(RAW, value['raw_files']):
        check(item)
        require(Path(item['path']) == directory / name, 'Actual producer raw8 names/directories differ')
    require((directory / 'command.sh').read_text() == shlex.join(argv) + '\n'
            and (directory / 'cwd.txt').read_text() == str(cwd) + '\n'
            and (directory / 'exit-status.txt').read_text() == '0\n', 'Actual raw command/cwd/exit differs')
    start, end = (datetime.fromisoformat((directory / name).read_text().strip()) for name in ('start.txt', 'end.txt'))
    require(start.utcoffset().total_seconds() == end.utcoffset().total_seconds() == 0 and start <= end, 'Actual raw UTC clocks differ')
    timing = unique(line.strip().split(': ', 1) for line in (directory / 'time.txt').read_text().splitlines() if line.startswith('\t') and ': ' in line)
    require(timing['Exit status'] == '0' and timing['Command being timed'] == '"' + ' '.join(argv) + '"', 'Actual GNU time argv/exit differs')
    return value


def receipt(value, binary, argv, inputs):
    completed(value, 'uncertainty-feedback-command/1')
    return receipt_in_context(value, binary, argv, inputs, value['source_witness'], ROOT)


def original_scalar_receipt(receipt_pin, key, binary, argv, inputs):
    original = read(UNIT / 'dependencies.json')['original_scalar']
    require(receipt_pin == original[key], 'Original scalar receipt dependency differs')
    check(receipt_pin)
    return receipt_in_context(read(receipt_pin['path']), binary, argv, inputs,
                              original_scalar_witness(), Path(original['source_root']))


def runtime(runtime_pin, binary):
    check(runtime_pin)
    value = read(runtime_pin['path']); original = read(UNIT / 'dependencies.json')['original_scalar']
    is_original = runtime_pin in original['runtimes'].values()
    if not is_original:
        completed(value, 'uncertainty-feedback-runtime/1')
    expected_witness = original_scalar_witness() if is_original else witness(value)
    cwd = Path(original['source_root']) if is_original else ROOT
    require(value['schema'] == 'uncertainty-feedback-runtime/1' and value['complete'] is True
            and value['source_witness'] == expected_witness, 'Runtime completion/source context differs')
    require(value['binary'] == binary, 'Runtime binary differs'); check(value['inspection'])
    inspector = read(UNIT / 'dependencies.json')['runtime_inspector']
    inspection = read(value['inspection']['path']); argv = [inspector['path'], binary['path']]
    actual = (receipt_in_context(inspection, inspector, argv, [binary], expected_witness, cwd)
              if is_original else receipt(inspection, inspector, argv, [binary]))
    require(actual['environment'] == command_environment() and actual['runtime'] is None and actual['extra_runtimes'] == [], 'Runtime-inspection clean bootstrap differs')
    paths = set()
    for line in Path(actual['raw_files'][5]['path']).read_text().splitlines():
        require('not found' not in line, 'Unresolved runtime library')
        found = [str(Path(token).resolve(strict=True)) for token in line.split() if token.startswith('/')]
        require(found or 'linux-vdso' in line, 'Unsupported runtime inspector output'); paths.update(found)
    require(paths and value['libraries'] == [pin(Path(path)) for path in sorted(paths)], 'Actual runtime library closure differs')
    return value


def scalar_contract():
    dependencies = read(UNIT / 'dependencies.json'); tool = dependencies['scalar_toolchain']
    scalar_unit = Path(dependencies['original_scalar']['source_root']) / 'tools/uncertainty_feedback/scalar_oracle'
    inputs = [pin(scalar_unit / name) for name in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', 'src/main.rs')]
    inputs += dependencies['independent_scalar_sources'] + [tool[key] for key in ('anyhow_archive', 'rustc', 'sha256', 'linker')]
    for key in ('anyhow_source_directory', 'sysroot_library_directory'):
        directory = Path(tool[key]); require(directory.is_absolute() and directory.is_dir(), 'Exact Rust source/sysroot directory absent')
        entries = sorted(directory.rglob('*')); require(not any(path.is_symlink() for path in entries), 'Symlink in Rust build-input closure')
        files = [path for path in entries if path.is_file()]; require(0 < len(files) <= 1024, 'Rust build-input closure census bound')
        inputs.extend(pin(path) for path in files)
    argv = [tool['cargo']['path'], 'build', '--offline', '--locked', '--release', '--manifest-path', str(scalar_unit / 'Cargo.toml'), '--target-dir', tool['target_directory']]
    environment = dict(command_environment(), **tool['build_environment'])
    return tool, inputs, argv, environment


def owned_output(path):
    path = Path(path).absolute()
    require(path.is_relative_to(ROOT / 'results/context-feedback') or path.is_relative_to(ROOT / 'logs/context-feedback-targeting'),
            'Output outside isolated owned namespace')
    require(not path.exists(), 'Fresh output required')
    path.mkdir(parents=True)
    return path


def inventory_bytes():
    total = 0
    for base in (ROOT / 'results/context-feedback', ROOT / 'logs'):
        if not base.exists():
            continue
        for path in base.rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():
                    total += path.stat().st_size
            except FileNotFoundError:
                pass
    return total


def qualified_decoder():
    declared = read(UNIT / 'dependencies.json')
    check(declared['unchanged_decoder_manifest_pin'])
    manifest = read(declared['unchanged_decoder_manifest'])
    require(manifest['binary'] == declared['unchanged_decoder'], 'Old qualified decoder identity differs')
    check(manifest['binary'])
    for source in manifest['compiled_sources']:
        check(source)
    check(manifest['build_closure'])
    return manifest


def record(args):
    request_pin = pin(args.request)
    require(request_pin['sha256'] == args.request_sha256, 'Command request pin mismatch')
    request = read(args.request)
    grant = read(args.admission)
    require(request['schema'] == 'uncertainty-feedback-command-request/1' and grant['request'] == request_pin,
            'Queue grant does not bind this exact command request')
    declared_sources = sources()
    # These unchanged helpers inspect the external lock owner and whole-unit cgroup.
    manifest = qualified_decoder()
    expected = {item['path']: item for item in manifest['compiled_sources']}
    for name in ('process_guard.py', 'process_supervisor.py'):
        path = ORIGINAL / 'tools/context_decoder' / name
        check(expected[str(path)])
    guard = load('targeting_original_process_guard', ORIGINAL / 'tools/context_decoder/process_guard.py')
    supervisor = load('targeting_original_process_supervisor', ORIGINAL / 'tools/context_decoder/process_supervisor.py')
    guard.adopt_orphans()
    output = owned_output(args.output)
    supervisor.worker_intake(args.worker_intake, grant, sys.modules[__name__])
    current = dict(line.split(':', 2)[::2] for line in Path('/proc/self/cgroup').read_text().splitlines())['0']
    require(current == grant['cgroup'], 'Worker is outside the admitted cgroup')
    config = read(ROOT / 'config/uncertainty-feedback-v1.json')['execution']
    graph = request.get('graph_resource_phase', False)
    require(grant['cpu_quota'] <= 2 and grant['memory_bytes'] <= config['graph_memory_bytes' if graph else 'memory_bytes']
            and grant['address_space_bytes'] <= config['graph_address_space_bytes' if graph else 'address_space_bytes']
            and grant['swap_bytes'] == 0 and grant['maximum_wall_seconds'] <= 300, 'Grant exceeds frozen phase envelope')
    cgroup = Path('/sys/fs/cgroup') / current.lstrip('/')
    require(int((cgroup / 'memory.max').read_text()) <= grant['memory_bytes']
            and int((cgroup / 'memory.swap.max').read_text()) == 0, 'Kernel memory/swap limits differ')
    quota, period = (cgroup / 'cpu.max').read_text().split()
    require(quota != 'max' and int(quota) <= int(period) * 2, 'Kernel CPU quota differs')
    address_space = resource.getrlimit(resource.RLIMIT_AS)
    require(0 < address_space[0] <= grant['address_space_bytes'] and 0 < address_space[1] <= grant['address_space_bytes'],
            'Kernel address-space limits differ')
    require(os.environ.get('UV_PROJECT_ENVIRONMENT') == '/home/jake/Projects/nanopore_basecaller-retrieval/.venv'
            and os.environ.get('UV_OFFLINE') == '1' and os.environ.get('UV_PYTHON_DOWNLOADS') == 'never'
            and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'Frozen offline Python environment differs')
    check(request['connector_witness'])
    source_witness = witness(read(request['connector_witness']['path']))
    dependencies = read(UNIT / 'dependencies.json'); check(dependencies['recorder_time'])
    environment = command_environment()
    require(request['binary'] != dependencies['scalar_toolchain']['cargo'],
            'Original scalar build is immutable; reuse its pinned dependency')
    require(request['environment'] == environment, 'Actual child environment differs from exact clean environment')
    if request.get('role') == 'runtime-inspection':
        inspector = dependencies['runtime_inspector']
        require(request['binary'] == inspector and len(request['inputs']) == 1
                and request['argv'] == [inspector['path'], request['inputs'][0]['path']]
                and request['runtime'] is None and request['extra_runtimes'] == [], 'Runtime-inspection bootstrap differs')
    else:
        runtime(request['runtime'], request['binary'])
        for runtime_pin in request['extra_runtimes']:
            check(runtime_pin); runtime(runtime_pin, read(runtime_pin['path'])['binary'])
    check(request['binary'])
    require(request['argv'][0] == request['binary']['path'] and all(isinstance(value, str) for value in request['argv']),
            'Actual command executable differs')
    for item in request['inputs']:
        check(item)
    require(request['cwd'] == str(ROOT), 'Command cwd differs')
    require(shutil.disk_usage(ROOT).free >= config['disk_floor_bytes'], 'Disk reserve unavailable')
    baseline = inventory_bytes()
    require(baseline <= config['aggregate_output_bytes'], 'Initial aggregate owned output exceeds price')
    started = time.monotonic()
    (output / 'command.sh').write_text(shlex.join(request['argv']) + '\n')
    (output / 'cwd.txt').write_text(str(ROOT) + '\n')
    (output / 'start.txt').write_text(utc() + '\n')
    process = None
    failure = None
    cleanup = None
    try:
        with (output / 'stdout').open('xb') as stdout, (output / 'stderr').open('xb') as stderr:
            process = subprocess.Popen([dependencies['recorder_time']['path'], '-v', '-o', str(output / 'time.txt'), '--', *request['argv']],
                                       cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True, env=environment)
            while process.poll() is None:
                growth = inventory_bytes() - baseline
                require(time.monotonic() - started < min(295, grant['maximum_wall_seconds'] - 3), 'Command wall bound')
                require(growth <= config['unit_output_growth_bytes'] and inventory_bytes() <= config['aggregate_output_bytes'],
                        'Command output-growth/aggregate bound')
                require(shutil.disk_usage(ROOT).free >= config['disk_floor_bytes'], 'Command disk reserve boundary')
                time.sleep(0.1)
    except BaseException as error:
        failure = type(error).__name__ + ': ' + str(error)
    finally:
        if process is not None:
            cleanup = guard.stop_group(process, process.pid)
            exit_status = process.wait(timeout=2)
        else:
            exit_status = -1
        (output / 'end.txt').write_text(utc() + '\n')
        (output / 'exit-status.txt').write_text(str(exit_status) + '\n')
        fresh(output / 'attempt.json', dict(request=request_pin, grant=pin(args.admission), failure=failure,
              exit_status=exit_status, cleanup=cleanup, wall_seconds=time.monotonic() - started,
              output_growth_bytes=inventory_bytes() - baseline, sources=declared_sources))
    require(failure is None and exit_status == 0 and cleanup['terminal'], 'Command failed; raw attempt retained')
    for item in declared_sources:
        check(item)
    for item in request['inputs']:
        check(item)
    produced = []
    if request.get('role') != 'runtime-inspection':
        runtime(request['runtime'], request['binary'])
        for runtime_pin in request['extra_runtimes']:
            runtime(runtime_pin, read(runtime_pin['path'])['binary'])
    for path in request.get('produced_files', []):
        produced.append(pin(path))
    for path in request.get('produced_directories', []):
        directory = Path(path)
        require(directory.is_relative_to(ROOT / 'results/context-feedback') and directory.is_dir()
                and not directory.is_symlink(), 'Producer output directory differs')
        for member in sorted(directory.rglob('*')):
            require(not member.is_symlink(), 'Symlink in producer output closure')
            if member.is_file():
                produced.append(pin(member))
    require(len({item['path'] for item in produced}) == len(produced), 'Duplicate produced output declaration')
    final_bytes = inventory_bytes()
    require(final_bytes - baseline <= config['unit_output_growth_bytes'] and final_bytes <= config['aggregate_output_bytes']
            and shutil.disk_usage(ROOT).free >= config['disk_floor_bytes'], 'Terminal command growth/aggregate/disk boundary')
    check(dependencies['recorder_time']); witness(dict(source_witness=source_witness))
    completion = dict(schema='uncertainty-feedback-command/1', complete=True, source_witness=source_witness,
          request=request_pin, argv=request['argv'], binary=request['binary'], inputs=request['inputs'],
          raw_files=[pin(output / name) for name in RAW], produced_files=produced, exit_status=exit_status, sources=declared_sources,
          attempt=pin(output / 'attempt.json'), grant=pin(args.admission), dependency_manifest=pin(UNIT / 'dependencies.json'),
          environment=environment, runtime=request['runtime'], extra_runtimes=request['extra_runtimes'])
    receipt(completion, request['binary'], request['argv'], request['inputs'])
    projected = final_bytes + len(json.dumps(completion, indent=2, sort_keys=True, allow_nan=False).encode()) + 1
    require(projected - baseline <= config['unit_output_growth_bytes'] and projected <= config['aggregate_output_bytes'], 'Completion bytes exceed terminal output price')
    fresh(output / 'complete.json', completion)


def seal_scalars(args):
    requests = read(args.requests)
    require(pin(args.requests)['sha256'] == args.requests_sha256
            and requests['schema'] == 'uncertainty-feedback-scalar-requests/1' and requests['complete'], 'Scalar requests root differs')
    completed(requests, 'uncertainty-feedback-scalar-requests/1')
    runs = read(args.runs)
    check(runs['binary']); check(runs['build_receipt'])
    build = read(runs['build_receipt']['path'])
    tool, expected_sources, build_argv, build_environment = scalar_contract()
    original = read(UNIT / 'dependencies.json')['original_scalar']
    require(runs['binary'] == original['binary'] and runs['build_receipt'] == original['build_receipt']
            and runs['compiler_version'] == original['compiler_version']
            and runs['runtime'] == original['runtimes']['scalar']
            and runs['sha256_runtime'] == original['runtimes']['sha256'],
            'Scalar reuse differs from exact original build/runtime dependency')
    original_scalar_receipt(runs['build_receipt'], 'build_receipt', tool['cargo'], build_argv, expected_sources)
    require(build['environment'] == build_environment and len(build['extra_runtimes']) == 2, 'Exact Cargo environment/child runtime census differs')
    runtime(build['runtime'], tool['cargo']); runtime(build['extra_runtimes'][0], tool['rustc']); runtime(build['extra_runtimes'][1], tool['linker'])
    require(runs['binary'] in build['produced_files'], 'Independent scalar executable not bound by its actual build')
    require(runs['sources'] == expected_sources and runs['binary']['path'] == str(Path(tool['target_directory']) / 'release/context-scalar-oracle'), 'Exact scalar source/shim/lock/compiler/build target differs')
    for item in expected_sources:
        check(item)
        require(item in runs['sources'], 'Independent original scalar source absent from build witness')
    for item in runs['sources']:
        check(item)
    runtime(runs['runtime'], runs['binary']); runtime(runs['sha256_runtime'], tool['sha256'])
    version = original_scalar_receipt(runs['compiler_version'], 'compiler_version', tool['rustc'],
                                      [tool['rustc']['path'], '--version', '--verbose'], [tool['rustc']])
    require(version['environment'] == command_environment() and version['runtime'] == build['extra_runtimes'][0]
            and version['extra_runtimes'] == [], 'Compiler version actual runtime/environment differs')
    require(Path(version['raw_files'][5]['path']).read_text().startswith(tool['rustc_version_prefix']), 'Actual Rust compiler version differs')
    expected = {item['query_index']: item for item in requests['requests']}
    rows = []
    for run in runs['rows']:
        query = run['query_index']; check(run['producer'])
        require(query in expected and query not in {row['query_index'] for row in rows}, 'Foreign/duplicate scalar run')
        request = expected[query]['request']; check(request)
        producer = read(run['producer']['path'])
        directory = Path(run['output'])
        require(producer['complete'] and producer['exit_status'] == 0 and producer['binary'] == runs['binary']
                and producer['argv'] == [runs['binary']['path'], 'score', '--request', request['path'],
                                        '--request-sha256', request['sha256'], '--output', str(directory)], 'Scalar actual argv/request/output differs')
        receipt(producer, runs['binary'], producer['argv'], [request, runs['build_receipt'], *expected_sources])
        require(producer['environment'] == command_environment() and producer['runtime'] == runs['runtime']
                and producer['extra_runtimes'] == [runs['sha256_runtime']], 'Scalar actual runtime/environment differs')
        for name in ('retained-scalar.tsv', 'audit.tsv'):
            require(pin(directory / name) in producer['produced_files'], 'Scalar output not bound by actual producer')
        rows.append(dict(query_index=query, request=request, scalar=pin(directory / 'retained-scalar.tsv'),
                         audit=pin(directory / 'audit.tsv'), producer=run['producer']))
    require(set(expected) == {row['query_index'] for row in rows}, 'Incomplete scalar request population')
    output = owned_output(args.output)
    fresh(output / 'complete.json', dict(schema='uncertainty-feedback-scalars/1', complete=True,
          source_witness=requests['source_witness'], plan=requests['plan'],
          plan_sha256=requests['plan_sha256'], requests=pin(args.requests), binary=runs['binary'],
          build_receipt=runs['build_receipt'], sources=runs['sources'], rows=rows, truth_input=False,
          runtime=runs['runtime'], sha256_runtime=runs['sha256_runtime'], compiler_version=runs['compiler_version']))


def seal_decodes(args):
    require(pin(args.frames)['sha256'] == args.frames_sha256, 'Frame completion pin differs')
    frames = completed(read(args.frames), 'uncertainty-feedback-frames/1'); check(frames['frames'])
    expected = {row['query_index']: row for row in read(frames['frames']['path'])}
    manifest = qualified_decoder(); runs = read(args.runs); rows = []
    for run in runs:
        query = run['query_index']; require(query in expected and query not in {row['query_index'] for row in rows}, 'Foreign/duplicate decoded run')
        frame = expected[query]; check(frame['frame']); check(frame['base_frame']); check(run['producer'])
        producer = read(run['producer']['path']); directory = Path(run['output'])
        argv = [manifest['binary']['path'], 'decode-guarded', '--frame', frame['frame']['path'], '--frame-sha256', frame['frame']['sha256'],
                '--output', str(directory), '--beam', '128', '--min-center', '0', '--max-center', '108', '--weight', '0.5', '--deficit', '0.5', '--margin', '0.5']
        receipt(producer, manifest['binary'], argv, [frame['frame'], *manifest['compiled_sources']])
        require(producer['environment'] == command_environment() and producer['extra_runtimes'] == [], 'Decoder actual environment/runtime census differs')
        runtime(producer['runtime'], manifest['binary'])
        seal = read(directory / 'complete.json')
        require(seal['schema'] == 'context-decoder-complete/1' and seal['complete'], 'Decoder completion missing')
        for item in seal['files']:
            check(item)
            require(item in producer['produced_files'], 'Decoded output not bound by actual producer')
        attempt = read(directory / 'attempt.json')
        require(attempt['binary'] == manifest['binary'] and attempt['argv'] == argv
                and attempt['compiled_sources'] == manifest['compiled_sources'], 'Decoder compiled witness/argv differs')
        rows.append(dict(query_index=query, frame=frame['frame'], base_frame=frame['base_frame'], construction=frame['construction'],
                         producer=run['producer'], completion=pin(directory / 'complete.json'), result=pin(directory / 'result.json')))
    require(set(expected) == {row['query_index'] for row in rows}, 'Incomplete decoded frame population')
    output = owned_output(args.output)
    fresh(output / 'complete.json', dict(schema='uncertainty-feedback-decoded/1', complete=True,
          source_witness=frames['source_witness'], plan=frames['plan'],
          plan_sha256=frames['plan_sha256'], frames=pin(args.frames), rows=rows, unchanged_decoder=manifest['binary'], truth_input=False))


def collect_decodes(args):
    require(pin(args.parts)['sha256'] == args.parts_sha256, 'Decode part-list pin differs')
    parts = read(args.parts)
    rows = {}
    plan_hash = None
    decoder = None
    plan = None
    source_witness = None
    for item in parts:
        check(item)
        part = completed(read(item['path']), 'uncertainty-feedback-decoded/1')
        if plan_hash is None:
            plan_hash, decoder = part['plan_sha256'], part['unchanged_decoder']
            plan, source_witness = part['plan'], part['source_witness']
        require(part['plan_sha256'] == plan_hash and part['unchanged_decoder'] == decoder and part['plan'] == plan, 'Foreign decode part plan/binary')
        for row in part['rows']:
            require(row['query_index'] not in rows, 'Replayed/overlapping decoded query')
            for key in ('producer', 'completion', 'result', 'frame', 'base_frame', 'construction'):
                check(row[key])
            rows[row['query_index']] = row
    require(rows, 'Empty decoded population')
    output = owned_output(args.output)
    fresh(output / 'complete.json', dict(schema='uncertainty-feedback-decoded/1', complete=True,
          source_witness=source_witness, plan=plan,
          plan_sha256=plan_hash, rows=[rows[key] for key in sorted(rows)], unchanged_decoder=decoder,
          parts=parts, population_complete=set(rows) == set(range(512)), truth_input=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    sub = commands.add_parser('record')
    for name in ('request', 'request-sha256', 'admission', 'worker-intake', 'output'):
        sub.add_argument('--' + name, required=True)
    sub = commands.add_parser('seal-scalars')
    for name in ('requests', 'requests-sha256', 'runs', 'output'):
        sub.add_argument('--' + name, required=True)
    sub = commands.add_parser('seal-decodes')
    for name in ('frames', 'frames-sha256', 'runs', 'output'):
        sub.add_argument('--' + name, required=True)
    sub = commands.add_parser('collect-decodes')
    for name in ('parts', 'parts-sha256', 'output'):
        sub.add_argument('--' + name, required=True)
    args = parser.parse_args()
    {'record': record, 'seal-scalars': seal_scalars, 'seal-decodes': seal_decodes, 'collect-decodes': collect_decodes}[args.command](args)


if __name__ == '__main__':
    main()
