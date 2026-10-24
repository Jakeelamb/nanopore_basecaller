#!/usr/bin/env python3
"""Freeze this unit's reviewed handoff pointers and current source pins."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('receipt_audit', Path(__file__).with_name('verify-receipt.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

sources = []
for crate in ('catalogue_bridge', 'graph_prior', 'graph_frontier'):
    for path in sorted((ROOT / 'tools' / crate).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and 'target' not in path.parts:
            sources.append(a.pin(path))
for relative in ('scripts/catalogue-bridge.py', 'tests/test_catalogue_bridge.py',
                 'config/compound-frontier-v1.json', 'research/compound-frontier-bridge.md'):
    sources.append(a.pin(ROOT / relative))
receipts = [
    '20261023T160513Z-release-2acf0b41',
    '20261023T160525Z-transform-e06d8a38', '20261023T160530Z-admit-99de341f',
    '20261023T160549Z-checkpoint-controls-61d0e04b',
    '20261023T160645Z-transform-fe92746d', '20261023T160729Z-admit-8c39ee6e',
    '20261023T160927Z-full-controls-d18c48bb', '20261023T160941Z-final-fmt-8ac0da14',
    '20261023T160945Z-final-rust-test-e9bbaf83', '20261023T160950Z-final-clippy-889037f9',
    '20261023T161607Z-full-receipt-audit-4058a6e8', '20261023T161614Z-resume-admit-c8b72f27',
    '20261023T161745Z-resume-proof-cd6074ad',
]
receipt_pins = []
for name in receipts:
    path = ROOT / 'logs/compound-frontier' / name / 'finish.json'
    value = a.read(path)
    a.require(value['status'] == 'finished' and value['exit'] == 0, 'Unsuccessful evidence receipt')
    for item in value['files'].values():
        a.check(item)
    receipt_pins.append(a.pin(path))
full = ROOT / 'results/compound-frontier/20261023T160645Z-full-b2ea3920/admission'
admission = a.read(full / 'bridge-admission.json')
for item in admission['bridge_producer']['compiled_source_pins']:
    a.check(item)
summary = a.read(full / 'candidates/summary.json')
for arm in summary['arms']:
    a.check(arm['sam'])
reference_paths = [
    'research/compound-frontier-bridge.md',
    'results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/complete.json',
    'results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/bridge-admission.json',
    'results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/cohort.json',
    'results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/protocol.json',
    'results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/candidates/complete.json',
    'results/compound-frontier/full-raw-receipt-audit.json',
    'results/compound-frontier/raw-receipt-controls-v2/summary.json',
    'results/compound-frontier/resumed-admission-v1/complete.json',
    'results/compound-frontier/resume-proof.json',
]
owned_bytes = sum(p.stat().st_size for directory in ('results/compound-frontier', 'logs/compound-frontier')
                  for p in (ROOT / directory).rglob('*') if p.is_file())
free_bytes = shutil.disk_usage(ROOT).free
a.require(owned_bytes < 10 * 1024**3 and free_bytes >= 30 * 1024**3, 'Resource envelope breached')
result = dict(schema='compound-frontier-handoff/1', frozen_utc=datetime.now(timezone.utc).isoformat(),
              verdict='VERIFIED_ENGINEERING_ONLY', biological_admission=False,
              source_base='6a40e6e5ae79019d8ab43f236deb2792c92a3e7e',
              report=a.pin(ROOT / 'research/compound-frontier-bridge.md'), sources=sources,
              compiled_sources=admission['bridge_producer']['compiled_source_pins'],
              binary=admission['bridge_producer']['executable'], prerequisites=admission['prerequisites'],
              evidence=[a.pin(ROOT / p) for p in reference_paths], successful_receipts=receipt_pins,
              candidate_artifacts=summary['artifacts'], owned_bytes=owned_bytes, disk_free_bytes=free_bytes,
              limitations=['Root-hash corruption controls do not exercise deeper native identity guards',
                           'Additional launch/cwd/source/time/stderr checks are a separate retained-artifact audit',
                           'Completion is written last and synced, not rename-atomic',
                           'Independent coordinator review and reference-owner downstream batch admission are separate'])
output = ROOT / 'results/compound-frontier/handoff-evidence.json'
a.write(output, result)
print(json.dumps(dict(handoff=a.pin(output), report=result['report'])))
