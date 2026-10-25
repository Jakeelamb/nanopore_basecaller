#!/usr/bin/env python3
"""Coordinate bounded C++ engineering or one frozen prefix-feedback window."""
import argparse
import ast
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import resource
import shlex
import sys
import xml.etree.ElementTree as ET

import location as loc

MODULE = loc.ROOT/'tools/prefix_feedback'
COMPILER = Path('/home/jake/Projects/nanopore_basecaller/software/source-build-qualification-20261023/toolchain-gcc15/usr/bin/g++-15')
COMPILER_SHA = '7c1ff2182981fb185022a8cdd699abaab64b8ea0965e30855754dd95a6c09d15'


def native_sources():
    return [loc.pin((MODULE/name).resolve()) for name in loc.read(MODULE/'native-source-files.json')]


def original_auditor():
    path = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v5/tools/context_decoder/model_observe.py')
    loc.require(loc.pin(path)['sha256'] == 'd20da3f3ce5581504d659917b0ee1cd6d7fce773a66a437c790a195fa0ae1abf',
                'Read-only original outer auditor changed')
    audit = loc.load('causal_native_original_auditor', path)
    loc.require(audit.ROOT == path.parents[2], 'Original auditor ROOT differs')
    return audit


def completed(directory, w, schema):
    value = loc.read(directory/'complete.json')
    loc.require(value['schema'] == schema and value['complete'], 'Prerequisite is incomplete')
    for item in value['sources']+value['files']+[value['attempt']]+value.get('inputs', []):
        loc.check(item)
    for item in value['stages']:
        w.evidence.stage(item, w.c)
    outer = original_auditor().outer_unit(directory.name, loc.pin(directory/'complete.json'), w)
    return value, outer


def runtime(execution, binary):
    stage = execution.stage('prefix-feedback-ldd', ['/usr/bin/ldd', binary])
    text = Path(stage['raw']['stdout']['path']).read_text()
    loc.require('not found' not in text, 'Native runtime dependency missing')
    paths = {match.group(1) for match in re.finditer(r'(?:=>\s+)?(/\S+)\s+\(', text)}
    loc.require(paths, 'Empty native runtime closure')
    return dict(binary=loc.pin(binary), stage=execution.receipts[-1], libraries=[loc.pin(p) for p in sorted(paths)])


def ctest_report(text, stdout):
    report = ET.fromstring(text)
    cases = list(report.iter('testcase'))
    loc.require(report.tag in ('testsuite', 'testsuites') and len(list(report.iter('testsuite'))) == 1
                and len(cases) == 1 and cases[0].get('name') == 'causal_prefix_controls',
                'CTest requires exactly one named native test')
    loc.require(not any(list(report.iter(tag)) for tag in ('failure', 'error', 'skipped'))
                and cases[0].get('status', 'run').lower() in ('run', 'passed')
                and all(int(suite.get('tests', '1')) == 1 and
                        all(int(suite.get(key, '0')) == 0 for key in ('failures', 'errors', 'skipped', 'disabled'))
                        for suite in report.iter('testsuite')),
                'CTest requires actual execution and zero failures/skips')
    loc.require(all(marker in stdout for marker in
                ('"reset_monotonic_commit_controls":true', '"actual_session_input_controls":true',
                 '"independent_state_dependent_rank_comparisons":',
                 '"disabled_exact_bits_and_trace":true', '"strong_private_snv_ins_del":true')),
                'Actual native control JSON markers missing')


def validate_prior_result(result, parent, expected_revision):
    session = result['session']
    loc.require(result['schema'] == 'prefix-feedback-result/1' and result['parent'] == parent
                and result['qname'] == parent+'__H4096' and result['horizon'] == 4096
                and result['encoder_reset'] is True and result['irreversible_commits'] == 0,
                'Prior result parent/horizon/reset differs')
    loc.require(session['schema'] == 'prefix-feedback-session/1' and session['parent'] == parent
                and session['horizon'] == 4096 and session['encoder_reset'] is True
                and session['policy'] == 'bounded_reset_zero_commits'
                and session['revision'] == expected_revision and expected_revision
                and set(expected_revision) <= set('ACGT')
                and session['committed_prefix'] == session['committed_quality'] == '',
                'Prior actual session revision/commitment differs')
    return session


