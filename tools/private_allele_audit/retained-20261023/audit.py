import collections, csv, datetime, fcntl, gzip, hashlib, json, math, os, pathlib, re, resource, shlex, shutil, struct, subprocess, sys, time, traceback

P = pathlib.Path('/home/jake/Projects/nanopore_basecaller-private')
R = pathlib.Path('/home/jake/Projects/nanopore_basecaller-reference')
BASE = pathlib.Path(__file__).resolve().parent
O = pathlib.Path(sys.argv[1]).resolve()
utc = lambda: datetime.datetime.now(datetime.timezone.utc)
read = lambda p: json.loads(pathlib.Path(p).read_text())
write = lambda name, value: (O / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def rows(path):
    with open(path) as f:
        for line in f:
            yield json.loads(line)

def pins(value):
    result = []
    if isinstance(value, dict):
        if {'path', 'size', 'sha256'} <= value.keys():
            result.append({k: value[k] for k in ('path', 'size', 'sha256')})
        for child in value.values(): result.extend(pins(child))
    elif isinstance(value, list):
        for child in value: result.extend(pins(child))
    return result

def bits(value):
    return None if value is None else struct.pack('!d', value).hex()

grant = read(O / 'grant.json')
launch = utc()
assert datetime.datetime.fromisoformat(grant['not_before']) <= launch <= datetime.datetime.fromisoformat(grant['latest_start'])
assert grant['max_wall_seconds'] == 300 and grant['actual_owner_release_confirmed'] is True
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)
resource.setrlimit(resource.RLIMIT_RSS, (4 * 1024**3,) * 2)
resource.setrlimit(resource.RLIMIT_CPU, (295, 300))
resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024**2,) * 2)
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
assert shutil.disk_usage(P).free >= 30 * 1024**3
lock = open('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock', 'a')
wait_start = time.monotonic()
while True:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
    except BlockingIOError:
        assert time.monotonic() - wait_start < 30, 'canonical lock wait exceeds 30 seconds'
        time.sleep(.1)
assert utc() < datetime.datetime.fromisoformat(grant['hard_end'])
start = utc()
write('admission.json', dict(launch=launch.isoformat(), acquired=start.isoformat(), lock_wait_seconds=time.monotonic()-wait_start,
    affinity=sorted(os.sched_getaffinity(0)), as_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],
    free_bytes=shutil.disk_usage(P).free, grant=grant))

result = dict(start=start.isoformat(), phases={}, risks=[], errors=[], producer_replay=False)
hash_cache = {}
hashed_bytes = 0
reused_hashes = []
reuse_source_evidence = {}
retained = {}
checked = []
drift = []
all_pins = []
context = {}
if 'reuse_pin_checks' in grant:
    prior_path=pathlib.Path(grant['reuse_pin_checks'])
    prior=read(prior_path.parent/'result.json')
    assert prior['phases']['closure']['status']=='pass'
    proof_paths=[prior_path,prior_path.parent/'result.json',prior_path.parent/'audit.py.sha256',prior_path.parent/'project.rs.sha256',pathlib.Path(grant['prior_auditor_source']),pathlib.Path(grant['prior_helper_source'])]
    proofs=[dict(path=str(p),size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in proof_paths]
    assert proofs[-2]['sha256']==(prior_path.parent/'audit.py.sha256').read_text().split()[0]
    assert proofs[-1]['sha256']==(prior_path.parent/'project.rs.sha256').read_text().split()[0]
    assert proofs[0]['sha256']==grant['reuse_pin_checks_sha256'] and proofs[1]['sha256']==grant['reuse_result_sha256']
    reuse_source_evidence=dict(prior_phase='closure',prior_overall_complete=prior['complete'],proofs=proofs,
        qualification='Prior successful SHA reads reused with current size and mtime checks. This is operational reuse, not fresh content hashing of those resources.')
    prior_end=datetime.datetime.fromisoformat(prior['end']).timestamp()
    for entry in read(prior_path):
        expected=entry['expected'];target=pathlib.Path(entry['checked_path'])
        if expected['size']<=1024**2:continue
        stat=target.stat()
        assert stat.st_size==expected['size'] and stat.st_mtime<=prior_end,('changed since prior SHA pass',str(target))
        hash_cache[(str(target),stat.st_size,stat.st_mtime_ns)]={**expected,'path':str(target)}
        reused_hashes.append(dict(prior_receipt=str(prior_path),expected=expected,checked_path=str(target),current_mtime_ns=stat.st_mtime_ns,current_size=stat.st_size))

def pin(path):
    global hashed_bytes
    path = pathlib.Path(path)
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in hash_cache:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(4 * 1024**2), b''): h.update(block)
        hashed_bytes += st.st_size
        hash_cache[key] = dict(path=str(path), size=st.st_size, sha256=h.hexdigest())
    return hash_cache[key]

def check(p):
    expected = {k:p[k] for k in ('path','size','sha256')}
    original = pathlib.Path(p['path'])
    alternate = retained.get((p['path'], p['sha256']))
    target = alternate or original
    actual = pin(target)
    assert (actual['size'], actual['sha256']) == (p['size'], p['sha256']), (expected, actual)
    checked.append(dict(expected=expected, checked_path=str(target)))
    if alternate and original.exists() and original.stat().st_size < 20*1024**2:
        current = pin(original)
        if current['sha256'] != p['sha256']:
            drift.append(dict(original=expected, current=current, authoritative_retained=actual))
    return actual

def phase(name, function):
    print(json.dumps(dict(phase=name, state='start', utc=utc().isoformat())), flush=True)
    began = time.monotonic()
    dependency={'receipts':'closure','tensor_association':'receipts','case_audit':'tensor_association','decisions_and_reports':'case_audit','denominators':'case_audit','truth_rejection':'case_audit'}.get(name)
    if dependency and result['phases'][dependency]['status']!='pass':
        result['phases'][name]=dict(status='blocked',depends_on=dependency)
        result['errors'].append(name)
        write('progress.json',result)
        print(json.dumps(dict(phase=name,**result['phases'][name])),flush=True)
        return
    try:
        value = function()
        result['phases'][name] = dict(status='pass', seconds=time.monotonic()-began, evidence=value)
    except Exception as error:
        text = traceback.format_exc()
        (O / (name + '.failure.txt')).write_text(text)
        result['phases'][name] = dict(status='fail', seconds=time.monotonic()-began, error=str(error))
        result['errors'].append(name)
    write('progress.json', result)
    print(json.dumps(dict(phase=name, **result['phases'][name])), flush=True)

