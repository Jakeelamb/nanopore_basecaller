#!/usr/bin/env python3
"""Two fixed verification steps after the sealed genuine block0 advance."""
import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

F1 = Path('/home/jake/Projects/nanopore_basecaller-next-prefix-loop')
PREFIX_SCRIPT = F1 / 'scripts/prefix-feedback.py'
sys.path.insert(0, str(F1 / 'tools/prefix_feedback'))
import bounded_cli as io
import joint

SOURCE = 'b1106cb351a8d9acb20284562a08c6e41acbe900a341cbac85ce5d02cdcb86e4'
BINARY_SHA = '84f89ca38c361a7534dd0222c7fb8b25a1c1581fefeeadd0969604426f23aae5'
PLAN_SHA = '5ee39340d675d8313e385fded9c4036d89a6c5649b72fe143bb22691b2cc08ee'
CONFIG_SHA = '96997e360a66f6c321977f256023f8d17df122357f50c4a91ca5f2f88939598d'
POLICY = dict(beam_width=128, context_weight=0.5, maximum_locations=32,
              maximum_symbols=1024, minimum_symbols=1)
COMMON = {'schema', 'operation', 'plan', 'binary', 'source_sha256', 'source_pins',
          'retained', 'predecessor_sources', 'expected'}
EXPECTED = {'read_id', 'parent_id', 'chunk_index', 'block_index', 'row_begin', 'row_end',
            'available_score_end', 'available_signal_end', 'plan_sha256',
            'previous_state_sha256', 'state_sha256'}
RETAINED = ('state', 'snapshot', 'complete', 'producer')


def exact(value, fields, label):
    io.require(isinstance(value, dict) and set(value) == set(fields), label + ' fields differ')


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_pin(value):
    exact(value, ('path', 'size', 'sha256'), 'FilePin')
    path = Path(value['path'])
    io.require(path.is_absolute() and path == path.resolve() and type(value['size']) is int
               and value['size'] >= 0 and sha(value['sha256']), 'FilePin shape differs')


def consumed(value):
    file_pin(value)
    io.check(value)
    result = io.read(value['path'])
    io.check(value)
    return result


def result_path(path):
    path = Path(path)
    io.require(path.is_absolute() and path == path.resolve()
               and path.is_relative_to(F1 / 'results/prefix-feedback')
               and path != F1 / 'results/prefix-feedback', 'output/work directory outside F1 results')
    return path


@dataclass(frozen=True)
class StepSpec:
    value: dict
    pin: dict

    @classmethod
    def load(cls, path, expected_sha256):
        pin = io.pin(path)
        io.require(pin['sha256'] == expected_sha256, 'external spec hash differs')
        value = consumed(pin)
        operation = value.get('operation')
        io.require(operation in ('locate', 'advance-next'), 'only locate and advance-next are supported')
        extra = {'work_directory', 'execution_index'} if operation == 'locate' else {
            'location_result', 'update', 'next_block'}
        exact(value, COMMON | extra, 'step spec')
        io.require(value['schema'] == 'prefix-feedback-verifier-spec/1', 'step schema differs')
        exact(value['expected'], EXPECTED, 'independent expected binding')
        e = value['expected']
        n = e['block_index']
        io.require(all(type(e[k]) is int for k in ('chunk_index', 'block_index', 'row_begin', 'row_end',
                       'available_score_end', 'available_signal_end'))
                   and 0 <= n <= 2 and e['chunk_index'] == 0
                   and e['row_begin'] == 497 * n and e['row_end'] == e['available_score_end'] == 497 * (n + 1)
                   and e['available_signal_end'] == 12222, 'retained block endpoints differ')
        io.require(isinstance(e['read_id'], str) and e['read_id'] and e['parent_id'] == e['read_id']
                   and e['plan_sha256'] == CONFIG_SHA
                   and sha(e['previous_state_sha256']) and sha(e['state_sha256']), 'expected identity differs')
        io.require(value['source_sha256'] == SOURCE and value['plan']['sha256'] == PLAN_SHA
                   and value['binary']['sha256'] == BINARY_SHA, 'frozen source/plan/binary identity differs')
        exact(value['retained'], RETAINED, 'retained advance')
        pins = [value['plan'], value['binary'], *value['retained'].values()]
        for name in ('source_pins', 'predecessor_sources'):
            sources = value[name]
            io.require(isinstance(sources, list) and sources
                       and len({p['path'] for p in sources}) == len(sources), 'source closure differs')
            pins.extend(sources)
        if operation == 'locate':
            result_path(value['work_directory'])
            pins.append(value['execution_index'])
        else:
            exact(value['next_block'], ('block_index', 'row_begin', 'row_end'), 'next block')
            io.require(all(type(p) is int for p in value['next_block'].values())
                       and value['next_block'] == dict(block_index=n + 1, row_begin=497 * (n + 1),
                       row_end=497 * (n + 2)), 'advance0 or wrong next block/endpoints refused')
            pins.extend([value['location_result'], value['update']])
        for item in pins:
            file_pin(item)
        for item in [value['binary'], *value['retained'].values()]:
            result_path(Path(item['path']).parent)
        required = [Path(__file__).resolve(), Path(io.__file__).resolve(), Path(joint.__file__).resolve(),
                    F1 / 'tools/prefix_feedback/qualification.py', PREFIX_SCRIPT]
        for path in required:
            io.require(io.pin(path) in value['source_pins'], 'loaded driver/source pin absent')
        io.require(io.GUARD in value['source_pins'] and io.F4 in value['source_pins'], 'recorder closure absent')
        return cls(value, pin)


