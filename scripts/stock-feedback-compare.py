#!/usr/bin/env python3
"""Inventory, plan and report retained evidence; run delegates exact external admission."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/stock_feedback'))
import bounded
import compare

parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=('inventory', 'plan', 'run', 'report'))
parser.add_argument('--config', type=Path)
parser.add_argument('--inputs', type=Path)
parser.add_argument('--plan', type=Path)
parser.add_argument('--request', type=Path)
parser.add_argument('--request-sha256')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.phase == 'run':
    bounded.require(args.request is not None and args.request_sha256, 'fresh exact external request required')
    bounded.supervise(args.request, args.request_sha256, args.output)
else:
    bounded.require(args.config is not None, 'config required')
    config = bounded.read(args.config)
    if args.phase == 'inventory':
        result = compare.inspect(config)
    elif args.phase == 'plan':
        result = compare.plan(config, bounded.read(args.inputs) if args.inputs else [])
    else:
        bounded.require(args.plan is not None, 'frozen plan required')
        result = compare.report(config, bounded.read(args.plan), bounded.read(args.inputs) if args.inputs else [])
    bounded.write(args.output, result)
