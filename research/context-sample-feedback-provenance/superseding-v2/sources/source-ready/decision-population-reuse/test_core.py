"""Source-only boundary controls; no producer or genuine trace body is run."""
import ast
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('reuse_test_core', HERE/'core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
spec = importlib.util.spec_from_file_location('reuse_test_runner', HERE/'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixtures():
    snapshot = dict(path='/fixture/snapshot', size=1, sha256='snapshot')
    pop = dict(arm='population', canonical_arm='population', sam=dict(sha256='e451d61479f5bf25205265c0a11d7ef0d8e3c3f3c7f54ffa5b5eb84604fa9ece'), edits=list(range(42)))
    nn = dict(arm='nn_u', sam=dict(sha256='ea97a4108b9544b95ec55f1f1bd84dd8490e041a22c91e4e5251e01808499009'), edits=list(range(9)))
    current = dict(parents=64, ordinary_cases=311, snapshot=snapshot, private_frames_applied=False, arms=[pop, nn])
    previous = deepcopy(current)
    previous['arms'][0].update(arm='feasible_escape', canonical_arm='feasible_escape')
    previous['arms'][1].update(arm='reference_free', historical_reference_free_mapping=dict(path='/fixture/mapped', size=1, sha256='mapped'))
    mapped = previous['arms'][1]['historical_reference_free_mapping']
    measurement = dict(emitted=deepcopy(pop['sam']), summaries={role:{'100':{}, '500':{}} for role in ('native', 'reference_free')}, comparisons={role:{} for role in ('native', 'reference_free')}, parents=64, arm='feasible_escape', canonical_arm='feasible_escape', candidate_promoted=False, biological_qualification=False)
    mapping = dict(snapshot=deepcopy(snapshot), aliases=['historical_free', 'nn_u', 'missing_source'], mapped=deepcopy(mapped))
    return current, previous, measurement, mapping


class BoundaryControls(unittest.TestCase):
    def test_join_positive(self):
        current, previous, result, mapping = fixtures()
        selected, old, mapped = core.join(current, previous, result, mapping)
        self.assertEqual(selected['edits'], old['edits'])
        self.assertEqual(mapped, mapping['mapped'])

    def reject(self, mutate):
        values = fixtures()
        mutate(*values)
        with self.assertRaises(ValueError):
            core.join(*values)

    def test_wrong_population_sam(self):
        self.reject(lambda a,b,c,d: a['arms'][0]['sam'].update(sha256='wrong'))

    def test_wrong_snapshot(self):
        self.reject(lambda a,b,c,d: d['snapshot'].update(sha256='wrong'))

    def test_changed_ledger(self):
        self.reject(lambda a,b,c,d: a['arms'][0]['edits'].reverse())

    def test_partial_parent_census(self):
        self.reject(lambda a,b,c,d: a.update(parents=63))

    def test_partial_case_census(self):
        self.reject(lambda a,b,c,d: b.update(ordinary_cases=310))

    def test_private_applied(self):
        self.reject(lambda a,b,c,d: b.update(private_frames_applied=True))

    def test_false_canonical_role(self):
        self.reject(lambda a,b,c,d: b['arms'][0].update(canonical_arm='population'))

    def test_nn_ledger_drift(self):
        self.reject(lambda a,b,c,d: a['arms'][1]['edits'].append(9))

    def test_nn_mapping_drift(self):
        self.reject(lambda a,b,c,d: d['mapped'].update(sha256='wrong'))

    def test_missing_actual_nn_alias(self):
        self.reject(lambda a,b,c,d: d.update(aliases=['historical_free']))

    def test_missing_frozen_mask(self):
        self.reject(lambda a,b,c,d: c['summaries']['native'].pop('500'))

    def test_no_promotion(self):
        self.reject(lambda a,b,c,d: c.update(candidate_promoted=True))

    def test_stage_positive_and_rejections(self):
        valid = dict(exit=0, failure=None, projection_error=None, missing_raw=[], argv=['tool','score'])
        core.stage_argv(valid, ['tool','score'])
        for patch in ({'exit':1}, {'failure':'failed'}, {'projection_error':'lost'}, {'missing_raw':['end.txt']}, {'argv':['tool','different']}):
            value = dict(valid, **patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                core.stage_argv(value, ['tool','score'])

    def test_actual_frozen_metadata_join(self):
        plan = json.loads((HERE/'plan.json').read_text())
        inputs = [Path(value['path']).parent for value in plan['reuse_inputs']]
        files = [inputs[0]/'emission.json', inputs[1]/'summary.json', inputs[2]/'execution-complete.json']
        outer = json.loads(files[-1].read_text())
        files += [Path(outer['worker']['path']), Path(outer['emission']['path']).parent/'emission.json']
        worker = json.loads(files[-2].read_text())
        old_emit_outer = json.loads(Path(outer['emission']['path']).read_text())
        old_emit_worker = json.loads(Path(old_emit_outer['worker']['path']).read_text())
        self.assertEqual(worker['sources_sha256'], core.DECISION_SOURCE)
        self.assertEqual(old_emit_worker['sources_sha256'], core.DECISION_EMISSION_SOURCE)
        files.append(Path(worker['result']['path']))
        self.assertLess(sum(path.stat().st_size for path in files), 2*1024**2)
        current, nn, _, _, old, result = [json.loads(path.read_text()) for path in files]
        core.join(current, old, result, nn['mapping'])
        changed = deepcopy(current)
        population = next(row for row in changed['arms'] if row['arm'] == 'population')
        population['sam']['sha256'] = 'transposed'
        with self.assertRaises(ValueError):
            core.join(changed, old, result, nn['mapping'])


class AdmissionControls(unittest.TestCase):
    def admitted(self, patch=None):
        now = datetime.now(timezone.utc)
        value = dict(schema='context-sample-feedback-continuation-admission/1', id='fixture', phase='reuse-population', scope='all', config={}, sources_sha256='fixture', compiled_sources_sha256=core.SAMPLE_SOURCE, output=str(ROOT/'results/context-sample-feedback/fixture-unused'), qualification={}, inputs=[], not_before_utc=(now-timedelta(seconds=1)).isoformat(), expires_utc=(now+timedelta(seconds=290)).isoformat(), cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-sample-feedback-fixture.service', case_id=None, source_audit=None, arm=None, recovery=None, **runner.CAPS)
        if patch:
            value.update(patch)
        with tempfile.TemporaryDirectory(prefix='admission-fixture-', dir=HERE) as directory:
            path = Path(directory)/'admission.json'
            path.write_text(json.dumps(value))
            args = argparse.Namespace(admission=path, phase='reuse-population', scope='all', output=Path(value['output']))
            return runner.grant(args, verify=False)

    def test_admission_positive(self):
        self.assertEqual(self.admitted()['phase'], 'reuse-population')

    def test_admission_bounds(self):
        for patch in ({'memory_bytes':16*1024**3}, {'maximum_wall_seconds':301}, {'maximum_growth_bytes':104857601}, {'cpu_quota':3}, {'swap_bytes':1}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.admitted(patch)

    def test_admission_old_or_foreign(self):
        for patch in ({'schema':'context-sample-feedback-admission/1'}, {'compiled_sources_sha256':'other'}, {'cgroup':'/foreign'}, {'arm':'population'}, {'extra':'field'}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.admitted(patch)

    def test_admission_expiry(self):
        with self.assertRaises(ValueError):
            self.admitted({'expires_utc':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()})

    def test_admission_output_escape(self):
        with self.assertRaises(ValueError):
            self.admitted({'output':'/tmp/foreign-result'})


class ActualDecisionTerminalControls(unittest.TestCase):
    def terminal(self):
        path = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision/logs/context-decision/program/measure-feasible-20261025T033225Z-775528/terminal.json')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), 'ad913f2d93a4fe7b4fa3086c06dbcd101f7a85e9d75ec4a578d9cdd10b448d54')
        return json.loads(path.read_text())

    def test_actual_terminal_positive(self):
        core.decision_terminal(self.terminal())

    def test_actual_worker_false(self):
        value = self.terminal()
        value['whole_worker_cgroup_terminal'] = False
        with self.assertRaises(ValueError):
            core.decision_terminal(value)

    def test_actual_worker_missing(self):
        value = self.terminal()
        del value['whole_worker_cgroup_terminal']
        with self.assertRaises(ValueError):
            core.decision_terminal(value)

    def test_actual_launcher_false(self):
        value = self.terminal()
        value['launcher_terminal'] = False
        with self.assertRaises(ValueError):
            core.decision_terminal(value)

    def test_actual_launcher_missing(self):
        value = self.terminal()
        del value['launcher_terminal']
        with self.assertRaises(ValueError):
            core.decision_terminal(value)

    def test_actual_failure_or_live_group(self):
        for patch in ({'exit':1}, {'error':'failed'}, {'canonical_lock_retained':False}):
            value = self.terminal()
            value.update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                core.decision_terminal(value)
        for patch in ({'MainPID':'123'}, {'ControlPID':'123'}, {'ControlGroup':'/live'}, {'ExecMainStatus':'1'}, {'ActiveState':'active'}, {'Result':'failed'}):
            value = self.terminal()
            value['proof']['properties'].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                core.decision_terminal(value)


class PreservedSourceControls(unittest.TestCase):
    def function(self, path, name):
        return next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)

    def test_whole_supervisor_only_two_literal_changes(self):
        actual = self.function(HERE/'run.py', 'supervise')
        expected = self.function(ROOT/'scripts/context-sample-feedback.py', 'supervise')
        replacements = {'continuation-supervisor-':'sample-supervisor-', 'context-sample-feedback-continuation-execution/1':'context-sample-feedback-execution/1'}
        for node in ast.walk(actual):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = replacements.get(node.value, node.value)
        self.assertEqual(ast.dump(actual), ast.dump(expected))

    def test_report_gate_loop_and_result_unchanged(self):
        actual = self.function(HERE/'core.py', 'report_science')
        expected = self.function(ROOT/'tools/context_sample_feedback/measure.py', 'report')
        def excerpt(function):
            start = next(i for i,node in enumerate(function.body) if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'checks' for target in node.targets))
            return ast.dump(ast.Module(body=function.body[start:start+3], type_ignores=[]))
        self.assertEqual(excerpt(actual), excerpt(expected))


if __name__ == '__main__':
    unittest.main(verbosity=2)