def closure():
    units = [P/'results/private-allele'/name for name in ('actual-v2-flank','actual-v3-attachment','additional-graph-v1','additional-original-score-v2','additional-challenge-v1')]
    for unit in (units[0], units[1], units[-1]):
        retention = read(unit/'source-retention.json')
        for item in retention:
            a,b = item['original'],item['retained']
            assert (a['size'],a['sha256']) == (b['size'],b['sha256'])
            retained[(a['path'],a['sha256'])] = b['path']
            all_pins.append(b)
    manifests = {}
    for unit in units:
        complete = read(unit/'complete.json')
        assert complete['complete'] is True
        manifests[str(unit)] = pin(unit/'complete.json')
        all_pins.extend(pins(complete))
        if 'files' in complete:
            expected = {p['path'] for p in complete['files']}
            if unit.name.startswith('actual-'):
                actual = {str(p) for p in unit.rglob('*') if p.is_file() and p.name != 'complete.json'}
                assert actual == expected, dict(missing=sorted(expected-actual), unregistered=sorted(actual-expected))
        if unit.name=='additional-challenge-v1':
            expected={p['path'] for p in complete['outputs']}|{r['retained']['path'] for r in read(unit/'source-retention.json')}
            actual={str(p) for p in unit.rglob('*') if p.is_file() and p.name!='complete.json'}
            assert actual==expected,dict(missing=sorted(expected-actual),unregistered=sorted(actual-expected))
        for directory,key in [('graph','graph_files'),('candidates','files')]:
            if key in complete and (unit/directory).is_dir():
                expected={p['path'] for p in complete[key]}
                actual={str(p) for p in (unit/directory).rglob('*') if p.is_file()}
                assert actual==expected,dict(unit=str(unit),missing=sorted(expected-actual),unregistered=sorted(actual-expected))
        if (unit/'admission.json').exists(): all_pins.extend(pins(read(unit/'admission.json')))
    context['units'] = units
    context['manifests'] = manifests
    unique = {(p['path'],p['sha256']):p for p in all_pins}
    write('hash-plan.json', dict(files=len(unique), registered_bytes=sum(p['size'] for p in unique.values()), largest=sorted(unique.values(),key=lambda p:p['size'],reverse=True)[:10]))
    for p in unique.values(): check(p)
    for name in ('cases.jsonl','inference.jsonl','decisions.jsonl','report.json','challenge-build.json'):
        a,b = [pin(unit/'output'/name) for unit in units[:2]]
        assert (a['size'],a['sha256']) == (b['size'],b['sha256']), name
    source_rows = []
    for (original, sha), path in retained.items():
        if '/src/' in original or original.endswith(('Cargo.toml','Cargo.lock')):
            source_rows.append(dict(original=original, sha256=sha, retained=path))
    write('source-closure.json',source_rows)
    context['binary'] = next(path for (original,sha),path in retained.items() if original.endswith('/release/private-allele-challenge') and '/additional-challenge-v1/' in path)
    return dict(manifests=manifests, pin_checks=len(checked), retained_revisions=len(retained), original_output_equality=True, newly_hashed_bytes=hashed_bytes,reused_hash_checks=len(reused_hashes))

def raw_receipt(path, success=True):
    receipt = read(path)
    assert (receipt['status']=='finished' and receipt['exit']==0) if success else (receipt['status']=='command_failed' and receipt['exit']!=0)
    for p in pins(receipt): check(p)
    raw = pathlib.Path(receipt['recorder'])
    assert (raw/'cwd.txt').read_text().strip()==str(P if pathlib.Path(path).is_relative_to(P) else R)
    argv = shlex.split((raw/'command.sh').read_text())
    assert argv == receipt['argv']
    assert str(raw/'stdout') == receipt['stdout']
    return raw_evidence(raw, expected_exit=receipt['exit'], receipt=receipt, receipt_path=path)

def raw_evidence(raw, expected_exit=0, receipt=None, receipt_path=None):
    raw=pathlib.Path(raw)
    code=int((raw/'exit-status.txt').read_text())
    assert code==expected_exit
    begin=datetime.datetime.fromisoformat((raw/'start.txt').read_text().strip().replace('Z','+00:00'))
    end=datetime.datetime.fromisoformat((raw/'end.txt').read_text().strip().replace('Z','+00:00'))
    assert begin<=end
    cwd=(raw/'cwd.txt').read_text().strip()
    assert pathlib.Path(cwd).is_dir()
    timed=(raw/'time.txt').read_text()
    assert 'Command being timed:' in timed
    assert 'Maximum resident set size (kbytes):' in timed
    assert 'Exit status: '+str(code) in timed or code!=0
    if receipt:
        launched=datetime.datetime.fromisoformat(receipt['native_launch_utc'])
        finished=datetime.datetime.fromisoformat(receipt['native_end_utc'])
        assert begin-datetime.timedelta(seconds=1)<=launched<=finished<=end+datetime.timedelta(seconds=1.25)
        assert receipt['native_end_monotonic_ns']>=receipt['native_launch_monotonic_ns']
    files=[pin(p) for p in sorted(raw.iterdir()) if p.is_file()]
    return dict(receipt=str(receipt_path) if receipt_path else None, recorder=str(raw), command=(raw/'command.sh').read_text().strip(), cwd=cwd,
        start=begin.isoformat(), end=end.isoformat(), exit=code, rss_kib=int(re.search(r'Maximum resident set size \(kbytes\): (\d+)',timed)[1]), files=files)

def receipts():
    dev=R/'results/graph-prior/pilot-v1/development'
    registry={p['path']:p for p in pins(read(R/'provenance/verification/graph-prior-v1.json'))}
    protocol=read(P/'config/private-allele-dev-v1.json')
    assert pin(R/'provenance/verification/graph-prior-v1.json')['sha256']==protocol['registered_pilot_sha256']
    receipt_rows=[]
    artifacts={}
    for name in ('windows','local-decode','observe-native','graph-context'):
        path=dev/'artifacts'/(name+'.json')
        assert pin(path)==registry[str(path)]
        artifacts[name]=read(path)
        for p in pins(artifacts[name]): check(p)
    native=read(dev/'native.json')
    assert pin(dev/'native.json')==registry[str(dev/'native.json')]
    registry.update({p['path']:p for p in pins(native)})
    source={}
    context.update(dev=dev,registry=registry,source=source)
    for stage in ('native-call','native-decode','native-align','native-sam','truth-subset','truth-normalize','observe-native','windows','local-decode','graph-context'):
        matches=list((dev/'stages'/stage).glob('*/finish.json'))
        assert len(matches)==1,stage
        path=matches[0]
        assert pin(path)==registry[str(path)], ('unregistered receipt',stage)
        source[stage]=read(path)
        receipt_rows.append(raw_receipt(path))
        registry.update({p['path']:p for p in pins(source[stage])})
    option=lambda argv,key:argv[argv.index(key)+1]
    mapped=option(source['local-decode']['argv'],'--sam')
    context['mapped']=mapped
    assert mapped==option(source['windows']['argv'],'--sam')==option(source['observe-native']['argv'],'--sam')==source['native-sam']['stdout']
    assert source['native-sam']['argv'][-1]==source['native-align']['stdout']
    assert source['native-align']['argv'][3]==source['native-call']['stdout']
    assert source['native-decode']['argv'][-1]==native['bam']['path']==source['native-call']['stdout']
    assert native['sam']['path']==source['native-decode']['stdout']
    assert mapped!=native['sam']['path']
    inputs=read(R/'results/reference-assisted/inputs-native-frozen-v1.json')
    context['inputs']=inputs
    assert source['truth-subset']['argv'][-1]==inputs['original_truth_vcf']['path']
    assert source['truth-normalize']['argv'][-1]==source['truth-subset']['stdout']
    assert option(source['observe-native']['argv'],'--vcf')==source['truth-normalize']['stdout']
    for key in ('reference','confident'):
        assert option(source['observe-native']['argv'],'--'+key)==inputs[key]['path']
        check(inputs[key])
    check(inputs['original_truth_vcf'])
    assert source['observe-native']['argv']==artifacts['observe-native']['argv']
    assert source['local-decode']['argv']==artifacts['local-decode']['argv']
    assert source['windows']['argv']==artifacts['windows']['argv']
    for unit in context['units'][2:4]: receipt_rows.append(raw_receipt(pathlib.Path(read(unit/'complete.json')['producer']['path'])))
    failed_scores=list((P/'results/private-allele/additional-original-score-v1/stages/score').glob('*/finish.json'))
    assert len(failed_scores)==1
    failed=read(failed_scores[0]);successful=read(context['units'][3]/'complete.json');successful=read(successful['producer']['path'])
    receipt_rows.append(raw_receipt(failed_scores[0],success=False))
    output_index=failed['argv'].index('--output')+1
    assert failed['argv'][:output_index]==successful['argv'][:output_index] and failed['argv'][output_index+1:]==successful['argv'][output_index+1:]
    for stage in ('build-receipt','infer-receipt','report-receipt'):
        directory=P/'results/private-allele/actual-v3-attachment'/stage
        assert int((directory/'exit-status.txt').read_text())==0
        assert datetime.datetime.fromisoformat((directory/'start.txt').read_text().strip())<=datetime.datetime.fromisoformat((directory/'end.txt').read_text().strip())
        argv=read(directory/'argv.json')
        assert argv[0].endswith('/private-allele-challenge')
    raw_final=pathlib.Path(read(context['units'][-1]/'complete.json')['producer_files'][0]['path']).parent
    assert (raw_final/'cwd.txt').read_text().strip()==str(P)
    receipt_rows.append(raw_evidence(raw_final))
    assert 'cargo build --release --offline --manifest-path tools/private_allele_challenge/Cargo.toml' in (raw_final/'command.sh').read_text()
    catalogue=R/'results/reference-frontier/catalogue-v1/full-roundtrip'
    complete=read(catalogue/'complete.json')
    assert complete['kind']=='full' and complete['complete']
    for p in pins(complete): check(p)
    attempt=read(catalogue/'attempt.json')
    for p in pins(attempt): check(p)
    expanded_raw=R/'logs/20261023T153558Z-frontier-catalogue-full-roundtrip-UnfjQf'
    assert (expanded_raw/'cwd.txt').read_text().strip()==str(R)
    expanded_evidence=raw_evidence(expanded_raw)
    command=shlex.split((expanded_raw/'command.sh').read_text())
    assert command[command.index(attempt['argv'][0]):]==attempt['argv']
    announcement=read(expanded_raw/'stdout')
    check(announcement['completion'])
    assert announcement['completion']==pin(catalogue/'complete.json') and announcement['partial'] is False
    receipt_rows.append(expanded_evidence)
    write('recorder-closure.json',receipt_rows)
    context.update(dev=dev,mapped=mapped,inputs=inputs,registry=registry,source=source)
    return dict(receipts=len(receipt_rows), original_native_mapped_chain=True, original_truth_chain=True,
        final_recorded_end=receipt_rows[-2]['end'], final_known_one_second_deviation=True,failed_score_attempt_retained=True,score_retry_argv_unchanged_except_output=True)

