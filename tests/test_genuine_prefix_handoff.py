import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/genuine-prefix-handoff.py'
module_spec = importlib.util.spec_from_file_location('genuine_prefix_handoff', SCRIPT)
handoff = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = handoff
module_spec.loader.exec_module(handoff)
io = handoff.io


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def spec(self):
        sources = [io.pin(path) for path in (SCRIPT, Path(io.__file__), Path(handoff.joint.__file__),
            handoff.F1 / 'tools/prefix_feedback/qualification.py')]
        sources += [io.GUARD, io.F4]
        fake_f3_source = dict(path=str(handoff.F3 / 'metadata-only-source'), size=1, sha256='f' * 64)
        sources.append(fake_f3_source)
        operand = dict(path=str(self.root / 'unexecuted-operand'), size=0, sha256='0' * 64)
        return dict(schema='genuine-prefix-handoff-spec/1', advance_spec=operand, advance_complete=operand,
            expected_producer=operand, f1=dict(operand, path=str(handoff.F1 / 'results/unexecuted-binary')),
            f2=dict(operand, path=str(handoff.F2 / 'results/unexecuted-binary')),
            f3=dict(operand, path=str(handoff.F3 / 'results/unexecuted-binary')),
            f2_cwd=str(handoff.F2), f3_cwd=str(handoff.F3), source_pins=sources,
            f3_source_files=[fake_f3_source], source_sha256='b' * 64,
            expected=dict(read_id='development-parent', parent_index=0, chunk_index=0, block_index=0,
                          row_begin=0, row_end=497, previous_state_sha256='a' * 64, plan_sha256='c' * 64),
            policy=copy.deepcopy(handoff.POLICY))

    def load(self, value):
        path = self.root / 'spec.json'
        io.fresh(path, value)
        return handoff.HandoffSpec.load(path, io.pin(path)['sha256'])

    def test_parse_closed_spec_does_not_authorize_missing_dependencies(self):
        parsed = self.load(self.spec())
        self.assertEqual(parsed.value['expected']['row_end'], 497)
        with self.assertRaises(ValueError):
            parsed.check_dependencies()

    def test_reject_spec_hash_tampering(self):
        path = self.root / 'spec.json'
        io.fresh(path, self.spec())
        with self.assertRaisesRegex(ValueError, 'external handoff spec hash'):
            handoff.HandoffSpec.load(path, '0' * 64)

    def test_reject_extra_truth_field(self):
        value = self.spec()
        value['truth'] = 'not-authorized'
        with self.assertRaisesRegex(ValueError, 'spec fields'):
            self.load(value)

    def test_reject_holdout_parent(self):
        value = self.spec()
        value['expected']['read_id'] = 'HG005'
        with self.assertRaisesRegex(ValueError, 'development parent'):
            self.load(value)

    def test_reject_future_block_or_changed_endpoint(self):
        for field, replacement in (('block_index', 1), ('row_begin', 1), ('row_end', 513), ('parent_index', 1)):
            with self.subTest(field=field), tempfile.TemporaryDirectory(dir=self.root) as directory:
                value = self.spec()
                value['expected'][field] = replacement
                path = Path(directory) / 'spec.json'
                io.fresh(path, value)
                with self.assertRaisesRegex(ValueError, 'first block'):
                    handoff.HandoffSpec.load(path, io.pin(path)['sha256'])

    def test_reject_changed_policy_or_cwd(self):
        for field in ('policy', 'f3_cwd'):
            with self.subTest(field=field), tempfile.TemporaryDirectory(dir=self.root) as directory:
                value = self.spec()
                if field == 'policy':
                    value['policy']['maximum_context_weight'] = 0.4
                else:
                    value[field] += '-foreign'
                path = Path(directory) / 'spec.json'
                io.fresh(path, value)
                with self.assertRaises(ValueError):
                    handoff.HandoffSpec.load(path, io.pin(path)['sha256'])

    def test_reject_foreign_binary_or_missing_recorder_closure(self):
        for field in ('f1', 'source_pins'):
            with self.subTest(field=field), tempfile.TemporaryDirectory(dir=self.root) as directory:
                value = self.spec()
                if field == 'f1':
                    value[field]['path'] = '/tmp/foreign-binary'
                else:
                    value[field] = value[field][1:]
                path = Path(directory) / 'spec.json'
                io.fresh(path, value)
                with self.assertRaises(ValueError):
                    handoff.HandoffSpec.load(path, io.pin(path)['sha256'])

    def test_changed_consumed_pin_is_rejected(self):
        path = self.root / 'metadata.json'
        io.fresh(path, dict(read_id='original'))
        pin = io.pin(path)
        path.write_text('{"read_id":"foreign"}')
        with self.assertRaisesRegex(ValueError, 'consumed pin differs'):
            handoff.consumed(pin)

    def test_resealed_controls_keep_independent_binding_and_original(self):
        batch = dict(binding=dict(read_id='parent', previous_state_sha256='a' * 64), candidates=[])
        before = copy.deepcopy(batch)
        controls = handoff.binding_controls(batch, dict(prior='uniform'), self.root)
        self.assertEqual(batch, before)
        self.assertEqual([label for label, _ in controls], ['foreign-read', 'stale-previous-state'])
        for _, request in controls:
            modified = handoff.consumed(request['batch_pin'])
            self.assertNotEqual(modified['binding'], request['expected_binding'])
            self.assertEqual(request['expected_binding'], batch['binding'])
            self.assertEqual(request['expected_batch_sha256'], io.pin(request['batch_pin']['path'])['sha256'])

    def snapshot(self):
        value = self.spec()
        block = dict(read_id='development-parent', parent_id='development-parent', chunk_index=0,
            block_index=0, row_begin=0, row_end=497, chunk_row_begin=0, chunk_row_end=497,
            available_score_end=497, tensor={}, release_receipt={})
        state = dict(metadata_only=True)
        snapshot = dict(schema='prefix-snapshot/1', read_id='development-parent', parent_id='development-parent',
            plan_sha256='c' * 64, source_sha256='b' * 64, previous_state_sha256='a' * 64,
            state_sha256=handoff.digest(state), initial_prior='uniform-all-CRF-states',
            locations=[], location_updates=[], binding=copy.deepcopy(block))
        return snapshot, state, block, value

    def test_reject_snapshot_foreign_stale_endpoint_and_fake_k1_prior(self):
        for field, replacement in (('read_id', 'foreign'), ('previous_state_sha256', 'd' * 64),
                                   ('initial_prior', 'k1-toy')):
            snapshot, state, block, value = self.snapshot()
            snapshot[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'independent binding'):
                handoff.check_snapshot(snapshot, state, block, value)
        snapshot, state, block, value = self.snapshot()
        snapshot['binding']['row_end'] += 1
        with self.assertRaisesRegex(ValueError, 'block binding'):
            handoff.check_snapshot(snapshot, state, block, value)

    def test_zero_additions_equal_H_U_valid_and_original_mutation_rejected(self):
        original = dict(binding={}, native=dict(sequence='A', quality='!'), locations=[],
            reference_free_candidate_id='H', union_nn_candidate_id='H',
            candidates=[dict(id='H', sequence='A', neural_log_likelihood=-1, context_cost=0)])
        handoff.check_merge(original, copy.deepcopy(original))
        final = copy.deepcopy(original)
        final['candidates'].append(dict(id='U', sequence='AA', neural_log_likelihood=0, context_cost=0))
        final['union_nn_candidate_id'] = 'U'
        handoff.check_merge(original, final)
        final['candidates'][0]['neural_log_likelihood'] = 0
        with self.assertRaisesRegex(ValueError, 'original candidate objects'):
            handoff.check_merge(original, final)

    def test_existing_empty_and_partial_attempts_refuse_without_modification(self):
        result_root = self.root / 'results/prefix-feedback'
        result_root.mkdir(parents=True)
        for name in ('empty', 'partial'):
            output = result_root / name
            output.mkdir()
            if name == 'partial':
                (output / 'upstream').write_text('retained')
            before = list(output.iterdir())
            with patch.object(io, 'admitted_worker'), patch.object(handoff, 'F1', self.root):
                with self.assertRaisesRegex(ValueError, 'fresh attempt'):
                    handoff.run(self.root / 'missing-spec', '0' * 64, output)
            self.assertEqual(list(output.iterdir()), before)

    def test_admission_failure_writes_no_attempt(self):
        output = self.root / 'not-created'
        with patch.object(io, 'admitted_worker', side_effect=ValueError('not admitted')):
            with self.assertRaisesRegex(ValueError, 'not admitted'):
                handoff.run(self.root / 'missing-spec', '0' * 64, output)
        self.assertFalse(output.exists())

    def test_spec_admission_failure_retains_fresh_attempt_without_native_work(self):
        result_root = self.root / 'results/prefix-feedback'
        result_root.mkdir(parents=True)
        output = result_root / 'rejected'
        spec_path = self.root / 'bad-spec.json'
        io.fresh(spec_path, {})
        with patch.object(io, 'admitted_worker'), patch.object(handoff, 'F1', self.root):
            with self.assertRaisesRegex(ValueError, 'external handoff spec hash'):
                handoff.run(spec_path, '0' * 64, output)
        report = io.read(output / 'failed.json')
        self.assertEqual(report['completed_stages'], [])
        self.assertEqual(report['retained_stage_files'], [])
        self.assertFalse(report['producer_replay_permitted'])
        self.assertFalse((output / 'complete.json').exists())

    def test_abstention_does_not_invoke_a_stage(self):
        result = handoff.consume(None, SimpleNamespace(value={}), {}, dict(abstained=True), self.root)
        self.assertEqual(result['outcome'], 'abstained')
        self.assertFalse(result['handoff_completed'])
        self.assertFalse(result['transport_qualified'])

    def test_failure_report_retains_success_and_projection_gap_operands(self):
        stage = self.root / 'records/stage-1'
        stage.mkdir(parents=True)
        io.fresh(stage / 'terminal.json', dict(exit_known=True, exit=0, cleanup=dict(terminal=True)))
        (stage / 'stdout').write_text('raw projection gap')
        io.fresh(self.root / 'records/request-1.json', dict(mode='normalize'))
        upstream = self.root / 'records/upstream-metadata.json'
        io.fresh(upstream, dict(retained=True))
        pin = io.pin(upstream)
        handoff.failure(self.root, pin, SimpleNamespace(receipts=[pin]), ValueError('projection gap'))
        report = io.read(self.root / 'failed.json')
        self.assertFalse(report['producer_replay_permitted'])
        self.assertEqual(report['completed_stages'], [pin])
        self.assertIn(io.pin(stage / 'terminal.json'), report['retained_stage_files'])
        self.assertIn(io.pin(stage / 'stdout'), report['retained_stage_files'])
        self.assertEqual(len(report['recovery_requests']), 1)
        self.assertFalse((self.root / 'complete.json').exists())


if __name__ == '__main__':
    unittest.main()
