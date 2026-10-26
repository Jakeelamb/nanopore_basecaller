"""Focused CPU custody/cleanup controls. Run only in Root's freshly admitted unit."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
import signal
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
import legacy as l


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

    def legacy_fixture(self):
        directory = self.root / 'legacy-raw'
        directory.mkdir()
        values = {'command.sh': '/usr/bin/true \n', 'cwd.txt': str(self.root) + '\n',
                  'start.txt': '2026-01-01T00:00:00Z\n', 'end.txt': '2026-01-01T00:00:01Z\n',
                  'exit-status.txt': '0\n', 'stdout': 'synthetic-scientific-body', 'stderr': '', 'time.txt': 'Exit status: 0\n'}
        for name, value in values.items():
            (directory / name).write_text(value)
        raw = {name: b.pin(directory / name) for name in l.RAW}
        receipt = dict(status='finished', exit=0, failure=None, native_launch_monotonic_ns=1,
                       native_end_monotonic_ns=2, argv=['/usr/bin/true'], recorder=str(directory),
                       stdout=raw['stdout']['path'], pins=list(raw.values()),
                       context=dict(experiment='fixture-experiment', sources=[], executables=[]))
        path = self.root / 'finish.json'
        b.write(path, receipt)
        manifest = self.root / 'experiment.json'
        b.write(manifest, dict(identity='fixture-experiment', model_pins=[],
                cohorts={'development': dict(ids=b.pin(self.ids), raw=raw['stdout'])}))
        return b.pin(path), b.pin(manifest), raw

    def test_legacy_finish_reads_metadata_and_never_scientific_stdout(self):
        receipt, _manifest, raw = self.legacy_fixture()
        actual = Path.read_bytes
        def guarded_read(path):
            self.assertNotEqual(str(path), raw['stdout']['path'], 'scientific body was opened')
            return actual(path)
        with patch.object(Path, 'read_bytes', guarded_read):
            imported = l.stock_finish(l.Metadata(), receipt, str(self.root))
        self.assertEqual(imported['result'], raw['stdout'])
        self.assertFalse(imported['scientific_bodies_read'])

    def test_legacy_missing_recorder_and_changed_metadata_reject_at_distinct_guards(self):
        receipt, _manifest, raw = self.legacy_fixture()
        Path(raw['time.txt']['path']).unlink()
        with self.assertRaisesRegex(ValueError, 'missing or size-changed linked artifact'):
            l.stock_finish(l.Metadata(), receipt, str(self.root))
        Path(receipt['path']).write_text('x' * receipt['size'])
        with self.assertRaisesRegex(ValueError, 'metadata hash differs'):
            l.stock_finish(l.Metadata(), receipt, str(self.root))

    def test_actual_legacy_producer_alias_binds_whole_source_input_argv_tuple(self):
        receipt, manifest, raw = self.legacy_fixture()
        item = dict(receipt=receipt, experiment_manifest=manifest, role='development',
                    cwd=str(self.root), argv=['/usr/bin/true'], result=raw['stdout'],
                    source=dict(sources=[], executables=[]), input_pins=[b.pin(self.ids), raw['stdout']])
        self.assertEqual(c.producer(item), c.producer(copy.deepcopy(item)))
        changed = copy.deepcopy(item)
        changed['input_pins'] = []
        with self.assertRaisesRegex(ValueError, 'source/input tuple differs'):
            c.producer(changed)
        changed = copy.deepcopy(item)
        changed['argv'] = ['/usr/bin/false']
        with self.assertRaisesRegex(ValueError, 'argv/result differs'):
            c.producer(changed)

    def test_genuine_retained_inventory_preserves_incompatible_SUP_and_all64(self):
        # Requires Root's separately pinned metadata-only admission; it never launches a producer.
        config = b.read(Path(__file__).resolve().parents[1] / 'config/stock-feedback-compare-v1.json')
        inventory = l.inventory(config)
        self.assertEqual([arm['status'] for arm in inventory['arms']],
                         ['retained-reuse-available', 'retained-reuse-available', 'incompatible-retained-control'])
        self.assertTrue(all(len(arm['parents']) == 64 for arm in inventory['arms']))
        self.assertFalse(inventory['scientific_bodies_read'] or inventory['producer_replayed'])
        self.assertFalse(inventory['matched_three_arm_comparison'])
        self.assertLessEqual(inventory['metadata_bytes'], 32 * 1024**2)
        self.assertIn('trim differs', inventory['arms'][2]['gaps'])
        print(json.dumps(dict(control='genuine-retained-metadata-inventory', metadata_bytes=inventory['metadata_bytes'],
                              statuses=[arm['status'] for arm in inventory['arms']], population=64,
                              scientific_bodies_read=False, producer_replayed=False)))

    def retained_stock_producer(self, config, index):
        reader = l.Metadata()
        receipt_pin = config['legacy']['native_receipts'][index]
        receipt = reader.read(receipt_pin)
        manifest = reader.read(config['legacy']['experiment'])
        imported = l.stock_finish(reader, receipt_pin, config['legacy']['native_cwd'])
        cohort = manifest['cohorts']['development']
        return dict(receipt=receipt_pin, experiment_manifest=config['legacy']['experiment'], role='development',
                    cwd=config['legacy']['native_cwd'], argv=receipt['argv'], result=imported['result'],
                    source=dict(sources=receipt['context']['sources'], executables=receipt['context']['executables']),
                    input_pins=[cohort['ids'], cohort['raw'], *manifest['model_pins']])

    def retained_uncertainty_producer(self, config, receipt_pin):
        reader = l.Metadata()
        receipt = reader.read(receipt_pin)
        imported = l.uncertainty_command(reader, receipt_pin, config['legacy']['context_cwd'])
        return dict(receipt=receipt_pin, cwd=config['legacy']['context_cwd'], argv=receipt['argv'],
                    result=imported['result'], input_pins=receipt['inputs'],
                    source=dict(witness=receipt['source_witness'], sources=receipt['sources'],
                                binary=receipt['binary'], runtime=receipt['runtime'], dependency=receipt['dependency_manifest']))

    def retained_declaration(self, config, arm, producer):
        kind = 'sup' if arm == 'stock-sup' else 'hac'
        return dict(arm=arm, **{key: config[key] for key in c.CONTRACT_KEYS},
                    parents=c.parents(config['parents_pin']['path']), producer=producer,
                    model=dict(name=Path(config['legacy'][kind + '_model']).name,
                               config_pin=config['legacy'][kind + '_config']))

    def test_real_retained_HAC_receipt_cannot_be_declared_SUP(self):
        config = b.read(Path(__file__).resolve().parents[1] / 'config/stock-feedback-compare-v1.json')
        genuine_hac = self.retained_stock_producer(config, 0)
        self.assertEqual(Path(c.producer(genuine_hac)['custody']['model']).name,
                         Path(config['legacy']['hac_model']).name)
        # Same actual HAC tuple as the independent retained counterexample; only the arm declares SUP.
        declared_sup = self.retained_declaration(config, 'stock-sup', genuine_hac)
        planned = c.plan(config, [declared_sup])
        row = next(arm for arm in planned['arms'] if arm['arm'] == 'stock-sup')
        self.assertEqual(row['status'], 'unqualified')
        self.assertIn('actual producer model/config differs from arm declaration', row['gaps'])
        self.assertEqual(len(row['parents']), 64)

    def test_real_retained_native_mapped_result_binds_native_arm(self):
        config = b.read(Path(__file__).resolve().parents[1] / 'config/stock-feedback-compare-v1.json')
        declaration = self.retained_declaration(config, 'native-hac', self.retained_stock_producer(config, 2))
        row = c.plan(config, [declaration])['arms'][0]
        self.assertEqual(row['status'], 'retained-metadata-valid')
        self.assertEqual(row['custody']['result'], config['legacy']['native_sam'])

    def test_real_observation_rejects_wrong_result_arm_and_mask(self):
        config = b.read(Path(__file__).resolve().parents[1] / 'config/stock-feedback-compare-v1.json')
        context_map = l.Metadata().read(config['legacy']['context_map'])
        context = self.retained_declaration(config, 'hac-context', self.retained_uncertainty_producer(
            config, context_map['records']['mapped-sam']))
        native = self.retained_declaration(config, 'native-hac', self.retained_stock_producer(config, 2))
        planned = c.plan(config, [native, context])
        base = ('/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback/'
                'targeting-engineering-1/observation-selected-native-3/')
        # Source-pinned command-metadata leaves of the accepted-context-map role; no result body is opened.
        score_pins = {100: dict(path=base + 'score-100/raw/complete.json', size=19384,
                               sha256='a22169b174febc25938bd8bca11837c59ee6d999226f2c6c09b6196ecb08ad3e'),
                      500: dict(path=base + 'score-500/raw/complete.json', size=19384,
                                sha256='4710fd7efc1c70cf2b8fd632e1386abff6ef8d8124ecfeebaf2beb9083877190')}
        receipts = {mask: l.Metadata().read(value) for mask, value in score_pins.items()}
        results = {mask: next(p for p in value['produced_files'] if p['path'].endswith('/summary.json'))
                   for mask, value in receipts.items()}
        domain = planned['retained_closure']['domains']
        observation = dict(arm='hac-context', mask=100, parents=context['parents'], domains=config['truth_domains'],
                masks=config['masks'], zero_exposure_preserved=True, denominator='M+X+I+D', errors='X+I+D',
                technical_bounds=dict(parent=None, genomic_block=None), strata=dict(target43=None, nontarget21=None),
                changed_footprint_alt=dict(SNV=None, INS=None, DEL=None), result=results[100],
                producer=self.retained_uncertainty_producer(config, score_pins[100]),
                observer_tuple=dict(arm='hac-context', mask=100, observer=domain['pairer'],
                    reference=domain['reference'], eligible=domain['eligible']['100'],
                    baseline=config['legacy']['native_sam'], candidate=context_map['mapped'], parents=domain['parents']))
        valid = c.report(config, planned, [observation])
        observed = next(row for row in valid['matrix'] if row['arm'] == 'hac-context' and row['mask'] == 100)
        self.assertEqual(observed['status'], 'retained-metadata-valid')
        self.assertFalse(observed['native_observation']['numeric_payload_verified'])
        for case in ('arm', 'mask', 'result'):
            changed = copy.deepcopy(observation)
            if case == 'arm':
                changed['arm'] = changed['observer_tuple']['arm'] = 'native-hac'
                changed['observer_tuple']['candidate'] = config['legacy']['native_sam']
            elif case == 'mask':
                changed['mask'] = changed['observer_tuple']['mask'] = 500
                changed['observer_tuple']['eligible'] = domain['eligible']['500']
            else:
                changed['result'] = results[500]
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, 'observation actual arm/mask/observer|observation result is not linked'):
                c.report(config, planned, [changed])

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

    def test_worker_interrupted_wait_retains_actual_reaped_exit_status(self):
        request = self.request()
        marker = self.root / 'worker-started'
        request['argv'] = [sys.executable, '-c',
                           'from pathlib import Path; import time; Path(' + repr(str(marker)) +
                           ').write_text("started"); time.sleep(60)']
        request['source_pins'].append(b.pin(sys.executable))
        request_path = self.root / 'interrupted-request.json'
        b.write(request_path, request)
        output = self.root / 'interrupted-attempt'
        output.mkdir()
        original_popen = subprocess.Popen
        launched = []
        original_term = signal.getsignal(signal.SIGTERM)

        def interrupted_wait(*_args, **_kwargs):
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), 'actual child did not initialize before interrupted wait')
            os.kill(os.getpid(), signal.SIGTERM)
            raise AssertionError('worker TERM handler did not interrupt wait')

        def spawn(argv, **kwargs):
            process = original_popen(argv, **kwargs)
            process.wait = interrupted_wait
            launched.append(process)
            return process

        try:
            with patch.object(b, 'kernel_check', return_value={'test_only': True}), \
                    patch.object(b.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaisesRegex(ValueError, 'whole-unit termination requested'):
                    b.worker(request_path, b.pin(request_path)['sha256'], output)
            terminal = b.read(output / 'terminal.json')
            self.assertIsNotNone(launched[0].returncode)
            self.assertNotEqual(launched[0].returncode, 0)
            self.assertEqual(terminal['exit'], launched[0].returncode)
            self.assertEqual((output / 'exit-status.txt').read_text().strip(), str(launched[0].returncode))
            self.assertTrue(terminal['exit_known'] and terminal['cleanup']['terminal'])
            self.assertIsNotNone(terminal['error'])
            self.assertFalse((output / 'complete.json').exists())
            print(json.dumps(dict(control='worker-interrupted-wait', terminal=terminal)))
        finally:
            signal.signal(signal.SIGTERM, original_term)
            for process in launched:
                b.guard().stop_group(process, process.pid)

    def outer_fixture(self, inject_cleanup_failure=False, inject_projection_failure=False, inject_manager_kill=False):
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
        finish = ('import os,signal; os.kill(os.getpid(),signal.SIGKILL)' if inject_manager_kill else
                  '[Path(' + repr(str(output)) + ',name).write_text("test-only-inner-record") for name in ' +
                  repr((*b.RAW, 'terminal.json', 'complete.json')) + ']')
        parent = ('import subprocess,sys,time; from pathlib import Path; '
                  'subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); time.sleep(0.2); '
                  + finish)
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
                                          'MainPID': '0', 'ControlPID': '0', 'ControlGroup': '',
                                          'Result': 'timeout' if inject_manager_kill else 'success'})

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
                elif inject_cleanup_failure or inject_manager_kill:
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
                if inject_manager_kill:
                    terminal = b.read(output / 'outer-terminal.json')
                    self.assertIsNotNone(terminal['error'])
                    self.assertEqual(terminal['exit'], -signal.SIGKILL)
                    self.assertFalse(terminal['worker_complete'])
                    self.assertIn('time.txt', terminal['missing_worker_records'])
                    self.assertIn('terminal.json', terminal['missing_worker_records'])
                    self.assertIn('complete.json', terminal['missing_worker_records'])
                    self.assertFalse((output / 'time.txt').exists())
                    self.assertFalse((output / 'terminal.json').exists())
                    self.assertFalse((output / 'complete.json').exists())
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

    def test_outer_manager_kill_records_failure_and_missing_inner_clocks(self):
        self.outer_fixture(inject_manager_kill=True)

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