def check_plan(value):
    plan = consumed(value['plan'])
    exact(plan, ('schema', 'config', 'spec', 'blocks', 'selected', 'exclusions', 'mapper', 'samtools',
                 'reference', 'reference_index', 'reference_fai', 'index_provenance', 'producer_sources',
                 'truth_opened', 'allow_refill', 'available_native_passthrough'), 'frozen plan')
    config = consumed(plan['config'])
    exact(config, ('schema', 'role', 'hypothesis', 'endpoint', 'selection', 'manifest', 'policy', 'releases',
                   'causality', 'reference', 'reference_index', 'reference_fai_path', 'mapper_path',
                   'index_provenance', 'producer_sources', 'samtools', 'execution', 'hg005_selection',
                   'truth_input', 'promotion'), 'development config')
    io.require(plan['config']['sha256'] == CONFIG_SHA and config['schema'] == 'prefix-feedback-config/1'
               and config['role'] == 'development-HG002' and config['hg005_selection'] is False
               and config['truth_input'] is None and config['promotion'] is False, 'development config role/truth differs')
    io.require(plan['schema'] == 'prefix-pilot-plan/1' and plan['truth_opened'] is False
               and plan['allow_refill'] is False and plan['available_native_passthrough'] is None,
               'frozen plan selection differs')
    e = value['expected']
    io.require(plan['selected']['parent'] == plan['spec']['read_id'] == e['read_id']
               and plan['spec']['plan_sha256'] == e['plan_sha256']
               and plan['spec']['state_length'] == 4 and plan['spec']['policy'] == config['policy'] == POLICY
               and plan['spec']['stay_score'] == 2.0, 'selected parent/session differs')
    io.require(plan['selected']['cutoffs'] == [0, 497, 994, 1491, 1988]
               and plan['selected']['ownership'][0] == [0, 1988] and len(plan['blocks']) == 4,
               'original four releases differ')
    for n, block in enumerate(plan['blocks']):
        io.require(block['read_id'] == block['parent_id'] == e['read_id'] and block['chunk_index'] == 0
                   and block['block_index'] == n and block['row_begin'] == block['chunk_row_begin'] == 497 * n
                   and block['row_end'] == block['chunk_row_end'] == block['available_score_end'] == 497 * (n + 1)
                   and block['available_signal_end'] == block['chunk_signal_end'] == block['declared_chunk_lookahead'] == 12222
                   and block['chunk_signal_begin'] == 0 and block['orientation'] == 'signal-forward',
                   'original release ownership differs')
        release = consumed(block['release_receipt'])
        io.require(release['schema'] == 'prefix-release/1' and release['read_id'] == e['read_id']
                   and release['tensor'] == block['tensor']
                   and release['binding'] == {k: p for k, p in block.items() if k != 'release_receipt'}
                   and release['original_row_begin'] == block['chunk_row_begin']
                   and release['original_row_end'] == block['chunk_row_end']
                   and release['original_tensor'] == plan['selected']['chunks'][0]['tensor']
                   and release['metadata'] == plan['selected']['chunks'][0]['metadata'], 'release receipt ownership differs')
    return plan


