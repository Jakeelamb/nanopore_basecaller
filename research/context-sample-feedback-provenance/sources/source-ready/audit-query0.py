"""Check retained query0 artifacts and exact traces without decoder or truth replay."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import struct

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
OUT = ROOT/'logs/context-sample-feedback/source-ready'
UNIT = ROOT/'results/context-sample-feedback/sample-query0-1'
NATIVE = UNIT/'native-case'


def pin(path):
    data = Path(path).read_bytes()
    return dict(path=str(path), size=len(data), sha256=hashlib.sha256(data).hexdigest())


def check(row):
    assert pin(row['path']) == row, row['path']
    return Path(row['path'])


def read(row):
    return json.loads(check(row).read_text())


def table(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def trace(data, left_length, right_length):
    header = b'sample-guarded-exact-trace/1\n'
    assert data.startswith(header)
    offset = len(header)

    def integer():
        nonlocal offset
        assert offset + 8 <= len(data)
        value = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        return value

    def real():
        value = struct.unpack('<d', struct.pack('<Q', integer()))[0]
        assert not math.isnan(value)
        return value

    def vector(expected):
        assert integer() == expected
        return [real() for _ in range(expected)]

    def sequence():
        nonlocal offset
        size = integer()
        assert size <= 108 and offset + size <= len(data)
        value = data[offset:offset+size].decode('ascii')
        assert set(value) <= set('ACGT')
        offset += size
        return value

    pruned, bound, count = integer(), integer(), integer()
    assert pruned in (0, 1) and bound in (0, 1) and count == 103
    bundles = generated = merged = dropped = 0
    for timestep in range(1, count+1):
        assert integer() == timestep
        made, unique, removed = integer(), integer(), integer()
        vector(left_length)
        retained = integer()
        assert retained <= 128 and unique >= removed + retained and made >= unique
        generated += made
        merged += unique
        dropped += removed
        bundles += retained
        seen = set()
        for _ in range(retained):
            center = sequence()
            assert center not in seen
            seen.add(center)
            real()
            vector(right_length)
            assert math.isfinite(real()) and math.isfinite(real()) and math.isfinite(real())
    count_finalists = integer()
    finalists = {}
    for _ in range(count_finalists):
        center = sequence()
        assert center not in finalists
        state = integer()
        signal_mass, potential, rank = real(), real(), real()
        assert all(math.isfinite(value) for value in (signal_mass, potential, rank))
        finalists[center] = dict(state=state, retained_signal_mass=signal_mass,
                                 terminal_potential=potential, rank=rank)
    assert offset == len(data)
    return dict(pruned=bool(pruned), bound=bool(bound), steps=count,
                retained_bundles=bundles, generated=generated, merged=merged,
                pruned_bundles=dropped, finalists=finalists)


def time_values(text):
    def value(name):
        return re.search(r'^\s*'+re.escape(name)+r': (.+)$', text, re.M)[1]
    return dict(elapsed=value('Elapsed (wall clock) time (h:mm:ss or m:ss)'),
                user_seconds=value('User time (seconds)'), system_seconds=value('System time (seconds)'),
                maximum_rss_kib=int(value('Maximum resident set size (kbytes)')),
                exit=int(value('Exit status')))


parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path)
args = parser.parse_args()
inventory = json.loads((OUT/'source-inventory-post-format-2.json').read_text())
assert len(inventory['sources']) == 89
assert inventory['sha256'] == '63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2'
for row in inventory['sources']:
    check(row)
outer = json.loads((UNIT/'execution-complete.json').read_text())
assert outer['complete'] and outer['phase'] == 'infer' and outer['whole_worker_cgroup_terminal']
for row in outer['files']:
    check(row)
terminal = read(outer['terminal'])
assert terminal['error'] is None and terminal['exit'] == 0
assert terminal['owned_cgroup_terminal'] and terminal['canonical_lock_retained']
props = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
assert props['MainPID'] == props['ControlPID'] == '0'
assert props['Result'] == 'success' and props['ActiveState'] == 'inactive' and props['ControlGroup'] == ''
supervisor = Path(outer['terminal']['path']).parent
assert json.loads((supervisor/'launcher-cleanup.json').read_text())['terminal']
intake = read(outer['worker_intake'])
assert intake['verified'] and intake['parent_lock_retained']
grant = read(intake['admission'])
assert not Path('/sys/fs/cgroup'+grant['cgroup']).exists()
worker = read(outer['worker'])
assert worker['complete'] and worker['phase'] == 'infer' and worker['sources_sha256'] == inventory['sha256']
for row in worker['files']:
    check(row)
summary = json.loads((UNIT/'summary.json').read_text())
assert summary['case_id'] == 'ordinary/0/ordinary' and summary['scope'] == 'query0'
assert len(summary['stages']) == len(summary['native']) == 1
stage = read(summary['stages'][0])
assert stage['name'] == 'sample-infer' and stage['exit'] == 0
assert stage['failure'] is None and stage['projection_error'] is None and not stage['missing_raw']
assert set(stage['raw']) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}
for row in stage['raw'].values():
    check(row)
assert shlex.split(check(stage['raw']['command.sh']).read_text()) == stage['argv']
assert check(stage['raw']['cwd.txt']).read_text().strip() == str(ROOT)
assert check(stage['raw']['exit-status.txt']).read_text().strip() == '0'
check(stage['terminal'])
assert read(stage['group_cleanup'])['terminal']
native = read(summary['native'][0])
assert native['complete'] and native['source']['compiled_sources'] == inventory['sources']
attempt = read(native['attempt'])
assert attempt['argv'] == stage['argv'] and attempt['binary'] == summary['binary']
assert attempt['source'] == native['source']
check(summary['binary'])
result = read(native['result'])
assert result['case_id'] == 'ordinary/0/ordinary' and result['historical_six_roles_verified']
assert result['scalar_comparisons'] == 137 and result['truth_available'] is False
config = json.loads((ROOT/'config/context-sample-feedback-v1.json').read_text())
assert all(result[key] is False for key in config['qualification_flags'])
for row in native['inputs']:
    check(row)
frames = table(summary['prepared']['frames']['path'])
frame = next(row for row in frames if row['case_id'] == result['case_id'])
fields = dict(line.split('\t', 1) for line in Path(frame['frame_path']).read_text().splitlines()[1:])
left, right, native_center = len(fields['left_guard']), len(fields['right_guard']), fields['native_center']
archives = json.loads((NATIVE/'trace-archives.json').read_text())
assert archives['lossless'] and len(archives['archives']) == 4
archive_map = {row['original']['path']:row for row in archives['archives']}
traces = {}
storage = []
for row in native['files']:
    if row['path'] in archive_map:
        archived = archive_map[row['path']]
        assert archived['original'] == row
        compressed = check(archived['archive']).read_bytes()
        assert compressed[4:8] == b'\0\0\0\0'
        data = gzip.decompress(compressed)
        assert len(data) == row['size'] and hashlib.sha256(data).hexdigest() == row['sha256']
        name = Path(row['path']).name.removesuffix('-trace.bin')
        traces[name] = trace(data, left, right)
        storage.append(dict(beam=name, raw=row, archive=archived['archive']))
        assert not Path(row['path']).exists()
    else:
        check(row)
assert set(traces) == {'free', 'population', 'sample', 'combined'}
beams = {row['beam']:row for row in table(NATIVE/'beams.tsv')}
for name, parsed in traces.items():
    assert beams[name]['status'] == 'complete' and not parsed['bound']
    assert int(beams[name]['pruned']) == parsed['pruned'] == True
    assert int(beams[name]['steps']) == parsed['steps'] == 103
    assert int(beams[name]['finalists']) == len(parsed['finalists']) == 128
candidates = table(NATIVE/'candidates.tsv')
indexed = {row['sequence']:row for row in candidates}
assert len(indexed) == len(candidates)
origins = {native_center:1}
for name, bits in dict(free=2, population=4, sample=8, combined=16).items():
    for sequence in traces[name]['finalists']:
        origins[sequence] = origins.get(sequence, 0) | bits
assert set(origins) == set(indexed)
for sequence, row in indexed.items():
    assert row['case_id'] == result['case_id'] and row['domain'] == 'ordinary'
    assert hashlib.sha256(sequence.encode()).hexdigest() == row['sequence_sha256']
    likelihood = float(row['full_log_likelihood'])
    assert math.isfinite(likelihood) and struct.unpack('<Q', struct.pack('<d', likelihood))[0] == int(row['likelihood_bits'])
    assert int(row['origins']) == origins[sequence]
nn = min(indexed, key=lambda sequence:(-float(indexed[sequence]['full_log_likelihood']), sequence != native_center, sequence))
decisions = {row['arm']:row for row in table(NATIVE/'decisions.tsv')}
assert set(decisions) == set(config['arms'])
scored = set(config['arms']) - {'disabled_edits', 'historical_free'}
for arm, row in decisions.items():
    assert row['case_id'] == result['case_id']
    for name in ('baseline', 'proposed', 'accepted'):
        candidate = indexed[row[name]]
        assert row[name+'_sha256'] == candidate['sequence_sha256']
        assert float(row[name+'_likelihood']) == float(candidate['full_log_likelihood'])
        assert row[name+'_origins'] == candidate['origins']
    if arm in scored:
        assert row['baseline'] == nn
        assert float(row['baseline_objective']) == float(row['baseline_likelihood']) + .5*float(row['baseline_potential'])
        assert float(row['proposed_objective']) == float(row['proposed_likelihood']) + .5*float(row['proposed_potential'])
        assert float(row['proposed_likelihood']) >= float(row['baseline_likelihood'])-.5
        margin = float(row['proposed_objective'])-float(row['baseline_objective'])
        assert row['accepted'] == (row['proposed'] if margin >= .5 else row['baseline'])
assert decisions['nn_u']['accepted'] == decisions['missing_source']['accepted'] == nn
assert decisions['disabled_edits']['accepted'] == native_center
historical = table(NATIVE/'historical.tsv')
assert len(historical) == 6 and {row['role'] for row in historical} == {'native','reference_free','context_winner','final_rerank_winner','final_rerank','selected'}
assert decisions['historical_free']['accepted'] == next(row['sequence'] for row in historical if row['role'] == 'reference_free')
proposal = table(NATIVE/'proposal-diagnostics.tsv')
assert len(proposal) == 1 and proposal[0]['nn_u'] == nn
raw_bytes = sum(row['raw']['size'] for row in storage)
compressed_bytes = sum(row['archive']['size'] for row in storage)
price = json.loads((ROOT/'results/context-sample-feedback/sample-price-query0-1/native-case/result.json').read_text())
assert raw_bytes <= price['maximum_raw_trace_bytes'] <= 52428800
native_time = time_values(check(stage['raw']['time.txt']).read_text())
assert native_time['exit'] == 0
outer_time = time_values((supervisor/'time.txt').read_text())
assert outer_time['exit'] == 0
record = dict(schema='context-sample-feedback-query0-audit/1', complete=True,
    utc=datetime.now(timezone.utc).isoformat(), source_identity=inventory['sha256'], source_count=89,
    completion=pin(UNIT/'execution-complete.json'), native_completion=summary['native'][0],
    native_result=native['result'], result=result, binary=summary['binary'], grant=intake['admission'],
    source_files_rehashed=True, native_argv_raw8_and_seals_verified=True, producer=summary['stages'][0], raw=stage['raw'],
    terminal=outer['terminal'], launcher=pin(supervisor/'launcher-cleanup.json'),
    exec_parent_exit=0, exec_parent_session=99160,
    exec_parent_observation='tools.write_stdin returned exit_code0 and no session_id',
    archives=pin(NATIVE/'trace-archives.json'), storage=storage,
    raw_trace_bytes=raw_bytes, compressed_trace_bytes=compressed_bytes,
    raw_trace_price_bytes=price['maximum_raw_trace_bytes'], trace_eof_all_vectors_counts_and_hashes_verified=True,
    traces={name:{key:value for key,value in parsed.items() if key != 'finalists'} | dict(finalist_count=len(parsed['finalists'])) for name,parsed in traces.items()},
    common_u_candidates=len(candidates), origins_exactly_reconstructed_from_successful_trace_finalists=True,
    full_likelihood_decimal_bits_match=True, neural_likelihoods_not_recomputed_from_tensors=True,
    shared_nn_baseline_and_reported_feasibility_objective_margin_verified=True,
    source_potentials_not_independently_recomputed=True,
    accepted_centers={arm:row['accepted'] for arm,row in decisions.items()},
    changed_from_native={arm:row['accepted'] != native_center for arm,row in decisions.items()},
    proposal=proposal[0], historical_roles=6, scalar_comparisons=137,
    native_cost=native_time, outer_launcher_cost=outer_time,
    service_cost_stdout=pin(supervisor/'stderr'),
    service_cost_text=(supervisor/'stderr').read_text(),
    outer_start_utc=(supervisor/'start.txt').read_text().strip(), outer_end_utc=(supervisor/'end.txt').read_text().strip(),
    cost_run_count=1, cost_spread_unmeasured=True, performance_limiter_unprofiled=True,
    cost_is_single_case_admission_observation_not_speed_comparison_or_full_corpus_bound=True,
    no_truth_payload_join=True, physical_read_independence_qualified=False, promotion_eligible=False,
    caps={key:grant[key] for key in ('maximum_wall_seconds','cpu_quota','memory_bytes','address_space_bytes',
          'swap_bytes','maximum_growth_bytes','maximum_output_bytes')})
if args.output is not None:
    with args.output.open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
print(json.dumps(dict(audit=None if args.output is None else pin(args.output), completion=record['completion'],
    source_identity=inventory['sha256'], candidates=len(candidates), raw_trace_bytes=raw_bytes,
    compressed_trace_bytes=compressed_bytes, trace_bundles={name:parsed['retained_bundles'] for name,parsed in traces.items()},
    native_cost=native_time, outer_start_utc=record['outer_start_utc'], outer_end_utc=record['outer_end_utc'],
    changed_from_native=record['changed_from_native'], terminal=record['terminal'], launcher=record['launcher'])))
