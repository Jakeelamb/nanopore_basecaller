#!/usr/bin/env python3
"""Choose one uncertainty window per located prefix and obtain native faidx context."""
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
from pathlib import Path
import sys

import location as loc


def project(anchor, begin, end):
    loc.require(anchor['query_begin'] <= begin < end <= anchor['query_end'], 'Projection crosses CIGAR gap')
    if anchor['reverse']:
        return anchor['reference_end']-(end-anchor['query_begin']), anchor['reference_end']-(begin-anchor['query_begin'])
    return anchor['reference_begin']+begin-anchor['query_begin'], anchor['reference_begin']+end-anchor['query_begin']


def reference_index(reference_path):
    path = Path(str(reference_path)+'.fai')
    loc.require(path.is_file() and not path.is_symlink(), 'Existing regular non-symlink FAI required before faidx')
    return loc.pin(path)


def choose(row, located):
    if located['status'] != 'located':
        return dict(status='abstained', reason=located['status'])
    primary = located['usable_primary']
    emission_rows = [i for i, move in enumerate(row['moves']) if move == '1']
    proposals = []
    for anchor in primary['anchors']:
        for begin in range(max(14, anchor['query_begin']+14), min(len(row['sequence'])-41, anchor['query_end']-40)+1):
            end = begin+20
            row_begin, row_end = emission_rows[begin-10], emission_rows[end+20]
            if row_end-row_begin > 128 or row_end*6+10 > row['horizon']:
                continue
            quality_sum = sum(ord(q)-33 for q in row['quality'][begin:end])
            identity = f"{row['parent']}:{row['horizon']}:{begin}:{end}"
            tie = hashlib.sha256(identity.encode()).hexdigest()
            proposals.append((quality_sum, tie, begin, end, row_begin, row_end, anchor))
    if not proposals:
        return dict(status='abstained', reason='no54base_continuous_anchor_with_admitted_rows_le128')
    _, tie, begin, end, row_begin, row_end, anchor = min(proposals)
    ref_begin, ref_end = project(anchor, begin, end)
    return dict(status='selected', core_begin=begin, core_end=end, row_begin=row_begin, row_end=row_end,
                initial_context=row['sequence'][begin-14:begin-10], contig=primary['contig'],
                reference_begin=ref_begin, reference_end=ref_end, reverse=int(primary['reverse']),
                uncertainty_quality_sum=sum(ord(q)-33 for q in row['quality'][begin:end]),
                tie_sha256=tie, proposal_census=len(proposals), anchor=anchor)


def packet(path, values):
    with Path(path).open('x') as stream:
        stream.write('prefix-feedback-window/1\n')
        for key, value in sorted(values.items()):
            loc.require('\n' not in str(value) and '\t' not in str(value), 'Unsafe packet field')
            stream.write(key+'\t'+str(value)+'\n')
        stream.flush()
        loc.os.fsync(stream.fileno())
    loc.sync_directory(path.parent)


