#!/usr/bin/env python3
"""Freeze same-H prefix arms, then map/observe without feeding truth into inference."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import resource
import sys

import location as loc
import native_unit as native


def write_text(path, text):
    with Path(path).open('x') as stream:
        stream.write(text)
        stream.flush()
        loc.os.fsync(stream.fileno())
    loc.sync_directory(Path(path).parent)


def evaluation_sources():
    base = loc.ROOT/'tools/prefix_feedback'
    return [loc.pin((base/name).resolve()) for name in loc.read(base/'evaluation-source-files.json')]


def checked(directory, schema, w):
    value, outer = native.completed(directory, w, schema)
    return value, outer


def validate_emission_join(work, prepared, prepared_pin, location_pin):
    loc.require(work['prepared'] == prepared_pin, 'Inference work uses a different prepared completion')
    loc.require(prepared['location_complete'] == location_pin, 'Prepared unit uses a different location completion')


def validate_mapping_join(mapping, emitted_pin, horizon, canonical_arm):
    loc.require(mapping['emitted'] == emitted_pin, 'Candidate mapping uses a different emitted completion')
    loc.require(mapping['horizon'] == horizon and mapping['arm'] == canonical_arm,
                'Candidate mapping arm/horizon differs')


def rename_native(source, target, old_name):
    lines = []
    records = 0
    for line in Path(source).read_text().splitlines():
        if line.startswith('@'):
            lines.append(line)
            continue
        fields = line.split('\t')
        if fields[0] != old_name:
            continue
        fields[0] = loc.UUID
        lines.append('\t'.join(fields))
        records += 1
    loc.require(records > 0, 'Native analysis rename found no prefix records')
    write_text(target, '\n'.join(lines)+'\n')


def arm_sequence(row, selected, center):
    begin, end = selected['core_begin'], selected['core_end']
    loc.require(set(center) <= set('ACGT'), 'Candidate center is noncanonical')
    sequence = row['sequence'][:begin]+center+row['sequence'][end:]
    quality = row['quality'][:begin]+'!'*len(center)+row['quality'][end:]
    if sequence == row['sequence']:
        quality = row['quality']
    loc.require(len(sequence) == len(quality), 'Candidate SEQ/Q length mismatch')
    return sequence, quality


def emit(args, execution, w):
    tests = execution.stage('prefix-observation-controls', ['uv', 'run', '--no-sync', 'python',
        '-m', 'unittest', 'discover', '-s', 'tools/prefix_feedback', '-p', 'test_evaluate.py', '-v'])
    controls = Path(tests['raw']['stderr']['path']).read_text()
    loc.require(re.search(r'(?m)^Ran 12 tests in [0-9.]+s$', controls) is not None
                and controls.rstrip().endswith('\nOK'),
                'Evaluation emission requires12 actual tests and zero skips')
    loc.require(args.inference is not None and args.prepared is not None and args.location is not None,
                'Emission requires frozen inference/prepared/location')
    inference, inference_outer = checked(args.inference, 'prefix-feedback-inference/1', w)
    prepared, prepared_outer = checked(args.prepared, 'prefix-feedback-prepared/1', w)
    location, location_outer = checked(args.location, 'prefix-location-complete/1', w)
    original = loc.read(args.location/'prefixes.json')
    plans = loc.read(args.prepared/'plans.json')
    work = loc.read(args.inference/'work-price.json')
    validate_emission_join(work, prepared, loc.pin(args.prepared/'complete.json'), loc.pin(args.location/'complete.json'))
    horizon = work['plan']['horizon']
    row = next(row for row in original['prefixes'] if row['horizon'] == horizon)
    selected = next(plan for plan in plans['plans'] if plan['horizon'] == horizon)['selection']
    mapped = loc.read(args.location/'locations.json')['mapped']
    loc.check(mapped)
    rename_native(mapped['path'], args.output/'native.sam', row['qname'])
    write_text(args.output/'parents.ids', loc.UUID+'\n')
    names = {'native': row['sequence']}
    qualities = {'native': row['quality']}
    if inference['native'] is not None:
        result = loc.read(args.inference/'native/result.json')
        loc.require(result['horizon'] == horizon and result['qname'] == row['qname']
                    and result['irreversible_commits'] == 0 and result['encoder_reset'] is True,
                    'Frozen inference identity/commitments differ')
        for arm, center in (('reference_free', result['matched_reference_free']['sequence']),
                            ('final_rerank', result['final_rerank']['sequence']),
                            ('partial_search', result['partial_search']['selected']['sequence'])):
            names[arm], qualities[arm] = arm_sequence(row, selected, center)
    else:
        for arm in ('reference_free', 'final_rerank', 'partial_search'):
            names[arm], qualities[arm] = row['sequence'], row['quality']
    canonical = {}
    arms = []
    for arm, sequence in names.items():
        alias = canonical.setdefault(sequence, arm)
        sam = args.output/(arm+'.sam')
        if alias == arm and arm != 'native':
            loc.emit_sam(sam, [dict(qname=loc.UUID, sequence=sequence, quality=qualities[arm])])
        elif arm == 'native':
            sam = args.output/'native.sam'
        else:
            sam = args.output/(alias+'.sam')
        arms.append(dict(arm=arm, canonical_arm=alias, sequence_sha256=loc.hashlib.sha256(sequence.encode()).hexdigest(),
                         sam=loc.pin(sam), already_mapped=alias == 'native', sequence_bases=len(sequence)))
    loc.fresh(args.output/'arms.json', dict(schema='prefix-feedback-observation-arms/1', arms=arms,
        horizon=horizon, original_prefix_qname=row['qname'], analysis_qname=loc.UUID, parent=loc.UUID,
        rename='oneH_perSAM_UUID_only_interface_reversible_name_change_no_sequence_change',
        quality_policy='native_unchanged; newly emitted center bases Phred0 placeholder, uncalibrated',
        core_selection=selected,
        prefixes_physical_molecules=1, correlated_horizons=2, truth_imported=False,
        inference=loc.pin(args.inference/'complete.json'), prepared=loc.pin(args.prepared/'complete.json'),
        location=loc.pin(args.location/'complete.json'), upstream_outer=inference_outer+prepared_outer+location_outer))
    return dict(files=[loc.pin(args.output/'arms.json'), loc.pin(args.output/'parents.ids')]+
                      list({arm['sam']['path']: arm['sam'] for arm in arms}.values()))


def mapped(args, execution, w):
    loc.require(args.emitted is not None and args.arm is not None, 'Mapping requires emitted canonical arm')
    checked(args.emitted, 'prefix-feedback-evaluation-emit/1', w)
    manifest = loc.read(args.emitted/'arms.json')
    arm = next(item for item in manifest['arms'] if item['arm'] == args.arm)
    loc.require(arm['canonical_arm'] == args.arm and not arm['already_mapped'], 'Map only unique changed arms')
    loc.check(arm['sam'])
    loc.require(loc.pin(loc.SNAPSHOT)['sha256'] == loc.SNAPSHOT_SHA, 'Frozen snapshot changed')
    snapshot = loc.read(loc.SNAPSHOT)
    tools = {name: snapshot['tools'][name] for name in ('dorado', 'samtools', 'index')}
    for item in tools.values():
        loc.check(item)
    closure = loc.runtime(execution, tools)
    bam = execution.stage('prefix-observe-sam-to-bam', [tools['samtools']['path'], 'view', '-b', arm['sam']['path']])
    aligned = execution.stage('prefix-observe-align', [tools['dorado']['path'], 'aligner', tools['index']['path'],
        bam['raw']['stdout']['path'], '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
    sam = execution.stage('prefix-observe-sam', [tools['samtools']['path'], 'view', '-h', aligned['raw']['stdout']['path']])
    # Reuse the strict exact SEQ/Q+orientation SAM guard, with the analysis-only UUID name.
    input_fields = next(line.split('\t') for line in Path(arm['sam']['path']).read_text().splitlines() if not line.startswith('@'))
    census = loc.sam_locations(sam['raw']['stdout']['path'], [dict(qname=loc.UUID, parent=loc.UUID,
         horizon=manifest['horizon'], sequence=input_fields[9], quality=input_fields[10])])
    loc.fresh(args.output/'mapping.json', dict(schema='prefix-feedback-observation-mapping/1',
              emitted=loc.pin(args.emitted/'complete.json'), arm=args.arm, horizon=manifest['horizon'],
              mapped=loc.pin(sam['raw']['stdout']['path']), runtime=closure, census=census, truth_imported=False))
    return dict(files=[loc.pin(args.output/'mapping.json')])


def score(args, execution, w):
    loc.require(args.emitted is not None and args.arm is not None, 'Observation requires emitted arm')
    checked(args.emitted, 'prefix-feedback-evaluation-emit/1', w)
    manifest = loc.read(args.emitted/'arms.json')
    arm = next(item for item in manifest['arms'] if item['arm'] == args.arm)
    baseline = next(item for item in manifest['arms'] if item['arm'] == 'native')['sam']
    if arm['already_mapped']:
        candidate = baseline
        mapping_outer = []
    else:
        loc.require(args.mapping is not None, 'Changed sequence requires qualified native mapping')
        _, mapping_outer = checked(args.mapping, 'prefix-feedback-evaluation-map/1', w)
        mapping = loc.read(args.mapping/'mapping.json')
        validate_mapping_join(mapping, loc.pin(args.emitted/'complete.json'), manifest['horizon'], arm['canonical_arm'])
        candidate = mapping['mapped']
    for item in (baseline, candidate):
        loc.check(item)
    # This is the first phase permitted to read truth/eligible bytes.
    loc.require(loc.pin(loc.SNAPSHOT)['sha256'] == loc.SNAPSHOT_SHA, 'Frozen snapshot changed')
    snapshot = loc.read(loc.SNAPSHOT)
    inputs = [snapshot['reference'], snapshot['truth'], snapshot['confident'], snapshot['pairer'], snapshot['observer'],
              *snapshot['eligible'].values()]
    for item in inputs:
        loc.check(item)
    closure = [native.runtime(execution, snapshot[name]['path']) for name in ('pairer', 'observer')]
    summaries = {}
    for domain, eligible in sorted(snapshot['eligible'].items()):
        pairs, summary = args.output/('pair-'+domain), args.output/('summary-'+domain)
        execution.stage('prefix-pair-'+domain, [snapshot['pairer']['path'], 'score',
            '--reference', snapshot['reference']['path'], '--eligible', eligible['path'],
            '--left', baseline['path'], '--right', candidate['path'],
            '--parents', args.emitted/'parents.ids', '--output', pairs])
        execution.stage('prefix-summary-'+domain, [snapshot['pairer']['path'], 'summarize',
            '--pairs', pairs, '--selected', 'all', '--output', summary])
        value = loc.read(summary/'summary.json')
        loc.require(value['parents'] == 1 and value['complete'], 'Single physical parent summary differs')
        summaries[domain] = loc.pin(summary/'summary.json')
    for name, sam in (('native', baseline), ('candidate', candidate)):
        execution.stage('prefix-alleles-'+name, [snapshot['observer']['path'], 'observe',
            '--reference', snapshot['reference']['path'], '--vcf', snapshot['truth']['path'],
            '--confident', snapshot['confident']['path'], '--sam', sam['path'],
            '--parents', args.emitted/'parents.ids', '--output', args.output/('alleles-'+name)])
    comparison = args.output/'allele-comparison'
    execution.stage('prefix-allele-compare', [snapshot['observer']['path'], 'compare',
        '--baseline', args.output/'alleles-native', '--candidate', args.output/'alleles-candidate', '--output', comparison])
    support = {kind: Counter(baseline_alt=0, alt_retained=0, alt_loss=0)
               for kind in ('snv', 'insertion', 'deletion')}
    core = manifest['core_selection']
    changed = arm['sequence_sha256'] != next(item for item in manifest['arms'] if item['arm'] == 'native')['sequence_sha256']
    if changed and core['status'] == 'selected':
        with (comparison/'variants.tsv').open() as stream:
            variants = {row['variant']: row for row in csv.DictReader(stream, delimiter='\t')}
        with (comparison/'paired.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                variant = variants[row['variant']]
                if (variant['contig'] == core['contig'] and int(variant['start0']) < core['reference_end']+1
                        and int(variant['end0']) > max(0, core['reference_begin']-1)):
                    for key in ('baseline_alt', 'alt_retained', 'alt_loss'):
                        support[row['stratum']][key] += int(row[key])
    loc.fresh(args.output/'observation.json', dict(schema='prefix-feedback-posthoc-observation/1',
        horizon=manifest['horizon'], arm=args.arm, canonical_arm=arm['canonical_arm'], physical_molecules=1,
        correlated_horizons=2, summaries=summaries, allele_comparison=loc.pin(comparison/'compare.json'),
        inference=manifest['inference'], emitted=loc.pin(args.emitted/'complete.json'), mapping_outer=mapping_outer,
        baseline=baseline, candidate=candidate, runtime=closure, scientific_inputs=inputs,
        changed_core_alt_support={key: dict(value) for key, value in support.items()},
        changed_footprint_policy='conservative selected native core reference interval plus one flank base; observer window overlap; posthoc only',
        truth_used_for='posthoc_observation_only', private_variant_safety_qualified=False,
        biological_qualification=False, candidate_promoted=False,
        scope='sameH_conditional_mapping_matched_domain_observation_one_exposed_parent_not64parent_endpoint'))
    return dict(files=[loc.pin(path) for path in sorted(args.output.rglob('*'))
                       if path.is_file() and path.name not in ('attempt.json', 'kernel-limits.json')])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('emit', 'map', 'score'))
    parser.add_argument('--admission-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in ('inference', 'prepared', 'location', 'emitted', 'mapping'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--arm', choices=('native', 'reference_free', 'final_rerank', 'partial_search'))
    args = parser.parse_args()
    loc.require(re.fullmatch('[A-Za-z0-9_-]{1,80}', args.admission_id), 'Unsafe unit identity')
    args.output = args.output.resolve()
    loc.require(args.output.is_relative_to(loc.ROOT/'results/context-feedback'), 'Output outside owned results')
    args.output.mkdir()
    w = loc.load('causal_evaluation_execution', loc.ROOT/'scripts/context-feedback.py')
    sources = evaluation_sources()
    now = datetime.now(timezone.utc)
    grant = dict(id=args.admission_id, maximum_wall_seconds=280,
                 expires_utc=(now+timedelta(seconds=280)).isoformat(), cpu_quota=2,
                 memory_bytes=16*1024**3, address_space_bytes=24*1024**3, swap_bytes=0,
                 maximum_output_bytes=512*1024**2,
                 cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-'+args.admission_id+'.service')
    loc.fresh(args.output/'attempt.json', dict(argv=sys.argv, sources=sources, grant=grant,
                                             truth_phase=args.phase == 'score'))
    w.cgroup_limits(grant)
    directory = Path('/sys/fs/cgroup')/grant['cgroup'].lstrip('/')
    loc.fresh(args.output/'kernel-limits.json', dict(cgroup=grant['cgroup'], values={name: (directory/name).read_text()
        for name in ('cpu.max', 'memory.max', 'memory.swap.max')}, rlimit_as=resource.getrlimit(resource.RLIMIT_AS),
        rlimit_fsize=resource.getrlimit(resource.RLIMIT_FSIZE), service=w.supervisor.show('context-'+args.admission_id+'.service')))
    execution = w.Execution(grant, args.output, sources)
    result = {'emit': emit, 'map': mapped, 'score': score}[args.phase](args, execution, w)
    execution.budget()
    loc.fresh(args.output/'complete.json', dict(schema='prefix-feedback-evaluation-'+args.phase+'/1', complete=True,
        sources=sources, attempt=loc.pin(args.output/'attempt.json'), stages=execution.receipts,
        files=[loc.pin(args.output/'kernel-limits.json')]+result['files'], biological_qualification=False,
        candidate_promoted=False))
    print(loc.json.dumps(dict(completion=loc.pin(args.output/'complete.json'))))


if __name__ == '__main__':
    main()
