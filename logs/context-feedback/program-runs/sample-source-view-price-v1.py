"""Price one source-view phase from actual successful parent metadata, without reading source DNA."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MIB = 1024**2
PREFIX = dict(completion=dict(path=str(ROOT / 'results/sample-context/sample-prefix-fetch-1/complete.json'), size=48541,
                             sha256='438189ae9b8535f7c8ffe05dcc5bad5a94d567cb727180738754224d0e834ddb'),
              outer=dict(path=str(HERE / 'run-sample-prefix-fetch-1/outer-evidence.json'), size=3911,
                         sha256='6e08769b2f69f6755e36b6bd14e8fcc73daabedf335c17bf763bbc5b6e8dc3e7'))
CAPS = {'framing-proof': 16, 'assemble': 320, 'pilot': 64, 'decode': 768, 'packet': 32, 'tables': 512}


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve(strict=True)
    need(path.stat().st_size <= MIB, 'Task builder reads only bounded metadata/source files')
    return dict(path=str(path), size=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def read(value):
    need(pin(value['path']) == value, 'Task-builder metadata pin differs')
    return json.loads(Path(value['path']).read_text())


def validate_outer(start, terminal, cleanup, worker, intake, active):
    properties = active['observation']['properties']
    need(start['worker'] == worker and start['controller'] == pin(HERE / 'run-sample-bounded-v2.py')
         and start['controller']['sha256'] == 'fe4cedf2e9341398972c68b55371720a832eb70ab7537e0b057b02d8804a6d5f'
         and terminal['exit'] == 0 and terminal['error'] is None and cleanup['terminal'] is True
         and terminal['proof']['properties']['ActiveState'] == 'inactive'
         and terminal['proof']['properties']['Result'] == 'success'
         and terminal['proof']['properties']['MainPID'] == '0'
         and terminal['proof']['properties']['ControlPID'] == '0'
         and terminal['proof']['properties']['ControlGroup'] == ''
         and active['verified'] is True and active['intake'] == start['intake']
         and active['parent_lock_retained'] is True and properties['ActiveState'] == 'active'
         and properties['ControlGroup'] == terminal['expected_cgroup'] == intake['cgroup']
         and properties['Description'] == intake['description']
         and properties['ExitType'] == 'cgroup' and properties['KillMode'] == 'control-group'
         and active['kernel']['cpu.max'] == '200000 100000'
         and active['kernel']['memory.max'] == '4294967296' and active['kernel']['memory.swap.max'] == '0'
         and active['rlimit_as'] == [8589934592, 8589934592], 'Actual successful source/controller/tree/live-caps metadata required')


def preview(value, phase):
    seal, outer = read(value['completion']), read(value['outer'])
    start, terminal = read(outer['start']), read(outer['terminal'])
    active, intake = read(seal['worker_intake']), read(start['intake'])
    worker = pin(HERE / ('sample-prefix-fetch-v1.py' if phase == 'prefix-acquisition' else 'sample-source-view-v1.py'))
    if phase == 'prefix-acquisition':
        need(value == PREFIX and worker['sha256'] == 'ecd605cfc71411864ba6edeeaf7f8cff7a5940fc50302d83c605cf4c2dfc63c1',
             'Exact actual prefix producer required')
    need(seal['schema'] == 'sample-context-unit/1' and seal['complete'] is True and seal['phase'] == phase
         and outer['projection_error'] is None, 'Successful actual parent phase required')
    validate_outer(start, terminal, read(outer['launcher_cleanup']), worker, intake, active)
    wrong = dict(start, controller=dict(start['controller'], sha256='0'*64))
    try:
        validate_outer(wrong, terminal, read(outer['launcher_cleanup']), worker, intake, active)
    except ValueError:
        pass
    else:
        raise ValueError('Wrong-controller source metadata was accepted')
    need(set(outer['raw']) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'},
         'Whole-worker raw receipt set missing')
    for raw in outer['raw'].values():
        need(pin(raw['path']) == raw, 'Actual whole-worker raw metadata changed')
    need(shlex.split(Path(outer['raw']['command.sh']['path']).read_text()) == start['worker_argv']
         and Path(outer['raw']['exit-status.txt']['path']).read_text().strip() == '0'
         and json.loads(Path(outer['raw']['stdout']['path']).read_text()) == dict(completion=value['completion']),
         'Actual whole-worker command/exit/completion binding differs')
    name = 'prefix-acquisition.json' if phase == 'prefix-acquisition' else 'native-report.json'
    report_pin = next(item for item in seal['files'] if Path(item['path']).name == name)
    report = read(report_pin)
    if phase == 'prefix-acquisition':
        need(report['request']['sha256'] == '1a02357cdffa843fecd4299374ef997f58abb4ce231b03d4cf9deee5eeabd9ff'
             and report['outcome']['sha256'] == 'c04be98126d5b4bf5256e91164307485217849a04c61a5343298a2a777982ca8'
             and report['payload_bytes'] == 2835 and len(report['prefixes']) == 45
             and report['cache_consumed_bytes'] == 2835 and report['cache_reserved_bytes'] == 2880
             and report['genuine_cached_receipt_reuse_control'] is True and report['expanded_range_rejected'] is True
             and report['wrong_controller_rejected'] is True, 'Actual prefix request/outcome/controls differ')
    else:
        need(report['phase'] == phase, 'Actual source-view report phase differs')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=list(CAPS))
    parser.add_argument('identity')
    parser.add_argument('--prior-completion', type=Path, required=True)
    parser.add_argument('--prior-outer', type=Path, required=True)
    args = parser.parse_args()
    need(Path.cwd().resolve() == ROOT and re.fullmatch('sample-[A-Za-z0-9_-]{1,64}', args.identity), 'Owned task identity/cwd required')
    worker = pin(HERE / 'sample-source-view-v1.py')
    prior = dict(completion=pin(args.prior_completion), outer=pin(args.prior_outer))
    required = {'framing-proof': 'prefix-acquisition', 'assemble': 'framing-proof', 'pilot': 'assemble',
                'decode': 'pilot', 'packet': 'decode', 'tables': 'packet'}[args.phase]
    report = preview(prior, required)
    task = dict(schema='sample-source-view-task/1', phase=args.phase)
    if args.phase == 'framing-proof':
        task['prefix_unit'] = prior
    elif args.phase == 'assemble':
        task.update(prefix_unit=report['prefix_unit'], proof_unit=prior)
    elif args.phase == 'pilot':
        task['assembly_unit'] = prior
    elif args.phase == 'decode':
        task.update(assembly_unit=report['assembly_unit'], pilot_unit=prior)
    elif args.phase == 'packet':
        task['decode_unit'] = prior
    else:
        task['packet_unit'] = prior
    task_path = HERE / (args.identity+'-task.json')
    with task_path.open('x') as stream:
        stream.write(json.dumps(task, indent=2)+'\n')
    task_pin = pin(task_path)
    price = dict(schema='sample-context-bounded-price/1', id=args.identity,
                 phase='engineering' if args.phase == 'framing-proof' else args.phase, worker=worker,
                 priced_new_bytes=CAPS[args.phase]*MIB, maximum_new_bytes=CAPS[args.phase]*MIB,
                 maximum_cumulative_bytes=2*1024**3, scientific_work=args.phase != 'framing-proof',
                 worker_arguments=['--task', str(task_path), '--task-sha256', task_pin['sha256']])
    price_path = HERE / (args.identity+'-price.json')
    with price_path.open('x') as stream:
        stream.write(json.dumps(price, indent=2)+'\n')
    price_pin = pin(price_path)
    print(json.dumps(dict(task=task_pin, price=price_pin, actual_parent_metadata_checked=True,
                         wrong_controller_metadata_rejected=True, payload_read=False, execution_admitted=False)))
    print('UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 '
          +shlex.join(['/home/jake/.local/bin/uv', 'run', '--no-sync', 'python', str(HERE / 'run-sample-bounded-v2.py'), str(price_path), '--price-sha256', price_pin['sha256']]))


if __name__ == '__main__':
    main()
