"""Bounded synthetic codec/storage controls, executed only by a separately admitted worker."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch
import zlib

def run(root,source):
    root=Path(root); root.mkdir(exist_ok=False)
    spec=importlib.util.spec_from_file_location('targeting_archive_codec_controls',source)
    archive=importlib.util.module_from_spec(spec); spec.loader.exec_module(archive)
    cases=[]
    def require(value,message):
        if not value: raise ValueError(message)
    def scenario(name,index=1):
        directory=root/name; directory.mkdir(); raw=directory/'phase-trace.bin'; raw.write_bytes(b'SYNTHETIC storage fixture\nACGT\n'*256)
        original=archive.digest(raw); marker=directory/'synthetic-origin.txt'; marker.write_text('SYNTHETIC; not a native producer or seal\n'); markerpin=archive.digest(marker)
        request=dict(query_index=index,native_completion=markerpin,producer=markerpin,codec=dict(format='gzip',level=6,mtime=0,filename='',members='single-no-trailing'),
            raw_policy='retain-native-anchor' if index==0 else 'prune-after-durable-archive',maximum_archive_bytes=original['size']+1048576,
            archive=str(directory/'phase-trace.bin.gz'),intent=str(directory/'archive-intent.json'),receipt=str(directory/'archive-receipt.json'))
        request_path=directory/'synthetic-storage-request.json'; request_path.write_text(json.dumps(request,sort_keys=True)+'\n')
        return request,archive.digest(request_path),original
    def accepted(name,action): action(); cases.append(dict(name=name,expected='accept',status='passed'))
    def rejected(name,action,after=None):
        try: action()
        except (ValueError,zlib.error,OSError):
            if after: after()
            cases.append(dict(name=name,expected='reject',status='passed'))
        else: raise ValueError('Synthetic negative accepted: '+name)
    request,request_pin,original=scenario('normal')
    result=archive._convert(request_pin,request,original,{},request['query_index'])
    require(not Path(original['path']).exists() and Path(request['receipt']).exists(),'Prune must follow durable successful proof')
    accepted('lossless conversion prunes only redundant raw',lambda:archive.verify_gzip(request['archive'],original,request['maximum_archive_bytes'],result['descriptor']['storage']['archive']))
    before=archive.digest(request['archive']); again=archive._convert(request_pin,request,original,{},request['query_index'])
    accepted('exact repeat validates same archive and receipt',lambda:require(again==result and archive.digest(request['archive'])==before,'Repeat changed archive/receipt'))
    keep,keep_pin,keep_original=scenario('retained-q0-anchor',0); keep_result=archive._convert(keep_pin,keep,keep_original,{},keep['query_index'])
    accepted('q0 anchor stays physical while gzip verifies',lambda:require(keep_result['raw_trace_present'] and archive.digest(keep_original['path'])==keep_original,'Retained q0 anchor lost'))
    wrong=copy.deepcopy(keep); wrong['raw_policy']='prune-after-durable-archive'
    rejected('q0 prune policy rejected',lambda:archive._convert(keep_pin,wrong,keep_original,{},wrong['query_index']))
    fail,fail_pin,fail_original=scenario('publication-failure')
    actual_fresh=archive.fresh
    def failed_publication(path,value):
        if Path(path)==Path(fail['receipt']): raise OSError('Synthetic receipt publication failure')
        return actual_fresh(path,value)
    with patch.object(archive,'fresh',failed_publication):
        rejected('failed durable receipt retains raw',lambda:archive._convert(fail_pin,fail,fail_original,{},fail['query_index']),
            lambda:require(Path(fail_original['path']).exists() and not Path(fail['receipt']).exists(),'Raw lost before receipt'))
    prior_gzip=archive.digest(fail['archive']); recovered=archive._convert(fail_pin,fail,fail_original,{},fail['query_index'])
    accepted('explicit exact recovery verifies without recompression',lambda:require(archive.digest(fail['archive'])==prior_gzip and not recovered['raw_trace_present'],'Recovery rewrote or failed prune'))
    interrupted,interrupted_pin,interrupted_original=scenario('preexisting-before-original-sync')
    actual_fsync=archive.os.fsync
    def stop_original_sync(fd):
        if Path(os.readlink('/proc/self/fd/'+str(fd)))==Path(interrupted['archive']):
            raise OSError('Synthetic interruption before initial archive data sync')
        return actual_fsync(fd)
    with patch.object(archive.os,'fsync',stop_original_sync):
        rejected('interruption before original archive fsync retains raw',
            lambda:archive._convert(interrupted_pin,interrupted,interrupted_original,{},interrupted['query_index']),
            lambda:require(Path(interrupted_original['path']).exists() and not Path(interrupted['receipt']).exists(),'Raw lost before archive sync'))
    archive_before=archive.digest(interrupted['archive']); events=[]; actual_unlink=archive.os.unlink
    def recorded_sync(fd):
        path=Path(os.readlink('/proc/self/fd/'+str(fd)))
        if path==Path(interrupted['archive']): events.append('archive-sync')
        elif path==Path(interrupted['archive']).parent: events.append('directory-sync')
        return actual_fsync(fd)
    def recorded_fresh(path,value):
        if Path(path)==Path(interrupted['receipt']):
            require('archive-sync' in events and 'directory-sync' in events and events.index('archive-sync')<events.index('directory-sync'),
                    'Preexisting verified archive+directory must sync before receipt')
            events.append('receipt-publication')
        return actual_fresh(path,value)
    def recorded_unlink(path,*args,**kwargs):
        if Path(path)==Path(interrupted_original['path']):
            require('receipt-publication' in events and Path(interrupted['receipt']).is_file(),'Prune before durable receipt')
            events.append('raw-prune')
        return actual_unlink(path,*args,**kwargs)
    with patch.object(archive.os,'fsync',recorded_sync),patch.object(archive,'fresh',recorded_fresh),patch.object(archive.os,'unlink',recorded_unlink):
        resumed=archive._convert(interrupted_pin,interrupted,interrupted_original,{},interrupted['query_index'])
    accepted('preexisting recovery sync barrier precedes proof and prune',lambda:require(
        archive.digest(interrupted['archive'])==archive_before and not resumed['raw_trace_present']
        and events.index('archive-sync')<events.index('directory-sync')<events.index('receipt-publication')<events.index('raw-prune'),
        'Preexisting recovery barrier/order/identity failed'))
    bad,bad_pin,bad_original=scenario('raw-hash-failure'); changed=dict(bad_original,sha256='0'*64)
    rejected('raw hash mismatch retains raw and no receipt',lambda:archive._convert(bad_pin,bad,changed,{},bad['query_index']),
        lambda:require(Path(bad_original['path']).exists() and not Path(bad['receipt']).exists(),'Raw lost on mismatch'))
    rejected('retained bad partial archive refuses overwrite',lambda:archive._convert(bad_pin,bad,bad_original,{},bad['query_index']),
        lambda:require(Path(bad_original['path']).exists(),'Partial recovery lost raw'))
    good=Path(request['archive']).read_bytes()
    for name,bytes_ in [('truncated',good[:-4]),('CRC',good[:-8]+bytes([good[-8]^1])+good[-7:]),('trailing',good+b'x'),('second-member',good+good),('header',good[:9]+b'\x03'+good[10:])]:
        path=root/(name+'.gz'); path.write_bytes(bytes_)
        rejected('gzip '+name,lambda path=path:archive.verify_gzip(path,original,request['maximum_archive_bytes']))
    rejected('expanded raw size overrun',lambda:archive.verify_gzip(request['archive'],dict(original,size=original['size']-1),request['maximum_archive_bytes']))
    rejected('wrong original raw SHA',lambda:archive.verify_gzip(request['archive'],dict(original,sha256='0'*64),request['maximum_archive_bytes']))
    rejected('wrong current compressed Pin',lambda:archive.verify_gzip(request['archive'],original,request['maximum_archive_bytes'],dict(before,sha256='0'*64)))
    rejected('compressed bound exceeded',lambda:archive.verify_gzip(request['archive'],original,1))
    linked=root/'symlink.gz'; linked.symlink_to(request['archive'])
    rejected('gzip symlink rejected',lambda:archive.verify_gzip(linked,original,request['maximum_archive_bytes']))
    return dict(schema='targeting-archive-codec-controls/1',complete=True,synthetic_only=True,native_acceptance=False,biological_qualification=False,
                source=archive.digest(source),assertions=len(cases),skipped=0,cases=cases)