def check_snapshot(state, batch, plan, expected):
    n = expected['block_index']
    block = plan['blocks'][n]
    io.require(state['schema'] == 'prefix-session/1' and state['source_sha256'] == SOURCE
               and state['spec'] == plan['spec'] and state['consumed'] == plan['blocks'][:n + 1]
               and state['last_binding'] == block and state['consumed_rows'] == block['row_end']
               and state['next_block'] == n + 1, 'state ownership/session differs')
    io.require(batch['schema'] == 'prefix-snapshot/1' and batch['source_sha256'] == SOURCE
               and all(batch[key] == expected[key] for key in ('read_id', 'parent_id', 'plan_sha256',
                       'state_sha256', 'previous_state_sha256'))
               and batch['state_sha256'] == digest(state) and batch['policy'] == POLICY
               and batch['initial_prior'] == 'uniform-all-CRF-states'
               and batch['location_updates'] == state['updates'] and len(state['updates']) == n,
               'snapshot independent binding differs')
    io.require(all(batch['binding'][key] == item for key, item in block.items())
               and batch['binding']['source_sha256'] == SOURCE
               and batch['binding']['plan_sha256'] == expected['plan_sha256']
               and batch['binding']['previous_state_sha256'] == expected['previous_state_sha256']
               and batch['binding']['resource_manifest'] == plan['spec']['resource_manifest'],
               'snapshot block binding differs')
    if n == 0:
        io.require(state['updates'] == state['locations'] == state['first_locations'] == batch['locations'] == [],
                   'block0 context differs')


def check_producer(retained, binary, request, sources):
    receipt = consumed(retained['producer'])
    exact(receipt, ('schema', 'complete', 'binary', 'command', 'terminal', 'outputs', 'stdout', 'stderr', 'time'),
          'native producer receipt')
    stage = Path(retained['producer']['path']).parent
    root = stage.parent
    io.require(stage.name == 'stage-0' and Path(retained['producer']['path']).name == 'receipt.json'
               and receipt['schema'] == 'prefix-stage-receipt/1' and receipt['complete'] is True
               and receipt['binary'] == binary
               and receipt['outputs'] == [retained[key] for key in ('state', 'snapshot', 'complete')],
               'native producer output census differs')
    complete = consumed(retained['complete'])
    exact(complete, ('schema', 'complete', 'request', 'source', 'source_sha256'), 'native completion')
    io.require(complete['schema'] == 'prefix-complete/1' and complete['complete'] is True
               and complete['source_sha256'] == SOURCE and complete['source']['root'] == str(F1)
               and digest(complete['source']) == SOURCE, 'compiled witness differs')
    for item in complete['source']['sources']:
        io.require(any(p['path'] == item['path'] and p['sha256'] == item['sha256'] for p in sources),
                   'compiled source absent from producer closure')
    request_pin = complete['request']
    io.require(request_pin == io.pin(root / 'request-0.json') and consumed(request_pin) == request,
               'actual prior advance request differs')
    native_output = Path(retained['complete']['path']).parent
    io.require([retained[k]['path'] for k in ('state', 'snapshot', 'complete')]
               == [str(native_output / name) for name in ('state.json', 'snapshot.json', 'complete.json')],
               'native output paths differ')
    io.require(receipt['command'] == io.pin(stage / 'command.json')
               and consumed(receipt['command']) == dict(argv=[binary['path'], 'advance', '--request', request_pin['path'],
                   '--request-sha256', request_pin['sha256'], '--output', str(native_output)], cwd=str(F1),
                   env=dict(io.ENVIRONMENT, TMPDIR=str(root / 'tmp')), input_pins=[request_pin], source_pins=sources),
               'native producer exact argv/cwd/env/source/input differs')
    terminal = consumed(receipt['terminal'])
    io.require(receipt['terminal'] == io.pin(stage / 'terminal.json')
               and terminal['command'] == receipt['command'] and terminal['exit_known'] is True
               and terminal['exit'] == 0 and terminal['failure'] is None and terminal['cleanup']['terminal'] is True
               and terminal['start'] and terminal['start'] <= terminal['end'], 'native exit/cleanup/clock differs')
    for key, name in (('stdout', 'stdout'), ('stderr', 'stderr'), ('time', 'time.txt')):
        io.require(receipt[key] == io.pin(stage / name), 'native raw pin differs')


