"""Hermetic observer controls: no native commands, lock, mapping or scoring."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('observer_v2_controls', ROOT / 'tools/context_decoder/observe.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
c = o.c


class ObserverControls(unittest.TestCase):
    def test_splice_deletions_insertions_and_native_guards(self):
        self.assertTrue(o.controls()['empty_deletion_and_zero_span_insertion'])
        sequence, quality = 'A'*10 + 'CG' + 'T'*20, '0123456789' + 'ab' + 'c'*20
        for replacement in ('', 'A', 'CGG', 'CG'):
            edits = [dict(start=10,end=12,stock='CG',replacement=replacement)]
            seq, qual = o.splice(sequence,quality,edits)
            self.assertEqual(seq, sequence[:10]+replacement+sequence[12:])
            self.assertEqual(qual, quality[:10]+'!'*len(replacement)+quality[12:])
            self.assertEqual((seq,qual),o.independent_splice(sequence,quality,edits))

    def test_all_context_modes_have_exact_census(self):
        config = dict(qualification_queries=[0],checkpoint_queries=list(range(32)),full_queries=list(range(451)))
        summary=dict(schema='context-feedback-unit/2',phase='private',outcomes=[dict(query_index=q,context_mode=m) for q in range(40) for m in o.MODES])
        for mode in o.MODES:
            self.assertEqual(len(o.selected_rows(summary,'private',config,mode)),40)
        duplicate=copy.deepcopy(summary);duplicate['outcomes'][-1]=duplicate['outcomes'][0]
        with self.assertRaisesRegex(ValueError,'census'):
            o.selected_rows(duplicate,'private',config,'ordinary')
        with self.assertRaisesRegex(ValueError,'unavailable'):
            o.selected_rows(dict(schema='context-feedback-unit/2',phase='full',outcomes=[]),'full',config,'withheld')

    def test_grants_bind_mode_checkpoint_and_caps(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            c.fresh(directory/'complete.json',dict(complete=True,phase='full'))
            args=argparse.Namespace(command='prepare',arm=None,checkpoint=directory,manifest=None,context_mode='ordinary',output=o.w.RESULTS/'observer-control-only')
            now=datetime.now(timezone.utc)
            grant=dict(schema='context-feedback-observation-admission/1',id='observer-control',command='prepare',arm=None,
                context_mode='ordinary',checkpoint=c.pin(directory/'complete.json'),manifest=None,source=o.SOURCE,
                output=str(args.output.resolve()),not_before_utc=(now-timedelta(seconds=1)).isoformat(),
                expires_utc=(now+timedelta(seconds=100)).isoformat(),maximum_wall_seconds=100,cpu_quota=2,
                memory_bytes=4*1024**3,address_space_bytes=8*1024**3,swap_bytes=0,maximum_output_bytes=4*1024**3,
                cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-feedback-observer-control.service')
            o.validate_grant(args,grant,now)
            for key,value in [('context_mode','withheld'),('checkpoint',None),('memory_bytes',16*1024**3),('maximum_output_bytes',4*1024**3+1)]:
                invalid=dict(grant,**{key:value})
                with self.assertRaises(ValueError):
                    o.validate_grant(args,invalid,now)
            manifest=directory/'emission.json';c.fresh(manifest,dict(synthetic=True))
            args.command='arm';args.arm='final_rerank';args.checkpoint=None;args.manifest=manifest;args.context_mode='withheld'
            grant.update(command='arm',arm='final_rerank',checkpoint=None,manifest=c.pin(manifest),context_mode='withheld',memory_bytes=16*1024**3,address_space_bytes=24*1024**3)
            o.validate_grant(args,grant,now)

    def fixture(self,directory):
        sequence='A'*80
        common=dict(read_id='parent',SEQ=sequence,Q='!'*80,MOVES='1'*80,signal_samples=480,chunk_count=1)
        parent=directory/'parent.tsv';c.tabular(parent,'format\tDGP1',common)
        meta=directory/'meta.tsv';c.tabular(meta,'format\tDGM1',dict(common,chunk_index=0,input_offset=0,raw_chunk_size=480,variable_chunk_sizes=1))
        tensor=directory/'tensor';tensor.write_text('synthetic source pin only\n')
        sam=directory/'sam';sam.write_text('\t'.join(('parent','0','chr1','1','60','80=','*','0','0',sequence,'!'*80))+'\n')
        receipt=directory/'receipt';receipt.write_text('{}\n')
        e=dict(metadata_pin=c.pin(meta),parent_pin=c.pin(parent),score_pin=c.pin(tensor),reconstruction_metadata_pins=[c.pin(meta)])
        window=dict(schema='graph-prior-window/1',query_index=0,read_id='parent',chunk_index=0,chunk_start=10,chunk_end=32,read_start=10,read_end=32,
                    stock='A'*22,context='AAAA',reverse=False,contig='chr1',ref_start=10,ref_end=32,t_start=10,t_end=32)
        graph=dict(schema='hprc-local-paths/1',query_index=0,query=dict(sample='GRCh38',contig='chr1',start=10,end=32),reference=dict(start=0,end=80,sequence=sequence),
                   walks=[dict(sequence=sequence,cigar='80M',both_anchors=True,is_reference=True)])
        pins=dict(windows=dict(sha256='1'*64),graph_walks=dict(sha256='2'*64))
        base=dict(plan_sha256='1'*64,graph_sha256='2'*64,query_index=0,parent='parent',chunk_index=0,stock='A'*22,t_start=10,t_end=32,
                  initial_context='AAAA',reverse=0,contig='chr1',ref_start=10,ref_end=32,location_status='usable')
        for prefix,pin in [('tensor',e['score_pin']),('metadata',e['metadata_pin']),('location_receipt',c.pin(receipt)),('location_sam',c.pin(sam))]:
            base.update({prefix+'_'+k:v for k,v in pin.items()})
        base_path=directory/'base.tsv';c.tabular(base_path,'context-frame/1',base)
        constructed=o.g.construct(dict(status='constructed',frame=c.pin(base_path)),window,e,graph,directory/'guarded')
        target=directory/'decoded';target.mkdir()
        frame=o.fields(constructed['frame']['path'],'guarded-frame/2')
        result=dict(schema='context-decoder-guarded-frame/2',frame=constructed['frame'],binding=frame,
                    outcome=dict(schema='guarded-outcome/2',native=dict(sequence='AA'),reference_free=dict(sequence=''),
                                 final_rerank=dict(sequence='C'),selected=dict(sequence='GG')))
        c.fresh(target/'result.json',result);c.fresh(target/'complete.json',dict(complete=True))
        constructed.update(native=dict(completion=c.pin(target/'complete.json')),context_mode='ordinary')
        admitted=dict(plan={0:window},decisions={0:dict(status='scored')},receipts={0:e},graph={0:graph},cohort=dict(pins=pins),
                      native=c.pin(sam),location_pin=c.pin(receipt),allowed_walk_hashes={})
        return constructed,admitted,result,target

    def test_construction_and_actual_result_bind_center_and_keep_all_arms(self):
        with tempfile.TemporaryDirectory() as temporary:
            outcome,admitted,result,target=self.fixture(Path(temporary))
            edit=o.validate_outcome(outcome,admitted,'ordinary')
            self.assertEqual((edit['start'],edit['end'],edit['stock']),(20,22,'AA'))
            self.assertEqual(edit['choices'],dict(reference_free='',final_rerank='C',selected='GG'))
            self.assertEqual(o.splice('A'*80,'!'*80,[dict(edit,replacement='')])[0],'A'*78)
            for key,value in [('owned_start',21),('owned_end',23),('native_center','AC')]:
                invalid=dict(outcome,**{key:value})
                with self.assertRaisesRegex(ValueError,'Summary center'):
                    o.validate_outcome(invalid,admitted,'ordinary')
            result['outcome']['native']['sequence']='AC'
            (target/'result.json').write_text(__import__('json').dumps(result))
            with self.assertRaisesRegex(ValueError,'Native guarded result/center'):
                o.validate_outcome(outcome,admitted,'ordinary')


if __name__=='__main__':
    unittest.main()
