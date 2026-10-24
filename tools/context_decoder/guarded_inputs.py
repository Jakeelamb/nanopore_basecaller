from pathlib import Path
import hashlib
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('guarded_input_boundary', ROOT / 'tools/context_decoder/context_inputs.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
_retained = {}


def frame_fields(path):
    lines = Path(path).read_text().splitlines()
    c.require(lines[0] == 'context-frame/1', 'Original frame schema differs')
    pairs = [line.split('\t') for line in lines[1:]]
    c.require(all(len(p) == 2 for p in pairs) and len({p[0] for p in pairs}) == len(pairs), 'Original frame fields malformed')
    return dict(pairs)


def retained_chunks(evidence):
    parent_pin = evidence['parent_pin']
    key = parent_pin['sha256']
    if key in _retained:
        return _retained[key]
    parent = c.metadata(c.check(parent_pin)['path'])
    chunks = []
    for item in evidence['reconstruction_metadata_pins']:
        meta = c.metadata(c.check(item)['path'])
        if meta['format'] == 'DGP1':
            c.require(item == parent_pin, 'Reconstruction parent manifest differs')
            continue
        c.require(meta['format'] == 'DGM1' and meta['read_id'] == parent['read_id'], 'Reconstruction parent differs')
        c.require(set(meta['MOVES']) <= {'0','1'} and meta['MOVES'].count('1') == len(meta['SEQ']) == len(meta['Q']), 'Reconstruction SEQ/Q/MOVES differs')
        chunks.append(meta)
    chunks.sort(key=lambda m: int(m['chunk_index']))
    count = int(chunks[0]['chunk_count'])
    c.require(len(chunks) == count and [int(m['chunk_index']) for m in chunks] == list(range(count)), 'Reconstruction chunk census differs')
    signal = int(parent['signal_samples'])
    sequence, quality, moves = '', '', ''
    front = 0
    result = []
    for i, meta in enumerate(chunks):
        c.require(int(meta['signal_samples']) == signal and int(meta['chunk_count']) == count, 'Reconstruction signal provenance differs')
        if i+1 < count:
            overlap = int(meta['input_offset']) + int(meta['raw_chunk_size']) - int(chunks[i+1]['input_offset'])
            c.require(overlap >= 0 and overlap % 6 == 0, 'Reconstruction overlap differs')
            steps = overlap // 6
            rear = steps // 2
            end, next_front = len(meta['MOVES'])-rear, steps-rear
        elif count == 1 or meta['variable_chunk_sizes'] == '1':
            end, next_front = (min(signal,int(meta['raw_chunk_size']))+5)//6, 0
        else:
            end, next_front = len(meta['MOVES']), 0
        c.require(0 <= front <= end <= len(meta['MOVES']), 'Reconstruction retained timestep bounds')
        a = meta['MOVES'][:front].count('1')
        b = a + meta['MOVES'][front:end].count('1')
        start = len(sequence)
        sequence += meta['SEQ'][a:b]
        quality += meta['Q'][a:b]
        moves += meta['MOVES'][front:end]
        result.append(dict(t_start=front,t_end=end,chunk_base_start=a,chunk_base_end=b,
                           parent_base_start=start,parent_base_end=len(sequence)))
        front = next_front
    if len(moves) > signal//6:
        c.require(len(moves) == signal//6+1, 'Reconstruction partial overhang differs')
        last = moves[-1]
        moves = moves[:-1]
        if last == '1':
            sequence, quality = sequence[:-1], quality[:-1]
            result[-1]['chunk_base_end'] -= 1
        result[-1]['t_end'] -= 1
        result[-1]['parent_base_end'] = len(sequence)
    c.require((sequence,quality,moves) == (parent['SEQ'],parent['Q'],parent['MOVES']), 'Complete native reconstruction differs')
    _retained[key] = result
    return result


def project_centers(window, graph, allowed_walk_hashes=None):
    c.require(graph['schema'] == 'hprc-local-paths/1' and graph['query_index'] == window['query_index']
              and graph['query'] == dict(sample='GRCh38',contig=window['contig'],start=window['ref_start'],end=window['ref_end']), 'Guarded graph query linkage differs')
    reference = graph['reference']
    c.require(reference['end']-reference['start'] == len(reference['sequence']), 'Graph reference span differs')
    c.require(any(p['is_reference'] and p['both_anchors'] and p['sequence'] == reference['sequence']
                  and p['cigar'] == str(len(reference['sequence']))+'M' for p in graph['walks']), 'Guarded graph lacks complete reference path')
    start, end = window['ref_start']+10, window['ref_end']-10
    c.require(start <= end, 'Guarded genomic center reversed')
    paths = set()
    exclusions = []
    for index, walk in enumerate(graph['walks']):
        digest = hashlib.sha256(walk['sequence'].encode()).hexdigest()
        if not walk['both_anchors'] or allowed_walk_hashes is not None and digest not in allowed_walk_hashes:
            exclusions.append(dict(walk=index,reason='unanchored_or_predeclared_withheld'))
            continue
        r, q, mapping = reference['start'], 0, {}
        for length, op in c.cigar(walk['cigar']):
            if op in 'M=X':
                mapping.update((r+i,q+i) for i in range(length))
                r, q = r+length, q+length
            elif op == 'I':
                q += length
            elif op == 'D':
                r += length
            else:
                raise ValueError('Unsupported guarded graph CIGAR')
        c.require(r == reference['end'] and q == len(walk['sequence']), 'Guarded graph CIGAR span differs')
        a, b = mapping.get(start-1), mapping.get(end)
        if a is None or b is None:
            exclusions.append(dict(walk=index,reason='editable_center_guard_anchor_absent'))
            continue
        c.require(a+1 <= b, 'Guarded graph center reversed')
        sequence = walk['sequence'][a+1:b]
        if window['reverse']:
            sequence = c.reverse_complement(sequence)
        c.require(set(sequence) <= set('ACGT') and len(sequence) <= 108, 'Guarded center context bound')
        paths.add(sequence)
    c.require(len(paths) <= 32, 'Guarded unique context cap exceeded')
    return sorted(paths), exclusions



def guard_contiguous(window, observation):
    mapping = []
    reference = observation['start']
    for length, op in c.cigar(observation['fields'][5]):
        if op in 'M=X':
            mapping.extend(range(reference,reference+length))
            reference += length
        elif op in 'IS':
            mapping.extend([None]*length)
        elif op in 'DN':
            reference += length
        else:
            c.require(op == 'P', 'Unsupported guarded native CIGAR')
    c.require(len(mapping) == len(observation['aligned']), 'Guarded location CIGAR length differs')
    for a,b in ((window['read_start'],window['read_start']+10),
                (window['read_end']-10,window['read_end']+10)):
        if observation['reverse']:
            a,b = len(mapping)-b,len(mapping)-a
        if not 0 <= a < b <= len(mapping):
            return False
        values = mapping[a:b]
        if any(value is None for value in values) or any(y != x+1 for x,y in zip(values,values[1:])):
            return False
    return True


def construct(base, window, evidence, graph, directory, allowed_walk_hashes=None):
    if base['status'] == 'original_excluded':
        return base
    c.require(base['status'] == 'constructed', 'Original frame was not constructed')
    f = frame_fields(c.check(base['frame'])['path'])
    meta = c.metadata(c.check(evidence['metadata_pin'])['path'])
    parent = c.metadata(c.check(evidence['parent_pin'])['path'])
    spans = retained_chunks(evidence)
    retained = spans[window['chunk_index']]
    a, b = window['chunk_start'], window['chunk_end']
    moves = [i for i,value in enumerate(meta['MOVES']) if value == '1']
    reason = None
    if a < 4 or b-a < 20 or b+10 >= len(moves):
        reason = 'native_guard_unavailable'
    elif a < retained['chunk_base_start'] or b+10 > retained['chunk_base_end']:
        reason = 'expanded_guard_outside_retained_chunk'
    elif moves[b+10]-moves[a] > 256 or moves[b+10] > retained['t_end']:
        reason = 'expanded_guard_timestep_bound'
    if reason:
        return dict(query_index=window['query_index'],read_id=window['read_id'],status='boundary_excluded',reason=reason,base_frame=base['frame'])
    c.require(retained['parent_base_start']+a-retained['chunk_base_start'] == window['read_start']
              and retained['parent_base_start']+b-retained['chunk_base_start'] == window['read_end'], 'Guarded parent/retained chunk coordinates differ')
    c.require(parent['SEQ'][window['read_start']:window['read_end']] == meta['SEQ'][a:b] == window['stock'], 'Guarded original native stock differs')
    sam = dict(path=f['location_sam_path'],size=int(f['location_sam_size']),sha256=f['location_sam_sha256'])
    if not guard_contiguous(window,c.mapped(c.check(sam)['path'],window['read_id'])):
        return dict(query_index=window['query_index'],read_id=window['read_id'],status='boundary_excluded',
                    reason='native_guard_gapped_or_clipped_in_sam',base_frame=base['frame'])
    left, center, right = meta['SEQ'][a:a+10],meta['SEQ'][a+10:b-10],meta['SEQ'][b-10:b+10]
    c.require(set(left+center+right) <= set('ACGT'), 'Guarded native DNA differs')
    paths, exclusions = project_centers(window, graph, allowed_walk_hashes)
    availability = f['location_status']
    if not paths:
        availability = 'missing'
    if availability != 'usable':
        paths = []
    directory = Path(directory)
    directory.mkdir()
    values = dict(base_frame_sha256=base['frame']['sha256'],plan_sha256=f['plan_sha256'],query_index=window['query_index'],
                  parent=window['read_id'],chunk_index=window['chunk_index'],tensor_sha256=f['tensor_sha256'],
                  expanded_t_start=moves[a],expanded_t_end=moves[b+10],owned_start=window['read_start']+10,
                  owned_end=window['read_end']-10,availability=availability,graph_sha256=f['graph_sha256'])
    context = directory/'context.tsv'
    c.tabular(context,'context-centers/2',dict(values,**{'sequence_'+str(i):seq for i,seq in enumerate(paths)}))
    frame = dict(read_start=window['read_start'],read_end=window['read_end'],owned_start=window['read_start']+10,
                 owned_end=window['read_end']-10,anchor_bases=10,future_bases=10,expanded_t_start=moves[a],
                 expanded_t_end=moves[b+10],left_guard=left,right_guard=right,native_center=center,
                 retained_chunk_start=retained['chunk_base_start'],retained_chunk_end=retained['chunk_base_end'])
    for prefix,item in [('base_frame',base['frame']),('parent',evidence['parent_pin']),('context',c.pin(context))]:
        frame.update({prefix+'_'+key:value for key,value in item.items()})
    c.tabular(directory/'frame.tsv','guarded-frame/2',frame)
    c.fresh(directory/'construction.json',dict(schema='guarded-window-construction/2',original_window=window,
          base_frame=base['frame'],frame=c.pin(directory/'frame.tsv'),parent=evidence['parent_pin'],
          reconstruction_metadata=evidence['reconstruction_metadata_pins'],retained=retained,
          projection_exclusions=exclusions,owned_native=center,future_source='native MOVES and retained chunk',
          truth_input=False,constructor=c.pin(__file__)))
    t = moves[b+10]-moves[a]
    return dict(query_index=window['query_index'],read_id=window['read_id'],status='constructed',
                frame=c.pin(directory/'frame.tsv'),base_frame=base['frame'],construction=c.pin(directory/'construction.json'),
                work_bound=dict(guide_cells=(t+1)*256*22,phase_updates=t*128*25,
                                context_cells=t*128*max(1,len(paths))*109*109,
                                scalar_cells=t*139*257),owned_start=window['read_start']+10,
                owned_end=window['read_end']-10,native_center=center)
