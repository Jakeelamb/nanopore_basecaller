#!/usr/bin/env python3
"""One admitted block0 consumer of a retained genuine native advance."""
import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

F1 = Path('/home/jake/Projects/nanopore_basecaller-next-prefix-loop')
F2 = Path('/home/jake/Projects/nanopore_basecaller-next-context-policy')
F3 = Path('/home/jake/Projects/nanopore_basecaller-next-indel-decoder')
sys.path.insert(0, str(F1 / 'tools/prefix_feedback'))
import bounded_cli as io
import joint

POLICY = dict(maximum_context_weight=0.5, maximum_neural_deficit=0.5,
              minimum_objective_margin=0.5, parameter_status='predeclared_unfitted',
              quality_status='uncalibrated')
SPEC_FIELDS = {'schema', 'advance_spec', 'advance_complete', 'expected_producer',
               'f1', 'f2', 'f3', 'f2_cwd', 'f3_cwd', 'source_pins',
               'f3_source_files', 'source_sha256', 'expected', 'policy'}
EXPECTED_FIELDS = {'read_id', 'parent_index', 'chunk_index', 'block_index',
                   'row_begin', 'row_end', 'previous_state_sha256', 'plan_sha256'}


def exact(value, fields, label):
    io.require(isinstance(value, dict) and set(value) == set(fields), label + ' fields differ')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def consumed(pin):
    exact(pin, ('path', 'size', 'sha256'), 'pin')
    io.check(pin)
    value = io.read(pin['path'])
    io.check(pin)
    return value


@dataclass(frozen=True)
class HandoffSpec:
    value: dict
    pin: dict

    @classmethod
    def load(cls, path, expected_sha256):
        pin = io.pin(path)
        io.require(pin['sha256'] == expected_sha256, 'external handoff spec hash differs')
        value = consumed(pin)
        exact(value, SPEC_FIELDS, 'handoff spec')
        io.require(value['schema'] == 'genuine-prefix-handoff-spec/1', 'handoff schema differs')
        exact(value['expected'], EXPECTED_FIELDS, 'expected binding')
        expected = value['expected']
        io.require(value['policy'] == POLICY, 'predeclared policy differs')
        io.require(value['f2_cwd'] == str(F2) and value['f3_cwd'] == str(F3), 'sibling cwd differs')
        io.require(expected['parent_index'] == 0 and expected['chunk_index'] == 0
                   and expected['block_index'] == 0 and expected['row_begin'] == 0
                   and type(expected['row_end']) is int and 1 <= expected['row_end'] <= 512,
                   'only the frozen first block is supported')
        io.require(isinstance(expected['read_id'], str) and expected['read_id']
                   and 'HG005' not in expected['read_id'].upper(), 'development parent differs')
        for key in ('previous_state_sha256', 'plan_sha256'):
            io.require(isinstance(expected[key], str) and len(expected[key]) == 64
                       and all(c in '0123456789abcdef' for c in expected[key]), 'expected hash shape differs')
        for key, root in (('f1', F1), ('f2', F2), ('f3', F3)):
            item = value[key]
            exact(item, ('path', 'size', 'sha256'), 'binary pin')
            path = Path(item['path'])
            io.require(path.is_absolute() and path == path.resolve()
                       and path.is_relative_to(root / 'results'), 'frozen binary root differs')
        sources = value['source_pins']
        io.require(isinstance(sources, list) and sources
                   and len({item['path'] for item in sources}) == len(sources), 'source closure differs')
        for item in sources + value['f3_source_files']:
            exact(item, ('path', 'size', 'sha256'), 'source pin')
        for path in (Path(__file__).resolve(), Path(io.__file__).resolve(), Path(joint.__file__).resolve(),
                     F1 / 'tools/prefix_feedback/qualification.py'):
            io.require(io.pin(path) in sources, 'companion/recorder source absent')
        io.require(io.GUARD in sources and io.F4 in sources and value['f3_source_files']
                   and all(item in sources for item in value['f3_source_files']), 'native recorder closure absent')
        return cls(value, pin)

    def check_dependencies(self):
        for item in [self.value[key] for key in ('f1', 'f2', 'f3')] + self.value['source_pins']:
            io.check(item)


