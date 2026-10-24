#!/usr/bin/env python3
"""Coordinate source-bound C++ context decoding after explicit CPU admission."""
import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import re
import shlex
import signal
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_input_boundary', ROOT / 'tools/context_decoder/context_inputs.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
_guard_spec = importlib.util.spec_from_file_location('context_process_guard', ROOT / 'tools/context_decoder/process_guard.py')
pg = importlib.util.module_from_spec(_guard_spec)
_guard_spec.loader.exec_module(pg)
_supervisor_spec = importlib.util.spec_from_file_location('context_process_supervisor', ROOT / 'tools/context_decoder/process_supervisor.py')
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)
_evidence_spec = importlib.util.spec_from_file_location('context_phase_evidence', ROOT / 'tools/context_decoder/evidence.py')
evidence = importlib.util.module_from_spec(_evidence_spec)
_evidence_spec.loader.exec_module(evidence)
LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')
RESULTS = ROOT / 'results/context-feedback'
LOGS = ROOT / 'logs/context-feedback'
BUILD = RESULTS / 'build'
BINARY = BUILD / 'context-decoder'
CPP = ('include/context_decoder/decoder.h', 'include/context_decoder/io.h', 'include/context_decoder/controls.h',
       'include/context_decoder/guarded.h', 'include/context_decoder/guarded_io.h',
       'src/decoder.cpp', 'src/io.cpp', 'src/json.cpp', 'src/main.cpp', 'src/guarded.cpp', 'src/guarded_io.cpp',
       'tests/controls.cpp', 'tests/main.cpp', 'tests/guarded_controls.cpp')


def sources():
    paths = [ROOT / 'tools/context_decoder' / p for p in (*CPP, 'CMakeLists.txt', '.clang-format', 'context_inputs.py',
              'verify_formatter.cmake', 'process_guard.py', 'process_supervisor.py', 'process-guard-provenance.json', 'evidence.py', 'guarded_inputs.py', 'private_inputs.py', 'private-context-registry.json')]
    paths += [ROOT / p for p in ('scripts/context-feedback.py', 'config/context-feedback-dev-v1.json',
                                'config/context-feedback-dev-v2.json', 'tests/test_context_feedback.py', 'tests/test_context_feedback_v2.py', 'scripts/record-command.sh')]
    paths.append(Path('/home/jake/Projects/nanopore_basecaller-retrieval/tools/catalogue_bridge/verify-receipt.py'))
    return [c.pin(p) for p in sorted(paths)]


def inventory_hash(pins):
    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def configuration(path):
    value = c.read(path)
    if value['schema'] == 'context-feedback-config/2':
        c.require(set(value) == {'schema','role','scope','inputs','policy','qualification_queries','checkpoint_queries','full_queries','execution'}, 'Unknown guarded config field')
        c.require(value['role'] == 'development' and set(value['inputs']) == {'legacy_inputs_config'}, 'Unknown guarded inference inputs')
        c.check(value['inputs']['legacy_inputs_config'])
        c.require(value['policy'] == dict(beam_width=128,min_center=0,max_center=108,context_weight=.5,
                  maximum_signal_deficit=.5,minimum_objective_margin=.5,minimum_mapq=30,anchor_bases=10,
                  future_bases=10,tie_rule='native then lexical center'), 'Frozen guarded policy differs')
        c.require(value['qualification_queries']==[0] and value['checkpoint_queries']==list(range(32))
                  and value['full_queries']==list(range(451)), 'Guarded query census differs')
        c.require(value['execution']['canonical_lock']==str(LOCK) and value['execution']['requires_external_admission'] is True
                  and value['execution']['default_admission'] is None, 'Guarded intake policy differs')
        return value
    c.require(set(value) == {'schema', 'role', 'scope', 'inputs', 'policy', 'qualification_queries',
                            'checkpoint_queries', 'execution'}, 'Unknown config inference field')
    c.require(value['schema'] == 'context-feedback-config/1' and value['role'] == 'development', 'Development config required')
    c.require(set(value['policy']) == {'beam_width', 'max_symbols', 'min_symbols', 'context_weight',
               'maximum_signal_deficit', 'minimum_objective_margin', 'minimum_mapq', 'tie_rule',
               'context_formula', 'escape_rule', 'beam_pruning'}, 'Unknown policy inference field')
    c.require(set(value['inputs']) == {'handoff', 'handoff_sha256', 'package', 'admission_receipt',
              'original_cohort_sha256', 'plan_sha256', 'mapped_sam_sha256', 'query0'}, 'Unknown input inference field')
    c.require(set(value['inputs']['query0']) == {'query_index', 'parent', 'tensor', 'tensor_sha256',
              'tensor_size', 'timesteps', 'interpretation'}, 'Unknown query inference field')
    c.require(value['qualification_queries'] == [0] and value['checkpoint_queries'] == list(range(32)), 'Frozen query census changed')
    c.require(value['execution']['requires_external_admission'] is True
              and value['execution']['default_admission'] is None
              and value['execution']['canonical_lock'] == str(LOCK), 'Canonical source-only policy changed')
    return value