def kv(path):
    lines=pathlib.Path(path).read_text().splitlines()
    out=dict(line.split('\t',1) for line in lines)
    assert len(out)==len(lines)
    return out

def rc(sequence): return sequence.translate(str.maketrans('ACGTRYMKBDHVN','TGCAYRKMVHDBN'))[::-1]
def oriented(sequence, reverse): return rc(sequence) if reverse else sequence
def cigar(text):
    ops=[(int(n),op) for n,op in re.findall(r'(\d+)([MIDNSHP=X])',text)]
    assert ''.join(str(n)+op for n,op in ops)==text and all(n>0 for n,op in ops)
    return ops

def overlap(a,b): return a['start']<b['end'] and b['start']<a['end']

def extract(sequence,text,reference_start,span):
    r=reference_start;q=0;start=None;end=None
    for n,op in cigar(text):
        if op in 'M=X':
            if r<=span['start']<r+n:start=q+span['start']-r
            if r<=span['end']-1<r+n:end=q+span['end']-r
            r+=n;q+=n
        elif op=='I':
            assert r not in (span['start'],span['end']),'boundary insertion'
            q+=n
        elif op in 'DN':
            assert not (op=='N' and overlap(dict(start=r,end=r+n),span)),'reference skip'
            assert not (r<=span['start']<r+n or r<span['end']<=r+n),'boundary deletion'
            r+=n
        elif op=='S':q+=n
        elif op=='H':raise AssertionError('hard clipping')
        elif op!='P':raise AssertionError(op)
        assert q<=len(sequence)
    assert q==len(sequence) and start is not None and end is not None
    return sequence[start:end],dict(start=start,end=end)

def sams(path, ids):
    out={}
    with open(path) as f:
        for line in f:
            if line.startswith('@'): continue
            row=line.rstrip('\n').split('\t')
            if row[0] not in ids or int(row[1])&(256|2048): continue
            assert row[0] not in out and len(row[9])==len(row[10])
            reverse=bool(int(row[1])&16)
            out[row[0]]=dict(id=row[0],flag=int(row[1]),contig=row[2],pos=int(row[3])-1,mapq=int(row[4]),cigar=row[5],aligned=row[9],seq=oriented(row[9],reverse),qual=row[10][::-1] if reverse else row[10],reverse=reverse)
    assert set(out)==set(ids)
    return out

