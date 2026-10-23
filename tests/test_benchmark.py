import importlib.util
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
import test_signals
from unittest.mock import patch
from uuid import UUID

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark', PROJECT / 'scripts/benchmark.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
MODEL = 'dna_r10.4.1_e8.2_400bps_hac@v6.0.0'
A, B, C, D = [str(UUID(int=n)) for n in range(1, 5)]
BATCH_FALLBACK = ('[2026-10-22 15:06:44.119] [info] Failed to find optimal batch size for cuda:0. '
                  'Consider generating a benchmark with --run-batchsize-benchmarks, or loading an existing '
                  'benchmark with --batchsize-benchmarks-file')


class NativeLogTests(unittest.TestCase):
    def test_known_info_batch_fallback_is_separate_from_loader_diagnostics(self):
        effective = '[2026-10-22 15:07:00.107] [debug] cuda:0 using chunk size 12288, batch size 576'
        log = BATCH_FALLBACK + '\n' + effective + '\n'
        diagnostics = b.native_log_diagnostics(log)
        self.assertEqual(diagnostics['native_loader_error_lines'], [])
        self.assertEqual(diagnostics['batch_selection_diagnostics'], [BATCH_FALLBACK])
        self.assertEqual(diagnostics['batch_selection_status'], 'precomputed_benchmark_unavailable')
        self.assertEqual(diagnostics['effective_batch_chunk_log_lines'], [BATCH_FALLBACK, effective])

    def test_error_severity_other_failures_skips_and_changed_fallback_remain_unresolved(self):
        lines = [BATCH_FALLBACK.replace('[info]', '[error]'),
                 '[2026-10-22 15:06:44.119] [error] Failed to load POD5 input',
                 '[2026-10-22 15:06:44.119] [warning] Skipping unreadable input',
                 '[2026-10-22 15:06:44.119] [info] Failed to load read',
                 BATCH_FALLBACK + ' Additional failure',
                 BATCH_FALLBACK.replace('optimal batch size', 'requested batch size')]
        diagnostics = b.native_log_diagnostics('\n'.join([BATCH_FALLBACK] + lines))
        self.assertEqual(diagnostics['native_loader_error_lines'], lines)
        self.assertEqual(diagnostics['batch_selection_diagnostics'], [BATCH_FALLBACK])
        for line in lines:
            with self.subTest(line=line):
                diagnostics = b.native_log_diagnostics(line)
                self.assertEqual(diagnostics['native_loader_error_lines'], [line])
                self.assertEqual(diagnostics['batch_selection_diagnostics'], [])
                self.assertEqual(diagnostics['batch_selection_status'], 'no_known_fallback_diagnostic')


def header(reference=False):
    return ('@HD\tVN:1.6\tSO:unknown\n' + ('@SQ\tSN:chr1\tLN:200\n' if reference else '') +
            f'@RG\tID:run_model\tDS:runid=run basecall_model={MODEL}\n' +
            '@PG\tID:basecaller\tPN:dorado\tVN:2.1.2+8b8fc5d\tCL:fixture-adapter-test\n')


def record(name=A, seq='AACGTACGTA', qual='ABCDEFGHIJ', flag=4, pos=0, cigar='*', extra='', parent=None):
    tags = '\tRG:Z:run_model\tns:i:500\tts:i:10\tqs:f:20'
    if parent:
        tags += f'\tpi:Z:{parent}\tsp:i:0'
    return f'{name}\t{flag}\t{"chr1" if not flag & 4 else "*"}\t{pos}\t60\t{cigar}\t*\t0\t0\t{seq}\t{qual}{tags}{extra}\n'


