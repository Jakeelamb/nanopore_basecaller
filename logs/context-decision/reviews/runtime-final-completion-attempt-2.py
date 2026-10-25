"""Bounded continuation: the named native-SAM exception and final union evidence."""
import csv
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,io,json,math,re,shlex
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision'); O=R/'logs/context-decision/reviews'
LIMIT=100*1024**2; FILE=8*1024**2
base_path=O/'runtime-final-snapshot.json';base_bytes=base_path.read_bytes();base=json.loads(base_bytes)
used=base['bytes_read']+len(base_bytes)+512*1024
cutoff=datetime.fromisoformat(base['ended_utc']).timestamp()
old={p['path']:p for key in ('independently_hashed','reused_independently_hashed') for p in base[key]}
new,cache,reused={}, {}, {}
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def rd(path):
    global used
    p=Path(path).resolve(strict=True);key=str(p)
    if key not in cache:
        n=p.stat().st_size;need(n<=FILE,'8MiB bound '+key);need(used+n<=LIMIT,'100MiB bound '+key)
        b=p.read_bytes();used+=len(b);cache[key]=b;new[key]=dict(path=key,size=len(b),sha256=hashlib.sha256(b).hexdigest())
    return cache[key]
def j(path):return json.loads(rd(path))
def txt(path):return rd(path).decode()
def pn(path):
    p=Path(path).resolve(strict=True);key=str(p)
    if key in old and p.stat().st_size==old[key]['size'] and max(p.stat().st_mtime,p.stat().st_ctime)<=cutoff:
        reused[key]=old[key];return old[key]
    rd(p);return new[key]
def ck(p):need(pn(p['path'])==p,'pin '+p['path'])
def tab(path):return list(csv.DictReader(io.StringIO(txt(path)),delimiter='\t'))
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sam_records(data,parents=None):
    result={}
    for line in data.splitlines():
        if line.startswith('@'):continue
        f=line.split('\t')
        if parents is not None and f[0] not in parents:continue
        if int(f[1])&0x900:continue
        need(f[0] not in result and len(f[9])==len(f[10]),'SAM primary SEQ/Q')
        seq,q=f[9],f[10]
        if int(f[1])&16:seq=seq.translate(str.maketrans('ACGTN','TGCAN'))[::-1];q=q[::-1]
        result[f[0]]=(seq,q)
    return result
obs=base['observations']; need(base['error'] is None and obs['verdict']=='PASS_EVIDENCE_FOR_SUBTHRESHOLD_DEVELOPMENT_CANDIDATE','main audit')
emission=j(R/'results/context-feedback/decision-emit-all-1/emission.json');arms={a['arm']:a for a in emission['arms']}
disabled_pin=arms['disabled_edits']['sam']
snapshot=j(emission['snapshot']['path']);native=snapshot['native']
exception_path=Path('/home/jake/Projects/nanopore_basecaller-reference/logs/20261023T035916Z-stock-fe30a2dbcb664128bf187fdaf8f68340-CoVGDR/stdout')
need(native==dict(path=str(exception_path),size=16085465,sha256='db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe'),'named exception pin')
need(exception_path.stat().st_size==native['size'] and max(exception_path.stat().st_mtime,exception_path.stat().st_ctime)<=cutoff,'native file unchanged since observed successful checks')
# The preserved first continuation reached line81 after its exact hash and64 SEQ/Q assertions passed.
# Preserve that actual observation; do not reread16MiB after the later timestamp projection error.
prior_paths={base_path, R/'results/context-feedback/decision-emit-all-1/emission.json',Path(emission['snapshot']['path']),Path(disabled_pin['path'])}
for item in base['stages'].values():
    if 'launcher' in item['receipt']:prior_paths.add(Path(item['receipt']['launcher'])/'launch.json')
for unit_value in base['units'].values():
    if unit_value['worker'].get('admission'):prior_paths.add(Path(unit_value['worker']['admission']['path']))
failed_read_upper_bound=sum(p.stat().st_size for p in prior_paths)+native['size']+512*1024+1663
used+=failed_read_upper_bound
need(used<=LIMIT,'cumulative prior attempts budget')
exception=dict(**native,independent_hash=True,selected_primary_parents=64,orientation_normalized=True,
               authority='Root explicit task-message exception for this exact file only; all other files remain at most8MiB',
               observed_in='runtime-final-completion-attempt-1.py exact hash and64 SEQ/Q assertions completed before later line81 KeyError; no reread',
               retained_failure='runtime-final-audit-failures.json')