def tensor_association():
    dev=context['dev']; export=dev/'native-export'
    windows={w['query_index']:w for w in rows(dev/'windows/windows.jsonl')}
    added=list(rows(P/'results/private-allele/actual-v3-attachment/output/additional-attached-windows.jsonl'))
    cases=list(rows(P/'results/private-allele/actual-v3-attachment/output/cases.jsonl'))+list(rows(P/'results/private-allele/additional-challenge-v1/cases.jsonl'))
    selected=read(P/'results/private-allele/actual-v3-attachment/output/additional-windows.json')['targets']
    ids={t['source_uuid'] for t in selected}|{c['parent'] for c in cases}
    mapped=sams(context['mapped'],ids)
    native=sams(read(dev/'native.json')['sam']['path'],ids)
    assert all((s['seq'],s['qual'])==(native[p]['seq'],native[p]['qual']) for p,s in mapped.items())
    metadata=collections.defaultdict(list)
    for path in export.glob('*.scores.meta.tsv'):
        m=kv(path)
        if m['read_id'] in ids: metadata[m['read_id']].append(m)
    reconstructed={}; headers={}; tensor_checks=[];reconstruction_results={}
    for parent in sorted(ids):
        pm=kv(export/(parent+'.parent.tsv'))
        assert pm['format']=='DGP1' and pm['read_id']==parent and int(pm['stride'])==6
        chunks=sorted(metadata[parent],key=lambda m:int(m['chunk_index']))
        assert len(chunks)==int(pm['chunk_count']) and [int(m['chunk_index']) for m in chunks]==list(range(len(chunks)))
        parts=[]; quals=[]; moves=[]; retained_rows=[]; front=0
        for i,m in enumerate(chunks):
            assert m['format']=='DGM1' and m['read_id']==parent and m['chunk_count']==pm['chunk_count']
            assert all(ch in '01' for ch in m['MOVES']) and m['MOVES'].count('1')==len(m['SEQ'])==len(m['Q'])
            path=export/m['score_file']
            with path.open('rb') as f: raw=f.readline(4096)
            h=raw.decode().strip().split('\t')
            assert len(h)==15 and h[0]=='DGS1' and h[2:5]==['1024','4','6']
            assert int(h[1])==len(m['MOVES'])==int(m['T']) and int(h[2])==int(m['C'])
            assert h[12]==m['time_offset'] and h[13]==m['token'] and m['score_file']==h[13]+'_s'+h[14]+'.scores'
            assert path.stat().st_size==len(raw)+int(h[1])*1024*2
            for key in ('signal_samples','num_trimmed_samples','variable_chunk_sizes'): assert m[key]==pm[key]
            assert int(m['original_signal_samples'])==int(pm['signal_samples'])+int(pm['num_trimmed_samples'])
            raw_samples=int(m['raw_chunk_size']);gran=int(m['chunk_size_granularity']);T=len(m['MOVES'])
            assert ((raw_samples+gran-1)//gran*gran+T//2)//T==6
            if i+1<len(chunks):
                overlap=int(m['input_offset'])+raw_samples-int(chunks[i+1]['input_offset'])
                assert overlap>=0 and overlap%6==0
                end=T-overlap//6//2; following=overlap//6-overlap//6//2
            elif len(chunks)==1 or pm['variable_chunk_sizes']=='1': end=(min(int(pm['signal_samples']),raw_samples)+5)//6;following=0
            else: end=T;following=0
            assert 0<=front<=end<=T
            a=m['MOVES'][:front].count('1');b=m['MOVES'][:end].count('1')
            pbase=sum(map(len,parts))
            parts.append(m['SEQ'][a:b]);quals.append(m['Q'][a:b]);moves.append(m['MOVES'][front:end])
            retained_rows.append(dict(m=m,t_start=front,t_end=end,chunk_base_start=a,parent_base_start=pbase,parent_base_end=pbase+b-a))
            front=following
            tensor_pin=pin(path)
            expected=context['registry'].get(str(path))
            if expected: assert tensor_pin==expected
            headers[m['score_file']]=tensor_pin
            tensor_checks.append(dict(parent=parent,chunk=i,header=h,score=tensor_pin,registered=expected is not None))
        seq=''.join(parts);qual=''.join(quals);mv=''.join(moves)
        if len(mv)>int(pm['signal_samples'])//6:
            if mv[-1]=='1':seq=seq[:-1];qual=qual[:-1]
            mv=mv[:-1];retained_rows[-1]['t_end']-=1;retained_rows[-1]['parent_base_end']=len(seq)
        assert (seq,qual,mv)==(pm['SEQ'],pm['Q'],pm['MOVES'])
        if (seq,qual)!=(mapped[parent]['seq'],mapped[parent]['qual']):
            reconstruction_results[parent]='export/native primary parent SEQ/Q mismatch'
        else:
            reconstruction_results[parent]=None
            reconstructed[parent]=retained_rows
    attachment=read(P/'results/private-allele/actual-v3-attachment/output/additional-attachment.json')
    wanted_parents=sorted({t['source_uuid'] for t in selected})
    assert attachment['parent_reconstruction']==[dict(source_uuid=p,reconstructed=reconstruction_results[p] is None,reason=reconstruction_results[p]) for p in wanted_parents]
    assert all(c['parent'] in reconstructed for c in cases) and all(w['read_id'] in reconstructed for w in added)
    checked_windows=[]
    for w in list(windows.values())+added:
        if w['read_id'] not in ids:continue
        assert w['read_id'] in reconstructed
        parent=mapped[w['read_id']]
        assert parent['seq'][w['read_start']:w['read_end']]==w['stock'] and parent['reverse']==w['reverse']
        retained_row=next(x for x in reconstructed[w['read_id']] if w['read_start']>=x['parent_base_start']+25 and w['read_end']+25<=x['parent_base_end'])
        m=retained_row['m'];a=retained_row['chunk_base_start']+w['read_start']-retained_row['parent_base_start'];b=a+len(w['stock'])
        emissions=[t for t,mv in enumerate(m['MOVES']) if mv=='1']
        ta=emissions[a];tb=emissions[b] if b<len(emissions) else retained_row['t_end']
        assert (a,b,ta,tb,m['SEQ'][a-4:a],m['score_file'],int(m['chunk_index']))==(w['chunk_start'],w['chunk_end'],w['t_start'],w['t_end'],w['context'],w['score_file'],w['chunk_index'])
        assert a>=4 and m['SEQ'][a:b]==w['stock'] and retained_row['t_start']<=ta<tb<=retained_row['t_end'] and tb-ta<=256
        checked_windows.append(dict(parent=w['read_id'],query=w['query_index'],score=headers[w['score_file']],t_start=ta,t_end=tb))
    write('tensor-associations.json',dict(parents=sorted(ids),parent_reconstruction=reconstruction_results,tensors=tensor_checks,windows=checked_windows))
    with open(dev/'windows/windows.jsonl') as f:
        window_hashes={json.loads(raw)['query_index']:hashlib.sha256(raw.rstrip('\n').encode()).hexdigest() for raw in f}
    context.update(windows=windows,added={w['query_index']:w for w in added},mapped_sams=mapped,tensor_pins=headers,reconstructed=reconstructed,reconstruction_results=reconstruction_results,window_line_hashes=window_hashes)
    return dict(parents=len(ids),successful_parent_reconstructions=len(reconstructed),reconstruction_exclusions={p:r for p,r in reconstruction_results.items() if r},chunk_headers=len(tensor_checks),windows=len(checked_windows),registered_tensors=sum(x['registered'] for x in tensor_checks),native_SEQ_Q_MOVES_exact_for_admitted=True)

def project(case, sequences):
    lines=['\t'.join([case['reference_window'],str(case['truth_window_start_in_reference_window']),str(case['truth_window_end_in_reference_window']),case['alt_haplotype'],oriented(s,case['reverse'])]) for s in sequences]
    done=subprocess.run([str(O/'project')],input='\n'.join(lines)+'\n',text=True,capture_output=True,check=True,timeout=30)
    values=done.stdout.splitlines()
    assert len(values)==len(sequences)
    return dict(zip(sequences,values))

def trimmed(walk, graph, window):
    seq=walk['sequence'];rp=graph['reference']['start'];qp=0;mapping={}
    for count,op in cigar(walk['cigar']):
        if op in 'M=X':
            for k in range(count):mapping[rp+k]=qp+k
            rp+=count;qp+=count
        elif op=='I':qp+=count
        elif op=='D':rp+=count
        else:raise AssertionError(op)
    assert qp==len(seq) and rp==graph['reference']['end']
    a=mapping[window['ref_start']];b=mapping[window['ref_end']-1]+1
    assert all(mapping[window['ref_start']+k]==a+k and mapping[window['ref_end']-10+k]==b-10+k for k in range(10))
    return oriented(seq[a:b],window['reverse'])

def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        old=row[0];row[0]=i
        for j,y in enumerate(b,1):
            previous=row[j];row[j]=min(row[j]+1,row[j-1]+1,old+(x!=y));old=previous
    return row[-1]

def compatibility(evidence, prototypes):
    left={};right={};both={}
    for p in prototypes:
        l=distance(evidence['left'],p['left']);r=distance(evidence['right'],p['right']);c=p['center']
        for table,d in ((left,l),(right,r),(both,l+r)):table[c]=min(table.get(c,d),d)
    best=lambda table:sorted(c for c,d in table.items() if d==min(table.values())) if table else []
    lb=best(left);rb=best(right);abstain=bool(both) and set(lb).isdisjoint(rb);minimum=min(both.values(),default=0)
    bonuses={c:1.0 if abstain or d==minimum else math.log1p(math.expm1(1)*math.exp(-math.log(3)*(d-minimum))) for c,d in both.items()}
    return dict(mode='empty-neutral' if not both else 'left-right-disagreement-binary' if abstain else 'conditioned',distances=both,bonuses=bonuses,left_best=lb,right_best=rb)

def near(a,b):
    if isinstance(a,dict):assert a.keys()==b.keys();[near(a[k],b[k]) for k in a]
    elif isinstance(a,list):assert len(a)==len(b);[near(x,y) for x,y in zip(a,b)]
    elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-14,abs_tol=1e-15),(a,b)
    else:assert a==b,(a,b)

