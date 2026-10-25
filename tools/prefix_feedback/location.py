#!/usr/bin/env python3
"""Consume qualified prefix SEQ/Q; locate before constructing reference context."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import sys

ROOT = Path(__file__).resolve().parents[2]
PREFIX = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-prefix')
AUDIT = PREFIX/'logs/context-feedback-program/reviews/prefix-runtime-audit.py'
AUDIT_SHA = '83b3a30a1f4fd6d89a5c4d341370ca000b67774602e6b14f1c4a3eda6a85faa8'
REVIEW = PREFIX/'logs/context-feedback-program/reviews/prefix-runtime.md'
SNAPSHOT = Path('/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json')
SNAPSHOT_SHA = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'
UUID = '7214d805-8331-49aa-af61-478be074d7a6'
HORIZONS = (4096, 12288)
NATIVE_SHA = {4096: '74030e03a55908ffb2eca3f45ded92656aceca1f3859bae1a3418b95597d556c',
              12288: 'b6d6d7ad9f9fc9299d0b776b863c53208209c378c02e03ffecbebf8fafad7330'}
OUTER_SHA = {4096: '3587736f26c0780fbe404a1d06ad3f274cc6c2b362fefe899c48d6484f23464e',
             12288: '8edb4e91dc5209e650cf3ddd3c1d4f52cb58ff50f0791f1dce2dd2cf3dd8bb84'}
CAPS = dict(wall_seconds=300, cpu=2, memory=16*1024**3, address_space=24*1024**3,
            swap=0, maximum_output_bytes=512*1024**2, disk_floor_bytes=30*1024**3)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def pin(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def read(path):
    return json.loads(Path(path).read_text())


def fresh(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(Path(path).parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def check(value):
    require(pin(value['path']) == value, 'Changed pinned file: '+value['path'])


def native(path, horizon):
    lines = Path(path).read_text().splitlines()
    require(lines[0] == 'prefix-native/1', 'Native TSV schema differs')
    values = {}
    for line in lines[1:]:
        cells = line.split('\t')
        require(len(cells) == 2 and cells[0] not in values, 'Native TSV duplicate/width')
        values[cells[0]] = cells[1]
    require(set(values) == {'uuid', 'raw_horizon', 'initial_state', 'SEQ', 'Q', 'MOVES'},
            'Native TSV field census differs')
    require(values['uuid'] == UUID and values['raw_horizon'] == str(horizon)
            and values['initial_state'] == 'uniform_native_cpu', 'Native identity differs')
    seq, quality, moves = (values[k] for k in ('SEQ', 'Q', 'MOVES'))
    require(seq and set(seq) <= set('ACGT') and len(seq) == len(quality)
            and all(33 <= ord(q) <= 126 for q in quality), 'Invalid exact native SEQ/Q')
    require(set(moves) <= set('01') and len(moves) == ((horizon-10+5)//6)
            and moves.count('1') == len(seq), 'Native MOVES shape differs')
    return dict(qname=UUID+'__H'+str(horizon), parent=UUID, horizon=horizon,
                initial_state=values['initial_state'], sequence=seq, quality=quality, moves=moves)


def prefix_inputs():
    require(pin(AUDIT)['sha256'] == AUDIT_SHA, 'Independent producer auditor changed')
    rows = []
    for horizon in HORIZONS:
        base = PREFIX/'results/context-feedback'/('prefix-forward-'+str(horizon)+'-1')
        require(pin(base/'complete.json')['sha256'] == OUTER_SHA[horizon]
                and pin(base/'native/complete.json')['sha256'] == NATIVE_SHA[horizon],
                'Qualified forward completion changed')
        complete = read(base/'native/complete.json')
        row = native(base/'native'/('horizon-'+str(horizon)+'.native.tsv'), horizon)
        for item in [complete['attempt'], complete['result'], *complete['files']]:
            check(item)
        attempt = read(complete['attempt']['path'])
        require(attempt['source'] == complete['source'], 'Native attempt/source mismatch')
        row.update(native=pin(base/'native'/('horizon-'+str(horizon)+'.native.tsv')),
                   tensor=pin(base/'native'/('horizon-'+str(horizon)+'-baseline.scores.f32')),
                   metadata=pin(base/'native'/('horizon-'+str(horizon)+'.metadata.json')),
                   native_complete=pin(base/'native/complete.json'), outer_complete=pin(base/'complete.json'),
                   producer_attempt=complete['attempt'], producer_source=complete['source'])
        rows.append(row)
    require(len({r['qname'] for r in rows}) == 2, 'Prefix names must be unique')
    return rows


def emit_sam(path, rows):
    with Path(path).open('x') as stream:
        stream.write('@HD\tVN:1.6\tSO:unknown\n')
        for row in rows:
            stream.write('\t'.join((row['qname'], '4', '*', '0', '0', '*', '*', '0', '0',
                                    row['sequence'], row['quality']))+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(Path(path).parent)


def cigar_anchors(cigar, position, reverse, sequence_length):
    tokens = re.findall(r'([0-9]+)([MIDNSHP=X])', cigar)
    require(tokens and ''.join(n+op for n, op in tokens) == cigar, 'Malformed CIGAR')
    query, ref = 0, position-1
    anchors = []
    for n, op in tokens:
        count = int(n)
        require(count > 0, 'Zero-length CIGAR')
        if op in 'M=X':
            anchor = dict(query_begin=sequence_length-query-count if reverse else query,
                          query_end=sequence_length-query if reverse else query+count,
                          reference_begin=ref, reference_end=ref+count,
                          operation='aligned', reverse=reverse)
            if anchors and anchors[-1]['reference_end'] == ref and (
                    anchors[-1]['query_begin'] == anchor['query_end'] if reverse else
                    anchors[-1]['query_end'] == anchor['query_begin']):
                anchors[-1]['query_begin'] = min(anchors[-1]['query_begin'], anchor['query_begin'])
                anchors[-1]['query_end'] = max(anchors[-1]['query_end'], anchor['query_end'])
                anchors[-1]['reference_end'] = ref+count
            else:
                anchors.append(anchor)
            query += count
            ref += count
        elif op in 'IS':
            query += count
        elif op in 'DN':
            ref += count
        elif op == 'H':
            raise ValueError('Hard-clipped prefix cannot preserve exact SEQ/Q')
    require(query == sequence_length, 'CIGAR query span differs')
    return sorted(anchors, key=lambda item: item['query_begin'])


def sam_locations(path, rows):
    expected = {r['qname']: r for r in rows}
    records = {name: [] for name in expected}
    complement = str.maketrans('ACGT', 'TGCA')
    for line in Path(path).read_text().splitlines():
        if line.startswith('@'):
            continue
        fields = line.split('\t')
        require(len(fields) >= 11 and fields[0] in expected, 'Foreign/short prefix alignment')
        name, flag, chrom, position, mapq, cigar = fields[:6]
        flag, position, mapq = int(flag), int(position), int(mapq)
        require(0 <= flag <= 65535 and 0 <= mapq <= 255, 'SAM flag/MAPQ range')
        row = expected[name]
        reverse = bool(flag & 16)
        seq = row['sequence'].translate(complement)[::-1] if reverse else row['sequence']
        quality = row['quality'][::-1] if reverse else row['quality']
        primary = not flag & 0x900
        # Secondary SAM records may legally omit SEQ/Q. Primary must retain exact bytes.
        require((fields[9:11] == [seq, quality]) or
                (not primary and fields[9:11] == ['*', '*']), 'Mapped exact SEQ/Q custody differs')
        mapped = not flag & 4
        anchors = cigar_anchors(cigar, position, reverse, len(seq)) if mapped else []
        records[name].append(dict(flag=flag, primary=primary, secondary=bool(flag & 256),
                                  supplementary=bool(flag & 2048), mapped=mapped, contig=chrom,
                                  position_1=position, mapq=mapq, cigar=cigar, reverse=reverse,
                                  anchors=anchors, optional=fields[11:], seq_q_omitted=fields[9] == '*'))
    result = []
    for name, alignments in records.items():
        primary = [a for a in alignments if a['primary']]
        require(len(primary) == 1, 'Prefix must have exactly one mapped/unmapped primary')
        best = primary[0]
        competitors = [a for a in alignments if a['mapped'] and a is not best]
        if not best['mapped']:
            status = 'unknown'
        elif competitors:
            status = 'multimap'
        elif not 30 <= best['mapq'] <= 254:
            status = 'unknown'
        elif not any(a['query_end']-a['query_begin'] >= 54 for a in best['anchors']):
            status = 'insufficient_continuous_anchor'
        else:
            status = 'located'
        result.append(dict(qname=name, parent=expected[name]['parent'], horizon=expected[name]['horizon'],
                           status=status, alignments=alignments,
                           reason='all mapped competitors force abstention; primary MAPQ30..254 and continuous54bp required',
                           usable_primary=best if status == 'located' else None))
    return result


def sources():
    base = ROOT/'tools/prefix_feedback'
    census = read(base/'location-source-files.json')
    paths = [(base/p).resolve(strict=True) for p in census]
    require(len(paths) == len(set(paths)), 'Duplicate owned source')
    return [pin(p) for p in sorted(paths)]


def runtime(execution, tools):
    result = []
    for name in ('dorado', 'samtools'):
        check(tools[name])
        stage = execution.stage('prefix-location-ldd-'+name, ['/usr/bin/ldd', tools[name]['path']])
        text = Path(stage['raw']['stdout']['path']).read_text()
        require('not found' not in text, 'Unresolved runtime library')
        paths = {m.group(1) for m in re.finditer(r'(?:=>\s+)?(/\S+)\s+\(', text)}
        require(paths, 'Empty runtime library census')
        result.append(dict(name=name, binary=tools[name], stage=execution.receipts[-1],
                           libraries=[pin(p) for p in sorted(paths)]))
    return result


def locate(args):
    require(re.fullmatch('[A-Za-z0-9_-]{1,80}', args.admission_id), 'Unsafe unit identity')
    w = load('causal_location_execution', ROOT/'scripts/context-feedback.py')
    require(w.ROOT == ROOT and w.c.ROOT == ROOT, 'Execution source root differs')
    output = args.output.resolve()
    require(output.is_relative_to(ROOT/'results/context-feedback'), 'Output outside owned results')
    output.mkdir()
    now = datetime.now(timezone.utc)
    grant = dict(id=args.admission_id, maximum_wall_seconds=280,
                 expires_utc=(now+timedelta(seconds=280)).isoformat(), cpu_quota=2,
                 memory_bytes=CAPS['memory'], address_space_bytes=CAPS['address_space'], swap_bytes=0,
                 maximum_output_bytes=CAPS['maximum_output_bytes'],
                 cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-'+args.admission_id+'.service')
    source = sources()+[pin(w.__file__), pin(AUDIT), pin(REVIEW), pin(ROOT/'scripts/record-command.sh')]
    fresh(output/'attempt.json', dict(schema='prefix-location-attempt/1', argv=sys.argv, sources=source,
                                     grant=grant, caps=CAPS, truth_imported=False))
    # This verifies actual kernel CPU/memory/swap limits and installs AS/FSIZE before work.
    w.cgroup_limits(grant)
    cgroup = Path('/sys/fs/cgroup')/grant['cgroup'].lstrip('/')
    service = w.supervisor.show('context-'+args.admission_id+'.service')
    policy = service['properties']
    require(service['exit'] == 0 and policy['ControlGroup'] == grant['cgroup']
            and policy['Type'] == 'exec' and policy['ExitType'] == 'cgroup'
            and policy['KillMode'] == 'control-group' and policy['SendSIGKILL'] == 'yes'
            and policy['FinalKillSignal'] == '9' and policy['CollectMode'] == 'inactive'
            and 0 < w.supervisor.duration(policy['RuntimeMaxUSec']) <= 300
            and w.supervisor.duration(policy['TimeoutStopUSec']) <= 1,
            'Whole-unit live supervisor policy differs')
    fresh(output/'kernel-limits.json', dict(cgroup=grant['cgroup'], values={name: (cgroup/name).read_text()
          for name in ('cpu.max', 'memory.max', 'memory.swap.max')}, service=service,
          rlimit_as=resource.getrlimit(resource.RLIMIT_AS),
          rlimit_fsize=resource.getrlimit(resource.RLIMIT_FSIZE)))
    execution = w.Execution(grant, output, source)
    engineering = execution.stage('prefix-location-controls', ['uv', 'run', '--no-sync', 'python',
        '-m', 'unittest', 'discover', '-s', 'tools/prefix_feedback', '-p', 'test_location.py', '-v'])
    controls = Path(engineering['raw']['stderr']['path']).read_text()
    require(re.search(r'(?m)^Ran 12 tests in [0-9.]+s$', controls) is not None
            and controls.rstrip().endswith('\nOK') and 'skipped' not in controls.lower(),
            'Location engineering requires12 actual tests and zero skips')
    audit = execution.stage('prefix-producer-audit', ['uv', 'run', '--no-sync', 'python', str(AUDIT)])
    require('PASS_BOUNDED_PREFIX_CPU_RUNTIME' in Path(audit['raw']['stdout']['path']).read_text(),
            'Genuine producer runtime audit did not pass')
    rows = prefix_inputs()
    require(pin(SNAPSHOT)['sha256'] == SNAPSHOT_SHA, 'Frozen reference snapshot changed')
    snapshot = read(SNAPSHOT)
    # No historical alignment, case coordinates, truth, eligible BED or genotype is read here.
    tools = {k: snapshot['tools'][k] for k in ('dorado', 'samtools', 'index')}
    check(tools['index'])
    closure = runtime(execution, tools)
    emit_sam(output/'prefixes.sam', rows)
    fresh(output/'prefixes.json', dict(schema='qualified-prefix-consumer/1', prefixes=rows,
                                     physical_molecules=1, correlated_horizons=2,
                                     producer_audit=execution.receipts[1], reference_snapshot=pin(SNAPSHOT)))
    bam = execution.stage('prefix-location-sam-to-bam', [tools['samtools']['path'], 'view', '-b', output/'prefixes.sam'])
    aligned = execution.stage('prefix-location-align', [tools['dorado']['path'], 'aligner', tools['index']['path'],
        bam['raw']['stdout']['path'], '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
    mapped = execution.stage('prefix-location-sam', [tools['samtools']['path'], 'view', '-h', aligned['raw']['stdout']['path']])
    locations = sam_locations(mapped['raw']['stdout']['path'], rows)
    fresh(output/'locations.json', dict(schema='prefix-location/1', locations=locations,
         mapped=pin(mapped['raw']['stdout']['path']), reference_snapshot=pin(SNAPSHOT), tools=tools,
         runtime=closure, truth_imported=False, location_source='each actual native prefix SEQ only',
         tensor_origin='PFS1 CPU FP32 reset encoder; native start uniform; bounded prefix redecode',
         stock_cuda_parity=False, gpu_activity_traced=False, streaming_state_continuity=False))
    execution.budget()
    fresh(output/'complete.json', dict(schema='prefix-location-complete/1', complete=True, sources=source,
          attempt=pin(output/'attempt.json'), stages=execution.receipts,
          files=[pin(output/name) for name in ('kernel-limits.json', 'prefixes.sam', 'prefixes.json', 'locations.json')],
          biological_qualification=False, candidate_promoted=False))
    print(json.dumps(dict(completion=pin(output/'complete.json'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--admission-id', required=True)
    locate(parser.parse_args())


if __name__ == '__main__':
    main()
