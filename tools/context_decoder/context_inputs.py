import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON field ' + key)
        value[key] = item
    return value


def read(path):
    def invalid(value):
        raise ValueError('Nonfinite JSON value ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object, parse_constant=invalid)


def pin(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as handle:
        sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=sha)


def check(value):
    require(set(value) == {'path', 'size', 'sha256'} and Path(value['path']).is_absolute(), 'Malformed file pin')
    require(pin(value['path']) == value, 'Changed file ' + value['path'])
    return value


def fresh(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def tabular(path, schema, values):
    with Path(path).open('x') as handle:
        handle.write(schema + '\n')
        for key, value in sorted(values.items()):
            value = str(value)
            require(not any(c in key + value for c in '\r\n\t'), 'Tabular field contains control separator')
            handle.write(key + '\t' + value + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def rows(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        value = json.loads(line, object_pairs_hook=unique_object)
        index = value['query_index']
        require(type(index) is int and index not in result, 'Duplicate/invalid query index')
        result[index] = value
    return result


def metadata(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split('\t')
        require(len(fields) == 2 and fields[0] not in result, 'Malformed native metadata')
        result[fields[0]] = fields[1]
    return result


def reverse_complement(sequence):
    require(set(sequence) <= set('ACGTN'), 'Noncanonical parent sequence')
    return sequence.translate(str.maketrans('ACGTN', 'TGCAN'))[::-1]


def cigar(value):
    parts = re.findall(r'([0-9]+)([MIDNSHP=X])', value)
    require(''.join(n + op for n, op in parts) == value and parts, 'Malformed CIGAR')
    require(all(0 < int(n) <= 10000000 for n, _ in parts), 'CIGAR operation bound')
    return [(int(n), op) for n, op in parts]


def mapped(path, parent):
    selected = []
    for line in Path(path).read_text().splitlines():
        if line.startswith('@'):
            continue
        fields = line.split('\t')
        require(len(fields) >= 11, 'Short native SAM')
        if fields[0] != parent or int(fields[1]) & 0x900:
            continue
        selected.append(fields)
    require(len(selected) == 1, 'Missing/duplicate mapped primary')
    f = selected[0]
    require(f[9] != '*' and len(f[9]) == len(f[10]) and all(33 <= ord(c) <= 126 for c in f[10]),
            'Incomplete native SEQ/Q')
    reverse = bool(int(f[1]) & 16)
    return dict(fields=f, flag=int(f[1]), contig=f[2], start=max(int(f[3]) - 1, 0),
                mapq=int(f[4]), aligned=f[9], sequence=reverse_complement(f[9]) if reverse else f[9],
                quality=f[10][::-1] if reverse else f[10], reverse=reverse)


def validate_location(window, observation, minimum_mapq):
    require(window['read_id'] == observation['fields'][0], 'Location parent mismatch')
    if observation['flag'] & 4:
        return 'missing'
    if observation['mapq'] < minimum_mapq or observation['mapq'] == 255:
        return 'ambiguous'
    require(observation['contig'] == window['contig'] and observation['reverse'] == window['reverse'],
            'Location contig/orientation mismatch')
    mapping = {}
    reference = observation['start']
    query = 0
    for length, op in cigar(observation['fields'][5]):
        if op in '=XM':
            mapping.update((reference + i, query + i) for i in range(length))
            reference += length
            query += length
        elif op in 'IS':
            query += length
        elif op in 'DN':
            reference += length
        else:
            require(op == 'P', 'Hardclipped location cannot bind full native sequence')
    require(query == len(observation['aligned']), 'Location CIGAR/sequence mismatch')
    a, b = mapping.get(window['ref_start']), mapping.get(window['ref_end'] - 1)
    require(a is not None and b is not None, 'Location window anchors absent')
    b += 1
    original = (len(observation['aligned']) - b, len(observation['aligned']) - a) if observation['reverse'] else (a, b)
    require(original == (window['read_start'], window['read_end']), 'Location/read interval mismatch')
    require(observation['sequence'][original[0]:original[1]] == window['stock'], 'Location/native stock mismatch')
    return 'usable'


def retrieve(window, graph):
    query = graph['query']
    require(graph['schema'] == 'hprc-local-paths/1' and graph['query_index'] == window['query_index']
            and query == dict(sample='GRCh38', contig=window['contig'], start=window['ref_start'], end=window['ref_end']),
            'Wrong graph-path linkage')
    reference = graph['reference']
    require(reference['end'] - reference['start'] == len(reference['sequence'])
            and reference['start'] <= window['ref_start'] < window['ref_end'] <= reference['end'],
            'Graph reference span mismatch')
    require(any(p['is_reference'] and p['both_anchors'] and p['sequence'] == reference['sequence']
                and p['cigar'] == str(len(reference['sequence'])) + 'M' for p in graph['walks']),
            'Graph lacks producer-bound complete reference walk')
    paths = set()
    for walk in graph['walks']:
        if not walk['both_anchors']:
            continue
        require(set(walk['sequence']) <= set('ACGT') and len(walk['sequence']) <= 4096, 'Graph sequence bound')
        r, q = reference['start'], 0
        mapping = {}
        for length, op in cigar(walk['cigar']):
            if op in 'M=X':
                mapping.update((r + i, q + i) for i in range(length))
                r += length
                q += length
            elif op == 'I':
                q += length
            elif op == 'D':
                r += length
            else:
                raise ValueError('Unsupported graph CIGAR')
        require(r == reference['end'] and q == len(walk['sequence']), 'Graph CIGAR span mismatch')
        a, b = mapping.get(window['ref_start']), mapping.get(window['ref_end'] - 1)
        require(a is not None and b is not None, 'Graph core boundary absent')
        sequence = walk['sequence'][a:b + 1]
        if window['reverse']:
            sequence = reverse_complement(sequence)
        require(20 <= len(sequence) <= 128, 'Context length bound')
        paths.add(sequence)
    require(len(paths) <= 32, 'Context unique-path cap exceeded')
    return sorted(paths)


def receipt(path):
    value = read(path)
    require(value['status'] == 'finished' and value['exit'] == 0, 'Incomplete location producer')
    for item in value['pins']:
        check(item)
    directory = Path(value['recorder'])
    for name in ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'):
        actual = pin(directory / name)
        require(actual in value['pins'], 'Location producer lacks complete raw evidence')
    require(shlex.split((directory / 'command.sh').read_text()) == value['argv'], 'Location raw argv mismatch')
    require((directory / 'exit-status.txt').read_text().strip() == '0', 'Location raw exit mismatch')
    require(value['stdout'] == str(directory / 'stdout'), 'Location producer stdout mismatch')
    return value


def historical_auditor(registry):
    expected = next(p for p in registry['sources'] if p['path'].endswith('/tools/catalogue_bridge/verify-receipt.py'))
    helper = Path(check(expected)['path'])
    spec = importlib.util.spec_from_file_location('retained_bridge_auditor', helper)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    require(audit.ROOT == helper.resolve().parents[2], 'Historical auditor source-location contract differs')
    return audit


def inputs(config):
    declared = config['inputs']
    handoff = pin(declared['handoff'])
    require(handoff['sha256'] == declared['handoff_sha256'], 'Unregistered bridge handoff')
    registry = read(handoff['path'])
    package = Path(declared['package'])
    seal_pin = pin(package / 'complete.json')
    require(seal_pin in registry['evidence'], 'Package lacks frozen reviewed ancestry')
    seal = read(seal_pin['path'])
    for item in seal['files']:
        check(item)
    admission = read(package / 'bridge-admission.json')
    audit = historical_auditor(registry)
    proof = audit.contract(package, declared['admission_receipt'])
    original = admission['original']
    cohort_pin = check(original['cohort'])
    require(cohort_pin['sha256'] == declared['original_cohort_sha256'], 'Unregistered original cohort')
    cohort = read(cohort_pin['path'])
    require(cohort['role'] == 'development', 'Only registered development inputs allowed')
    for item in cohort['pins'].values():
        check(item)
    require(cohort['pins']['windows']['sha256'] == declared['plan_sha256'], 'Wrong original plan')
    native = check(original['scoring_baseline_sam'])
    require(native['sha256'] == declared['mapped_sam_sha256'], 'Wrong native location SAM')
    producers = original['scoring_baseline_producers']
    require(len(producers) == 1, 'Unique registered location producer required')
    location_pin = check(producers[0])
    producer = receipt(location_pin['path'])
    require(producer['stdout'] == native['path'], 'Location is not mapped native producer stdout')
    receipts = check(admission['catalogue']['seal']['receipts'])
    return dict(cohort=cohort, original=original, plan=rows(cohort['pins']['windows']['path']),
                decisions=rows(cohort['pins']['decisions']['path']), graph=rows(cohort['pins']['graph_walks']['path']),
                receipts=rows(receipts['path']), native=native, location_pin=location_pin,
                bridge_audit=proof, catalogue_receipts=receipts)


def build_frame(config, admitted, query, directory):
    window = admitted['plan'][query]
    decision = admitted['decisions'][query]
    require(window['read_id'] == decision['read_id'], 'Plan/decision UUID mismatch')
    if decision['status'] == 'excluded':
        return dict(query_index=query, read_id=window['read_id'], status='original_excluded', reason=decision['reason'])
    require(decision['status'] == 'scored', 'Unknown original decision status')
    evidence = admitted['receipts'][query]
    require(evidence['read_id'] == window['read_id'], 'Catalogue receipt UUID mismatch')
    for item in [evidence['score_pin'], evidence['metadata_pin'], evidence['parent_pin'], *evidence['reconstruction_metadata_pins']]:
        check(item)
    tensor = evidence['score_pin']
    require(tensor['sha256'] == decision['score_sha256'] and Path(tensor['path']).name == window['score_file'],
            'Tensor/plan/producer association mismatch')
    if query == 0:
        q0 = config['inputs']['query0']
        require(window['read_id'] == q0['parent'] and tensor == dict(path=q0['tensor'], size=q0['tensor_size'], sha256=q0['tensor_sha256'])
                and window['t_end'] - window['t_start'] == q0['timesteps'], 'Registered query-0 geometry mismatch')
    meta = metadata(evidence['metadata_pin']['path'])
    parent = metadata(evidence['parent_pin']['path'])
    require(meta['format'] == 'DGM1' and parent['format'] == 'DGP1'
            and meta['read_id'] == parent['read_id'] == window['read_id']
            and int(meta['chunk_index']) == window['chunk_index'], 'Native frame metadata association mismatch')
    moves = meta['MOVES']
    require(set(moves) <= {'0', '1'} and moves.count('1') == len(meta['SEQ']) == len(meta['Q']), 'Native SEQ/Q/MOVES mismatch')
    emissions = [i for i, value in enumerate(moves) if value == '1']
    a, b = window['chunk_start'], window['chunk_end']
    require(a >= 4 and b < len(emissions) and meta['SEQ'][a:b] == window['stock']
            and meta['SEQ'][a - 4:a] == window['context']
            and emissions[a] == window['t_start'] and emissions[b] == window['t_end'], 'Native retained attachment mismatch')
    observation = mapped(admitted['native']['path'], window['read_id'])
    require(parent['SEQ'] == observation['sequence'] and parent['Q'] == observation['quality'], 'Original native parent SEQ/Q mismatch')
    status = validate_location(window, observation, config['policy']['minimum_mapq'])
    paths = retrieve(window, admitted['graph'][query])
    if not paths:
        status = 'missing'
    initial = 0
    for base in window['context']:
        initial = initial * 4 + 'ACGT'.index(base)
    identity = dict(plan_sha256=config['inputs']['plan_sha256'], query_index=query, parent=window['read_id'],
                    chunk_index=window['chunk_index'], tensor_sha256=tensor['sha256'], t_start=window['t_start'],
                    t_end=window['t_end'], initial_context=window['context'], initial_state=initial,
                    reverse=int(window['reverse']), contig=window['contig'], ref_start=window['ref_start'], ref_end=window['ref_end'],
                    graph_sha256=admitted['cohort']['pins']['graph_walks']['sha256'],
                    location_receipt_sha256=admitted['location_pin']['sha256'], location_sam_sha256=admitted['native']['sha256'])
    directory = Path(directory)
    directory.mkdir()
    context_path = directory / 'context.tsv'
    tabular(context_path, 'context-paths/1', dict(identity, **{'sequence_' + str(i): seq for i, seq in enumerate(paths)}))
    controls = directory / 'retained-scalar.tsv'
    with controls.open('x') as handle:
        for hypothesis in decision['hypotheses']:
            value = hypothesis['likelihood']
            require(value is None or math.isfinite(value), 'Nonfinite retained scalar control')
            handle.write(hypothesis['sequence'] + '\t' + ('impossible' if value is None else repr(value)) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    frame = dict(identity, location_status=status, stock=window['stock'])
    for prefix, item in [('tensor', tensor), ('metadata', evidence['metadata_pin']), ('context', pin(context_path)),
                         ('location_receipt', admitted['location_pin']), ('location_sam', admitted['native']), ('scalar_controls', pin(controls))]:
        frame.update({prefix + '_' + k: v for k, v in item.items()})
    tabular(directory / 'frame.tsv', 'context-frame/1', frame)
    fresh(directory / 'construction.json', dict(schema='context-frame-construction/1', window=window,
          producer_receipt=evidence, original_plan=admitted['cohort']['pins']['windows'],
          native_location=admitted['native'], location_producer=admitted['location_pin'],
          context_source=admitted['cohort']['pins']['graph_walks'], frame=pin(directory / 'frame.tsv'),
          constructor=pin(__file__), truth_input=False, causal_streaming_qualified=False))
    timesteps = window['t_end'] - window['t_start']
    beam = config['policy']['beam_width']
    work = dict(context_edit_cells=(5 * beam * timesteps * (timesteps + 1) // 2 + 4 * beam * timesteps)
                * sum(len(path) for path in paths),
                guide_transitions=timesteps * 256 * 5,
                scalar_cell_upper=timesteps * (min(timesteps, config['policy']['max_symbols']) + 1)
                * (2 * beam + 1 + len(decision['hypotheses'])),
                interpretation='Conservative operation bounds, not measured wall time or a speed claim')
    fresh(directory / 'work-bound.json', work)
    return dict(query_index=query, read_id=window['read_id'], status='constructed', frame=pin(directory / 'frame.tsv'),
                work_bound=work, work_bound_receipt=pin(directory / 'work-bound.json'))