def case_audit():
    compile_result=subprocess.run(['rustc','-O',str(BASE/'project.rs'),'-o',str(O/'project')],capture_output=True,text=True,timeout=30)
    (O/'rustc.stderr').write_text(compile_result.stderr)
    assert compile_result.returncode==0
    fixtures='GCTAAAATCG\t1\t9\tCTAAAAATC\tGCTAAAAATCG\nAAAA\t1\t3\tAAA\tAAAAA\nACGT\t1\t3\tCG\tACGT\n'
    fixture=subprocess.run([str(O/'project')],input=fixtures,text=True,capture_output=True,check=True)
    assert fixture.stdout.splitlines()==['alt','ambiguous','alt']
    (O/'projection-controls.txt').write_text(fixtures+'\nObserved\n'+fixture.stdout)
    primary=P/'results/private-allele/actual-v3-attachment/output';additional=P/'results/private-allele/additional-challenge-v1'
    groups=[]
    for name,work,count in [('original-expanded',primary,76),('additional',additional,26)]:
        cases=list(rows(work/'cases.jsonl'));inference=list(rows(work/'inference.jsonl'));decisions=list(rows(work/'decisions.jsonl'))
        cm={c['case_id']:c for c in cases};im={c['case_id']:c for c in inference}
        assert len(cm)==len(cases)==len(im)==len(inference)==count and cm.keys()==im.keys()
        assert collections.Counter(c['dataset'] for c in cases)==({'original':38,'expanded':38} if name=='original-expanded' else {'additional_original':26})
        assert all(c['case_id']==c['dataset']+'/'+str(c['query_index']) and c['truth_inference_use'] is False for c in cases)
        assert all(i['schema']=='private-allele-inference/1' for i in inference)
        groups.append((name,work,cm,im,decisions))
    context['groups']=groups
    all_cases={};all_inference={};saved={};wanted=collections.defaultdict(dict)
    for name,work,cm,im,decisions in groups:
        assert all_cases.keys().isdisjoint(cm)
        all_cases.update(cm);all_inference.update(im)
        for cid,c in cm.items():wanted[c['saved_scores_file']][c['query_index']]=cid
    context.update(all_cases=all_cases,all_inference=all_inference)
    compared=0;all_score_rows={}
    for path,queries in wanted.items():
        seen=set();scored=0;excluded=[]
        with open(path) as f:
            for raw in f:
                row=json.loads(raw);q=row['query_index'];assert q not in seen;seen.add(q)
                if row['status']=='scored':scored+=1
                else:assert row['status']=='excluded';excluded.append(q)
                if q not in queries:continue
                cid=queries[q];c=all_cases[cid];inf=all_inference[cid]
                assert row['status']=='scored' and row['read_id']==c['parent'] and hashlib.sha256(raw.rstrip('\n').encode()).hexdigest()==c['saved_row_sha256']
                hs=row['hypotheses'];ih=inf['hypotheses']
                assert len(hs)==len(ih)==c['all_hypotheses']
                assert [(h['sequence'],bits(h['likelihood'])) for h in hs]==[(h['sequence'],bits(h['likelihood'])) for h in ih]
                assert len({h['sequence'] for h in ih})==len(ih)
                assert all(h['likelihood'] is None or math.isfinite(h['likelihood']) for h in ih)
                assert all(h['ordinary']==s['graph_presence'] and (not h['withheld'] or h['ordinary']) for h,s in zip(ih,hs))
                assert next(bits(h['likelihood']) for h in ih if h['sequence']==inf['stock'])==bits(row['stock_likelihood'])
                w=(context['added'] if c['dataset']=='additional_original' else context['windows'])[q]
                assert context['tensor_pins'][w['score_file']]['sha256']==row['score_sha256']==c['tensor_sha256']
                assert c['stock']==inf['stock']==w['stock'] and c['reverse']==w['reverse']
                assert set(inf)=={'schema','case_id','stock','hypotheses','ordinary_flank','withheld_flank'}
                assert all(set(h)=={'sequence','likelihood','ordinary','withheld'} for h in ih)
                saved[cid]=row;compared+=len(ih)
        assert seen==set(context['added'] if 'additional-original-score-v2' in path else context['windows'])
        all_score_rows[path]=dict(total=len(seen),scored=scored,excluded=excluded)
    for cid,c in all_cases.items():
        if c['dataset']=='expanded':
            original=all_inference['original/'+str(c['query_index'])]['hypotheses']
            expanded={h['sequence']:h for h in all_inference[cid]['hypotheses']}
            assert all(expanded[h['sequence']]==h for h in original)
    graphs={q['query_index']:q for q in rows(context['dev']/'graph/walks.jsonl')}
    new_graphs={q['query_index']:q for q in rows(P/'results/private-allele/additional-graph-v1/graph/walks.jsonl')}
    plans={p['query_index']:p for p in rows('/home/jake/Projects/nanopore_basecaller-flank/results/flank-prior/20261023T165826Z-eligibility/plans.jsonl')}
    variants={v['variant']:v for v in csv.DictReader(open(context['dev']/'alleles/native/variants.tsv'),delimiter='\t')}
    observations={(o['parent'],o['variant']):o['call'] for o in csv.DictReader(open(context['dev']/'alleles/native/observations.tsv'),delimiter='\t')}
    projection_count=0;prototype_count=0;eligible=0;reverse=0;detail=[]
    for cid,c in all_cases.items():
        inf=all_inference[cid];q=c['query_index'];extra=c['dataset']=='additional_original';w=(context['added'] if extra else context['windows'])[q];g=(new_graphs if extra else graphs)[q]
        assert observations[(c['parent'],c['variant'])]=='alt'
        v=variants[c['variant']]
        sam=context['mapped_sams'][c['parent']]
        native_truth,_=extract(sam['aligned'],sam['cigar'],sam['pos'],dict(start=int(v['start0']),end=int(v['end0'])))
        assert native_truth==v['alt_haplotype']
        assert (c['stratum'],c['alt_haplotype'])==(v['stratum'],v['alt_haplotype'])
        s=int(v['start0'])-w['ref_start'];e=int(v['end0'])-w['ref_start']
        assert (s,e)==(c['truth_window_start_in_reference_window'],c['truth_window_end_in_reference_window'])
        gs=g['reference']['start'];assert g['reference']['sequence'][w['ref_start']-gs:w['ref_end']-gs]==c['reference_window']
        walks=[p for p in g['walks'] if p['both_anchors']]
        prototypes=[dict(center=trimmed(p,g,w),full_sequence_sha256=hashlib.sha256(p['sequence'].encode()).hexdigest()) for p in walks]
        panel={h['sequence'] for h in inf['hypotheses'] if h['ordinary']}
        assert {p['center'] for p in prototypes}==panel
        projected=project(c,[h['sequence'] for h in inf['hypotheses']])
        projection_count+=len(projected);prototype_count+=len(prototypes);reverse+=c['reverse']
        assert projected[c['stock']]=='alt' and all(projected[p]!='ambiguous' for p in panel)
        removed={p for p in panel if projected[p]=='alt'};kept=panel-removed
        assert sorted(removed)==c['removed_panel_centers'] and sorted(kept)==c['retained_panel_centers']
        assert c['natural_panel_absent']==(not removed)
        assert [{**p,'removed':p['center'] in removed} for p in prototypes]==c['prototypes']
        assert {h['sequence'] for h in inf['hypotheses'] if h['withheld']}==kept
        finite=sum(projected[h['sequence']]=='alt' and h['likelihood'] is not None for h in inf['hypotheses'])
        impossible=sum(projected[h['sequence']]=='alt' and h['likelihood'] is None for h in inf['hypotheses'])
        ambiguous=sum(value=='ambiguous' for value in projected.values())
        assert (finite,impossible,ambiguous)==(c['finite_alt_hypotheses'],c['impossible_alt_hypotheses'],c['ambiguous_hypotheses'])
        if c['flank']['source_status']=='eligible':
            eligible+=1;plan=plans[q];ps=plan['prototypes'];evidence=plan['evidence']
            assert evidence['mapped_sam_sha256']==pin(context['mapped'])['sha256']
            assert {p['center'] for p in ps}==panel
            refs=evidence['reference_intervals'];read_spans=evidence['read_intervals'];sam=context['mapped_sams'][c['parent']]
            assert refs==[dict(start=w['ref_start']-100,end=w['ref_start']-50),dict(start=w['ref_end']+50,end=w['ref_end']+100)]
            assert evidence['window_sha256']==context['window_line_hashes'][q]
            for index,span in enumerate(refs):
                native_flank,span_read=extract(sam['aligned'],sam['cigar'],sam['pos'],span)
                if w['reverse']:span_read=dict(start=len(sam['seq'])-span_read['end'],end=len(sam['seq'])-span_read['start'])
                assert native_flank==evidence['left' if index==0 else 'right'] and span_read==read_spans[index]
                assert all(not overlap(span,dict(start=x['core_start'],end=x['core_end'])) and not overlap(span_read,dict(start=x['read_start']+10,end=x['read_end']-10)) for x in context['windows'].values() if x['read_id']==c['parent'])
            distinct={}
            for walk,p in zip(walks,prototypes):
                l,_=extract(walk['sequence'],walk['cigar'],g['reference']['start'],refs[0]);r,_=extract(walk['sequence'],walk['cigar'],g['reference']['start'],refs[1])
                h=hashlib.sha256(json.dumps(dict(sequence=walk['sequence'],cigar=walk['cigar'],reference_start=g['reference']['start']),sort_keys=True,separators=(',',':')).encode()).hexdigest()
                item=dict(left=l,center=p['center'],right=r,source_walk_sha256=h,source_cigar=walk['cigar']);key=(l,p['center'],r)
                if key not in distinct or h<distinct[key]['source_walk_sha256']:distinct[key]=item
            assert ps==[distinct[k] for k in sorted(distinct)]
            ordinary=compatibility(evidence,ps);withheld=compatibility(evidence,[p for p in ps if p['center'] not in removed])
            near(ordinary,plan['compatibility']);near(ordinary,c['flank']['ordinary']);near(withheld,c['flank']['withheld'])
            near(ordinary['bonuses'],inf['ordinary_flank']);near(withheld['bonuses'],inf['withheld_flank'])
        else:
            assert c['flank']['source_status']=='abstain-binary'
            assert inf['ordinary_flank']=={s:1 for s in panel} and inf['withheld_flank']=={s:1 for s in kept}
        differences=sum(inf['ordinary_flank'].get(h['sequence'],0.0)!=float(h['ordinary']) or inf['withheld_flank'].get(h['sequence'],0.0)!=float(h['withheld']) for h in inf['hypotheses'])
        assert differences==c['flank_binary_hypothesis_bonus_differences']
        detail.append(dict(case_id=cid,hypotheses=len(projected),reverse=c['reverse'],full_walks=len(prototypes),removed_full_walks=sum(p['center'] in removed for p in prototypes),finite_alt=finite,impossible_alt=impossible,ambiguous=ambiguous))
    write('case-projection-and-withholding.json',detail)
    context.update(groups=groups,all_cases=all_cases,all_inference=all_inference,saved=saved,variants=variants,observations=observations,score_census=all_score_rows)
    return dict(cases=len(all_cases),compared_H_likelihood_bits=compared,projected_H=projection_count,complete_walks=prototype_count,eligible_flank_cases=eligible,reverse_cases=reverse,score_census=all_score_rows)

