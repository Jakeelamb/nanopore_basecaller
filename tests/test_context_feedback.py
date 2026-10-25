import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import unittest
import uuid
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_feedback_wrapper', ROOT / 'scripts/context-feedback.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
c = w.c


def fixture(name):
    directory = ROOT / 'results/context-feedback/python-controls' / (name + '-' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    return directory


def native_fixture(directory):
    tensor = directory / 'p1_b0_s0.scores'
    header = 'DGS1\t2\t1024\t4\t6\t-3\t128\t100\t0\t1\t0\t5\t0\tp1_b0\t0\n'
    tensor.write_bytes(header.encode() + struct.pack('<' + 'H' * 2048, *([0] * 2048)))
    metadata = directory / 'p1_b0_s0.scores.meta.tsv'
    c.tabular(metadata, 'format\tDGM1', dict(read_id='synthetic-parent', chunk_index=0,
              score_file=tensor.name, token='p1_b0', time_offset=0, T=2, C=1024))
    receipt = directory / 'synthetic-location.json'
    receipt.write_text('{"synthetic_only":true}\n')
    sam = directory / 'synthetic.sam'
    sam.write_text('synthetic-parent\t4\t*\t0\t0\t*\t*\t0\t0\tA\t!\n')
    scalar = directory / 'scalar.tsv'
    scalar.write_text('A\t' + repr(-3.0 + math.log(2.0)) + '\n')
    identity = dict(plan_sha256='1' * 64, query_index=0, parent='synthetic-parent', chunk_index=0,
                    tensor_sha256=c.pin(tensor)['sha256'], t_start=0, t_end=2,
                    initial_context='AAAA', initial_state=0, reverse=0, contig='synthetic',
                    ref_start=0, ref_end=1, graph_sha256='2' * 64,
                    location_receipt_sha256=c.pin(receipt)['sha256'], location_sam_sha256=c.pin(sam)['sha256'])
    context = directory / 'context.tsv'
    c.tabular(context, 'context-paths/1', dict(identity, sequence_0='A'))
    values = dict(identity, location_status='usable', stock='A')
    for prefix, path in [('tensor', tensor), ('metadata', metadata), ('location_receipt', receipt),
                         ('location_sam', sam), ('context', context), ('scalar_controls', scalar)]:
        values.update({prefix + '_' + key: value for key, value in c.pin(path).items()})
    frame = directory / 'frame.tsv'
    c.tabular(frame, 'context-frame/1', values)
    return frame, values


class BoundaryControls(unittest.TestCase):
    def test_unloaded_terminal_requires_successful_observation_and_empty_group(self):
        absent = '/context-feedback-synthetic-absent-' + uuid.uuid4().hex
        good = dict(exit=0, properties=dict(LoadState='not-found'))
        self.assertTrue(w.supervisor.unloaded_terminal(good, absent))
        self.assertFalse(w.supervisor.unloaded_terminal(dict(exit=1, properties={}), absent))
        self.assertFalse(w.supervisor.unloaded_terminal(dict(exit=1, properties=good['properties']), absent))
        self.assertFalse(w.supervisor.unloaded_terminal(dict(exit=0, properties={}), absent))
        self.assertFalse(w.supervisor.unloaded_terminal(good, '/'))

    def test_historical_auditor_keeps_registered_source_location_and_cwd(self):
        d = fixture('historical-helper-location')
        old = d / 'original/tools/catalogue_bridge/verify-receipt.py'
        copied = d / 'relocated/tools/catalogue_bridge/verify-receipt.py'
        old.parent.mkdir(parents=True)
        copied.parent.mkdir(parents=True)
        body = 'from pathlib import Path\nROOT=Path(__file__).resolve().parents[2]\ndef accepts_cwd(path):\n    return Path(path)==ROOT\n'
        old.write_text(body)
        copied.write_text(body)
        registry = dict(sources=[c.pin(old)])
        with patch.object(c, 'ROOT', d / 'relocated'):
            helper = c.historical_auditor(registry)
        self.assertEqual(Path(helper.__file__), old)
        self.assertTrue(helper.accepts_cwd(d / 'original'))
        self.assertFalse(helper.accepts_cwd(d / 'relocated'))
        self.assertEqual(c.pin(old)['sha256'], c.pin(copied)['sha256'])

    def test_missing_linked_stage_file_rejected(self):
        d = fixture('missing-linked-stage')
        finish = dict(schema='context-feedback-stage/1', exit=0, failure=None, projection_error=None,
                      terminal=dict(path=str(d / 'missing-terminal.json'), size=0, sha256='0' * 64))
        c.fresh(d / 'finish.json', finish)
        with self.assertRaises(FileNotFoundError):
            w.evidence.stage(c.pin(d / 'finish.json'), c)

    def test_missing_recorderfile_preserves_execution_evidence(self):
        d = fixture('missing-recorder-file')
        raw = d / 'synthetic-raw'
        raw.mkdir()
        argv = ['/synthetic/tool']
        for name, body in {'command.sh': '/synthetic/tool\n', 'cwd.txt': str(ROOT) + '\n',
                           'start.txt': '2026-01-01T00:00:00Z\n', 'end.txt': '2026-01-01T00:00:00Z\n',
                           'exit-status.txt': '0\n', 'stdout': '', 'stderr': ''}.items():
            (raw / name).write_text(body)
        grant = dict(id='synthetic-projection-control', maximum_wall_seconds=30,
                     expires_utc=(datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat())
        execution = w.Execution(grant, d, [])
        execution.budget = lambda: None
        def launch(_argv, **kwargs):
            kwargs['stdout'].write((str(raw) + '\n').encode())
            kwargs['stdout'].flush()
            return SimpleNamespace(pid=999999, returncode=0, poll=lambda: 0)
        with patch.object(w, 'LOGS', d / 'logs'), patch.object(w.subprocess, 'Popen', side_effect=launch), \
             patch.object(w.pg, 'stop_group', return_value=dict(terminal=True, synthetic_only=True)):
            with self.assertRaisesRegex(ValueError, 'Stage failed'):
                execution.stage('projection-control', argv)
        launcher = next((d / 'logs').glob('projection-control-*'))
        terminal = c.read(launcher / 'terminal.json')
        failed = c.read(launcher / 'finish.json')
        self.assertEqual(terminal['exit'], 0)
        self.assertIsNone(terminal['failure'])
        self.assertIn('raw recorder files', failed['projection_error'])
        self.assertIn('time.txt', failed['missing_raw'])
        failed['projection_error'] = None
        c.fresh(d / 'repinned-finish.json', failed)
        with self.assertRaisesRegex(ValueError, 'Missing linked raw recorder evidence'):
            w.evidence.stage(c.pin(d / 'repinned-finish.json'), c)

    def test_default_config_requires_fresh_admission(self):
        value = w.configuration(ROOT / 'config/context-feedback-dev-v1.json')
        self.assertIsNone(value['execution']['default_admission'])
        with self.assertRaisesRegex(ValueError, 'SOURCE ONLY'):
            w.admission(None, ROOT / 'config/context-feedback-dev-v1.json', 'qualify', ROOT / 'results/context-feedback/not-created')

    def test_unknown_truth_inference_field_rejected(self):
        d = fixture('truth')
        value = c.read(ROOT / 'config/context-feedback-dev-v1.json')
        value['desired_winner'] = 'A'
        c.fresh(d / 'config.json', value)
        with self.assertRaisesRegex(ValueError, 'Unknown config inference field'):
            w.configuration(d / 'config.json')

    def test_stale_admission_rejected_before_resource_probe(self):
        d = fixture('stale')
        now = datetime.now(timezone.utc)
        config = ROOT / 'config/context-feedback-dev-v1.json'
        value = dict(schema='context-feedback-admission/1', id='synthetic-stale', phase='qualify',
                     config=c.pin(config), source_inventory_sha256=w.inventory_hash(w.sources()),
                     output=str(d / 'output'), not_before_utc=(now - timedelta(seconds=20)).isoformat(),
                     expires_utc=(now - timedelta(seconds=1)).isoformat(), maximum_wall_seconds=19,
                     maximum_output_bytes=100 * 1024**2, address_space_bytes=8 * 1024**3,
                     memory_bytes=4 * 1024**3, swap_bytes=0, cpu_quota=2, cgroup='/not-a-real-grant')
        c.fresh(d / 'admission.json', value)
        with self.assertRaisesRegex(ValueError, 'Expired'):
            w.admission(d / 'admission.json', config, 'qualify', d / 'output', now=now)
        self.assertFalse((d / 'output').exists())

    def test_canonical_lock_is_single_fixed_existing_path(self):
        self.assertEqual(w.LOCK, Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock'))
        self.assertTrue(c.read(ROOT / 'config/context-feedback-dev-v1.json')['execution']['requires_external_admission'])

    def test_wrong_graph_path_linkage_rejected(self):
        window = dict(query_index=0, contig='synthetic', ref_start=0, ref_end=20, reverse=False)
        graph = dict(schema='hprc-local-paths/1', query_index=1,
                     query=dict(sample='GRCh38', contig='synthetic', start=0, end=20))
        with self.assertRaisesRegex(ValueError, 'Wrong graph-path linkage'):
            c.retrieve(window, graph)

    def test_context_alias_permutation_has_no_multiplicity(self):
        window = dict(query_index=0, contig='synthetic', ref_start=0, ref_end=20, reverse=False)
        walk = dict(is_reference=True, both_anchors=True, sequence='A' * 20, cigar='20M')
        graph = dict(schema='hprc-local-paths/1', query_index=0,
                     query=dict(sample='GRCh38', contig='synthetic', start=0, end=20),
                     reference=dict(start=0, end=20, sequence='A' * 20), walks=[walk])
        expected = c.retrieve(window, graph)
        graph['walks'] = [copy.deepcopy(walk), copy.deepcopy(walk)]
        self.assertEqual(c.retrieve(window, graph), expected)

    def test_ambiguous_and_wrong_parent_location_are_distinct(self):
        window = dict(read_id='parent')
        observation = dict(fields=['parent'], flag=0, mapq=0)
        self.assertEqual(c.validate_location(window, observation, 30), 'ambiguous')
        observation['fields'] = ['other']
        with self.assertRaisesRegex(ValueError, 'Location parent mismatch'):
            c.validate_location(window, observation, 30)

    def test_duplicate_metadata_and_pin_drift_rejected(self):
        d = fixture('metadata')
        path = d / 'meta'
        path.write_text('format\tDGM1\nformat\tDGM1\n')
        with self.assertRaisesRegex(ValueError, 'Malformed native metadata'):
            c.metadata(path)
        expected = c.pin(path)
        path.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'Changed file'):
            c.check(expected)


@unittest.skipUnless(os.environ.get('CONTEXT_DECODER_BINARY'), 'Set the qualified C++ binary for consumed-frame controls')
class ConsumedFrameControls(unittest.TestCase):
    def invoke(self, directory, frame, expect_error=None):
        binary = os.environ['CONTEXT_DECODER_BINARY']
        argv = [binary, 'decode', '--frame', str(frame), '--frame-sha256', c.pin(frame)['sha256'],
                '--output', str(directory / 'native-output'), '--beam', '4', '--min-symbols', '0',
                '--max-symbols', '4', '--weight', '0.5', '--deficit', '0.5', '--margin', '0.5']
        c.fresh(directory / 'command.json', argv)
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
        (directory / 'stdout').write_bytes(result.stdout)
        (directory / 'stderr').write_bytes(result.stderr)
        (directory / 'exit-status.txt').write_text(str(result.returncode) + '\n')
        if expect_error:
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b'')
            self.assertFalse((directory / 'native-output/complete.json').exists())
            self.assertIn(expect_error, result.stderr.decode())
        else:
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertTrue((directory / 'native-output/complete.json').exists())
        return result

    def test_actual_synthetic_tensor_consumed(self):
        d = fixture('native-genuine-synthetic')
        frame, _ = native_fixture(d)
        self.invoke(d, frame)

    def test_corrupted_consumed_payload_rejected(self):
        d = fixture('payload')
        frame, values = native_fixture(d)
        path = Path(values['tensor_path'])
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        self.invoke(d, frame, 'consumed input hash changed')

    def test_same_shape_tensor_swap_rejected(self):
        d = fixture('swap')
        frame, values = native_fixture(d)
        other = d / 'p2_b0_s0.scores'
        other.write_bytes(Path(values['tensor_path']).read_bytes())
        values.update({'tensor_' + k: v for k, v in c.pin(other).items()})
        alternate = d / 'swapped-frame.tsv'
        c.tabular(alternate, 'context-frame/1', values)
        self.invoke(d, alternate, 'tensor/metadata filename mismatch')

    def test_wrong_consumed_graph_link_rejected_after_repin(self):
        d = fixture('wrong-link')
        frame, values = native_fixture(d)
        context = Path(values['context_path'])
        context.write_text(context.read_text().replace('query_index\t0\n', 'query_index\t1\n'))
        values.update({'context_' + k: v for k, v in c.pin(context).items()})
        alternate = d / 'wrong-link-frame.tsv'
        c.tabular(alternate, 'context-frame/1', values)
        self.invoke(d, alternate, 'context/frame linkage mismatch')

    def test_truth_field_in_actual_frame_rejected(self):
        d = fixture('frame-truth')
        frame, values = native_fixture(d)
        values['desired_winner'] = 'A'
        alternate = d / 'truth-frame.tsv'
        c.tabular(alternate, 'context-frame/1', values)
        self.invoke(d, alternate, 'unknown or missing inference field')

    def test_initial_state_is_reconstructed_from_actual_context(self):
        d = fixture('initial-state')
        frame, values = native_fixture(d)
        values['initial_state'] = 1
        alternate = d / 'initial-state-frame.tsv'
        c.tabular(alternate, 'context-frame/1', values)
        self.invoke(d, alternate, 'initial state/context mismatch')


if __name__ == '__main__':
    unittest.main()
