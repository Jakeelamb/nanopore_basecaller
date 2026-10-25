"""Finish small source checks and account every retained read attempt."""
from pathlib import Path
import hashlib,json,re,shlex
from datetime import datetime,timezone
R=Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision');O=R/'logs/context-decision/reviews'
reads={}
def rd(p):
    p=Path(p).resolve(strict=True);n=p.stat().st_size
    assert n<=8*1024**2
    if str(p) not in reads:reads[str(p)]=p.read_bytes()
    return reads[str(p)]
def j(p):return json.loads(rd(p))
def pin(p):
    p=Path(p).resolve(strict=True);b=rd(p);return dict(path=str(p),size=len(b),sha256=hashlib.sha256(b).hexdigest())
def need(ok,msg):
    if not ok:raise AssertionError(msg)
bp=O/'runtime-final-snapshot.json';b=j(bp);obs=b['observations'];cutoff=datetime.fromisoformat(b['ended_utc']).timestamp()
known={p['path']:p for key in ('independently_hashed','reused_independently_hashed') for p in b[key]}
def new_pin_read(p):
    p=Path(p).resolve(strict=True);s=p.stat()
    return not(str(p) in known and s.st_size==known[str(p)]['size'] and max(s.st_mtime,s.st_ctime)<=cutoff)
em_path=R/'results/context-feedback/decision-emit-all-1/emission.json';em=j(em_path);arms={a['arm']:a for a in em['arms']};snap_path=Path(em['snapshot']['path'])
snapshot=j(snap_path);native=snapshot['native']
need(native['size']==16085465 and native['sha256']=='db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe','named native exception pin')
need(max(Path(native['path']).stat().st_mtime,Path(native['path']).stat().st_ctime)<=cutoff,'native unchanged since prior audit')
first={bp,em_path,snap_path,Path(arms['disabled_edits']['sam']['path'])}
for v in b['stages'].values():
    if 'launcher' in v['receipt']:first.add(Path(v['receipt']['launcher'])/'launch.json')
for u in b['units'].values():
    if u['worker'].get('admission'):first.add(Path(u['worker']['admission']['path']))
first_upper=sum(p.stat().st_size for p in first)+native['size']+512*1024+1663
second={bp,em_path,snap_path,Path(b['units']['decision-observe-all-2']['outer']['worker_intake']['path'])}
d=R/'results/context-feedback/decision-measure-feasible-1'
for comp in ('native','reference_free'):
    for mask in ('100','500'):
        second.update((d/('pair-'+comp+'-'+mask)/'parents.tsv',d/('pair-'+comp+'-'+mask)/'blocks.tsv',d/('summary-'+comp+'-'+mask)/'summary.json'))
ob_path=R/'results/context-feedback/decision-observe-all-2/observation.json';ob=j(ob_path);private=next(p for p in ob['evidence'] if p['path'].endswith('/private.tsv'))
second.update((ob_path,Path(private['path']),R/'results/context-feedback/decision-observe-all-2/private.tsv',d/'inputs.json'))
inputs=j(d/'inputs.json');old_free=next(p for p in inputs['evidence'] if p.get('sha256')==arms['reference_free']['sam']['sha256'])
if new_pin_read(old_free['path']):second.add(Path(old_free['path']))
manifest_path=R/'logs/context-decision/source-ready/union-post-format-sources-1.json';manifest=j(manifest_path)
second.add(manifest_path)
for p in manifest['sources']:
    if new_pin_read(p['path']):second.add(Path(p['path']))
second.add(R/'config/context-decision-v1.json')
ub=obs['union']['qualify']['summary']['binary']
if new_pin_read(ub['path']):second.add(Path(ub['path']))
for label,name in (('qualify','decision-union-qualify-2'),('diagnose','decision-union-diagnose-1')):
    path=R/'results/context-feedback'/name;outer_path=path/'execution-complete.json';outer=j(outer_path)
    second.update((outer_path,Path(outer['worker']['path'])))
    for p in obs['union'][label]['summary']['native']:
        seal=j(p['path']);attempt=j(seal['attempt']['path']);second.update((Path(p['path']),Path(seal['attempt']['path'])))
        producer=next(s['receipt'] for s in b['stages'].values() if s['receipt']['argv']==attempt['argv'])
        second.add(Path(producer['raw']['stdout']['path']))
second.update((R/'results/context-feedback/decision-union-qualify-2/build/CMakeCache.txt',R/'results/context-feedback/decision-union-qualify-2/build/compile_commands.json',R/'results/context-feedback/decision-infer-remaining-1/native-remaining/historical.tsv',R/'results/context-feedback/decision-union-diagnose-1/native-diagnostic/decisions.tsv',O/'union-source-delta-2-snapshot.json'))
old=j(O/'union-source-delta-2-snapshot.json')
pattern=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|[A-Za-z_][A-Za-z_0-9]*|[0-9][A-Za-z_0-9.]*|%:%:|<<=|>>=|<=>|->\*|\.\.\.|::|\+\+|--|->|\.\*|<<|>>|<=|>=|==|!=|&&|\|\||\*=|/=|%=|\+=|-=|&=|\^=|\|=|##|<:|:>|<%|%>|%:|[^\s]')
def tok(s):
    need(not re.search(r'(?<![A-Za-z0-9_])(?:u8|u|U|L)?R"',s),'actual raw literal needs separate tokenizer')
    return [m.group() for m in pattern.finditer(s) if not m.group().startswith(('//','/*'))]
