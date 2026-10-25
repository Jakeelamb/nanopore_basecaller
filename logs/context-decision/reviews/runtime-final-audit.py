"""Read-only retained-evidence audit. No product imports or scientific producers."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision')
REVIEW = ROOT/'logs/context-decision/reviews'
MAX_FILE = 8*1024**2
MAX_TOTAL = 100*1024**2
previous = json.loads((REVIEW/'runtime-final-attempt-1.json').read_text())
prior_hashes = {p['path']:p for p in previous['independently_hashed']}
prior_cutoff = datetime.fromisoformat(previous['ended_utc']).timestamp()
cache, hashes, size_only, observations = {}, {}, {}, {}
stages, units = previous['stages'], previous['units']
reused_hashes = {}
# Include all previous audited reads and a conservative 1 MiB for audit-code and accounting-file reads.
exploration_bytes = previous['bytes_read'] + 1024**2
bytes_read = exploration_bytes
started = datetime.now(timezone.utc).isoformat()

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def read(path):
    global bytes_read
    path = Path(path).resolve(strict=True)
    if str(path) not in cache:
        size = path.stat().st_size
        require(size <= MAX_FILE, 'per-file read bound '+str(path))
        require(bytes_read+size <= MAX_TOTAL, 'total read bound '+str(path))
        data = path.read_bytes(); require(len(data) == size, 'changed during read '+str(path))
        bytes_read += len(data); cache[str(path)] = data
        hashes[str(path)] = dict(path=str(path), size=size, sha256=hashlib.sha256(data).hexdigest())
    return cache[str(path)]

def obj(path): return json.loads(read(path))
def text(path): return read(path).decode()
def pin(path):
    path=Path(path).resolve(strict=True); key=str(path)
    if key in prior_hashes and path.stat().st_size==prior_hashes[key]['size'] and max(path.stat().st_mtime,path.stat().st_ctime)<=prior_cutoff:
        reused_hashes[key]=prior_hashes[key]
        return prior_hashes[key]
    read(path); return hashes[key]
def check(value, mode='hash'):
    path = Path(value['path']).resolve(strict=True)
    require(path.stat().st_size == value['size'], 'size differs '+str(path))
    if mode == 'size' or value['size'] > MAX_FILE:
        size_only[str(path)] = dict(**value, audit='producer-checked hash; independent current size only')
    else:
        require(pin(path) == value, 'pin differs '+str(path))
    return value

def rows(path):
    reader = csv.DictReader(io.StringIO(text(path)), delimiter='\t')
    require(reader.fieldnames and len(reader.fieldnames)==len(set(reader.fieldnames)), 'TSV header '+str(path))
    result=list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in result), 'TSV shape '+str(path))
    return result

def identity(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def utc(value): return datetime.fromisoformat(value.replace('Z','+00:00'))

def stage(value):
    if set(value)=={'path','size','sha256'}: check(value); value=obj(value['path'])
    key=value.get('name',value.get('path',str(len(stages))))
    if key in stages: return stages[key]['receipt']
    require(value['exit']==0 and value['failure'] is None and value['projection_error'] is None,'stage failure '+key)
    for name in ('terminal','group_cleanup'): check(value[name])
    terminal=obj(value['terminal']['path']); cleanup=obj(value['group_cleanup']['path'])
    require(terminal['exit']==0 and terminal['failure'] is None and terminal['argv']==value['argv'],'stage terminal '+key)
    require(cleanup['terminal'] is True,'stage cleanup '+key)
    raw=value['raw']; expected={'command.sh','cwd.txt','start.txt','end.txt','exit-status.txt','stdout','stderr','time.txt'}
    require(set(raw)==expected and not value['missing_raw'],'raw8 '+key)
    for p in raw.values(): check(p)
    require(shlex.split(text(raw['command.sh']['path']))==value['argv'],'raw argv '+key)
    require(text(raw['cwd.txt']['path']).strip()==str(ROOT),'raw cwd '+key)
    require(text(raw['exit-status.txt']['path']).strip()=='0','raw exit '+key)
    a,b=(text(raw[n]['path']).strip() for n in ('start.txt','end.txt'))
    require(a.endswith('Z') and b.endswith('Z') and utc(a)<=utc(b),'raw clock '+key)
    times={}
    for line in text(raw['time.txt']['path']).splitlines():
        if line.startswith('\t') and ': ' in line:
            k,v=line.strip().split(': ',1); times[k]=v
    require(times['Exit status']=='0' and times['Command being timed']=='"'+' '.join(value['argv'])+'"','GNU time command '+key)
    require(float(times['User time (seconds)'])>=0 and float(times['System time (seconds)'])>=0 and int(times['Maximum resident set size (kbytes)'])>0,'GNU time CPU/RSS '+key)
    require(all(float(x)>=0 for x in times['Elapsed (wall clock) time (h:mm:ss or m:ss)'].split(':')),'GNU time wall '+key)
    stages[key]=dict(receipt=value, time=times, raw_stderr=text(raw['stderr']['path'])[:12000], raw_clock=[a,b])
    return value

def terminal_proof(value):
    require(value.get('exit')==0 and value.get('error') is None,'unit terminal failed')
    proof=value['proof']; proof=proof.get('unloaded_empty_group',proof)
    p=proof.get('properties',{})
    require(p.get('ActiveState') in ('inactive','failed') or p.get('LoadState')=='not-found','terminal active')
    require(p.get('MainPID','0')==p.get('ControlPID','0')=='0','terminal process IDs')
    if p.get('LoadState')!='not-found': require(p.get('Result')=='success','terminal service result')
    return p

def unit(name):
    if name in units: return units[name]
    directory=ROOT/'results/context-feedback'/name
    outer=obj(directory/'execution-complete.json'); worker=obj(outer['worker']['path'])
    check(outer['worker']); check(outer['terminal']); term=obj(outer['terminal']['path']); p=terminal_proof(term)
    for item in outer.get('files',[]): check(item)
    if 'worker_intake' in outer: check(outer['worker_intake']); require(obj(outer['worker_intake']['path'])['verified'],'intake')
    require(outer['complete'] and outer['whole_worker_cgroup_terminal'] and worker['complete'],'unit completion '+name)
    for item in worker['files']: check(item)
    summary=obj(directory/'summary.json')
    for item in summary['stages']: stage(item)
    for item in summary.get('native',[]): check(item)
    units[name]=dict(outer=outer,worker=worker,summary=summary,terminal=term,terminal_properties=p,outer_pin=pin(directory/'execution-complete.json'))
    return units[name]

def native(value):
    check(value); seal=obj(value['path']); attempt=obj(seal['attempt']['path']); result=obj(seal['result']['path'])
    check(seal['attempt']); check(seal['result'])
    for item in seal['files']: check(item)
    for item in seal.get('inputs',[]): check(item,'size')
    require(attempt['source']==seal['source'],'native witness source')
    require(seal['source']['compiled_sources']==frozen,'native source52')
    require(attempt['binary']==binary,'native binary handoff')
    matches=[s['receipt'] for s in stages.values() if s['receipt']['argv']==attempt['argv']]
    require(len(matches)==1,'native raw producer cardinality')
    require(obj(matches[0]['raw']['stdout']['path'])['completion']==value,'native stdout completion')
    return dict(seal=seal,attempt=attempt,result=result)

def sam(path):
    records={}
    for line in text(path).splitlines():
        if line.startswith('@'): continue
        f=line.split('\t'); require(len(f)>=11,'SAM fields')
        if int(f[1])&0x900: continue
        require(f[0] not in records and len(f[9])==len(f[10]),'SAM primary census')
        seq,q=f[9],f[10]
        if int(f[1])&16: seq=seq.translate(str.maketrans('ACGTN','TGCAN'))[::-1]; q=q[::-1]
        records[f[0]]=(seq,q)
    require(len(records)==64,'SAM64')
    return records

def metric_check(summary, parent_rows, block_rows):
    require(len(parent_rows)==64 and len({r['parent'] for r in parent_rows})==64,'metric parent64')
    for side,target in (('left','left_counts'),('right','candidate_counts')):
        totals={k:sum(int(r[side+'_'+k]) for r in parent_rows) for k in 'mxid'}
        blocks={k:sum(int(r[side+'_'+k]) for r in block_rows) for k in 'mxid'}
        require(totals==blocks==summary['metrics'][target],'count conservation '+side)
        require(totals['m']+totals['x']+totals['d']==summary['matched_refexposure'],'reference exposure conservation')
    require(sum(int(r['refexposure']) for r in parent_rows)==sum(int(r['refexposure']) for r in block_rows)==summary['matched_refexposure'],'exposure sum')
    result={}
    for side,key in (('left','left_counts'),('candidate','candidate_counts')):
        counts=summary['metrics'][key]; err=counts['x']+counts['i']+counts['d']; denom=sum(counts.values()); rate=err/denom
        require(math.isclose(rate,summary['metrics'][side+'_error_fraction'],rel_tol=0,abs_tol=1e-15),'rate arithmetic')
        result[side]=dict(errors=err,denominator=denom,rate=rate,counts=counts)
    rel=(result['left']['rate']-result['candidate']['rate'])/result['left']['rate']
    require(math.isclose(rel,summary['metrics']['relative_error_reduction'],rel_tol=0,abs_tol=1e-14),'relative arithmetic')
    for key in ('parent_bootstrap','genomic_1mb_block_bootstrap'):
        require(summary[key]['candidate_minus_left_error_fraction_95_percentile'][1]<0,'delta upper')
    result.update(relative_error_reduction=rel,one_percent=rel>=.01,parents=64,positive_parents=sum(int(r['refexposure'])>0 for r in parent_rows),zero_parents=sum(int(r['refexposure'])==0 for r in parent_rows),uncertainty={k:summary[k] for k in ('parent_bootstrap','genomic_1mb_block_bootstrap')})
    return result

def main():
    global frozen,binary
    frozen=obj(ROOT/'logs/context-decision/source-ready/post-format-sources.json')
    require(len(frozen)==52 and identity(frozen)=='6357128e0c6c5151001866a1f8e1fe1603807747ed38cd39919c29a42017c6ff','frozen52 identity')
    for item in frozen: check(item)
    source55=obj(ROOT/'logs/context-decision/source-ready/measure-controller-sources-2.json')['sources']
    require(identity(source55)=='8e8607ebe49e9c990605777876f8657b0530138cf4a712c8ca42386103c92a1f','source55 identity')
    for item in source55: check(item)
    controller=ROOT/'logs/context-decision/program/run-measure-bounded.py'
    require(pin(controller)['sha256']=='e5d6812d89617f8023b753f26d8f6b1fba193a28a6c9b93fe58acdcf6316be82','controller cut')
    fmt=unit('decision-format-1'); qual=unit('decision-qualify-1'); binary=qual['summary']['binary'];check(binary)
    closure=obj(ROOT/'results/context-feedback/decision-qualify-1/build-closure.json')
    for item in [closure['compiler'],closure['formatter'],closure['cache'],closure['compile_commands'],*closure['runtime_libraries']]: check(item)
    config=obj(ROOT/'config/context-decision-v1.json')
    require(closure['compiler']==config['toolchain']['compiler'] and closure['formatter']==config['toolchain']['formatter'],'qualified tools')
    cache_text=text(closure['cache']['path']); require(config['toolchain']['compiler']['path'] in cache_text,'actual compiler cache')
    required={'-std=c++23','-Wall','-Wextra','-Wpedantic','-Wconversion','-Wsign-conversion','-Wshadow','-Werror','-fno-fast-math','-ffp-contract=off'}
    for row in obj(closure['compile_commands']['path']):
        argv=row.get('arguments') or shlex.split(row['command']); require(required<=set(argv) and '-ffast-math' not in argv,'actual strict compile flags')
    junit=ET.fromstring(read(ROOT/'results/context-feedback/decision-qualify-1/ctest.xml'))
    tests=list(junit.iter('testcase')); require(len(tests)==1 and not any(tests[0].find(n) is not None for n in ('failure','error','skipped')),'CTest zero skips')
    nq=native(qual['summary']['native'][0]);require(nq['result']['controls']==2941 and nq['result']['passed'],'2941 native controls')
    python_stage=next(v for k,v in stages.items() if k=='decision-python-controls')
    require(re.search(r'^Ran 12 tests in ',python_stage['raw_stderr'],re.M) and re.search(r'^OK$',python_stage['raw_stderr'],re.M),'12 Python controls')
    prices=unit('decision-price-all-3'); price_results=[native(p)['result'] for p in prices['summary']['native']]
    require([p['cases'] for p in price_results]==[1,21,346],'price scopes')
    choices={}; infer=[]; histories=[]
    for name,count in (('decision-infer-query0-1',1),('decision-infer-first32-1',21),('decision-infer-remaining-1',346)):
        u=unit(name); n=native(u['summary']['native'][0]);require(n['result']['cases']==count and n['result']['packet_cases']==368 and n['result']['historical_replay'] and not n['result']['truth_available'],'infer scope')
        d=Path(u['summary']['native'][0]['path']).parent
        hist=rows(d/'historical.tsv');require(len(hist)==368*6 and len({(r['case_id'],r['role']) for r in hist})==368*6,'historical6 census');histories.append(pin(d/'historical.tsv')['sha256'])
        table=rows(d/'decisions.tsv');require(len({r['case_id'] for r in table})==count,'selected case count')
        for row in table:
            key=(row['case_id'],row['arm']);require(key not in choices,'disjoint scope');choices[key]=row
            for field in ('proposed','accepted'): require(hashlib.sha256(row[field].encode()).hexdigest()==row[field+'_sha256'],'choice digest')
        infer.append(dict(name=name,cases=count,outer=u['outer_pin'],result=n['result']))
    require(len({k[0] for k in choices})==368 and len(set(histories))==1,'all368 replay identity')
    obs=unit('decision-observe-all-2'); emit=unit('decision-emit-all-1')
    for u in (obs,emit): require(u['summary']['binary']==binary,'late binary custody')
    observation=obj(ROOT/'results/context-feedback/decision-observe-all-2/observation.json')
    effects=rows(ROOT/'results/context-feedback/decision-observe-all-2/effects.tsv')
    require(len(effects)==368*8*2*2,'effect census')
    em=obj(ROOT/'results/context-feedback/decision-emit-all-1/emission.json');check(em['snapshot']); snapshot=obj(em['snapshot']['path'])
    require(em['parents']==64 and em['ordinary_cases']==311 and not em['private_frames_applied'],'emission scope')
    arms={a['arm']:a for a in em['arms']}; require(arms['feasible_escape']['sam']==arms['feasible_partial']['sam'],'SAM aliases')
    check(snapshot['native'],'size')
    # The retained emitted disabled control is the bounded primary-native comparison.
    # The upstream stock SAM is producer-checked and current-size-only, never read above 8 MiB.
    check(arms['disabled_edits']['sam'])
    original=sam(arms['disabled_edits']['sam']['path']); parents=set(original)
    for name in ('disabled_edits','reference_free','feasible_escape'):
        arm=arms[name];check(arm['sam']); actual=sam(arm['sam']['path']);require(set(actual)==parents,'emitted parent IDs')
        for parent in parents:
            seq,q=original[parent]; cursor=0; ss=[];qq=[]
            for edit in sorted((e for e in arm['edits'] if e['parent']==parent),key=lambda e:e['start']):
                a,b=edit['start'],edit['end'];require(cursor<=a<=b<=len(seq) and seq[a:b]==edit['stock'],'edit attachment')
                ss.extend((seq[cursor:a],edit['replacement']));qq.extend((q[cursor:a],'!'*len(edit['replacement'])));cursor=b
            require((''.join(ss)+seq[cursor:],''.join(qq)+q[cursor:])==actual[parent],'actual SEQ/Q reconstruction')
    require([len(arms[n]['edits']) for n in ('raw_veto_escape','reference_free','disabled_edits','feasible_escape')]==[37,9,0,42],'edit census')
    differences=[]
    accepted={(r['case_id'],r['arm'],r['mask']):r for r in effects if r['choice']=='accepted'}
    for case in {r['case_id'] for r in effects if r['domain']=='ordinary'}:
        a=accepted[(case,'feasible_escape','100')]; b=accepted[(case,'raw_veto_escape','100')]
        if a['candidate_sha256']!=b['candidate_sha256']: differences.append(dict(case=case,masks={mask:accepted[(case,'feasible_escape',mask)] for mask in ('100','500')}))
    require({d['case'] for d in differences}=={'ordinary/'+str(i)+'/ordinary' for i in (35,107,127,164,399)},'five changed choices')
    private=rows(ROOT/'results/context-feedback/decision-observe-all-2/private.tsv')
    private_summary={}
    for arm in ('feasible_escape','feasible_partial'):
        selected=[r for r in private if r['arm']==arm and r['choice']=='accepted' and r['domain']=='private-withheld']
        require(len(selected)==26 and len({r['case_id'] for r in selected})==26,'26 withheld cases')
        require(all(r['call']=='alt' and r['exact_alt_support_loss']=='0' and r['alt_consequence_unresolved']=='0' for r in selected),'private ALT retain')
        private_summary[arm]=dict(cases=26,alt=26,alt_loss=0,unresolved=0)
    measure_dir=ROOT/'results/context-feedback/decision-measure-feasible-1'
    outer=obj(measure_dir/'execution-complete.json');require(pin(measure_dir/'execution-complete.json')['sha256']=='f9fd250779bb702274a81362b242004b4ffb8fb55ec88b90515e49dc288bf397','final cut')
    require(outer['complete'] and outer['whole_worker_cgroup_terminal'] and outer['launcher_tree_terminal'],'measurement outer seal')
    for item in [outer['worker'],outer['controller_worker'],outer['terminal'],*outer['files']]: check(item)
    term=obj(outer['terminal']['path']);terminal_proof(term)
    worker=obj(outer['worker']['path']);env=obj(outer['controller_worker']['path']);require(env['controller']==pin(controller),'actual controller custody')
    admission=obj(worker['admission']['path']);check(worker['admission']);require(admission['controller']==pin(controller),'admitted controller')
    require(worker['sources']==source55 and worker['sources_sha256']==identity(source55),'actual measurement source55')
    for item in worker['files']: check(item)
    check(worker['result']);result=obj(worker['result']['path'])
    for item in worker['stages']: stage(item)
    directory=Path(outer['terminal']['path']).parent
    whole=stage(obj(directory/'raw-projection.json')); require(whole['argv'][0]==admission['uv']['path'],'whole worker uv argv')
    require(obj(directory/'launcher-cleanup.json')['terminal'] and obj(directory/'worker-intake.json')['verified'],'measurement terminal/intake')
    require(env['intake']['parent_lock_retained'] and term['canonical_lock_retained'] and term['launcher_terminal'],'canonical custody')
    for k in ('kernel_start','kernel_end'):
        v=env[k];require(v['address_space']==[24*1024**3]*2 and v['files']['cpu.max'].split()==['200000','100000'] and v['files']['memory.max'].strip()==str(16*1024**3) and v['files']['memory.swap.max'].strip()=='0','actual kernel envelope')
    require(env['final_budget']['owned_bytes']<=512*1024**2 and env['final_budget']['disk_free_bytes']>=30*1024**3,'final budget')
    require(utc(term['ended_utc'])<=utc(admission['expires_utc']) and (utc(term['ended_utc'])-utc(term['started_utc'])).total_seconds()<=300,'measurement wall')
    for item in result['runtime']:
        check(item['binary'],'size' if item['binary']['size']>MAX_FILE else 'hash')
        for lib in item['libraries']:check(lib,'size' if lib['size']>MAX_FILE else 'hash')
        stage(item['stage'])
    check(result['emitted']);check(result['mapped']);require(sam(result['mapped']['path'])==sam(result['emitted']['path']),'mapped SEQ/Q custody')
    metrics={}
    for comparator in ('native','reference_free'):
        metrics[comparator]={}
        for mask in ('100','500'):
            summary=obj(result['summaries'][comparator][mask]['summary']['path'])
            parent_rows=rows(measure_dir/('pair-'+comparator+'-'+mask)/'parents.tsv');block_rows=rows(measure_dir/('pair-'+comparator+'-'+mask)/'blocks.tsv')
            metrics[comparator][mask]=metric_check(summary,parent_rows,block_rows)
            require(not metrics[comparator][mask]['one_percent'],'subthreshold')
    alt={}
    for comparator in ('native','reference_free'):
        comparison=obj(result['comparisons'][comparator]['summary']['path']);paired=rows(measure_dir/('comparison-'+comparator)/'paired.tsv')
        counts={}
        for stratum in ('snv','insertion','deletion'):
            subset=[r for r in paired if r['stratum']==stratum]
            totals={k:sum(int(r[k]) for r in subset) for k in ('baseline_alt','alt_retained','alt_loss')}
            require(totals==comparison['strata'][stratum],'ALT integer conservation');counts[stratum]=totals
        alt[comparator]=dict(counts=counts,support=result['comparisons'][comparator]['support'])
    require(sum(x['baseline_alt'] for x in alt['native']['counts'].values())==829 and sum(x['alt_loss'] for x in alt['native']['counts'].values())==0,'native829 ALT')
    require(all(not result['comparisons'][k]['support']['adequate_per_class_changed_support'] for k in ('native','reference_free')),'unsupported productive ALT')
    # Demonstrate the independent arithmetic audit rejects a one-count corruption.
    bad=[dict(r) for r in parent_rows];bad[0]['left_m']=str(int(bad[0]['left_m'])+1)
    caught=False
    try: metric_check(summary,bad,block_rows)
    except AssertionError: caught=True
    require(caught,'negative count fixture not rejected')
    union_qual_dir=ROOT/'results/context-feedback/decision-union-qualify-2'
    union_diag_dir=ROOT/'results/context-feedback/decision-union-diagnose-1'
    union={}
    for label,directory in (('qualify',union_qual_dir),('diagnose',union_diag_dir)):
        u=obj(directory/'execution-complete.json');check(u['worker']);check(u['terminal']);terminal_proof(obj(u['terminal']['path']))
        require(u['complete'] and u['whole_worker_cgroup_terminal'],'union whole unit')
        for item in u['files']:check(item)
        uw=obj(u['worker']['path'])
        for item in uw['files']:check(item)
        us=obj(directory/'summary.json')
        for item in us['stages']:stage(item)
        for item in us['native']:
            check(item); n=obj(item['path']);check(n['attempt']);check(n['result'])
            for p in n['files']:check(p)
            for p in n.get('inputs',[]):check(p,'size')
            ur=obj(n['result']['path'])
        union[label]=dict(execution=pin(directory/'execution-complete.json'),result=ur,summary=us)
    require(union['qualify']['result']['assertions']==189,'union189 native controls')
    uj=ET.fromstring(read(union_qual_dir/'ctest.xml'));ut=list(uj.iter('testcase'))
    require(len(ut)==1 and not any(ut[0].find(k) is not None for k in ('failure','error','skipped')),'union structured CTest')
    ud=union['diagnose']['result'];require(ud['cases']==368 and ud['historical_replay'] and ud['new_neural_calls']==0 and ud['different_from_historical_free']==ud['ordinary_different_from_historical_free']==0,'union identical historical free')
    census=rows(union_diag_dir/'native-diagnostic/union-census.tsv')
    require(len(census)==368 and all(r['retained_pool_only']=='1' and r['different_from_historical_free']=='0' and r['cap_or_empty_flags']=='0' for r in census),'union census')
    observations.update(verdict='PASS_EVIDENCE_FOR_SUBTHRESHOLD_DEVELOPMENT_CANDIDATE',source52=identity(frozen),source55=identity(source55),controller=pin(controller),binary=binary,qualification=dict(native_controls=2941,python_controls=12,ctest=1,skipped=0),price=price_results,inference=infer,historical_replay_cases=368,emission=dict(parents=64,ordinary_cases=311,edits={k:len(a['edits']) for k,a in arms.items()},feasible_sam=arms['feasible_escape']['sam'],unchanged_seq_q_reconstructed=True,independent_native_base='emitted disabled_edits SAM; upstream whole-stock binding producer-checked size-only'),changed_cases=differences,private=private_summary,measurement_outer=pin(measure_dir/'execution-complete.json'),measurement_terminal=term,measurement_envelope=env,whole_worker_time=stages[whole['name']]['time'],metrics=metrics,ALT=alt,union=union,no_promotion=True,negative_count_control_rejected=caught)
    print(json.dumps(dict(verdict=observations['verdict'],bytes_read=bytes_read,files=len(cache),stages=len(stages),metrics={k:{m:v['relative_error_reduction'] for m,v in vv.items()} for k,vv in metrics.items()},private=private_summary),indent=2))

def save(error=None):
    report=dict(schema='independent-retained-runtime-audit/1',started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),cwd=str(ROOT),observations=observations,error=error,bytes_read=bytes_read,exploration_bytes=exploration_bytes,max_file_read=max(previous['max_file_read'],max((len(v) for v in cache.values()),default=0)),read_limit=MAX_TOTAL,file_limit=MAX_FILE,independently_hashed=list(hashes.values()),reused_independently_hashed=list(reused_hashes.values()),prior_audit=pin(REVIEW/'runtime-final-attempt-1.json'),reuse_guard='same size and mtime/ctime no later than previous read interval end',producer_hash_size_only=list(size_only.values()),stages=stages,units=units,scientific_producers_run=[],product_modules_imported=[])
    (REVIEW/'runtime-final-snapshot.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')

try:
    main();save()
except BaseException as exc:
    save(repr(exc));raise
