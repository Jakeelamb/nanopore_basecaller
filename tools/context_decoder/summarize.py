#!/usr/bin/env python3
"""Summarize retained guarded decoding and biological observations without rerunning producers."""
import argparse
from collections import Counter, defaultdict
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('guarded_observer', ROOT / 'tools/context_decoder/observe.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
c = o.c


def table(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def phase(directory):
    directory = Path(directory)
    summary = c.read(directory / 'summary.json')
    proof = o.w.evidence.completed(directory, summary['phase'], o.w.inventory_hash(o.w.sources()), c)
    modes = {}
    cores = defaultdict(list)
    for mode in sorted({row['context_mode'] for row in summary['outcomes']}):
        rows = [row for row in summary['outcomes'] if row['context_mode'] == mode]
        changes, gates, caps = Counter(), Counter(), Counter()
        beyond_panel, different = [], []
        for row in rows:
            if 'native' not in row:
                continue
            result = c.read(Path(row['native']['completion']['path']).parent / 'result.json')
            outcome = result['outcome']
            construction = c.read(row['construction']['path'])
            window = construction['original_window']
            changed = [arm for arm in o.ARMS if outcome[arm]['sequence'] != outcome['native']['sequence']]
            cores[mode].append(dict(parent=row['read_id'], query=row['query_index'],contig=window['contig'],
                                    start=window['ref_start']+10,end=window['ref_end']-10,changed=changed))
            for arm in o.ARMS:
                changes[arm] += arm in changed
            gates[outcome['gate']] += 1
            changes['context_winner_differs_from_native'] += outcome['context_winner']['sequence'] != outcome['native']['sequence']
            changes['context_winner_differs_from_free'] += outcome['context_winner']['sequence'] != outcome['reference_free']['sequence']
            changes['partial_search_changed'] += outcome['partial_search_differences'] > 0
            if outcome['selected']['sequence'] != outcome['final_rerank']['sequence']:
                different.append(row['query_index'])
            for name in ('reference_free_escape','conditioned_search'):
                caps[name] += outcome[name]['center_bound_reached']
            base = o.g.frame_fields(row['base_frame']['path'])
            panel = {line.split('\t')[0] for line in Path(base['scalar_controls_path']).read_text().splitlines()}
            binding = result['binding']
            full = binding['left_guard'] + outcome['selected']['sequence'] + binding['right_guard'][:10]
            if 'selected' in changed and full not in panel:
                beyond_panel.append(row['query_index'])
        modes[mode] = dict(statuses=dict(Counter(row['status'] for row in rows)),
                           boundary_reasons=dict(Counter(row['reason'] for row in rows if row['status']=='boundary_excluded')),
                           changes_from_native=dict(changes),gates=dict(gates),center_caps=dict(caps),
                           in_search_vs_final_rerank_queries=different,selected_changed_outside_old_scalar_panel=beyond_panel)
    return dict(proof=proof,summary=c.pin(directory/'summary.json'),inventory=c.pin(directory/'inventory.json'),
                selection=summary['selection'],modes=modes),cores


def observations(directory, cores):
    result = {}
    for arm in ('reference_free','final_rerank'):
        directory_arm = Path(directory)/arm
        seal = o.completed_producer(directory_arm/'complete.json','arm','ordinary')
        for item in seal['outputs']:
            c.check(item)
        for item in seal['stages']:
            o.w.evidence.stage(item,c)
        metrics = {}
        for comparator in ('native','reference_free'):
            for domain in (100,500):
                path = directory_arm/f'summary-{comparator}-{domain}'/'summary.json'
                if path.exists():
                    value = c.read(path)
                    metrics[f'{comparator}_{domain}'] = dict(pin=c.pin(path),matched_refexposure=value['matched_refexposure'],
                        metrics=value['metrics'],parent_bootstrap=value['parent_bootstrap'],
                        genomic_1mb_block_bootstrap=value['genomic_1mb_block_bootstrap'])
        variants = {row['variant']:row for row in table(directory_arm/'alleles/variants.tsv')}
        strata = {}
        for scope in ('all_mutable_centers','actually_edited_centers'):
            local = defaultdict(lambda: dict(observations=0,loss=0,variants=set(),parents=set()))
            for row in table(directory_arm/'comparison/paired.tsv'):
                if row['baseline_alt'] != '1':
                    continue
                variant = variants[row['variant']]
                a,b = int(variant['pos0']),int(variant['pos0'])+len(variant['ref'])
                eligible = [core for core in cores if core['parent']==row['parent'] and core['contig']==variant['contig']
                            and (scope=='all_mutable_centers' or arm in core['changed'])]
                if any(core['start'] <= a and b <= core['end'] for core in eligible):
                    x=local[row['stratum']];x['observations']+=1;x['loss']+=int(row['alt_loss'])
                    x['variants'].add(row['variant']);x['parents'].add(row['parent'])
            strata[scope]={key:dict(observations=value['observations'],loss=value['loss'],
                distinct_variants=len(value['variants']),distinct_parents=len(value['parents'])) for key,value in local.items()}
        result[arm]=dict(completion=c.pin(directory_arm/'complete.json'),outer=c.pin(directory_arm/'execution-complete.json'),
                        metrics=metrics,alt=c.read(directory_arm/'comparison/compare.json'),local_alt=strata)
    return result


def identities(full_emission, private_emissions):
    full=o.completed_producer(Path(full_emission)/'complete.json','prepare','ordinary')
    byarm={row['arm']:row for row in full['arms']}
    a,b=byarm['final_rerank']['sam'],byarm['selected']['sam']
    c.check(a);c.check(b)
    c.require(Path(a['path']).read_bytes()==Path(b['path']).read_bytes(),'Full search/rerank emission differs')
    snapshot=c.read(full['snapshot']['path']);c.check(snapshot['native']);c.check(snapshot['parents'])
    parents=Path(snapshot['parents']['path']).read_text().splitlines()
    native={p:c.mapped(snapshot['native']['path'],p) for p in parents}
    private=[]
    for mode,directory in private_emissions.items():
        seal=o.completed_producer(Path(directory)/'complete.json','prepare',mode)
        for arm in seal['arms']:
            c.check(arm['sam'])
            for parent in parents:
                mapped=c.mapped(arm['sam']['path'],parent)
                c.require((mapped['sequence'],mapped['quality'])==(native[parent]['sequence'],native[parent]['quality']),
                          'Private complete parent differs from native')
            private.append(dict(mode=mode,arm=arm['arm'],sam=arm['sam'],literal_native_parents=len(parents),
                                emission=c.pin(Path(directory)/'complete.json')))
    return dict(full_selected_reuses_final_rerank=dict(final_rerank=a,selected=b,exact_bytes=True,
                newly_mapped_selected=False),private_reuses_native=dict(native=snapshot['native'],arms=private,
                new_mapping_or_truth_scoring=False,interpretation='Literal sequence and quality preservation; no new calling gain or safety generalization.'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('full','first32','private','emission','observations','private_ordinary','private_withheld','output'):
        parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    args=parser.parse_args()
    full,cores=phase(args.full)
    first,_=phase(args.first32)
    private,_=phase(args.private)
    result=dict(schema='guarded-development-report/2',source=c.pin(__file__),full=full,first32=first,private=private,
        observations=observations(args.observations,cores['ordinary']),
        identities=identities(args.emission,dict(ordinary=args.private_ordinary,withheld=args.private_withheld)),
        context_weight=.5,minimum_objective_margin=.5,maximum_signal_deficit=.5,
        promotion_target_relative_reduction=.01,promoted=False,blinded_confirmation=False,
        inference_scope='Offline retained CRF scores; no encoder, exporter or GPU replay; no native streaming integration.')
    c.fresh(args.output,result)
    print(c.pin(args.output))


if __name__=='__main__':
    main()
