#!/usr/bin/env python3
"""Bind original retained exports and collect sealed uncertainty scan parts."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
UNIT = Path(__file__).resolve().parent
ORIGINAL = Path('/home/jake/Projects/nanopore_basecaller-reference/scripts/frontier-proposals.py')
ORIGINAL_SHA256 = 'a0a8e645f52e38b36d911e6d64cfc1769d95bc6e988e18c30ca341d0be6906c2'
REGISTRY = ORIGINAL.parent.parent/'results/graph-prior/pilot-v1/development/artifacts/native-call.json'
REGISTRY_SHA256 = 'f8470d591314a24e95ec594c5334d4969e0336be95115b644509da18e5543adf'
MODEL_CONFIG = Path('/home/jake/Projects/nanopore_basecaller/models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0/config.toml')
MODEL_CONFIG_SHA256 = 'e550ccbedb68ed74d6ee88e2f510adf33c52a1c868bd5e3a2bfbb7dfe6154c3f'
RAW_FILES = ('command.sh','cwd.txt','start.txt','end.txt','exit-status.txt','stdout','stderr','time.txt')
ENGINEERING_STAGES = tuple('uncertainty-'+name for name in
                           ('cmake-configure','cmake-build','format','ctest','native-controls','runtime-libraries','python-controls'))
STRICT_FLAGS = ('-Wall','-Wextra','-Wpedantic','-Wconversion','-Wsign-conversion','-Wshadow','-Werror',
                '-fno-fast-math','-ffp-contract=off','-std=c++23')
BOUNDARY_CONTROL_COUNT = 16


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            digest.update(block)
    return dict(path=str(path), size=path.stat().st_size, sha256=digest.hexdigest())


def check(value):
    require(pin(value['path']) == value, 'Missing or changed consumed file: '+value['path'])
    return value


def read(path):
    return json.loads(Path(path).read_text())


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sources():
    paths = [(UNIT/name).resolve(strict=True) for name in read(UNIT/'source-files.json')]
    require(len(paths) == len(set(paths)) and all(path.is_relative_to(ROOT) for path in paths), 'Source census duplicates/foreign paths')
    return [pin(path) for path in sorted(paths)]


def source_identity(items):
    return hashlib.sha256(''.join(item['path']+'\t'+str(item['size'])+'\t'+item['sha256']+'\n' for item in items).encode()).hexdigest()


def sync_directory(path):
    descriptor = os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fresh(path, value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    sync_directory(Path(path).parent)


def original():
    require(pin(ORIGINAL)['sha256'] == ORIGINAL_SHA256, 'Original auditor source changed')
    value = load('uncertainty_original_auditor',ORIGINAL)
    require(value.ROOT == ORIGINAL.parent.parent and Path(value.__file__).resolve() == ORIGINAL, 'Original auditor relocated')
    return value


def native_metadata(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        pair = line.split('\t')
        require(len(pair) == 2 and pair[0] not in result, 'Malformed/duplicate native metadata')
        result[pair[0]] = pair[1]
    return result


def output_directory(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT/'results/context-feedback') and not path.exists(), 'Fresh owned output required')
    path.mkdir(parents=True)
    sync_directory(path.parent)
    return path


def prepare(output):
    owned = sources()
    fresh(output/'attempt.json',dict(schema='uncertainty-preparation-attempt/1',argv=sys.argv,sources=owned,
          utc=datetime.now(timezone.utc).isoformat(),offline_completed_chunk_development=True))
    auditor = original()
    proof = auditor.qualify_original()
    require(proof['role'] == 'development' and len(proof['parent_ids']) == 64
            and proof['score_verification'].startswith('registered producer hashes'), 'Original export qualification differs')
    registry = pin(REGISTRY); model = pin(MODEL_CONFIG)
    require(registry['sha256'] == REGISTRY_SHA256 and model['sha256'] == MODEL_CONFIG_SHA256, 'Registered export/model identity changed')
    declared = {item['path']:item for item in read(REGISTRY)['pins']}
    require(len(declared) == 3179 and list(declared.values()) == proof['export_declarations'], 'Original export declaration census differs')
    parents, chunks, evidence = {},[],{}
    for item in declared.values():
        path = Path(item['path'])
        require(path.parent == Path(proof['export']) and path.is_file() and not path.is_symlink()
                and path.stat().st_size == item['size'], 'Original export shape differs')
        if path.suffix == '.scores':
            continue
        check(item); evidence[item['path']] = item
        if path.name.endswith('.parent.tsv'):
            meta = native_metadata(path)
            require(meta['format'] == 'DGP1' and meta['read_id'] not in parents, 'Duplicate/malformed DGP parent')
            parents[meta['read_id']] = item
        elif path.name.endswith('.scores.meta.tsv'):
            meta = native_metadata(path)
            require(meta['format'] == 'DGM1', 'Foreign chunk metadata')
            score = declared.get(str(path.with_name(meta['score_file'])))
            require(score is not None and meta['C'] == '1024' and meta['model_path'] == str(MODEL_CONFIG.parent), 'Foreign score/model binding')
            chunks.append(dict(id=meta['read_id']+'/'+str(int(meta['chunk_index'])),parent=meta['read_id'],
                          index=int(meta['chunk_index']),count=int(meta['chunk_count']),T=int(meta['T']),score=score,metadata=item))
    require(set(parents) == set(proof['parent_ids']) and len(chunks) == 1557, 'Complete parent/chunk census differs')
    chunks.sort(key=lambda row:(row['parent'],row['index']))
    for parent in parents:
        group = [row for row in chunks if row['parent'] == parent]
        count = int(native_metadata(parents[parent]['path'])['chunk_count'])
        require([row['index'] for row in group] == list(range(count)) and all(row['count'] == count for row in group), 'Declared chunk indices incomplete')
    fresh(output/'original-qualification.json',proof)
    proof_pin = pin(output/'original-qualification.json')
    for item in [registry,model,pin(ORIGINAL),proof['aligned_sam'],proof['parents'],proof['report'],*proof['receipts'],proof_pin]:
        check(item); evidence[item['path']] = item
    def fields(item):
        return [item['path'],str(item['size']),item['sha256']]
    records = [['uncertainty-inputs/1','development',proof_pin['sha256']]]
    records += [['SOURCE',*fields(item)] for item in sorted(evidence.values(),key=lambda value:value['path'])]
    records += [['ALIGN',*fields(proof['aligned_sam'])]]
    records += [['PARENT',parent,*fields(parents[parent])] for parent in sorted(parents)]
    records += [['CHUNK',row['id'],row['parent'],str(row['index']),*fields(row['score']),*fields(row['metadata'])] for row in chunks]
    with (output/'inputs.tsv').open('x') as stream:
        for record in records:
            require(not any(any(c in value for c in '\t\r\n') for value in record), 'Manifest separator in field')
            stream.write('\t'.join(record)+'\n')
        stream.flush(); os.fsync(stream.fileno())
    for item in owned:
        check(item)
    fresh(output/'complete.json',dict(schema='uncertainty-preparation/1',complete=True,sources=owned,source_id=source_identity(owned),
          manifest=pin(output/'inputs.tsv'),original=proof_pin,original_auditor=pin(ORIGINAL),files=[pin(output/'attempt.json'),pin(output/'inputs.tsv'),proof_pin],
          parents=64,chunks=1557,score_payloads_hashed_or_parsed=False,score_hashes_are_registered_original=True,
          native_state_length=4,blank_score=2.0,posterior_initial_state='uniform',posterior_final_state='unrestricted',
          selection_uses_truth=False,biological_qualification=False))
    return pin(output/'complete.json')


def prepared(completion):
    check(completion)
    seal = read(completion['path'])
    require(seal['schema'] == 'uncertainty-preparation/1' and seal['complete'] is True
            and seal['sources'] == sources() and seal['source_id'] == source_identity(sources())
            and seal['parents'] == 64 and seal['chunks'] == 1557, 'Prepared source/census differs')
    require(len(seal['files']) == 3 and {item['path'] for item in seal['files']} ==
            {str(Path(completion['path']).parent/name) for name in ('attempt.json','inputs.tsv','original-qualification.json')}, 'Prepared file census differs')
    members = {item['path']:item for item in seal['files']}
    require(seal['manifest']['path'] == str(Path(completion['path']).parent/'inputs.tsv')
            and seal['original']['path'] == str(Path(completion['path']).parent/'original-qualification.json')
            and members[seal['manifest']['path']] == seal['manifest'] and members[seal['original']['path']] == seal['original']
            and seal['original_auditor']['path'] == str(ORIGINAL)
            and seal['original_auditor']['sha256'] == ORIGINAL_SHA256, 'Prepared links differ')
    for item in seal['files']:
        check(item)
    check(seal['manifest']); check(seal['original']); check(seal['original_auditor'])
    require(read(seal['original']['path']) == original().qualify_original(), 'Original qualification ancestry changed')
    return seal


def raw_receipt(directory, argv, root):
    directory = Path(directory).resolve(strict=True)
    require(directory.is_relative_to(root/'logs/context-feedback/recorder-root/logs'), 'Outer recorder location differs')
    result = {name:pin(directory/name) for name in RAW_FILES}
    require(shlex.split((directory/'command.sh').read_text()) == argv, 'Outer recorded command differs')
    require((directory/'cwd.txt').read_text().strip() == str(root), 'Outer recorder cwd differs')
    require((directory/'exit-status.txt').read_text().strip() == '0', 'Outer recorder exit failed')
    start,end = ((directory/name).read_text().strip() for name in ('start.txt','end.txt'))
    require(start.endswith('Z') and end.endswith('Z') and datetime.fromisoformat(start) <= datetime.fromisoformat(end), 'Outer recorder clocks invalid')
    times = {}
    for line in (directory/'time.txt').read_text().splitlines():
        if line.startswith('\t') and ': ' in line:
            key,value = line.strip().split(': ',1); times[key] = value
    require(times.get('Exit status') == '0' and times.get('Command being timed') == '"'+' '.join(argv)+'"', 'Outer GNU time command/exit differs')
    numeric = [float(times[key]) for key in ('User time (seconds)','System time (seconds)')]
    wall = times['Elapsed (wall clock) time (h:mm:ss or m:ss)'].split(':')
    require(all(math.isfinite(value) and value >= 0 for value in numeric)
            and int(times['Maximum resident set size (kbytes)']) > 0
            and len(wall) in (2,3) and all(math.isfinite(float(value)) and float(value) >= 0 for value in wall), 'Outer time/RSS evidence incomplete')
    return result


def outer_unit(completion, worker, root):
    identity = worker['admission_id']
    require(identity and all(char.isalnum() or char in '-_' for char in identity), 'Invalid unit identity')
    directory = root/'logs/context-feedback/program-runs'/('run-'+identity)
    pins = {name:pin(directory/name) for name in ('start.json','terminal.json','cleanup.json','stdout')}
    start,terminal,cleanup = (read(pins[name]['path']) for name in ('start.json','terminal.json','cleanup.json'))
    require(terminal['error'] is None and terminal['exit'] == 0 and cleanup['terminal'] is True, 'Outer launcher not successful terminal')
    proof = terminal['proof'].get('unloaded_empty_group',terminal['proof'])
    properties = proof['properties']
    require(properties['Result'] == 'success' and properties['ActiveState'] == 'inactive'
            and properties['MainPID'] == properties['ControlPID'] == '0'
            and properties['ControlGroup'] == '', 'Outer cgroup not empty terminal')
    require(start['cwd'] == str(root) and start['worker'] == worker['driver'], 'Outer worker source/cwd differs')
    for key in ('worker','controller','recorder'):
        check(start[key])
    command = start['argv']; at = command.index('--')
    require(command[0] == 'systemd-run' and '--wait' in command[:at] and '--pipe' in command[:at]
            and '--property=KillMode=control-group' in command[:at]
            and '--property=ExitType=cgroup' in command[:at]
            and '--working-directory='+str(root) in command[:at], 'Outer service boundary differs')
    recorder = root/'logs/context-feedback/recorder-root/scripts/record-command.sh'
    require(command[at+1] == str(recorder) and start['recorder'] == pin(recorder)
            and command[at+2] == identity and command[at+3:]
            and worker['driver']['path'] in command[at+3:], 'Outer exact recorder/worker command differs')
    require(start['caps']['cpu'] == 2 and start['caps']['memory'] == 4*1024**3
            and start['caps']['address_space'] == 8*1024**3 and start['caps']['swap'] == 0
            and 0 < start['caps']['wall_seconds'] <= 300
            and 0 < start['caps']['maximum_output_bytes'] <= 100*1024**2, 'Outer declared caps differ')
    require(all(option in command[:at] for option in ('--property=CPUQuota=200%',
            '--property=MemoryMax=4294967296','--property=MemorySwapMax=0',
            '--property=LimitAS=8589934592','--property=TimeoutStopSec=1s')),
            'Outer actual service caps differ')
    runtime = [value.removeprefix('--property=RuntimeMaxSec=') for value in command[:at]
               if value.startswith('--property=RuntimeMaxSec=')]
    require(len(runtime) == 1 and runtime[0].endswith('s')
            and 0 < float(runtime[0][:-1]) <= start['caps']['wall_seconds']-1, 'Outer actual wall bound differs')
    raw = raw_receipt(Path(Path(pins['stdout']['path']).read_text().strip()),command[at+3:],root)
    require(read(raw['stdout']['path']) == dict(completion=completion), 'Outer stdout does not bind worker completion')
    return [*pins.values(),*raw.values(),start['worker'],start['controller'],start['recorder']]


def native_completion(completion, producer, worker):
    check(completion)
    native = read(completion['path'])
    require(native['schema'] == 'uncertainty-native-complete/1' and native['complete'] is True
            and native['source_id'] == worker['source_id'], 'Native source/completion differs')
    for item in [native['attempt'],native['result'],*native['files'],*native['inputs']]:
        check(item)
    attempt = read(native['attempt']['path'])
    require(attempt['schema'] == 'uncertainty-native-attempt/1' and attempt['argv'] == producer['argv']
            and attempt['binary'] == worker['binary'] and native['source'] == attempt['source']
            and attempt['source']['compiled_sources'] == worker['sources']
            and producer['argv'][0] == worker['binary']['path']
            and read(producer['raw']['stdout']['path']) == dict(completion=completion), 'Native binary/source/producer link differs')
    return native,attempt


def cache_value(cache, key, accepted_types):
    entries = [line for line in cache.splitlines()
               if line.startswith(key+':') or line.startswith(key+'=')]
    require(len(entries) == 1, 'Actual CMake '+key+' entry missing/duplicated')
    match = re.fullmatch(re.escape(key)+r':([^=]+)=(.*)',entries[0])
    require(match is not None and match[1] in accepted_types, 'Actual CMake '+key+' cache type differs')
    return match[2]


def worker_unit(completion, phase, expected_sources, root=ROOT):
    check(completion); worker = read(completion['path'])
    require(worker['schema'] == 'uncertainty-worker/1' and worker['complete'] is True
            and worker['phase'] == phase and worker['sources'] == expected_sources
            and worker['source_id'] == source_identity(expected_sources), 'Worker source/phase differs')
    check(worker['driver']); check(worker['binary'])
    proofs = [completion,*outer_unit(completion,worker,root)]
    boundary = SimpleNamespace(ROOT=root,check=check,read=read,require=require,pin=pin)
    evidence = load('uncertainty_stage_evidence',UNIT.parent/'context_decoder/evidence.py')
    require(worker['stages'] and len({item['path'] for item in worker['stages']}) == len(worker['stages']), 'Worker stages missing/duplicated')
    stages = [evidence.stage(item,boundary) for item in worker['stages']]
    require(all(stage['admission_id'] == worker['admission_id'] for stage in stages), 'Stage admission does not bind worker')
    for stage in stages:
        check(stage['recorder_source'])
        require(stage['recorder_source'] == pin(root/'logs/context-feedback/recorder-root/scripts/record-command.sh'), 'Stage recorder source differs')
    producers = [stage for stage in stages if stage['argv'][:2] == [worker['binary']['path'],'qualify' if phase == 'engineering' else 'scan']]
    require(len(producers) == 1, 'Exact native producer missing/duplicated')
    native,attempt = native_completion(worker['native'],producers[0],worker)
    require(native['command'] == ('qualify' if phase == 'engineering' else 'scan'), 'Native phase differs')
    if phase == 'engineering':
        require(tuple(stage['name'] for stage in stages) == ENGINEERING_STAGES, 'Engineering stage census differs')
        check(worker['build_closure']); closure = read(worker['build_closure']['path'])
        require(closure['binary'] == worker['binary'] and closure['compiled_sources'] == expected_sources
                and closure['runtime_libraries'], 'Engineering binary/runtime closure missing')
        for item in [closure['compiler'],closure['cache'],closure['compile_commands'],*closure['runtime_libraries']]:
            check(item)
        require(closure['compiler']['path'] == attempt['source']['compiler_path']
                or closure['compiler']['path'] == str(Path(attempt['source']['compiler_path']).resolve()), 'Engineering compiler location differs')
        require(closure['compiler']['sha256'] == attempt['source']['compiler_sha256'], 'Engineering compiler hash differs')
        commands = read(closure['compile_commands']['path'])
        expected_cpp = {item['path'] for item in expected_sources if item['path'].endswith('.cpp')}
        require(isinstance(commands,list) and {str(Path(row['file']).resolve()) for row in commands} == expected_cpp, 'Actual compiled translation-unit census differs')
        for row in commands:
            args = row.get('arguments') or shlex.split(row['command'])
            require(all(flag in args for flag in STRICT_FLAGS)
                    and not any(flag in args for flag in ('-ffast-math','-Ofast','-ffp-contract=fast'))
                    and not any(flag.startswith(('-Wno-','-funsafe-math','-ffinite-math'))
                                or (flag.startswith('-std=') and flag != '-std=c++23') for flag in args)
                    and str(Path(args[0]).resolve()) == closure['compiler']['path'], 'Actual strict compiler command differs')
        cache = Path(closure['cache']['path']).read_text()
        require(cache_value(cache,'CMAKE_CXX_COMPILER',('STRING','FILEPATH')) == attempt['source']['compiler_path'],
                'Actual CMake compiler path differs')
        require(cache_value(cache,'CMAKE_BUILD_TYPE',('STRING',)) == 'Release', 'Actual CMake build type differs')
        require(closure['runtime_producer'] in worker['stages'], 'Runtime library producer missing')
        runtime = stages[worker['stages'].index(closure['runtime_producer'])]
        check(closure['runtime_tool'])
        require(runtime['name'] == 'uncertainty-runtime-libraries'
                and runtime['argv'] == [closure['runtime_tool']['path'],worker['binary']['path']], 'Actual runtime command differs')
        libraries = set()
        for line in Path(runtime['raw']['stdout']['path']).read_text().splitlines():
            require('not found' not in line, 'Unresolved actual runtime library')
            match = re.fullmatch(r'\s*(?:\S+ => )?(/\S+) \(0x[0-9a-fA-F]+\)\s*',line)
            require(match is not None or re.fullmatch(r'\s*linux-vdso\.so\.\d+ \(0x[0-9a-fA-F]+\)\s*',line) is not None, 'Unknown actual runtime-library line')
            if match:
                libraries.add(str(Path(match[1]).resolve(strict=True)))
        require(libraries == {item['path'] for item in closure['runtime_libraries']}
                and len(libraries) == len(closure['runtime_libraries']), 'Actual resolved runtime library census differs')
        controls = stages[-1]
        require(read(controls['raw']['stdout']['path']) == dict(controls=BOUNDARY_CONTROL_COUNT,failed=0,skipped=0,synthetic_only=True),
                'Python boundary controls not'+str(BOUNDARY_CONTROL_COUNT)+' passed skipped0')
        proofs += [worker['build_closure'],closure['compiler'],closure['cache'],closure['compile_commands'],closure['runtime_tool'],*closure['runtime_libraries']]
    proofs += worker['stages']+[worker['native']]
    return worker,stages,native,proofs


def scan_unit(record, expected_sources, manifest, root=ROOT):
    require(set(record) == {'completion','receipt','unit','engineering'}, 'Unknown scan admission field')
    qualified,_,_,proofs = worker_unit(record['engineering'],'engineering',expected_sources,root)
    worker,stages,native,scan_proofs = worker_unit(record['unit'],'scan',expected_sources,root)
    require(worker['engineering'] == record['engineering'] and worker['binary'] == qualified['binary']
            and worker['native'] == record['completion'] and record['receipt'] in worker['stages'], 'Scan differs from qualified unit/binary')
    producer = stages[worker['stages'].index(record['receipt'])]
    require(producer['argv'][:2] == [worker['binary']['path'],'scan'], 'Selected stage is not the scan producer')
    require(manifest in native['inputs'], 'Native scan consumed another manifest')
    return native,proofs+scan_proofs


def boundary_controls():
    class Controls(unittest.TestCase):
        def setUp(self):
            self.temporary = tempfile.TemporaryDirectory(prefix='uncertainty-boundary-')
            self.root = Path(self.temporary.name)
            self.expected = sources()
            self.workers = {}
            self.recorder = self.write(self.root/'logs/context-feedback/recorder-root/scripts/record-command.sh','synthetic recorder\n')
            self.binary = self.write(self.root/'build/context-uncertainty','synthetic binary\n')
            self.compiler = self.write(self.root/'compiler','synthetic compiler\n')
            self.library = self.write(self.root/'libfixture.so','synthetic library\n')
            self.manifest = self.write(self.root/'inputs.tsv','synthetic manifest\n')
            self.engineering = self.unit('engineering',ENGINEERING_STAGES)
            self.scan = self.unit('scan',('uncertainty-scan',))

        def tearDown(self):
            self.temporary.cleanup()

        def write(self,path,value):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(value if isinstance(value,str) else json.dumps(value))
            return pin(path)

        def raw(self,identity,argv,stdout):
            directory = self.root/'logs/context-feedback/recorder-root/logs'/identity
            fields = {'command.sh':shlex.join(argv),'cwd.txt':str(self.root),
                      'start.txt':'2026-01-01T00:00:00Z','end.txt':'2026-01-01T00:00:01Z',
                      'exit-status.txt':'0','stdout':stdout,'stderr':'',
                      'time.txt':'\tCommand being timed: "'+' '.join(argv)+'"\n\tExit status: 0\n'
                      '\tUser time (seconds): 0\n\tSystem time (seconds): 0\n'
                      '\tMaximum resident set size (kbytes): 1\n\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:01\n'}
            return {name:self.write(directory/name,value) for name,value in fields.items()}

        def stage(self,identity,name,argv,stdout):
            directory = self.root/'stages'/identity/name
            raw = self.raw(identity+'-'+name,argv,stdout)
            terminal = self.write(directory/'terminal.json',dict(exit=0,failure=None,argv=argv))
            cleanup = self.write(directory/'cleanup.json',dict(terminal=True))
            return self.write(directory/'finish.json',dict(schema='context-feedback-stage/1',name=name,
                admission_id=identity,argv=argv,exit=0,failure=None,projection_error=None,missing_raw=[],
                terminal=terminal,group_cleanup=cleanup,raw=raw,recorder_source=self.recorder))

        def unit(self,phase,names):
            identity = 'synthetic-'+phase
            directory = self.root/'results'/identity
            driver = self.write(directory/'worker.py','synthetic worker source\n')
            source = dict(compiled_sources=self.expected,compiler_path=self.compiler['path'],
                          compiler_sha256=self.compiler['sha256'])
            command = 'qualify' if phase == 'engineering' else 'scan'
            argv = [self.binary['path'],command,'--output',str(directory/'native')]
            attempt = self.write(directory/'native/attempt.json',dict(schema='uncertainty-native-attempt/1',
                    argv=argv,binary=self.binary,source=source))
            result = self.write(directory/'native/result.json',dict(synthetic_only=True))
            native = self.write(directory/'native/complete.json',dict(schema='uncertainty-native-complete/1',
                    complete=True,source_id=source_identity(self.expected),command=command,source=source,
                    attempt=attempt,result=result,files=[],inputs=[] if phase == 'engineering' else [self.manifest]))
            stages = []
            for name in names:
                stage_argv,stdout = ['/synthetic/'+name],''
                if name.endswith('native-controls') or phase == 'scan':
                    stage_argv,stdout = argv,dict(completion=native)
                elif name.endswith('runtime-libraries'):
                    self.runtime_tool = self.write(self.root/'ldd','synthetic runtime tool\n')
                    stage_argv,stdout = [self.runtime_tool['path'],self.binary['path']],self.library['path']+' (0x01)\n'
                elif name.endswith('python-controls'):
                    stdout = dict(controls=BOUNDARY_CONTROL_COUNT,failed=0,skipped=0,synthetic_only=True)
                stages.append(self.stage(identity,name,stage_argv,stdout))
            worker = dict(schema='uncertainty-worker/1',complete=True,phase=phase,admission_id=identity,
                sources=self.expected,source_id=source_identity(self.expected),driver=driver,binary=self.binary,
                native=native,stages=stages)
            if phase == 'engineering':
                commands = [dict(file=item['path'],arguments=[self.compiler['path'],*STRICT_FLAGS,'-c',item['path']])
                            for item in self.expected if item['path'].endswith('.cpp')]
                closure = dict(binary=self.binary,compiled_sources=self.expected,compiler=self.compiler,
                    cache=self.write(directory/'CMakeCache.txt','CMAKE_CXX_COMPILER:STRING='+self.compiler['path']+'\nCMAKE_BUILD_TYPE:STRING=Release\n'),
                    compile_commands=self.write(directory/'compile_commands.json',commands),
                    runtime_tool=self.runtime_tool,runtime_producer=stages[-2],runtime_libraries=[self.library])
                worker['build_closure'] = self.write(directory/'build-closure.json',closure)
            else:
                worker['engineering'] = self.engineering
            self.workers[phase] = worker
            return self.resign(phase)

        def resign(self,phase):
            worker = self.workers[phase]; identity = worker['admission_id']
            completion = self.write(self.root/'results'/identity/'complete.json',worker)
            directory = self.root/'logs/context-feedback/program-runs'/('run-'+identity)
            controller = self.write(directory/'controller.py','synthetic controller\n')
            argv = ['systemd-run','--wait','--pipe','--working-directory='+str(self.root),
                    '--property=KillMode=control-group','--property=ExitType=cgroup',
                    '--property=CPUQuota=200%','--property=MemoryMax=4294967296',
                    '--property=MemorySwapMax=0','--property=LimitAS=8589934592',
                    '--property=RuntimeMaxSec=290s','--property=TimeoutStopSec=1s','--',
                    self.recorder['path'],identity,'/synthetic/python',worker['driver']['path']]
            self.write(directory/'start.json',dict(argv=argv,cwd=str(self.root),worker=worker['driver'],
                controller=controller,recorder=self.recorder,caps=dict(cpu=2,memory=4*1024**3,
                address_space=8*1024**3,swap=0,wall_seconds=300,maximum_output_bytes=100*1024**2)))
            self.write(directory/'terminal.json',dict(error=None,exit=0,proof=dict(properties=dict(
                Result='success',ActiveState='inactive',MainPID='0',ControlPID='0',ControlGroup=''))))
            self.write(directory/'cleanup.json',dict(terminal=True))
            raw = self.raw(identity,argv[argv.index('--')+3:],dict(completion=completion))
            self.write(directory/'stdout',str(Path(raw['stdout']['path']).parent))
            return completion

        def validate(self):
            stages = self.workers['scan']['stages']
            record = dict(completion=self.workers['scan']['native'],receipt=stages[0] if stages else self.scan,
                          unit=self.scan,engineering=self.engineering)
            return scan_unit(record,self.expected,self.manifest,self.root)

        def test_complete_synthetic_chain(self):
            self.assertEqual(self.validate()[0]['command'],'scan')

        def replace_cache(self,compiler_entries=None,build_entries=None):
            compiler_entries = ['CMAKE_CXX_COMPILER:STRING='+self.compiler['path']] if compiler_entries is None else compiler_entries
            build_entries = ['CMAKE_BUILD_TYPE:STRING=Release'] if build_entries is None else build_entries
            worker = self.workers['engineering']; closure = read(worker['build_closure']['path'])
            closure['cache'] = self.write(Path(closure['cache']['path']),'\n'.join(compiler_entries+build_entries)+'\n')
            worker['build_closure'] = self.write(Path(worker['build_closure']['path']),closure)
            self.engineering = self.resign('engineering')
            self.workers['scan']['engineering'] = self.engineering
            self.scan = self.resign('scan')

        def test_filepath_cache_chain(self):
            self.replace_cache(compiler_entries=['CMAKE_CXX_COMPILER:FILEPATH='+self.compiler['path']])
            self.assertEqual(self.validate()[0]['command'],'scan')

        def test_wrong_compiler_cache_type(self):
            self.replace_cache(compiler_entries=['CMAKE_CXX_COMPILER:BOOL='+self.compiler['path']])
            with self.assertRaisesRegex(ValueError,'CMAKE_CXX_COMPILER cache type differs'):
                self.validate()

        def test_wrong_compiler_cache_path(self):
            self.replace_cache(compiler_entries=['CMAKE_CXX_COMPILER:STRING=/unrelated/compiler'])
            with self.assertRaisesRegex(ValueError,'Actual CMake compiler path differs'):
                self.validate()

        def test_duplicate_compiler_cache_entry(self):
            self.replace_cache(compiler_entries=['CMAKE_CXX_COMPILER:STRING='+self.compiler['path'],
                                                'CMAKE_CXX_COMPILER:FILEPATH='+self.compiler['path']])
            with self.assertRaisesRegex(ValueError,'CMAKE_CXX_COMPILER entry missing/duplicated'):
                self.validate()

        def test_missing_compiler_cache_entry(self):
            self.replace_cache(compiler_entries=[])
            with self.assertRaisesRegex(ValueError,'CMAKE_CXX_COMPILER entry missing/duplicated'):
                self.validate()

        def test_duplicate_build_cache_entry(self):
            self.replace_cache(build_entries=['CMAKE_BUILD_TYPE:STRING=Release','CMAKE_BUILD_TYPE:STRING=Release'])
            with self.assertRaisesRegex(ValueError,'CMAKE_BUILD_TYPE entry missing/duplicated'):
                self.validate()

        def test_missing_build_cache_entry(self):
            self.replace_cache(build_entries=[])
            with self.assertRaisesRegex(ValueError,'CMAKE_BUILD_TYPE entry missing/duplicated'):
                self.validate()

        def test_wrong_build_cache_type(self):
            self.replace_cache(build_entries=['CMAKE_BUILD_TYPE:BOOL=Release'])
            with self.assertRaisesRegex(ValueError,'CMAKE_BUILD_TYPE cache type differs'):
                self.validate()

        def test_wrong_build_cache_value(self):
            self.replace_cache(build_entries=['CMAKE_BUILD_TYPE:STRING=Debug'])
            with self.assertRaisesRegex(ValueError,'Actual CMake build type differs'):
                self.validate()

        def test_swapped_format_outer(self):
            self.write(self.root/'logs/context-feedback/recorder-root/logs/synthetic-scan/stdout',dict(completion=self.engineering))
            with self.assertRaisesRegex(ValueError,'Outer stdout does not bind'):
                self.validate()

        def test_missing_scan_stage(self):
            self.workers['scan']['stages'] = []; self.scan = self.resign('scan')
            with self.assertRaisesRegex(ValueError,'Worker stages missing'):
                self.validate()

        def test_missing_runtime_census(self):
            worker = self.workers['engineering']; closure = read(worker['build_closure']['path'])
            closure['runtime_libraries'] = []
            worker['build_closure'] = self.write(Path(worker['build_closure']['path']),closure)
            self.engineering = self.resign('engineering')
            with self.assertRaisesRegex(ValueError,'Engineering binary/runtime closure missing'):
                self.validate()

        def test_missing_binary(self):
            Path(self.binary['path']).unlink()
            with self.assertRaises(FileNotFoundError):
                self.validate()

        def test_wrong_stage_admission(self):
            worker = self.workers['scan']; stage = read(worker['stages'][0]['path'])
            stage['admission_id'] = 'unrelated-format'
            worker['stages'][0] = self.write(Path(worker['stages'][0]['path']),stage)
            self.scan = self.resign('scan')
            with self.assertRaisesRegex(ValueError,'Stage admission does not bind'):
                self.validate()

        def test_missing_runtime_file(self):
            Path(self.library['path']).unlink()
            with self.assertRaises(FileNotFoundError):
                self.validate()

    result = unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    require(result.wasSuccessful() and result.testsRun == BOUNDARY_CONTROL_COUNT and not result.skipped, 'Boundary controls failed/skipped')
    return dict(controls=result.testsRun,failed=len(result.failures)+len(result.errors),skipped=len(result.skipped),synthetic_only=True)


def collect(output, completion, scans_pin):
    seal = prepared(completion); check(scans_pin)
    records = read(scans_pin['path'])
    require(isinstance(records,list) and records, 'No native scan records')
    lines = [['uncertainty-parts/1',seal['manifest']['sha256'],seal['source_id']]]
    seen = set(); proofs = []
    for record in records:
        native,unit_proofs = scan_unit(record,seal['sources'],seal['manifest'])
        files = {Path(item['path']).name:item for item in native['files']}
        require(set(files) == {'chunks.tsv','proposals.tsv'}, 'Scan output file census differs')
        rows = Path(files['chunks.tsv']['path']).read_text().splitlines()
        require(rows[0] == '\t'.join(['uncertainty-chunks/1',seal['manifest']['sha256'],seal['source_id']]), 'Scan chunk header differs')
        for line in rows[1:]:
            identity = line.split('\t')[0]
            require(identity not in seen, 'Repeated successful chunk; resume without producer replay')
            seen.add(identity)
        lines.append(['PART',*[str(value) for key in ('chunks.tsv','proposals.tsv') for value in (files[key]['path'],files[key]['size'],files[key]['sha256'])],
                      record['completion']['path'],str(record['completion']['size']),record['completion']['sha256']])
        proofs.extend(unit_proofs)
    require(len(seen) == 1557, 'Complete global nomination requires all1557 scanned chunks')
    with (output/'parts.tsv').open('x') as stream:
        stream.write(''.join('\t'.join(row)+'\n' for row in lines));stream.flush();os.fsync(stream.fileno())
    fresh(output/'complete.json',dict(schema='uncertainty-collected-parts/1',complete=True,prepared=completion,scans=scans_pin,
          sources=sources(),parts=pin(output/'parts.tsv'),native_proofs=proofs,qualified_chunks=len(seen),files=[pin(output/'parts.tsv')],biological_qualification=False))
    return pin(output/'complete.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','collect','controls','verify-unit'))
    parser.add_argument('--output',type=Path)
    parser.add_argument('--prepared',type=Path);parser.add_argument('--prepared-sha256')
    parser.add_argument('--scans',type=Path);parser.add_argument('--scans-sha256')
    args = parser.parse_args()
    if args.phase == 'controls':
        print(json.dumps(boundary_controls()));return
    require(args.output is not None, 'Fresh output required')
    output = output_directory(args.output)
    if args.phase == 'prepare':
        result = prepare(output)
    else:
        require(args.prepared is not None and args.prepared_sha256 is not None and args.scans is not None and args.scans_sha256 is not None, 'Pinned preparation/scans required')
        completed = pin(args.prepared);scans = pin(args.scans)
        require(completed['sha256'] == args.prepared_sha256 and scans['sha256'] == args.scans_sha256, 'Coordinator input pin differs')
        if args.phase == 'verify-unit':
            seal = prepared(completed);check(scans)
            records = read(scans['path'])
            require(isinstance(records,list) and len(records) == 1, 'One genuine scan unit required')
            native,proofs = scan_unit(records[0],seal['sources'],seal['manifest'])
            fresh(output/'complete.json',dict(schema='uncertainty-unit-verification/1',complete=True,
                  prepared=completed,scans=scans,native=records[0]['completion'],proofs=proofs,
                  command=native['command'],biological_qualification=False))
            result = pin(output/'complete.json')
        else:
            result = collect(output,completed,scans)
    print(json.dumps(dict(completion=result)))


if __name__ == '__main__':
    main()
