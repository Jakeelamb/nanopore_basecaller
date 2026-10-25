"""Check normal63 paired measurements from bounded metadata, never replay tools."""
import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re
import shlex
import json

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'
spec = importlib.util.spec_from_file_location('retained_map_metadata_io', READY/'audit-map-retained.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
spec = importlib.util.spec_from_file_location('unchanged_measurement_arithmetic', Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v5/tools/context_decoder/model_measure.py'))
math = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)


def audit(arm, session):
    output = ROOT/('results/context-sample-feedback/sample-measure-all-'+arm+'-1')
    outer = h.read(output/'execution-complete.json')
    h.require(outer['complete'] and outer['phase'] == 'measure' and outer['whole_worker_cgroup_terminal'], 'Outer measure incomplete')
    for value in [outer['worker'], outer['worker_intake'], outer['terminal'], *outer['files']]:
        h.checked(value)
    terminal = h.read(outer['terminal']['path'])
    h.require(terminal['exit'] == 0 and terminal['error'] is None and terminal['canonical_lock_retained'] and terminal['owned_cgroup_terminal'], 'Whole measure failed')
    properties = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    h.require(properties['MainPID'] == properties['ControlPID'] == '0' and properties['ActiveState'] == 'inactive' and properties['Result'] == 'success', 'Worker not terminal')
    raw = {Path(value['path']).name:value for value in outer['files']}
    h.require(h.read(raw['launcher-cleanup.json']['path'])['terminal'], 'Launcher not terminal')
    command = h.read(raw['command.json']['path'])
    h.require(shlex.split(h.data(raw['command.sh']['path']).decode()) == command['argv'] and h.data(raw['exit-status.txt']['path']).strip() == b'0' and h.data(raw['cwd.txt']['path']).decode().strip() == str(ROOT), 'Outer argv/cwd/status differs')
    ready = h.read(READY/'normal-five-canonical-measures-ready.json')
    unit = next(value for value in ready['units'] if value['arm'] == arm)
    grant = command['grant']
    h.require(grant['phase'] == 'measure' and grant['scope'] == 'all' and grant['arm'] == arm and grant['sources_sha256'] == ready['source_identity'] and grant['config'] == ready['config'] and grant['qualification'] == ready['qualification'] and grant['inputs'] == unit['input_pins'] and grant['output'] == str(output), 'Exact measure grant differs')
    h.require(all(grant[key] == value for key, value in unit['caps'].items()), 'Measure caps differ')
    intake = h.read(outer['worker_intake']['path'])
    h.checked(intake['admission'])
    h.require(intake['verified'] and intake['parent_lock_retained'] and h.read(intake['admission']['path']) == grant, 'Worker intake differs')
    worker = h.read(outer['worker']['path'])
    h.require(worker['complete'] and worker['phase'] == 'measure' and worker['scope'] == 'all' and worker['sources_sha256'] == ready['source_identity'] and worker['qualification'] == ready['qualification'] and worker['inputs'] == unit['input_pins'], 'Worker source/input differs')
    for value in worker['files']:
        h.checked(value)
    summary = h.read(output/'summary.json')
    result = summary['measurement']
    h.require(summary['phase'] == 'measure' and summary['scope'] == 'all' and summary['arm'] == arm and summary['native'] == [] and result['arm'] == arm and result['parents'] == 64 and not result['candidate_promoted'] and all(value is False for value in result['qualification_flags'].values()), 'Measurement scope/flags differ')
    stages = {}
    for value in summary['stages']:
        h.checked(value)
        stage = h.read(value['path'])
        h.require(stage['exit'] == 0 and stage['failure'] is None and stage['projection_error'] is None and not stage['missing_raw'], 'Native stage failed')
        h.require(set(stage['raw']) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}, 'Raw eight differs')
        for evidence in stage['raw'].values():
            h.checked(evidence)
        h.require(shlex.split(h.data(stage['raw']['command.sh']['path']).decode()) == stage['argv'] and h.data(stage['raw']['cwd.txt']['path']).decode().strip() == str(ROOT) and h.data(stage['raw']['exit-status.txt']['path']).strip() == b'0', 'Native raw argv/cwd/status differs')
        h.checked(stage['terminal'])
        h.checked(stage['group_cleanup'])
        h.require(h.read(stage['group_cleanup']['path'])['terminal'] and stage['name'] not in stages, 'Native launcher nonterminal/duplicate')
        stages[stage['name']] = dict(receipt=value, value=stage)
    h.require(len(stages) == 10, 'Expected four pairers/four summaries/two comparisons')
    emission = h.read(Path(ready['emission']['path']).parent/'emission.json')
    h.checked(emission['snapshot'])
    snapshot = h.read(emission['snapshot']['path'])
    target = h.read(Path(unit['input_pins'][1]['path']).parent/'summary.json')['mapping']
    nn = h.read(Path(ready['actual_NN_mapping']['path']).parent/'summary.json')['mapping']
    h.require(result['actual_native'] == snapshot['native'] and result['actual_nn_u_baseline'] == nn['mapped'] and target['mapped'] == unit['mapped'] and target['snapshot'] == nn['snapshot'] == emission['snapshot'], 'Actual native/NN/target lineage differs')
    def expected(name, argv):
        h.require(stages['sample-measure-'+name]['value']['argv'] == [str(value) for value in argv], 'Expected paired argv differs: '+name)
    endpoints = {}
    for baseline, left, before in (('native', snapshot['native'], snapshot['baseline_observations']), ('nn_u', nn['mapped'], nn['alleles'])):
        endpoints[baseline] = {}
        h.require(set(result['summaries'][baseline]) == {'100', '500'}, 'Both frozen masks required')
        for mask, eligible in sorted(snapshot['eligible'].items()):
            pairs = output/('pairs-'+baseline+'-'+mask)
            summed = output/('summary-'+baseline+'-'+mask)
            expected('pair-'+baseline+'-'+mask, [snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'], '--eligible', eligible['path'], '--left', left['path'], '--right', target['mapped']['path'], '--parents', snapshot['parents']['path'], '--output', pairs])
            expected('summary-'+baseline+'-'+mask, [snapshot['pairer']['path'], 'summarize', '--pairs', pairs, '--selected', 'all', '--output', summed])
            saved = result['summaries'][baseline][mask]
            h.checked(saved['summary'])
            value = h.read(saved['summary']['path'])
            h.require(saved['checks'] == math.summary_check(value) and value['parents'] == value['selected_parents'] == 64 and value['selection'] == 'all', 'Native summary contract/arithmetic differs')
            endpoints[baseline][mask] = dict(summary=saved['summary'], metrics=value['metrics'], checks=saved['checks'], parent_interval=value['parent_bootstrap'], block_interval=value['genomic_1mb_block_bootstrap'], matched_refexposure=value['matched_refexposure'], zero_exposure_parents=value['zero_exposure_parents'], scope=value['scope'])
        compared = output/('comparison-'+baseline)
        expected('compare-'+baseline, [snapshot['observer']['path'], 'compare', '--baseline', before, '--candidate', target['alleles'], '--output', compared])
        h.checked(result['comparisons'][baseline]['summary'])
    native_compare = h.read(result['comparisons']['native']['summary']['path'])
    h.require(native_compare['parents'] == 64 and sum(value['baseline_alt'] for value in native_compare['strata'].values()) == 829, 'Native829 ALT/64 census differs')
    start = h.data(raw['start.txt']['path']).decode().strip()
    end = h.data(raw['end.txt']['path']).decode().strip()
    memory = re.search(r'Memory peak: ([^\n]+)', h.data(raw['stderr']['path']).decode())
    return dict(schema='context-sample-feedback-normal-measure-retained-audit/1', complete=True, utc=datetime.now(timezone.utc).isoformat(), arm=arm, actual_exec_session_id=session, actual_exec_parent_returned=True, actual_exec_parent_exit=0, completion=h.pin(output/'execution-complete.json'), terminal=outer['terminal'], launcher_cleanup=raw['launcher-cleanup.json'], grant=intake['admission'], source_identity=ready['source_identity'], config=ready['config'], qualification=ready['qualification'], exact_inputs=unit['input_pins'], parents=64, stages=[value['receipt'] for value in stages.values()], endpoints=endpoints, comparisons=result['comparisons'], start_utc=start, end_utc=end, whole_unit_wall_seconds=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(), service_memory_peak_raw=None if memory is None else memory[1], explicit_metadata_bytes=h.TOTAL, maximum_bytes=64*1024**2, current_owned_results_bytes=sum(path.stat().st_size for path in (ROOT/'results/context-sample-feedback').rglob('*') if path.is_file()), no_reference_truth_tensor_archive_library_body_read=True, uncertainty_scope='technical parent/block conditional on frozen mappings and paired domains; not biological population or full-input basecalling', physical_read_independence_qualified=False, promotion_eligible=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', required=True)
    parser.add_argument('--session', type=int, required=True)
    arguments = parser.parse_args()
    result = audit(arguments.arm, arguments.session)
    path = READY/('measure-'+arguments.arm+'-1-audit.json')
    h.fresh(path, result)
    print(json.dumps(dict(audit=h.pin(path), result=result)))
