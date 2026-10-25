import importlib.util,json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
r=Path.cwd();s=importlib.util.spec_from_file_location('e',r/'scripts/context-feedback.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w);c=w.c
out=r/'results/context-feedback/support-fetch-v3-controls-1';out.mkdir();pins=[c.pin(r/p) for p in ('tools/support_context/transport_fetch_v3.py','tests/test_support_transport_fetch_v3.py','tools/support_context/transport.py','tools/support_context/source.json','logs/context-feedback/program-runs/fetch-v3-handoff.py')]+[c.pin(__file__)]
now=datetime.now(timezone.utc);g=dict(id=out.name,maximum_wall_seconds=280,expires_utc=(now+timedelta(seconds=280)).isoformat(),maximum_output_bytes=int(os.environ['CONTEXT_UNIT_MAX_OUTPUT']),cpu_quota=2,memory_bytes=4*1024**3,address_space_bytes=8*1024**3,swap_bytes=0,cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-support-fetch-v3-controls-1.service');c.fresh(out/'start.json',dict(sources=pins,grant=g));w.cgroup_limits(g);e=w.Execution(g,out,pins)
stage=e.stage('support-fetch-v3-python-controls',['uv','run','--no-sync','python','-m','unittest','discover','-s','tests','-p','test_support_transport_fetch_v3.py','-v']);text=Path(stage['raw']['stderr']['path']).read_text();c.require('Ran 22 tests' in text and 'skipped' not in text.lower() and text.count(' ... ok\n')==22,'Exactly22 skipped0 required')
e.stage('support-fetch-v3-genuine-handoff',['uv','run','--no-sync','python',r/'logs/context-feedback/program-runs/fetch-v3-handoff.py'])
for item in e.receipts:w.evidence.stage(item,c)
e.budget();c.fresh(out/'complete.json',dict(schema='support-fetch-v3-qualification/1',complete=True,sources=pins,stages=e.receipts,files=[c.pin(out/'start.json'),c.pin(out/'handoff.json')],network_requests=0,biological_qualification=False));print(json.dumps(dict(completion=c.pin(out/'complete.json'))))
