#!/usr/bin/env python3
"""Export a complete controlled stock baseline from retained evidence, without native work."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from statistics import mean, median, stdev
import subprocess

import benchmark as b

ROOT = Path(__file__).resolve().parents[1]
TIERS = ('hac', 'sup')
DOMAINS = (100, 500)
FULL_IDS = {f'full-{role}-{tier}' for role in ('development', 'validation', 'sealed_test') for tier in TIERS}
TIMING_IDS = {f'timing-{rep}-{tier}' for rep in range(1, 6) for tier in TIERS}
EXPECTED_IDS = FULL_IDS | TIMING_IDS | {'smoke-1-hac', 'smoke-1-sup', 'split-fixture-hac'}
STAGES = {'align', 'aligned-decode', 'aligned-quickcheck', 'aligned-summary', 'base-decode',
          'base-quickcheck', 'base-summary', 'basecall', 'calmd', 'calmd-decode', 'flagstat', 'sort', 'stats'}
SMALL_PIN_LIMIT = 2 * 1024**2
INCIDENT_PLAN = '1c995eba5d6454a6ef8a8fc6dcd767fd9e9aead811389da38f3906ddaf6815e0'
INCIDENT_NOTES = 'provenance/verification/controlled-measurement-notes-20261023.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_pin(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024**2), b''):
            digest.update(block)
    return {'path': str(path), 'size': path.stat().st_size, 'sha256': digest.hexdigest()}


def number(value, label, positive=False):
    require(isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value), f'{label}: finite number required')
    require(value > 0 if positive else value >= 0, f'{label}: invalid nonpositive/negative value')
    return value


def count(value, label):
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f'{label}: nonnegative integer required')
    return value


def close(actual, expected, label):
    number(actual, label)
    require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12), f'{label}: inconsistent rate/count')


def unique(items, key, label):
    result = {item[key]: item for item in items}
    require(len(result) == len(items), f'{label}: duplicate identity')
    return result


def pin_for(pins, path):
    # Native pin() already stores absolute resolved paths. Resolve the lookup
    # once; resolving every manifest entry made joins needlessly quadratic.
    target = str(Path(path).resolve())
    found = [p for p in pins if p['path'] == target]
    require(found and all(p == found[0] for p in found), f'Missing/conflicting bound pin: {path}')
    return found[0]


def validate_score(row, unit, plan, inputs, truth):
    label = f"{row['unit']}/{row['padding']}"
    score, producer = row['score'], row['producer']
    for key in ('expected_parents', 'represented_parents', 'absent_parents', 'positive_denominator_parents', 'children', 'alignment_columns', 'eligible_query_columns', 'eligible_reference_columns'):
        count(score[key], f'{label}/{key}')
    require(row['tier'] == unit['tier'] and row['sample'] == unit['asset']['sample'], f'{label}: foreign tier/sample')
    require(producer['status'] == 'finished' and producer['exit'] == 0 and not producer.get('failure'), f'{label}: native scorer failed')
    context = producer['context']
    require(context['plan'] == plan['sha256'] and context['unit'] == unit['id'] and context['padding'] == row['padding'], f'{label}: foreign scorer context')
    require(context['sources'] == truth['sources'], f'{label}: scorer source mismatch')
    domain = truth['truth'][f"{row['sample']}-{row['padding']}"]
    require(context['truth'] == pin_for(truth['pins'], Path(domain['directory']) / 'eligible.bed'), f'{label}: wrong truth domain pin')
    require(context['parents'] == pin_for(plan['pins'], unit['ids']), f'{label}: wrong input parent pin')
    require(producer['argv'][0] == truth['binary'], f'{label}: wrong retained scorer binary')
    require(score['schema'] == 1 and score['min_mapq'] == inputs['config']['min_mapq'] == 30, f'{label}: unsupported scoring policy')
    require(score['endpoint'] == 'giab_invariant_sequence_alignment_column_error', f'{label}: unsupported endpoint')
    c = score['counts']
    require(set(c) == {'m', 'x', 'i', 'd'}, f'{label}: incomplete M/X/I/D')
    for key, value in c.items():
        count(value, f'{label}/{key}')
    columns = sum(c.values())
    require(columns > 0 and score['alignment_columns'] == columns, f'{label}: zero/inconsistent alignment columns')
    require(score['eligible_query_columns'] == c['m'] + c['x'] + c['i'], f'{label}: query denominator mismatch')
    require(score['eligible_reference_columns'] == c['m'] + c['x'] + c['d'], f'{label}: reference denominator mismatch')
    close(score['aggregate_error_fraction'], (c['x'] + c['i'] + c['d']) / columns, label + '/error')
    close(score['aggregate_accuracy'], c['m'] / columns, label + '/accuracy')
    close(score['parent_mean_accuracy'], 1 - score['parent_mean_error_fraction'], label + '/parent mean')
    for key in ('aggregate_accuracy', 'aggregate_error_fraction', 'parent_mean_accuracy', 'parent_mean_error_fraction'):
        number(score[key], label + '/' + key)
        require(score[key] <= 1, f'{label}: rate outside [0,1]')
    require(score['expected_parents'] == len(unit['parents']), f'{label}: input parent count mismatch')
    require(score['represented_parents'] + score['absent_parents'] == score['expected_parents'], f'{label}: parent conservation failed')
    require(0 < score['positive_denominator_parents'] <= score['represented_parents'], f'{label}: no positive parent exposure')
    for status, n in score['statuses'].items():
        require(status in {'selected', 'unmapped', 'low_mapq', 'unknown_mapq', 'nonautosomal', 'no_eligible_columns'}, f'{label}: unknown child status')
        count(n, f'{label}/{status}')
    require(sum(score['statuses'].values()) == score['children'], f'{label}: child status conservation failed')
    losses = score['losses']
    for key, n in losses.items():
        count(n, f'{label}/loss/{key}')
    require(losses['query_bases'] == sum(losses[k] for k in ('excluded_query_bases', 'policy_excluded_query_bases', 'soft_clipped', 'unmapped_query_bases')) + score['eligible_query_columns'], f'{label}: called-query loss conservation failed')
    bootstrap = score['bootstrap']
    require(bootstrap['status'] == 'available' and bootstrap['replicates'] == 2000 and bootstrap['scope'] == 'technical_within_flowcell_only', f'{label}: technical bootstrap unavailable')
    require(bootstrap['seed'] == '0x4e414e4f504f5245' and bootstrap['unit'] == 'positive_denominator_source_parent', f'{label}: wrong bootstrap protocol')
    for key in ('aggregate_error_fraction_95_percentile', 'parent_mean_error_fraction_95_percentile'):
        ci = bootstrap[key]
        for value in ci:
            number(value, label + '/bootstrap CI')
        require(len(ci) == 2 and 0 <= ci[0] <= ci[1] <= 1, f'{label}: invalid bootstrap interval')
    labels = {'length_strata': {'0-999', '1000-9999', '10000-49999', '50000+'},
              'native_qscore_strata': {'unavailable', '<10', '10-<20', '20-<30', '30+'},
              'homopolymer_context': {'1', '2-3', '4-6', '7-10', '11+'}}
    for key, valid_labels in labels.items():
        require(set(score[key]) <= valid_labels, f'{label}: unknown {key} bin')
        for bin_name, bin_ in score[key].items():
            require(set(bin_) == set(c), f'{label}: incomplete {key} bin')
            for column, n in bin_.items():
                count(n, f'{label}/{key}/{bin_name}/{column}')
        for column in c:
            require(sum(bin_[column] for bin_ in score[key].values()) == c[column], f'{label}: {key} count mismatch')
    qbins = score['qscore']
    require(sum(b['query_columns'] for b in qbins.values()) == score['eligible_query_columns'], f'{label}: Q denominator mismatch')
    require(sum(b['errors_x_i'] for b in qbins.values()) == c['x'] + c['i'], f'{label}: Q error mismatch')
    for q, bin_ in qbins.items():
        n, errors = count(bin_['query_columns'], label + '/Q n'), count(bin_['errors_x_i'], label + '/Q errors')
        require(errors <= n and 0 <= int(q) <= 93, f'{label}: invalid Q bin')
        expected = n * 10 ** (-int(q) / 10)
        require(math.isclose(bin_['expected_error_sum'], expected, rel_tol=1e-7, abs_tol=1e-9), f'{label}: Q expectation mismatch')
    hp = score['homopolymer_length_endpoint']
    count(hp['observations'], label + '/homopolymer observations')
    require(set(score['homopolymer_length_counts']) <= labels['homopolymer_context'] - {'1'}, f'{label}: unknown homopolymer length bin')
    for bin_ in score['homopolymer_length_counts'].values():
        require(set(bin_) == {'correct', 'under', 'over', 'complex'}, f'{label}: incomplete homopolymer outcomes')
        for n in bin_.values():
            count(n, label + '/homopolymer count')
    require(sum(sum(bin_.values()) for bin_ in score['homopolymer_length_counts'].values()) == hp['observations'], f'{label}: homopolymer count mismatch')


def validate_bundle(bundle, current_verifier, current_sources, amendment):
    """Pure JSON acceptance boundary; no decoding, scoring, or large-file hashing."""
    plan, report, qualification = (bundle[k] for k in ('plan', 'stock', 'qualification'))
    inputs, truth = bundle['inputs'], bundle['truth']
    require(plan['schema'] == inputs['schema'] == 1, 'Unsupported plan/input schema')
    require(plan['sha256'] == identity({k: v for k, v in plan.items() if k != 'sha256'}), 'Changed plan identity')
    require(inputs['identity'] == identity({k: v for k, v in inputs.items() if k != 'identity'}), 'Changed accuracy input identity')
    planned = unique(plan['units'], 'id', 'plan')
    units = unique(report['units'], 'unit', 'stock report')
    require(set(planned) == set(units) == EXPECTED_IDS, 'Exact 19 controlled stock units required')
    for role in ('development', 'validation', 'sealed_test'):
        left, right = (planned[f'full-{role}-{tier}'] for tier in TIERS)
        require(left['parents'] == right['parents'] and left['asset'] == right['asset'], f'{role}: model input membership mismatch')
    require(report['plan'] == qualification['plan'] == plan['sha256'], 'Stock plan identity mismatch')
    require(qualification['status'] == 'verified' and qualification['verifier_sha256'] == current_verifier, 'Current native qualification required')
    expected_controls = {(name, control) for name in ('smoke-1-hac', 'smoke-1-sup')
                         for control in ('foreign', 'duplicate', 'model', 'truncated', 'reference', 'NM', 'removed-parent')}
    expected_controls |= {('split-fixture-hac', control) for control in ('foreign', 'duplicate', 'model', 'split-sp', 'split-pi', 'truncated', 'removed-parent')}
    controls = qualification['controls']
    require(len(controls) == len(expected_controls) and {(c['unit'], c['control']) for c in controls} == expected_controls, 'Exact native qualification controls required')
    require(all(c['status'] == ('absence recorded or empty rejected' if c['control'] == 'removed-parent' else 'rejected') for c in controls), 'Native qualification control failed')
    require(truth['status'] == 'verified' and truth['inputs_identity'] == inputs['identity'], 'Truth/input qualification mismatch')
    require(truth['sources'] == current_sources, 'Current accuracy source/tool pins required')
    require(truth['amendment'] == amendment and amendment['version'] == '1.1', 'Frozen v1.1 truth amendment required')
    require(inputs['config']['padding_and_confidence_erosion_bp'] == list(DOMAINS), 'Both predeclared domains required')
    require(set(truth['truth']) == {f'{sample}-{padding}' for sample in ('HG002', 'HG005') for padding in DOMAINS}, 'Exact four truth domains required')
    for key, domain in truth['truth'].items():
        diag, producer = domain['diagnostics'], domain['producer']
        require(key == f"{diag['sample']}-{diag['padding']}" and diag['eligible_bases'] > 0, f'{key}: invalid truth exposure')
        require(diag['spanning_policy'] == amendment['spanning_policy'], f'{key}: wrong star policy')
        require(producer['status'] == 'finished' and producer['exit'] == 0 and not producer.get('failure'), f'{key}: truth native producer failed')
        require(producer['context']['inputs'] == inputs['identity'] and producer['context']['sources'] == truth['sources'] and producer['context']['amendment'] == amendment, f'{key}: foreign truth producer')
        ordered = list(diag['ordered_domain_bases'].values())
        require(all(a >= b >= 0 for a, b in zip(ordered, ordered[1:])) and ordered[-1] == diag['eligible_bases'], f'{key}: truth census mismatch')
        require(diag['spanning_removed_union_bases'] == sum(item['end'] - item['start'] for item in diag['spanning_removed_intervals']), f'{key}: star removal census mismatch')
    policy = plan['config']['measurement_policy']
    require(policy == b.CONTROLLED_POLICY, 'Frozen controlled measurement policy required')
    require(report['measurement_policy'] == policy, 'Report measurement policy mismatch')
    expected_policy = {**policy, 'cpu_affinity': plan['environment']['cpu_affinity']}
    attempts = []
    for name, unit in units.items():
        p, obs = planned[name], unit['observation']
        require(unit['scope'] == p['scope'] and unit['tier'] == p['tier'], f'{name}: scope/tier mismatch')
        require(unit['status'] == 'verified' and obs and obs['status'] == 'verified', f'{name}: stock unit not verified')
        require(obs['unit'] == name and obs['plan'] == plan['sha256'], f'{name}: foreign stock observation')
        require(obs['verifier_sha256'] == current_verifier, f'{name}: current verifier required')
        require(obs['measurement_qualified'] is True and obs['measurement_policy'] == expected_policy, f'{name}: observation measurement unqualified')
        calmd = obs['calmd_verification']
        require(calmd['status'] == 'verified' and calmd['all_other_primary_fields_equal'] is True, f'{name}: calmd verification required')
        reference_stage = calmd['reference_check_stage']
        require(reference_stage in (None, 'calmd-reference-iupac'), f'{name}: unknown reference check')
        require(not reference_stage or name in {'full-validation-hac', 'full-validation-sup'}, f'{name}: unexpected IUPAC reference-check unit')
        if reference_stage is None:
            require(calmd['exact_md_agreement'] is True and calmd['md_reference_ambiguity_bases'] == calmd['md_reference_ambiguity_records'] == 0
                    and calmd['md_reference_ambiguity_exceptions'] == [], f'{name}: missing calmd exception check')
        required_stages = STAGES | ({reference_stage} if reference_stage else set())
        require(set(unit['stages']) == required_stages, f'{name}: core 13 native stages and declared reference check required')
        for stage_name, stage in unit['stages'].items():
            require(stage['status'] == 'finished' and stage['exit'] == 0 and not stage.get('failure') and stage['measurement_qualified'] is True, f'{name}/{stage_name}: native measurement failed')
            resources = stage['resources']
            require(resources['measurement_qualified'] is True, f'{name}/{stage_name}: resource measurement unqualified')
            number(resources['native_wall_seconds'], name + '/native clock')
            for field in ('recorder_elapsed_seconds', 'host_max_rss_kib', 'user_cpu_seconds', 'system_cpu_seconds'):
                number(resources[field], name + '/' + field)
            history = stage['attempts']
            require(history and history[-1]['receipt'] == stage['receipt'] and history[-1]['status'] == stage['status'] and history[-1]['exit'] == stage['exit'], f'{name}/{stage_name}: latest attempt mismatch')
            require(len({a['receipt'] for a in history}) == len(history), f'{name}/{stage_name}: duplicate attempt')
            for attempt in history:
                attempts.append({'unit': name, 'stage': stage_name, **attempt})
        number(obs['basecall_process_wall_seconds'], name + '/basecall wall', positive=True)
        close(obs['basecall_process_wall_seconds'], unit['stages']['basecall']['resources']['native_wall_seconds'], name + '/native basecall wall')
        base = obs['basecall']
        require(base['metrics']['requested_parents'] == len(p['parents']), f'{name}: requested parent count mismatch')
        require(base['metrics']['represented_parents'] + len(base['missing_parents']) == len(p['parents']), f'{name}: stock parent count mismatch')
        require(base['metrics']['children'] >= base['metrics']['represented_parents'], f'{name}: child/parent count mismatch')
        if p['scope'] == 'smoke':
            require(len(p['parents']) == 32 and base['complete_processing'] is True and obs['complete_work_qualification'] == 'verified', f'{name}: complete 32-parent smoke required')
        if p['scope'] == 'fixture':
            require(len(p['parents']) == base['metrics']['represented_parents'] == 1 and base['metrics']['split_parents'] == 1 and base['metrics']['children'] >= 2, f'{name}: genuine split fixture required')
        if p['scope'] == 'timing':
            development = planned[f"full-development-{p['tier']}"]
            require(p['parents'] == development['parents'] and len(p['parents']) == 2608 and sum(p['parents'].values()) == 641769607, f'{name}: full development timing membership required')
            require(obs['complete_work_qualification'] == 'verified' and base['complete_processing'] is True and not base['missing_parents'] and not obs['native_loader_error_lines'], f'{name}: incomplete timing workload')
        failures = unit.get('observation_failures', [])
        require(all(f.get('completed_ns', 0) < obs['completed_ns'] for f in failures), f'{name}: newer verification failure')
    all_attempts = attempts + report['other_native_processes']
    counts = dict(Counter(a['status'] for a in all_attempts))
    counts['total'] = len(all_attempts)
    require(counts == report['native_process_attempt_counts'], 'Native attempt count mismatch; failures may be hidden')
    for tier in TIERS:
        timing = report['timing'][tier]
        require(timing['planned'] == timing['successful'] == 5 and timing['complete_work_baseline'] is True, f'{tier}: five complete timing observations required')
        require(timing['basecall_attempts'] == sum(a['stage'] == 'basecall' and units[a['unit']]['scope'] == 'timing' and units[a['unit']]['tier'] == tier for a in attempts), f'{tier}: attempt summary mismatch')
    for scope, names in [('full', FULL_IDS), ('timing', TIMING_IDS)]:
        accuracy = bundle['accuracy'].get(scope)
        if scope == 'timing' and accuracy is None:
            continue
        require(accuracy is not None, 'Full accuracy report required')
        require(accuracy['status'] == 'verified' and accuracy['scope'] == scope and accuracy['plan'] == plan['sha256'] and accuracy['inputs'] == inputs['identity'], f'{scope}: foreign accuracy report')
        require(accuracy['domain'] == amendment['endpoint'] and accuracy['sample_identity'] == inputs['config']['sample_identity'], f'{scope}: endpoint/sample identity mismatch')
        rows = accuracy['units']
        pairs = {(r['unit'], r['padding']) for r in rows}
        require(len(pairs) == len(rows) and pairs == {(name, padding) for name in names for padding in DOMAINS}, f'{scope}: exact unit/domain pairs required')
        for row in rows:
            validate_score(row, planned[row['unit']], plan, inputs, truth)
            score, base = row['score'], units[row['unit']]['observation']['basecall']['metrics']
            require(score['children'] == base['children'] and score['represented_parents'] == base['represented_parents'] and score['losses']['query_bases'] == base['called_bases'], f"{row['unit']}: score/native ledger count mismatch")
    return planned, units, attempts


class Reader:
    def __init__(self, verify_pins=False):
        self.verify_pins = verify_pins
        self.pins = {}
        self.checked = set()

    def retain(self, pins):
        for pin in pins:
            path = str(Path(pin['path']).resolve())
            require(re.fullmatch('[0-9a-f]{64}', pin['sha256']) and isinstance(pin['size'], int) and pin['size'] >= 0, f'Malformed pin: {path}')
            old = self.pins.get(path)
            require(old is None or old == pin, f'Conflicting artifact pins: {path}')
            self.pins[path] = pin
            if path in self.checked:
                continue
            require(Path(path).is_file() and Path(path).stat().st_size == pin['size'], f'Artifact missing/size changed: {path}')
            # Default stays metadata-only for large native outputs and raw inputs.
            metadata = Path(path).suffix in ('.json', '.jsonl', '.csv', '.txt') or Path(path).name == 'command.sh'
            if self.verify_pins or metadata or pin['size'] <= SMALL_PIN_LIMIT:
                require(file_pin(path) == pin, f'Artifact pin changed: {path}')
            self.checked.add(path)

    def read(self, path):
        path = Path(path).resolve()
        value = json.loads(path.read_text())
        self.retain([file_pin(path)])
        return value


def load_bundle(stock, accuracy, inputs_path, reader):
    bundle = {'plan': reader.read(stock / 'plan.json'), 'stock': reader.read(stock / 'report.json'),
              'qualification': reader.read(stock / 'qualification.json'), 'inputs': reader.read(inputs_path),
              'truth': reader.read(accuracy / 'truth-qualified.json'), 'accuracy': {}}
    plan = bundle['plan']
    require(len(bundle['stock']['units']) == 19 and all(u['status'] == 'verified' for u in bundle['stock']['units']), 'Incomplete stock snapshot: all 19 verified units required')
    for item in ('plan', 'qualification', 'inputs', 'truth'):
        reader.retain(bundle[item]['pins'])
    sources = reader.read(accuracy / 'sources.json')
    require(sources['sources'] == bundle['truth']['sources'] and sources['inputs'] == bundle['inputs']['identity'] and sources['amendment'] == bundle['truth']['amendment'], 'Retained source context mismatch')
    for source in bundle['truth']['sources']:
        require(file_pin(source['path']) == source, f"Current source/tool changed: {source['path']}")
    require(bundle['inputs']['config'] == reader.read(ROOT / 'config/accuracy-v1.json'), 'Accuracy config differs from current pinned v1 protocol')
    frozen_config = reader.read(ROOT / 'config/controlled-stock-benchmark.json')
    require(pin_for(plan['pins'], ROOT / 'config/controlled-stock-benchmark.json') == file_pin(ROOT / 'config/controlled-stock-benchmark.json'), 'Controlled config is not bound to plan')
    normalized_config = {**frozen_config, 'models': {tier: str((ROOT / path).resolve()) for tier, path in frozen_config['models'].items()}}
    for key in ('dorado', 'samtools'):
        tool = frozen_config[key]
        normalized_config[key] = str((ROOT / (Path(tool) if '/' in tool else Path(shutil.which(tool) or tool))).resolve())
    require(plan['config'] == normalized_config, 'Plan config differs from frozen controlled protocol')
    require(plan['tool_versions']['dorado'].strip() == '2.1.2+8b8fc5d', 'Unchanged stock Dorado version required')
    require(set(plan['config']['models']) == set(plan['model_trees']) == set(TIERS), 'Both stock model trees required')
    for tier, tree in plan['model_trees'].items():
        path = Path(tree['path'])
        require(path.resolve() == Path(plan['config']['models'][tier]).resolve(), 'Model tree/config mismatch')
        require(sorted(str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()) == tree['files'], f'{tier}: changed model tree membership')
    reference = ROOT / plan['config']['reference']
    require(pin_for(plan['pins'], reference) == pin_for(bundle['inputs']['pins'], reference), 'Stock/accuracy full reference pin mismatch')
    bundle['warmup'] = validate_warmup(stock, plan, reader)
    for unit in bundle['stock']['units']:
        if unit.get('observation'):
            actual = reader.read(stock / 'units' / unit['unit'] / 'observation.json')
            require(actual == unit['observation'], f"Stock report observation changed: {unit['unit']}")
            reader.retain(actual['pins'])
        if unit['scope'] in ('full', 'timing'):
            basecall = reader.read(unit['stages']['basecall']['receipt'])
            require(datetime.fromisoformat(bundle['warmup']['native']['end_utc']) <= datetime.fromisoformat(basecall['native_launch_utc']), 'Filesystem warmup did not precede measured basecalling')
        unit_root = stock / 'units' / unit['unit']
        actual_stage_names = {p.parent.parent.name for p in unit_root.glob('*/*/start.json')}
        require(actual_stage_names == set(unit['stages']), 'Stock report hides native stage directories')
        expected_policy = {**plan['config']['measurement_policy'], 'cpu_affinity': plan['environment']['cpu_affinity']}
        for stage_name, stage in unit['stages'].items():
            starts = sorted((unit_root / stage_name).glob('*/start.json'))
            actual_paths = [str(p.parent / ('finish.json' if (p.parent / 'finish.json').exists() else 'start.json')) for p in starts]
            require(actual_paths == [a['receipt'] for a in stage['attempts']], 'Stock report hides/reorders native attempts')
            bound, _ = bound_stage(unit['observation'], unit_root, stage_name, reader)
            require(str(bound) == stage['receipt'], 'Current stage differs from observation-bound producer')
            for attempt in stage['attempts']:
                receipt = reader.read(attempt['receipt'])
                require(receipt['status'] == attempt['status'] and receipt['exit'] == attempt['exit'], 'Native attempt receipt mismatch')
                require(receipt.get('failure') == attempt.get('failure') and receipt.get('measurement_qualified') == attempt.get('measurement_qualified'), 'Native attempt measurement/failure mismatch')
                require(receipt['context'] == {'plan': plan['sha256'], 'unit': unit['unit']}, 'Foreign stock native context')
                reader.retain(receipt.get('pins', []))
                if receipt['status'] == 'finished':
                    expected_argv = stock_argv(plan, unit, stage_name, reader) if attempt['receipt'] == stage['receipt'] else receipt['argv']
                    validate_native_receipt(receipt, expected_argv, {'plan': plan['sha256'], 'unit': unit['unit']}, reader,
                                            Path(attempt['receipt']), expected_policy, stage_name == 'basecall',
                                            latest=attempt['receipt'] == stage['receipt'])
                    b.measurement_evidence(receipt, expected_policy)
                    validate_resources(receipt, attempt['resources'])
                    if stage_name == 'calmd-reference-iupac' and attempt['receipt'] == stage['receipt']:
                        validate_iupac(unit['observation']['calmd_verification'], Path(receipt['stdout']))
            require(all(stage[k] == stage['attempts'][-1][k] for k in ('receipt', 'status', 'exit', 'resources', 'measurement_qualified', 'failure')), 'Stock latest native stage projection mismatch')
    for domain in bundle['truth']['truth'].values():
        require(reader.read(Path(domain['directory']) / 'truth.json') == domain['diagnostics'], 'Truth diagnostics changed')
        diag = domain['diagnostics']
        truth_input = bundle['inputs']['truth'][diag['sample']]
        spans = reader.read(inputs_path.parent / 'original-spans.json')
        argv = [bundle['truth']['binary'], 'truth', '--reference', bundle['inputs']['reference'], '--vcf', truth_input['vcf'],
                '--confident', truth_input['confident'], '--sample', diag['sample'], '--padding', str(diag['padding']),
                '--output', domain['directory'], '--original-footprints', spans['samples'][diag['sample']]['bed'],
                '--spanning-policy', bundle['truth']['amendment']['spanning_policy']]
        for path in bundle['inputs']['exclusions']:
            argv.extend(['--exclusions', path])
        validate_native_receipt(domain['producer'], argv, sources, reader)
    validate_other_processes(stock, plan, bundle['stock']['other_native_processes'], reader)
    for scope in ('full', 'timing'):
        path = accuracy / f"report-{plan['sha256']}-{scope}.json"
        if not path.exists():
            continue
        report = reader.read(path)
        bundle['accuracy'][scope] = report
        for row in report['units']:
            output = accuracy / 'scores' / plan['sha256'] / row['unit'] / str(row['padding'])
            require(reader.read(output / 'observation.json') == row, 'Accuracy report observation changed')
            require(reader.read(output / 'score.json') == row['score'], 'Accuracy score JSON changed')
            reader.retain(row['pins'])
            stock_path = stock / 'units' / row['unit'] / 'observation.json'
            require(pin_for(row['pins'], stock_path) == file_pin(stock_path), 'Accuracy bound to a different stock observation')
            producer = row['producer']
            starts = list((accuracy / 'score-stages' / plan['sha256'] / row['unit'] / str(row['padding'])).glob('*/finish.json'))
            matches = [p for p in starts if json.loads(p.read_text()).get('key') == producer['key']]
            require(len(matches) == 1 and reader.read(matches[0]) == producer, 'Scorer producer receipt changed/ambiguous')
            stock_unit = next(u for u in bundle['stock']['units'] if u['unit'] == row['unit'])
            observation = stock_unit['observation']
            sam_pin = producer['context']['sam']
            decoder_path, decoder = bound_stage(observation, stock / 'units' / row['unit'], 'aligned-decode', reader)
            require(str(decoder_path) == stock_unit['stages']['aligned-decode']['receipt'], 'Scorer decoder is not the current observation-bound stage')
            require(sam_pin == pin_for(decoder['pins'], decoder['stdout']) == pin_for(observation['pins'], decoder['stdout']), 'Scorer SAM not bound to exact aligned decoder')
            planned = next(u for u in plan['units'] if u['id'] == row['unit'])
            domain = bundle['truth']['truth'][f"{row['sample']}-{row['padding']}"]
            argv = [bundle['truth']['binary'], 'score', '--reference', bundle['inputs']['reference'], '--eligible', str(Path(domain['directory']) / 'eligible.bed'),
                    '--sam', decoder['stdout'], '--parents', planned['ids'], '--output', str(output), '--min-mapq', str(bundle['inputs']['config']['min_mapq'])]
            context = {'plan': plan['sha256'], 'unit': row['unit'], 'padding': row['padding'],
                       'truth': pin_for(bundle['truth']['pins'], Path(domain['directory']) / 'eligible.bed'),
                       'sam': sam_pin, 'parents': pin_for(plan['pins'], planned['ids']), 'sources': bundle['truth']['sources']}
            validate_native_receipt(producer, argv, context, reader, matches[0])
    return bundle


def bound_stage(observation, unit_root, stage, reader):
    """The accuracy.observation_stage join, using retained SAM pins without rehashing SAM."""
    paths = [Path(p['path']) for p in observation['pins'] if Path(p['path']).name == 'finish.json'
             and Path(p['path']).parent.parent == unit_root / stage]
    require(len(paths) == 1, 'Missing/ambiguous observation-bound decoder receipt')
    path = paths[0]
    require(file_pin(path) == pin_for(observation['pins'], path), 'Observation-bound native receipt changed')
    receipt = reader.read(path)
    output_pin = pin_for(receipt['pins'], receipt['stdout'])
    require(output_pin == pin_for(observation['pins'], receipt['stdout']), 'Decoded SAM is not bound to stock observation')
    reader.retain([output_pin])
    return path, receipt


def validate_warmup(stock, plan, reader):
    warmup = reader.read(stock / 'filesystem-warmup.json')
    config = plan['config']
    paths = {ROOT / config['reference'], ROOT / config['index'], Path(config['dorado']), Path(config['samtools'])}
    paths.update(ROOT / unit['asset']['path'] for unit in plan['units'])
    for tree in plan['model_trees'].values():
        paths.update(Path(tree['path']) / name for name in tree['files'])
    paths.update(path for path in (Path(config['dorado']).parent.parent / 'lib').rglob('*') if path.is_file())
    paths.update(ROOT / (config['reference'] + suffix) for suffix in ('.fai', '.gzi'))
    files = sorted(str(path.resolve()) for path in paths)
    inputs = [pin_for(plan['pins'], path) for path in files]
    context = {'plan': plan['sha256'], 'warmup_source': file_pin(ROOT / 'scripts/warm-stock-inputs.py'), 'inputs': inputs,
               'policy': 'sequential native cat of runtime inputs; stdout discarded; no cache flush'}
    require(warmup['status'] == 'verified' and warmup['context'] == context, 'Filesystem warmup plan/input/source mismatch')
    require(warmup['files'] == len(files) and warmup['bytes'] == sum(p['size'] for p in inputs), 'Filesystem warmup census mismatch')
    reader.retain(warmup['pins'] + inputs + [context['warmup_source']])
    validate_native_receipt(warmup['native'], ['bash', '-c', 'cat -- "$@" > /dev/null', '--', *files], context, reader)
    return warmup


def validate_other_processes(stock, plan, reported, reader):
    """Inventory every retained qualification/preparation attempt, including failures."""
    expected = []
    for start in sorted((stock / 'controls').glob('*/*/*/start.json')):
        finish = start.parent / 'finish.json'
        receipt = reader.read(finish if finish.exists() else start)
        if finish.exists():
            validate_native_receipt(receipt, receipt['argv'], receipt['context'], reader, finish, latest=False)
        else:
            receipt = {**receipt, 'status': 'interrupted', 'exit': None}
        expected.append({'kind': 'qualification_control', 'receipt': str(finish if finish.exists() else start),
                         'status': receipt['status'], 'exit': receipt['exit']})
    for name in plan['preparation_runs']:
        run = ROOT / name
        pins = [pin_for(plan['pins'], run / item) for item in ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')]
        reader.retain(pins)
        exit_code = int((run / 'exit-status.txt').read_text())
        require(Path((run / 'cwd.txt').read_text().strip()).resolve() == ROOT.resolve(), 'Preparation raw cwd mismatch')
        require(datetime.fromisoformat((run / 'start.txt').read_text().strip()) <= datetime.fromisoformat((run / 'end.txt').read_text().strip()), 'Preparation raw UTC clocks out of order')
        raw_exit = re.search(r'Exit status: ([0-9]+)', (run / 'time.txt').read_text())
        require(raw_exit is not None and int(raw_exit[1]) == exit_code and (run / 'command.sh').read_text().strip(), 'Preparation raw exit/command unavailable')
        expected.append({'kind': 'preparation', 'recorder': str(run), 'status': 'finished' if exit_code == 0 else 'command_failed', 'exit': exit_code})
    projected = [{key: item.get(key) for key in row} for row, item in zip(expected, reported)]
    require(len(expected) == len(reported) and projected == expected, 'Other native process inventory/status mismatch; retained failures may be hidden')


def stock_argv(plan, unit, name, reader):
    config = plan['config']
    planned = next(p for p in plan['units'] if p['id'] == unit['unit'])
    unit_root = Path(unit['stages']['basecall']['receipt']).parent.parent.parent

    def output(stage):
        path, receipt = bound_stage(unit['observation'], unit_root, stage, reader)
        require(str(path) == unit['stages'][stage]['receipt'], 'Current stage differs from observation-bound producer')
        return receipt['stdout']

    d, s = config['dorado'], config['samtools']
    if name == 'basecall':
        return list(map(str, [d, 'basecaller', ROOT / config['models'][planned['tier']], ROOT / planned['asset']['path'],
                            '--read-ids', planned['ids'], '--device', 'cuda:0', '--batchsize', '0', '--min-qscore', '0', '--trim', 'all', '-v']))
    if name == 'base-quickcheck':
        return [s, 'quickcheck', '-u', '-v', output('basecall')]
    if name == 'base-decode':
        return [s, 'view', '-h', output('basecall')]
    if name == 'base-summary':
        return [d, 'summary', output('basecall')]
    if name == 'align':
        return [d, 'aligner', str(ROOT / config['index']), output('basecall'), '--threads', '16', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y']
    if name == 'sort':
        return [s, 'sort', '-@', '3', '-m', '256M', '-O', 'BAM', output('align')]
    if name == 'aligned-quickcheck':
        return [s, 'quickcheck', '-v', output('sort')]
    if name == 'aligned-decode':
        return [s, 'view', '-h', output('sort')]
    if name == 'aligned-summary':
        return [d, 'summary', output('sort')]
    if name == 'flagstat':
        return [s, 'flagstat', '-O', 'json', output('sort')]
    if name == 'stats':
        return [s, 'stats', '-F', '0x900', '-r', str(ROOT / config['reference']), output('sort')]
    if name == 'calmd':
        return [s, 'calmd', '-b', output('sort'), str(ROOT / config['reference'])]
    if name == 'calmd-decode':
        return [s, 'view', '-h', output('calmd')]
    require(name == 'calmd-reference-iupac' and unit['unit'] in {'full-validation-hac', 'full-validation-sup'}, 'Unexpected native stage')
    exceptions = unit['observation']['calmd_verification']['md_reference_ambiguity_exceptions']
    require(exceptions and all(e['native_md_base'] == 'N' and e['calmd_md_base'] == e['reference_base'] and e['reference_base'] in 'RYSWKMBDHV' for e in exceptions), 'Invalid coordinate-confirmed IUPAC exceptions')
    regions = sorted({f"{e['contig']}:{e['reference_position_1based']}-{e['reference_position_1based']}" for e in exceptions})
    return [s, 'faidx', str(ROOT / config['reference']), *regions]


def validate_native_receipt(receipt, argv, context, reader, finish=None, policy=None, gpu_start=False, latest=True):
    """Reconcile raw native producer evidence with the retained stage identity."""
    require(receipt['argv'] == argv and receipt['context'] == context, 'Native command/context mismatch')
    data = {'argv': argv, 'context': context}
    if policy is not None:
        data.update(measurement=policy, gpu_start=gpu_start)
        require(receipt.get('measurement_policy') == policy and receipt.get('gpu_start') is gpu_start, 'Native measurement policy/start mismatch')
    else:
        require('measurement_policy' not in receipt, 'Unexpected native measurement policy')
    require(receipt['key'] == identity(data), 'Native stage identity mismatch')
    require(receipt['explicit_env'] == {'LC_ALL': 'C'}, 'Native recorder locale/environment mismatch')
    reader.retain(receipt['pins'])
    starts = [Path(p['path']) for p in receipt['pins'] if Path(p['path']).name == 'start.json']
    require(len(starts) == 1, 'Unique native start receipt required')
    start = reader.read(starts[0])
    require(start['status'] == 'running' and all(receipt.get(k) == value for k, value in start.items() if k != 'status'), 'Native start/finish identity mismatch')
    if finish is not None:
        require(Path(finish) == starts[0].parent / 'finish.json', 'Native finish/start attempt mismatch')
    actual_finish = starts[0].parent / 'finish.json'
    require(reader.read(actual_finish) == receipt, 'Native producer finish receipt changed')
    starts_on_disk = sorted(starts[0].parent.parent.glob('*/start.json'))
    require(not latest or starts_on_disk and starts_on_disk[-1] == starts[0], 'Newer native attempt exists outside accepted producer')
    recorder = Path(receipt['recorder'])
    require(receipt['stdout'] == str(recorder / 'stdout'), 'Native stdout/recorder mismatch')
    for name in ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'):
        pin_for(receipt['pins'], recorder / name)
    encoded = subprocess.check_output(['bash', '-c', 'printf "%q " "$@"; printf "\\n"', '--', *argv], text=True, env={'LC_ALL': 'C'})
    require((recorder / 'command.sh').read_text() == encoded, 'Raw native command mismatch')
    require(Path((recorder / 'cwd.txt').read_text().strip()).resolve() == ROOT.resolve(), 'Raw native cwd mismatch')
    native_exit = int((recorder / 'exit-status.txt').read_text().strip())
    require(native_exit == receipt['exit'], 'Raw native exit status mismatch')
    time_exit = re.search(r'Exit status: ([0-9]+)', (recorder / 'time.txt').read_text())
    require(time_exit is not None and int(time_exit[1]) == native_exit, 'GNU time/raw native exit status mismatch')
    if receipt['status'] == 'finished':
        require(native_exit == 0 and not receipt.get('failure'), 'Successful native producer has failed raw exit')
    else:
        require(receipt['status'] == 'command_failed' and (native_exit != 0 or receipt.get('failure')), 'Native failure status mismatch')
    clocks = [datetime.fromisoformat(receipt[key]).timestamp() for key in ('utc', 'native_launch_utc', 'native_end_utc', 'end_utc')]
    require(all(a <= b_ for a, b_ in zip(clocks, clocks[1:])), 'Native UTC clocks out of order')
    raw_start = datetime.fromisoformat((recorder / 'start.txt').read_text().strip()).timestamp()
    raw_end = datetime.fromisoformat((recorder / 'end.txt').read_text().strip()).timestamp()
    require(math.floor(clocks[1]) <= raw_start <= raw_end <= clocks[2], 'Raw native UTC clocks outside producer boundary')
    require(receipt['monotonic_ns'] <= receipt['native_launch_monotonic_ns'] <= receipt['native_end_monotonic_ns'] <= receipt['monotonic_ns'] + receipt['elapsed_ns'], 'Native monotonic clocks out of order')


def validate_iupac(verification, output):
    """Check the retained tiny faidx response, without reading reference or SAM data."""
    exceptions = verification['md_reference_ambiguity_exceptions']
    require(verification['status'] == 'verified' and verification['all_other_primary_fields_equal'] is True
            and verification['exact_md_agreement'] is False, 'IUPAC calmd verification unavailable')
    require(verification['md_reference_ambiguity_bases'] == len(exceptions)
            and verification['md_reference_ambiguity_records'] == len({e['child'] for e in exceptions}), 'IUPAC exception census mismatch')
    expected = {}
    for e in exceptions:
        region = f"{e['contig']}:{e['reference_position_1based']}-{e['reference_position_1based']}"
        require(region not in expected or expected[region] == e['reference_base'], 'Conflicting IUPAC coordinate labels')
        expected[region] = e['reference_base']
    actual, region = {}, None
    for line in output.read_text().splitlines():
        if line.startswith('>'):
            region = line[1:]
            require(region not in actual, 'Duplicate native faidx region')
            actual[region] = ''
        else:
            require(region is not None, 'Native faidx sequence without region')
            actual[region] += line.strip().upper()
    require(actual == expected, 'Native faidx IUPAC coordinates/bases mismatch')


def validate_resources(receipt, resources):
    """Bind the displayed native clocks to the retained GNU time receipt."""
    text = (Path(receipt['recorder']) / 'time.txt').read_text()
    match = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([0-9:.]+)', text)
    require(match is not None, 'Native GNU time clock unavailable')
    elapsed = 0.
    for part in match[1].split(':'):
        elapsed = elapsed * 60 + float(part)
    close(resources['native_wall_seconds'], elapsed, 'Native resource wall clock')
    close(resources['recorder_elapsed_seconds'], receipt['elapsed_ns'] / 1e9, 'Observer resource clock')
    for key, field in [('user_cpu_seconds', 'User time (seconds)'), ('system_cpu_seconds', 'System time (seconds)'), ('host_max_rss_kib', 'Maximum resident set size (kbytes)')]:
        match = re.search(re.escape(field) + r': ([0-9.]+)', text)
        require(match is not None, 'Native GNU time resource unavailable: ' + key)
        close(resources[key], float(match[1]), 'Native ' + key)
    require(resources['measurement_qualified'] == receipt['measurement_qualified'], 'Native resource measurement qualification mismatch')
    if 'gpu' in resources:
        require(resources['gpu'] == b.process_resources(receipt)['gpu'], 'Native GPU resource projection mismatch')


def summary(values):
    require(values, 'Cannot summarize an empty series')
    sd = stdev(values) if len(values) > 1 else None
    return {'n': len(values), 'raw': values, 'median': median(values), 'min': min(values), 'max': max(values),
            'mean': mean(values), 'sample_sd': sd, 'cv_percent': sd / mean(values) * 100 if sd is not None and mean(values) else None}


def telemetry(stage, reader):
    """Small observer CSVs only; never read a BAM, signal, reference, or sequence ledger."""
    receipt = reader.read(stage['receipt'])
    paths = {Path(p['path']).name: Path(p['path']) for p in receipt.get('pins', [])}
    result = {'scope': 'device-wide observer interval; not isolated native process/kernel',
              'peaks': stage['resources']['gpu'], 'sample_means': {}, 'host': {}}
    if 'gpu.csv' in paths:
        with paths['gpu.csv'].open() as handle:
            rows = list(csv.DictReader(handle, skipinitialspace=True))
        result['gpu_sample_count'] = len(rows)
        for key in ('utilization.gpu [%]', 'memory.used [MiB]', 'power.draw [W]', 'temperature.gpu', 'clocks.current.sm [MHz]'):
            values = [float(m[0]) for row in rows if (m := re.match(r'^[0-9]+(?:\.[0-9]+)?', row.get(key, '').strip()))]
            result['sample_means'][key] = mean(values) if values else None
    if 'host.jsonl' in paths:
        rows = [json.loads(line) for line in paths['host.jsonl'].read_text().splitlines() if line.strip()]
        result['host']['sample_count'] = len(rows)
        loads = [float(row['loadavg'].split()[0]) for row in rows if row.get('loadavg')]
        result['host']['load_average_1m'] = summary(loads) if loads else None
        times = [row['monotonic_ns'] / 1e9 for row in rows]
        result['host']['max_sample_gap_seconds'] = max((b - a for a, b in zip(times, times[1:])), default=None)
        result['host']['ac_online_values'] = sorted({row['ac_online'] for row in rows})
        result['host']['platform_profiles'] = sorted({row['platform_profile'] for row in rows})
        result['host']['cpu_affinities'] = sorted({tuple(row['cpu_affinity']) for row in rows})
        result['host']['foreign_gpu_compute_pid_samples'] = sum(bool(row['foreign_gpu_compute_pids']) for row in rows)
        result['host']['control_error_samples'] = sum(bool(row['control_errors']) for row in rows)
    return result


def evidence_bundle(bundle, planned, units, attempts, reader):
    timing, stages, gpu = {}, {}, {}
    for tier in TIERS:
        group = [u for u in units.values() if u['scope'] == 'timing' and u['tier'] == tier]
        timing[tier] = {key: summary(values) for key, values in {
            'basecall_wall_seconds': [u['observation']['basecall_process_wall_seconds'] for u in group],
            'signal_msamples_per_second': [sum(planned[u['unit']]['parents'].values()) / u['observation']['basecall_process_wall_seconds'] / 1e6 for u in group],
            'called_bases_per_second': [u['observation']['basecall']['metrics']['called_bases'] / u['observation']['basecall_process_wall_seconds'] for u in group]}.items()}
        names = set().union(*(set(u['stages']) for u in group))
        stages[tier] = {name: {field: summary([u['stages'][name]['resources'][field] for u in group if name in u['stages']]) for field in ('native_wall_seconds', 'recorder_elapsed_seconds', 'host_max_rss_kib', 'user_cpu_seconds', 'system_cpu_seconds')} for name in sorted(names)}
        gpu[tier] = {u['unit']: telemetry(u['stages']['basecall'], reader) for u in group}
    attempts_history = [{k: a.get(k) for k in ('unit', 'stage', 'status', 'exit', 'failure', 'superseded', 'measurement_qualified', 'receipt')} for a in attempts]
    variations = {}
    if bundle['accuracy'].get('timing'):
        for tier in TIERS:
            for padding in DOMAINS:
                scores = [r['score'] for r in bundle['accuracy']['timing']['units'] if r['tier'] == tier and r['padding'] == padding]
                variations[f'{tier}-{padding}'] = {key: summary([s[key] for s in scores]) for key in ('aggregate_accuracy', 'alignment_columns', 'children', 'represented_parents', 'positive_denominator_parents')}
    history = analysis_history(bundle['truth']['amendment'], reader)
    return {'schema': 1, 'status': 'complete-controlled-baseline', 'plan': bundle['plan']['sha256'],
            'inputs': bundle['inputs']['identity'], 'endpoint': bundle['truth']['amendment']['endpoint'],
            'artifact_validation': 'all retained pins rehashed' if reader.verify_pins else 'identities, exact JSON joins, sizes and small-file pins checked; large pins retained, not rehashed',
            'timing': timing, 'native_stages': stages, 'basecall_observer_telemetry': gpu,
            'accuracy': bundle['accuracy'], 'truth': bundle['truth']['truth'], 'timing_accuracy_variability': variations,
            'native_attempts': attempts_history, 'other_native_processes': bundle['stock']['other_native_processes'],
            'native_process_attempt_counts': bundle['stock']['native_process_attempt_counts'],
            'observation_failures': {u['unit']: u['observation_failures'] for u in units.values()},
            'native_qualification_controls': bundle['qualification']['controls'],
            'versions': bundle['plan']['tool_versions'], 'models': bundle['plan']['model_trees'],
            'measurement_policy': bundle['plan']['config']['measurement_policy'],
            'analysis_history': history,
            'filesystem_warmup': bundle.get('warmup'),
            'measurement_notes': bundle.get('measurement_notes'),
            'artifact_pins': sorted(reader.pins.values(), key=lambda p: p['path'])}


def analysis_history(amendment, reader):
    result = {'current_revision': amendment['version'], 'scope': 'only current frozen analysis outputs accepted; previous attempts/revisions are not qualified by this export'}
    if amendment.get('strict_failure'):
        directory = ROOT / amendment['strict_failure']
        pins = [file_pin(directory / name) for name in ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stderr', 'stdout', 'time.txt')]
        reader.retain(pins)
        result['strict_star_attempt'] = {'status': 'command_failed', 'exit': int((directory / 'exit-status.txt').read_text()), 'recorder': str(directory), 'pins': pins}
        require(result['strict_star_attempt']['exit'] != 0, 'Declared strict failed attempt has successful exit')
    return result


def validate_measurement_notes(notes, plan, units):
    require(notes['schema'] == 1 and notes['plan'] == plan['sha256'], 'Measurement notes plan/schema mismatch')
    if plan['sha256'] == INCIDENT_PLAN:
        require(any(note.get('unit') == 'full-sealed_test-sup' and note.get('stage') == 'basecall'
                    and note.get('pid') == 672880 and note.get('status') == 'descriptive_with_owned_cpu_interference'
                    for note in notes['notes']), 'Known owned CPU incident annotation required')
    planned = {u['id']: u for u in plan['units']}
    seen = set()
    for note in notes['notes']:
        name, stage = note['unit'], note['stage']
        require(name in planned and stage in units[name]['stages'], 'Measurement note has foreign unit/stage')
        require(planned[name]['scope'] != 'timing', 'Primary timing repetition has owned CPU interference')
        require(note['kind'] == 'owned_cpu_interference' and note['status'] == 'descriptive_with_owned_cpu_interference', 'Unsupported measurement note kind/status')
        require(note['time_precision'] in ('approximate', 'exact') and isinstance(note['pid'], int) and note['pid'] > 0,
                'Measurement note precision/PID unavailable')
        require(note['reason'] and isinstance(note['command'], list) and note['command'] and isinstance(note['evidence_paths'], list), 'Measurement note provenance unavailable')
        start, end, stopped = (datetime.fromisoformat(note[key]) for key in ('start_utc', 'end_utc', 'worker_terminated_before_utc'))
        require(all(t.tzinfo is not None for t in (start, end, stopped)) and start <= end <= stopped, 'Measurement note UTC interval invalid')
        resources = units[name]['stages'][stage]['resources']
        native_start, native_end = (datetime.fromisoformat(resources[key]) for key in ('start_utc', 'end_utc'))
        require(start <= native_end and end >= native_start, 'Measurement note does not overlap affected observer interval')
        signature = (name, stage, note['pid'], note['start_utc'], note['end_utc'])
        require(signature not in seen, 'Duplicate measurement note')
        seen.add(signature)
        for unit in units.values():
            if unit['scope'] == 'timing':
                require(datetime.fromisoformat(unit['stages']['basecall']['resources']['start_utc']) > stopped, 'Primary timing starts before confirmed worker termination')


def timing_note(evidence, unit, stage='basecall'):
    return '; '.join(note['status'] for note in (evidence.get('measurement_notes') or {}).get('notes', []) if note['unit'] == unit and note['stage'] == stage) or 'controlled process observation'


def load_measurement_notes(path, stock, plan, units, reader):
    canonical = ROOT / INCIDENT_NOTES if plan['sha256'] == INCIDENT_PLAN else stock / 'measurement-notes.json'
    if plan['sha256'] == INCIDENT_PLAN:
        require(canonical.is_file(), 'Canonical known-incident annotation unavailable')
    if path is None and not canonical.exists():
        return None
    notes = reader.read(path or canonical)
    if canonical.exists():
        require(notes == reader.read(canonical), 'Measurement note override differs from retained canonical annotations')
    validate_measurement_notes(notes, plan, units)
    return notes


def fmt(value):
    if value is None:
        return 'UNAVAILABLE'
    if isinstance(value, float):
        return f'{value:.6g}'
    return str(value).replace('|', '\\|').replace('\n', ' ')


def spread(s):
    return f"{fmt(s['median'])} [{fmt(s['min'])}, {fmt(s['max'])}]"


def percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def render(bundle, evidence, planned, units, stock, accuracy, evidence_path):
    lines = ['# Controlled stock baseline', '']

    def paragraph(text):
        lines.extend([text, ''])

    def table(headers, rows):
        lines.extend(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'])
        lines.extend('| ' + ' | '.join(fmt(v) for v in row) + ' |' for row in rows)
        lines.append('')

    def detail(title):
        lines.extend([f'<details><summary>{title}</summary>', ''])

    def end_detail():
        lines.extend(['</details>', ''])

    paragraph('**Complete:** 19/19 stock units verified with the current native verifier; six full cohort/model outputs scored in both fixed truth domains. The accuracy wrapper qualifies native execution and exact ledgers. Scientific scope is the bounded endpoint described below.')
    paragraph(f"Plan `{evidence['plan']}`. Inputs `{evidence['inputs']}`. [Machine-readable evidence]({evidence_path.resolve()}) retains every Q bin, stratum, artifact SHA-256 and native receipt path. Local [stock report]({stock.resolve() / 'report.json'}), [plan]({stock.resolve() / 'plan.json'}), [native qualification]({stock.resolve() / 'qualification.json'}) and [truth qualification]({accuracy.resolve() / 'truth-qualified.json'}). Export validation: {evidence['artifact_validation']}.")
    paragraph('Endpoint: **' + evidence['endpoint'] + '**. Conditional on publisher donor labels and accepted primary autosomal mappings (MAPQ 30–254). Variants, known reference errors, non-ACGT truth and fixed unsupported-star confidence neighborhoods are excluded. Unknown reference errors and mapping errors remain possible. This is neither whole-read diploid accuracy nor variant calling; vendor training exclusion is unknown. HG005 is reported as a stock control and selects no candidate.')
    paragraph('Accuracy is M/(M+X+I+D), where X is substitution, I inserted bases and D deleted bases. Query exposure is M+X+I; reference exposure is M+X+D. Insertions need both flanks in one eligible interval; deletions count eligible reference positions. Split children combine by original parent. Aggregate and mean-parent rates differ. The 95% parent bootstrap intervals use 2,000 fixed-seed replicates and quantify within-pilot technical resampling only; genomic dependence, duplex relationships, flowcell and population variation, truth and donor uncertainty are not covered.')
    paragraph('## Repeated process timing')
    paragraph('Five fresh processes per tier use all 2,608 development parents and 641,769,607 electrical samples each. Filesystem inputs/models/reference/index were explicitly warmed outside timing. ACAD external power and balanced laptop profile were sampled continuously; the observed power ceiling is 100 W. Stock DVFS, fan control and clocks remain dynamic. Three one-second idle GPU observations at ≤40 C and ≤5% utilization gate each start outside the native clock. The repeated timing phase was scheduled without other CPU-heavy work; disclosed full-cohort incidents appear below. This is process throughput, including startup, loading, input/output and shutdown, with no isolated-kernel or model-winner claim.')
    rows = []
    for tier in TIERS:
        t = evidence['timing'][tier]
        clock = t['basecall_wall_seconds']
        rows.append((tier, ', '.join(fmt(x) for x in clock['raw']), spread(clock), clock['sample_sd'], clock['cv_percent'], spread(t['signal_msamples_per_second']), spread(t['called_bases_per_second'])))
    table(['Tier', 'Five native wall clocks s', 'Wall median [range] s', 'Sample SD s', 'CV %', 'Signal MSamples/s median [range]', 'Called bases/s median [range]'], rows)
    table(['Repetition', 'Native wall s', 'Signal MSamples/s', 'Called bases', 'Called bases/s', 'Input/represented parents'], [
        (u['unit'], (wall := u['observation']['basecall_process_wall_seconds']), sum(planned[u['unit']]['parents'].values()) / wall / 1e6,
         (base := u['observation']['basecall']['metrics'])['called_bases'], base['called_bases'] / wall,
         f"{len(planned[u['unit']]['parents'])}/{base['represented_parents']}") for u in units.values() if u['scope'] == 'timing'])
    detail('All 13 native stages: clock, CPU, RSS and observer scope')
    paragraph('Values are medians [minimum, maximum] over five repetitions. Native GNU time clocks have 0.01 s resolution; zero is below that resolution. Observer elapsed includes setup/telemetry overhead and is a separate boundary; host RSS is native maximum resident memory.')
    table(['Tier', 'Stage', 'n', 'Native wall s', 'Observer elapsed s', 'User CPU s', 'System CPU s', 'Max RSS KiB'], [(tier, name, metrics['native_wall_seconds']['n'], *(spread(metrics[k]) for k in ('native_wall_seconds', 'recorder_elapsed_seconds', 'user_cpu_seconds', 'system_cpu_seconds', 'host_max_rss_kib'))) for tier in TIERS for name, metrics in evidence['native_stages'][tier].items()])
    paragraph('The 13 core stages are always required. `calmd-reference-iupac` is an additional native samtools faidx stage only when the verifier records a coordinate-confirmed reference ambiguity; it remains subject to the same measurement and receipt requirements.')
    end_detail()
    detail('GPU and host observations, limiter evidence and batch choices')
    paragraph('GPU peaks and arithmetic sample means cover the device-wide observer interval, including setup and GPU cooldown before native launch. They are not instantaneous maxima or isolated process allocations. One-second sampling and a 2.5 s maximum gap cannot resolve subsecond events. Thermal/power counter deltas cover the retained before/after observer boundaries, including cooldown; they must not be divided by native wall time to estimate a native throttle fraction. Counter activity supports limiter observations but supplies no kernel-profiler evidence or causal bottleneck diagnosis. CPU load snapshots and full thermal/power samples remain in the evidence/receipts. Observer elapsed is closer to the wait-and-measure workflow; native wall is the separate process boundary.')
    table(['Unit', 'GPU peak MiB', 'Peak/mean W', 'Peak/mean utilization %', 'Peak/mean SM MHz', 'Peak C', 'Samples', 'Batch selection'], [(name, item['peaks'].get('peak_memory_mib'), f"{fmt(item['peaks'].get('peak_power_watts'))}/{fmt(item['sample_means'].get('power.draw [W]'))}", f"{fmt(item['peaks'].get('peak_utilization_percent'))}/{fmt(item['sample_means'].get('utilization.gpu [%]'))}", f"{fmt(item['peaks'].get('peak_sm_clock_mhz'))}/{fmt(item['sample_means'].get('clocks.current.sm [MHz]'))}", item['peaks'].get('peak_temperature_celsius'), item.get('gpu_sample_count'), units[name]['observation']['batch_selection_status']) for tier in TIERS for name, item in evidence['basecall_observer_telemetry'][tier].items()])
    counters = []
    for tier in TIERS:
        for name, item in evidence['basecall_observer_telemetry'][tier].items():
            for field, observation in item['peaks'].get('optional_telemetry', {}).items():
                if field.startswith('clocks_event_reasons_counters.'):
                    counters.append((name, field.rsplit('.', 1)[-1], observation.get('delta'), 'microseconds / observer boundary'))
    table(['Unit', 'Counter', 'Delta', 'Scope'], counters)
    table(['Unit', 'Observer loadavg 1m median [range]', 'Host samples', 'Maximum host sample gap s', 'External power samples', 'Platform profiles'], [
        (name, spread(host['load_average_1m']) if host['load_average_1m'] else None, host['sample_count'], host['max_sample_gap_seconds'],
         ', '.join(host['ac_online_values']), ', '.join(host['platform_profiles']))
        for tier in TIERS for name, item in evidence['basecall_observer_telemetry'][tier].items() if (host := item['host'])])
    paragraph('The known batchsize-0 precomputed-benchmark fallback is reported separately from native loader errors. Exact effective batch/chunk debug lines are retained in each stock observation. A known fallback diagnostic alone does not mean a loader failure.')
    table(['Unit', 'Complete work', 'Native loader error lines', 'Effective batch/chunk settings'], [(u['unit'], u['observation']['complete_work_qualification'], len(u['observation']['native_loader_error_lines']), '<br>'.join(line for line in u['observation'].get('effective_batch_chunk_log_lines', []) if 'using chunk size' in line)) for u in units.values() if u['scope'] in ('timing', 'full')])
    end_detail()
    paragraph('## Full cohort accuracy and exposure')
    paragraph('Full-cohort process clocks are additional single observations per cohort/model, separate from the five repeated development timing estimates.')
    table(['Full unit', 'Parents submitted', 'Signal samples', 'Native basecall wall s', 'Clock qualification', 'Called bases', 'Represented/absent parents', 'Complete work'], [
        (u['unit'], len(planned[u['unit']]['parents']), sum(planned[u['unit']]['parents'].values()),
         u['observation']['basecall_process_wall_seconds'], timing_note(evidence, u['unit']), (base := u['observation']['basecall'])['metrics']['called_bases'],
         f"{base['metrics']['represented_parents']}/{len(base['missing_parents'])}", u['observation']['complete_work_qualification'])
        for u in units.values() if u['scope'] == 'full'])
    if evidence.get('measurement_notes'):
        paragraph('Disclosed measurement incidents qualify the affected clock without discarding its observed output or subsequent source-bound accuracy scores. The uncertainty window overlaps the observer interval; this conservative qualification does not reconstruct instantaneous native contention. Required AC/profile/GPU telemetry qualification is separate from CPU isolation. Annotated full-cohort clocks are descriptive; the ten primary timing repetitions must start after confirmed worker termination and carry no such incident.')
        table(['Unit/stage', 'Status', 'PID', 'UTC window', 'Precision', 'Worker stopped before UTC', 'Reason'], [
            (note['unit'] + '/' + note['stage'], note['status'], note['pid'], note['start_utc'] + ' to ' + note['end_utc'],
             note['time_precision'], note['worker_terminated_before_utc'], note['reason']) for note in evidence['measurement_notes']['notes']])
    rows = []
    for row in bundle['accuracy']['full']['units']:
        s, c = row['score'], row['score']['counts']
        lo, hi = s['bootstrap']['aggregate_error_fraction_95_percentile']
        mean_lo, mean_hi = s['bootstrap']['parent_mean_error_fraction_95_percentile']
        rows.append((row['unit'], row['padding'], c['m'], c['x'], c['i'], c['d'], s['alignment_columns'], s['eligible_query_columns'], s['eligible_reference_columns'], 100 * s['aggregate_accuracy'], f'{100*(1-hi):.6f}–{100*(1-lo):.6f}', 100 * s['parent_mean_accuracy'], f'{100*(1-mean_hi):.6f}–{100*(1-mean_lo):.6f}'))
    table(['Unit', 'Domain bp', 'M', 'X', 'I', 'D', 'C', 'Query denom', 'Reference denom', 'Accuracy %', '95% technical CI %', 'Mean-parent accuracy %', 'Mean-parent 95% technical CI %'], rows)
    paragraph('100 bp is the fixed primary domain; 500 bp is the predeclared sensitivity domain. Both are reported regardless of which looks better. All-called fractions below divide retained eligible query labels by every emitted primary child base, so mapping, clipping and mask losses stay visible. Input absence is a parent count, not an inferred biological error.')
    table(['Unit', 'Domain bp', 'Input/represented/positive parents', 'Children', 'Called bases', 'Scored query/all-called %', 'Absent parents', 'Unmapped bases', 'Soft clips', 'Policy-excluded bases', 'Masked query bases', 'Child statuses'], [(r['unit'], r['padding'], f"{(s:=r['score'])['expected_parents']}/{s['represented_parents']}/{s['positive_denominator_parents']}", s['children'], (loss:=s['losses'])['query_bases'], 100*s['eligible_query_columns']/loss['query_bases'], s['absent_parents'], loss['unmapped_query_bases'], loss['soft_clipped'], loss['policy_excluded_query_bases'], loss['excluded_query_bases'], json.dumps(s['statuses'], sort_keys=True)) for r in bundle['accuracy']['full']['units']])
    detail('Truth census and fixed star removals')
    table(['Domain', 'Original confident bases', 'Star records', 'Removed original intervals', 'Removed union bases', 'After erosion', 'Eligible bases', 'Eligible intervals'], [(key, (d:=domain['diagnostics'])['confidence']['union_bases'], d['spanning_star_records'], len(d['spanning_removed_intervals']), d['spanning_removed_union_bases'], d['eroded_bases'], d['eligible_bases'], d['eligible_intervals']) for key, domain in bundle['truth']['truth'].items()])
    table(['Domain', 'Ordered subtraction census'], [(key, json.dumps(domain['diagnostics']['ordered_domain_bases'], sort_keys=True)) for key, domain in bundle['truth']['truth'].items()])
    paragraph('For every spanning * REF span, the frozen v1.1 rule removes intersected original merged confident intervals and the closest strictly left/right original neighbors; selection happens once before erosion, never recursively. Star REF padding and all concrete/original/repeat-equivalent masks remain. Exact removed interval coordinates and native qualification receipts are in the evidence. This does not reconstruct the missing upstream deletion extent.')
    end_detail()
    detail('Quality reliability, length/native-Q strata and homopolymers')
    paragraph('Emitted-Q reliability uses (X+I)/(M+X+I), with expected error 10^(−Q/10). D has no emitted Q and is reported separately. These labels are alignment/domain conditional and do not establish whole-read calibration. Full integer-Q histograms are in the evidence JSON; strata below preserve all M/X/I/D counts.')
    table(['Unit', 'Domain bp', 'Query labels', 'Observed X+I', 'Observed error %', 'Expected error %', 'D without emitted Q', 'Emitted Q bins'], [
        (row['unit'], row['padding'], (score := row['score'])['eligible_query_columns'], score['counts']['x'] + score['counts']['i'],
         percent(score['counts']['x'] + score['counts']['i'], score['eligible_query_columns']),
         percent(sum(b['expected_error_sum'] for b in score['qscore'].values()), score['eligible_query_columns']),
         score['counts']['d'], len(score['qscore'])) for row in bundle['accuracy']['full']['units']])
    for key, title in [('length_strata', 'Called length'), ('native_qscore_strata', 'Native qs'), ('homopolymer_context', 'Reference homopolymer context')]:
        table(['Unit', 'Domain bp', title, 'M', 'X', 'I', 'D', 'Accuracy %'], [(r['unit'], r['padding'], bin_name, c['m'], c['x'], c['i'], c['d'], 100*c['m']/sum(c.values()) if sum(c.values()) else None) for r in bundle['accuracy']['full']['units'] for bin_name, c in r['score'][key].items()])
    paragraph('The subordinate homopolymer length endpoint requires a maximal reference run of length 2–1000, two exact aligned bases on each flank, and the entire flanked span in one eligible interval. A non-run interior base is complex. It covers only these qualifying aligned runs, with no genome-wide repeat-reconstruction claim.')
    table(['Unit', 'Domain bp', 'Run length', 'Correct', 'Under', 'Over', 'Complex'], [(r['unit'], r['padding'], name, c['correct'], c['under'], c['over'], c['complex']) for r in bundle['accuracy']['full']['units'] for name, c in r['score']['homopolymer_length_counts'].items()])
    end_detail()
    if evidence['timing_accuracy_variability']:
        detail('Development accuracy variability across the five timing outputs')
        table(['Tier-domain', 'Metric', 'n', 'Median [range]'], [(key, metric, stats['n'], spread(stats)) for key, metrics in evidence['timing_accuracy_variability'].items() for metric, stats in metrics.items()])
        paragraph('These are repeated observations of the same development input, not independent biological replicates or a population confidence interval.')
        end_detail()
    else:
        paragraph('Timing-output accuracy variability is unavailable: no complete 20-pair timing accuracy report was supplied.')
    detail('All retained attempts, failures and reproducibility pins')
    table(['Process status', 'Count'], sorted(evidence['native_process_attempt_counts'].items()))
    failures = [a for a in evidence['native_attempts'] if a['status'] != 'finished' or a['exit'] != 0 or a.get('failure')]
    table(['Unit', 'Stage', 'Status', 'Exit', 'Failure', 'Retained receipt'], [(a['unit'], a['stage'], a['status'], a['exit'], a['failure'], f"[receipt]({a['receipt']})") for a in failures])
    paragraph('All native attempts, superseded attempts, verifier failures, preparation processes and qualification controls remain in the evidence JSON. Expected negative-control native exits are separate from measured process failures. Completion requires the latest native attempts to pass; retained earlier failures remain visible.')
    history = evidence['analysis_history']
    if history.get('strict_star_attempt'):
        failed = history['strict_star_attempt']
        paragraph(f"The original strict ALT-* truth attempt failed with exit {failed['exit']}; [retained receipt]({failed['recorder']}). The frozen v1.1 confidence-neighborhood amendment and current source snapshot supersede earlier analysis revisions. Earlier failed or superseded accuracy attempts are not qualified by this report.")
    table(['Tool', 'Version'], [(name, version.splitlines()[0]) for name, version in evidence['versions'].items()])
    table(['Tier', 'Model tree', 'Files'], [(tier, tree['path'], len(tree['files'])) for tier, tree in evidence['models'].items()])
    paragraph('Reproduce export with `uv run python scripts/summarize-controlled.py --stock ' + str(stock) + ' --accuracy ' + str(accuracy) + ' --inputs ' + str(bundle['_inputs_path']) + ' --output REPORT.md --evidence EVIDENCE.json --verify-pins`. Full pin verification reads large artifacts and must run outside GPU measurement. Raw signals, references, model trees, BAMs, ledgers and native logs stay outside Git.')
    end_detail()
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stock', 'accuracy', 'inputs', 'output', 'evidence'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--verify-pins', action='store_true', help='Rehash every retained artifact; run only outside measurements')
    parser.add_argument('--measurement-notes', type=Path, help='Plan-bound measurement annotations; the known controlled plan always requires its canonical retained incident manifest')
    args = parser.parse_args()
    reader = Reader(args.verify_pins)
    try:
        bundle = load_bundle(args.stock.resolve(), args.accuracy.resolve(), args.inputs.resolve(), reader)
        verifier = file_pin(ROOT / 'scripts/benchmark.py')['sha256']
        current = [file_pin(p['path']) for p in bundle['truth']['sources']]
        amendment = reader.read(ROOT / 'config/accuracy-v1.1.json')
        planned, units, attempts = validate_bundle(bundle, verifier, current, amendment)
        bundle['measurement_notes'] = load_measurement_notes(args.measurement_notes, args.stock, bundle['plan'], units, reader)
        evidence = evidence_bundle(bundle, planned, units, attempts, reader)
        bundle['_inputs_path'] = args.inputs
        markdown = render(bundle, evidence, planned, units, args.stock, args.accuracy, args.evidence)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        parser.exit(1, f'Controlled report refused: {exc}\n')
    for path in (args.output, args.evidence):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    args.output.write_text(markdown)
    print(f'{args.output}: COMPLETE; 19 stock units, 12 full accuracy pairs; evidence {args.evidence}')


if __name__ == '__main__':
    main()