@unittest.skipUnless(shutil.which('samtools'), 'samtools required for native fixtures')
class NativeBamTests(unittest.TestCase):
    def setUp(self):
        (PROJECT / 'logs').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.expected = {A: 1000, B: 1000}
        self.counter = 0

    def native(self, sam):
        self.counter += 1
        path = self.root / f'fixture-{self.counter}'
        path.with_suffix('.sam').write_text(sam)
        subprocess.run(['samtools', 'view', '-b', '-o', str(path.with_suffix('.bam')), str(path.with_suffix('.sam'))], check=True, capture_output=True)
        with path.with_suffix('.decoded.sam').open('wb') as out:
            subprocess.run(['samtools', 'view', '-h', str(path.with_suffix('.bam'))], check=True, stdout=out, stderr=subprocess.PIPE)
        return path.with_suffix('.decoded.sam'), path.with_suffix('.bam')

    def parse(self, sam, **kwargs):
        path, _ = self.native(sam)
        return b.parse_sam(path, MODEL, self.expected, **kwargs)

    def test_real_bam_parent_accounting_and_absence(self):
        full = self.parse(header() + record() + record(B))
        self.assertEqual(full['metrics']['represented_parents'], 2)
        self.assertEqual(full['metrics']['children'], 2)
        self.assertTrue(full['complete_processing'])
        removed = self.parse(header() + record())
        self.assertEqual(removed['missing_parents'], [B])
        self.assertEqual(removed['missing_reason'], 'unresolved')
        self.assertFalse(removed['complete_processing'])
        self.assertEqual(removed['scientific_endpoints']['biological_base_accuracy'], 'NOT VERIFIED')

    def test_foreign_duplicate_empty_wrong_model_and_version_rejected(self):
        for sam, error in [(header() + record(C), 'Foreign parent'),
                           (header() + record() * 2, 'Duplicate primary'),
                           (header(), 'No emitted'),
                           (header().replace(MODEL, 'wrong') + record(), 'Wrong model'),
                           (header().replace('VN:2.1.2+8b8fc5d', 'VN:2.0.0') + record(), 'Dorado version')]:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.parse(sam)

    def test_exact_stock_build_header_identity(self):
        for version in ('2.1.2', '2.1.2+0000000', '2.1.20+8b8fc5d', '2.1.2+8b8fc5d-dirty'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Dorado version'):
                self.parse(header().replace('VN:2.1.2+8b8fc5d', 'VN:' + version) + record())
        self.assertEqual(self.parse(header() + record())['metrics']['children'], 1)

    @unittest.skipUnless(os.environ.get('NANOPORE_NATIVE_BAM'), 'Set NANOPORE_NATIVE_BAM for retained native GPU evidence')
    def test_retained_native_stock_bam_build_identity(self):
        bam = Path(os.environ['NANOPORE_NATIVE_BAM']).resolve()
        self.assertEqual((bam.parent / 'exit-status.txt').read_text().strip(), '0')
        decoded = self.root / 'native-stock.sam'
        with decoded.open('wb') as out:
            subprocess.run(['samtools', 'view', '-h', str(bam)], stdout=out, stderr=subprocess.PIPE, check=True)
        members = set((PROJECT / 'data/splits/smoke.txt').read_text().splitlines())
        with (PROJECT / 'data/splits/read-inventory.tsv').open() as handle:
            inventory = {row['read_id']: int(row['num_samples']) for row in csv.DictReader(handle, delimiter='\t') if row['read_id'] in members}
        parsed = b.parse_sam(decoded, MODEL, inventory)
        self.assertEqual(parsed['metrics']['represented_parents'], 32)
        self.assertTrue(parsed['complete_processing'])
        native_log = (bam.parent / 'stderr').read_text()
        self.assertIn(BATCH_FALLBACK, native_log)
        diagnostics = b.native_log_diagnostics(native_log)
        self.assertEqual(diagnostics['native_loader_error_lines'], [])
        self.assertEqual(diagnostics['batch_selection_diagnostics'], [BATCH_FALLBACK])
        self.assertEqual(diagnostics['batch_selection_status'], 'precomputed_benchmark_unavailable')
        self.assertIn('[2026-10-22 15:07:00.107] [debug] cuda:0 using chunk size 12288, batch size 576',
                      diagnostics['effective_batch_chunk_log_lines'])
        original = decoded.read_text()
        self.assertIn('\tPN:dorado\tVN:2.1.2+8b8fc5d\t', original)
        for version in ('2.1.2', '2.1.2+0000000'):
            decoded.write_text(original.replace('VN:2.1.2+8b8fc5d', 'VN:' + version))
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Dorado version'):
                b.parse_sam(decoded, MODEL, inventory)

    def test_synthetic_split_tag_structure_and_overlap_controls(self):
        split = record(C, parent=A) + record(D, parent=A).replace('sp:i:0', 'sp:i:500')
        accepted = self.parse(header() + split)
        self.assertEqual(accepted['metrics']['children'], 2)
        self.assertEqual(accepted['metrics']['represented_parents'], 1)
        self.assertEqual(accepted['metrics']['split_parents'], 1)
        for bad, message in [(split.replace('sp:i:500', 'sp:i:499'), 'Overlapping'),
                             (split.replace('sp:i:500', 'sp:i:999'), 'Invalid split'),
                             (split.replace(f'\tpi:Z:{A}', ''), 'Foreign parent'),
                             (split + record(), 'Mixed split')]:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.parse(header() + bad)

    def test_strand_normalization_secondary_sequence_omission_and_counts(self):
        base = self.parse(header() + record() + record(B))['children']
        reverse = 'AACGTACGTA'.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
        alignment = header(True) + record(flag=0, pos=1, cigar='10=', extra='\tNM:i:0\tMD:Z:10')
        alignment += record(B, seq=reverse, qual='JIHGFEDCBA', flag=16, pos=30, cigar='6=1X3=', extra='\tNM:i:1\tMD:Z:6A3')
        alignment += record(B, seq='*', qual='*', flag=272, pos=60, cigar='10=', extra='\tNM:i:0\tMD:Z:10')
        parsed = self.parse(alignment, reference={'chr1': 200}, base=base)
        self.assertEqual(parsed['metrics']['records'], 3)
        self.assertEqual(parsed['metrics']['secondary'], 1)
        self.assertEqual(parsed['metrics']['mapped_children'], 2)
        self.assertAlmostEqual(parsed['reference_disagreement_proxy']['aggregate'], 1 / 20)
        for changed, reason in [(alignment.replace('JIHGFEDCBA', 'ABCDEFGHIJ'), 'Strand-normalized'),
                                (alignment.replace('LN:200', 'LN:201'), 'reference dictionary'),
                                (alignment.replace('NM:i:1', 'NM:i:2'), 'Inconsistent NM'),
                                (alignment.replace('ns:i:500', 'ns:i:499'), 'signal tags')]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.parse(changed, reference={'chr1': 200}, base=base)

    def test_native_rejects_cigar_query_mismatch(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.native(header(True) + record(flag=0, pos=1, cigar='11=', extra='\tNM:i:0\tMD:Z:11'))

    def test_cigar_clipping_and_proxy_arithmetic(self):
        seq = 'A' * 67
        base = self.parse(header() + record(seq=seq, qual='I' * 67))['children']
        parsed = self.parse(header(True) + record(seq=seq, qual='I' * 67, flag=0, pos=1,
                                                 cigar='5S20=1X10=2I10=3D15=4S', extra='\tNM:i:6\tMD:Z:20C20^AAA15'),
                            reference={'chr1': 200}, base=base)
        self.assertEqual(parsed['metrics']['cigar_S'], 9)
        self.assertEqual(parsed['metrics']['alignment_columns'], 61)
        self.assertEqual(parsed['metrics']['primary_aligned_query_bases'], 58)
        self.assertAlmostEqual(parsed['reference_disagreement_proxy']['aggregate'], 6 / 61)

    def test_native_calmd_detects_false_reference_disagreement(self):
        reference = self.root / 'reference.fa'
        reference.write_text('>chr1\n' + 'A' * 200 + '\n')
        base = self.parse(header() + record(seq='A' * 10))['children']
        sam, bam = self.native(header(True) + record(seq='A' * 10, flag=0, pos=1, cigar='10=', extra='\tNM:i:0\tMD:Z:9C0'))
        before = b.parse_sam(sam, MODEL, self.expected, {'chr1': 200}, base)
        fixed = self.root / 'calmd.sam'
        with fixed.open('wb') as out:
            subprocess.run(['samtools', 'calmd', str(bam), str(reference)], stdout=out, stderr=subprocess.PIPE, check=True)
        after = b.parse_sam(fixed, MODEL, self.expected, {'chr1': 200}, base)
        self.assertNotEqual(before['children'], after['children'])
        self.assertEqual(after['children'][A]['tags']['MD'], '10')
        with self.assertRaisesRegex(ValueError, 'MD structure'):
            b.verify_calmd(before['children'], after['children'], lambda regions: self.fail('Invalid MD reached faidx'))

    def ambiguity_fixture(self, deletion=False):
        reference = self.root / 'ambiguity.fa'
        reference.write_text('>chr1\nAY' + 'A' * 7 + 'W' + 'A' * 190 + '\n')
        sequence = 'A' * (9 if deletion else 10)
        base = self.parse(header() + record(seq=sequence, qual='I' * len(sequence)))['children']
        cigar, md, nm = ('1=1D7=1X', '1^N7N0', 2) if deletion else ('1=1X7=1X', '1N7N0', 2)
        sam, bam = self.native(header(True) + record(seq=sequence, qual='I' * len(sequence), flag=0, pos=1,
                                                    cigar=cigar, extra=f'\tNM:i:{nm}\tMD:Z:{md}'))
        corrected = self.root / 'ambiguity-calmd.sam'
        with corrected.open('wb') as out:
            subprocess.run(['samtools', 'calmd', str(bam), str(reference)], stdout=out, stderr=subprocess.PIPE, check=True)
        before = b.parse_sam(sam, MODEL, self.expected, {'chr1': 200}, base)['children']
        after = b.parse_sam(corrected, MODEL, self.expected, {'chr1': 200}, base)['children']
        return reference, before, after

    def reference_fetcher(self, reference, stage_root=None, execute=True):
        def fetch(regions):
            receipt = b.stage(stage_root or self.root / 'evidence', 'calmd-reference-iupac',
                              ['samtools', 'faidx', str(reference), *regions], {'reference': b.pin(reference)}, execute=execute)
            return receipt['stdout']
        return fetch

    def test_calmd_iupac_requires_native_coordinate_evidence_and_reuses_it(self):
        reference, before, after = self.ambiguity_fixture()
        result = b.verify_calmd(before, after, self.reference_fetcher(reference))
        self.assertFalse(result['exact_md_agreement'])
        self.assertTrue(result['all_other_primary_fields_equal'])
        self.assertEqual(result['md_reference_ambiguity_records'], 1)
        self.assertEqual(result['md_reference_ambiguity_bases'], 2)
        self.assertEqual([(v['reference_position_1based'], v['query_position_1based'], v['cigar_operation'], v['reference_base'])
                          for v in result['md_reference_ambiguity_exceptions']], [(2, 2, 'X', 'Y'), (10, 10, 'X', 'W')])
        self.assertEqual(b.verify_calmd(before, after, self.reference_fetcher(reference, execute=False)), result)
        self.assertEqual(len(list((self.root / 'evidence/calmd-reference-iupac').glob('*/start.json'))), 1)
        with self.assertRaisesRegex(ValueError, 'Missing retained stage'):
            b.verify_calmd(before, after, self.reference_fetcher(reference, self.root / 'missing', execute=False))
        exact = b.verify_calmd(after, after, lambda regions: self.fail('Exact MD invoked faidx'))
        self.assertTrue(exact['exact_md_agreement'])
        self.assertEqual(exact['md_reference_ambiguity_exceptions'], [])

    def test_calmd_iupac_deletion_preserves_structure_and_coordinates(self):
        reference, before, after = self.ambiguity_fixture(deletion=True)
        result = b.verify_calmd(before, after, self.reference_fetcher(reference))
        self.assertEqual([(v['reference_position_1based'], v['query_position_1based'], v['cigar_operation'], v['reference_base'])
                          for v in result['md_reference_ambiguity_exceptions']], [(2, None, 'D', 'Y'), (10, 9, 'X', 'W')])

    def test_calmd_iupac_rejects_canonical_counts_deletions_nm_and_other_fields(self):
        reference, before, after = self.ambiguity_fixture()
        changes = [('tags', 'MD', '1A7W0'), ('tags', 'MD', '2Y6W0'), ('tags', 'MD', '1^Y7W0'),
                   ('tags', 'NM', '3'), ('tags', 'qs', '21'), ('seq', None, 'C' + 'A' * 9),
                   ('qual', None, 'J' + 'I' * 9), ('alignment', 4, '59'), ('tag_types', 'NM', 'Z')]
        for field, key, value in changes:
            changed = json.loads(json.dumps(after))
            if key is None:
                changed[A][field] = value
            else:
                changed[A][field][key] = value
            with self.subTest(field=field, key=key, value=value), self.assertRaises(ValueError):
                b.verify_calmd(before, changed, lambda regions: self.fail('Invalid change reached faidx'))
        wrong = self.root / 'wrong.fa'
        wrong.write_text('>chr1\n' + 'A' * 200 + '\n')
        subprocess.run(['samtools', 'faidx', str(wrong)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, 'differs from pinned reference'):
            b.verify_calmd(before, after, self.reference_fetcher(wrong))
        with self.assertRaisesRegex(ValueError, 'Wrong faidx reference coordinates'):
            b.verify_calmd(before, after, lambda regions: reference)

    @unittest.skipUnless(os.environ.get('NANOPORE_CALMD_PLAN'), 'Set NANOPORE_CALMD_PLAN for retained validation ambiguity evidence')
    def test_retained_validation_calmd_iupac_and_native_reference(self):
        plan_path = Path(os.environ['NANOPORE_CALMD_PLAN']).resolve()
        plan = b.read(plan_path)
        unit = next(value for value in plan['units'] if value['id'] == 'full-validation-hac')
        directory = plan_path.parent / 'units' / unit['id']
        decoded = {}
        for stage in ('base-decode', 'aligned-decode', 'calmd-decode'):
            receipt = b.read(sorted((directory / stage).glob('*/finish.json'))[-1])
            self.assertEqual(receipt['status'], 'finished')
            b.check_pins(receipt['pins'])
            decoded[stage] = receipt['stdout']
        base = b.parse_sam(decoded['base-decode'], MODEL, unit['parents'])['children']
        before = b.parse_sam(decoded['aligned-decode'], MODEL, unit['parents'], plan['dictionary'], base)['children']
        after = b.parse_sam(decoded['calmd-decode'], MODEL, unit['parents'], plan['dictionary'], base)['children']
        reference = PROJECT / plan['config']['reference']
        self.assertTrue(any(Path(value['path']).resolve() == reference.resolve() and value['sha256'] == b.digest(reference)
                            for value in plan['pins']))
        result = b.verify_calmd(before, after, self.reference_fetcher(reference))
        self.assertEqual(result['primary_records_checked'], 2039)
        self.assertEqual(result['md_reference_ambiguity_records'], 2)
        self.assertEqual(result['md_reference_ambiguity_bases'], 7)
        self.assertFalse(result['exact_md_agreement'])
        self.assertEqual([(v['contig'], v['reference_position_1based'], v['reference_base']) for v in result['md_reference_ambiguity_exceptions']],
                         [('chr2', 233142970, 'Y'), ('chr2', 233143703, 'W'), ('chr2', 233143709, 'Y'),
                          ('chr2', 233143729, 'Y'), ('chr2', 233144847, 'K'), ('chr2', 233145086, 'W'), ('chr12', 122093260, 'Y')])
        receipt = b.read(next((self.root / 'evidence/calmd-reference-iupac').glob('*/finish.json')))
        print('Retained validation faidx recorder:', receipt['recorder'])

    def test_native_truncation_and_interior_corruption(self):
        _, bam = self.native(header() + record())
        truncated = self.root / 'truncated.bam'
        truncated.write_bytes(bam.read_bytes()[:-28])
        self.assertNotEqual(subprocess.run(['samtools', 'quickcheck', '-u', str(truncated)], capture_output=True).returncode, 0)
        corrupt = self.root / 'corrupt.bam'
        data = bytearray(bam.read_bytes())
        data[len(data) // 2] ^= 0xff
        corrupt.write_bytes(data)
        self.assertNotEqual(subprocess.run(['samtools', 'view', str(corrupt)], capture_output=True).returncode, 0)

    def test_native_summary_join_rejects_parent_and_count_changes(self):
        parsed = self.parse(header() + record())
        summary = self.root / 'summary.tsv'
        summary.write_text(f'read_id\tparent_read_id\tsequence_length_template\n{A}\t{A}\t10\n')
        b.verify_summary(summary, parsed)
        original = summary.read_text()
        summary.write_text(original.replace(f'{A}\t{A}', f'{A}\t{B}'))
        with self.assertRaisesRegex(ValueError, 'parent mismatch'):
            b.verify_summary(summary, parsed)
        summary.write_text(original.replace('\t10\n', '\t9\n'))
        with self.assertRaisesRegex(ValueError, 'sequence length'):
            b.verify_summary(summary, parsed)


class ReceiptFixture(unittest.TestCase):
    def setUp(self):
        (PROJECT / 'results').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='benchmark-tests-', dir=PROJECT / 'results')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'logs').mkdir()
        shutil.copy2(PROJECT / 'scripts/record-command.sh', self.root / 'scripts')
        self.root_patch = patch.object(b, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.sampler_patch = patch.object(b.shutil, 'which', return_value=None)
        self.sampler_patch.start()
        self.addCleanup(self.sampler_patch.stop)

class ControlledMeasurementTests(ReceiptFixture):
    def setUp(self):
        super().setUp()
        self.original_core_sampler = b.core_gpu_sample
        core = patch.object(b, 'core_gpu_sample', side_effect=self.valid_gpu)
        core.start()
        self.addCleanup(core.stop)

    def valid_gpu(self):
        return {'utc': b.utc(), 'monotonic_ns': b.time.monotonic_ns(), 'completed_monotonic_ns': b.time.monotonic_ns(),
                'exit': 0, 'stderr': '', 'stdout': 'timestamp, index, utilization.gpu [%], memory.used [MiB], power.draw [W], temperature.gpu, clocks.current.sm [MHz]\n2026/10/22 10:00:00, 0, 0 %, 5 MiB, 6.4 W, 32, 187 MHz\n'}

    def controlled_policy(self):
        return {**b.CONTROLLED_POLICY, 'cpu_affinity': sorted(os.sched_getaffinity(0))}

    def valid_host(self, policy, owned_pgid=None):
        return {'utc': b.utc(), 'monotonic_ns': b.time.monotonic_ns(), 'errors': [],
                'ac_online': '1', 'platform_profile': 'balanced', 'cpu_affinity': policy['cpu_affinity'],
                'owned_cpu_affinities': {}, 'foreign_gpu_compute_pids': [], 'loadavg': '0 0 0', 'proc_stat': 'cpu 1 2 3 4'}

    def snapshot_fixture(self, attempt, phase):
        b.write(attempt / f'gpu-state-{phase}.json', {'exit': 0, 'stdout': 'fixture state', 'utc': b.utc()})

    def test_controlled_tiny_process_has_boundaries_and_verified_reuse(self):
        policy = self.controlled_policy()
        argv = [sys.executable, '-c', "print('measured child')"]
        with patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture):
            receipt = b.stage(self.root / 'attempts', 'producer', argv, {}, measurement=policy)
        self.assertTrue(receipt['measurement_qualified'])
        samples = [json.loads(line) for line in Path(next(p['path'] for p in receipt['pins'] if Path(p['path']).name == 'host.jsonl')).read_text().splitlines()]
        self.assertEqual([sample['phase'] for sample in samples], ['before', 'after'])
        with patch.object(b, 'host_sample', side_effect=AssertionError('Verification sampled the current host')), patch.object(b.subprocess, 'Popen', side_effect=AssertionError('Verification launched a process')):
            self.assertEqual(b.stage(self.root / 'attempts', 'producer', argv, {}, measurement=policy, execute=False), receipt)
        host = next(Path(p['path']) for p in receipt['pins'] if Path(p['path']).name == 'host.jsonl')
        host.unlink()
        with self.assertRaisesRegex((ValueError, OSError), 'No such file|Changed evidence'):
            b.stage(self.root / 'attempts', 'producer', argv, {}, measurement=policy, execute=False)

    def test_unsupported_optional_gpu_field_does_not_abort_native_work(self):
        tool = self.root / 'scripts/nvidia-smi'
        tool.write_text(f'''#!{sys.executable}
import sys,time
query = next((arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--query-gpu=')), '')
if 'clocks_event_reasons.sw_thermal_slowdown' in query:
    print('unsupported alias', file=sys.stderr)
    raise SystemExit(2)
if '-q' in sys.argv:
    print('Enforced Power Limit : 100.00 W')
elif query:
    fields = query.split(',')
    names = {{'memory.used':'memory.used [MiB]', 'utilization.gpu':'utilization.gpu [%]', 'power.draw':'power.draw [W]', 'clocks.sm':'clocks.current.sm [MHz]'}}
    print(', '.join(names.get(field, field) for field in fields), flush=True)
    print(', '.join('100' if 'counter' in field or 'power.limit' in field else '0' for field in fields), flush=True)
    if '-l' in sys.argv:
        time.sleep(30)
''')
        tool.chmod(0o755)
        with patch.dict(os.environ, {'PATH': str(tool.parent) + os.pathsep + os.environ['PATH']}), patch.object(b.shutil, 'which', return_value=str(tool)), patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'core_gpu_sample', side_effect=self.original_core_sampler):
            receipt = b.stage(self.root / 'optional', 'producer', [sys.executable, '-c', "print('native success')"], {}, measurement=self.controlled_policy())
        self.assertTrue(receipt['measurement_qualified'])
        unsupported = next(Path(p['path']) for p in receipt['pins'] if Path(p['path']).name == 'clocks_event_reasons.sw_thermal_slowdown-support.json')
        self.assertEqual(b.read(unsupported)['exit'], 2)
        telemetry = b.process_resources(receipt)['gpu']['optional_telemetry']
        self.assertEqual(telemetry['clocks_event_reasons_counters.sw_power_cap']['delta'], 0)
        self.assertEqual(telemetry['enforced.power.limit']['raw_samples'][0], '100')

    def test_required_ac_profile_and_missing_telemetry_reject_before_launch(self):
        for field, value in [('ac_online', '0'), ('platform_profile', 'performance'), ('ac_online', None), ('loadavg', None), ('foreign_gpu_compute_pids', [123])]:
            with self.subTest(field=field, value=value):
                def invalid(policy, owned_pgid=None):
                    return {**self.valid_host(policy), field: value}
                marker = self.root / ('launched-' + field + str(value))
                argv = [sys.executable, '-c', f'from pathlib import Path; Path({str(marker)!r}).touch()']
                directory = self.root / ('reject-' + field + str(value))
                with patch.object(b, 'host_sample', side_effect=invalid), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), self.assertRaisesRegex(ValueError, 'interrupted'):
                    b.stage(directory, 'producer', argv, {}, measurement=self.controlled_policy())
                receipt = b.read(next((directory / 'producer').glob('*/finish.json')))
                self.assertFalse(marker.exists())
                self.assertFalse(receipt['measurement_qualified'])
                self.assertIsNone(receipt['exit'])
                self.assertIn(field if field != 'loadavg' else 'telemetry', receipt['failure'])

    def test_post_guard_change_and_during_change_retain_failed_attempt(self):
        for field, after in [('ac_online', '0'), ('platform_profile', 'performance')]:
            for duration in (0, 5):
                with self.subTest(field=field, duration=duration):
                    count = 0
                    def changed(policy, owned_pgid=None):
                        nonlocal count
                        count += 1
                        sample = self.valid_host(policy)
                        if count > 1:
                            sample[field] = after
                        return sample
                    directory = self.root / f'changed-{field}-{duration}'
                    argv = [sys.executable, '-c', f'import time; print("started", flush=True); time.sleep({duration})']
                    with patch.object(b, 'host_sample', side_effect=changed), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), self.assertRaisesRegex(ValueError, 'command_failed|interrupted'):
                        b.stage(directory, 'producer', argv, {}, measurement=self.controlled_policy())
                    receipt_path = next((directory / 'producer').glob('*/finish.json'))
                    receipt = b.read(receipt_path)
                    self.assertFalse(receipt['measurement_qualified'])
                    self.assertIn(field, receipt['failure'])
                    self.assertIsNotNone(receipt['native_launch_monotonic_ns'])
                    self.assertLess(receipt['elapsed_ns'] / 1e9, 4)
                    before = b.pin(receipt_path)
                    with self.assertRaisesRegex(ValueError, 'explicit --retry'):
                        b.stage(directory, 'producer', argv, {}, measurement=self.controlled_policy(), execute=False)
                    self.assertEqual(b.pin(receipt_path), before)

    def test_cooldown_is_retained_before_native_launch(self):
        policy = self.controlled_policy()
        with patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), patch.object(b, 'gpu_idle_sample', side_effect=lambda policy: {'idle': True, 'monotonic_ns': b.time.monotonic_ns()}):
            receipt = b.stage(self.root / 'cool', 'producer', [sys.executable, '-c', "print('cooled')"], {}, measurement=policy, gpu_start=True)
        preflight = next(Path(p['path']) for p in receipt['pins'] if Path(p['path']).name == 'preflight.jsonl')
        idle = [json.loads(line)['gpu'] for line in preflight.read_text().splitlines() if 'gpu' in json.loads(line)]
        self.assertEqual(len(idle), 3)
        self.assertTrue(all(sample['monotonic_ns'] < receipt['native_launch_monotonic_ns'] for sample in idle))
        self.assertGreater(receipt['native_launch_monotonic_ns'] - receipt['monotonic_ns'], 1.9e9)
        self.assertLess(b.process_resources(receipt)['native_wall_seconds'], 1)

    def test_retained_sample_gap_or_missing_boundary_cannot_qualify(self):
        policy = self.controlled_policy()
        directory = self.root / 'manual'
        directory.mkdir()
        host = directory / 'host.jsonl'
        before = {**self.valid_host(policy), 'phase': 'before', 'gpu_core': self.valid_gpu()}
        after = {**self.valid_host(policy), 'phase': 'after', 'gpu_core': self.valid_gpu(), 'monotonic_ns': before['monotonic_ns'] + 4_000_000_000}
        for samples, message in [([before], 'before/after'), ([before, after], 'continuous')]:
            host.write_text(''.join(json.dumps(sample) + '\n' for sample in samples))
            with self.assertRaisesRegex(ValueError, message):
                b.measurement_evidence({'measurement_policy': policy, 'measurement_qualified': True, 'pins': [b.pin(host)]}, policy)

    def test_core_gpu_failed_empty_or_nonnumeric_query_prevents_launch(self):
        invalid = [{'exit': 42}, {'stdout': ''}]
        for field, _, _ in b.GPU_CORE_FIELDS:
            row = self.valid_gpu()['stdout']
            columns = row.splitlines()[0].split(', ')
            cells = row.splitlines()[1].split(', ')
            for value in ('[N/A]', 'nan', 'inf', '', '9' * 400):
                altered = cells.copy()
                altered[columns.index(field)] = value
                invalid.append({'stdout': row.splitlines()[0] + '\n' + ', '.join(altered) + '\n'})
        for index, changes in enumerate(invalid):
            with self.subTest(changes=changes):
                directory = self.root / f'core-invalid-{index}'
                marker = directory / 'native-launched'
                with patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), patch.object(b, 'core_gpu_sample', side_effect=lambda: {**self.valid_gpu(), **changes}), self.assertRaisesRegex(ValueError, 'interrupted'):
                    b.stage(directory, 'producer', [sys.executable, '-c', f'from pathlib import Path; Path({str(marker)!r}).touch()'], {}, measurement=self.controlled_policy())
                receipt = b.read(next((directory / 'producer').glob('*/finish.json')))
                self.assertFalse(marker.exists())
                self.assertFalse(receipt['measurement_qualified'])
                samples = next(Path(item['path']) for item in receipt['pins'] if Path(item['path']).name == 'host.jsonl')
                self.assertEqual(json.loads(samples.read_text().splitlines()[0])['gpu_core']['exit'], changes.get('exit', 0))

    def test_real_core_query_exit42_or_empty_output_rejects_before_native(self):
        tool = self.root / 'scripts/nvidia-smi'
        for status in (42, 0):
            with self.subTest(query_exit=status):
                tool.write_text(f'#!/bin/sh\nexit {status}\n')
                tool.chmod(0o755)
                directory = self.root / f'real-core-query-{status}'
                marker = directory / 'native-launched'
                with patch.dict(os.environ, {'PATH': str(tool.parent) + os.pathsep + os.environ['PATH']}), patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), patch.object(b, 'core_gpu_sample', side_effect=self.original_core_sampler), self.assertRaisesRegex(ValueError, 'interrupted'):
                    b.stage(directory, 'producer', [sys.executable, '-c', f'from pathlib import Path; Path({str(marker)!r}).touch()'], {}, measurement=self.controlled_policy())
                receipt = b.read(next((directory / 'producer').glob('*/finish.json')))
                self.assertFalse(marker.exists())
                self.assertFalse(receipt['measurement_qualified'])
                host = next(Path(item['path']) for item in receipt['pins'] if Path(item['path']).name == 'host.jsonl')
                query = json.loads(host.read_text().splitlines()[0])['gpu_core']
                self.assertEqual(query['exit'], status)
                self.assertEqual(query['stdout'], '')

    def test_core_gpu_query_death_during_or_after_native_rejects_attempt(self):
        for duration in (0, 5):
            with self.subTest(duration=duration):
                calls = 0
                def failed_query():
                    nonlocal calls
                    calls += 1
                    return {**self.valid_gpu(), **({'exit': 42, 'stdout': '', 'stderr': 'query died'} if calls > 1 else {})}
                directory = self.root / f'core-dead-{duration}'
                with patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), patch.object(b, 'core_gpu_sample', side_effect=failed_query), self.assertRaisesRegex(ValueError, 'interrupted|command_failed'):
                    b.stage(directory, 'producer', [sys.executable, '-c', f'import time; time.sleep({duration})'], {}, measurement=self.controlled_policy())
                receipt = b.read(next((directory / 'producer').glob('*/finish.json')))
                self.assertFalse(receipt['measurement_qualified'])
                self.assertIn('core GPU query failed', receipt['failure'])
                self.assertLess(receipt['elapsed_ns'] / 1e9, 4)
                if duration == 0:
                    self.assertEqual(receipt['exit'], 0)

    def test_retained_core_gpu_gap_missing_csv_or_boundary_cannot_qualify(self):
        policy = self.controlled_policy()
        with patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture):
            receipt = b.stage(self.root / 'retained-core', 'producer', [sys.executable, '-c', "print('native')"], {}, measurement=policy)
        b.measurement_evidence(receipt, policy)
        host = next(Path(item['path']) for item in receipt['pins'] if Path(item['path']).name == 'host.jsonl')
        samples = [json.loads(line) for line in host.read_text().splitlines()]
        originals = host.read_text()
        samples[-1]['gpu_core']['monotonic_ns'] += 4_000_000_000
        samples[-1]['gpu_core']['completed_monotonic_ns'] += 4_000_000_000
        host.write_text(''.join(json.dumps(sample) + '\n' for sample in samples))
        with patch.object(b, 'core_gpu_sample', side_effect=AssertionError('Verification queried GPU')), self.assertRaisesRegex(ValueError, 'continuous core GPU'):
            b.measurement_evidence(receipt, policy)
        host.write_text(originals)
        with self.assertRaisesRegex(ValueError, 'bracket'):
            b.measurement_evidence({**receipt, 'native_end_monotonic_ns': receipt['native_launch_monotonic_ns'] - 1}, policy)
        gpu = next(Path(item['path']) for item in receipt['pins'] if Path(item['path']).name == 'gpu.csv')
        gpu.write_text('')
        with self.assertRaisesRegex(ValueError, 'core GPU CSV'):
            b.measurement_evidence(receipt, policy)

    def test_controlled_interrupt_retains_unqualified_evidence(self):
        original_sleep = b.time.sleep
        interrupted = False
        def interrupt_once(delay):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            original_sleep(delay)
        with patch.object(b, 'host_sample', side_effect=self.valid_host), patch.object(b, 'gpu_snapshot', side_effect=self.snapshot_fixture), patch.object(b.time, 'sleep', side_effect=interrupt_once), self.assertRaisesRegex(ValueError, 'interrupted|command_failed'):
            b.stage(self.root / 'interrupt', 'producer', [sys.executable, '-c', 'import time; time.sleep(30)'], {}, measurement=self.controlled_policy())
        receipt = b.read(next((self.root / 'interrupt/producer').glob('*/finish.json')))
        self.assertFalse(receipt['measurement_qualified'])
        self.assertIn('KeyboardInterrupt', receipt['failure'])

