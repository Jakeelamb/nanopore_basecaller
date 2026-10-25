import ast, hashlib, json
from pathlib import Path
R=Path.cwd(); O=R/'logs/context-sample-feedback/query0-partial-trace-ready'; S=R/'logs/context-sample-feedback/source-ready'
def pin(p):
 b=p.read_bytes(); assert len(b)<=8*1024**2; return dict(path=str(p),size=len(b),sha256=hashlib.sha256(b).hexdigest())
p=S/'audit-query0.py'; tree=ast.parse(p.read_text()); f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='trace'); parser=ast.get_source_segment(p.read_text(),f)
parser=parser.replace('bundles = generated = merged = dropped = 0','bundles = generated = merged = dropped = 0\n    prefix_sets = []').replace('    count_finalists = integer()','        prefix_sets.append(frozenset(seen))\n    count_finalists = integer()').replace('pruned_bundles=dropped, finalists=finalists)','pruned_bundles=dropped, finalists=finalists, prefix_sets=prefix_sets)')
a=json.loads((S/'query0-1-audit.json').read_text()); summary=json.loads((R/'results/context-sample-feedback/sample-query0-1/summary.json').read_text()); native=json.loads(Path(summary['native'][0]['path']).read_text())
paths=[S/'query0-1-audit.json',p,S/'source-inventory-post-format-2.json',R/'results/context-sample-feedback/sample-query0-1/summary.json',Path(a['completion']['path']),Path(a['archives']['path']),Path(a['native_completion']['path']),Path(a['producer']['path']),Path(a['native_result']['path']),Path(summary['prepared']['frames']['path'])]
pins={str(p):pin(p) for p in paths}
(O/'input-pins.json').write_text(json.dumps(dict(metadata=pins,producer_binary=a['binary'],source_identity=a['source_identity'],storage=a['storage'],expected_steps=103,expected_finalists=128,parser_origin=pin(p if False else S/'audit-query0.py')),indent=2)+'\n')
(O/'compare.py').write_text('''"""Retained query0 trace observation only; no producer imports or execution."""
import argparse, csv, gzip, hashlib, json, math, struct
from pathlib import Path

'''+parser+'''

def checked(row):
    p=Path(row['path'])
    assert p.stat().st_size == row['size'], str(p)
    b=p.read_bytes()
    assert hashlib.sha256(b).hexdigest() == row['sha256'], str(p)
    return b

def set_hash(values):
    return hashlib.sha256(json.dumps(sorted(values),separators=(',',':')).encode()).hexdigest()

def compare(a,b):
    assert len(a)==len(b)==103
    rows=[]
    for step,(x,y) in enumerate(zip(a[:-1],b[:-1]),1):
        rows.append(dict(step=step,equal=x==y,free_size=len(x),source_size=len(y),
            free_only=len(x-y),source_only=len(y-x),free_set_sha256=set_hash(x),source_set_sha256=set_hash(y)))
    changed=[r['step'] for r in rows if not r['equal']]
    return dict(nonterminal_steps=102,changed_steps=len(changed),first_changed_step=next(iter(changed),None),steps=rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=Path); args=ap.parse_args()
    pins=json.loads(Path(__file__).with_name('input-pins.json').read_text())
    meta={p:checked(row) for p,row in pins['metadata'].items()}
    def item(suffix):
        return json.loads(next(v for p,v in meta.items() if p.endswith(suffix)))
    audit=item('/query0-1-audit.json'); outer=item('/execution-complete.json'); summary=item('/summary.json')
    native=item('/native-case/complete.json'); archives=item('/trace-archives.json')
    assert outer['complete'] and outer['whole_worker_cgroup_terminal']
    assert audit['trace_eof_all_vectors_counts_and_hashes_verified'] and audit['source_files_rehashed']
    assert summary['binary']==audit['binary']==pins['producer_binary']
    assert audit['source_identity']==pins['source_identity']=='63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2'
    inventory=item('/source-inventory-post-format-2.json')
    assert native['source']['compiled_sources']==inventory['sources']
    assert inventory['sha256']==pins['source_identity']
    assert summary['native'][0]==audit['native_completion'] and summary['stages'][0]==audit['producer']
    assert archives['lossless'] and len(archives['archives'])==4
    assert {r['original']['path']:r for r in archives['archives']}=={r['raw']['path']:dict(original=r['raw'],archive=r['archive']) for r in pins['storage']}
    frames_path=summary['prepared']['frames']['path']
    import io
    frame=next(r for r in csv.DictReader(io.StringIO(meta[frames_path].decode()),delimiter='\\t') if r['case_id']=='ordinary/0/ordinary')
    assert summary['prepared']['frames'] in native['inputs']
    frame_pin=dict(path=frame['frame_path'],size=int(frame['frame_size']),sha256=frame['frame_sha256'])
    fields=dict(line.split('\\t',1) for line in checked(frame_pin).decode().splitlines()[1:])
    beams={}
    for row in pins['storage']:
        compressed=checked(row['archive']); assert compressed[4:8]==b'\\0\\0\\0\\0'
        # Bound decompression by the sealed raw size; no disk extraction.
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw=stream.read(row['raw']['size']+1)
            assert len(raw)==row['raw']['size'] and stream.read(1)==b''
        assert hashlib.sha256(raw).hexdigest()==row['raw']['sha256']
        parsed=trace(raw,len(fields['left_guard']),len(fields['right_guard']))
        name=row['beam']; assert name not in beams
        expected=audit['traces'][name]
        for key in ('pruned','bound','steps','retained_bundles','generated','merged','pruned_bundles'):
            assert parsed[key]==expected[key]
        assert len(parsed['finalists'])==expected['finalist_count']==128
        assert set(parsed['finalists'])<=parsed['prefix_sets'][-1]
        beams[name]=parsed
    assert set(beams)=={'free','population','sample','combined'}
    report=dict(schema='query0-retained-prefix-comparison/1',complete=True,
        source_identity=pins['source_identity'],completion=audit['completion'],archives=audit['archives'],
        original_producer_pins_verified_against_sealed_metadata=True,producer_binary_rehashed=False,
        source_payloads_rehashed=False,prior_full_trace_validation=audit['completion'],
        trace_steps=103,nonterminal_steps_compared=102,terminal_step_excluded=True,
        comparisons={name:compare(beams['free']['prefix_sets'],beams[name]['prefix_sets']) for name in ('population','sample','combined')},
        pruned={n:b['pruned'] for n,b in beams.items()},global_optimum_claim=False,
        numerical_differences_alone_counted=False,producer_rerun=False,truth_read=False)
    with args.output.open('x') as stream: json.dump(report,stream,indent=2); stream.write('\\n')
    print(json.dumps({n:{k:v for k,v in r.items() if k!='steps'} for n,r in report['comparisons'].items()},sort_keys=True))

if __name__=='__main__': main()
''')
print(json.dumps(dict(metadata_files=len(paths),metadata_bytes=sum(r['size'] for r in pins.values()),archive_body_reads=0)))
