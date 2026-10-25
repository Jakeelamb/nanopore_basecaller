#!/usr/bin/env python3
"""Validate sealed model decisions, join private diagnostics, and emit matched complete parents."""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[2]
ATLAS_ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v4')
ORIGINAL_ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v2')
MODEL_IDENTITY = '54e022509ac9735381bd4da1408190c64a5495d183c790dfc50c0442139bb664'
ATLAS_IDENTITY = '695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa'
ORIGINAL_IDENTITY = '7a1b9c6f05597dd70e5eb96c894c2ed9e0cf811c28cc7735354fa1aed1f0164b'
UNITS = (('v5-model-query0-1', 'query0', 0, 1),
         ('v5-model-checkpoint-1', 'checkpoint', 1, 32),
         ('v5-model-all-1', 'all', 32, 368))
PROFILES = tuple((mu, arm) for mu in ('0.001', '0.01')
                 for arm in ('graph', 'none', 'reference', 'wrong'))
RAW_FILES = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')


def require(value, message):
    if not value:
        raise ValueError(message)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    require(Path(value.__file__).resolve() == Path(path).resolve(), 'Imported source location differs')
    return value


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def finite(value):
    result = float(value)
    require(math.isfinite(result), 'Nonfinite retained model field')
    return result


def near(left, right):
    return math.isclose(finite(left), finite(right), rel_tol=0, abs_tol=1e-10)


def table(path):
    with Path(path).open(encoding='ascii', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), 'Malformed TSV header')
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()), 'Malformed TSV row')
            yield row


def raw_receipt(directory, argv, root, boundary):
    directory = Path(directory).resolve()
    require(directory.is_relative_to(root/'logs/context-feedback/recorder-root/logs'), 'Outer recorder location differs')
    pins = {name: boundary.pin(directory/name) for name in RAW_FILES}
    require(shlex.split((directory/'command.sh').read_text()) == argv, 'Outer recorded command differs')
    require((directory/'cwd.txt').read_text().strip() == str(root), 'Outer recorder cwd differs')
    require((directory/'exit-status.txt').read_text().strip() == '0', 'Outer recorder exit failed')
    start, end = ((directory/name).read_text().strip() for name in ('start.txt', 'end.txt'))
    require(start.endswith('Z') and end.endswith('Z') and datetime.fromisoformat(start) <= datetime.fromisoformat(end), 'Outer recorder clocks differ')
    times = {}
    for line in (directory/'time.txt').read_text().splitlines():
        if line.startswith('\t') and ': ' in line:
            key, value = line.strip().split(': ', 1)
            times[key] = value
    require(times.get('Exit status') == '0' and times.get('Command being timed') == '"'+' '.join(argv)+'"', 'Outer GNU time command/exit differs')
    require(finite(times['User time (seconds)']) >= 0 and finite(times['System time (seconds)']) >= 0
            and int(times['Maximum resident set size (kbytes)']) > 0, 'Outer time/RSS evidence incomplete')
    wall = times['Elapsed (wall clock) time (h:mm:ss or m:ss)'].split(':')
    require(len(wall) in (2, 3) and all(finite(part) >= 0 for part in wall), 'Outer elapsed time invalid')
    return pins


def outer_unit(identity, completion, program):
    root, boundary = program.ROOT, program.c
    directory = root/'logs/context-feedback/program-runs'/('run-'+identity)
    terminal = boundary.read(directory/'terminal.json')
    require(terminal['error'] is None and terminal['exit'] == 0, 'Model outer unit failed')
    properties = terminal['proof']['properties']
    require(properties['Result'] == 'success' and properties['ActiveState'] == 'inactive'
            and properties['MainPID'] == properties['ControlPID'] == '0', 'Model outer tree is not terminal success')
    cleanup = boundary.read(directory/'cleanup.json')
    require(cleanup['terminal'] is True, 'Model launcher tree is not terminal')
    start = boundary.read(directory/'start.json')
    boundary.check(start['worker']); boundary.check(start['controller'])
    require(start['cwd'] == str(root), 'Model outer cwd differs')
    command = start['argv']
    at = command.index('--')
    require(Path(command[at+1]).resolve() == root/'scripts/record-command.sh'
            and command[at+2] == identity and command[at+3:], 'Model outer wrapper differs')
    raw_directory = Path((directory/'stdout').read_text().strip())
    raw = raw_receipt(raw_directory, command[at+3:], root, boundary)
    require(boundary.read(raw['stdout']['path']) == dict(completion=completion), 'Outer completion stdout does not bind model unit')
    return [boundary.pin(directory/name) for name in ('start.json', 'terminal.json', 'cleanup.json')]+list(raw.values())


