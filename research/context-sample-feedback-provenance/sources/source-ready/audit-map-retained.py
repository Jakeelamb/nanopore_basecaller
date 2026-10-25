"""Audit an accepted ordinary SAMPLE map without reference/library body reads."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'
CACHE = {}
ARTIFACTS = set()
TOTAL = 0


def require(value, message):
    if not value:
        raise ValueError(message)


def data(path):
    global TOTAL
    path = Path(path).resolve(strict=True)
    require(path.suffix.lower() not in {'.gz', '.bin', '.dgs', '.fa', '.fasta', '.vcf', '.pod5', '.pt', '.safetensors'} and path.name != 'truth.tsv', 'Prohibited body')
    if path not in CACHE:
        limit = 8*1024**2 if path in ARTIFACTS else 2*1024**2
        require(path.stat().st_size <= limit and TOTAL+path.stat().st_size <= 64*1024**2, 'Metadata/SAM budget exceeded')
        CACHE[path] = path.read_bytes()
        TOTAL += len(CACHE[path])
        require(TOTAL <= 64*1024**2, 'Read grew above budget')
    return CACHE[path]


def pin(path):
    path = Path(path).resolve(strict=True)
    value = data(path)
    return dict(path=str(path), size=len(value), sha256=hashlib.sha256(value).hexdigest())


def read(path):
    return json.loads(data(path))


def checked(value):
    require(pin(value['path']) == value, 'Pin differs: '+value['path'])


def sam(path):
    result, counts = {}, Counter()
    for line in data(path).decode('ascii').splitlines():
        if line.startswith('@'):
            continue
        fields = line.split('\t')
        require(len(fields) >= 11, 'Short SAM record')
        flag = int(fields[1])
        if flag & 0x900:
            counts['secondary_or_supplementary'] += 1
            continue
        name, sequence, quality = fields[0], fields[9], fields[10]
        require(name not in result and len(sequence) == len(quality), 'Invalid primary SEQ/Q')
        if flag & 16:
            sequence = sequence.translate(str.maketrans('ACGTNacgtn', 'TGCANtgcan'))[::-1]
            quality = quality[::-1]
            counts['reverse_primary'] += 1
        result[name] = sequence, quality
        counts['primary'] += 1
    return result, dict(counts)


def fresh(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def audit(arm, session):
    output = ROOT/('results/context-sample-feedback/sample-map-all-'+arm+'-1')
    outer = read(output/'execution-complete.json')
    require(outer['complete'] and outer['phase'] == 'map' and outer['whole_worker_cgroup_terminal'], 'Outer map incomplete')
    for value in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]:
        checked(value)
    terminal = read(outer['terminal']['path'])
    require(terminal['exit'] == 0 and terminal['error'] is None and terminal['canonical_lock_retained'] and terminal['owned_cgroup_terminal'], 'Map unit failed')
    properties = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    require(properties['MainPID'] == properties['ControlPID'] == '0' and properties['ActiveState'] == 'inactive' and properties['Result'] == 'success', 'Worker not terminal')
    raw = {Path(value['path']).name:value for value in outer['files']}
    require(read(raw['launcher-cleanup.json']['path'])['terminal'], 'Launcher not terminal')
    command = read(raw['command.json']['path'])
    require(shlex.split(data(raw['command.sh']['path']).decode()) == command['argv'] and data(raw['exit-status.txt']['path']).strip() == b'0' and data(raw['cwd.txt']['path']).decode().strip() == str(ROOT), 'Outer raw argv/cwd/status differs')
    ready = read(READY/'actual-six-canonical-mapping-ready.json')
    planned = next(value for value in ready['units'] if value['arm'] == arm)
    grant = command['grant']
    require(grant['phase'] == 'map' and grant['scope'] == 'all' and grant['arm'] == arm and grant['sources_sha256'] == planned['source_identity'] and grant['config'] == planned['config'] and grant['qualification'] == planned['qualification'] and grant['inputs'] == planned['input_pins'] and grant['output'] == str(output), 'Map admission identity differs')
    require(all(grant[key] == value for key, value in planned['caps'].items()), 'Map caps differ')
    intake = read(outer['worker_intake']['path'])
    checked(intake['admission'])
    require(intake['verified'] and intake['parent_lock_retained'] and read(intake['admission']['path']) == grant, 'Intake differs')
    worker = read(outer['worker']['path'])
    require(worker['complete'] and worker['phase'] == 'map' and worker['scope'] == 'all' and worker['sources_sha256'] == planned['source_identity'] and worker['qualification'] == planned['qualification'] and worker['inputs'] == planned['input_pins'], 'Worker source/input differs')
    for value in worker['files']:
        checked(value)
    summary = read(output/'summary.json')
    mapping = summary['mapping']
    require(summary['phase'] == 'map' and summary['scope'] == 'all' and summary['arm'] == arm and summary['native'] == [], 'Map summary differs')
    require(mapping['arm'] == mapping['canonical_arm'] == arm and mapping['snapshot'] == planned['snapshot'] and mapping['emitted'] == planned['sam'] and mapping['aliases'] == planned['aliases'] and not mapping['calibration_claim'] and all(value is False for value in mapping['qualification_flags'].values()), 'Map binding/aliases differ')
    ARTIFACTS.update(Path(mapping[key]['path']).resolve() for key in ('mapped', 'emitted'))
    stage_rows = []
    for value in summary['stages']:
        checked(value)
        stage = read(value['path'])
        require(stage['exit'] == 0 and stage['failure'] is None and stage['projection_error'] is None and not stage['missing_raw'], 'Stage failed')
        require(set(stage['raw']) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}, 'Raw eight differs')
        ARTIFACTS.add(Path(stage['raw']['stdout']['path']).resolve())
        for evidence in stage['raw'].values():
            checked(evidence)
        require(shlex.split(data(stage['raw']['command.sh']['path']).decode()) == stage['argv'] and data(stage['raw']['cwd.txt']['path']).decode().strip() == str(ROOT) and data(stage['raw']['exit-status.txt']['path']).strip() == b'0', 'Native stage raw differs')
        checked(stage['terminal'])
        checked(stage['group_cleanup'])
        require(read(stage['group_cleanup']['path'])['terminal'], 'Stage launcher not terminal')
        stage_rows.append(dict(name=stage['name'], receipt=value, argv=stage['argv'], raw=stage['raw']))
    checked(mapping['mapped'])
    checked(mapping['emitted'])
    emitted, emitted_census = sam(mapping['emitted']['path'])
    mapped, mapped_census = sam(mapping['mapped']['path'])
    require(len(emitted) == len(mapped) == 64 and emitted == mapped, 'Complete64 mapping changed primary SEQ/Q')
    for value in mapping['allele_files']:
        checked(value)
    require(len(mapping['runtime']) == 4 and all(value['libraries'] for value in mapping['runtime']), 'Runtime closure absent')
    stage_pins = {value['path'] for value in summary['stages']}
    require(all(value['stage']['path'] in stage_pins for value in mapping['runtime']), 'Runtime stage absent')
    aligned = [value for value in stage_rows if value['name'] == 'sample-map-align']
    reused = mapping['exact_historical_mapping_reused']
    require(reused == planned['existing_historical_full_SAM_snapshot_mapping_reuse'], 'Reuse behavior differs')
    require((reused and not aligned) or (not reused and len(aligned) == 1), 'Mapper replay or missing new mapper')
    if reused:
        require(mapping['mapped'] == planned['existing_mapped_pin'], 'Historical mapped artifact differs')
    start = data(raw['start.txt']['path']).decode().strip()
    end = data(raw['end.txt']['path']).decode().strip()
    memory = re.search(r'Memory peak: ([^\n]+)', data(raw['stderr']['path']).decode())
    return dict(schema='context-sample-feedback-map-retained-audit/1', complete=True, utc=datetime.now(timezone.utc).isoformat(), arm=arm, actual_exec_session_id=session, actual_exec_parent_exit=0, actual_exec_parent_returned=True, completion=pin(output/'execution-complete.json'), terminal=outer['terminal'], launcher_cleanup=raw['launcher-cleanup.json'], grant=intake['admission'], source_identity=planned['source_identity'], config=planned['config'], qualification=planned['qualification'], input_emission=planned['input_pins'][0], mapped=mapping['mapped'], emitted=mapping['emitted'], snapshot=mapping['snapshot'], aliases=mapping['aliases'], complete_primary_SEQ_Q_custody=True, emitted_census=emitted_census, mapped_census=mapped_census, exact_historical_mapping_reused=reused, new_aligner_stages=len(aligned), stages=stage_rows, runtime_descriptor_entries=4, runtime_library_pin_count=sum(len(value['libraries']) for value in mapping['runtime']), runtime_binaries_libraries_and_reference_byte_revalidation_delegated_to_actual_bounded_CLI=True, allele_files=mapping['allele_files'], caps=planned['caps'], start_utc=start, end_utc=end, whole_unit_wall_seconds=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(), service_memory_peak_raw=None if memory is None else memory[1], explicit_metadata_and_small_mapping_artifact_bytes=TOTAL, maximum_bytes=64*1024**2, current_owned_results_bytes=sum(path.stat().st_size for path in (ROOT/'results/context-sample-feedback').rglob('*') if path.is_file()), no_reference_truth_tensor_archive_library_body_read=True, no_aligner_or_observer_replay=True, full_read_paired_error_endpoints_pending=True, physical_read_independence_qualified=False, promotion_eligible=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', required=True)
    parser.add_argument('--session', type=int, required=True)
    arguments = parser.parse_args()
    result = audit(arguments.arm, arguments.session)
    path = READY/('map-'+arguments.arm+'-1-audit.json')
    fresh(path, result)
    print(json.dumps(dict(audit=pin(path), result=result)))
