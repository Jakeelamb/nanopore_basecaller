"""Run all-case pricing only from the declared successful 8+3 engineering chain."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
chain = s.load('sample_engineering_chain_v1', HERE / 'sample-engineering-chain-v1.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    parser.add_argument('--chain-sha256', required=True)
    for name in ('qualification', 'outer', 'request'):
        parser.add_argument('--' + name, type=Path, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    s.require(unit.price['phase'] == 'plan' and unit.price['scientific_work'] is True, 'Explicit all-case plan price required')
    validator = s.pin(HERE / 'sample-engineering-chain-v1.py')
    values = {name: s.pin(getattr(args, name)) for name in ('qualification', 'outer', 'request')}
    s.require(validator['sha256'] == args.chain_sha256
              and all(value['sha256'] == getattr(args, name + '_sha256') for name, value in values.items()),
              'Declared continued-engineering intake pins differ')
    closure = chain.continued(values['qualification'], values['outer'])
    stage = unit.stage('sample-all-case-plan', [str(s.UV), 'run', '--no-sync', 'python',
                       s.ROOT / 'tools/sample_context/pipeline.py', 'plan', '--request', args.request,
                       '--request-sha256', args.request_sha256, '--output', unit.directory / 'plan'])
    completion = json.loads(Path(stage['raw']['stdout']['path']).read_text())['completion']
    seal = s.read(completion)
    s.require(seal['schema'] == 'sample-context-pipeline-complete/1' and seal['complete'] is True
              and seal['phase'] == 'plan', 'Actual all-case plan did not complete')
    for value in seal['sources'] + seal['files']:
        s.check(value)
    p = s.load('sample_context_metadata', s.ROOT / 'tools/sample_context/pipeline.py')
    plan_pin = next(value for value in seal['files'] if Path(value['path']).name == 'plan.json')
    plan = p.load_plan(plan_pin)
    inspection = p.transport_completion(plan['inspect'], 'inspect')
    old_price_pin = p.named(inspection['files'], 'price.json')
    old_price = p.read(old_price_pin)
    additional = p.subtract(plan['required_ranges'], old_price['ranges'])
    coverage = [dict(case_id=case['id'], geometry_sha256=case['geometry'],
                    covered_by_old_price=bool(case['required_ranges']) and
                    all(p.covered(interval, old_price['ranges']) for interval in case['required_ranges']))
                for case in plan['cases']]
    s.require(len(coverage) == 368, 'All-case gap census differs')
    proposal = unit.directory / 'old-inspect-comparison.json'
    s.fresh(proposal, dict(schema='sample-context-old-price-comparison/1', plan=plan_pin, inspect=plan['inspect'],
            old_price=old_price_pin, old_encoded_bytes=old_price['bytes'], old_selected_containers=old_price['selected_containers'],
            all_case_encoded_bytes=sum(b-a for a, b in plan['required_ranges']),
            all_case_selected_containers=plan['selected_containers'], additional_complete_container_ranges=additional,
            additional_encoded_bytes=sum(b-a for a, b in additional),
            covered_by_old_price=sum(row['covered_by_old_price'] for row in coverage), cases=coverage,
            new_network_requests=0, reads_decoded=False, biological_qualification=False))
    unit.complete('plan', [completion, plan_pin, s.pin(proposal)], sources=seal['sources'] + [validator],
                  details=dict(qualification_kind='declared_engineering_2_partial_plus_3',
                               qualification=values['qualification'], qualification_outer=values['outer'],
                               runtime_closure=closure, reads_decoded=False, new_network_requests=0))


if __name__ == '__main__':
    main()
