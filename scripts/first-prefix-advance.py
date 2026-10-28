import json
import sys
from pathlib import Path

F1=Path('/home/jake/Projects/nanopore_basecaller-next-prefix-loop')
sys.path.insert(0,str(F1/'tools/prefix_feedback'))
import bounded_cli as io
import joint

io.admitted_worker()
spec_path,expected,output_path=sys.argv[1:]
io.require(io.pin(spec_path)['sha256']==expected,'independent advance spec differs')
spec=io.read(spec_path)
for item in [spec['plan'],spec['binary']]+spec['source_pins']:
    io.check(item)
plan=io.read(spec['plan']['path'])
io.require(plan['truth_opened'] is False and plan['allow_refill'] is False,'frozen development selection differs')
request=dict(schema='prefix-advance/1',source_sha256=spec['source_sha256'],spec=plan['spec'],state=None,update=None,
             block=plan['blocks'][0],expected_previous_state_sha256=None)
stages=joint.Stages(Path(output_path),spec['source_pins'])
producer,_=stages.f1(spec['binary'],'advance',request,Path(output_path)/'advance',('state.json','snapshot.json','complete.json'))
snapshot=io.read(Path(output_path)/'advance/snapshot.json')
io.fresh(Path(output_path)/'complete.json',dict(schema='genuine-prefix-first-advance/1',complete=True,
    plan=spec['plan'],binary=spec['binary'],producer=producer,snapshot=io.pin(Path(output_path)/'advance/snapshot.json'),
    state=io.pin(Path(output_path)/'advance/state.json'),source_sha256=spec['source_sha256'],
    selected_parent=plan['selected']['parent'],genuine_scores=True,whole_chunk_lookahead=True,
    scientific_qualified=False,mapper_updates=0,abstained=snapshot['abstained']))