def prepare(args):
    output = args.output.resolve()
    loc.require(output.is_relative_to(loc.ROOT/'results/context-feedback'), 'Output outside owned results')
    output.mkdir()
    w = loc.load('causal_prepare_execution', loc.ROOT/'scripts/context-feedback.py')
    source = loc.sources()+[loc.pin(__file__), loc.pin(Path(__file__).with_name('test_prepare.py')), loc.pin(w.__file__)]
    now = datetime.now(timezone.utc)
    grant = dict(id=args.admission_id, maximum_wall_seconds=280,
                 expires_utc=(now+timedelta(seconds=280)).isoformat(), cpu_quota=2,
                 memory_bytes=4*1024**3, address_space_bytes=8*1024**3, swap_bytes=0,
                 maximum_output_bytes=512*1024**2,
                 cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-'+args.admission_id+'.service')
    loc.fresh(output/'attempt.json', dict(argv=sys.argv, sources=source, grant=grant,
                                         location_complete=loc.pin(args.location/'complete.json')))
    w.cgroup_limits(grant)
    cgroup = Path('/sys/fs/cgroup')/grant['cgroup'].lstrip('/')
    loc.fresh(output/'kernel-limits.json', dict(cgroup=grant['cgroup'], values={name: (cgroup/name).read_text()
        for name in ('cpu.max', 'memory.max', 'memory.swap.max')},
        rlimit_as=loc.resource.getrlimit(loc.resource.RLIMIT_AS),
        rlimit_fsize=loc.resource.getrlimit(loc.resource.RLIMIT_FSIZE),
        service=w.supervisor.show('context-'+args.admission_id+'.service')))
    execution = w.Execution(grant, output, source)
    tests = execution.stage('prefix-feedback-python-controls', ['uv', 'run', '--no-sync', 'python',
        '-m', 'unittest', 'discover', '-s', 'tools/prefix_feedback', '-p', 'test_prepare.py', '-v'])
    controls = Path(tests['raw']['stderr']['path']).read_text()
    loc.require(loc.re.search(r'(?m)^Ran 11 tests in [0-9.]+s$', controls) is not None
                and controls.rstrip().endswith('\nOK') and 'skipped' not in controls.lower(),
                'Preparation requires11 actual tests and zero skips')
    original_observer_path = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v5/tools/context_decoder/model_observe.py')
    loc.require(loc.pin(original_observer_path)['sha256'] == 'd20da3f3ce5581504d659917b0ee1cd6d7fce773a66a437c790a195fa0ae1abf',
                'Read-only original outer auditor changed')
    auditor = loc.load('causal_location_outer_auditor', original_observer_path)
    loc.require(auditor.ROOT == original_observer_path.parents[2], 'Original auditor ROOT differs')
    outer = auditor.outer_unit(args.location.name, loc.pin(args.location/'complete.json'), w)
    completion = loc.read(args.location/'complete.json')
    loc.require(completion['schema'] == 'prefix-location-complete/1' and completion['complete'], 'Unqualified location')
    for item in completion['sources']+completion['files']+[completion['attempt']]:
        loc.check(item)
    for item in completion['stages']:
        w.evidence.stage(item, w.c)
    prefix_manifest = loc.read(args.location/'prefixes.json')
    locations = loc.read(args.location/'locations.json')
    loc.check(prefix_manifest['reference_snapshot'])
    snapshot = loc.read(prefix_manifest['reference_snapshot']['path'])
    reference = snapshot['reference']
    loc.check(reference)
    retained_index = reference_index(reference['path'])
    tools = snapshot['tools']
    loc.check(tools['samtools'])
    indexed = {r['qname']: r for r in locations['locations']}
    plans = []
    for row in prefix_manifest['prefixes']:
        for key in ('native', 'tensor', 'metadata', 'native_complete', 'outer_complete'):
            loc.check(row[key])
        selected = choose(row, indexed[row['qname']])
        plan = dict(qname=row['qname'], horizon=row['horizon'], selection=selected)
        plans.append(plan)
        if selected['status'] != 'selected':
            continue
        region = f"{selected['contig']}:{selected['reference_begin']+1}-{selected['reference_end']}"
        loc.require(reference_index(reference['path']) == retained_index, 'Retained FAI changed before faidx')
        stage = execution.stage('prefix-context-faidx-'+str(row['horizon']),
                                [tools['samtools']['path'], 'faidx', reference['path'], region])
        loc.require(reference_index(reference['path']) == retained_index, 'Retained FAI changed during faidx')
        context = loc.pin(stage['raw']['stdout']['path'])
        fields = dict(parent=row['parent'], qname=row['qname'], horizon=row['horizon'],
                      **{k: selected[k] for k in ('core_begin', 'core_end', 'row_begin', 'row_end', 'initial_context',
                                                'contig', 'reference_begin', 'reference_end', 'reverse')},
                      location_status='located', selection_recipe='quality_min20_then_sha256_tie_v1',
                      context_status='reference_only', native_start='uniform_native_cpu',
                      local_start='condition_on_native4_matched_arms', score_layout='4*next+(previous>>6)',
                      score_clamp='native_cpu_5', padding_selection='exclude_nominal_rows_past_H',
                      reference_sha256=reference['sha256'], snapshot_sha256=loc.SNAPSHOT_SHA)
        fields['reference_index_custody'] = 'individually_pinned_retained_index_no_producer_provenance_claim'
        for key, value in dict(native=row['native'], tensor=row['tensor'], metadata=row['metadata'],
                               prefix_complete=row['native_complete'], location_complete=loc.pin(args.location/'complete.json'),
                               locations=loc.pin(args.location/'locations.json'), reference_context=context,
                               reference_index=retained_index).items():
            for name, item in value.items():
                fields[key+'_'+name] = item
        target = output/('H'+str(row['horizon'])+'.tsv')
        packet(target, fields)
        plan['packet'] = loc.pin(target)
        # Price bounded structures before any decoder. No biological numbers are inferred.
        timesteps = selected['row_end']-selected['row_begin']
        plan['work_price'] = dict(score_values=timesteps*1024, guide_cells=(timesteps+1)*256*22,
                                 guide_double_bytes=(timesteps+1)*256*22*8,
                                 beam_width=64, maximum_center=64, arms=4,
                                 exact_scalar_upper_cell_updates=4*129*timesteps*(10+64+20+1),
                                 hard_rows=128, hard_output_bytes=512*1024**2)
    loc.fresh(output/'plans.json', dict(schema='prefix-feedback-plans/1', plans=plans,
          truth_imported=False, selection_predeclared=True, physical_molecules=1,
          correlated_horizons=2, irreversible_commits=0, streaming_state_continuity=False))
    execution.budget()
    loc.fresh(output/'complete.json', dict(schema='prefix-feedback-prepared/1', complete=True, sources=source,
              attempt=loc.pin(output/'attempt.json'), location_complete=loc.pin(args.location/'complete.json'),
              location_outer=outer, original_auditor=loc.pin(original_observer_path),
              inputs=[reference, retained_index, tools['samtools']],
              reference_index_custody='individually_pinned_retained_index_no_producer_provenance_claim',
              stages=execution.receipts, files=[loc.pin(output/'plans.json'), loc.pin(output/'kernel-limits.json')]+
              [p['packet'] for p in plans if 'packet' in p]))
    print(loc.json.dumps(dict(completion=loc.pin(output/'complete.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--location', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--admission-id', required=True)
    prepare(parser.parse_args())