ARMS={'neutral','ordinary_panel','withheld_panel','ordinary_flank','withheld_flank'}
def coverage(cases,decisions):
    keys=[(d['case_id'],d['arm']) for d in decisions]
    assert len(keys)==len(set(keys)) and set(keys)=={(cid,arm) for cid in cases for arm in ARMS}

def decisions_and_reports():
    outputs=[];losses=[]
    for name,work,cm,im,decisions in context['groups']:
        coverage(cm,decisions)
        rejected=0
        for invalid in (decisions[:-1],decisions+[decisions[0]]):
            try:coverage(cm,invalid)
            except AssertionError:rejected+=1
        assert rejected==2
        report=read(work/'report.json');expected_rows=[];counts={};edits=collections.Counter();arm_losses=collections.Counter()
        assert report['schema']=='private-allele-report/1' and report['role']=='development' and report['admissible_candidate'] is False
        for d in decisions:
            c=cm[d['case_id']];inf=im[d['case_id']];hs=inf['hypotheses'];stock=inf['stock'];arm=d['arm']
            if arm=='neutral':bonuses={}
            elif arm.endswith('panel'):bonuses={h['sequence']:float(h['withheld' if arm.startswith('withheld') else 'ordinary']) for h in hs}
            else:bonuses=inf['withheld_flank' if arm.startswith('withheld') else 'ordinary_flank']
            ll={h['sequence']:-math.inf if h['likelihood'] is None else h['likelihood'] for h in hs}
            objectives={s:value+bonuses.get(s,0) for s,value in ll.items()};maximum=max(objectives.values())
            winner=stock if objectives[stock]==maximum else min(s for s,value in objectives.items() if value==maximum)
            margin=objectives[winner]-objectives[stock];delta=ll[winner]-ll[stock]
            gate='native' if winner==stock else 'objective_margin' if margin<.5 else 'neural_deficit' if delta<-.5 else 'edit'
            actual=d['decision']
            assert (winner,bits(margin),bits(delta),gate,gate=='edit')==(actual['winner'],bits(actual['objective_margin']),bits(actual['neural_delta']),actual['gate'],actual['edited'])
            assert bits(actual['winner_likelihood'])==bits(ll[winner])
            if arm.endswith('flank'):assert bits(actual['bonus'])==bits(bonuses.get(winner,0.0))
            else:
                winner_h=next(h for h in hs if h['sequence']==winner)
                assert actual['winner_graph_presence']==winner_h['withheld' if arm.startswith('withheld') else 'ordinary']
                masked=sum(h['sequence']!=stock and h['sequence']!=winner and h['likelihood'] is not None and objectives[h['sequence']]-objectives[stock]>=.5 and ll[h['sequence']]-ll[stock]>=-.5 for h in hs) if gate!='edit' else 0
                assert actual['masked_feasible']==masked and actual['native_exact_ties']==sum(h['sequence']!=stock and objectives[h['sequence']]==objectives[stock] for h in hs)
            assert d['emitted']==(winner if gate=='edit' else stock)
            projected=project(c,[d['emitted'],winner]);retained_alt=projected[d['emitted']]=='alt';winner_alt=projected[winner]=='alt'
            group='/'.join([c['dataset'],'natural_absent' if c['natural_panel_absent'] else 'engineered_withheld',c['stratum'],arm])
            count=counts.setdefault(group,dict(cores=0,edited_cores=0,alt_retained=0,alt_lost=0,edited_alt_lost=0,alt_pregate_winner=0))
            for key,yes in [('cores',True),('edited_cores',gate=='edit'),('alt_retained',retained_alt),('alt_lost',not retained_alt),('edited_alt_lost',not retained_alt and gate=='edit'),('alt_pregate_winner',winner_alt)]:count[key]+=int(yes)
            expected_rows.append(dict(case_id=d['case_id'],variant=c['variant'],parent=c['parent'],stratum=c['stratum'],arm=arm,edited=gate=='edit',gate=gate,native_alt_retained=retained_alt,pregate_winner_alt=winner_alt,objective_margin=margin,neural_delta=delta))
            edits[arm]+=gate=='edit';arm_losses[arm]+=not retained_alt
            if not retained_alt:losses.append(dict(case_id=d['case_id'],arm=arm,variant=c['variant'],parent=c['parent'],stock=stock,emitted=d['emitted'],decision=actual,qualified_continuous_flank=c['flank']['source_status']=='eligible'))
        assert report['rows']==expected_rows and report['groups']==counts
        outputs.append(dict(cohort=name,cases=len(cm),decisions=len(decisions),edits=dict(edits),alt_losses=dict(arm_losses),coverage_negative_rejections=rejected,classes=dict(collections.Counter(c['dataset']+'/'+c['stratum'] for c in cm.values())),natural_absent=dict(collections.Counter(c['dataset'] for c in cm.values() if c['natural_panel_absent']))))
    write('verified-losses.json',losses);write('decision-report-census.json',outputs)
    return dict(cohorts=outputs,loss_rows=losses)

