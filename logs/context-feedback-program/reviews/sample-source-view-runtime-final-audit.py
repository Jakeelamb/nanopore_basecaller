"""Read-only bounded retained-producer audit. Run no product code or native tool."""
import argparse
import bisect
import collections
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import struct
import traceback
import zlib

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-support-v2')
REVIEWS = ROOT / 'logs/context-feedback-program/reviews'
HELPERS = ROOT / 'logs/context-feedback/program-runs'
MIB = 1024**2
MAX_READ = 90*MIB
MAX_FILE = 8*MIB
RAW_NAMES = {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}
ENV = dict(UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv', UV_OFFLINE='1',
           UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1', REF_PATH='/dev/null', REF_CACHE='/dev/null')
RUN = '11d77535b149da7c6f7153939924a9fe29559cc7'
CACHE = {}
READ_BYTES = 0
RANGE_BYTES = 0
CHECKED = {}
SKIPPED = {}
COMMANDS = []
REPORT = {}


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def small(path):
    global READ_BYTES
    path = Path(path)
    key = str(path.resolve())
    if key in CACHE:
        return CACHE[key]
    size = path.stat().st_size
    need(size <= MAX_FILE, 'Refused file above 8MiB: '+str(path))
    need(READ_BYTES+size <= MAX_READ, 'Read budget reached')
    data = path.read_bytes()
    READ_BYTES += len(data)
    need(len(data) == size and path.stat().st_size == size, 'File size changed: '+str(path))
    CACHE[key] = data
    return data


def science(path):
    text = str(path)
    return (text.endswith('.data') or text.endswith('.cram') or text.endswith('selected-view.cram')
            or ('sample-view-pilot-' in text or 'sample-view-full-' in text) and text.endswith('/stdout')
            or '/accuracy-reference-decompress-' in text and text.endswith('/stdout'))


def check(pin, force=False):
    path = Path(pin['path'])
    need(path.stat().st_size == pin['size'], 'Current size differs: '+str(path))
    if not force and (pin['size'] > MAX_FILE or science(path)):
        SKIPPED[str(path)] = dict(pin, independent='current-size-only', hash_evidence='retained producer/consumer full-file pin')
        return None
    data = small(path)
    need(digest(data) == pin['sha256'], 'Hash differs: '+str(path))
    CHECKED[str(path)] = pin
    return data


def read(pin):
    data = check(pin)
    need(data is not None, 'Refused JSON interpretation of payload: '+pin['path'])
    return json.loads(data)


def unpinned_json(path):
    return json.loads(small(path))


def pin_for(path):
    data = small(path)
    return dict(path=str(Path(path).resolve()), size=len(data), sha256=digest(data))


def stamp(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def wall(text):
    result = 0.0
    for piece in text.split(':'):
        result = result*60+float(piece)
    return result


def raw_check(raw, argv):
    need(set(raw) == RAW_NAMES, 'Raw file census differs')
    for value in raw.values():
        check(value)
    text = {key:small(raw[key]['path']).decode() for key in RAW_NAMES-{'stdout'}}
    need(shlex.split(text['command.sh']) == argv, 'Actual raw argv differs')
    need(text['cwd.txt'].strip() == str(ROOT), 'Actual raw cwd differs')
    need(text['exit-status.txt'].strip() == '0' and text['stderr'] == '', 'Nonzero/raw stderr')
    begin, end = text['start.txt'].strip(), text['end.txt'].strip()
    need(begin.endswith('Z') and end.endswith('Z') and stamp(begin) <= stamp(end), 'Raw clocks differ')
    timing = dict(line.strip().split(': ', 1) for line in text['time.txt'].splitlines() if line.startswith('\t') and ': ' in line)
    need(timing['Exit status'] == '0' and timing['Command being timed'] == '"'+' '.join(argv)+'"', 'Raw time command/exit differs')
    need(float(timing['User time (seconds)']) >= 0 and float(timing['System time (seconds)']) >= 0
         and int(timing['Maximum resident set size (kbytes)']) > 0, 'Raw time/RSS invalid')
    COMMANDS.append(dict(argv=argv, cwd=str(ROOT), raw=raw, start=begin, end=end, elapsed_seconds=wall(timing['Elapsed (wall clock) time (h:mm:ss or m:ss)'])))
    return begin, end


def stage_check(value):
    stage = read(value)
    need(stage['exit'] == 0 and stage['failure'] is None and stage['projection_error'] is None
         and stage['missing_raw'] == [] and stage['explicit_env'] == ENV, 'Stage receipt failed')
    terminal = read(stage['terminal'])
    need(terminal['argv'] == stage['argv'] and terminal['exit'] == 0 and terminal['failure'] is None, 'Stage terminal differs')
    need(read(stage['group_cleanup'])['terminal'] is True, 'Stage group not terminal')
    raw_check(stage['raw'], stage['argv'])
    return stage


def file_named(seal, name):
    matches = [value for value in seal['files'] if Path(value['path']).name == name]
    need(len(matches) == 1, 'Missing/duplicate file '+name)
    return matches[0]


def phase_check(phase, recorder_pin):
    seal, outer, price = read(phase['completion']), read(phase['outer']), read(phase['price'])
    start = read(outer['start'])
    terminal, cleanup, active = read(outer['terminal']), read(outer['launcher_cleanup']), read(seal['worker_intake'])
    intake = read(start['intake'])
    need(seal['complete'] is True and seal['phase'] == phase['phase'], 'Unit phase differs')
    need(start['worker'] == price['worker'] == pin_for(HELPERS/'sample-source-view-v1.py'), 'Worker differs')
    need(start['controller'] == pin_for(HELPERS/'run-sample-bounded-v2.py')
         and start['runtime'] == pin_for(HELPERS/'sample-runtime.py'), 'Controller/runtime differs')
    need(start['recorder'] == outer['recorder'] == recorder_pin and start['cwd'] == str(ROOT), 'Recorder/cwd differs')
    need(start['lock'] == intake['canonical_lock'] == '/home/jake/Projects/nanopore_basecaller/results/stock/host.lock', 'Canonical lock differs')
    need(outer['projection_error'] is None and outer['lock_retained'] is True and terminal['exit'] == 0
         and terminal['error'] is None and terminal['lock_retained_during_projection'] is True and cleanup['terminal'] is True, 'Outer terminal failed')
    p = terminal['proof']['properties']
    need(terminal['proof']['exit'] == 0 and p['ActiveState'] == 'inactive' and p['Result'] == 'success'
         and p['MainPID'] == p['ControlPID'] == '0' and p['ControlGroup'] == '', 'Service terminal differs')
    need(terminal['live_worker_intake'] == seal['worker_intake'] == phase['worker_intake'], 'Live intake linkage differs')
    ap = active['observation']['properties']
    need(active['verified'] is True and active['parent_lock_retained'] is True and active['intake'] == start['intake']
         and active['observation']['exit'] == 0 and ap['ActiveState'] == 'active' and ap['LoadState'] == 'loaded'
         and ap['Description'] == intake['description'] and ap['ControlGroup'] == intake['cgroup'] == terminal['expected_cgroup']
         and ap['Type'] == 'exec' and ap['ExitType'] == 'cgroup' and ap['KillMode'] == 'control-group'
         and ap['CollectMode'] == 'inactive' and ap['SendSIGKILL'] == 'yes' and ap['FinalKillSignal'] == '9'
         and ap['RuntimeMaxUSec'] == '4min 55s' and ap['TimeoutStopUSec'] == '1s', 'Active policy differs')
    need(active['kernel']['cpu.max'] == '200000 100000' and active['kernel']['memory.max'] == '4294967296'
         and active['kernel']['memory.swap.max'] == '0' and active['rlimit_as'] == [8589934592,8589934592]
         and active['explicit_env'] == ENV, 'Live caps/env differ')
    caps = start['caps']
    need(caps == phase['caps'] and caps['cpu'] == 2 and caps['memory'] == 4*1024**3 and caps['address_space'] == 8*1024**3
         and caps['swap'] == 0 and caps['wall_seconds'] == 300 and caps['service_seconds'] == 295
         and caps['maximum_new_bytes'] == price['maximum_new_bytes']
         and caps['maximum_cumulative_bytes'] == 2*1024**3, 'Price/caps differ')
    resources = outer['final_resources']
    need(resources == phase['resources'] and resources['new_bytes'] <= price['maximum_new_bytes']
         and resources['cumulative_bytes'] <= 2*1024**3 and resources['free_bytes'] >= 30*1024**3, 'Final resources exceed caps')
    expected = ['/home/jake/.local/bin/uv','run','--no-sync','python',price['worker']['path'],price['id'],
                '--intake',start['intake']['path'],'--intake-sha256',start['intake']['sha256'],*price['worker_arguments']]
    need(start['worker_argv'] == expected and read(intake['price']) == price, 'Actual worker task/price argv differs')
    raw_check(outer['raw'], expected)
    need(json.loads(small(outer['raw']['stdout']['path'])) == dict(completion=phase['completion']), 'Outer stdout binding differs')
    need(COMMANDS[-1]['elapsed_seconds'] <= 300, 'Whole-unit actual wall exceeded 300s')
    for value in seal['sources']+start['sources']+active['sources']+seal['files']:
        check(value)
    stages = [stage_check(value) for value in seal['stages']]
    need([q['receipt'] for q in phase['stages']] == seal['stages'], 'Handoff stage census differs')
    report = read(file_named(seal,'native-report.json'))
    group_path = Path('/sys/fs/cgroup')/terminal['expected_cgroup'].lstrip('/')
    need(not group_path.exists(), 'Old service cgroup currently exists')
    process_stat = Path('/proc')/str(intake['parent_pid'])/'stat'
    if process_stat.exists():
        ticks = small(process_stat).decode().rsplit(') ',1)[1].split()[19]
        need(ticks != intake['parent_start'], 'Original outer PID/start is still live')
    return seal, report, stages


class HeaderReader:
    def __init__(self,data):
        self.data,self.at=data,0
    def byte(self):
        need(self.at < len(self.data), 'Header truncated')
        value=self.data[self.at];self.at+=1;return value
    def itf(self):
        first=self.byte()
        n=0 if first<128 else 1 if first<192 else 2 if first<224 else 3 if first<240 else 4
        value=first & (127 if n==0 else 63 if n==1 else 31 if n==2 else 15)
        for i in range(n):
            value=(value<<4)|(self.byte()&15) if i==3 else (value<<8)|self.byte()
        return value
    def ltf(self):
        first=self.byte();n=0
        while n<8 and first&(128>>n):n+=1
        value=0 if n>=7 else first&((1<<(7-n))-1)
        for _ in range(n):value=(value<<8)|self.byte()
        return value


def container(data):
    need(len(data)>=4,'No container length')
    r=HeaderReader(data);length=struct.unpack('<I',data[:4])[0];r.at=4
    ref=r.itf();ref=ref if ref<2**31 else ref-2**32
    start,span,records=r.itf(),r.itf(),r.itf()
    r.ltf();r.ltf();blocks,count=r.itf(),r.itf()
    need(count<=256 and 0<length<=512*MIB and 0<blocks<=1000000 and 0<records<2**31,'Invalid bounded header fields')
    landmarks=[r.itf() for _ in range(count)];crc_at=r.at
    need(crc_at+4<=len(data),'CRC truncated')
    stored=struct.unpack('<I',data[crc_at:crc_at+4])[0]
    need(zlib.crc32(data[:crc_at]) == stored,'Independent container CRC mismatch')
    return dict(length=length,ref=ref,start=start,span=span,records=records,bytes=crc_at+4,landmarks=landmarks)


def range_bytes(path,offset,count):
    global READ_BYTES,RANGE_BYTES
    need(0<=count<=65572 and READ_BYTES+count<=MAX_READ,'Bounded range budget')
    with Path(path).open('rb') as stream:
        stream.seek(offset);data=stream.read(count)
    READ_BYTES+=len(data);RANGE_BYTES+=len(data)
    need(len(data)==count,'Short retained range')
    return data


def tables(rows_pin):
    return list(csv.DictReader(io.StringIO(check(rows_pin).decode()),delimiter='\t'))


def main():
    handoff_pin=dict(path=str(HELPERS/'sample-source-view-runtime-handoff-v1.json'),size=34228,
                     sha256='34af15fa77af94810ecaaf9711881fc9348873d83923b2038a66c8e3cf0f2ec1')
    handoff=read(handoff_pin)
    REPORT['handoff']=handoff_pin
    need(handoff['complete'] is True and handoff['successful_phase_count']==6 and handoff['successful_stage_count']==10,'Handoff phase count')
    cut=read(handoff['source_cut']);freeze=read(handoff['core_freeze'])
    for value in cut['sources']+cut['unchanged_frozen_helpers']+freeze['sources']+[handoff['qualified_binary']]:check(value)
    need(len(freeze['sources'])==15,'Source freeze census')
    record=pin_for(ROOT/'scripts/record-command.sh')
    states={}
    for phase in handoff['phases']:
        states[phase['phase']]=phase_check(phase,record)
    need(len(COMMANDS)==16 and len(COMMANDS)*8==handoff['raw_receipt_count']==128,'Raw receipt count')
    REPORT['native_commands']=COMMANDS
    REPORT['phases']=[dict(phase=p['phase'],completion=p['completion'],outer=p['outer'],actual_parent_session_claim=p['actual_parent_session'],
                           historical_parent_closed_exit_claim=p['parent_closed_exit'],resources=p['resources'],caps=p['caps']) for p in handoff['phases']]
    reports={phase:state[1] for phase,state in states.items()}
    need(reports['assemble']['proof_unit']['completion']==handoff['phases'][0]['completion'],'Proof ancestry')
    need(reports['pilot']['assembly_unit']==reports['decode']['assembly_unit'],'New-input assembly ancestry')
    need(reports['packet']['decode_unit']['completion']==handoff['phases'][3]['completion'],'Full decode ancestry')
    need(reports['tables']['packet_unit']['completion']==handoff['phases'][4]['completion'],'Packet ancestry')
    proof=read(reports['framing-proof']['framing_proof']);pr=proof['result']
    need(pr['schema']=='sample-cram-framing/3' and pr['selected_headers_proven']==81 and pr['successor_headers_proven']==45,'Proof census')
    need(all(pr[k] is True for k in ('all_selected_header_framing_proven','independent_header_crc','crc_mutation_rejected','adjacency_control','gap_control','overlap_control','slice_metadata_raw_only')),'Native proof controls')
    view=read(handoff['source_view']);assembly=read(handoff['corrected_assembly'])
    need(view['derivative']==assembly['derivative']==handoff['corrected_derivative'] and len(view['pieces'])==317 and len(view['runs'])==45,'View binding/census')
    need(view['expected_bytes']==sum(p['length'] for p in view['pieces'])==259201887 and view['header_range']==[0,9144] and view['synthetic_bytes'] is False,'View byte accounting')
    prefix=read(handoff['exact_prefix_acquisition']['manifest'])
    need(len(prefix['prefixes'])==45 and prefix['payload_bytes']==prefix['cache_consumed_bytes']==2835 and prefix['cache_reserved_bytes']==2880,'Actual prefix census')
    need(all(prefix[k] is True for k in ('genuine_cached_receipt_reuse_control','expanded_range_rejected','wrong_controller_rejected')),'Actual prefix controls')
    original=read(prefix['original_assembly']);request=read(prefix['request']);plan=read(request['original_selected_plan'])
    spans=original['original_parts']+[dict(range=row['range'],payload=row['payload']) for row in prefix['prefixes']]
    spans.sort(key=lambda p:p['range'][0]);begins=[p['range'][0] for p in spans]
    for i,p in enumerate(spans):
        a,b=p['range'];need(Path(p['payload']['path']).stat().st_size==b-a==p['payload']['size'],'Span current size')
        need(i==0 or spans[i-1]['range'][1]<=a,'Span overlap')
    for row in prefix['prefixes']:check(row['payload'],force=True)
    def virtual(position,count):
        output=bytearray()
        while len(output)<count:
            i=bisect.bisect_right(begins,position)-1
            need(i>=0 and position<spans[i]['range'][1],'Virtual gap')
            p=spans[i];a,b=p['range'];n=min(count-len(output),b-position)
            output.extend(range_bytes(p['payload']['path'],position-a,n));position+=n
        return bytes(output)
    observations=pr['observations'];seen=set();selected=successors=0;mutation_rejected=False
    for observation in observations:
        position=observation['physical_start'];need(position not in seen,'Repeated proof boundary');seen.add(position)
        raw=virtual(position,observation['header_bytes']);header=container(raw)
        need(header['bytes']==observation['header_bytes'] and header['length']==observation['body_bytes']
             and position+header['bytes']+header['length']==observation['physical_end']
             and header['records']==observation['records_declared'] and header['ref']==observation['container_ref_id']
             and header['start']==observation['container_start'] and header['span']==observation['container_span'],'Independent header metadata differs')
        selected+=observation['role']=='selected';successors+=observation['role']=='successor'
        if not mutation_rejected:
            bad=bytearray(raw);bad[-1]^=1
            try:container(bad)
            except AssertionError as error:mutation_rejected=str(error)=='Independent container CRC mismatch'
        for row in observation['slice_headers']:
            need(row['slice_start_offset'] in header['landmarks'] and row['physical_slice_position']==position+header['bytes']+row['slice_start_offset'],'Slice landmark operand')
            need(row['method']=='RAW' and row['metadata_bytes']<=65536 and row['native_slice_crc_valid'] is True,'RAW metadata scope')
            if row['coordinate_status']=='exact_match':need((row['actual_ref_id'],row['actual_start'],row['actual_span'])==(row['expected_ref_id'],row['expected_start'],row['expected_span']),'Slice coordinate match')
            else:need(row['coordinate_status']=='multi_reference_not_row_comparable' and row['actual_ref_id']==-2,'Multi-reference status')
    need(selected==81 and successors==45 and mutation_rejected,'Independent bounded CRC census/control')
    REPORT['independent_headers']=dict(selected=selected,successors=successors,crc_mutation_rejected=mutation_rejected,bytes_read=RANGE_BYTES,
                                       scope='actual container header bytes only; no record/block-body decoding or whole-chunk hash')
    for run in view['runs']:
        begin,end=run['original_range'];need(run['physical_range']==[begin-63,end-63] and run['omitted_unselected_successor_tail']==[end-63,end],'Run finite view')
        cursor=begin-63
        for p in run['pieces']:
            a,b=p['source_range'];need(a==cursor and b-a==p['length'],'Run piece gap/length');cursor=b
        need(cursor==end-63,'Run piece end')
    need(reports['decode']['sam']==handoff['native_full_SAM'],'Full native SAM binding')
    check(handoff['native_full_SAM']);check(handoff['corrected_derivative'])
    packets={role:read(pin) for role,pin in reports['packet']['packets'].items()}
    roles_summary={}
    for role,declared in handoff['roles'].items():
        complete=read(declared['producers']['completion']);result=read(declared['producers']['result']);packet=packets[role]
        need(result==declared['result'] and complete['result']==declared['producers']['result'],'Role result binding')
        need(packet['sam']==handoff['native_full_SAM'] and packet['assembly']==handoff['corrected_assembly'],'Role native source binding')
        need(complete['inputs']==[packet['cases'],packet['sam']],'Table actual input binding')
        attempt=read(complete['attempt']);need(attempt['binary']==handoff['qualified_binary'],'Qualified native binary')
        for pin in complete['files']:check(pin)
        data={Path(pin['path']).name:tables(pin) for pin in complete['files']}
        census=data['cases.tsv'];contexts=data['contexts.tsv'];families=data['families.tsv'];lineage=data['lineage.tsv'];observations=data['observations.tsv'];excluded=data['excluded.tsv']
        packet_lines=check(packet['cases']).decode().splitlines();packet_rows=[r.split('\t') for r in packet_lines]
        need(packet_rows[0][0:2]==['SCHEMA','sample-context-cases/2'],'Packet schema')
        need(packet_rows[0][2:6]==[result['source_cases_sha256'],result['lineage_contract_sha256'],result['reference_proof_sha256'],result['assembly_proof_sha256']],'Result provenance')
        target={r[1] for r in packet_rows if r[0]=='TARGET'};excluded_names={r[1] for r in packet_rows if r[0]=='EXCLUDE'}
        groups={r[1] for r in packet_rows if r[0]=='RG'}
        inputs={r[1]:r for r in packet_rows if r[0]=='CASE'}
        need(len(target)==64 and len(excluded_names)==64 and len(groups)==1 and len(inputs)==len(census)==368,'Packet/table case census')
        need(sum(r[0]=='SQ' for r in packet_rows)==195,'Packet SQ census')
        plan_cases={r['id']:r for r in plan['cases']}
        windows={}
        for case_id,r in inputs.items():
            pc=plan_cases[case_id]
            need([r[2],r[3],r[4],*map(int,r[5:9]),r[9],r[10],r[12]]==[pc['parent'],pc['contig'],pc['strand'],pc['ref_begin'],pc['ref_end'],pc['core_begin'],pc['core_end'],pc['left'],pc['right'],pc['geometry']],'Plan/packet geometry')
            need(len(r[9])==10 and len(r[10])==20 and r[11]=='10' and r[14]=='covered','Native guard/coverage')
            a,b,c,d=map(int,r[5:9]);need(c-a==(20 if r[4]=='-' else 10) and b-d==(10 if r[4]=='-' else 20),'Oriented geometry')
            need(len(r[13])==b-a and set(r[13])<=set('ACGTN'),'Reference fragment length')
            windows[case_id]=digest(('sample-physical-window/1\t'+'\t'.join(r[3:11])+'\n').encode())
        need(len(set(windows.values()))==342,'Physical window census')
        by_read={r['read_id']:r for r in lineage};need(len(by_read)==len(lineage)==5309,'Lineage unique read census')
        need(all(r['dx']=='0' and r['read_group'] in groups for r in lineage),'Observed dx/RG')
        parent_census=collections.Counter(r['parent_absent_seen'] for r in lineage)
        need(parent_census=={'1':5262,'0':47},'Parent absence census')
        expected_paths=collections.defaultdict(lambda:collections.defaultdict(set))
        observation_votes=collections.defaultdict(lambda:dict(reads=set(),seqs=set()))
        for obs in observations:
            node=by_read[obs['read_id']]
            family_id=digest((RUN+'\n'+node['family_root']+'\n').encode())
            need(obs['family_sha256']==family_id and obs['physical_window_sha256'] in set(windows.values()),'Observation lineage/window')
            if obs['status']=='resolved':
                key=(obs['physical_window_sha256'],family_id);observation_votes[key]['reads'].add(obs['read_id']);observation_votes[key]['seqs'].add(obs['sequence_sha256'])
        family_keys=set()
        for family in families:
            key=(family['physical_window_sha256'],family['family_sha256']);need(key not in family_keys,'Duplicate family-window vote');family_keys.add(key)
            need(key in observation_votes,'Family lacks actual resolved observation')
            vote=observation_votes[key];names=json.loads(family['read_ids_json'])
            need(len(names)==len(set(names)) and set(names)==vote['reads'],'Family read provenance')
            need(family['family_sha256']==digest((RUN+'\n'+family['family_root']+'\n').encode()),'Family root digest')
            need(all(by_read[name]['family_root']==family['family_root'] for name in names),'Family lineage root')
            need(family['status']==('resolved' if len(vote['seqs'])==1 else 'conflicting_family'),'Family conflict handling')
            if family['status']=='resolved':
                need(family['sequence_sha256']==next(iter(vote['seqs'])),'Family sequence digest')
                expected_paths[key[0]][family['sequence_sha256']].add(key[1])
        need(family_keys==set(observation_votes),'Observation/family vote coverage')
        context_by_case=collections.defaultdict(list)
        for context in contexts:
            case_id=context['case_id'];need(case_id in inputs,'Unexpected context case')
            need(context['geometry_sha256']==inputs[case_id][12] and context['physical_window_sha256']==windows[case_id],'Context geometry/digest')
            need(digest(context['sequence'].encode())==context['sequence_sha256'] and len(context['sequence'])<=4096 and set(context['sequence'])<=set('ACGT'),'Context sequence/digest')
            ids=context['family_sha256s'].split(',') if context['family_sha256s'] else []
            need(len(ids)==len(set(ids))==int(context['family_count']) and set(ids)==expected_paths[windows[case_id]][context['sequence_sha256']],'Context family vote aggregation')
            need(context['context_role']==role and context['strict_read_level_qualified']=='0' and context['promotion_eligible']=='0','Context role flags')
            context_by_case[case_id].append(context)
        for case in census:
            case_id=case['case_id'];paths=context_by_case[case_id]
            need(case['geometry_sha256']==inputs[case_id][12] and case['physical_window_sha256']==windows[case_id] and case['coverage']=='covered','Case geometry/coverage')
            need(int(case['paths'])==len(paths)==len(expected_paths[windows[case_id]]) and int(case['families'])==sum(int(p['family_count']) for p in paths),'Case path/family census')
            need(case['context_role']==role and case['strict_read_level_qualified']=='0','Case role')
        need(len(contexts)==result['path_rows'] and sum(int(c['paths'])>0 for c in census)==result['available_cases'],'Final available/path result')
        need(result['cases']==368 and result['physical_windows']==342 and result['supporting_names']==5309 and result['supporting_records']==5309,'Result census')
        need(all(result[k] is False for k in ('strict_read_level_qualified','consumer_ready','promotion_eligible','biological_qualification','independent_donor_confirmation','probability_weights_emitted')),'Qualification flags')
        need(result['minimum_base_quality']==10 and result['minimum_mapping_quality']==30,'Quality policy')
        statuses=collections.Counter(c['status'] for c in census)
        actual_excluded={r['reason']:int(r['observations']) for r in excluded}
        if role=='strict':
            need(not contexts and not families and not observations and statuses=={'producer_lineage_unqualified':368},'Strict usable context')
            need(all(r['status']=='producer_lineage_unqualified' and r['family_root']=='' for r in lineage),'Strict lineage unavailable')
            need(actual_excluded=={'mapping_quality':372,'producer_lineage_unqualified':4937},'Strict exclusion census')
        else:
            need(len(contexts)==789 and len(families)==13179 and statuses=={'exploratory_available':356,'no_resolved_support':12},'Exploratory census')
            need(all(r['status']=='resolved' for r in lineage) and len({r['family_root'] for r in lineage})==5300,'Exploratory lineage roots')
            for name,node in by_read.items():
                ancestry=json.loads(node['known_ancestry_json']);current=name;walk=[]
                while True:
                    need(current not in walk and len(walk)<64,'Lineage cycle/depth');walk.append(current)
                    need(current not in target|excluded_names,'Target-connected lineage')
                    if current not in by_read or by_read[current]['parent_id']=='.':break
                    current=by_read[current]['parent_id']
                need(walk==ancestry and current==node['family_root'],'Reported lineage walk differs')
                parents=json.loads(node['observed_parent_ids_json'])
                need(parents==([] if node['parent_id']=='.' else [node['parent_id']]),'Observed pi edges')
            obs_reasons=collections.Counter(r['status'] for r in observations if r['status']!='resolved')
            need(actual_excluded==dict(obs_reasons,mapping_quality=372),'Exploratory nonadditive exclusion observations')
            need(result['exploratory_consumer_ready'] is True and result['assumption_tag']=='published_protocol_pi_dx_preservation_v1','Exploratory opt-in declaration')
        roles_summary[role]=dict(cases=len(census),physical_windows=len(set(windows.values())),available_cases=result['available_cases'],
                                context_rows=len(contexts),family_window_votes=len(families),lineage_names=len(lineage),
                                statuses=dict(statuses),exclusion_observations=actual_excluded,independence_qualified=False)
    REPORT['roles']=roles_summary
    bad_context=dict(handoff['roles']['exploratory_published_protocol']['files'][0],sha256='0'*64)
    try:check(bad_context)
    except AssertionError as error:need(str(error).startswith('Hash differs:'),'Unexpected negative failure')
    else:raise AssertionError('Corrupted table hash accepted')
    REPORT['negative_controls']=dict(actual_header_crc_mutation_rejected=True,wrong_table_hash_rejected=True)
    REPORT['verdict']='PASS_EVIDENCE_FOR_EXPLORATORY_SOURCE_ONLY'
    REPORT['limits']=['No native/product parser or producer replay; no large SAM/derivative/reference rehash.',
                      'Full SAM record count and actual filter inputs remain qualified-producer/source-counter evidence.',
                      'Bounded independent header CRC does not requalify full chunks, DNA blocks or whole source object.',
                      'Published pi/dx preservation and definitive physical-read independence remain unqualified.',
                      'No GT/VCF, truth, accuracy, feedback effect, donor confirmation, training or speed claim.',
                      'Runtime libraries are retained ldd pins, not actual loaded mappings.',
                      'Parent tool-session CLOSED0 claims come from coordinator handoff; retained OS-parent start identities and terminal cgroups were independently checked.']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);args=parser.parse_args()
    path=REVIEWS/('sample-source-view-runtime-final-'+args.attempt+'.json')
    need(not path.exists(),'Fresh audit attempt evidence required')
    try:
        main()
    except BaseException:
        REPORT['verdict']='AUDIT_OBSERVATION_FAILED'
        REPORT['failure']=traceback.format_exc()
        raise
    finally:
        REPORT.update(audit_source=pin_for(__file__),read_bytes=READ_BYTES,bounded_range_bytes=RANGE_BYTES,
                      fully_independently_hashed=list(CHECKED.values()),producer_hash_current_size_only=list(SKIPPED.values()),
                      observed_utc=datetime.now(timezone.utc).isoformat(),read_budget=MAX_READ,per_file_full_read_limit=MAX_FILE,
                      product_imported=False,native_executed=False,network=False,GT_VCF_truth_opened=False)
        with path.open('x') as stream:json.dump(REPORT,stream,indent=2,sort_keys=True);stream.write('\n')
        print(json.dumps(dict(verdict=REPORT['verdict'],evidence=str(path),read_bytes=READ_BYTES,bounded_range_bytes=RANGE_BYTES)))