def native_unit(pin, stage, program, sources, cases=None):
    boundary = program.c
    boundary.check(pin)
    directory = Path(pin['path']).parent
    require(program.native(directory, stage, sources) == pin, 'Model native completion differs')
    seal = boundary.read(pin['path'])
    attempt = boundary.read(directory/'attempt.json')
    require(seal['schema'] == 'context-model-native-complete/1'
            and attempt['schema'] == 'context-model-native-attempt/1', 'Model native schema differs')
    require(seal['source'] == attempt['source'], 'Model source snapshots differ')
    expected = [] if cases is None else [cases]
    require(seal['inputs'] == expected, 'Model native input census differs')
    result = boundary.read(seal['result']['path'])
    command = attempt['argv'][1]
    names = [] if command == 'qualify' else ['work.tsv', 'contexts.tsv', 'policies.json']
    if command == 'replay':
        names += ['candidates.tsv', 'decisions.tsv']
    require(len(seal['files']) == len(names)
            and {item['path']: item for item in seal['files']} == {str(directory/name): boundary.pin(directory/name) for name in names}, 'Model native file census differs')
    return directory, command, result


def engineering(program, sources):
    boundary = program.c
    directory = program.ROOT/'results/context-feedback/v5-model-engineering-2'
    completion = boundary.pin(directory/'complete.json')
    evidence = outer_unit(directory.name, completion, program)
    seal = boundary.read(completion['path'])
    require(seal['schema'] == 'context-model-engineering/1' and seal['complete'] is True
            and seal['source_inventory_sha256'] == MODEL_IDENTITY, 'Model engineering identity differs')
    expected_files = [boundary.pin(directory/name) for name in ('start.json', 'build-closure.json')]
    require(seal['files'] == expected_files, 'Model engineering file census differs')
    start = boundary.read(directory/'start.json')
    require(start['sources'] == sources, 'Engineering admitted source census differs')
    boundary.check(start['driver']); boundary.check(seal['binary'])
    names = ('model-cmake-configure', 'model-cmake-build', 'model-format', 'model-ctest',
             'model-native-controls', 'model-build-handoff', 'model-python-controls', 'program-linked-model')
    stages = [program.w.evidence.stage(item, boundary) for item in seal['stages']]
    require(tuple(stage['name'] for stage in stages) == names, 'Model engineering stage census differs')
    producer = stages[4]
    require(producer['argv'] == [seal['binary']['path'], 'qualify', '--output', str(directory/'native-controls')], 'Model controls command differs')
    _, _, controls = native_unit(seal['native'], producer, program, sources)
    negative = {'missing_length_normalizer', 'best_history', 'path_vote_count', 'silent_interleavings',
                'joint_map', 'novel_mass_not_variant_safety'}
    require(controls['synthetic_only'] is True and controls['biological_qualification'] is False
            and controls['assertions'] > 0 and set(controls['negative_controls']) == negative
            and all(controls['negative_controls'].values()), 'Model native controls incomplete')
    stderr = Path(stages[6]['raw']['stderr']['path']).read_text()
    require('Ran 54 tests' in stderr and 'skipped' not in stderr.lower() and stderr.count(' ... ok\n') == 54, 'Model Python controls were not54 skipped0')
    closure = boundary.read(directory/'build-closure.json')
    require(closure['binaries'] == dict(model=seal['binary']) and closure['runtime_libraries'], 'Model actual runtime closure differs')
    for item in [closure['compiler'], closure['cache'], closure['compile_commands'], *closure['runtime_libraries']]:
        boundary.check(item)
    evidence += [completion, *seal['files'], *seal['stages'], seal['native']]
    return completion, seal['binary'], evidence


def read_packet(path, wire):
    cases, pools, bases, candidates = {}, defaultdict(dict), defaultdict(dict), defaultdict(dict)
    with Path(path).open(encoding='ascii') as stream:
        header = stream.readline().rstrip('\n').split('\t')
        require(len(header) == 3 and header[:2] == ['SCHEMA', wire['candidate_schema']], 'Candidate packet header differs')
        for line in stream:
            values = line.rstrip('\n').split('\t')
            require(values[0] in wire['candidate_records'], 'Unknown candidate packet record')
            fields = wire['candidate_records'][values[0]]
            require(len(values) == len(fields)+1, 'Candidate packet width differs')
            row = dict(zip(fields, values[1:])); case_id = row['case_id']
            if values[0] == 'CASE':
                require(case_id not in cases, 'Duplicate model case')
                cases[case_id] = row
            else:
                require(case_id in cases, 'Candidate record precedes case')
                if values[0] == 'CAND':
                    sequence, origins = row['sequence'], int(row['origins'])
                    score = None if row['log_mass'] == '.' else finite(row['log_mass'])
                    old = candidates[case_id].get(sequence)
                    require(old is None or old[1] == score, 'Conflicting retained signal values')
                    candidates[case_id][sequence] = (origins | (0 if old is None else old[0]), score)
                elif values[0] == 'BASE':
                    require(row['role'] not in bases[case_id], 'Duplicate saved baseline')
                    bases[case_id][row['role']] = row
    for case_id, values in candidates.items():
        for sequence, (origins, score) in values.items():
            if origins & (wire['origins']['native'] | wire['origins']['escape']):
                require(score is not None, 'Inference candidate is unscored')
                pools[case_id][digest(sequence)] = (sequence, score)
        require(pools[case_id] and set(bases[case_id]) == set(wire['enums']['baseline_role']), 'Model pool or baseline census differs')
    require(set(cases) == set(pools) == set(bases), 'Model case/pool census differs')
    return header[2], cases, dict(pools), dict(bases)


