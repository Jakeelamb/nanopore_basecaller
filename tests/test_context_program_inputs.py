import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


p = load('program_inputs_under_test',ROOT/'tools/context_decoder/program_inputs.py')
c = load('program_fixture_boundary',ROOT/'tools/context_decoder/context_inputs.py')
g = load('program_fixture_projection',ROOT/'tools/context_decoder/guarded_inputs.py')
SCHEMA = c.read(p.SCHEMA)


class Inputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        sequence = 'ACGT'*20
        self.window = dict(query_index=0,read_id='parent',chunk_index=0,chunk_start=10,chunk_end=40,
                           read_start=10,read_end=40,ref_start=110,ref_end=140,contig='chrFixture',reverse=False,stock=sequence[10:40])
        def table(name,schema,values):
            path = self.directory/name
            if schema in ('DGP1','DGM1'):
                path.write_text(''.join(f'{k}\t{v}\n' for k,v in dict(format=schema,**values).items()))
            else:
                c.tabular(path,schema,values)
            return c.pin(path)
        self.parent = table('parent.tsv','DGP1',dict(read_id='parent',SEQ=sequence,Q='I'*80))
        tensor = self.directory/'fixture_s0.scores'
        header = 'DGS1\t80\t1024\t4\t6\t2\t0\t0\t0\t0\t0\t0\t0\tfixture\t0\n'
        tensor.write_bytes(header.encode()+bytes(80*1024*2))
        meta = table('metadata.tsv','DGM1',dict(read_id='parent',chunk_index=0,score_file=tensor.name,
                     SEQ=sequence,Q='I'*80,MOVES='1'*80,T=80,C=1024,token='fixture',time_offset=0))
        sam = self.directory/'native.sam'
        sam.write_text('parent\t0\tchrFixture\t101\t60\t80M\t*\t0\t0\t'+sequence+'\t'+'I'*80+'\n')
        receipt = self.directory/'receipt.json'; c.fresh(receipt,{})
        base = dict(parent='parent',query_index=0,chunk_index=0,initial_context=sequence[6:10],initial_state=177,
                    graph_sha256='b'*64,plan_sha256='c'*64)
        for prefix,pin in (('tensor',c.pin(tensor)),('metadata',meta),('location_sam',c.pin(sam)),('location_receipt',c.pin(receipt))):
            base.update({prefix+'_'+k:v for k,v in pin.items()})
        self.base = table('base.tsv','context-frame/1',base)
        context = dict(availability='usable',parent='parent',query_index=0,chunk_index=0,tensor_sha256=c.pin(tensor)['sha256'],
                       plan_sha256='c'*64,graph_sha256='b'*64,base_frame_sha256=self.base['sha256'],
                       expanded_t_start=10,expanded_t_end=50,owned_start=20,owned_end=30,sequence_0=sequence[20:30])
        context_pin = table('context.tsv','context-centers/2',context)
        frame = dict(anchor_bases=10,future_bases=10,left_guard=sequence[10:20],native_center=sequence[20:30],right_guard=sequence[30:50],
                     read_start=10,read_end=40,owned_start=20,owned_end=30,expanded_t_start=10,expanded_t_end=50)
        for prefix,pin in (('base_frame',self.base),('parent',self.parent),('context',context_pin)):
            frame.update({prefix+'_'+k:v for k,v in pin.items()})
        frame_pin = table('frame.tsv','guarded-frame/2',frame)
        construction = self.directory/'construction.json'
        c.fresh(construction,dict(original_window=self.window,frame=frame_pin,base_frame=self.base,parent=self.parent,owned_native=sequence[20:30]))
        choice = dict(sequence=sequence[20:30],signal_likelihood=2.,context_potential=0.,objective=2.)
        outcome = {role:dict(choice) for role in SCHEMA['enums']['baseline_role']}
        outcome.update(candidates=[dict(choice=choice,native=True,free_finalist=True,conditioned_finalist=True)],
                       reference_free_escape=dict(center_bound_reached=False,finalists=[{}]),conditioned_search=dict(center_bound_reached=False,finalists=[{}]),
                       gate='objective_margin_fallback',final_rerank_gate='objective_margin_fallback',abstained=False,
                       reference_free_abstained=False,final_rerank_abstained=False)
        self.result = self.directory/'result.json'
        c.fresh(self.result,dict(frame=frame_pin,binding={k:str(v) for k,v in frame.items()},outcome=outcome))
        self.seal = self.directory/'complete.json'; c.fresh(self.seal,dict(files=[c.pin(self.result)]))
        self.row = dict(frame=frame_pin,base_frame=self.base,construction=c.pin(construction),query_index=0,read_id='parent',
                        native_center=sequence[20:30],context_mode='ordinary',native=dict(completion=c.pin(self.seal)))
        self.graph = dict(schema='hprc-local-paths/1',query_index=0,query=dict(sample='GRCh38',contig='chrFixture',start=110,end=140),
                          reference=dict(start=110,end=140,sequence=sequence[10:40]),
                          walks=[dict(is_reference=True,both_anchors=True,sequence=sequence[10:40],cigar='30M')])
        self.observation = p.sam_index(sam,c)['parent']

    def project(self):
        return p.project_case('ordinary',self.row,c,c.check,self.graph,g.project_centers,self.observation,SCHEMA)

    def test_packet_uses_authoritative_census(self):
        records,_ = self.project()
        target = self.directory/'cases.tsv'
        p.write_packet(target,SCHEMA,'candidate','a'*64,records)
        self.assertTrue(target.read_text().startswith('SCHEMA\tcontext-candidate-case/1\t'))
        for line in target.read_text().splitlines()[1:]:
            cells = line.split('\t')
            self.assertEqual(len(cells)-1,len(SCHEMA['candidate_records'][cells[0]]))

    def test_truth_field_in_inference_rejected(self):
        records,_ = self.project(); records[0][1]['alt_haplotype']='A'
        with self.assertRaisesRegex(ValueError,'packet field'):
            p.write_packet(self.directory/'bad.tsv',SCHEMA,'candidate','a'*64,records)

    def test_duplicate_frame_field_rejected(self):
        path = self.directory/'bad-frame.tsv'; path.write_text('guarded-frame/2\nx\t1\nx\t2\n')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            p.fields(path,'guarded-frame/2')

    def test_same_size_frame_corruption_rejected(self):
        path = Path(self.row['frame']['path']); data=path.read_text(); path.write_text(data.replace('anchor_bases\t10','anchor_bases\t11'))
        with self.assertRaisesRegex(ValueError,'Changed file'):
            self.project()

    def test_same_size_parent_corruption_rejected(self):
        path = Path(self.parent['path']); data=path.read_text(); path.write_text(data.replace('SEQ\tA','SEQ\tT',1))
        with self.assertRaisesRegex(ValueError,'Changed file'):
            self.project()

    def test_same_size_result_corruption_rejected(self):
        self.result.write_text(self.result.read_text().replace('2.0','3.0',1))
        with self.assertRaisesRegex(ValueError,'Changed file'):
            self.project()

    def test_same_size_construction_corruption_rejected(self):
        path=Path(self.row['construction']['path'])
        path.write_text(path.read_text().replace('chrFixture','chrForeign',1))
        with self.assertRaisesRegex(ValueError,'Changed file'):
            self.project()

    def test_original_auditor_ignores_cwd_trap(self):
        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            (self.directory/'scripts').mkdir()
            (self.directory/'scripts/context-feedback.py').write_text('raise RuntimeError("cwd trap")\n')
            auditor = p.original_auditor()
            self.assertEqual(auditor.ROOT,p.ORIGINAL.parent.parent)
            self.assertEqual(auditor.c.ROOT,auditor.ROOT)
        finally:
            os.chdir(previous)

    def test_original_auditor_rejects_relocated_root(self):
        auditor = type('Auditor',(),dict(__file__=str(p.ORIGINAL),ROOT=self.directory,c=c))()
        with mock.patch.object(p,'load_module',return_value=auditor):
            with self.assertRaisesRegex(ValueError,'source-location'):
                p.original_auditor()

    def test_geometry_binds_native_ancestry(self):
        _,fact = self.project(); case=copy.deepcopy(fact['case']); case['geometry_ancestry_sha256']='d'*64
        self.assertNotEqual(p.geometry_sha(case,SCHEMA),fact['case']['geometry_sha256'])
        case['case_id']='private/0/withheld'
        self.assertEqual(p.geometry_sha(case,SCHEMA),p.geometry_sha(dict(case,case_id='private/0/ordinary'),SCHEMA))

    def test_neural_scores_use_exact_candidate_rescore(self):
        records,_ = self.project()
        candidate = next(value for tag,value in records if tag=='CAND')
        self.assertEqual(candidate['log_mass'],'2.0')
        self.assertEqual(candidate['origins'],15)

    def test_graph_only_score_stays_unavailable(self):
        context_path=self.directory/'context.tsv'
        text=context_path.read_text().replace('sequence_0\tACGTACGTAC','sequence_0\tTTTTTTTTTT')
        context_path.write_text(text)
        frame=p.fields(self.row['frame']['path'],'guarded-frame/2')
        for key,value in c.pin(context_path).items(): frame['context_'+key]=str(value)
        Path(self.row['frame']['path']).unlink(); c.tabular(self.row['frame']['path'],'guarded-frame/2',frame)
        self.row['frame']=c.pin(self.row['frame']['path'])
        construction=c.read(self.row['construction']['path']); construction['frame']=self.row['frame']
        Path(self.row['construction']['path']).unlink(); c.fresh(self.row['construction']['path'],construction);self.row['construction']=c.pin(self.row['construction']['path'])
        result=c.read(self.result);result['frame']=self.row['frame'];result['binding']=frame
        self.result.unlink();c.fresh(self.result,result);self.seal.unlink();c.fresh(self.seal,dict(files=[c.pin(self.result)]));self.row['native']['completion']=c.pin(self.seal)
        records,_=self.project(); candidate=next(v for t,v in records if t=='CAND' and v['sequence']=='TTTTTTTTTT')
        self.assertEqual((candidate['origins'],candidate['log_mass']),(8,'.'))

    def test_forward_future_extends_reference_right(self):
        self.assertEqual(p.reference_geometry(self.window,self.observation,c),((110,150),(120,130)))

    def test_reverse_future_extends_reference_left(self):
        window=dict(self.window,reverse=True,read_start=40,read_end=70)
        observation=dict(self.observation,reverse=True)
        self.assertEqual(p.reference_geometry(window,observation,c),((100,140),(120,130)))

    def boundary_geometry(self, op, trailing):
        for reverse in (False,True):
            with self.subTest(reverse=reverse):
                before = (20,29 if op == 'I' else 30)[trailing != reverse]
                after = 80-before-(1 if op == 'I' else 0)
                fields = list(self.observation['fields']); fields[5] = f'{before}M1{op}{after}M'
                end = 139 if op == 'I' else 141
                window = dict(self.window,reverse=reverse,read_start=40 if reverse else 10,
                              read_end=70 if reverse else 40,ref_end=end)
                observation = dict(self.observation,fields=fields,reverse=reverse)
                expanded = (100,end) if reverse else (110,end+10)
                self.assertEqual(p.reference_geometry(window,observation,c),(expanded,(120,end-10)))

    def test_leading_core_insertion_preserves_anchor_cuts(self):
        self.boundary_geometry('I',False)

    def test_trailing_core_insertion_preserves_anchor_cuts(self):
        self.boundary_geometry('I',True)

    def test_leading_core_deletion_preserves_anchor_cuts(self):
        self.boundary_geometry('D',False)

    def test_trailing_core_deletion_preserves_anchor_cuts(self):
        self.boundary_geometry('D',True)

    def test_gapped_or_clipped_anchor_still_rejected(self):
        for reverse in (False,True):
            for op in ('I','D','S'):
                with self.subTest(reverse=reverse,op=op):
                    fields = list(self.observation['fields']); fields[5] = f'15M1{op}{65 if op == "D" else 64}M'
                    window = dict(self.window,reverse=reverse,read_start=40 if reverse else 10,
                                  read_end=70 if reverse else 40,ref_end=141 if op == 'D' else 139)
                    with self.assertRaisesRegex(ValueError,'gapped/clipped'):
                        p.reference_geometry(window,dict(self.observation,fields=fields,reverse=reverse),c)

    def test_truth_mutation_cannot_change_inference_bytes(self):
        records,fact=self.project();cases=self.directory/'cases.tsv'
        p.write_packet(cases,SCHEMA,'candidate','a'*64,records);before=cases.read_bytes()
        fragments={p.region('chrFixture',110,150):'A'*40}
        labels=p.label_records([fact],fragments,{'100':{},'500':{}},{},{},c)
        p.write_packet(self.directory/'truth.tsv',SCHEMA,'truth','b'*64,labels)
        (self.directory/'truth.tsv').write_text('arbitrarily changed oracle labels\n')
        self.assertEqual(cases.read_bytes(),before)
        self.assertFalse(any(tag in ('TRUTH','MASK','EVENT') for tag,_ in records))

    def test_private_archive_exact_reference_identity(self):
        _,fact=self.project(); fact['case']['domain']='private-ordinary'
        case=fact['case'];stock=case['left_guard']+case['native']+case['right_guard'][:-10]
        archive={0:dict(parent='parent',reverse=False,stock=stock,reference_window='C'*30,
                        truth_window_start_in_reference_window=10,truth_window_end_in_reference_window=20,alt_haplotype='G'*10,variant='event')}
        fragments={p.region('chrFixture',110,150):'A'*40,p.region('chrFixture',110,140):'A'*30}
        with self.assertRaisesRegex(ValueError,'pinned FASTA'):
            p.label_records([fact],fragments,{},archive,{},c)

    def test_private_missing_archive_retains_reason(self):
        _,fact=self.project();fact['case']['domain']='private-ordinary'
        labels=p.label_records([fact],{p.region('chrFixture',110,150):'A'*40},{},{},{0:'ambiguous placement'},c)
        self.assertEqual(labels[-1][1]['resolved'],0)
        self.assertEqual(labels[-1][1]['reason'],'ambiguous placement')

    def test_fasta_missing_region_rejected(self):
        path=self.directory/'extract.fa';path.write_text('>chrFixture:111-150\nAAAA\n')
        with self.assertRaisesRegex(ValueError,'length'):
            p.fasta_fragments(path,{'chrFixture:111-150':('chrFixture',110,150)})

    def test_matched_masks_preserve_parent_and_contig(self):
        path=self.directory/'matched.bed';path.write_text('chrFixture\t120\t125\tparent\nchrFixture\t127\t130\tother\n')
        self.assertEqual(p.masked_intervals(path)[('parent','chrFixture')],[(120,125)])

    def test_native_binary_packet_handoff(self):
        binary=os.environ.get('CONTEXT_PROGRAM_INFER_BINARY')
        if not binary:
            self.skipTest('Controller must provide qualified inference binary')
        records,_=self.project();cases=self.directory/'handoff.tsv'
        p.write_packet(cases,SCHEMA,'candidate','a'*64,records)
        result=subprocess.run([binary,'replay','--cases',str(cases),'--cases-sha256',c.pin(cases)['sha256'],
                               '--output',str(self.directory/'native-output')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


class PreparedReuse(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.prepared = self.directory/'prepared'; self.prepared.mkdir()
        self.original_root = self.directory/'original'
        self.results = self.original_root/'results'
        self.original_path = self.original_root/'scripts/context-feedback.py'
        self.original_path.parent.mkdir(parents=True)
        self.original_path.write_text('fixture original auditor\n')
        self.source_path = self.original_root/'source.cpp'; self.source_path.write_text('fixture source\n')
        self.binary = self.original_root/'binary'; self.binary.write_text('fixture binary\n')
        self.identity = p.digest([c.pin(self.original_path),c.pin(self.source_path)])
        self.raw = {}; self.proofs = []
        for phase in ('full','private'):
            stage,raw = self.stage('v2-'+phase+'-1/producer')
            self.raw[phase] = raw
            outer = self.write('v2-'+phase+'-1/execution-complete.json',dict(stages=[stage]))
            self.proofs.append(dict(execution=outer,phase=phase,binary=c.pin(self.binary)))
        self.observer_stage,self.raw['observer'] = self.stage('v2-observe-full-1/final_rerank/producer')
        self.mask_directory = self.results/'v2-observe-full-1/final_rerank'
        self.masks = [self.write('v2-observe-full-1/final_rerank/pair-native-'+name+'/matched.bed',{})
                      for name in SCHEMA['enums']['mask_name']]
        self.observer_seal = self.write('v2-observe-full-1/final_rerank/complete.json',dict(stages=[self.observer_stage],outputs=self.masks))
        self.observer_outer = self.write('v2-observe-full-1/final_rerank/execution-complete.json',{})
        self.regions = self.local('regions.txt','chrFixture:1-20\n')
        self.extraction = self.local('extraction.fa','>chrFixture:1-20\n'+'A'*20+'\n')
        self.truth_sources = {key:self.write(key+'.json',{}) for key in ('reference','fai','snapshot','samtools','archive')}
        self.argv = [self.truth_sources['samtools']['path'],'faidx','-r',self.regions['path'],self.truth_sources['reference']['path']]
        self.extraction_stage = self.write('current-extraction.json',dict(argv=self.argv,raw=dict(stdout=self.extraction)))
        self.census = dict(selected_cases=1,local_alignment_cells=20,alignment_cells=20,private_event_alignment_cells=0)
        self.inference = dict(schema='context-program-inference-manifest/1',scope='query0',truth_input=False,
                              original_auditor=c.pin(self.original_path),old_source_inventory_sha256=self.identity,
                              proofs=self.proofs,consumed_pins=[],census=dict(selected_cases=1,local_alignment_cells=20),cases=[dict(case=dict(case_id='case'))])
        self.truth = dict(schema='context-program-truth-manifest/1',regions=self.regions,extraction=self.extraction,
                          observer=dict(completion=self.observer_seal,execution=self.observer_outer),masks=self.masks,
                          **self.truth_sources)
        self.auditor = SimpleNamespace(ROOT=self.original_root,RESULTS=self.results,c=c,
            sources=lambda:[c.pin(self.original_path),c.pin(self.source_path)],inventory_hash=p.digest,
            evidence=SimpleNamespace(completed=self.completed,stage=self.check_stage))
        self.observer = SimpleNamespace(completed_producer=self.observed)
        for name,value in (('ORIGINAL',self.original_path),('ORIGINAL_SOURCE_SHA256',self.identity),
                           ('original_auditor',lambda:self.auditor),('load_module',lambda *_:self.observer)):
            patcher = mock.patch.object(p,name,value); patcher.start(); self.addCleanup(patcher.stop)
        self.refresh()

    def write(self, name, value):
        path = self.results/name; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value)+'\n')
        return c.pin(path)

    def local(self, name, value):
        path = self.prepared/name
        path.write_text(value if isinstance(value,str) else json.dumps(value)+'\n')
        return c.pin(path)

    def stage(self, name):
        raw = self.write(name+'/stdout',{})
        return self.write(name+'/finish.json',dict(raw=[raw])),raw

    def check_stage(self, pin, boundary):
        boundary.check(pin)
        stage = boundary.read(pin['path'])
        for item in stage['raw']:
            boundary.check(item)

    def completed(self, directory, phase, identity, boundary):
        self.assertEqual(identity,self.identity)
        outer = c.pin(directory/'execution-complete.json')
        for stage in boundary.read(outer['path'])['stages']:
            self.check_stage(stage,boundary)
        return dict(execution=outer,phase=phase,binary=c.pin(self.binary))

    def observed(self, manifest, command, mode):
        self.assertEqual((manifest,command,mode),(self.mask_directory/'complete.json','arm','ordinary'))
        c.check(self.observer_outer); c.check(self.observer_seal)
        return c.read(manifest)

    def refresh(self, case_header=None, truth_header=None, files=None):
        inference_pin = self.local('inference-manifest.json',self.inference)
        self.truth['inference'] = inference_pin
        truth_manifest = self.local('truth-manifest.json',self.truth)
        cases = self.local('cases.tsv','SCHEMA\tcontext-candidate-case/1\t'+(case_header or inference_pin['sha256'])+'\n')
        truth = self.local('truth.tsv','SCHEMA\tcontext-oracle-truth/1\t'+(truth_header or truth_manifest['sha256'])+'\n')
        self.manifest = dict(schema='context-program-inputs/1',scope='query0',cases=cases,truth=truth,inference=inference_pin,
                             truth_manifest=truth_manifest,census=self.census,selectedCaseIDs=['case'],
                             source_pins=[*self.truth_sources.values(),self.extraction])
        manifest_pin = self.local('manifest.json',self.manifest)
        expected = [cases,truth,inference_pin,truth_manifest,self.regions]
        completion = self.local('complete.json',dict(schema='context-program-inputs-complete/1',complete=True,
                               manifest=manifest_pin,files=expected if files is None else files))
        self.packet = dict(completion=completion,manifest=manifest_pin,cases=cases,truth=truth,census=self.census,selectedCaseIDs=['case'])

    def verify(self):
        return p.verify_prepared(self.packet,c,[self.extraction_stage])

    def missing(self, target):
        real_open = Path.open
        def opened(path, *args, **kwargs):
            if path == target:
                raise FileNotFoundError(str(path))
            return real_open(path,*args,**kwargs)
        return mock.patch.object(Path,'open',opened)

    def test_complete_hermetic_handoff_revalidates(self):
        self.assertEqual(self.verify(),self.manifest)

    def test_missing_original_execution_rejected(self):
        for phase in ('full','private'):
            with self.subTest(phase=phase):
                target = Path(next(x for x in self.proofs if x['phase'] == phase)['execution']['path'])
                with self.missing(target):
                    with self.assertRaises(FileNotFoundError):
                        self.verify()

    def test_missing_nested_producer_file_rejected(self):
        Path(self.raw['full']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify()

    def test_missing_nested_producer_stage_rejected(self):
        outer = c.read(self.proofs[0]['execution']['path'])
        Path(outer['stages'][0]['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify()

    def test_missing_observer_stage_rejected(self):
        Path(self.observer_stage['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify()

    def test_missing_observer_execution_rejected(self):
        Path(self.observer_outer['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify()

    def test_missing_observer_raw_file_rejected(self):
        Path(self.raw['observer']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify()

    def test_changed_original_source_rejected(self):
        self.source_path.write_text('changed source\n')
        with self.assertRaisesRegex(ValueError,'Original source inventory'):
            self.verify()

    def test_missing_prepared_manifest_files_rejected(self):
        for name in ('inference-manifest.json','truth-manifest.json','regions.txt'):
            with self.subTest(name=name):
                target = self.prepared/name
                with self.missing(target):
                    with self.assertRaises(FileNotFoundError):
                        self.verify()

    def test_modified_completion_pin_rejected(self):
        self.local('complete.json',{})
        with self.assertRaisesRegex(ValueError,'Changed file'):
            self.verify()

    def test_empty_duplicate_or_omitted_file_census_rejected(self):
        omitted = [self.packet['cases'],self.packet['truth'],self.manifest['inference'],self.manifest['truth_manifest']]
        for files in ([],[self.regions]*5,omitted):
            with self.subTest(files=files):
                self.refresh(files=files)
                with self.assertRaisesRegex(ValueError,'file census'):
                    self.verify()

    def test_foreign_file_census_rejected(self):
        self.refresh(files=[self.packet['cases'],self.packet['truth'],self.manifest['inference'],self.manifest['truth_manifest'],self.extraction])
        with self.assertRaisesRegex(ValueError,'file census'):
            self.verify()

    def test_cross_packet_header_rejected(self):
        for key in ('case_header','truth_header'):
            with self.subTest(key=key):
                self.refresh(**{key:'0'*64})
                with self.assertRaisesRegex(ValueError,'packet header'):
                    self.verify()

    def test_duplicate_original_proof_rejected(self):
        self.inference['proofs'] = [self.proofs[0],self.proofs[0]]; self.refresh()
        with self.assertRaisesRegex(ValueError,'proof census'):
            self.verify()

    def test_uncovered_consumed_source_rejected(self):
        self.inference['consumed_pins'] = [c.pin(self.source_path)]; self.refresh()
        with self.assertRaisesRegex(ValueError,'consumed source link'):
            self.verify()

    def test_extraction_producer_mismatch_rejected(self):
        self.extraction_stage = self.write('current-extraction.json',dict(argv=['wrong'],raw=dict(stdout=self.extraction)))
        with self.assertRaisesRegex(ValueError,'extraction producer'):
            self.verify()


class Census(unittest.TestCase):
    def fixture(self):
        ordinary=[]
        for q in range(451):
            status='constructed' if q<311 else 'original_excluded' if q<431 else 'boundary_excluded'
            row=dict(query_index=q,read_id=f'parent-{q}',context_mode='ordinary',status=status)
            if status=='constructed':row['native']={}
            ordinary.append(row)
        private=[]
        for mode in ('ordinary','withheld'):
            for q in range(40):
                status='original_excluded' if q>=31 else 'challenge_excluded' if mode=='withheld' and q>=26 else 'constructed'
                row=dict(query_index=q,read_id=f'private-{q}',context_mode=mode,status=status)
                if status=='constructed':row['native']={}
                private.append(row)
        return dict(outcomes=ordinary),dict(outcomes=private,selection=dict(selected=60,attached=40,scored=31,unambiguous_challenge=26))

    def test_scope_keeps_complete_metadata_census(self):
        full,private=self.fixture()
        for scope,native in (('query0',1),('first32',32),('all',368)):
            rows,inventory=p.selection(full,private,scope)
            self.assertEqual((len(rows),len(inventory)),(native,531))

    def test_mode_corruption_rejected(self):
        full,private=self.fixture();private['outcomes'][0]['context_mode']='withheld'
        with self.assertRaisesRegex(ValueError,'mode census'):
            p.selection(full,private,'all')

    def test_missing_outcome_rejected(self):
        full,private=self.fixture();full['outcomes'].pop()
        with self.assertRaisesRegex(ValueError,'outcome census'):
            p.selection(full,private,'all')


if __name__ == '__main__':
    unittest.main()