class ReceiptTests(ReceiptFixture):
    def test_relative_producer_pin_accepts_current_bytes_rejects_change(self):
        artifact = self.root / 'reference.fa'
        artifact.write_text('>chr1\nACGT\n')
        relative = {**b.pin(artifact), 'path': 'reference.fa'}
        b.check_pins([relative])
        artifact.write_text('>chr1\nAGGT\n')
        with self.assertRaisesRegex(ValueError, 'Changed evidence'):
            b.check_pins([relative])

    def test_current_observation_failure_retires_previous_success(self):
        unit = self.root / 'units/timing-1-hac'
        plan = {'sha256': 'fixed', 'units': [{'id': 'timing-1-hac', 'scope': 'timing', 'tier': 'hac'}]}
        observation = {'status': 'verified', 'plan': 'fixed', 'pins': [], 'verifier_sha256': '0' * 64,
                       'completed_ns': 1, 'basecall_process_wall_seconds': 2.0, 'complete_work_qualification': 'verified'}
        b.write(unit / 'observation.json', observation)
        self.assertEqual(b.report(plan, self.root)['timing']['hac']['successful'], 0)
        observation['verifier_sha256'] = b.digest(b.__file__)
        b.write(unit / 'observation.json', observation)
        self.assertEqual(b.report(plan, self.root)['timing']['hac']['successful'], 1)
        failure = {'status': 'observation_failed', 'completed_ns': 2, 'utc': '2026-10-22T21:43:59+00:00',
                   'error': 'Native calmd changed primary NM/MD or alignment', 'verifier_sha256': b.digest(b.__file__)}
        b.write(unit / 'observation-failure-2.json', failure)
        result = b.report(plan, self.root)
        self.assertEqual(result['timing']['hac']['successful'], 0)
        self.assertEqual(result['units'][0]['observation_failures'], [{**failure, 'path': str(unit / 'observation-failure-2.json'),
                                                                     'pin': b.pin(unit / 'observation-failure-2.json')}])
        self.assertEqual(result['native_process_attempt_counts'], {'total': 0})
        observation['completed_ns'] = 3
        b.write(unit / 'observation.json', observation)
        result = b.report(plan, self.root)
        self.assertEqual(result['timing']['hac']['successful'], 1)
        self.assertEqual(len(result['units'][0]['observation_failures']), 1)

    def test_retry_reports_all_executed_attempts_and_process_resources(self):
        marker = self.root / 'marker'
        argv = [sys.executable, '-c', f"from pathlib import Path; p=Path({str(marker)!r}); old=p.exists(); p.touch(); raise SystemExit(0 if old else 7)"]
        unit = self.root / 'units/timing-1-hac'
        with self.assertRaisesRegex(ValueError, 'command_failed'):
            b.stage(unit, 'basecall', argv, {})
        b.stage(unit, 'basecall', argv, {}, retry=True)
        b.write(unit / 'basecall/9999999999999999999/start.json', {'status': 'running', 'argv': argv})
        plan = {'sha256': 'fixed', 'units': [{'id': 'timing-1-hac', 'scope': 'timing', 'tier': 'hac'}]}
        result = b.report(plan, self.root)
        self.assertEqual(result['timing']['hac']['failed_basecall'], 2)
        attempts = result['units'][0]['stages']['basecall']['attempts']
        self.assertEqual([a['exit'] for a in attempts], [7, 0, None])
        self.assertEqual([a['superseded'] for a in attempts], [True, True, False])
        self.assertIn('host_max_rss_kib', attempts[0]['resources'])
        self.assertIn('native_wall_seconds', attempts[1]['resources'])

    def test_actual_gpu_query_row_with_units_projects_supported_fields(self):
        result = subprocess.run(['nvidia-smi', '--query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw,temperature.gpu,clocks.sm', '--format=csv'], capture_output=True, text=True, check=True)
        path = self.root / 'gpu.csv'
        path.write_text(result.stdout)
        projected = b.gpu_resources(path)
        self.assertGreater(projected['peak_memory_mib'], 0)
        self.assertIsNotNone(projected['peak_utilization_percent'])
        self.assertIsNotNone(projected['peak_power_watts'])
        path.write_text('memory.used [MiB], utilization.gpu [%], power.draw [W]\n294 MiB, 0 %, 6.84 W\n[N/A], [N/A], [Not Supported]\n')
        self.assertEqual(b.gpu_resources(path)['peak_memory_mib'], 294)
        self.assertEqual(b.gpu_resources(path)['peak_power_watts'], 6.84)
        self.assertEqual(b.gpu_resources(path)['unavailable_samples']['peak_power_watts'], 1)

    def preparation_fixture(self):
        for directory in ('config', 'provenance', 'data/raw', 'software/bin', 'software/archives', 'references', 'results'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        config = json.loads((PROJECT / 'config/stock-benchmark.json').read_text())
        assets = []
        helper = SimpleNamespace(root=self.root, read_ids={'development': [UUID(A), UUID(D)], 'validation': [UUID(B)], 'sealed_test': [UUID(C)]})
        for role in b.ROLES:
            asset = {'id': role, 'role': role, 'sample': 'HG002' if role != 'sealed_test' else 'HG005', 'flowcell': role, 'path': 'data/raw/' + role + '.pod5'}
            test_signals.SignalInspectionTests.write_pod5(helper, asset)
            assets.append({**asset, 'bytes': (self.root / asset['path']).stat().st_size})
        for tier, model in config['models'].items():
            archive = self.root / 'software/archives' / (Path(model).name + '.zip')
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr(Path(model).name + '/config.toml', 'stock=true')
                zipped.writestr(Path(model).name + '/weight.tensor', b'fixture-stock-weight')
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(self.root / 'models')
            assets.append({'id': 'model-' + tier, 'role': 'stock_model', 'model_name': Path(model).name,
                           'path': str(archive.relative_to(self.root)), 'bytes': archive.stat().st_size})
        reference = self.root / config['reference']
        fasta = self.root / 'references/input.fa'
        fasta.write_text('>chr1\n' + 'A' * 200 + '\n')
        with reference.open('wb') as out:
            subprocess.run(['bgzip', '-c', str(fasta)], stdout=out, check=True)
        subprocess.run(['samtools', 'faidx', str(reference)], capture_output=True, check=True)
        assets.append({'id': 'grch38', 'role': 'reference', 'path': config['reference'], 'bytes': reference.stat().st_size})
        b.write(self.root / 'config/assets.json', assets)
        b.write(self.root / 'provenance/assets.lock.json', [{**a, 'sha256': b.digest(self.root / a['path'])} for a in assets])
        shutil.copy2(PROJECT / 'scripts/inspect-signals.py', self.root / 'scripts')
        subprocess.run([sys.executable, str(self.root / 'scripts/inspect-signals.py')], capture_output=True, check=True)
        shutil.copy2(PROJECT / 'scripts/prepare-reference.py', self.root / 'scripts')
        shutil.copy2(PROJECT / 'software/bin/minimap2', self.root / 'software/bin/minimap2')
        config['samtools'] = '/usr/bin/samtools'
        config['split_fixture'] = str(PROJECT / config['split_fixture'])
        b.write(self.root / 'config/stock-benchmark.json', config)
        for tier, model in config['models'].items():
            for aligned in (False, True):
                sam = self.root / 'results' / (tier + ('-aligned.sam' if aligned else '-base.sam'))
                sam.write_text((header(aligned) + record(flag=0, pos=1, cigar='10=', extra='\tNM:i:0\tMD:Z:10') if aligned else header() + record()).replace(MODEL, Path(model).name))
                subprocess.run(['samtools', 'view', '-b', '-o', str(sam.with_suffix('.bam')), str(sam)], capture_output=True, check=True)
        dorado = self.root / config['dorado']
        dorado.write_text(f"#!{sys.executable}\nimport sys,subprocess\nfrom pathlib import Path\nr=Path({str(self.root)!r})\nif sys.argv[1]=='--version': print('2.1.2+8b8fc5d'); raise SystemExit\nif sys.argv[1]=='basecaller': tier='hac' if '_hac@' in sys.argv[2] else 'sup'; kind='base'\nelse: tier='hac' if b'_hac@' in subprocess.check_output(['samtools','view','-H',sys.argv[3]]) else 'sup'; kind='aligned'\nsys.stdout.buffer.write((r/'results'/(tier+'-'+kind+'.bam')).read_bytes())\n")
        dorado.chmod(0o755)
        producers = []
        for tier, model in config['models'].items():
            result = subprocess.run([str(self.root / 'scripts/record-command.sh'), 'fixture-' + tier, str(dorado), 'basecaller', str(self.root / model), str(self.root / assets[0]['path'])], capture_output=True, text=True, check=True)
            producers.append(Path(result.stdout.strip()) / 'stdout')
        command = [sys.executable, str(self.root / 'scripts/prepare-reference.py')]
        for producer in producers:
            command.extend(['--parity-bam', str(producer)])
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return config

    def prepared_plan(self, version='2.1.2+8b8fc5d'):
        def output(argv, **kwargs):
            if argv[-2:] == ['rev-parse', 'HEAD']:
                return b.SOURCE + '\n'
            if 'status' in argv:
                return ''
            return version if kwargs.get('text') else version.encode()
        with patch.object(b.subprocess, 'check_output', side_effect=output):
            return b.prepare(Path('config/stock-benchmark.json'), self.root / 'results/stock/plan')

    def test_prepare_real_pod5_zip_and_reference_producer_handoff(self):
        config = self.preparation_fixture()
        plan_path = self.prepared_plan()
        plan = b.load_plan(plan_path)
        self.assertEqual(len([u for u in plan['units'] if u['scope'] == 'full']), 6)
        self.assertEqual([u['tier'] for u in plan['units'] if u['scope'] == 'timing'], ['hac', 'sup', 'sup', 'hac', 'hac', 'sup', 'sup', 'hac', 'hac', 'sup'])
        self.assertEqual(next(u for u in plan['units'] if u['id'] == 'full-development-hac')['parents'], {A: 4, D: 5})
        fixture = next(u for u in plan['units'] if u['scope'] == 'fixture')
        self.assertEqual(sum(fixture['parents'].values()), 365157)
        reference_receipt = b.read(self.root / config['reference_receipt'])
        self.assertTrue(all(not Path(item['path']).is_absolute() for item in reference_receipt['pins']))
        b.check_pins(reference_receipt['pins'])
        artifact = self.root / reference_receipt['pins'][0]['path']
        artifact.write_bytes(artifact.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed evidence'):
            b.load_plan(plan_path)

    def test_full_development_timing_preserves_subsets_and_19_units(self):
        config = self.preparation_fixture()
        benchmark = self.root / 'data/splits/benchmark.txt'
        subset_pin = b.pin(benchmark)
        config.update(timing_workload='full-development', measurement_policy=b.CONTROLLED_POLICY)
        b.write(self.root / 'config/stock-benchmark.json', config)
        plan = b.load_plan(self.prepared_plan())
        development = next(unit for unit in plan['units'] if unit['id'] == 'full-development-hac')
        self.assertEqual(len(plan['units']), 19)
        for unit in [unit for unit in plan['units'] if unit['scope'] == 'timing']:
            self.assertEqual(unit['ids'], str(self.root / 'data/splits/development.txt'))
            self.assertEqual(unit['parents'], development['parents'])
        self.assertEqual(b.pin(benchmark), subset_pin)
        self.assertEqual(plan['environment']['cache'], 'warmed-filesystem')
        self.assertEqual(plan['config']['measurement_policy'], b.CONTROLLED_POLICY)

    def test_prepare_rejects_other_stock_binary_builds(self):
        self.preparation_fixture()
        for version in ('2.1.2', '2.1.2+0000000', '2.1.20+8b8fc5d', '2.1.2+8b8fc5d-dirty'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Dorado version'):
                self.prepared_plan(version)

    def test_prepare_rejects_short_full_membership_and_wrong_signal_metadata(self):
        self.preparation_fixture()
        membership = self.root / 'data/splits/development.txt'
        original = membership.read_text()
        membership.write_text(A + '\n')
        with self.assertRaisesRegex(ValueError, 'Full membership'):
            self.prepared_plan()
        membership.write_text(original)
        inventory = self.root / 'data/splits/read-inventory.tsv'
        original_inventory = inventory.read_text()
        inventory.write_text(original_inventory.replace('\t4\t5000\t', '\t400\t5000\t', 1))
        with self.assertRaisesRegex(ValueError, 'POD5 metadata'):
            self.prepared_plan()
        inventory.write_text(original_inventory)
        summary = self.root / 'provenance/signal-inventory.json'
        values = b.read(summary)
        original_summary = json.loads(json.dumps(values))
        values[0]['signal_samples'] += 1
        b.write(summary, values)
        with self.assertRaisesRegex(ValueError, 'Signal receipt'):
            self.prepared_plan()
        b.write(summary, original_summary)
        assets = [a for a in b.read(self.root / 'config/assets.json') if a['role'] in b.ROLES]
        helper = SimpleNamespace(root=self.root, read_ids={'development': [UUID(A), UUID(D)]})
        test_signals.SignalInspectionTests.write_pod5(helper, assets[0], sample_rate=4000)
        with self.assertRaisesRegex(ValueError, 'POD5 chemistry'):
            b.signal_census(assets, inventory, summary)

    def test_prepare_rejects_changed_stock_extraction_and_incomplete_parity(self):
        config = self.preparation_fixture()
        model = self.root / config['models']['hac'] / 'weight.tensor'
        original = model.read_bytes()
        model.write_bytes(b'changed-before-prepare')
        with self.assertRaisesRegex(ValueError, 'differs from stock ZIP'):
            self.prepared_plan()
        model.write_bytes(original)
        extra = model.parent / 'extra.tensor'
        extra.write_bytes(b'unarchived')
        with self.assertRaisesRegex(ValueError, 'file census mismatch'):
            self.prepared_plan()
        extra.unlink()
        model.unlink()
        with self.assertRaisesRegex(ValueError, 'file census mismatch'):
            self.prepared_plan()
        model.write_bytes(original)
        receipt_path = self.root / config['index_receipt']
        receipt = b.read(receipt_path)
        original_receipt = json.loads(json.dumps(receipt))
        receipt['parity'] = ['fixture receipt']
        b.write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'both stock tiers'):
            self.prepared_plan()
        receipt = json.loads(json.dumps(original_receipt))
        receipt['parity'] = receipt['parity'][:1]
        b.write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'both stock tiers'):
            self.prepared_plan()
        receipt = json.loads(json.dumps(original_receipt))
        entry = receipt['parity'][0]
        entry['pins'] = [item for item in entry['pins'] if item['path'] != entry['input_decode']['path']]
        b.write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'Unpinned nested'):
            self.prepared_plan()
        receipt = json.loads(json.dumps(original_receipt))
        receipt['parity'][0]['mapped_records'] = 0
        b.write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'Unqualified tier'):
            self.prepared_plan()
        b.write(receipt_path, original_receipt)
        nested = self.root / original_receipt['parity'][0]['input_decode']['path']
        nested.write_text(nested.read_text() + 'changed')
        with self.assertRaisesRegex(ValueError, 'Changed evidence'):
            self.prepared_plan()

    def test_report_cannot_promote_changed_or_missing_evidence(self):
        artifact = self.root / 'retained.bam'
        artifact.write_bytes(b'producer-output')
        plan = {'sha256': 'fixed', 'units': [{'id': 'timing-1-hac', 'scope': 'timing', 'tier': 'hac'}]}
        observation = {'status': 'verified', 'plan': 'fixed', 'pins': [b.pin(artifact)],
                       'basecall_process_wall_seconds': 2.0, 'complete_work_qualification': 'verified', 'verifier_sha256': b.digest(b.__file__), 'completed_ns': 1}
        b.write(self.root / 'units/timing-1-hac/observation.json', observation)
        result = b.report(plan, self.root)
        self.assertEqual(result['timing']['hac']['successful'], 1)
        artifact.unlink()
        result = b.report(plan, self.root)
        self.assertEqual(result['timing']['hac']['successful'], 0)
        self.assertTrue(result['units'][0]['status'].startswith('evidence_changed'))

    def test_success_reuse_is_hash_verified_without_relaunch(self):
        argv = [sys.executable, '-c', "print('genuine producer stdout')"]
        first = b.stage(self.root / 'attempts', 'producer', argv, {'model': 'pinned'})
        self.assertEqual(first['status'], 'finished')
        self.assertTrue(Path(first['stdout']).is_file())
        with patch.object(b.subprocess, 'Popen', side_effect=AssertionError('Producer relaunched')):
            second = b.stage(self.root / 'attempts', 'producer', argv, {'model': 'pinned'})
        self.assertEqual(first, second)
        projection = self.root / 'projection.json'
        b.write(projection, {'derived': Path(second['stdout']).read_text()})
        projection.unlink()
        reused = b.stage(self.root / 'attempts', 'producer', argv, {'model': 'pinned'}, execute=False)
        b.write(projection, {'derived': Path(reused['stdout']).read_text()})
        self.assertIn('genuine producer', b.read(projection)['derived'])
        Path(first['stdout']).write_text('mutated')
        with self.assertRaisesRegex(ValueError, 'Changed evidence'):
            b.stage(self.root / 'attempts', 'producer', argv, {'model': 'pinned'}, retry=True)

    def test_wrong_model_or_parent_pin_changes_stage_identity(self):
        argv = [sys.executable, '-c', "print('one')"]
        b.stage(self.root / 'attempts', 'producer', argv, {'model': 'pinned', 'parent': 'abc'})
        for context in [{'model': 'wrong', 'parent': 'abc'}, {'model': 'pinned', 'parent': 'wrong'}]:
            with self.assertRaisesRegex(ValueError, 'Changed stage identity'):
                b.stage(self.root / 'attempts', 'producer', argv, context)

    def test_failed_stage_requires_explicit_retry_preserves_first_receipt(self):
        argv = [sys.executable, '-c', 'raise SystemExit(7)']
        with self.assertRaisesRegex(ValueError, 'command_failed'):
            b.stage(self.root / 'attempts', 'producer', argv, {})
        first = sorted((self.root / 'attempts/producer').glob('*/finish.json'))
        self.assertEqual(b.read(first[0])['exit'], 7)
        with self.assertRaisesRegex(ValueError, 'explicit --retry'):
            b.stage(self.root / 'attempts', 'producer', argv, {})
        self.assertEqual(len(list((self.root / 'attempts/producer').glob('*/start.json'))), 1)
        with self.assertRaisesRegex(ValueError, 'command_failed'):
            b.stage(self.root / 'attempts', 'producer', argv, {}, retry=True)
        self.assertEqual(len(list((self.root / 'attempts/producer').glob('*/start.json'))), 2)
        self.assertEqual(b.read(first[0])['exit'], 7)

    def test_interrupted_stage_cannot_qualify(self):
        argv = [sys.executable, '-c', "print('real child')"]
        directory = self.root / 'attempts/producer/100'
        b.write(directory / 'start.json', {'key': b.identity({'argv': argv, 'context': {}}), 'status': 'running'})
        with self.assertRaisesRegex(ValueError, 'Failed/interrupted'):
            b.stage(self.root / 'attempts', 'producer', argv, {})
        with self.assertRaisesRegex(ValueError, 'Missing retained'):
            b.stage(self.root / 'attempts', 'producer', argv, {}, retry=True, execute=False)
        self.assertFalse((directory / 'finish.json').exists())

    def test_real_child_interrupt_records_noncompletion(self):
        original_sleep = b.time.sleep
        interrupted = False
        def interrupt_once(delay):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            original_sleep(delay)
        with patch.object(b.time, 'sleep', side_effect=interrupt_once):
            with self.assertRaisesRegex(ValueError, 'command_failed|interrupted'):
                b.stage(self.root / 'attempts', 'producer', [sys.executable, '-c', 'import time; time.sleep(30)'], {})
        receipt = b.read(next((self.root / 'attempts/producer').glob('*/finish.json')))
        self.assertNotEqual(receipt['status'], 'finished')
        self.assertEqual(receipt['failure'], 'KeyboardInterrupt')

    def test_changed_plan_or_reference_pin_rejected(self):
        reference = self.root / 'reference.fa'
        reference.write_text('>chr1\nACGT\n')
        plan = {'pins': [b.pin(reference)], 'config': {}}
        plan['sha256'] = b.identity(plan)
        path = self.root / 'plan.json'
        b.write(path, plan)
        self.assertEqual(b.load_plan(path), plan)
        reference.write_text('>chr1\nAGGT\n')
        with self.assertRaisesRegex(ValueError, 'Changed evidence'):
            b.load_plan(path)
        plan['config']['reference'] = 'wrong'
        b.write(path, plan)
        with self.assertRaisesRegex(ValueError, 'Changed plan'):
            b.load_plan(path)


if __name__ == '__main__':
    unittest.main()
