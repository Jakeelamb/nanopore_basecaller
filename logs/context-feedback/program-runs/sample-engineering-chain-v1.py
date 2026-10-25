"""Validate only the declared engineering-2 partial producer and its explicit continuation."""
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
v2 = s.load('sample_bounded_v2', HERE / 'run-sample-bounded-v2.py')
ORIGINAL = s.RESULTS / 'sample-engineering-2'
BUILD = ORIGINAL / 'build'
OUTER = dict(path=str(HERE / 'run-sample-engineering-2/outer-evidence.json'), size=3891,
             sha256='adfb62217abdab3246c67d313037701b56ff386c2d50b823c1db6b3da46ee4c2')
FREEZE = dict(path=str(s.RESULTS / 'sample-format-1/source-freeze.json'), size=8280,
              sha256='ea0fab88eec6ec1d038ba7f057e3d1bf40808a180f927bbde83e1f649538300c')
BUILT = {name: dict(path=str(BUILD / name), size=size, sha256=sha) for name, size, sha in (
    ('sample-context', 437472, '66c21a7b76570b5a52aaa943d48ae1512ecbb45db5061d1efffb927a032cf55b'),
    ('compile_commands.json', 4215, '37c160369b6dcfa916d46225e83ed6b04e65c2100c6f126b7887d4c85b69a609'),
    ('CMakeCache.txt', 18838, '59ff661e48736593e3a581534c6da0016fd9aa964cc86291d72e05ae187df4e0'),
    ('sample_sources.h', 3559, 'e9d3a2f159d26a57c39d17c8e59be4c6b53050214e9c1b1c9c4718970267a57d'))}
COUNTERS = dict(independently_enumerated_alignments=3528, complete_core_deletion_cases=4,
                deep_lineage_component_cases=2, conflicting_parent_order_cases=4)


def ctest_pass(text):
    named = re.findall(r'^\s*1/1 Test #1: sample_context_contract_controls \.\.\.\s+Passed\s+[0-9.]+ sec\s*$', text, re.M)
    summary = re.findall(r'^100% tests passed out of 1\s*$', text, re.M)
    s.require(len(named) == 1 and len(summary) == 1
              and not re.search(r'not\s*run|skipped|disabled|\b0 tests\b', text, re.I),
              'CTest must show the named 1/1 Passed test with skipped0')


def counters(value):
    s.require(value['schema'] == 'sample-context-controls/1' and value['synthetic_only'] is True
              and value['biological_qualification'] is False and value['assertions'] >= 3528
              and all(value.get(key) == number for key, number in COUNTERS.items()),
              'Actual exhaustive/family/deletion acceptance counters differ')


def stage(value, expected):
    item = s.read(value)
    terminal = s.read(item['terminal'])
    s.require(item['schema'] == 'context-feedback-stage/1' and item['argv'] == expected
              and item['exit'] == 0 and item['failure'] is None and item['projection_error'] is None
              and not item['missing_raw'] and item['explicit_env'] == s.ENV
              and terminal['argv'] == expected and terminal['exit'] == 0 and terminal['failure'] is None
              and s.read(item['group_cleanup'])['terminal'] is True
              and set(item['raw']) == set(s.RAW_NAMES)
              and item['raw'] == s.verify_raw(Path(item['raw']['stdout']['path']).parent, expected, 0),
              'Successful engineering stage argv/raw/tree differs')
    return item


