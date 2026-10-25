import gzip
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('support_transport',ROOT/'tools/support_context/transport_fetch_v3.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class Response:
    def __init__(self,body,headers,status=206):
        self.body = io.BytesIO(body)
        self.headers = headers
        self.status = status
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self,*args):
        return None

    def read(self,size):
        self.reads += 1
        return self.body.read(size)


class Opener:
    def __init__(self,response):
        self.response = response
        self.requests = []

    def open(self,request,timeout):
        self.requests.append((request,timeout))
        return self.response


class RangeControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.obj = dict(url='https://ont-open-data.s3.amazonaws.com/fixture.cram',size=100,
                        etag='"frozen"',last_modified='Tue, 14 Jan 2025 17:22:15 GMT',version_id='v/1')
        self.headers = {'Content-Range':'bytes 10-19/100','Content-Length':'10','ETag':'"frozen"',
                        'Last-Modified':self.obj['last_modified'],'x-amz-version-id':'v/1'}

    def transfer(self,body=b'0123456789',headers=None,status=206,maximum_bytes=100):
        response = Response(body,self.headers if headers is None else headers,status)
        opener = Opener(response)
        return t.Transport(self.output,maximum_bytes,20,opener),response,opener

    def test_exact_range_and_version_pinned_conditional_request(self):
        transfer,response,opener = self.transfer()
        value = transfer.fetch('cram',self.obj,10,20)
        self.assertEqual(t.check(value).read_bytes(),b'0123456789')
        request,timeout = opener.requests[0]
        self.assertEqual(request.full_url,self.obj['url'])
        self.assertEqual(request.get_header('Range'),'bytes=10-19')
        self.assertEqual(request.get_header('If-match'),'"frozen"')
        self.assertEqual(timeout,20)
        self.assertEqual(transfer.consumed,10)
        self.assertGreater(response.reads,0)

    def test_http200_refused_before_body(self):
        transfer,response,_ = self.transfer(status=200)
        with self.assertRaisesRegex(ValueError,'not 206'):
            transfer.fetch('cram',self.obj,10,20)
        self.assertEqual(response.reads,0)

    def test_reservation_namespace_synced_before_http(self):
        synced = []
        real_sync = t.sync_directory
        def sync(path):
            real_sync(path)
            synced.append(Path(path))
        response = Response(b'0123456789',self.headers)
        class CheckedOpener:
            def open(inner,request,timeout):
                directory = self.output/'chunks/cram-10-20'
                self.assertIn(self.output,synced)
                self.assertIn(self.output/'chunks',synced)
                self.assertGreaterEqual(synced.count(directory),2)
                self.assertEqual(len(list(directory.glob('*.attempt.json'))),1)
                return response
        with mock.patch.object(t,'sync_directory',side_effect=sync):
            transfer = t.Transport(self.output,100,20,CheckedOpener())
            transfer.fetch('cram',self.obj,10,20)

    def test_header_mismatches_refused_before_body(self):
        changes = {'Content-Range':'bytes 10-19/101','Content-Length':'11','ETag':'"changed"',
                   'Last-Modified':'different','x-amz-version-id':'different','Content-Encoding':'gzip'}
        for key,value in changes.items():
            with self.subTest(header=key):
                transfer,response,_ = self.transfer(headers=dict(self.headers,**{key:value}))
                with self.assertRaisesRegex(ValueError,'metadata differs'):
                    transfer.fetch('cram',self.obj,10,20)
                self.assertEqual(response.reads,0)

    def test_truncation_retained_without_completion(self):
        transfer,_,_ = self.transfer(body=b'123')
        with self.assertRaisesRegex(ValueError,'Truncated'):
            transfer.fetch('cram',self.obj,10,20)
        self.assertEqual([p.stat().st_size for p in (self.output/'chunks').glob('*/*.data')],[3])
        self.assertFalse([p for p in (self.output/'chunks').glob('*/*.json') if not p.name.endswith('.attempt.json')])

    def test_overrun_rejected(self):
        transfer,_,_ = self.transfer(body=b'0123456789X')
        with self.assertRaisesRegex(ValueError,'Oversized'):
            transfer.fetch('cram',self.obj,10,20)
        self.assertEqual(transfer.consumed,11)

    def test_budget_refused_before_request(self):
        transfer,response,opener = self.transfer(maximum_bytes=10)
        with self.assertRaisesRegex(ValueError,'aggregate cap'):
            transfer.fetch('cram',self.obj,10,20)
        self.assertEqual(response.reads,0)
        self.assertFalse(opener.requests)

    def test_request_extent_cap_refused(self):
        transfer,_,opener = self.transfer()
        with self.assertRaisesRegex(ValueError,'request cap'):
            transfer.fetch('cram',self.obj,10,40)
        self.assertFalse(opener.requests)

    def test_resume_reuses_exact_immutable_chunk(self):
        transfer,_,opener = self.transfer()
        expected = transfer.fetch('cram',self.obj,10,20)
        resumed = t.Transport(self.output,100,20,opener)
        self.assertEqual(resumed.fetch('cram',self.obj,10,20),expected)
        self.assertEqual(len(opener.requests),1)
        self.assertEqual(resumed.consumed,10)

    def test_corruption_refuses_resume_without_refetch(self):
        transfer,_,opener = self.transfer()
        value = transfer.fetch('cram',self.obj,10,20)
        Path(value['path']).write_bytes(b'corruption')
        with self.assertRaisesRegex(ValueError,'changed pinned'):
            t.Transport(self.output,100,20,opener).fetch('cram',self.obj,10,20)
        self.assertEqual(len(opener.requests),1)

    def test_failed_partial_counts_against_resume_cap(self):
        transfer,_,_ = self.transfer(body=b'123')
        with self.assertRaises(ValueError):
            transfer.fetch('cram',self.obj,10,20)
        resumed,_,opener = self.transfer(maximum_bytes=13)
        with self.assertRaisesRegex(ValueError,'aggregate cap'):
            resumed.fetch('cram',self.obj,10,20)
        self.assertFalse(opener.requests)

    def test_redirect_does_not_follow_new_url(self):
        with self.assertRaisesRegex(ValueError,'Redirect refused'):
            t.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://untrusted.invalid')


class IndexControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'index.crai'
        self.rows = [(0,101,20,100,10,40),(0,501,20,300,10,40),(1,101,20,500,10,40)]

    def write(self,text):
        self.path.write_bytes(gzip.compress(text.encode('ascii')))

    def test_six_column_gzip_index(self):
        self.write(''.join('\t'.join(map(str,row))+'\n' for row in self.rows))
        self.assertEqual(t.crai_rows(self.path,1000),self.rows)

    def test_index_malformed_extent_and_duplicate_rejected(self):
        for value in ('0\t1\t1\t100\t5\n','-2\t1\t1\t100\t5\t5\n',
                      '0\t1\t1\t100\t5\t1000\n','0\t1\t1\t100\t5\t5\n'*2):
            with self.subTest(value=value):
                self.write(value)
                with self.assertRaises(ValueError):
                    t.crai_rows(self.path,1000)

    def test_decompression_cap_rejected(self):
        self.write('0\t1\t1\t100\t5\t5\n')
        with self.assertRaisesRegex(ValueError,'decompression cap'):
            t.crai_rows(self.path,1000,10)

    def test_complete_container_prices_include_overfetch(self):
        refs = [dict(name='chr1',length=1000),dict(name='chr2',length=1000)]
        targets = [dict(contig='chr1',start=100,end=120),dict(contig='chr2',start=100,end=120)]
        result = t.price(self.rows,refs,targets,1000)
        self.assertEqual(result['ranges'],[[100,300],[500,1000]])
        self.assertEqual(result['bytes'],700)
        self.assertEqual(result['selected_containers'],2)
        self.assertFalse(result['reference_md5_qualified'])
        self.assertFalse(result['physical_family_exclusion_qualified'])

    def test_coordinate_edges_are_half_open(self):
        refs = [dict(name='chr1',length=1000),dict(name='chr2',length=1000)]
        self.assertEqual(t.price(self.rows,refs,[dict(contig='chr1',start=120,end=121)],1000)['bytes'],0)
        self.assertEqual(t.price(self.rows,refs,[dict(contig='chr1',start=99,end=100)],1000)['bytes'],0)
        self.assertEqual(t.price(self.rows,refs,[dict(contig='chr1',start=119,end=120)],1000)['bytes'],200)

    def test_adjacent_container_ranges_coalesce(self):
        self.assertEqual(t.coalesce([(100,300),(300,500),(100,300),(600,700)]),[[100,500],[600,700]])

    def test_json_roundtrip_ranges_coalesce(self):
        import json
        ranges = json.loads(json.dumps([[100,300],[300,500],[100,300],[600,700]]))
        self.assertEqual(t.coalesce(ranges),[[100,500],[600,700]])

    def test_registered_inspect_source_remains_available(self):
        self.assertEqual(t.pin(t.PREVIOUS_CONTROLLER['path']),t.PREVIOUS_CONTROLLER)
        self.assertNotEqual(t.pin(t.__file__),t.PREVIOUS_CONTROLLER)

    def test_missing_contig_or_flank_beyond_end_rejected(self):
        refs = [dict(name='chr1',length=1000),dict(name='chr2',length=1000)]
        for target in (dict(contig='unknown',start=1,end=2),dict(contig='chr1',start=990,end=1010)):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    t.price(self.rows,refs,[target],1000)

    def test_actual_cram_header_requires_reference_md5_and_flowcell(self):
        text = '@SQ\tSN:chr1\tLN:1000\tM5:'+'a'*32+'\n@RG\tID:group\tSM:hg002\tPU:PAW71238\n'
        references,groups = t.header_dictionary(text)
        self.assertEqual(references,[dict(name='chr1',length=1000,md5='a'*32)])
        self.assertEqual(groups[0]['PU'],'PAW71238')
        for invalid in (text.replace('\tM5:'+'a'*32,''),text.replace('PAW71238','PAW70337'),text+text):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    t.header_dictionary(invalid)


if __name__ == '__main__':
    unittest.main()
