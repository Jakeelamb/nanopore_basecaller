"""Explicit Decision population reuse and typed final report, outside source63."""
from copy import deepcopy
from datetime import datetime
import importlib.util
from pathlib import Path

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
HERE = Path(__file__).resolve().parent
SAMPLE_SOURCE = '63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2'
DECISION_SOURCE = '8e8607ebe49e9c990605777876f8657b0530138cf4a712c8ca42386103c92a1f'
DECISION_EMISSION_SOURCE = '6357128e0c6c5151001866a1f8e1fe1603807747ed38cd39919c29a42017c6ff'


def require(value, message):
    if not value:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ordinary():
    module = load('retained_sample_measure', ROOT/'tools/context_sample_feedback/measure.py')
    require(module.ROOT == module.b.ROOT == ROOT, 'Ordinary ROOT differs')
    require(module.b.identity(module.b.sources()) == SAMPLE_SOURCE, 'Compiled source63 changed')
    return module


def join(current, previous, result, nn_mapping):
    """Pure boundary used by real qualification and small rejection controls."""
    require(current['parents'] == previous['parents'] == 64 and current['ordinary_cases'] == previous['ordinary_cases'] == 311, 'Full parent/case census differs')
    require(current['snapshot'] == previous['snapshot'] == nn_mapping['snapshot'], 'Snapshot differs')
    require(current['private_frames_applied'] is previous['private_frames_applied'] is False, 'Private frames applied')
    selected = next(arm for arm in current['arms'] if arm['arm'] == 'population')
    old = next(arm for arm in previous['arms'] if arm['arm'] == 'feasible_escape')
    require(selected['canonical_arm'] == 'population' and old['canonical_arm'] == 'feasible_escape', 'Canonical role differs')
    require(selected['sam']['sha256'] == old['sam']['sha256'] == result['emitted']['sha256'] == 'e451d61479f5bf25205265c0a11d7ef0d8e3c3f3c7f54ffa5b5eb84604fa9ece', 'Exact population SAM differs')
    require(selected['edits'] == old['edits'] and len(selected['edits']) == 42, 'Exact edit ledger differs')
    new_nn = next(arm for arm in current['arms'] if arm['arm'] == 'nn_u')
    old_nn = next(arm for arm in previous['arms'] if arm['arm'] == 'reference_free')
    require(new_nn['sam']['sha256'] == old_nn['sam']['sha256'] == 'ea97a4108b9544b95ec55f1f1bd84dd8490e041a22c91e4e5251e01808499009' and new_nn['edits'] == old_nn['edits'], 'Actual NN SAM/ledger differs')
    require('nn_u' in nn_mapping['aliases'] and nn_mapping['mapped'] == old_nn['historical_reference_free_mapping'], 'Actual NN mapped baseline differs')
    require(set(result['summaries']) == set(result['comparisons']) == {'native', 'reference_free'} and all(set(value) == {'100', '500'} for value in result['summaries'].values()), 'Frozen endpoint domains differ')
    require(result['parents'] == 64 and result['arm'] == result['canonical_arm'] == 'feasible_escape' and result['candidate_promoted'] is result['biological_qualification'] is False, 'Retained measurement role differs')
    return selected, old, nn_mapping['mapped']


def stage_argv(stage, expected):
    require(stage['exit'] == 0 and stage['failure'] is None and stage['projection_error'] is None and not stage['missing_raw'], 'Original stage failed')
    require(stage['argv'] == [str(value) for value in expected], 'Original argv differs')


def decision_terminal(terminal):
    require({'exit', 'error', 'whole_worker_cgroup_terminal', 'launcher_terminal',
             'canonical_lock_retained', 'proof'} <= terminal.keys(), 'Decision terminal fields absent')
    require(terminal['exit'] == 0 and terminal['error'] is None
            and terminal['whole_worker_cgroup_terminal'] is True
            and terminal['launcher_terminal'] is True
            and terminal['canonical_lock_retained'] is True, 'Decision terminal failed')
    properties = terminal['proof']['properties']
    require(properties['MainPID'] == properties['ControlPID'] == '0'
            and properties['ControlGroup'] == '' and properties['ExecMainStatus'] == '0'
            and properties['ActiveState'] == 'inactive' and properties['Result'] == 'success',
            'Decision worker not terminal')


