#!/usr/bin/env python3
"""Derive a private helper target from retained native compile/link metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys

STOCK = Path('/home/jake/Projects/nanopore_basecaller')
REFERENCE = Path('/home/jake/Projects/nanopore_basecaller-reference')
BUILD = REFERENCE / 'software/graph-prior/build'
NATIVE = REFERENCE / 'software/graph-prior/source'
DEPS = REFERENCE / 'software/graph-prior/dependencies'
COMPILER = STOCK / 'software/source-build-qualification-20261023/toolchain-gcc15/usr/bin/g++-15'
COMPILER_SHA = '7c1ff2182981fb185022a8cdd699abaab64b8ea0965e30855754dd95a6c09d15'
STRICT = ['-Wall', '-Wextra', '-Wpedantic', '-Wconversion', '-Wsign-conversion', '-Wshadow', '-Werror',
          '-fno-fast-math', '-ffp-contract=off']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve(strict=True)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return dict(path=str(path), size=path.stat().st_size, sha256=h.hexdigest())


def cmake_list(name, values):
    require(all(']===]' not in value and '\n' not in value for value in values), 'Unsafe CMake field')
    return 'set(' + name + '\n' + ''.join('  [===[' + value + ']===]\n' for value in values) + ')\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(strict=True), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    entries = json.loads((source / 'source-files.json').read_text())
    paths = [(source / value).resolve(strict=True) for value in entries]
    require(paths and len(paths) == len(set(paths)) and all(p.is_relative_to(source) for p in paths),
            'Invalid owned source census')
    cpp = sorted(p for p in paths if p.suffix in ('.cpp', '.h'))
    actual = sorted(p.resolve() for folder in ('include', 'src', 'tests') for p in (source / folder).rglob('*')
                    if p.is_file() and p.suffix in ('.cpp', '.h'))
    require(cpp == actual, 'Owned C++ census differs')
    compiler = pin(COMPILER)
    require(compiler['sha256'] == COMPILER_SHA, 'Retained compiler drift')
    formatter_path = shutil.which('clang-format')
    require(formatter_path is not None, 'Pinned formatter unavailable')
    formatter = pin(formatter_path)
    commands = json.loads((BUILD / 'compile_commands.json').read_text())
    selected = [row for row in commands if row['file'] == str(NATIVE / 'dorado/basecall/GraphScoreReplay.cpp')]
    require(len(selected) == 1 and selected[0]['directory'] == str(BUILD), 'Retained replay compile entry differs')
    command = shlex.split(selected[0]['command'])
    require(command[0] == str(COMPILER) and command[-2:] == ['-c', selected[0]['file']],
            'Retained compile argv differs')
    options, includes = [], []
    i = 1
    while i < len(command):
        item = command[i]
        if item in ('-o', '-c'):
            require(i + 1 < len(command), 'Missing retained output/source')
            i += 2
        elif item.startswith('-I'):
            path = item[2:] if len(item) > 2 else command[i + 1]
            includes.append(str(Path(path).resolve(strict=True)))
            i += 1 if len(item) > 2 else 2
        elif item == '-isystem':
            require(i + 1 < len(command), 'Missing retained system include')
            includes.append(str(Path(command[i + 1]).resolve(strict=True)))
            i += 2
        else:
            require(item.startswith(('-D', '-O', '-std=', '-f')) or item == '-DNDEBUG',
                    'Unexpected retained compile option: ' + item)
            options.append(item)
            i += 1
    require('-std=c++23' in options and '-DDORADO_CUDA_BUILD=1' in options
            and not any('_GLIBCXX_USE_CXX11_ABI=0' in item for item in options), 'Native language/ABI differs')
    includes += [str(DEPS / 'pod5-0.3.39-Linux/include'), str(NATIVE / 'dorado/basecall'),
                 str(DEPS / 'openssl-3.5.5-Linux-x86_64/include')]
    options += STRICT
    ninja = (BUILD / 'build.ninja').read_text().splitlines()
    begin = [i for i, line in enumerate(ninja) if line.startswith('build bin/dorado_graph_replay: ')]
    require(len(begin) == 1, 'Retained replay link entry differs')
    fields = {}
    for line in ninja[begin[0] + 1:]:
        if not line.startswith('  '):
            break
        key, value = line.strip().split(' = ', 1)
        fields[key] = value
    require({'LINK_LIBRARIES', 'LINK_PATH', 'LINK_FLAGS'} <= fields.keys(), 'Retained link metadata incomplete')
    require(all('$' not in fields[key] for key in ('LINK_LIBRARIES', 'LINK_PATH', 'LINK_FLAGS')),
            'Unexpanded retained Ninja link variable')
    libraries = shlex.split(fields['LINK_PATH']) + shlex.split(fields['LINK_LIBRARIES'])
    native_assets = {BUILD / 'build.ninja', BUILD / 'compile_commands.json', BUILD / 'CMakeCache.txt', COMPILER,
                     Path(sys.executable), Path('/home/jake/.local/bin/uv'),
                     Path(formatter['path']), DEPS / 'pod5-0.3.39-Linux/include/pod5_format/c_api.h',
                     NATIVE / 'dorado/basecall/include/basecall/crf_utils.h',
                     NATIVE / 'dorado/config/include/config/BasecallModelConfig.h',
                     NATIVE / 'dorado/config/include/config/BatchParams.h',
                     NATIVE / 'dorado/torch_utils/include/torch_utils/tensor_utils.h',
                     NATIVE / 'dorado/basecall/decode/Decoder.h',
                     NATIVE / 'dorado/basecall/include/basecall/DecodedChunk.h'}
    native_assets.update(NATIVE / value for value in (
        'dorado/basecall/crf_utils.cpp', 'dorado/basecall/model/CRFModel.cpp',
        'dorado/basecall/decode/CPUDecoder.cpp', 'dorado/basecall/decode/beam_search.cpp',
        'dorado/nn/FLSTMStack.cpp', 'dorado/torch_utils/tensor_utils.cpp',
        'dorado/read_pipeline/nodes/ScalerNode.cpp', 'dorado/read_pipeline/nodes/BasecallerNode.cpp',
        'dorado/data_loader/DataLoader.cpp'))
    converted = []
    for item in libraries:
        if item.startswith('-'):
            converted.append(item)
            for part in item.split(','):
                if part.startswith('/') and Path(part).is_file():
                    native_assets.add(Path(part))
        else:
            path = Path(item) if Path(item).is_absolute() else BUILD / item
            path = path.resolve(strict=True)
            require(path.is_file(), 'Native library is not a file')
            native_assets.add(path)
            converted.append(str(path))
    pod5 = (DEPS / 'pod5-0.3.39-Linux/lib/libpod5_format.so').resolve(strict=True)
    native_assets.add(pod5)
    converted += [str(pod5), '-Wl,-rpath,' + str(pod5.parent)]
    flags = shlex.split(fields['LINK_FLAGS'])
    require(len(flags) == 1 and flags[0].startswith('-Wl,--dependency-file='), 'Unexpected retained linker output flag')
    flags = ['-Wl,--dependency-file=' + str(output / 'native-link.d')]
    own_pins = [pin(path) for path in sorted(paths)]
    native_pins = [pin(path) for path in sorted(native_assets)]
    payload = dict(schema='context-prefix-build/1', compiler=compiler, formatter=formatter,
                   retained_compile_entry=selected[0], compile_options=options,
                   system_include_directories=includes, link_options=flags,
                   link_libraries=converted, sources=own_pins, native_assets=native_pins,
                   native_archives_rebuilt=False, system_libraries_require_runtime_inventory=True)
    (output / 'native-build.json').write_text(json.dumps(payload, indent=2) + '\n')
    header = '#pragma once\n#include <cstdint>\nnamespace prefix_compiled {\nstruct Source { const char* path; const char* sha256; std::uintmax_t size; };\n'
    for name, values in (('sources', own_pins), ('native_assets', native_pins)):
        header += 'inline constexpr Source ' + name + '[] = {\n'
        for value in values:
            header += '{' + json.dumps(value['path']) + ',' + json.dumps(value['sha256']) + ',' + str(value['size']) + '},\n'
        header += '};\n'
    for name, value in dict(root=str(source.parents[1]), compiler_path=compiler['path'], compiler_sha256=compiler['sha256'],
                            formatter_path=formatter['path'], formatter_sha256=formatter['sha256'],
                            compile_flags=shlex.join(options)).items():
        header += 'inline constexpr const char* ' + name + ' = ' + json.dumps(value) + ';\n'
    (output / 'prefix_sources.h').write_text(header + '}\n')
    cmake = cmake_list('PREFIX_NATIVE_OPTIONS', options) + cmake_list('PREFIX_NATIVE_LIBRARIES', converted)
    cmake += cmake_list('PREFIX_NATIVE_SYSTEM_INCLUDES', includes)
    cmake += cmake_list('PREFIX_NATIVE_LINK_OPTIONS', flags) + cmake_list('PREFIX_OWNED_CPP', [str(path) for path in cpp])
    cmake += cmake_list('PREFIX_CLOSURE_FILES', [p['path'] for p in own_pins + native_pins])
    cmake += cmake_list('PREFIX_FORMATTER', [formatter['path']])
    cmake += cmake_list('PREFIX_FORMATTER_SHA256', [formatter['sha256']])
    (output / 'native.cmake').write_text(cmake)


if __name__ == '__main__':
    main()
