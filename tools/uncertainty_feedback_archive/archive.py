"""Lossless trace storage only; native science and original receipts remain unchanged.

Call only inside an admitted single-writer unit after the genuine producer's exact
recipe/runtime has qualified. The archive consumer independently revalidates it.
"""
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import zlib

CHUNK=1024*1024
PIN_FIELDS={'path','size','sha256'}
RAW=('command.sh','cwd.txt','start.txt','end.txt','exit-status.txt','stdout','stderr','time.txt')

def require(value,message):
    if not value: raise ValueError(message)

def filepin(value):
    require(isinstance(value,dict) and set(value)==PIN_FIELDS and isinstance(value['path'],str)
            and Path(value['path']).is_absolute() and type(value['size']) is int and value['size']>=0
            and isinstance(value['sha256'],str) and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']),
            'Exact absolute FilePin required')
    return value

@contextmanager
def regular(path,flags=os.O_RDONLY):
    path=Path(path); require(path.is_absolute(),'Absolute storage path required')
    fd=os.open(path,flags|os.O_NOFOLLOW,0o600)
    try:
        opened=os.fstat(fd); require(stat.S_ISREG(opened.st_mode) and opened.st_nlink==1,'Single-link regular file required')
        with os.fdopen(fd,'rb' if flags==os.O_RDONLY else 'wb',closefd=False) as stream:
            yield stream,opened
            current=os.fstat(fd); linked=path.lstat()
            identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            # Writes legitimately change size/time; the inode itself must stay stable.
            require((opened.st_dev,opened.st_ino)==(current.st_dev,current.st_ino)==(linked.st_dev,linked.st_ino)
                    and stat.S_ISREG(linked.st_mode) and linked.st_nlink==1,'Opened storage path identity changed')
            if flags==os.O_RDONLY: require(identity(opened)==identity(current),'Read file changed')
    finally: os.close(fd)

def digest(path):
    with regular(path) as (stream,_):
        count=0; sha=hashlib.sha256()
        while chunk:=stream.read(CHUNK): count+=len(chunk); sha.update(chunk)
    return dict(path=str(path),size=count,sha256=sha.hexdigest())

def check(item):
    filepin(item); require(digest(item['path'])==item,'Pinned current bytes changed')

def read(path):
    require(Path(path).stat().st_size<=16*1024**2,'Metadata exceeds16MiB')
    def unique(items):
        value={}
        for key,item in items: require(key not in value,'Duplicate metadata key'); value[key]=item
        return value
    with regular(path) as (stream,_):
        return json.load(stream,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))

def sync_directory(path):
    fd=os.open(Path(path),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)

