"""Independent bounded protocol/projection controls; no real tensor or graph load."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v2/tools/context_decoder/guarded_inputs.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path):
    return dict(path=str(path), size=path.stat().st_size, sha256=digest(path))


def fixture(reverse=False):
    reference = 'A' * 10 + 'CGTT' + 'A' * 10
    window = dict(query_index=0, contig='chr1', ref_start=100, ref_end=124, reverse=reverse)
    walk = dict(is_reference=True, both_anchors=True, sequence=reference, cigar='24M', copy_count=None)
    graph = dict(schema='hprc-local-paths/1', query_index=0,
                 query=dict(sample='GRCh38', contig='chr1', start=100, end=124),
                 reference=dict(start=100, end=124, sequence=reference), boundary_nodes=['>1', '>2'], walks=[walk])
    return window, graph


class Projection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ['UNCERTAINTY_FEEDBACK_BINARY']
        spec = importlib.util.spec_from_file_location('unchanged_targeting_projection_oracle', ORIGINAL)
        cls.oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.oracle)
        if Path(cls.oracle.__file__).resolve() != ORIGINAL or cls.oracle.ROOT != ORIGINAL.parents[2]:
            raise AssertionError('Original projection oracle relocated')

    def run_projection(self, window, graph, raw=None):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            request = directory / 'request.json'
            request.write_text(raw if raw is not None else json.dumps(dict(window=window, graph=graph)))
            output = directory / 'output'
            process = subprocess.run([self.binary, 'project', '--request', str(request), '--request-sha256', digest(request),
                                      '--output', str(output)], capture_output=True, text=True, timeout=15)
            result = json.loads((output / 'complete.json').read_text()) if process.returncode == 0 else None
            return process, result

    def compare(self, window, graph):
        expected, exclusions = self.oracle.project_centers(window, graph)
        process, result = self.run_projection(window, graph)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(result['centers'], expected)
        self.assertEqual(result['exclusions'], exclusions)

    def test_forward_and_reverse_match_unchanged_oracle(self):
        for reverse in (False, True):
            self.compare(*fixture(reverse))

    def test_empty_deletion_center_preserved_both_strands(self):
        for reverse in (False, True):
            window, graph = fixture(reverse)
            graph['walks'].append(dict(is_reference=False, both_anchors=True, sequence='A' * 20, cigar='10M4D10M', copy_count=1))
            self.compare(window, graph)

    def test_insertion_boundary_ownership_matches_oracle(self):
        for cigar, sequence in (('10M1I14M', 'A' * 10 + 'GCGTT' + 'A' * 10),
                                ('14M1I10M', 'A' * 10 + 'CGTTG' + 'A' * 10)):
            window, graph = fixture()
            graph['walks'].append(dict(is_reference=False, both_anchors=True, sequence=sequence, cigar=cigar, copy_count=1))
            self.compare(window, graph)

    def test_unanchored_walk_and_deleted_boundary_exclusions(self):
        window, graph = fixture()
        graph['walks'].append(dict(is_reference=False, both_anchors=False, sequence='A', cigar='*', copy_count=None))
        graph['walks'].append(dict(is_reference=False, both_anchors=True, sequence='A' * 9 + 'CGTT' + 'A' * 10,
                                 cigar='9M1D14M', copy_count=None))
        self.compare(window, graph)

    def test_full_center_length_108_preserved(self):
        window, graph = fixture()
        graph['walks'].append(dict(is_reference=False, both_anchors=True, sequence='A' * 10 + 'C' * 108 + 'A' * 10,
                                 cigar='10M104I14M', copy_count=1))
        self.compare(window, graph)

    def test_center_length_109_rejects(self):
        window, graph = fixture()
        graph['walks'].append(dict(is_reference=False, both_anchors=True, sequence='A' * 10 + 'C' * 109 + 'A' * 10,
                                 cigar='10M105I14M', copy_count=1))
        with self.assertRaises(ValueError):
            self.oracle.project_centers(window, graph)
        process, _ = self.run_projection(window, graph)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('Guarded center context bound', process.stderr)

    def test_unique_path_cap_rejects_instead_of_truncating(self):
        window, graph = fixture()
        for number in range(33):
            center = ''.join('ACGT'[(number >> shift) & 3] for shift in (6, 4, 2, 0))
            graph['walks'].append(dict(is_reference=False, both_anchors=True, sequence='A' * 10 + center + 'A' * 10,
                                     cigar='24M', copy_count=1))
        with self.assertRaises(ValueError):
            self.oracle.project_centers(window, graph)
        process, _ = self.run_projection(window, graph)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('unique context cap', process.stderr)

    def test_duplicate_json_key_rejected(self):
        process, _ = self.run_projection(*fixture(), raw='{"window":{},"window":{},"graph":{}}')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('Duplicate JSON', process.stderr)

    def test_wrong_query_and_base_vs_expanded_span_reject(self):
        for kind in ('query', 'future', 'reference', 'cigar'):
            window, graph = fixture()
            if kind == 'query':
                graph['query_index'] = 9
            elif kind == 'future':
                graph['query']['end'] += 10
            elif kind == 'reference':
                graph['reference']['end'] += 1
            else:
                graph['walks'][0]['cigar'] = '23M'
            process, _ = self.run_projection(window, graph)
            self.assertNotEqual(process.returncode, 0, kind)


class ScalarExposure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ['UNCERTAINTY_SCALAR_BINARY']

    def scalar(self, value=8.0, clamp=0, corruption=None):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            tensor = directory / 'p1_b1_s0.scores'
            header = f'DGS1\t6\t1024\t4\t6\t2\t128\t100\t0\t0\t0\t{clamp}\t0\tp1_b1\t0\n'.encode()
            payload = bytearray(6 * 1024 * 2)
            payload[(4 * 1024 + 4) * 2:(4 * 1024 + 4) * 2 + 2] = struct.pack('<e', value)
            payload[(4 * 1024 + 1) * 2:(4 * 1024 + 1) * 2 + 2] = struct.pack('<e', -3)
            if corruption == 'nonfinite_outside_slice':
                payload[0:2] = b'\x00\x7e'
            tensor.write_bytes(header + payload)
            meta = directory / 'native.meta.tsv'
            metadata = dict(format='DGM1', read_id='synthetic-parent', chunk_index='0', T='6', C='1024',
                            token='p1_b1', time_offset='0', score_file=tensor.name, SEQ='AAAACG', Q='IIIIII', MOVES='111111')
            meta.write_text(''.join(f'{key}\t{item}\n' for key, item in metadata.items()))
            values = dict(plan_sha256='0' * 64, query_index='0', parent='synthetic-parent', chunk_index='0',
                          t_start='4', t_end='5', initial_context='AAAA', initial_state='0', sequence='C',
                          token='p1_b1', time_offset='0', T='6', C='1024')
            for prefix, item in (('tensor', pin(tensor)), ('metadata', pin(meta))):
                values.update({prefix + '_' + key: str(item) for key, item in item.items()})
            if corruption == 'initial':
                values['initial_state'] = '1'
            if corruption == 'offset':
                values['time_offset'] = '1'
            request = directory / 'request.tsv'
            request.write_text('context-scalar-request/1\n' + ''.join(f'{key}\t{item}\n' for key, item in sorted(values.items())))
            process = subprocess.run([self.binary, 'score', '--request', str(request), '--request-sha256', digest(request),
                                      '--output', str(directory / 'output')], capture_output=True, text=True, timeout=15)
            if process.returncode:
                return process, None, None
            scalar = (directory / 'output/retained-scalar.tsv').read_text().rstrip('\n').split('\t')
            audit = dict(line.split('\t') for line in (directory / 'output/audit.tsv').read_text().splitlines()[1:])
            return process, float(scalar[1]), audit

    def test_existing_rust_channel_mapping(self):
        process, value, audit = self.scalar()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(value, 8.0)
        self.assertEqual(audit['bits'], '4020000000000000')

    def test_existing_half_subnormal_and_clamp(self):
        for expected, argument, clamp in ((5.0, 8.0, 5), (2.0 ** -24, 2.0 ** -24, 0), (-0.0, -0.0, 0)):
            process, value, _ = self.scalar(argument, clamp)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(value, expected)

    def test_deep_nonfinite_and_geometry_rejections(self):
        for corruption in ('nonfinite_outside_slice', 'initial', 'offset'):
            process, _, _ = self.scalar(corruption=corruption)
            self.assertNotEqual(process.returncode, 0, corruption)


class BoundaryCustody(unittest.TestCase):
    """Synthetic structural artifacts only; genuine plan/native admission is separate."""
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ['UNCERTAINTY_FEEDBACK_BINARY']
        spec = importlib.util.spec_from_file_location('targeting_custody_driver', ROOT / 'tools/uncertainty_feedback/driver.py')
        cls.driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.driver)
        result = subprocess.run([cls.binary, 'controls'], capture_output=True, text=True, timeout=30, check=True)
        cls.source_witness = json.loads(result.stdout)['source_witness']

    def fake_plan(self, directory):
        windows = [dict(schema='graph-prior-window/1', query_index=index, read_id='synthetic', contig='chr1', ref_start=100+index*50,
                        ref_end=141+index*50, core_start=110+index*50, core_end=131+index*50, read_start=index*50, read_end=41+index*50,
                        chunk_index=0, chunk_start=10, chunk_end=51, t_start=10, t_end=51, reverse=False, stock='A'*41,
                        context='AAAA', score_file='p1_b1_s0.scores') for index in range(512)]
        window_file = directory / 'windows.jsonl'
        window_file.write_text(''.join(json.dumps(row, sort_keys=True, separators=(',', ':'))+'\n' for row in windows))
        joins = directory / 'joins.json'; joins.write_text(json.dumps([dict(query_index=index, window=row) for index, row in enumerate(windows)]))
        parents = directory / 'parents.json'; parents.write_text(json.dumps({f'synthetic-{index}': {} for index in range(64)}))
        config = self.driver.read(ROOT / 'config/uncertainty-feedback-v1.json')
        return dict(schema='uncertainty-feedback-plan/1', complete=True, source_witness=self.source_witness,
                    windows=pin(window_file), plan_sha256=digest(window_file), joins=pin(joins), parents=pin(parents),
                    audit=pin(Path(config['inputs']['audit'])), nomination_count=512)

    def test_deep_rehashed_plan_identity_and_completion_negatives(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name); plan = self.fake_plan(directory)
            for kind in ('positive_structure', 'plan_identity', 'schema', 'complete', 'witness'):
                changed = json.loads(json.dumps(plan))
                if kind == 'plan_identity': changed['plan_sha256'] = '0'*64
                elif kind == 'schema': changed['schema'] = 'foreign-plan/1'
                elif kind == 'complete': changed['complete'] = False
                elif kind == 'witness': changed['source_witness']['compiler']['sha256'] = '0'*64
                path = directory / (kind+'.json'); path.write_text(json.dumps(changed))
                result = subprocess.run([self.binary, 'batch', '--plan', str(path), '--plan-sha256', digest(path),
                    '--queries', '0', '--output', str(directory / (kind+'-out'))], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode == 0, kind == 'positive_structure', result.stderr)
                if kind == 'plan_identity': self.assertIn('authoritative windows bytes', result.stderr)

    def test_mask_substitutions_deep_rehashed_before_any_mask_body(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name); plan = self.fake_plan(directory)
            plan_path = directory / 'plan.json'; plan_path.write_text(json.dumps(plan))
            dependencies = self.driver.read(ROOT / 'tools/uncertainty_feedback/dependencies.json')
            masks = self.driver.read(dependencies['observation_snapshot']['path'])['eligible']
            substitute = directory / 'substituted.bed'; substitute.write_text('chr1\t1\t2\n')
            for index, changed in enumerate(({}, {'100':masks['100']}, {'100':masks['500'],'500':masks['100']}, {'100':pin(substitute),'500':masks['500']})):
                request = directory / (str(index)+'.json')
                request.write_text(json.dumps(dict(schema='uncertainty-feedback-exposure-request/1', plan=pin(plan_path), masks=changed)))
                result = subprocess.run([self.binary, 'exposure', '--request', str(request), '--request-sha256', digest(request),
                    '--output', str(directory / (str(index)+'-out'))], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Exact frozen both-domain', result.stderr)

    def synthetic_receipt(self, directory):
        directory.mkdir(); binary = directory / 'synthetic-tool'; binary.write_text('not executed\n')
        input_file = directory / 'input'; input_file.write_text('synthetic metadata\n')
        argv = [str(binary), '--offline', '--locked']; inputs = [pin(input_file)]
        raw = directory / 'raw'; raw.mkdir()
        values = {'command.sh':shlex.join(argv)+'\n','cwd.txt':str(ROOT)+'\n','start.txt':'2026-10-25T00:00:00+00:00\n',
                  'end.txt':'2026-10-25T00:00:01+00:00\n','exit-status.txt':'0\n','stdout':'','stderr':'',
                  'time.txt':'\tCommand being timed: "'+' '.join(argv)+'"\n\tExit status: 0\n'}
        for key, value in values.items(): (raw/key).write_text(value)
        receipt = dict(schema='uncertainty-feedback-command/1', complete=True, source_witness=self.source_witness,
                       binary=pin(binary), argv=argv, inputs=inputs, exit_status=0, raw_files=[pin(raw/name) for name in self.driver.RAW])
        return receipt, argv, inputs, raw

    def test_exact_raw_inventory_and_deep_rehashed_exit_command_inputs(self):
        with tempfile.TemporaryDirectory() as name:
            for kind in ('positive', 'missing_raw', 'exit', 'command', 'inputs'):
                value, argv, inputs, raw = self.synthetic_receipt(Path(name)/kind)
                if kind == 'missing_raw': value['raw_files'] = []
                elif kind == 'exit': (raw/'exit-status.txt').write_text('1\n'); value['raw_files'][4] = pin(raw/'exit-status.txt')
                elif kind == 'command': (raw/'command.sh').write_text('unrelated --offline --locked\n'); value['raw_files'][0] = pin(raw/'command.sh')
                elif kind == 'inputs': value['inputs'] = []
                if kind == 'positive': self.driver.receipt(value, value['binary'], argv, inputs)
                else:
                    with self.assertRaises(ValueError): self.driver.receipt(value, value['binary'], argv, inputs)

    def test_unrelated_offline_locked_build_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            value, _, _, _ = self.synthetic_receipt(Path(name)/'build')
            tool, inputs, argv, _ = self.driver.scalar_contract()
            with self.assertRaises(ValueError): self.driver.receipt(value, tool['cargo'], argv, inputs)

    def test_original_scalar_build_is_an_exact_external_dependency(self):
        original = self.driver.read(ROOT / 'tools/uncertainty_feedback/dependencies.json')['original_scalar']
        tool, inputs, argv, environment = self.driver.scalar_contract()
        build = self.driver.original_scalar_receipt(original['build_receipt'], 'build_receipt', tool['cargo'], argv, inputs)
        self.assertEqual(build['environment'], environment)
        self.assertEqual(build['source_witness'], self.driver.original_scalar_witness())
        self.assertNotEqual(build['source_witness'], self.source_witness)
        self.assertEqual(Path(argv[argv.index('--manifest-path') + 1]),
                         Path(original['source_root']) / 'tools/uncertainty_feedback/scalar_oracle/Cargo.toml')
        with self.assertRaises(ValueError):
            self.driver.receipt(build, tool['cargo'], argv, inputs)
        with self.assertRaises(ValueError):
            self.driver.original_scalar_receipt(original['compiler_version'], 'build_receipt', tool['cargo'], argv, inputs)
        with self.assertRaises(ValueError):
            self.driver.original_scalar_receipt(original['build_receipt'], 'build_receipt', tool['cargo'],
                                                [*argv[:-1], str(ROOT / 'results/substituted')], inputs)
        with tempfile.TemporaryDirectory() as name:
            copied = Path(name) / 'same-build-new-path.json'
            copied.write_bytes(Path(original['build_receipt']['path']).read_bytes())
            with self.assertRaises(ValueError):
                self.driver.original_scalar_receipt(pin(copied), 'build_receipt', tool['cargo'], argv, inputs)

    def test_original_scalar_runtime_allowlist_does_not_admit_transplants(self):
        original = self.driver.read(ROOT / 'tools/uncertainty_feedback/dependencies.json')['original_scalar']
        self.driver.runtime(original['runtimes']['scalar'], original['binary'])
        self.driver.runtime(original['runtimes']['sha256'], self.driver.read(ROOT / 'tools/uncertainty_feedback/dependencies.json')['scalar_toolchain']['sha256'])
        with tempfile.TemporaryDirectory() as name:
            copied = Path(name) / 'same-runtime-new-path.json'
            copied.write_bytes(Path(original['runtimes']['scalar']['path']).read_bytes())
            with self.assertRaises(ValueError):
                self.driver.runtime(pin(copied), original['binary'])


if __name__ == '__main__':
    unittest.main()