def partial():
    outer, freeze = s.read(OUTER), s.read(FREEZE)
    start = s.read(outer['start'])
    intake = s.read(start['intake'])
    terminal = s.read(outer['terminal'])
    s.require(start['worker'] == s.pin(HERE / 'sample-engineering.py')
              and start['controller'] == s.pin(HERE / 'run-sample-bounded-v2.py')
              and start['runtime'] == s.pin(HERE / 'sample-runtime.py')
              and start['recorder'] == s.pin(s.ROOT / 'scripts/record-command.sh')
              and start['sources'] == s.source_closure(HERE / 'sample-engineering.py') + [start['controller']]
              and start['cwd'] == str(s.ROOT) and start['lock'] == str(s.LOCK)
              and outer['projection_error'] is None and outer['lock_retained'] is True
              and terminal['error'] == 'Owned service failed' and terminal['exit'] == 1
              and terminal['proof']['properties']['Result'] == 'exit-code'
              and terminal['proof']['properties']['ActiveState'] == 'failed'
              and s.supervisor.terminal(terminal['proof'], terminal['expected_cgroup'])
              and s.read(outer['launcher_cleanup'])['terminal'] is True,
              'Declared original partial engineering source/failure/tree differs')
    active = v2.verified_active_intake(ORIGINAL, start['intake'], intake['description'], terminal['expected_cgroup'])
    s.require(outer['raw'] == s.verify_raw(Path(outer['raw']['stdout']['path']).parent, start['worker_argv'], 1)
              and s.check(outer['raw']['stdout']).stat().st_size == 0
              and s.check(outer['raw']['stderr']).read_text().rstrip().endswith(
                  'ValueError: CTest must execute 1 test with skipped 0')
              and not (ORIGINAL / 'complete.json').exists(), 'Original known CTest observation failure differs')
    s.require(start['worker_argv'][-4:] == ['--freeze', FREEZE['path'], '--freeze-sha256', FREEZE['sha256']]
              and freeze['schema'] == 'sample-context-source-freeze/1' and len(freeze['sources']) == 15,
              'Original reviewed source-freeze intake differs')
    for value in start['sources'] + freeze['sources'] + freeze['snapshots'] + list(BUILT.values()):
        s.check(value)
    tools = {name: s.pin(path) for name, path in dict(cmake='/usr/bin/cmake', compiler='/usr/bin/c++',
             formatter='/usr/bin/clang-format', ctest='/usr/bin/ctest', ldd='/usr/bin/ldd',
             uv=str(s.UV), python=str(s.ENVIRONMENT / 'bin/python')).items()}
    commands = [('sample-version-' + name, [tools[name]['path'], '--version'])
                for name in ('compiler', 'formatter', 'uv', 'python')]
    commands += [('sample-configure', [tools['cmake']['path'], '-S', str(s.ROOT / 'tools/sample_context'), '-B', str(BUILD),
                  '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=/usr/bin/c++', '-DSAMPLE_FORMATTER=/usr/bin/clang-format']),
                 ('sample-build', [tools['cmake']['path'], '--build', str(BUILD), '--parallel', '2']),
                 ('sample-format-check', [tools['cmake']['path'], '--build', str(BUILD), '--target', 'format-check']),
                 ('sample-ctest', [tools['ctest']['path'], '--test-dir', str(BUILD), '--output-on-failure', '--parallel', '1'])]
    s.require({path.name for path in (ORIGINAL / 'stages').iterdir()} == {name for name, _ in commands},
              'Original partial must contain exactly the eight executed stages')
    stages = []
    for name, argv in commands:
        value = s.pin(ORIGINAL / 'stages' / name / 'finish.json')
        item = stage(value, argv)
        s.require(item['name'] == name, 'Original stage name differs')
        stages.append(value)
    ctest = s.read(stages[-1])
    ctest_pass(s.check(ctest['raw']['stdout']).read_text())
    last_test = s.pin(BUILD / 'Testing/Temporary/LastTest.log')
    observed = [json.loads(line) for line in s.check(last_test).read_text().splitlines() if line.startswith('{')]
    s.require(len(observed) == 1, 'Actual CTest native control output missing/duplicated')
    counters(observed[0])
    compile_commands = s.read(BUILT['compile_commands.json'])
    s.require({str(Path(row['file']).resolve()) for row in compile_commands}
              == {value['path'] for value in freeze['sources'] if value['path'].endswith('.cpp')}
              and all(all(flag in row['command'] for flag in ('-O3', '-DNDEBUG', '-std=c++23', '-Werror',
                          '-fno-fast-math', '-ffp-contract=off', '-Wconversion', '-Wsign-conversion'))
                      for row in compile_commands), 'Original compiled source census/flags differ')
    witness = s.check(BUILT['sample_sources.h']).read_text()
    embedded = [dict(path=path, sha256=sha, size=int(size)) for path, sha, size in
                re.findall(r'\{"([^"]+)","([a-f0-9]{64})",([0-9]+)\},', witness)]
    s.require(embedded == freeze['sources'] and tools['compiler']['sha256'] in witness
              and tools['formatter']['sha256'] in witness, 'Original compiled witness differs')
    return dict(schema='sample-context-partial-engineering/1', original_id='sample-engineering-2',
                original_outer=OUTER, original_start=outer['start'], original_failed_terminal=outer['terminal'],
                original_worker_intake=active, original_stages=stages, source_freeze=FREEZE, built=BUILT,
                ctest_native_output=last_test, ctest_controls=observed[0], tools=tools,
                failure='CTest stdout summary literal differed after eight successful stages',
                original_complete=False, build_repeated=False, ctest_repeated=False)