def unittest_summary(text):
    loc.require(re.search(r'(?m)^Ran 10 tests in [0-9.]+s$', text) is not None
                and text.rstrip().endswith('\nOK'),
                'Session/CTest parser controls require10 actual tests and standalone OK')


def reused_python_controls(receipt, w):
    stage_pin = loc.pin(receipt)
    loc.require(stage_pin['sha256'] == '0aada11a637c05254c58ac55afdaa5af1d5858e0ed99d6826824050d3cf359b3',
                'Only the retained successful engineering1 Python stage is admitted for reuse')
    stage = w.evidence.stage(stage_pin, w.c)
    loc.require(stage['argv'] == ['uv', 'run', '--no-sync', 'python', '-m', 'unittest', 'discover',
                '-s', 'tools/prefix_feedback', '-p', 'test_native_unit.py', '-v'], 'Reused Python command differs')
    old_source = loc.ROOT/'logs/context-feedback-program/reviews/causal-python-observer-1/native_unit-before.py'
    loc.require(loc.pin(old_source)['sha256'] == '21b11def966513e98305154c5c46f691e3148d363b8945044e94c00d22f979b4',
                'Tested old observer source archive differs')
    old_unit = loc.ROOT/'results/context-feedback/causal-engineering-1'
    old_cut = loc.read(old_unit/'source-cut.json')
    old_attempt = loc.read(old_unit/'attempt.json')
    for item in old_cut['sources']+old_attempt['sources']:
        if item['path'] == str(Path(__file__).resolve()):
            loc.require(item['sha256'] == loc.pin(old_source)['sha256'] and item['size'] == old_source.stat().st_size,
                        'Old actual source cut does not bind the archived observer')
        else:
            loc.check(item)
    tested = ('ctest_report', 'validate_prior_result')
    trees = [ast.parse(path.read_text()) for path in (old_source, Path(__file__))]
    unchanged = [node.name for node in trees[0].body if isinstance(node, ast.FunctionDef)
                 and node.name not in ('engineer', 'main')]
    for name in unchanged:
        nodes = [next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
                 for tree in trees]
        loc.require(ast.dump(nodes[0], include_attributes=False) == ast.dump(nodes[1], include_attributes=False),
                    'A pre-existing non-observer function changed')
    outer = loc.ROOT/'logs/context-feedback/program-runs/run-causal-engineering-1'
    start, terminal, cleanup = (loc.read(outer/name) for name in ('start.json', 'terminal.json', 'cleanup.json'))
    loc.require(terminal['exit'] == 1 and terminal['error'] is None
                and terminal['proof']['properties']['Result'] == 'exit-code'
                and terminal['proof']['properties']['MainPID'] == terminal['proof']['properties']['ControlPID'] == '0'
                and terminal['proof']['properties']['ActiveState'] in ('failed', 'inactive')
                and cleanup['terminal'] is True, 'Original failed outer/terminal custody differs')
    loc.require(start['worker']['sha256'] == loc.pin(old_source)['sha256']
                and start['cwd'] == str(loc.ROOT) and start['lock'] == str(w.LOCK),
                'Original worker/source/lock identity differs')
    loc.check(start['controller'])
    loc.check(start['recorder'])
    command = start['argv']
    at = command.index('--')
    argv = command[at+3:]
    loc.require(argv[argv.index('python')+1:] == old_attempt['argv']
                and all(item in command for item in ('--property=Type=exec', '--property=ExitType=cgroup',
                    '--property=KillMode=control-group', '--property=CollectMode=inactive',
                    '--property=RuntimeMaxSec=290s', '--property=TimeoutStopSec=1s', '--property=CPUQuota=200%',
                    '--property=MemoryMax=4294967296', '--property=MemorySwapMax=0', '--property=LimitAS=8589934592')),
                'Original actual outer command/caps differ')
    raw = Path((outer/'stdout').read_text().strip())
    names = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')
    raw_pins = [loc.pin(raw/name) for name in names]
    loc.require(shlex.split((raw/'command.sh').read_text()) == argv
                and (raw/'cwd.txt').read_text().strip() == str(loc.ROOT)
                and (raw/'exit-status.txt').read_text().strip() == '1'
                and datetime.fromisoformat((raw/'start.txt').read_text().strip()) <=
                    datetime.fromisoformat((raw/'end.txt').read_text().strip()), 'Original failed raw8 differs')
    times = dict(line.strip().split(': ', 1) for line in (raw/'time.txt').read_text().splitlines()
                 if line.startswith('\t') and ': ' in line)
    loc.require(times['Exit status'] == '1' and times['Command being timed'] == '"'+' '.join(argv)+'"'
                and int(times['Maximum resident set size (kbytes)']) > 0
                and float(times['User time (seconds)']) >= 0 and float(times['System time (seconds)']) >= 0
                and times['Elapsed (wall clock) time (h:mm:ss or m:ss)'],
                'Original failed GNU time status/command/RSS differs')
    loc.require('Session/CTest parser controls require10 actual tests and zero skips' in (raw/'stderr').read_text(),
                'Original failure is not the known summary projection failure')
    kernel = loc.read(old_unit/'kernel-limits.json')
    quota, period = map(int, kernel['values']['cpu.max'].split())
    loc.require(quota <= 2*period and int(kernel['values']['memory.max']) <= 4*1024**3
                and kernel['values']['memory.swap.max'].strip() == '0'
                and kernel['rlimit_as'] == [8*1024**3]*2 and kernel['rlimit_fsize'] == [512*1024**2]*2,
                'Original actual kernel/AS/FSIZE evidence differs')
    policy = kernel['service']['properties']
    loc.require(kernel['service']['exit'] == 0 and policy['ControlGroup'] == kernel['cgroup']
                and policy['Type'] == 'exec' and policy['ExitType'] == 'cgroup'
                and policy['KillMode'] == 'control-group' and policy['CollectMode'] == 'inactive'
                and policy['SendSIGKILL'] == 'yes' and policy['FinalKillSignal'] == '9'
                and 0 < w.supervisor.duration(policy['RuntimeMaxUSec']) <= 300
                and w.supervisor.duration(policy['TimeoutStopUSec']) <= 1,
                'Original live whole-unit hard policy evidence differs')
    text = Path(stage['raw']['stderr']['path']).read_text()
    unittest_summary(text)
    negatives = (text.replace('Ran 10 tests', 'Ran 0 tests'), text.replace('Ran 10 tests', 'Ran 9 tests'),
                 text.rstrip()[:-2]+'OK (skipped=1)\n', text.rstrip()[:-2])
    rejected = 0
    for changed in negatives:
        try:
            unittest_summary(changed)
        except ValueError:
            rejected += 1
    loc.require(rejected == 4, 'Retained-stderr summary rejection control unexpectedly accepted')
    return dict(stage=stage_pin, tested_source=loc.pin(old_source), tested_functions_unchanged=list(tested),
        non_observer_functions_unchanged=unchanged,
        current_observer=loc.pin(__file__), old_parent_attempt=loc.pin(old_unit/'attempt.json'),
        old_source_cut=loc.pin(old_unit/'source-cut.json'), old_kernel=loc.pin(old_unit/'kernel-limits.json'),
        old_outer=[loc.pin(outer/name) for name in ('start.json', 'terminal.json', 'cleanup.json')],
        old_failed_raw8=raw_pins, actual_retained_stderr=stage['raw']['stderr'],
        positive_summary=True, rejected_summary_controls=rejected,
        original_attempt_passed=False, scope='narrow_observation_repair_not_parent_attempt_success')


