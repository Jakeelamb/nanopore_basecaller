from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v2/scripts/context-feedback.py')
ORIGINAL_SOURCE_SHA256 = '7a1b9c6f05597dd70e5eb96c894c2ed9e0cf811c28cc7735354fa1aed1f0164b'
SNAPSHOT = Path('/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json')
SNAPSHOT_SHA256 = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'
SCHEMA = Path(__file__).with_name('study') / 'wire-schema.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def original_auditor():
    w = load_module('context_program_original_v2', ORIGINAL)
    require(Path(w.__file__).resolve() == ORIGINAL and w.ROOT == ORIGINAL.parent.parent
            and w.c.ROOT == w.ROOT, 'Original v2 source-location contract differs')
    return w


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')).hexdigest()


def fields(path, schema):
    lines = Path(path).read_text().splitlines()
    require(lines and lines[0] == schema, 'Frame/context schema differs')
    pairs = [line.split('\t') for line in lines[1:]]
    require(all(len(p) == 2 for p in pairs) and len({p[0] for p in pairs}) == len(pairs), 'Duplicate/malformed frame field')
    return dict(pairs)


def field_pin(values, prefix):
    return dict(path=values[prefix + '_path'], size=int(values[prefix + '_size']), sha256=values[prefix + '_sha256'])


def geometry_sha(case, schema):
    recipe = schema['geometry_recipe']
    return hashlib.sha256(('\t'.join([recipe['prefix'], *(str(case[k]) for k in recipe['case_fields'])]) + '\n').encode('ascii')).hexdigest()


