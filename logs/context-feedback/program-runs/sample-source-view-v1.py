"""Prove a finite CRAM source view, then use separately admitted corrected-input phases."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CPP_SHA = '41e9bfbcf6cb4ec5b96a1a27a6322ff197e0e3c4204a2d94fb095d091238ff24'
NATIVE_SHA = 'b22163d82c2fbeaee8fa2814d69ad91722ea38938635f0ed6bd37d6218b669ab'
PREFIX_SHA = 'ecd605cfc71411864ba6edeeaf7f8cff7a5940fc50302d83c605cf4c2dfc63c1'
CONTRACT_SHA = '5d9a01bb16644b6119e1c03d4b5a1df878109928539f2392fe7f428f5356d3b1'
PREFIX_UNIT = dict(
    completion=dict(path=str(s.RESULTS / 'sample-prefix-fetch-1/complete.json'), size=48541,
                    sha256='438189ae9b8535f7c8ffe05dcc5bad5a94d567cb727180738754224d0e834ddb'),
    outer=dict(path=str(HERE / 'run-sample-prefix-fetch-1/outer-evidence.json'), size=3911,
               sha256='6e08769b2f69f6755e36b6bd14e8fcc73daabedf335c17bf763bbc5b6e8dc3e7'))
FLAGS = ['-std=c++23', '-O2', '-DNDEBUG', '-Wall', '-Wextra', '-Wpedantic', '-Wconversion',
         '-Wsign-conversion', '-Wshadow', '-Werror', '-fno-fast-math', '-ffp-contract=off']
native = None


def take(value, phase):
    """Only this frozen view worker, or the exact retained prefix worker, may produce these phases."""
    s.require(phase in ('prefix-acquisition', 'framing-proof', 'assemble', 'pilot', 'decode', 'packet', 'tables'),
              'Unknown source-view producer phase')
    worker = s.pin(HERE / 'sample-prefix-fetch-v1.py') if phase == 'prefix-acquisition' else s.pin(__file__)
    if phase == 'prefix-acquisition':
        s.require(value == PREFIX_UNIT and worker['sha256'] == PREFIX_SHA, 'Exact actual prefix producer required')
    seal, outer = s.read(value['completion']), s.read(value['outer'])
    start, terminal = s.read(outer['start']), s.read(outer['terminal'])
    intake = s.read(start['intake'])
    s.require(seal['schema'] == 'sample-context-unit/1' and seal['complete'] is True and seal['phase'] == phase
              and start['worker'] == worker and start['controller'] == s.pin(HERE / 'run-sample-bounded-v2.py')
              and terminal['exit'] == 0 and terminal['error'] is None and outer['projection_error'] is None
              and s.read(outer['launcher_cleanup'])['terminal'] is True
              and s.supervisor.terminal(terminal['proof'], terminal['expected_cgroup'])
              and terminal['proof']['properties']['Result'] == 'success'
              and terminal['proof']['properties']['ActiveState'] == 'inactive'
              and outer['raw'] == s.verify_raw(Path(outer['raw']['stdout']['path']).parent, start['worker_argv'], 0)
              and json.loads(s.check(outer['raw']['stdout']).read_text()) == dict(completion=value['completion']),
              'Actual source-view producer/source/raw/tree differs')
    native.v2.verified_active_intake(Path(value['completion']['path']).parent, start['intake'],
                                    intake['description'], terminal['expected_cgroup'])
    for item in seal['sources'] + seal['files']:
        s.check(item)
    for item in seal['stages']:
        native.chain.stage(item, s.read(item)['argv'])
    name = 'prefix-acquisition.json' if phase == 'prefix-acquisition' else 'native-report.json'
    report = next(item for item in seal['files'] if Path(item['path']).name == name)
    return s.read(report)


def inputs(task):
    s.require(task['prefix_unit'] == PREFIX_UNIT, 'Source view requires the actual successful exact prefix producer')
    prefix = take(task['prefix_unit'], 'prefix-acquisition')
    request = s.read(prefix['request'])
    outcome = s.read(request['outcome'])
    s.require(request['outcome'] == prefix['outcome'] and request['source_object'] == prefix['source_object']
              and prefix['payload_bytes'] == 2835 and len(prefix['prefixes']) == 45
              and prefix['genuine_cached_receipt_reuse_control'] is True
              and prefix['expanded_range_rejected'] is True and prefix['wrong_controller_rejected'] is True
              and prefix['supporting_DNA_decoded'] is False, 'Actual prefix handoff/census differs')
    contract_pin = s.pin(HERE / 'sample-source-view-future-tasks-v1.json')
    s.require(contract_pin['sha256'] == CONTRACT_SHA, 'Finite source-view declaration changed')
    contract = s.read(contract_pin)
    s.require(contract['prefix_request'] == prefix['request'], 'Prefix/view declarations differ')
    plan = s.read(request['original_selected_plan'])
    prefix_api = s.load('sample_view_prefix_intake', HERE / 'sample-prefix-fetch-v1.py')
    prefix_api.validate_ranges(request, outcome, plan)
    prefix_api.take_probe(request, native)
    audit = s.read(outcome['audit'])
    old_report = native.take(audit['assembly_unit'], 'assemble')
    original = s.read(old_report['assembly'])
    s.require(old_report['assembly'] == prefix['original_assembly'] == audit['assembly']
              and original['source_object'] == prefix['source_object'] and original['plan'] == request['original_selected_plan'],
              'Source-view original assembly/source ancestry differs')
    for row in prefix['prefixes']:
        begin, end, payload = native.p.range_receipt(row['receipt'], prefix['source_object'], prefix['transport'])
        s.require([begin, end] == row['range'] and payload == row['payload'], 'Actual prefix range differs')
    return prefix, original, old_report, plan, outcome, contract


def proof(unit, task):
    prefix, original, old_report, plan, outcome, contract = inputs(task)
    cpp = s.pin(HERE / 'sample-cram-framing-v3.cpp')
    s.require(cpp['sha256'] == CPP_SHA, 'Reviewed virtual framing source changed')
    parts = original['original_parts'] + [dict(range=row['range'], payload=row['payload']) for row in prefix['prefixes']]
    for part in parts:
        s.check(part['payload'])
        s.require(not any(ch.isspace() for ch in part['payload']['path']), 'Virtual span path cannot be framed')
    spans = unit.directory / 'spans.tsv'
    s.fresh(spans, ''.join(f'{row["range"][0]}\t{row["range"][1]}\t{row["payload"]["path"]}\n' for row in parts))
    declared = contract['tasks'][0]
    targets = unit.directory / 'targets.tsv'
    s.fresh(targets, ''.join(f'selected\t{row["crai_offset"]}\t{row["expected_physical_end"]+63}\n'
                            for row in declared['selected_containers'])
                    + ''.join(f'successor\t{offset}\t0\n' for offset in declared['successor_header_crai_offsets']))
    inspection = native.p.transport_completion(original['inspect'], 'inspect')
    crai = native.p.named(inspection['files'], 'index.crai')
    compiler, binary = s.pin('/usr/bin/c++'), unit.directory / 'sample-cram-framing'
    unit.stage('sample-view-framing-compile', [compiler['path'], *FLAGS, cpp['path'], '-o', binary, '-lhts', '-lz'])
    binary_pin = s.pin(binary)
    scratch = unit.directory / 'metadata-scratch'
    scratch.mkdir()
    observed = unit.stage('sample-view-framing-metadata', [binary, original['header']['path'], crai['path'], spans, targets, scratch])
    result = json.loads(Path(observed['raw']['stdout']['path']).read_text())
    selected = {row['crai_offset']: row for row in result['observations'] if row['role'] == 'selected'}
    successors = {row['crai_offset']: row for row in result['observations'] if row['role'] == 'successor'}
    s.require(result['schema'] == 'sample-cram-framing/3' and result['source_DNA_decoded'] is False
              and result['selected_headers_proven'] == len(selected) == 81
              and result['successor_headers_proven'] == len(successors) == 45
              and set(selected) == {row['crai_offset'] for row in declared['selected_containers']}
              and set(successors) == set(declared['successor_header_crai_offsets'])
              and result['all_selected_header_framing_proven'] is True and result['native_header_end'] == 9144
              and result['derived_header_delta'] == -63 and result['crai_first_container'] == 9207
              and all(result[key] is True for key in ('independent_header_crc', 'crc_mutation_rejected', 'adjacency_control',
                                                    'gap_control', 'overlap_control', 'slice_metadata_raw_only')),
              'Actual all81 finite source-view framing/control evidence differs')
    for row in declared['selected_containers']:
        actual = selected[row['crai_offset']]
        s.require(actual['physical_start'] == row['physical_start'] and actual['physical_end'] == row['expected_physical_end']
                  and actual['complete_selected_span_available'] is True and actual['records_declared'] > 0,
                  'Selected physical span differs from the exact declaration')
    for end in (row[1] for row in plan['required_ranges']):
        s.require(successors[end]['physical_start'] == end-63 and successors[end]['records_declared'] > 0
                  and successors[end]['native_container_crc_valid'] is True,
                  'Every run end requires its actual non-EOF successor header before applying end delta')
    linked = unit.stage('sample-view-framing-libraries', ['/usr/bin/ldd', binary])
    libraries = []
    for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
        s.require('not found' not in line, 'Framing runtime library missing')
        match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
        if match:
            libraries.append(s.pin(match.group(1)))
    s.require(any('libhts.so' in row['path'] for row in libraries), 'Actual native HTSlib link closure missing')
    output = unit.directory / 'framing-proof.json'
    s.fresh(output, dict(schema='sample-source-view-framing-proof/1', prefix_unit=task['prefix_unit'],
            task=task, original_assembly=prefix['original_assembly'], source_object=prefix['source_object'],
            native_observation=observed['raw']['stdout'], result=result, spans=s.pin(spans), targets=s.pin(targets),
            binary=binary_pin, compiler=compiler, flags=FLAGS, runtime_libraries=libraries,
            supporting_DNA_decoded=False, per_record_multireference_extents_qualified=False,
            whole_object_displacement_qualified=False, source_qualification=False))
    files = [s.pin(output), binary_pin, observed['raw']['stdout'], s.pin(spans), s.pin(targets), *libraries]
    files += [s.pin(path) for path in sorted(scratch.iterdir())]
    return dict(phase='framing-proof', prefix_unit=task['prefix_unit'], framing_proof=s.pin(output)), files


def require_proof(value, prefix_unit):
    report = take(value, 'framing-proof')
    proof_value = s.read(report['framing_proof'])
    r = proof_value['result']
    s.require(report['prefix_unit'] == proof_value['prefix_unit'] == prefix_unit == PREFIX_UNIT
              and proof_value['schema'] == 'sample-source-view-framing-proof/1'
              and r['selected_headers_proven'] == 81 and r['successor_headers_proven'] == 45
              and r['all_selected_header_framing_proven'] is True and r['source_DNA_decoded'] is False
              and all(row['header_crc_valid'] is True and row['native_container_crc_valid'] is True
                      and row['records_declared'] > 0 for row in r['observations']), 'All81 proof is unavailable')
    return report, proof_value


def assemble(unit, task):
    proof_report, proof_value = require_proof(task['proof_unit'], task['prefix_unit'])
    prefix, original, old_report, plan, outcome, contract = inputs(task)
    s.require(proof_value['original_assembly'] == prefix['original_assembly'], 'Framing/assembly original differs')
    r = proof_value['result']
    successors = {row['crai_offset']: row for row in r['observations'] if row['role'] == 'successor'}
    pieces = [dict(payload=original['header'], file_offset=0, length=r['native_header_end'], source_range=[0, r['native_header_end']], role='original_header')]
    runs = []
    prefixes = {tuple(row['range']): row for row in prefix['prefixes']}
    for begin, end in plan['required_ranges']:
        s.require(end in successors and successors[end]['physical_start'] == end-63
                  and successors[end]['records_declared'] > 0, 'Run end has no proven non-EOF successor')
        initial = prefixes[(begin-63, begin)]
        run_parts = [dict(payload=initial['payload'], file_offset=0, length=63, source_range=[begin-63, begin], role='original_prefix')]
        cursor = begin
        for part in original['original_parts']:
            a, b = part['range']; lo, hi = max(a, begin), min(b, end-63)
            if lo >= hi:
                continue
            s.require(lo == cursor, 'Original run view contains a gap or overlap')
            run_parts.append(dict(payload=part['payload'], file_offset=lo-a, length=hi-lo, source_range=[lo, hi], role='original_acquired_body'))
            cursor = hi
        s.require(cursor == end-63 and sum(row['length'] for row in run_parts) == end-begin,
                  'Finite physical run byte census differs')
        runs.append(dict(original_range=[begin, end], physical_range=[begin-63, end-63], pieces=run_parts,
                         omitted_unselected_successor_tail=[end-63, end]))
        pieces += run_parts
    a, b, eof = native.p.range_receipt(original['eof_receipt'], original['source_object'])
    s.require([a, b] == [native.p.CRAM_SIZE-38, native.p.CRAM_SIZE] and eof == original['eof_payload'], 'Exact original EOF identity differs')
    native.p.verify_eof(s.check(eof).read_bytes())
    pieces.append(dict(payload=eof, file_offset=0, length=38, source_range=[a, b], role='original_EOF'))
    encoded = sum(end-begin for begin, end in plan['required_ranges'])
    expected = sum(row['length'] for row in pieces)
    s.require(encoded == 259192705 and expected == encoded+r['native_header_end']+38
              and len(runs) == 45, 'Actual declared finite source-view size differs')
    derivative = unit.directory / 'selected-view.cram'
    with derivative.open('xb') as target:
        for piece in pieces:
            unit.budget()
            with s.check(piece['payload']).open('rb') as stream:
                stream.seek(piece['file_offset']); remaining = piece['length']
                while remaining:
                    block = stream.read(min(remaining, s.MIB))
                    s.require(block, 'Original source-view bytes truncated')
                    target.write(block); remaining -= len(block)
        target.flush(); s.os.fsync(target.fileno())
    s.sync(unit.directory)
    s.require(derivative.stat().st_size == expected, 'Actual corrected derivative length differs')
    derivative_pin = s.pin(derivative)
    view_path = unit.directory / 'source-view.json'
    s.fresh(view_path, dict(schema='sample-cram-source-view/1', prefix_unit=task['prefix_unit'], proof_unit=task['proof_unit'],
            framing_proof=proof_report['framing_proof'], original_assembly=prefix['original_assembly'],
            source_object=original['source_object'], header_range=[0, r['native_header_end']], runs=runs, pieces=pieces,
            encoded_bytes=encoded, expected_bytes=expected, derivative=derivative_pin,
            original_full_header_retained=original['header'], omitted_original_header_tail=[r['native_header_end'], original['header']['size']],
            synthetic_bytes=False, original_files_unchanged=True, old_derivative_not_body_qualified=original['derivative'],
            whole_object_index_unchanged=True, supporting_DNA_decoded=False, source_qualification=False))
    assembly_path = unit.directory / 'assembly.json'
    preserved = {key: original[key] for key in ('plan', 'reference', 'inspect', 'fetch', 'source_object', 'header', 'original_parts', 'eof_receipt', 'eof_payload')}
    s.fresh(assembly_path, dict(preserved, schema='sample-context-assembly/1', derivative=derivative_pin,
            source_view=s.pin(view_path), framing_proof=proof_report['framing_proof'], prefix_acquisition=PREFIX_UNIT,
            correction_of=prefix['original_assembly'], original_files_unchanged=True, reads_decoded=False,
            quickcheck_still_required=True, assembly_adapter=s.pin(__file__)))
    ref = native.take(old_report['reference_unit'], 'reference')
    _, reference = native.native_reference(ref)
    quick = unit.stage('sample-view-quickcheck', [reference['samtools']['path'], 'quickcheck', '-v', derivative])
    s.require(quick['raw']['stdout']['size'] == 0, 'Corrected source-view quickcheck emitted diagnostics')
    return dict(phase='assemble', prefix_unit=task['prefix_unit'], proof_unit=task['proof_unit'], source_view=s.pin(view_path),
                assembly=s.pin(assembly_path), derivative=derivative_pin, reference_unit=old_report['reference_unit'],
                quickcheck_stage=s.pin(unit.directory / 'stages/sample-view-quickcheck/finish.json'), supporting_DNA_decoded=False), [s.pin(assembly_path), s.pin(view_path), derivative_pin]


def checked_view(value):
    report = take(value, 'assemble')
    require_proof(report['proof_unit'], report['prefix_unit'])
    assembly, view = s.read(report['assembly']), s.read(report['source_view'])
    s.require(assembly['source_view'] == report['source_view'] and assembly['derivative'] == view['derivative'] == report['derivative']
              and assembly['framing_proof'] == view['framing_proof'] and view['proof_unit'] == report['proof_unit']
              and view['prefix_unit'] == report['prefix_unit'] and view['schema'] == 'sample-cram-source-view/1'
              and view['synthetic_bytes'] is False and view['original_files_unchanged'] is True
              and len(view['runs']) == 45 and view['expected_bytes'] == report['derivative']['size'],
              'Explicit corrected finite source-view handoff missing')
    return report


def decode(unit, task, pilot):
    assembled = checked_view(task['assembly_unit'])
    ref = native.take(assembled['reference_unit'], 'reference')
    _, reference = native.native_reference(ref)
    if pilot:
        bed = unit.directory / 'pilot.bed'
        s.fresh(bed, s.check(ref['bed']).read_text().splitlines()[0]+'\n')
        bed_pin = s.pin(bed)
    else:
        previous = take(task['pilot_unit'], 'pilot')
        s.require(previous['assembly_unit'] == task['assembly_unit'] and previous['pilot_only'] is True, 'New-input pilot ancestry differs')
        bed_pin = ref['bed']
    name = 'sample-view-pilot' if pilot else 'sample-view-full'
    stage = unit.stage(name, [reference['samtools']['path'], 'view', '-h', '--no-PG', '-T', reference['reference']['path'],
                             '-L', bed_pin['path'], assembled['derivative']['path']])
    s.require(stage['raw']['stdout']['size'] <= (64 if pilot else 768)*s.MIB, 'Native source-view SAM exceeds declared phase bound')
    s.check(native.FAI)
    return dict(phase='pilot' if pilot else 'decode', assembly_unit=task['assembly_unit'], reference_unit=assembled['reference_unit'],
                sam=stage['raw']['stdout'], bed=bed_pin, decode_stage=s.pin(unit.directory / 'stages' / name / 'finish.json'),
                pilot_only=pilot, full_acquired_context=not pilot, supporting_DNA_decoded=True), [stage['raw']['stdout'], bed_pin]


def packets(unit, task):
    decoded = take(task['decode_unit'], 'decode')
    s.require(decoded['full_acquired_context'] is True and decoded['pilot_only'] is False, 'Full new-input native SAM producer required')
    assembled = checked_view(decoded['assembly_unit'])
    ref = native.take(assembled['reference_unit'], 'reference')
    native.native_reference(ref)
    s.require(s.read(native.LINEAGE)['read_level_contract_qualified'] is False, 'Actual strict lineage contract changed')
    packets_by_role, files = {}, []
    for role in ('strict', 'exploratory_published_protocol'):
        request = dict(plan=ref['plan'], reference=ref['reference'], assembly=assembled['assembly'], bed=ref['bed'],
                       regions=ref['regions'], quickcheck_stage=assembled['quickcheck_stage'], faidx_stage=ref['faidx_stage'],
                       decode_stage=decoded['decode_stage'], lineage=native.LINEAGE)
        if role != 'strict':
            request['context_role'] = role
        complete, values = native.pipeline(unit, 'packet', request, 'packet-'+role)
        prepared = s.read(values['prepared.json'])
        s.require(prepared['sam'] == decoded['sam'] and prepared['context_role'] == role
                  and prepared['strict_read_level_qualified'] is False and prepared['consumer_ready'] is False
                  and prepared['promotion_eligible'] is False and prepared['independent_donor_confirmation'] is False
                  and prepared['lineage_mode'] == ('unavailable' if role == 'strict' else 'assumption_qualified'),
                  'Unchanged typed packet role/lineage contract differs')
        packets_by_role[role] = values['prepared.json']; files += [complete, *values.values()]
    return dict(phase='packet', decode_unit=task['decode_unit'], packets=packets_by_role,
                source_ALT_information_changed_withholding=True, strict_read_level_qualified=False), files


def tables(unit, task):
    prepared = take(task['packet_unit'], 'packet')
    binary = native.chain.BUILT['sample-context']; s.check(binary)
    results, files = {}, []
    for role, packet_pin in prepared['packets'].items():
        packet = s.read(packet_pin)
        command = [binary['path'], 'build', '--cases', packet['cases']['path'], '--cases-sha256', packet['cases']['sha256'],
                   '--sam', packet['sam']['path'], '--sam-sha256', packet['sam']['sha256'], '--output', str(unit.directory / role)]
        if role == 'exploratory_published_protocol':
            command += ['--context-role', role]
        stage = unit.stage('sample-view-tables-'+role, command)
        completion = json.loads(Path(stage['raw']['stdout']['path']).read_text())['completion']
        seal = s.read(completion); result = s.read(seal['result'])
        s.require(seal['complete'] is True and result['cases'] == 368 and result['context_role'] == role
                  and result['strict_read_level_qualified'] is False and result['consumer_ready'] is False
                  and result['promotion_eligible'] is False and result['independent_donor_confirmation'] is False,
                  'Actual source-view table role/census differs')
        if role == 'strict':
            s.require(result['available_cases'] == 0 and result['path_rows'] == 0, 'Unavailable strict lineage emitted usable context')
        else:
            s.require(result['assumption_tag'] == 'published_protocol_pi_dx_preservation_v1'
                      and result['exploratory_consumer_ready'] is True, 'Explicit exploratory table declaration differs')
        for item in seal['files'] + seal['inputs']:
            s.check(item)
        results[role] = dict(completion=completion, result=seal['result']); files += [completion, seal['result'], *seal['files']]
    return dict(phase='tables', packet_unit=task['packet_unit'], results=results, source_table_frozen=True,
                source_ALT_information_changed_withholding=True, strict_read_level_qualified=False,
                promotion_eligible=False, independent_donor_confirmation=False), files


def main():
    global native
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--task-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    task_pin = s.pin(args.task)
    s.require(task_pin['sha256'] == args.task_sha256, 'Source-view task pin differs')
    task = s.read(task_pin); phase = task['phase']
    s.require(task['schema'] == 'sample-source-view-task/1'
              and phase in ('framing-proof', 'assemble', 'pilot', 'decode', 'packet', 'tables')
              and unit.price['phase'] == ('engineering' if phase == 'framing-proof' else phase)
              and unit.price['scientific_work'] is (phase != 'framing-proof'), 'Explicit source-view phase price required')
    native_pin = s.pin(HERE / 'sample-native-v2.py')
    s.require(native_pin['sha256'] == NATIVE_SHA and s.pin(HERE / 'sample-prefix-fetch-v1.py')['sha256'] == PREFIX_SHA,
              'Frozen native/prefix intake source differs')
    native = s.load('sample_view_frozen_native', Path(native_pin['path']))
    native.chain.continued(native.QUALIFICATION, native.QUALIFICATION_OUTER)
    if phase == 'framing-proof': report, files = proof(unit, task)
    elif phase == 'assemble': report, files = assemble(unit, task)
    elif phase in ('pilot', 'decode'): report, files = decode(unit, task, phase == 'pilot')
    elif phase == 'packet': report, files = packets(unit, task)
    else: report, files = tables(unit, task)
    path = unit.directory / 'native-report.json'; s.fresh(path, report)
    sources = s.read(native.chain.FREEZE)['sources'] + [native_pin, s.pin(HERE / 'sample-prefix-fetch-v1.py'),
              s.pin(HERE / 'sample-source-view-future-tasks-v1.json'), s.pin(HERE / 'sample-cram-framing-v3.cpp'),
              s.pin('/usr/include/htslib/cram.h'), s.pin('/usr/include/htslib/hfile.h')]
    unit.complete(phase, [s.pin(path), task_pin, *files], sources=sources,
                  details=dict(supporting_DNA_decoded=phase in ('pilot', 'decode', 'packet', 'tables'),
                               source_table_frozen=phase == 'tables', biological_qualification=False))


if __name__ == '__main__':
    main()
