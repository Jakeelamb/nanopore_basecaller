#!/usr/bin/env python3
"""Acquire and price pinned regional context bytes without decoding supporting reads."""
import argparse
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('source.json')
RECORDER = ROOT / 'scripts/record-command.sh'
RESULTS = ROOT / 'results/support-context'
MIB = 1024 * 1024
PREVIOUS_CONTROLLER = dict(path=str(Path(__file__).with_name('transport.py').resolve()), size=23883,
                           sha256='374a10ec66511478649fa86d12199f645c2debecb01905b4b8312258dafeaba8')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(MIB):
            h.update(block)
    return dict(path=str(path), size=path.stat().st_size, sha256=h.hexdigest())


def check(value):
    require(pin(value['path']) == value, 'Missing or changed pinned file: ' + value['path'])
    return Path(value['path'])


def read(path):
    return json.loads(Path(path).read_text())


def sync_directory(path):
    descriptor = os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_directory(path):
    path = Path(path)
    if not path.exists():
        create_directory(path.parent)
        path.mkdir(exist_ok=True)
        sync_directory(path)
        sync_directory(path.parent)


def fresh(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(Path(path).parent)


def source():
    value = read(SOURCE)
    require(value['schema'] == 'context-support-source/1' and value['donor'] == 'HG002'
            and value['flowcell'] == 'PAW71238' and value['role'] == 'exposed_development_support'
            and value['flank_bases'] == 100, 'Unexpected support source or target policy')
    require(set(value['objects']) == {'cram', 'crai'}, 'Unexpected remote objects')
    for item in value['objects'].values():
        require(set(item) == {'url', 'size', 'etag', 'last_modified', 'version_id'}
                and urllib.parse.urlsplit(item['url']).scheme == 'https'
                and urllib.parse.urlsplit(item['url']).netloc == 'ont-open-data.s3.amazonaws.com'
                and '/HG002/PAW71238/' in item['url'] and item['size'] > 0,
                'Unexpected remote object identity')
    check(value['metadata_lookup'])
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError('Redirect refused before reading its body')


class Transport:
    def __init__(self, output, maximum_bytes, maximum_request=MIB, opener=None):
        require(0 < maximum_request <= MIB and maximum_bytes > 0, 'Invalid transfer bound')
        self.output = Path(output)
        self.chunks = self.output / 'chunks'
        create_directory(self.chunks)
        self.maximum_bytes = maximum_bytes
        self.maximum_request = maximum_request
        self.consumed = sum(p.stat().st_size for p in self.chunks.glob('*/*.data'))
        self.reserved = 0
        self.proofs = []
        for path in self.chunks.glob('*/*.attempt.json'):
            record = read(path)
            begin,end = record['range']
            require(0 <= begin < end <= record['object']['size'] and end-begin <= maximum_request
                    and record['reserved_bytes'] == end-begin+1, 'Invalid retained range reservation')
            self.reserved += record['reserved_bytes']
        require(max(self.consumed,self.reserved) <= maximum_bytes, 'Existing transport bytes exceed aggregate cap')
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def fetch(self, name, obj, begin, end):
        require(name in ('cram', 'crai') and 0 <= begin < end <= obj['size']
                and end - begin <= self.maximum_request, 'Range outside declared object/request cap')
        key = name + '-' + str(begin) + '-' + str(end)
        directory = self.chunks / key
        create_directory(directory)
        for receipt in sorted(directory.glob('*.json')):
            if receipt.name.endswith('.attempt.json'):
                continue
            saved = read(receipt)
            require(saved['object'] == obj and saved['range'] == [begin, end]
                    and saved['complete'] is True, 'Cached range identity differs')
            request_proof = read(check(saved['request']))
            require(request_proof['object'] == obj and request_proof['range'] == [begin,end]
                    and request_proof['controller'] == pin(__file__)
                    and request_proof['source'] == pin(SOURCE), 'Cached range source differs')
            check(saved['payload'])
            self.proofs.extend([pin(receipt),saved['request']])
            return saved['payload']
        require(self.reserved + end - begin + 1 <= self.maximum_bytes,
                'Range plus one-byte overrun detection exceeds aggregate cap')
        request_id = uuid.uuid4().hex
        payload = directory / (request_id + '.data')
        target = obj['url']
        request = urllib.request.Request(target, headers={
            'Range': f'bytes={begin}-{end-1}', 'Accept-Encoding': 'identity',
            'If-Match': obj['etag'], 'If-Unmodified-Since': obj['last_modified']})
        attempt = dict(object=obj, range=[begin, end], argv_url=target, reserved_bytes=end-begin+1,
                       controller=pin(__file__), source=pin(SOURCE),
                       request_headers=dict(request.header_items()), started_utc=datetime.now(timezone.utc).isoformat())
        fresh(directory / (request_id + '.attempt.json'), attempt)
        self.reserved += end-begin+1
        with self.opener.open(request, timeout=20) as response:
            h = response.headers
            require(response.status == 206, 'HTTP response is not 206; body not read')
            require(h.get('Content-Range') == f'bytes {begin}-{end-1}/{obj["size"]}'
                    and h.get('Content-Length') == str(end-begin)
                    and h.get('ETag') == obj['etag'] and h.get('Last-Modified') == obj['last_modified']
                    and h.get('x-amz-version-id') == obj['version_id']
                    and h.get('Content-Encoding', 'identity') == 'identity',
                    'Remote range or immutable metadata differs; body not read')
            remaining = end-begin
            with payload.open('xb') as stream:
                while remaining:
                    block = response.read(min(65536, remaining))
                    require(block and len(block) <= remaining, 'Truncated or oversized range body')
                    self.consumed += len(block)
                    require(self.consumed <= self.maximum_bytes, 'Aggregate transport cap reached')
                    stream.write(block)
                    remaining -= len(block)
                extra = response.read(1)
                self.consumed += len(extra)
                stream.write(extra)
                require(not extra, 'Oversized range body')
                stream.flush()
                os.fsync(stream.fileno())
            result = dict(complete=True, object=obj, range=[begin, end], payload=pin(payload),
                          request=pin(directory / (request_id + '.attempt.json')),
                          response_headers=dict(h.items()), finished_utc=datetime.now(timezone.utc).isoformat())
        receipt = directory / (request_id + '.json')
        fresh(receipt, result)
        self.proofs.extend([pin(receipt),result['request']])
        return result['payload']

    def assemble(self, name, obj, begin, end, destination):
        parts = [self.fetch(name, obj, start, min(start+self.maximum_request, end))
                 for start in range(begin, end, self.maximum_request)]
        with Path(destination).open('xb') as target:
            for part in parts:
                with check(part).open('rb') as stream:
                    while block := stream.read(65536):
                        target.write(block)
            target.flush()
            os.fsync(target.fileno())
        return pin(destination), parts


def crai_rows(path, cram_size, maximum_uncompressed=16*MIB):
    with gzip.open(path, 'rb') as stream:
        data = stream.read(maximum_uncompressed+1)
    require(len(data) <= maximum_uncompressed, 'CRAI decompression cap exceeded')
    rows = []
    for line in data.decode('ascii').splitlines():
        require(re.fullmatch(r'-?\d+(?:\t-?\d+){5}', line) is not None, 'Malformed six-column CRAI')
        rid, start, span, container, offset, size = map(int, line.split('\t'))
        require(rid >= -1 and (rid == -1 or start >= 1 and span > 0)
                and 26 <= container < cram_size and offset >= 0 and size > 0
                and container+offset+size < cram_size, 'Invalid CRAI coordinates or extent')
        rows.append((rid, start, span, container, offset, size))
    require(rows and len(rows) == len(set(rows)), 'Empty or duplicate CRAI rows')
    return rows


def target_regions(config):
    check(config['target_summary'])
    auditor_path = check(config['original_auditor'])
    spec = importlib.util.spec_from_file_location('support_original_v2', auditor_path)
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    require(auditor.ROOT == auditor_path.parent.parent and auditor.c.ROOT == auditor.ROOT,
            'Original auditor was relocated')
    identity = auditor.inventory_hash(auditor.sources())
    require(identity == config['old_source_inventory_sha256'], 'Historical source inventory differs')
    proof = auditor.evidence.completed(Path(config['target_summary']['path']).parent, 'full', identity, auditor.c)
    summary = read(config['target_summary']['path'])
    rows = [row for row in summary['outcomes'] if 'native' in row]
    require(len(summary['outcomes']) == 451 and len(rows) == 311, 'Historical target census differs')
    targets, ancestry = [], []
    for row in rows:
        construction = read(check(row['construction']))
        window = construction['original_window']
        require(window['query_index'] == row['query_index'] and window['read_id'] == row['read_id']
                and 0 <= window['core_start'] < window['core_end'], 'Target metadata identity differs')
        targets.append(dict(query=row['query_index'], parent=row['read_id'], contig=window['contig'],
                            start=max(0, window['core_start']-100), end=window['core_end']+100,
                            core_start=window['core_start'], core_end=window['core_end']))
        ancestry.append(row['construction'])
    require(len({r['query'] for r in targets}) == 311, 'Duplicate target query')
    return dict(policy='311 admitted v2 ordinary cores plus fixed100bp flanks',
                targets=targets, construction_pins=ancestry, original_proof=proof)


def header_dictionary(text):
    references, groups = [], []
    for line in text.splitlines():
        fields = line.split('\t')
        if fields[0] not in ('@SQ', '@RG'):
            continue
        tags = dict(part.split(':', 1) for part in fields[1:])
        require(len(tags) == len(fields)-1, 'Duplicate SAM header tag')
        if fields[0] == '@SQ':
            require('SN' in tags and 'LN' in tags and int(tags['LN']) > 0
                    and re.fullmatch('[a-fA-F0-9]{32}', tags.get('M5', '')) is not None,
                    'CRAM reference lacks a valid name, length or M5')
            references.append(dict(name=tags['SN'], length=int(tags['LN']), md5=tags['M5'].lower()))
        else:
            groups.append(tags)
    require(references and len({r['name'] for r in references}) == len(references), 'Missing/duplicate CRAM references')
    require(groups and all(g.get('SM', '').lower() == 'hg002' and g.get('PU') == 'PAW71238' for g in groups),
            'CRAM read groups do not bind expected donor/flowcell')
    return references, groups


def coalesce(ranges):
    result = []
    for a, b in sorted({(a, b) for a, b in ranges}):
        require(0 <= a < b, 'Invalid byte interval')
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result


def price(rows, references, targets, cram_size):
    names = {r['name']: (i, r['length']) for i, r in enumerate(references)}
    containers = sorted({r[3] for r in rows})
    ends = dict(zip(containers, containers[1:]+[cram_size]))
    by_reference = {}
    for row in rows:
        require(row[0] < len(references) and row[3]+row[4]+row[5] < ends[row[3]],
                'CRAI reference ID or container lower extent differs')
        by_reference.setdefault(row[0],[]).append(row)
    selected, overlaps = set(), 0
    for target in targets:
        require(target['contig'] in names, 'Target contig absent from actual CRAM header')
        rid, length = names[target['contig']]
        require(0 <= target['start'] < target['end'] <= length, 'Target flank exceeds actual reference bounds')
        for _, start, span, container, _, _ in by_reference.get(rid,[]):
            if start-1 < target['end'] and target['start'] < start-1+span:
                selected.add(container)
                overlaps += 1
    ranges = coalesce((offset, ends[offset]) for offset in selected)
    return dict(ranges=ranges, bytes=sum(b-a for a,b in ranges), selected_containers=len(selected),
                indexed_overlap_pairs=overlaps, policy='complete containers, including unselected slices; final container through EOF',
                reference_md5_qualified=False, physical_family_exclusion_qualified=False, biological_qualification=False)


def native_header(header, samtools, expected_sha256, directory):
    binary, recorder_source = pin(samtools), pin(RECORDER)
    require(binary['sha256'] == expected_sha256, 'samtools binary identity differs')
    (ROOT/'logs').mkdir(exist_ok=True)
    name = 'support-header-' + uuid.uuid4().hex
    argv = [str(RECORDER), name, str(Path(samtools).resolve()), 'view', '--no-PG', '-H', header['path']]
    completed, failure = None, None
    started = datetime.now(timezone.utc).isoformat()
    try:
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
    except BaseException as error:
        failure = repr(error)
    finally:
        fresh(directory/'header-launch.json',dict(argv=argv, cwd=str(ROOT),
              started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(), failure=failure,
              exit=None if completed is None else completed.returncode,
              stdout=None if completed is None else completed.stdout,
              stderr=None if completed is None else completed.stderr,
              samtools=binary, recorder=recorder_source))
    require(failure is None and completed is not None and completed.returncode == 0,
            'Native CRAM header extraction failed; launch and raw receipts retained')
    raw = Path(completed.stdout.strip()).resolve()
    require(raw.is_relative_to(ROOT/'logs') and raw.is_dir(), 'Native raw recorder path differs')
    expected = [str(Path(samtools).resolve()), 'view', '--no-PG', '-H', header['path']]
    require(shlex.split((raw/'command.sh').read_text()) == expected
            and (raw/'cwd.txt').read_text().strip() == str(ROOT)
            and (raw/'exit-status.txt').read_text().strip() == '0', 'Native header raw command/cwd/exit differs')
    begin,end = ((raw/name).read_text().strip() for name in ('start.txt','end.txt'))
    require(begin.endswith('Z') and end.endswith('Z')
            and datetime.fromisoformat(begin) <= datetime.fromisoformat(end), 'Native header raw clocks differ')
    times = {}
    for line in (raw/'time.txt').read_text().splitlines():
        if line.startswith('\t') and ': ' in line:
            key,value = line.strip().split(': ',1)
            times[key] = value
    require(times.get('Exit status') == '0'
            and times.get('Command being timed') == '"'+' '.join(expected)+'"'
            and float(times['User time (seconds)']) >= 0 and float(times['System time (seconds)']) >= 0
            and int(times['Maximum resident set size (kbytes)']) > 0
            and times['Elapsed (wall clock) time (h:mm:ss or m:ss)'], 'Native header GNU time evidence differs')
    files = [pin(raw/n) for n in ('command.sh','cwd.txt','start.txt','end.txt','exit-status.txt','stdout','stderr','time.txt')]
    return pin(raw/'stdout'), [*files,pin(directory/'header-launch.json')]


def inspect(config, transfer, attempt, samtools, expected_sha256):
    targets = target_regions(config)
    crai = config['objects']['crai']
    require(crai['size'] == 537321, 'Frozen CRAI size differs')
    index, index_parts = transfer.assemble('crai',crai,0,crai['size'],attempt/'index.crai')
    rows = crai_rows(index['path'],config['objects']['cram']['size'])
    header_end = min(r[3] for r in rows)
    require(26 < header_end <= 4*MIB, 'CRAM header prefix exceeds fixed4MiB cap')
    header, header_parts = transfer.assemble('cram',config['objects']['cram'],0,header_end,attempt/'header.cram')
    with Path(header['path']).open('rb') as stream:
        require(stream.read(6) == b'CRAM\x03\x00', 'Unexpected CRAM version/file definition')
    native, receipts = native_header(header,samtools,expected_sha256,attempt)
    require(native['size'] <= 4*MIB, 'Native SAM header text exceeds fixed4MiB cap')
    references, groups = header_dictionary(check(native).read_text())
    result = price(rows,references,targets['targets'],config['objects']['cram']['size'])
    fresh(attempt/'targets.json',targets)
    fresh(attempt/'price.json',dict(result, references=references, read_groups=groups))
    return [index,header,native,pin(attempt/'targets.json'),pin(attempt/'price.json'),*receipts,*index_parts,*header_parts]


def fetch_ranges(config, transfer, attempt, manifest_pin, maximum_payload):
    manifest = read(check(manifest_pin))
    require(manifest['phase'] == 'inspect' and manifest['complete'] is True
            and manifest['source'] == pin(SOURCE)
            and manifest['controller'] in (pin(__file__), PREVIOUS_CONTROLLER),
            'Qualified inspect manifest required')
    check(manifest['controller'])
    for item in manifest['files']:
        check(item)
    prices = [p for p in manifest['files'] if Path(p['path']).name == 'price.json']
    require(len(prices) == 1, 'Inspect price pin missing or duplicated')
    plan = read(check(prices[0]))
    targets = [p for p in manifest['files'] if Path(p['path']).name == 'targets.json']
    require(len(targets) == 1 and read(check(targets[0])) == target_regions(config),
            'Historical target custody differs on inspect reuse')
    require(coalesce(plan['ranges']) == plan['ranges']
            and all(0 <= a < b <= config['objects']['cram']['size'] for a,b in plan['ranges'])
            and plan['bytes'] <= maximum_payload and plan['bytes'] == sum(b-a for a,b in plan['ranges']),
            'Declared complete-container payload exceeds acquisition cap')
    parts = []
    for begin,end in plan['ranges']:
        for start in range(begin,end,transfer.maximum_request):
            parts.append(transfer.fetch('cram',config['objects']['cram'],start,min(start+transfer.maximum_request,end)))
    fresh(attempt/'acquired-ranges.json',dict(inspect=manifest_pin, ranges=plan['ranges'], files=parts,
          encoded_bytes=plan['bytes'], reads_decoded=False, biological_qualification=False))
    return [manifest_pin,*manifest['files'],pin(attempt/'acquired-ranges.json'),*parts]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('inspect','fetch'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--maximum-network-bytes',type=int,required=True)
    parser.add_argument('--samtools',type=Path)
    parser.add_argument('--samtools-sha256')
    parser.add_argument('--inspect-manifest',type=Path)
    parser.add_argument('--inspect-manifest-sha256')
    parser.add_argument('--maximum-payload-bytes',type=int)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    config = source()
    output = args.output.resolve()
    require(output.is_relative_to(RESULTS) and output != RESULTS, 'Output outside owned support results')
    require(0 < args.maximum_network_bytes <= (8*MIB if args.phase == 'inspect' else 512*MIB), 'Network cap exceeds phase bound')
    if args.phase == 'inspect':
        require(args.samtools is not None and args.samtools_sha256 is not None, 'Pinned native samtools required')
    else:
        require(args.inspect_manifest is not None and args.inspect_manifest_sha256 is not None
                and args.maximum_payload_bytes is not None and 0 < args.maximum_payload_bytes <= 512*MIB,
                'Pinned inspect manifest and explicit payload cap required')
    existed = output.exists()
    require(not existed or args.resume, 'Existing attempt requires explicit resume')
    create_directory(output)
    with (output/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        attempt = output/uuid.uuid4().hex
        create_directory(attempt)
        fresh(attempt/'attempt.json',dict(phase=args.phase, argv=os.sys.argv, source=pin(SOURCE),
              controller=pin(__file__), started_utc=datetime.now(timezone.utc).isoformat(),
              maximum_network_bytes=args.maximum_network_bytes, external_host_supervision_required=True))
        transfer = None
        try:
            transfer = Transport(output,args.maximum_network_bytes)
            files = inspect(config,transfer,attempt,args.samtools,args.samtools_sha256) if args.phase == 'inspect' else fetch_ranges(
                config,transfer,attempt,dict(pin(args.inspect_manifest),sha256=args.inspect_manifest_sha256),args.maximum_payload_bytes)
        except BaseException as error:
            fresh(attempt/'terminal.json',dict(operation_finished=False, error=repr(error),
                  reserved_payload_bytes=None if transfer is None else transfer.reserved,
                  consumed_cache_payload_bytes=None if transfer is None else transfer.consumed,
                  finished_utc=datetime.now(timezone.utc).isoformat()))
            raise
        fresh(attempt/'terminal.json',dict(operation_finished=True, error=None,
              reserved_payload_bytes=transfer.reserved, consumed_cache_payload_bytes=transfer.consumed,
              finished_utc=datetime.now(timezone.utc).isoformat()))
        files.append(pin(attempt/'terminal.json'))
        files.extend(transfer.proofs)
        files.append(pin(attempt/'attempt.json'))
        unique = {p['path']:p for p in files}
        require(all(unique[p['path']] == p for p in files), 'Conflicting output pins')
        fresh(attempt/'complete.json',dict(schema='context-support-transport/1', complete=True, phase=args.phase,
              source=pin(SOURCE), controller=pin(__file__), files=list(unique.values()),
              consumed_cache_payload_bytes=transfer.consumed, reserved_payload_bytes=transfer.reserved,
              finished_utc=datetime.now(timezone.utc).isoformat(),
              reads_decoded=False, independent_confirmation=False, biological_qualification=False))
        descriptor = os.open(attempt,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        print(json.dumps(dict(completion=pin(attempt/'complete.json'))))


if __name__ == '__main__':
    main()