def continued(completion, outer_pin):
    """Accept this explicit 8+3 producer chain, never reinterpret a generic failed unit."""
    seal, outer = s.read(completion), s.read(outer_pin)
    start = s.read(outer['start'])
    terminal = s.read(outer['terminal'])
    s.require(seal['schema'] == 'sample-context-unit/1' and seal['complete'] is True
              and seal['phase'] == 'engineering-continuation'
              and seal['details']['qualification_kind'] == 'declared_engineering_2_partial_plus_3'
              and seal['details']['qualified'] is True and seal['biological_qualification'] is False
              and start['worker'] == s.pin(HERE / 'sample-engineering-continue-v1.py')
              and start['controller'] == s.pin(HERE / 'run-sample-bounded-v2.py')
              and start['runtime'] == s.pin(HERE / 'sample-runtime.py')
              and start['sources'] == s.source_closure(HERE / 'sample-engineering-continue-v1.py') + [start['controller']]
              and start['cwd'] == str(s.ROOT) and start['lock'] == str(s.LOCK)
              and outer['projection_error'] is None and terminal['error'] is None and terminal['exit'] == 0
              and s.read(outer['launcher_cleanup'])['terminal'] is True,
              'Declared engineering continuation source/result/tree differs')
    output = Path(completion['path']).parent
    intake = s.read(start['intake'])
    v2.verified_active_intake(output, start['intake'], intake['description'], terminal['expected_cgroup'])
    s.require(s.supervisor.terminal(terminal['proof'], terminal['expected_cgroup'])
              and terminal['proof']['properties']['Result'] == 'success'
              and terminal['proof']['properties']['ActiveState'] == 'inactive'
              and outer['raw'] == s.verify_raw(Path(outer['raw']['stdout']['path']).parent, start['worker_argv'], 0)
              and json.loads(s.check(outer['raw']['stdout']).read_text()) == dict(completion=completion),
              'Continuation outer raw completion/terminal binding differs')
    original = partial()
    closure_pin = next(value for value in seal['files'] if Path(value['path']).name == 'runtime-closure.json')
    closure = s.read(closure_pin)
    s.require(closure['schema'] == 'sample-context-runtime-closure/2'
              and closure['qualification_kind'] == 'declared_engineering_2_partial_plus_3'
              and s.read(closure['original_partial']) == original
              and closure['original_stages'] == original['original_stages']
              and closure['continuation_stages'] == seal['stages'] and len(seal['stages']) == 3
              and closure['binary'] == BUILT['sample-context'] and closure['source_freeze'] == FREEZE
              and closure['python_tests'] == 12 and closure['python_skipped'] == 0
              and closure['ctest_tests'] == 1 and closure['ctest_skipped'] == 0,
              'Explicit original-eight plus continuation-three closure differs')
    counters(closure['cpp_controls'])
    freeze = s.read(FREEZE)
    s.require(seal['sources'] == start['sources'] + freeze['sources'] + [s.pin(__file__)],
              'Continuation complete source census differs')
    for value in seal['sources'] + seal['files'] + list(closure['compiler_and_tools'].values()) + closure['linked_libraries']:
        s.check(value)
    expected = [
        [str(s.UV), 'run', '--no-sync', 'python', '-m', 'unittest', 'discover', '-s', 'tools/sample_context/tests', '-p', 'test_pipeline.py', '-v'],
        [BUILT['sample-context']['path'], 'qualify', '--output', str(output / 'arithmetic')],
        [original['tools']['ldd']['path'], BUILT['sample-context']['path']]]
    for value, argv in zip(seal['stages'], expected):
        stage(value, argv)
    return closure_pin
