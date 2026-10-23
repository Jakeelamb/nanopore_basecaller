"""Acceptance/rejection controls for the metadata-only controlled exporter."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import sys
import csv
import io
import json
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

SPEC = importlib.util.spec_from_file_location('controlled_report', Path(__file__).resolve().parents[1] / 'scripts/summarize-controlled.py')
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def pin(path):
    return {'path': str(Path('/fixture') / path), 'size': 1, 'sha256': 'a' * 64}


def fixture():
    verifier = 'b' * 64
    sources = [pin('benchmark.py'), pin('accuracy.py'), pin('accuracy')]
    amendment = {'version': '1.1', 'endpoint': 'fixed conditional endpoint', 'spanning_policy': 'exclude-confidence-neighborhood'}
    inputs = {'schema': 1, 'config': {'padding_and_confidence_erosion_bp': [100, 500], 'min_mapq': 30, 'sample_identity': 'publisher conditional'}}
    inputs['identity'] = r.identity(inputs)
    parents = {str(n): 1 for n in range(2608)}
    parents['0'] = 641767000
    policy = copy.deepcopy(r.b.CONTROLLED_POLICY)
    planned = []
    for name in sorted(r.EXPECTED_IDS):
        tier = name.rsplit('-', 1)[1]
        scope = name.split('-', 1)[0] if name != 'split-fixture-hac' else 'fixture'
        cohort = parents if scope == 'timing' or name.startswith('full-development') else {str(n): 1 for n in range(32 if scope == 'smoke' else 1)}
        planned.append({'id': name, 'tier': tier, 'scope': scope, 'parents': cohort,
                        'asset': {'sample': 'HG005' if 'sealed_test' in name else 'HG002'}, 'ids': pin(name + '.txt')['path']})
    plan = {'schema': 1, 'units': planned, 'pins': [pin(u['id'] + '.txt') for u in planned],
            'config': {'measurement_policy': policy}, 'environment': {'cpu_affinity': [0]},
            'tool_versions': {'dorado': '2.1.2+8b8fc5d'},
            'model_trees': {tier: {'path': '/fixture/' + tier, 'files': ['config.toml']} for tier in r.TIERS}}
    plan['sha256'] = r.identity(plan)
    truth = {'status': 'verified', 'inputs_identity': inputs['identity'], 'sources': sources,
             'amendment': amendment, 'binary': '/fixture/accuracy', 'truth': {}, 'pins': []}
    for sample in ('HG002', 'HG005'):
        for padding in r.DOMAINS:
            key = f'{sample}-{padding}'
            path = '/fixture/' + key
            truth['pins'].append(pin(key + '/eligible.bed'))
            truth['truth'][key] = {'directory': path, 'diagnostics': {'sample': sample, 'padding': padding, 'eligible_bases': 900,
                'spanning_policy': amendment['spanning_policy'], 'ordered_domain_bases': {'0': 1000, '1': 900},
                'spanning_removed_union_bases': 5, 'spanning_removed_intervals': [{'start': 10, 'end': 15}],
                'confidence': {'union_bases': 1000}, 'spanning_star_records': 1, 'eroded_bases': 950, 'eligible_intervals': 2},
                'producer': {'status': 'finished', 'exit': 0, 'context': {'inputs': inputs['identity'], 'sources': sources, 'amendment': amendment}}}
    units = []
    for p in planned:
        children = 2 if p['scope'] == 'fixture' else len(p['parents'])
        base = {'metrics': {'requested_parents': len(p['parents']), 'represented_parents': len(p['parents']), 'called_bases': 120,
                            'children': children, 'split_parents': int(p['scope'] == 'fixture')}, 'missing_parents': [], 'complete_processing': True}
        obs = {'status': 'verified', 'unit': p['id'], 'plan': plan['sha256'], 'verifier_sha256': verifier,
               'measurement_qualified': True, 'measurement_policy': {**policy, 'cpu_affinity': [0]}, 'basecall': base,
               'complete_work_qualification': 'verified', 'native_loader_error_lines': [], 'basecall_process_wall_seconds': 10,
               'completed_ns': 100, 'batch_selection_status': 'no_known_fallback_diagnostic',
               'calmd_verification': {'status': 'verified', 'all_other_primary_fields_equal': True, 'reference_check_stage': None,
                                      'exact_md_agreement': True, 'md_reference_ambiguity_bases': 0,
                                      'md_reference_ambiguity_records': 0, 'md_reference_ambiguity_exceptions': []}}
        stages = {}
        for name in r.STAGES:
            attempt = {'status': 'finished', 'exit': 0, 'receipt': f'/fixture/{p["id"]}/{name}/finish.json',
                       'measurement_qualified': True, 'resources': {'measurement_qualified': True, 'native_wall_seconds': 10,
                       'recorder_elapsed_seconds': 12, 'host_max_rss_kib': 100, 'user_cpu_seconds': 5, 'system_cpu_seconds': 1}}
            stages[name] = {**attempt, 'attempts': [attempt]}
        units.append({'unit': p['id'], 'tier': p['tier'], 'scope': p['scope'], 'status': 'verified', 'observation': obs,
                      'stages': stages, 'observation_failures': []})
    stock = {'plan': plan['sha256'], 'units': units, 'measurement_policy': policy, 'other_native_processes': [],
             'native_process_attempt_counts': {'finished': 19 * 13, 'total': 19 * 13},
             'timing': {tier: {'planned': 5, 'successful': 5, 'complete_work_baseline': True, 'basecall_attempts': 5} for tier in r.TIERS}}
    accuracy = {'full': {'status': 'verified', 'scope': 'full', 'plan': plan['sha256'], 'inputs': inputs['identity'],
                         'domain': amendment['endpoint'], 'sample_identity': inputs['config']['sample_identity'], 'units': []}}
    for p in planned:
        if p['scope'] != 'full':
            continue
        for padding in r.DOMAINS:
            c = {'m': 90, 'x': 5, 'i': 3, 'd': 2}
            n = len(p['parents'])
            score = {'schema': 1, 'min_mapq': 30, 'endpoint': 'giab_invariant_sequence_alignment_column_error',
                     'counts': c, 'alignment_columns': 100, 'eligible_query_columns': 98, 'eligible_reference_columns': 97,
                     'aggregate_error_fraction': .1, 'aggregate_accuracy': .9, 'parent_mean_accuracy': .9,
                     'parent_mean_error_fraction': .1, 'expected_parents': n, 'represented_parents': n,
                     'absent_parents': 0, 'positive_denominator_parents': 1, 'children': n,
                     'statuses': {'selected': 1, 'no_eligible_columns': n - 1},
                     'losses': {'query_bases': 120, 'excluded_query_bases': 5, 'policy_excluded_query_bases': 5,
                                'soft_clipped': 10, 'unmapped_query_bases': 2},
                     'bootstrap': {'status': 'available', 'replicates': 2000, 'scope': 'technical_within_flowcell_only',
                                   'seed': '0x4e414e4f504f5245', 'unit': 'positive_denominator_source_parent',
                                   'aggregate_error_fraction_95_percentile': [.05, .2], 'parent_mean_error_fraction_95_percentile': [.05, .2]},
                     'length_strata': {'0-999': c}, 'native_qscore_strata': {'10-<20': c}, 'homopolymer_context': {'1': c},
                     'qscore': {'10': {'query_columns': 98, 'errors_x_i': 8, 'expected_error_sum': 9.8}},
                     'homopolymer_length_endpoint': {'observations': 1}, 'homopolymer_length_counts': {'2-3': {'correct': 1, 'under': 0, 'over': 0, 'complex': 0}}}
            producer = {'status': 'finished', 'exit': 0, 'argv': ['/fixture/accuracy'], 'context': {'plan': plan['sha256'],
                        'unit': p['id'], 'padding': padding, 'sources': sources,
                        'truth': pin(p['asset']['sample'] + '-' + str(padding) + '/eligible.bed'), 'parents': pin(p['id'] + '.txt')}}
            accuracy['full']['units'].append({'unit': p['id'], 'tier': p['tier'], 'sample': p['asset']['sample'], 'padding': padding,
                                              'score': score, 'producer': producer})
    controls = [{'unit': name, 'control': control, 'status': 'absence recorded or empty rejected' if control == 'removed-parent' else 'rejected'}
                for name in ('smoke-1-hac', 'smoke-1-sup', 'split-fixture-hac')
                for control in (('foreign', 'duplicate', 'model', 'split-sp', 'split-pi', 'truncated', 'removed-parent') if name.startswith('split') else ('foreign', 'duplicate', 'model', 'truncated', 'reference', 'NM', 'removed-parent'))]
    return {'plan': plan, 'stock': stock, 'inputs': inputs, 'truth': truth, 'accuracy': accuracy,
            'qualification': {'status': 'verified', 'plan': plan['sha256'], 'verifier_sha256': verifier, 'controls': controls}}, verifier, sources, amendment


class ControlledReportTests(unittest.TestCase):
    def setUp(self):
        self.bundle, self.verifier, self.sources, self.amendment = fixture()

    def check(self):
        return r.validate_bundle(self.bundle, self.verifier, self.sources, self.amendment)

    def reject(self, text):
        with self.assertRaisesRegex(ValueError, text):
            self.check()

    def score(self):
        return self.bundle['accuracy']['full']['units'][0]['score']

    def unit(self, name='timing-1-hac'):
        return next(u for u in self.bundle['stock']['units'] if u['unit'] == name)

    def test_complete_fixture_accepts(self):
        planned, units, attempts = self.check()
        self.assertEqual(len(planned), 19)
        self.assertEqual(len(units), 19)
        self.assertEqual(len(attempts), 247)

    def test_missing_stock_unit_rejected(self):
        self.bundle['stock']['units'].pop()
        self.reject('19 controlled')

    def test_missing_sensitivity_domain_rejected(self):
        self.bundle['accuracy']['full']['units'].pop()
        self.reject('exact unit/domain')

    def test_missing_truth_domain_rejected(self):
        del self.bundle['truth']['truth']['HG005-500']
        self.reject('four truth')

    def test_qualification_control_must_reject_corruption(self):
        self.bundle['qualification']['controls'][0]['status'] = 'accepted'
        self.reject('control failed')

    def test_smoke_must_be_complete(self):
        self.unit('smoke-1-hac')['observation']['basecall']['complete_processing'] = False
        self.reject('complete 32-parent')

    def test_fixture_must_represent_genuine_split(self):
        self.unit('split-fixture-hac')['observation']['basecall']['metrics']['split_parents'] = 0
        self.reject('genuine split')

    def test_declared_iupac_reference_native_stage_accepted(self):
        unit = self.unit('full-validation-hac')
        unit['observation']['calmd_verification']['reference_check_stage'] = 'calmd-reference-iupac'
        unit['stages']['calmd-reference-iupac'] = copy.deepcopy(unit['stages']['calmd'])
        counts = self.bundle['stock']['native_process_attempt_counts']
        counts.update(finished=248, total=248)
        self.check()

    def test_undeclared_extra_native_stage_rejected(self):
        self.unit()['stages']['unexplained'] = copy.deepcopy(self.unit()['stages']['calmd'])
        self.reject('core 13 native stages')

    def test_iupac_reference_stage_rejected_on_timing_unit(self):
        self.unit()['observation']['calmd_verification']['reference_check_stage'] = 'calmd-reference-iupac'
        self.reject('unexpected IUPAC')

    def test_zero_columns_rejected(self):
        self.score()['counts'] = dict.fromkeys(('m', 'x', 'i', 'd'), 0)
        self.score()['alignment_columns'] = 0
        self.reject('zero/inconsistent')

    def test_outdated_verifier_rejected(self):
        self.unit()['observation']['verifier_sha256'] = 'c' * 64
        self.reject('current verifier')

    def test_outdated_native_qualification_rejected(self):
        self.bundle['qualification']['verifier_sha256'] = 'c' * 64
        self.reject('Current native qualification')

    def test_failed_measurement_rejected(self):
        self.unit()['stages']['align']['measurement_qualified'] = False
        self.reject('measurement failed')

    def test_failed_latest_native_attempt_rejected(self):
        self.unit()['stages']['align']['status'] = 'command_failed'
        self.unit()['stages']['align']['exit'] = 1
        self.reject('native measurement failed')

    def test_denominator_count_mismatch_rejected(self):
        self.score()['eligible_reference_columns'] += 1
        self.reject('reference denominator')

    def test_actual_accuracy_mismatch_rejected(self):
        self.score()['aggregate_accuracy'] = .999
        self.reject('inconsistent rate/count')

    def test_parent_rate_out_of_bounds_rejected(self):
        self.score()['parent_mean_error_fraction'] = -1
        self.score()['parent_mean_accuracy'] = 2
        self.reject('rate outside')

    def test_unknown_stratum_bin_rejected(self):
        bins = self.score()['length_strata']
        bins['all'] = bins.pop('0-999')
        self.reject('unknown length_strata')

    def test_negative_cancelling_stratum_counts_rejected(self):
        bins = self.score()['length_strata']
        bins['0-999'] = {'m': -1, 'x': 0, 'i': 0, 'd': 0}
        bins['1000-9999'] = {'m': 91, 'x': 5, 'i': 3, 'd': 2}
        self.reject('nonnegative integer')

    def test_negative_cancelling_loss_counts_rejected(self):
        self.score()['losses']['soft_clipped'] = -1
        self.score()['losses']['excluded_query_bases'] = 16
        self.reject('nonnegative integer')

    def test_q_histogram_count_mismatch_rejected(self):
        self.score()['qscore']['10']['errors_x_i'] = 9
        self.reject('Q error mismatch')

    def test_score_native_ledger_mismatch_rejected(self):
        self.score()['losses']['query_bases'] += 1
        self.score()['losses']['soft_clipped'] += 1
        self.reject('score/native ledger')

    def test_incomplete_timing_rejected(self):
        self.unit()['observation']['complete_work_qualification'] = 'unavailable'
        self.reject('incomplete timing')

    def test_hidden_attempt_count_rejected(self):
        self.bundle['stock']['native_process_attempt_counts']['total'] -= 1
        self.reject('attempt count mismatch')

    def test_prior_failure_retained_and_allowed(self):
        stage = self.unit()['stages']['basecall']
        attempt = {**copy.deepcopy(stage['attempts'][0]), 'status': 'command_failed', 'exit': 1,
                   'receipt': '/fixture/failed/finish.json', 'measurement_qualified': False, 'superseded': True}
        stage['attempts'].insert(0, attempt)
        counts = self.bundle['stock']['native_process_attempt_counts']
        counts.update(command_failed=1, total=248)
        self.bundle['stock']['timing']['hac']['basecall_attempts'] = 6
        _, _, attempts = self.check()
        self.assertEqual(sum(a['exit'] == 1 for a in attempts), 1)

    def test_full_absent_parent_remains_observable(self):
        unit = self.unit('full-development-hac')
        base = unit['observation']['basecall']
        base['metrics']['represented_parents'] -= 1
        base['missing_parents'] = ['1']
        base['complete_processing'] = False
        unit['observation']['complete_work_qualification'] = 'unavailable: absent parents'
        for row in self.bundle['accuracy']['full']['units']:
            if row['unit'] == unit['unit']:
                row['score']['represented_parents'] -= 1
                row['score']['absent_parents'] = 1
        self.check()

    def test_foreign_truth_pin_rejected(self):
        self.bundle['accuracy']['full']['units'][0]['producer']['context']['truth'] = pin('wrong.bed')
        self.reject('wrong truth domain')

    def test_foreign_scorer_sources_rejected(self):
        self.bundle['truth']['sources'] = []
        self.reject('Current accuracy source')

    def test_changed_plan_identity_rejected(self):
        self.bundle['plan']['config']['measurement_policy']['cache_policy'] = 'cold'
        self.reject('Changed plan')

    def test_self_consistent_changed_measurement_policy_rejected(self):
        bundle = self.bundle
        bundle['plan']['config']['measurement_policy']['cache_policy'] = 'cold'
        bundle['plan']['sha256'] = r.identity({k: v for k, v in bundle['plan'].items() if k != 'sha256'})
        plan_id = bundle['plan']['sha256']
        bundle['stock']['plan'] = bundle['qualification']['plan'] = plan_id
        for unit in bundle['stock']['units']:
            unit['observation']['plan'] = plan_id
            unit['observation']['measurement_policy']['cache_policy'] = 'cold'
        for report in bundle['accuracy'].values():
            report['plan'] = plan_id
            for row in report['units']:
                row['producer']['context']['plan'] = plan_id
        self.reject('Frozen controlled measurement policy')

    def test_missing_calmd_verification_rejected(self):
        self.unit()['observation']['calmd_verification']['status'] = 'failed'
        self.reject('calmd verification required')

    def test_timing_accuracy_report_must_be_complete_when_present(self):
        report = copy.deepcopy(self.bundle['accuracy']['full'])
        report['scope'] = 'timing'
        self.bundle['accuracy']['timing'] = report
        self.reject('exact unit/domain')

    def test_statistics_are_sample_sd_and_raw_clocks(self):
        stats = r.summary([1., 2., 3., 4., 5.])
        self.assertEqual(stats['raw'], [1., 2., 3., 4., 5.])
        self.assertEqual(stats['median'], 3.)
        self.assertAlmostEqual(stats['sample_sd'], 2.5 ** .5)
        self.assertAlmostEqual(stats['cv_percent'], 2.5 ** .5 / 3 * 100)

    def test_native_clock_projection_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'time.txt').write_text('Elapsed (wall clock) time (h:mm:ss or m:ss): 1:02.50\nUser time (seconds): 8.00\nSystem time (seconds): 2.00\nMaximum resident set size (kbytes): 1000\n')
            receipt = {'recorder': directory, 'elapsed_ns': 65_000_000_000, 'measurement_qualified': True}
            resources = {'native_wall_seconds': 62.5, 'recorder_elapsed_seconds': 65., 'user_cpu_seconds': 8., 'system_cpu_seconds': 2.,
                         'host_max_rss_kib': 1000., 'measurement_qualified': True}
            r.validate_resources(receipt, resources)
            resources['native_wall_seconds'] = 60.
            with self.assertRaisesRegex(ValueError, 'inconsistent rate/count'):
                r.validate_resources(receipt, resources)

    def test_render_complete_fixture_retains_scientific_scope_and_raw_clocks(self):
        planned, units, attempts = self.check()
        reader = r.Reader()
        with patch.object(r, 'telemetry', return_value={'scope': 'observer', 'peaks': {}, 'sample_means': {}, 'host': {}}):
            evidence = r.evidence_bundle(self.bundle, planned, units, attempts, reader)
        self.bundle['_inputs_path'] = Path('/fixture/inputs.json')
        text = r.render(self.bundle, evidence, planned, units, Path('/fixture/stock'), Path('/fixture/accuracy'), Path('/fixture/evidence.json'))
        self.assertIn('19/19', text)
        self.assertIn('10, 10, 10, 10, 10', text)
        self.assertIn('publisher donor labels', text)
        self.assertIn('within-pilot technical', text)
        self.assertIn('500 bp is the predeclared sensitivity', text)
        self.assertIn('D has no emitted Q', text)
        self.assertIn('80.000000–95.000000', text)


class RawReceiptTests(unittest.TestCase):
    """Tiny native-receipt fixtures exercise the same checks used by load_bundle."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(r, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.stage = self.root / 'units' / 'test' / 'basecall' / '0001'
        self.recorder = self.root / 'logs' / 'fixture'
        self.stage.mkdir(parents=True)
        self.recorder.mkdir(parents=True)
        self.argv = ['/usr/bin/printf', 'native\n']
        self.context = {'plan': 'fixture', 'unit': 'test'}
        self.policy = {**r.b.CONTROLLED_POLICY, 'cpu_affinity': [0]}
        encoded = subprocess.check_output(['bash', '-c', 'printf "%q " "$@"; printf "\\n"', '--', *self.argv], text=True)
        values = {'command.sh': encoded, 'cwd.txt': str(self.root) + '\n', 'start.txt': '2026-10-22T00:00:01Z\n',
                  'end.txt': '2026-10-22T00:00:02Z\n', 'exit-status.txt': '0\n', 'stdout': 'native\n', 'stderr': '',
                  'time.txt': 'Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.00\nUser time (seconds): 0.10\nSystem time (seconds): 0.02\nMaximum resident set size (kbytes): 1000\nExit status: 0\n'}
        for name, value in values.items():
            (self.recorder / name).write_text(value)
        self.start = {'argv': self.argv, 'context': self.context, 'explicit_env': {'LC_ALL': 'C'},
                      'status': 'running', 'utc': '2026-10-22T00:00:00+00:00', 'monotonic_ns': 0,
                      'measurement_policy': self.policy, 'gpu_start': True}
        self.start['key'] = r.identity({'argv': self.argv, 'context': self.context, 'measurement': self.policy, 'gpu_start': True})
        self.receipt = {**self.start, 'status': 'finished', 'exit': 0, 'failure': None, 'measurement_qualified': True,
                        'recorder': str(self.recorder), 'stdout': str(self.recorder / 'stdout'),
                        'native_launch_utc': '2026-10-22T00:00:01+00:00', 'native_end_utc': '2026-10-22T00:00:02+00:00',
                        'end_utc': '2026-10-22T00:00:03+00:00', 'elapsed_ns': 3_000_000_000,
                        'native_launch_monotonic_ns': 1_000_000_000, 'native_end_monotonic_ns': 2_000_000_000}
        gpu_text = 'timestamp,index,utilization.gpu [%],memory.used [MiB],power.draw [W],temperature.gpu,clocks.current.sm [MHz]\n2026/10/22 00:00:01,0,50 %,100 MiB,60 W,35,1500 MHz\n'
        self.samples = []
        for index, ns in enumerate((500_000_000, 1_500_000_000, 2_500_000_000)):
            self.samples.append({'phase': ('before', 'during', 'after')[index], 'monotonic_ns': ns, 'utc': '2026-10-22T00:00:01+00:00',
                'ac_online': '1', 'platform_profile': 'balanced', 'cpu_affinity': [0], 'foreign_gpu_compute_pids': [],
                'owned_cpu_affinities': {}, 'errors': [], 'control_errors': [], 'loadavg': '1 1 1', 'proc_stat': 'cpu 1 2 3',
                'gpu_core': {'exit': 0, 'utc': '2026-10-22T00:00:01+00:00', 'monotonic_ns': ns + 1_000_000,
                             'completed_monotonic_ns': ns + 10_000_000, 'stdout': gpu_text}})
        rows = [row for sample in self.samples for row in r.b.core_gpu_rows(sample['gpu_core'])]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        (self.stage / 'gpu.csv').write_text(buffer.getvalue())
        for phase in ('before', 'after'):
            (self.stage / f'gpu-state-{phase}.json').write_text(json.dumps({'exit': 0}))
        (self.stage / 'preflight.jsonl').write_text('\n'.join(json.dumps({'gpu': {'idle': True}}) for _ in range(3)) + '\n')
        self.rewrite()

    def rewrite(self):
        (self.stage / 'host.jsonl').write_text('\n'.join(json.dumps(s) for s in self.samples) + '\n')
        (self.stage / 'start.json').write_text(json.dumps(self.start))
        self.receipt['pins'] = [r.file_pin(p) for directory in (self.stage, self.recorder)
                                for p in sorted(directory.iterdir()) if p.is_file() and p.name != 'finish.json']
        (self.stage / 'finish.json').write_text(json.dumps(self.receipt))

    def check(self):
        reader = r.Reader()
        r.validate_native_receipt(self.receipt, self.argv, self.context, reader, self.stage / 'finish.json', self.policy, True)
        r.b.measurement_evidence(self.receipt, self.policy)

    def test_complete_raw_receipt_and_measurement_accepts(self):
        self.check()

    def test_raw_nonzero_exit_cannot_be_projected_as_success(self):
        (self.recorder / 'exit-status.txt').write_text('1\n')
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'Raw native exit status mismatch'):
            self.check()

    def test_raw_wrong_command_rejected_even_with_updated_pins(self):
        (self.recorder / 'command.sh').write_text('/usr/bin/false \n')
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'Raw native command mismatch'):
            self.check()

    def test_raw_wrong_cwd_rejected_even_with_updated_pins(self):
        (self.recorder / 'cwd.txt').write_text('/wrong\n')
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'cwd mismatch'):
            self.check()

    def test_raw_reversed_utc_rejected(self):
        (self.recorder / 'end.txt').write_text('2026-10-21T23:59:59Z\n')
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'Raw native UTC'):
            self.check()

    def test_changed_stage_identity_rejected(self):
        self.start['key'] = self.receipt['key'] = 'f' * 64
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'stage identity mismatch'):
            self.check()

    def test_changed_expected_scorer_argv_rejected(self):
        with self.assertRaisesRegex(ValueError, 'command/context mismatch'):
            r.validate_native_receipt(self.receipt, ['/wrong/ref'], self.context, r.Reader(), self.stage / 'finish.json', self.policy, True)

    def test_measurement_flag_does_not_hide_control_failure(self):
        self.samples[1]['ac_online'] = '0'
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'Invalid retained measurement sample'):
            self.check()

    def test_measurement_flag_does_not_hide_nonnumeric_gpu(self):
        self.samples[1]['gpu_core']['stdout'] = self.samples[1]['gpu_core']['stdout'].replace('60 W', 'N/A')
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'nonnumeric core GPU'):
            self.check()

    def test_measurement_flag_does_not_hide_csv_disagreement(self):
        path = self.stage / 'gpu.csv'
        path.write_text(path.read_text().replace('60 W', '70 W'))
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'changed core GPU CSV'):
            self.check()

    def test_measurement_flag_does_not_hide_unbracketed_native_clock(self):
        self.receipt['native_end_monotonic_ns'] = 2_900_000_000
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'do not bracket native'):
            self.check()

    def test_measurement_flag_does_not_hide_bad_cooldown(self):
        (self.stage / 'preflight.jsonl').write_text(json.dumps({'gpu': {'idle': False}}) + '\n')
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'cooldown evidence'):
            self.check()

    def test_newer_interrupted_native_attempt_rejected(self):
        next_stage = self.stage.parent / '0002'
        next_stage.mkdir()
        (next_stage / 'start.json').write_text(json.dumps(self.start))
        with self.assertRaisesRegex(ValueError, 'Newer native attempt'):
            self.check()

    def test_bound_decoder_requires_unique_observation_pinned_receipt(self):
        observation = {'pins': [r.file_pin(self.stage / 'finish.json'), *self.receipt['pins']]}
        path, decoder = r.bound_stage(observation, self.stage.parent.parent, 'basecall', r.Reader())
        self.assertEqual(path, self.stage / 'finish.json')
        self.assertEqual(decoder['stdout'], self.receipt['stdout'])
        next_stage = self.stage.parent / '0002'
        next_stage.mkdir()
        (next_stage / 'finish.json').write_text(json.dumps(self.receipt))
        observation['pins'].append(r.file_pin(next_stage / 'finish.json'))
        with self.assertRaisesRegex(ValueError, 'ambiguous observation-bound'):
            r.bound_stage(observation, self.stage.parent.parent, 'basecall', r.Reader())

    def test_bound_decoder_rejects_other_output_in_observation(self):
        observation = {'pins': [r.file_pin(self.stage / 'finish.json')]}
        with self.assertRaisesRegex(ValueError, 'Missing/conflicting bound pin'):
            r.bound_stage(observation, self.stage.parent.parent, 'basecall', r.Reader())

    def test_iupac_native_faidx_bases_must_match_coordinates(self):
        output = self.root / 'iupac.fa'
        output.write_text('>chr2:10-10\nY\n')
        verification = {'status': 'verified', 'all_other_primary_fields_equal': True, 'exact_md_agreement': False,
                        'md_reference_ambiguity_bases': 1, 'md_reference_ambiguity_records': 1,
                        'md_reference_ambiguity_exceptions': [{'child': 'child', 'contig': 'chr2', 'reference_position_1based': 10, 'reference_base': 'Y'}]}
        r.validate_iupac(verification, output)
        output.write_text('>chr2:10-10\nW\n')
        with self.assertRaisesRegex(ValueError, 'IUPAC coordinates/bases mismatch'):
            r.validate_iupac(verification, output)


