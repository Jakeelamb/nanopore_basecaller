#!/usr/bin/env python3
"""Admit a development-only saved-score diagnostic and retain exact native receipts."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
REF = Path('/home/jake/Projects/nanopore_basecaller-reference')
LOCK = Path('/home/jake/Projects/nanopore_basecaller/results/stock/host.lock')
CONFIG = ROOT / 'config/private-allele-dev-v1.json'
BINARY = ROOT / 'results/private-allele/target/release/private-allele-challenge'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return dict(path=str(path), size=path.stat().st_size, sha256=h.hexdigest())


def check(value):
    require(pin(value['path']) == value, 'Changed pin ' + value['path'])


def option(argv, key):
    require(argv.count(key) == 1, 'Missing or duplicate option ' + key)
    return argv[argv.index(key) + 1]


def registered_pins(value):
    result = {}
    def collect(item):
        if isinstance(item, dict):
            if {'path', 'size', 'sha256'} <= item.keys():
                result[item['path']] = {k: item[k] for k in ('path', 'size', 'sha256')}
            for child in item.values():
                collect(child)
        elif isinstance(item, list):
            for child in item:
                collect(child)
    collect(value)
    return result


def successful_receipt(path):
    receipt = read(path)
    require(receipt['status'] == 'finished' and receipt['exit'] == 0, 'Incomplete producer')
    raw = Path(receipt['recorder'])
    require(int((raw / 'exit-status.txt').read_text()) == 0, 'Raw producer failed')
    require(shlex.split((raw / 'command.sh').read_text()) == receipt['argv'], 'Raw command mismatch')
    require(receipt['stdout'] == str(raw / 'stdout'), 'Raw stdout mismatch')
    return receipt


def admit():
    protocol = read(CONFIG)
    require(protocol['role'] == 'development' and protocol['sample'] == 'HG002', 'Development only')
    pilot = REF / 'results/graph-prior/pilot-v1'
    dev = pilot / 'development'
    report = REF / 'provenance/verification/graph-prior-v1.json'
    require(pin(report)['sha256'] == protocol['registered_pilot_sha256'], 'Changed registered pilot')
    registered = registered_pins(read(report))
    evidence = [pin(report), pin(CONFIG)]
    artifacts = {}
    for name in ('windows', 'local-decode', 'observe-native', 'graph-context'):
        path = dev / 'artifacts' / (name + '.json')
        require(registered.get(str(path)) == pin(path), 'Artifact lacks registered producer custody')
        value = read(path)
        artifacts[name] = value
        registered.update(registered_pins(value))
        evidence.append(pin(path))
        selected = value['pins'] if name != 'graph-context' else [p for p in value['pins'] if p['path'].endswith('/walks.jsonl')]
        for p in selected:
            check(p)
            evidence.append(p)
    cohort_path = REF / 'results/reference-frontier/decision-v2/development-cohort.json'
    cohort = read(cohort_path)
    require(cohort['role'] == 'development', 'Wrong cohort')
    native_source = dev / 'native.json'
    require(registered.get(str(native_source)) == pin(native_source), 'Native source unregistered')
    registered.update(registered_pins(read(native_source)))
    evidence.append(pin(native_source))
    provenance = {}
    for stage in ('native-sam', 'truth-subset', 'truth-normalize'):
        paths = list((dev / 'stages' / stage).glob('*/finish.json'))
        require(len(paths) == 1 and registered.get(str(paths[0])) == pin(paths[0]), 'Unregistered or ambiguous prerequisite producer ' + stage)
        receipt = successful_receipt(paths[0])
        registered.update(registered_pins(receipt))
        evidence.append(pin(paths[0]))
        provenance[stage] = receipt
    producer_path = Path(cohort['producer_receipt']['path'])
    require(registered.get(str(producer_path)) == pin(producer_path), 'Original score producer unregistered')
    producer = successful_receipt(producer_path)
    require(producer['argv'] == artifacts['local-decode']['argv'], 'Score receipt differs from admitted decoder')
    mapped = option(producer['argv'], '--sam')
    require(mapped == option(artifacts['windows']['argv'], '--sam') == option(artifacts['observe-native']['argv'], '--sam'), 'Observer/planner/score mapped SAM mismatch')
    require(mapped != cohort['pins']['native_sam']['path'], 'Mapped original SAM required')
    inputs_path = REF / 'results/reference-assisted/inputs-native-frozen-v1.json'
    inputs = read(inputs_path)
    require(provenance['truth-subset']['argv'][-1] == inputs['original_truth_vcf']['path'], 'Wrong source truth VCF')
    check(inputs['original_truth_vcf'])
    evidence.append(inputs['original_truth_vcf'])
    require(provenance['truth-normalize']['argv'][-1] == provenance['truth-subset']['stdout'] and provenance['truth-normalize']['stdout'] == option(artifacts['observe-native']['argv'], '--vcf'), 'Truth transform chain differs')
    for key in ('reference', 'confident'):
        require(option(artifacts['observe-native']['argv'], '--' + key) == inputs[key]['path'], 'Frozen observer input differs')
        check(inputs[key])
        evidence.append(inputs[key])
    require(option(artifacts['observe-native']['argv'], '--parents') == cohort['pins']['parents']['path'], 'Parent universe differs')
    check(cohort['pins']['parents'])
    for p in (pin(mapped), cohort['pins']['native_sam'], cohort['pins']['parents'], pin(option(artifacts['observe-native']['argv'], '--vcf'))):
        require(p == registered.get(p['path']), 'Input lacks registered source pin ' + p['path'])
        check(p)
        evidence.append(p)
    observe_receipts = list((dev / 'stages/observe-native').glob('*/finish.json'))
    require(len(observe_receipts) == 1, 'Ambiguous original observer producer')
    observer = successful_receipt(observe_receipts[0])
    require(observer['argv'] == artifacts['observe-native']['argv'], 'Observer command mismatch')
    evidence += [pin(producer_path), pin(observe_receipts[0]), pin(cohort_path), pin(inputs_path)]
    expanded = REF / 'results/reference-frontier/catalogue-v1/full-roundtrip'
    raw = REF / 'logs/20261023T153558Z-frontier-catalogue-full-roundtrip-UnfjQf'
    require(int((raw / 'exit-status.txt').read_text()) == 0, 'Expanded producer failed')
    announcement = read(raw / 'stdout')
    check(announcement['completion'])
    require(announcement['completion']['path'] == str(expanded / 'complete.json') and announcement['partial'] is False, 'Wrong expanded producer completion')
    complete = read(expanded / 'complete.json')
    require(complete['complete'] is True and complete['kind'] == 'full', 'Incomplete expanded catalogue')
    for key in ('decisions', 'receipts', 'summary', 'work_plan'):
        check(complete[key])
        evidence.append(complete[key])
    attempt = read(expanded / 'attempt.json')
    check(attempt['cohort_pin'])
    require(attempt['cohort_pin'] == pin(cohort_path), 'Expanded source cohort differs')
    raw_argv = shlex.split((raw / 'command.sh').read_text())
    start = raw_argv.index(attempt['argv'][0])
    require(raw_argv[start:] == attempt['argv'], 'Expanded raw command mismatch')
    for p in attempt['compiled_source_pins']:
        check(p)
        evidence.append(p)
    evidence += [pin(expanded / 'attempt.json'), announcement['completion']]
    evidence += [pin(p) for p in sorted(raw.iterdir()) if p.is_file()]
    current = Path(protocol['current_bridge_candidates'])
    current_summary = read(current / 'summary.json')
    expected = {arm['id']: arm for arm in current_summary['arms']}
    for key in ('compound-panel-100', 'compound-linear-100'):
        require(expected[key]['lambda'] == 1 and expected[key]['margin'] == 0.5 and expected[key]['neural_deficit'] == 0.5, 'Current policy differs')
    current_complete = read(current / 'complete.json')
    for p in registered_pins(current_complete).values():
        check(p)
        evidence.append(p)
    evidence += [pin(current / name) for name in ('decisions.jsonl', 'summary.json', 'complete.json')]
    flank = Path('/home/jake/Projects/nanopore_basecaller-flank')
    eligibility = flank / 'results/flank-prior/20261023T165826Z-eligibility'
    emission = flank / 'results/flank-prior/20261023T165833Z-emit'
    for directory in (eligibility, emission):
        completion = read(directory / 'complete.json')
        check(completion['summary'])
        execution = read(directory / 'execution-complete.json')
        for p in registered_pins(execution).values():
            check(p)
            evidence.append(p)
        evidence += [pin(directory / name) for name in ('complete.json', 'execution-complete.json', 'summary.json')]
    plans = pin(eligibility / 'plans.jsonl')
    require(read(eligibility / 'summary.json')['plans'] == plans, 'Flank plans differ from qualified producer')
    evidence.append(plans)
    origin = flank / 'tools/flank_prior/src/lib.rs'
    snapshot = ROOT / 'tools/private_allele_challenge/src/flank_snapshot.rs'
    require(pin(origin)['sha256'] == pin(snapshot)['sha256'] == 'f6f5d7564a45ac287d0f4b6abd8c2c25bc4f66bb1f8421d0ace97c0ed3a52f06', 'Flank source snapshot differs from qualified producer')
    evidence.append(pin(origin))
    evidence += [pin(p) for p in sorted((ROOT / 'tools/private_allele_challenge').rglob('*.rs'))]
    evidence += [pin(ROOT / 'tools/graph_frontier/src/decision.rs'), pin(Path(__file__)), pin(BINARY)]
    evidence += [pin(ROOT / 'tools/private_allele_challenge' / name) for name in ('Cargo.toml', 'Cargo.lock')]
    for crate in ('graph_prior', 'accuracy'):
        for path in sorted((ROOT / 'tools' / crate / 'src').glob('*.rs')):
            origin_path = REF / path.relative_to(ROOT)
            require(pin(path)['sha256'] == pin(origin_path)['sha256'], 'Native attachment prerequisite source differs')
            evidence.append(pin(path))
        evidence += [pin(ROOT / 'tools' / crate / name) for name in ('Cargo.toml', 'Cargo.lock')]
    evidence.append(pin(Path(inputs['reference']['path'] + '.fai')))
    frozen_targets = ROOT / 'results/private-allele/actual-v2-flank/output/additional-windows.json'
    selected = {row['source_uuid'] for row in read(frozen_targets)['targets']}
    require(len(selected) == 18 and selected <= set(Path(cohort['pins']['parents']['path']).read_text().splitlines()), 'Additional source-parent membership differs')
    evidence.append(pin(frozen_targets))
    export = dev / 'native-export'
    tensor_paths = set()
    for metadata in sorted(export.glob('*.scores.meta.tsv')):
        fields = dict(line.split('\t', 1) for line in metadata.read_text().splitlines())
        if fields['read_id'] in selected:
            evidence.append(pin(metadata))
            tensor_paths.add(export / fields['score_file'])
    evidence += [pin(export / (parent + '.parent.tsv')) for parent in sorted(selected)]
    evidence += [pin(path) for path in sorted(tensor_paths)]
    experiment = read(pilot / 'experiment.json')
    check(experiment['cohorts']['development']['raw'])
    evidence.append(experiment['cohorts']['development']['raw'])
    for p in experiment['model_pins']:
        check(p)
        evidence.append(p)
    native_receipts = list((dev / 'stages/native-call').glob('*/finish.json'))
    require(len(native_receipts) == 1, 'Ambiguous original exporter')
    successful_receipt(native_receipts[0])
    evidence += [pin(native_receipts[0]), pin(pilot / 'qualification-admission.json'), pin(pilot / 'qualification.json')]
    return dict(schema='private-allele-admission/1', role='development', admissible_candidate=False, mapped_sam=pin(mapped), source_pins=list({p['path']: p for p in evidence}.values()))


def run_native(argv, destination):
    destination.mkdir()
    (destination / 'argv.json').write_text(json.dumps(list(map(str, argv)), indent=2) + '\n')
    (destination / 'start.txt').write_text(datetime.now(timezone.utc).isoformat() + '\n')
    with (destination / 'stdout').open('wb') as stdout, (destination / 'stderr').open('wb') as stderr:
        result = subprocess.run(['/usr/bin/time', '-v', '-o', str(destination / 'time.txt'), *map(str, argv)], stdout=stdout, stderr=stderr, timeout=280)
    (destination / 'exit-status.txt').write_text(str(result.returncode) + '\n')
    (destination / 'end.txt').write_text(datetime.now(timezone.utc).isoformat() + '\n')
    require(result.returncode == 0, 'Native diagnostic failed, retained ' + str(destination))


def bind_followon(work, admission):
    frozen = ROOT / 'results/private-allele/actual-v2-flank/output/additional-windows.json'
    require(read(frozen) == read(work / 'additional-windows.json'), 'Frozen additional-window selection changed')
    pilot = REF / 'results/graph-prior/pilot-v1'
    dev = pilot / 'development'
    receipt_path = next((dev / 'stages/native-call').glob('*/finish.json'))
    receipt = successful_receipt(receipt_path)
    command = list(receipt['argv'])
    export_destination = str(work.parent / 'proposed-unused-native-export')
    command[1] = 'DORADO_GRAPH_EXPORT=' + export_destination
    command[command.index('--read-ids') + 1] = str(work / 'additional-parents.ids')
    source_pins = [p for p in admission['source_pins'] if '/native-export/' in p['path']]
    score_bytes = sum(p['size'] for p in source_pins if p['path'].endswith('.scores'))
    metadata_bytes = sum(p['size'] for p in source_pins if not p['path'].endswith('.scores'))
    attachment = read(work / 'additional-attachment.json')
    value = dict(schema='private-allele-followon-export/1', role='development', admissible_candidate=False,
                 frozen_targets=pin(frozen), targets=pin(work / 'additional-windows.json'), attachment=pin(work / 'additional-attachment.json'),
                 existing_native_exporter_receipt=pin(receipt_path), qualified_exporter=pin(command[2]),
                 original_native_sam=read(dev / 'native.json')['sam'], mapped_sam=admission['mapped_sam'],
                 raw=read(pilot / 'experiment.json')['cohorts']['development']['raw'],
                 source_parent_inventory=read(pilot / 'experiment.json')['cohorts']['development']['inventory'],
                 parent_ids=pin(work / 'additional-parents.ids'), source_pins=source_pins,
                 storage=dict(existing_selected_parent_tensor_bytes=score_bytes, existing_selected_parent_metadata_bytes=metadata_bytes,
                              incremental_raw_acquisition_bytes=0, incremental_neural_tensor_export_bytes=0,
                              new_graph_and_likelihood_output_budget_bytes=1024**3,
                              optional_reexport_estimate_bytes=int(1.25 * (score_bytes + metadata_bytes))),
                 optional_export_command=command, optional_export_authorized=False,
                 attached_targets=attachment['attached_targets'], excluded_targets=attachment['excluded_targets'],
                 new_gpu_required=False, next_step='Extract qualified graph walks for attached targets, score only this new frozen diagnostic cohort with unchanged saved tensor intervals, retain every exclusion. Do not rerun native model.')
    (work / 'followon-export.json').write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT / 'results/private-allele') and not output.exists(), 'Fresh owned output required')
    require(shutil.disk_usage(ROOT).free >= 30 * 1024**3, '30 GiB free floor')
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
        admission = admit()
        output.mkdir()
        (output / 'admission.json').write_text(json.dumps(admission, indent=2) + '\n')
        retained = output / 'retained-sources'
        retained.mkdir()
        retention = []
        for p in admission['source_pins']:
            if '/nanopore_basecaller-private/' in p['path']:
                destination = retained / (p['sha256'] + '-' + Path(p['path']).name)
                shutil.copyfile(p['path'], destination)
                require(pin(destination)['sha256'] == p['sha256'], 'Source retention mismatch')
                retention.append(dict(original=p, retained=pin(destination)))
        (output / 'source-retention.json').write_text(json.dumps(retention, indent=2) + '\n')
        work = output / 'output'
        run_native([BINARY, REF, work], output / 'build-receipt')
        run_native([BINARY, 'infer', work / 'inference.jsonl', work / 'decisions.jsonl'], output / 'infer-receipt')
        run_native([BINARY, 'report', work / 'cases.jsonl', work / 'decisions.jsonl', work / 'report.json'], output / 'report-receipt')
        bind_followon(work, admission)
        for p in admission['source_pins']:
            check(p)
        files = [pin(p) for p in sorted(output.rglob('*')) if p.is_file()]
        require(sum(p['size'] for p in files) <= 1024**3, 'Diagnostic output exceeds 1 GiB')
        (output / 'complete.json').write_text(json.dumps(dict(schema='private-allele-complete/1', complete=True, admission=pin(output / 'admission.json'), files=files), indent=2) + '\n')
        print(json.dumps(dict(output=str(output), report=pin(work / 'report.json'))))


if __name__ == '__main__':
    main()
