"""Finish the three unexecuted engineering stages after the declared CTest observation fault."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
chain = s.load('sample_engineering_chain_v1', HERE / 'sample-engineering-chain-v1.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    parser.add_argument('--chain-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    s.require(unit.price['phase'] == 'engineering' and unit.price['scientific_work'] is False,
              'Engineering continuation requires its fresh bounded price')
    validator = s.pin(HERE / 'sample-engineering-chain-v1.py')
    s.require(validator['sha256'] == args.chain_sha256, 'Declared continuation validator pin differs')
    original = chain.partial()
    partial_path = unit.directory / 'original-partial.json'
    s.fresh(partial_path, original)
    last_stage = s.read(original['original_stages'][-1])
    actual = s.check(last_stage['raw']['stdout']).read_text()
    negatives = dict(missing_test_name=actual.replace('sample_context_contract_controls', 'other_test'),
                     zero_tests=actual.replace('1/1 Test #1:', '0/0 Test #0:').replace('out of 1', 'out of 0'),
                     skipped=actual.replace('Passed', 'Skipped'))
    rejections = {}
    for name, text in negatives.items():
        try:
            chain.ctest_pass(text)
        except ValueError as error:
            s.require(str(error) == 'CTest must show the named 1/1 Passed test with skipped0',
                      'Unexpected CTest observation control rejection')
            rejections[name] = str(error)
        else:
            raise ValueError('Invalid CTest observation accepted: ' + name)
    controls = unit.directory / 'ctest-observation-controls.json'
    s.fresh(controls, dict(actual_retained_stdout=last_stage['raw']['stdout'], positive=True,
            negative_rejections=rejections, native_command_replayed=False))
    python = unit.stage('sample-python-controls', [str(s.UV), 'run', '--no-sync', 'python', '-m', 'unittest',
                        'discover', '-s', 'tools/sample_context/tests', '-p', 'test_pipeline.py', '-v'])
    python_text = Path(python['raw']['stderr']['path']).read_text()
    s.require('Ran 12 tests' in python_text and python_text.count(' ... ok\n') == 12
              and 'skipped' not in python_text.lower() and python_text.rstrip().endswith('OK'),
              'Python controls must actually execute exactly 12 tests with skipped 0')
    binary = original['built']['sample-context']
    unit.stage('sample-arithmetic', [binary['path'], 'qualify', '--output', unit.directory / 'arithmetic'])
    arithmetic = json.loads((unit.directory / 'arithmetic/result.json').read_text())
    chain.counters(arithmetic)
    linked = unit.stage('sample-linked-libraries', [original['tools']['ldd']['path'], binary['path']])
    libraries = []
    for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
        s.require('not found' not in line, 'Missing runtime library')
        match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
        if match:
            libraries.append(s.pin(match.group(1)))
    s.require(libraries and any('libcrypto.so' in value['path'] for value in libraries), 'Actual OpenSSL runtime closure missing')
    s.require(chain.partial() == original, 'Original partial artifacts changed during continuation')
    for value in libraries + list(original['tools'].values()) + [validator]:
        s.check(value)
    closure = unit.directory / 'runtime-closure.json'
    s.fresh(closure, dict(schema='sample-context-runtime-closure/2',
            qualification_kind='declared_engineering_2_partial_plus_3', original_partial=s.pin(partial_path),
            original_stages=original['original_stages'], continuation_stages=unit.receipts,
            original_failed_outer=chain.OUTER, source_freeze=chain.FREEZE, binary=binary,
            compiler_and_tools=original['tools'], linked_libraries=libraries,
            compile_commands=original['built']['compile_commands.json'], cache=original['built']['CMakeCache.txt'],
            compiled_witness=original['built']['sample_sources.h'], cpp_controls=arithmetic,
            ctest_controls=original['ctest_controls'], python_tests=12, python_skipped=0,
            ctest_tests=1, ctest_skipped=0, build_repeated=False, ctest_repeated=False,
            biological_qualification=False))
    freeze = s.read(chain.FREEZE)
    unit.complete('engineering-continuation', [s.pin(closure), s.pin(partial_path), s.pin(controls), binary,
                  s.pin(unit.directory / 'arithmetic/complete.json')], sources=freeze['sources'] + [validator],
                  details=dict(qualification_kind='declared_engineering_2_partial_plus_3', qualified=True,
                               original_partial=s.pin(partial_path), original_failed_outer=chain.OUTER,
                               original_eight_stages=original['original_stages'], build_repeated=False,
                               ctest_repeated=False, native_sam_decode=False, biological_qualification=False))


if __name__ == '__main__':
    main()
