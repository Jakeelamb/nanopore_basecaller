#!/usr/bin/env python3
"""Run source-bound CPU units for the context-feedback research program."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import signal
import shutil
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'tools/context_decoder/study'
CONFIG = ROOT / 'config/context-program-v1.json'
spec = importlib.util.spec_from_file_location('program_execution_primitives', ROOT / 'scripts/context-feedback.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
c = w.c
PHASES = ('qualify', 'prepare', 'evaluate', 'controller-control')


def sources():
    entries = c.read(STUDY / 'source-files.json')
    c.require(isinstance(entries, list) and entries, 'Study source census is empty')
    paths = [(Path(p) if Path(p).is_absolute() else STUDY / p).resolve(strict=True) for p in entries]
    c.require(len(paths) == len(set(paths)) and all(p.is_relative_to(ROOT) for p in paths), 'Study source census has duplicates or foreign files')
    c.require(Path(__file__).resolve() in paths and (STUDY/'source-files.json') in paths, 'Controller/census missing from source closure')
    return [c.pin(p) for p in sorted(paths)]


def identity(pins):
    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def packet_boundary():
    spec = importlib.util.spec_from_file_location('program_packet_boundary', ROOT/'tools/context_decoder/program_inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configuration(path):
    value = c.read(path)
    c.require(set(value) == {'schema','role','baseline','scopes','python_test_count','execution'}
              and value['schema'] == 'context-program-config/1' and value['role'] == 'development', 'Unknown program configuration')
    c.require(set(value['baseline']) == {'root','source_inventory_sha256'}, 'Unknown baseline field')
    c.require(value['baseline']['root'] == '/home/jake/Projects/nanopore_basecaller-context-feedback-v2'
              and value['baseline']['source_inventory_sha256'] == '7a1b9c6f05597dd70e5eb96c894c2ed9e0cf811c28cc7735354fa1aed1f0164b', 'Frozen control source differs')
    c.require(value['scopes'] == ['query0','first32','all'] and type(value['python_test_count']) is int
              and value['python_test_count'] > 0, 'Program scope/test census differs')
    c.require(value['execution'] == dict(canonical_lock=str(w.LOCK),maximum_wall_seconds=300,cpu_quota=2,
              memory_bytes=4*1024**3,address_space_bytes=8*1024**3,swap_bytes=0,
              maximum_output_bytes=4*1024**3,disk_floor_bytes=30*1024**3), 'Program resource policy differs')
    return value


def grant(args, now=None):
    value = c.read(args.admission)
    required = {'schema','id','phase','scope','config','sources_sha256','output','qualification','prepared',
                'not_before_utc','expires_utc','maximum_wall_seconds','maximum_output_bytes','memory_bytes',
                'address_space_bytes','swap_bytes','cpu_quota','cgroup'}
    c.require(set(value) == required and value['schema'] == 'context-program-admission/1', 'Program admission schema differs')
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value['id']) is not None, 'Unsafe program unit identity')
    c.require(value['phase'] == args.phase and value['scope'] == args.scope and value['config'] == c.pin(args.config)
              and value['sources_sha256'] == identity(sources()) and value['output'] == str(args.output.resolve()), 'Program source/input/output admission differs')
    for key in ('qualification','prepared'):
        path = getattr(args,key)
        c.require(value[key] == (None if path is None else c.pin(path.resolve()/'execution-complete.json')), 'Program prerequisite admission differs')
    current = now or datetime.now(timezone.utc)
    start,end = (datetime.fromisoformat(value[k]) for k in ('not_before_utc','expires_utc'))
    c.require(start <= current < end and 5 < (end-current).total_seconds() <= 300
              and 0 < (end-start).total_seconds() <= 300 and 0 < value['maximum_wall_seconds'] <= 300, 'Program unit is expired/unbounded')
    c.require(0 < value['cpu_quota'] <= 2 and 0 < value['memory_bytes'] <= 4*1024**3
              and 0 < value['address_space_bytes'] <= 8*1024**3 and value['swap_bytes'] == 0
              and 0 < value['maximum_output_bytes'] <= 4*1024**3, 'Program CPU grant exceeds its policy')
    expected = '/user.slice/user-1000.slice/user@1000.service/app.slice/context-program-'+value['id']+'.service'
    c.require(value['cgroup'] == expected and args.output.resolve().is_relative_to(w.RESULTS), 'Wrong program cgroup/output root')
    configuration(args.config)
    return value


def native(directory, producer, expected_sources):
    directory = Path(directory)
    completion = c.read(producer['raw']['stdout']['path'])['completion']
    c.check(completion)
    c.require(completion['path'] == str(directory.resolve()/'complete.json'), 'Native completion path differs')
    seal = c.read(completion['path'])
    c.require(seal['complete'] is True, 'Native unit is incomplete')
    for item in [seal['attempt'],seal['result'],*seal['files'],*seal.get('inputs',[])]:
        c.check(item)
    attempt = c.read(directory/'attempt.json')
    c.require(attempt['argv'] == producer['argv'], 'Native attempt command differs')
    c.require(attempt['binary'] == c.pin(producer['argv'][0]), 'Native executable identity differs')
    c.require({p['path']:p for p in attempt['source']['compiled_sources']} == {p['path']:p for p in expected_sources}, 'Native compiled source closure differs')
    return completion


def completed(directory, phase, visited=None):
    directory = Path(directory).resolve()
    seen = set() if visited is None else set(visited)
    c.require(directory not in seen and len(seen) < 4, 'Cyclic or excessive program ancestry')
    seen.add(directory)
    outer = c.read(directory/'execution-complete.json')
    c.require(outer['complete'] is True and outer['phase'] == phase and outer['whole_worker_cgroup_terminal'] is True, 'Program outer completion differs')
    for item in outer['files']:
        c.check(item)
    c.check(outer['terminal'])
    terminal = c.read(outer['terminal']['path'])
    c.require(terminal['error'] is None and terminal['exit'] == 0 and terminal['owned_cgroup_terminal'] is True, 'Program outer service failed')
    proof = terminal['proof']
    properties = proof.get('unloaded_empty_group',proof)['properties']
    c.require(properties.get('Result') == 'success' and properties.get('ActiveState') == 'inactive', 'Program terminal result is not successful')
    intake = c.read(outer['worker_intake']['path'])
    c.require(intake['verified'] is True, 'Program worker intake is not verified')
    c.check(outer['worker'])
    worker = c.read(outer['worker']['path'])
    c.require(worker['complete'] is True and worker['phase'] == phase
              and worker['sources_sha256'] == identity(sources()), 'Program worker source/phase differs')
    for item in worker['files']:
        c.check(item)
    summary = c.read(directory/'summary.json')
    for stage in summary['stages']:
        w.evidence.stage(stage,c)
    for dependency in worker['prerequisites']:
        c.check(dependency['outer'])
        completed(Path(dependency['outer']['path']).parent,dependency['phase'],seen)
    for name,item in summary.get('binaries',{}).items():
        c.check(item)
        c.require(name in ('atlas','infer'),'Unknown native artifact')
    if phase == 'qualify':
        closure = c.read(directory/'build-closure.json')
        for key in ('compiler','cache','compile_commands'):
            c.check(closure[key])
        for item in closure['runtime_libraries']:
            c.check(item)
        c.require(closure['runtime_libraries'], 'No runtime library closure')
    for item in summary.get('native',{}).values():
        c.check(item)
        target = Path(item['path']).parent
        seal = c.read(item['path'])
        attempt = c.read(target/'attempt.json')
        producers = [w.evidence.stage(pin,c) for pin in summary['stages'] if c.read(pin['path'])['argv'] == attempt['argv']]
        c.require(len(producers) == 1, 'Native command lacks one linked producer')
        native(target,producers[0],sources())
    if phase == 'prepare':
        packet_boundary().verify_prepared(summary['prepared'],c,summary['stages'])
    return dict(phase=phase,outer=c.pin(directory/'execution-complete.json'),summary=summary)


def build_closure(output, execution, binaries):
    cache = output/'build/CMakeCache.txt'
    compiler = next(line.split('=',1)[1] for line in cache.read_text().splitlines() if line.startswith('CMAKE_CXX_COMPILER:FILEPATH='))
    commands = output/'build/compile_commands.json'
    flags = ('-std=c++23','-Werror','-Wconversion','-Wsign-conversion','-Wshadow','-fno-fast-math','-ffp-contract=off')
    for row in c.read(commands):
        argv = row.get('arguments') or shlex.split(row['command'])
        c.require(all(flag in argv for flag in flags) and '-ffast-math' not in argv, 'Actual C++ compilation flags differ')
    libraries = {}
    for name,binary in binaries.items():
        linked = execution.stage('program-linked-'+name,['ldd',binary['path']])
        for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
            match = re.search(r'(?:=>\s+)?(/[^\s]+)\s+\(',line)
            if match:
                item = c.pin(match.group(1));libraries[item['path']] = item
    c.fresh(output/'build-closure.json',dict(compiler=c.pin(compiler),cache=c.pin(cache),compile_commands=c.pin(commands),
             runtime_libraries=list(libraries.values()),binaries=binaries))


def worker(args):
    value = grant(args)
    w.pg.adopt_orphans()
    w.supervisor.worker_intake(args.worker_intake,value,c)
    w.cgroup_limits(value)
    output = args.output.resolve()
    output.mkdir()
    pins = sources()
    c.fresh(output/'start.json',dict(phase=args.phase,scope=args.scope,config=c.pin(args.config),grant=c.pin(args.admission),sources=pins))
    execution = w.Execution(value,output,pins)
    config = configuration(args.config)
    dependencies,binaries,observations = [],{},{}
    prepared = None
    if args.phase == 'controller-control':
        pid = os.fork()
        if pid == 0:
            os.setsid()
            signal.signal(signal.SIGTERM,signal.SIG_IGN)
            c.fresh(output/'child-ready.json',dict(pid=os.getpid(),start=w.supervisor.process_start(os.getpid()),ignores_term=True,separate_session=True))
            time.sleep(30)
            os._exit(0)
        deadline = time.monotonic()+2
        while not (output/'child-ready.json').exists() and time.monotonic()<deadline:
            time.sleep(.02)
        c.require((output/'child-ready.json').exists(), 'Control child did not become ready')
        c.fresh(output/'parent-ready.json',dict(pid=os.getpid(),child=pid))
        time.sleep(30)
        raise ValueError('Hard supervisor did not stop the control')
    if args.phase == 'qualify':
        strict = '-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off'
        execution.stage('program-cmake-configure',['cmake','-S',STUDY,'-B',output/'build','-DCMAKE_BUILD_TYPE=Release',
            '-DBUILD_TESTING=ON','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DCMAKE_CXX_FLAGS='+strict])
        execution.stage('program-cmake-build',['cmake','--build',output/'build','--parallel','2'])
        execution.stage('program-format-check',['cmake','--build',output/'build','--target','format-check','--parallel','1'])
        execution.stage('program-ctest',['ctest','--test-dir',output/'build','--output-on-failure','--parallel','1'])
        binaries = dict(atlas=c.pin(output/'build/context-atlas'),infer=c.pin(output/'build/context-infer'))
        stage = execution.stage('program-native-controls',[binaries['atlas']['path'],'qualify','--output',output/'native-controls'])
        observations['controls'] = native(output/'native-controls',stage,pins)
        result = execution.stage('program-python-controls',['uv','run','--no-sync','python','-m','unittest',
            'test_context_program_inputs','test_context_program','-v'],
            env=dict(PYTHONPATH=str(ROOT/'tests'),CONTEXT_ATLAS_BINARY=binaries['atlas']['path'],CONTEXT_INFER_BINARY=binaries['infer']['path'],CONTEXT_PROGRAM_INFER_BINARY=binaries['infer']['path']))
        evidence = Path(result['raw']['stderr']['path']).read_text()
        count = config['python_test_count']
        c.require('Ran '+str(count)+' tests' in evidence and 'skipped' not in evidence.lower()
                  and evidence.count(' ... ok\n') == count, 'Program Python controls did not all execute with skipped0')
        build_closure(output,execution,binaries)
    else:
        c.require(args.qualification is not None, 'Successful program qualification is required')
        prior = completed(args.qualification,'qualify')
        dependencies.append(dict(phase='qualify',outer=prior['outer']))
        binaries = prior['summary']['binaries']
        if args.phase == 'prepare':
            prepared = packet_boundary().prepare(output/'prepared',execution,args.scope)
        else:
            c.require(args.prepared is not None, 'Successful prepared packet required')
            packet = completed(args.prepared,'prepare')
            dependencies.append(dict(phase='prepare',outer=packet['outer']))
            c.require(packet['summary']['scope'] == args.scope, 'Prepared packet scope differs from priced evaluation')
            prepared = packet['summary']['prepared']
            for tool,verb in (('infer','replay'),('atlas','evaluate')):
                target = output/('native-'+tool)
                argv = [binaries[tool]['path'],verb,'--cases',prepared['cases']['path'],
                        '--cases-sha256',prepared['cases']['sha256']]
                if tool == 'atlas':
                    argv += ['--truth',prepared['truth']['path'],'--truth-sha256',prepared['truth']['sha256']]
                argv += ['--output',target]
                stage = execution.stage('program-'+verb,argv)
                observations[tool] = native(target,stage,pins)
    execution.budget()
    summary = dict(phase=args.phase,scope=args.scope,binaries=binaries,sources=pins,stages=execution.receipts,native=observations)
    if prepared is not None:
        summary['prepared'] = prepared
    c.fresh(output/'summary.json',summary)
    files = [c.pin(output/name) for name in ('start.json','summary.json')]
    if args.phase == 'qualify':
        files.append(c.pin(output/'build-closure.json'))
    c.fresh(output/'complete.json',dict(schema='context-program-unit/1',complete=True,phase=args.phase,
            sources_sha256=identity(pins),files=files,prerequisites=dependencies))
    fd = os.open(output,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps(dict(completion=c.pin(output/'complete.json'))))


def supervise(args):
    value = grant(args)
    end = datetime.fromisoformat(value['expires_utc'])
    directory = w.LOGS/('program-supervisor-'+value['id'])
    directory.mkdir(parents=True)
    unit = 'context-program-'+value['id']+'.service'
    description = 'Context program '+uuid.uuid4().hex
    w.pg.adopt_orphans()
    with w.LOCK.open('r') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            c.fresh(directory/'refused.json',dict(reason='canonical lock held',grant=value))
            raise
        intake = directory/'intake.json'
        c.fresh(intake,dict(grant_id=value['id'],admission=str(args.admission.resolve()),parent_pid=os.getpid(),
                parent_start=w.supervisor.process_start(os.getpid()),lock_fd=lock.fileno(),unit=unit,description=description))
        remaining = min(value['maximum_wall_seconds'],(end-datetime.now(timezone.utc)).total_seconds())-3
        c.require(remaining>1,'No bounded program interval remains')
        argv = ['systemd-run','--user','--wait','--pipe','--unit='+unit,'--description='+description,
            '--working-directory='+str(ROOT),'--property=Type=exec','--property=ExitType=cgroup','--property=KillMode=control-group',
            '--property=Slice=app.slice','--property=CollectMode=inactive','--property=SendSIGKILL=yes','--property=FinalKillSignal=SIGKILL',
            '--property=TimeoutStopSec=1s','--property=RuntimeMaxSec='+str(remaining)+'s',
            '--property=CPUQuota='+str(value['cpu_quota']*100)+'%','--property=MemoryMax='+str(value['memory_bytes']),
            '--property=MemorySwapMax=0','--property=LimitAS='+str(value['address_space_bytes']),
            '--setenv=UV_PROJECT_ENVIRONMENT='+os.environ['UV_PROJECT_ENVIRONMENT'],'--',shutil.which('uv'),'run','--no-sync','python',
            str(Path(__file__).resolve()),args.phase,'--scope',args.scope,'--config',str(args.config.resolve()),
            '--output',str(args.output.resolve()),'--admission',str(args.admission.resolve()),'--worker-intake',str(intake)]
        for name in ('qualification','prepared'):
            path = getattr(args,name)
            if path is not None:
                argv += ['--'+name,str(path.resolve())]
        c.fresh(directory/'command.json',dict(argv=argv,grant=value,cwd=str(ROOT),utc=datetime.now(timezone.utc).isoformat()))
        process,error,proof = None,None,None
        try:
            with (directory/'stdout').open('xb') as out,(directory/'stderr').open('xb') as err:
                process = subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
                while process.poll() is None:
                    if time.time() >= end.timestamp()-1 or w.owned_bytes() > value['maximum_output_bytes'] or shutil.disk_usage(ROOT).free < 30*1024**3:
                        raise ValueError('Program wall/output/disk boundary reached')
                    time.sleep(.2)
        except BaseException as caught:
            error = repr(caught)
        finally:
            index = 0
            while proof is None:
                try:
                    observed = w.supervisor.show(unit)
                    if observed['properties'].get('Description') == description:
                        if w.supervisor.terminal(observed,value['cgroup']):
                            proof = observed
                            if observed['properties'].get('Result') != 'success':
                                error = error or 'Program service failed'
                        else:
                            subprocess.run(['systemctl','--user','stop','--no-block',unit],capture_output=True,timeout=3)
                    elif process is None or (process.poll() is not None and w.supervisor.unloaded_terminal(observed,value['cgroup'])):
                        proof = dict(unloaded_empty_group=observed)
                except BaseException as caught:
                    index += 1
                    c.fresh(directory/('termination-error-'+str(index)+'.json'),dict(error=repr(caught),canonical_lock_retained=True))
                if proof is None:
                    time.sleep(.2)
            if process is not None:
                while True:
                    try:
                        c.fresh(directory/'launcher-cleanup.json',w.pg.stop_group(process,process.pid))
                        break
                    except BaseException as caught:
                        index += 1
                        c.fresh(directory/('launcher-error-'+str(index)+'.json'),dict(error=repr(caught),canonical_lock_retained=True))
                        time.sleep(.2)
            c.fresh(directory/'terminal.json',dict(error=error,exit=None if process is None else process.returncode,
                     utc=datetime.now(timezone.utc).isoformat(),proof=proof,owned_cgroup_terminal=True,canonical_lock_retained=True))
        c.require(error is None and process is not None and process.returncode == 0, 'Program unit failed; retained '+str(directory))
        c.require(c.read(directory/'worker-intake.json')['verified'] is True, 'Missing program worker intake')
        result = c.read(directory/'stdout')['completion']
        c.check(result)
        c.require(result['path'] == str(args.output.resolve()/'complete.json'), 'Program worker completion path differs')
        seal = c.read(result['path'])
        c.require(seal['sources_sha256'] == identity(sources()) and seal['phase'] == args.phase and seal['complete'] is True,
                  'Program completion source/phase differs')
        for item in seal['files']:
            c.check(item)
        summary = c.read(args.output/'summary.json')
        for item in summary['stages']:
            w.evidence.stage(item,c)
        files = [c.pin(directory/name) for name in ('command.json','intake.json','worker-intake.json','stdout','stderr','launcher-cleanup.json')]
        c.fresh(args.output/'execution-complete.json',dict(schema='context-program-execution/1',complete=True,phase=args.phase,
            worker=result,worker_intake=c.pin(directory/'worker-intake.json'),terminal=c.pin(directory/'terminal.json'),
            files=files,whole_worker_cgroup_terminal=True))
        print(json.dumps(dict(completion=c.pin(args.output/'execution-complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=PHASES+('source-inventory',))
    parser.add_argument('--scope',choices=('query0','first32','all'),default='all')
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--admission',type=Path)
    parser.add_argument('--qualification',type=Path)
    parser.add_argument('--prepared',type=Path)
    parser.add_argument('--worker-intake',type=Path)
    args = parser.parse_args()
    if args.phase == 'source-inventory':
        pins = sources();print(json.dumps(dict(sources=pins,sha256=identity(pins))))
    else:
        c.require(args.output is not None and args.admission is not None,'Explicit fresh program unit required')
        if args.worker_intake is None:
            supervise(args)
        else:
            worker(args)


if __name__ == '__main__':
    main()
