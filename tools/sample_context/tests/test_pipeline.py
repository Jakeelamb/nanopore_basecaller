import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'pipeline.py'
SPEC = importlib.util.spec_from_file_location('sample_context_metadata', MODULE)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class MetadataControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sample-context-metadata-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def file(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        elif isinstance(value, str):
            path.write_text(value)
        else:
            path.write_text(json.dumps(value))
        return p.pin(path)

    def test_json_ranges_and_subtraction(self):
        ranges = json.loads('[[20,30],[10,20],[10,20],[40,50]]')
        self.assertEqual(p.coalesce(ranges), [[10,30],[40,50]])
        self.assertEqual(p.subtract(ranges, [[15,25],[45,55]]), [[10,15],[25,30],[40,45]])
        self.assertTrue(p.covered([12,29], ranges))
        self.assertFalse(p.covered([29,41], ranges))
        with self.assertRaises(ValueError):
            p.coalesce([[30,20]])

    def test_private_geometry_is_priced_and_missing_is_explicit(self):
        rows = [(0,101,50,1000,0,100),(0,1001,50,2000,0,100),(0,9001,50,3000,0,100)]
        references = [dict(name='chr1',length=10000,md5='a'*32)]
        cases = [dict(id='ordinary/0',contig='chr1',core_begin=110,core_end=120,ref_begin=100,ref_end=140),
                 dict(id='private/1',contig='chr1',core_begin=1010,core_end=1020,ref_begin=1000,ref_end=1040)]
        result = p.container_plan(rows,references,cases,[[1000,2000]])
        self.assertEqual([r['id'] for r in result['cases']], ['ordinary/0','private/1'])
        self.assertEqual([r['covered'] for r in result['cases']], [True,False])
        self.assertEqual(result['required_ranges'],[[1000,3000]])
        self.assertEqual(result['additional_ranges'],[[2000,3000]])
        self.assertEqual(result['additional_encoded_bytes'],1000)
        self.assertEqual(result['selected_containers'],2)

    def test_native_dictionary_m5_all_references(self):
        text = '@HD\tVN:1.6\n@SQ\tSN:chr1\tLN:1000\tM5:'+'a'*32+'\n@SQ\tSN:chr2\tLN:2000\tM5:'+'b'*32+'\n'
        actual = p.dictionary(text)
        references = [dict(name='chr1',length=1000,md5='a'*32),dict(name='chr2',length=2000,md5='b'*32)]
        p.match_dictionary(references,actual)
        for bad in [dict(name='chr2',length=2001,md5='b'*32),dict(name='chr2',length=2000,md5='c'*32),dict(name='missing',length=2000,md5='b'*32)]:
            with self.assertRaises(ValueError):
                p.match_dictionary([references[0],bad],actual)
        with self.assertRaises(ValueError):
            p.dictionary('@SQ\tSN:chr1\tLN:1000\n')
        with self.assertRaises(ValueError):
            p.dictionary(text+text)

    def test_original_eof_template_and_corruption(self):
        self.assertEqual(len(p.EOF),38)
        p.verify_eof(p.EOF)
        historical = bytearray(p.EOF)
        historical[9] |= 0xf0
        p.verify_eof(bytes(historical))
        for value in [p.EOF[:-1],p.EOF+b'\0',b'\0'+p.EOF[1:]]:
            with self.assertRaises(ValueError):
                p.verify_eof(value)

    def test_range_payload_and_original_response_identity(self):
        source = dict(size=100,url='https://example.invalid/pinned',etag='"fixed"',last_modified='date',version_id='version')
        config = self.file('source.json',{})
        controller = self.file('controller.py','synthetic metadata fixture')
        payload = self.file('bytes.data',b'abc')
        request = self.file('request.json',dict(object=source,range=[10,13],source=config,controller=controller,reserved_bytes=4))
        receipt = dict(complete=True,object=source,range=[10,13],payload=payload,request=request,
                       response_headers={'Content-Range':'bytes 10-12/100','Content-Length':'3','ETag':'"fixed"',
                                         'Last-Modified':'date','x-amz-version-id':'version'})
        with patch.object(p,'SOURCE_SHA',config['sha256']):
            good = self.file('good.json',receipt)
            self.assertEqual(p.range_receipt(good,source,controller),(10,13,payload))
            receipt['response_headers']['x-amz-version-id']='other'
            with self.assertRaises(ValueError):
                p.range_receipt(self.file('wrong-version.json',receipt),source,controller)
            Path(payload['path']).write_bytes(b'abd')
            with self.assertRaises(ValueError):
                p.range_receipt(good,source,controller)

    def stage_fixture(self):
        argv = ['/synthetic/samtools','dict','/synthetic/reference']
        raw = {name:self.file('raw/'+name,text) for name,text in {
            'command.sh':shlex_join(argv)+'\n','cwd.txt':str(p.ROOT)+'\n','start.txt':'2026-10-24T00:00:00Z\n',
            'end.txt':'2026-10-24T00:00:01Z\n','exit-status.txt':'0\n','stdout':'synthetic\n','stderr':'',
            'time.txt':'\tCommand being timed: "'+' '.join(argv)+'"\n\tExit status: 0\n\tUser time (seconds): 0.1\n\tSystem time (seconds): 0.1\n\tMaximum resident set size (kbytes): 1\n\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:01\n'}.items()}
        value = dict(schema='context-feedback-stage/1',argv=argv,exit=0,failure=None,projection_error=None,
                     terminal=self.file('terminal.json',dict(argv=argv,exit=0,failure=None)),
                     group_cleanup=self.file('group.json',dict(terminal=True)),raw=raw,missing_raw=[])
        return argv,value

    def test_missing_linked_recorder_file_is_rejected(self):
        argv,value = self.stage_fixture()
        valid = self.file('stage.json',value)
        self.assertEqual(p.stage(valid,argv),value['raw']['stdout'])
        Path(value['raw']['stderr']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            p.stage(valid,argv)

    def test_wrong_raw_cwd_and_nonterminal_tree_are_rejected(self):
        argv,value = self.stage_fixture()
        value['raw']['cwd.txt']=self.file('wrong-cwd','/other/worktree\n')
        with self.assertRaises(ValueError):
            p.stage(self.file('wrong-stage.json',value),argv)
        value['raw']['cwd.txt']=self.file('correct-cwd',str(p.ROOT)+'\n')
        value['group_cleanup']=self.file('alive-group.json',dict(terminal=False))
        with self.assertRaises(ValueError):
            p.stage(self.file('alive-stage.json',value),argv)

    def test_missing_lineage_has_explicit_unqualified_result(self):
        self.assertEqual(p.lineage(None,{})['mode'],'unavailable')
        self.assertEqual(p.lineage(None,{})['role'],'strict')
        self.assertEqual(p.lineage(None,{},'exploratory_published_protocol')['mode'],'unavailable')

    def lineage_fixture(self):
        evidence = self.file('producer-evidence','synthetic source pin')
        parents = self.file('parents.ids','target0\n')
        groups = [dict(ID='group',SM='hg002',PU='PAW71238',DS='runid='+p.RUN)]
        plan = dict(groups=groups,parents=parents,native_header=evidence)
        contract = dict(schema='sample-producer-lineage/1',supporting_run=p.RUN,supporting_flowcell='PAW71238',
                        target_flowcell='PAW70337',donor='HG002',semantics='pi_original_read_dx_zero_simplex_v1',
                        tag_writer_version='0.8.2',pi_dx_relationships_preserved=True,groups=groups,target_parents=parents,
                        read_level_contract_qualified=True,independent_donor_confirmation=False,
                        known_target_family_names=['ancestor','complement'],
                        evidence={key:[evidence] for key in ['actual_pg_chain','pi_dx_tag_writer','tag_preservation',
                                                           'publisher_library_protocol','target_family_closure']})
        return plan,contract

    def test_lineage_requires_actual_pg_and_target_closure_evidence(self):
        plan,contract = self.lineage_fixture()
        value = self.file('contract.json',contract)
        self.assertEqual(p.lineage(value,plan),dict(contract=value['sha256'],role='strict',mode='strict_qualified',
                                                  exclusions=['ancestor','complement'],assumption_tag='.'))
        del contract['evidence']['target_family_closure']
        with self.assertRaises(ValueError):
            p.lineage(self.file('missing-closure.json',contract),plan)
        contract['evidence']['target_family_closure']=[plan['native_header']]
        contract['supporting_flowcell']='PAW70337'
        with self.assertRaises(ValueError):
            p.lineage(self.file('wrong-run.json',contract),plan)

    def test_unqualified_contract_never_implicitly_enables_exploration(self):
        plan,contract = self.lineage_fixture()
        contract.update(read_level_contract_qualified=False,pi_dx_relationships_preserved=None,
                        operational_producer_declaration_supported=True,exploratory_assumptions=['Published producer preservation is assumed.'],
                        declared_root_rule={key:'pinned assumption' for key in ['present_pi','absent_pi','dx_zero','dx_nonzero','missing_dx','same_root_versions']})
        value = self.file('unqualified-contract.json',contract)
        result = p.lineage(value,plan)
        self.assertEqual(result['mode'],'unavailable')
        self.assertEqual(result['role'],'strict')
        self.assertEqual(result['contract'],value['sha256'])

    def test_explicit_exploratory_role_is_tagged_and_requires_assumptions(self):
        plan,contract = self.lineage_fixture()
        contract.update(read_level_contract_qualified=False,pi_dx_relationships_preserved=None)
        self.assertEqual(p.lineage(self.file('unproved.json',contract),plan,'exploratory_published_protocol')['mode'],'unavailable')
        contract.update(operational_producer_declaration_supported=True,exploratory_assumptions=['Published producer preservation is assumed.'],
                        declared_root_rule={key:'pinned assumption' for key in ['present_pi','absent_pi','dx_zero','dx_nonzero','missing_dx','same_root_versions']})
        result = p.lineage(self.file('exploratory.json',contract),plan,'exploratory_published_protocol')
        self.assertEqual(result['mode'],'assumption_qualified')
        self.assertEqual(result['role'],'exploratory_published_protocol')
        self.assertEqual(result['assumption_tag'],'published_protocol_pi_dx_preservation_v1')
        self.assertNotEqual(result['mode'],'strict_qualified')

    def test_fasta_copy_requires_unique_headers(self):
        fragments = self.file('reference.fasta','>chr1:101-103\nAC\nG\n')
        self.assertEqual(p.fasta(fragments['path']),{'chr1:101-103':'ACG'})
        malformed = self.file('duplicate.fasta','>same\nAC\n>same\nGT\n')
        with self.assertRaises(ValueError):
            p.fasta(malformed['path'])


def shlex_join(argv):
    import shlex
    return shlex.join(argv)


if __name__ == '__main__':
    unittest.main()