def write_packet(path, schema, kind, manifest_sha256, records):
    census = schema[kind + '_records']
    with Path(path).open('x', encoding='ascii', newline='') as stream:
        stream.write('\t'.join(['SCHEMA', schema[kind + '_schema'], manifest_sha256]) + '\n')
        for tag, record in records:
            require(tag in census and set(record) == set(census[tag]), 'Unknown/missing packet field in ' + tag)
            values = [str(record[k]) for k in census[tag]]
            require(not any(any(ch in value for ch in '\t\r\n') for value in values), 'Packet separator in field')
            stream.write('\t'.join([tag, *values]) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def selection(full, private, scope):
    require(scope in ('all', 'query0', 'first32'), 'Unknown input scope')
    ordinary, diagnostic = full['outcomes'], private['outcomes']
    require(len(ordinary) == 451 and len(diagnostic) == 80, 'Full outcome census differs')
    require(Counter(x['context_mode'] for x in ordinary) == {'ordinary': 451}
            and Counter(x['context_mode'] for x in diagnostic) == {'ordinary': 40, 'withheld': 40}, 'Context mode census differs')
    require(sum('native' in x for x in ordinary) == 311
            and Counter(x['context_mode'] for x in diagnostic if 'native' in x) == {'ordinary': 31, 'withheld': 26}, 'Native case census differs')
    require(Counter(x['status'] for x in ordinary) == {'constructed': 311, 'original_excluded': 120, 'boundary_excluded': 20}
            and Counter(x['status'] for x in diagnostic) == {'constructed': 57, 'original_excluded': 18, 'challenge_excluded': 5}, 'Exclusion census differs')
    funnel = private['selection']
    require([funnel[k] for k in ('selected', 'attached', 'scored', 'unambiguous_challenge')] == [60, 40, 31, 26], 'Private funnel differs')
    rows = [('ordinary', x) for x in ordinary] + [('private', x) for x in diagnostic]
    selected = [(namespace, row) for namespace, row in rows if 'native' in row and
                (scope == 'all' or namespace == 'ordinary' and row['query_index'] < (1 if scope == 'query0' else 32))]
    require(selected, 'Scope has no genuine native case')
    inventory = [dict(namespace=namespace, query_index=row['query_index'], parent=row['read_id'],
                      mode=row['context_mode'], status=row['status'], reason=row.get('reason'),
                      native='native' in row) for namespace, row in rows]
    require(len({(x['namespace'], x['query_index'], x['mode']) for x in inventory}) == 531, 'Duplicate case identity')
    return selected, inventory


def sam_index(path, c):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('@'):
            continue
        f = line.split('\t')
        require(len(f) >= 11, 'Short native SAM row')
        if int(f[1]) & 0x900:
            continue
        require(f[0] not in result, 'Duplicate primary native parent')
        reverse = bool(int(f[1]) & 16)
        result[f[0]] = dict(fields=f, reverse=reverse, contig=f[2], start=int(f[3])-1,
                             aligned=f[9], sequence=c.reverse_complement(f[9]) if reverse else f[9],
                             quality=f[10][::-1] if reverse else f[10])
    return result


def reference_geometry(window, observation, c):
    mapping, r = [], observation['start']
    for n, op in c.cigar(observation['fields'][5]):
        if op in 'M=X':
            mapping.extend(range(r, r+n)); r += n
        elif op in 'IS':
            mapping.extend([None]*n)
        elif op in 'DN':
            r += n
        else:
            require(op == 'P', 'Unsupported native CIGAR')
    require(len(mapping) == len(observation['aligned']) and observation['reverse'] == window['reverse']
            and observation['contig'] == window['contig'], 'Native CIGAR/location binding differs')
    def interval(a, b):
        if observation['reverse']:
            a, b = len(mapping)-b, len(mapping)-a
        require(0 <= a < b <= len(mapping) and mapping[a] is not None and mapping[b-1] is not None, 'Native guard reference bounds absent')
        return mapping[a], mapping[b-1]+1
    a, b = window['read_start'], window['read_end']
    require(interval(a,b) == (window['ref_start'],window['ref_end']), 'Native reference anchors differ')
    for x,y in ((a,a+10),(b-10,b+10)):
        lo, hi = (len(mapping)-y,len(mapping)-x) if observation['reverse'] else (x,y)
        values = mapping[lo:hi]
        require(len(values) == y-x and all(v is not None for v in values)
                and all(v == u+1 for u,v in zip(values,values[1:])), 'Native guard gapped/clipped')
    core = window['ref_start']+10, window['ref_end']-10
    require(core[0] < core[1], 'Native reference core is empty')
    return interval(a,b+10), core


def verify_prepared(packet, boundary, stages):
    require(set(packet) == {'completion','manifest','cases','truth','selectedCaseIDs','census'}, 'Prepared descriptor fields differ')
    boundary.check(packet['completion'])
    directory = Path(packet['completion']['path']).parent
    require(Path(packet['completion']['path']) == directory/'complete.json', 'Prepared completion location differs')
    seal = boundary.read(packet['completion']['path'])
    require(seal['schema'] == 'context-program-inputs-complete/1' and seal['complete'] is True
            and seal['manifest'] == packet['manifest'], 'Prepared completion differs')
    for key,name in (('manifest','manifest.json'),('cases','cases.tsv'),('truth','truth.tsv')):
        require(packet[key]['path'] == str(directory/name), 'Prepared packet location differs')
        boundary.check(packet[key])
    manifest = boundary.read(packet['manifest']['path'])
    require(manifest['schema'] == 'context-program-inputs/1'
            and all(manifest[key] == packet[key] for key in ('cases','truth','census','selectedCaseIDs')), 'Prepared manifest differs')
    for key,name in (('inference','inference-manifest.json'),('truth_manifest','truth-manifest.json')):
        require(manifest[key]['path'] == str(directory/name), 'Prepared manifest location differs')
        boundary.check(manifest[key])
    inference = boundary.read(manifest['inference']['path'])
    truth = boundary.read(manifest['truth_manifest']['path'])
    require(inference['schema'] == 'context-program-inference-manifest/1' and inference['truth_input'] is False
            and inference['scope'] == manifest['scope'] and truth['schema'] == 'context-program-truth-manifest/1'
            and truth['inference'] == manifest['inference'], 'Prepared ancestry differs')
    require(truth['regions']['path'] == str(directory/'regions.txt'), 'Prepared regions location differs')
    expected = [packet['cases'],packet['truth'],manifest['inference'],manifest['truth_manifest'],truth['regions']]
    require(len(seal['files']) == 5 and len({item['path'] for item in seal['files']}) == 5
            and {item['path']:item for item in seal['files']} == {item['path']:item for item in expected}, 'Prepared file census differs')
    for item in expected:
        boundary.check(item)
    for key,kind,manifest_key in (('cases','candidate','inference'),('truth','truth','truth_manifest')):
        with Path(packet[key]['path']).open(encoding='ascii') as stream:
            header = stream.readline(4096)
        require(header == '\t'.join(['SCHEMA',boundary.read(SCHEMA)[kind+'_schema'],manifest[manifest_key]['sha256']])+'\n', 'Prepared packet header differs')
    source_map = {item['path']:item for item in manifest['source_pins']}
    require(len(source_map) == len(manifest['source_pins']), 'Prepared consumed source census differs')
    for item in manifest['source_pins']:
        boundary.check(item)
    for item in inference['consumed_pins'] + [truth[key] for key in ('reference','fai','snapshot','samtools','archive','extraction')]:
        require(source_map.get(item['path']) == item, 'Prepared consumed source link differs')
    require(len(inference['cases']) == len(packet['selectedCaseIDs']) == len(set(packet['selectedCaseIDs'])) == packet['census']['selected_cases']
            and [item['case']['case_id'] for item in inference['cases']] == packet['selectedCaseIDs'], 'Prepared case census differs')
    for key,value in inference['census'].items():
        require(packet['census'][key] == value, 'Prepared inference census differs')
    require(inference['original_auditor']['path'] == str(ORIGINAL), 'Original auditor path differs')
    boundary.check(inference['original_auditor'])
    original = original_auditor()
    identity = original.inventory_hash(original.sources())
    require(identity == ORIGINAL_SOURCE_SHA256 == inference['old_source_inventory_sha256'], 'Original source inventory differs')
    proofs = inference['proofs']
    require(len(proofs) == 2 and {proof['phase'] for proof in proofs} == {'full','private'}, 'Original proof census differs')
    for proof in proofs:
        path = original.RESULTS/('v2-'+proof['phase']+'-1')
        require(proof['execution']['path'] == str(path/'execution-complete.json'), 'Original proof location differs')
        boundary.check(proof['execution'])
        require(original.evidence.completed(path,proof['phase'],identity,original.c) == proof, 'Original proof differs')
    mask_directory = original.RESULTS/'v2-observe-full-1/final_rerank'
    observer_proof = truth['observer']
    for key,name in (('completion','complete.json'),('execution','execution-complete.json')):
        require(observer_proof[key]['path'] == str(mask_directory/name), 'Original observer location differs')
        boundary.check(observer_proof[key])
    observer = load_module('context_program_original_observer_reuse',original.ROOT/'tools/context_decoder/observe.py')
    observed = observer.completed_producer(mask_directory/'complete.json','arm','ordinary')
    for stage in observed['stages']:
        original.evidence.stage(stage,original.c)
    mask_names = boundary.read(SCHEMA)['enums']['mask_name']
    require(len(truth['masks']) == len(mask_names)
            and {item['path'] for item in truth['masks']} == {str(mask_directory/('pair-native-'+name)/'matched.bed') for name in mask_names}, 'Original mask census differs')
    for item in truth['masks']:
        boundary.check(item)
        require(item in observed['outputs'], 'Original matched mask lacks producer pin')
    argv = [truth['samtools']['path'],'faidx','-r',truth['regions']['path'],truth['reference']['path']]
    observed_stages = [boundary.read(stage['path']) for stage in stages]
    extraction = [stage for stage in observed_stages if stage['argv'] == argv]
    require(len(extraction) == 1 and extraction[0]['raw']['stdout'] == truth['extraction'], 'Prepared extraction producer differs')
    boundary.check(truth['extraction'])
    return manifest


def project_case(namespace, row, c, check, graph, project_centers, observation, schema):
    for key in ('frame', 'base_frame', 'construction'):
        check(row[key])
    construction = c.read(row['construction']['path'])
    for pin in construction.get('reconstruction_metadata',[]):
        check(pin)
    frame = fields(row['frame']['path'], 'guarded-frame/2')
    base = fields(row['base_frame']['path'], 'context-frame/1')
    result_path = Path(row['native']['completion']['path']).parent / 'result.json'
    seal = c.read(check(row['native']['completion'])['path'])
    result_pin = next(p for p in seal['files'] if p['path'] == str(result_path))
    result = c.read(check(result_pin)['path'])
    require(result['frame'] == row['frame'] == construction['frame'] and result['binding'] == frame
            and construction['base_frame'] == row['base_frame'] == field_pin(frame,'base_frame'), 'Frame/result/construction binding differs')
    parent_pin = check(field_pin(frame,'parent'))
    require(parent_pin == construction['parent'], 'Parent pin differs')
    parent = c.metadata(parent_pin['path'])
    window = construction['original_window']
    require(base['parent'] == parent['read_id'] == row['read_id'] == window['read_id']
            and int(base['query_index']) == row['query_index'] == window['query_index'], 'Foreign case/parent join')
    require(observation['sequence'] == parent['SEQ'] and observation['quality'] == parent['Q'], 'Native SAM/parent sequence differs')
    a,b = window['read_start'],window['read_end']
    require(parent['SEQ'][a:b] == window['stock']
            and parent['SEQ'][a:b+10] == frame['left_guard']+frame['native_center']+frame['right_guard']
            and frame['native_center'] == construction['owned_native'] == row['native_center'], 'Native center/guard attachment differs')
    require((int(frame['owned_start']),int(frame['owned_end'])) == (a+10,b-10)
            and (int(frame['read_start']),int(frame['read_end'])) == (a,b)
            and len(frame['left_guard']) == 10 and len(frame['right_guard']) == 20
            and int(frame['anchor_bases']) == int(frame['future_bases']) == 10, 'Guard ownership differs')
    context_pin = check(field_pin(frame,'context'))
    context = fields(context_pin['path'], 'context-centers/2')
    for k in ('query_index','parent','chunk_index','tensor_sha256','plan_sha256'):
        require(context[k] == base[k], 'Context/base linkage differs')
    for k in ('expanded_t_start','expanded_t_end','owned_start','owned_end'):
        require(context[k] == frame[k], 'Context/guarded linkage differs')
    require(context['base_frame_sha256'] == row['base_frame']['sha256'] and context['graph_sha256'] == base['graph_sha256'], 'Context source pins differ')
    for prefix in ('metadata','tensor','location_sam','location_receipt'):
        check(field_pin(base,prefix))
    metadata = c.metadata(base['metadata_path'])
    tensor_pin = field_pin(base,'tensor')
    with Path(tensor_pin['path']).open('rb') as stream:
        header_bytes = stream.readline(4096)
        header = header_bytes.decode('ascii').rstrip('\n').split('\t')
    require(len(header) == 15 and header[:1] == ['DGS1'] and header[2:5] == ['1024','4','6']
            and header[1] == metadata['T'] and header[13] == metadata['token'] and header[12] == metadata['time_offset'], 'Tensor header geometry differs')
    require(tensor_pin['size'] == len(header_bytes)+int(header[1])*1024*2
            and 0 <= int(frame['expanded_t_start']) < int(frame['expanded_t_end']) <= int(header[1])
            and int(frame['expanded_t_end'])-int(frame['expanded_t_start']) <= 256, 'Tensor size/timestep bounds differ')
    require(metadata['read_id'] == row['read_id'] and metadata['chunk_index'] == base['chunk_index']
            and metadata['score_file'] == Path(tensor_pin['path']).name, 'Chunk metadata binding differs')
    initial = base['initial_context']
    require(len(initial) == 4 and set(initial) <= set('ACGT')
            and sum('ACGT'.index(ch)*4**i for i,ch in enumerate(reversed(initial))) == int(base['initial_state']), 'Initial state/context differs')
    chunk_a, chunk_b = window['chunk_start'],window['chunk_end']
    moves = [i for i,x in enumerate(metadata['MOVES']) if x == '1']
    require(metadata['SEQ'][chunk_a:chunk_b] == window['stock']
            and metadata['SEQ'][chunk_a-4:chunk_a] == initial
            and (moves[chunk_a],moves[chunk_b+10]) == (int(frame['expanded_t_start']),int(frame['expanded_t_end'])), 'Expanded timestep/native chunk differs')
    expected_paths = sorted(value for key,value in context.items() if key.startswith('sequence_'))
    paths = expected_paths if context['availability'] == 'usable' else []
    # This arm comes exclusively from a source graph, never from oracle fragments.
    references = {hashlib.sha256(w['sequence'].encode('ascii')).hexdigest() for w in graph['walks'] if w['is_reference']}
    reference_paths,_ = project_centers(window, graph, references)
    reference_paths = sorted(set(reference_paths) & set(paths))
    expanded, core = reference_geometry(window, observation, c)
    ancestry = dict(parent_pin=parent_pin, initial_context=initial, initial_state=int(base['initial_state']),
                    chunk_index=int(base['chunk_index']), tensor_pin=tensor_pin,
                    expanded_t_start=int(frame['expanded_t_start']), expanded_t_end=int(frame['expanded_t_end']))
    case_id = f'{namespace}/{row["query_index"]}/{row["context_mode"]}'
    outcome = result['outcome']
    case = dict(case_id=case_id,domain='ordinary' if namespace == 'ordinary' else 'private-'+row['context_mode'],
                parent=row['read_id'],contig=window['contig'],strand='-' if window['reverse'] else '+',
                read_start=a,read_end=b,owned_start=a+10,owned_end=b-10,ref_start=expanded[0],ref_end=expanded[1],
                core_start=core[0],core_end=core[1],future_bases=10,left_guard=frame['left_guard'],right_guard=frame['right_guard'],
                native=frame['native_center'],availability=context['availability'],
                escape_capped=int(outcome['reference_free_escape']['center_bound_reached']),
                conditioned_capped=int(outcome['conditioned_search']['center_bound_reached']),
                escape_empty=int(not outcome['reference_free_escape']['finalists']),conditioned_empty=int(not outcome['conditioned_search']['finalists']),
                geometry_ancestry_sha256=digest(ancestry))
    case['geometry_sha256'] = geometry_sha(case,schema)
    candidates = {}
    origins = schema['origins']
    for candidate in outcome['candidates']:
        choice = candidate['choice']; sequence = choice['sequence']; score = choice['signal_likelihood']
        require(score is None or math.isfinite(score), 'Nonfinite retained log mass')
        bits = sum(origins[name] for name,key in (('native','native'),('escape','free_finalist'),('conditioned','conditioned_finalist')) if candidate[key])
        require(sequence not in candidates and bits, 'Duplicate/unattributed retained candidate')
        candidates[sequence] = dict(case_id=case_id,sequence=sequence,origins=bits,log_mass='.' if score is None else repr(score))
    require(case['native'] in candidates and candidates[case['native']]['origins'] & origins['native'], 'Native candidate absent')
    for sequence in paths:
        if sequence not in candidates:
            candidates[sequence] = dict(case_id=case_id,sequence=sequence,origins=0,log_mass='.')
        candidates[sequence]['origins'] |= origins['graph']
    records = [('CASE',case)] + [('PATH',dict(case_id=case_id,sequence=p)) for p in paths]
    records += [('REFPATH',dict(case_id=case_id,sequence=p)) for p in reference_paths]
    records += [('CAND',candidates[p]) for p in sorted(candidates)]
    for role in schema['enums']['baseline_role']:
        choice = outcome[role]
        gate = outcome['gate'] if role == 'selected' else outcome['final_rerank_gate'] if role == 'final_rerank' else '.'
        abstained = outcome['abstained'] if role == 'selected' else outcome.get(role+'_abstained',False)
        records.append(('BASE',dict(case_id=case_id,role=role,sequence=choice['sequence'],log_mass=repr(choice['signal_likelihood']),
                                   potential=repr(choice['context_potential']),objective=repr(choice['objective']),gate=gate,abstained=int(abstained))))
    facts = dict(case=case,window=window,ancestry=ancestry,result=result_pin,construction=row['construction'],frame=row['frame'],
                 base_frame=row['base_frame'],context=context_pin,parent=parent_pin,tensor_header=header,
                 reconstruction_metadata=construction.get('reconstruction_metadata',[]),
                 graph_reference_paths=reference_paths,candidate_count=len(candidates),graph_only=sum(x['origins']==origins['graph'] for x in candidates.values()),
                 origin_census=dict(Counter(str(x['origins']) for x in candidates.values())),
                 escape_entries=len(outcome['reference_free_escape']['finalists']),
                 conditioned_only=sum(bool(x['origins'] & origins['conditioned']) and not x['origins'] & (origins['native']|origins['escape']) for x in candidates.values()))
    return records, facts


def masked_intervals(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        contig,a,b,parent = line.split('\t')
        a,b = int(a),int(b)
        require(0 <= a < b, 'Invalid matched BED interval')
        result.setdefault((parent,contig),[]).append((a,b))
    for spans in result.values():
        spans.sort()
        require(all(a[1] <= b[0] for a,b in zip(spans,spans[1:])), 'Overlapping matched BED intervals')
    return result


def fasta_fragments(path, regions):
    result, name = {}, None
    for line in Path(path).read_text().splitlines():
        if line.startswith('>'):
            name = line[1:]
            require(name in regions and name not in result, 'Unexpected/duplicate faidx region')
            result[name] = ''
        else:
            require(name is not None and set(line) <= set('ACGT'), 'Invalid faidx DNA')
            result[name] += line
    require(set(result) == set(regions), 'Missing faidx region')
    for name,sequence in result.items():
        require(len(sequence) == regions[name][2]-regions[name][1], 'Faidx region length differs')
    return result


def region(contig, start, end):
    require(0 <= start < end, 'Empty/reversed reference request')
    return f'{contig}:{start+1}-{end}'


def label_records(facts, fragments, masks, archives, exclusions, c):
    records = []
    for fact in facts:
        case, window = fact['case'],fact['window']
        case_id = case['case_id']
        ref = fragments[region(case['contig'],case['ref_start'],case['ref_end'])]
        records.append(('TRUTH',dict(case_id=case_id,geometry_sha256=case['geometry_sha256'],reference_forward=ref)))
        if case['domain'] == 'ordinary':
            for name,domain in masks.items():
                for a,b in domain.get((case['parent'],case['contig']),[]):
                    a,b = max(a,case['core_start']),min(b,case['core_end'])
                    if a < b:
                        records.append(('MASK',dict(case_id=case_id,name=name,begin=a,end=b)))
            continue
        query = window['query_index']
        archived = archives.get(query)
        native = case['left_guard']+case['native']+case['right_guard'][:-case['future_bases']]
        forward_native = c.reverse_complement(native) if case['strand'] == '-' else native
        if archived is None:
            require(query in exclusions, 'Missing private archive without exclusion')
            event = dict(case_id=case_id,event_id=f'additional_original/{query}',resolved=0,reference_window='',
                         event_start=0,event_end=0,alt_haplotype='',archived_native_forward=forward_native,reason=exclusions[query])
        else:
            require(archived['parent'] == case['parent'] and archived['reverse'] == window['reverse']
                    and archived['stock'] == native, 'Private archive/native join differs')
            saved_reference = fragments[region(window['contig'],window['ref_start'],window['ref_end'])]
            require(archived['reference_window'] == saved_reference, 'Archived reference differs from pinned FASTA extraction')
            a,b = archived['truth_window_start_in_reference_window'],archived['truth_window_end_in_reference_window']
            require(0 <= a < b <= len(saved_reference) and archived['alt_haplotype'], 'Private event interval differs')
            event = dict(case_id=case_id,event_id=archived['variant'],resolved=1,reference_window=saved_reference,
                         event_start=a,event_end=b,alt_haplotype=archived['alt_haplotype'],archived_native_forward=forward_native,reason='.')
        records.append(('EVENT',event))
    return records


def prepare(output, execution, scope='all'):
    """Run only inside the controller's bounded worker with its recorded stage API."""
    w = original_auditor()
    c = w.c
    output = Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    require(not (output/'complete.json').exists(), 'Preparation output already completed')
    checked = {}
    def check(pin):
        if pin['path'] not in checked:
            execution.budget()
            c.check(pin)
            checked[pin['path']] = pin
        require(checked[pin['path']] == pin, 'Conflicting consumed source pin')
        return pin
    schema = c.read(SCHEMA)
    check(c.pin(SCHEMA)); check(c.pin(__file__))
    original_sources = w.sources()
    identity = w.inventory_hash(original_sources)
    require(identity == ORIGINAL_SOURCE_SHA256, 'Original source inventory differs')
    for source in original_sources:
        check(source)
    full_dir,private_dir = w.RESULTS/'v2-full-1',w.RESULTS/'v2-private-1'
    proofs = [w.evidence.completed(full_dir,'full',identity,c),w.evidence.completed(private_dir,'private',identity,c)]
    execution.budget()
    full,private = c.read(full_dir/'summary.json'),c.read(private_dir/'summary.json')
    selected,inventory = selection(full,private,scope)
    for directory in (full_dir,private_dir):
        check(c.pin(directory/'summary.json')); check(c.pin(directory/'inventory.json'))
    legacy_path = w.ROOT/'config/context-feedback-dev-v1.json'
    legacy = c.read(check(c.pin(legacy_path))['path'])
    admission = c.read(check(c.pin(Path(legacy['inputs']['package'])/'bridge-admission.json'))['path'])
    cohort_pin = check(admission['original']['cohort'])
    require(cohort_pin['sha256'] == legacy['inputs']['original_cohort_sha256'], 'Original cohort identity differs')
    cohort = c.read(cohort_pin['path'])
    registry = c.read(check(c.pin(w.ROOT/'tools/context_decoder/private-context-registry.json'))['path'])
    graph_pins = dict(ordinary=check(cohort['pins']['graph_walks']),private=check(registry['files']['graph_walks']))
    graphs = {name:c.rows(pin['path']) for name,pin in graph_pins.items()}
    g = load_module('context_program_original_guarded',w.ROOT/'tools/context_decoder/guarded_inputs.py')
    sam,records,facts = {},[],[]
    for namespace,row in selected:
        execution.budget()
        base = fields(check(row['base_frame'])['path'],'context-frame/1')
        sam_pin = check(field_pin(base,'location_sam'))
        if sam_pin['path'] not in sam:
            sam[sam_pin['path']] = sam_index(sam_pin['path'],c)
        require(graph_pins[namespace]['sha256'] == base['graph_sha256'], 'Graph file identity differs')
        case_records,fact = project_case(namespace,row,c,check,graphs[namespace][row['query_index']],g.project_centers,
                                         sam[sam_pin['path']][row['read_id']],schema)
        fact['graph'] = graph_pins[namespace]
        records.extend(case_records); facts.append(fact)
    if scope == 'all':
        ordinary = [f for f in facts if f['case']['domain'] == 'ordinary']
        require(sum(f['escape_entries'] for f in ordinary) == 39808
                and sum(f['conditioned_only'] for f in ordinary) == 6631, 'Ordinary candidate origin census differs')
    census = dict(outcomes=len(inventory),ordinary_outcomes=451,private_outcomes=80,native_cases=368,
                  selected_cases=len(facts),unique_candidates=sum(f['candidate_count'] for f in facts),
                  graph_only_candidates=sum(f['graph_only'] for f in facts),private_funnel=[60,40,31,26])
    by_id = {f['case']['case_id']:f for f in facts}
    local_cells = 0
    for tag,record in records:
        if tag != 'CAND':
            continue
        case = by_id[record['case_id']]['case']
        cells = (case['ref_end']-case['ref_start']+1)*(len(case['left_guard'])+len(record['sequence'])+len(case['right_guard'])+1)
        require(cells <= schema['limits']['alignment_cells'], 'Candidate alignment cell cap exceeded')
        local_cells += cells
    census['local_alignment_cells'] = local_cells
    inference = dict(schema='context-program-inference-manifest/1',scope=scope,original_auditor=c.pin(ORIGINAL),
                     old_source_inventory_sha256=identity,proofs=proofs,inventory=inventory,census=census,cases=facts,
                     consumed_pins=list(checked.values()),truth_input=False)
    c.fresh(output/'inference-manifest.json',inference)
    inference_pin = c.pin(output/'inference-manifest.json')
    write_packet(output/'cases.tsv',schema,'candidate',inference_pin['sha256'],records)
    cases_pin = c.pin(output/'cases.tsv')
    # Oracle data becomes reachable only after the immutable inference packet exists.
    snapshot_pin = check(c.pin(SNAPSHOT))
    require(snapshot_pin['sha256'] == SNAPSHOT_SHA256, 'Reference snapshot identity differs')
    snapshot = c.read(SNAPSHOT)
    reference = check(snapshot['reference'])
    fai = check(c.pin(reference['path']+'.fai'))
    samtools = check(snapshot['tools']['samtools'])
    regions = {}
    for fact in facts:
        case,window = fact['case'],fact['window']
        for a,b in ((case['ref_start'],case['ref_end']),(window['ref_start'],window['ref_end'])):
            regions[region(case['contig'],a,b)] = (case['contig'],a,b)
    region_path = output/'regions.txt'
    with region_path.open('x') as stream:
        stream.write(''.join(name+'\n' for name in sorted(regions)))
        stream.flush(); os.fsync(stream.fileno())
    extraction = execution.stage('reference-fragments',[samtools['path'],'faidx','-r',str(region_path),reference['path']])
    extraction_stdout = check(extraction['raw']['stdout'])
    fragments = fasta_fragments(extraction_stdout['path'],regions)
    observer = load_module('context_program_original_observer',w.ROOT/'tools/context_decoder/observe.py')
    mask_directory = w.RESULTS/'v2-observe-full-1/final_rerank'
    mask_seal = observer.completed_producer(mask_directory/'complete.json','arm','ordinary')
    check(c.pin(mask_directory/'complete.json')); check(c.pin(mask_directory/'execution-complete.json'))
    for stage in mask_seal['stages']:
        w.evidence.stage(stage,c)
    masks,pins = {},[]
    for name in schema['enums']['mask_name']:
        path = w.RESULTS/'v2-observe-full-1/final_rerank'/('pair-native-'+name)/'matched.bed'
        pin = check(c.pin(path))
        require(pin in mask_seal['outputs'], 'Matched BED lacks original producer pin')
        pins.append(pin); masks[name] = masked_intervals(path)
    archive_pin = check(registry['archived_cases'])
    archives = c.rows(archive_pin['path'])
    require(len(archives) == 26, 'Private archive census differs')
    exclusions = {int(x['case_id'].rsplit('/',1)[1]):x['reason'] for x in private['selection']['challenge_exclusions']}
    truth_records = label_records(facts,fragments,masks,archives,exclusions,c)
    truth_ancestry = dict(schema='context-program-truth-manifest/1',inference=inference_pin,reference=reference,fai=fai,
                          snapshot=snapshot_pin,samtools=samtools,regions=c.pin(region_path),extraction=extraction_stdout,
                          masks=pins,archive=archive_pin,challenge_exclusions=private['selection']['challenge_exclusions'],
                          observer=dict(completion=c.pin(mask_directory/'complete.json'),execution=c.pin(mask_directory/'execution-complete.json')))
    c.fresh(output/'truth-manifest.json',truth_ancestry)
    truth_manifest_pin = c.pin(output/'truth-manifest.json')
    write_packet(output/'truth.tsv',schema,'truth',truth_manifest_pin['sha256'],truth_records)
    truth_pin = c.pin(output/'truth.tsv')
    resolved_events = {r['case_id']:r for tag,r in truth_records if tag == 'EVENT' and r['resolved']}
    event_cells = 0
    for tag,record in records:
        if tag == 'CAND' and record['case_id'] in resolved_events:
            case = by_id[record['case_id']]['case']
            event = resolved_events[record['case_id']]
            event_cells += (len(event['reference_window'])+1)*(len(case['left_guard'])+len(record['sequence'])+len(case['right_guard'])-case['future_bases']+1)
    census['private_event_alignment_cells'] = event_cells
    census['alignment_cells'] = local_cells+event_cells
    for pin in checked.values():
        execution.budget(); c.check(pin)
    require(c.pin(output/'cases.tsv') == cases_pin, 'Oracle preparation changed inference packet')
    manifest = dict(schema='context-program-inputs/1',scope=scope,cases=cases_pin,truth=truth_pin,
                    inference=inference_pin,truth_manifest=truth_manifest_pin,census=census,
                    selectedCaseIDs=[f['case']['case_id'] for f in facts],source_pins=list(checked.values()),
                    selections=dict(ordinary=full['selection'],private=private['selection']),
                    native_cigar_endpoint='not computed; local edit diagnostic is a separate endpoint')
    c.fresh(output/'manifest.json',manifest)
    manifest_pin = c.pin(output/'manifest.json')
    execution.budget()
    c.fresh(output/'complete.json',dict(schema='context-program-inputs-complete/1',complete=True,manifest=manifest_pin,
                                      files=[cases_pin,truth_pin,inference_pin,truth_manifest_pin,c.pin(region_path)]))
    descriptor = os.open(output,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return dict(completion=c.pin(output/'complete.json'),manifest=manifest_pin,cases=cases_pin,truth=truth_pin,
                selectedCaseIDs=manifest['selectedCaseIDs'],census=census)
