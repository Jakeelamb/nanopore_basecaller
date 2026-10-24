#!/usr/bin/env python3
"""Coordinate native truth preparation and the Rust accuracy scorer."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import benchmark as b

ROOT = b.ROOT
CONFIG = ROOT / 'config/accuracy-v1.json'
AMENDMENT = ROOT / 'config/accuracy-v1.1.json'
REFERENCE = ROOT / 'references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz'
SCORER = ROOT / 'tools/accuracy/target/release/accuracy'


def source_pins():
    paths = [Path(__file__), ROOT / 'scripts/benchmark.py', CONFIG, AMENDMENT, SCORER,
             ROOT / 'tools/accuracy/Cargo.toml', ROOT / 'tools/accuracy/Cargo.lock']
    paths.extend(sorted((ROOT / 'tools/accuracy/src').rglob('*.rs')))
    return [b.pin(path) for path in paths]


def adopt(run, argv):
    """Accept an existing recorder only with complete, matching successful evidence."""
    run = run.resolve()
    names = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt',
             'stdout', 'stderr', 'time.txt')
    b.require(all((run / name).is_file() for name in names), 'Incomplete retained native producer')
    # The recorder uses Bash %q (including $'...' for newlines). Compare its
    # canonical encoding; never execute a retained command file to inspect it.
    encoded = subprocess.check_output(['bash', '-c', 'printf "%q " "$@"; printf "\\n"',
                                       '--', *map(str, argv)], text=True)
    b.require((run / 'command.sh').read_text() == encoded, 'Retained command mismatch')
    b.require((run / 'exit-status.txt').read_text().strip() == '0', 'Retained producer failed')
    b.require(Path((run / 'cwd.txt').read_text().strip()) == ROOT, 'Retained producer cwd mismatch')
    b.require((run / 'start.txt').read_text().strip() and (run / 'end.txt').read_text().strip(), 'Missing native UTC clocks')
    b.require('Elapsed (wall clock)' in (run / 'time.txt').read_text(), 'Missing native resource clock')
    return {'status': 'finished', 'exit': 0, 'argv': argv, 'recorder': str(run),
            'stdout': str(run / 'stdout'), 'pins': [b.pin(run / name) for name in names]}


def frozen(path, value):
    if path.exists():
        b.require(b.read(path) == value, f'Changed immutable accuracy input: {path}')
    else:
        b.write(path, value)


def retain_sources(root, sources, executable=SCORER):
    """Run a retained executable copy so a later build cannot replace the producer."""
    retained, binary = [], None
    for source in sources:
        path = root / 'tool-snapshot' / (source['sha256'] + '-' + Path(source['path']).name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            shutil.copyfile(source['path'], path)
            path.chmod(0o555 if Path(source['path']).resolve() == executable.resolve() else 0o444)
        saved = b.pin(path)
        b.require(all(saved[k] == source[k] for k in ('size', 'sha256')), 'Source changed while retaining tool snapshot')
        retained.append({'source': source, 'retained': saved})
        if Path(source['path']).resolve() == executable.resolve():
            binary = str(path)
    b.require(binary is not None, 'Missing retained scorer executable')
    frozen(root / 'tool-snapshot.json', retained)
    return binary, [item['retained'] for item in retained] + [b.pin(root / 'tool-snapshot.json')]


def checked_stage(root, name, argv, context, execute=True, retry=False):
    return b.stage(root, name, list(map(str, argv)), context, execute=execute, retry=retry,
                   reserve=30 * 1024**3)


def prepare(args):
    root = args.output.resolve()
    b.require(not (root / 'inputs.json').exists(), 'Accuracy inputs already prepared; use retained inputs')
    root.mkdir(parents=True, exist_ok=True)
    assets = b.read(ROOT / 'config/assets.json')
    lock = b.read(ROOT / 'provenance/assets.lock.json')
    b.require(len(assets) == len(lock), 'Acquired lock census mismatch')
    inputs = [b.pin(CONFIG), b.pin(REFERENCE), b.pin(ROOT / 'software/bin/bcftools')]
    producers, truth, exclusions = {}, {}, []
    context = {'accuracy_config': b.digest(CONFIG), 'reference': b.digest(REFERENCE)}
    ref_argv = ['gzip', '-cd', str(REFERENCE.relative_to(ROOT))]
    ref = adopt(args.reference_run, ref_argv) if args.reference_run else checked_stage(root / 'native', 'reference-decode', ref_argv, context)
    producers['reference'] = ref
    inputs.extend(ref['pins'])
    for item in b.read(CONFIG)['reference_error_assets']:
        result = checked_stage(root / 'native', item['name'] + '-fetch', ['curl', '-fL', '--retry', '3', item['url']], context)
        path = Path(result['stdout'])
        b.require(b.digest(path) == item['sha256'], 'Reference exclusion SHA-256 mismatch')
        if 'md5' in item:
            b.require(hashlib.md5(path.read_bytes()).hexdigest() == item['md5'], 'Reference exclusion publisher MD5 mismatch')
        inputs.extend(result['pins'])
        producers[item['name'] + '-fetch'] = result
        if item['name'].endswith('.gz'):
            result = checked_stage(root / 'native', item['name'] + '-decode', ['gzip', '-cd', path], context)
            inputs.extend(result['pins'])
            producers[item['name'] + '-decode'] = result
        exclusions.append(result['stdout'])
    for sample in ('HG002', 'HG005'):
        selected = [a for a in assets if a.get('sample') == sample and a['path'].startswith('truth/')]
        # Sample metadata is not universal in older assets; file paths are explicit.
        if not selected:
            selected = [a for a in assets if a['path'].startswith(f'truth/{sample}/')]
        for asset in selected:
            index = assets.index(asset)
            value = b.pin(ROOT / asset['path'])
            b.require(value['sha256'] == lock[index]['sha256'] and value['size'] == asset['bytes'], 'Truth asset changed')
            inputs.append(value)
        vcf = next(ROOT / a['path'] for a in selected if a['path'].endswith('.vcf.gz'))
        bed = next(ROOT / a['path'] for a in selected if a['path'].endswith('.bed'))
        argv = ['software/bin/bcftools', 'norm', '--check-ref', 'e', '-f', str(REFERENCE.relative_to(ROOT)), '-m', '-any', '-Ov', str(vcf.relative_to(ROOT))]
        supplied = getattr(args, sample.lower() + '_run')
        result = adopt(supplied, argv) if supplied else checked_stage(root / 'native', sample + '-normalize', argv, context)
        producers[sample] = result
        inputs.extend(result['pins'])
        truth[sample] = {'vcf': result['stdout'], 'confident': str(bed)}
    value = {'schema': 1, 'config': b.read(CONFIG), 'reference': ref['stdout'], 'truth': truth,
             'exclusions': exclusions, 'producers': producers, 'pins': inputs}
    value['identity'] = b.identity(value)
    frozen(root / 'inputs.json', value)
    return root / 'inputs.json'


def load_inputs(path):
    value = b.read(path)
    b.require(value['identity'] == b.identity({k: v for k, v in value.items() if k != 'identity'}), 'Changed accuracy inputs')
    b.check_pins(value['pins'])
    return value


def prepare_spans(path, execute=True):
    inputs = load_inputs(path)
    root = path.resolve().parent
    outcomes, pins = {}, [b.pin(path), b.pin(ROOT / 'software/bin/bcftools')]
    for sample in inputs['truth']:
        original = next(ROOT / asset['path'] for asset in b.read(ROOT / 'config/assets.json')
                        if asset['path'].startswith(f'truth/{sample}/') and asset['path'].endswith('.vcf.gz'))
        original_pin = b.pin(original)
        b.require(original_pin in inputs['pins'], 'Original VCF not bound to acquired truth inputs')
        context = {'inputs': inputs['identity'], 'original': original_pin, 'tool': b.pin(ROOT / 'software/bin/bcftools')}
        result = checked_stage(root / 'native', sample + '-original-spans',
                               [ROOT / 'software/bin/bcftools', 'query', '-f', '%CHROM\t%POS0\t%END\n', original],
                               context, execute=execute)
        outcomes[sample] = {'bed': result['stdout'], 'producer': result, 'original': original_pin}
        pins.extend(result['pins'] + [original_pin])
    value = {'status': 'verified', 'inputs_identity': inputs['identity'], 'samples': outcomes, 'pins': pins}
    frozen(root / 'original-spans.json', value)
    return value


def qualify_truth(path, execute=True, analysis_root=None):
    inputs = load_inputs(path)
    root = analysis_root.resolve() if analysis_root else path.resolve().parent
    b.require(root.is_relative_to(ROOT / 'results/accuracy'), 'Analysis belongs under results/accuracy')
    sources = source_pins()
    span_path = path.resolve().parent / 'original-spans.json'
    spans = b.read(span_path)
    b.require(spans['status'] == 'verified' and spans['inputs_identity'] == inputs['identity'], 'Original variant footprints unavailable')
    b.check_pins(spans['pins'])
    binary, retained = retain_sources(root, sources)
    context = {'inputs': inputs['identity'], 'sources': sources, 'retained': retained, 'amendment': b.read(AMENDMENT)}
    frozen(root / 'sources.json', context)
    outputs, pins = {}, sources + retained + spans['pins'] + [b.pin(path), b.pin(root / 'sources.json'), b.pin(span_path)]
    for sample, item in inputs['truth'].items():
        for padding in inputs['config']['padding_and_confidence_erosion_bp']:
            key = f'{sample}-{padding}'
            output = root / 'truth' / key
            b.check_pins(sources + retained)
            argv = [binary, 'truth', '--reference', inputs['reference'], '--vcf', item['vcf'],
                    '--confident', item['confident'], '--sample', sample, '--padding', str(padding), '--output', output]
            argv.extend(['--original-footprints', spans['samples'][sample]['bed']])
            argv.extend(['--spanning-policy', b.read(AMENDMENT)['spanning_policy']])
            for excluded in inputs['exclusions']:
                argv.extend(['--exclusions', excluded])
            result = checked_stage(root / 'stages', key, argv, context, execute=execute)
            generated = [output / 'truth.json', output / 'eligible.bed']
            b.require(all(p.is_file() for p in generated), 'Missing Rust truth outputs')
            pins.extend(result['pins'] + [b.pin(p) for p in generated])
            outputs[key] = {'directory': str(output), 'producer': result, 'diagnostics': b.read(output / 'truth.json')}
    value = {'status': 'verified', 'inputs_identity': inputs['identity'], 'sources': sources,
             'binary': binary, 'amendment': b.read(AMENDMENT), 'truth': outputs, 'pins': pins}
    frozen(root / 'truth-qualified.json', value)
    return value


def score(args, execute):
    inputs = load_inputs(args.inputs)
    root = args.analysis_root.resolve() if args.analysis_root else args.inputs.resolve().parent
    qualified = b.read(root / 'truth-qualified.json')
    b.require(qualified['status'] == 'verified' and qualified['inputs_identity'] == inputs['identity'], 'Truth not qualified')
    b.check_pins(qualified['pins'])
    b.require(source_pins() == qualified['sources'], 'Scoring source changed since truth qualification')
    plan = b.load_plan(args.plan)
    stock = args.plan.resolve().parent
    outcomes = []
    for unit in plan['units']:
        if unit['scope'] != args.scope:
            continue
        observation = b.read(stock / 'units' / unit['id'] / 'observation.json')
        b.require(observation['status'] == 'verified', 'Stock observation unavailable')
        b.require(observation['plan'] == plan['sha256'] and observation['unit'] == unit['id'], 'Foreign stock observation')
        b.require(observation['verifier_sha256'] == b.digest(ROOT / 'scripts/benchmark.py'), 'Stock observation requires the current verifier')
        b.check_pins(observation['pins'])
        receipt_path, receipt = observation_stage(observation, stock / 'units' / unit['id'], 'aligned-decode')
        b.require(receipt['status'] == 'finished', 'Aligned decoder unavailable')
        b.require(receipt['context'] == {'plan': plan['sha256'], 'unit': unit['id']}, 'Foreign aligned decoder context')
        b.check_pins(receipt['pins'])
        sample = unit['asset']['sample']
        for padding in inputs['config']['padding_and_confidence_erosion_bp']:
            key = f'{sample}-{padding}'
            truth = Path(qualified['truth'][key]['directory'])
            output = root / 'scores' / plan['sha256'] / unit['id'] / str(padding)
            context = {'plan': plan['sha256'], 'unit': unit['id'], 'padding': padding,
                       'truth': b.pin(truth / 'eligible.bed'), 'sam': b.pin(receipt['stdout']),
                       'parents': b.pin(unit['ids']), 'sources': qualified['sources']}
            b.check_pins(qualified['sources'])
            argv = [qualified['binary'], 'score', '--reference', inputs['reference'], '--eligible', truth / 'eligible.bed',
                    '--sam', receipt['stdout'], '--parents', unit['ids'], '--output', output,
                    '--min-mapq', str(inputs['config']['min_mapq'])]
            result = checked_stage(root / 'score-stages' / plan['sha256'] / unit['id'], str(padding), argv, context, execute=execute)
            generated = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'observation.json')
            score_data = b.read(output / 'score.json')
            value = {'unit': unit['id'], 'tier': unit['tier'], 'sample': sample, 'padding': padding,
                     'score': score_data, 'producer': result,
                     'pins': result['pins'] + [b.pin(p) for p in generated] + [b.pin(stock / 'units' / unit['id'] / 'observation.json')]}
            # Both ledgers must close on exactly the submitted parent universe.
            import csv
            with (stock / 'units' / unit['id'] / 'parents.tsv').open() as handle:
                native = {r['input_uuid']: int(r['output_children']) for r in csv.DictReader(handle, delimiter='\t')}
            with (output / 'parents.tsv').open() as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))
            # The Rust header is checked here instead of relying on positional fields.
            b.require(rows and 'parent' in rows[0] and 'children' in rows[0], 'Unknown Rust parent ledger schema')
            actual = {r['parent']: int(r['children']) for r in rows}
            b.require(native == actual, 'Rust/native emitted parent ledger mismatch')
            frozen(output / 'observation.json', value)
            outcomes.append(value)
    b.require(outcomes, 'No matching stock units')
    summary = {'status': 'verified', 'plan': plan['sha256'], 'inputs': inputs['identity'], 'scope': args.scope,
               'domain': qualified['amendment']['endpoint'], 'sample_identity': inputs['config']['sample_identity'], 'units': outcomes}
    b.write(root / ('report-' + plan['sha256'] + '-' + args.scope + '.json'), summary)
    return summary


def observation_stage(observation, unit_root, stage):
    """Select the exact producer bound to the verified observation, never a newer file."""
    paths = [Path(item['path']) for item in observation['pins']
             if Path(item['path']).name == 'finish.json'
             and Path(item['path']).parent.parent == unit_root / stage]
    b.require(len(paths) == 1, 'Missing/ambiguous observation-bound decoder receipt')
    path = paths[0]
    receipt = b.read(path)
    expected = b.pin(receipt['stdout'])
    b.require(expected in observation['pins'] and expected in receipt['pins'], 'Decoded SAM is not bound to stock observation')
    return path, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--output', required=True, type=Path)
    for key in ('reference', 'hg002', 'hg005'):
        prep.add_argument('--' + key + '-run', type=Path)
    for action in ('spans', 'truth', 'verify-truth', 'run', 'verify'):
        cli = sub.add_parser(action)
        cli.add_argument('--inputs', required=True, type=Path)
        cli.add_argument('--analysis-root', type=Path)
        if action in ('run', 'verify'):
            cli.add_argument('--plan', required=True, type=Path)
            cli.add_argument('--scope', choices=('smoke', 'full', 'timing'), default='full')
    args = parser.parse_args()
    (ROOT / 'results/stock').mkdir(parents=True, exist_ok=True)
    with (ROOT / 'results/stock/host.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            print(prepare(args))
        elif args.action == 'spans':
            print(json.dumps({'samples': list(prepare_spans(args.inputs)['samples'])}))
        elif args.action in ('truth', 'verify-truth'):
            print(json.dumps({'truth': list(qualify_truth(args.inputs, args.action == 'truth', args.analysis_root)['truth'])}))
        else:
            result = score(args, args.action == 'run')
            print(json.dumps({'status': result['status'], 'observations': len(result['units'])}))


if __name__ == '__main__':
    main()
