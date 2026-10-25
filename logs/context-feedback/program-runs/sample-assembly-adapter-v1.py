"""Assemble acquired payloads while retaining inherited inspect receipt provenance."""
import importlib.util
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_context_metadata_adapter', HERE.parents[2] / 'tools/sample_context/pipeline.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def run(request_pin, output):
    output = Path(output).resolve()
    p.require(output.is_relative_to(p.ROOT / 'results/sample-context') and not output.exists(),
              'Fresh owned assembly adapter output required')
    output.mkdir()
    sources = p.source_inventory() + [p.pin(__file__)]
    p.save(output / 'attempt.json', dict(schema='sample-context-assembly-adapter-attempt/1', request=request_pin,
           sources=sources, started_utc=p.stamp(), original_qualified_pipeline_unchanged=True))
    try:
        request = p.read(request_pin)
        metadata = p.load_plan(request['plan'])
        p.load_reference(request['reference'], request['plan'], metadata)
        inspection = p.transport_completion(metadata['inspect'], 'inspect')
        fetched = p.transport_completion(request['fetch'], 'fetch')
        acquired = p.read(p.named(fetched['files'], 'acquired-ranges.json'))
        p.require(acquired['inspect'] == metadata['inspect'] and request['fetch'] == metadata['fetch']
                  and p.coalesce(acquired['ranges']) == metadata['retained_ranges'], 'Assembled range set differs from plan')
        source = p.read(fetched['source'])['objects']['cram']
        payloads = {value['path']: value for value in acquired['files']}
        parts, selected_receipts, inherited = [], [], []
        for value in fetched['files']:
            if not value['path'].endswith('.json') or value['path'].endswith('.attempt.json'):
                continue
            candidate = p.read(value)
            if not (candidate.get('complete') is True and candidate.get('object') == source and 'payload' in candidate):
                continue
            # Membership precedes the fetch-controller guard; inherited inspect files retain their own controller.
            if candidate['payload']['path'] not in payloads:
                p.require(value in inspection['files'], 'Unacquired receipt is outside the exact inherited inspect')
                part = p.range_receipt(value, source, inspection['controller'])
                inherited.append(dict(receipt=value, range=[part[0], part[1]], payload=part[2],
                                      controller=inspection['controller'], selected_acquisition_payload=False))
                continue
            parts.append(p.range_receipt(value, source, fetched['controller']))
            selected_receipts.append(value)
        parts.sort(key=lambda row: row[0])
        p.require(len(payloads) == len(acquired['files']) and len(parts) == len(payloads)
                  and len({row[2]['path'] for row in parts}) == len(parts)
                  and p.coalesce([[a, b] for a, b, _ in parts]) == acquired['ranges']
                  and sum(b-a for a, b, _ in parts) == acquired['encoded_bytes'],
                  'Acquired complete-container chunks contain gaps/duplicates/foreign ranges')
        p.require(selected_receipts and inherited, 'Genuine selected/inherited metadata handoff required')
        wrong = dict(fetched['controller'], sha256='0' * 64)
        try:
            p.range_receipt(selected_receipts[0], source, wrong)
        except ValueError as error:
            p.require(str(error) == 'Acquired range controller differs', 'Unexpected selected-controller rejection')
            rejection = str(error)
        else:
            raise ValueError('Wrong-controller selected chunk was accepted')
        p.save(output / 'handoff.json', dict(schema='sample-context-assembly-handoff/1',
               inspect=metadata['inspect'], fetch=request['fetch'], inherited_inspect_provenance=inherited,
               acquired_controller=fetched['controller'], acquired_payload_count=len(parts),
               acquired_encoded_bytes=acquired['encoded_bytes'], positive_genuine_handoff=True,
               wrong_controller_selected_chunk_rejected=rejection, readonly_observation_control=True,
               new_requests=0, original_producers_replayed=False))
        header = p.named(inspection['files'], 'header.cram')
        begin, end, tail = p.range_receipt(request['eof_receipt'], source)
        p.require([begin, end] == [p.CRAM_SIZE-38, p.CRAM_SIZE], 'EOF must be fetched at the original exact source tail')
        eof = p.check(tail).read_bytes()
        p.verify_eof(eof)
        p.require(all(a >= header['size'] for a, _, _ in parts), 'Container range overlaps header prefix')
        expected_size = header['size'] + acquired['encoded_bytes'] + (0 if parts and parts[-1][1] == p.CRAM_SIZE else 38)
        p.require(expected_size <= 512*p.MIB and shutil.disk_usage(output).free >= 30*1024**3 + expected_size,
                  'Derivative size/disk reserve exceeds proposed unit')
        derivative = output / 'selected.cram'
        with derivative.open('xb') as target:
            for value in [header] + [row[2] for row in parts]:
                with p.check(value).open('rb') as stream:
                    shutil.copyfileobj(stream, target, p.MIB)
            if not parts or parts[-1][1] != p.CRAM_SIZE:
                target.write(eof)
            target.flush()
            p.os.fsync(target.fileno())
        p.sync(output)
        p.require(derivative.stat().st_size == expected_size, 'Derivative CRAM size differs')
        with derivative.open('rb') as stream:
            p.require(stream.read(6) == b'CRAM\x03\x00', 'Derivative is not CRAM v3')
            stream.seek(-38, 2)
            p.require(stream.read() == eof, 'Derivative exact original EOF differs')
        p.save(output / 'assembly.json', dict(schema='sample-context-assembly/1', plan=request['plan'],
               reference=request['reference'], inspect=metadata['inspect'], fetch=request['fetch'],
               source_object=source, header=header, original_parts=[dict(range=[a, b], payload=value) for a, b, value in parts],
               eof_receipt=request['eof_receipt'], eof_payload=tail, derivative=p.pin(derivative),
               original_files_unchanged=True, reads_decoded=False, quickcheck_still_required=True,
               assembly_adapter=p.pin(__file__), handoff=p.pin(output / 'handoff.json')))
        for value in [header, tail, request_pin] + list(payloads.values()) + sources:
            p.check(value)
        files = [p.pin(output / name) for name in ('selected.cram', 'assembly.json', 'handoff.json')]
        p.save(output / 'complete.json', dict(schema='sample-context-assembly-adapter-complete/1', complete=True,
               request=request_pin, files=files, sources=sources, finished_utc=p.stamp(),
               native_tools_executed=False, network_requests=0, biological_qualification=False))
        return p.pin(output / 'complete.json'), {Path(value['path']).name: value for value in files}
    except BaseException as error:
        p.save(output / 'failure.json', dict(complete=False, error=repr(error), finished_utc=p.stamp()))
        raise
