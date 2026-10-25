#!/usr/bin/env python3
"""Prepare pinned independent-molecule context inputs; execute no native tools or network requests."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MIB = 1024 ** 2
RUN = '11d77535b149da7c6f7153939924a9fe29559cc7'
CRAM_SIZE = 89968340536
SOURCE_SHA = '86fce07a6f38ce6ffd98ea1f056126232d5b89efe91888806adfca724e0519fc'
INSPECT_SHA = 'e4369d3e7f73ec2519350130242bf5d0f4863c179d67d55b63b4f1de1b8fc950'
CASES_SHA = '9cda8f2adcad2c495e300b208e85f009d924d7dd39d46dad8099310817257dd7'
V4_IDENTITY = '695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa'
SNAPSHOT_SHA = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'
PARENTS_SHA = 'c8c0522c01a446b35517cee773f5e7d8014d390796c650b394fa4562a83a9d4a'
EOF = bytes.fromhex('0f000000ffffffff0fe0454f4600000000010005bdd94f0001000606010001000100ee63014b')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve(strict=True)
    size = path.stat().st_size
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(MIB):
            digest.update(block)
    require(path.stat().st_size == size, 'File size changed while hashing')
    return dict(path=str(path), size=size, sha256=digest.hexdigest())


def check(value):
    require(isinstance(value, dict) and set(value) == {'path', 'size', 'sha256'}
            and pin(value['path']) == value, 'Missing or changed pinned input: ' + str(value))
    return Path(value['path'])


def read(value):
    return json.loads(check(value).read_text())


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sync(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fresh(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data if isinstance(data, bytes) else data.encode('ascii'))
        stream.flush()
        os.fsync(stream.fileno())
    sync(Path(path).parent)


def save(path, value):
    fresh(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def coalesce(ranges):
    result = []
    for begin, end in sorted(set(tuple(row) for row in ranges)):
        require(type(begin) is int and type(end) is int and 0 <= begin < end <= CRAM_SIZE,
                'Invalid encoded byte interval')
        if result and begin <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([begin, end])
    return result


def covered(interval, ranges):
    return any(a <= interval[0] and interval[1] <= b for a, b in coalesce(ranges))


def subtract(ranges, retained):
    result = []
    for begin, end in coalesce(ranges):
        cursor = begin
        for a, b in coalesce(retained):
            if b <= cursor or a >= end:
                continue
            if a > cursor:
                result.append([cursor, a])
            cursor = max(cursor, b)
        if cursor < end:
            result.append([cursor, end])
    return result


def source_inventory():
    relative = json.loads((HERE / 'source-files.json').read_text())
    paths = [(HERE / name).resolve(strict=True) for name in relative]
    require(len(paths) == len(set(paths)) and all(p.is_relative_to(ROOT) for p in paths)
            and Path(__file__).resolve() in paths, 'Source census is incomplete/foreign/duplicated')
    return [pin(path) for path in sorted(paths)]


def historical_cases(request):
    packet, execution, auditor_pin = request['cases'], request['execution'], request['auditor']
    require(packet['sha256'] == CASES_SHA and execution['sha256'] ==
            '14e4fc1c4f9de03c789cbb20dc9df71d953a78002ce8278873cbb7ac6d30ae45',
            'Immutable v4 candidate packet/execution differs')
    check(execution)
    auditor_path = check(auditor_pin)
    require(auditor_path == Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v4/scripts/context-program.py'),
            'Historical auditor must stay in its original source location')
    spec = importlib.util.spec_from_file_location('sample_context_original_v4', auditor_path)
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    require(auditor.ROOT == auditor_path.parent.parent and auditor.c.ROOT == auditor.ROOT
            and auditor.identity(auditor.sources()) == V4_IDENTITY, 'Historical source closure differs')
    auditor.completed(Path(execution['path']).parent, 'prepare')
    require(packet['path'] == str(Path(execution['path']).parent / 'prepared/cases.tsv'),
            'Candidate packet is outside its historical completed preparation')
    return parse_cases(check(packet))


def parse_cases(path):
    schema = json.loads((ROOT / 'tools/context_decoder/study/wire-schema.json').read_text())
    fields = schema['candidate_records']['CASE']
    cases, domains = [], {}
    with Path(path).open(encoding='ascii') as stream:
        first = stream.readline().rstrip('\n').split('\t')
        require(len(first) == 3 and first[:2] == ['SCHEMA', 'context-candidate-case/1'], 'Candidate schema differs')
        for line in stream:
            if not line.startswith('CASE\t'):
                continue
            values = line.rstrip('\n').split('\t')[1:]
            require(len(values) == len(fields), 'Candidate CASE width differs')
            row = dict(zip(fields, values))
            recipe = schema['geometry_recipe']
            digest = hashlib.sha256((recipe['prefix'] + '\t' + '\t'.join(
                row[name] for name in recipe['case_fields']) + '\n').encode('ascii')).hexdigest()
            require(digest == row['geometry_sha256'], 'Candidate geometry digest differs')
            domains[row['domain']] = domains.get(row['domain'], 0) + 1
            numbers = {key: int(row[key]) for key in ('ref_start', 'ref_end', 'core_start', 'core_end', 'future_bases')}
            require(row['strand'] in ('+', '-') and numbers['future_bases'] == 10
                    and 0 <= numbers['ref_start'] < numbers['core_start'] < numbers['core_end'] < numbers['ref_end']
                    and len(row['left_guard']) == 10 and len(row['right_guard']) == 20,
                    'Native guard/future geometry differs')
            # Candidate strings, scores, private labels, and truth records never enter this projection.
            cases.append(dict(id=row['case_id'], parent=row['parent'], contig=row['contig'], strand=row['strand'],
                              ref_begin=numbers['ref_start'], ref_end=numbers['ref_end'],
                              core_begin=numbers['core_start'], core_end=numbers['core_end'],
                              future_bases=10, left=row['left_guard'], right=row['right_guard'],
                              geometry=row['geometry_sha256']))
    require(domains == {'ordinary': 311, 'private-ordinary': 31, 'private-withheld': 26}
            and len({row['id'] for row in cases}) == 368, 'All-368 candidate CASE census differs')
    return cases


def transport_completion(value, phase):
    result = read(value)
    require(result['schema'] == 'context-support-transport/1' and result['complete'] is True
            and result['phase'] == phase and result['source']['sha256'] == SOURCE_SHA,
            'Qualified support transport completion required')
    check(result['source'])
    check(result['controller'])
    files = result['files']
    require(len({p['path'] for p in files}) == len(files), 'Transport file census duplicated')
    for item in files:
        check(item)
    terminals = [item for item in files if Path(item['path']).name == 'terminal.json'
                 and Path(item['path']).parent == Path(value['path']).parent]
    require(len(terminals) == 1 and read(terminals[0])['operation_finished'] is True,
            'Transport operation lacks successful durable terminal status')
    return result


def named(files, name):
    matches = [item for item in files if Path(item['path']).name == name]
    require(len(matches) == 1, 'Missing/duplicate linked file: ' + name)
    return matches[0]


def crai(path):
    with gzip.open(path, 'rb') as stream:
        data = stream.read(16 * MIB + 1)
    require(len(data) <= 16 * MIB, 'CRAI metadata decompression bound exceeded')
    rows = []
    for line in data.decode('ascii').splitlines():
        require(re.fullmatch(r'-?\d+(?:\t-?\d+){5}', line), 'Malformed cached CRAI')
        rid, start, span, container, offset, size = map(int, line.split('\t'))
        require(rid >= -1 and (rid == -1 or start > 0 and span > 0) and 26 <= container < CRAM_SIZE
                and offset >= 0 and size > 0, 'Cached CRAI row outside bounds')
        rows.append((rid, start, span, container, offset, size))
    require(rows and len(set(rows)) == len(rows), 'Cached CRAI empty/duplicated')
    return rows


def container_plan(rows, references, cases, retained):
    starts = sorted({r[3] for r in rows})
    ends = dict(zip(starts, starts[1:] + [CRAM_SIZE]))
    names = {row['name']: (i, row['length']) for i, row in enumerate(references)}
    by_reference = {}
    for row in rows:
        require(row[0] < len(references) and row[3] + row[4] + row[5] < ends[row[3]],
                'Cached CRAI reference/container extent differs')
        by_reference.setdefault(row[0], []).append(row)
    selected, result = set(), []
    for case in cases:
        require(case['contig'] in names, 'Case reference absent from supporting CRAM')
        rid, length = names[case['contig']]
        begin, end = max(0, case['core_begin'] - 100), min(length, case['core_end'] + 100)
        require(0 <= case['ref_begin'] < case['ref_end'] <= length, 'Case reference geometry outside SQ')
        overlap = {r[3] for r in by_reference.get(rid, []) if r[1] - 1 < end and begin < r[1] - 1 + r[2]}
        selected.update(overlap)
        needed = [[start, ends[start]] for start in sorted(overlap)]
        result.append(dict(case, required_ranges=needed,
                           covered=bool(needed) and all(covered(row, retained) for row in needed)))
    ranges = coalesce([[start, ends[start]] for start in selected])
    missing = subtract(ranges, retained)
    return dict(cases=result, required_ranges=ranges, additional_ranges=missing,
                additional_encoded_bytes=sum(b-a for a, b in missing), selected_containers=len(selected))


def plan(request, output):
    require(request['inspect']['sha256'] == INSPECT_SHA, 'Registered native inspect pin differs')
    inspection = transport_completion(request['inspect'], 'inspect')
    price = read(named(inspection['files'], 'price.json'))
    require(price['read_groups'] and all(group.get('SM') == 'hg002' and group.get('PU') == 'PAW71238'
            and group.get('DS', '').split().count('runid=' + RUN) == 1 for group in price['read_groups']),
            'Actual supporting RG acquisition/run differs')
    cases = historical_cases(request)
    parents = check(request['parents']).read_text().splitlines()
    require(request['parents']['sha256'] == PARENTS_SHA and len(parents) == len(set(parents)) == 64
            and all(case['parent'] in parents for case in cases), 'Target parent census differs')
    retained = []
    if request.get('fetch') is not None:
        fetched = transport_completion(request['fetch'], 'fetch')
        acquired = read(named(fetched['files'], 'acquired-ranges.json'))
        require(acquired['inspect'] == request['inspect'], 'Fetched containers bind another inspect')
        retained = coalesce(acquired['ranges'])
    rows = crai(check(named(inspection['files'], 'index.crai')))
    value = container_plan(rows, price['references'], cases, retained)
    value.update(schema='sample-context-plan/1', source_cases=request['cases'], inspect=request['inspect'],
                 historical_execution=request['execution'], historical_auditor=request['auditor'],
                 parents=request['parents'], fetch=request.get('fetch'), references=price['references'],
                 groups=price['read_groups'], native_header=named(inspection['files'], 'stdout'),
                 retained_ranges=retained, target_count=64,
                 case_count=368, reads_decoded=False, biological_qualification=False)
    save(output / 'plan.json', value)
    physical = sorted({(row['contig'], row['ref_begin'], row['ref_end']) for row in value['cases']})
    acquired = sorted({(row['contig'], row['ref_begin'], row['ref_end']) for row in value['cases'] if row['covered']})
    fresh(output / 'targets.bed', ''.join(f'{name}\t{begin}\t{end}\n' for name, begin, end in acquired))
    fresh(output / 'regions.txt', ''.join(f'{name}:{begin+1}-{end}\n' for name, begin, end in physical))
    return [pin(output / name) for name in ('plan.json', 'targets.bed', 'regions.txt')]


def stage(value, expected):
    observed = read(value)
    require(observed['schema'] == 'context-feedback-stage/1' and observed['argv'] == expected
            and observed['exit'] == 0 and observed['failure'] is None and observed['projection_error'] is None,
            'Native stage command/result differs')
    terminal = read(observed['terminal'])
    require(terminal['exit'] == 0 and terminal['failure'] is None and terminal['argv'] == expected,
            'Native durable terminal differs')
    require(read(observed['group_cleanup'])['terminal'] is True, 'Native process group is not terminal')
    raw = observed['raw']
    require(set(raw) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}
            and not observed['missing_raw'], 'Native recorder evidence incomplete')
    text = {name: check(item).read_text() for name, item in raw.items() if name != 'stdout'}
    check(raw['stdout'])
    require(shlex.split(text['command.sh']) == expected and text['cwd.txt'].strip() == str(ROOT)
            and text['exit-status.txt'].strip() == '0', 'Native raw command/cwd/exit differs')
    begin, end = (text[name].strip() for name in ('start.txt', 'end.txt'))
    require(begin.endswith('Z') and end.endswith('Z') and datetime.fromisoformat(begin) <= datetime.fromisoformat(end),
            'Native raw clocks differ')
    timing = dict(line.strip().split(': ', 1) for line in text['time.txt'].splitlines()
                  if line.startswith('\t') and ': ' in line)
    require(timing.get('Exit status') == '0' and timing.get('Command being timed') == '"' + ' '.join(expected) + '"'
            and float(timing['User time (seconds)']) >= 0 and float(timing['System time (seconds)']) >= 0
            and int(timing['Maximum resident set size (kbytes)']) > 0
            and timing['Elapsed (wall clock) time (h:mm:ss or m:ss)'], 'Native time/RSS evidence incomplete')
    return raw['stdout']


def load_plan(value):
    metadata = read(value)
    require(metadata['schema'] == 'sample-context-plan/1' and metadata['case_count'] == 368
            and metadata['target_count'] == 64 and metadata['inspect']['sha256'] == INSPECT_SHA,
            'Prepared all-case plan identity differs')
    cases = historical_cases(dict(cases=metadata['source_cases'], execution=metadata['historical_execution'],
                                 auditor=metadata['historical_auditor']))
    check(metadata['parents'])
    require(metadata['parents']['sha256'] == PARENTS_SHA, 'Prepared target census differs')
    inspection = transport_completion(metadata['inspect'], 'inspect')
    price = read(named(inspection['files'], 'price.json'))
    require(metadata['references'] == price['references'] and metadata['groups'] == price['read_groups']
            and metadata['native_header'] == named(inspection['files'], 'stdout'), 'Prepared header metadata differs')
    retained = []
    if metadata['fetch'] is not None:
        fetched = transport_completion(metadata['fetch'], 'fetch')
        acquired = read(named(fetched['files'], 'acquired-ranges.json'))
        require(acquired['inspect'] == metadata['inspect'], 'Prepared acquisition ancestry differs')
        retained = coalesce(acquired['ranges'])
    expected = container_plan(crai(check(named(inspection['files'], 'index.crai'))), metadata['references'], cases, retained)
    require(metadata['retained_ranges'] == retained and all(metadata[key] == expected[key] for key in expected),
            'Prepared CASE/range coverage differs from original candidate packet and retained CRAI')
    return metadata


def dictionary(text):
    result = {}
    for line in text.splitlines():
        if not line.startswith('@SQ\t'):
            continue
        parts = line.split('\t')[1:]
        tags = dict(part.split(':', 1) for part in parts)
        require(len(tags) == len(parts) and {'SN', 'LN', 'M5'} <= set(tags)
                and tags['SN'] not in result and int(tags['LN']) > 0
                and re.fullmatch('[a-fA-F0-9]{32}', tags['M5']), 'Native dictionary SQ/M5 malformed')
        result[tags['SN']] = (int(tags['LN']), tags['M5'].lower())
    require(result, 'Native reference dictionary empty')
    return result


def match_dictionary(references, actual):
    require(references and len({row['name'] for row in references}) == len(references), 'CRAM SQ census duplicated/empty')
    for row in references:
        require(actual.get(row['name']) == (row['length'], row['md5']), 'CRAM SQ M5 differs from stock reference')


def reference(request, output):
    require(request['snapshot']['sha256'] == SNAPSHOT_SHA, 'Registered stock snapshot differs')
    stock = read(request['snapshot'])
    reference_pin, samtools = stock['reference'], stock['tools']['samtools']
    check(reference_pin)
    check(samtools)
    require(request['fai']['path'] == reference_pin['path'] + '.fai', 'Pinned preexisting reference FAI required')
    check(request['fai'])
    metadata = load_plan(request['plan'])
    native = stage(request['dictionary_stage'], [samtools['path'], 'dict', reference_pin['path']])
    actual = dictionary(check(native).read_text())
    match_dictionary(metadata['references'], actual)
    save(output / 'reference.json', dict(schema='sample-context-reference/1', plan=request['plan'],
         snapshot=request['snapshot'], reference=reference_pin, samtools=samtools, fai=request['fai'],
         dictionary_stage=request['dictionary_stage'], dictionary_stdout=native,
         all_cram_sq_m5_verified=True, reads_decoded=False))
    return [pin(output / 'reference.json')]


def load_reference(value, plan_pin, metadata):
    proof = read(value)
    require(proof['schema'] == 'sample-context-reference/1' and proof['all_cram_sq_m5_verified'] is True
            and proof['plan'] == plan_pin and proof['snapshot']['sha256'] == SNAPSHOT_SHA,
            'Linked reference proof identity differs')
    stock = read(proof['snapshot'])
    require(proof['reference'] == stock['reference'] and proof['samtools'] == stock['tools']['samtools']
            and proof['fai']['path'] == proof['reference']['path'] + '.fai', 'Linked stock reference/tool differs')
    for name in ('reference', 'samtools', 'fai'):
        check(proof[name])
    native = stage(proof['dictionary_stage'], [proof['samtools']['path'], 'dict', proof['reference']['path']])
    require(native == proof['dictionary_stdout'], 'Linked native dictionary output differs')
    match_dictionary(metadata['references'], dictionary(check(native).read_text()))
    return proof


def range_receipt(value, source, controller=None):
    receipt = read(value)
    require(receipt['complete'] is True and receipt['object'] == source, 'Acquired object identity differs')
    begin, end = receipt['range']
    require(0 <= begin < end <= source['size'] and receipt['payload']['size'] == end-begin,
            'Acquired range/payload length differs')
    check(receipt['payload'])
    attempt = read(receipt['request'])
    require(attempt['object'] == source and attempt['range'] == [begin, end]
            and attempt['source']['sha256'] == SOURCE_SHA and attempt['reserved_bytes'] == end-begin+1,
            'Acquired range request/source differs')
    check(attempt['source'])
    check(attempt['controller'])
    require(controller is None or attempt['controller'] == controller, 'Acquired range controller differs')
    headers = {key.lower(): text for key, text in receipt['response_headers'].items()}
    require(headers['content-range'] == f'bytes {begin}-{end-1}/{source["size"]}'
            and headers['content-length'] == str(end-begin) and headers['etag'] == source['etag']
            and headers['last-modified'] == source['last_modified'] and headers['x-amz-version-id'] == source['version_id']
            and headers.get('content-encoding', 'identity') == 'identity', 'Acquired response identity differs')
    return begin, end, receipt['payload']


def verify_eof(data):
    require(len(data) == 38 and len(EOF) == 38, 'CRAM v3 EOF must be exactly 38 original bytes')
    actual, expected = bytearray(data), bytearray(EOF)
    actual[9] &= 15
    expected[9] &= 15
    require(actual == expected, 'Native HTSlib CRAM v3 EOF template differs')


def assemble(request, output):
    metadata = load_plan(request['plan'])
    load_reference(request['reference'], request['plan'], metadata)
    inspection = transport_completion(metadata['inspect'], 'inspect')
    fetched = transport_completion(request['fetch'], 'fetch')
    acquired = read(named(fetched['files'], 'acquired-ranges.json'))
    require(acquired['inspect'] == metadata['inspect'] and request['fetch'] == metadata['fetch']
            and coalesce(acquired['ranges']) == metadata['retained_ranges'], 'Assembled range set differs from plan')
    source = read(fetched['source'])['objects']['cram']
    payloads = {item['path']: item for item in acquired['files']}
    parts = []
    for item in fetched['files']:
        if not item['path'].endswith('.json') or item['path'].endswith('.attempt.json'):
            continue
        candidate = read(item)
        if candidate.get('complete') is True and candidate.get('object') == source and 'payload' in candidate:
            part = range_receipt(item, source, fetched['controller'])
            if part[2]['path'] in payloads:
                parts.append(part)
    parts.sort(key=lambda row: row[0])
    require(len(parts) == len(payloads) and len({p[2]['path'] for p in parts}) == len(parts)
            and coalesce([[a, b] for a, b, _ in parts]) == acquired['ranges']
            and sum(b-a for a, b, _ in parts) == acquired['encoded_bytes'],
            'Acquired complete-container chunks contain gaps/duplicates/foreign ranges')
    header = named(inspection['files'], 'header.cram')
    begin, end, tail = range_receipt(request['eof_receipt'], source)
    require([begin, end] == [CRAM_SIZE-38, CRAM_SIZE], 'EOF must be fetched at the original exact source tail')
    eof = check(tail).read_bytes()
    verify_eof(eof)
    require(all(a >= header['size'] for a, _, _ in parts), 'Container range overlaps header prefix')
    expected_size = header['size'] + acquired['encoded_bytes'] + (0 if parts and parts[-1][1] == CRAM_SIZE else 38)
    require(expected_size <= 512 * MIB and shutil.disk_usage(output).free >= 30 * 1024**3 + expected_size,
            'Derivative size/disk reserve exceeds proposed unit')
    derivative = output / 'selected.cram'
    with derivative.open('xb') as target:
        for item in [header] + [p[2] for p in parts]:
            with check(item).open('rb') as stream:
                shutil.copyfileobj(stream, target, MIB)
        if not parts or parts[-1][1] != CRAM_SIZE:
            target.write(eof)
        target.flush()
        os.fsync(target.fileno())
    sync(output)
    require(derivative.stat().st_size == expected_size, 'Derivative CRAM size differs')
    with derivative.open('rb') as stream:
        require(stream.read(6) == b'CRAM\x03\x00', 'Derivative is not CRAM v3')
        stream.seek(-38, 2)
        require(stream.read() == eof, 'Derivative exact original EOF differs')
    save(output / 'assembly.json', dict(schema='sample-context-assembly/1', plan=request['plan'],
         reference=request['reference'], inspect=metadata['inspect'], fetch=request['fetch'],
         source_object=source, header=header, original_parts=[dict(range=[a, b], payload=p) for a, b, p in parts],
         eof_receipt=request['eof_receipt'], eof_payload=tail, derivative=pin(derivative),
         original_files_unchanged=True, reads_decoded=False, quickcheck_still_required=True))
    for item in [header, tail] + list(payloads.values()):
        check(item)
    return [pin(derivative), pin(output / 'assembly.json')]


def fasta(path):
    result, name = {}, None
    with Path(path).open(encoding='ascii') as stream:
        for line in stream:
            if line.startswith('>'):
                name = line[1:].strip()
                require(name and name not in result, 'Duplicate/empty native reference fragment')
                result[name] = ''
            else:
                require(name is not None, 'Native reference fragment lacks FASTA header')
                result[name] += line.strip()
    return result


def lineage(value, plan_value, role='strict'):
    require(role in ('strict', 'exploratory_published_protocol'), 'Unknown context role')
    result = dict(contract='.', role=role, mode='unavailable', exclusions=[], assumption_tag='.')
    if value is None:
        return result
    contract = read(value)
    require(contract['schema'] == 'sample-producer-lineage/1' and contract['supporting_run'] == RUN
            and contract['supporting_flowcell'] == 'PAW71238' and contract['target_flowcell'] == 'PAW70337'
            and contract['donor'] == 'HG002' and contract['semantics'] == 'pi_original_read_dx_zero_simplex_v1'
            and contract['tag_writer_version'] == '0.8.2'
            and contract['groups'] == plan_value['groups'] and contract['target_parents'] == plan_value['parents']
            and contract['independent_donor_confirmation'] is False,
            'Producer lineage contract identity/semantics differs')
    exclusions = contract.get('known_target_family_names', [])
    require(isinstance(exclusions, list) and len(exclusions) == len(set(exclusions))
            and all(isinstance(name, str) and re.fullmatch(r'[^\s]+', name) for name in exclusions),
            'Known target family exclusion names malformed')
    result.update(contract=value['sha256'], exclusions=sorted(exclusions))
    strict = contract.get('read_level_contract_qualified') is True and contract.get('pi_dx_relationships_preserved') is True
    assumptions = contract.get('exploratory_assumptions')
    root_rule = contract.get('declared_root_rule')
    exploratory = (contract.get('operational_producer_declaration_supported') is True
                   and isinstance(assumptions, list) and bool(assumptions)
                   and all(isinstance(text, str) and text for text in assumptions)
                   and isinstance(root_rule, dict) and {'present_pi', 'absent_pi', 'dx_zero', 'dx_nonzero',
                                                       'missing_dx', 'same_root_versions'} <= set(root_rule))
    if (role == 'strict' and not strict) or (role == 'exploratory_published_protocol' and not exploratory):
        return result
    required = {'actual_pg_chain', 'pi_dx_tag_writer', 'tag_preservation', 'publisher_library_protocol', 'target_family_closure'}
    require(set(contract['evidence']) == required and all(contract['evidence'].values()),
            'Lineage contract lacks actual producer/source/protocol/family evidence')
    for values in contract['evidence'].values():
        for item in values:
            check(item)
    require(plan_value['native_header'] in contract['evidence']['actual_pg_chain'],
            'Actual supporting @PG header must be in the lineage evidence closure')
    if role == 'strict':
        result['mode'] = 'strict_qualified'
    else:
        result.update(mode='assumption_qualified', assumption_tag='published_protocol_pi_dx_preservation_v1')
    return result


def packet(request, output):
    plan_value = load_plan(request['plan'])
    proof = load_reference(request['reference'], request['plan'], plan_value)
    assembly = read(request['assembly'])
    require(assembly['schema'] == 'sample-context-assembly/1' and assembly['plan'] == request['plan']
            and assembly['reference'] == request['reference'] and assembly['inspect'] == plan_value['inspect']
            and assembly['fetch'] == plan_value['fetch'],
            'Native source/reference/assembly ancestry differs')
    transport_completion(assembly['inspect'], 'inspect')
    transport_completion(assembly['fetch'], 'fetch')
    check(assembly['header'])
    for part in assembly['original_parts']:
        check(part['payload'])
    source = read(transport_completion(assembly['fetch'], 'fetch')['source'])['objects']['cram']
    begin, end, eof_pin = range_receipt(assembly['eof_receipt'], source)
    require([begin, end] == [CRAM_SIZE-38, CRAM_SIZE] and eof_pin == assembly['eof_payload'],
            'Linked original EOF proof differs')
    verify_eof(check(eof_pin).read_bytes())
    derivative = check(assembly['derivative'])
    binary = proof['samtools']['path']
    quick = stage(request['quickcheck_stage'], [binary, 'quickcheck', '-v', str(derivative)])
    require(quick['size'] == 0, 'Native CRAM quickcheck emitted diagnostics')
    bed = check(request['bed'])
    regions = check(request['regions'])
    expected = sorted({(row['contig'], row['ref_begin'], row['ref_end']) for row in plan_value['cases']})
    acquired = sorted({(row['contig'], row['ref_begin'], row['ref_end']) for row in plan_value['cases'] if row['covered']})
    require(acquired and bed.read_text() == ''.join(f'{c}\t{a}\t{b}\n' for c, a, b in acquired)
            and regions.read_text() == ''.join(f'{c}:{a+1}-{b}\n' for c, a, b in expected),
            'Native reference/filter census omits acquired all-368 contexts')
    native_reference = stage(request['faidx_stage'], [binary, 'faidx', '-r', str(regions), proof['reference']['path']])
    fragments = fasta(check(native_reference))
    require(set(fragments) == {f'{c}:{a+1}-{b}' for c, a, b in expected}, 'Native reference fragment census differs')
    decoded = stage(request['decode_stage'], [binary, 'view', '-h', '--no-PG', '-T', proof['reference']['path'], '-L', str(bed), str(derivative)])
    require(decoded['size'] <= 2 * 1024**3, 'Native SAM output exceeds proposed bound')
    policy = lineage(request.get('lineage'), plan_value, request.get('context_role', 'strict'))
    parents = check(plan_value['parents']).read_text().splitlines()
    rows = ['\t'.join(['SCHEMA', 'sample-context-cases/2', plan_value['source_cases']['sha256'], policy['contract'],
                       request['reference']['sha256'], request['assembly']['sha256'], policy['role'], policy['mode']])]
    rows += ['TARGET\t' + parent for parent in sorted(parents)]
    rows += ['EXCLUDE\t' + name for name in policy['exclusions']]
    rows += ['RG\t' + group['ID'] for group in plan_value['groups']]
    rows += ['\t'.join(['SQ', row['name'], str(row['length']), row['md5']]) for row in plan_value['references']]
    for case in plan_value['cases']:
        key = f'{case["contig"]}:{case["ref_begin"]+1}-{case["ref_end"]}'
        fragment = fragments[key]
        rows.append('\t'.join(map(str, ['CASE', case['id'], case['parent'], case['contig'], case['strand'],
             case['ref_begin'], case['ref_end'], case['core_begin'], case['core_end'], case['left'], case['right'],
             10, case['geometry'], fragment, 'covered' if case['covered'] else 'needs_ranges'])))
    require(sum(line.startswith('CASE\t') for line in rows) == 368,
            'All 368 geometries require native faidx fragments, including contexts whose encoded ranges are missing')
    fresh(output / 'cases.tsv', '\n'.join(rows) + '\n')
    save(output / 'prepared.json', dict(schema='sample-context-prepared/1', plan=request['plan'], reference=request['reference'],
         assembly=request['assembly'], quickcheck_stage=request['quickcheck_stage'], faidx_stage=request['faidx_stage'],
         decode_stage=request['decode_stage'], lineage=request.get('lineage'), cases=pin(output / 'cases.tsv'), sam=decoded,
         context_role=policy['role'], lineage_mode=policy['mode'], exploratory_assumption_tag=policy['assumption_tag'],
         strict_read_level_qualified=policy['mode'] == 'strict_qualified', consumer_ready=policy['mode'] == 'strict_qualified',
         exploratory_consumer_ready=policy['mode'] == 'assumption_qualified', promotion_eligible=False,
         inference_truth_files=[], independent_donor_confirmation=False,
         biological_qualification=False))
    return [pin(output / 'cases.tsv'), pin(output / 'prepared.json')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('plan', 'reference', 'assemble', 'packet'))
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT / 'results/sample-context') and output != ROOT / 'results/sample-context'
            and not output.exists(), 'Fresh owned output directory required')
    output.mkdir(parents=True)
    sync(output.parent)
    save(output / 'attempt.json', dict(schema='sample-context-pipeline-attempt/1', argv=os.sys.argv,
         phase=args.phase, started_utc=stamp(), external_whole_unit_supervision_required=True))
    try:
        inputs = pin(args.request)
        require(inputs['sha256'] == args.request_sha256, 'Request manifest pin differs')
        sources = source_inventory()
        files = globals()[args.phase](read(inputs), output)
        for item in [inputs] + sources:
            check(item)
        save(output / 'complete.json', dict(schema='sample-context-pipeline-complete/1', complete=True,
             phase=args.phase, request=inputs, files=files, sources=sources, finished_utc=stamp(),
             native_tools_executed=False, network_requests=0, biological_qualification=False))
        print(json.dumps(dict(completion=pin(output / 'complete.json'))))
    except BaseException as error:
        save(output / 'failure.json', dict(complete=False, error=repr(error), finished_utc=stamp()))
        raise


if __name__ == '__main__':
    main()
