"""Hermetic native gzip/SHA controls. Execute only under Root's fresh bounded engineering grant."""
import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/stock_feedback'))
import bounded as b
import resource_attestation as r


class ResourceAttestation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = b.read(Path(r.__file__).parent / 'resource-attestation-hg002-v1.json')['tools']

    def raw(self, name, argv, stdout=b'', stderr=b''):
        directory = self.root / name
        directory.mkdir()
        values = {'command.sh': (shlex.join(argv) + '\n').encode(), 'cwd.txt': (str(self.root) + '\n').encode(),
                  'start.txt': b'2026-01-01T00:00:00Z\n', 'end.txt': b'2026-01-01T00:00:01Z\n',
                  'exit-status.txt': b'0\n', 'time.txt': b'Exit status: 0\n', 'stdout': stdout, 'stderr': stderr}
        for key, value in values.items():
            (directory / key).write_bytes(value)
        return [b.pin(directory / key) for key in values]

    def save(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value))
        return b.pin(path)

    def fixture(self, sequence=b'AAAA'):
        reference = self.root / 'reference.fa'
        reference.write_bytes(b'>chr1\nAAAA\n')
        compressed = self.root / 'reference.fa.gz'
        compressed.write_bytes(gzip.compress(b'>chr1\n' + sequence + b'\n', mtime=0))
        mmi = self.root / 'reference.mmi'
        mmi.write_bytes(b'synthetic registered index bytes')
        resources = dict(compressed=b.pin(compressed), reference=b.pin(reference), mmi=b.pin(mmi))
        for role in ('fai', 'publisher_fai', 'registered_fai'):
            path = self.root / (role + '.fai')
            path.write_text('chr1\t4\t6\t4\t5\n')
            resources[role] = b.pin(path)
        historical_tool = self.root / 'legacy-minimap2'
        historical_tool.write_text('not executable; historical identity fixture only')
        index_argv = [str(historical_tool), '-x', 'lr:hq', '-I', '16G', '-t', '16', '-d',
                      str(self.root / 'missing-old-index.mmi'), str(compressed)]
        index_raw = self.raw('index-old', index_argv, stderr=b'old stderr\n')
        build = dict(pins=[resources['mmi']], reference_sha256=resources['compressed']['sha256'],
                     producer_run='index-old', producer_pins=[*index_raw, b.pin(historical_tool)])
        reference_qualified = dict(status='verified', pins=[resources['compressed'], resources['publisher_fai']],
                                   dictionary={'chr1': 4}, contigs=1, reference_bases=4)
        decomp_argv = ['gzip', '-cd', compressed.name]
        decomp_raw = self.raw('decompress-old', decomp_argv, stdout=reference.read_bytes())
        # The retained decompressor output is the current reference artifact, just as production D/stdout is.
        resources['reference'] = next(p for p in decomp_raw if Path(p['path']).name == 'stdout')
        fai_argv = ['/usr/bin/samtools', 'faidx', '--fai-idx', resources['registered_fai']['path'], resources['reference']['path']]
        fai_raw = self.raw('fai-old', fai_argv)
        fai = dict(status='finished', exit=0, failure=None, native_launch_monotonic_ns=1,
                   native_end_monotonic_ns=2, argv=fai_argv, recorder=str(self.root / 'fai-old'),
                   stdout=str(self.root / 'fai-old/stdout'), pins=fai_raw, context={'sources': []})
        return dict(schema='prefix-legacy-resource-request/1', purpose='hermetic-control', legacy_root=str(self.root),
                    fai_cwd=str(self.root), samtools_path='/usr/bin/samtools', resources=resources, tools=self.tools,
                    index_argv=index_argv, decompress_argv=decomp_argv, decompress_raw=decomp_raw,
                    registries=dict(index_built=self.save('index-built.json', build),
                        index_qualified=self.save('index-qualified.json', dict(status='verified', build=build, pins=[resources['mmi']])),
                        reference_qualified=self.save('reference-qualified.json', reference_qualified),
                        fai_finish=self.save('fai-finish.json', fai)))

    def run_case(self, spec, name='attestation'):
        return r.verify(spec, self.root / name)

    def cli_grant(self, spec):
        spec_pin = self.save('request.json', spec)
        grant_path = self.root / 'grant.json'
        argv = [str(Path(r.__file__).resolve()), 'verify', '--spec', spec_pin['path'],
                '--grant', str(grant_path), '--output', str(self.root / 'attestation')]
        now = datetime.now(timezone.utc)
        sources = [b.pin(path) for path in (r.__file__, r.legacy.__file__, b.__file__, b.GUARD['path'],
                                            sys.executable, '/home/jake/.local/bin/uv')]
        sources += list(spec['tools'].values())
        inputs = [spec_pin, *r.admitted_inputs(spec)]
        expected = str(self.root / 'attestation/complete.json')
        grant = dict(schema='bounded-command/1', id='synthetic-source-admission',
                     not_before_utc=(now - timedelta(seconds=1)).isoformat(),
                     expires_utc=(now + timedelta(seconds=299)).isoformat(), wall_seconds=300,
                     profile='engineering', memory_bytes=4 * 1024**3, address_space_bytes=8 * 1024**3,
                     cpus=2, swap_bytes=0, growth_bytes=100 * 1024**2, aggregate_bytes=4 * 1024**3,
                     reserve_bytes=30 * 1024**3, root=str(Path.cwd()), cwd=str(Path.cwd()),
                     argv=['/home/jake/.local/bin/uv', 'run', '--project',
                           '/home/jake/Projects/nanopore_basecaller-retrieval', '--no-sync', 'python', *argv],
                     env=dict(UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv',
                              UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1',
                              LC_ALL='C', TMPDIR=str(self.root)), output_roots=[str(self.root)],
                     source_pins=sources, input_pins=inputs, expected_files=[expected],
                     roles=dict(unit='F4/resource-attestation', inputs={str(i): i for i in range(len(inputs))},
                                outputs={'attestation': expected}))
        # This is a boundary fixture, never a Root execution authorization or kernel receipt.
        b.validate(grant)
        r.require_admitted_sources(grant, spec)
        return argv, grant_path, grant

    def assert_main_source_rejection(self, argv, grant_path, grant, path):
        grant_path.write_text(json.dumps(grant))
        # No kernel predicate is mocked: the real source guard must reject before that boundary.
        with patch.object(sys, 'argv', argv), patch.object(r, 'verify') as verify:
            with self.assertRaisesRegex(ValueError, 'attestation source is not admitted: ' + path):
                r.main()
            verify.assert_not_called()
        self.assertFalse((self.root / 'attestation').exists())

    def test_root_shaped_source_closure_positive(self):
        self.cli_grant(self.fixture())

    def test_main_rejects_missing_actual_verifier_or_imported_legacy_source(self):
        argv, grant_path, grant = self.cli_grant(self.fixture())
        for path in (r.__file__, r.legacy.__file__):
            with self.subTest(source=path):
                changed = dict(grant, source_pins=[p for p in grant['source_pins'] if p['path'] != path])
                self.assert_main_source_rejection(argv, grant_path, changed, path)

    def test_main_rejects_declared_source_hash_corruption(self):
        argv, grant_path, grant = self.cli_grant(self.fixture())
        for path in (r.__file__, r.legacy.__file__):
            with self.subTest(source=path):
                changed = dict(grant, source_pins=[dict(p, sha256='0' * 64) if p['path'] == path else p
                                                  for p in grant['source_pins']])
                self.assert_main_source_rejection(argv, grant_path, changed, path)

    def test_genuine_native_pipeline_positive_keeps_old_terminal_unqualified(self):
        spec = self.fixture()
        proof = self.run_case(spec)
        self.assertEqual(proof['stream']['bytes'], spec['resources']['reference']['size'])
        self.assertEqual(proof['stream']['sha256'], spec['resources']['reference']['sha256'])
        self.assertEqual(proof['stream']['exits'], {'gzip': 0, 'sha256': 0})
        self.assertEqual(proof['legacy']['contig_names_lengths'], {'chr1': 4})
        self.assertFalse(proof['historical_index_terminal'] or proof['historical_admission_requalified'])
        self.assertIsNone(proof['historical_index_controller_source_pin'])
        self.assertFalse(proof['new_index_built'] or proof['new_fai_built'])
        self.assertTrue((self.root / 'attestation/terminal.json').is_file())
        self.assertTrue(all(row['terminal'] for row in proof['stream']['cleanup'].values()))
        self.assertLess((self.root / 'attestation/sha256/stdout').stat().st_size, 128)
        self.assertFalse((self.root / 'attestation/gzip/stdout').exists())

    def test_independent_valid_B_gzip_A_reference_pass_pins_then_fail_deep_digest(self):
        spec = self.fixture(sequence=b'TTTT')
        # Same qualified full-pin primitive as Root's input gate; neither pin is deliberately corrupted.
        b.check(spec['resources']['compressed'])
        b.check(spec['resources']['reference'])
        with self.assertRaisesRegex(ValueError, 'gzip stream digest differs from current reference'):
            self.run_case(spec)
        terminal = b.read(self.root / 'attestation/terminal.json')
        self.assertTrue(terminal['checks']['current_pins_verified'])
        self.assertTrue(terminal['checks']['legacy_custody_verified'])
        self.assertTrue(terminal['checks']['stream_size_verified'])
        self.assertFalse(terminal['checks']['stream_digest_verified'])
        self.assertEqual(terminal['phase'], 'equivalence')
        self.assertEqual(terminal['stream']['exits'], {'gzip': 0, 'sha256': 0})
        self.assertFalse((self.root / 'attestation/complete.json').exists())
        self.assertTrue((self.root / 'attestation/failed.json').is_file())

    def test_missing_old_raw_rejects_without_native_replay(self):
        spec = self.fixture()
        (self.root / 'index-old/time.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'time.txt'):
            self.run_case(spec)
        self.assertFalse((self.root / 'attestation/gzip').exists())
        self.assertEqual(b.read(self.root / 'attestation/failed.json')['phase'], 'legacy-custody')

    def test_native_gzip_failure_retains_both_actual_terminal_statuses(self):
        spec = self.fixture()
        compressed = Path(spec['resources']['compressed']['path'])
        compressed.write_bytes(b'not a gzip stream')
        spec['resources']['compressed'] = b.pin(compressed)
        build = b.read(spec['registries']['index_built']['path'])
        build['reference_sha256'] = spec['resources']['compressed']['sha256']
        spec['registries']['index_built'] = self.save('index-built.json', build)
        spec['registries']['index_qualified'] = self.save('index-qualified.json', dict(status='verified', build=build,
                                                                                    pins=[spec['resources']['mmi']]))
        qualified = b.read(spec['registries']['reference_qualified']['path'])
        qualified['pins'][0] = spec['resources']['compressed']
        spec['registries']['reference_qualified'] = self.save('reference-qualified.json', qualified)
        with self.assertRaisesRegex(ValueError, 'native pipeline execution failed'):
            self.run_case(spec)
        gzip_status = b.read(self.root / 'attestation/gzip/terminal.json')
        sha_status = b.read(self.root / 'attestation/sha256/terminal.json')
        self.assertTrue(gzip_status['exit_known'] and sha_status['exit_known'])
        self.assertNotEqual(gzip_status['recorder_exit'], 0)
        self.assertEqual(sha_status['recorder_exit'], 0)
        self.assertGreater((self.root / 'attestation/gzip/stderr').stat().st_size, 0)
        self.assertTrue((self.root / 'attestation/failed.json').exists())
        self.assertFalse((self.root / 'attestation/complete.json').exists())

    def test_changed_old_stderr_reaches_metadata_hash_guard(self):
        spec = self.fixture()
        (self.root / 'index-old/stderr').write_bytes(b'bad stderr\n')
        with self.assertRaisesRegex(ValueError, 'metadata hash differs: .*stderr'):
            self.run_case(spec)
        self.assertFalse((self.root / 'attestation/gzip').exists())

    def test_independently_repinned_wrong_old_cwd_reaches_cwd_guard(self):
        spec = self.fixture()
        cwd = self.root / 'index-old/cwd.txt'
        cwd.write_text('/wrong-old-cwd\n')
        build = b.read(spec['registries']['index_built']['path'])
        build['producer_pins'] = [b.pin(cwd) if p['path'] == str(cwd) else p for p in build['producer_pins']]
        spec['registries']['index_built'] = self.save('index-built.json', build)
        spec['registries']['index_qualified'] = self.save('index-qualified.json', dict(status='verified', build=build,
                                                                                    pins=[spec['resources']['mmi']]))
        with self.assertRaisesRegex(ValueError, 'raw cwd differs'):
            self.run_case(spec)
        self.assertTrue(b.read(self.root / 'attestation/terminal.json')['checks']['current_pins_verified'])
        self.assertFalse((self.root / 'attestation/gzip').exists())

    def test_repinned_registry_cannot_rebind_actual_current_MMI(self):
        spec = self.fixture()
        build = b.read(spec['registries']['index_built']['path'])
        build['pins'][0]['sha256'] = 'f' * 64
        spec['registries']['index_built'] = self.save('index-built.json', build)
        with self.assertRaisesRegex(ValueError, 'registered final MMI pin differs'):
            self.run_case(spec)
        self.assertTrue(b.read(self.root / 'attestation/terminal.json')['checks']['current_pins_verified'])
        self.assertFalse((self.root / 'attestation/gzip').exists())

    def test_full_contig_identity_not_just_length_total_is_required(self):
        spec = self.fixture()
        qualified = b.read(spec['registries']['reference_qualified']['path'])
        qualified['dictionary'] = {'wrong-contig': 4}
        spec['registries']['reference_qualified'] = self.save('reference-qualified.json', qualified)
        with self.assertRaisesRegex(ValueError, 'full FAI contig map differs'):
            self.run_case(spec)
        self.assertFalse((self.root / 'attestation/gzip').exists())

    def test_admitted_inputs_deduplicate_reference_raw_alias(self):
        spec = self.fixture()
        values = r.admitted_inputs(spec)
        self.assertEqual(len(values), len({p['path'] for p in values}))
        self.assertEqual(values.count(spec['resources']['reference']), 1)
        self.assertIn(spec['registries']['fai_finish'], values)


if __name__ == '__main__':
    unittest.main()
