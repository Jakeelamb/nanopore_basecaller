"""Reconstruct all native parents from frozen common-U choices after inference."""
import hashlib
import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sample_emission_boundary', ROOT/'tools/context_sample_feedback/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
c = b.c


def dna_digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def validate_edits(sequence, edits):
    cursor, previous = 0, None
    for edit in sorted(edits, key=lambda item: item['start']):
        start, end = edit['start'], edit['end']
        c.require(type(start) is int and type(end) is int and cursor <= start <= end <= len(sequence) and start != previous,
                  'Overlapping/out-of-range native edits')
        c.require(sequence[start:end] == edit['stock'] and edit['replacement'] != edit['stock']
                  and isinstance(edit['replacement'], str) and set(edit['replacement']) <= set('ACGT'), 'Native attachment/no-op/DNA differs')
        cursor, previous = end, start


def sam_bytes(parents, originals, edits, observer):
    c.require(len(parents) == len(set(parents)) == len(originals) and set(parents) == set(originals), 'Parent census differs')
    c.require(all(edit['parent'] in originals for edit in edits), 'Foreign edited parent')
    lines = ['@HD\tVN:1.6\tSO:unknown']
    for parent in parents:
        native = originals[parent]
        changes = [edit for edit in edits if edit['parent'] == parent]
        validate_edits(native['sequence'], changes)
        sequence, quality = observer.splice(native['sequence'], native['quality'], changes)
        c.require((sequence, quality) == observer.independent_splice(native['sequence'], native['quality'], changes)
                  and len(sequence) == len(quality), 'Independent parent reconstruction differs')
        if not changes:
            c.require((sequence, quality) == (native['sequence'], native['quality']), 'Untouched native SEQ/Q differs')
        lines.append('\t'.join((parent, '4', '*', '0', '0', '*', '*', '0', '0', sequence, quality)))
    return ('\n'.join(lines)+'\n').encode('ascii')


def deduplicate(contents):
    seen, aliases = {}, {}
    for arm, data in sorted(contents.items()):
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            canonical, saved = seen[digest]
            c.require(saved == data, 'Full SAM digest collision')
            aliases[arm] = canonical
        else:
            seen[digest] = (arm, data)
            aliases[arm] = arm
    return dict(seen.values()), aliases


def cases(config):
    fields = c.read(b.STUDY/'wire-schema.json')['candidate_records']['CASE']
    rows = {}
    with Path(config['packet']['path']).open(encoding='ascii') as stream:
        for line in stream:
            parts = line.rstrip('\n').split('\t')
            if parts[0] == 'CASE':
                row = dict(zip(fields, parts[1:], strict=True))
                c.require(row['case_id'] not in rows, 'Duplicate original case')
                rows[row['case_id']] = row
    c.require(len(rows) == 368 and sum(row['domain'] == 'ordinary' for row in rows.values()) == 311,
              'Original ordinary/private census differs')
    return rows


def frozen_choices(summaries, config):
    inputs = cases(config)
    choices = {}
    for summary in summaries:
        c.require(summary['phase'] == 'infer' and len(summary['native']) == 1, 'Inference native count differs')
        seal = c.read(summary['native'][0]['path'])
        result = c.read(seal['result']['path'])
        c.require(result['historical_six_roles_verified'] is True and result['truth_available'] is False
                  and all(result[key] is False for key in config['qualification_flags']), 'Frozen inference/role contract differs')
        path = next(pin for pin in seal['files'] if pin['path'].endswith('/decisions.tsv'))
        for row in b.table(path['path']):
            key = (row['case_id'], row['arm'])
            c.require(key not in choices and row['case_id'] in inputs and row['arm'] in b.ARMS
                      and row['domain'] == inputs[row['case_id']]['domain'], 'Foreign/duplicate decision')
            choices[key] = row
    c.require(set(choices) == {(case, arm) for case in inputs for arm in b.ARMS}, 'Complete368 by arm decision census differs')
    for case, row in inputs.items():
        for arm in b.ARMS: validate_choice(row, choices[case, arm], choices[case, 'nn_u'])
        c.require(choices[case, 'disabled_edits']['accepted'] == row['native'], 'Disabled native identity differs')
        c.require(choices[case, 'missing_source']['accepted'] == choices[case, 'nn_u']['accepted'], 'Missing-source NN identity differs')
    return inputs, choices