def retained_advance(spec):
    value = spec.value
    advance_spec = consumed(value['advance_spec'])
    exact(advance_spec, ('binary', 'plan', 'source_pins', 'source_sha256'), 'advance spec')
    io.require(advance_spec['binary'] == value['f1']
               and advance_spec['source_sha256'] == value['source_sha256'], 'advance binary/source differs')
    for item in advance_spec['source_pins']:
        io.check(item)
    plan = consumed(advance_spec['plan'])
    exact(plan, ('schema', 'config', 'spec', 'blocks', 'selected', 'exclusions', 'mapper',
                 'samtools', 'reference', 'reference_index', 'reference_fai', 'index_provenance',
                 'producer_sources', 'truth_opened', 'allow_refill', 'available_native_passthrough'), 'plan')
    io.require(plan['schema'] == 'prefix-pilot-plan/1' and plan['truth_opened'] is False
               and plan['allow_refill'] is False and plan['available_native_passthrough'] is None,
               'frozen development plan differs')
    expected = value['expected']
    io.require(plan['spec']['state_length'] == 4
               and plan['spec']['read_id'] == plan['selected']['parent'] == expected['read_id']
               and plan['spec']['plan_sha256'] == expected['plan_sha256'], 'genuine k4 parent/plan differs')
    block = plan['blocks'][0]
    for key in ('read_id', 'chunk_index', 'block_index', 'row_begin', 'row_end'):
        io.require(block[key] == expected[key], 'frozen block endpoint differs')
    io.require(block['parent_id'] == expected['read_id'] and block['chunk_row_begin'] == 0
               and block['chunk_row_end'] == block['available_score_end'] == expected['row_end']
               and block['orientation'] == 'signal-forward', 'released first-block ownership differs')
    complete = consumed(value['advance_complete'])
    exact(complete, ('schema', 'complete', 'plan', 'binary', 'producer', 'snapshot', 'state',
                     'source_sha256', 'selected_parent', 'genuine_scores', 'whole_chunk_lookahead',
                     'scientific_qualified', 'mapper_updates', 'abstained'), 'advance completion')
    root = Path(value['advance_complete']['path']).parent
    io.require(root == root.resolve() and root.is_relative_to(F1 / 'results/prefix-feedback')
               and complete['schema'] == 'genuine-prefix-first-advance/1' and complete['complete'] is True
               and complete['plan'] == advance_spec['plan'] and complete['binary'] == value['f1']
               and complete['source_sha256'] == value['source_sha256']
               and complete['selected_parent'] == expected['read_id']
               and complete['genuine_scores'] is True and complete['whole_chunk_lookahead'] is True
               and complete['scientific_qualified'] is False and complete['mapper_updates'] == 0
               and complete['producer'] == value['expected_producer'] == io.pin(root / 'stage-0/receipt.json'),
               'retained advance identity differs')
    state_pin = io.pin(root / 'advance/state.json')
    snapshot_pin = io.pin(root / 'advance/snapshot.json')
    native_complete_pin = io.pin(root / 'advance/complete.json')
    io.require(complete['state'] == state_pin and complete['snapshot'] == snapshot_pin,
               'advance output path differs')
    native_complete = consumed(native_complete_pin)
    exact(native_complete, ('schema', 'complete', 'request', 'source', 'source_sha256'), 'native completion')
    witness = native_complete['source']
    io.require(native_complete['schema'] == 'prefix-complete/1' and native_complete['complete'] is True
               and witness['root'] == str(F1) and digest(witness) == value['source_sha256']
               and native_complete['source_sha256'] == value['source_sha256'], 'compiled source witness differs')
    for item in witness['sources']:
        io.require(any(pin['path'] == item['path'] and pin['sha256'] == item['sha256']
                       for pin in advance_spec['source_pins']), 'compiled closure absent from original producer')
    request_pin = native_complete['request']
    io.require(request_pin == io.pin(root / 'request-0.json'), 'advance request path differs')
    request = consumed(request_pin)
    io.require(request == dict(schema='prefix-advance/1', source_sha256=value['source_sha256'],
        spec=plan['spec'], state=None, update=None, block=block, expected_previous_state_sha256=None),
        'actual advance request differs')
    receipt = consumed(value['expected_producer'])
    exact(receipt, ('schema', 'complete', 'binary', 'command', 'terminal', 'outputs',
                    'stdout', 'stderr', 'time'), 'producer receipt')
    io.require(receipt['schema'] == 'prefix-stage-receipt/1' and receipt['complete'] is True
               and receipt['binary'] == value['f1']
               and receipt['outputs'] == [state_pin, snapshot_pin, native_complete_pin], 'producer output census differs')
    command = consumed(receipt['command'])
    io.require(receipt['command'] == io.pin(root / 'stage-0/command.json')
               and command == dict(argv=[value['f1']['path'], 'advance', '--request', request_pin['path'],
                   '--request-sha256', request_pin['sha256'], '--output', str(root / 'advance')],
                   cwd=str(F1), env=dict(io.ENVIRONMENT, TMPDIR=str(root / 'tmp')),
                   input_pins=[request_pin], source_pins=advance_spec['source_pins']),
               'producer exact command/cwd/env/source/input differs')
    terminal = consumed(receipt['terminal'])
    io.require(receipt['terminal'] == io.pin(root / 'stage-0/terminal.json')
               and terminal['command'] == receipt['command'] and terminal['exit_known'] is True
               and terminal['exit'] == 0 and terminal['failure'] is None
               and terminal['cleanup']['terminal'] is True and terminal['start']
               and terminal['start'] <= terminal['end'], 'producer exit/cleanup/clock differs')
    for field, name in (('stdout', 'stdout'), ('stderr', 'stderr'), ('time', 'time.txt')):
        io.require(receipt[field] == io.pin(root / 'stage-0' / name), 'producer raw pin differs')
    state = consumed(state_pin)
    snapshot = consumed(snapshot_pin)
    io.require(state['schema'] == 'prefix-session/1' and state['spec'] == plan['spec']
               and state['source_sha256'] == value['source_sha256'] and state['consumed'] == [block]
               and state['last_binding'] == block and state['consumed_rows'] == expected['row_end']
               and state['next_block'] == 1 and state['updates'] == state['locations'] == state['first_locations'] == [],
               'retained state ownership/context differs')
    check_snapshot(snapshot, state, block, value)
    io.require(snapshot['abstained'] == complete['abstained'], 'advance abstention differs')
    return complete, snapshot


