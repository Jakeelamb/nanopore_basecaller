"""Recompute retained endpoint fractions from integer counts without tools."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path


def ratio(counts):
    if set(counts) != {'m', 'x', 'i', 'd'} or any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError('Invalid error-count census')
    denominator = sum(counts.values())
    if denominator <= 0:
        raise ValueError('Empty error denominator')
    return Fraction(counts['x']+counts['i']+counts['d'], denominator), denominator


def endpoint(metrics, checks):
    candidate, denominator = ratio(metrics['candidate_counts'])
    left, left_denominator = ratio(metrics['left_counts'])
    if left == 0:
        raise ValueError('Undefined relative reduction')
    reduction = (left-candidate)/left
    expected = ((candidate, metrics['candidate_error_fraction']),
                (left, metrics['left_error_fraction']),
                (reduction, metrics['relative_error_reduction']))
    if not all(math.isclose(float(exact), observed, rel_tol=1e-10, abs_tol=1e-14) for exact,observed in expected):
        raise ValueError('Reported fraction differs from count arithmetic')
    if checks['denominators'] != dict(candidate=denominator, left=left_denominator):
        raise ValueError('Reported denominator differs')
    if checks['one_percent'] != (reduction >= Fraction(1,100)):
        raise ValueError('Reported one-percent gate differs')
    return dict(candidate_error_fraction_exact=str(candidate), relative_reduction_exact=str(reduction),
                candidate_denominator=denominator, left_denominator=left_denominator)


def verify(paths):
    rows = []
    for path in paths:
        audit = json.loads(path.read_text())
        if not audit['complete'] or audit['actual_exec_parent_exit'] != 0:
            raise ValueError('Unaccepted measurement audit')
        for baseline, masks in audit['endpoints'].items():
            for mask, saved in masks.items():
                rows.append(dict(arm=audit['arm'], baseline=baseline, mask=mask,
                                 **endpoint(saved['metrics'], saved['checks'])))
    return dict(complete=True, endpoint_checks=len(rows), rows=rows, scientific_producers=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.audit), sort_keys=True))
