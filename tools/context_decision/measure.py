#!/usr/bin/env python3
"""Measure frozen feasible-decision parent outputs in a separately admitted worker."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('decision_measure_boundary', ROOT/'tools/context_decision/boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
c, w = b.c, b.w
HELPER = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v5/tools/context_decoder/model_measure.py')
helper = b.module('decision_immutable_measure_helpers', HELPER)
SNAPSHOT_HASH = 'f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324'


def source_pins():
    return [*b.sources(), c.pin(__file__), c.pin(ROOT/'tools/context_decision/tests/test_measure.py'), c.pin(HELPER)]


def admission(args):
    value = c.read(args.admission)
    c.require(value['schema'] == 'context-decision-measure-admission/1'
              and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['id']) is not None,
              'Invalid measurement admission')
    c.require(value['sources_sha256'] == b.identity(source_pins()) and value['arm'] == args.arm
              and value['output'] == str(args.output.resolve())
              and value['emission'] == c.pin(args.emission/'execution-complete.json'),
              'Measurement source/arm/input/output admission differs')
    now = datetime.now(timezone.utc)
    start, end = (datetime.fromisoformat(value[key]) for key in ('not_before_utc', 'expires_utc'))
    c.require(start <= now < end and 0 < (end-start).total_seconds() <= 300
              and 5 < (end-now).total_seconds() <= 300 and 0 < value['maximum_wall_seconds'] <= 300,
              'Unbounded or expired mapping admission')
    c.require(value['cpu_quota'] == 2 and value['memory_bytes'] == 16*1024**3
              and value['address_space_bytes'] == 24*1024**3 and value['swap_bytes'] == 0
              and value['maximum_output_bytes'] == 512*1024**2,
              'Mapping resource envelope differs')
    c.require(args.output.resolve().is_relative_to(w.RESULTS) and args.output.resolve() != w.RESULTS,
              'Mapping output outside owned results')
    return value


def inputs(emission_path):
    b.completed(emission_path, 'emit')
    emission = c.read(emission_path/'emission.json')
    c.check(emission['snapshot'])
    c.require(emission['snapshot']['sha256'] == SNAPSHOT_HASH and emission['parents'] == 64
              and emission['ordinary_cases'] == 311 and emission['private_frames_applied'] is False,
              'Frozen emission scope/snapshot differs')
    snapshot = c.read(emission['snapshot']['path'])
    original = b.module('decision_measure_original_observer', b.ORIGINAL/'tools/context_decoder/observe.py')
    c.require(original.ROOT == original.c.ROOT == original.w.ROOT == b.ORIGINAL
              and original.w.inventory_hash(original.w.sources()) == b.ORIGINAL_ID,
              'Original mapper comparator ROOT/source differs')
    c.check(emission['historical_mapping'])
    free = original.completed_producer(emission['historical_mapping']['path'], 'arm', 'ordinary')
    historical = original.completed_producer(free['manifest']['path'], 'prepare', 'ordinary')
    c.require(historical['snapshot'] == emission['snapshot'], 'Historical mapping snapshot differs')
    stages = [original.w.evidence.stage(pin, original.c) for pin in free['stages']]
    old_sam = next(arm['sam'] for arm in historical['arms'] if arm['arm'] == 'reference_free')
    tools = snapshot['tools']
    c.require(stages[0]['argv'] == [tools['samtools']['path'], 'view', '-b', old_sam['path']]
              and stages[1]['argv'] == [tools['dorado']['path'], 'aligner', tools['index']['path'],
                stages[0]['raw']['stdout']['path'], '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y']
              and stages[2]['argv'] == [tools['samtools']['path'], 'view', '-h', stages[1]['raw']['stdout']['path']]
              and free['mapped'] == stages[2]['raw']['stdout'], 'Historical actual mapper chain differs')
    pins = [snapshot[key] for key in ('pairer', 'observer', 'parents', 'native', 'truth', 'confident', 'reference')]
    pins += [*snapshot['eligible'].values(), *tools.values(), *snapshot['baseline_observation_pins'],
             free['mapped'], old_sam]
    for pin in [*pins, *free['outputs']]:
        c.check(pin)
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    c.require(len(parents) == len(set(parents)) == 64 and set(snapshot['eligible']) == {'100', '500'},
              'Parent/domain census differs')
    originals = helper.sam_census(snapshot['native']['path'], parents, c)
    o = b.module("decision_measure_emission_controls", ROOT/"tools/context_decision/observe.py")
    for arm in emission['arms']:
        c.check(arm['sam'])
        observed = helper.sam_census(arm['sam']['path'], parents, c)
        for parent in parents:
            edits = [edit for edit in arm['edits'] if edit['parent'] == parent]
            o.validate_edits(originals[parent]['sequence'], edits)
            seq_q = original.splice(originals[parent]['sequence'], originals[parent]['quality'], edits)
            c.require(seq_q == original.independent_splice(originals[parent]['sequence'], originals[parent]['quality'], edits)
                      == (observed[parent]['sequence'], observed[parent]['quality']), 'Emitted parent reconstruction differs')
        if arm['historical_reference_free_mapping'] is not None:
            c.require(Path(arm['sam']['path']).read_bytes() == Path(old_sam['path']).read_bytes()
                      and arm['historical_reference_free_mapping'] == free['mapped'],
                      'Historical mapping reuse lacks exact SAM byte proof')
    return emission, snapshot, parents, originals, free, pins


def worker(args):
    value = admission(args)
    w.pg.adopt_orphans()
    w.supervisor.worker_intake(args.worker_intake, value, c)
    w.cgroup_limits(value)
    output = args.output.resolve()
    output.mkdir()
    pins = source_pins()
    c.fresh(output/'start.json', dict(schema='context-decision-measure-start/1', sources=pins,
            grant=c.pin(args.admission), emission=c.pin(args.emission/'execution-complete.json'), arm=args.arm))
    execution = w.Execution(value, output, pins)
    controls = execution.stage('decision-measure-controls', ['uv', 'run', '--no-sync', 'python', '-m', 'unittest',
            'discover', '-s', 'tools/context_decision/tests', '-p', 'test_measure.py', '-v'])
    b.unittest_counts(Path(controls['raw']['stderr']['path']).read_text(), 6)
    emission, snapshot, parents, originals, free, evidence = inputs(args.emission)
    selected = next(arm for arm in emission['arms'] if arm['arm'] == args.arm)
    aliases = [arm['arm'] for arm in emission['arms'] if arm['canonical_arm'] == selected['canonical_arm']]
    c.fresh(output/'inputs.json', dict(emission=c.pin(args.emission/'emission.json'), snapshot=emission['snapshot'],
            selected=selected, historical_mapping=emission['historical_mapping'], evidence=evidence))
    runtime = helper.runtime_closure(execution, snapshot, c)

    def stage(name, argv):
        return execution.stage('decision-measure-'+name, argv)['raw']['stdout']['path']

    tools = snapshot['tools']
    if selected['historical_reference_free_mapping'] is None:
        bam = stage('sam-to-bam', [tools['samtools']['path'], 'view', '-b', selected['sam']['path']])
        aligned = stage('align', [tools['dorado']['path'], 'aligner', tools['index']['path'], bam,
                        '--threads', '2', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'])
        mapped = stage('mapped-sam', [tools['samtools']['path'], 'view', '-h', aligned])
    else:
        mapped = selected['historical_reference_free_mapping']['path']
    helper.custody(selected['sam']['path'], mapped, parents, c)
    summaries = {}
    for name, left in (('native', snapshot['native']['path']), ('reference_free', free['mapped']['path'])):
        summaries[name] = {}
        for mask, eligible in sorted(snapshot['eligible'].items()):
            pairs, summary = output/('pair-'+name+'-'+mask), output/('summary-'+name+'-'+mask)
            stage('pair-'+name+'-'+mask, [snapshot['pairer']['path'], 'score', '--reference', snapshot['reference']['path'],
                '--eligible', eligible['path'], '--left', left, '--right', mapped, '--parents', snapshot['parents']['path'], '--output', pairs])
            stage('summary-'+name+'-'+mask, [snapshot['pairer']['path'], 'summarize', '--pairs', pairs,
                                          '--selected', 'all', '--output', summary])
            summaries[name][mask] = dict(summary=c.pin(summary/'summary.json'), checks=helper.summary_check(c.read(summary/'summary.json')))
    alleles = output/'alleles'
    stage('observe', [snapshot['observer']['path'], 'observe', '--reference', snapshot['reference']['path'],
        '--vcf', snapshot['truth']['path'], '--confident', snapshot['confident']['path'], '--sam', mapped,
        '--parents', snapshot['parents']['path'], '--output', alleles])
    comparisons = {}
    for name, baseline in (('native', snapshot['baseline_observations']),
                          ('reference_free', str(Path(emission['historical_mapping']['path']).parent/'alleles'))):
        comparison = output/('comparison-'+name)
        stage('compare-'+name, [snapshot['observer']['path'], 'compare', '--baseline', baseline,
                               '--candidate', alleles, '--output', comparison])
        c.require(c.read(comparison/'compare.json')['parents'] == 64, 'Allele parent census differs')
        comparisons[name] = dict(summary=c.pin(comparison/'compare.json'),
                support=helper.variant_support(selected, originals, parents, alleles, baseline, b, c))
    c.require(sum(v['baseline_alt'] for v in c.read(comparisons['native']['summary']['path'])['strata'].values()) == 829,
              'Frozen829 native ALT census differs')
    result = dict(schema='context-decision-native-measurement/1', arm=args.arm, canonical_arm=selected['canonical_arm'],
        aliases=aliases, emitted=selected['sam'], mapped=c.pin(mapped), parents=64, summaries=summaries,
        comparisons=comparisons, runtime=runtime, stock_controls_unchanged=True, candidate_promoted=False,
        biological_qualification=False, private_diagnostics_required=True,
        scope='Exposed HG002 development; matched invariant columns; technical uncertainty only.')
    c.fresh(output/'result.json', result)
    for pin in execution.receipts:
        w.evidence.stage(pin, c)
    execution.budget()
    files = [c.pin(path) for path in sorted(output.rglob('*')) if path.is_file()]
    c.fresh(output/'complete.json', dict(schema='context-decision-measurement/1', complete=True,
        sources=pins, sources_sha256=b.identity(pins), admission=c.pin(args.admission), arm=args.arm,
        emission=c.pin(args.emission/'execution-complete.json'), stages=execution.receipts,
        files=files, result=c.pin(output/'result.json'), biological_qualification=False))
    return c.pin(output/'complete.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('source-inventory', 'worker'))
    parser.add_argument('--arm', choices=('feasible_escape', 'feasible_partial'))
    parser.add_argument('--emission', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--worker-intake', type=Path)
    args = parser.parse_args()
    if args.command == 'source-inventory':
        pins = source_pins()
        print(json.dumps(dict(sources=pins, sha256=b.identity(pins))))
    else:
        c.require(all(getattr(args, name) is not None for name in ('arm', 'emission', 'output', 'admission', 'worker_intake')),
                  'Explicit external controller/admission/emission required')
        print(json.dumps(dict(completion=worker(args))))


if __name__ == '__main__':
    main()
