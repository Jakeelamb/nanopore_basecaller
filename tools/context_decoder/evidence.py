from datetime import datetime
from pathlib import Path
import shlex


def stage(pin, boundary):
    boundary.check(pin)
    value = boundary.read(pin['path'])
    boundary.require(value['schema'] == 'context-feedback-stage/1' and value['exit'] == 0
                     and value['failure'] is None and value['projection_error'] is None,
                     'Linked stage did not finish successfully')
    boundary.check(value['terminal'])
    observed = boundary.read(value['terminal']['path'])
    boundary.require(observed['exit'] == 0 and observed['failure'] is None and observed['argv'] == value['argv'],
                     'Durable stage observation differs')
    boundary.check(value['group_cleanup'])
    boundary.require(boundary.read(value['group_cleanup']['path'])['terminal'] is True, 'Linked process group is not terminal')
    raw = value['raw']
    required = {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}
    boundary.require(set(raw) == required and not value['missing_raw'], 'Missing linked raw recorder evidence')
    for item in raw.values():
        boundary.check(item)
    boundary.require(shlex.split(Path(raw['command.sh']['path']).read_text()) == value['argv']
                     and Path(raw['exit-status.txt']['path']).read_text().strip() == '0', 'Linked native command/exit differs')
    boundary.require(Path(raw['cwd.txt']['path']).read_text().strip() == str(boundary.ROOT), 'Linked native cwd differs')
    start = Path(raw['start.txt']['path']).read_text().strip()
    end = Path(raw['end.txt']['path']).read_text().strip()
    boundary.require(start.endswith('Z') and end.endswith('Z')
                     and datetime.fromisoformat(start) <= datetime.fromisoformat(end), 'Linked raw clocks invalid')
    times = {}
    for line in Path(raw['time.txt']['path']).read_text().splitlines():
        if line.startswith('\t') and ': ' in line:
            key, data = line.strip().split(': ', 1)
            times[key] = data
    boundary.require(times.get('Exit status') == '0' and
                     times.get('Command being timed') == '"' + ' '.join(value['argv']) + '"', 'Linked GNU time command/exit differs')
    boundary.require(float(times['User time (seconds)']) >= 0 and float(times['System time (seconds)']) >= 0
                     and int(times['Maximum resident set size (kbytes)']) > 0
                     and times['Elapsed (wall clock) time (h:mm:ss or m:ss)'], 'Incomplete linked time/RSS evidence')
    wall = times['Elapsed (wall clock) time (h:mm:ss or m:ss)'].split(':')
    boundary.require(len(wall) in (2, 3) and all(float(part) >= 0 for part in wall), 'Invalid linked wall clock')
    return value


def native(directory, expected_binary, expected_sources, producer, boundary):
    directory = Path(directory)
    seal = boundary.read(directory / 'complete.json')
    boundary.require(seal['schema'] == 'context-decoder-complete/1' and seal['complete'] is True, 'Incomplete linked native attempt')
    for item in seal['files']:
        boundary.check(item)
    attempt = boundary.read(directory / 'attempt.json')
    boundary.require(attempt['binary'] == expected_binary and attempt['argv'] == producer['argv'], 'Linked native binary/argv differs')
    boundary.require(attempt['compiled_sources'] == expected_sources, 'Linked compiled source closure differs')
    for item in attempt['compiled_sources']:
        boundary.check(item)
    stdout = boundary.read(producer['raw']['stdout']['path'])
    boundary.require(stdout == dict(completion=boundary.pin(directory / 'complete.json')), 'Linked native completion stdout differs')
    return boundary.pin(directory / 'complete.json')


def completed(directory, phase, source_identity, boundary, seen=None):
    directory = Path(directory).resolve()
    visited = set() if seen is None else seen
    boundary.require(directory not in visited and len(visited) < 4, 'Cyclic/unbounded qualification ancestry')
    visited.add(directory)
    outer_path = directory / 'execution-complete.json'
    outer = boundary.read(outer_path)
    boundary.require(outer['schema'] == 'context-feedback-execution/1' and outer['complete'] is True and outer['phase'] == phase
                     and outer['whole_worker_cgroup_terminal'] is True and outer['stopped_for_limit'] is False,
                     'Successful outer terminal execution is required')
    for item in outer['files']:
        boundary.check(item)
    boundary.check(outer['terminal'])
    terminal = boundary.read(outer['terminal']['path'])
    boundary.require(terminal['released_after_empty_cgroup'] is True and terminal['worker_exit'] == 0 and terminal['error'] is None,
                     'Outer worker tree was not qualified terminal')
    proof = terminal['proof']
    if 'properties' in proof:
        boundary.require(proof['properties'].get('Result') == 'success'
                         and proof['properties'].get('ActiveState') == 'inactive', 'Terminal service result was not successful')
    else:
        boundary.require(proof.get('unit_unloaded_and_cgroup_absent') is True
                         and proof.get('worker_intake_verified') is True, 'No successful worker terminal proof')
    boundary.check(outer['worker_completion'])
    worker = boundary.read(outer['worker_completion']['path'])
    boundary.require(worker['complete'] is True and worker['phase'] == phase and worker['source_inventory_sha256'] == source_identity,
                     'Worker source/phase qualification differs')
    for item in worker['files']:
        boundary.check(item)
    boundary.check(worker['binary'])
    summary = boundary.read(directory / 'summary.json')
    source_map = {p['path']: p for p in summary['sources']}
    boundary.require(worker['stages'] == summary['stages'] and worker['binary'] == summary['binary'], 'Linked unit membership differs')
    stages = [stage(p, boundary) for p in worker['stages']]
    for dependency in worker.get('prerequisites', []):
        boundary.check(dependency['execution'])
        completed(Path(dependency['execution']['path']).parent, dependency['phase'], source_identity, boundary, set(visited))
    if phase == 'qualify':
        closure = boundary.read(directory / 'build-closure.json')
        for key in ('compiler', 'cache', 'compile_commands', 'binary'):
            boundary.check(closure[key])
        for library in closure['runtime_libraries']:
            boundary.check(library)
        boundary.require(closure['runtime_libraries'], 'Linked runtime closure is empty')
        boundary.require(closure['binary'] == worker['binary'], 'Actual build/runtime binary differs')
        producer = next(s for s in stages if s['argv'][:2] == [worker['binary']['path'], 'qualify'])
        attempt = boundary.read(directory / 'arithmetic/attempt.json')
        expected_sources = attempt['compiled_sources']
        boundary.require({p['path']: p for p in expected_sources} == source_map, 'Compiled source inventory differs from admission')
        native(directory / 'arithmetic', worker['binary'], expected_sources, producer, boundary)
    else:
        for outcome in summary['outcomes']:
            if 'native' not in outcome or outcome.get('reused_query0'):
                continue
            boundary.check(outcome['native']['completion'])
            producer = stage(outcome['native']['receipt'], boundary)
            target = Path(outcome['native']['completion']['path']).parent
            attempt = boundary.read(target / 'attempt.json')
            boundary.require({p['path']: p for p in attempt['compiled_sources']} == source_map,
                             'Frame compiled source inventory differs')
            native(target, worker['binary'], attempt['compiled_sources'], producer, boundary)
            result = boundary.read(target / 'result.json')
            boundary.require(result['frame'] == outcome['frame'], 'Frame result differs from actual constructed input')
    return dict(execution=boundary.pin(outer_path), phase=phase, binary=worker['binary'])