def binding(row, cases, pool_digests):
    case_id = row['case_id']
    require(case_id in cases, 'Foreign model case')
    case = cases[case_id]
    require(row['parent'] == case['parent'] and row['geometry_sha256'] == case['geometry_sha256']
            and row['pool_sha256'] == pool_digests[case_id], 'Model case/parent/geometry/pool binding differs')
    return case_id


def validate_tables(cases, pools, bases, blocks):
    expected_profiles = {(case_id, mu, arm) for case_id in cases for mu, arm in PROFILES}
    seen, contexts, decisions = defaultdict(set), {}, {}
    pool_digests = {case_id: digest('context-model-primary-pool/1\n'+''.join(sequence+'\t'+format(score, '.17g')+'\n'
                    for sequence, score in sorted(pool.values()))) for case_id, pool in pools.items()}
    for directory, selected in blocks:
        actual_cases = set()
        for row in table(directory/'contexts.tsv'):
            case_id = binding(row, cases, pool_digests)
            require(case_id in selected, 'Context outside sealed slice')
            key = (case_id, row['arm'])
            require(row['arm'] in ('graph', 'none', 'reference', 'wrong') and key not in contexts, 'Duplicate or unknown context assignment')
            contexts[key] = row
        candidate_choices = {}
        for row in table(directory/'candidates.tsv'):
            case_id = binding(row, cases, pool_digests)
            key = (case_id, row['mu'], row['arm'])
            require(case_id in selected and key in expected_profiles, 'Candidate outside sealed profile/slice')
            candidate = row['candidate_sha256']
            require(candidate in pools[case_id] and candidate not in seen[key], 'Missing, duplicate or foreign model candidate')
            sequence, signal = pools[case_id][candidate]
            require(row['sequence'] == sequence and digest(sequence) == candidate and finite(row['signal']) == signal, 'Model candidate sequence or retained signal changed')
            require(row['context_sha256'] == contexts[(case_id, row['arm'])]['context_sha256'], 'Model candidate context differs')
            require(near(row['objective'], signal+finite(row['log_ratio'])), 'Model objective projection differs')
            if row['arm'] == 'none':
                require(finite(row['log_ratio']) == 0 and finite(row['objective']) == signal, 'Disabled model changed a signal score')
            seen[key].add(candidate)
            candidate_choices[(key, candidate)] = (signal, finite(row['objective']))
        for row in table(directory/'decisions.tsv'):
            case_id = binding(row, cases, pool_digests)
            key = (case_id, row['mu'], row['arm'])
            require(case_id in selected and key in expected_profiles and key not in decisions, 'Duplicate, missing or foreign model decision')
            require(row['baseline'] == bases[case_id]['reference_free']['sequence'], 'Matched reference-free baseline differs')
            for choice in ('baseline', 'raw', 'accepted'):
                candidate = row[choice+'_sha256']
                require(candidate == digest(row[choice]) and candidate in pools[case_id], 'Decision choice absent from retained pool')
                signal, objective = candidate_choices[(key, candidate)]
                require(row[choice] == pools[case_id][candidate][0] and finite(row[choice+'_signal']) == signal
                        and near(row[choice+'_objective'], objective), 'Decision component values differ')
            require(near(row['neural_delta'], finite(row['raw_signal'])-finite(row['baseline_signal']))
                    and near(row['objective_delta'], finite(row['raw_objective'])-finite(row['baseline_objective'])), 'Decision delta projection differs')
            if row['arm'] == 'none':
                require(row['accepted'] == row['baseline'] and row['gate'] in ('reference_free_fallback', 'search_bound_abstain', 'no_eligible_finalist_abstain'), 'Disabled model changed matched reference-free output')
            require(row['abstained'] in ('0', '1'), 'Invalid model abstention field')
            decisions[key] = row; actual_cases.add(case_id)
        require(actual_cases == set(selected), 'Native replay case census differs')
    require(set(decisions) == set(seen) == expected_profiles, 'Incomplete eight-profile model coverage')
    require(set(contexts) == {(case_id, arm) for case_id in cases for _, arm in PROFILES}, 'Incomplete context census')
    for key, values in seen.items():
        require(values == set(pools[key[0]]), 'Model arm omitted retained candidates')
    return decisions, contexts


@dataclass
class Corpus:
    program: object
    atlas: object
    cases_pin: dict
    cases: dict
    pools: dict
    bases: dict
    facts: dict
    decisions: dict
    contexts: dict
    evidence: list