def admission(path, config_path, phase, output, now=None):
    c.require(path is not None, 'SOURCE ONLY: explicit fresh admission is required before any execution')
    value = c.read(path)
    required = {'schema', 'id', 'phase', 'config', 'source_inventory_sha256', 'output', 'not_before_utc',
                'expires_utc', 'maximum_wall_seconds', 'maximum_output_bytes', 'address_space_bytes',
                'memory_bytes', 'swap_bytes', 'cpu_quota', 'cgroup'}
    c.require(set(value) == required and value['schema'] == 'context-feedback-admission/1', 'Admission schema')
    c.require(value['phase'] == phase and value['config'] == c.pin(config_path)
              and value['source_inventory_sha256'] == inventory_hash(sources())
              and value['output'] == str(Path(output).resolve()), 'Stale or unrelated source/output admission')
    current = now or datetime.now(timezone.utc)
    start = datetime.fromisoformat(value['not_before_utc'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(value['expires_utc'].replace('Z', '+00:00'))
    c.require(start <= current < end and 0 < (end - start).total_seconds() <= 300, 'Expired or unbounded admission')
    c.require(0 < value['maximum_wall_seconds'] <= 300 and 0 < value['maximum_output_bytes'] <= 4 * 1024**3
              and 0 < value['address_space_bytes'] <= 8 * 1024**3 and 0 < value['memory_bytes'] <= 4 * 1024**3
              and value['swap_bytes'] == 0 and 0 < value['cpu_quota'] <= 2, 'Admission exceeds proposed resource caps')
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['id']) is not None, 'Unsafe admission identity')
    return value


def cgroup_limits(grant):
    entries = Path('/proc/self/cgroup').read_text().splitlines()
    unified = next(line.split(':', 2)[2] for line in entries if line.startswith('0::'))
    c.require(unified == grant['cgroup'], 'Execution is outside the admitted cgroup')
    directory = Path('/sys/fs/cgroup') / unified.lstrip('/')
    quota, period = (directory / 'cpu.max').read_text().split()
    c.require(quota != 'max' and int(quota) <= grant['cpu_quota'] * int(period), 'CPU quota is not enforced')
    memory = (directory / 'memory.max').read_text().strip()
    swap = (directory / 'memory.swap.max').read_text().strip()
    c.require(memory != 'max' and int(memory) <= grant['memory_bytes'] and swap == '0', 'Kernel memory/swap caps are not enforced')
    resource.setrlimit(resource.RLIMIT_AS, (grant['address_space_bytes'], grant['address_space_bytes']))
    resource.setrlimit(resource.RLIMIT_FSIZE, (grant['maximum_output_bytes'], grant['maximum_output_bytes']))


def owned_bytes():
    return sum(p.stat().st_size for directory in (RESULTS, LOGS) if directory.exists()
               for p in directory.rglob('*') if p.is_file() and not p.is_symlink())


