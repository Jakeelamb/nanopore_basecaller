from datetime import datetime,timezone
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('subset_worker',ROOT/'tools/context_decoder/observe_subset.py')
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
w,c=s.w,s.c
parser=argparse.ArgumentParser(description='Bound one checkpoint observation and retain the host lock until its worker tree is terminal.')
parser.add_argument('--manifest',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--admission',type=Path,required=True)
args=parser.parse_args()
grant=c.read(args.admission)
now=datetime.now(timezone.utc)
end=s.validate_grant(args,grant,now)
remaining=min(grant['maximum_wall_seconds'],(end-now).total_seconds())-3
c.require(remaining>1,'No bounded subset interval remains')
directory=w.LOGS/('supervisor-'+grant['id'])
directory.mkdir()
unit='context-feedback-'+grant['id']+'.service'
description='Context subset observation '+uuid.uuid4().hex
w.pg.adopt_orphans()
with w.LOCK.open('r') as lock:
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        c.fresh(directory/'refused.json',dict(reason='canonical lock held',grant=grant,utc=now.isoformat()))
        raise
    intake=directory/'intake.json'
    c.fresh(intake,dict(grant_id=grant['id'],admission=str(args.admission.resolve()),parent_pid=os.getpid(),
            parent_start=w.supervisor.process_start(os.getpid()),lock_fd=lock.fileno(),unit=unit,description=description,
            canonical_lock=str(w.LOCK),controller=c.pin(__file__)))
    command=['systemd-run','--user','--wait','--pipe','--unit='+unit,'--description='+description,
        '--working-directory='+str(ROOT),'--property=Type=exec','--property=ExitType=cgroup','--property=KillMode=control-group',
        '--property=Slice=app.slice','--property=CollectMode=inactive','--property=SendSIGKILL=yes',
        '--property=FinalKillSignal=SIGKILL','--property=TimeoutStopSec=1s','--property=RuntimeMaxSec='+str(remaining)+'s',
        '--property=CPUQuota='+str(grant['cpu_quota']*100)+'%','--property=MemoryMax='+str(grant['memory_bytes']),
        '--property=MemorySwapMax=0','--property=LimitAS='+str(grant['address_space_bytes']),
        '--setenv=UV_PROJECT_ENVIRONMENT='+os.environ['UV_PROJECT_ENVIRONMENT'],'--',shutil.which('uv'),
        'run','--no-sync','python',str(ROOT/'tools/context_decoder/observe_subset.py'),
        '--manifest',str(args.manifest.resolve()),'--output',str(args.output.resolve()),
        '--admission',str(args.admission.resolve()),'--worker-intake',str(intake)]
    c.fresh(directory/'command.json',dict(argv=command,grant=grant,cwd=str(ROOT),utc=now.isoformat(),controller=c.pin(__file__)))
    process,error,proof=None,None,None
    try:
        with (directory/'stdout').open('xb') as out,(directory/'stderr').open('xb') as err:
            process=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
            while process.poll() is None:
                if time.time()>=end.timestamp()-1 or w.owned_bytes()>grant['maximum_output_bytes'] or shutil.disk_usage(ROOT).free<30*1024**3:
                    raise ValueError('Subset wall/output/disk boundary reached')
                time.sleep(.2)
    except BaseException as caught:
        error=repr(caught)
    finally:
        index=0
        while proof is None:
            try:
                observed=w.supervisor.show(unit)
                if observed['properties'].get('Description')==description:
                    if w.supervisor.terminal(observed,grant['cgroup']):
                        proof=observed
                        if observed['properties'].get('Result')!='success':
                            error=error or 'Subset service failed'
                    else:
                        subprocess.run(['systemctl','--user','stop','--no-block',unit],capture_output=True,timeout=3)
                elif process is None or (process.poll() is not None and w.supervisor.unloaded_terminal(observed,grant['cgroup'])):
                    proof=dict(unloaded_empty_group=observed)
            except BaseException as caught:
                index+=1
                c.fresh(directory/('termination-observation-error-'+str(index)+'.json'),dict(error=repr(caught),canonical_lock_retained=True))
            if proof is None:
                time.sleep(.2)
        if process is not None:
            while True:
                try:
                    c.fresh(directory/'launcher-cleanup.json',w.pg.stop_group(process,process.pid))
                    break
                except BaseException as caught:
                    index+=1
                    c.fresh(directory/('launcher-cleanup-error-'+str(index)+'.json'),dict(error=repr(caught),canonical_lock_retained=True))
                    time.sleep(.2)
        c.fresh(directory/'terminal.json',dict(proof=proof,error=error,exit=None if process is None else process.returncode,
                utc=datetime.now(timezone.utc).isoformat(),owned_cgroup_terminal=True,canonical_lock_retained=True))
    c.require(error is None and process is not None and process.returncode==0,'Subset observation failed; retained '+str(directory))
    c.require(c.read(directory/'worker-intake.json')['verified'] is True,'Subset worker intake missing')
    result=c.read(directory/'stdout')['completion']
    c.check(result)
    c.require(result['path']==str(args.output.resolve()/'complete.json'),'Subset worker completion path differs')
    seal=c.read(result['path'])
    c.require(seal['complete'] is True and seal['source']==s.SOURCE and seal['controller']==c.pin(__file__)
              and seal['manifest']==c.pin(args.manifest),'Subset worker completion/source/input differs')
    for item in seal['outputs']:
        c.check(item)
    for stage in seal['stages']:
        w.evidence.stage(stage,c)
    c.fresh(args.output/'execution-complete.json',dict(schema='context-feedback-subset-execution/1',complete=True,
            worker=result,source=s.SOURCE,controller=c.pin(__file__),manifest=c.pin(args.manifest),
            terminal=c.pin(directory/'terminal.json'),command=c.pin(directory/'command.json'),
            worker_intake=c.pin(directory/'worker-intake.json'),stdout=c.pin(directory/'stdout'),stderr=c.pin(directory/'stderr'),
            whole_worker_cgroup_terminal=True))
    print(json.dumps(dict(completion=c.pin(args.output/'execution-complete.json'))))