class MeasurementNotesTests(unittest.TestCase):
    def setUp(self):
        self.bundle, _, _, _ = fixture()
        self.units = {u['unit']: u for u in self.bundle['stock']['units']}
        for unit in self.units.values():
            for stage in unit['stages'].values():
                stage['resources'].update(start_utc='2026-10-23T00:20:00+00:00', end_utc='2026-10-23T00:25:00+00:00')
            if unit['scope'] == 'timing':
                unit['stages']['basecall']['resources'].update(start_utc='2026-10-23T00:30:00+00:00', end_utc='2026-10-23T00:31:00+00:00')
        self.notes = {'schema': 1, 'plan': self.bundle['plan']['sha256'], 'notes': [{
            'unit': 'full-sealed_test-sup', 'stage': 'basecall', 'kind': 'owned_cpu_interference',
            'status': 'descriptive_with_owned_cpu_interference', 'start_utc': '2026-10-23T00:23:00+00:00',
            'end_utc': '2026-10-23T00:25:00+00:00', 'worker_terminated_before_utc': '2026-10-23T00:26:04+00:00',
            'time_precision': 'approximate', 'pid': 672880, 'command': ['uv', 'run', 'python', '-'],
            'reason': 'Disclosed metadata lookup unexpectedly used one CPU core', 'evidence_paths': []}]}

    def check(self):
        r.validate_measurement_notes(self.notes, self.bundle['plan'], self.units)

    def test_approximate_full_clock_annotation_preserves_raw_clock(self):
        before = self.units['full-sealed_test-sup']['observation']['basecall_process_wall_seconds']
        self.check()
        self.assertEqual(r.timing_note({'measurement_notes': self.notes}, 'full-sealed_test-sup'), 'descriptive_with_owned_cpu_interference')
        self.assertEqual(self.units['full-sealed_test-sup']['observation']['basecall_process_wall_seconds'], before)

    def test_foreign_plan_annotation_rejected(self):
        self.notes['plan'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'plan/schema mismatch'):
            self.check()

    def test_foreign_unit_annotation_rejected(self):
        self.notes['notes'][0]['unit'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'foreign unit/stage'):
            self.check()

    def test_nonoverlapping_incident_rejected(self):
        self.notes['notes'][0].update(start_utc='2026-10-22T00:23:00+00:00', end_utc='2026-10-22T00:25:00+00:00')
        with self.assertRaisesRegex(ValueError, 'does not overlap'):
            self.check()

    def test_incident_on_primary_timing_rejected(self):
        self.notes['notes'][0]['unit'] = 'timing-1-sup'
        with self.assertRaisesRegex(ValueError, 'Primary timing repetition'):
            self.check()

    def test_primary_timing_before_confirmed_worker_termination_rejected(self):
        self.units['timing-1-hac']['stages']['basecall']['resources']['start_utc'] = '2026-10-23T00:26:00+00:00'
        with self.assertRaisesRegex(ValueError, 'before confirmed worker termination'):
            self.check()

    def test_known_incident_cannot_be_removed_with_empty_notes(self):
        self.bundle['plan']['sha256'] = r.INCIDENT_PLAN
        self.notes.update(plan=r.INCIDENT_PLAN, notes=[])
        with self.assertRaisesRegex(ValueError, 'Known owned CPU incident'):
            self.check()

    def test_empty_override_cannot_hide_canonical_incident(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, 'ROOT', Path(directory)):
            self.bundle['plan']['sha256'] = r.INCIDENT_PLAN
            self.notes['plan'] = r.INCIDENT_PLAN
            canonical = Path(directory) / r.INCIDENT_NOTES
            canonical.parent.mkdir(parents=True)
            canonical.write_text(json.dumps(self.notes))
            override = Path(directory) / 'override.json'
            override.write_text(json.dumps({'schema': 1, 'plan': r.INCIDENT_PLAN, 'notes': []}))
            with self.assertRaisesRegex(ValueError, 'override differs'):
                r.load_measurement_notes(override, Path(directory), self.bundle['plan'], self.units, r.Reader())


if __name__ == '__main__':
    unittest.main()
