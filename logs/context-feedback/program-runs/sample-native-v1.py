"""Run separately priced native sample-source phases over the fixed qualified inputs."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
chain = s.load('sample_engineering_chain_v1', HERE / 'sample-engineering-chain-v1.py')
v2 = chain.v2
p = s.load('sample_context_metadata', s.ROOT / 'tools/sample_context/pipeline.py')
QUALIFICATION = dict(path=str(s.RESULTS / 'sample-engineering-continuation-1/complete.json'), size=12246,
                     sha256='02e7ac5eee60d3d89ee0a6793845f7de28b5b872949369152b9dec2618ec1754')
QUALIFICATION_OUTER = dict(path=str(HERE / 'run-sample-engineering-continuation-1/outer-evidence.json'), size=4137,
                           sha256='ccd5a75a7c21540a86949e736e0a3dea77ef1c2a8dcdb0ec4bd6cfe2b6e15423')
FETCH = dict(path=str(s.ROOT / 'results/support-context/paw71238-fetch-2/47549a28034646b99141c4eb48da9cac/complete.json'),
             size=266788, sha256='bde8f5802fe047bfc6fe6f8d79ac5da567adfaa1a355411ced61093b071da445')
SNAPSHOT = dict(path='/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json',
                size=12027, sha256='f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324')
FAI = dict(path='/home/jake/Projects/nanopore_basecaller/logs/20261022T232044Z-accuracy-reference-decompress-2BpPCr/stdout.fai',
           size=7804, sha256='502a1b8fb73ccd53285c28a0f12df90c818b4fe3de1e862ef47c593ef1a0a4b4')
LINEAGE = dict(path=str(s.ROOT / 'logs/context-feedback-program/design/proposed-lineage-contract.json'),
               size=17252, sha256='8cbcfbda13da45069104d3c61b8604008abfb9f8915acba13fdf5a673d5b4640')
TRANSPORT_SHA = '185ef1a5d8468817ce5792a49a0fe52ca308b2f18b672a3991f2a0d836a7839a'
CHAIN_SHA = '62ea1691281c63f0f4e833e03a3d9e9037f015d687b15cf9b041a7ed1c001cdf'


def pipeline(unit, phase, request, suffix=None):
    name = suffix or phase
    request_path = unit.directory / (name + '-request.json')
    s.fresh(request_path, request)
    request_pin = s.pin(request_path)
    output = unit.directory / name
    stage = unit.stage('sample-pipeline-' + name, [str(s.UV), 'run', '--no-sync', 'python',
                       s.ROOT / 'tools/sample_context/pipeline.py', phase, '--request', request_path,
                       '--request-sha256', request_pin['sha256'], '--output', output])
    completion = json.loads(Path(stage['raw']['stdout']['path']).read_text())['completion']
    seal = s.read(completion)
    s.require(seal['schema'] == 'sample-context-pipeline-complete/1' and seal['complete'] is True
              and seal['phase'] == phase and seal['request'] == request_pin, 'Pipeline producer differs')
    for value in seal['sources'] + seal['files']:
        s.check(value)
    return completion, {Path(value['path']).name: value for value in seal['files']}


def take(value, phase):
    """Consume the exact successful whole-unit producer, with no replay."""
    seal, outer = s.read(value['completion']), s.read(value['outer'])
    start = s.read(outer['start'])
    terminal = s.read(outer['terminal'])
    intake = s.read(start['intake'])
    s.require(seal['schema'] == 'sample-context-unit/1' and seal['complete'] is True and seal['phase'] == phase
              and start['worker'] == s.pin(__file__) and start['controller'] == s.pin(HERE / 'run-sample-bounded-v2.py')
              and outer['projection_error'] is None and terminal['error'] is None and terminal['exit'] == 0
              and s.read(outer['launcher_cleanup'])['terminal'] is True
              and s.supervisor.terminal(terminal['proof'], terminal['expected_cgroup'])
              and terminal['proof']['properties']['Result'] == 'success'
              and terminal['proof']['properties']['ActiveState'] == 'inactive'
              and outer['raw'] == s.verify_raw(Path(outer['raw']['stdout']['path']).parent, start['worker_argv'], 0)
              and json.loads(s.check(outer['raw']['stdout']).read_text()) == dict(completion=value['completion']),
              'Prior native whole-unit source/result/raw/tree differs')
    v2.verified_active_intake(Path(value['completion']['path']).parent, start['intake'],
                             intake['description'], terminal['expected_cgroup'])
    for item in seal['sources'] + seal['files']:
        s.check(item)
    for item in seal['stages']:
        observed = s.read(item)
        chain.stage(item, observed['argv'])
    report = next(item for item in seal['files'] if Path(item['path']).name == 'native-report.json')
    result = s.read(report)
    s.require(result['phase'] == phase, 'Prior native report phase differs')
    return result


def native_reference(report):
    metadata = p.load_plan(report['plan'])
    proof = p.load_reference(report['reference'], report['plan'], metadata)
    s.require(len(metadata['cases']) == 368 and all(row['covered'] for row in metadata['cases'])
              and metadata['fetch'] == FETCH and metadata['additional_encoded_bytes'] == 0,
              'All-368 complete-container acquisition required')
    s.check(FAI)
    return metadata, proof


def reference(unit):
    request = json.loads((HERE / 'sample-plan-request.json').read_text())
    s.require(s.pin(HERE / 'sample-plan-request.json')['sha256'] == '607840daabdb7e254176bcf01ec224406119883c64777fb49d0a62d05032909d',
              'Original all-case plan request differs')
    request['fetch'] = FETCH
    plan_complete, files = pipeline(unit, 'plan', request)
    metadata = p.load_plan(files['plan.json'])
    s.require(metadata['selected_containers'] == 81 and len(metadata['cases']) == 368
              and all(row['covered'] for row in metadata['cases']) and metadata['additional_encoded_bytes'] == 0,
              'Completed fetch does not cover the frozen all-368 plan')
    stock = s.read(SNAPSHOT)
    ref, samtools = stock['reference'], stock['tools']['samtools']
    s.require(ref['size'] == 3144230986 and ref['sha256'] == '9cce8b926416dd96b152deea85188495b75f7ac8d634cc723a017067be8702b7'
              and samtools['sha256'] == 'e839773cc27090fa109588cae8b8240b0d48de816a25b962045867a4c3b7e1ff'
              and FAI['path'] == ref['path'] + '.fai', 'Fixed stock reference/tool/FAI differs')
    for value in (ref, samtools, FAI):
        s.check(value)
    unit.stage('sample-samtools-version', [samtools['path'], '--version'])
    linked = unit.stage('sample-samtools-libraries', [chain.partial()['tools']['ldd']['path'], samtools['path']])
    libraries = []
    for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
        s.require('not found' not in line, 'Missing samtools runtime library')
        match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
        if match:
            libraries.append(s.pin(match.group(1)))
    s.require(libraries and any('libhts.so' in item['path'] for item in libraries), 'Actual native HTSlib closure missing')
    dictionary = unit.stage('sample-stock-dictionary', [samtools['path'], 'dict', ref['path']])
    dictionary_stage = s.pin(unit.directory / 'stages/sample-stock-dictionary/finish.json')
    p.match_dictionary(metadata['references'], p.dictionary(Path(dictionary['raw']['stdout']['path']).read_text()))
    ref_complete, reference_files = pipeline(unit, 'reference', dict(plan=files['plan.json'], snapshot=SNAPSHOT,
                                              fai=FAI, dictionary_stage=dictionary_stage))
    p.load_reference(reference_files['reference.json'], files['plan.json'], metadata)
    faidx = unit.stage('sample-stock-fragments', [samtools['path'], 'faidx', '-r', files['regions.txt']['path'], ref['path']])
    fragments = p.fasta(s.check(faidx['raw']['stdout']))
    expected = {f'{row["contig"]}:{row["ref_begin"]+1}-{row["ref_end"]}' for row in metadata['cases']}
    s.require(set(fragments) == expected, 'Actual all-case native fragment census differs')
    s.check(FAI)
    report = dict(phase='reference', plan=files['plan.json'], reference=reference_files['reference.json'],
                  bed=files['targets.bed'], regions=files['regions.txt'], fetch=FETCH,
                  dictionary_stage=dictionary_stage, faidx_stage=s.pin(unit.directory / 'stages/sample-stock-fragments/finish.json'),
                  native_reference=faidx['raw']['stdout'], covered_cases=368, selected_containers=81,
                  samtools_binary=samtools, samtools_runtime_libraries=libraries,
                  additional_encoded_bytes=0, support_reads_decoded=False)
    return report, [plan_complete, ref_complete, *files.values(), *reference_files.values(), *libraries]


def eof(unit, task):
    report = take(task['reference_unit'], 'reference')
    native_reference(report)
    controller = s.pin(s.ROOT / 'tools/support_context/transport_fetch_v3.py')
    s.require(controller['sha256'] == TRANSPORT_SHA, 'Qualified exact transport API differs')
    transport = s.load('sample_exact_eof_transport', Path(controller['path']))
    config = transport.source()
    transfer = transport.Transport(unit.directory / 'eof', maximum_bytes=1024, maximum_request=38)
    source = config['objects']['cram']
    payload = transfer.fetch('cram', source, p.CRAM_SIZE - 38, p.CRAM_SIZE)
    receipts = [value for value in transfer.proofs if not value['path'].endswith('.attempt.json')]
    s.require(len(receipts) == 1 and transfer.consumed == 38 and transfer.reserved == 39,
              'Exactly one original 38-byte EOF response required')
    begin, end, observed = p.range_receipt(receipts[0], source, controller)
    s.require([begin, end] == [p.CRAM_SIZE - 38, p.CRAM_SIZE] and observed == payload, 'Exact original EOF receipt differs')
    p.verify_eof(s.check(payload).read_bytes())
    report = dict(phase='eof', reference_unit=task['reference_unit'], eof_receipt=receipts[0], eof_payload=payload,
                  network_cap_bytes=1024, consumed_payload_bytes=38, reserved_bytes=39, support_reads_decoded=False)
    return report, [receipts[0], payload, s.read(receipts[0])['request']]

def assembly(unit, task):
    reference_report = take(task['reference_unit'], 'reference')
    native_reference(reference_report)
    eof_report = take(task['eof_unit'], 'eof')
    s.require(eof_report['reference_unit'] == task['reference_unit'], 'EOF reference ancestry differs')
    complete, files = pipeline(unit, 'assemble', dict(plan=reference_report['plan'], reference=reference_report['reference'],
                               fetch=FETCH, eof_receipt=eof_report['eof_receipt']))
    assembled = s.read(files['assembly.json'])
    quick = unit.stage('sample-cram-quickcheck', ['/usr/bin/samtools', 'quickcheck', '-v', files['selected.cram']['path']])
    s.require(quick['raw']['stdout']['size'] == 0, 'Successful CRAM quickcheck must emit no file diagnostics')
    return dict(phase='assemble', reference_unit=task['reference_unit'], reference_report=reference_report,
                eof_unit=task['eof_unit'], assembly=files['assembly.json'], derivative=assembled['derivative'],
                quickcheck_stage=s.pin(unit.directory / 'stages/sample-cram-quickcheck/finish.json'),
                support_reads_decoded=False), [complete, *files.values()]


def decode(unit, task, pilot):
    assembled = take(task['assembly_unit'], 'assemble')
    ref = take(assembled['reference_unit'], 'reference')
    _, proof = native_reference(ref)
    if pilot:
        rows = s.check(ref['bed']).read_text().splitlines()
        s.require(rows, 'Acquired all-case BED is empty')
        bed = unit.directory / 'pilot.bed'
        s.fresh(bed, rows[0] + '\n')
        bed_pin = s.pin(bed)
    else:
        pilot_report = take(task['pilot_unit'], 'pilot')
        s.require(pilot_report['assembly_unit'] == task['assembly_unit'], 'Pilot assembly ancestry differs')
        bed_pin = ref['bed']
    name = 'sample-native-pilot' if pilot else 'sample-native-full'
    stage = unit.stage(name, [proof['samtools']['path'], 'view', '-h', '--no-PG', '-T', proof['reference']['path'],
                             '-L', bed_pin['path'], assembled['derivative']['path']])
    s.require(stage['raw']['stdout']['size'] <= (64 if pilot else 768) * s.MIB, 'Native SAM output exceeds its declared phase bound')
    s.check(FAI)
    return dict(phase='pilot' if pilot else 'decode', assembly_unit=task['assembly_unit'], reference_unit=assembled['reference_unit'],
                bed=bed_pin, sam=stage['raw']['stdout'], decode_stage=s.pin(unit.directory / 'stages' / name / 'finish.json'),
                pilot_only=pilot, full_acquired_context=not pilot, support_reads_decoded=True), [stage['raw']['stdout'], bed_pin]


def packet(unit, task):
    decoded = take(task['decode_unit'], 'decode')
    s.require(decoded['full_acquired_context'] is True and decoded['pilot_only'] is False, 'Full fresh native SAM producer required')
    assembled = take(decoded['assembly_unit'], 'assemble')
    ref = take(decoded['reference_unit'], 'reference')
    native_reference(ref)
    contract = s.read(LINEAGE)
    s.require(contract['read_level_contract_qualified'] is False, 'Actual strict lineage declaration changed')
    packets, files = {}, []
    for role in ('strict', 'exploratory_published_protocol'):
        request = dict(plan=ref['plan'], reference=ref['reference'], assembly=assembled['assembly'],
                       bed=ref['bed'], regions=ref['regions'], quickcheck_stage=assembled['quickcheck_stage'],
                       faidx_stage=ref['faidx_stage'], decode_stage=decoded['decode_stage'], lineage=LINEAGE)
        if role != 'strict':
            request['context_role'] = role
        complete, prepared_files = pipeline(unit, 'packet', request, 'packet-' + role)
        prepared = s.read(prepared_files['prepared.json'])
        s.require(prepared['sam'] == decoded['sam'] and prepared['context_role'] == role
                  and prepared['strict_read_level_qualified'] is False and prepared['consumer_ready'] is False
                  and prepared['promotion_eligible'] is False
                  and prepared['lineage_mode'] == ('unavailable' if role == 'strict' else 'assumption_qualified'),
                  'Separate strict-unavailable/exploratory-assumption packet roles differ')
        packets[role] = prepared_files['prepared.json']
        files += [complete, *prepared_files.values()]
    return dict(phase='packet', decode_unit=task['decode_unit'], packets=packets, lineage=LINEAGE,
                strict_read_level_qualified=False, promotion_eligible=False,
                new_source_can_carry_formerly_withheld_ALT=True), files


def tables(unit, task):
    prepared = take(task['packet_unit'], 'packet')
    binary = chain.BUILT['sample-context']
    results, files = {}, []
    for role, packet_pin in prepared['packets'].items():
        inputs = s.read(packet_pin)
        s.check(binary)
        command = [binary['path'], 'build', '--cases', inputs['cases']['path'], '--cases-sha256', inputs['cases']['sha256'],
                   '--sam', inputs['sam']['path'], '--sam-sha256', inputs['sam']['sha256'], '--output', str(unit.directory / role)]
        if role == 'exploratory_published_protocol':
            command += ['--context-role', role]
        stage = unit.stage('sample-tables-' + role, command)
        complete = json.loads(Path(stage['raw']['stdout']['path']).read_text())['completion']
        seal = s.read(complete)
        result = s.read(seal['result'])
        s.require(seal['complete'] is True and result['cases'] == 368 and result['context_role'] == role
                  and result['strict_read_level_qualified'] is False and result['consumer_ready'] is False
                  and result['promotion_eligible'] is False and result['independent_donor_confirmation'] is False,
                  'Actual full native table role/census differs')
        if role == 'strict':
            s.require(result['available_cases'] == 0 and result['path_rows'] == 0, 'Unqualified strict contract emitted usable DNA')
        else:
            s.require(result['assumption_tag'] == 'published_protocol_pi_dx_preservation_v1'
                      and result['exploratory_consumer_ready'] is True, 'Exploratory table role/assumption differs')
        for item in seal['files'] + seal['inputs']:
            s.check(item)
        results[role] = dict(completion=complete, result=seal['result'])
        files += [complete, seal['result'], *seal['files']]
    return dict(phase='tables', packet_unit=task['packet_unit'], results=results, source_table_frozen=True,
                source_ALT_information_changed_withholding=True, strict_read_level_qualified=False,
                promotion_eligible=False, independent_donor_confirmation=False), files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--task-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    task_pin = s.pin(args.task)
    s.require(task_pin['sha256'] == args.task_sha256, 'Native task pin differs')
    task = s.read(task_pin)
    phase = task['phase']
    s.require(task['schema'] == 'sample-native-task/1' and unit.price['scientific_work'] is True
              and unit.price['phase'] == ('assemble' if phase == 'eof' else phase), 'Native phase price/task differs')
    validator = s.pin(HERE / 'sample-engineering-chain-v1.py')
    s.require(validator['sha256'] == CHAIN_SHA, 'Qualified engineering chain source changed')
    chain.continued(QUALIFICATION, QUALIFICATION_OUTER)
    if phase == 'reference':
        report, files = reference(unit)
    elif phase == 'eof':
        report, files = eof(unit, task)
    elif phase == 'assemble':
        report, files = assembly(unit, task)
    elif phase in ('pilot', 'decode'):
        report, files = decode(unit, task, phase == 'pilot')
    elif phase == 'packet':
        report, files = packet(unit, task)
    elif phase == 'tables':
        report, files = tables(unit, task)
    else:
        raise ValueError('Unknown native task phase')
    report_path = unit.directory / 'native-report.json'
    s.fresh(report_path, report)
    sources = s.read(chain.FREEZE)['sources'] + [validator]
    if phase == 'eof':
        sources.append(s.pin(s.ROOT / 'tools/support_context/transport_fetch_v3.py'))
    unit.complete(phase, [s.pin(report_path), task_pin, *files], sources=sources,
                  details=dict(qualified_engineering=QUALIFICATION, inputs=task, reads_decoded=phase in ('pilot', 'decode', 'packet', 'tables'),
                               biological_qualification=False))


if __name__ == '__main__':
    main()
