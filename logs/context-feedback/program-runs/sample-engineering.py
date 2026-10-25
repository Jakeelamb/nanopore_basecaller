"""Qualify the exact reviewed formatter cut, with complete raw engineering receipts."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--freeze-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    s.require(unit.price['phase'] == 'engineering' and unit.price['scientific_work'] is False,
              'Engineering-only qualification price required')
    freeze_pin = s.pin(args.freeze)
    s.require(freeze_pin['sha256'] == args.freeze_sha256, 'Reviewed source freeze pin differs')
    freeze = s.read(freeze_pin)
    s.require(freeze['schema'] == 'sample-context-source-freeze/1' and freeze['source_only_preparation'] is True
              and freeze['controls_executed'] is False and freeze['scientific_work'] is False,
              'Source-only formatter cut required')
    for value in freeze['sources'] + freeze['snapshots'] + [freeze['formatter']]:
        s.check(value)
    build = unit.directory / 'build'
    source = s.ROOT / 'tools/sample_context'
    tools = {name: s.pin(path) for name, path in dict(cmake='/usr/bin/cmake', compiler='/usr/bin/c++',
             formatter='/usr/bin/clang-format', ctest='/usr/bin/ctest', ldd='/usr/bin/ldd',
             uv=str(s.UV), python=str(s.ENVIRONMENT / 'bin/python')).items()}
    s.require(tools['formatter'] == freeze['formatter'], 'Reviewed formatter differs')
    for name in ('compiler', 'formatter', 'uv', 'python'):
        unit.stage('sample-version-' + name, [tools[name]['path'], '--version'])
    unit.stage('sample-configure', [tools['cmake']['path'], '-S', source, '-B', build,
               '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=/usr/bin/c++', '-DSAMPLE_FORMATTER=/usr/bin/clang-format'])
    unit.stage('sample-build', [tools['cmake']['path'], '--build', build, '--parallel', '2'])
    unit.stage('sample-format-check', [tools['cmake']['path'], '--build', build, '--target', 'format-check'])
    ctest = unit.stage('sample-ctest', [tools['ctest']['path'], '--test-dir', build,
                       '--output-on-failure', '--parallel', '1'])
    ctest_text = Path(ctest['raw']['stdout']['path']).read_text()
    s.require('100% tests passed, 0 tests failed out of 1' in ctest_text
              and 'sample_context_contract_controls' in ctest_text
              and not any(text in ctest_text for text in ('Not Run', 'Disabled', 'Skipped')), 'CTest must execute 1 test with skipped 0')
    python = unit.stage('sample-python-controls', [str(s.UV), 'run', '--no-sync', 'python', '-m', 'unittest',
                        'discover', '-s', 'tools/sample_context/tests', '-p', 'test_pipeline.py', '-v'])
    python_text = Path(python['raw']['stderr']['path']).read_text()
    s.require('Ran 12 tests' in python_text and python_text.count(' ... ok\n') == 12
              and 'skipped' not in python_text.lower() and python_text.rstrip().endswith('OK'),
              'Python controls must actually execute exactly 12 tests with skipped 0')
    binary = s.pin(build / 'sample-context')
    unit.stage('sample-arithmetic', [binary['path'], 'qualify', '--output', unit.directory / 'arithmetic'])
    arithmetic = json.loads((unit.directory / 'arithmetic/result.json').read_text())
    s.require(arithmetic['schema'] == 'sample-context-controls/1' and arithmetic['synthetic_only'] is True
              and arithmetic['independently_enumerated_alignments'] == 3528
              and arithmetic['assertions'] >= 3528 and arithmetic['biological_qualification'] is False,
              'Exhaustive C++ controls did not execute the declared alignment census')
    linked = unit.stage('sample-linked-libraries', [tools['ldd']['path'], binary['path']])
    libraries = []
    for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
        s.require('not found' not in line, 'Missing runtime library')
        match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
        if match:
            libraries.append(s.pin(match.group(1)))
    s.require(libraries and any('libcrypto.so' in value['path'] for value in libraries), 'Actual OpenSSL runtime closure missing')
    compile_commands = json.loads((build / 'compile_commands.json').read_text())
    expected_cpp = {value['path'] for value in freeze['sources'] if value['path'].endswith('.cpp')}
    s.require({str(Path(row['file']).resolve()) for row in compile_commands} == expected_cpp
              and all(all(flag in row['command'] for flag in ('-O3', '-DNDEBUG', '-std=c++23', '-Werror',
                          '-fno-fast-math', '-ffp-contract=off', '-Wconversion', '-Wsign-conversion'))
                      for row in compile_commands), 'Actual compiled source census/flags differ')
    for value in freeze['sources'] + list(tools.values()) + libraries + [binary]:
        s.check(value)
    closure = unit.directory / 'runtime-closure.json'
    s.fresh(closure, dict(schema='sample-context-runtime-closure/1', freeze=freeze_pin, binary=binary,
            compiler_and_tools=tools, linked_libraries=libraries,
            compile_commands=s.pin(build / 'compile_commands.json'), cache=s.pin(build / 'CMakeCache.txt'),
            compiled_witness=s.pin(build / 'sample_sources.h'), cpp_controls=arithmetic,
            python_tests=12, python_skipped=0, ctest_tests=1, ctest_skipped=0,
            biological_qualification=False))
    unit.complete('engineering', [s.pin(closure), binary, s.pin(unit.directory / 'arithmetic/complete.json')],
                  sources=freeze['sources'], details=dict(qualified=True, native_sam_decode=False, biological_qualification=False))


if __name__ == '__main__':
    main()
