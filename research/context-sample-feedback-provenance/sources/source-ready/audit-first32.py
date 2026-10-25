"""Audit small retained first32 metadata and freeze the fixed remaining proposal."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import struct

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'
DISPATCH = ROOT/'logs/context-sample-feedback/first32-dispatch-20261025T070825194753Z-2602a2fe'
HELPER = READY/'first32-dispatch/dispatch.py'
original_bytes = Path.read_bytes
reads = Counter()
total = 0


def bounded_bytes(path):
    global total
    path = path.resolve(strict=True)
    require(path.suffix.lower() not in {'.gz', '.bin', '.dgs', '.fa', '.fasta', '.fai', '.bam', '.cram', '.sam', '.vcf', '.bcf', '.pod5', '.pt', '.safetensors'}, 'Heavy payload prohibited')
    require(path.name != 'truth.tsv', 'Truth payload prohibited')
    size = path.stat().st_size
    require(size <= 2*1024**2 and total+size <= 64*1024**2, 'Metadata read budget exceeded')
    data = original_bytes(path)
    total += len(data)
    require(len(data) <= 2*1024**2 and total <= 64*1024**2, 'Metadata grew above budget')
    reads[str(path)] += len(data)
    return data


def bounded_text(path, encoding=None, errors=None, newline=None):
    return bounded_bytes(path).decode(encoding or 'utf-8', errors or 'strict')


def require(value, message):
    if not value:
        raise ValueError(message)


Path.read_bytes = bounded_bytes
Path.read_text = bounded_text


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), size=len(data), sha256=hashlib.sha256(data).hexdigest())


def read(path):
    return json.loads(Path(path).read_text())


def table(path):
    return list(csv.DictReader(io.StringIO(Path(path).read_text(), newline=''), delimiter='\t'))


def cost(text):
    def value(name):
        return re.search(r'^\s*'+re.escape(name)+r': (.+)$', text, re.M)[1]
    elapsed = value('Elapsed (wall clock) time (h:mm:ss or m:ss)')
    seconds = sum(float(part)*60**index for index, part in enumerate(reversed(elapsed.split(':'))))
    require(value('Exit status') == '0', 'Native command failed')
    return dict(elapsed_seconds=seconds, elapsed_raw=elapsed,
                user_seconds=float(value('User time (seconds)')), system_seconds=float(value('System time (seconds)')),
                maximum_rss_kib=int(value('Maximum resident set size (kbytes)')))


parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--remaining-proposal', type=Path, required=True)
args = parser.parse_args()
require(pin(HELPER)['sha256'] == '75a28371e36eca5ea47739d1a08db3095c6f8294313218a31ebea792c5284c1d', 'Reviewed helper changed')
spec = importlib.util.spec_from_file_location('first32_metadata_only_dispatch', HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
manifest = helper.expected_manifest()
require(read(READY/'first32-dispatch/manifest.json') == manifest, 'Fixed manifest changed')
dispatch = read(DISPATCH/'complete.json')
require(dispatch['complete'] is True and len(dispatch['products']['cases']) == 21, 'Dispatch incomplete')
require(not (DISPATCH/'failed.json').exists(), 'Failed dispatch retained')
closed = [read(path) for path in DISPATCH.glob('first32-*/closed.json')]
require(len(closed) == 43 and all(row['exit'] == 0 and row['actual_subprocess_run_returned'] is True for row in closed), 'Actual child-parent closure census differs')
acceptances = list(DISPATCH.glob('first32-*/accepted.json'))
require(len(acceptances) == 43, 'Accepted-unit census differs')
prices = {}
inferences = [ROOT/'results/context-sample-feedback/sample-query0-1']
for item, product in zip(manifest['units'], dispatch['products']['cases'], strict=True):
    require(product['case_id'] == item['case_id'] and not product['price']['reused'] and not product['infer']['reused'], 'Case order or unexpected replay/reuse differs')
    price_pin, price_value = helper.accepted(item['price_output'], 'price', item['case_id'], [manifest['prepared']], manifest)
    require(product['price']['completion'] == price_pin and product['price']['value'] == price_value, 'Price product differs')
    infer_pin, infer_value = helper.accepted(item['infer_output'], 'infer', item['case_id'],
        [manifest['prepared'], price_pin, manifest['query0_checkpoint']], manifest)
    require(product['infer']['completion'] == infer_pin and product['infer']['value'] == infer_value, 'Inference product differs')
    prices[item['case_id']] = price_value
    inferences.append(Path(item['infer_output']))
inputs = [pin(path/'execution-complete.json') for path in inferences]
checkpoint_pin, checkpoint = helper.accepted(manifest['checkpoint_output'], 'checkpoint', None, inputs, manifest)
require(dispatch['products']['checkpoint']['completion'] == checkpoint_pin, 'Checkpoint product differs')
prices['ordinary/0/ordinary'] = read(ROOT/'results/context-sample-feedback/sample-price-query0-1/native-case/result.json')
config = helper.read_pin(manifest['config'])
rows = []
for directory in inferences:
    summary = read(directory/'summary.json')
    native = helper.read_pin(summary['native'][0])
    result = helper.read_pin(native['result'])
    case = summary['case_id']
    require(result['case_id'] == case and result['truth_available'] is False
            and result['historical_six_roles_verified'] is True and result['scalar_comparisons'] > 0
            and all(result[key] is False for key in config['qualification_flags']), 'Result or false qualification flags differ')
    metadata = {Path(row['path']).name:row for row in native['files'] if not row['path'].endswith('-trace.bin')}
    for name in ('candidates.tsv', 'decisions.tsv', 'beams.tsv', 'historical.tsv', 'sources.tsv', 'proposal-diagnostics.tsv'):
        helper.checked(metadata[name])
    candidates = table(directory/'native-case/candidates.tsv')
    indexed = {row['sequence']:row for row in candidates}
    require(len(indexed) == len(candidates), 'Duplicate U center')
    history = table(directory/'native-case/historical.tsv')
    require(len(history) == 6 and len({row['role'] for row in history}) == 6, 'Historical role census differs')
    native_center = next(row['sequence'] for row in history if row['role'] == 'native')
    beams = {row['beam']:row for row in table(directory/'native-case/beams.tsv')}
    require({'free', 'population'} <= set(beams) <= {'free', 'population', 'sample', 'combined'}, 'Enabled beam census differs')
    allowed = 1
    if beams['free']['status'] == 'complete':
        for name, bits in dict(free=2, population=4, sample=8, combined=16).items():
            if name in beams and beams[name]['status'] == 'complete':
                allowed |= bits
    else:
        require(len(candidates) == 1 and native_center in indexed, 'Failed free beam admitted U candidates')
    for sequence, candidate in indexed.items():
        require(candidate['case_id'] == case and hashlib.sha256(sequence.encode()).hexdigest() == candidate['sequence_sha256'], 'Candidate identity differs')
        likelihood = float(candidate['full_log_likelihood'])
        require(math.isfinite(likelihood) and struct.unpack('<Q', struct.pack('<d', likelihood))[0] == int(candidate['likelihood_bits']), 'Full-likelihood decimal/bit mismatch')
        origins = int(candidate['origins'])
        require(origins > 0 and origins & ~allowed == 0, 'Unavailable/failed beam origin admitted')
    nn = min(indexed, key=lambda sequence:(-float(indexed[sequence]['full_log_likelihood']), sequence != native_center, sequence))
    decisions = {row['arm']:row for row in table(directory/'native-case/decisions.tsv')}
    require(set(decisions) == set(config['arms']), 'Eight-arm census differs')
    for arm, decision in decisions.items():
        require(decision['case_id'] == case, 'Decision case differs')
        for name in ('baseline', 'proposed', 'accepted'):
            candidate = indexed[decision[name]]
            require(decision[name+'_sha256'] == candidate['sequence_sha256']
                    and float(decision[name+'_likelihood']) == float(candidate['full_log_likelihood'])
                    and decision[name+'_origins'] == candidate['origins'], 'Decision not joined to actual full U')
        if arm not in ('disabled_edits', 'historical_free'):
            require(decision['baseline'] == (nn if beams['free']['status'] == 'complete' else native_center), 'Actual NN baseline differs')
            require(float(decision['baseline_objective']) == float(decision['baseline_likelihood'])+.5*float(decision['baseline_potential'])
                    and float(decision['proposed_objective']) == float(decision['proposed_likelihood'])+.5*float(decision['proposed_potential']), 'Reported contextual objective arithmetic differs')
            if decision['abstained'] == '1':
                require(decision['accepted'] == native_center, 'Search failure did not abstain at native')
            else:
                require(float(decision['proposed_likelihood']) >= float(decision['baseline_likelihood'])-.5, 'Infeasible proposal accepted')
                margin = float(decision['proposed_objective'])-float(decision['baseline_objective'])
                require(decision['accepted'] == (decision['proposed'] if margin >= .5 else decision['baseline']), 'Objective margin gate differs')
    require(decisions['disabled_edits']['accepted'] == native_center, 'Disabled arm edited center')
    require(decisions['nn_u']['accepted'] == decisions['missing_source']['accepted'], 'Missing-source fallback differs from actual NN')
    require(decisions['historical_free']['accepted'] == next(row['sequence'] for row in history if row['role'] == 'reference_free'), 'Historical-free replay differs')
    archives = read(directory/'native-case/trace-archives.json')
    original_pins = {row['path']:row for row in native['files'] if row['path'].endswith('-trace.bin')}
    require(archives['lossless'] is True and len(archives['archives']) == len(beams), 'Trace archive census differs')
    for archived in archives['archives']:
        require(original_pins.get(archived['original']['path']) == archived['original']
                and Path(archived['archive']['path']).stat().st_size == archived['archive']['size'], 'Archive identity/current size differs')
    raw_bytes = sum(row['original']['size'] for row in archives['archives'])
    compressed_bytes = sum(row['archive']['size'] for row in archives['archives'])
    require(raw_bytes <= prices[case]['maximum_raw_trace_bytes'] < 52428800, 'Actual trace storage exceeds exact price/headroom')
    proposal = table(directory/'native-case/proposal-diagnostics.tsv')
    require(len(proposal) == 1 and proposal[0]['case_id'] == case and proposal[0]['nn_u'] == nn, 'Proposal diagnostics identity differs')
    stage = helper.read_pin(summary['stages'][0])
    native_cost = cost(Path(stage['raw']['time.txt']['path']).read_text())
    outer = read(directory/'execution-complete.json')
    supervisor = Path(outer['terminal']['path']).parent
    stderr = (supervisor/'stderr').read_text()
    service_memory = re.search(r'Memory peak: ([^\n]+)', stderr)
    start, end = ((supervisor/name).read_text().strip() for name in ('start.txt', 'end.txt'))
    rows.append(dict(case_id=case, completion=pin(directory/'execution-complete.json'), native_result=native['result'],
        scalar_comparisons=result['scalar_comparisons'], historical_roles_verified=True,
        sample_source_status=result['sample_source_status'], candidates=len(candidates),
        candidate_origin_counts={str(bits):sum(int(candidate['origins']) == bits for candidate in candidates) for bits in sorted({int(candidate['origins']) for candidate in candidates})},
        source_beam_only_center_count=sum(int(candidate['origins']) & 24 != 0 and int(candidate['origins']) & 7 == 0 for candidate in candidates),
        beams=beams, trace_archives=pin(directory/'native-case/trace-archives.json'), raw_trace_bytes=raw_bytes,
        compressed_trace_bytes=compressed_bytes, raw_trace_price_bytes=prices[case]['maximum_raw_trace_bytes'],
        metadata_full_U_likelihood_bits_and_reported_gates_verified=True,
        proposal=proposal[0], changed_from_native={arm:decision['accepted'] != native_center for arm,decision in decisions.items()},
        changed_from_nn={arm:decision['accepted'] != decisions['nn_u']['accepted'] for arm,decision in decisions.items()},
        gates={arm:decision['gate'] for arm,decision in decisions.items()},
        native_cost=native_cost, whole_unit_wall_seconds=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(),
        service_memory_peak_raw=None if service_memory is None else service_memory[1],
        raw_native_time=stage['raw']['time.txt'], raw_supervisor_stderr=pin(supervisor/'stderr')))
require(set(checkpoint['case_ids']) == {row['case_id'] for row in rows} and len(rows) == 22, 'Actual first32 case census differs')
require(sum(row['raw_trace_bytes'] for row in rows) == sum(row['raw_bytes'] for row in checkpoint['traces'])
        and sum(row['compressed_trace_bytes'] for row in rows) == sum(row['compressed_bytes'] for row in checkpoint['traces']), 'Checkpoint storage sums differ')
for item in checkpoint['traces']:
    actual = next(row for row in rows if row['case_id'] == item['case_id'])
    require(item['raw_bytes'] == actual['raw_trace_bytes'] and item['compressed_bytes'] == actual['compressed_trace_bytes'], 'Checkpoint per-case storage differs')
aggregate = dict(cases=22, new_cases=21, closed_accepted_units=43, original_holes_preserved=10,
    scalar_comparisons=sum(row['scalar_comparisons'] for row in rows), scalar_positive_cases=sum(row['scalar_comparisons'] > 0 for row in rows),
    historical_six_role_cases=22, candidate_centers_sum=sum(row['candidates'] for row in rows),
    source_beam_only_centers=sum(row['source_beam_only_center_count'] for row in rows),
    diagnostic_new_candidates_absent_old_h=sum(int(row['proposal']['new_candidates_absent_old_h']) for row in rows),
    diagnostic_new_candidate_cases=sum(int(row['proposal']['new_candidates_absent_old_h']) > 0 for row in rows),
    diagnostic_neural_gain_positive_cases=sum(float(row['proposal']['proposal_neural_gain']) > 0 for row in rows),
    beams=dict(Counter(beam['status'] for row in rows for beam in row['beams'].values())),
    pruned_beams=sum(beam['pruned'] == '1' for row in rows for beam in row['beams'].values()),
    stored_timesteps=sum(int(beam['steps']) for row in rows for beam in row['beams'].values()),
    stored_finalists=sum(int(beam['finalists']) for row in rows for beam in row['beams'].values()),
    raw_trace_bytes=sum(row['raw_trace_bytes'] for row in rows), compressed_trace_bytes=sum(row['compressed_trace_bytes'] for row in rows),
    changed_from_native={arm:sum(row['changed_from_native'][arm] for row in rows) for arm in config['arms']},
    changed_from_nn={arm:sum(row['changed_from_nn'][arm] for row in rows) for arm in config['arms']},
    sample_source_status=dict(Counter(row['sample_source_status'] for row in rows)),
    largest_native_wall=sorted([dict(case_id=row['case_id'], **row['native_cost']) for row in rows], key=lambda row:row['elapsed_seconds'], reverse=True)[:3],
    largest_native_rss=sorted([dict(case_id=row['case_id'], **row['native_cost']) for row in rows], key=lambda row:row['maximum_rss_kib'], reverse=True)[:3],
    largest_whole_unit_wall=sorted([dict(case_id=row['case_id'], seconds=row['whole_unit_wall_seconds']) for row in rows], key=lambda row:row['seconds'], reverse=True)[:3],
    largest_compressed_traces=sorted([dict(case_id=row['case_id'], raw_bytes=row['raw_trace_bytes'], compressed_bytes=row['compressed_trace_bytes']) for row in rows], key=lambda row:row['compressed_bytes'], reverse=True)[:3],
    cumulative_owned_bytes_at_checkpoint=checkpoint['cumulative_bytes'], descriptive_full_trace_forecast_bytes=checkpoint['descriptive_full_trace_forecast_bytes'], forecast_is_bound=False)
require(pin(config['source_cases']['path']) == config['source_cases'], 'Original source case census pin differs')
source_cases = table(config['source_cases']['path'])
full_ids = {row['case_id'] for row in source_cases}
prepared = read(Path(manifest['prepared']['path']).parent/'prepared.json')
frame_ids = {row['case_id'] for row in table(prepared['frames']['path'])}
require(full_ids == frame_ids and len(full_ids) == 368, 'Frozen full case census differs')
remaining = sorted(full_ids-set(checkpoint['case_ids']), key=lambda case:(case.split('/')[0] != 'ordinary', int(case.split('/')[1]), case))
require(len(remaining) == 346 and all((case.startswith('ordinary/') and int(case.split('/')[1]) >= 32) or case.startswith('private/') for case in remaining), 'Remaining scope differs')
require(sum(case.startswith('ordinary/') for case in remaining) == 289 and sum(case.startswith('private/') for case in remaining) == 57, 'Remaining ordinary/private accounting differs')
qualification = Path(manifest['qualification']['path']).parent
preparation = Path(manifest['prepared']['path']).parent
first32_checkpoint = Path(checkpoint_pin['path']).parent
uv = 'UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/context-sample-feedback.py '
units = []
for case in remaining:
    slug = case.replace('/', '-')
    require(re.fullmatch(r'[A-Za-z0-9_-]+', slug), 'Unsafe fixed case slug')
    price = ROOT/('results/context-sample-feedback/sample-price-remaining-'+slug+'-1')
    infer = ROOT/('results/context-sample-feedback/sample-remaining-'+slug+'-1')
    require(not price.exists() and not infer.exists(), 'Unreviewed existing remaining output')
    units.append(dict(case_id=case, price_output=str(price), infer_output=str(infer), price_inputs=[manifest['prepared']],
        infer_inputs=[manifest['prepared'], 'only actual accepted '+str(price/'execution-complete.json'), checkpoint_pin],
        price_command=uv+'price --scope remaining --case-id '+case+' --qualification '+str(qualification)+' --input '+str(preparation)+' --output '+str(price)+' --admission "$PRICE_GRANT"',
        conditional_infer_command=uv+'infer --scope remaining --case-id '+case+' --qualification '+str(qualification)+' --input '+str(preparation)+' --input '+str(price)+' --input '+str(first32_checkpoint)+' --output '+str(infer)+' --admission "$INFER_GRANT"'))
require(len({item['price_output'] for item in units}) == len({item['infer_output'] for item in units}) == 346, 'Remaining output collision')
proposal = dict(schema='context-sample-feedback-remaining-ready-proposal/1', complete=True, utc=datetime.now(timezone.utc).isoformat(),
    source_identity=manifest['source_identity'], source_inventory=manifest['source_inventory'], config=manifest['config'], qualification=manifest['qualification'],
    prepared=manifest['prepared'], first32_checkpoint=checkpoint_pin, source_case_table=config['source_cases'], case_ids=remaining,
    count=346, ordinary_count=289, private_count=57, reused_completed_case_ids=checkpoint['case_ids'], units=units,
    selection='exact frozen368 case census minus actual22 accepted first32 cases; no availability or outcome filter',
    scope='remaining', arm=None, source_audit=None, recovery=None, caps=manifest['caps'], disk_floor_bytes=32212254720,
    admission_interval_seconds=300, no_remaining_execution_admitted=True, no_grants_instantiated=True,
    scientific_source_and_all_0_5_gates_unchanged=True, all_private_and_ordinary_choices_frozen_before_truth=True,
    physical_read_independence_qualified=False, promotion_eligible=False)
helper.fresh(args.remaining_proposal, proposal)
record = dict(schema='context-sample-feedback-first32-audit/1', complete=True, utc=datetime.now(timezone.utc).isoformat(),
    scientific_source_identity=manifest['source_identity'], scientific_source_count=89,
    dispatch_completion=pin(DISPATCH/'complete.json'), checkpoint=checkpoint_pin, aggregate=aggregate, cases=rows,
    exec_parent_exit=0, exec_parent_session=5763, exec_parent_observation='tools.write_stdin returned exit_code0 and no session_id',
    native_units_independently_metadata_rechecked=43, actual_closed_parent_receipts=43,
    deep_archive_byte_validation_ran_inside_each_bounded_cli_and_first32_checkpoint=True,
    posthoc_archive_check_is_only_sealed_original_identity_and_current_file_size=True,
    no_trace_payload_decompression_or_hash_outside_units=True, no_DGS_reference_GT_or_scoring_outside_units=True,
    full_likelihood_bit_and_reported_objective_checks_are_metadata_arithmetic=True,
    neural_likelihoods_and_source_potentials_not_recomputed=True,
    costs_are_different_cases_once_each_not_performance_comparison=True,
    remaining_proposal=pin(args.remaining_proposal), remaining_cases=346,
    explicit_metadata_read_bytes=total, metadata_read_limit_bytes=64*1024**2,
    read_paths=dict(reads), physical_read_independence_qualified=False, promotion_eligible=False)
helper.fresh(args.output, record)
print(json.dumps(dict(audit=pin(args.output), checkpoint=checkpoint_pin, aggregate=aggregate,
                     metadata_read_bytes=total, remaining_proposal=record['remaining_proposal'], remaining_cases=346)))
