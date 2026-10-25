"""Check retained emission metadata and reconstruct selected primary SAM SEQ/Q."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import hashlib
import io
import json
import os
import re
import shlex

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'
OUTPUT = ROOT/'results/context-sample-feedback/sample-emit-all-1'
NATIVE = Path('/home/jake/Projects/nanopore_basecaller-reference/logs/20261023T035916Z-stock-fe30a2dbcb664128bf187fdaf8f68340-CoVGDR/stdout')
CACHE = {}
TOTAL = 0


def require(value, message):
    if not value:
        raise ValueError(message)


def data(path):
    global TOTAL
    path = Path(path).resolve(strict=True)
    require(path.suffix.lower() not in {'.gz', '.bin', '.dgs', '.fa', '.fasta', '.bam', '.vcf', '.pod5', '.pt', '.safetensors'} and path.name != 'truth.tsv', 'Prohibited payload')
    if path not in CACHE:
        limit = 17*1024**2 if path == NATIVE else 8*1024**2 if path.suffix == '.sam' else 2*1024**2
        require(path.stat().st_size <= limit and TOTAL+path.stat().st_size <= 64*1024**2, 'Bounded SAM/metadata read exceeded')
        CACHE[path] = path.read_bytes()
        TOTAL += len(CACHE[path])
        require(TOTAL <= 64*1024**2, 'Read grew above aggregate limit')
    return CACHE[path]


def pin(path):
    path = Path(path).resolve(strict=True)
    value = data(path)
    return dict(path=str(path), size=len(value), sha256=hashlib.sha256(value).hexdigest())


def read(path):
    return json.loads(data(path))


def checked(value):
    require(pin(value['path']) == value, 'Retained pin differs: '+value['path'])


def table(path):
    return list(csv.DictReader(io.StringIO(data(path).decode()), delimiter='\t'))


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


def primary_sam(path):
    rows, counts = {}, Counter()
    complement = str.maketrans('ACGTNacgtn', 'TGCANtgcan')
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
        require(name not in rows and len(sequence) == len(quality), 'Duplicate primary or unequal primary SEQ/Q')
        if flag & 16:
            sequence, quality = sequence.translate(complement)[::-1], quality[::-1]
            counts['reverse_primary'] += 1
        rows[name] = sequence, quality
        counts['primary'] += 1
    return rows, dict(counts)


def audit():
    frozen = read(READY/'all368-frozen-inputs.json')
    outer = read(OUTPUT/'execution-complete.json')
    require(pin(OUTPUT/'execution-complete.json')['sha256'] == '3628b55fcb4639366dca27e073e6553dc9adcc759329f26f9620e61be70354e8', 'Actual completion differs')
    require(outer['complete'] and outer['phase'] == 'emit' and outer['whole_worker_cgroup_terminal'], 'Outer not accepted')
    for value in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]:
        checked(value)
    terminal = read(outer['terminal']['path'])
    require(terminal['exit'] == 0 and terminal['error'] is None and terminal['canonical_lock_retained'] and terminal['owned_cgroup_terminal'], 'Whole unit failed')
    properties = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    require(properties['MainPID'] == properties['ControlPID'] == '0' and properties['Result'] == 'success' and properties['ActiveState'] == 'inactive', 'Worker terminal differs')
    files = {Path(value['path']).name:value for value in outer['files']}
    require({'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'} <= files.keys(), 'Raw-eight missing')
    require(read(files['launcher-cleanup.json']['path'])['terminal'] and data(files['exit-status.txt']['path']).strip() == b'0' and data(files['cwd.txt']['path']).decode().strip() == str(ROOT), 'Raw closure differs')
    command = read(files['command.json']['path'])
    require(shlex.split(data(files['command.sh']['path']).decode()) == command['argv'], 'Raw argv differs')
    grant = command['grant']
    require(grant['phase'] == 'emit' and grant['scope'] == 'all' and grant['sources_sha256'] == frozen['scientific_source_identity'] and grant['config'] == frozen['config'] and grant['qualification'] == frozen['qualification'] and grant['inputs'] == frozen['input_pins'], 'Grant source/input differs')
    caps = dict(maximum_wall_seconds=300, maximum_output_bytes=4294967296, maximum_growth_bytes=104857600, memory_bytes=4294967296, address_space_bytes=8589934592, swap_bytes=0, cpu_quota=2)
    require(all(grant[key] == value for key, value in caps.items()), 'Grant caps differ')
    intake = read(outer['worker_intake']['path'])
    checked(intake['admission'])
    require(intake['verified'] and intake['parent_lock_retained'] and read(intake['admission']['path']) == grant, 'Intake differs')
    worker = read(outer['worker']['path'])
    require(worker['complete'] and worker['phase'] == 'emit' and worker['scope'] == 'all' and worker['sources_sha256'] == frozen['scientific_source_identity'] and worker['inputs'] == frozen['input_pins'] and worker['qualification'] == frozen['qualification'], 'Worker source/input differs')
    for value in worker['files']:
        checked(value)
    summary = read(OUTPUT/'summary.json')
    require(summary['native'] == summary['stages'] == [] and summary['binary']['sha256'] == '001af437a02fcf615f78617af1fad164af0ad60f18d1beba6ce9ff2fcae1f475', 'Unexpected producer or binary')
    emission = read(OUTPUT/'emission.json')
    require(emission['parents'] == 64 and emission['ordinary_cases'] == 311 and not emission['private_frames_applied'] and emission['private_diagnostics_separate'] and all(value is False for value in emission['qualification_flags'].values()) and emission['inputs'] == frozen['input_pins'], 'Full emission scope differs')
    choices = table(OUTPUT/'all-choices.tsv')
    indexed = {(row['case_id'], row['arm']):row for row in choices}
    arms = {arm['arm'] for arm in emission['arms']}
    ids = {row['case_id'] for row in frozen['ordered_inputs']}
    require(len(indexed) == len(choices) == 2944 and set(indexed) == {(case, arm) for case in ids for arm in arms}, 'Full368 by8 census differs')
    for item in frozen['ordered_inputs']:
        checked(item['completion'])
        for row in table(Path(item['completion']['path']).parent/'native-case/decisions.tsv'):
            require(row == indexed[row['case_id'], row['arm']], 'Frozen decision changed')
    checked(emission['snapshot'])
    snapshot = read(emission['snapshot']['path'])
    require(snapshot['native']['path'] == str(NATIVE) and snapshot['native']['sha256'] == 'db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe' and snapshot['native']['size'] == 16085465, 'Exact native SAM allowance differs')
    checked(snapshot['native'])
    originals, native_census = primary_sam(NATIVE)
    checked(snapshot['parents'])
    parents = data(snapshot['parents']['path']).decode().splitlines()
    require(len(parents) == len(set(parents)) == 64 and set(parents) <= originals.keys(), 'Selected parent census differs')
    by_arm, aliases, edits_by_arm = {}, {}, {}
    for arm in emission['arms']:
        checked(arm['sam'])
        parsed, census = primary_sam(arm['sam']['path'])
        require(set(parsed) == set(parents) and census.get('primary') == 64 and not census.get('secondary_or_supplementary'), 'Emitted primary64 census differs')
        for parent in parents:
            sequence, quality = originals[parent]
            edits = sorted([edit for edit in arm['edits'] if edit['parent'] == parent], key=lambda edit:edit['start'])
            sequence_parts, quality_parts, cursor = [], [], 0
            for edit in edits:
                start, end = edit['start'], edit['end']
                require(cursor <= start <= end <= len(sequence) and sequence[start:end] == edit['stock'] and edit['replacement'] != edit['stock'], 'Edit attachment/range differs')
                require(edit['case_id'].startswith('ordinary/') and indexed[edit['case_id'], arm['arm']]['accepted'] == edit['replacement'], 'Private edit or replacement differs')
                sequence_parts.extend([sequence[cursor:start], edit['replacement']])
                quality_parts.extend([quality[cursor:start], '!'*len(edit['replacement'])])
                cursor = end
            sequence_parts.append(sequence[cursor:])
            quality_parts.append(quality[cursor:])
            require(parsed[parent] == (''.join(sequence_parts), ''.join(quality_parts)), 'Independent original-primary SEQ/Q reconstruction differs')
        by_arm[arm['arm']] = data(arm['sam']['path'])
        aliases[arm['arm']] = arm['canonical_arm']
        edits_by_arm[arm['arm']] = len(arm['edits'])
    for arm, canonical in aliases.items():
        require(by_arm[arm] == by_arm[canonical], 'Exact SAM alias differs')
    require(len(set(by_arm.values())) == 6 and aliases['nn_u'] == aliases['missing_source'] == aliases['historical_free'] == 'historical_free', 'Actual dedup census differs')
    start = data(files['start.txt']['path']).decode().strip()
    end = data(files['end.txt']['path']).decode().strip()
    peak = re.search(r'Memory peak: ([^\n]+)', data(files['stderr']['path']).decode())
    return dict(schema='context-sample-feedback-all368-emission-audit/1', complete=True, utc=datetime.now(timezone.utc).isoformat(), actual_exec_session_id=72451, actual_exec_parent_returned=True, actual_exec_exit=0, completion=pin(OUTPUT/'execution-complete.json'), terminal=outer['terminal'], launcher_cleanup=files['launcher-cleanup.json'], grant=intake['admission'], source_identity=frozen['scientific_source_identity'], config=frozen['config'], qualification=frozen['qualification'], frozen_inputs=pin(READY/'all368-frozen-inputs.json'), cases=368, ordinary_cases=311, private_cases=57, frozen_choices=2944, complete_parents=64, independent_original_primary_SEQ_Q_reconstruction_passed=True, original_native_SAM=snapshot['native'], original_native_record_census=native_census, source_both_unchanged_splice_contracts_passed=True, untouched_SEQ_Q_and_changed_bang_quality_checked=True, alias_groups=aliases, unique_SAMs=6, canonical_SAMs=[dict(arm=arm['arm'], sam=arm['sam'], edits=len(arm['edits']), historical_mapping_reuse_eligible=arm['historical_reference_free_mapping'] is not None) for arm in emission['arms'] if arm['arm'] == arm['canonical_arm']], edits_by_arm=edits_by_arm, all_choices_pin=pin(OUTPUT/'all-choices.tsv'), emission_pin=pin(OUTPUT/'emission.json'), start_utc=start, end_utc=end, whole_unit_wall_seconds=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(), service_memory_peak_raw=None if peak is None else peak[1], current_owned_results_bytes=sum(path.stat().st_size for path in (ROOT/'results/context-sample-feedback').rglob('*') if path.is_file()), auditor=pin(__file__), explicit_metadata_and_SAM_bytes_read=TOTAL, maximum_bytes_per_repaired_audit=64*1024**2, prior_failed_audits_retained_separately=True, no_emit_replay=True, no_archive_tensor_reference_truth_body_read=True, no_observer_mapping_or_truth_join=True, physical_read_independence_qualified=False, promotion_eligible=False)


if __name__ == '__main__':
    try:
        result = audit()
    except BaseException as error:
        fresh(READY/'emit-all-1-audit-recovery-failed.json', dict(error=repr(error), explicit_bytes=TOTAL, actual_emit_parent_exit=0, no_product_rerun=True))
        raise
    fresh(READY/'emit-all-1-audit.json', result)
    print(json.dumps(dict(audit=pin(READY/'emit-all-1-audit.json'), result=result)))