def denominators():
    work=P/'results/private-allele/actual-v3-attachment/output';attachment=read(work/'additional-attachment.json');targets=read(work/'additional-windows.json')['targets']
    frozen=read(P/'results/private-allele/actual-v2-flank/output/additional-windows.json')['targets']
    assert targets==frozen and len(targets)==60
    assert [t['target_id'] for t in attachment['targets']]==list(range(60))
    assert all((r['source_uuid'],r['variant'],r['stratum'])==(t['source_uuid'],t['variant'],t['stratum']) for r,t in zip(attachment['targets'],targets))
    assert len({t['source_uuid'] for t in targets})==18
    development=set(pathlib.Path('/home/jake/Projects/nanopore_basecaller/data/splits/development.txt').read_text().splitlines())
    observed=set((context['dev']/'parents.ids').read_text().splitlines())
    assert len(development)==2608 and len(observed)==64 and {t['source_uuid'] for t in targets}<=observed<=development
    variants=context['variants'];observations=context['observations'];windows=context['windows']
    by_variant=collections.defaultdict(list);by_parent=collections.defaultdict(list)
    for (parent,variant),call in observations.items():
        if call=='alt':by_variant[variant].append(parent)
    for w in windows.values():by_parent[w['read_id']].append(w)
    def event(v):
        r=v['ref'];a=v['alt'];left=0;right=0
        while left<min(len(r),len(a)) and r[left]==a[left]:left+=1
        while right<min(len(r)-left,len(a)-left) and r[len(r)-1-right]==a[len(a)-1-right]:right+=1
        return int(v['pos0'])+left,int(v['pos0'])+len(r)-right
    selected_again=[]
    for kind in ('snv','insertion','deletion'):
        options=[]
        for variant,v in variants.items():
            if v['stratum']!=kind:continue
            s,e=event(v)
            if e-s>21:continue
            for parent in by_variant[variant]:
                intersects=any(w['contig']==v['contig'] and ((w['core_start']<=s<w['core_end']) if s==e else (s<w['core_end'] and w['core_start']<e)) for w in by_parent[parent])
                if not intersects:options.append((variant,parent,s,e))
        for variant,parent,s,e in sorted(options)[:20]:
            center=s+(e-s)//2
            selected_again.append((parent,variant,kind,center-10,center+11))
    assert selected_again==[(t['source_uuid'],t['variant'],t['stratum'],t['proposed_core_start0'],t['proposed_core_end0']) for t in targets]
    attached={r['query_index']:r for r in attachment['targets'] if r['status']=='attached-existing-scores'}
    excluded=[r for r in attachment['targets'] if r['status']=='excluded']
    assert set(attached)==set(range(40)) and len(excluded)==20
    ref=pathlib.Path(context['inputs']['reference']['path'])
    fai={r[0]:tuple(map(int,r[1:])) for r in (line.split('\t') for line in pathlib.Path(str(ref)+'.fai').read_text().splitlines())}
    def reference_slice(contig,start,end):
        length,offset,bases,width=fai[contig];assert 0<=start<end<=length
        values=[]
        with ref.open('rb') as handle:
            cursor=start
            while cursor<end:
                count=min(bases-cursor%bases,end-cursor);handle.seek(offset+cursor//bases*width+cursor%bases)
                values.append(handle.read(count).decode());cursor+=count
        return ''.join(values)
    selected_variants={t['variant'] for t in targets}|{c['variant'] for c in context['all_cases'].values()}
    normalized={};sample=None
    with open(context['source']['truth-normalize']['stdout']) as handle:
        for raw in handle:
            if raw.startswith('#CHROM\t'):
                header=raw.rstrip('\n').split('\t');matches=[i for i,sample_name in enumerate(header) if i>=9 and sample_name=='HG002'];assert len(matches)==1;sample=matches[0]
                continue
            if raw.startswith('#'):continue
            f=raw.rstrip('\n').split('\t');vid=':'.join([f[0],f[1],f[3],f[4]])
            if vid in selected_variants:
                assert sample is not None and vid not in normalized
                gt=dict(zip(f[8].split(':'),f[sample].split(':')))['GT'];normalized[vid]=gt
                alleles=re.split(r'[/|]',gt)
                assert len(alleles)==2 and all(a in ('0','1') for a in alleles) and '1' in alleles
                assert f[0] in {'chr'+str(i) for i in range(1,23)} and f[6]=='PASS' and ',' not in f[4]
                assert 1<=len(f[3])<=50 and 1<=len(f[4])<=50 and f[3]!=f[4] and all(c in 'ACGT' for c in f[3]+f[4])
                kind='snv' if len(f[3])==len(f[4])==1 else 'insertion' if len(f[3])==1 and f[4].startswith(f[3]) else 'deletion' if len(f[4])==1 and f[3].startswith(f[4]) else 'complex'
                assert kind==variants[vid]['stratum'] and kind!='complex'
    assert set(normalized)==selected_variants
    confident=collections.defaultdict(list);bed=pathlib.Path(context['inputs']['confident']['path'])
    opener=gzip.open if bed.name.endswith('.gz') else open
    with opener(bed,'rt') as handle:
        for raw in handle:
            if raw.startswith(('#','track','browser')):continue
            f=raw.rstrip('\n').split('\t');confident[f[0]].append((int(f[1]),int(f[2])))
    for contig,intervals in confident.items():
        merged=[]
        for a,b in sorted(intervals):
            if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],b))
            else:merged.append((a,b))
        confident[contig]=merged
    for vid in selected_variants:
        v=variants[vid];s=int(v['start0']);e=int(v['end0']);pos=int(v['pos0'])
        assert normalized[vid]==v['gt'] and '1' in re.split(r'[/|]',v['gt'])
        rf=reference_slice(v['contig'],s,e)
        assert rf==v['reference_haplotype'] and rf[pos-s:pos-s+len(v['ref'])]==v['ref']
        assert rf[:pos-s]+v['alt']+rf[pos-s+len(v['ref']):]==v['alt_haplotype']
        assert any(a<=s and e<=b for a,b in confident[v['contig']])
    def need(value,reason):
        if not value:raise ValueError(reason)
    admitted=[];attachment_check=[]
    for tid,t in enumerate(targets):
        sam=context['mapped_sams'][t['source_uuid']];row=attachment['targets'][tid]
        try:
            need(t['source_uuid'] in context['reconstructed'],'parent reconstruction: '+str(context['reconstruction_results'][t['source_uuid']]))
            need(not sam['flag']&4 and 30<=sam['mapq']<=254 and sam['contig']==t['contig'],'primary mapping exclusion')
            cs=t['proposed_core_start0'];ce=t['proposed_core_end0'];start=cs-10;end=ce+10;rf=reference_slice(t['contig'],start,end)
            rp=sam['pos'];qp=0;mapping={}
            for n,op in cigar(sam['cigar']):
                if op in '=X':
                    for k in range(max(0,start-rp),min(n,end-rp)):mapping[rp+k]=qp+k
                    rp+=n;qp+=n
                elif op in 'IS':qp+=n
                elif op=='D':rp+=n
                else:raise ValueError('non-EQX target alignment')
            need(qp==len(sam['aligned']),'CIGAR length mismatch')
            need(start in mapping,'left target anchor missing');need(end-1 in mapping,'right target anchor missing')
            a=mapping[start];z=mapping[end-1]+1
            need(z>=a+20 and z<=len(sam['aligned']) and z-a-20<=32 and abs(z-a-20-21)<=5,'core size exclusion')
            need(all(mapping.get(start+k)==a+k and mapping.get(end-10+k)==z-10+k for k in range(10)),'gapped target anchor')
            need(sam['aligned'][a:a+10]==rf[:10] and sam['aligned'][z-10:z]==rf[-10:],'inexact target anchor')
            ra,rz=(len(sam['seq'])-z,len(sam['seq'])-a) if sam['reverse'] else (a,z)
            stock=sam['seq'][ra:rz]
            retained_row=next((r for r in context['reconstructed'][t['source_uuid']] if ra>=r['parent_base_start']+25 and rz+25<=r['parent_base_end']),None)
            need(retained_row is not None,'window lacks 25 retained bases at both chunk edges')
            m=retained_row['m'];ca=retained_row['chunk_base_start']+ra-retained_row['parent_base_start'];cb=ca+len(stock)
            need(ca>=4 and m['SEQ'][ca:cb]==stock,'chunk stock/context mismatch')
            emissions=[i for i,mv in enumerate(m['MOVES']) if mv=='1'];ta=emissions[ca];tb=emissions[cb] if cb<len(emissions) else retained_row['t_end']
            need(retained_row['t_start']<=ta<tb<=retained_row['t_end'] and tb-ta<=256,'time interval invalid or over cap')
            need(not any(old['read_id']==t['source_uuid'] and old['read_start']<rz and ra<old['read_end'] for old in admitted),'overlap with earlier frozen target')
            w=dict(schema='graph-prior-window/1',query_index=len(admitted),read_id=t['source_uuid'],contig=t['contig'],ref_start=start,ref_end=end,core_start=cs,core_end=ce,read_start=ra,read_end=rz,stock=stock,reverse=sam['reverse'],chunk_index=int(m['chunk_index']),chunk_start=ca,chunk_end=cb,t_start=ta,t_end=tb,context=m['SEQ'][ca-4:ca],score_file=m['score_file'])
            assert row['status']=='attached-existing-scores' and context['added'][len(admitted)]==w
            admitted.append(w);attachment_check.append(dict(target_id=tid,status='attached',query_index=w['query_index']))
        except ValueError as error:
            assert row['status']=='excluded' and row['reason']==str(error),(tid,row,str(error))
            attachment_check.append(dict(target_id=tid,status='excluded',reason=str(error)))
    assert len(admitted)==40
    write('attachment-recalculation.json',attachment_check)
    score_path=P/'results/private-allele/additional-original-score-v2/candidates/decisions.jsonl'
    score={r['query_index']:r for r in rows(score_path)}
    assert set(score)==set(attached) and sum(r['status']=='scored' for r in score.values())==31
    build=read(P/'results/private-allele/additional-challenge-v1/challenge-build.json');cases=[c for c in context['all_cases'].values() if c['dataset']=='additional_original'];representation=build['exclusions']
    assert len(cases)==26 and len(representation)==5
    assert {c['query_index'] for c in cases}|{int(e['case_id'].split('/')[1]) for e in representation}=={q for q,r in score.items() if r['status']=='scored'}
    assert not ({c['query_index'] for c in cases}&{int(e['case_id'].split('/')[1]) for e in representation})
    graphs={g['query_index']:g for g in rows(P/'results/private-allele/additional-graph-v1/graph/walks.jsonl')}
    for exclusion in representation:
        q=int(exclusion['case_id'].split('/')[1]);t=attached[q];v=variants[t['variant']];w=context['added'][q];g=graphs[q];gs=g['reference']['start']
        c=dict(reference_window=g['reference']['sequence'][w['ref_start']-gs:w['ref_end']-gs],truth_window_start_in_reference_window=int(v['start0'])-w['ref_start'],truth_window_end_in_reference_window=int(v['end0'])-w['ref_start'],alt_haplotype=v['alt_haplotype'],reverse=w['reverse'])
        if c['truth_window_start_in_reference_window']<0 or c['truth_window_end_in_reference_window']>len(c['reference_window']):reason='truth_window_outside_saved_window'
        else:
            panel=[h['sequence'] for h in score[q]['hypotheses'] if h['graph_presence']]
            projected=project(c,[w['stock']]+panel)
            if projected[w['stock']]!='alt':reason='native_hypothesis_projection_ambiguous_or_other'
            else:
                assert any(projected[p]=='ambiguous' for p in panel)
                reason='panel_representation_ambiguous'
        assert reason==exclusion['reason']
    ledger=[]
    for tid,(target,row) in enumerate(zip(targets,attachment['targets'])):
        assert context['observations'][(target['source_uuid'],target['variant'])]=='alt'
        entry=dict(target_id=tid,parent=target['source_uuid'],variant=target['variant'],stratum=target['stratum'])
        if row['status']=='excluded':entry.update(stage='attachment_excluded',reason=row['reason'])
        else:
            q=row['query_index'];entry['query_index']=q
            if score[q]['status']=='excluded':entry.update(stage='score_excluded',reason=score[q].get('reason'))
            else:
                exclusion=next((e for e in representation if e['case_id']=='additional_original/'+str(q)),None)
                if exclusion:entry.update(stage='projection_excluded',reason=exclusion['reason'])
                else:entry.update(stage='included',case_id='additional_original/'+str(q))
        ledger.append(entry)
    write('all-60-targets.json',ledger)
    return dict(selected=60,observed_source_parents=64,membership_universe=2608,selected_parents=18,classes=dict(collections.Counter(t['stratum'] for t in targets)),stages=dict(collections.Counter(r['stage'] for r in ledger)),attached_classes=dict(collections.Counter(r['stratum'] for r in attachment['targets'] if r['status']!='excluded')),included_classes=dict(collections.Counter(c['stratum'] for c in cases)),exclusions=dict(collections.Counter((r['stage']+'/'+str(r.get('reason'))) for r in ledger if r['stage']!='included')))

