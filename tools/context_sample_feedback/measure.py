"""Coordinate unchanged native mapping and paired endpoints for exact emitted SAMs."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sample_measure_boundary', ROOT/'tools/context_sample_feedback/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
c = b.c
HELPER = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v5/tools/context_decoder/model_measure.py')
helper = b.module('sample_unchanged_measure_helpers', HELPER)


def emission(directory, config):
    b.completed(directory, 'emit')
    value = c.read(directory/'emission.json')
    c.check(value['snapshot'])
    c.require(value['snapshot']['sha256'] == config['snapshot_sha256'] and value['parents'] == 64
              and value['ordinary_cases'] == 311 and value['private_frames_applied'] is False, 'Emission snapshot/scope differs')
    snapshot = c.read(value['snapshot']['path'])
    for pin in [snapshot[key] for key in ('parents','native','reference','truth','confident','pairer','observer')]: c.check(pin)
    for pin in [*snapshot['eligible'].values(), *snapshot['tools'].values()]: c.check(pin)
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    originals = helper.sam_census(snapshot['native']['path'], parents, c)
    observer = b.module('sample_measure_original_observer', b.ORIGINAL/'tools/context_decoder/observe.py')
    c.require(observer.ROOT == observer.c.ROOT == observer.w.ROOT == b.ORIGINAL
              and observer.w.inventory_hash(observer.w.sources()) == b.ORIGINAL_ID, 'Original observer ROOT/source differs')
    o = b.module('sample_measure_emission_controls', b.OWNED/'observe.py')
    for arm in value['arms']:
        c.check(arm['sam'])
        parsed = helper.sam_census(arm['sam']['path'], parents, c)
        for parent in parents:
            edits = [edit for edit in arm['edits'] if edit['parent'] == parent]
            o.validate_edits(originals[parent]['sequence'], edits)
            expected = observer.splice(originals[parent]['sequence'], originals[parent]['quality'], edits)
            c.require(expected == observer.independent_splice(originals[parent]['sequence'], originals[parent]['quality'], edits)
                      == (parsed[parent]['sequence'],parsed[parent]['quality']), 'Emitted SEQ/Q reconstruction differs')
    return value, snapshot, parents, originals, observer


def map_arm(args, output, config, execution):
    c.require(args.arm in b.ARMS and len(args.input) >= 1, 'Emission and canonical arm required')
    value, snapshot, parents, _, observer = emission(args.input[0], config)
    selected = next(arm for arm in value['arms'] if arm['arm'] == args.arm)
    c.require(selected['canonical_arm'] == args.arm, 'Map the canonical exact-SAM arm once')
    previous = [b.completed(path, 'map')['mapping'] for path in args.input[1:]]
    c.require(not any(row['emitted']['sha256'] == selected['sam']['sha256'] and row['snapshot'] == value['snapshot'] for row in previous),
              'Successful retained mapping for exact SAM/snapshot must be reused')
    tools = snapshot['tools']
    runtime = helper.runtime_closure(execution, snapshot, c)
    def stage(name, argv): return execution.stage('sample-map-'+name, argv)['raw']['stdout']['path']
    if selected['historical_reference_free_mapping'] is None:
        bam = stage('sam-to-bam', [tools['samtools']['path'], 'view', '-b', selected['sam']['path']])
        aligned = stage('align', [tools['dorado']['path'], 'aligner', tools['index']['path'], bam,
            '--threads','2','--no-sort','--mm2-opts','-x lr:hq -I 16G --eqx -Y'])
        mapped = stage('mapped-sam', [tools['samtools']['path'],'view','-h',aligned])
        reused = False
    else:
        free = observer.completed_producer(value['historical_mapping']['path'], 'arm', 'ordinary')
        historical = observer.completed_producer(free['manifest']['path'], 'prepare', 'ordinary')
        old_sam = next(arm['sam'] for arm in historical['arms'] if arm['arm'] == 'reference_free')
        c.check(old_sam)
        c.require(historical['snapshot'] == value['snapshot'] and Path(old_sam['path']).read_bytes() == Path(selected['sam']['path']).read_bytes()
                  and free['mapped'] == selected['historical_reference_free_mapping'], 'Historical mapping reuse lacks exact SAM/snapshot identity')
        mapped = free['mapped']['path']; reused = True
    helper.custody(selected['sam']['path'], mapped, parents, c)
    alleles = output/'alleles'
    stage('alleles', [snapshot['observer']['path'],'observe','--reference',snapshot['reference']['path'], '--vcf',snapshot['truth']['path'],
        '--confident',snapshot['confident']['path'],'--sam',mapped,'--parents',snapshot['parents']['path'],'--output',alleles])
    result = dict(schema='context-sample-feedback-mapping/1', arm=args.arm, canonical_arm=args.arm, emitted=selected['sam'],
        mapped=c.pin(mapped), snapshot=value['snapshot'], aliases=[arm['arm'] for arm in value['arms'] if arm['canonical_arm'] == args.arm],
        alleles=str(alleles), allele_files=[c.pin(path) for path in sorted(alleles.rglob('*')) if path.is_file()], runtime=runtime,
        exact_historical_mapping_reused=reused, calibration_claim=False, qualification_flags=config['qualification_flags'])
    c.fresh(output/'mapping.json', result)
    return result


def measure_arm(args, output, config, execution):
    c.require(args.arm in b.ARMS and len(args.input) >= 2, 'Emission and mapped units required')
    value, snapshot, parents, originals, _ = emission(args.input[0], config)
    maps = [b.completed(path, 'map')['mapping'] for path in args.input[1:]]
    selected = next(arm for arm in value['arms'] if arm['arm'] == args.arm)
    target = next(row for row in maps if args.arm in row['aliases'])
    nn = next(row for row in maps if 'nn_u' in row['aliases'])
    for row in (target, nn):
        c.require(row['snapshot'] == value['snapshot'], 'Mapped baseline snapshot differs')
        c.check(row['mapped'])
        for pin in row['allele_files']: c.check(pin)
    c.require(target['emitted'] == selected['sam'], 'Actual mapped SAM choice differs')
    def stage(name, argv): return execution.stage('sample-measure-'+name, argv)['raw']['stdout']['path']
    summaries, comparisons = {}, {}
    for name, baseline, baseline_alleles in (('native', snapshot['native']['path'], snapshot['baseline_observations']),
                                            ('nn_u', nn['mapped']['path'], nn['alleles'])):
        summaries[name] = {}
        for mask, eligible in sorted(snapshot['eligible'].items()):
            pairs, summary = output/('pairs-'+name+'-'+mask), output/('summary-'+name+'-'+mask)
            stage('pair-'+name+'-'+mask, [snapshot['pairer']['path'],'score','--reference',snapshot['reference']['path'], '--eligible',eligible['path'],
                '--left',baseline,'--right',target['mapped']['path'],'--parents',snapshot['parents']['path'],'--output',pairs])
            stage('summary-'+name+'-'+mask, [snapshot['pairer']['path'],'summarize','--pairs',pairs,'--selected','all','--output',summary])
            summaries[name][mask] = dict(summary=c.pin(summary/'summary.json'), checks=helper.summary_check(c.read(summary/'summary.json')))
        compared = output/('comparison-'+name)
        stage('compare-'+name, [snapshot['observer']['path'],'compare','--baseline',baseline_alleles,'--candidate',target['alleles'],'--output',compared])
        comparisons[name] = dict(summary=c.pin(compared/'compare.json'), support=helper.variant_support(selected, originals, parents, target['alleles'], baseline_alleles, b, c))
    native_compare = c.read(comparisons['native']['summary']['path'])
    c.require(native_compare['parents'] == 64 and sum(row['baseline_alt'] for row in native_compare['strata'].values()) == 829, 'Native829 ALT/parent census differs')
    result = dict(schema='context-sample-feedback-measurement/1', arm=args.arm, actual_nn_u_baseline=nn['mapped'], actual_native=snapshot['native'],
        summaries=summaries, comparisons=comparisons, parents=64, candidate_promoted=False, qualification_flags=config['qualification_flags'],
        scope='Exposed HG002 development only; technical parent and genomic block uncertainty; added other-read DNA can contain formerly panel-withheld ALT.')
    c.fresh(output/'measurement.json', result)
    return result


def report(args, output, config):
    measured = [path for path in args.input if c.read(path/'complete.json')['phase'] == 'measure']
    observed = [path for path in args.input if c.read(path/'complete.json')['phase'] == 'observe']
    c.require(len(observed) == 1 and len(measured) == len(args.input)-1, 'One complete private/effect observer required')
    observation = b.completed(observed[0], 'observe')
    native = c.read(observation['native'][0]['path'])
    private_pin = next(pin for pin in native['files'] if pin['path'].endswith('/private.tsv'))
    private = b.table(private_pin['path'])
    measurements = [b.completed(path, 'measure')['measurement'] for path in measured]
    c.require({row['arm'] for row in measurements} == set(b.ARMS) and len(measurements) == len(b.ARMS), 'Full arm measurement census required')
    checks = []
    for row in measurements:
        numerical = {}
        for baseline, domains in row['summaries'].items():
            c.require(set(domains) == {'100','500'}, 'Both frozen endpoint domains required')
            numerical[baseline] = all(item['checks']['one_percent'] and all(item['checks']['technical_upper_negative'].values()) for item in domains.values())
        productive = row['comparisons']['native']['support']['adequate_per_class_changed_support']
        counts = row['comparisons']['native']['support']['counts']
        retention = all(counts[category+'_baseline_alt'] == counts[category+'_retained'] for category in ('snv','insertion','deletion'))
        witnesses = [item for item in private if item['domain'] == 'private-withheld' and item['arm'] == row['arm']
                     and item['choice'] == 'accepted' and item['native_call'] == 'alt']
        private_gate = len({(item['case_id'],item['event_id']) for item in witnesses}) == 26 and all(item['call'] == 'alt' for item in witnesses)
        checks.append(dict(arm=row['arm'], endpoint_and_technical_gates=numerical, productive_alt_gate=productive,
            all_native_alt_retained=retention, private26_gate=private_gate, private_rows=len(witnesses), source_independence_gate=False, promotion=False))
    result = dict(schema='context-sample-feedback-report/1', measurements=measurements, checks=checks,
        private_diagnostics=private_pin, source_independence_unproved=True, candidate_promoted=False,
        reason='Source independence remains false regardless of exploratory endpoint results.', qualification_flags=config['qualification_flags'])
    c.fresh(output/'report.json', result)
    return result
