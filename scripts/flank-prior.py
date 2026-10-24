#!/usr/bin/env python3
"""Run declared CPU-only flank units under the canonical shared host lock."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('unit', choices=['build-test', 'checkpoint', 'eligibility', 'emit'])
    parser.add_argument('--plans', type=Path)
    parser.add_argument('--wait-lock-seconds', type=float, default=30)
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log = ROOT / 'logs/flank-prior' / f'{stamp}-{args.unit}'
    log.mkdir(parents=True)
    binary = ROOT / 'results/flank-prior/build/release/flank-prior'
    output = None
    if args.unit == 'build-test':
        commands = [['cargo', 'generate-lockfile', '--offline', '--manifest-path', 'tools/flank_prior/Cargo.toml'], ['cargo', 'test', '--offline', '--locked', '--manifest-path', 'tools/flank_prior/Cargo.toml'], ['cargo', 'build', '--release', '--offline', '--locked', '--manifest-path', 'tools/flank_prior/Cargo.toml'], ['uv','run','--no-sync','python','-m','unittest','discover','-s','tests','-p','test_flank_prior.py','-v'], ['cargo','clippy','--offline','--locked','--manifest-path','tools/flank_prior/Cargo.toml','--all-targets','--','-D','warnings']]
        seconds, rss = 180, 1024
    elif args.unit == 'emit':
        if args.plans is None:
            parser.error('--plans is required for emit')
        output = ROOT / 'results/flank-prior' / f'{stamp}-{args.unit}'
        commands = [[str(binary), 'emit', 'config/flank-prior-dev-v1.json', str(output), str(args.plans.resolve())]]
        seconds, rss = 600, 4096
    else:
        count = 32 if args.unit == 'checkpoint' else 451
        output = ROOT / 'results/flank-prior' / f'{stamp}-{args.unit}'
        commands = [[str(binary), 'diagnostic', 'config/flank-prior-dev-v1.json', str(output), str(count)]]
        seconds, rss = 60, 1024
    max_output_mib = 2048 if args.unit == 'emit' else 100
    receipt = {'schema': 'flank-prior-execution/1', 'unit': args.unit, 'cwd': str(ROOT), 'lock': str(LOCK), 'budget': {'cpus': 1, 'rss_mib': rss, 'seconds': seconds, 'output_mib':max_output_mib,'disk_floor_gib':30}, 'commands': commands, 'utc_start': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    frozen = log / 'frozen-source'
    for p in [*sorted((ROOT/'tools/flank_prior').rglob('*')),ROOT/'scripts/flank-prior.py',ROOT/'config/flank-prior-dev-v1.json']:
        if p.is_file() and 'target' not in p.parts:
            destination = frozen / p.relative_to(ROOT)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,destination)
    if shutil.disk_usage(ROOT).free < 30*1024**3:
        raise RuntimeError('30GiB disk floor')
    if args.unit != 'build-test':
        immutable_binary = log / 'flank-prior'
        shutil.copy2(binary, immutable_binary)
        binary = immutable_binary
        commands[0][0] = str(binary)
        receipt['binary_sha256_before'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (log/'start.json').write_text(json.dumps(receipt, indent=2)+'\n')
    with LOCK.open('a') as lock:
        start=time.monotonic()
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()-start >= args.wait_lock_seconds:
                    receipt.update(exit=75, reason='bounded host-lock wait exhausted')
                    (log/'finish.json').write_text(json.dumps(receipt, indent=2)+'\n')
                    return 75
                time.sleep(0.2)
        receipt['lock_acquired_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        env=os.environ.copy()
        env['CARGO_TARGET_DIR']=str(ROOT/'results/flank-prior/build')
        def limits():
            resource.setrlimit(resource.RLIMIT_AS,(rss*1024**2,rss*1024**2))
            resource.setrlimit(resource.RLIMIT_FSIZE,(max_output_mib*1024**2,max_output_mib*1024**2))
            resource.setrlimit(resource.RLIMIT_CPU,(seconds,seconds))
            os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
        statuses=[]
        for i,cmd in enumerate(commands):
            with (log/f'{i}.stdout').open('wb') as out, (log/f'{i}.stderr').open('wb') as err:
                try:
                    p=subprocess.Popen(['/usr/bin/time','-v','-o',str(log/f'{i}.time'),*cmd],cwd=ROOT,env=env,stdout=out,stderr=err,preexec_fn=limits,start_new_session=True)
                    code=p.wait(timeout=seconds)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGTERM)
                    try:
                        p.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        os.killpg(p.pid, signal.SIGKILL)
                        p.wait()
                    code=124
            statuses.append(code)
            if code:break
        receipt.update(exit=statuses[-1],statuses=statuses,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat())
        receipt['source_pins']=[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'tools/flank_prior').rglob('*')) if p.is_file() and 'target' not in p.parts]
        (log/'finish.json').write_text(json.dumps(receipt,indent=2)+'\n')
        def pin(p):
            return {'path':str(p.resolve()),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        if output is not None and statuses[-1] == 0:
            if sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) > max_output_mib*1024**2:
                raise RuntimeError('aggregate output budget exceeded')
            if hashlib.sha256(binary.read_bytes()).hexdigest() != receipt['binary_sha256_before']:
                raise RuntimeError('binary changed during execution')
            stdout_attestation = json.loads((log/'0.stdout').read_text())
            if stdout_attestation['completion'] != pin(output/'complete.json') or stdout_attestation['summary'] != pin(output/'summary.json'):
                raise RuntimeError('raw producer stdout does not bind the complete output')
            seal={'schema':'flank-prior-execution-completion/1','complete':True,'producer':pin(log/'finish.json'),'raw_stdout':pin(log/'0.stdout'),'raw_stderr':pin(log/'0.stderr'),'time':pin(log/'0.time'),'binary':pin(binary),'producer_completion':pin(output/'complete.json'),'files':[pin(p) for p in sorted(output.iterdir()) if p.is_file()]}
            (output/'execution-complete.json').write_text(json.dumps(seal,indent=2)+'\n')
        print(json.dumps({'log':str(log),'exit':statuses[-1]}))
        return statuses[-1]


if __name__ == '__main__':
    raise SystemExit(run())
