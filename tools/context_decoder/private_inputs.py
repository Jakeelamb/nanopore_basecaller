"""Pinned private diagnostic attachments; no truth-dependent runtime selection."""

import hashlib
import importlib.util
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('private_context_boundary', ROOT / 'tools/context_decoder/context_inputs.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REGISTRY = Path(__file__).with_name('private-context-registry.json')


def member(items, expected):
    c.require(expected in items, 'Private ancestry missing ' + expected['path'])


def load_private(legacy_admitted):
    registry = c.read(REGISTRY)
    c.require(set(registry) == {'schema', 'namespace', 'files', 'archived_cases',
                               'withheld_prototype_sets', 'scope'}
              and registry['schema'] == 'private-context-registry/1', 'Private registry schema differs')
    files = registry['files']
    for item in files.values():
        c.check(item)
    namespace = registry['namespace']
    c.require(namespace == dict(dataset='additional_original',
              selection_plan_sha256=files['selection']['sha256'],
              attached_windows_sha256=files['windows']['sha256'],
              graph_walks_sha256=files['graph_walks']['sha256']), 'Private namespace differs')
    packet = c.read(files['packet']['path'])
    c.require(packet['schema'] == 'private-alt-score-reuse/1' and not packet['missing_parents'],
              'Private native packet differs')
    for key in ('qualification', 'qualification_admission', 'native_producer', 'native_inventory', 'original_native'):
        c.check(packet[key])
    for item in packet['sources']:
        c.check(item)
    for item in packet['producer_context']['sources']:
        c.check(item)
    native_producer = c.receipt(packet['native_producer']['path'])
    attachment = c.read(files['attachment_complete']['path'])
    c.require(attachment['complete'] is True, 'Private attachment incomplete')
    for key in ('attachment', 'selection', 'windows', 'queries'):
        member(attachment['files'], files[key])
    # Retained source bytes, rather than a mutable current checkout, bind the constructor.
    for item in attachment['files']:
        if '/retained-sources/' in item['path'] or '-receipt/' in item['path']:
            c.check(item)
    graph_seal = c.read(files['graph_complete']['path'])
    c.require(graph_seal['complete'] is True, 'Private graph incomplete')
    for key in ('selection', 'windows', 'queries'):
        member(graph_seal['qualified_assets'], files[key])
    member(graph_seal['graph_files'], files['graph_walks'])
    for item in graph_seal['sources'] + graph_seal['graph_files']:
        c.check(item)
    c.receipt(c.check(graph_seal['producer'])['path'])
    scored = c.read(files['scored_complete']['path'])
    c.require(scored['complete'] is True and scored['role'] == 'development'
              and scored['attached_queries'] == 40 and scored['original_selected_targets'] == 60,
              'Private scored cohort differs')
    member(scored['files'], files['decisions'])
    for key in ('attachment_complete', 'attachment', 'selection', 'windows', 'graph_complete'):
        member(scored['context']['qualified_assets'], files[key])
    for item in scored['files'] + scored['context']['sources'] + scored['context']['executables']:
        c.check(item)
    producer = c.receipt(c.check(scored['producer'])['path'])
    c.require(producer['context'] == scored['context'], 'Private scoring producer context differs')
    for option, key in (('--windows', 'windows'), ('--graph', 'graph_walks')):
        c.require(producer['argv'].count(option) == 1
                  and producer['argv'][producer['argv'].index(option) + 1] == files[key]['path'],
                  'Private scoring producer input differs')
    native = c.check(legacy_admitted['native'])
    location_pin = c.check(legacy_admitted['location_pin'])
    member(scored['context']['qualified_assets'], native)
    location = c.read(location_pin['path'])
    c.require(location['stdout'] == native['path'] and location['status'] == 'finished'
              and location['exit'] == 0, 'Private native location differs')
    challenge = c.read(files['challenge_complete']['path'])
    c.require(challenge['complete'] is True and challenge['role'] == 'development'
              and challenge['unambiguous_challenge_cases'] == 26
              and challenge['scored_windows'] == 31, 'Private challenge census differs')
    for key in ('attachment_complete', 'attachment', 'selection', 'graph_complete', 'scored_complete', 'decisions'):
        member(challenge['inputs'], files[key])
    for key in ('challenge_build', 'challenge_sources'):
        member(challenge['outputs'], files[key])
    member(challenge['outputs'], registry['archived_cases'])
    # The archived cases pin records offline extraction ancestry. Never open cases at runtime.
    for item in challenge['producer_files']:
        c.check(item)
    for item in c.read(files['challenge_sources']['path']):
        c.check(item['retained'])
    build = c.read(files['challenge_build']['path'])
    challenge_exclusions = [dict(case_id=x['case_id'], reason=x['reason']) for x in build['exclusions']]
    attachment_rows = c.read(files['attachment']['path'])
    c.require(attachment_rows['selected_targets'] == 60 and attachment_rows['attached_targets'] == 40
              and attachment_rows['excluded_targets'] == 20, 'Private attachment census differs')
    attachment_exclusions = [dict(target_id=x['target_id'], read_id=x['source_uuid'], reason=x['reason'])
                             for x in attachment_rows['targets'] if x['status'] == 'excluded']
    plan, graph = c.rows(files['windows']['path']), c.rows(files['graph_walks']['path'])
    old = c.rows(files['decisions']['path'])
    c.require(set(plan) == set(graph) == set(old) == set(range(40)), 'Private attached query census differs')
    attached = {x['query_index']: x for x in attachment_rows['targets'] if x['status'] == 'attached-existing-scores'}
    parents = {x['parent']: x for x in packet['parents']}
    c.require(len(parents) == len(packet['parents']), 'Duplicate private native parent')
    receipts, decisions = {}, {}
    for query, window in plan.items():
        target, decision = attached[query], old[query]
        c.require(window['schema'] == 'graph-prior-window/1'
                  and target['source_uuid'] == decision['read_id'] == window['read_id'], 'Private UUID join differs')
        for key in ('chunk_index', 'chunk_start', 'chunk_end', 'read_start', 'read_end', 't_start', 't_end'):
            c.require(target[key] == window[key], 'Private attachment bound differs: ' + key)
        g = graph[query]
        c.require(g['schema'] == 'hprc-local-paths/1' and g['query'] == dict(sample='GRCh38',
                  contig=window['contig'], start=window['ref_start'], end=window['ref_end']), 'Private graph query differs')
        parent = parents[window['read_id']]
        chunks = sorted(parent['chunks'], key=lambda x: x['chunk_index'])
        c.require([x['chunk_index'] for x in chunks] == list(range(len(chunks)))
                  and all(x['chunk_count'] == len(chunks) for x in chunks), 'Private whole-parent census differs')
        chunk = chunks[window['chunk_index']]
        c.require(target['score_file'] == chunk['score']['path']
                  and target['score_metadata'] == chunk['metadata']['path']
                  and target['parent_moves'] == parent['stitched_parent']['path']
                  and Path(chunk['score']['path']).name == window['score_file'], 'Private tensor ownership differs')
        receipts[query] = dict(query_index=query, read_id=window['read_id'], score_pin=chunk['score'],
              metadata_pin=chunk['metadata'], parent_pin=parent['stitched_parent'],
              reconstruction_metadata_pins=[x['metadata'] for x in chunks], registered_header=chunk['header'])
        c.require(decision['status'] in ('scored', 'excluded'), 'Unknown private scoring status')
        if decision['status'] == 'scored':
            c.require(decision['score_sha256'] == chunk['score']['sha256'], 'Private score control tensor differs')
            decisions[query] = {k: decision[k] for k in ('query_index', 'read_id', 'status', 'score_sha256', 'stock_likelihood', 'hypotheses')}
        else:
            decisions[query] = {k: decision[k] for k in ('query_index', 'read_id', 'status', 'reason')}
    allowed = {}
    for row in registry['withheld_prototype_sets']:
        c.require(set(row) == {'case_id', 'query_index', 'full_sequence_sha256'}, 'Withheld registry contains extra fields')
        query = row['query_index']
        c.require(type(query) is int and query in plan and query not in allowed
                  and row['case_id'] == 'additional_original/' + str(query)
                  and decisions[query]['status'] == 'scored', 'Withheld query namespace differs')
        hashes = row['full_sequence_sha256']
        actual = {hashlib.sha256(w['sequence'].encode()).hexdigest() for w in graph[query]['walks']}
        c.require(hashes == sorted(set(hashes)) and hashes and set(hashes) <= actual,
                  'Withheld membership does not remove only registered full graph walks')
        allowed[query] = hashes
    scored_ids = {q for q, d in decisions.items() if d['status'] == 'scored'}
    excluded_challenge_ids = {int(x['case_id'].split('/')[1]) for x in challenge_exclusions}
    c.require(len(scored_ids) == 31 and len(allowed) == 26 and len(attachment_exclusions) == 20
              and len(challenge_exclusions) == 5 and set(allowed).isdisjoint(excluded_challenge_ids)
              and set(allowed) | excluded_challenge_ids == scored_ids, 'Private diagnostic funnel differs')
    return dict(plan=plan, decisions=decisions, graph=graph, receipts=receipts, native=native,
          location_pin=location_pin, namespace=namespace, allowed_walk_hashes=allowed,
          selection_counts=dict(selected=60, attached=40, scored=31, unambiguous_challenge=26),
          attachment_exclusions=attachment_exclusions, challenge_exclusions=challenge_exclusions,
          scoring_exclusions=[decisions[q] for q in sorted(decisions) if decisions[q]['status'] == 'excluded'],
          cohort=dict(role='development', pins=dict(windows=files['windows'], graph_walks=files['graph_walks'], decisions=files['decisions'])),
          source_pins=dict(files, registry=c.pin(REGISTRY), archived_cases=registry['archived_cases'],
                           native_producer=packet['native_producer'], qualification=packet['qualification'],
                           qualification_admission=packet['qualification_admission'], scoring_producer=scored['producer'],
                           graph_producer=graph_seal['producer']),
          native_producer_pins=native_producer['pins'],
          policy=dict(beam_width=128, max_symbols=128, minimum_mapq=30))


def build_base(private, query, directory):
    """Construct the legacy interval control frame from a private attachment."""
    c.require(type(query) is int and query in private['plan'], 'Unknown private query')
    files = private['source_pins']
    for key in ('windows', 'graph_walks', 'decisions'):
        c.check(files[key])
    window, decision = private['plan'][query], private['decisions'][query]
    c.require(window == c.rows(files['windows']['path'])[query]
              and private['graph'][query] == c.rows(files['graph_walks']['path'])[query], 'Private source row changed')
    if decision['status'] == 'excluded':
        return dict(query_index=query, read_id=window['read_id'], status='original_excluded', reason=decision['reason'])
    original_decision = c.rows(files['decisions']['path'])[query]
    c.require(all(original_decision[k] == v for k, v in decision.items()), 'Private scalar controls changed')
    evidence = private['receipts'][query]
    for item in [evidence['score_pin'], evidence['metadata_pin'], evidence['parent_pin'], *evidence['reconstruction_metadata_pins']]:
        c.check(item)
    tensor = evidence['score_pin']
    c.require(tensor['sha256'] == decision['score_sha256'] and evidence['read_id'] == window['read_id'], 'Private tensor changed')
    meta, parent = c.metadata(evidence['metadata_pin']['path']), c.metadata(evidence['parent_pin']['path'])
    with Path(tensor['path']).open('rb') as handle:
        header_bytes = handle.readline(4096)
    h = header_bytes.decode('ascii').strip().split('\t')
    c.require(h == evidence['registered_header'] and len(h) == 15 and h[:1] == ['DGS1']
              and h[2:5] == ['1024', '4', '6']
              and tensor['size'] == len(header_bytes) + int(h[1]) * 1024 * 2
              and Path(tensor['path']).name == h[13] + '_s' + h[14] + '.scores', 'Private DGS1 producer geometry differs')
    c.require(meta['format'] == 'DGM1' and parent['format'] == 'DGP1'
              and meta['read_id'] == parent['read_id'] == window['read_id']
              and int(meta['chunk_index']) == window['chunk_index']
              and meta['score_file'] == window['score_file']
              and [meta[k] for k in ('T', 'C', 'time_offset', 'token')] == [h[i] for i in (1, 2, 12, 13)],
              'Private native metadata association differs')
    moves = meta['MOVES']
    c.require(set(moves) <= {'0', '1'} and moves.count('1') == len(meta['SEQ']) == len(meta['Q']), 'Private native SEQ/Q/MOVES differs')
    emissions = [i for i, value in enumerate(moves) if value == '1']
    a, b = window['chunk_start'], window['chunk_end']
    c.require(a >= 4 and b < len(emissions) and meta['SEQ'][a:b] == window['stock']
              and meta['SEQ'][a - 4:a] == window['context'] and len(window['context']) == 4
              and emissions[a] == window['t_start'] and emissions[b] == window['t_end'], 'Private native attachment differs')
    c.check(private['native'])
    c.check(private['location_pin'])
    observation = c.mapped(private['native']['path'], window['read_id'])
    c.require(parent['SEQ'] == observation['sequence'] and parent['Q'] == observation['quality'], 'Private parent/native location differs')
    status = c.validate_location(window, observation, private['policy']['minimum_mapq'])
    paths = c.retrieve(window, private['graph'][query])
    if not paths:
        status = 'missing'
    initial = 0
    for base in window['context']:
        initial = initial * 4 + 'ACGT'.index(base)
    identity = dict(plan_sha256=files['windows']['sha256'], query_index=query, parent=window['read_id'],
          chunk_index=window['chunk_index'], tensor_sha256=tensor['sha256'], t_start=window['t_start'],
          t_end=window['t_end'], initial_context=window['context'], initial_state=initial,
          reverse=int(window['reverse']), contig=window['contig'], ref_start=window['ref_start'], ref_end=window['ref_end'],
          graph_sha256=files['graph_walks']['sha256'], location_receipt_sha256=private['location_pin']['sha256'],
          location_sam_sha256=private['native']['sha256'])
    directory = Path(directory)
    directory.mkdir()
    context = directory / 'context.tsv'
    c.tabular(context, 'context-paths/1', dict(identity, **{'sequence_' + str(i): seq for i, seq in enumerate(paths)}))
    controls = directory / 'retained-scalar.tsv'
    with controls.open('x') as handle:
        for hypothesis in decision['hypotheses']:
            value = hypothesis['likelihood']
            c.require(value is None or math.isfinite(value), 'Nonfinite private scalar control')
            handle.write(hypothesis['sequence'] + '\t' + ('impossible' if value is None else repr(value)) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    frame = dict(identity, location_status=status, stock=window['stock'])
    for prefix, item in [('tensor', tensor), ('metadata', evidence['metadata_pin']), ('context', c.pin(context)),
                         ('location_receipt', private['location_pin']), ('location_sam', private['native']), ('scalar_controls', c.pin(controls))]:
        frame.update({prefix + '_' + key: value for key, value in item.items()})
    c.tabular(directory / 'frame.tsv', 'context-frame/1', frame)
    c.fresh(directory / 'construction.json', dict(schema='private-context-frame-construction/1', namespace=private['namespace'],
          window=window, producer_receipt=evidence, source_pins=files, native_location=private['native'],
          location_producer=private['location_pin'], frame=c.pin(directory / 'frame.tsv'), constructor=c.pin(__file__),
          truth_input=False, causal_streaming_qualified=False, biological_qualification=False))
    t, beam = window['t_end'] - window['t_start'], private['policy']['beam_width']
    work = dict(context_edit_cells=(5 * beam * t * (t + 1) // 2 + 4 * beam * t) * sum(map(len, paths)),
          guide_transitions=t * 256 * 5,
          scalar_cell_upper=t * (min(t, private['policy']['max_symbols']) + 1) * (2 * beam + 1 + len(decision['hypotheses'])),
          interpretation='Conservative operation bounds, not measured wall time or a speed claim')
    c.fresh(directory / 'work-bound.json', work)
    return dict(query_index=query, read_id=window['read_id'], status='constructed', frame=c.pin(directory / 'frame.tsv'),
                work_bound=work, work_bound_receipt=c.pin(directory / 'work-bound.json'))
