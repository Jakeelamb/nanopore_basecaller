"""Recheck retained qualification artifacts without executing the product."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import xml.etree.ElementTree as ET

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
OUT = ROOT/'logs/context-sample-feedback/source-ready'
UNIT = ROOT/'results/context-sample-feedback/sample-qualify-3'


def pin(path):
    data = Path(path).read_bytes()
    return dict(path=str(path), size=len(data), sha256=hashlib.sha256(data).hexdigest())


def check(value):
    assert pin(value['path']) == value, value['path']
    return Path(value['path'])


def read(value):
    return json.loads(check(value).read_text())


inventory = json.loads((OUT/'source-inventory-post-format-2.json').read_text())
assert len(inventory['sources']) == 89
assert hashlib.sha256(json.dumps(inventory['sources'], sort_keys=True, separators=(',', ':')).encode()).hexdigest() == inventory['sha256'] == '63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2'
for row in inventory['sources']:
    check(row)
outer = read(pin(UNIT/'execution-complete.json'))
assert outer['complete'] and outer['phase'] == 'qualify' and outer['whole_worker_cgroup_terminal']
for row in outer['files']:
    check(row)
terminal = read(outer['terminal'])
assert terminal['error'] is None and terminal['exit'] == 0
assert terminal['owned_cgroup_terminal'] and terminal['canonical_lock_retained']
proof = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
assert proof['MainPID'] == proof['ControlPID'] == '0'
assert proof['Result'] == 'success' and proof['ActiveState'] == 'inactive' and proof['ControlGroup'] == ''
supervisor = Path(outer['terminal']['path']).parent
cleanup = json.loads((supervisor/'launcher-cleanup.json').read_text())
assert cleanup['terminal']
intake = read(outer['worker_intake'])
assert intake['verified'] and intake['parent_lock_retained']
grant = read(intake['admission'])
assert grant['sources_sha256'] == inventory['sha256'] and grant['phase'] == 'qualify'
assert intake['observation']['properties']['ControlGroup'] == grant['cgroup']
assert not Path('/sys/fs/cgroup'+grant['cgroup']).exists()
worker = read(outer['worker'])
assert worker['complete'] and worker['phase'] == 'qualify' and worker['sources_sha256'] == inventory['sha256']
for row in worker['files']:
    check(row)
start = json.loads((UNIT/'start.json').read_text())
assert start['sources'] == inventory['sources'] and start['grant'] == intake['admission']
summary = json.loads((UNIT/'summary.json').read_text())
stages = []
for value in summary['stages']:
    stage = read(value)
    assert stage['exit'] == 0 and stage['failure'] is None and stage['projection_error'] is None
    assert not stage['missing_raw'] and stage['admission_id'] == grant['id']
    assert set(stage['raw']) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}
    for row in stage['raw'].values():
        check(row)
    assert shlex.split(check(stage['raw']['command.sh']).read_text()) == stage['argv']
    assert check(stage['raw']['cwd.txt']).read_text().strip() == str(ROOT)
    assert check(stage['raw']['exit-status.txt']).read_text().strip() == '0'
    assert '\tExit status: 0' in check(stage['raw']['time.txt']).read_text()
    assert datetime.fromisoformat(stage['start_utc']) <= datetime.fromisoformat(stage['end_utc'])
    for key in ('terminal', 'group_cleanup'):
        check(stage[key])
    assert read(stage['group_cleanup'])['terminal']
    stages.append(stage)
expected = ['sample-cmake-configure', 'sample-cmake-build', 'sample-format-check', 'sample-ctest',
            'sample-native-controls', 'sample-python-controls', 'sample-linked-runtime']
assert [stage['name'] for stage in stages] == expected
by_name = {stage['name']: stage for stage in stages}
ctest = ET.parse(UNIT/'ctest.xml').getroot()
assert all(ctest.attrib[key] == value for key, value in dict(tests='1', failures='0', skipped='0').items())
testcases = list(ctest.iter('testcase'))
assert len(testcases) == 1 and not any(testcases[0].find(name) is not None for name in ('failure', 'error', 'skipped'))
ctest_result = json.loads(testcases[0].find('system-out').text)
assert ctest_result == dict(executed=112, skipped=0, passed=True)
python_stderr = check(by_name['sample-python-controls']['raw']['stderr']).read_text()
python_lines = re.findall(r'^(test_\S+) \([^\n]+\) \.\.\. ok$', python_stderr, re.M)
assert len(python_lines) == len(set(python_lines)) == 24
assert 'test_genuine_frame_executes_exact_rust_scalar_comparisons' in python_lines
assert re.search(r'^Ran 24 tests in [0-9.]+s$', python_stderr, re.M)
assert re.search(r'^OK$', python_stderr, re.M) and 'skipped' not in python_stderr
assert len(summary['native']) == 1
native = read(summary['native'][0])
assert native['complete'] and native['source']['compiled_sources'] == inventory['sources']
attempt = read(native['attempt'])
assert attempt['argv'] == by_name['sample-native-controls']['argv']
assert attempt['binary'] == summary['binary'] and attempt['source'] == native['source']
native_result = read(native['result'])
assert native_result == dict(schema='context-sample-feedback-controls/1', passed=True, executed=112, skipped=0)
for row in native['files'] + native['inputs']:
    check(row)
closure = json.loads((UNIT/'build-closure.json').read_text())
for key in ('compiler', 'formatter', 'cache', 'compile_commands', 'binary'):
    check(closure[key])
assert closure['binary'] == summary['binary']
check(summary['observer_binary'])
assert closure['runtime_libraries']
for row in closure['runtime_libraries']:
    check(row)
flags = {'-std=c++23', '-Wall', '-Wextra', '-Wpedantic', '-Wconversion', '-Wsign-conversion',
         '-Wshadow', '-Werror', '-fno-fast-math', '-ffp-contract=off', '-O3', '-DNDEBUG'}
commands = read(closure['compile_commands'])
for command in commands:
    argv = command.get('arguments') or shlex.split(command['command'])
    assert flags <= set(argv) and '-ffast-math' not in argv
    assert pin(Path(argv[0])) == closure['compiler']
assert 'CMAKE_BUILD_TYPE:STRING=Release' in check(closure['cache']).read_text()
witness = (UNIT/'build/sample_sources.h').read_text()
witness_rows = [dict(path=path, sha256=digest, size=int(size)) for path, digest, size in re.findall(r'\{"([^"\n]+)","([a-f0-9]{64})",([0-9]+)\}', witness)]
assert witness_rows == inventory['sources']
ldd = check(by_name['sample-linked-runtime']['raw']['stdout']).read_text()
libraries = {}
for line in ldd.splitlines():
    match = re.search(r'(?:=>\s+)?(/[^\s]+)\s+\(', line)
    if match:
        row = pin(Path(match.group(1)).resolve())
        libraries[row['path']] = row
assert list(libraries.values()) == closure['runtime_libraries']
record = dict(schema='context-sample-feedback-qualification-audit/1', complete=True,
    utc=datetime.now(timezone.utc).isoformat(), source_identity=inventory['sha256'], source_count=89,
    sources_rehashed=True, compiled_source_witness_matches=True, completion=pin(UNIT/'execution-complete.json'),
    grant=intake['admission'], binary=summary['binary'], observer_binary=summary['observer_binary'],
    build_closure=pin(UNIT/'build-closure.json'), compile_command_count=len(commands),
    runtime_library_count=len(closure['runtime_libraries']), runtime_closure_kind='retained ldd paths, not loaded mappings',
    stages=[dict(name=stage['name'], start_utc=stage['start_utc'], end_utc=stage['end_utc'],
                 finish=summary['stages'][index], raw=stage['raw']) for index, stage in enumerate(stages)],
    ctest=dict(executed=1, skipped=0, native_assertions=112), native_controls=native_result,
    python_controls=dict(executed=24, skipped=0, genuine_frame_positive_passed=True,
                         scalar_comparisons_asserted_positive=True, exact_scalar_count_not_retained=True,
                         raw_stderr=by_name['sample-python-controls']['raw']['stderr']),
    terminal=outer['terminal'], launcher=pin(supervisor/'launcher-cleanup.json'),
    worker_intake=outer['worker_intake'], exec_parent_exit=0, exec_parent_session=86434,
    exec_parent_observation='tools.write_stdin returned exit_code0 and no session_id',
    outer_start_utc=(supervisor/'start.txt').read_text().strip(),
    outer_end_utc=(supervisor/'end.txt').read_text().strip(),
    supervisor_time=pin(supervisor/'time.txt'),
    caps={key: grant[key] for key in ('maximum_wall_seconds', 'cpu_quota', 'memory_bytes', 'address_space_bytes',
          'swap_bytes', 'maximum_growth_bytes', 'maximum_output_bytes')},
    disk_floor_bytes=32212254720, no_product_execution_in_this_audit=True,
    source_edited=False, scientific_outcomes_qualified=False, physical_read_independence_qualified=False,
    promotion_eligible=False)
with (OUT/'qualify-3-audit.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(audit=pin(OUT/'qualify-3-audit.json'), source_identity=record['source_identity'],
                     completion=record['completion'], binary=summary['binary'],
                     controls=record['native_controls'], python_controls=24,
                     compile_commands=len(commands), runtime_libraries=len(closure['runtime_libraries']),
                     terminal=record['terminal'], launcher=record['launcher'],
                     outer_start_utc=record['outer_start_utc'], outer_end_utc=record['outer_end_utc'])))