def fresh(path,value):
    with regular(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL) as (stream,_):
        stream.write((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()); stream.flush(); os.fsync(stream.fileno())
    sync_directory(Path(path).parent)

def unique_pins(items):
    result={}
    for item in items:
        filepin(item); require(item['path'] not in result,'Duplicate catalogue path'); result[item['path']]=item
    return result

def metadata_fields(item,header):
    check(item); require(item['size']<=16*1024**2,'Frame metadata byte bound')
    with regular(item['path']) as (stream,_): lines=stream.read().decode().splitlines()
    require(lines and lines[0]==header,'Authenticated frame schema differs'); fields={}
    for line in lines[1:]:
        parts=line.split('\t'); require(len(parts)==2 and parts[0] not in fields,'Duplicate/malformed frame metadata field')
        fields[parts[0]]=parts[1]
    return fields

def native_query(request,binding,result,manifest):
    for key in ('legacy_plan','decoded_part'): check(request[key])
    planned=read(request['legacy_plan']['path']); part=read(request['decoded_part']['path'])
    require(planned['schema']=='uncertainty-feedback-plan/1' and planned['complete'] is True and planned['source_witness']==binding['source_witness']
            and part['schema']=='uncertainty-feedback-decoded/1' and part['complete'] is True and part['source_witness']==binding['source_witness']
            and part['plan']==planned and part['plan_sha256']==planned['plan_sha256'] and part['unchanged_decoder']==manifest['binary'],'Authenticated decoded part/full PLAN differs')
    check(planned['windows']); check(planned['joins'])
    require(planned['plan_sha256']==planned['windows']['sha256'],'Authenticated PLAN windows identity differs')
    require(type(part['rows']) is list and len(part['rows'])==1,'Authentic one-case part required')
    row=part['rows'][0]; query=row['query_index']
    require(type(query) is int and type(request['query_index']) is int and 0<=query<512 and query==request['query_index'],
            'Request query differs from authenticated singleton native identity')
    require(row['completion']==request['native_completion'] and row['producer']==request['producer'] and row['result']==request['result']
            and row['frame']==result['frame'],'Authenticated singleton/native file join differs')
    frame=metadata_fields(row['frame'],'guarded-frame/2'); base=metadata_fields(row['base_frame'],'context-frame/1'); check(row['construction'])
    joins=read(planned['joins']['path']); require(len(joins)==planned['nomination_count']==512,'Authenticated full PLAN census differs'); target=joins[query]
    require(target['query_index']==target['window']['query_index']==query and result['binding']==frame and base['query_index']==str(query)
            and base['plan_sha256']==planned['plan_sha256'] and base['parent']==target['window']['read_id'],
            'Authenticated native frame/base/PLAN query join differs')
    require(all(frame['base_frame_'+key]==str(row['base_frame'][key]) for key in ('path','size','sha256'))
            and frame['owned_start']==str(target['owned_start']) and frame['owned_end']==str(target['owned_end']),
            'Authenticated guarded/base Pin or ownership differs')
    construction=read(row['construction']['path'])
    require(construction['schema']=='uncertainty-feedback-frame-construction/1' and construction['new_plan_sha256']==planned['plan_sha256']
            and construction['target']==target and construction['original_window']==target['window'] and construction['frame']==row['frame']
            and construction['base_frame']==row['base_frame'] and construction['truth_input'] is False,'Authenticated construction/PLAN join differs')
    return query

def native_trace(request,binding):
    """Validate authentic original catalogues before storage conversion, without rewriting one."""
    require(request['legacy_source_binding']==binding,'Exact registered legacy binding differs')
    complete=request['native_completion']; producer_pin=request['producer']; result_pin=request['result']; original=request['original']
    for item in (complete,producer_pin,result_pin,request['old_decoder_manifest']): check(item)
    seal=read(complete['path']); producer=read(producer_pin['path']); result=read(result_pin['path']); manifest=read(request['old_decoder_manifest']['path'])
    require(seal['schema']=='context-decoder-complete/1' and seal['complete'] is True and result['schema']=='context-decoder-guarded-frame/2',
            'Authentic native completion/result schemas required')
    query=native_query(request,binding,result,manifest)
    catalogue=unique_pins(seal['files']); root=Path(complete['path']).parent
    require(set(catalogue)=={str(root/name) for name in ('attempt.json','result.json','phase-trace.bin')}
            and catalogue[str(root/'result.json')]==result_pin and catalogue[str(root/'phase-trace.bin')]==original==result['phase_trace'],
            'Native exact3 catalogue/result trace join differs')
    attempt_pin=catalogue[str(root/'attempt.json')]; check(attempt_pin); attempt=read(attempt_pin['path'])
    require(attempt['schema']=='context-decoder-attempt/1' and attempt['binary']==manifest['binary'] and len(attempt['compiled_sources'])==32
            and unique_pins(attempt['compiled_sources'])==unique_pins(manifest['compiled_sources']), 'Native unique32 source catalogue differs')
    argv=[manifest['binary']['path'],'decode-guarded','--frame',result['frame']['path'],'--frame-sha256',result['frame']['sha256'],
          '--output',str(root),'--beam','128','--min-center','0','--max-center','108','--weight','0.5','--deficit','0.5','--margin','0.5']
    require(attempt['argv']==argv and attempt['cpp_standard']==23 and attempt['fast_math'] is False and attempt['fp_contract']=='off'
            and producer['schema']=='uncertainty-feedback-command/1' and producer['complete'] is True and producer['exit_status']==0
            and producer['source_witness']==binding['source_witness'] and producer['binary']==manifest['binary'] and producer['argv']==argv
            and producer['inputs']==[result['frame'],*manifest['compiled_sources']], 'Literal native binary/argv/input/witness differs')
    require(unique_pins(producer['produced_files'])==dict(catalogue,**{complete['path']:complete}),'Native exact4 produced catalogue differs')
    require(len(producer['raw_files'])==8,'Native raw8 required')
    raw=Path(producer['raw_files'][0]['path']).parent
    for name,item in zip(RAW,producer['raw_files']):
        require(item['path']==str(raw/name),'Native raw8 order/path differs'); check(item)
    require(read(raw/'stdout')==dict(completion=complete) and (raw/'exit-status.txt').read_text()=='0\n','Native original completion stdout/exit join differs')
    # Full legacy source/frame/scalar/runtime/raw-clock guards belong to the admitted
    # exact producer controller and distinct consumer, not to a storage receipt.
    return original,query

def verify_gzip(path,original,maximum_archive_bytes,expected_archive=None,durable=False):
    """One gzip member, no trailing bytes; stream bounds and hashes both identities."""
    filepin(original); count=stored=0; raw_hash=hashlib.sha256(); archive_hash=hashlib.sha256(); decoder=zlib.decompressobj(31)
    with regular(path) as (stream,opened):
        require(opened.st_size<=maximum_archive_bytes,'Compressed storage reservation exceeded')
        while block:=stream.read(CHUNK):
            stored+=len(block); archive_hash.update(block)
            if stored==len(block): require(block[:10]==bytes.fromhex('1f8b08000000000000ff'),'Frozen gzip header differs')
            require(stored<=maximum_archive_bytes and not decoder.eof,'Trailing gzip bytes/member rejected')
            pending=block
            while pending:
                room=original['size']+1-count; require(room>0,'Expanded trace exceeds original bound')
                output=decoder.decompress(pending,min(CHUNK,room)); count+=len(output); raw_hash.update(output)
                require(count<=original['size'] and not decoder.unused_data,'Expanded bound/trailing gzip bytes rejected')
                pending=decoder.unconsumed_tail
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,'Truncated gzip stream')
        archive=dict(path=str(path),size=stored,sha256=archive_hash.hexdigest())
        require(count==original['size'] and raw_hash.hexdigest()==original['sha256'],'Lossless original trace identity differs')
        if expected_archive is not None: require(archive==expected_archive,'Current gzip FilePin differs')
        if durable:
            os.fsync(stream.fileno()); sync_directory(Path(path).parent)
        return archive