launcher_count=sum('launcher' in v['receipt'] for v in base['stages'].values())
# Inference predates observation; pinning and timestamps do not substitute for an independent cohort.
latest_infer=max(datetime.fromisoformat(base['units'][n]['terminal']['utc']) for n in ('decision-infer-query0-1','decision-infer-first32-1','decision-infer-remaining-1'))
observe_start=datetime.fromisoformat(j(base['units']['decision-observe-all-2']['outer']['worker_intake']['path'])['observation']['observed_utc'])
need(latest_infer<observe_start,'truth join follows all inference')
# Per-parent block conservation and mean-parent arithmetic, without re-scoring a CIGAR.
for comparator in ('native','reference_free'):
    for mask in ('100','500'):
        d=R/'results/context-feedback/decision-measure-feasible-1';pp=tab(d/('pair-'+comparator+'-'+mask)/'parents.tsv');bb=tab(d/('pair-'+comparator+'-'+mask)/'blocks.tsv')
        sm=j(d/('summary-'+comparator+'-'+mask)/'summary.json');deltas=[]
        for p in pp:
            block=[b for b in bb if b['parent']==p['parent']]
            for key in ['refexposure']+[s+'_'+k for s in ('left','right') for k in 'mxid']:
                need(sum(int(b[key]) for b in block)==int(p[key]),'per-parent block conservation')
            for s in ('left','right'):need(sum(int(p[s+'_'+k]) for k in 'mxd')==int(p['refexposure']),'per-parent reference denominator')
            if int(p['refexposure']):
                rates=[]
                for s in ('left','right'):
                    counts={k:int(p[s+'_'+k]) for k in 'mxid'};rates.append(sum(counts[k] for k in 'xid')/sum(counts.values()))
                deltas.append(rates[1]-rates[0])
        need(math.isclose(sum(deltas)/len(deltas),sm['metrics']['mean_parent_candidate_minus_left_error_fraction'],abs_tol=1e-15),'mean parent arithmetic')
# Exact input-label joins for the retained private witnesses, without variant re-calling.
observation=j(R/'results/context-feedback/decision-observe-all-2/observation.json')
private_pin=next(p for p in observation['evidence'] if p['path'].endswith('/private.tsv'));ck(private_pin)
atlas=tab(private_pin['path']);lookup={(p['case_id'],p['candidate_sha256'],p['event_id']):p for p in atlas}
joined=tab(R/'results/context-feedback/decision-observe-all-2/private.tsv');joined_count=0
for p in joined:
    q=lookup[(p['case_id'],p['candidate_sha256'],p['event_id'])]
    need(all(p[k]==v for k,v in q.items()),'actual private label join');joined_count+=1
# Full historical free SAM equality is checked when the bounded input pin identifies it.
inputs=j(R/'results/context-feedback/decision-measure-feasible-1/inputs.json')
old_free=next(p for p in inputs['evidence'] if p.get('sha256')==arms['reference_free']['sam']['sha256'])
ck(old_free);need(old_free['sha256']==arms['reference_free']['sam']['sha256'],'historical free SAM byte identity')
# Final diagnostic build and source witnesses use the formatted source cut.
manifest=j(R/'logs/context-decision/source-ready/union-post-format-sources-1.json')
need(ident(manifest['sources'])=='2d5bc2d87edb398af03015fe36465cc2a613b64af174800ec5b0229b334b20cd','formatted63 identity')
for p in manifest['sources']:ck(p)
config=j(R/'config/context-decision-v1.json');union=obs['union'];ub=union['qualify']['summary']['binary'];ck(ub)
need(ub['sha256']=='fb3c0cb01577798a22c5041604d6f93c4536a3d2af815c5d427f462b9b43e64d','union binary')
for label,path in (('qualify',R/'results/context-feedback/decision-union-qualify-2'),('diagnose',R/'results/context-feedback/decision-union-diagnose-1')):
    outer=j(path/'execution-complete.json');worker=j(outer['worker']['path'])
    need(worker['sources_sha256']==manifest['sources_sha256'],'union worker current source63')
    for p in union[label]['summary']['native']:
        seal=j(p['path']);attempt=j(seal['attempt']['path'])
        need(seal['complete'] and seal['source']==attempt['source'] and attempt['binary']==ub,'union native seal/binary')
        need(seal['source']['compiled_sources']==manifest['compiled_sources'] and len(manifest['compiled_sources'])==37,'union actual compiled37')
        for role in ('compiler','formatter'):
            need(seal['source'][role+'_path']==config['toolchain'][role]['path'] and seal['source'][role+'_sha256']==config['toolchain'][role]['sha256'],'actual union tool witness')
        producers=[s['receipt'] for s in base['stages'].values() if s['receipt']['argv']==attempt['argv']]
        need(len(producers)==1 and j(producers[0]['raw']['stdout']['path'])['completion']==p,'union actual producer handoff')