def check_snapshot(snapshot, state, block, value):
    expected = value['expected']
    io.require(snapshot['schema'] == 'prefix-snapshot/1' and snapshot['read_id'] == expected['read_id']
               and snapshot['parent_id'] == expected['read_id'] and snapshot['plan_sha256'] == expected['plan_sha256']
               and snapshot['source_sha256'] == value['source_sha256']
               and snapshot['previous_state_sha256'] == expected['previous_state_sha256']
               and snapshot['state_sha256'] == digest(state) and snapshot['initial_prior'] == 'uniform-all-CRF-states'
               and snapshot['locations'] == snapshot['location_updates'] == [], 'snapshot independent binding differs')
    for key in ('read_id', 'parent_id', 'chunk_index', 'block_index', 'row_begin', 'row_end',
                'chunk_row_begin', 'chunk_row_end', 'available_score_end', 'tensor', 'release_receipt'):
        io.require(snapshot['binding'][key] == block[key], 'snapshot block binding differs')


def nomination(batch_pin, binding, descriptor):
    return dict(schema='indel-prefix-nomination-request/1', mode='consumed-prefix-unscored-v1',
        batch_pin=batch_pin, expected_batch_sha256=batch_pin['sha256'], expected_binding=copy.deepcopy(binding),
        scoring_descriptor=descriptor, expected_scoring_descriptor=descriptor)


def binding_controls(batch, descriptor, output):
    result = []
    for label, field, replacement in (('foreign-read', 'read_id', batch['binding']['read_id'] + '-foreign'),
                                      ('stale-previous-state', 'previous_state_sha256',
                                       '0' * 64 if batch['binding']['previous_state_sha256'] != '0' * 64 else '1' * 64)):
        bad = copy.deepcopy(batch)
        bad['binding'][field] = replacement
        path = output / (label + '-batch.json')
        io.fresh(path, bad)
        result.append((label, nomination(io.pin(path), batch['binding'], descriptor)))
    return result


def check_merge(original, final):
    io.require(final['binding'] == original['binding'] and final['native'] == original['native']
               and final['locations'] == original['locations']
               and final['reference_free_candidate_id'] == original['reference_free_candidate_id'], 'merge changed H/binding')
    by_id = {item['id']: item for item in final['candidates']}
    io.require(len(by_id) == len(final['candidates'])
               and all(by_id.get(item['id']) == item for item in original['candidates'])
               and final['union_nn_candidate_id'] in by_id, 'merge changed original candidate objects/U role')


