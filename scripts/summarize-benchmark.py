#!/usr/bin/env python3
"""Render retained stock benchmark observations; never execute native tools."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from statistics import median


def value(item):
    if item is None:
        return 'UNAVAILABLE'
    if isinstance(item, float):
        return f'{item:.6g}'
    return str(item).replace('|', '\\|').replace('\n', ' ')


def spread(items):
    def clock(seconds):
        return '<0.01' if seconds == 0 else f'{seconds:.2f}'
    return (f'{clock(median(items))} [{clock(min(items))}, {clock(max(items))}]'
            if items else 'UNAVAILABLE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results_dir', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--power-observation', type=Path)
    args = parser.parse_args()
    root = args.results_dir.resolve()
    project = Path(__file__).resolve().parents[1]
    raw = (root / 'report.json').read_bytes()
    report = json.loads(raw)
    plan = json.loads((root / 'plan.json').read_text())
    qualification_path = root / 'qualification.json'
    qualification = json.loads(qualification_path.read_text()) if qualification_path.exists() else {}
    units = report['units']
    planned = {u['id']: u for u in plan['units']}
    if (report['plan'] != plan['sha256'] or qualification.get('plan') != plan['sha256']
            or len(units) != len(planned) or {u['unit'] for u in units} != set(planned)):
        raise ValueError('Report, qualification and planned unit identities must match')
    power = json.loads(args.power_observation.read_text()) if args.power_observation else None
    if power and (power['plan_identity'] != plan['sha256'] or power['initial_power_snapshot'] != plan['environment']['power']):
        raise ValueError('Power observation must match the frozen plan')
    lines = ['# Stock baseline results', '']

    def paragraph(text):
        lines.extend([text, ''])

    def table(headers, rows):
        lines.append('| ' + ' | '.join(headers) + ' |')
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        lines.extend('| ' + ' | '.join(value(v) for v in row) + ' |' for row in rows)
        lines.append('')

    def link(path, label):
        target = Path(path).resolve()
        if target.is_relative_to(project / 'provenance'):
            return f'[{label}]({os.path.relpath(target, args.output.resolve().parent)})'
        return f'`{os.path.relpath(target, project)}`'

    complete = (all(u['status'] == 'verified' and u.get('observation', {}).get('verifier_sha256') == qualification.get('verifier_sha256') for u in units)
                and qualification.get('status') == 'verified')
    paragraph(f"Snapshot: **{'COMPLETE' if complete else 'INCOMPLETE'}**. Completion counts verified planned observations. Per-unit complete-work status and represented input parents are reported separately. This exporter displays retained verifier results; it does not revalidate artifacts or qualify scientific endpoints.")
    paragraph(f"Local artifact sources: {link(root / 'plan.json', 'plan')}, {link(root / 'report.json', 'report')}, {link(qualification_path, 'qualification')}. Raw artifacts and receipts are excluded from Git. Report bytes SHA-256: `{hashlib.sha256(raw).hexdigest()}`. Plan identity: `{report['plan']}`.")
    verifiers = sorted({u['observation']['verifier_sha256'] for u in units if u.get('observation')})
    paragraph(f"Qualification status: **{qualification.get('status', 'UNAVAILABLE')}**; qualification verifier SHA-256 `{qualification.get('verifier_sha256', 'UNAVAILABLE')}`. Observation verifier SHA-256: {', '.join('`' + v + '`' for v in verifiers) or 'UNAVAILABLE'}.")
    paragraph(f"Native Dorado version: `{plan['tool_versions']['dorado'].strip()}`. Models: " + '; '.join(f"{tier}: `{Path(path).name}`" for tier, path in plan['config']['models'].items()) + '.')
    full_inputs = {u['asset']['flowcell']: u for u in plan['units'] if u['scope'] == 'full'}
    paragraph(f"Input cohort: {len(full_inputs):,} flowcells; {sum(len(u['parents']) for u in full_inputs.values()):,} parents; {sum(sum(u['parents'].values()) for u in full_inputs.values()):,} signal samples. Each tier receives this same cohort.")
    table(['Scope', 'Planned', 'Verified', 'Statuses'], [
        (scope, sum(p['scope'] == scope for p in planned.values()), sum(u['status'] == 'verified' for u in units if u['scope'] == scope), dict(Counter(u['status'] for u in units if u['scope'] == scope)))
        for scope in ['timing', 'full', 'smoke', 'fixture']])
    paragraph('This size-selected pilot has two individuals and three flowcells. Reads within each flowcell are technical observations; this cohort does not support population-level conclusions. Vendor training contamination is unknown. HG005 stock processing is authorized; candidate selection must remain on development and validation. Shared workstation; earlier runs warmed caches and cache state is uncontrolled. GPU sampling observes utilization, but the limiting code path has not been profiled. Biological accuracy, intrinsic throughput, model winners, and speedups remain unqualified.')
    if power:
        changed = power['initial_power_snapshot'] != power['final_power_snapshot']
        paragraph('Host power snapshots ' + ('changed' if changed else 'agree') + ' between setup and completion; see ' + link(args.power_observation, 'the retained snapshots') + '. The exact transition time and per-attempt power source were not recorded. These clocks are descriptive observations under uncontrolled power conditions. Establish a fresh matched control on fixed external power before testing a candidate speedup.')
    else:
        paragraph('The plan retains an initial host power snapshot. Per-attempt power source was not recorded, so fixed power conditions are unqualified.')
    table(['Tier', 'Verified repetitions', 'Basecall wall s median [range]', 'Failed basecall attempts', 'Complete work'], [
        (tier, f"{item['successful']}/{item['planned']}", spread([row['observation']['basecall_process_wall_seconds'] for row in units if row['scope'] == 'timing' and row['tier'] == tier and row['status'] == 'verified']), item['failed_basecall'], item['complete_work_baseline'])
        for tier, item in report['timing'].items()])
    paragraph('Timing uses five fresh processes per tier on the frozen development subset. Median [minimum, maximum] below includes verified observations with retained successful native-stage resources. Missing observations are UNAVAILABLE. GNU time reports wall seconds to 0.01 seconds; <0.01 marks a value below that reporting resolution. Basecall process wall includes startup, loading, input/output and shutdown. Each stage has a separate native process clock.')
    stages = sorted({s for u in units if u['scope'] == 'timing' for s in u.get('stages', {})} | {'basecall', 'align'})
    stage_rows = []
    for tier in plan['config']['models']:
        group = [u for u in units if u['scope'] == 'timing' and u['tier'] == tier]
        for name in stages:
            samples, attempts = [], []
            for unit in group:
                stage = unit.get('stages', {}).get(name, {})
                attempts.extend(stage.get('attempts', []))
                wall = stage.get('resources', {}).get('native_wall_seconds')
                if unit['status'] == 'verified' and stage.get('exit') == 0 and wall is not None:
                    samples.append(wall)
            stage_rows.append((tier, name, f'{len(samples)}/{len(group)}', spread(samples), len(group)-len(samples), len(attempts), sum(a.get('exit') not in (None, 0) for a in attempts), sum(max(0, len(u.get('stages', {}).get(name, {}).get('attempts', []))-1) for u in group)))
    table(['Tier', 'Native stage', 'Verified n/planned', 'Wall seconds median [range]', 'Unavailable', 'Attempts', 'Nonzero exits', 'Retries'], stage_rows)
    paragraph('Full-cohort clocks below are single runs, not five-repetition performance estimates. Reference disagreement is conditional on mapped primary children: disagreement alignment columns / alignment columns. It includes genotype, mapping and reference differences. Clipping and unmapped output are reported separately; absent-parent causes and split-sibling completeness remain unresolved.')
    rows = []
    for unit in units:
        if unit['scope'] != 'full':
            continue
        obs = unit.get('observation') or {}
        base = obs.get('basecall', {}).get('metrics', {})
        mapping = obs.get('mapping', {}).get('metrics', {})
        absent = len(obs['basecall']['missing_parents']) if 'basecall' in obs else None
        rows.append((unit['unit'], unit['status'], obs.get('basecall_process_wall_seconds'), len(planned[unit['unit']]['parents']), base.get('represented_parents'), absent, base.get('children'), mapping.get('mapped_children'), mapping.get('secondary'), mapping.get('supplementary'), obs.get('mapping', {}).get('reference_disagreement_proxy', {}).get('aggregate'), mapping.get('disagreement_columns'), mapping.get('alignment_columns'), mapping.get('cigar_S'), mapping.get('unmapped_children'), mapping.get('unmapped_called_bases')))
    table(['Unit', 'Status', 'Basecall wall s', 'Input parents', 'Represented parents', 'Absent parents', 'Children', 'Mapped children', 'Secondary', 'Supplementary', 'Disagreement fraction', 'Disagreement columns', 'Alignment columns', 'Soft-clipped bases', 'Unmapped children', 'Unmapped bases'], rows)
    paragraph('A verified observation can include absent parents. The complete-work field remains unavailable for such units, and the per-unit parents.tsv retains every input UUID with its emitted or not_emitted status. Native filtered-output counts can also include a split sibling whose parent is still represented; they need not equal absent-parent counts.')
    paragraph('The calmd check requires identical primary fields, NM and other tags. An MD exception is accepted only when the stock N corresponds to a coordinate-confirmed IUPAC reference symbol. Exact MD agreement remains false for those units. The original rejection and its source investigation remain in [the discrepancy report](calmd-discrepancy.md).')
    table(['Unit', 'Primary records checked', 'Exact MD agreement', 'Reference ambiguity records', 'Reference ambiguity bases', 'Reference check stage'], [
        (u['unit'], (c := (u.get('observation') or {}).get('calmd_verification', {})).get('primary_records_checked'), c.get('exact_md_agreement'), c.get('md_reference_ambiguity_records'), c.get('md_reference_ambiguity_bases'), c.get('reference_check_stage') or 'not required')
        for u in units if u['scope'] == 'full'])
    paragraph('GPU values are device-wide peaks among 1 Hz samples, not true instantaneous peaks or isolated process allocations; RSS is native process maximum resident memory. Missing fields remain UNAVAILABLE. Stock `--batchsize 0` can select a heuristic fallback when precomputed timings are unavailable; the exact batch_selection_status is retained below, without assuming every tier took the same selection path.')
    table(['Unit', 'Status', 'Complete work', 'Batch selection status', 'GPU MiB', 'GPU W', 'GPU utilization %', 'SM MHz', 'Temperature C', 'RSS KiB'], [
        (u['unit'], u['status'], (o := u.get('observation') or {}).get('complete_work_qualification'), o.get('batch_selection_status'), *(o.get('gpu_resources', {}).get(k) for k in ['peak_memory_mib', 'peak_power_watts', 'peak_utilization_percent', 'peak_sm_clock_mhz', 'peak_temperature_celsius']), o.get('host_max_rss_kib')) for u in units])
    paragraph('Qualification control outcomes are copied verbatim; removed-parent absence accounting is not relabeled as rejection. The genuine smoke and split fixture units above establish retained producer checks, not biological accuracy. Full-reference parity evidence is retained in ' + link(project / 'provenance/index-qualified.json', 'index qualification') + ' and ' + link(project / 'provenance/reference-qualified.json', 'reference qualification') + '.')
    table(['Unit', 'Control', 'Outcome'], [(c['unit'], c['control'], c['status']) for c in qualification.get('controls', [])])
    other = report.get('other_native_processes', [])
    table(['Process category', 'Attempts', 'Nonzero exits', 'Exit unavailable'], [(kind, len(group := [x for x in other if x.get('kind') == kind]), sum(x.get('exit') not in (None, 0) for x in group), sum(x.get('exit') is None for x in group)) for kind in sorted({x.get('kind', 'UNAVAILABLE') for x in other})])
    paragraph('Nonzero qualification_control exits are expected native negative-control processes, separate from measured unit attempts. Inspect control outcomes above before interpreting them. Preparation processes below are individual single-run clocks, including failed attempts; they are not five-repetition estimates.')
    table(['Preparation receipt', 'Exit', 'Wall s', 'RSS KiB'], [(link(x.get('receipt') or x['recorder'], Path(x.get('receipt') or x['recorder']).parent.name if x.get('receipt') else Path(x['recorder']).name), x.get('exit'), x.get('resources', {}).get('native_wall_seconds'), x.get('resources', {}).get('host_max_rss_kib')) for x in other if x.get('kind') == 'preparation'])
    paragraph('Unit attempt receipts retain retries, failures and resource records. Large native artifacts remain outside Git.')
    table(['Unit', 'Native attempts', 'Nonzero exits', 'Retries', 'Receipt directory'], [(u['unit'], len(attempts := [a for s in u.get('stages', {}).values() for a in s.get('attempts', [])]), sum(a.get('exit') not in (None, 0) for a in attempts), sum(max(0, len(s.get('attempts', []))-1) for s in u.get('stages', {}).values()), link(root / 'units' / u['unit'], u['unit'])) for u in units])
    paragraph('Observation failures below are verifier failures, separate from native process exits. A later successful observation does not remove the earlier failure.')
    table(['Unit', 'UTC', 'Verifier SHA-256', 'Error', 'Failure receipt'], [
        (u['unit'], f.get('utc'), f.get('verifier_sha256'), f.get('error'), link(f['path'], 'failure'))
        for u in units for f in u.get('observation_failures', [])])
    table(['Scientific endpoint', 'Status'], list(report['scientific_endpoints'].items()))
    paragraph('Additional retained limits: ' + ' '.join(report.get('limits', [])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines))
    print(f'{args.output}: {"COMPLETE" if complete else "INCOMPLETE"}; {sum(u["status"] == "verified" for u in units)}/{len(planned)} verified units')


if __name__ == '__main__':
    main()