def packet_values(path):
    lines = Path(path).read_text().splitlines()
    loc.require(lines[0] == 'prefix-feedback-window/1', 'Prior packet schema differs')
    return dict(line.split('\t') for line in lines[1:])


def session_input(args, execution, w, engineering, plan):
    parent = packet_values(plan['packet']['path'])['parent']
    none = dict(path='none', size=0, sha256='0'*64)
    previous, prior_complete, prior_result = dict(horizon=0, revision='', committed_prefix=''), none, none
    binding = dict(policy='bounded_reset_zero_commits', parent=parent, current_horizon=args.horizon,
                   prior=None, genuine_prior_rejection_controls=0)
    if args.horizon == 4096:
        loc.require(args.prior is None, 'H4096 must start from H0 with no prior producer')
    else:
        loc.require(args.horizon == 12288 and args.prior is not None, 'H12288 requires qualified H4096 prior session')
        prior, outer = completed(args.prior, w, 'prefix-feedback-inference/1')
        loc.require(prior['native'] is not None, 'Prior inference has no actual native session; stop this branch')
        loc.check(prior['native'])
        seal = loc.read(prior['native']['path'])
        directory = Path(prior['native']['path']).parent
        result_pin, attempt_pin = loc.pin(directory/'result.json'), loc.pin(directory/'attempt.json')
        actual_attempt = loc.read(attempt_pin['path'])
        stages = [w.evidence.stage(item, w.c) for item in prior['stages']]
        decodes = [item for item in stages if len(item['argv']) > 1 and item['argv'][1] == 'decode']
        loc.require(len(decodes) == 1 and actual_attempt['argv'] == decodes[0]['argv']
                    and loc.read(decodes[0]['raw']['stdout']['path']) == dict(completion=prior['native']),
                    'Prior actual native command/raw completion differs')
        loc.require(seal['sources'] == engineering['compiled_sources']
                    and seal['result_sha256'] == result_pin['sha256']
                    and seal['attempt_sha256'] == attempt_pin['sha256']
                    and actual_attempt['binary']['sha256'] == engineering['binary']['sha256']
                    and actual_attempt['binary']['path'] == engineering['binary']['path'],
                    'Prior source/binary/native result binding differs')
        prior_work = loc.read(args.prior/'work-price.json')
        loc.require(prior_work['prepared'] == loc.pin(args.prepared/'complete.json')
                    and prior_work['plan']['horizon'] == 4096
                    and prior_work['engineering'] == loc.pin(args.engineering/'complete.json'),
                    'Prior prepared/engineering/horizon receipt differs')
        prior_packet = prior_work['plan']['packet']
        loc.check(prior_packet)
        fields = packet_values(prior_packet['path'])
        row = loc.native(fields['native_path'], 4096)
        prior_result_value = loc.read(result_pin['path'])
        begin, end = int(fields['core_begin']), int(fields['core_end'])
        expected_revision = row['sequence'][:begin]+prior_result_value['partial_search']['selected']['sequence']+row['sequence'][end:]
        previous = validate_prior_result(prior_result_value, parent, expected_revision)
        rejected = 0
        for fault in ('horizon', 'parent', 'revision', 'commitment'):
            changed = copy.deepcopy(prior_result_value)
            if fault == 'horizon':
                changed['horizon'] = changed['session']['horizon'] = 12288
            elif fault == 'parent':
                changed['parent'] = changed['session']['parent'] = '00000000-0000-0000-0000-000000000000'
            elif fault == 'revision':
                changed['session']['revision'] = 'T' if expected_revision != 'T' else 'A'
            else:
                changed['session']['committed_prefix'], changed['session']['committed_quality'] = expected_revision[:1], '!'
            try:
                validate_prior_result(changed, parent, expected_revision)
            except ValueError:
                rejected += 1
        loc.require(rejected == 4, 'Genuine prior-session rejection control unexpectedly accepted')
        prior_complete, prior_result = loc.pin(args.prior/'complete.json'), result_pin
        binding.update(prior=prior_complete, native=prior['native'], result=result_pin, attempt=attempt_pin,
                       binary=engineering['binary'], compiled_sources=engineering['compiled_sources'],
                       outer=outer, stages=prior['stages'], genuine_prior_rejection_controls=rejected)
    loc.fresh(args.output/'prior-binding.json', binding)
    values = dict(parent=parent, previous_horizon=previous['horizon'], previous_revision=previous['revision'],
                  committed_prefix=previous['committed_prefix'], current_horizon=args.horizon,
                  encoder_reset=1, policy='bounded_reset_zero_commits')
    for key, value in dict(prior_complete=prior_complete, prior_result=prior_result,
                           prior_binding=loc.pin(args.output/'prior-binding.json')).items():
        values.update({key+'_'+name: item for name, item in value.items()})
    path = args.output/'session.tsv'
    with path.open('x') as stream:
        stream.write('prefix-feedback-session-input/1\n')
        for key, value in sorted(values.items()):
            loc.require('\t' not in str(value) and '\n' not in str(value), 'Invalid session field')
            stream.write(key+'\t'+str(value)+'\n')
        stream.flush()
        loc.os.fsync(stream.fileno())
    loc.sync_directory(path.parent)
    return loc.pin(path)


