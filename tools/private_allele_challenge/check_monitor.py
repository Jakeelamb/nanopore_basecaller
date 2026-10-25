import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
from monitor_guard import fail_closed, guarded_monitor


def worker(root):
    child = subprocess.Popen(['sleep', '60'], start_new_session=True)
    (root / 'child.pid').write_text(str(child.pid))

    def terminate(_signum, _frame):
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=5)
        (root / 'cleanup.json').write_text(json.dumps(dict(returncode=child.returncode)))
        raise SystemExit(73)

    signal.signal(signal.SIGTERM, terminate)
    failures = []
    reject = lambda event: fail_closed(failures, event,
        lambda row: (root / 'failure.json').write_text(json.dumps(row)),
        lambda: os.kill(os.getpid(), signal.SIGTERM))
    sample = lambda: (root / 'injected-vanished-stat-target').stat()
    thread = threading.Thread(target=guarded_monitor,
        args=(threading.Event(), sample, reject, 0.01), daemon=True)
    thread.start()
    threading.Event().wait(10)
    raise AssertionError('monitor did not stop its owner')


if len(sys.argv) == 3 and sys.argv[1] == '--worker':
    worker(Path(sys.argv[2]))
else:
    with tempfile.TemporaryDirectory(prefix='batch-monitor-negative-') as directory:
        root = Path(directory)
        result = subprocess.run([sys.executable, __file__, '--worker', directory], timeout=15)
        assert result.returncode == 73, result.returncode
        failure = json.loads((root / 'failure.json').read_text())
        assert failure['reason'] == 'monitor_sampling_exception'
        assert failure['error_type'] == 'FileNotFoundError'
        pid = int((root / 'child.pid').read_text())
        assert not Path(f'/proc/{pid}').exists(), pid
        assert json.loads((root / 'cleanup.json').read_text())['returncode'] == -signal.SIGTERM
        stopped = []

        def broken_retention(_event):
            raise OSError('injected retention failure')

        fail_closed([], dict(reason='injected'), broken_retention, lambda: stopped.append(True))
        assert stopped == [True]
        print(json.dumps(dict(complete=True, owner_exit=73, owned_child_reaped=True,
            injected_error=failure, retention_failure_still_stops=True)))