def load_corpus():
    program = module('context_model_observer_program', ROOT/'scripts/context-program.py')
    atlas = module('context_model_observer_atlas', ATLAS_ROOT/'scripts/context-program.py')
    require(program.ROOT == ROOT and program.c.ROOT == ROOT and atlas.ROOT == atlas.c.ROOT == ATLAS_ROOT, 'Original program source-location contract differs')
    sources = program.sources()
    require(program.identity(sources) == MODEL_IDENTITY and atlas.identity(atlas.sources()) == ATLAS_IDENTITY, 'Frozen scorer or atlas source differs')
    qualification, binary, evidence = engineering(program, sources)
    prepared = atlas.completed(ATLAS_ROOT/'results/context-feedback/v4-prepare-all-1', 'prepare')
    descriptor = prepared['summary']['prepared']
    manifest = program.c.read(descriptor['manifest']['path'])
    inference = program.c.read(manifest['inference']['path'])
    wire = program.c.read(ROOT/'tools/context_decoder/study/wire-schema.json')
    header, cases, pools, bases = read_packet(descriptor['cases']['path'], wire)
    require(header == manifest['inference']['sha256'] and len(cases) == 368, 'Qualified model packet identity/census differs')
    facts = {item['case']['case_id']: item for item in inference['cases']}
    require(set(facts) == set(cases) and len(facts) == len(inference['cases']), 'Inference fact census differs')
    for case_id, case in cases.items():
        require(all(str(facts[case_id]['case'][key]) == value for key, value in case.items()), 'Packet and bound inference facts differ')
    ordered = sorted(cases); blocks = []
    for identity, phase, begin, end in UNITS:
        directory = ROOT/'results/context-feedback'/identity
        completion = program.c.pin(directory/'complete.json')
        evidence += outer_unit(identity, completion, program)+[completion]
        seal = program.c.read(completion['path'])
        require(seal['schema'] == 'context-model-unit/1' and seal['complete'] is True and seal['phase'] == phase
                and (seal['begin'], seal['end']) == (begin, end) and seal['cases'] == descriptor['cases']
                and seal['source_inventory_sha256'] == MODEL_IDENTITY and seal['qualification'] == qualification
                and seal['prepared'] == prepared['outer'], 'Model unit source/input/slice differs')
        expected_dependencies = [] if phase == 'query0' else ['v5-model-query0-1'] if phase == 'checkpoint' else ['v5-model-checkpoint-1']
        require(seal['dependencies'] == expected_dependencies, 'Model unit dependency census differs')
        expected_files = [program.c.pin(directory/name) for name in ('start.json', 'plan.json')]
        require(seal['files'] == expected_files, 'Model unit file census differs')
        start = program.c.read(directory/'start.json')
        require(start['sources'] == sources and start['qualification'] == qualification and start['prepared'] == prepared['outer'] and start['phase'] == phase, 'Model unit admitted source/input differs')
        program.c.check(start['driver']); program.c.check(seal['price'])
        plan = program.c.read(directory/'plan.json')
        require(plan['cases'] == descriptor['cases'] and plan['price'] == seal['price'] and (plan['begin'], plan['end']) == (begin, end), 'Model batch plan differs')
        stages = [program.w.evidence.stage(item, program.c) for item in seal['stages']]
        require(len(stages) == len(seal['native']) == len(plan['batches'])+(phase == 'query0'), 'Model producer/stage census differs')
        cursor = begin
        expected = []
        if phase == 'query0':
            expected.append(('price', directory/'price-all', ['--cases', descriptor['cases']['path'], '--cases-sha256', descriptor['cases']['sha256'], '--output', str(directory/'price-all')], None))
        for index, count, cells in plan['batches']:
            require(index == cursor and count > 0 and 0 < cells <= 25000000 and index+count <= end, 'Model batch overlap/gap/work cap differs')
            target = directory/('slice-'+str(index))
            expected.append(('replay', target, ['--cases', descriptor['cases']['path'], '--cases-sha256', descriptor['cases']['sha256'], '--begin', str(index), '--count', str(count), '--max-cells', '25000000', '--output', str(target)], (index, count, cells)))
            cursor += count
        require(cursor == end, 'Model batch coverage incomplete')
        for pin, stage, (verb, target, options, part) in zip(seal['native'], stages, expected):
            require(stage['argv'] == [binary['path'], verb, *options] and pin['path'] == str(target/'complete.json'), 'Model native intended command differs')
            actual, command, result = native_unit(pin, stage, program, sources, descriptor['cases'])
            require(actual == target and command == verb and result['candidate_manifest'] == header and result['packet_cases'] == 368 and result['biological_qualification'] is False, 'Model native result binding differs')
            if part is not None:
                index, count, cells = part
                require(not result['price_only'] and result['slice_begin'] == index and result['slice_cases'] == count and result['total_cells'] == cells, 'Model native executed slice/work differs')
                blocks.append((actual, ordered[index:index+count]))
            else:
                require(result['price_only'] is True, 'Model price performed inference')
        evidence += [*seal['files'], *seal['native'], *seal['stages'], seal['price']]
    decisions, contexts = validate_tables(cases, pools, bases, blocks)
    evidence += [prepared['outer'], descriptor['completion'], descriptor['manifest'], descriptor['cases'], manifest['inference']]
    return Corpus(program, atlas, descriptor['cases'], cases, pools, bases, facts, decisions, contexts, evidence)


