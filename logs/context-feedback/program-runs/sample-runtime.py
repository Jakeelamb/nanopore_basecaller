"""Bounded sample-context execution glue; imported only by owned sample helpers."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / 'results/sample-context'
LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')
UV = Path('/home/jake/.local/bin/uv')
ENVIRONMENT = Path('/home/jake/Projects/nanopore_basecaller-retrieval/.venv')
MIB = 1024 ** 2
GIB = 1024 ** 3
RAW_NAMES = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')
ENV = dict(UV_PROJECT_ENVIRONMENT=str(ENVIRONMENT), UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never',
           REF_PATH='/dev/null', REF_CACHE='/dev/null', PYTHONDONTWRITEBYTECODE='1')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pg = load('sample_process_guard', ROOT / 'tools/context_decoder/process_guard.py')
supervisor = load('sample_process_supervisor', ROOT / 'tools/context_decoder/process_supervisor.py')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def pin(path):
    path = Path(path).resolve(strict=True)
    size = path.stat().st_size
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(MIB):
            digest.update(block)
    require(path.stat().st_size == size, 'File size changed while pinning: ' + str(path))
    return dict(path=str(path), size=size, sha256=digest.hexdigest())


def check(value):
    require(isinstance(value, dict) and set(value) == {'path', 'size', 'sha256'} and pin(value['path']) == value,
            'Pinned file differs: ' + str(value))
    return Path(value['path'])


def read(value):
    return json.loads(check(value).read_text())


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fresh(path, value):
    data = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n'
    with Path(path).open('x') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync(Path(path).parent)


def census():
    """Only fresh sample outputs belong to this runner; no foreign result tree is charged."""
    files = {}
    bases = [RESULTS] + list(HERE.glob('run-sample-*'))
    for base in bases:
        if not base.exists():
            continue
        for path in base.rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():
                    files[str(path)] = path.stat().st_size
            except FileNotFoundError:
                # Compilers can rename temporary files between directory and stat reads.
                continue
    return files


def bytes_now(baseline):
    current = census()
    return dict(cumulative_bytes=sum(current.values()),
                new_bytes=sum(max(0, size - baseline.get(path, 0)) for path, size in current.items()),
                free_bytes=shutil.disk_usage(ROOT).free)


def verify_raw(directory, argv, expected_exit):
    raw = {name: pin(directory / name) for name in RAW_NAMES}
    require(shlex.split((directory / 'command.sh').read_text()) == argv
            and (directory / 'cwd.txt').read_text().strip() == str(ROOT)
            and (directory / 'exit-status.txt').read_text().strip() == str(expected_exit),
            'Raw command/cwd/exit differs')
    begin, end = ((directory / name).read_text().strip() for name in ('start.txt', 'end.txt'))
    require(begin.endswith('Z') and end.endswith('Z') and datetime.fromisoformat(begin) <= datetime.fromisoformat(end),
            'Raw clocks differ')
    timing = dict(line.strip().split(': ', 1) for line in (directory / 'time.txt').read_text().splitlines()
                  if line.startswith('\t') and ': ' in line)
    require(timing.get('Exit status') == str(expected_exit)
            and timing.get('Command being timed') == '"' + ' '.join(argv) + '"'
            and float(timing['User time (seconds)']) >= 0 and float(timing['System time (seconds)']) >= 0
            and int(timing['Maximum resident set size (kbytes)']) > 0
            and timing['Elapsed (wall clock) time (h:mm:ss or m:ss)'], 'Raw time/RSS evidence differs')
    return raw


def source_closure(worker):
    return [pin(path) for path in (worker, HERE / 'sample-runtime.py', HERE / 'run-sample-bounded.py',
            ROOT / 'scripts/record-command.sh', ROOT / 'tools/context_decoder/process_guard.py',
            ROOT / 'tools/context_decoder/process_supervisor.py', UV, ENVIRONMENT / 'pyvenv.cfg',
            ENVIRONMENT / 'bin/python')]


class Unit:
    def __init__(self, identity, intake_path, intake_sha256):
        require(Path.cwd().resolve() == ROOT, 'Wrong sample worker cwd')
        value = pin(intake_path)
        require(value['sha256'] == intake_sha256, 'Outer intake pin differs')
        self.intake = read(value)
        self.directory = RESULTS / identity
        self.price = read(self.intake['price'])
        require(self.price['id'] == identity and self.intake['output'] == str(self.directory)
                and self.price['worker'] == pin(Path(os.sys.argv[0])), 'Worker identity/source differs')
        self.deadline = self.intake['monotonic_deadline']
        self.receipts = []
        self.sources = self.intake['sources']
        for source in self.sources:
            check(source)
        parent = self.intake['parent_pid']
        require(parent != os.getpid() and supervisor.process_start(parent) == self.intake['parent_start'],
                'Outer parent process changed')
        fd = Path('/proc') / str(parent) / 'fd' / str(self.intake['lock_fd'])
        info = fd.parent.parent / 'fdinfo' / str(self.intake['lock_fd'])
        require(fd.resolve() == LOCK and 'FLOCK' in info.read_text() and 'WRITE' in info.read_text(),
                'Outer process does not retain canonical exclusive lock')
        observed = supervisor.show(self.intake['unit'])
        properties = observed['properties']
        require(observed['exit'] == 0 and properties['Description'] == self.intake['description']
                and properties['ControlGroup'] == self.intake['cgroup']
                and properties['KillMode'] == 'control-group' and properties['ExitType'] == 'cgroup'
                and properties['CollectMode'] == 'inactive' and properties['SendSIGKILL'] == 'yes'
                and properties['FinalKillSignal'] == '9' and properties['Type'] == 'exec'
                and properties['ActiveState'] == 'active'
                and 0 < supervisor.duration(properties['RuntimeMaxUSec']) <= 295
                and supervisor.duration(properties['TimeoutStopUSec']) <= 1,
                'Live whole-unit service policy differs')
        group = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                     if line.startswith('0::'))
        require(group == self.intake['cgroup'], 'Worker is outside admitted cgroup')
        kernel = Path('/sys/fs/cgroup') / group.lstrip('/')
        values = {name: (kernel / name).read_text().strip()
                  for name in ('cpu.max', 'memory.max', 'memory.swap.max', 'cgroup.events')}
        quota, period = values['cpu.max'].split()
        require(quota != 'max' and 0 < int(quota) <= 2 * int(period)
                and values['memory.max'] != 'max' and int(values['memory.max']) <= 4 * GIB
                and values['memory.swap.max'] == '0', 'Live kernel CPU/memory/swap caps differ')
        address_space = resource.getrlimit(resource.RLIMIT_AS)
        require(address_space == (8 * GIB, 8 * GIB), 'Live address-space hard/soft limit differs')
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.price['maximum_new_bytes'], self.price['maximum_new_bytes']))
        require(all(os.environ.get(key) == text for key, text in ENV.items()), 'Exact offline/native environment differs')
        fresh(self.directory / 'worker-intake.json', dict(verified=True, observed_utc=utc(), worker_pid=os.getpid(),
              parent_lock_retained=True, intake=value, observation=observed, kernel=values,
              rlimit_as=list(address_space), rlimit_fsize=list(resource.getrlimit(resource.RLIMIT_FSIZE)),
              explicit_env={key: os.environ[key] for key in ENV}, sources=self.sources))
        self.recorder = self.directory / 'recorder-root/scripts/record-command.sh'
        require(self.recorder.resolve() == ROOT / 'scripts/record-command.sh', 'Recorder alias differs')
        pg.adopt_orphans()
        self.budget()

    def budget(self):
        require(time.monotonic() < self.deadline, 'Worker wall boundary reached')
        sample = bytes_now(self.intake['baseline'])
        require(sample['new_bytes'] <= self.price['maximum_new_bytes']
                and sample['cumulative_bytes'] <= self.price['maximum_cumulative_bytes']
                and sample['free_bytes'] >= 30 * GIB, 'Worker output/disk boundary reached')

    def stage(self, name, argv):
        self.budget()
        argv = list(map(str, argv))
        launcher = self.directory / 'stages' / name
        launcher.mkdir(parents=True)
        fresh(launcher / 'launch.json', dict(argv=[str(self.recorder), name, *argv], cwd=str(ROOT),
              explicit_env={key: os.environ[key] for key in ENV}, started_utc=utc()))
        process, failure, cleanup = None, None, None
        started = utc()
        previous = set((self.directory / 'recorder-root/logs').iterdir())
        try:
            with (launcher / 'stdout').open('xb') as out, (launcher / 'stderr').open('xb') as err:
                process = subprocess.Popen([str(self.recorder), name, *argv], stdout=out, stderr=err,
                                           cwd=ROOT, start_new_session=True)
                while process.poll() is None:
                    self.budget()
                    time.sleep(.1)
        except BaseException as error:
            failure = repr(error)
        finally:
            if process is not None:
                cleanup = pg.stop_group(process, process.pid)
                fresh(launcher / 'group-cleanup.json', cleanup)
            status = None if process is None else process.returncode
            fresh(launcher / 'terminal.json', dict(argv=argv, started_utc=started, ended_utc=utc(),
                  exit=status, failure=failure, owned_group_cleanup=cleanup))
        observed = dict(schema='context-feedback-stage/1', name=name, argv=argv, exit=status, failure=failure,
                        terminal=pin(launcher / 'terminal.json'), projection_error=None,
                        group_cleanup=None if cleanup is None else pin(launcher / 'group-cleanup.json'),
                        raw={}, missing_raw=list(RAW_NAMES), explicit_env={key: os.environ[key] for key in ENV})
        try:
            text = (launcher / 'stdout').read_text().strip()
            created = set((self.directory / 'recorder-root/logs').iterdir()) - previous
            raw_directory = Path(text) if text else next(iter(created)) if len(created) == 1 else None
            require(raw_directory is not None and raw_directory in created, 'Raw recorder directory is ambiguous/foreign')
            observed['raw'] = {name: pin(raw_directory / name) for name in RAW_NAMES if (raw_directory / name).is_file()}
            observed['missing_raw'] = [name for name in RAW_NAMES if name not in observed['raw']]
            if status == 0 and failure is None:
                observed['raw'] = verify_raw(raw_directory, argv, 0)
        except BaseException as error:
            observed['projection_error'] = repr(error)
        fresh(launcher / 'finish.json', observed)
        self.receipts.append(pin(launcher / 'finish.json'))
        require(status == 0 and failure is None and observed['projection_error'] is None
                and not observed['missing_raw'], 'Stage failed; retained at ' + str(launcher))
        self.budget()
        return observed

    def complete(self, phase, files, sources=None, details=None):
        self.budget()
        for source in self.sources + (sources or []):
            check(source)
        fresh(self.directory / 'complete.json', dict(schema='sample-context-unit/1', complete=True, phase=phase,
              worker_intake=pin(self.directory / 'worker-intake.json'), sources=self.sources + (sources or []),
              stages=self.receipts, files=files, details=details or {}, finished_utc=utc(),
              biological_qualification=False))
        print(json.dumps(dict(completion=pin(self.directory / 'complete.json'))))
