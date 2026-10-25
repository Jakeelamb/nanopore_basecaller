import datetime, fcntl, hashlib, json, os, pathlib, resource, shutil, subprocess, time, traceback

O=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/home/jake/Projects/nanopore_basecaller-reference')
P=pathlib.Path('/home/jake/Projects/nanopore_basecaller-private')
read=lambda p:json.loads(pathlib.Path(p).read_text())
utc=lambda:datetime.datetime.now(datetime.timezone.utc)
grant=read(O/'grant.json')
assert utc()<datetime.datetime.fromisoformat(grant['hard_end'])-datetime.timedelta(seconds=5)
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
resource.setrlimit(resource.RLIMIT_RSS,(4*1024**3,)*2)
resource.setrlimit(resource.RLIMIT_CPU,(30,35))
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
assert shutil.disk_usage(P).free>=30*1024**3
lock=open('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock','a')
began=time.monotonic()
while True:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
    except BlockingIOError:
        assert time.monotonic()-began<30
        time.sleep(.1)

def pin(path):
    path=pathlib.Path(path);data=path.read_bytes()
    return dict(path=str(path),size=len(data),sha256=hashlib.sha256(data).hexdigest())
def pins(value):
    out=[]
    if isinstance(value,dict):
        if {'path','size','sha256'}<=value.keys():out.append({k:value[k] for k in ('path','size','sha256')})
        for v in value.values():out.extend(pins(v))
    elif isinstance(value,list):
        for v in value:out.extend(pins(v))
    return out

result=dict(start=utc().isoformat(),scope='Observation repair only. No scientific producer rerun.',errors=[])
try:
    report=R/'provenance/verification/graph-prior-v1.json'
    expected=next(x['expected'] for x in read(O/'checked-pins.json') if x['expected']['path']==str(report))
    assert pin(report)==expected
    registered={p['path']:p for p in pins(read(report))}
    manifest=R/'results/graph-prior/pilot-v1/development/artifacts/native-call.json'
    assert pin(manifest)==registered[str(manifest)]
    original={p['path']:p for p in pins(read(manifest))}
    associations=read(O/'tensor-associations.json');metadata=[];parents=set()
    for t in associations['tensors']:
        tensor=t['score'];assert tensor==original[tensor['path']]
        m=pathlib.Path(tensor['path']+'.meta.tsv');actual=pin(m);assert actual==original[str(m)];metadata.append(actual);parents.add(t['parent'])
    for parent in sorted(parents):
        path=manifest.parent.parent/'native-export'/(parent+'.parent.tsv');actual=pin(path);assert actual==original[str(path)];metadata.append(actual)
    result['native_export_registration']=dict(status='pass',pilot_report=expected,registered_export_manifest=pin(manifest),tensor_hashes_compared_to_registered_native_export=len(associations['tensors']),fresh_metadata_and_parent_checks=len(metadata),metadata_pins=metadata,no_tensor_rehash=True)
except Exception:
    result['errors'].append('native_export_registration');result['native_export_registration']=dict(status='fail',traceback=traceback.format_exc())

try:
    retention=read(P/'results/private-allele/additional-challenge-v1/source-retention.json')
    source=next(r['retained'] for r in retention if r['original']['path'].endswith('/release/private-allele-challenge'))
    actual=pin(source['path']);assert actual==source
    binary=O/'negative-control-binary';shutil.copyfile(source['path'],binary);binary.chmod(0o700)
    copied=pin(binary);assert (copied['size'],copied['sha256'])==(source['size'],source['sha256'])
    case=next(json.loads(line) for line in (P/'results/private-allele/additional-challenge-v1/inference.jsonl').read_text().splitlines() if json.loads(line)['case_id']=='additional_original/21')
    controls=[]
    for level in ('case','hypothesis'):
        bad=json.loads(json.dumps(case))
        if level=='case':bad['genotype']='0/1'
        else:bad['hypotheses'][0]['truth_alt']='C'
        inp=O/('supplement-truth-'+level+'.jsonl');out=O/('supplement-rejected-'+level+'.jsonl');inp.write_text(json.dumps(bad)+'\n')
        argv=[str(binary),'infer',str(inp),str(out)];start=utc();done=subprocess.run(argv,capture_output=True,text=True,timeout=5)
        (O/('supplement-truth-'+level+'.stderr')).write_text(done.stderr)
        assert done.returncode!=0 and 'unknown field' in done.stderr and out.stat().st_size==0
        controls.append(dict(level=level,argv=argv,start=start.isoformat(),end=utc().isoformat(),exit=done.returncode,stderr=done.stderr,output_bytes=out.stat().st_size))
    result['truth_rejection']=dict(status='pass',retained_binary=source,executable_copy=copied,retained_mode=oct(pathlib.Path(source['path']).stat().st_mode&0o777),controls=controls)
except Exception:
    result['errors'].append('truth_rejection');result['truth_rejection']=dict(status='fail',traceback=traceback.format_exc())
assert utc()<datetime.datetime.fromisoformat(grant['hard_end'])
assert sum(p.stat().st_size for p in O.rglob('*') if p.is_file())<=100*1024**2
result.update(end=utc().isoformat(),complete=not result['errors'])
(O/'supplement-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(complete=result['complete'],start=result['start'],end=result['end'],errors=result['errors'],native_export_registration=result['native_export_registration']['status'],truth_rejection=result['truth_rejection']['status'])))
raise SystemExit(0 if result['complete'] else 1)