def qualify_reuse(inputs, output, execution):
    m = ordinary()
    b, c, w = m.b, m.c, m.b.w
    plan = c.read(HERE/'plan.json')
    require([c.pin(path/'execution-complete.json') for path in inputs] == plan['reuse_inputs'], 'Exact reuse inputs differ')
    b.completed(inputs[0], 'emit')
    current = c.read(inputs[0]/'emission.json')
    nn = b.completed(inputs[1], 'map')['mapping']
    prior = inputs[2]
    outer = c.read(prior/'execution-complete.json')
    c.check(plan['old_measurement'])
    require(outer['schema'] == 'context-decision-measure-execution/1' and outer['complete'] and outer['arm'] == 'feasible_escape' and outer['sources_sha256'] == DECISION_SOURCE and outer['whole_worker_cgroup_terminal'] and outer['launcher_tree_terminal'], 'Decision outer lineage differs')
    for value in [outer['worker'], outer['controller_worker'], outer['terminal'], outer['emission'], *outer['files']]:
        c.check(value)
    terminal = c.read(outer['terminal']['path'])
    decision_terminal(terminal)
    launcher = next(value for value in outer['files'] if value['path'].endswith('/launcher-cleanup.json'))
    require(c.read(launcher['path'])['terminal'], 'Decision launcher not terminal')
    controller = c.read(outer['controller_worker']['path'])
    require(controller['complete'] and controller['sources_sha256'] == DECISION_SOURCE and controller['intake']['verified'] and controller['intake']['parent_lock_retained'] and controller['worker'] == outer['worker'] and controller['emission'] == outer['emission'], 'Decision controller/intake differs')
    c.check(controller['controller'])
    c.check(controller['intake']['admission'])
    for state in ('kernel_start', 'kernel_end'):
        kernel = controller[state]
        require(kernel['address_space'] == [25769803776, 25769803776] and kernel['files']['cpu.max'] == '200000 100000\n' and kernel['files']['memory.max'].strip() == '17179869184' and kernel['files']['memory.swap.max'].strip() == '0', 'Original kernel caps differ')
    worker = c.read(outer['worker']['path'])
    require(worker['complete'] and worker['arm'] == 'feasible_escape' and worker['sources_sha256'] == DECISION_SOURCE and worker['emission'] == outer['emission'], 'Decision worker lineage differs')
    require(b.identity(worker['sources']) == DECISION_SOURCE, 'Decision source census identity differs')
    for value in [worker['admission'], worker['result'], *worker['sources'], *worker['files']]:
        c.check(value)
    decision = load('retained_decision_measure', Path(plan['old_measurement']['path']).parents[3]/'tools/context_decision/measure.py')
    require(decision.ROOT == decision.b.ROOT == Path(plan['old_measurement']['path']).parents[3]
            and decision.source_pins() == worker['sources'], 'Original Decision source location/census differs')
    decision.b.completed(Path(outer['emission']['path']).parent, 'emit')
    previous_worker = c.read(c.read(outer['emission']['path'])['worker']['path'])
    require(previous_worker['phase'] == 'emit' and previous_worker['scope'] == 'all'
            and previous_worker['sources_sha256'] == DECISION_EMISSION_SOURCE, 'Original emitted scope/source differs')
    projected = next(value for value in outer['files'] if value['path'].endswith('/raw-projection.json'))
    projection = decision.b.w.evidence.stage(projected, decision.c)
    stage_argv(projection, ['/home/jake/.local/bin/uv', 'run', '--no-sync', 'python', controller['controller']['path'], 'run',
        '--arm', 'feasible_escape', '--emission', Path(outer['emission']['path']).parent,
        '--output', prior, '--admission', controller['intake']['admission']['path'],
        '--worker-intake', Path(projected['path']).parent/'intake.json'])
    old_grant = c.read(controller['intake']['admission']['path'])
    start, end = (datetime.fromisoformat(Path(projection['raw'][name]['path']).read_text().strip()) for name in ('start.txt', 'end.txt'))
    require(datetime.fromisoformat(old_grant['not_before_utc']) <= start <= end <= datetime.fromisoformat(old_grant['expires_utc'])
            and (end-start).total_seconds() <= 300, 'Original whole-unit clocks exceed admission')
    result = c.read(worker['result']['path'])
    previous = c.read(Path(outer['emission']['path']).parent/'emission.json')
    selected, old, nn_mapped = join(current, previous, result, nn)
    c.check(previous['snapshot'])
    snapshot = c.read(previous['snapshot']['path'])
    for value in [snapshot[key] for key in ('parents', 'native', 'reference', 'truth', 'confident', 'pairer', 'observer')]+list(snapshot['eligible'].values())+list(snapshot['tools'].values()):
        c.check(value)
    for value in (selected['sam'], old['sam'], result['emitted'], result['mapped'], nn_mapped):
        c.check(value)
    require(Path(selected['sam']['path']).read_bytes() == Path(old['sam']['path']).read_bytes(), 'Full SAM bytes differ')
    stages = {}
    for value in worker['stages']:
        decision.b.w.evidence.stage(value, decision.c)
        stage = c.read(value['path'])
        require(stage['name'] not in stages, 'Duplicate old stage')
        stages[stage['name']] = stage
    require(len(stages) == 19, 'Original fixed native stage census differs')
    def old_stage(name, argv):
        value = stages['decision-measure-'+name]
        stage_argv(value, argv)
        return value
    old_stage('controls', ['uv', 'run', '--no-sync', 'python', '-m', 'unittest', 'discover', '-s', 'tools/context_decision/tests', '-p', 'test_measure.py', '-v'])
    bam = old_stage('sam-to-bam', [snapshot['tools']['samtools']['path'], 'view', '-b', old['sam']['path']])['raw']['stdout']
    aligned = old_stage('align', [snapshot['tools']['dorado']['path'], 'aligner', snapshot['tools']['index']['path'], bam['path'], '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])['raw']['stdout']
    mapped = old_stage('mapped-sam', [snapshot['tools']['samtools']['path'], 'view', '-h', aligned['path']])['raw']['stdout']
    require(mapped == result['mapped'], 'Actual mapped raw output differs')
    require(len(result['runtime']) == 4, 'Original runtime closure absent')
    tools = dict(dorado=snapshot['tools']['dorado'], samtools=snapshot['tools']['samtools'], pairer=snapshot['pairer'], observer=snapshot['observer'])
    for runtime in result['runtime']:
        require(runtime['binary'] == tools[runtime['tool']] and runtime['libraries'] and runtime['stage'] in worker['stages'], 'Runtime descriptor differs')
        c.check(runtime['binary'])
        for library in runtime['libraries']:
            c.check(library)
        stage = c.read(runtime['stage']['path'])
        stage_argv(stage, ['/usr/bin/ldd', runtime['binary']['path']])
        require('not found' not in Path(stage['raw']['stdout']['path']).read_text(), 'Original runtime dependency absent')
    for baseline, left in (('native', snapshot['native']), ('reference_free', nn_mapped)):
        for mask, eligible in sorted(snapshot['eligible'].items()):
            pairs = prior/('pair-'+baseline+'-'+mask)
            summary = prior/('summary-'+baseline+'-'+mask)
            old_stage('pair-'+baseline+'-'+mask, [snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'], '--eligible', eligible['path'], '--left', left['path'], '--right', result['mapped']['path'], '--parents', snapshot['parents']['path'], '--output', pairs])
            old_stage('summary-'+baseline+'-'+mask, [snapshot['pairer']['path'], 'summarize', '--pairs', pairs, '--selected', 'all', '--output', summary])
            saved = result['summaries'][baseline][mask]
            c.check(saved['summary'])
            summary_value = c.read(saved['summary']['path'])
            require(saved['checks'] == m.helper.summary_check(summary_value)
                    and summary_value['parents'] == summary_value['selected_parents'] == 64
                    and summary_value['selection'] == 'all', 'Original summary arithmetic/census differs')
    alleles = prior/'alleles'
    old_stage('observe', [snapshot['observer']['path'], 'observe', '--reference', snapshot['reference']['path'], '--vcf', snapshot['truth']['path'], '--confident', snapshot['confident']['path'], '--sam', result['mapped']['path'], '--parents', snapshot['parents']['path'], '--output', alleles])
    old_nn_alleles = Path(plan['old_nn_alleles'])
    for name in ('observations.tsv', 'variants.tsv', 'parents.tsv', 'children.tsv', 'events.tsv', 'alternate-alignments.tsv', 'excluded.tsv'):
        require((old_nn_alleles/name).read_bytes() == (Path(nn['alleles'])/name).read_bytes(), 'Actual NN allele baseline differs')
    for baseline, before in (('native', snapshot['baseline_observations']), ('reference_free', old_nn_alleles)):
        old_stage('compare-'+baseline, [snapshot['observer']['path'], 'compare', '--baseline', before, '--candidate', alleles, '--output', prior/('comparison-'+baseline)])
        c.check(result['comparisons'][baseline]['summary'])
    native_compare = c.read(result['comparisons']['native']['summary']['path'])
    require(native_compare['parents'] == 64 and sum(row['baseline_alt'] for row in native_compare['strata'].values()) == 829, 'Original native829 ALT/parent census differs')
    m.helper.custody(selected['sam']['path'], result['mapped']['path'], Path(snapshot['parents']['path']).read_text().splitlines(), c)
    mapping = dict(schema='sample-decision-exact-mapping-view/1', arm='population', aliases=['population'], emitted=selected['sam'], mapped=result['mapped'], snapshot=current['snapshot'], alleles=str(alleles), allele_files=[c.pin(path) for path in sorted(alleles.rglob('*')) if path.is_file()], original_producer=plan['old_measurement'], native_mapper_launched=False)
    measurement = dict(schema='sample-decision-exact-measurement-view/1', arm='population', actual_nn_u_baseline=nn_mapped, actual_native=snapshot['native'], summaries=dict(native=result['summaries']['native'], nn_u=result['summaries']['reference_free']), comparisons=dict(native=result['comparisons']['native'], nn_u=result['comparisons']['reference_free']), parents=64, candidate_promoted=False, qualification_flags=c.read(ROOT/'config/context-sample-feedback-v1.json')['qualification_flags'], original_producer=plan['old_measurement'], baseline_alias='reference_free bytes/mapping exactly equal frozen actual NN(U)', native_pairer_or_observer_launched=False)
    for value in mapping['allele_files']:
        c.check(value)
    c.fresh(output/'population-mapping-view.json', mapping)
    c.fresh(output/'population-measurement-view.json', measurement)
    partial = plan['partial_trace']
    for value in partial['files']:
        c.check(value)
    execution.stage('retained-query0-prefix-comparison', partial['argv'])
    comparison = c.read(partial['expected_output']['path'])
    c.require(comparison['schema'] == 'query0-retained-prefix-comparison/1' and comparison['complete']
              and comparison['source_identity'] == SAMPLE_SOURCE and comparison['trace_steps'] == 103
              and comparison['nonterminal_steps_compared'] == 102 and comparison['terminal_step_excluded']
              and set(comparison['comparisons']) == {'population', 'sample', 'combined'}
              and comparison['producer_rerun'] is comparison['truth_read'] is comparison['global_optimum_claim'] is False,
              'Partial trace comparison scope differs')
    return dict(kind='decision-population-reuse', decision_producer=plan['old_measurement'], mapping=c.pin(output/'population-mapping-view.json'), measurement=c.pin(output/'population-measurement-view.json'), partial_trace=c.pin(partial['expected_output']['path']), decision_measurement_source=DECISION_SOURCE, decision_emission_compiled_source=DECISION_EMISSION_SOURCE, sample_compiled_source=SAMPLE_SOURCE, new_scientific_producers=0)


def report(inputs, output, config, completed_own):
    m = ordinary()
    b, c = m.b, m.c
    plan = c.read(HERE/'plan.json')
    require([str(path.resolve()) for path in inputs] == plan['report_input_paths'], 'Fixed report input paths differ')
    for value in plan['report_existing_inputs']:
        c.check(value)
    population = [path for path in inputs if (path/'population-measurement-view.json').exists()]
    require(len(population) == 1, 'One explicitly typed population reuse receipt required')
    reused = completed_own(population[0], 'reuse-population')
    reused_measurement = c.read(reused['reuse']['measurement']['path'])
    b.completed(Path(config['emission']['path']).parent, 'emit')
    value = c.read(Path(config['emission']['path']).parent/'emission.json')
    observed = [path for path in inputs if (path/'native-observer').is_dir()]
    require(len(observed) == 1, 'One frozen-choice observer required')
    observation = b.completed(observed[0], 'observe')
    measured = [path for path in inputs if path not in population+observed]
    canonical = {}
    for path in measured:
        row = b.completed(path, 'measure')['measurement']
        worker = c.read(path/'complete.json')
        require(worker['inputs'][0] == plan['emission'] and plan['reuse_inputs'][1] in worker['inputs'], 'Measure emission/actual NN input differs')
        require(row['arm'] not in canonical, 'Duplicate canonical measurement')
        canonical[row['arm']] = row
    require(set(canonical) == {'disabled_edits', 'historical_free', 'sample', 'combined', 'wrong_source_control'}, 'Five current canonical measurements required')
    canonical['population'] = reused_measurement
    views, lineage = [], []
    by_arm = {arm['arm']:arm for arm in value['arms']}
    for arm in b.ARMS:
        canonical_arm = by_arm[arm]['canonical_arm']
        require(by_arm[arm]['sam'] == by_arm[canonical_arm]['sam'] and by_arm[arm]['edits'] == by_arm[canonical_arm]['edits'], 'Measurement alias SAM/ledger differs')
        row = deepcopy(canonical[canonical_arm])
        row['arm'] = arm
        views.append(row)
        lineage.append(dict(arm=arm, canonical_measurement=canonical_arm, exact_alias=arm != canonical_arm))
    result = report_science(views, observation, config['configuration'])
    result['schema'] = 'context-sample-feedback-typed-continuation-report/1'
    result['measurement_lineage'] = lineage
    c.fresh(output/'report.json', result)
    return c.pin(output/'report.json')


def report_science(measurements, observation, config):
    m = ordinary()
    b, c = m.b, m.c
    native = c.read(observation['native'][0]['path'])
    private_pin = next(pin for pin in native['files'] if pin['path'].endswith('/private.tsv'))
    private = b.table(private_pin['path'])
    checks = []
    for row in measurements:
        numerical = {}
        for baseline, domains in row['summaries'].items():
            c.require(set(domains) == {'100','500'}, 'Both frozen endpoint domains required')
            numerical[baseline] = all(item['checks']['one_percent'] and all(item['checks']['technical_upper_negative'].values()) for item in domains.values())
        productive = row['comparisons']['native']['support']['adequate_per_class_changed_support']
        counts = row['comparisons']['native']['support']['counts']
        retention = all(counts[category+'_baseline_alt'] == counts[category+'_retained'] for category in ('snv','insertion','deletion'))
        witnesses = [item for item in private if item['domain'] == 'private-withheld' and item['arm'] == row['arm']
                     and item['choice'] == 'accepted' and item['native_call'] == 'alt']
        private_gate = len({(item['case_id'],item['event_id']) for item in witnesses}) == 26 and all(item['call'] == 'alt' for item in witnesses)
        checks.append(dict(arm=row['arm'], endpoint_and_technical_gates=numerical, productive_alt_gate=productive,
            all_native_alt_retained=retention, private26_gate=private_gate, private_rows=len(witnesses), source_independence_gate=False, promotion=False))
    result = dict(schema='context-sample-feedback-report/1', measurements=measurements, checks=checks,
        private_diagnostics=private_pin, source_independence_unproved=True, candidate_promoted=False,
        reason='Source independence remains false regardless of exploratory endpoint results.', qualification_flags=config['qualification_flags'])
    return result
