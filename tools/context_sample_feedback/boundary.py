"""Bind the sample frontend to original guarded producers and separate source tables."""
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OWNED = ROOT/'tools/context_sample_feedback'
ORIGINAL = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v2')
ATLAS = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v4')
STUDY = ATLAS/'tools/context_decoder/study'
ORIGINAL_ID = '7a1b9c6f05597dd70e5eb96c894c2ed9e0cf811c28cc7735354fa1aed1f0164b'
ARMS = ('disabled_edits', 'historical_free', 'nn_u', 'population', 'sample', 'combined', 'missing_source', 'wrong_source_control')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    if Path(result.__file__).resolve() != Path(path).resolve():
        raise ValueError('Imported source location differs')
    return result


w = module('sample_execution_primitives', ROOT/'scripts/context-feedback.py')
c = w.c
w.RESULTS = ROOT/'results/context-sample-feedback'
w.LOGS = ROOT/'logs/context-sample-feedback'


def identity(pins):
    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sources():
    paths = set()
    for directory, census in ((OWNED, OWNED/'source-files.json'), (STUDY, STUDY/'source-files.json'),
                             (ORIGINAL/'tools/context_decoder', OWNED/'engine-files.json')):
        values = [(directory/path).resolve(strict=True) for path in c.read(census)]
        c.require(len(values) == len(set(values)), 'Duplicate source census entry')
        paths.update(values)
    return [c.pin(path) for path in sorted(paths)]


def configuration(path):
    value = c.read(path)
    c.require(value['schema'] == 'context-sample-feedback-config/1' and value['role'] == 'development'
              and value['base_revision'] == '454f855f11385d27b6b54e94e64422e69486be17'
              and value['context_weight'] == value['neural_deficit_limit'] == value['objective_margin'] == 0.5
              and tuple(value['arms']) == ARMS and all(flag is False for flag in value['qualification_flags'].values()),
              'Frozen sample configuration differs')
    c.require(value['execution'] == dict(canonical_lock=str(w.LOCK), maximum_wall_seconds=300,
              cpu_quota=2, memory_bytes=4*1024**3, address_space_bytes=8*1024**3, swap_bytes=0,
              maximum_output_bytes=4*1024**3, maximum_growth_bytes=100*1024**2, disk_floor_bytes=30*1024**3),
              'Frozen sample resource envelope differs')
    for pin in value['toolchain'].values(): c.check(pin)
    return value


def check_pin(pin):
    actual = c.pin(pin['path'])
    c.require(all(actual[key] == expected for key, expected in pin.items()), 'Input pin differs')
    return actual


