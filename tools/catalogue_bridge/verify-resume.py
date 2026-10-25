#!/usr/bin/env python3
"""Compare a separate admit invocation with its retained successful producer."""
import argparse
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('bridge_receipt_audit', Path(__file__).with_name('verify-receipt.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = audit.contract(args.package, args.receipt)
    before = audit.read(args.before)
    for key in ('transform_completion', 'transform_attempt', 'successful_package'):
        audit.check(before[key])
    transform = Path(before['transform_completion']['path'])
    current_stat = dict(mtime_ns=transform.stat().st_mtime_ns, inode=transform.stat().st_ino)
    audit.require(current_stat == before['transform_complete_stat'], 'Transform completion was rewritten')
    audit.require(evidence['transform']['native_completion'] == before['transform_completion'], 'Different retained transform')
    count = len(list((audit.ROOT / 'logs/compound-frontier').glob('*-transform-*')))
    audit.require(count == before['transform_recorder_count'], 'A transform was invoked again')
    old = Path(before['successful_package']['path']).parent
    new = args.package.resolve()
    old_summary = audit.read(old / 'candidates/summary.json')
    new_summary = audit.read(new / 'candidates/summary.json')
    comparisons = []
    old_arms = {a['id']: a for a in old_summary['arms']}
    audit.require(set(old_arms) == {a['id'] for a in new_summary['arms']}, 'Policy membership differs')
    for arm in new_summary['arms']:
        previous = old_arms[arm['id']]
        audit.check(arm['sam'])
        audit.check(previous['sam'])
        audit.require((arm['sam']['size'], arm['sam']['sha256']) == (previous['sam']['size'], previous['sam']['sha256']),
                      'Resumed complete-parent output differs')
        comparisons.append(dict(policy_id=arm['id'], original=previous['sam'], resumed=arm['sam'], exact_bytes_equal=True))
    for relative in ('cohort.json', 'protocol.json', 'candidates/decisions.jsonl', 'candidates/parity.json'):
        a, b = audit.pin(old / relative), audit.pin(new / relative)
        audit.require((a['size'], a['sha256']) == (b['size'], b['sha256']), 'Resumed content differs ' + relative)
        comparisons.append(dict(relative=relative, original=a, resumed=b, exact_bytes_equal=True))
    result = dict(schema='compound-frontier-resume-proof/1', before=audit.pin(args.before),
                  original_package=before['successful_package'], resumed_package=evidence['package'],
                  retained_transform_completion=before['transform_completion'],
                  transform_completion_stat_unchanged=True, transform_recorder_count_unchanged=True,
                  transform_recorder_count=count, invoked_command='admit', invoked_run=False,
                  actual_raw_receipt_audit=evidence, comparisons=comparisons,
                  source=audit.pin(__file__), auditor_source=audit.pin(Path(__file__).with_name('verify-receipt.py')),
                  complete=True)
    audit.write(args.output, result)
    print(__import__('json').dumps(dict(resume_proof=audit.pin(args.output))))


if __name__ == '__main__':
    main()