def format_only(args, execution, source):
    before = native_sources()
    formatter = Path('/usr/bin/clang-format')
    owned = [item['path'] for item in before if Path(item['path']).is_relative_to(MODULE)
             and Path(item['path']).suffix in ('.h', '.cpp')]
    loc.require(owned, 'Owned formatter census empty')
    loc.fresh(args.output/'format-input.json', dict(sources=before, formatter=loc.pin(formatter)))
    execution.stage('prefix-feedback-format-owned', [formatter, '-i', *owned])
    # Format is an explicitly recorded source mutation before the compiled source cut.
    after = native_sources()
    execution.pins = source+after
    loc.fresh(args.output/'source-cut.json', dict(sources=after, compiler=loc.pin(COMPILER), formatter=loc.pin(formatter)))
    return dict(compiled_sources=after,
                files=[loc.pin(args.output/name) for name in ('format-input.json', 'source-cut.json')])


def engineer(args, execution, w, source):
    loc.require(args.freeze is not None, 'Engineering requires a separately reviewed format-only source cut')
    frozen, outer = completed(args.freeze, w, 'prefix-feedback-format/1')
    after = native_sources()
    loc.require(frozen['compiled_sources'] == after, 'Frozen format-only source cut changed')
    execution.pins = source+after
    loc.fresh(args.output/'source-cut.json', dict(sources=after, format_complete=loc.pin(args.freeze/'complete.json'),
                                                format_outer=outer))
    loc.require(loc.pin(COMPILER)['sha256'] == COMPILER_SHA, 'Pinned GCC15 changed')
    if args.python_controls is None:
        python_tests = execution.stage('prefix-feedback-session-controls', ['uv', 'run', '--no-sync', 'python',
            '-m', 'unittest', 'discover', '-s', 'tools/prefix_feedback', '-p', 'test_native_unit.py', '-v'])
        unittest_summary(Path(python_tests['raw']['stderr']['path']).read_text())
        python_evidence = dict(stage=execution.receipts[-1], reused=False)
    else:
        python_evidence = reused_python_controls(args.python_controls, w)
    loc.fresh(args.output/'python-controls.json', python_evidence)
    build = args.output/'build'
    execution.stage('prefix-feedback-compiler', [COMPILER, '--version'])
    execution.stage('prefix-feedback-configure', ['cmake', '-S', MODULE, '-B', build,
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=ON', '-DCMAKE_CXX_COMPILER='+str(COMPILER)])
    execution.stage('prefix-feedback-build', ['cmake', '--build', build, '--parallel', '2'])
    execution.stage('prefix-feedback-format-check', ['cmake', '--build', build, '--target', 'format-check', '--parallel', '1'])
    tests = execution.stage('prefix-feedback-ctest', ['ctest', '--test-dir', build, '-V', '--parallel', '1',
                                                    '--output-junit', build/'ctest.xml'])
    stdout = Path(tests['raw']['stdout']['path']).read_text()
    ctest_report((build/'ctest.xml').read_text(), stdout)
    commands = loc.read(build/'compile_commands.json')
    expected_sources = {str((MODULE/name).resolve()) for name in
                        ('src/feedback.cpp', 'src/main.cpp', 'tests/main.cpp', 'tests/controls.cpp',
                         '../context_decoder/src/decoder.cpp', '../context_decoder/src/guarded.cpp',
                         '../context_decoder/src/io.cpp', '../context_decoder/tests/guarded_controls.cpp')}
    loc.require({str(Path(item['file']).resolve()) for item in commands} == expected_sources,
                'Actual compile source census differs')
    for item in commands:
        loc.require(all(flag in item['command'].split() for flag in
                    ('-O3', '-DNDEBUG', '-std=c++23', '-Wall', '-Wextra', '-Wpedantic', '-Wconversion',
                     '-Wsign-conversion', '-Wshadow', '-Werror', '-fno-fast-math', '-ffp-contract=off')),
                    'Actual strict C++23 Release flags differ')
    closure = runtime(execution, build/'prefix-feedback')
    test_closure = runtime(execution, build/'prefix-feedback-tests')
    evidence = dict(compiler=loc.pin(COMPILER), compiler_sha256=COMPILER_SHA,
                    cache=loc.pin(build/'CMakeCache.txt'), compile_commands=loc.pin(build/'compile_commands.json'),
                    links=[loc.pin(build/'CMakeFiles'/name/'link.txt') for name in
                           ('prefix-feedback.dir', 'prefix-feedback-tests.dir', 'prefix_feedback.dir')],
                    runtime=closure, test_runtime=test_closure, sources=after,
                    generated_witness=loc.pin(build/'compiled_sources.h'))
    evidence['ctest_junit'] = loc.pin(build/'ctest.xml')
    loc.fresh(args.output/'build-closure.json', evidence)
    return dict(binary=loc.pin(build/'prefix-feedback'), compiled_sources=after,
                files=[loc.pin(args.output/name) for name in ('source-cut.json', 'python-controls.json', 'build-closure.json')])


def infer(args, execution, w):
    loc.require(args.engineering is not None and args.prepared is not None and args.horizon in loc.HORIZONS,
                'Inference requires engineering, prepared and one admitted horizon')
    engineering, engineering_outer = completed(args.engineering, w, 'prefix-feedback-engineering/1')
    prepared, prepared_outer = completed(args.prepared, w, 'prefix-feedback-prepared/1')
    loc.check(engineering['binary'])
    for item in engineering['compiled_sources']:
        loc.check(item)
    plans = loc.read(args.prepared/'plans.json')
    selected = [plan for plan in plans['plans'] if plan['horizon'] == args.horizon]
    loc.require(len(selected) == 1, 'Prepared horizon census differs')
    plan = selected[0]
    loc.fresh(args.output/'work-price.json', dict(plan=plan, engineering=loc.pin(args.engineering/'complete.json'),
               prepared=loc.pin(args.prepared/'complete.json'), engineering_outer=engineering_outer,
               prepared_outer=prepared_outer, truth_imported=False))
    if plan['selection']['status'] != 'selected':
        loc.fresh(args.output/'result.json', dict(status='abstained', reason=plan['selection']['reason']))
        return dict(files=[loc.pin(args.output/name) for name in ('work-price.json', 'result.json')], native=None)
    loc.check(plan['packet'])
    session = session_input(args, execution, w, engineering, plan)
    price = plan['work_price']
    loc.require(price['hard_rows'] <= 128 and price['beam_width'] == 64 and price['maximum_center'] == 64,
                'Undeclared native work price')
    closure = runtime(execution, engineering['binary']['path'])
    stage = execution.stage('prefix-feedback-decode-H'+str(args.horizon), [engineering['binary']['path'],
        'decode', '--packet', plan['packet']['path'], '--packet-sha256', plan['packet']['sha256'],
        '--session', session['path'], '--session-sha256', session['sha256'],
        '--output', args.output/'native'])
    reported = loc.read(stage['raw']['stdout']['path'])
    loc.require(reported == dict(completion=loc.pin(args.output/'native/complete.json')), 'Native raw completion differs')
    seal = loc.read(args.output/'native/complete.json')
    loc.require(seal['schema'] == 'prefix-feedback-complete/1' and seal['complete']
                and seal['sources'] == engineering['compiled_sources']
                and seal['result_sha256'] == loc.pin(args.output/'native/result.json')['sha256']
                and seal['attempt_sha256'] == loc.pin(args.output/'native/attempt.json')['sha256'],
                'Native closure differs')
    attempt = loc.read(args.output/'native/attempt.json')
    loc.require(attempt['argv'] == stage['argv'] and attempt['binary']['sha256'] == engineering['binary']['sha256'],
                'Native actual command/binary differs')
    loc.fresh(args.output/'runtime-libraries.json', closure)
    return dict(files=[loc.pin(args.output/name) for name in
                       ('work-price.json', 'prior-binding.json', 'session.tsv', 'runtime-libraries.json',
                        'native/attempt.json', 'native/result.json', 'native/complete.json')],
                native=loc.pin(args.output/'native/complete.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('format', 'engineer', 'infer'))
    parser.add_argument('--admission-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engineering', type=Path)
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--horizon', type=int)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--prior', type=Path)
    parser.add_argument('--python-controls', type=Path)
    args = parser.parse_args()
    loc.require(re.fullmatch('[A-Za-z0-9_-]{1,80}', args.admission_id), 'Unsafe unit identity')
    args.output = args.output.resolve()
    loc.require(args.output.is_relative_to(loc.ROOT/'results/context-feedback'), 'Output outside owned results')
    args.output.mkdir()
    w = loc.load('causal_native_execution', loc.ROOT/'scripts/context-feedback.py')
    source = loc.sources()+[loc.pin(__file__), loc.pin(MODULE/'prepare.py'), loc.pin(w.__file__)]
    now = datetime.now(timezone.utc)
    grant = dict(id=args.admission_id, maximum_wall_seconds=280,
                 expires_utc=(now+timedelta(seconds=280)).isoformat(), cpu_quota=2,
                 memory_bytes=4*1024**3, address_space_bytes=8*1024**3, swap_bytes=0,
                 maximum_output_bytes=512*1024**2,
                 cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-'+args.admission_id+'.service')
    loc.fresh(args.output/'attempt.json', dict(argv=sys.argv, sources=source, grant=grant, truth_imported=False))
    w.cgroup_limits(grant)
    directory = Path('/sys/fs/cgroup')/grant['cgroup'].lstrip('/')
    loc.fresh(args.output/'kernel-limits.json', dict(cgroup=grant['cgroup'], values={name: (directory/name).read_text()
        for name in ('cpu.max', 'memory.max', 'memory.swap.max')}, rlimit_as=resource.getrlimit(resource.RLIMIT_AS),
        rlimit_fsize=resource.getrlimit(resource.RLIMIT_FSIZE), service=w.supervisor.show('context-'+args.admission_id+'.service')))
    execution = w.Execution(grant, args.output, source)
    if args.phase == 'format':
        result = format_only(args, execution, source)
    elif args.phase == 'engineer':
        result = engineer(args, execution, w, source)
    else:
        result = infer(args, execution, w)
    execution.budget()
    label = {'format': 'format', 'engineer': 'engineering', 'infer': 'inference'}[args.phase]
    loc.fresh(args.output/'complete.json', dict(schema='prefix-feedback-'+label+'/1',
        complete=True, sources=source, attempt=loc.pin(args.output/'attempt.json'),
        stages=execution.receipts, files=[loc.pin(args.output/'kernel-limits.json')]+result.pop('files'), **result,
        biological_qualification=False, streaming_state_continuity=False, irreversible_commits=0))
    print(loc.json.dumps(dict(completion=loc.pin(args.output/'complete.json'))))


if __name__ == '__main__':
    main()
