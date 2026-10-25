"""Join frozen decision outputs to retained labels and reconstruct ordinary parents."""
from collections import Counter
import hashlib
import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('decision_observer_boundary', ROOT/'tools/context_decision/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
c = b.c
ARMS = ('raw_veto_escape', 'raw_veto_partial', 'reference_free', 'disabled_edits',
        'feasible_escape', 'feasible_partial', 'zero_weight_escape', 'zero_weight_partial')


def dna_digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def write_table(path, rows, fields):
    text = '\t'.join(fields)+'\n'
    for row in rows:
        values = [str(row[field]) for field in fields]
        c.require(all('\t' not in value and '\n' not in value for value in values), 'Invalid TSV value')
        text += '\t'.join(values)+'\n'
    with Path(path).open('xb') as stream:
        stream.write(text.encode('ascii'))


def read_cases(packet):
    wire = c.read(b.STUDY/'wire-schema.json')['candidate_records']
    cases, candidates = {}, {}
    for line in Path(packet['path']).read_text(encoding='ascii').splitlines()[1:]:
        fields = line.split('\t')
        if fields[0] == 'CASE':
            row = dict(zip(wire['CASE'], fields[1:], strict=True))
            c.require(row['case_id'] not in cases, 'Duplicate case')
            cases[row['case_id']] = row
        elif fields[0] == 'CAND':
            row = dict(zip(wire['CAND'], fields[1:], strict=True))
            key = (row['case_id'], dna_digest(row['sequence']))
            c.require(key not in candidates, 'Duplicate candidate')
            candidates[key] = row
    c.require(len(cases) == 368, 'Complete packet case census differs')
    return cases, candidates


def frozen_choices(directories, summaries, config):
    atlas, prepared, packet = b.qualified_packet(config)
    cases, candidates = read_cases(packet)
    decisions = {}
    c.require([summary['scope'] for summary in summaries] == ['query0', 'first32', 'remaining'],
              'Disjoint successful inference scope order differs')
    evidence = [prepared['outer']]
    for directory, summary in zip(directories, summaries, strict=True):
        c.require(summary['prepared'] == prepared['outer'] and len(summary['native']) == 1,
                  'Inference prepared custody differs')
        evidence.append(c.pin(directory/'execution-complete.json'))
        completion = c.read(summary['native'][0]['path'])
        result = c.read(completion['result']['path'])
        c.require(result['historical_replay'] is True and result['truth_available'] is False
                  and result['packet_cases'] == 368, 'Inference replay/truth contract differs')
        table_pin = next(pin for pin in completion['files'] if pin['path'].endswith('/decisions.tsv'))
        c.check(table_pin)
        evidence.append(table_pin)
        for row in b.table(table_pin['path']):
            key = (row['case_id'], row['arm'])
            c.require(key not in decisions and row['case_id'] in cases and row['arm'] in ARMS,
                      'Duplicate or foreign decision')
            case = cases[row['case_id']]
            c.require(row['domain'] == case['domain'] and row['abstained'] in ('0', '1'),
                      'Decision domain/abstention differs')
            for role in ('proposed', 'accepted'):
                sequence, digest = row[role], row[role+'_sha256']
                candidate = candidates.get((row['case_id'], digest))
                c.require(digest == dna_digest(sequence) and candidate is not None and
                          candidate['sequence'] == sequence, 'Decision/candidate DNA join differs')
                c.require(candidate["log_mass"] != "." and abs(float(candidate["log_mass"]) - float(row[role+"_log_mass"])) <= 1e-11,
                          "Decision neural score differs from retained scored candidate")
                c.require(all(math.isfinite(float(row[role+'_'+name])) for name in ('log_mass', 'potential', 'objective')),
                          'Nonfinite decision fields')
            decisions[key] = row
    c.require(set(decisions) == {(case, arm) for case in cases for arm in ARMS}, 'Decision output census differs')
    for case_id, case in cases.items():
        free = decisions[(case_id, 'reference_free')]['accepted']
        c.require(decisions[(case_id, 'disabled_edits')]['accepted'] == case['native'], 'Disabled edit identity differs')
        for arm in ('zero_weight_escape', 'zero_weight_partial'):
            c.require(decisions[(case_id, arm)]['accepted'] == free, 'Zero-weight matched free identity differs')
    return atlas, cases, decisions, evidence


def annotate(atlas, cases, decisions, output):
    complete = atlas.completed(b.ATLAS/'results/context-feedback/v4-evaluate-all-1', 'evaluate')
    directory = b.ATLAS/'results/context-feedback/v4-evaluate-all-1/native-atlas'
    candidate_pin, private_pin = c.pin(directory/'candidates.tsv'), c.pin(directory/'private.tsv')
    labels = {}
    for row in b.table(candidate_pin['path']):
        key = (row['case_id'], row['candidate_sha256'], row['mask'])
        c.require(key not in labels and row['case_id'] in cases, 'Atlas candidate label census differs')
        c.require(dna_digest(row['sequence']) == row['candidate_sha256'], 'Atlas DNA digest differs')
        labels[key] = row
    private = {}
    for row in b.table(private_pin['path']):
        key = (row['case_id'], row['candidate_sha256'])
        private.setdefault(key, []).append(row)
    effects, events = [], []
    for (case_id, arm), choice in sorted(decisions.items()):
        for role in ('proposed', 'accepted'):
            digest = choice[role+'_sha256']
            for mask in ('100', '500'):
                label = labels[(case_id, digest, mask)]
                effects.append(dict(case_id=case_id, domain=choice['domain'], arm=arm, choice=role,
                    candidate_sha256=digest, mask=mask, vs_native=label['vs_native'],
                    vs_reference_free=label['vs_reference_free'], exposure=label['exposure'],
                    boundary_resolved=label['boundary_resolved']))
            if choice['domain'] != 'ordinary':
                for event in private[(case_id, digest)]:
                    events.append(dict(event, arm=arm, choice=role))
    write_table(output/'effects.tsv', effects, ('case_id', 'domain', 'arm', 'choice', 'candidate_sha256',
                'mask', 'vs_native', 'vs_reference_free', 'exposure', 'boundary_resolved'))
    c.require(events, 'No private diagnostic labels joined')
    write_table(output/'private.tsv', events, (*events[0].keys(),))
    summary = Counter((row['domain'], row['arm'], row['choice'], row['mask'], row['vs_reference_free']) for row in effects)
    c.fresh(output/'observation.json', dict(schema='context-decision-observation/1', truth_join_after_inference=True,
            counts=[dict(zip(('domain', 'arm', 'choice', 'mask', 'vs_reference_free'), key), cases=count)
                    for key, count in sorted(summary.items())], biological_qualification=False,
            evidence=[complete['outer'], candidate_pin, private_pin]))


def validate_edits(sequence, edits):
    cursor, previous = 0, None
    for edit in sorted(edits, key=lambda item: item['start']):
        start, end = edit['start'], edit['end']
        c.require(type(start) is int and type(end) is int and cursor <= start <= end <= len(sequence)
                  and start != previous, 'Overlapping/out-of-range parent edits')
        c.require(sequence[start:end] == edit['stock'] and edit['replacement'] != edit['stock'],
                  'Native attachment/no-op edit ledger differs')
        c.require(isinstance(edit['replacement'], str) and set(edit['replacement']) <= set('ACGT'), 'Invalid replacement DNA')
        cursor, previous = end, start


def sam_bytes(parents, originals, edits, observer):
    c.require(len(parents) == len(set(parents)) == len(originals) and set(originals) == set(parents), 'Parent census differs')
    c.require(all(edit['parent'] in originals for edit in edits), 'Foreign edited parent')
    lines = ['@HD\tVN:1.6\tSO:unknown']
    for parent in parents:
        native = originals[parent]
        changes = [edit for edit in edits if edit['parent'] == parent]
        validate_edits(native['sequence'], changes)
        seq, qual = observer.splice(native['sequence'], native['quality'], changes)
        c.require((seq, qual) == observer.independent_splice(native['sequence'], native['quality'], changes),
                  'Independent whole-parent reconstruction differs')
        c.require(len(seq) == len(qual), 'Spliced SEQ/Q length differs')
        if not changes:
            c.require((seq, qual) == (native['sequence'], native['quality']), 'Disabled native SEQ/Q identity differs')
        lines.append('\t'.join((parent, '4', '*', '0', '0', '*', '*', '0', '0', seq, qual)))
    return ('\n'.join(lines)+'\n').encode('ascii')


def deduplicate(contents):
    known, aliases = {}, {}
    for arm, data in sorted(contents.items()):
        digest = hashlib.sha256(data).hexdigest()
        if digest in known:
            name, old = known[digest]
            c.require(old == data, 'SAM digest collision')
            aliases[arm] = name
        else:
            known[digest] = (arm, data)
            aliases[arm] = arm
    return dict(known.values()), aliases


def emit(atlas, cases, decisions, output):
    observer = b.module('decision_original_observer', b.ORIGINAL/'tools/context_decoder/observe.py')
    original = observer.w
    c.require(observer.ROOT == observer.c.ROOT == original.ROOT == b.ORIGINAL
              and original.inventory_hash(original.sources()) == b.ORIGINAL_ID, 'Original observer ROOT/source differs')
    free = observer.completed_producer(b.ORIGINAL/'results/context-feedback/v2-observe-full-1/reference_free/complete.json', 'arm', 'ordinary')
    for stage in free['stages']:
        original.evidence.stage(stage, original.c)
    emission = observer.completed_producer(free['manifest']['path'], 'prepare', 'ordinary')
    for pin in (emission['controls'], emission['snapshot'], free['mapped']):
        c.check(pin)
    snapshot = c.read(emission['snapshot']['path'])
    for name in ('parents', 'native'):
        c.check(snapshot[name])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    c.require(len(parents) == len(set(parents)) == 64, 'Original64 parent census differs')
    parsed = atlas.packet_boundary().sam_index(snapshot['native']['path'], atlas.c)
    originals = {parent: parsed[parent] for parent in parents}
    old_free = next(arm for arm in emission['arms'] if arm['arm'] == 'reference_free')
    c.check(old_free['sam'])
    old_bytes = Path(old_free['sam']['path']).read_bytes()
    ordinary = {key: case for key, case in cases.items() if case['domain'] == 'ordinary'}
    c.require(len(ordinary) == 311, 'Ordinary case census differs')
    contents, ledgers = {}, {}
    for arm in ARMS:
        edits = []
        for case_id, case in sorted(ordinary.items()):
            start, end = int(case['owned_start']), int(case['owned_end'])
            c.require(originals[case['parent']]['sequence'][start:end] == case['native'], 'Complete-parent native attachment differs')
            choice = decisions[(case_id, arm)]
            if choice['accepted'] != case['native']:
                edits.append(dict(case_id=case_id, parent=case['parent'], geometry_sha256=case['geometry_sha256'],
                    start=start, end=end, stock=case['native'], replacement=choice['accepted'],
                    candidate_sha256=choice['accepted_sha256']))
        contents[arm] = sam_bytes(parents, originals, edits, observer)
        ledgers[arm] = edits
        if arm in ('reference_free', 'zero_weight_escape', 'zero_weight_partial'):
            c.require(contents[arm] == old_bytes, 'Matched free complete-parent SAM bytes differ')
    canonical, aliases = deduplicate(contents)
    for arm, data in canonical.items():
        with (output/(arm+'.sam')).open('xb') as stream:
            stream.write(data)
    c.fresh(output/'emission.json', dict(schema='context-decision-parent-emission/1', parents=64,
        ordinary_cases=311, private_frames_applied=False, snapshot=emission['snapshot'],
        historical_emission=free['manifest'], historical_mapping=c.pin(b.ORIGINAL/'results/context-feedback/v2-observe-full-1/reference_free/complete.json'),
        arms=[dict(arm=arm, canonical_arm=aliases[arm], sam=c.pin(output/(aliases[arm]+'.sam')),
                   identical_bytes_alias=aliases[arm] != arm, edits=ledgers[arm],
                   historical_reference_free_mapping=free['mapped'] if contents[arm] == old_bytes else None)
              for arm in ARMS], quality='Changed centers carry uncalibrated !; unchanged SEQ/Q spans preserve native bytes.',
        biological_qualification=False))


def run(phase, directories, summaries, output, config):
    atlas, cases, decisions, evidence = frozen_choices(directories, summaries, config)
    if phase == 'observe':
        annotate(atlas, cases, decisions, output)
    else:
        emit(atlas, cases, decisions, output)
    c.fresh(output/'decision-inputs.json', dict(schema='context-decision-frozen-inputs/1', evidence=evidence,
            cases=len(cases), decisions=len(decisions), source=c.pin(__file__)))
