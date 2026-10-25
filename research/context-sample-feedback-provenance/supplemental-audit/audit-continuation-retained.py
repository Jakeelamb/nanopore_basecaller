"""Audit typed continuation metadata without repeating scientific body checks."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'
HERE = READY/'decision-population-reuse'
spec = importlib.util.spec_from_file_location('continuation_bounded_metadata', READY/'audit-map-retained.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def audit(phase, session):
    ready = h.read(HERE/'ready-v2.json')
    h.require(h.pin(HERE/'ready-v2.json')['sha256'] == '38cfdd7bd8921ed9daaefd4b034229eb9229095acff8fe73fb3cca431a94b72e', 'Ready changed')
    unit = next(row for row in ready['units'] if row['phase'] == phase)
    output = Path(unit['output'])
    outer = h.read(output/'execution-complete.json')
    h.require(outer['schema'] == 'context-sample-feedback-continuation-execution/1' and outer['complete'] and outer['phase'] == phase and outer['whole_worker_cgroup_terminal'], 'Typed outer differs')
    for pin in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]:
        h.checked(pin)
    terminal = h.read(outer['terminal']['path'])
    h.require(terminal['exit'] == 0 and terminal['error'] is None and terminal['owned_cgroup_terminal'] and terminal['canonical_lock_retained'], 'Typed worker failed')
    properties = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    h.require(properties['MainPID'] == properties['ControlPID'] == '0' and properties['ControlGroup'] == '' and properties['ActiveState'] == 'inactive' and properties['Result'] == 'success', 'Worker still live')
    raw = {Path(pin['path']).name:pin for pin in outer['files']}
    h.require(h.read(raw['launcher-cleanup.json']['path'])['terminal'], 'Launcher still live')
    command = h.read(raw['command.json']['path'])
    h.require(shlex.split(h.data(raw['command.sh']['path']).decode()) == command['argv'] and h.data(raw['exit-status.txt']['path']).strip() == b'0' and h.data(raw['cwd.txt']['path']).decode().strip() == str(ROOT), 'Outer raw argv/cwd/status differs')
    grant = command['grant']
    plan = h.read(HERE/'plan.json')
    expected_inputs = plan['reuse_inputs'] if phase == 'reuse-population' else [h.pin(Path(plan['report_input_paths'][0])/'execution-complete.json'), *plan['report_existing_inputs']]
    h.require(grant['schema'] == 'context-sample-feedback-continuation-admission/1' and grant['phase'] == phase and grant['scope'] == 'all' and grant['arm'] is grant['case_id'] is grant['source_audit'] is grant['recovery'] is None, 'Grant phase differs')
    h.require(grant['sources_sha256'] == ready['sources_sha256'] and grant['compiled_sources_sha256'] == ready['compiled_source_identity'] and grant['config'] == ready['config'] and grant['qualification'] == ready['qualification'] and grant['inputs'] == expected_inputs and grant['output'] == str(output), 'Exact source/input grant differs')
    h.require(all(grant[key] == value for key,value in unit['caps'].items()), 'Caps differ')
    intake = h.read(outer['worker_intake']['path'])
    h.checked(intake['admission'])
    h.require(intake['verified'] and intake['parent_lock_retained'] and h.read(intake['admission']['path']) == grant, 'Intake differs')
    worker = h.read(outer['worker']['path'])
    h.require(worker['schema'] == 'context-sample-feedback-continuation-unit/1' and worker['complete'] and worker['phase'] == phase and worker['scope'] == 'all' and worker['sources_sha256'] == ready['sources_sha256'] and worker['compiled_sources_sha256'] == ready['compiled_source_identity'] and worker['inputs'] == expected_inputs and worker['qualification'] == ready['qualification'], 'Worker source/inputs differ')
    for pin in worker['files']:
        h.checked(pin)
    start = h.read(output/'start.json')
    h.require(start['orchestration_sources'] == ready['sources'], 'Own source census differs')
    for pin in start['orchestration_sources']+start['compiled_sources']:
        h.checked(pin)
    def identity(pins):
        return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    h.require(len(start['compiled_sources']) == 89 and identity(start['compiled_sources']) == ready['compiled_source_identity'], 'Original compiled89 changed')
    summary = h.read(output/'summary.json')
    h.require(summary['schema'] == 'context-sample-feedback-continuation-summary/1' and summary['phase'] == phase and summary['scope'] == 'all' and summary['orchestration_sources_sha256'] == ready['sources_sha256'] and summary['compiled_sources_sha256'] == ready['compiled_source_identity'] and summary['native_producers_launched'] == 0, 'Typed summary differs')
    stages = []
    for pin in summary['stages']:
        h.checked(pin)
        stage = h.read(pin['path'])
        h.require(stage['exit'] == 0 and stage['failure'] is stage['projection_error'] is None and not stage['missing_raw'], 'Metadata stage failed')
        h.require(set(stage['raw']) == {'command.sh','cwd.txt','start.txt','end.txt','exit-status.txt','stdout','stderr','time.txt'}, 'Stage raw eight missing')
        for value in [*stage['raw'].values(),stage['terminal'],stage['group_cleanup']]:
            h.checked(value)
        h.require(shlex.split(h.data(stage['raw']['command.sh']['path']).decode()) == stage['argv'] and h.data(stage['raw']['exit-status.txt']['path']).strip() == b'0' and h.data(stage['raw']['cwd.txt']['path']).decode().strip() == str(ROOT) and h.read(stage['group_cleanup']['path'])['terminal'], 'Stage argv/status/tree differs')
        stages.append(stage)
    details = {}
    if phase == 'reuse-population':
        h.require(len(stages) == 2 and stages[0]['argv'] == ['uv','run','--no-sync','python',str(HERE/'test_core.py')] and stages[1]['argv'] == plan['partial_trace']['argv'], 'Two fixed metadata stages required')
        stderr = h.data(stages[0]['raw']['stderr']['path']).decode()
        h.require(re.search(r'Ran 28 tests',stderr) is not None and stderr.rstrip().endswith('OK') and 'skipped' not in stderr, 'Actual28controls/skip0 absent')
        reused = summary['reuse']
        h.require(reused['new_scientific_producers'] == 0 and reused['decision_producer'] == plan['old_measurement'] and reused['decision_measurement_source'] == ready['decision_measurement_source'] and reused['decision_emission_compiled_source'] == ready['decision_emission_compiled_source'] and reused['sample_compiled_source'] == ready['compiled_source_identity'], 'Reuse source roles differ')
        for key in ('mapping','measurement','partial_trace'):
            h.checked(reused[key])
        mapping = h.read(reused['mapping']['path'])
        measurement = h.read(reused['measurement']['path'])
        partial = h.read(reused['partial_trace']['path'])
        h.require(mapping['schema'] == 'sample-decision-exact-mapping-view/1' and mapping['mapped']['sha256'] == '834d2d90db137ab9f11dd158154f6681f0a00c7f1153ffdd1268c051cf5dfd0a' and mapping['emitted']['sha256'] == 'e451d61479f5bf25205265c0a11d7ef0d8e3c3f3c7f54ffa5b5eb84604fa9ece' and mapping['native_mapper_launched'] is False, 'Typed mapping lineage differs')
        h.require(measurement['schema'] == 'sample-decision-exact-measurement-view/1' and measurement['parents'] == 64 and measurement['arm'] == 'population' and measurement['native_pairer_or_observer_launched'] is False and measurement['candidate_promoted'] is False and all(value is False for value in measurement['qualification_flags'].values()), 'Typed measurement lineage differs')
        h.require(partial['schema'] == 'query0-retained-prefix-comparison/1' and partial['complete'] and partial['nonterminal_steps_compared'] == 102 and partial['terminal_step_excluded'] and partial['producer_rerun'] is partial['truth_read'] is partial['global_optimum_claim'] is False, 'Prefix comparison scope differs')
        details = dict(mapping=reused['mapping'], measurement=reused['measurement'], partial_trace=reused['partial_trace'], prefix_comparisons={name:{key:value for key,value in row.items() if key != 'steps'} for name,row in partial['comparisons'].items()}, measurement_view=measurement)
    else:
        h.require(not stages, 'Final report must not launch tools')
        h.checked(summary['report'])
        report = h.read(summary['report']['path'])
        h.require(report['schema'] == 'context-sample-feedback-typed-continuation-report/1' and len(report['measurements']) == len(report['checks']) == 8 and report['candidate_promoted'] is False and report['source_independence_unproved'] is True, 'Report scope/flags differ')
        details = dict(report=summary['report'], checks=report['checks'], measurement_lineage=report['measurement_lineage'])
    started = h.data(raw['start.txt']['path']).decode().strip()
    ended = h.data(raw['end.txt']['path']).decode().strip()
    h.require(datetime.fromisoformat(grant['not_before_utc']) <= datetime.fromisoformat(started) <= datetime.fromisoformat(ended) <= datetime.fromisoformat(grant['expires_utc']), 'Whole-unit clocks exceed grant')
    memory = re.search(r'Memory peak: ([^\n]+)', h.data(raw['stderr']['path']).decode())
    return dict(schema='context-sample-feedback-typed-retained-audit/1', complete=True, phase=phase, actual_exec_session_id=session, actual_exec_parent_returned=True, actual_exec_parent_exit=0, completion=h.pin(output/'execution-complete.json'), terminal=outer['terminal'], launcher=raw['launcher-cleanup.json'], grant=intake['admission'], source_identity=ready['sources_sha256'], compiled_source_identity=ready['compiled_source_identity'], config=ready['config'], qualification=ready['qualification'], exact_inputs=expected_inputs, stages=summary['stages'], details=details, start_utc=started, end_utc=ended, whole_unit_wall_seconds=(datetime.fromisoformat(ended)-datetime.fromisoformat(started)).total_seconds(), service_memory_peak_raw=None if memory is None else memory[1], metadata_bytes=h.TOTAL, metadata_limit=64*1024**2, owned_result_bytes=sum(path.stat().st_size for path in (ROOT/'results/context-sample-feedback').rglob('*') if path.is_file()), no_scientific_or_runtime_body_replay=True, source_independence=False, promotion=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('reuse-population','report'), required=True)
    parser.add_argument('--session', type=int, required=True)
    args = parser.parse_args()
    result = audit(args.phase,args.session)
    path = READY/(args.phase+'-1-audit.json')
    h.fresh(path,result)
    print(json.dumps(dict(audit=h.pin(path),result=result)))