class Execution:
    def __init__(self, grant, output, pins):
        self.grant = grant
        self.started = time.monotonic()
        self.deadline = min(self.started + grant['maximum_wall_seconds'], self.started +
                            (datetime.fromisoformat(grant['expires_utc'].replace('Z', '+00:00')) - datetime.now(timezone.utc)).total_seconds())
        self.output = Path(output).resolve()
        self.pins = pins
        self.receipts = []
        self.binary = BINARY

    def budget(self):
        c.require(time.monotonic() < self.deadline, 'CPU admission boundary reached')
        c.require(owned_bytes() <= self.grant['maximum_output_bytes'], 'Owned-output cap reached')
        c.require(__import__('shutil').disk_usage(ROOT).free >= 30 * 1024**3, '30 GiB disk reserve reached')
        for p in self.pins:
            c.check(p)

    def stage(self, name, argv, env=None):
        self.budget()
        runner_root = LOGS / 'recorder-root'
        (runner_root / 'scripts').mkdir(parents=True, exist_ok=True)
        (runner_root / 'logs').mkdir(exist_ok=True)
        recorder = runner_root / 'scripts/record-command.sh'
        if not recorder.exists():
            recorder.symlink_to(ROOT / 'scripts/record-command.sh')
        c.require(recorder.resolve() == ROOT / 'scripts/record-command.sh', 'Maintained recorder alias changed')
        argv = list(map(str, argv))
        environment = dict(os.environ)
        if env:
            environment.update(env)
        launcher = LOGS / (name + '-' + uuid.uuid4().hex[:12])
        launcher.mkdir()
        c.fresh(launcher / 'launch.json', dict(argv=[str(recorder), name, *argv], cwd=str(ROOT),
                                             explicit_env=env or {}, admission=self.grant))
        started = datetime.now(timezone.utc).isoformat()
        previous_runs = set((runner_root / 'logs').iterdir())
        failure = None
        process = None
        cleanup = None
        try:
            with (launcher / 'stdout').open('xb') as stdout, (launcher / 'stderr').open('xb') as stderr:
                process = subprocess.Popen([str(recorder), name, *argv], cwd=ROOT, env=environment,
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                while process.poll() is None:
                    time.sleep(0.1)
                    self.budget()
        except BaseException as error:
            failure = type(error).__name__ + ': ' + str(error)
        finally:
            if process is not None:
                retry = 0
                while cleanup is None:
                    try:
                        cleanup = pg.stop_group(process, process.pid)
                    except BaseException as error:
                        retry += 1
                        c.fresh(launcher / ('cleanup-error-' + str(retry) + '.json'),
                                dict(error=repr(error), whole_unit_supervisor_retains_custody=True))
                c.fresh(launcher / 'group-cleanup.json', cleanup)
            status = None if process is None else process.returncode
            ended = datetime.now(timezone.utc).isoformat()
            c.fresh(launcher / 'terminal.json', dict(argv=argv, started_utc=started, ended_utc=ended,
                    exit=status, failure=failure, owned_group_cleanup=cleanup,
                    note='Durable execution observation written before raw evidence projection'))
        value = dict(schema='context-feedback-stage/1', name=name, argv=argv, start_utc=started, end_utc=ended,
                     exit=status, launcher=str(launcher), admission_id=self.grant['id'], failure=failure,
                     terminal=c.pin(launcher / 'terminal.json'),
                     group_cleanup=None if cleanup is None else c.pin(launcher / 'group-cleanup.json'),
                     projection_error=None)
        try:
            path = (launcher / 'stdout').read_text().strip()
            if not path:
                created = set((runner_root / 'logs').iterdir()) - previous_runs
                if len(created) == 1:
                    path = str(next(iter(created)))
            if path and Path(path).is_dir():
                raw = Path(path)
                required = ['command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt']
                value['raw'] = {name: c.pin(raw / name) for name in required if (raw / name).is_file()}
                value['missing_raw'] = [name for name in required if name not in value['raw']]
                if status == 0 and failure is None:
                    c.require(not value['missing_raw'], 'Successful command lacks raw recorder files')
                    c.require(shlex.split((raw / 'command.sh').read_text()) == argv, 'Recorded command mismatch')
                    c.require((raw / 'cwd.txt').read_text().strip() == str(ROOT), 'Recorded cwd mismatch')
                    c.require(int((raw / 'exit-status.txt').read_text()) == status, 'Recorded exit mismatch')
            else:
                c.require(status != 0 or failure is not None, 'Successful producer lacks recorder directory')
        except BaseException as error:
            value['projection_error'] = type(error).__name__ + ': ' + str(error)
        c.fresh(launcher / 'finish.json', value)
        self.receipts.append(c.pin(launcher / 'finish.json'))
        c.require(status == 0 and failure is None and value['projection_error'] is None,
                  'Stage failed: ' + name + '; retained at ' + str(launcher))
        c.require('raw' in value, 'Successful command lacks complete raw recorder')
        self.budget()
        return value

    def decode(self, frame, target, policy):
        if 'max_center' in policy:
            argv = [self.binary, 'decode-guarded', '--frame', frame['path'], '--frame-sha256', frame['sha256'], '--output', target,
                    '--beam', str(policy['beam_width']), '--min-center',str(policy['min_center']), '--max-center',str(policy['max_center']),
                    '--weight',repr(policy['context_weight']), '--deficit',repr(policy['maximum_signal_deficit']), '--margin',repr(policy['minimum_objective_margin'])]
        else:
            argv = [self.binary, 'decode', '--frame', frame['path'], '--frame-sha256', frame['sha256'], '--output', target,
                '--beam', str(policy['beam_width']), '--min-symbols', str(policy['min_symbols']),
                '--max-symbols', str(policy['max_symbols']), '--weight', repr(policy['context_weight']),
                    '--deficit', repr(policy['maximum_signal_deficit']), '--margin', repr(policy['minimum_objective_margin'])]
        produced = self.stage('frame-decode', argv)
        stdout = c.read(produced['raw']['stdout']['path'])
        c.check(stdout['completion'])
        c.require(stdout['completion'] == c.pin(Path(target) / 'complete.json'), 'Native completion stdout differs')
        seal = c.read(stdout['completion']['path'])
        c.require(seal['complete'] is True, 'Incomplete native frame')
        for p in seal['files']:
            c.check(p)
        return dict(completion=stdout['completion'], receipt=self.receipts[-1])


def guarded_data(execution, phase, config, qualification, query0, checkpoint):
    modules = {}
    for name in ('guarded_inputs','private_inputs'):
        module_spec = importlib.util.spec_from_file_location(name, ROOT/'tools/context_decoder'/(name+'.py'))
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        modules[name] = module
    g, p = modules['guarded_inputs'], modules['private_inputs']
    c.require(qualification is not None, 'Guarded qualification is required')
    identity = inventory_hash(execution.pins)
    qualified = evidence.completed(qualification,'qualify',identity,c)
    execution.binary = Path(qualified['binary']['path'])
    prerequisites = [qualified]
    reused = {}
    if phase in ('checkpoint','full'):
        previous_path, previous_phase = (query0,'query0') if phase == 'checkpoint' else (checkpoint,'checkpoint')
        c.require(previous_path is not None, 'Successful preceding guarded checkpoint required')
        previous = evidence.completed(previous_path,previous_phase,identity,c)
        c.require(previous['binary'] == qualified['binary'], 'Guarded checkpoint binary differs')
        prerequisites.append(previous)
        reused = {x['query_index']:x for x in c.read(Path(previous_path)/'summary.json')['outcomes']}
    legacy_path = c.check(config['inputs']['legacy_inputs_config'])['path']
    legacy = configuration(legacy_path)
    ordinary = c.inputs(legacy)
    private = p.load_private(ordinary) if phase == 'private' else None
    admitted = ordinary if private is None else private
    cases = (list(range(40)) if private is not None else config['full_queries'] if phase=='full'
             else config['qualification_queries'] if phase=='query0' else config['checkpoint_queries'])
    directory = execution.output
    (directory/'base-frames').mkdir()
    (directory/'frames').mkdir()
    outcomes = []
    for query in cases:
        execution.budget()
        if query in reused:
            outcomes.append(dict(reused[query],reused=True))
            continue
        window = admitted['plan'][query]
        base = (c.build_frame(legacy,admitted,query,directory/'base-frames'/str(query)) if private is None
                else p.build_base(private,query,directory/'base-frames'/str(query)))
        for mode in (('ordinary',) if private is None else ('ordinary','withheld')):
            if base['status']=='original_excluded':
                outcomes.append(dict(base,context_mode=mode))
                continue
            if private is not None and mode=='withheld' and query not in private['allowed_walk_hashes']:
                outcomes.append(dict(query_index=query,read_id=window['read_id'],context_mode=mode,
                                     status='challenge_excluded',reason='archived challenge ambiguity'))
                continue
            allowed = None if mode=='ordinary' else private['allowed_walk_hashes'][query]
            frame = g.construct(base,window,admitted['receipts'][query],admitted['graph'][query],
                                directory/'frames'/(mode+'-'+str(query)),allowed)
            frame['context_mode'] = mode
            if frame['status']=='constructed':
                frame['native'] = execution.decode(frame['frame'],directory/('decoded-'+mode+'-'+str(query)),config['policy'])
            outcomes.append(frame)
    if private is None:
        indexed = {row['query_index']:row for row in outcomes}
        inventory = []
        for query,decision in sorted(admitted['decisions'].items()):
            if decision['status']=='excluded':
                inventory.append(dict(query_index=query,read_id=decision['read_id'],status='original_excluded',original_decision=decision))
            else:
                inventory.append(indexed.get(query,dict(query_index=query,read_id=decision['read_id'],status='not_selected')))
        c.require(len(inventory)==451 and sum(x['status']=='original_excluded' for x in inventory)==120,
                  'Guarded original plan/exclusion census differs')
        c.require([x['query_index'] for x in outcomes]==cases, 'Guarded selected query census differs')
        selection = dict(planned=451,original_excluded=120,selected_queries=cases)
    else:
        inventory = outcomes
        c.require(len(outcomes)==80 and sum(x['status']=='original_excluded' for x in outcomes)==18
                  and sum(x['status']=='challenge_excluded' for x in outcomes)==5, 'Private mode census differs')
        selection = dict(private['selection_counts'],attachment_exclusions=private['attachment_exclusions'],
                         scoring_exclusions=private['scoring_exclusions'],challenge_exclusions=private['challenge_exclusions'],
                         namespace=private['namespace'],sources=private['source_pins'])
    c.fresh(directory/'inventory.json',dict(schema='guarded-inventory/2',rows=inventory,selection=selection))
    c.fresh(directory/'summary.json',dict(schema='context-feedback-unit/2',phase=phase,role='development',scope=config['scope'],
            outcomes=outcomes,full_inventory=c.pin(directory/'inventory.json'),original_exclusions_retained=True,
            selection=selection,admissible_candidate=False,no_biological_improvement_claim=True,
            resource_caps=execution.grant,binary=c.pin(execution.binary),sources=execution.pins,stages=execution.receipts))
    execution.budget()
    c.fresh(directory/'complete.json',dict(schema='context-feedback-complete/1',complete=True,phase=phase,
            source_inventory_sha256=identity,binary=c.pin(execution.binary),prerequisites=prerequisites,
            files=[c.pin(directory/name) for name in ('start.json','summary.json','inventory.json')],stages=execution.receipts))
    descriptor=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(json.dumps(dict(completion=c.pin(directory/'complete.json'))))


def run(phase, config_path, output, admission_path, qualification=None, query0=None, worker_intake=None, checkpoint=None):
    if worker_intake is None:
        return supervisor.supervise(phase, config_path, output, admission_path, qualification, query0, c, pg, checkpoint)
    config_path = Path(config_path).resolve()
    config = configuration(config_path)
    grant = admission(admission_path, config_path, phase, output)
    c.require(Path(output).resolve().is_relative_to(RESULTS) and Path(output).resolve() != BUILD,
              'Output must stay in the isolated context-feedback result tree')
    cgroup_limits(grant)
    supervisor.worker_intake(worker_intake, grant, c)
    pg.adopt_orphans()
    LOGS.mkdir(parents=True, exist_ok=True)
    claim = LOGS / ('admission-' + grant['id'] + '.json')
    c.fresh(claim, dict(admission=c.pin(admission_path), argv=sys.argv, entered_utc=datetime.now(timezone.utc).isoformat()))
    with contextlib.nullcontext():
        RESULTS.mkdir(parents=True, exist_ok=True)
        directory = Path(output).resolve()
        directory.mkdir()
        execution = Execution(grant, directory, sources())
        prerequisites = []
        execution.budget()
        c.fresh(directory / 'start.json', dict(config=c.pin(config_path), source_pins=execution.pins,
                admission=c.pin(admission_path), scope=config['scope'], location_overlap='caller-reference explicitly cleared',
                qualification=None if qualification is None else str(qualification)))
        if config['schema']=='context-feedback-config/2' and phase!='qualify':
            return guarded_data(execution,phase,config,qualification,query0,checkpoint)
        if phase == 'qualify':
            flags = '-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off'
            execution.stage('cmake-configure', ['cmake', '-S', ROOT / 'tools/context_decoder', '-B', BUILD,
                            '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=ON', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                            '-DCMAKE_CXX_FLAGS=' + flags])
            execution.stage('cmake-build', ['cmake', '--build', BUILD, '--parallel', '2'])
            execution.binary = directory / 'context-decoder'
            shutil.copyfile(BINARY, execution.binary)
            execution.binary.chmod(0o555)
            execution.stage('format-check', ['cmake', '--build', BUILD, '--target', 'format-check', '--parallel', '1'])
            execution.stage('ctest', ['ctest', '--test-dir', BUILD, '--output-on-failure', '--parallel', '1'])
            python_stage = execution.stage('python-controls', ['uv', 'run', '--no-sync', 'python', '-m', 'unittest', 'test_context_feedback', 'test_context_feedback_v2', '-v'],
                            dict(PYTHONPATH=str(ROOT / 'tests'), CONTEXT_DECODER_BINARY=str(execution.binary)))
            python_evidence = Path(python_stage['raw']['stderr']['path']).read_text()
            c.require('Ran 31 tests' in python_evidence and 'skipped' not in python_evidence.lower()
                      and python_evidence.count(' ... ok\n') == 31, 'Required consumed-frame controls did not all execute with skipped0')
            execution.stage('native-controls', [execution.binary, 'qualify', '--output', directory / 'arithmetic'])
            linked = execution.stage('linked-runtime', ['ldd', execution.binary])
            libraries = []
            for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
                for item in line.split():
                    if item.startswith('/') and Path(item).is_file():
                        libraries.append(c.pin(item))
            c.require(libraries, 'Actual linked runtime library inventory is empty')
            cache = (BUILD / 'CMakeCache.txt').read_text().splitlines()
            compiler = next(line.split('=', 1)[1] for line in cache if line.startswith('CMAKE_CXX_COMPILER:FILEPATH='))
            compile_commands = c.read(BUILD / 'compile_commands.json')
            for entry in compile_commands:
                for required_flag in ('-std=c++23', '-fno-fast-math', '-ffp-contract=off', '-Werror'):
                    c.require(required_flag in entry['command'], 'Missing required compile option')
            c.fresh(directory / 'build-closure.json', dict(compiler=c.pin(compiler),
                    cache=c.pin(BUILD / 'CMakeCache.txt'), compile_commands=c.pin(BUILD / 'compile_commands.json'),
                    runtime_libraries=libraries, binary=c.pin(execution.binary)))
            cases = []
        else:
            c.require(qualification is not None, 'A successful qualification is required')
            qualified = evidence.completed(qualification, 'qualify', inventory_hash(execution.pins), c)
            prerequisites.append(qualified)
            execution.binary = Path(qualified['binary']['path'])
            cases = config['qualification_queries'] if phase == 'query0' else config['checkpoint_queries']
            if phase == 'checkpoint':
                c.require(query0 is not None, 'Successful separate query0 handoff is required')
                zero = evidence.completed(query0, 'query0', inventory_hash(execution.pins), c)
                c.require(zero['binary'] == qualified['binary'], 'Query0 binary differs from qualification')
                prerequisites.append(zero)
        admitted = None if phase == 'qualify' else c.inputs(config)
        outcomes = []
        frames = directory / 'frames'
        frames.mkdir()
        for query in cases:
            execution.budget()
            if phase == 'checkpoint' and query == 0:
                previous = c.read(Path(query0) / 'summary.json')['outcomes'][0]
                c.check(previous['native']['completion'])
                outcomes.append(dict(previous, reused_query0=True, original_query0=c.pin(Path(query0) / 'complete.json')))
                continue
            frame = c.build_frame(config, admitted, query, frames / ('query-' + str(query)))
            if frame['status'] == 'constructed':
                c.require(frame['work_bound']['context_edit_cells'] <= config['execution']['context_edit_cell_cap'],
                          'Frame exceeds predeclared context-cell budget; no decoder launched')
                frame['native'] = execution.decode(frame['frame'], directory / ('decoded-' + str(query)), config['policy'])
            outcomes.append(frame)
        c.require([o['query_index'] for o in outcomes] == cases, 'Window census changed')
        indexed_outcomes = {o['query_index']: o for o in outcomes}
        inventory = []
        for query, original in ([] if admitted is None else sorted(admitted['decisions'].items())):
            if original['status'] == 'excluded':
                inventory.append(dict(query_index=query, read_id=original['read_id'], status='original_excluded',
                                      original_decision=original))
            elif query in indexed_outcomes:
                inventory.append(indexed_outcomes[query])
            else:
                inventory.append(dict(query_index=query, read_id=original['read_id'], status='not_selected'))
        c.require(admitted is None or len(inventory) == 451 and sum(o['status'] == 'original_excluded' for o in inventory) == 120,
                  'Original full plan/exclusion census changed')
        c.fresh(directory / 'inventory.json', dict(schema='context-feedback-full-inventory/1', rows=inventory,
                planned=0 if admitted is None else 451, original_scored=0 if admitted is None else 331,
                original_excluded=0 if admitted is None else 120, selected_queries=cases))
        c.fresh(directory / 'summary.json', dict(schema='context-feedback-unit/1', phase=phase, role='development',
                scope=config['scope'], outcomes=outcomes, bridge_audit=None if admitted is None else admitted['bridge_audit'],
                full_inventory=c.pin(directory / 'inventory.json'), original_exclusions_retained=admitted is not None,
                admissible_candidate=False, no_biological_improvement_claim=True,
                query0_is_shared_exploratory_development=True, resource_caps=grant,
                binary=c.pin(execution.binary), sources=execution.pins, stages=execution.receipts))
        for p in execution.pins:
            c.check(p)
        execution.budget()
        c.fresh(directory / 'complete.json', dict(schema='context-feedback-complete/1', complete=True, phase=phase,
                source_inventory_sha256=inventory_hash(execution.pins), binary=c.pin(execution.binary), prerequisites=prerequisites,
                files=[c.pin(directory / name) for name in ('start.json', 'summary.json', 'build-closure.json', 'inventory.json')
                       if (directory / name).exists()], stages=execution.receipts))
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        print(json.dumps(dict(completion=c.pin(directory / 'complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('qualify', 'query0', 'checkpoint', 'full', 'private', 'source-inventory'))
    parser.add_argument('--config', type=Path, default=ROOT / 'config/context-feedback-dev-v2.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--query0', type=Path)
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--worker-intake', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.command == 'source-inventory':
        value = dict(sources=sources(), source_inventory_sha256=inventory_hash(sources()), executed=False)
        print(json.dumps(value, sort_keys=True))
    else:
        c.require(args.output is not None, 'New output directory required')
        run(args.command, args.config, args.output, args.admission, args.qualification, args.query0, args.worker_intake, args.checkpoint)


if __name__ == '__main__':
    main()
