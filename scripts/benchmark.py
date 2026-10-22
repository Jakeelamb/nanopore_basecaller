"""Fixed stock Dorado benchmark; native programs compute, receipts preserve evidence."""
import argparse
import collections
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import shlex
import zipfile
import statistics
import subprocess
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('development', 'validation', 'sealed_test')
SOURCE = '8b8fc5d36a9c0baab262a743cb175b5878e38ca6'
STOCK_VERSION = '2.1.2+' + SOURCE[:7]
BIOLOGY = {key: 'NOT VERIFIED' for key in ('biological_base_accuracy', 'biological_quality_calibration',
                                          'variant_aware_accuracy', 'variant_calling_accuracy')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def pin(path):
    path = Path(path).resolve()
    return {'path': str(path), 'size': path.stat().st_size, 'sha256': digest(path)}


def check_pins(pins):
    for expected in pins:
        actual = pin(ROOT / expected['path'])
        require(all(actual[key] == expected[key] for key in ('size', 'sha256')), f"Changed evidence: {expected['path']}")


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def ids(path):
    values = Path(path).read_text().splitlines()
    require(values and len(set(values)) == len(values), f'Empty/duplicate membership: {path}')
    for value in values:
        require(str(UUID(value)) == value, f'Noncanonical UUID: {value}')
    return values


def signal_census(assets, inventory_path, summary_path):
    import pod5
    with Path(inventory_path).open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    inventory = {row['read_id']: row for row in rows}
    summaries = read(summary_path)
    require(len(inventory) == len(rows) and len(summaries) == len(assets), 'Invalid inventory census')
    observed, result = set(), {}
    for asset in assets:
        counts, acquisitions, sample_ids, starts, channels = {}, set(), set(), [], set()
        role = asset['role']
        with pod5.Reader(ROOT / asset['path']) as reader:
            for record in reader.reads():
                uid, run, signal_data = str(record.read_id), record.run_info, record.signal
                require(uid not in observed and uid in inventory, 'POD5 UUID/inventory mismatch')
                observed.add(uid)
                row = inventory[uid]
                require(run.sample_rate == 5000 and run.flow_cell_id == asset['flowcell'] and run.sequencing_kit == 'sqk-lsk114', 'POD5 chemistry/flowcell mismatch')
                require(len(signal_data) == record.num_samples > 0 and math.isfinite(record.calibration.offset) and math.isfinite(record.calibration.scale) and record.calibration.scale > 0, 'Invalid decoded POD5 signal/calibration')
                expected = dict(role=role, sample=asset['sample'], flowcell=asset['flowcell'], read_id=uid, acquisition_id=run.acquisition_id,
                                channel=record.pore.channel, well=record.pore.well, read_number=record.read_number, start_sample=record.start_sample,
                                num_samples=record.num_samples, sample_rate=run.sample_rate, calibration_offset=record.calibration.offset,
                                calibration_scale=record.calibration.scale, signal_adc_min=int(signal_data.min()), signal_adc_max=int(signal_data.max()))
                require(set(row) == set(expected) and all(str(value) == row[key] for key, value in expected.items()), 'POD5 metadata/inventory mismatch: ' + uid)
                counts[uid] = record.num_samples
                acquisitions.add(run.acquisition_id)
                sample_ids.add(run.sample_id)
                starts.append(record.start_sample / run.sample_rate)
                channels.add(record.pore.channel)
        require(counts, 'Empty POD5 cohort')
        membership = ids(ROOT / f'data/splits/{role}.txt')
        require(set(membership) == set(counts), 'Full membership/inventory mismatch')
        durations = sorted(counts.values())
        expected_summary = {**{key: asset[key] for key in ('id', 'role', 'sample', 'flowcell')}, 'reads': len(counts),
                            'signal_samples': sum(durations), 'sample_rate': 5000, 'signal_seconds': sum(durations) / 5000,
                            'read_seconds_min': durations[0] / 5000, 'read_seconds_median': durations[len(durations) // 2] / 5000,
                            'read_seconds_max': durations[-1] / 5000, 'start_seconds_min': min(starts), 'start_seconds_max': max(starts),
                            'channels': len(channels), 'acquisition_ids': sorted(acquisitions), 'pod5_sample_ids': sorted(sample_ids),
                            'membership_sha256': hashlib.sha256((''.join(uid + '\n' for uid in sorted(counts))).encode()).hexdigest()}
        require(sum(item == expected_summary for item in summaries) == 1, 'Signal receipt does not match acquired POD5')
        result[role] = counts
    require(observed == set(inventory), 'Inventory includes unacquired molecules')
    return result


def stock_model(model_root, archive):
    model_root = Path(model_root)
    expected = {}
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            if entry.is_dir():
                continue
            relative = Path(entry.filename)
            require(relative.parts[0] == model_root.name and '..' not in relative.parts and len(relative.parts) > 1, 'Unexpected stock ZIP path')
            key = str(Path(*relative.parts[1:]))
            require(key not in expected, 'Duplicate stock ZIP member')
            with zipped.open(entry) as handle:
                expected[key] = (entry.file_size, hashlib.file_digest(handle, 'sha256').hexdigest())
    require(not any(p.is_symlink() for p in model_root.rglob('*')), 'Stock model tree contains symlinks')
    files = sorted(p for p in model_root.rglob('*') if p.is_file())
    require('config.toml' in expected and {str(p.relative_to(model_root)) for p in files} == set(expected), 'Stock ZIP/model file census mismatch')
    for path in files:
        require((path.stat().st_size, digest(path)) == expected[str(path.relative_to(model_root))], 'Extracted model differs from stock ZIP: ' + str(path))
    return files


def parity_evidence(index, config):
    entries = index.get('parity')
    require(isinstance(entries, list) and len(entries) == 2 and {entry.get('tier') for entry in entries if isinstance(entry, dict)} == {'hac', 'sup'}, 'Native parity requires both stock tiers')
    evidence = []
    for entry in entries:
        model = Path(config['models'][entry['tier']]).name
        require(entry['status'] == 'verified' and entry['model'] == model and entry['mapped_records'] > 0 and len(entry['outputs']) == 4, 'Unqualified tier parity')
        nested = [entry['input'], entry['input_decode'], *entry['outputs'], *entry['pins']]
        declared = {(str((ROOT / item['path']).resolve()), item['size'], item['sha256']) for item in entry['pins']}
        require(all((str((ROOT / item['path']).resolve()), item['size'], item['sha256']) in declared for item in nested), 'Unpinned nested parity artifact')
        for run_name in entry['producer_runs']:
            run = ROOT / run_name
            required = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'time.txt', 'exit-status.txt', 'stdout', 'stderr')
            require(all((run / name).is_file() for name in required) and (run / 'exit-status.txt').read_text().strip() == '0', 'Incomplete parity producer')
            log_pins = [pin(run / name) for name in required]
            require(all((item['path'], item['size'], item['sha256']) in declared for item in log_pins), 'Unpinned parity producer logs')
            nested.extend(log_pins)
        producer = ROOT / entry['input_producer_run']
        command = shlex.split((producer / 'command.sh').read_text())
        require(entry['input_producer_run'] in entry['producer_runs'] and (ROOT / entry['input']['path']).resolve() == (producer / 'stdout').resolve(), 'Parity input producer mismatch')
        require(len(command) >= 4 and command[1] == 'basecaller' and Path(command[2]).name == model and (ROOT / command[0]).resolve() == (ROOT / config['dorado']).resolve(), 'Parity producer is not configured stock basecaller')
        check_pins(nested)
        canonical = []
        for artifact in (entry['input_decode'], entry['outputs'][1], entry['outputs'][3]):
            lines = (ROOT / artifact['path']).read_text().splitlines()
            groups = [header_record(line) for line in lines if line.startswith('@RG\t')]
            require(groups and all('basecall_model=' + model in group.get('DS', '').split() for group in groups), 'Parity BAM model mismatch')
            require(any(line.startswith('@PG\t') and header_record(line).get('PN') == 'dorado' and header_record(line).get('VN') == STOCK_VERSION for line in lines), 'Parity lacks native Dorado version')
            records = [tuple(line.split('\t')[:11] + sorted(line.split('\t')[11:])) for line in lines if not line.startswith('@')]
            require(records, 'Empty parity native work')
            if artifact != entry['input_decode']:
                dictionary = {header_record(line)['SN']: int(header_record(line)['LN']) for line in lines if line.startswith('@SQ\t')}
                require(dictionary == index['dictionary'] and sum(not int(record[1]) & 4 for record in records) == entry['mapped_records'], 'Parity reference/work mismatch')
                canonical.append(sorted(records))
        require(canonical[0] == canonical[1], 'Native parity alignments differ')
        evidence.extend(nested)
    return evidence


def header_record(line):
    return dict(field.split(':', 1) for field in line.rstrip().split('\t')[1:])


def parse_sam(path, model, expected, reference=None, base=None):
    groups, dictionary, programs = {}, {}, []
    primary, roots, intervals, metrics = {}, collections.defaultdict(list), collections.defaultdict(list), collections.Counter()
    fractions = []
    with Path(path).open() as handle:
        for line in handle:
            if line.startswith('@'):
                fields = header_record(line)
                if line.startswith('@RG\t'):
                    require(fields['ID'] not in groups, 'Duplicate read group')
                    require(f'basecall_model={model}' in fields.get('DS', '').split(), 'Wrong model identity')
                    groups[fields['ID']] = fields
                elif line.startswith('@SQ\t'):
                    require(fields['SN'] not in dictionary, 'Duplicate reference contig')
                    dictionary[fields['SN']] = int(fields['LN'])
                elif line.startswith('@PG\t'):
                    programs.append(fields)
                continue
            fields = line.rstrip('\n').split('\t')
            require(len(fields) >= 11, 'Malformed SAM record')
            name, flag, contig, pos, mapq, cigar = fields[:6]
            UUID(name)
            flag, pos, mapq = int(flag), int(pos), int(mapq)
            tags, tag_types = {}, {}
            for field in fields[11:]:
                key, kind, value = field.split(':', 2)
                require(key not in tags, 'Duplicate auxiliary tag')
                tags[key] = value
                tag_types[key] = kind
            root = tags.get('pi', name)
            require(root in expected, f'Foreign parent: {root}')
            require(tags.get('RG') in groups, 'Unknown read group')
            seq, qual = fields[9:11]
            supplemental = bool(flag & 0x900)
            metrics['records'] += 1
            metrics['secondary'] += bool(flag & 0x100)
            metrics['supplementary'] += bool(flag & 0x800)
            if base is not None:
                require(name in base and root == base[name]['parent'], 'Unknown/mismatched aligned child')
            if seq != '*':
                require(qual != '*' and len(seq) == len(qual) and all(33 <= ord(q) <= 126 for q in qual), 'Sequence/quality mismatch')
            else:
                require(supplemental, 'Missing primary sequence')
            if not supplemental:
                require(name not in primary, 'Duplicate primary child')
                require(seq != '*' and seq, 'Empty primary sequence')
                normalized = seq.translate(str.maketrans('ACGTNacgtn', 'TGCANtgcan'))[::-1] if flag & 16 else seq
                normalized_q = qual[::-1] if flag & 16 else qual
                if base is not None:
                    require((normalized, normalized_q) == (base[name]['seq'], base[name]['qual']), 'Strand-normalized sequence/quality changed')
                    require(all(tags.get(key) == base[name]['tags'].get(key) for key in ('pi', 'sp', 'ns', 'ts', 'RG')), 'Aligned native signal tags changed')
                primary[name] = {'parent': root, 'seq': normalized, 'qual': normalized_q, 'tags': tags, 'tag_types': tag_types,
                                 'alignment': fields[:9], 'cigar': cigar}
                roots[root].append(name)
                metrics['called_bases'] += len(seq)
            if base is None:
                require(flag == 4 and cigar == '*' and contig == '*', 'Basecall is not primary unaligned')
                ns, ts = int(tags.get('ns', '-1')), int(tags.get('ts', '-1'))
                require(0 <= ts <= ns <= expected[root] and ns > 0, 'Invalid signal sample bounds')
                require('qs' in tags and math.isfinite(float(tags['qs'])), 'Missing/nonfinite native quality')
                if 'pi' in tags:
                    require(name != root and 'sp' in tags, 'Invalid split identity')
                    start = int(tags['sp'])
                    require(0 <= start < start + ns <= expected[root], 'Invalid split interval')
                    intervals[root].append((start, start + ns))
                else:
                    require('sp' not in tags and name == root, 'Invalid unsplit identity')
            elif not flag & 4:
                require(contig in dictionary and pos >= 1, 'Invalid reference coordinate')
                operations = re.findall(r'([1-9][0-9]*)([MIDNSHP=X])', cigar)
                require(''.join(n + op for n, op in operations) == cigar and operations, 'Invalid CIGAR')
                counts = collections.Counter()
                for number, op in operations:
                    counts[op] += int(number)
                require(not counts['M'], 'EQX CIGAR required')
                if seq != '*':
                    require(sum(counts[op] for op in 'MIS=X') == len(seq), 'CIGAR/query length mismatch')
                require(pos - 1 + sum(counts[op] for op in 'MDN=X') <= dictionary[contig], 'CIGAR/reference bounds')
                require('NM' in tags and int(tags['NM']) == counts['X'] + counts['I'] + counts['D'], 'Inconsistent NM')
                require('MD' in tags, 'Missing native MD')
                if not supplemental:
                    metrics['mapped_children'] += 1
                    for op, count in counts.items():
                        metrics[f'cigar_{op}'] += count
                    denominator = sum(counts[op] for op in '=XID')
                    require(denominator > 0, 'Empty alignment denominator')
                    metrics['disagreement_columns'] += int(tags['NM'])
                    metrics['alignment_columns'] += denominator
                    fractions.append(int(tags['NM']) / denominator)
                    metrics['primary_aligned_query_bases'] += sum(counts[op] for op in '=XI')
                metrics['mapped_records'] += 1
            elif not supplemental:
                metrics['unmapped_children'] += 1
                metrics['unmapped_called_bases'] += len(seq)
    require(groups and any(p.get('PN') == 'dorado' and p.get('VN') == STOCK_VERSION for p in programs), 'Wrong/missing Dorado version')
    require(primary, 'No emitted children')
    if base is not None:
        require(dictionary == reference, 'Wrong complete reference dictionary')
        require(set(primary) == set(base), 'Missing aligned primary child')
    for root, spans in intervals.items():
        require(len(spans) == len(roots[root]), 'Mixed split and unsplit parent')
        spans.sort()
        require(all(left[1] <= right[0] for left, right in zip(spans, spans[1:])), 'Overlapping split intervals')
    metrics.update(requested_parents=len(expected), represented_parents=len(roots), children=len(primary), split_parents=len(intervals))
    missing = sorted(set(expected) - set(roots))
    return {'children': primary, 'missing_parents': missing, 'metrics': dict(metrics),
            'complete_processing': not missing, 'missing_reason': 'unresolved' if missing else None,
            'lengths': {'min': min(len(v['seq']) for v in primary.values()), 'median': statistics.median(len(v['seq']) for v in primary.values()), 'max': max(len(v['seq']) for v in primary.values())},
            'reference_disagreement_proxy': {'aggregate': metrics['disagreement_columns'] / metrics['alignment_columns'] if fractions else None,
                                            'mean_child': statistics.mean(fractions) if fractions else None},
            'scientific_endpoints': BIOLOGY}


def verify_calmd(before, after, fetch_reference):
    require(set(before) == set(after), 'Native calmd changed primary membership')
    exceptions = []
    for child in sorted(before):
        old, new = before[child], after[child]
        require({k: v for k, v in old.items() if k != 'tags'} == {k: v for k, v in new.items() if k != 'tags'}, 'Native calmd changed primary fields or tag types')
        require({k: v for k, v in old['tags'].items() if k != 'MD'} == {k: v for k, v in new['tags'].items() if k != 'MD'}, 'Native calmd changed primary tags or NM')
        if old['tags'].get('MD') == new['tags'].get('MD'):
            continue
        old_md, new_md = old['tags'].get('MD', ''), new['tags'].get('MD', '')
        pattern = r'[0-9]+(?:(?:[A-Z]|\^[A-Z]+)[0-9]+)*'
        require(re.fullmatch(pattern, old_md) and re.fullmatch(pattern, new_md), 'Native calmd changed MD structure')
        old_tokens, new_tokens = [re.findall(r'[0-9]+|\^[A-Z]+|[A-Z]', md) for md in (old_md, new_md)]
        require(len(old_tokens) == len(new_tokens), 'Native calmd changed MD structure')
        segments, md_length, ref_pos, query_pos = [], 0, int(old['alignment'][3]), 1
        for number, op in re.findall(r'([1-9][0-9]*)([MIDNSHP=X])', old['cigar']):
            length = int(number)
            if op in '=XD':
                segments.append((md_length, md_length + length, ref_pos, query_pos, op))
                md_length += length
            if op in '=XDN':
                ref_pos += length
            if op in '=XIS':
                query_pos += length
        offset, segment_index = 0, 0

        def advance(length, required_op):
            nonlocal offset, segment_index
            while length:
                while segment_index < len(segments) and offset == segments[segment_index][1]:
                    segment_index += 1
                require(segment_index < len(segments), 'MD exceeds CIGAR')
                start, end, ref_start, query_start, op = segments[segment_index]
                require(op == required_op, 'MD disagrees with EQX CIGAR')
                amount = min(length, end - offset)
                offset += amount
                length -= amount

        for old_token, new_token in zip(old_tokens, new_tokens):
            if old_token.isdigit():
                require(old_token == new_token, 'Native calmd changed MD match runs')
                advance(int(old_token), '=')
                continue
            deletion = old_token.startswith('^')
            require(deletion == new_token.startswith('^') and len(old_token) == len(new_token) and not new_token.isdigit(), 'Native calmd changed MD deletion structure')
            for native_base, corrected_base in zip(old_token[1:] if deletion else old_token, new_token[1:] if deletion else new_token):
                if native_base != corrected_base:
                    require(native_base == 'N' and corrected_base in 'RYSWKMBDHV', 'Native calmd changed canonical MD base')
                    while segment_index < len(segments) and offset == segments[segment_index][1]:
                        segment_index += 1
                    require(segment_index < len(segments), 'MD exceeds CIGAR')
                    start, end, ref_start, query_start, op = segments[segment_index]
                    exceptions.append({'child': child, 'contig': old['alignment'][2],
                                       'reference_position_1based': ref_start + offset - start,
                                       'query_position_1based': None if deletion else query_start + offset - start,
                                       'cigar_operation': op, 'native_md_base': native_base, 'calmd_md_base': corrected_base})
                advance(1, 'D' if deletion else 'X')
        require(offset == md_length, 'MD does not cover CIGAR')
    if exceptions:
        regions = sorted({f"{item['contig']}:{item['reference_position_1based']}-{item['reference_position_1based']}" for item in exceptions})
        fasta, current, order = {}, None, []
        with Path(fetch_reference(regions)).open() as handle:
            for line in handle:
                line = line.rstrip('\n')
                if line.startswith('>'):
                    current = line[1:]
                    require(current not in fasta, 'Duplicate faidx reference coordinate')
                    fasta[current] = ''
                    order.append(current)
                else:
                    require(current is not None, 'Malformed faidx reference output')
                    fasta[current] += line
        require(order == regions, 'Wrong faidx reference coordinates')
        for item in exceptions:
            region = f"{item['contig']}:{item['reference_position_1based']}-{item['reference_position_1based']}"
            require(fasta[region] == item['calmd_md_base'], 'MD ambiguity differs from pinned reference')
            item['reference_base'] = fasta[region]
    return {'status': 'verified', 'primary_records_checked': len(before), 'exact_md_agreement': not exceptions,
            'all_other_primary_fields_equal': True, 'md_reference_ambiguity_records': len({item['child'] for item in exceptions}),
            'md_reference_ambiguity_bases': len(exceptions), 'md_reference_ambiguity_exceptions': exceptions,
            'reference_check_stage': 'calmd-reference-iupac' if exceptions else None}


def verify_summary(path, parsed, aligned=False):
    with Path(path).open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    require(len(rows) == len(parsed['children']), 'Native summary row count mismatch')
    seen = set()
    for row in rows:
        child = row['read_id']
        require(child not in seen and child in parsed['children'], 'Native summary child mismatch')
        seen.add(child)
        expected = parsed['children'][child]
        require(row['parent_read_id'] == expected['parent'], 'Native summary parent mismatch')
        require(int(row['sequence_length_template']) == len(expected['seq']), 'Native summary sequence length mismatch')
        if aligned and not int(expected['alignment'][1]) & 4:
            counts = collections.Counter()
            for n, op in re.findall(r'(\d+)([MIDNSHP=X])', expected['cigar']):
                counts[op] += int(n)
            for key, value in [('alignment_num_aligned', counts['='] + counts['X']),
                               ('alignment_num_correct', counts['=']), ('alignment_num_insertions', counts['I']),
                               ('alignment_num_deletions', counts['D'])]:
                require(int(row[key]) == value, f'Native summary count mismatch: {key}')


def stage(root, name, argv, context, retry=False, execute=True, reserve=0):
    directory = Path(root) / name
    directory.mkdir(parents=True, exist_ok=True)
    attempts = sorted(directory.glob('*/start.json'))
    key = identity({'argv': argv, 'context': context})
    if attempts:
        last = attempts[-1].parent
        require(read(last / 'start.json')['key'] == key, f'Changed stage identity: {name}')
        if (last / 'finish.json').exists():
            receipt = read(last / 'finish.json')
            if receipt['status'] == 'finished':
                check_pins(receipt['pins'])
                return receipt
        require(retry, f'Failed/interrupted stage {name}; explicit --retry UNIT:STAGE required')
    require(execute, f'Missing retained stage: {name}')
    attempt = directory / (str(time.time_ns()) + '-' + uuid4().hex[:8])
    attempt.mkdir()
    label = 'stock-' + uuid4().hex
    start = {'key': key, 'argv': argv, 'context': context, 'utc': utc(),
             'monotonic_ns': time.monotonic_ns(), 'recorder_label': label, 'explicit_env': {'LC_ALL': 'C'}, 'status': 'running'}
    write(attempt / 'start.json', start)
    sampler = None
    with (attempt / 'gpu.csv').open('w') as gpu, (attempt / 'gpu.stderr').open('w') as gpuerr:
        if shutil.which('nvidia-smi'):
            sampler = subprocess.Popen(['nvidia-smi', '--query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw,temperature.gpu,clocks.sm', '--format=csv', '-l', '1'], stdout=gpu, stderr=gpuerr)
        with (attempt / 'launcher.stdout').open('w') as out, (attempt / 'launcher.stderr').open('w') as err:
            process = subprocess.Popen([str(ROOT / 'scripts/record-command.sh'), label, *map(str, argv)], cwd=ROOT, stdout=out, stderr=err, start_new_session=True, env={**os.environ, 'LC_ALL': 'C'})
            failure = None
            try:
                while process.poll() is None:
                    if reserve and shutil.disk_usage(ROOT).free < reserve:
                        raise RuntimeError('Disk reserve breached')
                    time.sleep(0.25)
            except BaseException as exc:
                failure = str(exc) or type(exc).__name__
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            finally:
                if sampler is not None:
                    sampler.terminate()
                    sampler.wait()
    logs = list((ROOT / 'logs').glob('*-' + label + '-*'))
    recorder = logs[0] if len(logs) == 1 else None
    complete = recorder is not None and all((recorder / item).is_file() for item in ('exit-status.txt', 'start.txt', 'end.txt', 'time.txt', 'stdout', 'stderr', 'command.sh', 'cwd.txt'))
    status = 'finished' if complete and process.returncode == 0 and failure is None else 'command_failed' if complete else 'interrupted'
    receipt = {**start, 'status': status, 'end_utc': utc(), 'elapsed_ns': time.monotonic_ns() - start['monotonic_ns'],
               'exit': process.returncode, 'failure': failure, 'recorder': str(recorder) if recorder else None,
               'stdout': str(recorder / 'stdout') if recorder else None,
               'sampler_exit': sampler.returncode if sampler is not None else None,
               'resource_status': 'sampled; inspect raw query fields' if sampler is not None else 'unavailable: nvidia-smi absent',
               'pins': [pin(p) for p in sorted(attempt.iterdir()) if p.is_file()] + ([pin(p) for p in sorted(recorder.iterdir()) if p.is_file()] if recorder else [])}
    write(attempt / 'finish.json', receipt)
    require(status == 'finished', f'Native stage {name} {status}; evidence: {attempt}')
    return receipt


def prepare(config_path, output):
    config = read(ROOT / config_path)
    require(output.is_relative_to(ROOT / 'results/stock'), 'Stock plans belong under results/stock')
    require(not output.exists(), 'Plan output already exists')
    assets = read(ROOT / 'config/assets.json')
    lock = read(ROOT / 'provenance/assets.lock.json')
    require(len(assets) == len(lock), 'Asset lock census mismatch')
    pins = [pin(ROOT / config_path), pin(ROOT / 'config/assets.json'), pin(ROOT / 'provenance/assets.lock.json'), pin(ROOT / 'scripts/record-command.sh')]
    for asset, frozen in zip(assets, lock):
        require(all(frozen.get(k) == v for k, v in asset.items()), 'Asset lock metadata mismatch')
        value = pin(ROOT / asset['path'])
        require(value['sha256'] == frozen['sha256'] and value['size'] == asset['bytes'], 'Asset lock bytes mismatch')
        pins.append(value)
    source = ROOT / 'software/dorado-src'
    require(subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == SOURCE, 'Wrong stock source')
    require(not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--ignore-submodules=none'], text=True), 'Dirty stock source')
    for receipt_name in ('reference_receipt', 'index_receipt'):
        receipt_path = ROOT / config[receipt_name]
        receipt = read(receipt_path)
        require(receipt['status'] == 'verified' and receipt['pins'] and receipt['dictionary'], f'Unqualified {receipt_name}')
        check_pins(receipt['pins'])
        pins.extend(receipt['pins'] + [pin(receipt_path)])
    reference, index = read(ROOT / config['reference_receipt']), read(ROOT / config['index_receipt'])
    require(index['dictionary'] == reference['dictionary'] and index['reference_sha256'] == digest(ROOT / config['reference']), 'Index/reference identity mismatch')
    pins.extend(parity_evidence(index, config))
    preparation_runs = sorted(set(reference.get('native_runs', []) + index.get('native_runs', []) + [index['build']['producer_run']] + [run for entry in index['parity'] for run in entry['producer_runs']]))
    pins.extend(pin(path) for run in preparation_runs for path in (ROOT / run).iterdir() if path.is_file())
    for key in ('dorado', 'samtools'):
        tool = Path(config[key]) if '/' in config[key] else Path(shutil.which(config[key]) or config[key])
        config[key] = str((ROOT / tool).resolve())
        pins.append(pin(config[key]))
    require(subprocess.check_output([config['dorado'], '--version'], text=True).strip() == STOCK_VERSION, 'Wrong Dorado version')
    library_root = Path(config['dorado']).parent.parent / 'lib'
    pins.extend(pin(p) for p in sorted(library_root.rglob('*')) if p.is_file())
    submodules = subprocess.check_output(['git', '-C', str(source), 'submodule', 'status', '--recursive'], text=True)
    require(not any(line and line[0] in '-+U' for line in submodules.splitlines()), 'Unpinned/incomplete stock submodules')
    versions = {key: subprocess.check_output([config[key], '--version'], stderr=subprocess.STDOUT).decode(errors='replace') for key in ('dorado', 'samtools')}
    model_trees = {}
    for tier, path in config['models'].items():
        archives = [asset for asset in assets if asset['role'] == 'stock_model' and asset['model_name'] == Path(path).name]
        require(len(archives) == 1, 'Missing verified stock model archive')
        files = stock_model(ROOT / path, ROOT / archives[0]['path'])
        pins.extend(pin(p) for p in files)
        model_trees[tier] = {'path': str((ROOT / path).resolve()), 'files': [str(p.relative_to(ROOT / path)) for p in files]}
        config['models'][tier] = str((ROOT / path).resolve())
    inventory_path = ROOT / 'data/splits/read-inventory.tsv'
    pins.extend([pin(inventory_path), pin(ROOT / 'provenance/signal-inventory.json')])
    raw = [a for a in assets if a['role'] in ROLES]
    require(len(raw) == 3 and {a['role'] for a in raw} == set(ROLES), 'Wrong raw census')
    require({p.resolve() for p in (ROOT / 'data/raw').rglob('*.pod5')} == {(ROOT / a['path']).resolve() for a in raw}, 'Unconfigured raw POD5')
    census = signal_census(raw, inventory_path, ROOT / 'provenance/signal-inventory.json')
    units, seen = [], set()
    for asset in raw:
        membership = ROOT / f"data/splits/{asset['role']}.txt"
        selected = ids(membership)
        require(not seen.intersection(selected), 'Cross-role UUID overlap')
        seen.update(selected)
        counts = census[asset['role']]
        require(set(selected) == set(counts), 'Full membership/inventory mismatch')
        pins.append(pin(membership))
        for tier in ('hac', 'sup'):
            units.append({'id': f"full-{asset['role']}-{tier}", 'scope': 'full', 'tier': tier, 'asset': asset, 'ids': str(membership), 'parents': counts})
    development = next(a for a in raw if a['role'] == 'development')
    for scope, filename in [('smoke', 'smoke.txt'), ('timing', 'benchmark.txt')]:
        membership = ROOT / 'data/splits' / filename
        selected = ids(membership)
        ranked = sorted(ids(ROOT / 'data/splits/development.txt'), key=lambda v: hashlib.sha256(('nanopore-pilot-smoke-v1:' + v).encode()).hexdigest())
        require(selected == ranked[:32 if scope == 'smoke' else 256], 'Frozen development subset mismatch')
        pins.append(pin(membership))
        for repetition, order in enumerate([('hac', 'sup')] if scope == 'smoke' else [('hac', 'sup'), ('sup', 'hac'), ('hac', 'sup'), ('sup', 'hac'), ('hac', 'sup')], 1):
            for tier in order:
                units.append({'id': f'{scope}-{repetition}-{tier}', 'scope': scope, 'tier': tier, 'repetition': repetition, 'asset': development, 'ids': str(membership), 'parents': {uid: census['development'][uid] for uid in selected}})
    import pod5
    fixture = ROOT / config['split_fixture']
    with pod5.Reader(fixture) as reader:
        fixture_parents = {str(r.read_id): r.num_samples for r in reader.reads() if len(r.signal) > 0}
    require(len(fixture_parents) == 1, 'Wrong genuine split fixture')
    fixture_ids = output / 'split-fixture.txt'
    fixture_ids.parent.mkdir(parents=True)
    fixture_ids.write_text('\n'.join(fixture_parents) + '\n')
    runner_snapshot = output / 'runner-source.py'
    shutil.copyfile(__file__, runner_snapshot)
    pins.append(pin(runner_snapshot))
    pins.extend([pin(fixture), pin(fixture_ids)])
    units.append({'id': 'split-fixture-hac', 'scope': 'fixture', 'tier': 'hac', 'asset': {'path': str(fixture)}, 'ids': str(fixture_ids), 'parents': fixture_parents})
    gpu_state = subprocess.run(['nvidia-smi', '-q'], capture_output=True, text=True)
    environment = {'gpu_query_exit': gpu_state.returncode, 'gpu_query_stdout': gpu_state.stdout, 'gpu_query_stderr': gpu_state.stderr, 'disk': list(shutil.disk_usage(ROOT)), 'cpu_affinity': sorted(os.sched_getaffinity(0)), 'uname': list(os.uname()), 'cpu': Path('/proc/cpuinfo').read_text(), 'memory': Path('/proc/meminfo').read_text(),
                   'power': {str(p): p.read_text().strip() for p in Path('/sys/class/power_supply').glob('*/online')},
                   'cache': 'uncontrolled; earlier compatibility/smoke work retained separately', 'environment': {k: os.environ.get(k) for k in ('CUDA_VISIBLE_DEVICES', 'OMP_NUM_THREADS', 'LD_LIBRARY_PATH')}}
    plan = {'schema': 1, 'scope': 'stock-all-acquired', 'created_utc': utc(), 'config': config, 'pins': pins, 'units': units,
            'dictionary': reference['dictionary'], 'preparation_runs': preparation_runs, 'model_trees': model_trees, 'tool_versions': versions, 'source_submodules': submodules, 'environment': environment, 'scientific_endpoints': BIOLOGY}
    plan['sha256'] = identity(plan)
    write(output / 'plan.json', plan)
    return output / 'plan.json'


def load_plan(path):
    plan = read(path)
    require(plan['sha256'] == identity({k: v for k, v in plan.items() if k != 'sha256'}), 'Changed plan')
    check_pins(plan['pins'])
    for tree in plan.get('model_trees', {}).values():
        model_root = Path(tree['path'])
        require(not any(p.is_symlink() for p in model_root.rglob('*')), 'Changed model symlinks')
        require(sorted(str(p.relative_to(model_root)) for p in model_root.rglob('*') if p.is_file()) == tree['files'], 'Changed model tree membership')
    if 'environment' in plan:
        require(all(os.environ.get(key) == value for key, value in plan['environment']['environment'].items()), 'Changed frozen process environment')
        require(sorted(os.sched_getaffinity(0)) == plan['environment']['cpu_affinity'], 'Changed CPU affinity')
    return plan


def admission(config):
    require(shutil.disk_usage(ROOT).free >= (config['reserve_gib'] + config['headroom_gib']) * 1024**3, 'Insufficient disk reserve/headroom')
    require(not any((ROOT / a['path']).with_suffix(Path(a['path']).suffix + '.parts').exists() for a in read(ROOT / 'config/assets.json')), 'Acquisition parts remain')
    processes = subprocess.check_output(['ps', '-eo', 'pid,args'], text=True)
    require(not any(('scripts/fetch.py' in line or 'scripts/bootstrap.sh' in line) and int(line.split()[0]) != os.getpid() for line in processes.splitlines()[1:]), 'Acquisition/bootstrap process still active')
    result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name', '--format=csv,noheader'], capture_output=True, text=True)
    require(result.returncode == 0 and not result.stdout.strip(), 'GPU contention check unavailable or compute process active')


def gpu_resources(path):
    with Path(path).open() as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    result, unavailable = {}, {}
    for field, label, unit in [('memory.used [MiB]', 'peak_memory_mib', 'MiB'), ('utilization.gpu [%]', 'peak_utilization_percent', '%'), ('power.draw [W]', 'peak_power_watts', 'W'), ('temperature.gpu', 'peak_temperature_celsius', ''), ('clocks.current.sm [MHz]', 'peak_sm_clock_mhz', 'MHz')]:
        values = []
        for row in rows:
            match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*' + '(?:' + re.escape(unit) + ')?', row.get(field, '').strip()) if unit else re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)', row.get(field, '').strip())
            if match:
                values.append(float(match[1]))
        result[label] = max(values) if values else None
        unavailable[label] = len(rows) - len(values)
    result['unavailable_samples'] = unavailable
    result['status'] = 'sampled' if any(result[key] is not None for key in unavailable) else 'unavailable: no supported samples'
    return result


def process_resources(receipt):
    recorder = Path(receipt['recorder']) if receipt.get('recorder') else None
    clock = (recorder / 'time.txt').read_text() if recorder and (recorder / 'time.txt').exists() else ''
    wall = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([0-9:.]+)', clock)
    elapsed = None
    if wall:
        elapsed = 0.0
        for part in wall[1].split(':'):
            elapsed = elapsed * 60 + float(part)
    result = {'native_wall_seconds': elapsed, 'recorder_elapsed_seconds': receipt.get('elapsed_ns', 0) / 1e9 if 'elapsed_ns' in receipt else None,
              'start_utc': receipt.get('utc'), 'end_utc': receipt.get('end_utc')}
    for label, field in [('host_max_rss_kib', 'Maximum resident set size (kbytes)'), ('user_cpu_seconds', 'User time (seconds)'), ('system_cpu_seconds', 'System time (seconds)')]:
        match = re.search(re.escape(field) + r': ([0-9.]+)', clock)
        result[label] = float(match[1]) if match else None
    gpu = next((ROOT / item['path'] for item in receipt.get('pins', []) if Path(item['path']).name == 'gpu.csv'), None)
    result['gpu'] = gpu_resources(gpu) if gpu and gpu.exists() else {'status': 'unavailable: no retained sampler'}
    return result


def native_log_diagnostics(native_log):
    lines = native_log.splitlines()
    fallback = ('Failed to find optimal batch size for cuda:0. Consider generating a benchmark with '
                '--run-batchsize-benchmarks, or loading an existing benchmark with --batchsize-benchmarks-file')
    batch_selection = [line for line in lines if re.fullmatch(r'\[[^\]]+\] \[info\] ' + re.escape(fallback), line)]
    return {'effective_batch_chunk_log_lines': [line for line in lines if re.search('batch|chunk', line, re.I)],
            'batch_selection_diagnostics': batch_selection,
            'batch_selection_status': 'precomputed_benchmark_unavailable' if batch_selection else 'no_known_fallback_diagnostic',
            'native_loader_error_lines': [line for line in lines if line not in batch_selection and re.search(r'error|failed|skipp', line, re.I)]}


def run_unit(plan, unit, root, execute=True, retry=None):
    config = plan['config']
    directory = root / 'units' / unit['id']
    context = {'plan': plan['sha256'], 'unit': unit['id']}
    verifier = root / 'verifiers' / (digest(__file__) + '.py')
    verifier.parent.mkdir(parents=True, exist_ok=True)
    if not verifier.exists():
        shutil.copyfile(__file__, verifier)
    require(digest(verifier) == digest(__file__), 'Changed verifier snapshot')
    evidence = [pin(verifier)]
    reserve = config['reserve_gib'] * 1024**3 if execute else 0
    def command(name, argv):
        result = stage(directory, name, list(map(str, argv)), context, retry == unit['id'] + ':' + name, execute, reserve)
        evidence.extend(result['pins'])
        evidence.append(pin(sorted((directory / name).glob('*/finish.json'))[-1]))
        return Path(result['stdout']), result
    d, s = config['dorado'], config['samtools']
    model_path = ROOT / config['models'][unit['tier']]
    model = model_path.name
    calls, producer = command('basecall', [d, 'basecaller', model_path, ROOT / unit['asset']['path'], '--read-ids', unit['ids'], '--device', 'cuda:0', '--batchsize', '0', '--min-qscore', '0', '--trim', 'all', '-v'])
    command('base-quickcheck', [s, 'quickcheck', '-u', '-v', calls])
    sam, _ = command('base-decode', [s, 'view', '-h', calls])
    base = parse_sam(sam, model, unit['parents'])
    summary, _ = command('base-summary', [d, 'summary', calls])
    verify_summary(summary, base)
    aligned, _ = command('align', [d, 'aligner', ROOT / config['index'], calls, '--threads', '16', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
    alignlog = read(sorted((directory / 'align').glob('*/finish.json'))[-1])
    stderr = Path(alignlog['recorder']) / 'stderr'
    require(not re.search(r'(indexing parameters.*overridden|index.*parameter.*mismatch)', stderr.read_text(), re.I), 'Index parameter warning')
    sorted_bam, _ = command('sort', [s, 'sort', '-@', '3', '-m', '256M', '-O', 'BAM', aligned])
    command('aligned-quickcheck', [s, 'quickcheck', '-v', sorted_bam])
    aligned_sam, _ = command('aligned-decode', [s, 'view', '-h', sorted_bam])
    mapping = parse_sam(aligned_sam, model, unit['parents'], plan['dictionary'], base['children'])
    summary, _ = command('aligned-summary', [d, 'summary', sorted_bam])
    verify_summary(summary, mapping, True)
    flagstat, _ = command('flagstat', [s, 'flagstat', '-O', 'json', sorted_bam])
    totals = read(flagstat)
    for key, value in [('total', mapping['metrics']['records']), ('primary', mapping['metrics']['children']), ('secondary', mapping['metrics']['secondary']), ('supplementary', mapping['metrics']['supplementary'])]:
        require(sum(group[key] for group in totals.values()) == value, f'Native flagstat mismatch: {key}')
    command('stats', [s, 'stats', '-F', '0x900', '-r', ROOT / config['reference'], sorted_bam])
    corrected, _ = command('calmd', [s, 'calmd', '-b', sorted_bam, ROOT / config['reference']])
    corrected_sam, _ = command('calmd-decode', [s, 'view', '-h', corrected])
    native = parse_sam(corrected_sam, model, unit['parents'], plan['dictionary'], base['children'])
    calmd_verification = verify_calmd(mapping['children'], native['children'],
                                    lambda regions: command('calmd-reference-iupac', [s, 'faidx', ROOT / config['reference'], *regions])[0])
    parents_file = directory / 'parents.tsv'
    parents_file.parent.mkdir(parents=True, exist_ok=True)
    with parents_file.open('w') as handle:
        handle.write('input_uuid\tnum_samples\toutput_children\tstatus\treason\n')
        counts = collections.Counter(v['parent'] for v in base['children'].values())
        for parent, samples in sorted(unit['parents'].items()):
            handle.write(f"{parent}\t{samples}\t{counts[parent]}\t{'emitted' if counts[parent] else 'not_emitted'}\t{'unresolved' if not counts[parent] else ''}\n")
    resources = process_resources(producer)
    elapsed = resources['native_wall_seconds']
    require(elapsed is not None and elapsed > 0, 'Native wall clock unavailable/below measurement resolution')
    native_log = (Path(producer['recorder']) / 'stderr').read_text()
    observation = {'status': 'verified', 'completed_ns': time.time_ns(), 'verifier_sha256': digest(verifier), 'unit': unit['id'], 'plan': plan['sha256'], 'basecall': {k: v for k, v in base.items() if k != 'children'},
                   'mapping': {k: v for k, v in mapping.items() if k != 'children'}, 'calmd_verification': calmd_verification,
                   'basecall_process_wall_seconds': elapsed, 'recorder_elapsed_seconds': producer['elapsed_ns'] / 1e9,
                   'host_max_rss_kib': resources['host_max_rss_kib'], 'gpu_resources': resources['gpu'],
                   'submitted_signal_seconds_per_wall_second': sum(unit['parents'].values()) / 5000 / elapsed,
                   'emitted_bases_per_wall_second': base['metrics']['called_bases'] / elapsed,
                   **native_log_diagnostics(native_log),
                   'pins': evidence + [pin(parents_file)], 'scientific_endpoints': BIOLOGY}
    observation['complete_work_qualification'] = 'verified' if base['complete_processing'] and not observation['native_loader_error_lines'] else 'unavailable: absent parents or native loader diagnostics'
    write(directory / 'observation.json', observation)
    return observation


def qualify(plan, root):
    receipts, source_pins = [], []
    for unit in [u for u in plan['units'] if u['scope'] in ('smoke', 'fixture')]:
        run_unit(plan, unit, root, execute=False)
        directory = root / 'units' / unit['id']
        source_pins.extend(read(directory / 'observation.json')['pins'] + [pin(directory / 'observation.json')])
        receipt = read(sorted((directory / 'base-decode').glob('*/finish.json'))[-1])
        source = Path(receipt['stdout'])
        text = source.read_text()
        base = parse_sam(source, Path(plan['config']['models'][unit['tier']]).name, unit['parents'])
        if unit['scope'] == 'fixture':
            require(base['metrics']['split_parents'] > 0 and base['metrics']['children'] > 1, 'Genuine fixture did not exercise split branch')
        lines = text.splitlines(True)
        header = [line for line in lines if line.startswith('@')]
        records = [line for line in lines if not line.startswith('@')]
        foreign = re.sub(r'pi:Z:[^\t\n]+', 'pi:Z:' + str(UUID(int=0)), records[0]) if '\tpi:Z:' in records[0] else records[0].replace(records[0].split('\t')[0], str(UUID(int=0)), 1)
        controls = {'foreign': ''.join(header + [foreign] + records[1:]),
                    'duplicate': text + records[0], 'model': text.replace('basecall_model=', 'basecall_model=wrong-')}
        if unit['scope'] == 'fixture':
            controls['split-sp'] = re.sub(r'sp:i:\d+', 'sp:i:999999999', text)
            controls['split-pi'] = re.sub(r'\tpi:Z:[^\t\n]+', '', text)
        control_root = root / 'controls' / unit['id']
        for name, mutant in controls.items():
            sam = control_root / (name + '.sam')
            sam.parent.mkdir(parents=True, exist_ok=True)
            sam.write_text(mutant)
            bam = stage(control_root, name + '-encode', [plan['config']['samtools'], 'view', '-b', str(sam)], {'mutant': pin(sam)})
            decoded = stage(control_root, name + '-decode', [plan['config']['samtools'], 'view', '-h', bam['stdout']], {'bam': pin(bam['stdout'])})
            try:
                parse_sam(decoded['stdout'], Path(plan['config']['models'][unit['tier']]).name, unit['parents'])
            except ValueError as exc:
                receipts.append({'unit': unit['id'], 'control': name, 'status': 'rejected', 'reason': str(exc), 'pins': [pin(sam), pin(bam['stdout'])]})
            else:
                raise ValueError(f'Accepted rejection control: {name}')
        raw_bam = Path(read(sorted((directory / 'basecall').glob('*/finish.json'))[-1])['stdout'])
        truncated = control_root / 'truncated.bam'
        with raw_bam.open('rb') as source_bam, truncated.open('wb') as target:
            target.write(source_bam.read(max(1, raw_bam.stat().st_size // 2)))
        try:
            stage(control_root, 'truncated-quickcheck', [plan['config']['samtools'], 'quickcheck', '-u', '-v', str(truncated)], {'mutant': pin(truncated)})
        except ValueError:
            failure = read(sorted((control_root / 'truncated-quickcheck').glob('*/finish.json'))[-1])
            require(failure['status'] == 'command_failed' and failure['exit'] != 0, 'Truncation control missing native failure')
            receipts.append({'unit': unit['id'], 'control': 'truncated', 'status': 'rejected', 'pins': failure['pins'] + [pin(truncated)]})
        else:
            raise ValueError('Native quickcheck accepted truncation')
        alignment = Path(read(sorted((directory / 'aligned-decode').glob('*/finish.json'))[-1])['stdout']).read_text()
        for name, mutant in ([] if unit['scope'] == 'fixture' else [('reference', re.sub(r'LN:(\d+)', lambda m: 'LN:' + str(int(m[1]) + 1), alignment, count=1)),
                             ('NM', re.sub(r'NM:i:(\d+)', lambda m: 'NM:i:' + str(int(m[1]) + 1), alignment, count=1))]):
            require(mutant != alignment, 'Native aligned fixture did not exercise ' + name)
            sam = control_root / (name + '.sam')
            sam.write_text(mutant)
            encoded = stage(control_root, name + '-encode', [plan['config']['samtools'], 'view', '-b', str(sam)], {'mutant': pin(sam)})
            decoded = stage(control_root, name + '-decode', [plan['config']['samtools'], 'view', '-h', encoded['stdout']], {'bam': pin(encoded['stdout'])})
            try:
                parse_sam(decoded['stdout'], Path(plan['config']['models'][unit['tier']]).name, unit['parents'], plan['dictionary'], base['children'])
            except ValueError as exc:
                receipts.append({'unit': unit['id'], 'control': name, 'status': 'rejected', 'reason': str(exc), 'pins': [pin(sam), pin(encoded['stdout'])]})
            else:
                raise ValueError('Accepted native alignment rejection control: ' + name)
        root_removed = base['children'][records[0].split('\t')[0]]['parent']
        sam = control_root / 'removed.sam'
        sam.write_text(''.join(header + [line for line in records if base['children'][line.split('\t')[0]]['parent'] != root_removed]))
        if len(base['children']) > len([v for v in base['children'].values() if v['parent'] == root_removed]):
            changed = parse_sam(sam, Path(plan['config']['models'][unit['tier']]).name, unit['parents'])
            require(root_removed in changed['missing_parents'] and not changed['complete_processing'], 'Removed parent falsely complete')
        else:
            try:
                parse_sam(sam, Path(plan['config']['models'][unit['tier']]).name, unit['parents'])
            except ValueError as exc:
                require('No emitted' in str(exc), 'Wrong empty control rejection')
        receipts.append({'unit': unit['id'], 'control': 'removed-parent', 'status': 'absence recorded or empty rejected', 'pins': [pin(sam)]})
    write(root / 'qualification.json', {'status': 'verified', 'plan': plan['sha256'], 'verifier_sha256': digest(__file__), 'controls': receipts,
                                        'pins': source_pins + [p for item in receipts for p in item['pins']]})


def report(plan, root):
    rows = []
    for unit in plan['units']:
        directory = root / 'units' / unit['id']
        path = directory / 'observation.json'
        failures = [{**read(p), 'path': str(p), 'pin': pin(p)} for p in sorted(directory.glob('observation-failure-*.json'))]
        state = 'not_run'
        if path.exists():
            observation = read(path)
            try:
                require(observation['plan'] == plan['sha256'], 'Wrong observation plan')
                require(observation.get('verifier_sha256') == digest(__file__) and observation.get('completed_ns') is not None, 'Current successful verifier observation required')
                failure_times = [item.get('completed_ns', int(Path(item['path']).stem.rsplit('-', 1)[1])) for item in failures]
                require(not failure_times or max(failure_times) < observation['completed_ns'], 'Newer observation verification failed')
                check_pins(observation['pins'])
                for finish in directory.glob('*/*/finish.json'):
                    receipt = read(finish)
                    if receipt['status'] == 'finished':
                        check_pins(receipt['pins'])
                state = observation['status']
            except (ValueError, OSError) as exc:
                state = 'evidence_changed: ' + str(exc)
        elif directory.exists():
            state = 'failed_or_unobserved'
        stages = {}
        for stage_dir in directory.iterdir() if directory.exists() else []:
            if not stage_dir.is_dir():
                continue
            starts = sorted(stage_dir.glob('*/start.json'))
            attempts = []
            for index, start in enumerate(starts):
                finish = start.parent / 'finish.json'
                retained = read(finish) if finish.exists() else {**read(start), 'status': 'interrupted', 'exit': None}
                attempts.append({'status': retained['status'], 'exit': retained['exit'], 'receipt': str(finish if finish.exists() else start),
                                 'superseded': index < len(starts) - 1, 'resources': process_resources(retained)})
            if attempts:
                stages[stage_dir.name] = {**attempts[-1], 'attempts': attempts}
        rows.append({'unit': unit['id'], 'scope': unit['scope'], 'tier': unit['tier'], 'status': state, 'stages': stages,
                     'observation': observation if path.exists() else None, 'observation_failures': failures})
    timing = {}
    for tier in ('hac', 'sup'):
        selected = [row for row in rows if row['scope'] == 'timing' and row['tier'] == tier]
        values = [row['observation']['basecall_process_wall_seconds'] for row in selected if row['status'] == 'verified']
        timing[tier] = {'planned': 5, 'successful': len(values), 'failed_or_unavailable': 5 - len(values),
                        'median_seconds': statistics.median(values) if values else None, 'range_seconds': [min(values), max(values)] if values else None,
                        'baseline_status': 'five observations verified' if len(values) == 5 else 'incomplete',
                        'failed_basecall': sum(attempt['status'] in ('command_failed', 'interrupted') for row in selected for attempt in row['stages'].get('basecall', {}).get('attempts', [])),
                        'basecall_attempts': sum(len(row['stages'].get('basecall', {}).get('attempts', [])) for row in selected),
                        'completed_basecall_attempts': sum(attempt['status'] == 'finished' for row in selected for attempt in row['stages'].get('basecall', {}).get('attempts', [])),
                        'not_run': sum(not row['stages'].get('basecall') for row in selected),
                        'complete_work_baseline': len(values) == 5 and all(row['status'] == 'verified' and row['observation']['complete_work_qualification'] == 'verified' for row in selected)}
    other_processes = []
    for start in sorted((root / 'controls').glob('*/*/*/start.json')):
        finish = start.parent / 'finish.json'
        receipt = read(finish) if finish.exists() else {**read(start), 'status': 'interrupted', 'exit': None}
        other_processes.append({'kind': 'qualification_control', 'receipt': str(finish if finish.exists() else start), 'status': receipt['status'], 'exit': receipt['exit'], 'resources': process_resources(receipt)})
    for run_name in plan.get('preparation_runs', []):
        run = ROOT / run_name
        receipt = {'recorder': str(run), 'utc': (run / 'start.txt').read_text().strip(), 'end_utc': (run / 'end.txt').read_text().strip()}
        native_exit = int((run / 'exit-status.txt').read_text())
        other_processes.append({'kind': 'preparation', 'recorder': str(run), 'status': 'finished' if native_exit == 0 else 'command_failed', 'exit': native_exit, 'resources': process_resources(receipt)})
    all_attempts = [attempt for row in rows for stage in row['stages'].values() for attempt in stage['attempts']] + other_processes
    attempt_counts = dict(collections.Counter(attempt['status'] for attempt in all_attempts))
    attempt_counts['total'] = len(all_attempts)
    output = {'plan': plan['sha256'], 'units': rows, 'other_native_processes': other_processes, 'native_process_attempt_counts': attempt_counts, 'timing': timing, 'scientific_endpoints': BIOLOGY,
              'limits': ['Reference disagreement is a conditional mapped-child proxy.', 'Cache state uncontrolled; no model-tier speedup or winner claim.', 'Absent parents have unresolved causes.', 'Split sibling completeness cannot be established by parent membership alone.', 'Sampler fields may be unavailable; inspect raw logs.']}
    write(root / 'report.json', output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'verify', 'report', 'qualify-native'))
    parser.add_argument('path', type=Path, help='prepare: new output directory; otherwise plan.json')
    parser.add_argument('--config', type=Path, default=Path('config/stock-benchmark.json'))
    parser.add_argument('--scope', choices=('smoke', 'fixture', 'timing', 'full', 'all'), default='all')
    parser.add_argument('--retry', help='explicit failed/interrupted UNIT:STAGE; never repeats a successful producer')
    args = parser.parse_args()
    (ROOT / 'results/stock').mkdir(parents=True, exist_ok=True)
    with (ROOT / 'results/stock/host.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            print(prepare(args.config, args.path.resolve()))
            return
        plan = load_plan(args.path)
        root = args.path.resolve().parent
        if args.action == 'qualify-native':
            qualify(plan, root)
        elif args.action in ('run', 'verify'):
            if args.action == 'run' and args.scope in ('all', 'full', 'timing'):
                qualification = read(root / 'qualification.json')
                require(qualification['status'] == 'verified' and qualification['plan'] == plan['sha256'] and qualification['verifier_sha256'] == digest(__file__), 'Native qualification required for current verifier')
                check_pins(qualification['pins'])
            units = [u for u in plan['units'] if args.scope == 'all' or u['scope'] == args.scope]
            for unit in units:
                if args.action == 'run':
                    admission(plan['config'])
                try:
                    run_unit(plan, unit, root, args.action == 'run', args.retry)
                except Exception as exc:
                    write(root / 'units' / unit['id'] / ('observation-failure-' + str(time.time_ns()) + '.json'), {'status': 'observation_failed', 'error': str(exc), 'utc': utc(), 'completed_ns': time.time_ns(), 'verifier_sha256': digest(__file__)})
                    report(plan, root)
                    raise
        output = report(plan, root)
        print(json.dumps({'report': str(root / 'report.json'), 'timing': output['timing']}, indent=2))


if __name__ == '__main__':
    main()
