"""Close the duplicate stage-name observation without rerunning any command."""
from pathlib import Path
from datetime import datetime
import hashlib,json,re,shlex
R=Path('/home/jake/Projects/nanopore_basecaller-context-feedback-decision');O=R/'logs/context-decision/reviews'
cache={};charged=0
def rd(p):
    global charged
    p=Path(p).resolve(strict=True)
    if str(p) not in cache:
        n=p.stat().st_size;assert charged+n<=131072 and n<=8*1024**2
        cache[str(p)]=p.read_bytes();charged+=n
    return cache[str(p)]
def j(p):return json.loads(rd(p))
def txt(p):return rd(p).decode()
def pin(p):
    p=Path(p).resolve(strict=True);b=rd(p);return dict(path=str(p),size=len(b),sha256=hashlib.sha256(b).hexdigest())
def ck(p):assert pin(p['path'])==p
v=j(O/'runtime-final-verdict.json');q=R/'results/context-feedback/decision-union-qualify-2'
summary=j(q/'summary.json');target=None
for p in summary['stages']:
    receipt=j(p['path']);ck(p)
    if receipt['name']=='decision-linked-runtime':target=receipt
assert target is not None and target['argv']==['ldd',v['union']['binary']['path']]
assert target['exit']==0 and target['failure'] is None and target['projection_error'] is None
ck(target['terminal']);ck(target['group_cleanup'])
t=j(target['terminal']['path']);assert t['exit']==0 and t['failure'] is None and t['argv']==target['argv']
assert j(target['group_cleanup']['path'])['terminal'] is True
raw=target['raw'];assert set(raw)=={'command.sh','cwd.txt','start.txt','end.txt','exit-status.txt','stdout','stderr','time.txt'} and not target['missing_raw']
for p in raw.values():ck(p)
assert shlex.split(txt(raw['command.sh']['path']))==target['argv'] and txt(raw['cwd.txt']['path']).strip()==str(R)
assert txt(raw['exit-status.txt']['path']).strip()=='0'
a,b=(txt(raw[n]['path']).strip() for n in ('start.txt','end.txt'));assert a.endswith('Z') and b.endswith('Z') and datetime.fromisoformat(a)<=datetime.fromisoformat(b)
times={}
for line in txt(raw['time.txt']['path']).splitlines():
    if line.startswith('\t') and ': ' in line:
        k,data=line.strip().split(': ',1);times[k]=data
assert times['Exit status']=='0' and times['Command being timed']=='"'+' '.join(target['argv'])+'"'
assert float(times['User time (seconds)'])>=0 and float(times['System time (seconds)'])>=0 and int(times['Maximum resident set size (kbytes)'])>0
assert all(float(x)>=0 for x in times['Elapsed (wall clock) time (h:mm:ss or m:ss)'].split(':'))
launch=j(Path(target['launcher'])/'launch.json');assert launch['argv'][1:]==[target['name'],*target['argv']] and Path(launch['argv'][0]).resolve()==R/'scripts/record-command.sh'
recorder=pin(R/'scripts/record-command.sh');assert recorder['sha256']=='f3e0f628d3a32ef0551537ad4acb8585c0690b9203e3f48f765110703e397833'
closure=j(q/'build-closure.json');assert closure['binary']==v['union']['binary']
actual={str(Path(m.group(1)).resolve()) for line in txt(raw['stdout']['path']).splitlines() if (m:=re.search(r'(?:=>\s+)?(/[^\s]+)\s+\(',line))}
assert actual=={p['path'] for p in closure['runtime_libraries']}
result=dict(schema='independent-final-extra-receipt/1',extra_stage='decision-linked-runtime from union qualify',receipt=target,raw_time=times,
    recorder=recorder,closure=closure,ldd_paths_match=True,raw_stderr=txt(raw['stderr']['path']),read_bytes=charged,
    reserve_in_main_ledger=131072,cumulative_read_upper_bound=v['cumulative_read_bytes_upper_bound'],actual_unique_stage_receipts=42,
    observation='Initial stage index keyed by name reused the original linked-runtime name. This independently validates the distinct union binary receipt and launcher. No command repeated.',
    hashed=[pin(p) for p in cache],scientific_producers_run=[])
(O/'runtime-final-extra-receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('PASS distinct union runtime receipt/raw8/launcher/recorder and actual ldd closure; actual stage receipts42; reserved read bytes='+str(charged))
print(json.dumps(dict(native_metrics={k:{x:d[x] for x in ('left','candidate','relative_error_reduction','positive_parents','zero_parents')} for k,d in v['native_metrics'].items()},whole_worker_time=v['whole_worker_time'],union=v['union']),indent=2)[:7500])