def retained_inputs(value, plan):
    retained = value['retained']
    state, batch = consumed(retained['state']), consumed(retained['snapshot'])
    check_snapshot(state, batch, plan, value['expected'])
    complete = consumed(retained['complete'])
    request = consumed(complete['request'])
    n = value['expected']['block_index']
    prior_pin = request.get('state')
    prior = consumed(prior_pin) if n else None
    io.require((n == 0 and prior_pin is None and request.get('update') is None)
               or (n > 0 and prior['spec'] == plan['spec'] and prior['consumed'] == plan['blocks'][:n]
                   and prior['next_block'] == n and digest(prior) == batch['previous_state_sha256']
                   and state['updates'] == prior['updates'] + [request.get('update')]), 'predecessor state/update differs')
    wanted = dict(schema='prefix-advance/1', source_sha256=SOURCE, spec=plan['spec'], state=prior_pin,
                  update=None if n == 0 else state['updates'][-1], block=plan['blocks'][n],
                  expected_previous_state_sha256=None if n == 0 else batch['previous_state_sha256'])
    check_producer(retained, value['binary'], wanted, value['predecessor_sources'])
    for item in complete['source']['sources']:
        io.require(any(p['path'] == item['path'] and p['sha256'] == item['sha256']
                       for p in value['source_pins']), 'compiled source absent from current closure')
    return state, batch


def check_update(update, batch, plan):
    exact(update, ('schema', 'source_sha256', 'plan_sha256', 'read_id', 'state_sha256', 'query_sequence',
                   'query_sha256', 'query_length', 'query', 'available_score_end', 'available_signal_end',
                   'orientation', 'producer_receipt', 'paf', 'locations', 'mapper', 'reference_index',
                   'resource_manifest'), 'location update')
    io.require(update['schema'] == 'prefix-location/1' and update['source_sha256'] == SOURCE
               and all(update[k] == batch[k] for k in ('read_id', 'plan_sha256', 'state_sha256'))
               and update['query_sequence'] == batch['provisional_prefix']
               and update['query_sha256'] == hashlib.sha256(batch['provisional_prefix'].encode()).hexdigest()
               and update['query_length'] == len(batch['provisional_prefix'])
               and update['available_score_end'] == batch['binding']['row_end']
               and update['available_signal_end'] == batch['binding']['available_signal_end']
               and update['orientation'] == 'signal-forward'
               and update['resource_manifest'] == plan['spec']['resource_manifest']
               and update['mapper'] == plan['mapper'] and update['reference_index'] == plan['reference_index'],
               'location update binding differs')


def locate(value, batch, plan):
    if batch['abstained'] or not batch['mapper_request_eligible']:
        return dict(status='observed-no-eligible-prefix', update=None, actual_locations=0, usable_locations=0)
    index = consumed(value['execution_index'])
    exact(index, ('schema', 'source_pins', 'commands'), 'execution index')
    io.require(index['schema'] == 'prefix-command-index/1'
               and len({p['path'] for p in index['source_pins']}) == len(index['source_pins']),
               'execution index schema/closure differs')
    for item in index['source_pins']:
        file_pin(item)
    io.require(all(p in index['source_pins'] for p in (io.F4, value['binary'], plan['mapper'], plan['samtools']))
               and all(p in index['source_pins'] for p in plan['producer_sources']),
               'execution index frozen closure differs')
    for entry in index['commands']:
        exact(entry, ('proposal', 'complete'), 'execution index entry')
        file_pin(entry['proposal'])
        file_pin(entry['complete'])
    work = result_path(value['work_directory'])
    identity = {key: value[key] for key in COMMON if key != 'schema'}
    identity['index_source_pins'] = index['source_pins']
    if work.exists():
        io.require((work / 'admission.json').is_file() and io.read(work / 'admission.json') == identity,
                   'retained locate work identity differs')
        io.require(not any(p.is_symlink() for p in work.rglob('*')), 'symlink in retained locate work')
    else:
        work.mkdir()
        io.fresh(work / 'admission.json', identity)
    executor = io.RetainedCommands(index, plan['producer_sources'])
    module_spec = importlib.util.spec_from_file_location('canonical_prefix_feedback', PREFIX_SCRIPT)
    prefix = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(prefix)
    try:
        update = prefix.locate(executor, value['binary'], plan, batch, work / 'location')
    except io.PendingCommand as pending:
        return dict(status='awaiting-fresh-Root-grant', proposal=pending.proposal,
                    execution_index=value['execution_index'], work_directory=str(work),
                    native_command_executed=False, authorization=False)
    check_update(update, batch, plan)
    io.same_json(work / 'location.json', update)
    return dict(status='completed-location', update=io.pin(work / 'location.json'),
                actual_locations=len(update['locations']),
                usable_locations=sum(bool(item['continuation']) for item in update['locations']),
                execution_index=value['execution_index'], work_directory=str(work), native_command_executed=False)