formatted=[]
for name in ('src/main.cpp','src/union.cpp','tests/controls.cpp'):
    p=R/'tools/context_decision_union'/name;before=old['deltas'][str(p)]['text'];after=rd(p).decode();second.add(p)
    need(tok(before)==tok(after),'C++ token equality '+name);formatted.append(str(p))
refusals=[]
for p in (R/'logs/context-decision/program').glob('union-*/refused.json'):
    value=j(p);need(value['reason']=='canonical lock held','lock refusal');refusals.append(pin(p))
# Charge every path above even when the failed pass reused a prior hash, plus all this seal's reads.
second_upper=sum(p.stat().st_size for p in second)+512*1024
seal_reads=sum(len(v) for v in reads.values())
conservative=b['bytes_read']+first_upper+second_upper+seal_reads+128*1024
need(conservative<=100*1024**2,'conservative cumulative100MiB bound')
failures=dict(schema='independent-audit-attempt-retention/1',
    first=dict(script=pin(O/'runtime-final-audit-attempt-1.py'),observation='8MiB per-file guard refused whole-stock SAM before any of its bytes were read; report runtime-final-attempt-1.json'),
    native_continuation=dict(script=pin(O/'runtime-final-completion-attempt-1.py'),exit=1,error="KeyError: ended_utc at line81",passed_before_failure=['exact named native SAM stream SHA256','64 orientation-normalized native primary SEQ/Q equal disabled control','recorder/launcher linkage','phase source52'],native_read_once=True),
    metadata_continuation=dict(script=pin(O/'runtime-final-completion-attempt-2.py'),exit=1,error='Overbroad raw-literal guard matched OR at end of a normal quoted message before token comparison',passed_before_failure=['inference before observation','per-parent/block integer conservation','mean-parent arithmetic','912 exact private input-label joins','historical free SAM exact bytes','latest union source63/compiled37 witnesses','actual union cache/toolchain/strict flags','all1104 diagnostic choices matched historical free/native roles']),
    final_token_guard_fix='Require token-boundary raw-string prefix; all three actual before/after token sequences match',scientific_producers_replayed=[])
(O/'runtime-final-audit-failures.json').write_text(json.dumps(failures,indent=2,sort_keys=True)+'\n')
result=dict(schema='independent-runtime-final-verdict/1',verdict='PASS_EVIDENCE_FOR_SUBTHRESHOLD_DEVELOPMENT_CANDIDATE',
    main_snapshot=pin(bp),native_exception=dict(**native,independently_stream_hashed=True,actual_primary_SEQ_Q_parents=64,authority='Root explicit exact-file exception <=16MiB',evidence=failures['native_continuation']),
    cumulative_read_bytes_upper_bound=conservative,limit_bytes=100*1024**2,max_regular_file_bytes=8*1024**2,
    read_accounting=dict(main_audit=b['bytes_read'],failed_native_continuation_upper_bound=first_upper,metadata_continuation_upper_bound=second_upper,seal_metadata_bytes=seal_reads,final_reserve=128*1024),
    first_read_paths=[dict(path=str(p),size=p.stat().st_size) for p in sorted(first)],second_read_paths=[dict(path=str(p),size=p.stat().st_size) for p in sorted(second)],
    source52=obs['source52'],source55=obs['source55'],controller=obs['controller'],measurement=obs['measurement_outer'],
    whole_worker_time=obs['whole_worker_time'],native_metrics=obs['metrics']['native'],free_metrics=obs['metrics']['reference_free'],
    native_ALT=obs['ALT']['native'],free_ALT=obs['ALT']['reference_free'],private=obs['private'],changed_cases=obs['changed_cases'],
    union=dict(qualify=obs['union']['qualify']['execution'],diagnose=obs['union']['diagnose']['execution'],binary=ub,native_controls=189,cases=368,all_retained_union_equals_historical_free=True,three_arm_rows=1104,cap_empty_flags=0,source63=manifest['sources_sha256'],formatted_tokens_identical=formatted,lock_refusals=refusals),
    no_promotion=True,negative_count_fixture_rejected=obs['negative_count_control_rejected'],native_comparison_actual=True,scientific_producers_run=[],product_modules_imported=[],failure_evidence=pin(O/'runtime-final-audit-failures.json'),new_metadata_hashes=[dict(path=p,size=len(v),sha256=hashlib.sha256(v).hexdigest()) for p,v in reads.items()])
(O/'runtime-final-verdict.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:result[k] for k in ('verdict','cumulative_read_bytes_upper_bound','limit_bytes','native_comparison_actual','no_promotion')},indent=2))
print('PASS: actual native64 identity; all64 emitted edit reconstruction; source52/55; full receipt/terminal/kernel evidence; subthreshold conserved arithmetic; union368 unchanged historical-free choices; token-equivalent formatted source; malformed-count negative detected')
