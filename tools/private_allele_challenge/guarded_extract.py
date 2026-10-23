from datetime import datetime,timezone
import fcntl,json,os,resource,shutil,signal,subprocess,sys,threading,time
from pathlib import Path
from monitor_guard import fail_closed,guarded_monitor
ROOT=Path('/home/jake/Projects/nanopore_basecaller-private')
REF=Path('/home/jake/Projects/nanopore_basecaller-reference')
sys.path.insert(0,str(ROOT/'scripts'))
import benchmark as b
UNIT=ROOT/'results/private-allele/additional-graph-v1'
WORK=ROOT/'results/private-allele/actual-v3-attachment/output'
BIN=REF/'software/graph-prior/graph-resource/gbz-base-source/target/release/hprc-interval-extract'
GBZ=REF/'software/graph-prior/graph-resource/hprc-v2.1-mc-grch38-eval.gbz'
assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-23T17:10:00+00:00'),'admission start deadline'
lock=Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock').open('a')
started=time.monotonic()
while True:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
 except BlockingIOError:
  if time.monotonic()-started>=30:raise
  time.sleep(0.1)
assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-23T17:10:00+00:00'),'native launch deadline'
UNIT.mkdir()
resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
context=dict(experiment='private-allele-additional-frozen60-v1',sources=[b.pin(Path(__file__)),b.pin(Path(__file__).with_name('monitor_guard.py')),b.pin(Path(__file__).with_name('check_monitor.py'))],executables=[b.pin(BIN)],qualified_assets=[b.pin(GBZ),b.pin(WORK/'additional-queries.tsv'),b.pin(WORK/'additional-attached-windows.jsonl'),b.pin(WORK/'additional-windows.json')])
qualification=b.read(REF/'provenance/verification/graph-resource.json')
assert context['qualified_assets'][0]['sha256']==qualification['graph']['sha256']
def find_binary(value):
 if isinstance(value,dict):
  if str(value.get('path','')).endswith('/hprc-interval-extract') and 'sha256' in value:return value['sha256']
  for child in value.values():
   found=find_binary(child)
   if found:return found
 if isinstance(value,list):
  for child in value:
   found=find_binary(child)
   if found:return found
assert context['executables'][0]['sha256']==find_binary(qualification)
b.write(UNIT/'admission.json',dict(context=context,budget=dict(as_bytes=48*1024**3,rss_bytes=16*1024**3,wall_seconds=180,latest_launch='2026-10-23T17:10:00Z',hard_end='2026-10-23T17:13:00Z',minimum_free_bytes=30*1024**3),target_selection=60,attached_queries=40))
done=threading.Event();failures=[];PAGE=os.sysconf('SC_PAGE_SIZE')
def owned_processes():
 table={}
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   fields=(proc/'stat').read_text().rsplit(') ',1)[1].split()
   table[int(proc.name)]=dict(pid=int(proc.name),ppid=int(fields[1]),rss=int(fields[21])*PAGE,address_space=int(fields[20]))
  except (OSError,ValueError,IndexError):continue
 owned={os.getpid()}
 while True:
  expanded=owned|{pid for pid,row in table.items() if row['ppid'] in owned}
  if expanded==owned:break
  owned=expanded
 return [table[pid] for pid in owned if pid in table]
def reject(event):
 fail_closed(failures,event,lambda row:b.write(UNIT/'monitor-failure.json',row),lambda:os.kill(os.getpid(),signal.SIGTERM))
def sample():
 rows=owned_processes();rss=sum(p['rss'] for p in rows);owned=sum(p.stat().st_size for p in UNIT.rglob('*') if p.is_file());free=shutil.disk_usage(ROOT).free
 row=dict(utc=b.utc(),elapsed=time.monotonic()-started,rss_bytes=rss,owned_bytes=owned,free_bytes=free,processes=rows)
 with (UNIT/'resources.jsonl').open('a') as handle:handle.write(json.dumps(row)+'\n')
 if rss>16*1024**3 or owned>1024**3 or free<30*1024**3 or time.monotonic()-started>175 or datetime.now(timezone.utc)>=datetime.fromisoformat('2026-10-23T17:12:55+00:00'):reject(dict(reason='resource_or_deadline',**row))
def terminate(_signum,_frame):raise RuntimeError('live extraction guard rejected execution')
signal.signal(signal.SIGTERM,terminate)
thread=threading.Thread(target=guarded_monitor,args=(done,sample,reject),daemon=True);thread.start()
try:
 assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-23T17:10:00+00:00'),'native launch deadline'
 result=b.stage(UNIT/'stages','graph',[str(BIN),str(GBZ),str(WORK/'additional-queries.tsv'),str(UNIT/'graph')],context,reserve=30*1024**3)
 assert not failures,failures
 receipt=next((UNIT/'stages/graph').glob('*/finish.json'))
 b.write(UNIT/'complete.json',dict(complete=True,producer=b.pin(receipt),graph_files=[b.pin(p) for p in sorted((UNIT/'graph').rglob('*')) if p.is_file()],qualified_assets=context['qualified_assets'],sources=context['sources'],binary=context['executables'][0]))
 print(json.dumps(dict(complete=True,output=str(UNIT),exit=result['exit'])))
finally:done.set();thread.join(timeout=2)
