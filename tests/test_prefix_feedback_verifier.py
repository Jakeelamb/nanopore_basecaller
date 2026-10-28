import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify-prefix-feedback.py'
module_spec = importlib.util.spec_from_file_location('prefix_feedback_verifier', SCRIPT)
verifier = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = verifier
module_spec.loader.exec_module(verifier)
io = verifier.io


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.results = self.root / 'results/prefix-feedback'
        self.results.mkdir(parents=True)
        self.addCleanup(patch.stopall)

    def metadata(self, name, value):
        path = self.root / name
        io.fresh(path, value)
        return io.pin(path)

    def native_pin(self, state, raw=None):
        path = self.root / 'native-state.json'
        path.write_bytes(raw if raw is not None else json.dumps(
            state, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode() + b'\n')
        return io.pin(path)

    def spec(self, operation='locate'):
        operand = dict(path=str(verifier.F1 / 'results/prefix-feedback/not-executed/input.json'),
                       size=0, sha256='a' * 64)
        sources = [io.pin(path) for path in (SCRIPT, Path(io.__file__), Path(verifier.joint.__file__),
            verifier.F1 / 'tools/prefix_feedback/qualification.py', verifier.F1 / 'scripts/prefix-feedback.py')]
        sources += [io.GUARD, io.F4]
        value = dict(schema='prefix-feedback-verifier-spec/1', operation=operation,
            plan=dict(operand, sha256=verifier.PLAN_SHA), binary=dict(operand, sha256=verifier.BINARY_SHA),
            source_sha256=verifier.SOURCE, source_pins=sources, predecessor_sources=sources,
            retained={key: dict(operand) for key in verifier.RETAINED}, expected=dict(
                read_id='metadata-parent', parent_id='metadata-parent', chunk_index=0, block_index=0,
                row_begin=0, row_end=497, available_score_end=497, available_signal_end=12222,
                plan_sha256=verifier.CONFIG_SHA, previous_state_sha256='b' * 64, state_sha256='c' * 64))
        if operation == 'locate':
            value.update(work_directory=str(verifier.F1 / 'results/prefix-feedback/metadata-only-locate'),
                         execution_index=operand)
        else:
            value.update(location_result=operand, update=operand,
                         next_block=dict(block_index=1, row_begin=497, row_end=994))
        return value

    def load(self, value):
        pin = self.metadata('spec.json', value)
        return verifier.StepSpec.load(pin['path'], pin['sha256'])

    def snapshot(self):
        expected = self.spec()['expected']
        block = dict(read_id='metadata-parent', parent_id='metadata-parent', chunk_index=0,
                     block_index=0, row_begin=0, row_end=497, available_score_end=497,
                     available_signal_end=12222, orientation='signal-forward')
        session = dict(read_id='metadata-parent', plan_sha256=verifier.CONFIG_SHA, state_length=4,
                       stay_score=2.0, policy=verifier.POLICY, resource_manifest={})
        plan = dict(spec=session, blocks=[block])
        state = dict(schema='prefix-session/1', source_sha256=verifier.SOURCE, spec=session,
                     consumed=[block], last_binding=block, consumed_rows=497, next_block=1,
                     updates=[], locations=[], first_locations=[], signal=[], conditioned=[],
                     signal_pruned=False, conditioned_pruned=False, context_bound=False, symbol_bound=False)
        expected['state_sha256'] = verifier.digest(state)
        batch = dict(schema='prefix-snapshot/1', source_sha256=verifier.SOURCE,
                     read_id='metadata-parent', parent_id='metadata-parent', plan_sha256=verifier.CONFIG_SHA,
                     state_sha256=expected['state_sha256'], previous_state_sha256=expected['previous_state_sha256'],
                     initial_prior='uniform-all-CRF-states', policy=verifier.POLICY,
                     location_updates=[], locations=[], binding=dict(block, source_sha256=verifier.SOURCE,
                         plan_sha256=verifier.CONFIG_SHA, previous_state_sha256=expected['previous_state_sha256'],
                         resource_manifest={}))
        return state, batch, plan, expected

    def test_native_float_token_binds_snapshot_without_python_reserialization(self):
        state, batch, plan, expected = self.snapshot()
        state['conditioned'] = [['ACGT', 0, 0, 3096.4421839222982]]
        compact = json.dumps(state, sort_keys=True, separators=(',', ':')).encode().replace(
            b'3096.442183922298', b'3096.4421839222982')
        raw = json.dumps(state, sort_keys=True, indent=2).encode().replace(
            b'3096.442183922298', b'3096.4421839222982') + b'\n'
        pin = self.native_pin(state, raw)
        expected['state_sha256'] = batch['state_sha256'] = hashlib.sha256(compact).hexdigest()
        self.assertNotEqual(expected['state_sha256'], verifier.digest(state))
        self.assertEqual(verifier.native_state(pin), (state, expected['state_sha256']))
        self.assertEqual(verifier.check_snapshot(pin, batch, plan, expected), state)

    def test_native_string_whitespace_and_escape_tokens_preserved(self):
        state, _, _, _ = self.snapshot()
        state['spec']['read_id'] = '  parent\twith\nspaces "quoted" \\ and \\\\ '
        compact = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
        compact = compact.replace(b'parent', b'par\\u0065nt')
        raw = json.dumps(state, sort_keys=True, indent=2).encode().replace(b'parent', b'par\\u0065nt')
        pin = self.native_pin(state, b' \r\n\t' + raw + b'\n')
        self.assertEqual(verifier.native_state(pin), (state, hashlib.sha256(compact).hexdigest()))

    def test_native_state_mutated_pin_refused_before_and_after_read(self):
        state, _, _, _ = self.snapshot()
        pin = self.native_pin(state)
        path = Path(pin['path'])
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'pin differs'):
            verifier.native_state(pin)
        path.write_bytes(raw)
        check = io.check
        calls = []

        def mutate_on_recheck(value):
            calls.append(value)
            if len(calls) == 2:
                path.write_bytes(raw + b' ')
            return check(value)

        with patch.object(io, 'check', side_effect=mutate_on_recheck):
            with self.assertRaisesRegex(ValueError, 'pin differs'):
                verifier.native_state(pin)
        self.assertEqual(len(calls), 2)

    def test_native_duplicate_nonfinite_and_invalid_json_refused(self):
        state, _, _, _ = self.snapshot()
        raw = json.dumps(state, sort_keys=True).encode()
        for invalid, message in (
            (raw.replace(b'"conditioned": []', b'"conditioned": [], "conditioned": []'), 'duplicate'),
            (raw.replace(b'"conditioned": []', b'"conditioned": [NaN]'), 'nonfinite'),
            (raw.replace(b'"conditioned": []', b'"conditioned": [Infinity]'), 'nonfinite'),
            (raw.replace(b'"conditioned": []', b'"conditioned": [-Infinity]'), 'nonfinite'),
            (raw.replace(b'"conditioned": []', b'"conditioned": [1e999]'), 'nonfinite'),
            (raw + b' true', 'Extra data'),
            (raw[:-1] + b',}', 'property name'),
        ):
            with self.subTest(message=message):
                pin = self.native_pin(state, invalid)
                with self.assertRaisesRegex(ValueError, message):
                    verifier.native_state(pin)
        pin = self.native_pin(state, raw.replace(b'metadata-parent', b'\xff'))
        with self.assertRaises(UnicodeDecodeError):
            verifier.native_state(pin)

    def test_native_layout_order_size_and_depth_refused(self):
        state, _, _, _ = self.snapshot()
        raw = json.dumps(state, sort_keys=True).encode()
        for invalid, message in (
            (b'{"z":0,' + raw[1:], 'key order'),
            (raw.replace(b'"conditioned": []', b'"unexpected": []'), 'key order|fields'),
            (raw.replace(b'"conditioned": []', b'"conditioned": {}'), 'layout'),
            (b'[' * 65 + b'0' + b']' * 65, 'nesting bound'),
        ):
            with self.subTest(message=message):
                pin = self.native_pin(state, invalid)
                with self.assertRaisesRegex(ValueError, message):
                    verifier.native_state(pin)
        pin = self.native_pin(state)
        with patch.object(verifier, 'NATIVE_STATE_MAX_BYTES', pin['size'] - 1):
            with self.assertRaisesRegex(ValueError, 'size bound'):
                verifier.native_state(pin)

    def test_independent_current_and_previous_ids_reject_matching_snapshot(self):
        for key in ('state_sha256', 'previous_state_sha256'):
            state, batch, plan, expected = self.snapshot()
            expected[key] = 'd' * 64
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'snapshot independent binding'):
                verifier.check_snapshot(self.native_pin(state), batch, plan, expected)

    def test_resealed_changed_state_rejects_snapshot_identity(self):
        state, batch, plan, expected = self.snapshot()
        state['conditioned'] = [['ACGT', 0, 0, 1.0]]
        with self.assertRaisesRegex(ValueError, 'snapshot independent binding'):
            verifier.check_snapshot(self.native_pin(state), batch, plan, expected)

    def test_predecessor_native_identity_rejects_resealed_changed_state(self):
        prior, _, plan, expected = self.snapshot()
        prior['signal'] = [['ACGT', 0, 0, 3096.4421839222982]]
        native = json.dumps(prior, sort_keys=True).encode().replace(
            b'3096.442183922298', b'3096.4421839222982')
        prior_pin = self.native_pin(prior, native)
        prior_path = self.root / 'prior-state.json'
        prior_path.write_bytes(Path(prior_pin['path']).read_bytes())
        prior_pin = io.pin(prior_path)
        current = dict(prior, next_block=2, consumed_rows=994, signal=[],
                       consumed=[*prior['consumed'], dict(plan['blocks'][0], block_index=1,
                           row_begin=497, row_end=994, available_score_end=994)], updates=[{'update': 1}])
        current['last_binding'] = current['consumed'][1]
        plan['blocks'] = current['consumed']
        expected.update(block_index=1, row_begin=497, row_end=994, available_score_end=994,
                        previous_state_sha256=verifier.native_state(prior_pin)[1],
                        state_sha256=verifier.digest(current))
        batch = dict(schema='prefix-snapshot/1', source_sha256=verifier.SOURCE,
                     **{key: expected[key] for key in ('read_id', 'parent_id', 'plan_sha256',
                                                     'state_sha256', 'previous_state_sha256')},
                     policy=verifier.POLICY, initial_prior='uniform-all-CRF-states',
                     location_updates=current['updates'], binding=dict(current['last_binding'],
                         source_sha256=verifier.SOURCE, plan_sha256=verifier.CONFIG_SHA,
                         previous_state_sha256=expected['previous_state_sha256'], resource_manifest={}))
        request = self.metadata('request.json', dict(state=prior_pin, update=current['updates'][0]))
        value = dict(expected=expected, binary={}, predecessor_sources=[], retained=dict(state=self.native_pin(current),
            snapshot=self.metadata('snapshot.json', batch), complete=self.metadata('complete.json', dict(request=request))))
        with patch.object(verifier, 'check_producer', side_effect=ValueError('producer check reached')) as producer:
            with self.assertRaisesRegex(ValueError, 'producer check reached'):
                verifier.retained_inputs(value, plan)
        producer.assert_called_once()
        prior['signal'] = [['ACGT', 0, 0, 1.0]]
        prior_path.write_text(json.dumps(prior, sort_keys=True))
        prior_pin = io.pin(prior_path)
        request = self.metadata('changed-request.json', dict(state=prior_pin, update=current['updates'][0]))
        value['retained']['complete'] = self.metadata('changed-complete.json', dict(request=request))
        with patch.object(verifier, 'check_producer') as producer:
            with self.assertRaisesRegex(ValueError, 'predecessor state/update differs'):
                verifier.retained_inputs(value, plan)
        producer.assert_not_called()

    def test_closed_spec_accepts_metadata_shape_without_native_acceptance(self):
        self.assertEqual(self.load(self.spec()).value['operation'], 'locate')

    def test_unknown_truth_field_refused(self):
        value = self.spec()
        value['truth'] = 'forbidden'
        with self.assertRaisesRegex(ValueError, 'step spec fields'):
            self.load(value)

    def test_external_spec_hash_refused(self):
        pin = self.metadata('spec.json', self.spec())
        with self.assertRaisesRegex(ValueError, 'external spec hash'):
            verifier.StepSpec.load(pin['path'], '0' * 64)

    def test_source_plan_and_binary_identity_mismatch_refused(self):
        for key in ('source_sha256', 'plan', 'binary'):
            with self.subTest(key=key), tempfile.TemporaryDirectory(dir=self.root) as directory:
                value = self.spec()
                if key == 'source_sha256':
                    value[key] = '0' * 64
                else:
                    value[key]['sha256'] = '0' * 64
                path = Path(directory) / 'spec.json'
                io.fresh(path, value)
                with self.assertRaisesRegex(ValueError, 'frozen source/plan/binary'):
                    verifier.StepSpec.load(path, io.pin(path)['sha256'])

    def test_advance0_wrong_next_block_and_endpoints_refused(self):
        for block in (dict(block_index=0, row_begin=0, row_end=497),
                      dict(block_index=2, row_begin=994, row_end=1491),
                      dict(block_index=1, row_begin=498, row_end=994),
                      dict(block_index=True, row_begin=497, row_end=994)):
            with self.subTest(block=block), tempfile.TemporaryDirectory(dir=self.root) as directory:
                value = self.spec('advance-next')
                value['next_block'] = block
                path = Path(directory) / 'spec.json'
                io.fresh(path, value)
                with self.assertRaisesRegex(ValueError, 'advance0 or wrong next block'):
                    verifier.StepSpec.load(path, io.pin(path)['sha256'])

    def test_retained_wrong_endpoint_refused(self):
        value = self.spec()
        value['expected']['row_end'] += 1
        with self.assertRaisesRegex(ValueError, 'retained block endpoints'):
            self.load(value)

    def test_snapshot_foreign_parent_stale_state_and_endpoint_refused_before_work(self):
        for key, replacement in (('parent_id', 'foreign'), ('state_sha256', 'd' * 64),
                                  ('previous_state_sha256', 'd' * 64), ('source_sha256', 'd' * 64)):
            state, batch, plan, expected = self.snapshot()
            batch[key] = replacement
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'snapshot independent binding'):
                verifier.check_snapshot(self.native_pin(state), batch, plan, expected)
        state, batch, plan, expected = self.snapshot()
        batch['binding']['row_end'] += 1
        with self.assertRaisesRegex(ValueError, 'snapshot block binding'):
            verifier.check_snapshot(self.native_pin(state), batch, plan, expected)
        self.assertEqual(list(self.results.iterdir()), [])

    def test_state_row_ownership_refused(self):
        state, batch, plan, expected = self.snapshot()
        state['consumed_rows'] += 1
        with self.assertRaisesRegex(ValueError, 'state ownership'):
            verifier.check_snapshot(self.native_pin(state), batch, plan, expected)

    def test_changed_plan_pin_refused(self):
        pin = self.metadata('plan.json', {})
        Path(pin['path']).write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'consumed pin differs'):
            verifier.check_plan(dict(plan=pin))

    def test_unknown_truth_field_in_actual_config_refused(self):
        config = {key: None for key in ('schema', 'role', 'hypothesis', 'endpoint', 'selection', 'manifest',
            'policy', 'releases', 'causality', 'reference', 'reference_index', 'reference_fai_path',
            'mapper_path', 'index_provenance', 'producer_sources', 'samtools', 'execution',
            'hg005_selection', 'truth_input', 'promotion')}
        config['future_truth'] = 'forbidden'
        config_pin = self.metadata('config.json', config)
        plan = {key: None for key in ('schema', 'config', 'spec', 'blocks', 'selected', 'exclusions',
            'mapper', 'samtools', 'reference', 'reference_index', 'reference_fai', 'index_provenance',
            'producer_sources', 'truth_opened', 'allow_refill', 'available_native_passthrough')}
        plan['config'] = config_pin
        with self.assertRaisesRegex(ValueError, 'development config fields'):
            verifier.check_plan(dict(plan=self.metadata('plan.json', plan)))

    def locate_inputs(self):
        patch.object(verifier, 'F1', self.root).start()
        patch.object(io, 'ROOT', self.root).start()
        binary = dict(path=str(self.root / 'never-executed'), size=0, sha256='0' * 64)
        index = dict(schema='prefix-command-index/1', source_pins=[io.F4, binary], commands=[])
        value = dict(operation='locate', binary=binary, work_directory=str(self.results / 'work'),
                     execution_index=self.metadata('index.json', index))
        plan = dict(mapper=binary, samtools=binary, reference_index=binary, producer_sources=[],
                    spec=dict(policy=verifier.POLICY, resource_manifest={}))
        batch = dict(abstained=False, mapper_request_eligible=True, provisional_prefix='ACGT',
                     state_sha256='a' * 64, binding=dict(row_end=497, available_signal_end=12222))
        patch.object(verifier, 'COMMON', {'operation', 'binary'}).start()
        return value, batch, plan, index

    def test_pending_proposal_and_augmented_index_reuse_without_native_call(self):
        value, batch, plan, index = self.locate_inputs()
        with patch.object(verifier.joint, 'Stages', side_effect=AssertionError('native forbidden')):
            first = verifier.locate(value, batch, plan)
            self.assertEqual(first['status'], 'awaiting-fresh-Root-grant')
            self.assertFalse(first['native_command_executed'])
            self.assertFalse(first['authorization'])
            proposal = verifier.consumed(first['proposal'])
            self.assertEqual(proposal['role'], 'prefix-location')
            self.assertEqual(proposal['request']['profile'], 'mapping')
            self.assertFalse(proposal['authorization'])
            query = self.results / 'work/location/query.fasta'
            before = io.pin(query)
            unrelated = dict(path=str(self.root / 'unaccepted'), size=0, sha256='d' * 64)
            index['commands'].append(dict(proposal=unrelated, complete=unrelated))
            value['execution_index'] = self.metadata('index-augmented.json', index)
            second = verifier.locate(value, batch, plan)
        self.assertEqual(first['proposal'], second['proposal'])
        self.assertEqual(before, io.pin(query))
        self.assertFalse((self.results / 'work/location/mapper').exists())

    def test_unknown_existing_mapper_output_is_held(self):
        value, batch, plan, _ = self.locate_inputs()
        first = verifier.locate(value, batch, plan)
        mapper = self.results / 'work/location/mapper'
        mapper.mkdir()
        (mapper / 'stdout').write_text('retained unknown exit')
        with self.assertRaisesRegex(ValueError, 'no accepted receipt'):
            verifier.locate(value, batch, plan)
        self.assertEqual((mapper / 'stdout').read_text(), 'retained unknown exit')
        self.assertEqual(io.pin(Path(first['proposal']['path'])), first['proposal'])

    def test_no_eligible_prefix_is_an_observation_without_query(self):
        result = verifier.locate({}, dict(abstained=True), {})
        self.assertEqual(result['status'], 'observed-no-eligible-prefix')
        self.assertEqual(result['usable_locations'], 0)
        self.assertEqual(list(self.results.iterdir()), [])

    def test_existing_empty_or_partial_attempt_refused(self):
        patch.object(verifier, 'F1', self.root).start()
        for name in ('empty', 'partial'):
            output = self.results / name
            output.mkdir()
            if name == 'partial':
                (output / 'raw').write_text('preserved')
            before = verifier.evidence(output)
            with patch.object(io, 'admitted_worker'), self.assertRaisesRegex(ValueError, 'fresh attempt'):
                verifier.run(self.root / 'absent', '0' * 64, output)
            self.assertEqual(verifier.evidence(output), before)

    def test_no_admission_produces_no_attempt(self):
        output = self.results / 'absent'
        with patch.object(io, 'admitted_worker', side_effect=ValueError('no admission')):
            with self.assertRaisesRegex(ValueError, 'no admission'):
                verifier.run(self.root / 'spec', '0' * 64, output)
        self.assertFalse(output.exists())

    def test_failed_spec_has_explicit_last_result_and_no_native_call(self):
        patch.object(verifier, 'F1', self.root).start()
        pin = self.metadata('invalid.json', {})
        output = self.results / 'failed'
        with patch.object(io, 'admitted_worker'), patch.object(verifier.joint, 'Stages') as stages:
            with self.assertRaisesRegex(ValueError, 'external spec hash'):
                verifier.run(pin['path'], '0' * 64, output)
        stages.assert_not_called()
        result = io.read(output / 'result.json')
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['producer_replay_permitted'])
        self.assertEqual(result['completed_stages'], [])

    def test_failure_before_query_or_stage(self):
        value = self.spec()
        patch.object(verifier, 'F1', self.root).start()
        spec = verifier.StepSpec(value, dict(path=str(self.root / 'spec'), size=0, sha256='a' * 64))
        for label in ('foreign parent', 'stale snapshot', 'wrong endpoint'):
            output = self.results / label.replace(' ', '-')
            with patch.object(io, 'admitted_worker'), patch.object(verifier.StepSpec, 'load', return_value=spec), \
                 patch.object(io, 'check'), patch.object(verifier, 'check_plan', return_value={}), \
                 patch.object(verifier, 'retained_inputs', side_effect=ValueError(label)), \
                 patch.object(verifier, 'locate') as locate, patch.object(verifier.joint, 'Stages') as stages:
                with self.assertRaisesRegex(ValueError, label):
                    verifier.run(self.root / 'spec', 'a' * 64, output)
            locate.assert_not_called()
            stages.assert_not_called()
            self.assertEqual(io.read(output / 'result.json')['status'], 'failed')

    def test_wrong_update_state_refused(self):
        _, batch, plan, _ = self.snapshot()
        batch['provisional_prefix'] = 'ACGT'
        update = {key: None for key in ('schema', 'source_sha256', 'plan_sha256', 'read_id', 'state_sha256',
            'query_sequence', 'query_sha256', 'query_length', 'query', 'available_score_end',
            'available_signal_end', 'orientation', 'producer_receipt', 'paf', 'locations',
            'mapper', 'reference_index', 'resource_manifest')}
        update.update(schema='prefix-location/1', source_sha256=verifier.SOURCE, read_id=batch['read_id'],
                      plan_sha256=batch['plan_sha256'], state_sha256='d' * 64)
        with self.assertRaisesRegex(ValueError, 'location update binding'):
            verifier.check_update(update, batch, plan)


if __name__ == '__main__':
    unittest.main()
