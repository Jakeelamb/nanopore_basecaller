#!/usr/bin/env python3
"""Score one guarded checkpoint after proving native and context-arm identities."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('guarded_subset_observer', ROOT / 'tools/context_decoder/observe.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
w, c = o.w, o.c
SOURCE = c.pin(__file__)
CONTROLLER = ROOT / 'tools/context_decoder/observe_subset_controller.py'
OBSERVER_HASH = '746239cdd1df3ef230c8badd0fc31a4f7839c8784b3b667431ef3358a584bb36'


def validate_grant(args, grant, now=None):
    now = now or datetime.now(timezone.utc)
    required = {'schema','id','phase','source','observer_source','controller','source_inventory_sha256',
                'manifest','output','not_before_utc','expires_utc','maximum_wall_seconds','maximum_output_bytes',
                'memory_bytes','address_space_bytes','swap_bytes','cpu_quota','cgroup'}
    c.require(set(grant) == required and grant['schema'] == 'context-feedback-subset-observation-admission/1', 'Subset admission schema differs')
    c.require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',grant['id']) is not None, 'Unsafe subset identity')
    c.require(grant['source'] == SOURCE and grant['observer_source'] == o.SOURCE
              and o.SOURCE['sha256'] == OBSERVER_HASH and grant['controller'] == c.pin(CONTROLLER)
              and grant['source_inventory_sha256'] == w.inventory_hash(w.sources()), 'Subset source closure differs')
    c.require(grant['phase'] == 'checkpoint' and grant['manifest'] == c.pin(args.manifest)
              and grant['output'] == str(args.output.resolve()) and args.output.resolve().is_relative_to(w.RESULTS), 'Subset input/output grant differs')
    expected = '/user.slice/user-1000.slice/user@1000.service/app.slice/context-feedback-' + grant['id'] + '.service'
    start, end = (datetime.fromisoformat(grant[k]) for k in ('not_before_utc','expires_utc'))
    c.require(grant['cgroup'] == expected and start <= now < end and 0 < (end-start).total_seconds() <= 300
              and 5 < (end-now).total_seconds() <= 300 and 0 < grant['maximum_wall_seconds'] <= 300
              and 0 < grant['cpu_quota'] <= 2 and 0 < grant['memory_bytes'] <= 16*1024**3
              and 0 < grant['address_space_bytes'] <= 24*1024**3 and grant['swap_bytes'] == 0
              and 0 < grant['maximum_output_bytes'] <= 4*1024**3, 'Subset resource grant differs')
    return end


def native_identity(candidate, native, parents):
    c.require(len(parents) == len(set(parents)), 'Duplicate identity parents')
    identities = []
    for path in (candidate,native):
        actual = [row.split('\t')[0] for row in Path(path).read_text().splitlines()
                  if not row.startswith('@') and not int(row.split('\t')[1]) & 0x900]
        c.require(len(actual) == len(parents) and set(actual) == set(parents), 'Identity primary census differs')
    for parent in parents:
        left, right = c.mapped(candidate,parent),c.mapped(native,parent)
        c.require((left['sequence'],left['quality']) == (right['sequence'],right['quality']), 'Reference-free/native molecule SEQ/Q differs')
        identities.append(dict(parent=parent,length=len(left['sequence']),
                          sequence_quality_sha256=hashlib.sha256((left['sequence']+'\0'+left['quality']).encode()).hexdigest()))
    return identities


def context_identity(arms):
    c.require(len(arms) == 3 and {x['arm'] for x in arms} == set(o.ARMS), 'Subset arm census differs')
    indexed = {row['arm']:row for row in arms}
    for row in arms:
        c.check(row['sam'])
    c.require(Path(indexed['final_rerank']['sam']['path']).read_bytes() == Path(indexed['selected']['sam']['path']).read_bytes(),
              'Final-rerank/in-search complete SAM bytes differ')
    return indexed


def run(args, grant):
    w.pg.adopt_orphans()
    seal = o.completed_producer(args.manifest,'prepare','ordinary')
    c.require(seal['schema'] == 'context-feedback-parent-emission/2' and seal['source'] == o.SOURCE
              and seal['complete'] is True and seal['decoder']['phase'] == 'checkpoint', 'Subset emission phase/source differs')
    c.check(seal['controls'])
    decoder = Path(seal['decoder']['execution']['path']).parent
    w.evidence.completed(decoder,'checkpoint',grant['source_inventory_sha256'],c)
    c.require(seal['snapshot'] == c.pin(o.SNAPSHOT) and seal['snapshot']['sha256'] == o.SNAPSHOT_HASH, 'Subset snapshot differs')
    snapshot = c.read(c.check(seal['snapshot'])['path'])
    for key in ('pairer','observer','parents','native','truth','confident','reference'):
        c.check(snapshot[key])
    for item in [*snapshot['eligible'].values(),*snapshot['baseline_observation_pins']]:
        c.check(item)
    for item in snapshot['tools'].values():
        if isinstance(item,dict) and {'path','sha256','size'} <= set(item):
            c.check(item)
    parents = Path(snapshot['parents']['path']).read_text().splitlines()
    c.require(len(parents) == len(set(parents)) == 64, 'Subset parent census differs')
    arms = context_identity(seal['arms'])
    identities = native_identity(arms['reference_free']['sam']['path'],snapshot['native']['path'],parents)
    directory = args.output.resolve()
    directory.mkdir()
    pins = w.sources() + [SOURCE,o.SOURCE,grant['controller']]
    execution = w.Execution(grant,directory,pins)
    c.fresh(directory/'start.json',dict(schema='context-feedback-subset-observation-start/1',source=SOURCE,
            observer_source=o.SOURCE,controller=grant['controller'],grant=grant,manifest=c.pin(args.manifest),
            snapshot=seal['snapshot'],sources=pins))
    c.fresh(directory/'identity.json',dict(schema='context-feedback-subset-identities/1',parents=identities,
            reference_free=arms['reference_free']['sam'],native=snapshot['native'],
            final_rerank=arms['final_rerank']['sam'],selected=arms['selected']['sam'],
            reference_free_native_literal_molecule_identity=True,context_complete_sam_byte_identity=True,
            reuse='Score final_rerank once; selected is its exact input alias. Reference_free reuses the retained native mapping after exact whole-molecule SEQ/Q identity.'))
    def stage(name,argv):
        return execution.stage('subset-'+name,argv)['raw']['stdout']['path']
    tools = snapshot['tools']
    samtools,dorado,index = (tools[key]['path'] for key in ('samtools','dorado','index'))
    bam = stage('sam-to-bam',[samtools,'view','-b',arms['final_rerank']['sam']['path']])
    aligned = stage('align',[dorado,'aligner',index,bam,'--threads','2','--no-sort','--mm2-opts','-x lr:hq -I 16G --eqx -Y'])
    mapped = stage('mapped-sam',[samtools,'view','-h',aligned])
    native_identity(mapped,arms['final_rerank']['sam']['path'],parents)
    for domain,eligible in snapshot['eligible'].items():
        pairs = directory/('pair-native-'+domain)
        stage('pair-native-'+domain,[snapshot['pairer']['path'],'score','--reference',snapshot['reference']['path'],
              '--eligible',eligible['path'],'--left',snapshot['native']['path'],'--right',mapped,
              '--parents',snapshot['parents']['path'],'--output',pairs])
        stage('summary-native-'+domain,[snapshot['pairer']['path'],'summarize','--pairs',pairs,'--selected','all',
              '--output',directory/('summary-native-'+domain)])
    stage('observe',[snapshot['observer']['path'],'observe','--reference',snapshot['reference']['path'],'--vcf',snapshot['truth']['path'],
          '--confident',snapshot['confident']['path'],'--sam',mapped,'--parents',snapshot['parents']['path'],'--output',directory/'alleles'])
    stage('compare',[snapshot['observer']['path'],'compare','--baseline',snapshot['baseline_observations'],
          '--candidate',directory/'alleles','--output',directory/'comparison'])
    for item in snapshot['baseline_observation_pins']:
        c.check(item)
    execution.budget()
    c.fresh(directory/'complete.json',dict(schema='context-feedback-subset-observation/1',complete=True,source=SOURCE,
            observer_source=o.SOURCE,controller=grant['controller'],manifest=c.pin(args.manifest),decoder=seal['decoder'],
            source_inventory_sha256=grant['source_inventory_sha256'],snapshot=seal['snapshot'],identity=c.pin(directory/'identity.json'),
            mapped=c.pin(mapped),stages=execution.receipts,outputs=[c.pin(p) for p in sorted(directory.rglob('*')) if p.is_file()],
            matched_reference_free_metrics='The native pair/summaries are the matched reference-free pair/summaries by identity.json.',
            selected_metrics='The final_rerank pair/summaries are the selected pair/summaries by identity.json.',
            exploratory_development=True,candidate_promoted=False))
    return c.pin(directory/'complete.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--admission',type=Path,required=True)
    parser.add_argument('--worker-intake',type=Path,required=True)
    args = parser.parse_args()
    grant = c.read(args.admission)
    validate_grant(args,grant)
    w.supervisor.worker_intake(args.worker_intake,grant,c)
    w.cgroup_limits(grant)
    print(json.dumps(dict(completion=run(args,grant))))


if __name__ == '__main__':
    main()