def consume(stages, spec, advance, snapshot, output):
    value = spec.value
    if snapshot['abstained']:
        return dict(outcome='abstained', handoff_completed=False, transport_qualified=False)
    free = next(item for item in snapshot['candidates'] if item['id'] == snapshot['reference_free_candidate_id'])
    emitted = output / 'emitted'
    request = dict(schema='prefix-emit-free-input/1', source_sha256=value['source_sha256'],
        state=advance['state'], snapshot=advance['snapshot'],
        advance_complete=io.pin(Path(advance['state']['path']).parent / 'complete.json'),
        producer=value['expected_producer'], expected_producer=value['expected_producer'], parent_index=0)
    excluded = len(free['sequence']) > 512
    names = ('arm-excluded.json', 'complete.json') if excluded else (
        'tensor.dgs', 'panels.json', 'identity.json', 'emission.json', 'complete.json')
    producer, _ = stages.f1(value['f1'], 'emit-free-input', request, emitted, names)
    if excluded:
        return dict(outcome='emission-cap-excluded', handoff_completed=False, transport_qualified=False,
                    exclusion=io.pin(emitted / 'arm-excluded.json'))
    emission = io.read(emitted / 'emission.json')
    binding = emission['binding']
    expected = value['expected']
    for key in ('read_id', 'parent_index', 'chunk_index', 'block_index', 'previous_state_sha256', 'plan_sha256'):
        io.require(binding[key] == expected[key], 'emission independent binding differs')
    io.require(binding['availability']['row_begin'] == 0
               and binding['availability']['row_end'] == binding['availability']['available_row_end'] == expected['row_end'],
               'emission endpoint differs')
    normalize = dict(schema='prefix-normalize/1', source_sha256=value['source_sha256'],
        emission=io.pin(emitted / 'emission.json'), producer=producer, expected_producer=producer,
        expected_binding=binding)
    directory = output / 'normalized'
    stages.f1(value['f1'], 'normalize', normalize, directory,
              ('batch.json', 'descriptor.json', 'report.json', 'complete.json'))
    original_pin = io.pin(directory / 'batch.json')
    original = io.read(original_pin['path'])
    descriptor = io.read(directory / 'descriptor.json')
    io.require(original['binding'] == binding and original['locations'] == [], 'block0 normalized context differs')

    def nominate(request, label, accepted=True):
        path = output / (label + '-request.json')
        sidecar = output / (label + '-sidecar.json')
        io.fresh(path, request)
        result = stages.run(value['f3'], [value['f3']['path'], 'nominate-prefix', str(path),
            io.pin(path)['sha256'], str(sidecar)], value['f3_cwd'], [io.pin(path), request['batch_pin']],
            [sidecar] if accepted else [], 0 if accepted else 1)
        if not accepted:
            io.require(not sidecar.exists() and 'prefix independently expected binding differs'
                       in Path(result[1]['stderr']['path']).read_text(), 'F3 binding rejection reason differs')
        return result, sidecar

    (sidecar_producer, _), sidecar = nominate(nomination(original_pin, binding, descriptor), 'nominate')
    merged = output / 'merged'
    merge = dict(normalize, schema='prefix-merge-indels/1', batch=original_pin,
        sidecar=io.pin(sidecar), sidecar_producer=sidecar_producer, expected_sidecar_producer=sidecar_producer,
        sidecar_binary=value['f3'], sidecar_source_files=value['f3_source_files'])
    stages.f1(value['f1'], 'merge-indels', merge, merged,
              ('batch.json', 'descriptor.json', 'report.json', 'complete.json'))
    final_pin = io.pin(merged / 'batch.json')
    final = io.read(final_pin['path'])
    check_merge(original, final)
    h = next(item for item in final['candidates'] if item['id'] == final['reference_free_candidate_id'])
    u = next(item for item in final['candidates'] if item['id'] == final['union_nn_candidate_id'])
    io.require(h['sequence'] == final['native']['sequence'] == free['sequence'], 'available H identity differs')
    decisions = {}
    for mode in ('fixed', 'adaptive', 'prior-none', 'disabled'):
        policy = dict(value['policy'], mode=mode)
        if mode != 'fixed':
            policy['minimum_objective_margin'] = 0.0
        path = output / ('decision-' + mode + '-request.json')
        io.fresh(path, dict(schema='feedback-next/1', batch_pin=final_pin, expected_binding=binding,
                           expected_batch_sha256=final_pin['sha256'], policy=policy))
        _, record = stages.run(value['f2'], [value['f2']['path'], 'decide', str(path), io.pin(path)['sha256']],
                               value['f2_cwd'], [io.pin(path), final_pin])
        decision = io.read(record['stdout']['path'])
        selected = u if mode == 'prior-none' else h
        io.require(decision['binding'] == binding and decision['batch_sha256'] == final_pin['sha256']
                   and decision['selected_candidate_id'] == selected['id'] and decision['sequence'] == selected['sequence'],
                   'F2 bound decision differs')
        if mode == 'disabled':
            io.require(decision['quality'] == final['native']['quality'], 'disabled available H Q differs')
        decisions[mode] = record['stdout']
    controls = []
    for label, request in binding_controls(original, descriptor, output):
        nominate(request, label, False)
        controls.append(label)
    report = io.read(merged / 'report.json')
    proposals = io.read(sidecar)
    return dict(outcome='handoff-observed', handoff_completed=True,
        transport_qualified=proposals['status'] == 'ready' and report['new_arm_status'] == 'included',
        original_batch=original_pin, merged_batch=final_pin, merge_report=io.pin(merged / 'report.json'),
        sidecar=io.pin(sidecar), decisions=decisions, controls=controls,
        H=h['id'], U=u['id'], H_equals_U=h['id'] == u['id'],
        original_count=len(original['candidates']), final_count=len(final['candidates']),
        additions=len(final['candidates']) - len(original['candidates']))


