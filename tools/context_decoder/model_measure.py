#!/usr/bin/env python3
"""Measure fixed emitted complete parents with the maintained native tools."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
EMISSION = ROOT/'results/context-feedback/v5-model-emission-2/output/complete.json'
SNAPSHOT_HASH = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'
SOURCE_PATHS = ('tools/context_decoder/model_measure.py', 'tests/test_context_model_measure.py')
CAPS = dict(wall_seconds=300, cpu=2, memory=16*1024**3, address_space=24*1024**3,
            swap=0, maximum_output_bytes=512*1024**2, disk_floor_bytes=30*1024**3)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def require(value, message):
    if not value:
        raise ValueError(message)


def sam_census(path, parents, boundary):
    names = []
    for line in Path(path).read_text().splitlines():
        if line.startswith('@'):
            continue
        fields = line.split('\t')
        require(len(fields) >= 11 and fields[0] in parents, 'Foreign or short SAM record')
        if not int(fields[1]) & 0x900:
            names.append(fields[0])
    require(Counter(names) == Counter(parents), 'Complete64-parent primary census differs')
    return {parent: boundary.mapped(path, parent) for parent in parents}


def custody(emitted, mapped, parents, boundary):
    left = sam_census(emitted, parents, boundary)
    right = sam_census(mapped, parents, boundary)
    require(all((left[p]['sequence'], left[p]['quality']) ==
                (right[p]['sequence'], right[p]['quality']) for p in parents),
            'Mapper changed complete-parent SEQ/Q')


def source_pins(boundary):
    return [boundary.pin(ROOT/path) for path in SOURCE_PATHS]


def emission_unit(audit, program):
    boundary, w = program.c, program.w
    directory = EMISSION.parent.parent
    pin = boundary.pin(directory/'complete.json')
    outer = audit.outer_unit(directory.name, pin, program)
    unit = boundary.read(pin['path'])
    require(unit['schema'] == 'context-model-observer-unit/1' and unit['complete'] is True
            and unit['phase'] == 'emit' and unit['native'] == boundary.pin(EMISSION)
            and len(unit['stages']) == 1, 'Emission worker completion differs')
    for item in unit['sources']+unit['files']:
        boundary.check(item)
    stage = w.evidence.stage(unit['stages'][0], boundary)
    expected = ['uv', 'run', '--no-sync', 'python', str(ROOT/'tools/context_decoder/model_observe_v2.py'),
                'emit', '--output', str(EMISSION.parent)]
    require(stage['argv'] == expected and boundary.read(stage['raw']['stdout']['path']) ==
            dict(completion=boundary.pin(EMISSION)), 'Emission actual raw command/output differs')
    return [pin, *outer, *unit['sources'], *unit['files'], *unit['stages']]


def inputs():
    audit = load('measurement_model_observer', ROOT/'tools/context_decoder/model_observe_v2.py')
    program = audit.module('measurement_program', ROOT/'scripts/context-program.py')
    c = program.c
    emission_outer = emission_unit(audit, program)
    result = audit.completed(c.pin(EMISSION), 'emit')
    require(result['snapshot']['sha256'] == SNAPSHOT_HASH, 'Frozen snapshot identity differs')
    snapshot = c.read(result['snapshot']['path'])
    observer = audit.module('measurement_original_observer', audit.ORIGINAL_ROOT/'tools/context_decoder/observe.py')
    require(observer.ROOT == observer.c.ROOT == observer.w.ROOT == audit.ORIGINAL_ROOT,
            'Original observer source root differs')
    free_pin = result['historical_reference_free_mapping']
    c.check(free_pin)
    free = observer.completed_producer(free_pin['path'], 'arm', 'ordinary')
    old_emission = observer.completed_producer(free['manifest']['path'], 'prepare', 'ordinary')
    require(old_emission['snapshot'] == result['snapshot'], 'Historical mapping snapshot differs')
    historical_stages = [observer.w.evidence.stage(p, observer.c) for p in free['stages']]
    old_sam = next(arm['sam'] for arm in old_emission['arms'] if arm['arm'] == 'reference_free')
    tools = snapshot['tools']
    require(historical_stages[0]['argv'] == [tools['samtools']['path'], 'view', '-b', old_sam['path']]
            and historical_stages[1]['argv'] == [tools['dorado']['path'], 'aligner', tools['index']['path'],
                historical_stages[0]['raw']['stdout']['path'], '--threads', '2', '--no-sort', '--mm2-opts',
                '-x lr:hq -I 16G --eqx -Y']
            and historical_stages[2]['argv'] == [tools['samtools']['path'], 'view', '-h',
                historical_stages[1]['raw']['stdout']['path']]
            and free['mapped'] == historical_stages[2]['raw']['stdout'], 'Historical native mapping chain differs')
    data = [snapshot[key] for key in ('pairer', 'observer', 'parents', 'native', 'truth', 'confident', 'reference')]
    data += list(snapshot['eligible'].values()) + list(tools.values()) + snapshot['baseline_observation_pins']
    data += [free['mapped'], old_sam, result['disabled_edit']]
    for item in data+free['outputs']:
        c.check(item)
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    require(len(parents) == len(set(parents)) == 64 and set(snapshot['eligible']) == {'100', '500'},
            'Frozen parent/domain census differs')
    originals = sam_census(snapshot['native']['path'], parents, c)
    custody(result['disabled_edit']['path'], snapshot['native']['path'], parents, c)
    canonical = {}
    for arm in result['arms']:
        name = arm['canonical_arm']
        sam = sam_census(arm['sam']['path'], parents, c)
        edits = arm['edits']
        require(all(edit['replacement'] != edit['stock'] and edit['parent'] in originals for edit in edits),
                'No-op or foreign-parent edit')
        by_parent = {}
        for edit in edits:
            require(originals[edit['parent']]['sequence'][edit['start']:edit['end']] == edit['stock'],
                    'Edit stock/native join differs')
            by_parent.setdefault(edit['parent'], []).append(edit)
        for parent in parents:
            selected = sorted(by_parent.get(parent, []), key=lambda edit: edit['start'])
            require(all(a['end'] <= b['start'] for a, b in zip(selected, selected[1:])), 'Overlapping edit ledger')
            original = originals[parent]
            seq_q = observer.splice(original['sequence'], original['quality'], selected)
            require(seq_q == observer.independent_splice(original['sequence'], original['quality'], selected)
                    == (sam[parent]['sequence'], sam[parent]['quality']), 'Emitted SEQ/Q does not reconstruct')
        if arm['historical_reference_free'] is not None:
            require(arm['sam']['sha256'] == old_sam['sha256'] and arm['historical_reference_free'] == free['mapped'],
                    'Historical alias lacks byte identity')
        if name in canonical:
            require(canonical[name]['sam'] == arm['sam'] and canonical[name]['edits'] == edits,
                    'Alias changed bytes or edits')
        else:
            canonical[name] = arm
    require(set(canonical) == {'mu0.001-graph', 'mu0.001-reference', 'mu0.001-none'},
            'Fixed three-output emission differs')
    custody(old_sam['path'], free['mapped']['path'], parents, observer.c)
    evidence = [c.pin(EMISSION), *emission_outer, result['snapshot'], free_pin, *data,
                *[arm['sam'] for arm in canonical.values()]]
    return audit, program, result, snapshot, parents, originals, free, canonical, evidence


def summary_check(summary):
    require(summary['complete'] is True and summary['parents'] == summary['selected_parents'] == 64
            and summary['selection'] == 'all' and summary['conservation']['blocks_equal_parents']
            and summary['conservation']['same_reference_exposure_both_arms'], 'Paired complete-parent conservation failed')
    metrics = summary['metrics']
    denominators = {}
    for name in ('left', 'candidate'):
        counts = metrics[name+'_counts']
        require(set(counts) == {'m', 'x', 'i', 'd'} and all(type(v) is int and v >= 0 for v in counts.values()),
                'Invalid endpoint counts')
        denominator = sum(counts.values())
        require(denominator > 0, 'Zero aggregate endpoint denominator')
        rate = (counts['x']+counts['i']+counts['d'])/denominator
        require(abs(rate-metrics[name+'_error_fraction']) <= 1e-15, 'Endpoint rate/denominator differs')
        denominators[name] = denominator
    require(metrics['left_error_fraction'] > 0, 'Zero baseline error rate cannot define relative reduction')
    expected = 1-metrics['candidate_error_fraction']/metrics['left_error_fraction']
    require(abs(expected-metrics['relative_error_reduction']) <= 1e-12, 'Relative endpoint rate differs')
    require(summary['metrics']['positive_denominator_parents']+summary['zero_exposure_parents'] == 64,
            'Positive/zero parent accounting differs')
    technical = {}
    for key in ('parent_bootstrap', 'genomic_1mb_block_bootstrap'):
        interval = summary[key]['candidate_minus_left_error_fraction_95_percentile']
        require(summary[key]['status'] == 'available' and len(interval) == 2 and interval[0] <= interval[1],
                'Missing technical uncertainty')
        technical[key] = interval[1] < 0
    return dict(denominators=denominators, one_percent=expected >= 0.01, technical_upper_negative=technical,
                relative_error_reduction=metrics['relative_error_reduction'])


def edit_footprint(original, edit, boundary):
    if original['flag'] & 4:
        return None
    a, b = edit['start'], edit['end']
    if original['reverse']:
        a, b = len(original['sequence'])-b, len(original['sequence'])-a
    a, b = max(a-1, 0), min(b+1, len(original['sequence']))
    query, reference, touched = 0, original['start'], []
    for length, op in boundary.cigar(original['fields'][5]):
        if op in '=XM':
            lo, hi = max(a, query), min(b, query+length)
            if lo < hi:
                touched.append((reference+lo-query, reference+hi-query))
            query += length; reference += length
        elif op in 'IS':
            if op == 'I' and max(a, query) < min(b, query+length):
                touched.append((max(0, reference-1), reference+1))
            query += length
        elif op in 'DN':
            if a <= query < b:
                touched.append((reference, reference+length))
            reference += length
        else:
            require(op == 'P', 'Hard-clipped native cannot define complete edit footprint')
    if not touched:
        return None
    return dict(contig=original['contig'], start0=min(a for a, _ in touched), end0=max(b for _, b in touched))


def variant_support(arm, originals, parents, alleles, baseline, audit, boundary):
    variants = {row['variant']: row for row in audit.table(Path(alleles)/'variants.tsv')}
    before = {(row['parent'], row['variant']): row['call'] for row in audit.table(Path(baseline)/'observations.tsv')}
    after = {(row['parent'], row['variant']): row['call'] for row in audit.table(Path(alleles)/'observations.tsv')}
    require(all(p in parents and v in variants for p, v in before.keys() | after.keys()), 'Foreign allele observation')
    footprints = [(edit['case_id'], edit['parent'], edit_footprint(originals[edit['parent']], edit, boundary))
                  for edit in arm['edits']]
    counts, touched = Counter(), []
    for (parent, variant), call in sorted(before.items()):
        if call != 'alt':
            continue
        row = variants[variant]
        category = row['stratum']
        counts[category+'_baseline_alt'] += 1
        counts[category+'_retained'] += after.get((parent, variant), 'unobservable') == 'alt'
        hits = [case for case, owner, footprint in footprints if owner == parent and footprint is not None
                and footprint['contig'] == row['contig'] and footprint['start0'] < int(row['end0'])
                and int(row['start0']) < footprint['end0']]
        if hits:
            counts[category+'_changed_footprint_alt'] += 1
            touched.append(dict(parent=parent, variant=variant, stratum=category, cases=hits,
                                baseline=call, candidate=after.get((parent, variant), 'unobservable')))
    for category in ('snv', 'insertion', 'deletion'):
        for key in ('baseline_alt', 'retained', 'changed_footprint_alt'):
            counts.setdefault(category+'_'+key, 0)
    return dict(counts=dict(counts), changed_footprint_observations=touched,
                changed_centers=len(footprints), unavailable_edit_footprints=sum(p is None for _, _, p in footprints),
                footprint_policy='Native primary query edit interval plus one native query base on each side, projected through native CIGAR; conservative overlap with observer variant window.',
                adequate_per_class_changed_support=all(counts[k+'_changed_footprint_alt'] >= 100 for k in ('snv', 'insertion', 'deletion')))


def runtime_closure(execution, snapshot, boundary):
    result = []
    for name, binary in (('dorado', snapshot['tools']['dorado']), ('samtools', snapshot['tools']['samtools']),
                         ('pairer', snapshot['pairer']), ('observer', snapshot['observer'])):
        stage = execution.stage('measure-ldd-'+name, ['/usr/bin/ldd', binary['path']])
        libraries = []
        text = Path(stage['raw']['stdout']['path']).read_text()
        require('not found' not in text, 'Native runtime dependency missing')
        for line in text.splitlines():
            match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
            if match:
                libraries.append(boundary.pin(match.group(1)))
        require(libraries, 'Native runtime closure is empty')
        result.append(dict(tool=name, binary=binary, stage=execution.receipts[-1], libraries=libraries))
    return result


def measure(args):
    require(re.fullmatch('[a-zA-Z0-9_-]+', args.admission_id), 'Invalid unique admission identity')
    program = load('measurement_worker_program', ROOT/'scripts/context-program.py')
    c, w = program.c, program.w
    output = args.output.resolve()
    require(output.is_relative_to(ROOT/'results/context-feedback'), 'Measurement output outside owned results')
    output.mkdir()
    pins = source_pins(c)
    now = datetime.now(timezone.utc)
    grant = dict(id=args.admission_id, maximum_wall_seconds=280,
                 expires_utc=(now+timedelta(seconds=280)).isoformat(), maximum_output_bytes=CAPS['maximum_output_bytes'],
                 cpu_quota=2, memory_bytes=CAPS['memory'], address_space_bytes=CAPS['address_space'], swap_bytes=0,
                 cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-'+args.admission_id+'.service')
    c.fresh(output/'attempt.json', dict(argv=sys.argv, sources=pins, grant=grant, arm=args.arm,
                                      emission=c.pin(EMISSION), caps=CAPS))
    w.cgroup_limits(grant)
    execution = w.Execution(grant, output, pins)
    engineering = execution.stage('measure-engineering', ['uv', 'run', '--no-sync', 'python', '-m', 'unittest', 'discover',
                                                         '-s', 'tests', '-p', 'test_context_model_measure.py', '-v'])
    controls = Path(engineering['raw']['stderr']['path']).read_text()
    require(re.search(r'(?m)^Ran 17 tests in [0-9.]+s$', controls) is not None
            and controls.rstrip().endswith('\nOK') and 'skipped' not in controls.lower(),
            'Measurement engineering requires17 actual tests and zero skips')
    audit, _, emission, snapshot, parents, originals, free, canonical, evidence = inputs()
    selected = canonical['mu0.001-'+args.arm]
    require(selected['historical_reference_free'] is None, 'Historical alias must reuse its qualified mapping')
    c.fresh(output/'inputs.json', dict(emission=c.pin(EMISSION), snapshot=emission['snapshot'], selected=selected,
                                     historical_mapping=emission['historical_reference_free_mapping'], evidence=evidence))
    runtime = runtime_closure(execution, snapshot, c)

    def stage(name, argv):
        return execution.stage('measure-'+args.arm+'-'+name, argv)['raw']['stdout']['path']

    tools = snapshot['tools']
    bam = stage('sam-to-bam', [tools['samtools']['path'], 'view', '-b', selected['sam']['path']])
    aligned = stage('align', [tools['dorado']['path'], 'aligner', tools['index']['path'], bam,
                            '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
    mapped = stage('mapped-sam', [tools['samtools']['path'], 'view', '-h', aligned])
    custody(selected['sam']['path'], mapped, parents, c)
    summaries = {}
    for name, left in (('native', snapshot['native']['path']), ('reference_free', free['mapped']['path'])):
        summaries[name] = {}
        for domain, eligible in sorted(snapshot['eligible'].items()):
            pairs = output/('pair-'+name+'-'+domain)
            summary = output/('summary-'+name+'-'+domain)
            stage('pair-'+name+'-'+domain, [snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'],
                  '--eligible', eligible['path'], '--left', left, '--right', mapped,
                  '--parents', snapshot['parents']['path'], '--output', pairs])
            stage('summary-'+name+'-'+domain, [snapshot['pairer']['path'], 'summarize', '--pairs', pairs,
                                              '--selected', 'all', '--output', summary])
            summaries[name][domain] = dict(summary=c.pin(summary/'summary.json'), checks=summary_check(c.read(summary/'summary.json')))
    alleles = output/'alleles'
    stage('observe', [snapshot['observer']['path'], 'observe', '--reference', snapshot['reference']['path'],
          '--vcf', snapshot['truth']['path'], '--confident', snapshot['confident']['path'], '--sam', mapped,
          '--parents', snapshot['parents']['path'], '--output', alleles])
    comparisons = {}
    for name, baseline in (('native', snapshot['baseline_observations']),
                           ('reference_free', str(Path(emission['historical_reference_free_mapping']['path']).parent/'alleles'))):
        directory = output/('comparison-'+name)
        stage('compare-'+name, [snapshot['observer']['path'], 'compare', '--baseline', baseline,
                               '--candidate', alleles, '--output', directory])
        comparison = c.read(directory/'compare.json')
        require(comparison['parents'] == 64, 'Allele parent census differs')
        comparisons[name] = dict(summary=c.pin(directory/'compare.json'),
                                support=variant_support(selected, originals, parents, alleles, baseline, audit, c))
    require(sum(v['baseline_alt'] for v in c.read(comparisons['native']['summary']['path'])['strata'].values()) == 829,
            'Frozen829 native ALT census differs')
    aliases = [arm['arm'] for arm in emission['arms'] if arm['canonical_arm'] == selected['canonical_arm']]
    result = dict(schema='context-model-native-observation/1', arm=selected['canonical_arm'], aliases=aliases,
                  emitted=selected['sam'], mapped=c.pin(mapped), parents=64, summaries=summaries,
                  comparisons=comparisons, runtime=runtime, caps=CAPS, stock_controls_unchanged=True,
                  private_query21_status='FAIL_RETAINED_MODEL_A', biological_qualification=False,
                  candidate_promoted=False, scope='Exposed HG002 development; mapping-conditioned matched invariant columns; technical uncertainty only.')
    c.fresh(output/'result.json', result)
    for pin in execution.receipts:
        program.w.evidence.stage(pin, c)
    execution.budget()
    files = [c.pin(p) for p in sorted(output.rglob('*')) if p.is_file()]
    c.fresh(output/'complete.json', dict(schema='context-model-measure-complete/1', complete=True, sources=pins,
            arm=args.arm, admission_id=args.admission_id, emission=c.pin(EMISSION), evidence=evidence,
            stages=execution.receipts, files=files, result=c.pin(output/'result.json'), biological_qualification=False))
    return c.pin(output/'complete.json')


def review(directory, identity):
    directory = Path(directory).resolve()
    audit = load('measurement_review_observer', ROOT/'tools/context_decoder/model_observe_v2.py')
    program = audit.module('measurement_review_program', ROOT/'scripts/context-program.py')
    c = program.c
    pin = c.pin(Path(directory)/'complete.json')
    seal = c.read(pin['path'])
    outer = audit.outer_unit(identity, pin, program)
    require(seal['schema'] == 'context-model-measure-complete/1' and seal['complete'] is True
            and seal['sources'] == source_pins(c) and seal['admission_id'] == identity,
            'Measurement source/admission differs')
    for item in seal['sources']+seal['evidence']+seal['files']:
        c.check(item)
    stages = [program.w.evidence.stage(item, c) for item in seal['stages']]
    require(seal['emission'] == c.pin(EMISSION), 'Measurement consumed different emission')
    result = c.read(seal['result']['path'])
    require(result['parents'] == 64 and result['candidate_promoted'] is False
            and result['private_query21_status'] == 'FAIL_RETAINED_MODEL_A', 'Measurement scope/gates differ')
    require(len(stages) == 19, 'Measurement exact stage census differs')
    declared = c.read(Path(directory)/'inputs.json')
    snapshot = c.read(declared['snapshot']['path'])
    selected = declared['selected']
    tools = snapshot['tools']
    require(result['emitted'] == selected['sam'] and declared['emission'] == seal['emission'], 'Measurement emitted input differs')
    free = c.read(declared['historical_mapping']['path'])
    expected = [['uv', 'run', '--no-sync', 'python', '-m', 'unittest', 'discover', '-s', 'tests', '-p',
                 'test_context_model_measure.py', '-v']]
    expected += [['/usr/bin/ldd', binary['path']] for binary in
                 (tools['dorado'], tools['samtools'], snapshot['pairer'], snapshot['observer'])]
    expected += [[tools['samtools']['path'], 'view', '-b', selected['sam']['path']],
                 [tools['dorado']['path'], 'aligner', tools['index']['path'], stages[5]['raw']['stdout']['path'],
                  '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'],
                 [tools['samtools']['path'], 'view', '-h', stages[6]['raw']['stdout']['path']]]
    require(result['mapped'] == stages[7]['raw']['stdout'], 'Mapped SAM does not bind actual mapper chain')
    for name, left in (('native', snapshot['native']['path']), ('reference_free', free['mapped']['path'])):
        for domain, eligible in sorted(snapshot['eligible'].items()):
            pairs = str(Path(directory)/('pair-'+name+'-'+domain))
            summary = str(Path(directory)/('summary-'+name+'-'+domain))
            expected += [[snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'],
                          '--eligible', eligible['path'], '--left', left, '--right', result['mapped']['path'],
                          '--parents', snapshot['parents']['path'], '--output', pairs],
                         [snapshot['pairer']['path'], 'summarize', '--pairs', pairs, '--selected', 'all', '--output', summary]]
    alleles = str(Path(directory)/'alleles')
    expected += [[snapshot['observer']['path'], 'observe', '--reference', snapshot['reference']['path'],
                  '--vcf', snapshot['truth']['path'], '--confident', snapshot['confident']['path'], '--sam', result['mapped']['path'],
                  '--parents', snapshot['parents']['path'], '--output', alleles]]
    for name, baseline in (('native', snapshot['baseline_observations']),
                           ('reference_free', str(Path(declared['historical_mapping']['path']).parent/'alleles'))):
        expected += [[snapshot['observer']['path'], 'compare', '--baseline', baseline, '--candidate', alleles,
                      '--output', str(Path(directory)/('comparison-'+name))]]
    require([stage['argv'] for stage in stages] == expected, 'Measurement actual native command chain differs')
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    custody(selected['sam']['path'], result['mapped']['path'], parents, c)
    current_files = [c.pin(p) for p in sorted(directory.rglob('*')) if p.is_file() and p != directory/'complete.json']
    require(current_files == seal['files'], 'Measurement exact output file census differs')
    for comparator in result['summaries'].values():
        require(set(comparator) == {'100', '500'}, 'Measurement domain census differs')
        for value in comparator.values():
            require(summary_check(c.read(value['summary']['path'])) == value['checks'], 'Summary projection differs')
    for tool in result['runtime']:
        c.check(tool['binary'])
        for library in tool['libraries']:
            c.check(library)
    return dict(completion=pin, outer=outer, result=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    worker = commands.add_parser('measure')
    worker.add_argument('--arm', choices=('graph', 'reference'), required=True)
    worker.add_argument('--output', type=Path, required=True)
    worker.add_argument('--admission-id', required=True)
    verifier = commands.add_parser('review')
    verifier.add_argument('--output', type=Path, required=True)
    verifier.add_argument('--admission-id', required=True)
    args = parser.parse_args()
    value = dict(completion=measure(args)) if args.command == 'measure' else review(args.output, args.admission_id)
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
