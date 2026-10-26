"""Focused CPU custody/cleanup controls. Run only in Root's freshly admitted unit."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/stock_feedback'))
import bounded as b
import compare as c


class StockFeedback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ids = self.root / 'parents.ids'
        self.ids.write_text(''.join('parent-' + str(i) + '\n' for i in range(64)))
        self.config = dict(parents_pin=b.pin(self.ids), pod5_pin={'sha256': 'raw'}, chemistry={'kit': 'kit'},
                           settings={'trim': 'none'}, mapper={'pin': 'mapper'}, masks=[100, 500],
                           truth_domains={'pin': 'unchanged'}, hg005_selection=False)

    def request(self):
        now = datetime.now(timezone.utc)
        return dict(schema='bounded-command/1', id='control', not_before_utc=(now-timedelta(seconds=1)).isoformat(),
                    expires_utc=(now+timedelta(seconds=250)).isoformat(), wall_seconds=200, profile='engineering',
                    memory_bytes=4*1024**3, address_space_bytes=8*1024**3, cpus=2, swap_bytes=0,
                    growth_bytes=100*1024**2, aggregate_bytes=4*1024**3, reserve_bytes=30*1024**3,
                    root=str(self.root), cwd=str(self.root), argv=['/usr/bin/true'],
                    source_pins=[b.pin(b.__file__), b.pin('/usr/bin/true'), b.pin('/usr/bin/time')], input_pins=[],
                    expected_files=[str(self.ids)], output_roots=[str(self.root)],
                    roles=dict(unit='F4/engineering', inputs={}, outputs={'control': str(self.ids)}),
                    env=dict(UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1'))

    def test_all64_and_zero_exposure_matrix_not_dropped(self):
        planned = c.plan(self.config, [])
        reported = c.report(self.config, planned, [])
        self.assertEqual(len(reported['matrix']), 6)
        for row in reported['matrix']:
            self.assertEqual(len(row['parent_rows']), 64)
            self.assertEqual(row['status'], 'unqualified')
        self.assertIsNone(reported['model_winner'])

    def test_reordered_missing_duplicate_extra_parents_rejected(self):
        for values in ([str(i) for i in range(63)], ['x']*64, [str(i) for i in range(65)]):
            self.ids.write_text('\n'.join(values) + '\n')
            with self.assertRaisesRegex(ValueError, 'exact original64'):
                c.plan(self.config, [])

    def test_wrong_model_and_read_set_do_not_qualify(self):
        item = dict(arm='stock-sup', **{k: self.config[k] for k in c.CONTRACT_KEYS})
        item.update(parents=c.parents(self.ids)[::-1], model={'name': 'sup'})
        plan = c.plan(self.config, [item])
        self.assertIn('missing, reordered or extra original parent identities', plan['arms'][2]['gaps'])
        self.assertIn('model/config declaration missing', plan['arms'][2]['gaps'])

    def test_alias_requires_whole_source_input_argv_cwd_tuple(self):
        original = dict(source=['s'], inputs=['i'], argv=['a'], cwd='root')
        for key in original:
            changed = copy.deepcopy(original)
            changed[key] = ['different'] if isinstance(original[key], list) else 'different'
            self.assertNotEqual(c.identity(original), c.identity(changed))

    def test_ordinary_large_memory_profile_mismatch_negative(self):
        request = self.request()
        self.assertGreater(b.validate(request), 0)
        request['memory_bytes'], request['address_space_bytes'] = b.PROFILES['mapping']
        with self.assertRaisesRegex(ValueError, 'profile/kernel caps mismatch'):
            b.validate(request)
        request['profile'] = 'mapping'
        self.assertGreater(b.validate(request), 0)

    def test_stale_grant_wrong_cwd_and_missing_source_reject_separately(self):
        for mutation, error in (
            (lambda r: r.update(expires_utc='2000-01-01T00:00:00+00:00'), 'stale'),
            (lambda r: r.update(cwd='/tmp'), 'cwd/root'),
            (lambda r: r.update(source_pins=[]), 'source/input')):
            request = self.request()
            mutation(request)
            with self.assertRaisesRegex(ValueError, error):
                b.validate(request)

    def test_source_hash_guard_rejects_changed_input(self):
        before = b.pin(self.ids)
        self.ids.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'pin differs'):
            b.check(before)

    def test_unloaded_service_exit_one_is_terminal_only_with_absent_cgroup(self):
        self.assertTrue(b.terminal(dict(exit=1, properties={'LoadState': 'not-found'}),
                                   '/feedback-next-nonexistent-hermetic-control'))
        self.assertFalse(b.terminal(dict(exit=1, properties={}),
                                    '/feedback-next-nonexistent-hermetic-control'))

    def test_genuine_producer_consumed_then_missing_result_and_recorder_no_replay(self):
        request = self.request()
        counter = self.root / 'counter'
        result = self.root / 'result'
        code = ('from pathlib import Path; p=Path(' + repr(str(counter)) + '); '
                'p.write_text(str(int(p.read_text())+1) if p.exists() else "1"); '
                'Path(' + repr(str(result)) + ').write_text("genuine result")')
        request['argv'] = [sys.executable, '-c', code]
        request['source_pins'].append(b.pin(sys.executable))
        request['expected_files'] = [str(result)]
        request['roles']['outputs'] = {'genuine-result': str(result)}
        request_path = self.root / 'request.json'
        b.write(request_path, request)
        out = self.root / 'attempt'
        out.mkdir()
        with patch.object(b, 'kernel_check', return_value={'test_only': True}):
            b.worker(request_path, b.pin(request_path)['sha256'], out)
        complete = b.read(out / 'complete.json')
        self.assertTrue(complete['complete'])
        self.assertEqual(result.read_text(), 'genuine result')
        result.unlink()
        with self.assertRaisesRegex(ValueError, 'missing success-linked'):
            b.linked_files(request['expected_files'])
        (out / 'time.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'missing success-linked'):
            b.linked_files([str(out / name) for name in b.RAW])
        self.assertEqual(counter.read_text(), '1')
        self.assertEqual(b.read(out / 'terminal.json')['exit'], 0)

    def test_missing_result_durable_projection_failure_after_single_success(self):
        request = self.request()
        request['expected_files'] = [str(self.root / 'absent-recorder')]
        request['roles']['outputs'] = {'missing-recorder': request['expected_files'][0]}
        request_path = self.root / 'request.json'
        b.write(request_path, request)
        out = self.root / 'attempt'
        out.mkdir()
        with patch.object(b, 'kernel_check', return_value={'test_only': True}):
            with self.assertRaisesRegex(ValueError, 'missing success-linked'):
                b.worker(request_path, b.pin(request_path)['sha256'], out)
        self.assertEqual(b.read(out / 'terminal.json')['exit'], 0)
        self.assertFalse(b.read(out / 'projection-failed.json')['producer_replay_permitted'])
        self.assertFalse((out / 'complete.json').exists())

    def outer_fixture(self, inject_cleanup_failure=False, inject_projection_failure=False):
        """Exercise supervise's actual finally path; only systemd transport/canonical lock are stand-ins."""
        pg = b.guard()
        pg.adopt_orphans()
        request = self.request()
        request_path = self.root / 'request.json'
        b.write(request_path, request)
        output = self.root / 'outer-attempt'
        lock_path = self.root / 'test-only.lock'
        lock_path.touch()
        child_marker = self.root / 'outer-child.json'
        child = ('import json,os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                 'open(' + repr(str(child_marker)) + ',"w").write(json.dumps({"pid":os.getpid()})); time.sleep(60)')
        parent = ('import subprocess,sys,time; from pathlib import Path; '
                  'subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); time.sleep(0.2); '
                  'Path(' + repr(str(output / 'complete.json')) + ').write_text("{}")')
        original_popen = subprocess.Popen
        unrelated = original_popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        launched = []
        observations = []
        cleanup_calls = []
        actual_write = b.write

        def spawn(_argv, **_kwargs):
            process = original_popen([sys.executable, '-c', parent], start_new_session=True)
            launched.append(process)
            return process

        def cleanup(process, pgid):
            cleanup_calls.append(pgid)
            if inject_cleanup_failure and len(cleanup_calls) == 1:
                raise subprocess.TimeoutExpired('injected outer wait/cleanup failure', 3)
            return pg.stop_group(process, pgid)

        def observe(_unit):
            if not launched:
                return dict(exit=0, properties={'LoadState': 'not-found'})
            # An independent competing descriptor must still be excluded while either proof is pending.
            with lock_path.open('r') as competing:
                with self.assertRaises(BlockingIOError):
                    b.fcntl.flock(competing, b.fcntl.LOCK_EX | b.fcntl.LOCK_NB)
            self.assertFalse(pg.group_exists(launched[0].pid))
            self.assertIsNone(unrelated.poll())
            observations.append(True)
            return dict(exit=0, properties={'ActiveState': 'active' if len(observations) == 1 else 'inactive',
                                          'MainPID': '0', 'ControlPID': '0', 'ControlGroup': ''})

        def writing(path, value):
            if inject_projection_failure and Path(path).name == 'outer-terminal.json':
                self.assertFalse(pg.group_exists(launched[0].pid))
                self.assertGreaterEqual(len(observations), 2)
                raise OSError('injected terminal receipt write failure after empty proofs')
            return actual_write(path, value)

        standin_guard = SimpleNamespace(adopt_orphans=pg.adopt_orphans, stop_group=cleanup, group_exists=pg.group_exists)
        try:
            with patch.object(b, 'LOCK', lock_path), patch.object(b.Path, 'cwd', return_value=self.root), \
                    patch.object(b, 'guard', return_value=standin_guard), patch.object(b.subprocess, 'Popen', side_effect=spawn), \
                    patch.object(b.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')), \
                    patch.object(b, 'show', side_effect=observe), patch.object(b, 'write', side_effect=writing):
                if inject_projection_failure:
                    with self.assertRaisesRegex(OSError, 'terminal receipt write failure'):
                        b.supervise(request_path, b.pin(request_path)['sha256'], output)
                elif inject_cleanup_failure:
                    with self.assertRaisesRegex(ValueError, 'unit failed'):
                        b.supervise(request_path, b.pin(request_path)['sha256'], output)
                else:
                    self.assertEqual(b.supervise(request_path, b.pin(request_path)['sha256'], output), output / 'complete.json')
            self.assertFalse(pg.group_exists(launched[0].pid))
            self.assertIsNone(unrelated.poll())
            self.assertGreaterEqual(len(observations), 2)
            if not inject_projection_failure:
                proof = b.read(output / 'outer-terminal.json')['proof']
                self.assertTrue(proof['launcher']['leader_exited_before_cleanup'])
                self.assertTrue(proof['launcher']['kill_sent'])
                self.assertTrue(proof['launcher']['reaped'])
                self.assertTrue(proof['launcher_group_empty'] and proof['service_cgroup_empty'])
                self.assertEqual(bool(proof['failures']), inject_cleanup_failure)
                print(json.dumps(dict(control='actual-outer-cleanup', injected_failure=inject_cleanup_failure,
                                      proof=proof, unrelated_pid=unrelated.pid, unrelated_survived=True)))
            child_pid = json.loads(child_marker.read_text())['pid']
            self.assertFalse(pg.pid_exists(child_pid))
            with lock_path.open('r') as released:
                b.fcntl.flock(released, b.fcntl.LOCK_EX | b.fcntl.LOCK_NB)
        finally:
            for process in launched:
                pg.stop_group(process, process.pid)
            unrelated.terminate()
            unrelated.wait(timeout=3)

    def test_actual_outer_cleanup_after_leader_exit_preserves_unrelated_and_lock(self):
        self.outer_fixture()

    def test_actual_outer_cleanup_failure_cannot_unwind_before_both_empty_proofs(self):
        self.outer_fixture(inject_cleanup_failure=True)

    def test_actual_outer_receipt_failure_occurs_only_after_both_trees_empty(self):
        self.outer_fixture(inject_projection_failure=True)

    def test_original_guard_ignored_TERM_descendant_after_leader_exit(self):
        pg = b.guard()
        pg.adopt_orphans()
        marker = self.root / 'child.json'
        child = ('import json,os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                 'open(' + repr(str(marker)) + ',"w").write(json.dumps({"pid":os.getpid()})); time.sleep(60)')
        parent = ('import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
                  'time.sleep(0.2)')
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        process = subprocess.Popen([sys.executable, '-c', parent], start_new_session=True)
        try:
            deadline = time.monotonic()+3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), 'descendant did not initialize')
            child_pid = json.loads(marker.read_text())['pid']
            process.wait(timeout=3)
            event = pg.stop_group(process, process.pid)
            self.assertTrue(event['leader_exited_before_cleanup'])
            self.assertTrue(event['term_sent'] and event['kill_sent'] and event['terminal'])
            self.assertIn(child_pid, [row['pid'] for row in event['reaped']])
            self.assertFalse(pg.group_exists(process.pid))
            self.assertIsNone(unrelated.poll())
            print(json.dumps(dict(control='original-guard', cleanup=event, unrelated_pid=unrelated.pid,
                                  unrelated_survived=True)))
        finally:
            pg.stop_group(process, process.pid)
            unrelated.terminate()
            unrelated.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
