import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import unittest

from test_context_feedback import w, c, fixture

spec = importlib.util.spec_from_file_location('guarded_test_inputs', w.ROOT / 'tools/context_decoder/guarded_inputs.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def synthetic(directory, reverse=False):
    seq = 'A'*80
    tensor = directory/'p1_b0_s0.scores'
    tensor.write_bytes(b'DGS1\t80\t1024\t4\t6\t-3\t128\t100\t0\t1\t0\t0\t0\tp1_b0\t0\n' + struct.pack('<H',0)*(80*1024))
    common = dict(read_id='synthetic-parent',chunk_count=1,signal_samples=480,num_trimmed_samples=0,
                  original_signal_samples=480,variable_chunk_sizes=1,SEQ=seq,Q='!'*80,MOVES='1'*80)
    metadata = directory/'p1_b0_s0.scores.meta.tsv'
    c.tabular(metadata,'format\tDGM1',dict(common,chunk_index=0,score_file=tensor.name,token='p1_b0',time_offset=0,
                                         T=80,C=1024,input_offset=0,raw_chunk_size=480,chunk_size_granularity=6))
    parent = directory/'synthetic-parent.parent.tsv'
    c.tabular(parent,'format\tDGP1',dict(common,stride=6))
    sam = directory/'synthetic.sam'
    sam.write_text('\t'.join(('synthetic-parent','16' if reverse else '0','synthetic','1','60','80=','*','0','0','T'*80 if reverse else seq,'!'*80))+'\n')
    receipt = directory/'location.json'
    receipt.write_text('{"synthetic_only":true}\n')
    controls = directory/'scalar.tsv'
    controls.write_text('A'*22+'\t0\n')
    identity = dict(plan_sha256='1'*64,query_index=0,parent='synthetic-parent',chunk_index=0,tensor_sha256=c.pin(tensor)['sha256'],
                    t_start=10,t_end=32,initial_context='AAAA',initial_state=0,reverse=int(reverse),contig='synthetic',
                    ref_start=48 if reverse else 10,ref_end=70 if reverse else 32,graph_sha256='2'*64,
                    location_receipt_sha256=c.pin(receipt)['sha256'],location_sam_sha256=c.pin(sam)['sha256'])
    context = directory/'base-context.tsv'
    c.tabular(context,'context-paths/1',dict(identity,sequence_0='A'*22))
    values = dict(identity,location_status='usable',stock='A'*22)
    for key,path in [('tensor',tensor),('metadata',metadata),('location_receipt',receipt),('location_sam',sam),('context',context),('scalar_controls',controls)]:
        values.update({key+'_'+k:v for k,v in c.pin(path).items()})
    base = directory/'base.tsv'
    c.tabular(base,'context-frame/1',values)
    f = dict(base_frame_sha256=c.pin(base)['sha256'],plan_sha256='1'*64,query_index=0,parent='synthetic-parent',chunk_index=0,
             tensor_sha256=values['tensor_sha256'],expanded_t_start=10,expanded_t_end=42,owned_start=20,owned_end=22,
             availability='usable',graph_sha256='2'*64)
    center = directory/'center.tsv'
    c.tabular(center,'context-centers/2',dict(f,sequence_0='AA'))
    fields = dict(read_start=10,read_end=32,owned_start=20,owned_end=22,anchor_bases=10,future_bases=10,
                  expanded_t_start=10,expanded_t_end=42,left_guard='A'*10,right_guard='A'*20,native_center='AA',
                  retained_chunk_start=0,retained_chunk_end=80)
    for key,path in [('base_frame',base),('parent',parent),('context',center)]:
        fields.update({key+'_'+k:v for k,v in c.pin(path).items()})
    frame=directory/'guarded.tsv'
    c.tabular(frame,'guarded-frame/2',fields)
    return frame,fields


class GuardedProjectionControls(unittest.TestCase):
    def graph(self,sequence,cigar):
        return dict(schema='hprc-local-paths/1',query_index=0,query=dict(sample='GRCh38',contig='x',start=0,end=22),
                    reference=dict(start=0,end=22,sequence='A'*22),walks=[dict(is_reference=True,both_anchors=True,sequence='A'*22,cigar='22M'),
                    dict(is_reference=False,both_anchors=True,sequence=sequence,cigar=cigar)])

    def test_center_projection_includes_boundary_insertion(self):
        window=dict(query_index=0,contig='x',ref_start=0,ref_end=22,reverse=False)
        paths,_=g.project_centers(window,self.graph('A'*10+'C'+'A'*12,'10M1I12M'))
        self.assertEqual(paths,['AA','CAA'])

    def test_center_projection_allows_complete_deletion(self):
        window=dict(query_index=0,contig='x',ref_start=0,ref_end=22,reverse=False)
        paths,_=g.project_centers(window,self.graph('A'*20,'10M2D10M'))
        self.assertEqual(paths,['','AA'])

    def test_wrong_query_namespace_rejected(self):
        window=dict(query_index=1,contig='x',ref_start=0,ref_end=22,reverse=False)
        with self.assertRaisesRegex(ValueError,'query linkage'):
            g.project_centers(window,self.graph('A'*22,'22M'))


    def test_future_guard_gap_is_explicit_boundary_exclusion(self):
        for label,cigar in [('insertion','35M1I44M'),('deletion','35M1D45M'),('clip','35M45S')]:
            directory=fixture('guard-preflight-'+label)
            base,_=synthetic(directory)
            original=directory/'base.tsv'
            fields=g.frame_fields(original)
            sam=directory/'synthetic.sam'
            row=sam.read_text().strip().split('\t')
            row[5]=cigar
            sam.write_text('\t'.join(row)+'\n')
            fields.update({'location_sam_'+k:v for k,v in c.pin(sam).items()})
            c.tabular(directory/'preflight-base.tsv','context-frame/1',fields)
            window=dict(query_index=0,read_id='synthetic-parent',chunk_index=0,chunk_start=10,chunk_end=32,
                        read_start=10,read_end=32,stock='A'*22)
            evidence=dict(metadata_pin=c.pin(directory/'p1_b0_s0.scores.meta.tsv'),
                          parent_pin=c.pin(directory/'synthetic-parent.parent.tsv'),
                          reconstruction_metadata_pins=[c.pin(directory/'p1_b0_s0.scores.meta.tsv'),c.pin(directory/'synthetic-parent.parent.tsv')])
            result=g.construct(dict(status='constructed',frame=c.pin(directory/'preflight-base.tsv')),
                               window,evidence,{},directory/'constructed')
            self.assertEqual(result['status'],'boundary_excluded')
            self.assertEqual(result['reason'],'native_guard_gapped_or_clipped_in_sam')
        for reverse in (False,True):
            fields=['parent','16' if reverse else '0','x','1','60','80M']
            observation=dict(start=0,fields=fields,aligned='A'*80,reverse=reverse)
            self.assertTrue(g.guard_contiguous(dict(read_start=10,read_end=32),observation))


@unittest.skipUnless(os.environ.get('CONTEXT_DECODER_BINARY'),'Set the qualified C++ binary for guarded consumed controls')
class GuardedConsumedControls(unittest.TestCase):
    def run_case(self,name,change=None,reverse=False,expected=None):
        directory=fixture('guarded-'+name)
        frame,fields=synthetic(directory,reverse)
        if change:
            change(directory,fields)
            frame=directory/'changed.tsv'
            c.tabular(frame,'guarded-frame/2',fields)
        command=[os.environ['CONTEXT_DECODER_BINARY'],'decode-guarded','--frame',str(frame),'--frame-sha256',c.pin(frame)['sha256'],
                 '--output',str(directory/'native-output'),'--beam','16','--min-center','0','--max-center','8',
                 '--weight','0.5','--deficit','0.5','--margin','0.5']
        result=subprocess.run(command,cwd=w.ROOT,capture_output=True,check=False)
        (directory/'stdout').write_bytes(result.stdout)
        (directory/'stderr').write_bytes(result.stderr)
        (directory/'exit-status.txt').write_text(str(result.returncode)+'\n')
        c.fresh(directory/'command.json',command)
        if expected:
            self.assertNotEqual(result.returncode,0)
            self.assertIn(expected,result.stderr.decode())
            self.assertFalse((directory/'native-output/complete.json').exists())
        else:
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertTrue((directory/'native-output/complete.json').exists())
        return directory

    def test_actual_guarded_tensor_consumed(self):
        directory=self.run_case('consumed')
        result=c.read(directory/'native-output/result.json')
        c.check(result['phase_trace'])
        data=Path(result['phase_trace']['path']).read_bytes()
        magic=b'guarded-phase-trace/2\n'
        self.assertTrue(data.startswith(magic))
        offset=len(magic)
        def integer():
            nonlocal offset
            value=struct.unpack_from('<Q',data,offset)[0]
            offset+=8
            return value
        def number():
            nonlocal offset
            value=struct.unpack_from('<d',data,offset)[0]
            offset+=8
            self.assertFalse(math.isnan(value))
            return value
        def vector():
            return [number() for _ in range(integer())]
        for key in ('reference_free_escape','conditioned_search'):
            trace=result['outcome'][key]['trace']
            self.assertEqual(integer(),len(trace))
            for step in trace:
                self.assertEqual([integer() for _ in range(4)],
                                 [step['timestep'],step['generated'],step['merged'],step['pruned']])
                vector()
                centers=[]
                for _ in range(integer()):
                    size=integer()
                    centers.append(data[offset:offset+size].decode())
                    offset+=size
                    number()
                    self.assertEqual(len(vector()),20)
                    number();number();number()
                self.assertEqual(centers,step['retained_centers'])
        self.assertEqual(offset,len(data))

    def test_reverse_original_read_binding(self):
        self.run_case('reverse',reverse=True)

    def test_repinned_wrong_future_guard(self):
        self.run_case('future',lambda d,f:f.update(right_guard='A'*19+'C'),expected='guard')

    def test_wrong_expanded_emission_boundary(self):
        self.run_case('emission',lambda d,f:f.update(expanded_t_end=43),expected='expanded interval')

    def test_repeated_parent_offset_still_binds_to_sam(self):
        self.run_case('offset',lambda d,f:f.update(read_start=11,read_end=33,owned_start=21,owned_end=23),expected='SAM anchors')

    def test_unknown_truth_field_rejected(self):
        self.run_case('truth',lambda d,f:f.update(desired_winner='AA'),expected='field')

    def test_retained_chunk_guard_bound(self):
        self.run_case('retained',lambda d,f:f.update(retained_chunk_end=35),expected='retained native chunk')

    def test_repin_context_linkage_rejected(self):
        def change(directory,fields):
            path=Path(fields['context_path'])
            path.write_text(path.read_text().replace('query_index\t0\n','query_index\t1\n'))
            fields.update({'context_'+k:v for k,v in c.pin(path).items()})
        self.run_case('linkage',change,expected='linkage')

    def test_empty_context_center_is_not_missing(self):
        def change(directory,fields):
            path=Path(fields['context_path'])
            path.write_text(path.read_text().replace('sequence_0\tAA\n','sequence_0\t\n'))
            fields.update({'context_'+k:v for k,v in c.pin(path).items()})
        directory=self.run_case('empty-path',change)
        self.assertTrue(c.read(directory/'native-output/result.json')['outcome']['context_enabled'])
