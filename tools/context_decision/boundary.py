"""Custody checks for the separately declared feasible-candidate experiment."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT/'tools/context_decoder/study'
OWNED = ROOT/'tools/context_decision'
ATLAS = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v4')
ORIGINAL = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v2')
ATLAS_ID = '695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa'
ORIGINAL_ID = '7a1b9c6f05597dd70e5eb96c894c2ed9e0cf811c28cc7735354fa1aed1f0164b'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    if Path(value.__file__).resolve() != Path(path).resolve():
        raise ValueError('Imported source location differs')
    return value


w = module('decision_execution_primitives', ROOT/'scripts/context-feedback.py')
c = w.c


def identity(pins):
    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sources():
    paths = []
    for root in (OWNED, STUDY):
        census = c.read(root/'source-files.json')
        resolved = [(Path(p) if Path(p).is_absolute() else root/p).resolve(strict=True) for p in census]
        c.require(len(resolved) == len(set(resolved)), 'Duplicate source census entry')
        paths.extend(resolved)
    return [c.pin(path) for path in sorted(set(paths))]


def configuration(path):
    value = c.read(path)
    c.require(value['schema'] == 'context-decision-config/1' and value['role'] == 'development'
              and value['base_revision'] == '6a8c23e8a34d37bef76f25c30cc007bf429deae5'
              and value['context_weight'] == value['neural_deficit_limit'] == value['objective_margin'] == 0.5
              and value['arms'] == ['feasible_escape', 'feasible_partial'], 'Frozen decision policy differs')
    c.require(value['execution'] == dict(canonical_lock=str(w.LOCK), maximum_wall_seconds=300,
              cpu_quota=2, memory_bytes=4*1024**3, address_space_bytes=8*1024**3, swap_bytes=0,
              maximum_output_bytes=4*1024**3, maximum_growth_bytes=100*1024**2,
              disk_floor_bytes=30*1024**3), 'Frozen decision resource envelope differs')
    for pin in value['toolchain'].values():
        c.check(pin)
    return value


def qualified_packet(config):
    atlas = module('decision_original_atlas_program', ATLAS/'scripts/context-program.py')
    c.require(atlas.ROOT == atlas.c.ROOT == ATLAS and identity(atlas.sources()) == ATLAS_ID,
              'Original atlas ROOT/source identity differs')
    prepared = atlas.completed(ATLAS/'results/context-feedback/v4-prepare-all-1', 'prepare')
    packet = prepared['summary']['prepared']['cases']
    c.check(packet)
    c.require(packet['path'] == config['candidate_packet']['path']
              and packet['sha256'] == config['candidate_packet']['sha256'], 'Qualified packet differs')
    return atlas, prepared, packet


def native(directory, producer, pins):
    directory = Path(directory).resolve()
    completion = c.read(producer['raw']['stdout']['path'])['completion']
    c.check(completion)
    c.require(completion['path'] == str(directory/'complete.json'), 'Native completion path differs')
    seal = c.read(completion['path'])
    c.require(seal['schema'] == 'context-decision-native-complete/1' and seal['complete'] is True,
              'Native decision protocol differs')
    for pin in [seal['attempt'], seal['result'], *seal['files'], *seal['inputs']]:
        c.check(pin)
    attempt = c.read(seal['attempt']['path'])
    c.require(attempt['argv'] == producer['argv'] and attempt['binary'] == c.pin(producer['argv'][0]),
              'Native command/binary differs')
    c.require(attempt['source'] == seal['source'] and attempt['source']['compiled_sources'] == pins,
              'Native source closure differs')
    return completion


def completed(directory, phase):
    directory = Path(directory).resolve()
    outer = c.read(directory/'execution-complete.json')
    c.require(outer['complete'] is True and outer['phase'] == phase
              and outer['whole_worker_cgroup_terminal'] is True, 'Outer unit is not complete')
    for pin in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]:
        c.check(pin)
    terminal = c.read(outer['terminal']['path'])
    c.require(terminal['error'] is None and terminal['exit'] == 0 and terminal['owned_cgroup_terminal'] is True,
              'Whole decision unit failed')
    cleanup = c.read(next(pin['path'] for pin in outer['files'] if pin['path'].endswith('/launcher-cleanup.json')))
    c.require(cleanup['terminal'] is True, 'Decision launcher tree is not terminal')
    proof = terminal["proof"].get("unloaded_empty_group", terminal["proof"])["properties"]
    c.require(proof.get("Result") == "success" and proof.get("ActiveState") == "inactive"
              and proof.get("MainPID", "0") == proof.get("ControlPID", "0") == "0",
              "Decision terminal service proof differs")
    c.require(c.read(outer["worker_intake"]["path"])["verified"] is True, "Worker intake not verified")
    worker = c.read(outer['worker']['path'])
    c.require(worker['schema'] == 'context-decision-unit/1' and worker['complete'] is True
              and worker['phase'] == phase and worker['sources_sha256'] == identity(sources()),
              'Decision source/phase identity differs')
    for pin in worker['files']:
        c.check(pin)
    summary = c.read(directory/'summary.json')
    if worker["qualification"] is not None:
        c.check(worker["qualification"])
        prior = completed(Path(worker["qualification"]["path"]).parent, "qualify")
        c.require(summary.get("binary") == prior["binary"], "Qualified binary handoff differs")
    for pin in summary['stages']:
        w.evidence.stage(pin, c)
    for pin in summary.get('native', []):
        c.check(pin)
        attempt = c.read(Path(pin['path']).parent/'attempt.json')
        producers = [w.evidence.stage(item, c) for item in summary['stages']
                     if c.read(item['path'])['argv'] == attempt['argv']]
        c.require(len(producers) == 1, 'Native result lacks exactly one raw producer')
        native(Path(pin['path']).parent, producers[0], sources())
    for name in ('binary',):
        if name in summary:
            c.check(summary[name])
    if phase == 'qualify':
        closure = c.read(directory/'build-closure.json')
        for pin in [closure['compiler'], closure['formatter'], closure['cache'], closure['compile_commands'],
                    *closure['runtime_libraries']]:
            c.check(pin)
    return summary


def ctest_counts(path):
    root = ET.parse(path).getroot()
    tests = list(root.iter('testcase'))
    c.require(len(tests) == 1 and tests[0].get('name') == 'exhaustive_context_decision_controls'
              and not any(tests[0].find(name) is not None for name in ('failure', 'error', 'skipped')),
              'Structured CTest controls did not all execute successfully')
    return len(tests)


def unittest_counts(stderr, expected):
    c.require(re.search(r'^Ran '+str(expected)+r' tests? in [0-9.]+s$', stderr, re.M) is not None
              and re.search(r'^OK$', stderr, re.M) is not None
              and not re.search(r'^(?:FAILED|OK \(|.* \.\.\. skipped)', stderr, re.M),
              'Python control count/result differs')


def compiler_from_cache(path, expected):
    matches = [line.split('=', 1)[1] for line in Path(path).read_text().splitlines()
               if re.match(r'^CMAKE_CXX_COMPILER:(?:FILEPATH|STRING)=', line)]
    c.require(len(matches) == 1 and c.pin(matches[0]) == expected, 'Actual compiler path/hash differs')
    return expected


def build_closure(output, execution, binary, config):
    cache, commands = output/'build/CMakeCache.txt', output/'build/compile_commands.json'
    compiler = compiler_from_cache(cache, config['toolchain']['compiler'])
    flags = ('-std=c++23', '-Werror', '-Wconversion', '-Wsign-conversion', '-Wshadow',
             '-Wall', '-Wextra', '-Wpedantic', '-fno-fast-math', '-ffp-contract=off')
    for row in c.read(commands):
        argv = row.get('arguments') or shlex.split(row['command'])
        c.require(all(flag in argv for flag in flags) and '-ffast-math' not in argv,
                  'Actual C++ strict flags differ')
    stage = execution.stage('decision-linked-runtime', ['ldd', binary['path']])
    libraries = {}
    for line in Path(stage['raw']['stdout']['path']).read_text().splitlines():
        match = re.search(r'(?:=>\s+)?(/[^\s]+)\s+\(', line)
        if match:
            pin = c.pin(match.group(1)); libraries[pin['path']] = pin
    c.require(libraries, 'No actual runtime library closure')
    c.fresh(output/'build-closure.json', dict(compiler=compiler, formatter=config['toolchain']['formatter'],
            cache=c.pin(cache), compile_commands=c.pin(commands), runtime_libraries=list(libraries.values()),
            binary=binary))


def table(path):
    with Path(path).open(encoding='ascii', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        c.require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Invalid TSV header')
        rows = list(reader)
        c.require(all(None not in row and all(v is not None for v in row.values()) for row in rows), 'Malformed TSV row')
        return rows