def advance_request(value, batch, plan):
    location = consumed(value['location_result'])
    io.require(location['schema'] == 'prefix-feedback-verifier-result/1'
               and location['operation'] == 'locate' and location['status'] == 'completed-location'
               and location['retained'] == value['retained'] and location['expected'] == value['expected']
               and location['plan'] == value['plan'] and location['update'] == value['update']
               and location['producer_replay_permitted'] is False, 'completed location result differs')
    update = consumed(value['update'])
    check_update(update, batch, plan)
    io.require(not batch['abstained'] and batch['mapper_request_eligible'], 'no eligible prefix for next advance')
    block = plan['blocks'][value['next_block']['block_index']]
    return dict(schema='prefix-advance/1', source_sha256=SOURCE, spec=plan['spec'],
                state=value['retained']['state'], update=update, block=block,
                expected_previous_state_sha256=batch['state_sha256'])


def evidence(output):
    return [io.pin(p) for p in sorted(output.rglob('*')) if p.is_file() and not p.is_symlink()]


def run(spec_path, expected_sha256, output):
    io.admitted_worker()
    output = result_path(output)
    io.require(not output.exists(), 'fresh attempt required; producer replay prohibited')
    output.mkdir()
    stages = None
    spec = None
    try:
        spec = StepSpec.load(spec_path, expected_sha256)
        value = spec.value
        if value['operation'] == 'locate':
            work = Path(value['work_directory'])
            io.require(not output.is_relative_to(work) and not work.is_relative_to(output), 'work and result overlap')
        for item in [value['binary'], *value['source_pins'], *value['predecessor_sources']]:
            io.check(item)
        plan = check_plan(value)
        _, batch = retained_inputs(value, plan)
        result = dict(schema='prefix-feedback-verifier-result/1', operation=value['operation'], spec=spec.pin,
                      plan=value['plan'], binary=value['binary'], source_sha256=SOURCE,
                      expected=value['expected'], retained=value['retained'], producer_replay_permitted=False,
                      mechanism_qualified=False, scientific_qualified=False, whole_chunk_lookahead=True)
        if value['operation'] == 'locate':
            result.update(locate(value, batch, plan))
        else:
            request = advance_request(value, batch, plan)
            stages = joint.Stages(output / 'records', value['source_pins'])
            producer, _ = stages.f1(value['binary'], 'advance', request, output / 'advance',
                                    ('state.json', 'snapshot.json', 'complete.json'))
            retained = {key: io.pin(output / 'advance' / name) for key, name in (
                ('state', 'state.json'), ('snapshot', 'snapshot.json'), ('complete', 'complete.json'))}
            retained['producer'] = producer
            state, snapshot = consumed(retained['state']), consumed(retained['snapshot'])
            expected = dict(value['expected'], **value['next_block'],
                            available_score_end=value['next_block']['row_end'],
                            previous_state_sha256=batch['state_sha256'], state_sha256=digest(state))
            check_producer(retained, value['binary'], request, value['source_pins'])
            check_snapshot(state, snapshot, plan, expected)
            io.require(state['updates'] == batch['location_updates'] + [request['update']], 'advance update census differs')
            result.update(status='completed-advance', produced=retained, produced_expected=expected,
                          update=value['update'], candidates=len(snapshot['candidates']),
                          mapper_updates=len(state['updates']), abstained=snapshot['abstained'],
                          actual_locations=len(request['update']['locations']),
                          usable_locations=sum(bool(p['continuation']) for p in request['update']['locations']))
        io.fresh(output / 'result.json', result)
        return result
    except BaseException as error:
        io.fresh(output / 'result.json', dict(schema='prefix-feedback-verifier-result/1', status='failed',
            spec=None if spec is None else spec.pin, error=repr(error), producer_replay_permitted=False,
            completed_stages=[] if stages is None else stages.receipts, retained_files=evidence(output),
            recovery_spec=str(spec_path), recovery_spec_sha256=expected_sha256,
            recovery_work_directory=None if spec is None else spec.value.get('work_directory'),
            recovery_execution_index=None if spec is None else spec.value.get('execution_index'),
            recovery='Preserve all operands. Root must inspect raw exits and requests before a fresh authorized action.'))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.spec.resolve(), args.spec_sha256, args.output)


if __name__ == '__main__':
    main()
