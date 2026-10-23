"""CPU contracts for the source adapter; no source/GPU producer runs here."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qualify_source', ROOT / 'scripts/qualify-source.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, text='sealed'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def build(self):
        artifact = self.file('binary')
        declared = {'path': str(artifact), 'sha256': q.b.digest(artifact), 'bytes': artifact.stat().st_size}
        transforms = self.file('transforms.json', json.dumps({'status': 'passed', 'transformations': []}))
        isolation = self.file('isolation.json', json.dumps({'status': 'passed'}))
        manifest = self.file('files.sha256', f'{q.b.digest(artifact)}  {artifact}\n')
        run = self.root / 'receipt-source-build-version-1'
        run.mkdir()
        for name, text in {'command.sh': f'env CUDA_VISIBLE_DEVICES= {artifact} --version \n', 'cwd.txt': str(ROOT),
                           'start.txt': 'start', 'end.txt': 'end', 'time.txt': 'Elapsed (wall clock)',
                           'stdout': q.b.STOCK_VERSION + '\n', 'stderr': '', 'exit-status.txt': '0'}.items():
            (run / name).write_text(text)
        pin = lambda p: {'path': str(p), 'sha256': q.b.digest(p), 'bytes': p.stat().st_size}
        data = {'qualification_status': 'source_build_and_selected_cpu_contracts_passed',
                'source': {'commit': q.b.SOURCE, 'canonical_clean_after_acceptance': True,
                           'recursive_submodules': [{'path': 'module', 'commit': '123'}], 'recursive_submodule_count': 1,
                           'vendor_transformations_evidence': pin(transforms), 'copied_git_isolation_evidence': pin(isolation),
                           'vendor_transformations': []},
                'build': {'version': q.b.STOCK_VERSION, 'binary': declared, 'authored_source_patches': [],
                          'unsupported_compiler_bypass_flags': [], 'basecalling_components_disabled': []},
                'acceptance': {'full_release_build': 'passed_582_tasks', 'version': 'passed_exact',
                               'cpu_tests': {'status': 'passed', 'failures': 0, 'errors': 0}},
                'dependency_archives': [], 'compiler_packages': [], 'runtime_elf_dependencies': [declared],
                'dependency_file_manifest': pin(manifest), 'compiler_file_manifest': pin(manifest),
                'receipts': [{'path': str(run), 'exit_status': 0, 'started_utc': 'start', 'finished_utc': 'end',
                              'command_sha256': q.b.digest(run / 'command.sh')}]}
        path = self.file('build.json', json.dumps(data))
        return path, data, artifact, run

    def test_completed_exact_build_and_retained_env_version_admit(self):
        path, _, artifact, _ = self.build()
        result = q._build(path, {'source_submodules': ' 123 module (123)\n'})
        self.assertEqual(result['executable'], q.b.pin(artifact))
        self.assertEqual(result['version'], q.b.STOCK_VERSION)
        self.assertTrue(result['version_runs'])

    def test_wrong_dirty_unfinished_source_and_changed_submodule_fail_closed(self):
        path, data, _, _ = self.build()
        changes = [(('build', 'version'), q.b.STOCK_VERSION + '+dirty', 'Ineligible'),
                   (('qualification_status',), 'building', 'unfinished'),
                   (('source', 'commit'), 'other', 'source custody'),
                   (('source', 'recursive_submodule_count'), 2, 'submodule'),
                   (('build', 'authored_source_patches'), ['patch'], 'Unsupported')]
        for keys, replacement, message in changes:
            with self.subTest(keys=keys):
                mutant = copy.deepcopy(data)
                target = mutant
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = replacement
                path.write_text(json.dumps(mutant))
                with self.assertRaisesRegex(ValueError, message):
                    q._build(path, {'source_submodules': ' 123 module (123)\n'})

    def test_changed_binary_and_missing_receipt_clock_reject(self):
        path, _, artifact, run = self.build()
        artifact.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Changed build'):
            q._build(path, {'source_submodules': ' 123 module (123)\n'})
        artifact.write_text('sealed')
        (run / 'time.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'Incomplete build receipt'):
            q._build(path, {'source_submodules': ' 123 module (123)\n'})

    def units(self):
        units = []
        for role, start in [('development', 1), ('validation', 100)]:
            parents = {str(UUID(int=index)): 1000 for index in range(start, start + 32)}
            membership = self.file(role + '.txt', ''.join(p + '\n' for p in parents))
            for tier in ('hac', 'sup'):
                units.append({'id': f'full-{role}-{tier}', 'scope': 'full', 'tier': tier,
                              'asset': {'sample': 'HG002', 'role': role, 'path': role + '.pod5'},
                              'ids': str(membership), 'parents': parents})
                if role == 'development':
                    smoke = copy.deepcopy(units[-1])
                    smoke.update(id='smoke-1-' + tier, scope='smoke')
                    units.append(smoke)
        uid = str(UUID(int=999))
        fixture_ids = self.file('fixture.txt', uid + '\n')
        units.append({'id': q.FIXTURE_ID, 'scope': 'fixture', 'tier': 'hac', 'asset': {'path': 'fixture.pod5'},
                      'ids': str(fixture_ids), 'parents': {uid: 1000}})
        return {'units': units, 'config': {'split_fixture': 'fixture.pod5'}}

    def test_only_fixed_hg002_devval_smoke_and_split_units_can_run(self):
        base = self.units()
        self.assertEqual({u['id'] for u in q._units(base, 'source')}, q.FULL_IDS | q.SMOKE_IDS | {q.FIXTURE_ID})
        self.assertEqual({u['id'] for u in q._units(base, 'official-smoke')}, q.SMOKE_IDS)
        for field, value in [('sample', 'HG005'), ('role', 'sealed_test')]:
            mutant = copy.deepcopy(base)
            mutant['units'][0]['asset'][field] = value
            with self.assertRaisesRegex(ValueError, 'Forbidden'):
                q._units(mutant, 'source')
        base['units'][0]['parents'][str(UUID(int=9999))] = 1000
        with self.assertRaisesRegex(ValueError, 'membership'):
            q._units(base, 'source')

    def test_frozen_verifier_drift_is_rejected(self):
        with patch.object(q.b, 'digest', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'Changed frozen'):
                q._frozen_tools()


class QualificationPolicyTests(unittest.TestCase):
    def test_supported_profile_is_frozen_without_changing_other_controls(self):
        for profile in ('balanced', 'performance'):
            with self.subTest(profile=profile):
                base = copy.deepcopy(q.b.CONTROLLED_POLICY)
                before = copy.deepcopy(base)
                policy = q._policy(base, profile)
                expected = copy.deepcopy(before)
                expected['platform_profile']['required'] = profile
                self.assertEqual(policy, expected)
                self.assertEqual(base, before)
                policy['cooldown']['max_temperature_celsius'] = 99
                self.assertEqual(base, before)

    def test_unexpected_profile_or_changed_control_policy_rejects(self):
        for profile in ('power-saver', '', 'balanced performance', 'PERFORMANCE'):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, 'Unsupported observed platform profile'):
                    q._policy(q.b.CONTROLLED_POLICY, profile)
        changed = copy.deepcopy(q.b.CONTROLLED_POLICY)
        changed['cooldown']['max_temperature_celsius'] = 99
        with self.assertRaisesRegex(ValueError, 'Unsupported qualification measurement policy'):
            q._policy(changed, 'performance')

    def test_sealing_rejects_unexpected_profile_before_build_or_producer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'new'
            base = {'sha256': q.BASE_ID, 'config': {'measurement_policy': copy.deepcopy(q.b.CONTROLLED_POLICY)}}
            with patch.object(q, '_frozen_tools'), patch.object(q.b, 'load_plan', return_value=base), \
                    patch.object(Path, 'read_text', return_value='power-saver\n'), \
                    patch.object(q, '_build', side_effect=AssertionError('build admission reached')), \
                    patch.object(q, '_native', side_effect=AssertionError('native producer reached')):
                with self.assertRaisesRegex(ValueError, 'Unsupported observed platform profile'):
                    q._seal(Path('build.json'), root)
            self.assertFalse(root.exists())


class ImmutableResumeTests(unittest.TestCase):
    def observation(self, root):
        plan, unit = {'sha256': 'plan', 'config': {}}, {'id': 'smoke-1-hac'}
        directory = root / 'units' / unit['id']
        pins = []
        for name in ('basecall', 'base-decode', 'aligned-decode', 'sort'):
            attempt = directory / name / '001'
            attempt.mkdir(parents=True)
            stdout = attempt / 'stdout'
            stdout.write_text('@PG\tID:dorado\tPN:dorado\tVN:' + q.b.STOCK_VERSION + '\nrecord\n')
            q.b.write(attempt / 'start.json', {'key': name})
            receipt = {'status': 'finished', 'exit': 0, 'context': {'plan': 'plan', 'unit': unit['id']},
                       'stdout': str(stdout), 'pins': [q.b.pin(stdout)]}
            q.b.write(attempt / 'finish.json', receipt)
            pins.extend([q.b.pin(attempt / 'finish.json'), q.b.pin(stdout)])
        value = {'status': 'verified', 'plan': 'plan', 'unit': unit['id'],
                 'verifier_sha256': q.FROZEN['benchmark.py'], 'pins': pins}
        q.b.write(directory / 'observation.json', value)
        return plan, unit, value

    def test_real_bound_receipt_audit_is_read_only_and_rejects_newer_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, unit, expected = self.observation(root)
            observed_path = root / 'units' / unit['id'] / 'observation.json'
            before = observed_path.read_bytes()
            self.assertEqual(q._observation(plan, unit, root), expected)
            self.assertEqual(observed_path.read_bytes(), before)
            newer = observed_path.parent / 'basecall' / '999' / 'start.json'
            q.b.write(newer, {'status': 'running'})
            with self.assertRaisesRegex(ValueError, 'Newer native attempt'):
                q._observation(plan, unit, root)

    def test_every_dorado_header_must_have_exact_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, unit, value = self.observation(root)
            directory = root / 'units' / unit['id']
            stdout = directory / 'base-decode' / '001' / 'stdout'
            stdout.write_text('@PG\tID:old\tPN:dorado\tVN:' + q.b.STOCK_VERSION + '\n@PG\tID:new\tPN:dorado\tVN:wrong\nrecord\n')
            receipt_path = stdout.parent / 'finish.json'
            receipt = q.b.read(receipt_path)
            receipt['pins'] = [q.b.pin(stdout)]
            q.b.write(receipt_path, receipt)
            value['pins'] = [q.b.pin(item['path']) for item in value['pins']]
            q.b.write(directory / 'observation.json', value)
            with self.assertRaisesRegex(ValueError, 'emitted Dorado program version'):
                q._observation(plan, unit, root)

    def test_existing_observation_never_calls_runner_or_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'units' / 'smoke-1-hac' / 'observation.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"completed_ns":42}\n')
            original = path.read_bytes()
            with patch.object(q, '_observation', return_value={'status': 'verified'}) as audit, \
                    patch.object(q.b, 'run_unit', side_effect=AssertionError('producer replay')), \
                    patch.object(q.b, 'admission', side_effect=AssertionError('native admission')):
                self.assertEqual(q._ensure_unit({}, {'id': 'smoke-1-hac'}, root), {'status': 'verified'})
                audit.assert_called_once()
            self.assertEqual(path.read_bytes(), original)

    def test_verify_audits_pins_and_observations_without_mutating_or_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = {'pins': [], 'plans': {'source': {'path': 'source/plan.json'}}}
            contract['sha256'] = q.b.identity(contract)
            report = {'contract': contract['sha256'], 'pins': [], 'through': 'smoke'}
            q.b.write(root / 'contract.json', contract)
            q.b.write(root / 'qualification.json', report)
            before = {p: p.read_bytes() for p in root.iterdir()}
            with patch.object(q, '_frozen_tools'), patch.object(q.b, 'load_plan', return_value={'units': [{'scope': 'smoke'}]}), \
                    patch.object(q, '_observation', return_value={}), \
                    patch.object(q.b, 'qualify', side_effect=AssertionError('qualify writes')), \
                    patch.object(q.a, 'score', side_effect=AssertionError('score writes')):
                self.assertEqual(q._audit(root), report)
            self.assertEqual({p: p.read_bytes() for p in root.iterdir()}, before)

    def test_failed_accuracy_requires_explicit_fresh_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'accuracy' / 'source-smoke' / 'failed').mkdir(parents=True)
            with patch.object(q.a, 'score', side_effect=AssertionError('score replay')):
                with self.assertRaisesRegex(ValueError, 'fresh attempt'):
                    q._score(root, 'source-smoke', Path('plan.json'), 'smoke')

    def test_changed_pin_is_not_a_successful_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / 'evidence'
            evidence.write_text('accepted')
            q.b.write(root / 'score-evidence' / 'source-smoke.json', {'pins': [q.b.pin(evidence)]})
            evidence.write_text('changed')
            with patch.object(q.a, 'score', side_effect=AssertionError('score replay')):
                with self.assertRaisesRegex(ValueError, 'Changed evidence'):
                    q._score(root, 'source-smoke', Path('plan.json'), 'smoke')

    def test_nested_evidence_pin_changes_fail_read_only_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / 'native.stdout'
            artifact.write_text('accepted')
            nested = root / 'nested.json'
            q.b.write(nested, {'pins': [q.b.pin(artifact)]})
            top = [q.b.pin(nested)]
            q._check_documents(top)
            artifact.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Changed evidence'):
                q._check_documents(top)


class CanonicalComparatorTests(unittest.TestCase):
    def canonical(self, text):
        normal = subprocess.run(['awk', q.CANONICAL_AWK], input=text, text=True, capture_output=True, check=True).stdout
        return subprocess.run(['sort'], input=normal, text=True, capture_output=True, check=True,
                              env={**q.os.environ, 'LC_ALL': 'C'}).stdout

    def test_record_and_tag_order_are_irrelevant_every_field_value_is_exact(self):
        a = 'a\t4\t*\t0\t0\t*\t*\t0\t0\tAC\tIJ\tzz:Z:a:b\tpi:Z:parent\tsp:i:2\n'
        b = 'b\t4\t*\t0\t0\t*\t*\t0\t0\tGT\tKL\tsp:i:4\tpi:Z:parent\n'
        permuted = '\n'.join('\t'.join(row.split('\t')[:11] + list(reversed(row.split('\t')[11:]))) for row in (b.rstrip(), a.rstrip())) + '\n'
        self.assertEqual(self.canonical(a + b), self.canonical('@HD\tVN:1.6\n' + permuted))
        for original, replacement in [('AC', 'AT'), ('IJ', 'II'), ('sp:i:2', 'sp:i:3'), ('a\t4', 'c\t4'), ('pi:Z:parent', 'pi:Z:foreign'), ('zz:Z:a:b', 'zz:Z:a')]:
            with self.subTest(original=original):
                self.assertNotEqual(self.canonical(a + b), self.canonical((a + b).replace(original, replacement, 1)))
        self.assertNotEqual(self.canonical(a + b), self.canonical(a))

    def test_malformed_record_is_a_command_failure(self):
        result = subprocess.run(['awk', q.CANONICAL_AWK], input='a\t4\n', text=True, capture_output=True)
        self.assertEqual(result.returncode, 65)

    def test_wrapper_records_unequal_as_data_and_propagates_execution_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            decoder = root / 'decoder'
            decoder.write_text('#!/bin/sh\n[ "$1" = view ] || exit 64\ncat -- "$2"\n')
            decoder.chmod(0o755)
            left, right = root / 'left', root / 'right'
            record = 'a\t4\t*\t0\t0\t*\t*\t0\t0\tAC\tIJ\tsp:i:2\n'
            left.write_text(record)
            right.write_text(record)
            def run(name):
                return subprocess.run(['bash', '-c', q.COMPARE_SH, '--', str(decoder), str(left), str(right), str(root / name),
                                       shutil.which('awk'), q.CANONICAL_AWK,
                                       *[shutil.which(key) for key in ('sort', 'cmp', 'sha256sum', 'diff', 'head', 'wc', 'rm')]],
                                      text=True, capture_output=True)
            equal = run('equal')
            self.assertEqual(equal.returncode, 0, equal.stderr)
            self.assertTrue(equal.stdout.endswith('cmp_exit=0\n'))
            self.assertFalse((root / 'equal' / 'left.sam').exists())
            right.write_text(record.replace('AC', 'AG'))
            different = run('different')
            self.assertEqual(different.returncode, 0, different.stderr)
            self.assertTrue(different.stdout.endswith('cmp_exit=1\n'))
            self.assertLessEqual((root / 'different' / 'difference.txt').stat().st_size, 4096)
            self.assertIn('left_bytes=', different.stdout)
            right.unlink()
            failed = run('failed')
            self.assertNotEqual(failed.returncode, 0)
            self.assertNotIn('cmp_exit=0', failed.stdout)


if __name__ == '__main__':
    unittest.main()