def table(path):
    with Path(path).open(encoding='ascii', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        c.require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Invalid table header')
        rows = list(reader)
        c.require(all(None not in row and all(value is not None for value in row.values()) for row in rows), 'Malformed TSV row')
        return rows


def write_table(path, rows, fields):
    with Path(path).open('x', encoding='ascii', newline='') as stream:
        writer = csv.DictWriter(stream, fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for row in rows:
            c.require(all('\t' not in str(value) and '\n' not in str(value) for value in row.values()), 'Invalid table field')
            writer.writerow(row)


def prepare(config, output, source_audit):
    original = module('sample_original_program', ORIGINAL/'scripts/context-feedback.py')
    c.require(original.ROOT == original.c.ROOT == ORIGINAL and original.inventory_hash(original.sources()) == ORIGINAL_ID,
              'Original guarded ROOT/source inventory differs')
    atlas = module('sample_original_atlas', ATLAS/'scripts/context-program.py')
    c.require(atlas.ROOT == atlas.c.ROOT == ATLAS and identity(atlas.sources()) ==
              '695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa', 'Original atlas ROOT/source identity differs')
    qualified = atlas.completed(ATLAS/'results/context-feedback/v4-prepare-all-1', 'prepare')
    for key in ('packet', 'inference_manifest', 'source_handoff', 'source_cases', 'contexts', 'table_completion'):
        check_pin(config[key])
    c.require(qualified['summary']['prepared']['cases'] == config['packet'], 'Original prepared packet differs')
    c.require(source_audit is not None, 'Independent actual-source audit receipt required')
    c.require(c.pin(source_audit) == config['source_audit'], 'Exact independent source audit pin differs')
    audit = c.read(source_audit)
    c.require(audit['schema'] == 'sample-source-view-runtime-audit/1' and audit['complete'] is True
              and audit['verdict'] == 'PASS_EVIDENCE_FOR_EXPLORATORY_SOURCE_ONLY'
              and audit['exploratory_source_consumption_qualified'] is True
              and audit['source_role'] == 'exploratory_published_protocol'
              and audit['assumption_tag'] == 'published_protocol_pi_dx_preservation_v1'
              and all(audit[key] is False for key in config['qualification_flags'])
              and audit['source_handoff'] == config['source_handoff'] and audit['table_completion']['sha256'] == config['table_completion']['sha256']
              and audit['table_outer']['sha256'] == config['table_outer_sha256'],
              'Independent source audit does not qualify this exact handoff')
    handoff = c.read(config['source_handoff']['path'])
    c.require(handoff['complete'] is True and handoff['actual_scientific_lane_released'] is True, 'Source lane not terminal/released')
    role = handoff['roles']['exploratory_published_protocol']
    completion = role['producers']['completion']
    c.check(completion)
    c.require(completion['sha256'] == '4c545ebd0b8fd183f9875efd1a1ef7d4dff47bd457dbf6cdbfd3ee81ff309486' and
              config['source_cases'] in role['files'] and config['contexts'] in role['files'], 'Role completion/table ancestry differs')
    result = role['result']
    c.require(result['source_cases_sha256'] == config['packet']['sha256'] and result['context_role'] == 'exploratory_published_protocol'
              and result['assumption_tag'] == 'published_protocol_pi_dx_preservation_v1'
              and result['available_cases'] == 356 and result['cases'] == 368 and result['path_rows'] == 789
              and result['exploratory_consumer_ready'] is True
              and all(result[key] is False for key in ('strict_read_level_qualified','consumer_ready','promotion_eligible','biological_qualification','independent_donor_confirmation')),
              'Exploratory source role/flags/census differs')
    c.require(handoff['roles']['strict']['result']['available_cases'] == 0 and
              all(handoff['roles']['strict']['result'][key] is False for key in ('strict_read_level_qualified','consumer_ready','promotion_eligible','biological_qualification','independent_donor_confirmation')),
              'Strict source role was upgraded')
    manifest = c.read(config['inference_manifest']['path'])
    c.require(manifest['schema'] == 'context-program-inference-manifest/1' and len(manifest['cases']) == 368
              and manifest['old_source_inventory_sha256'] == ORIGINAL_ID, 'Original inference manifest differs')
    rows = []
    for fact in manifest['cases']:
        case = fact['case']
        frame = c.check(fact['frame'])
        base = c.check(fact['base_frame'])
        lines = Path(base['path']).read_text(encoding='ascii').splitlines()
        c.require(lines[0] == 'context-frame/1', 'Original base frame schema differs')
        fields = dict(line.split('\t',1) for line in lines[1:])
        c.require(identity(fact['ancestry']) == case['geometry_ancestry_sha256'], 'Native ancestry digest differs')
        rows.append(dict(case_id=case['case_id'], geometry_sha256=case['geometry_sha256'],
            ancestry_sha256=case['geometry_ancestry_sha256'], frame_path=frame['path'], frame_size=frame['size'], frame_sha256=frame['sha256'],
            base_frame_sha256=base['sha256'], plan_sha256=fields['plan_sha256'], query_index=fields['query_index'],
            location_receipt_sha256=fields['location_receipt_sha256'], location_sam_sha256=fields['location_sam_sha256']))
    c.require(len({row['case_id'] for row in rows}) == 368, 'Frame index duplicate case')
    write_table(output/'frames.tsv', rows, ('case_id', 'geometry_sha256', 'ancestry_sha256', 'frame_path', 'frame_size', 'frame_sha256',
        'base_frame_sha256', 'plan_sha256', 'query_index', 'location_receipt_sha256', 'location_sam_sha256'))
    fields = dict(packet_sha256=config['packet']['sha256'], source_cases_sha256=config['source_cases']['sha256'],
        contexts_sha256=config['contexts']['sha256'], table_completion_sha256=config['table_completion']['sha256'],
        role_completion_sha256=completion['sha256'], context_role=result['context_role'], assumption_tag=result['assumption_tag'],
        source_audit_sha256=config['source_audit']['sha256'],
        **{name:'0' for name in config['qualification_flags']})
    text = 'sample-feedback-source-handshake/1\n'+''.join(key+'\t'+value+'\n' for key,value in fields.items())
    with (output/'source-handshake.tsv').open('x', encoding='ascii') as stream: stream.write(text)
    c.fresh(output/'prepared.json', dict(schema='context-sample-feedback-prepared/1', packet=config['packet'],
        frames=c.pin(output/'frames.tsv'), handshake=c.pin(output/'source-handshake.tsv'), source_audit=c.pin(source_audit),
        source_completion=completion, source_handoff=config['source_handoff'], qualified_packet=qualified['outer'],
        qualification_flags=config['qualification_flags']))
    return c.read(output/'prepared.json')


def archive_traces(directory):
    archives = []
    for path in sorted(Path(directory).glob('*-trace.bin')):
        before = c.pin(path)
        target = Path(str(path)+'.gz')
        with path.open('rb') as source, target.open('xb') as raw:
            with gzip.GzipFile(filename='', mode='wb', compresslevel=6, fileobj=raw, mtime=0) as sink:
                while block := source.read(1024*1024): sink.write(block)
            raw.flush(); __import__('os').fsync(raw.fileno())
        check_archive(dict(original=before, archive=c.pin(target)))
        archives.append(dict(original=before, archive=c.pin(target)))
        path.unlink()
    c.fresh(Path(directory)/'trace-archives.json', dict(schema='context-sample-feedback-trace-archives/1', lossless=True, archives=archives))
    return archives


def check_archive(row):
    c.check(row['archive'])
    digest, count = hashlib.sha256(), 0
    with gzip.open(row['archive']['path'], 'rb') as source:
        while block := source.read(1024*1024): digest.update(block); count += len(block)
    c.require(digest.hexdigest() == row['original']['sha256'] and count == row['original']['size'], 'Lossless trace archive differs')


def native(directory, producer, pins, archive_override=None):
    completion = c.read(producer['raw']['stdout']['path'])['completion']
    c.check(completion)
    c.require(completion['path'] == str(Path(directory)/'complete.json'), 'Native completion path differs')
    seal = c.read(completion['path'])
    c.require(seal['complete'] is True and seal['schema'] == 'context-sample-feedback-native-complete/1', 'Native sample protocol differs')
    archive_file = Path(directory)/'trace-archives.json' if archive_override is None else Path(archive_override)
    archives = {row['original']['path']: row for row in c.read(archive_file)['archives']} if archive_file.exists() else {}
    for pin in [seal['attempt'], seal['result'], *seal['inputs'], *seal['files']]:
        if pin['path'] in archives:
            c.require(pin == archives[pin['path']]['original'], 'Archive native pin differs'); check_archive(archives[pin['path']])
        else: c.check(pin)
    attempt = c.read(seal['attempt']['path'])
    c.require(attempt['argv'] == producer['argv'] and attempt['binary'] == c.pin(producer['argv'][0])
              and attempt['source'] == seal['source'] and attempt['source']['compiled_sources'] == pins, 'Native command/binary/source closure differs')
    return completion


def ctest_counts(path):
    tests = list(ET.parse(path).getroot().iter('testcase'))
    c.require(len(tests) == 1 and tests[0].get('name') == 'exhaustive_sample_feedback_controls'
              and not any(tests[0].find(key) is not None for key in ('failure', 'error', 'skipped')), 'CTest count/skips/failure differs')
    return dict(executed=1, skipped=0)


def unittest_counts(stderr, expected):
    c.require(re.search(r'^Ran '+str(expected)+r' tests? in [0-9.]+s$', stderr, re.M) is not None
              and re.search(r'^OK$', stderr, re.M) is not None and not re.search(r'^(?:FAILED|OK \(|.* \.\.\. skipped)', stderr, re.M),
              'Consumed-frame Python controls did not execute exactly with skipped0')


def completed(directory, phase):
    directory = Path(directory).resolve()
    outer = c.read(directory/'execution-complete.json')
    recovering_infer = phase == 'infer' and outer['phase'] == 'recover'
    c.require(outer['complete'] is True and (outer['phase'] == phase or recovering_infer) and outer['whole_worker_cgroup_terminal'] is True, 'Sample outer completion differs')
    for pin in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]: c.check(pin)
    terminal = c.read(outer['terminal']['path'])
    c.require(terminal['error'] is None and terminal['exit'] == 0 and terminal['owned_cgroup_terminal'] is True, 'Sample whole unit failed')
    proof = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    c.require(proof.get('MainPID','0') == proof.get('ControlPID','0') == '0' and
              (proof.get('LoadState') == 'not-found' or (proof.get('Result') == 'success' and proof.get('ActiveState') == 'inactive')),
              'Sample worker cgroup terminal proof differs')
    cleanup = c.read(next(pin['path'] for pin in outer['files'] if pin['path'].endswith('/launcher-cleanup.json')))
    c.require(cleanup['terminal'] is True and c.read(outer['worker_intake']['path'])['verified'] is True, 'Launcher/intake terminal proof differs')
    worker = c.read(outer['worker']['path'])
    c.require(worker['complete'] is True and worker['sources_sha256'] == identity(sources()) and worker['phase'] == outer['phase'], 'Sample source/phase differs')
    for pin in worker['files']: c.check(pin)
    summary = c.read(directory/'summary.json')
    c.require(not recovering_infer or summary['phase'] == 'infer', 'Recovered scientific phase differs')
    for stage in summary['stages']: w.evidence.stage(stage, c)
    for pin in summary.get('native', []):
        c.check(pin)
        attempt = c.read(Path(pin['path']).parent/'attempt.json')
        producers = [w.evidence.stage(stage,c) for stage in summary['stages'] if c.read(stage['path'])['argv'] == attempt['argv']]
        c.require(len(producers) == 1, 'Native producer absent/duplicate')
        archive = summary.get('native_archives', {}).get(pin['path'])
        if archive is not None: c.check(archive)
        native(Path(pin['path']).parent, producers[0], sources(), None if archive is None else archive['path'])
    if phase == 'qualify':
        check_build_closure(directory, summary['binary'])
        c.check(summary['observer_binary'])
    return summary


def check_build_closure(directory, binary):
    closure = c.read(Path(directory)/'build-closure.json')
    for key in ('compiler', 'formatter', 'cache', 'compile_commands', 'binary'):
        c.check(closure[key])
    c.require(closure['runtime_libraries'], 'Qualified runtime closure is empty')
    for library in closure['runtime_libraries']: c.check(library)
    c.require(closure['binary'] == binary, 'Qualified build/runtime binary differs')


def build_closure(output, execution, binary, config):
    cache = output/'build/CMakeCache.txt'
    commands = output/'build/compile_commands.json'
    matches = [line.split('=',1)[1] for line in cache.read_text().splitlines()
               if re.match(r'^CMAKE_CXX_COMPILER:(?:FILEPATH|STRING)=', line)]
    c.require(len(matches) == 1 and c.pin(matches[0]) == config['toolchain']['compiler'], 'Actual compiler differs')
    flags = ('-std=c++23', '-Wall', '-Wextra', '-Wpedantic', '-Wconversion', '-Wsign-conversion', '-Wshadow',
             '-Werror', '-fno-fast-math', '-ffp-contract=off')
    for row in c.read(commands):
        argv = row.get('arguments') or shlex.split(row['command'])
        c.require(all(flag in argv for flag in flags) and '-ffast-math' not in argv, 'Actual strict compilation flags differ')
    stage = execution.stage('sample-linked-runtime', ['ldd', binary['path']])
    libraries = {}
    for line in Path(stage['raw']['stdout']['path']).read_text().splitlines():
        match = re.search(r'(?:=>\s+)?(/[^\s]+)\s+\(', line)
        if match:
            pin = c.pin(match.group(1)); libraries[pin['path']] = pin
    c.require(libraries, 'Actual linked runtime closure absent')
    c.fresh(output/'build-closure.json', dict(compiler=config['toolchain']['compiler'], formatter=config['toolchain']['formatter'],
        cache=c.pin(cache), compile_commands=c.pin(commands), runtime_libraries=list(libraries.values()), binary=binary))


def check_scope(scope, case_id):
    parts = case_id.split('/')
    c.require(len(parts) == 3 and parts[1].isdigit(), 'Invalid case ID')
    number = int(parts[1])
    c.require((scope == 'query0' and case_id == 'ordinary/0/ordinary') or
              (scope == 'first32' and parts[0] == 'ordinary' and 0 < number < 32) or
              (scope == 'remaining' and ((parts[0] == 'ordinary' and number >= 32) or parts[0] == 'private')),
              'Case is outside disjoint frozen scope')


def check_prior(args, config):
    prior = [completed(path, c.read(path/'complete.json')['phase']) for path in args.input[1:]]
    prices = [summary for summary in prior if summary['phase'] == 'price' and summary['case_id'] == args.case_id]
    c.require(len(prices) == 1, 'Exact case price required before inference')
    price = c.read(c.read(prices[0]['native'][0]['path'])['result']['path'])
    c.require(price['maximum_raw_trace_bytes'] <= config['execution']['maximum_growth_bytes']//2,
              'Priced raw trace plus compression headroom exceeds unit output cap')
    inferences = [summary for summary in prior if summary['phase'] == 'infer']
    checkpoints = [summary['checkpoint'] for summary in prior if summary['phase'] == 'checkpoint']
    previous = {summary['case_id'] for summary in inferences}
    for checkpoint in checkpoints: previous.update(checkpoint['case_ids'])
    c.require(args.case_id not in previous, 'Successful retained case must not be replayed')
    if args.scope != 'query0':
        c.require('ordinary/0/ordinary' in previous, 'Genuine query0 checkpoint required')
    if args.scope == 'remaining':
        cases = [row for row in table(config['source_cases']['path']) if row['case_id'].startswith('ordinary/') and
                 0 < int(row['case_id'].split('/')[1]) < 32]
        c.require({row['case_id'] for row in cases} <= previous, 'Complete first32 checkpoint required')


def checkpoint(args, output, config):
    c.require(args.scope in ('query0','first32'), 'Checkpoint scope must be query0 or first32')
    summaries = [completed(path, 'infer') for path in args.input]
    ids = [summary['case_id'] for summary in summaries]
    expected = {'ordinary/0/ordinary'} if args.scope == 'query0' else {
        row['case_id'] for row in table(config['source_cases']['path']) if row['case_id'].startswith('ordinary/')
        and int(row['case_id'].split('/')[1]) < 32}
    c.require(len(ids) == len(set(ids)) and set(ids) == expected, 'Checkpoint exact case accounting differs')
    c.require(all(summary['binary'] == summaries[0]['binary'] for summary in summaries), 'Checkpoint binary differs')
    trace_bytes = []
    for summary in summaries:
        directory = Path(summary['native'][0]['path']).parent
        archive = summary.get('native_archives', {}).get(summary['native'][0]['path'])
        archives = c.read(directory/'trace-archives.json' if archive is None else archive['path'])['archives']
        trace_bytes.append(dict(case_id=summary['case_id'], raw_bytes=sum(row['original']['size'] for row in archives),
                               compressed_bytes=sum(row['archive']['size'] for row in archives)))
    forecast = max(row['compressed_bytes'] for row in trace_bytes) * 368
    value = dict(schema='context-sample-feedback-checkpoint/1', scope=args.scope, case_ids=sorted(ids),
                 inputs=[c.pin(path/'execution-complete.json') for path in args.input], binary=summaries[0]['binary'], traces=trace_bytes,
                 descriptive_full_trace_forecast_bytes=forecast, forecast_is_bound=False, cumulative_bytes=w.owned_bytes(),
                 further_execution_requires_fresh_coordinator_grant=True)
    c.fresh(output/'checkpoint.json', value)
    return value


def recovery_header(value, case_id, scope, source_identity):
    c.require(value['schema'] == 'context-sample-feedback-recovery/1' and value['case_id'] == case_id
              and value['scope'] == scope and value['source_identity'] == source_identity, 'Recovery source/case/scope differs')
    check_scope(scope, case_id)


def recovery_original(value):
    for key in ('producer', 'outer_terminal', 'outer_command', 'launcher_cleanup', 'worker_intake'): c.check(value[key])
    outer = c.read(value['outer_command']['path'])
    grant = outer['grant']
    directory = w.LOGS/('sample-supervisor-'+grant['id'])
    for key, name in (('outer_command', 'command.json'), ('outer_terminal', 'terminal.json'),
                      ('launcher_cleanup', 'launcher-cleanup.json'), ('worker_intake', 'worker-intake.json')):
        c.require(value[key]['path'] == str(directory/name), 'Recovery original supervisor membership differs')
    intake = c.read(directory/'intake.json')
    worker = c.read(value['worker_intake']['path'])
    unit = 'context-sample-feedback-'+grant['id']+'.service'
    c.check(worker['admission'])
    c.require(intake['grant_id'] == grant['id'] and intake['unit'] == unit
              and intake['admission'] == worker['admission']['path'] and c.read(intake['admission']) == grant
              and worker['verified'] is True and worker['parent_lock_retained'] is True,
              'Recovery original intake/admission differs')
    observation = worker['observation']
    c.require(observation['exit'] == 0 and observation['argv'][:4] == ['systemctl', '--user', 'show', unit]
              and observation['properties']['ControlGroup'] == grant['cgroup']
              and observation['properties']['Description'] == intake['description'], 'Recovery original worker cgroup differs')
    tail = ['run', '--no-sync', 'python', str(ROOT/'scripts/context-sample-feedback.py'), 'infer',
            '--scope', grant['scope'], '--config', grant['config']['path'], '--output', grant['output'],
            '--admission', intake['admission'], '--worker-intake', str(directory/'intake.json')]
    for key, option in (('case_id', '--case-id'), ('source_audit', '--source-audit'), ('arm', '--arm'),
                        ('recovery', '--recovery'), ('qualification', '--qualification')):
        if grant[key] is not None:
            item = grant[key]
            if key == 'qualification': item = str(Path(item['path']).parent)
            elif isinstance(item, dict): item = item['path']
            tail += [option, item]
    for item in grant['inputs']: tail += ['--input', str(Path(item['path']).parent)]
    argv = outer['argv']
    c.require(argv[0] == 'systemd-run' and argv[argv.index('--')+2:] == tail
              and '--unit='+unit in argv and '--description='+intake['description'] in argv
              and '--working-directory='+str(ROOT) in argv and outer['cwd'] == str(ROOT)
              and shlex.split((directory/'command.sh').read_text()) == argv
              and (directory/'cwd.txt').read_text().strip() == str(ROOT), 'Recovery original launcher command/cwd differs')
    terminal = c.read(value['outer_terminal']['path'])
    proof = terminal['proof'].get('unloaded_empty_group', terminal['proof'])
    properties = proof['properties']
    c.require(proof['exit'] == 0 and proof['argv'][:4] == observation['argv'][:4]
              and terminal['owned_cgroup_terminal'] is True and terminal['canonical_lock_retained'] is True
              and properties.get('MainPID','0') == properties.get('ControlPID','0') == '0'
              and properties.get('ControlGroup','') in ('', grant['cgroup'])
              and (properties.get('LoadState') == 'not-found' or (properties.get('ActiveState') in ('inactive','failed')
                   and properties.get('Description') == intake['description']))
              and c.read(value['launcher_cleanup']['path'])['terminal'] is True,
              'Failed original whole-unit tree lacks terminal proof')
    producer = c.read(value['producer']['path'])
    launcher = Path(producer['launcher'])
    launch = c.read(launcher/'launch.json')
    c.require(value['producer']['path'] == str(launcher/'finish.json') and producer['admission_id'] == grant['id']
              and launch['admission'] == grant and launch['cwd'] == str(ROOT)
              and launch['argv'] == [str(w.LOGS/'recorder-root/scripts/record-command.sh'), producer['name'], *producer['argv']],
              'Recovery producer original admission differs')
    native_directory = Path(grant['output'])/'native-case'
    c.require(value['native_directory'] == str(native_directory) and native_directory.is_relative_to(w.RESULTS)
              and producer['argv'][producer['argv'].index('--output')+1] == str(native_directory),
              'Recovery producer original native directory differs')
    return outer, producer


def recover(args, output, config, qualification, execution):
    c.require(args.recovery is not None and len(args.input) == 1 and args.case_id is not None, 'Exact recovery descriptor and prepared unit required')
    value = c.read(args.recovery)
    recovery_header(value, args.case_id, args.scope, identity(sources()))
    outer, producer = recovery_original(value)
    old_grant = outer['grant']
    c.require(old_grant['phase'] == 'infer' and old_grant['case_id'] == args.case_id and old_grant['scope'] == args.scope
              and old_grant['sources_sha256'] == value['source_identity'] and old_grant['config'] == c.pin(args.config)
              and old_grant['qualification'] == c.pin(args.qualification/'execution-complete.json')
              and old_grant['inputs'][0] == c.pin(args.input[0]/'execution-complete.json'), 'Recovery original admission differs')
    c.require(producer['exit'] == 0 and producer['failure'] is None, 'Recovery requires an actual successful retained producer')
    normalized = dict(producer, projection_error=None, recovered_projection_from=value['producer'])
    c.fresh(output/'recovered-producer.json', normalized)
    recovered_stage = c.pin(output/'recovered-producer.json')
    producer = w.evidence.stage(recovered_stage, c)
    native_directory = Path(value['native_directory']).resolve()
    c.require(native_directory.is_relative_to(w.RESULTS) and native_directory != output, 'Recovery native directory outside owned results')
    completion = c.read(producer['raw']['stdout']['path'])['completion']
    c.check(completion)
    c.require(completion['path'] == str(native_directory/'complete.json'), 'Recovery native completion path differs')
    seal = c.read(completion['path'])
    c.check(seal['attempt']); c.check(seal['result'])
    attempt = c.read(seal['attempt']['path'])
    result = c.read(seal['result']['path'])
    c.require(attempt['binary'] == qualification['binary'] and producer['argv'][1] == 'infer' and result['case_id'] == args.case_id
              and result['truth_available'] is False and result['historical_six_roles_verified'] is True, 'Recovery binary/phase/result differs')
    prepared = completed(args.input[0], 'prepare')['prepared']
    argv = producer['argv']
    c.require(argv[argv.index('--frames')+1] == prepared['frames']['path'] and argv[argv.index('--frames-sha256')+1] == prepared['frames']['sha256']
              and argv[argv.index('--handshake-sha256')+1] == prepared['handshake']['sha256'], 'Recovery prepared frame/source handoff differs')
    archives = []
    for pin in seal['files']:
        if not pin['path'].endswith('-trace.bin'): continue
        original = Path(pin['path'])
        target = output/(original.name+'.gz')
        if original.exists():
            c.check(pin)
            with original.open('rb') as source, target.open('xb') as raw:
                with gzip.GzipFile(filename='', mode='wb', compresslevel=6, fileobj=raw, mtime=0) as sink:
                    while block := source.read(1024*1024): sink.write(block)
                raw.flush(); __import__('os').fsync(raw.fileno())
            row = dict(original=pin, archive=c.pin(target))
        else:
            row = dict(original=pin, archive=c.pin(str(original)+'.gz'))
        check_archive(row); archives.append(row); execution.budget()
    c.fresh(output/'trace-archives.json', dict(schema='context-sample-feedback-trace-archives/1', lossless=True, archives=archives))
    archive = c.pin(output/'trace-archives.json')
    native(native_directory, producer, sources(), archive['path'])
    execution.receipts.append(recovered_stage)
    return dict(phase='infer', scope=args.scope, case_id=args.case_id, arm=None, binary=qualification['binary'], native=[completion],
                native_archives={completion['path']:archive}, prepared=prepared, recovery=c.pin(args.recovery), original_outer_terminal=value['outer_terminal'])
