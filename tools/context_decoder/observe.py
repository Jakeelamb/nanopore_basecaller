#!/usr/bin/env python3
"""Emit complete matched parents and coordinate the unchanged biological observer."""
import argparse
import fcntl
from datetime import datetime, timezone
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import uuid
import shutil

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('context_feedback', ROOT / 'scripts/context-feedback.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
c = w.c
SOURCE = c.pin(__file__)
SNAPSHOT = Path('/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json')
SNAPSHOT_HASH = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'
ARMS = ('reference_free', 'final_rerank', 'selected')
MODES = ('ordinary', 'withheld')


def module(name):
    spec = importlib.util.spec_from_file_location('observer_' + name, ROOT / 'tools/context_decoder' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


g = module('guarded_inputs')
p = module('private_inputs')


def splice(sequence, quality, edits):
    c.require(len(sequence) == len(quality), 'Parent SEQ/Q lengths differ')
    cursor = 0
    seq, qual = [], []
    previous = None
    for edit in sorted(edits, key=lambda e: e['start']):
        a, b, replacement = edit['start'], edit['end'], edit['replacement']
        c.require(type(a) is int and type(b) is int and cursor <= a <= b <= len(sequence)
                  and (previous is None or a != previous), 'Overlapping/out-of-range parent edits')
        c.require(sequence[a:b] == edit['stock'], 'Edit/native attachment mismatch')
        c.require(isinstance(replacement, str) and set(replacement) <= set('ACGT'), 'Invalid replacement DNA')
        seq += [sequence[cursor:a], replacement]
        qual += [quality[cursor:a], '!' * len(replacement)]
        cursor = b
        previous = a
    return ''.join(seq) + sequence[cursor:], ''.join(qual) + quality[cursor:]


def independent_splice(sequence, quality, edits):
    for edit in sorted(edits, key=lambda e: e['start'], reverse=True):
        a, b = edit['start'], edit['end']
        sequence = sequence[:a] + edit['replacement'] + sequence[b:]
        quality = quality[:a] + '!' * len(edit['replacement']) + quality[b:]
    return sequence, quality


def completed_producer(manifest, command, context_mode):
    manifest = Path(manifest).resolve()
    outer = c.read(manifest.parent / 'execution-complete.json')
    for key in ('worker', 'source', 'terminal', 'command', 'worker_intake', 'stdout', 'stderr'):
        c.check(outer[key])
    c.require(outer['complete'] is True and outer['worker'] == c.pin(manifest)
              and outer['source'] == SOURCE, 'Producer outer completion/source differs')
    terminal = c.read(outer['terminal']['path'])
    c.require(terminal['error'] is None and terminal['exit'] == 0, 'Producer outer execution failed')
    c.require(c.read(outer['worker_intake']['path'])['verified'] is True, 'Producer worker intake not verified')
    c.require(c.read(outer['stdout']['path']) == dict(completion=c.pin(manifest)), 'Producer stdout differs')
    launch = c.read(outer['command']['path'])
    c.require(launch['grant']['source'] == SOURCE and launch['grant']['command'] == command
              and launch['grant']['output'] == str(manifest.parent)
              and launch['grant']['context_mode'] == context_mode, 'Producer intended command/source/mode differs')
    c.require(str(Path(__file__).resolve()) in launch['argv']
              and launch['argv'][launch['argv'].index(str(Path(__file__).resolve())) + 1] == command,
              'Producer launch command differs')
    c.require(launch['argv'].count('--context-mode') == 1
              and launch['argv'][launch['argv'].index('--context-mode')+1] == context_mode, 'Producer launch mode differs')
    seal = c.read(manifest)
    c.require(seal['context_mode'] == context_mode, 'Producer completed mode differs')
    if command == 'prepare':
        phase_directory = Path(seal['decoder']['execution']['path']).parent
        c.require(launch['grant']['checkpoint'] == c.pin(phase_directory/'complete.json')
                  and launch['grant']['manifest'] is None, 'Producer guarded phase binding differs')
    else:
        c.require(launch['grant']['manifest'] == seal['manifest'] and launch['grant']['checkpoint'] is None,
                  'Producer emission manifest binding differs')
    return seal


def guarded_phase(checkpoint):
    c.require(checkpoint is not None, 'Guarded decoder completion directory required')
    complete = c.read(Path(checkpoint) / 'complete.json')
    phase = complete['phase']
    c.require(complete['complete'] is True and phase in ('query0', 'checkpoint', 'full', 'private'),
              'Guarded data phase completion required')
    return phase


def selected_rows(summary, phase, config, mode):
    c.require(mode in MODES and (mode == 'ordinary' or phase == 'private'), 'Context mode unavailable in this phase')
    c.require(summary['schema'] == 'context-feedback-unit/2' and summary['phase'] == phase, 'Guarded summary phase differs')
    cases = list(range(40)) if phase == 'private' else config[{'query0': 'qualification_queries',
              'checkpoint': 'checkpoint_queries', 'full': 'full_queries'}[phase]]
    expected = {(q, m) for q in cases for m in (MODES if phase == 'private' else ('ordinary',))}
    actual = [(x['query_index'], x['context_mode']) for x in summary['outcomes']]
    c.require(len(actual) == len(set(actual)) and set(actual) == expected, 'Guarded outcome query/mode census differs')
    return [x for x in summary['outcomes'] if x['context_mode'] == mode]


def fields(path, schema):
    lines = Path(path).read_text().splitlines()
    c.require(lines and lines[0] == schema, 'Observer input schema differs')
    pairs = [line.split('\t') for line in lines[1:]]
    c.require(all(len(x) == 2 for x in pairs) and len({x[0] for x in pairs}) == len(pairs), 'Observer input fields malformed')
    return dict(pairs)


def validate_outcome(outcome, admitted, mode, observation=None):
    """Bind emitted centers to actual source windows and native construction bytes."""
    query = outcome['query_index']
    window, decision = admitted['plan'][query], admitted['decisions'][query]
    c.require(outcome['read_id'] == window['read_id'], 'Decoded parent/plan differs')
    if decision['status'] == 'excluded':
        c.require(outcome['status'] == 'original_excluded' and outcome['reason'] == decision['reason']
                  and 'native' not in outcome, 'Original exclusion differs')
        return None
    if mode == 'withheld' and query not in admitted['allowed_walk_hashes']:
        c.require(outcome['status'] == 'challenge_excluded' and 'native' not in outcome, 'Challenge exclusion differs')
        return None
    evidence = admitted['receipts'][query]
    meta = c.metadata(c.check(evidence['metadata_pin'])['path'])
    parent = c.metadata(c.check(evidence['parent_pin'])['path'])
    retained = g.retained_chunks(evidence)[window['chunk_index']]
    a, b = window['chunk_start'], window['chunk_end']
    moves = [i for i, value in enumerate(meta['MOVES']) if value == '1']
    reason = ('native_guard_unavailable' if a < 4 or b-a < 20 or b+10 >= len(moves)
              else 'expanded_guard_outside_retained_chunk' if a < retained['chunk_base_start'] or b+10 > retained['chunk_base_end']
              else 'expanded_guard_timestep_bound' if moves[b+10]-moves[a] > 256 or moves[b+10] > retained['t_end'] else None)
    observation = observation or c.mapped(c.check(admitted['native'])['path'], window['read_id'])
    c.require((parent['SEQ'], parent['Q']) == (observation['sequence'], observation['quality']), 'Complete native parent SEQ/Q differs')
    if reason is None and not g.guard_contiguous(window, observation):
        reason = 'native_guard_gapped_or_clipped_in_sam'
    if reason:
        c.require(outcome['status'] == 'boundary_excluded' and outcome['reason'] == reason
                  and 'native' not in outcome, 'Guard boundary exclusion differs')
        return None
    c.require(outcome['status'] == 'constructed' and 'native' in outcome, 'Usable guarded window lacks result')
    start, end = window['read_start']+10, window['read_end']-10
    native = meta['SEQ'][a+10:b-10]
    c.require(parent['read_id'] == meta['read_id'] == window['read_id']
              and retained['parent_base_start']+a-retained['chunk_base_start'] == window['read_start']
              and retained['parent_base_start']+b-retained['chunk_base_start'] == window['read_end']
              and parent['SEQ'][window['read_start']:window['read_end']] == meta['SEQ'][a:b] == window['stock']
              and parent['SEQ'][start:end] == native, 'Native center/source attachment differs')
    for key, value in (('owned_start', start), ('owned_end', end), ('native_center', native)):
        c.require(outcome[key] == value, 'Summary center differs: ' + key)
    construction = c.read(c.check(outcome['construction'])['path'])
    c.require(construction['schema'] == 'guarded-window-construction/2'
              and construction['original_window'] == window and construction['parent'] == evidence['parent_pin']
              and construction['reconstruction_metadata'] == evidence['reconstruction_metadata_pins']
              and construction['retained'] == retained and construction['owned_native'] == native
              and construction['constructor'] == c.pin(g.__file__) and construction['truth_input'] is False
              and construction['frame'] == outcome['frame'] and construction['base_frame'] == outcome['base_frame'],
              'Guarded construction/source differs')
    frame = fields(c.check(outcome['frame'])['path'], 'guarded-frame/2')
    expected = dict(read_start=window['read_start'], read_end=window['read_end'], owned_start=start, owned_end=end,
              anchor_bases=10, future_bases=10, expanded_t_start=moves[a], expanded_t_end=moves[b+10],
              left_guard=meta['SEQ'][a:a+10], right_guard=meta['SEQ'][b-10:b+10], native_center=native,
              retained_chunk_start=retained['chunk_base_start'], retained_chunk_end=retained['chunk_base_end'])
    for prefix, pin in (('base_frame', outcome['base_frame']), ('parent', evidence['parent_pin'])):
        expected.update({prefix+'_'+key: value for key, value in pin.items()})
    c.require(all(frame.get(k) == str(v) for k, v in expected.items()), 'Guarded frame geometry/source differs')
    base = g.frame_fields(c.check(outcome['base_frame'])['path'])
    c.require(base['location_status'] == c.validate_location(window, observation, 30), 'Base location status/source differs')
    source = admitted['cohort']['pins']
    for key, value in dict(plan_sha256=source['windows']['sha256'], graph_sha256=source['graph_walks']['sha256'],
              query_index=query, parent=window['read_id'], chunk_index=window['chunk_index'], stock=window['stock'],
              t_start=window['t_start'], t_end=window['t_end'], initial_context=window['context'], reverse=int(window['reverse']),
              contig=window['contig'], ref_start=window['ref_start'], ref_end=window['ref_end']).items():
        c.require(base.get(key) == str(value), 'Base frame/source plan differs: ' + key)
    for prefix, pin in (('tensor', evidence['score_pin']), ('metadata', evidence['metadata_pin']),
                        ('location_receipt', admitted['location_pin']), ('location_sam', admitted['native'])):
        c.require(all(base[prefix+'_'+k] == str(v) for k, v in pin.items()), 'Base producer source differs')
    context_pin = {key: int(frame['context_'+key]) if key == 'size' else frame['context_'+key] for key in ('path', 'size', 'sha256')}
    context = fields(c.check(context_pin)['path'], 'context-centers/2')
    allowed = None if mode == 'ordinary' else admitted['allowed_walk_hashes'][query]
    paths, exclusions = g.project_centers(window, admitted['graph'][query], allowed)
    availability = base['location_status'] if paths else 'missing'
    paths = paths if availability == 'usable' else []
    expected_context = dict(base_frame_sha256=outcome['base_frame']['sha256'],plan_sha256=base['plan_sha256'],
              query_index=query,parent=window['read_id'],chunk_index=window['chunk_index'],tensor_sha256=base['tensor_sha256'],
              expanded_t_start=moves[a],expanded_t_end=moves[b+10],owned_start=start,owned_end=end,
              availability=availability,graph_sha256=base['graph_sha256'],**{'sequence_'+str(i): s for i,s in enumerate(paths)})
    c.require(context == {k:str(v) for k,v in expected_context.items()}
              and construction['projection_exclusions'] == exclusions, 'Guarded context mode/source projection differs')
    target = Path(c.check(outcome['native']['completion'])['path']).parent
    result = c.read(target / 'result.json')
    c.require(result['schema'] == 'context-decoder-guarded-frame/2' and result['frame'] == outcome['frame']
              and result['binding'] == frame and result['outcome']['schema'] == 'guarded-outcome/2'
              and result['outcome']['native']['sequence'] == native, 'Native guarded result/center differs')
    choices = {arm: result['outcome'][arm]['sequence'] for arm in ARMS}
    c.require(all(isinstance(s, str) and set(s) <= set('ACGT') and len(s) <= 108 for s in choices.values()), 'Invalid decoded center')
    return dict(parent=window['read_id'],query=query,start=start,end=end,stock=native,
                choices=choices,native_result=c.pin(target / 'result.json'),construction=outcome['construction'])


def prepare(checkpoint, output, context_mode='ordinary'):
    c.require(c.pin(SNAPSHOT)['sha256'] == SNAPSHOT_HASH, 'Observer seam snapshot changed')
    snapshot = c.read(SNAPSHOT)
    source = w.inventory_hash(w.sources())
    phase = guarded_phase(checkpoint)
    qualified = w.evidence.completed(checkpoint, phase, source, c)
    summary = c.read(Path(checkpoint) / 'summary.json')
    start = c.read(Path(checkpoint) / 'start.json')
    config = w.configuration(c.check(start['config'])['path'])
    c.require(config['schema'] == 'context-feedback-config/2', 'Guarded observer requires v2 configuration')
    legacy = w.configuration(c.check(config['inputs']['legacy_inputs_config'])['path'])
    ordinary = c.inputs(legacy)
    admitted = p.load_private(ordinary) if phase == 'private' else ordinary
    c.check(snapshot['parents'])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    c.require(len(parents) == len(set(parents)) == 64, 'Original parent census changed')
    c.check(snapshot['native'])
    original = {parent: c.mapped(snapshot['native']['path'], parent) for parent in parents}
    c.require(snapshot['native'] == admitted['native'], 'Observer and decoder native parents differ')
    ledger = {arm: [] for arm in ARMS}
    choices = []
    for outcome in selected_rows(summary, phase, config, context_mode):
        c.require(outcome['read_id'] in original, 'Decoded parent outside complete native census')
        edit = validate_outcome(outcome, admitted, context_mode, original[outcome['read_id']])
        if edit is None:
            continue
        c.require(edit['parent'] in original and original[edit['parent']]['sequence'][edit['start']:edit['end']] == edit['stock'],
                  'Decoded native center differs from complete parent')
        choices.append(edit)
        for arm in ledger:
            replacement = edit['choices'][arm]
            if replacement != edit['stock']:
                ledger[arm].append(dict({k:v for k,v in edit.items() if k != 'choices'},replacement=replacement))
    directory = Path(output).resolve()
    directory.mkdir()
    c.fresh(directory / 'controls.json', controls())
    arms = []
    for arm, edits in ledger.items():
        lines = ['@HD\tVN:1.6\tSO:unknown']
        for parent in parents:
            native = original[parent]
            changes = [e for e in edits if e['parent'] == parent]
            seq, qual = splice(native['sequence'], native['quality'], changes)
            c.require((seq, qual) == independent_splice(native['sequence'], native['quality'], changes),
                      'Independent complete parent reconstruction differs')
            lines.append('\t'.join((parent, '4', '*', '0', '0', '*', '*', '0', '0', seq, qual)))
        path = directory / (arm + '.sam')
        with path.open('x') as stream:
            stream.write('\n'.join(lines) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        parsed = [line.split('\t') for line in path.read_text().splitlines() if not line.startswith('@')]
        c.require([p[0] for p in parsed] == parents, 'Emitted parent census/order differs')
        for row in parsed:
            native = original[row[0]]
            expected = independent_splice(native['sequence'], native['quality'], [e for e in edits if e['parent'] == row[0]])
            c.require((row[9], row[10]) == expected, 'Actual emitted SEQ/Q differs')
        arms.append(dict(arm=arm, sam=c.pin(path), edits=edits, parents=64))
    c.check(SOURCE)
    c.fresh(directory / 'complete.json', dict(schema='context-feedback-parent-emission/2', complete=True,
            source=SOURCE, decoder=qualified, context_mode=context_mode, snapshot=c.pin(SNAPSHOT), arms=arms, choices=choices,
            controls=c.pin(directory / 'controls.json'),
            policy='Replace only the sealed owned center literally; all outside-center SEQ/Q unchanged, including native guards and future.',
            quality='Changed centers carry uncalibrated ! qualities; unchanged centers preserve original qualities.',
            original_exclusions_retained=True, exploratory_development=True, biological_claim=False))
    return c.pin(directory / 'complete.json')


def worker(manifest, arm, output, grant, context_mode='ordinary'):
    w.pg.adopt_orphans()
    seal = completed_producer(manifest, 'prepare', context_mode)
    c.require(seal['schema'] == 'context-feedback-parent-emission/2'
              and seal['complete'] and seal['source'] == SOURCE and arm in ARMS, 'Emission source/arm differs')
    c.check(seal['controls'])
    phase_directory = Path(seal['decoder']['execution']['path']).parent
    phase = guarded_phase(phase_directory)
    c.require(seal['decoder']['phase'] == phase, 'Emission decoder phase differs')
    w.evidence.completed(phase_directory, phase, w.inventory_hash(w.sources()), c)
    c.check(seal['snapshot'])
    snapshot = c.read(seal['snapshot']['path'])
    selected = next(a for a in seal['arms'] if a['arm'] == arm)
    c.check(selected['sam'])
    directory = Path(output).resolve()
    directory.mkdir()
    c.fresh(directory / 'controls.json', controls())
    execution = w.Execution(grant, directory, w.sources() + [c.pin(__file__)])
    def stage(name, argv):
        result = execution.stage('biology-' + arm + '-' + name, argv)
        return result['raw']['stdout']['path']
    tools = snapshot['tools']
    c.fresh(directory / 'start.json', dict(manifest=c.pin(manifest), arm=arm, context_mode=context_mode, source=c.pin(__file__),
                                          snapshot=seal['snapshot'], grant=grant, tools=tools))
    for key in ('pairer', 'observer', 'parents', 'native', 'truth', 'confident'):
        c.check(snapshot[key])
    for p in snapshot['eligible'].values():
        c.check(p)
    for p in tools.values():
        if isinstance(p, dict) and {'path', 'sha256', 'size'} <= set(p):
            c.check(p)
    samtools = tools['samtools']['path']
    dorado = tools['dorado']['path']
    index = tools['index']['path']
    c.check(snapshot['reference'])
    bam = stage('sam-to-bam', [samtools, 'view', '-b', selected['sam']['path']])
    aligned = stage('align', [dorado, 'aligner', index, bam, '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
    mapped = stage('mapped-sam', [samtools, 'view', '-h', aligned])
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    for parent in parents:
        observed = c.mapped(mapped, parent)
        emitted = c.mapped(selected['sam']['path'], parent)
        c.require((observed['sequence'], observed['quality']) == (emitted['sequence'], emitted['quality']), 'Mapper changed complete parent SEQ/Q')
    lefts = dict(native=snapshot['native']['path'])
    if arm != 'reference_free':
        other_directory = directory.parent / 'reference_free'
        other = completed_producer(other_directory / 'complete.json', 'arm', context_mode)
        c.require(other['manifest'] == c.pin(manifest) and other['arm'] == 'reference_free'
                  and other['source'] == SOURCE, 'Reference-free comparator producer differs')
        for item in other['outputs']:
            c.check(item)
        stages = [w.evidence.stage(item, c) for item in other['stages']]
        free = next(a for a in seal['arms'] if a['arm'] == 'reference_free')
        c.check(free['sam'])
        c.require(stages[0]['argv'] == [samtools, 'view', '-b', free['sam']['path']]
                  and stages[1]['argv'] == [dorado, 'aligner', index, stages[0]['raw']['stdout']['path'], '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y']
                  and stages[2]['argv'] == [samtools, 'view', '-h', stages[1]['raw']['stdout']['path']]
                  and other['mapped'] == stages[2]['raw']['stdout'], 'Reference-free mapping/input chain differs')
        c.check(other['mapped'])
        lefts['reference_free'] = other['mapped']['path']
    for name, left in lefts.items():
        for domain, eligible in snapshot['eligible'].items():
            pairs = directory / ('pair-' + name + '-' + domain)
            stage('pair-' + name + '-' + domain, [snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'], '--eligible', eligible['path'], '--left', left, '--right', mapped, '--parents', snapshot['parents']['path'], '--output', pairs])
            stage('summary-' + name + '-' + domain, [snapshot['pairer']['path'], 'summarize', '--pairs', pairs, '--selected', 'all', '--output', directory / ('summary-' + name + '-' + domain)])
    stage('observe', [snapshot['observer']['path'], 'observe', '--reference', snapshot['reference']['path'], '--vcf', snapshot['truth']['path'], '--confident', snapshot['confident']['path'], '--sam', mapped, '--parents', snapshot['parents']['path'], '--output', directory / 'alleles'])
    stage('compare', [snapshot['observer']['path'], 'compare', '--baseline', snapshot['baseline_observations'], '--candidate', directory / 'alleles', '--output', directory / 'comparison'])
    for p in snapshot['baseline_observation_pins']:
        c.check(p)
    c.check(SOURCE)
    c.fresh(directory / 'complete.json', dict(schema='context-feedback-observation/2', complete=True,
            source=SOURCE, manifest=c.pin(manifest), arm=arm, context_mode=context_mode, mapped=c.pin(mapped),
            stages=execution.receipts, outputs=[c.pin(p) for p in sorted(directory.rglob('*')) if p.is_file()],
            exploratory_development=True, candidate_promoted=False))
    return c.pin(directory / 'complete.json')


def controls():
    sequence, quality = 'ACGTTACG', 'ABCDEFGH'
    for edits, expected in [([], (sequence, quality)),
            ([dict(start=1, end=3, stock='CG', replacement='T')], ('ATTTACG', 'A!DEFGH')),
            ([dict(start=1, end=3, stock='CG', replacement='')], ('ATTACG', 'ADEFGH')),
            ([dict(start=2, end=2, stock='', replacement='TT')], ('ACTTGTTACG', 'AB!!CDEFGH')),
            ([dict(start=2, end=2, stock='', replacement='')], (sequence, quality)),
            ([dict(start=1, end=2, stock='C', replacement='GG'), dict(start=5, end=7, stock='AC', replacement='T')], ('AGGGTTTG', 'A!!CDE!H'))]:
        c.require(splice(sequence, quality, edits) == expected, 'Splice fixture differs')
        c.require(splice(sequence, quality, edits) == independent_splice(sequence, quality, edits), 'Independent splice differs')
    for edits in [[dict(start=1, end=3, stock='XX', replacement='A')],
                  [dict(start=2, end=2, stock='', replacement='A'), dict(start=2,end=2,stock='',replacement='C')],
                  [dict(start=1, end=3, stock='CG', replacement='A'), dict(start=2, end=4, stock='GT', replacement='C')]]:
        try:
            splice(sequence, quality, edits)
        except ValueError:
            continue
        raise ValueError('Invalid splice did not reject')
    c.require(c.reverse_complement('ACGTTACG') == 'CGTAACGT', 'Orientation control differs')
    return dict(complete=True, independent_reconstruction=True, overlap_and_attachment_reject=True,
                empty_deletion_and_zero_span_insertion=True, arms=list(ARMS), context_modes=list(MODES))


def validate_grant(args, grant, now=None):
    now = now or datetime.now(timezone.utc)
    end = datetime.fromisoformat(grant['expires_utc'])
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', grant['id']) is not None, 'Unsafe observation identity')
    expected_group = '/user.slice/user-1000.slice/user@1000.service/app.slice/context-feedback-' + grant['id'] + '.service'
    c.require(args.context_mode in MODES and args.command in ('prepare', 'arm'), 'Invalid observation command/mode')
    c.require((args.command == 'prepare' and args.checkpoint is not None and args.manifest is None and args.arm is None)
              or (args.command == 'arm' and args.manifest is not None and args.checkpoint is None and args.arm in ARMS),
              'Observation command inputs differ')
    checkpoint = None if args.checkpoint is None else c.pin(args.checkpoint.resolve()/'complete.json')
    c.require(grant['schema'] == 'context-feedback-observation-admission/1'
              and grant['cgroup'] == expected_group and grant['source'] == SOURCE and grant['command'] == args.command
              and grant['arm'] == args.arm and grant['context_mode'] == args.context_mode and grant['checkpoint'] == checkpoint
              and grant['output'] == str(args.output.resolve())
              and grant['manifest'] == (None if args.manifest is None else c.pin(args.manifest)), 'Wrong observation admission')
    memory, address = (4, 8) if args.command == 'prepare' else (16, 24)
    c.require(datetime.fromisoformat(grant['not_before_utc']) <= now < end
              and 5 < (end-now).total_seconds() <= 300 and 0 < grant['maximum_wall_seconds'] <= 300
              and 0 < grant['cpu_quota'] <= 2 and 0 < grant['memory_bytes'] <= memory * 1024**3
              and 0 < grant['address_space_bytes'] <= address * 1024**3 and grant['swap_bytes'] == 0
              and 0 < grant['maximum_output_bytes'] <= 4 * 1024**3, 'Observation caps exceed admitted ceiling')
    c.require(args.output.resolve().is_relative_to(w.RESULTS), 'Observation output outside owned tree')
    return end


def supervise(args):
    grant = c.read(args.admission)
    now = datetime.now(timezone.utc)
    end = validate_grant(args, grant, now)
    directory = w.LOGS / ('supervisor-' + grant['id'])
    directory.mkdir()
    unit = 'context-feedback-' + grant['id'] + '.service'
    description = 'Context observation ' + uuid.uuid4().hex
    w.pg.adopt_orphans()
    with w.LOCK.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            c.fresh(directory / 'refused.json', dict(reason='canonical lock held'))
            raise
        intake = directory / 'intake.json'
        c.fresh(intake, dict(grant_id=grant['id'], admission=str(args.admission.resolve()), parent_pid=os.getpid(),
                    parent_start=w.supervisor.process_start(os.getpid()), lock_fd=lock.fileno(), unit=unit, description=description))
        command = ['systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit,
                   '--description=' + description, '--working-directory=' + str(ROOT),
                   '--property=Type=exec', '--property=ExitType=cgroup', '--property=KillMode=control-group',
                   '--property=Slice=app.slice',
                   '--property=CollectMode=inactive', '--property=SendSIGKILL=yes', '--property=FinalKillSignal=SIGKILL',
                   '--property=TimeoutStopSec=1s', '--property=RuntimeMaxSec=' + str(min(grant['maximum_wall_seconds'], (end-now).total_seconds())-3) + 's',
                   '--property=CPUQuota=' + str(grant['cpu_quota'] * 100) + '%', '--property=MemoryMax=' + str(grant['memory_bytes']),
                   '--property=MemorySwapMax=0', '--property=LimitAS=' + str(grant['address_space_bytes']),
                   '--setenv=UV_PROJECT_ENVIRONMENT=' + os.environ['UV_PROJECT_ENVIRONMENT'], '--', shutil.which('uv'),
                   'run', '--no-sync', 'python', str(Path(__file__).resolve()), args.command, '--output', str(args.output.resolve()),
                   '--admission', str(args.admission.resolve()), '--worker-intake', str(intake)]
        for key in ('checkpoint', 'manifest', 'arm', 'context_mode'):
            value = getattr(args, key)
            if value is not None:
                command += ['--' + key.replace('_', '-'), str(value.resolve() if isinstance(value, Path) else value)]
        c.fresh(directory / 'command.json', dict(argv=command, grant=grant, utc=now.isoformat()))
        process = None
        error = None
        proof = None
        try:
            with (directory / 'stdout').open('xb') as out, (directory / 'stderr').open('xb') as err:
                process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    if time.time() >= end.timestamp()-1 or w.owned_bytes() > grant['maximum_output_bytes'] or shutil.disk_usage(ROOT).free < 30*1024**3:
                        raise ValueError('Observation wall/output/disk boundary reached')
                    time.sleep(.2)
        except BaseException as caught:
            error = repr(caught)
        finally:
            sample = 0
            while proof is None:
                try:
                    observation = w.supervisor.show(unit)
                    if observation['properties'].get('Description') == description:
                        if w.supervisor.terminal(observation, grant['cgroup']):
                            proof = observation
                            if observation['properties'].get('Result') != 'success':
                                error = error or 'Service failed'
                        else:
                            subprocess.run(['systemctl', '--user', 'stop', '--no-block', unit], capture_output=True, timeout=3)
                    elif process is None or (process.poll() is not None and w.supervisor.unloaded_terminal(observation, grant['cgroup'])):
                        proof = dict(unloaded_empty_group=observation)
                except BaseException as caught:
                    sample += 1
                    c.fresh(directory / ('termination-observation-error-' + str(sample) + '.json'),
                            dict(error=repr(caught), canonical_lock_retained=True))
                if proof is None:
                    time.sleep(.2)
            if process is not None:
                while True:
                    try:
                        cleanup = w.pg.stop_group(process, process.pid)
                        c.fresh(directory / 'launcher-cleanup.json', cleanup)
                        break
                    except BaseException as caught:
                        sample += 1
                        c.fresh(directory / ('launcher-cleanup-error-' + str(sample) + '.json'),
                                dict(error=repr(caught), canonical_lock_retained=True))
                        time.sleep(.2)
            c.fresh(directory / 'terminal.json', dict(proof=proof, error=error,
                    exit=None if process is None else process.returncode, utc=datetime.now(timezone.utc).isoformat()))
        c.require(error is None and process is not None and process.returncode == 0, 'Observation unit failed; retained ' + str(directory))
        result = c.read(directory / 'stdout')['completion']
        c.check(result)
        c.require(result['path'] == str(args.output.resolve() / 'complete.json'), 'Worker completion path differs')
        c.check(SOURCE)
        c.fresh(args.output / 'execution-complete.json', dict(complete=True, worker=result, source=SOURCE,
                terminal=c.pin(directory / 'terminal.json'), command=c.pin(directory / 'command.json'),
                worker_intake=c.pin(directory / 'worker-intake.json'), stdout=c.pin(directory / 'stdout'), stderr=c.pin(directory / 'stderr')))
        print(json.dumps(dict(completion=c.pin(args.output / 'execution-complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'arm'))
    parser.add_argument('--checkpoint', type=Path, help='Completed guarded query0, checkpoint, full or private phase directory')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--context-mode', choices=MODES, default='ordinary', help='Frozen context mode; withheld requires a private phase')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--worker-intake', type=Path)
    args = parser.parse_args()
    if args.worker_intake is None:
        supervise(args)
        return
    grant = c.read(args.admission)
    validate_grant(args, grant)
    w.supervisor.worker_intake(args.worker_intake, grant, c)
    w.cgroup_limits(grant)
    if args.command == 'prepare':
        result = prepare(args.checkpoint, args.output, args.context_mode)
    else:
        result = worker(args.manifest, args.arm, args.output, grant, args.context_mode)
    print(json.dumps(dict(completion=result)))


if __name__ == '__main__':
    main()