def unique_rows(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        require(key not in result, 'Duplicate diagnostic join row')
        result[key] = row
    return result


def joined_annotation(corpus, candidate_rows, event_rows):
    labels = unique_rows(candidate_rows, ('case_id', 'candidate_sha256', 'mask'))
    events = unique_rows(event_rows, ('case_id', 'candidate_sha256', 'event_id'))
    for (case_id, candidate, mask), row in labels.items():
        require(case_id in corpus.cases and mask in ('100', '500') and row['parent'] == corpus.cases[case_id]['parent']
                and row['domain'] == corpus.cases[case_id]['domain'] and digest(row['sequence']) == candidate, 'Foreign candidate diagnostic binding')
        require(row['vs_reference_free'] in ('helpful', 'harmful', 'neutral', 'unresolved', 'no_exposure'), 'Unknown candidate diagnostic effect')
    event_ids = defaultdict(set)
    for (case_id, candidate, event), row in events.items():
        require(case_id in corpus.cases and row['parent'] == corpus.cases[case_id]['parent'] and row['domain'] == corpus.cases[case_id]['domain'], 'Foreign private diagnostic binding')
        event_ids[case_id].add(event)
        require(row['call'] in ('alt', 'ref', 'other', 'unresolved') and row['native_call'] in ('alt', 'ref', 'other', 'unresolved'), 'Unknown private call')
        require(all(row[key] in ('0', '1') for key in ('alt_to_ref', 'exact_alt_support_loss', 'alt_consequence_unresolved')), 'Unknown private consequence flag')
        expected = (row['native_call'] == 'alt' and row['call'] == 'ref',
                    row['native_call'] == 'alt' and row['call'] in ('ref', 'other'),
                    row['native_call'] == 'alt' and row['call'] == 'unresolved')
        require(tuple(row[key] == '1' for key in ('alt_to_ref', 'exact_alt_support_loss', 'alt_consequence_unresolved')) == expected, 'Private consequence projection differs')
    require(set(event_ids) == {case_id for case_id, case in corpus.cases.items() if case['domain'] != 'ordinary'}, 'Private event case census differs')
    effects, private, changes = Counter(), Counter(), Counter()
    effect_rows, private_rows = [], []
    for (case_id, mu, arm), decision in sorted(corpus.decisions.items()):
        case = corpus.cases[case_id]; prefix = (mu, arm, case['domain'])
        changes[prefix+('cases',)] += 1
        changes[prefix+('proposed',)] += decision['raw_sha256'] != decision['baseline_sha256']
        changes[prefix+('accepted',)] += decision['accepted_sha256'] != decision['baseline_sha256']
        changes[prefix+('abstained',)] += decision['abstained'] == '1'
        for mask in ('100', '500'):
            values = {}
            for choice in ('baseline', 'raw', 'accepted'):
                key = (case_id, decision[choice+'_sha256'], mask)
                require(key in labels, 'Model choice lacks qualified candidate label')
                row = labels[key]
                require(row['sequence'] == decision[choice], 'Model diagnostic sequence join differs')
                values[choice] = row['vs_reference_free']
                if choice != 'baseline':
                    effects[prefix+(mask, choice, row['vs_reference_free'])] += 1
            require(values['baseline'] in ('neutral', 'no_exposure'), 'Reference-free diagnostic baseline differs')
            effect_rows.append(dict(case_id=case_id, parent=case['parent'], domain=case['domain'], mu=mu, arm=arm,
                                    mask=mask, gate=decision['gate'], baseline_effect=values['baseline'],
                                    raw_effect=values['raw'], accepted_effect=values['accepted']))
        for event in sorted(event_ids[case_id]):
            rows = {}
            for choice in ('baseline', 'raw', 'accepted'):
                key = (case_id, decision[choice+'_sha256'], event)
                require(key in events, 'Model choice lacks qualified private label')
                rows[choice] = events[key]
            require(rows['baseline']['call'] == rows['baseline']['free_call'], 'Private matched baseline differs')
            for choice in ('raw', 'accepted'):
                row = rows[choice]
                private[prefix+(choice, row['native_call'], row['call'])] += 1
                private_rows.append(dict(case_id=case_id, parent=case['parent'], domain=case['domain'], event_id=event,
                    mu=mu, arm=arm, choice=choice, baseline_call=rows['baseline']['call'], call=row['call'],
                    alt_to_ref=row['alt_to_ref'], exact_alt_support_loss=row['exact_alt_support_loss'],
                    unresolved=row['alt_consequence_unresolved'], changed=decision[choice+'_sha256'] != decision['baseline_sha256']))
    return dict(effects=effects, private=private, changes=changes, effect_rows=effect_rows, private_rows=private_rows)


def write_table(path, rows, fields):
    with Path(path).open('x', encoding='ascii', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
        stream.flush(); os.fsync(stream.fileno())


def count_rows(values, fields):
    return [dict(zip(fields, key), count=count) for key, count in sorted(values.items())]


def annotate(corpus, output):
    atlas = corpus.atlas
    completed = atlas.completed(ATLAS_ROOT/'results/context-feedback/v4-evaluate-all-1', 'evaluate')
    directory = ATLAS_ROOT/'results/context-feedback/v4-evaluate-all-1/native-atlas'
    result = joined_annotation(corpus, table(directory/'candidates.tsv'), table(directory/'private.tsv'))
    write_table(output/'effects.tsv', result['effect_rows'], ('case_id', 'parent', 'domain', 'mu', 'arm', 'mask', 'gate', 'baseline_effect', 'raw_effect', 'accepted_effect'))
    write_table(output/'private.tsv', result['private_rows'], ('case_id', 'parent', 'domain', 'event_id', 'mu', 'arm', 'choice', 'baseline_call', 'call', 'alt_to_ref', 'exact_alt_support_loss', 'unresolved', 'changed'))
    summary = dict(schema='context-model-annotation/1', cases=len(corpus.cases), profiles=len(corpus.decisions),
                   candidate_pool='native_plus_escape_exact_retained_signal', none_identity='matched_reference_free',
                   development_only=True, biological_qualification=False,
                   changes=count_rows(result['changes'], ('mu', 'arm', 'domain', 'measure')),
                   effects=count_rows(result['effects'], ('mu', 'arm', 'domain', 'mask', 'choice', 'effect')),
                   private=count_rows(result['private'], ('mu', 'arm', 'domain', 'choice', 'native_call', 'call')),
                   denominators=dict(active_parents=len({case['parent'] for case in corpus.cases.values()}),
                                     ordinary_cases=sum(case['domain'] == 'ordinary' for case in corpus.cases.values()),
                                     private_cases=sum(case['domain'] != 'ordinary' for case in corpus.cases.values()),
                                     context_modes_share_biological_cases=True))
    corpus.program.c.fresh(output/'result.json', summary)
    return [completed['outer'], corpus.program.c.pin(directory/'complete.json')], ['result.json', 'effects.tsv', 'private.tsv']


def validate_edits(sequence, edits):
    cursor, previous = 0, None
    for edit in sorted(edits, key=lambda item: item['start']):
        a, b = edit['start'], edit['end']
        require(type(a) is int and type(b) is int and cursor <= a <= b <= len(sequence)
                and a != previous, 'Overlapping/out-of-range model parent edits')
        require(sequence[a:b] == edit['stock'] and edit['replacement'] != edit['stock'], 'Edit/native attachment or no-op ledger differs')
        require(isinstance(edit['replacement'], str) and set(edit['replacement']) <= set('ACGT'), 'Invalid model replacement DNA')
        cursor, previous = b, a


def sam_bytes(parents, originals, edits, observer):
    require(len(parents) == len(set(parents)) == len(originals), 'Complete-parent census differs')
    require(set(originals) == set(parents) and all(edit['parent'] in originals for edit in edits), 'Foreign edited parent')
    lines = ['@HD\tVN:1.6\tSO:unknown']
    for parent in parents:
        native = originals[parent]
        changes = [edit for edit in edits if edit['parent'] == parent]
        validate_edits(native['sequence'], changes)
        seq, qual = observer.splice(native['sequence'], native['quality'], changes)
        require((seq, qual) == observer.independent_splice(native['sequence'], native['quality'], changes), 'Independent whole-parent reconstruction differs')
        lines.append('\t'.join((parent, '4', '*', '0', '0', '*', '*', '0', '0', seq, qual)))
    return ('\n'.join(lines)+'\n').encode('ascii')


def deduplicate(contents):
    canonical, aliases = {}, {}
    for arm, data in sorted(contents.items()):
        key = hashlib.sha256(data).hexdigest()
        if key in canonical:
            original, old = canonical[key]
            require(old == data, 'Output digest collision or incorrect alias')
            aliases[arm] = original
        else:
            canonical[key] = (arm, data); aliases[arm] = arm
    return {arm: data for arm, data in canonical.values()}, aliases


def emission_material(corpus):
    boundary = corpus.program.c
    observer = module('context_model_original_observer', ORIGINAL_ROOT/'tools/context_decoder/observe.py')
    original = observer.w
    require(observer.ROOT == observer.c.ROOT == original.ROOT == ORIGINAL_ROOT
            and original.inventory_hash(original.sources()) == ORIGINAL_IDENTITY, 'Original emitter source-location identity differs')
    reference_free = observer.completed_producer(ORIGINAL_ROOT/'results/context-feedback/v2-observe-full-1/reference_free/complete.json', 'arm', 'ordinary')
    for stage in reference_free['stages']:
        original.evidence.stage(stage, original.c)
    emission = observer.completed_producer(reference_free['manifest']['path'], 'prepare', 'ordinary')
    for item in (emission['controls'], emission['snapshot'], reference_free['mapped']):
        boundary.check(item)
    snapshot = boundary.read(emission['snapshot']['path'])
    for name in ('parents', 'native'):
        boundary.check(snapshot[name])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    require(len(parents) == len(set(parents)) == 64, 'Original64-parent census differs')
    parsed = corpus.atlas.packet_boundary().sam_index(snapshot['native']['path'], corpus.atlas.c)
    originals = {parent: parsed[parent] for parent in parents}
    old_free = next(arm for arm in emission['arms'] if arm['arm'] == 'reference_free')
    boundary.check(old_free['sam'])
    return observer, parents, originals, emission, reference_free, snapshot, old_free


def edits_for(corpus, mu, arm, originals):
    ordinary = {case_id: case for case_id, case in corpus.cases.items() if case['domain'] == 'ordinary'}
    require(len(ordinary) == 311, 'Ordinary whole-parent edit census differs')
    edits = []
    for case_id, case in sorted(ordinary.items()):
        parent = originals[case['parent']]
        a, b = int(case['owned_start']), int(case['owned_end'])
        require(parent['sequence'][a:b] == case['native'], 'Model center/native complete-parent join differs')
        choice = corpus.decisions[(case_id, mu, arm)]
        if choice['accepted'] != case['native']:
            edits.append(dict(case_id=case_id, parent=case['parent'], geometry_sha256=case['geometry_sha256'],
                              start=a, end=b, stock=case['native'], replacement=choice['accepted'],
                              candidate_sha256=choice['accepted_sha256']))
    return edits


def emit(corpus, output):
    boundary = corpus.program.c
    observer, parents, originals, emission, reference_free, snapshot, old_free = emission_material(corpus)
    contents, ledgers = {}, {}
    old_bytes = Path(old_free['sam']['path']).read_bytes()
    for mu, arm in PROFILES:
        name = 'mu'+mu+'-'+arm
        edits = edits_for(corpus, mu, arm, originals)
        data = sam_bytes(parents, originals, edits, observer)
        if arm == 'none':
            require(data == old_bytes, 'None complete-parent SAM differs from historical reference-free producer')
        contents[name] = data; ledgers[name] = edits
    disabled = sam_bytes(parents, originals, [], observer)
    canonical, aliases = deduplicate(contents)
    for name, data in canonical.items():
        with (output/(name+'.sam')).open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    with (output/'disabled-edit.sam').open('xb') as stream:
        stream.write(disabled); stream.flush(); os.fsync(stream.fileno())
    arms = []
    for name in sorted(contents):
        source = aliases[name]
        pin = boundary.pin(output/(source+'.sam'))
        arms.append(dict(arm=name, canonical_arm=source, sam=pin, identical_bytes_alias=name != source,
                         edits=ledgers[name], parents=64,
                         historical_reference_free=reference_free['mapped'] if contents[name] == old_bytes else None))
    result = dict(schema='context-model-parent-emission/1', arms=arms, ordinary_cases=311, parents=64,
                  unique_outputs=len(canonical), disabled_edit=boundary.pin(output/'disabled-edit.sam'),
                  snapshot=emission['snapshot'], historical_emission=reference_free['manifest'],
                  historical_reference_free_mapping=boundary.pin(ORIGINAL_ROOT/'results/context-feedback/v2-observe-full-1/reference_free/complete.json'),
                  source=boundary.pin(__file__), quality='Changed centers carry uncalibrated !; unchanged SEQ/Q spans preserve native bytes.',
                  private_frames_applied=False, development_only=True, biological_qualification=False)
    boundary.fresh(output/'result.json', result)
    files = ['result.json', 'disabled-edit.sam']+[name+'.sam' for name in sorted(canonical)]
    evidence = [reference_free['manifest'], emission['snapshot'], snapshot['parents'], snapshot['native'], old_free['sam'],
                boundary.pin(ORIGINAL_ROOT/'results/context-feedback/v2-observe-full-1/reference_free/complete.json')]
    return evidence, files


def completed(completion, phase):
    require(phase in ('annotate', 'emit'), 'Unknown observer completion phase')
    boundary = module('context_model_completed_boundary', ROOT/'tools/context_decoder/context_inputs.py')
    boundary.check(completion)
    directory = Path(completion['path']).parent
    require(directory.is_relative_to(ROOT/'results/context-feedback')
            and Path(completion['path']) == directory/'complete.json', 'Observer completion location differs')
    seal = boundary.read(completion['path'])
    require(seal['schema'] == 'context-model-observer-complete/1' and seal['complete'] is True
            and seal['phase'] == phase and seal['source'] == boundary.pin(__file__)
            and seal['biological_qualification'] is False, 'Observer completion source/phase differs')
    boundary.check(seal['attempt'])
    require(seal['attempt']['path'] == str(directory/'attempt.json'), 'Observer attempt location differs')
    attempt = boundary.read(seal['attempt']['path'])
    require(attempt['source'] == seal['source'] and attempt['phase'] == phase
            and attempt['inference_source_identity'] == MODEL_IDENTITY, 'Observer attempt source differs')
    argv = attempt['argv']
    require(len(argv) == 4 and Path(argv[0]).resolve() == Path(__file__).resolve()
            and argv.count(phase) == argv.count('--output') == 1
            and Path(argv[argv.index('--output')+1]).resolve() == directory, 'Observer attempt command/output differs')
    require(len({item['path'] for item in seal['evidence']}) == len(seal['evidence']), 'Observer evidence census duplicates')
    for item in seal['evidence']:
        boundary.check(item)
    require(len({item['path'] for item in seal['files']}) == len(seal['files']), 'Observer output census duplicates')
    file_map = {item['path']: item for item in seal['files']}
    require(str(directory/'result.json') in file_map, 'Observer result is missing')
    result_pin = file_map[str(directory/'result.json')]
    boundary.check(result_pin); result = boundary.read(result_pin['path'])
    expected = ['result.json', 'effects.tsv', 'private.tsv']
    if phase == 'emit':
        arms = result['arms']
        names = {'mu'+mu+'-'+arm for mu, arm in PROFILES}
        require(len(arms) == 8 and {arm['arm'] for arm in arms} == names
                and result['parents'] == 64 and result['ordinary_cases'] == 311 and result['private_frames_applied'] is False, 'Emitted arm/parent census differs')
        by_name = {arm['arm']: arm for arm in arms}
        canonical = {arm['canonical_arm'] for arm in arms}
        require(len(canonical) == result['unique_outputs'], 'Emitted unique-output census differs')
        expected = ['result.json', 'disabled-edit.sam']+[name+'.sam' for name in sorted(canonical)]
        require(result['disabled_edit'] == boundary.pin(directory/'disabled-edit.sam'), 'Disabled edit output differs')
        for arm in arms:
            name = arm['canonical_arm']
            require(name in by_name and by_name[name]['canonical_arm'] == name
                    and arm['sam'] == by_name[name]['sam'] == boundary.pin(directory/(name+'.sam'))
                    and arm['identical_bytes_alias'] == (arm['arm'] != name) and arm['parents'] == 64, 'Output alias lacks exact canonical bytes')
    require(len(seal['files']) == len(expected)
            and {item['path']: item for item in seal['files']} == {str(directory/name): boundary.pin(directory/name) for name in expected}, 'Observer output file census differs')
    corpus = load_corpus()
    require(seal['cases'] == corpus.cases_pin, 'Observer consumed inference packet differs')
    evidence = {item['path']: item for item in seal['evidence']}
    require(all(evidence.get(item['path']) == item for item in corpus.evidence), 'Observer lost model ancestry')
    if phase == 'emit':
        _, _, _, emission, reference_free, _, old_free = emission_material(corpus)
        require(result['historical_emission'] == reference_free['manifest'] and result['snapshot'] == emission['snapshot'], 'Emitted historical ancestry differs')
        for arm in result['arms']:
            if arm['historical_reference_free'] is not None:
                require(arm['historical_reference_free'] == reference_free['mapped']
                        and Path(arm['sam']['path']).read_bytes() == Path(old_free['sam']['path']).read_bytes(), 'Historical mapping alias lacks exact emitted bytes')
    else:
        atlas = corpus.atlas.completed(ATLAS_ROOT/'results/context-feedback/v4-evaluate-all-1', 'evaluate')
        require(evidence.get(atlas['outer']['path']) == atlas['outer'], 'Observer lost diagnostic ancestry')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('annotate', 'emit'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT/'results/context-feedback') and output != ROOT/'results/context-feedback', 'Observer output outside owned results')
    output.mkdir()
    c = module('context_model_observation_boundary', ROOT/'tools/context_decoder/context_inputs.py')
    source = c.pin(__file__)
    c.fresh(output/'attempt.json', dict(schema='context-model-observer-attempt/1', source=source,
                                      argv=os.sys.argv, phase=args.phase, inference_source_identity=MODEL_IDENTITY,
                                      external_whole_worker_supervision_required=True))
    corpus = load_corpus()
    evidence, files = annotate(corpus, output) if args.phase == 'annotate' else emit(corpus, output)
    c.check(source)
    unique = {item['path']: item for item in corpus.evidence+evidence}
    require(all(unique[item['path']] == item for item in corpus.evidence+evidence), 'Conflicting observer ancestry pins')
    c.fresh(output/'complete.json', dict(schema='context-model-observer-complete/1', complete=True, phase=args.phase,
            source=source, cases=corpus.cases_pin, attempt=c.pin(output/'attempt.json'), evidence=list(unique.values()),
            files=[c.pin(output/name) for name in files], biological_qualification=False))
    descriptor = os.open(output, os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(json.dumps(dict(completion=c.pin(output/'complete.json'))))


if __name__ == '__main__':
    main()