def archive_trace(request_pin,binding,codec_runtime):
    """Durable exact-request conversion/recovery; keep raw on every pre-verification failure.

    A retained partial archive is never overwritten/recompressed. A fresh admitted
    recovery may only verify it, publish missing own metadata, then prune raw.
    """
    check(request_pin); request=read(request_pin['path'])
    require(set(request)=={'schema','query_index','native_completion','producer','result','original','old_decoder_manifest',
            'legacy_source_binding','codec','codec_runtime','maximum_archive_bytes','archive','intent','receipt','raw_policy','legacy_plan','decoded_part'}
            and request['schema']=='targeting-trace-archive-request/1' and type(request['query_index']) is int and 0<=request['query_index']<512,
            'Typed trace archive request differs')
    require(request['codec']==dict(format='gzip',level=6,mtime=0,filename='',members='single-no-trailing')
            and request['codec_runtime']==codec_runtime,'Frozen codec/runtime tuple differs')
    for item in codec_runtime.values(): check(item)
    original,query=native_trace(request,binding)
    return _convert(request_pin,request,original,codec_runtime,query)

def _convert(request_pin,request,original,codec_runtime,query):
    """Storage state machine; caller archive_trace authenticates native provenance."""
    maximum=request['maximum_archive_bytes']
    require(request['query_index']==query and request['raw_policy']==('retain-native-anchor' if query==0 else 'prune-after-durable-archive'),
            'Fixed q0 retained anchor/subsequent archive policy differs')
    require(type(maximum) is int and original['size']>0 and maximum==original['size']+1048576,'Exact case storage reservation differs')
    paths=[Path(request[name]) for name in ('archive','intent','receipt')]
    require(len(set(paths))==3 and all(p.is_absolute() for p in paths) and all(p.parent==paths[0].parent for p in paths)
            and paths[0].parent.resolve(strict=True)==paths[0].parent and paths[0].parent.is_relative_to(Path('/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback')),
            'Fresh archive metadata must share an owned monitored directory')
    archive,intent,receipt=paths; source=digest(Path(__file__).resolve())
    declaration=dict(schema='targeting-trace-archive-intent/1',request=request_pin,source=source,original=original,archive=str(archive))
    if intent.exists(): require(read(intent)==declaration,'Prior archive intent/source/request differs')
    else:
        require(not archive.exists() and not receipt.exists(),'Unattributed archive/receipt refuses overwrite'); fresh(intent,declaration)
    if not archive.exists():
        with regular(original['path']) as (raw,opened),regular(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL) as (out,_):
            require(opened.st_size==original['size'],'Raw trace size changed'); sha=hashlib.sha256(); count=0
            with gzip.GzipFile(filename='',mode='wb',compresslevel=6,fileobj=out,mtime=0) as encoder:
                while chunk:=raw.read(CHUNK):
                    count+=len(chunk); sha.update(chunk); require(count<=original['size'],'Raw trace grew')
                    encoder.write(chunk); out.flush(); require(out.tell()<=maximum,'Gzip reservation exceeded')
            out.flush(); os.fsync(out.fileno()); require(out.tell()<=maximum,'Gzip footer reservation exceeded')
            require(count==original['size'] and sha.hexdigest()==original['sha256'],'Raw trace identity changed')
        sync_directory(archive.parent)
    archive_pin=verify_gzip(archive,original,maximum,durable=True)
    descriptor=dict(query_index=query,native_completion=request['native_completion'],producer=request['producer'],
                    storage=dict(codec='gzip',original=original,archive=archive_pin))
    proof=dict(schema='targeting-trace-archive-receipt/1',complete=True,request=request_pin,source=source,intent=digest(intent),descriptor=descriptor,
               codec=request['codec'],codec_runtime=codec_runtime,raw_policy=request['raw_policy'],lossless=True,native_files_rewritten=False,native_producer_replayed=False)
    if receipt.exists(): require(read(receipt)==proof,'Prior archive receipt differs')
    else: fresh(receipt,proof)
    # Receipt and directory are durable before raw pruning. The receipt asserts
    # verified storage custody, never that a native producer or old seal reran.
    if request['raw_policy']=='retain-native-anchor':
        check(original)
    elif Path(original['path']).exists():
        check(original); os.unlink(original['path']); sync_directory(Path(original['path']).parent)
    verify_gzip(archive,original,maximum,archive_pin)
    require(Path(original['path']).exists()==(request['raw_policy']=='retain-native-anchor'),'Final physical storage policy differs')
    return dict(descriptor=descriptor,receipt=digest(receipt),raw_trace_present=Path(original['path']).exists())