def truth_rejection():
    case=context['all_inference']['additional_original/21']
    results=[]
    for level in ('case','hypothesis'):
        bad=json.loads(json.dumps(case))
        if level=='case':bad['genotype']='0/1'
        else:bad['hypotheses'][0]['truth_alt']='C'
        inp=O/('truth-'+level+'.jsonl');out=O/('rejected-'+level+'.jsonl')
        inp.write_text(json.dumps(bad)+'\n')
        command=[context['binary'],'infer',str(inp),str(out)]
        done=subprocess.run(command,capture_output=True,text=True,timeout=5)
        (O/('truth-'+level+'.stderr')).write_text(done.stderr)
        assert done.returncode!=0 and 'unknown field' in done.stderr and out.stat().st_size==0
        results.append(dict(level=level,argv=command,exit=done.returncode,stderr=done.stderr,output_bytes=out.stat().st_size))
    write('truth-rejections.json',results)
    return results

for name,function in [('closure',closure),('receipts',receipts),('tensor_association',tensor_association),('case_audit',case_audit),('decisions_and_reports',decisions_and_reports),('denominators',denominators),('truth_rejection',truth_rejection)]:
    phase(name,function)
    assert utc()<datetime.datetime.fromisoformat(grant['hard_end']), 'hard end exceeded'
    assert sum(p.stat().st_size for p in O.rglob('*') if p.is_file())<=100*1024**2
write('checked-pins.json',checked)
write('reused-hash-evidence.json',dict(source_evidence=reuse_source_evidence,checks=reused_hashes))
write('current-source-drift.json',drift)
result.update(end=utc().isoformat(),hashed_bytes=hashed_bytes,reused_hash_checks=len(reused_hashes),pin_checks=len(checked),current_source_drift=len(drift),complete=not result['errors'])
write('result.json',result)
print(json.dumps(dict(complete=result['complete'],end=result['end'],errors=result['errors'],hashed_bytes=hashed_bytes)),flush=True)
sys.exit(0 if result['complete'] else 1)