def failure(output, spec_pin, stages, error):
    raw = []
    for directory in sorted((output / 'records').glob('stage-*')):
        raw.extend(io.pin(path) for path in sorted(directory.iterdir()) if path.is_file())
    requests = [io.pin(path) for path in sorted(output.rglob('*request*.json'))]
    payloads = [io.pin(path) for path in sorted(output.glob('*.json'))]
    for name in ('emitted', 'normalized', 'merged'):
        payloads.extend(io.pin(path) for path in sorted((output / name).glob('*')) if path.is_file())
    io.fresh(output / 'failed.json', dict(schema='genuine-prefix-handoff-failure/1', error=repr(error),
        spec=spec_pin, completed_stages=[] if stages is None else stages.receipts, retained_stage_files=raw,
        recovery_requests=requests, retained_payload_files=payloads, producer_replay_permitted=False,
        recovery='Hold unknown exits and projection gaps. Authenticate these retained fixed-stage operands before any separately authorized recovery.'))


def run(spec_path, expected_sha256, output):
    io.admitted_worker()
    output = Path(output)
    io.require(output.is_absolute() and output == output.resolve()
               and output.is_relative_to(F1 / 'results/prefix-feedback'), 'handoff output outside canonical F1 results')
    io.require(not output.exists(), 'fresh attempt required; no overwrite or partial-attempt reuse')
    spec_pin = io.pin(spec_path)
    stages = None
    output.mkdir()
    try:
        spec = HandoffSpec.load(spec_path, expected_sha256)
        spec.check_dependencies()
        advance, snapshot = retained_advance(spec)
        stages = joint.Stages(output / 'records', spec.value['source_pins'])
        facts = consume(stages, spec, advance, snapshot, output)
        io.require(len(stages.receipts) == (10 if facts['handoff_completed'] else
                   1 if facts['outcome'] == 'emission-cap-excluded' else 0), 'fixed stage census differs')
        io.check(spec.pin)
        io.fresh(output / 'complete.json', dict(schema='genuine-prefix-handoff/1', complete=True,
            spec=spec.pin, advance_complete=spec.value['advance_complete'], producer=spec.value['expected_producer'],
            stages=stages.receipts, facts=facts, genuine_scores=True, state_length=4,
            consumed_rows=spec.value['expected']['row_end'], empty_context=True, whole_chunk_lookahead=True,
            scientific_qualified=False, native_stock_Q=False, whole_read_qualified=False,
            performance_qualified=False, promotion_qualified=False, producer_replay_permitted=False))
    except BaseException as error:
        failure(output, spec_pin, stages, error)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.spec, args.spec_sha256, args.output)


if __name__ == '__main__':
    main()
