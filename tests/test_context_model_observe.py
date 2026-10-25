import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_model_observe_controls', ROOT/'tools/context_decoder/model_observe.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


class Tables(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.case_id = 'ordinary/fixture/ordinary'
        self.case = dict(case_id=self.case_id, parent='parent', domain='ordinary', geometry_sha256='g'*64,
                         native='C', owned_start='2', owned_end='3')
        self.cases = {self.case_id:self.case}
        self.pools = {self.case_id:{o.digest('A'):('A',0.8),o.digest('C'):('C',1.0)}}
        self.bases = {self.case_id:dict(reference_free=dict(sequence='C'))}
        pool = o.digest('context-model-primary-pool/1\nA\t0.80000000000000004\nC\t1\n')
        self.common = dict(case_id=self.case_id,parent='parent',geometry_sha256='g'*64,pool_sha256=pool)
        self.contexts, self.candidates, self.decisions = [], [], []
        for arm in ('graph','none','reference','wrong'):
            self.contexts.append(dict(self.common,arm=arm,context_sha256=o.digest(arm),donor='donor',availability='available',reference_equals_graph='0'))
        for mu,arm in o.PROFILES:
            for sequence,signal in (('A','0.8'),('C','1')):
                self.candidates.append(dict(self.common,mu=mu,arm=arm,context_sha256=o.digest(arm),candidate_sha256=o.digest(sequence),
                    sequence=sequence,signal=signal,log_graph='0',log_background='0',log_mixture='0',log_ratio='0',objective=signal))
            self.decisions.append(dict(self.common,mu=mu,arm=arm,baseline_sha256=o.digest('C'),raw_sha256=o.digest('C'),accepted_sha256=o.digest('C'),
                baseline='C',raw='C',accepted='C',gate='reference_free_fallback' if arm=='none' else 'objective_margin_fallback',abstained='0',
                baseline_signal='1',baseline_objective='1',raw_signal='1',raw_objective='1',accepted_signal='1',accepted_objective='1',neural_delta='0',objective_delta='0'))
        self.write()

    def write(self):
        for name,rows in (('contexts.tsv',self.contexts),('candidates.tsv',self.candidates),('decisions.tsv',self.decisions)):
            with (self.directory/name).open('w',newline='') as stream:
                writer = csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
                writer.writeheader();writer.writerows(rows)

    def validate(self):
        return o.validate_tables(self.cases,self.pools,self.bases,[(self.directory,[self.case_id])])

    def test_complete_eight_arm_handoff(self):
        decisions,contexts = self.validate()
        self.assertEqual((len(decisions),len(contexts)),(8,4))

    def test_missing_profile_rejected(self):
        self.decisions.pop();self.write()
        with self.assertRaisesRegex(ValueError,'eight-profile'):
            self.validate()

    def test_missing_candidate_rejected(self):
        self.candidates.pop(0);self.write()
        with self.assertRaisesRegex(ValueError,'omitted retained'):
            self.validate()

    def test_duplicate_candidate_rejected(self):
        self.candidates.append(dict(self.candidates[0]));self.write()
        with self.assertRaisesRegex(ValueError,'duplicate or foreign model candidate'):
            self.validate()

    def test_duplicate_decision_rejected(self):
        self.decisions.append(dict(self.decisions[0]));self.write()
        with self.assertRaisesRegex(ValueError,'Duplicate, missing or foreign model decision'):
            self.validate()

    def test_changed_neural_score_rejected_exactly(self):
        self.candidates[0]['signal']='0.800000000000001';self.write()
        with self.assertRaisesRegex(ValueError,'retained signal changed'):
            self.validate()

    def test_changed_geometry_rejected(self):
        self.candidates[0]['geometry_sha256']='h'*64;self.write()
        with self.assertRaisesRegex(ValueError,'geometry/pool'):
            self.validate()

    def test_foreign_candidate_rejected(self):
        self.candidates[0]['candidate_sha256']=o.digest('T');self.write()
        with self.assertRaisesRegex(ValueError,'foreign model candidate'):
            self.validate()

    def test_missing_context_assignment_rejected(self):
        self.contexts.pop();self.write()
        with self.assertRaises((KeyError,ValueError)):
            self.validate()

    def test_none_change_is_rejected(self):
        item=next(row for row in self.decisions if row['arm']=='none')
        item.update(accepted='A',accepted_sha256=o.digest('A'),accepted_signal='0.8',accepted_objective='0.8')
        self.write()
        with self.assertRaisesRegex(ValueError,'Disabled model changed'):
            self.validate()

    def test_changed_baseline_rejected(self):
        self.decisions[0]['baseline']='A';self.write()
        with self.assertRaisesRegex(ValueError,'reference-free baseline'):
            self.validate()

    def test_missing_table_file_rejected(self):
        (self.directory/'candidates.tsv').unlink()
        with self.assertRaises(FileNotFoundError):
            self.validate()

    def test_annotation_keeps_zero_exposure_and_unresolved(self):
        decisions,contexts=self.validate()
        corpus=SimpleNamespace(cases=self.cases,decisions=decisions,contexts=contexts)
        labels=[]
        for sequence in ('A','C'):
            for mask in ('100','500'):
                labels.append(dict(case_id=self.case_id,parent='parent',domain='ordinary',candidate_sha256=o.digest(sequence),sequence=sequence,
                    mask=mask,vs_reference_free='no_exposure' if mask=='500' else 'neutral' if sequence=='C' else 'unresolved'))
        result=o.joined_annotation(corpus,labels,[])
        self.assertEqual(result['effects'][('0.001','graph','ordinary','500','accepted','no_exposure')],1)
        self.assertFalse(any(key[-1]=='helpful' for key in result['effects']))

    def test_duplicate_label_join_rejected(self):
        decisions,contexts=self.validate()
        corpus=SimpleNamespace(cases=self.cases,decisions=decisions,contexts=contexts)
        label=dict(case_id=self.case_id,parent='parent',domain='ordinary',candidate_sha256=o.digest('C'),sequence='C',mask='100',vs_reference_free='neutral')
        with self.assertRaisesRegex(ValueError,'Duplicate diagnostic'):
            o.joined_annotation(corpus,[label,label],[])

    def test_missing_choice_label_rejected(self):
        decisions,contexts=self.validate()
        with self.assertRaisesRegex(ValueError,'lacks qualified candidate'):
            o.joined_annotation(SimpleNamespace(cases=self.cases,decisions=decisions,contexts=contexts),[],[])

    def test_private_missing_event_case_rejected(self):
        decisions,contexts=self.validate();self.case['domain']='private-ordinary'
        with self.assertRaisesRegex(ValueError,'Private event case census'):
            o.joined_annotation(SimpleNamespace(cases=self.cases,decisions=decisions,contexts=contexts),[],[])

    def test_private_raw_harm_and_accepted_preservation_distinguished(self):
        decisions,contexts=self.validate();self.case['domain']='private-ordinary'
        row=decisions[(self.case_id,'0.001','graph')]
        row.update(raw='A',raw_sha256=o.digest('A'))
        corpus=SimpleNamespace(cases=self.cases,decisions=decisions,contexts=contexts)
        labels=[];events=[]
        for sequence,call in (('A','ref'),('C','alt')):
            for mask in ('100','500'):
                labels.append(dict(case_id=self.case_id,parent='parent',domain='private-ordinary',candidate_sha256=o.digest(sequence),sequence=sequence,
                    mask=mask,vs_reference_free='no_exposure'))
            events.append(dict(case_id=self.case_id,parent='parent',domain='private-ordinary',candidate_sha256=o.digest(sequence),event_id='event',call=call,
                native_call='alt',free_call='alt',alt_to_ref='1' if call=='ref' else '0',exact_alt_support_loss='1' if call=='ref' else '0',
                alt_consequence_unresolved='0'))
        result=o.joined_annotation(corpus,labels,events)
        self.assertEqual(result['private'][('0.001','graph','private-ordinary','raw','alt','ref')],1)
        self.assertEqual(result['private'][('0.001','graph','private-ordinary','accepted','alt','alt')],1)


class PacketControls(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name)/'packet.tsv'
        self.wire=dict(candidate_schema='candidate/1',candidate_records=dict(CASE=['case_id'],CAND=['case_id','sequence','origins','log_mass'],BASE=['case_id','role','sequence']),
                       origins=dict(native=1,escape=2),enums=dict(baseline_role=['reference_free']))
        self.rows=['SCHEMA\tcandidate/1\t'+'a'*64,'CASE\tcase','CAND\tcase\tC\t3\t1','BASE\tcase\treference_free\tC']

    def read(self):
        self.path.write_text('\n'.join(self.rows)+'\n')
        return o.read_packet(self.path,self.wire)

    def test_packet_qualified_pool(self):
        _,cases,pools,bases=self.read()
        self.assertEqual((set(cases),pools['case'][o.digest('C')],bases['case']['reference_free']['sequence']),({'case'},('C',1.0),'C'))

    def test_duplicate_case_rejected(self):
        self.rows.append('CASE\tcase')
        with self.assertRaisesRegex(ValueError,'Duplicate model case'):
            self.read()

    def test_conflicting_candidate_score_rejected(self):
        self.rows.append('CAND\tcase\tC\t3\t0.9')
        with self.assertRaisesRegex(ValueError,'Conflicting retained signal'):
            self.read()

    def test_unscored_eligible_candidate_rejected(self):
        self.rows[2]='CAND\tcase\tC\t3\t.'
        with self.assertRaisesRegex(ValueError,'unscored'):
            self.read()


class Edits(unittest.TestCase):
    @staticmethod
    def splice(sequence,quality,edits):
        for edit in sorted(edits,key=lambda item:item['start'],reverse=True):
            a,b=edit['start'],edit['end']
            sequence=sequence[:a]+edit['replacement']+sequence[b:]
            quality=quality[:a]+'!'*len(edit['replacement'])+quality[b:]
        return sequence,quality

    def setUp(self):
        self.originals=dict(parent=dict(sequence='AACCGG',quality='123456'))
        self.observer=SimpleNamespace(splice=self.splice,independent_splice=self.splice)

    def test_disabled_identity_preserves_seq_and_quality(self):
        row=o.sam_bytes(['parent'],self.originals,[],self.observer).decode().splitlines()[1].split('\t')
        self.assertEqual(row[9:],['AACCGG','123456'])

    def test_edit_reconstruction_and_outside_quality(self):
        edits=[dict(parent='parent',start=2,end=4,stock='CC',replacement='T')]
        row=o.sam_bytes(['parent'],self.originals,edits,self.observer).decode().splitlines()[1].split('\t')
        self.assertEqual(row[9:],['AATGG','12!56'])

    def test_overlapping_edits_reject(self):
        edits=[dict(start=1,end=4,stock='ACC',replacement='T'),dict(start=3,end=5,stock='CG',replacement='A')]
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            o.validate_edits('AACCGG',edits)

    def test_noop_quality_change_rejects(self):
        with self.assertRaisesRegex(ValueError,'no-op'):
            o.validate_edits('AACCGG',[dict(start=2,end=4,stock='CC',replacement='CC')])

    def test_wrong_stock_rejects(self):
        with self.assertRaisesRegex(ValueError,'attachment'):
            o.validate_edits('AACCGG',[dict(start=2,end=4,stock='GG',replacement='T')])

    def test_foreign_parent_rejects(self):
        with self.assertRaisesRegex(ValueError,'Foreign edited parent'):
            o.sam_bytes(['parent'],self.originals,[dict(parent='other')],self.observer)

    def test_duplicate_parent_rejects(self):
        with self.assertRaisesRegex(ValueError,'census'):
            o.sam_bytes(['parent','parent'],self.originals,[],self.observer)

    def test_aliases_require_exact_bytes(self):
        canonical,aliases=o.deduplicate(dict(graph=b'one',reference=b'one',none=b'two'))
        self.assertEqual(aliases,dict(graph='graph',none='none',reference='graph'))
        self.assertEqual(canonical,dict(graph=b'one',none=b'two'))


class Receipts(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.raw=self.root/'logs/context-feedback/recorder-root/logs/fixture'
        self.raw.mkdir(parents=True)
        self.argv=['uv','run','--no-sync','python','worker.py']
        self.boundary=SimpleNamespace(pin=self.pin,check=self.check,read=lambda path:json.loads(Path(path).read_text()))
        values={'command.sh':o.shlex.join(self.argv)+'\n','cwd.txt':str(self.root)+'\n',
                'start.txt':'2026-10-24T22:00:00Z\n','end.txt':'2026-10-24T22:00:01Z\n','exit-status.txt':'0\n',
                'stdout':'{}\n','stderr':'',
                'time.txt':'\tCommand being timed: "'+' '.join(self.argv)+'"\n\tExit status: 0\n\tUser time (seconds): 0\n\tSystem time (seconds): 0\n\tMaximum resident set size (kbytes): 1\n\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:01.00\n'}
        for name,value in values.items():(self.raw/name).write_text(value)

    @staticmethod
    def pin(path):
        path=Path(path).resolve()
        return dict(path=str(path),size=path.stat().st_size,sha256=o.hashlib.sha256(path.read_bytes()).hexdigest())

    def check(self,pin):
        o.require(self.pin(pin['path'])==pin,'Changed fixture')

    def test_complete_raw_record(self):
        self.assertEqual(set(o.raw_receipt(self.raw,self.argv,self.root,self.boundary)),set(o.RAW_FILES))

    def test_missing_stderr_rejected(self):
        (self.raw/'stderr').unlink()
        with self.assertRaises(FileNotFoundError):
            o.raw_receipt(self.raw,self.argv,self.root,self.boundary)

    def test_wrong_cwd_rejected(self):
        (self.raw/'cwd.txt').write_text('/wrong\n')
        with self.assertRaisesRegex(ValueError,'cwd'):
            o.raw_receipt(self.raw,self.argv,self.root,self.boundary)

    def test_missing_time_fields_rejected(self):
        (self.raw/'time.txt').write_text('')
        with self.assertRaises((KeyError,ValueError)):
            o.raw_receipt(self.raw,self.argv,self.root,self.boundary)

    def test_corrupt_exit_rejected(self):
        (self.raw/'exit-status.txt').write_text('2\n')
        with self.assertRaisesRegex(ValueError,'exit'):
            o.raw_receipt(self.raw,self.argv,self.root,self.boundary)

    def test_changed_command_rejected(self):
        (self.raw/'command.sh').write_text('false\n')
        with self.assertRaisesRegex(ValueError,'command'):
            o.raw_receipt(self.raw,self.argv,self.root,self.boundary)


class GenuineHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('CONTEXT_MODEL_OBSERVER_FIXTURE') != '1':
            raise unittest.SkipTest('Bounded qualification must enable the retained model fixture')
        cls.corpus=o.load_corpus()

    def test_consumed_frame_and_arm_census(self):
        self.assertEqual((len(self.corpus.cases),len(self.corpus.decisions),len(self.corpus.contexts)),(368,2944,1472))

    def test_actual_none_parent_handoff_is_byte_identical(self):
        observer,parents,originals,_,_,_,old_free=o.emission_material(self.corpus)
        edits=o.edits_for(self.corpus,'0.001','none',originals)
        actual=o.sam_bytes(parents,originals,edits,observer)
        self.assertEqual(actual,Path(old_free['sam']['path']).read_bytes())

    def test_actual_missing_native_result_rejects_without_mutation(self):
        program=self.corpus.program
        directory=ROOT/'results/context-feedback/v5-model-query0-1/slice-0'
        seal=program.c.read(directory.parent/'complete.json')
        native=next(item for item in seal['native'] if item['path']==str(directory/'complete.json'))
        attempt=program.c.read(directory/'attempt.json')
        stage=next(program.w.evidence.stage(item,program.c) for item in seal['stages']
                   if program.c.read(item['path'])['argv']==attempt['argv'])
        real_open=Path.open
        def opened(path,*args,**kwargs):
            if path==directory/'result.json':
                raise FileNotFoundError(str(path))
            return real_open(path,*args,**kwargs)
        with mock.patch.object(Path,'open',opened):
            with self.assertRaises(FileNotFoundError):
                o.native_unit(native,stage,program,program.sources(),self.corpus.cases_pin)


if __name__ == '__main__':
    unittest.main()