def validate_choice(case, row, nn):
    c.require(row['case_id'] == case['case_id'] == nn['case_id'] and row['domain'] == case['domain'] == nn['domain'],
              'Choice case/domain binding differs')
    for name in ('baseline','proposed','accepted'):
        c.require(dna_digest(row[name]) == row[name+'_sha256'] and set(row[name]) <= set('ACGT')
                  and math.isfinite(float(row[name+'_likelihood'])), 'Choice DNA digest/finite likelihood differs')
    if row['arm'] not in ('disabled_edits','historical_free'):
        c.require(row['baseline'] == nn['accepted'] and row['baseline_sha256'] == nn['accepted_sha256']
                  and row['baseline_likelihood'] == nn['accepted_likelihood'] and row['baseline_origins'] == nn['accepted_origins'],
                  'Actual frozen common-U NN baseline differs')


def emit(directories, summaries, output, config):
    inputs, choices = frozen_choices(summaries, config)
    observer = b.module('sample_original_splice_observer', b.ORIGINAL/'tools/context_decoder/observe.py')
    original = observer.w
    c.require(observer.ROOT == observer.c.ROOT == original.ROOT == b.ORIGINAL and
              original.inventory_hash(original.sources()) == b.ORIGINAL_ID, 'Original observer ROOT/source identity differs')
    free = observer.completed_producer(b.ORIGINAL/'results/context-feedback/v2-observe-full-1/reference_free/complete.json', 'arm', 'ordinary')
    historical = observer.completed_producer(free['manifest']['path'], 'prepare', 'ordinary')
    c.check(historical['snapshot'])
    c.require(historical['snapshot']['sha256'] == config['snapshot_sha256'], 'Frozen native snapshot differs')
    snapshot = c.read(historical['snapshot']['path'])
    for key in ('parents', 'native'): c.check(snapshot[key])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    c.require(len(parents) == len(set(parents)) == 64, 'Complete64 parent census differs')
    atlas = b.module('sample_original_parent_auditor', b.ATLAS/'scripts/context-program.py')
    c.require(atlas.ROOT == atlas.c.ROOT == b.ATLAS, 'Original parent auditor ROOT differs')
    parsed = atlas.packet_boundary().sam_index(snapshot['native']['path'], atlas.c)
    originals = {parent:parsed[parent] for parent in parents}
    ordinary = {key:row for key,row in inputs.items() if row['domain'] == 'ordinary'}
    contents, ledgers = {}, {}
    for arm in b.ARMS:
        edits = []
        for case, row in sorted(ordinary.items()):
            start, end = int(row['owned_start']), int(row['owned_end'])
            c.require(originals[row['parent']]['sequence'][start:end] == row['native'], 'Native parent attachment differs')
            sequence = choices[case, arm]['accepted']
            if sequence != row['native']:
                edits.append(dict(case_id=case, parent=row['parent'], geometry_sha256=row['geometry_sha256'], start=start,
                    end=end, stock=row['native'], replacement=sequence, candidate_sha256=dna_digest(sequence)))
        contents[arm] = sam_bytes(parents, originals, edits, observer)
        ledgers[arm] = edits
    canonical, aliases = deduplicate(contents)
    old_sam = next(arm['sam'] for arm in historical['arms'] if arm['arm'] == 'reference_free')
    c.check(old_sam)
    old_bytes = Path(old_sam['path']).read_bytes()
    c.require(contents['historical_free'] == old_bytes, 'Actual historical-free control SAM differs')
    for arm, data in canonical.items():
        with (output/(arm+'.sam')).open('xb') as stream: stream.write(data)
    b.write_table(output/'all-choices.tsv', [choices[key] for key in sorted(choices)], tuple(next(iter(choices.values())).keys()))
    c.fresh(output/'emission.json', dict(schema='context-sample-feedback-parent-emission/1', parents=64, ordinary_cases=311,
        private_frames_applied=False, snapshot=historical['snapshot'], historical_mapping=c.pin(b.ORIGINAL/'results/context-feedback/v2-observe-full-1/reference_free/complete.json'),
        inputs=[c.pin(directory/'execution-complete.json') for directory in directories],
        arms=[dict(arm=arm, canonical_arm=aliases[arm], sam=c.pin(output/(aliases[arm]+'.sam')), edits=ledgers[arm],
            historical_reference_free_mapping=free['mapped'] if contents[arm] == old_bytes else None) for arm in b.ARMS],
        private_diagnostics_separate=True, quality='Changed centers carry uncalibrated !; untouched native SEQ/Q retained.',
        qualification_flags=config['qualification_flags'], added_information='Other-read context can contain formerly population-withheld ALT; private results are not blind.'))
