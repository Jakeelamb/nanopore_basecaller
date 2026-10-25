"""Bounded native CRC/container/slice-header audit; decode no supporting DNA records."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sample_runtime', HERE / 'sample-runtime.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CPP_SHA = '9e635f75c24fc9d69346eb4ee5c6c913d514811ed123f059db48cbf6d846c59f'
NATIVE_SHA = 'b22163d82c2fbeaee8fa2814d69ad91722ea38938635f0ed6bd37d6218b669ab'
ASSEMBLY = dict(completion=dict(path=str(s.RESULTS / 'sample-native-assemble-3/complete.json'), size=10885,
                sha256='a3351c7a10fc6ed877c2a5dd7d2130ec0f41a38af28e85ce83f5adff85e3c5a5'),
                outer=dict(path=str(HERE / 'run-sample-native-assemble-3/outer-evidence.json'), size=3971,
                sha256='ac2c99ecee1fa7c203d37882ba97adb7bfefda53c0055b53d7660b1c88d12327'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--intake-sha256', required=True)
    args = parser.parse_args()
    unit = s.Unit(args.identity, args.intake, args.intake_sha256)
    s.require(unit.price['phase'] == 'engineering' and unit.price['scientific_work'] is False,
              'Metadata-only native framing audit price required')
    cpp = s.pin(HERE / 'sample-cram-framing-v2.cpp')
    native_pin = s.pin(HERE / 'sample-native-v2.py')
    s.require(cpp['sha256'] == CPP_SHA and native_pin['sha256'] == NATIVE_SHA, 'Reviewed framing/native source differs')
    native = s.load('sample_native_framing_intake', Path(native_pin['path']))
    report = native.take(ASSEMBLY, 'assemble')
    assembly = s.read(report['assembly'])
    inspection = native.p.transport_completion(assembly['inspect'], 'inspect')
    crai = native.p.named(inspection['files'], 'index.crai')
    chunks = unit.directory / 'chunks.tsv'
    for part in assembly['original_parts']:
        s.check(part['payload'])
        s.require(not any(ch.isspace() for ch in part['payload']['path']), 'Chunk path is outside manifest framing')
    s.fresh(chunks, ''.join(f'{part["range"][0]}\t{part["range"][1]}\t{part["payload"]["path"]}\n'
                           for part in assembly['original_parts']))
    sources = [cpp, native_pin, s.pin(HERE / 'sample-assembly-adapter-v1.py'),
               s.pin('/usr/include/htslib/cram.h'), s.pin('/usr/include/htslib/hfile.h'),
               s.pin('/home/jake/Projects/nanopore_basecaller/software/bcftools-1.24/htslib-1.24/cram/cram_io.c'),
               s.pin('/home/jake/Projects/nanopore_basecaller/software/bcftools-1.24/htslib-1.24/cram/cram_index.c')]
    compiler = s.pin('/usr/bin/c++')
    binary = unit.directory / 'sample-cram-framing'
    flags = ['-std=c++23', '-O2', '-DNDEBUG', '-Wall', '-Wextra', '-Wpedantic', '-Wconversion',
             '-Wsign-conversion', '-Wshadow', '-Werror', '-fno-fast-math', '-ffp-contract=off']
    unit.stage('sample-framing-compile', [compiler['path'], *flags, cpp['path'], '-o', binary, '-lhts', '-lz'])
    binary_pin = s.pin(binary)
    observed = unit.stage('sample-framing-metadata', [binary_pin['path'], assembly['header']['path'], crai['path'], chunks])
    result = json.loads(Path(observed['raw']['stdout']['path']).read_text())
    s.require(result['schema'] == 'sample-cram-framing/1' and result['source_DNA_decoded'] is False
              and result['independent_header_crc'] is True and result['crc_mutation_rejected'] is True
              and result['slice_metadata_raw_only'] is True,
              'Native framing/negative-control evidence missing')
    linked = unit.stage('sample-framing-libraries', ['/usr/bin/ldd', binary_pin['path']])
    libraries = []
    for line in Path(linked['raw']['stdout']['path']).read_text().splitlines():
        s.require('not found' not in line, 'Native framing runtime library missing')
        match = re.search(r'(?:=>\s+)?(/\S+)\s+\(', line)
        if match:
            libraries.append(s.pin(match.group(1)))
    s.require(any('libhts.so' in value['path'] for value in libraries), 'Actual native HTSlib closure missing')
    for value in sources + libraries + [compiler, binary_pin, crai, assembly['header']]:
        s.check(value)
    output = unit.directory / 'framing-audit.json'
    s.fresh(output, dict(schema='sample-cram-framing-audit/1', assembly_unit=ASSEMBLY, assembly=report['assembly'],
            header=assembly['header'], crai=crai, chunks=s.pin(chunks), binary=binary_pin, compiler=compiler,
            flags=flags, runtime_libraries=libraries, native_observation=observed['raw']['stdout'],
            result=result, original_header_index_unchanged=True, global_index_shift_applied=False,
            missing_prefix_bytes_synthesized=False, network_requests=0, supporting_DNA_decoded=False,
            source_qualification=False, biological_qualification=False,
            coverage_limits=['retained_header_tail_not_probed', 'cross_chunk_metadata_not_joined',
                             'missing_prefix_counter_is_not_complete_byte_census', 'nonraw_slice_metadata_not_attempted']))
    unit.complete('framing-audit', [s.pin(output), binary_pin, observed['raw']['stdout'], s.pin(chunks)], sources=sources,
                  details=dict(metadata_only=True, source_qualification=False, supporting_DNA_decoded=False,
                               native_header_end=result['native_header_end'], crai_first_container=result['crai_first_container'],
                               derived_header_delta=result['derived_header_delta'], biological_qualification=False))


if __name__ == '__main__':
    main()
