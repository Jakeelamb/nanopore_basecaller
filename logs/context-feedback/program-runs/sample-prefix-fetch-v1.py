"""Acquire only the 45 priced missing CRAM prefixes; retain exact partial-cache proofs."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
REQUEST_SHA = '1a02357cdffa843fecd4299374ef997f58abb4ce231b03d4cf9deee5eeabd9ff'
OUTCOME_SHA = 'c04be98126d5b4bf5256e91164307485217849a04c61a5343298a2a777982ca8'
NATIVE_SHA = 'b22163d82c2fbeaee8fa2814d69ad91722ea38938635f0ed6bd37d6218b669ab'
PROBE_WORKER_SHA = '0f8bb1975fd1035cbd28ee23234bd77a6982421a138f463add5ba083b05dfb99'
TRANSPORT_SHA = '185ef1a5d8468817ce5792a49a0fe52ca308b2f18b672a3991f2a0d836a7839a'


def validate_ranges(task, outcome, plan):
    expected = [[begin - 63, begin] for begin, end in plan['required_ranges']]
    s.require(task['candidate_header_delta'] == outcome['candidate_displacement'] == -63
              and outcome['native_header_end'] == 9144 and outcome['crai_first_container'] == 9207
              and len(expected) == 45 and task['ranges'] == expected
              and {end for begin, end in expected} == set(outcome['original_selected_missing_candidate_prefix_offsets'])
              and all(end - begin == 63 for begin, end in expected)
              and task['payload_bytes'] == sum(end - begin for begin, end in expected) == 2835
              and task['minimum_reserved_bytes'] == 2880
              and task['maximum_network_bytes'] == 4096 and task['maximum_request_bytes'] == 63,
              'Prefix ranges or exact predeclared transfer caps differ')


def take_probe(task, native):
    value = task['probe_unit']
    seal, outer = s.read(value['completion']), s.read(value['outer'])
    start, terminal = s.read(outer['start']), s.read(outer['terminal'])
    intake = s.read(start['intake'])
    worker = s.pin(HERE / 'sample-cram-framing-v2.py')
    s.require(worker['sha256'] == PROBE_WORKER_SHA and start['worker'] == worker
              and start['controller'] == s.pin(HERE / 'run-sample-bounded-v2.py')
              and seal['schema'] == 'sample-context-unit/1' and seal['complete'] is True
              and seal['phase'] == 'framing-audit' and outer['projection_error'] is None
              and terminal['exit'] == 0 and terminal['error'] is None
              and s.read(outer['launcher_cleanup'])['terminal'] is True
              and s.supervisor.terminal(terminal['proof'], terminal['expected_cgroup'])
              and terminal['proof']['properties']['Result'] == 'success'
              and terminal['proof']['properties']['ActiveState'] == 'inactive'
              and outer['raw'] == s.verify_raw(Path(outer['raw']['stdout']['path']).parent, start['worker_argv'], 0)
              and json.loads(s.check(outer['raw']['stdout']).read_text()) == dict(completion=value['completion']),
              'Exact retained successful metadata probe/raw/tree differs')
    native.v2.verified_active_intake(Path(value['completion']['path']).parent, start['intake'],
                                    intake['description'], terminal['expected_cgroup'])
    for item in seal['sources'] + seal['files']:
        s.check(item)
    for item in seal['stages']:
        native.chain.stage(item, s.read(item)['argv'])
    return seal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    request_pin = s.pin(args.request)
    s.require(request_pin['sha256'] == args.request_sha256 == REQUEST_SHA
              and unit.price['phase'] == 'assemble' and unit.price['scientific_work'] is True,
              'Exact reviewed prefix request/phase required')
    task = s.read(request_pin)
    s.require(task['schema'] == 'sample-prefix-request/1' and task['outcome']['sha256'] == OUTCOME_SHA
              and task['supporting_DNA_decoded'] is False and task['global_index_shift_applied'] is False
              and task['source_qualification'] is False, 'Prefix acquisition is not source/DNA qualification')
    outcome, plan = s.read(task['outcome']), s.read(task['original_selected_plan'])
    s.require(outcome['original_selected_plan'] == task['original_selected_plan']
              and task['probe_unit'] == dict(completion=outcome['completion'], outer=outcome['outer']),
              'Prefix census/probe ancestry differs')
    validate_ranges(task, outcome, plan)
    wrong = dict(task, ranges=[list(row) for row in task['ranges']])
    wrong['ranges'][0][0] -= 1
    try:
        validate_ranges(wrong, outcome, plan)
    except ValueError as error:
        s.require(str(error) == 'Prefix ranges or exact predeclared transfer caps differ', 'Unexpected range rejection')
    else:
        raise ValueError('Expanded prefix range was accepted')
    native_pin = s.pin(HERE / 'sample-native-v2.py')
    s.require(native_pin['sha256'] == NATIVE_SHA, 'Frozen native intake source differs')
    native = s.load('sample_prefix_native_intake', Path(native_pin['path']))
    seal = take_probe(task, native)
    s.require(outcome['audit'] in seal['files'], 'Census is outside the actual metadata probe output')
    audit = s.read(outcome['audit'])
    old_report = native.take(audit['assembly_unit'], 'assemble')
    s.require(old_report['assembly'] == audit['assembly'], 'Original assembly ancestry differs')
    original = s.read(old_report['assembly'])
    controller = s.check(task['transport'])
    s.require(task['transport']['sha256'] == TRANSPORT_SHA, 'Exact qualified transport source differs')
    transfer_api = s.load('sample_prefix_exact_transport', controller)
    config = transfer_api.source()
    s.require(task['source'] == s.pin(transfer_api.SOURCE) and task['source_object'] == config['objects']['cram']
              and original['source_object'] == task['source_object']
              and original['plan'] == task['original_selected_plan'], 'Original source/plan identity differs')
    cache = Path(task['cache'])
    s.require(cache == s.RESULTS / 'sample-prefix-cache-1', 'Prefix cache is outside its exact owned path')
    owner = dict(schema='sample-prefix-cache-owner/1', request=request_pin, transport=task['transport'],
                 source=task['source'], ranges=task['ranges'], maximum_network_bytes=4096, maximum_request_bytes=63)
    owner_path = cache / 'owner.json'
    if cache.exists():
        s.require(owner_path.is_file() and json.loads(owner_path.read_text()) == owner,
                  'Existing prefix cache belongs to another request/source')
    else:
        transfer_api.create_directory(cache)
        transfer_api.fresh(owner_path, owner)
    for path in cache.glob('chunks/*/*.attempt.json'):
        attempt = transfer_api.read(path)
        s.require(attempt['object'] == task['source_object'] and attempt['range'] in task['ranges']
                  and attempt['reserved_bytes'] == 64 and attempt['controller'] == task['transport']
                  and attempt['source'] == task['source'], 'Retained partial attempt is outside the exact price')
    transfer = transfer_api.Transport(cache, maximum_bytes=4096, maximum_request=63)
    initial_consumed, initial_reserved = transfer.consumed, transfer.reserved
    acquired = []
    try:
        for ordinal, (begin, end) in enumerate(task['ranges'], 1):
            unit.budget()
            before = transfer.reserved
            payload = transfer.fetch('cram', task['source_object'], begin, end)
            receipt = transfer.proofs[-2]
            a, b, observed = native.p.range_receipt(receipt, task['source_object'], task['transport'])
            s.require([a, b] == [begin, end] and observed == payload and payload['size'] == 63,
                      'Actual original prefix receipt differs')
            row = dict(range=[a, b], payload=payload, receipt=receipt, request=s.read(receipt)['request'],
                       reused_completed_receipt=transfer.reserved == before)
            acquired.append(row)
            s.fresh(unit.directory / f'prefix-{ordinal:02d}.json', row)
            unit.budget()
    except BaseException as error:
        s.fresh(unit.directory / 'prefix-failure.json', dict(complete=False, error=repr(error),
                completed_ranges=len(acquired), cache_owner=s.pin(owner_path), cache_retained=True,
                original_producers_replayed=False, supporting_DNA_decoded=False))
        raise
    first = acquired[0]
    before = (transfer.consumed, transfer.reserved)
    reused = transfer.fetch('cram', task['source_object'], *first['range'])
    s.require(reused == first['payload'] and (transfer.consumed, transfer.reserved) == before
              and transfer.proofs[-2] == first['receipt'], 'Genuine exact completed prefix cache reuse failed')
    try:
        native.p.range_receipt(first['receipt'], task['source_object'], dict(task['transport'], sha256='0' * 64))
    except ValueError as error:
        s.require(str(error) == 'Acquired range controller differs', 'Unexpected selected-controller rejection')
    else:
        raise ValueError('Wrong-controller prefix receipt was accepted')
    s.require(len(acquired) == 45 and sum(row['payload']['size'] for row in acquired) == 2835
              and 2880 <= transfer.reserved <= 4096 and 2835 <= transfer.consumed <= 4096,
              'Completed prefix census or retained aggregate transfer accounting differs')
    cache_files = [s.pin(path) for path in sorted(cache.rglob('*')) if path.is_file()]
    manifest = unit.directory / 'prefix-acquisition.json'
    s.fresh(manifest, dict(schema='sample-prefix-acquisition/1', request=request_pin, outcome=task['outcome'],
            probe_unit=task['probe_unit'], original_assembly=audit['assembly'], source=task['source'],
            source_object=task['source_object'], transport=task['transport'], cache_owner=s.pin(owner_path),
            prefixes=acquired, cache_files=cache_files, payload_bytes=2835, minimum_reserved_bytes=2880,
            cache_consumed_bytes=transfer.consumed, cache_reserved_bytes=transfer.reserved,
            newly_reserved_bytes=transfer.reserved-initial_reserved,
            newly_consumed_bytes=transfer.consumed-initial_consumed, maximum_network_bytes=4096, maximum_request_bytes=63,
            genuine_cached_receipt_reuse_control=True, expanded_range_rejected=True, wrong_controller_rejected=True,
            original_producers_replayed=False, supporting_DNA_decoded=False, source_qualification=False,
            global_index_shift_applied=False, original_files_unchanged=True))
    sources = [task['transport'], task['source'], native_pin, s.pin(s.ROOT / 'tools/sample_context/pipeline.py'),
               s.pin(HERE / 'sample-assembly-adapter-v1.py')]
    unit.complete('prefix-acquisition', [request_pin, s.pin(manifest), *cache_files], sources=sources,
                  details=dict(prefix_count=45, payload_bytes=2835, network_cap_bytes=4096,
                               partial_cache_retained=True, supporting_DNA_decoded=False,
                               source_qualification=False, global_index_shift_applied=False))


if __name__ == '__main__':
    main()
