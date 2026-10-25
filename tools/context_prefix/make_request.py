#!/usr/bin/env python3
"""Bind the exploratory q0 prefix request to immutable upstream custody and native assets."""
import argparse
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-v4/scripts/context-program.py')
UPSTREAM_SOURCE = '695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa'
STOCK = Path('/home/jake/Projects/nanopore_basecaller')
REFERENCE = Path('/home/jake/Projects/nanopore_basecaller-reference')
UUID = '7214d805-8331-49aa-af61-478be074d7a6'


def write(path, text):
    with path.open('x') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--prepared-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('prefix_original_v4_auditor', UPSTREAM)
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    c = upstream.c
    c.require(upstream.ROOT == UPSTREAM.parent.parent and Path(upstream.__file__).resolve() == UPSTREAM
              and upstream.identity(upstream.sources()) == UPSTREAM_SOURCE, 'Original upstream source-location identity differs')
    outer = c.pin(args.prepared)
    c.require(outer['sha256'] == args.prepared_sha256 and args.prepared.name == 'execution-complete.json',
              'Upstream prepared execution pin differs')
    proof = upstream.completed(args.prepared.parent, 'prepare')
    c.require(proof['outer'] == outer and proof['summary']['scope'] == 'all', 'Genuine full retained preparation required')
    packet = proof['summary']['prepared']
    manifest = c.read(packet['manifest']['path'])
    inference = c.read(manifest['inference']['path'])
    cases = [value['case'] for value in inference['cases'] if value['case']['case_id'] == 'ordinary/0/ordinary']
    c.require(len(cases) == 1 and cases[0]['parent'] == UUID, 'Exploratory original query0 identity differs')
    pod5 = STOCK / 'data/raw/HG002/PAW70337/PAW70337_66b2eea5_de8117b1_33.pod5'
    model = STOCK / 'models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0'
    allowlist = REFERENCE / 'results/graph-prior/pilot-v1/development/parents.ids'
    producer = REFERENCE / 'results/graph-prior/pilot-v1/development/artifacts/native-call.json'
    native = c.read(producer)
    argv = native['argv']
    c.require(argv.count('basecaller') == 1, 'Retained native basecaller verb differs')
    verb = argv.index('basecaller')
    c.require(verb > 0 and argv[verb - 1] == str(REFERENCE / 'software/graph-prior/build/bin/dorado')
              and argv[verb + 1:verb + 3] == [str(model), str(pod5)]
              and argv.count('--read-ids') == 1 and argv[argv.index('--read-ids') + 1] == str(allowlist),
              'Retained native caller input tuple differs')
    ids = allowlist.read_text().splitlines()
    c.require(len(ids) == len(set(ids)) == 64 and UUID in ids, 'Original cohort allowlist differs')
    output = args.output.resolve()
    c.require(output.is_relative_to(ROOT / 'results/context-feedback') and output != ROOT / 'results/context-feedback',
              'Request output outside owned results')
    output.mkdir(parents=True)
    files = sorted(path for path in model.iterdir() if path.is_file() and (path.name == 'config.toml' or path.suffix == '.tensor'))
    model_pins = [c.pin(path) for path in files]
    c.require(len(files) > 2 and any(path.name == 'config.toml' for path in files), 'Model file census incomplete')
    model_manifest = output / 'model-manifest.tsv'
    write(model_manifest, 'context-prefix-model/1\n' + ''.join(path.name + '\t' + str(value['size']) + '\t' + value['sha256'] + '\n'
                                                            for path, value in zip(files, model_pins, strict=True)))
    pins = dict(pod5=c.pin(pod5), allowlist=c.pin(allowlist), model_manifest=c.pin(model_manifest), native_producer=c.pin(producer))
    values = dict(role='exploratory_development', uuid=UUID, acquisition_id='de8117b1abf27d6d4ac91526772636b9a5ca7fde',
                  model_path=str(model.resolve()), horizons='4096,12288', lookahead='0', front_trim='10', pore_policy='disabled',
                  device='cpu', input_dtype='float32_from_native_half', score_dtype='float32', threads='2')
    for name, value in pins.items():
        for key in ('path', 'size', 'sha256'):
            values[name + '_' + key] = str(value[key])
    request = output / 'request.tsv'
    c.require(all(not any(ch in value for ch in '\t\r\n') for value in values.values()), 'Request separator in value')
    write(request, 'context-prefix-request/1\n' + ''.join(key + '\t' + value + '\n' for key, value in sorted(values.items())))
    provenance = dict(schema='context-prefix-request-custody/1', exploratory_development=True, independent_confirmation=False,
                      original_query0=cases[0], upstream=proof['outer'], upstream_inference=manifest['inference'],
                      upstream_auditor=c.pin(UPSTREAM), upstream_source_inventory_sha256=UPSTREAM_SOURCE,
                      generator=c.pin(__file__), native_inputs=pins, model_files=model_pins, request=c.pin(request),
                      horizons=[4096, 12288], lookahead=0, no_open_pore_variant=True,
                      inference_uses_no_oracle_sequences=True, stock_cuda_parity=False)
    write(output / 'custody.json', json.dumps(provenance, indent=2) + '\n')
    for value in [*pins.values(), *model_pins, outer]:
        c.check(value)
    write(output / 'complete.json', json.dumps(dict(schema='context-prefix-request-complete/1', complete=True,
          files=[c.pin(request), c.pin(model_manifest), c.pin(output / 'custody.json')], request=c.pin(request),
          original_prepared=outer, generator=c.pin(__file__)), indent=2) + '\n')
    print(json.dumps(dict(completion=c.pin(output / 'complete.json'), request=c.pin(request))))


if __name__ == '__main__':
    main()