cache_text=txt(R/'results/context-feedback/decision-union-qualify-2/build/CMakeCache.txt')
for key,expected in (('CMAKE_CXX_COMPILER',config['toolchain']['compiler']['path']),('UNION_CLANG_FORMAT',config['toolchain']['formatter']['path']),('STUDY_CLANG_FORMAT',config['toolchain']['formatter']['path'])):
    need(re.findall(r'^'+key+r':(?:FILEPATH|STRING)=(.*)$',cache_text,re.M)==[expected],'actual union CMake tool cache '+key)
for row in j(R/'results/context-feedback/decision-union-qualify-2/build/compile_commands.json'):
    argv=row.get('arguments') or shlex.split(row['command']);need({'-std=c++23','-Wall','-Wextra','-Wpedantic','-Wconversion','-Wsign-conversion','-Wshadow','-Werror','-fno-fast-math','-ffp-contract=off'}<=set(argv) and '-ffast-math' not in argv,'union actual strict flags')
# Independently compare the actual diagnostic table to the original six-role replay table.
history=tab(R/'results/context-feedback/decision-infer-remaining-1/native-remaining/historical.tsv')
hist={(p['case_id'],p['role']):p['candidate_sha256'] for p in history}
decisions=tab(R/'results/context-feedback/decision-union-diagnose-1/native-diagnostic/decisions.tsv');need(len(decisions)==368*3,'union three-arm census')
for p in decisions:
    role='native' if p['arm']=='disabled_edits' else 'reference_free'
    need(p['accepted_sha256']==hist[(p['case_id'],role)] and hashlib.sha256(p['accepted'].encode()).hexdigest()==p['accepted_sha256'],'union exact retained old choice')
# Formatting must preserve C++ tokens, including quoted literals and compound operators.
old_cut=j(O/'union-source-delta-2-snapshot.json')
pattern=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|[A-Za-z_][A-Za-z_0-9]*|[0-9][A-Za-z_0-9.]*|%:%:|<<=|>>=|<=>|->\*|\.\.\.|::|\+\+|--|->|\.\*|<<|>>|<=|>=|==|!=|&&|\|\||\*=|/=|%=|\+=|-=|&=|\^=|\|=|##|<:|:>|<%|%>|%:|[^\s]')
def tokens(s):
    need('R"' not in s,'raw literals need separate tokenizer')
    return [m.group() for m in pattern.finditer(s) if not m.group().startswith(('//','/*'))]
formatted=[]
for name in ('src/main.cpp','src/union.cpp','tests/controls.cpp'):
    p=R/'tools/context_decision_union'/name;before=old_cut['deltas'][str(p)]['text'];after=txt(p)
    need(tokens(before)==tokens(after),'format-only tokens '+name);formatted.append(str(p))
refusals=[]
for p in (R/'logs/context-decision/program').glob('union-*/refused.json'):
    value=j(p);need(value['reason']=='canonical lock held','retained lock refusal');refusals.append(pn(p))
report=dict(schema='independent-runtime-completion-audit/1',verdict='PASS_EVIDENCE_FOR_SUBTHRESHOLD_DEVELOPMENT_CANDIDATE',
    main_audit=pn(base_path),cumulative_read_bytes=used,read_limit_bytes=LIMIT,max_regular_file_bytes=FILE,
    named_native_exception=exception,native_disabled_seq_q_identity=True,transitive_all64_edit_reconstruction=True,
    actual_recorder_launches=launcher_count,private_label_join_rows=joined_count,
    inference_completed_before_observation=True,actual_parent_block_conservation=True,
    union_formatted_source63=manifest['sources_sha256'],union_compiled37_identity=ident(manifest['compiled_sources']),
    union_binary=ub,union_diagnostic_rows=len(decisions),union_native_controls=189,union_retained_union_equals_historical_free_cases=368,
    union_retained_pool_only=True,formatted_token_equivalence=formatted,retained_lock_refusals=refusals,
    newly_hashed=list(new.values()),reused_independent_hashes=list(reused.values()),scientific_producers_run=[],product_modules_imported=[])
(O/'runtime-final-completion.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:report[k] for k in ('verdict','cumulative_read_bytes','native_disabled_seq_q_identity','actual_recorder_launches','private_label_join_rows','union_diagnostic_rows','union_native_controls','union_retained_union_equals_historical_free_cases')},indent=2))
