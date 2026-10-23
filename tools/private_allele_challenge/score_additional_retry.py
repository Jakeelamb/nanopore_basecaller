from datetime import datetime,timezone
import fcntl,json,resource,sys
from pathlib import Path
ROOT=Path('/home/jake/Projects/nanopore_basecaller-private')
REF=Path('/home/jake/Projects/nanopore_basecaller-reference')
sys.path.insert(0,str(ROOT/'scripts'))
import benchmark as b
WORK=ROOT/'results/private-allele/actual-v3-attachment/output'
GRAPH=ROOT/'results/private-allele/additional-graph-v1'
UNIT=ROOT/'results/private-allele/additional-original-score-v2'
PILOT=REF/'results/graph-prior/pilot-v1/development'
BIN=REF/'tools/graph_prior/target/release/graph-prior'
assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-23T17:14:00+00:00'),'scoring latest start admission'
lock=Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock').open('a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
cgroup=Path('/sys/fs/cgroup')/next(line.split(':',2)[2].strip().lstrip('/') for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0:'))
assert (cgroup/'memory.max').read_text().strip()=='4294967296' and (cgroup/'memory.swap.max').read_text().strip()=='0','kernel memory bound mismatch'
print(json.dumps(dict(cgroup=str(cgroup),memory_max=(cgroup/'memory.max').read_text().strip(),swap_max=(cgroup/'memory.swap.max').read_text().strip())),flush=True)
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
complete=b.read(GRAPH/'complete.json');assert complete['complete'] is True
b.check_pins(complete['graph_files'])
producer=b.read(complete['producer']['path']);assert producer['exit']==0 and producer['status']=='finished'
old_receipt=next((PILOT/'stages/local-decode').glob('*/finish.json'))
old=b.read(old_receipt)
assert old['exit']==0 and old['status']=='finished'
expected=next(p for p in old['context']['executables'] if p['path']==str(BIN))
b.check_pins([expected])
inputs=b.read(REF/'results/reference-assisted/inputs-native-frozen-v1.json')
old_argv=old['argv'];mapped=old_argv[old_argv.index('--sam')+1]
argv=[str(BIN),'decode','--reference',inputs['reference']['path'],'--sam',mapped,'--export',str(PILOT/'native-export'),'--parents',str(PILOT/'parents.ids'),'--windows',str(WORK/'additional-attached-windows.jsonl'),'--graph',str(GRAPH/'graph/walks.jsonl'),'--output',str(UNIT/'candidates')]
context=dict(experiment='private-allele-additional60-original-H-v1',sources=[b.pin(Path(__file__)),b.pin(ROOT/'scripts/benchmark.py')],executables=[expected],qualified_assets=[b.pin(old_receipt),b.pin(GRAPH/'complete.json'),b.pin(WORK/'additional-attached-windows.jsonl'),b.pin(WORK/'additional-windows.json'),b.pin(WORK/'additional-attachment.json'),b.pin(PILOT/'parents.ids'),inputs['reference'],b.pin(mapped),b.pin(ROOT/'results/private-allele/actual-v3-attachment/complete.json')])
UNIT.mkdir()
b.write(UNIT/'admission.json',dict(role='development',admissible_candidate=False,registered_selection_targets=60,attached_queries=40,maximum_wall_seconds=120,maximum_address_space_bytes=8*1024**3,maximum_cgroup_memory_bytes=4*1024**3,hard_end='2026-10-23T17:15:00Z',context=context))
result=b.stage(UNIT/'stages','score',argv,context,reserve=30*1024**3)
assert result['exit']==0 and datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-23T17:15:00+00:00')
receipt=next((UNIT/'stages/score').glob('*/finish.json'))
files=[b.pin(p) for p in sorted((UNIT/'candidates').rglob('*')) if p.is_file()]
b.write(UNIT/'complete.json',dict(schema='private-allele-additional-score/1',role='development',complete=True,admissible_candidate=False,original_selected_targets=60,attached_queries=40,producer=b.pin(receipt),files=files,context=context,scope='New truth-enriched diagnostic windows, unchanged genuine saved DGS1 score intervals. No model or tensor replay.'))
print(json.dumps(dict(complete=True,output=str(UNIT),files=files)))
