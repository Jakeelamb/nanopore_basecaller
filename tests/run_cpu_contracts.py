#!/usr/bin/env python3
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import traceback
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    ('test_genuine_prefix_handoff.py', 16),
    ('test_prefix_feedback_verifier.py', 26),
)


def main():
    expected_total = sum(expected for _, expected in SUITES)
    summary = dict(scope='test-only-checkout-metadata', expected=expected_total, discovered=0,
                   run=0, failures=0, errors=0, skips=0, status='failed',
                   compiled_source_parity=False, native_acceptance=False)
    try:
        for name in ('bounded_cli', 'qualification', 'joint'):
            path = ROOT / 'tools/prefix_feedback' / (name + '.py')
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)

        suite = unittest.TestSuite()
        for pattern, expected in SUITES:
            tests = unittest.TestLoader().discover(str(ROOT / 'tests'), pattern=pattern)
            count = tests.countTestCases()
            summary['discovered'] += count
            if count != expected:
                raise RuntimeError(f'{pattern} discovered {count} methods, expected {expected}')
            suite.addTests(tests)
        if summary['discovered'] != expected_total:
            raise RuntimeError(f'expected exactly {expected_total} methods')

        handoff = sys.modules['genuine_prefix_handoff']
        verifier = sys.modules['prefix_feedback_verifier']
        with ExitStack() as context:
            context.enter_context(patch.object(handoff, 'F1', ROOT))
            context.enter_context(patch.object(verifier, 'F1', ROOT))
            context.enter_context(patch.object(verifier, 'PREFIX_SCRIPT', ROOT / 'scripts/prefix-feedback.py'))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary.update(run=result.testsRun, failures=len(result.failures),
                       errors=len(result.errors), skips=len(result.skipped))
        if result.wasSuccessful() and result.testsRun == expected_total and not result.skipped:
            summary['status'] = 'passed'
    except Exception as error:
        summary['bootstrap_error'] = str(error)
        traceback.print_exc()
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
