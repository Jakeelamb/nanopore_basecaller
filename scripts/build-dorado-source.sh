#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
canonical=$root/software/dorado-src
work=${DORADO_SOURCE_BUILD_WORK:-$root/software/source-build-qualification-20261023}
mkdir -p "$work"
work=$(realpath "$work")
input=$work/source-input-gcc15
build=$work/build-gcc15
cc=$work/toolchain-gcc15/usr/bin/gcc-15
cxx=$work/toolchain-gcc15/usr/bin/g++-15
record=$root/scripts/record-command.sh
jobs=${DORADO_SOURCE_BUILD_JOBS:-6}
[[ "$jobs" =~ ^[1-6]$ ]] || { echo 'Use 1 through 6 build jobs.' >&2; exit 2; }
[[ "$work" != "$canonical" && "$input" != "$canonical" ]] || exit 2

reserve() {
    local available
    available=$(df -B1 --output=avail "$work" | tail -n 1)
    (( available >= 32212254720 + $1 )) || {
        echo "Insufficient free space for the 30 GiB reserve and $1 additional bytes." >&2
        exit 1
    }
}

test "$(git -C "$canonical" rev-parse HEAD)" = 8b8fc5d36a9c0baab262a743cb175b5878e38ca6
test -z "$(git -C "$canonical" status --porcelain=v1 --untracked-files=all)"
test "$(git -C "$canonical" submodule status --recursive | wc -l)" = 22
if git -C "$canonical" submodule status --recursive | rg '^[-+U]'; then exit 1; fi
[[ -x "$cc" && -x "$cxx" ]] || {
    echo 'Extract the pinned GCC 15 packages into toolchain-gcc15 first. See provenance/source-build-20261023.json.' >&2
    exit 1
}
printf '%s  %s\n' fe3eadc0649563d6c5f522af4a3e548a227c833268bc543bc44d548e3970584f "$cc" 7c1ff2182981fb185022a8cdd699abaab64b8ea0965e30855754dd95a6c09d15 "$cxx" | sha256sum -c
if [[ ! -e "$input" ]]; then
    reserve 300000000
    "$record" source-build-copy-input cp -a --reflink=auto "$canonical" "$input"
fi
test "$(git -C "$input" rev-parse HEAD)" = 8b8fc5d36a9c0baab262a743cb175b5878e38ca6
diff <(git -C "$canonical" submodule status --recursive) <(git -C "$input" submodule status --recursive)
declare -A transformations=(
    [dorado/3rdparty/cxxpool]=380da41a4095dd301a372e9018aeb6dfd5326c899b6cce008cbfb67db0a859fa
    [dorado/3rdparty/edlib]=cc559bc05273913d0b039c61cc0cc5a4e249e09060413748518515ddc09658e4
    [dorado/3rdparty/toml11]=49ecb6320c3f22b18c450b95e8d4afaa81a2ba1f0279f0162dad4791b3bcfe40
    [dorado/3rdparty/ont-minimap2/src/3rdparty/minimap2]=d1b82b6133e9295749ef902475594675def7b8ac96859255b16dedd721b5bddd
)
mapfile -t modules < <(git -C "$input" submodule status --recursive | awk '{print $2}')
for module in . "${modules[@]}"; do
    path=$input/$module
    gitdir=$(git -C "$path" rev-parse --absolute-git-dir)
    top=$(git -C "$path" rev-parse --show-toplevel)
    core=$(git -C "$path" config --local --get core.worktree || true)
    [[ "$gitdir" == "$input/.git" || "$gitdir" == "$input/.git/"* ]]
    [[ "$top" == "$input" || "$top" == "$input/"* ]]
    if [[ -n "$core" ]]; then
        test "$(realpath -m "$gitdir/$core")" = "$top"
    fi
    git -C "$path" diff --cached --quiet
    test -z "$(git -C "$path" ls-files --others --exclude-standard)"
    if [[ -v "transformations[$module]" ]]; then
        transform=$(git -C "$path" diff --binary HEAD | sha256sum | cut -d ' ' -f 1)
        [[ "$transform" == e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 || "$transform" == "${transformations[$module]}" ]]
    else
        git -C "$path" diff --ignore-submodules --quiet
    fi
done

mkdir -p "$work/archives" "$work/dependencies" "$work/evidence" "$work/ccache"
while read -r name archive sha url bytes; do
    reserve "$bytes"
    if [[ ! -f "$work/archives/$archive" ]]; then
        "$record" source-build-fetch-dependency curl --fail --location --retry 2 --continue-at - --output "$work/archives/$archive.part" "$url"
        mv "$work/archives/$archive.part" "$work/archives/$archive"
    fi
    # shellcheck disable=SC2016
    "$record" source-build-dependency-pin bash -c 'printf "%s  %s\n" "$1" "$2" | sha256sum -c' -- "$sha" "$work/archives/$archive"
    if [[ ! -d "$work/dependencies/$name" ]]; then
        mkdir "$work/dependencies/$name"
        (cd "$work/dependencies/$name" && "$record" source-build-extract cmake -E tar xf "$work/archives/$archive")
    fi
done <<'PINS'
libkoi-0.7.5-Linux-x86_64-cuda-13.0 libkoi-0.7.5-Linux-x86_64-cuda-13.0.tar.gz 0600a138761b17467bd3a1f8933c6a6a02e17415a9da377f22bc14357c3101ca https://cdn.oxfordnanoportal.com/software/analysis/libkoi-0.7.5-Linux-x86_64-cuda-13.0.tar.gz 260000000
pod5-0.3.39-Linux lib_pod5-0.3.39-linux-x64.tar.gz 7fcf1d9f1da6f1bd13167782e900462fbadb0db57c666911bdba9bbdfd4e7e06 https://github.com/nanoporetech/pod5-file-format/releases/download/0.3.39/lib_pod5-0.3.39-linux-x64.tar.gz 270000000
torch-2.9.0.0-ont-CUDA-13.0-linux-x64-cxx11-abi torch-2.9.0.0-ont-CUDA-13.0-linux-x64-cxx11-abi.zip 8680441dbe3b0990fa7a99a70319affe25bc51f0cd6e105c3e07d522d7355929 https://cdn.oxfordnanoportal.com/software/analysis/torch-2.9.0.0-ont-CUDA-13.0-linux-x64-cxx11-abi.zip 3450000000
flashattention-fa4-v4.0.0.beta10-1-cu13.0-Linux-x86_64 flashattention-fa4-v4.0.0.beta10-1-cu13.0-Linux-x86_64.zip 8be268c386855e342e8881a1ec973daeb5c6e65bb71cc9bc0b814d22dc6485d4 https://cdn.oxfordnanoportal.com/software/analysis/flashattention-fa4-v4.0.0.beta10-1-cu13.0-Linux-x86_64.zip 150000000
openssl-3.5.5-Linux-x86_64 openssl-3.5.5-linux-x86_64.zip 20d7e3caf86368e03f61071c67d152cc3e18865d8b38e369df74ae4c57d1421b https://cdn.oxfordnanoportal.com/software/analysis/openssl-3.5.5-linux-x86_64.zip 50000000
PINS

build_env=(env "CC=$cc" "CXX=$cxx" "CCACHE_DIR=$work/ccache" CCACHE_MAXSIZE=1G CCACHE_COMPILERCHECK=content CUDA_VISIBLE_DEVICES= 'TORCH_CUDA_ARCH_LIST=7.5;8.0;8.6;8.7;9.0')
if [[ ! -f "$build/CMakeCache.txt" ]]; then
    "$record" source-build-configure "${build_env[@]}" uv run cmake -S "$input" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_C_COMPILER=$cc" "-DCMAKE_CXX_COMPILER=$cxx" -DCUDAToolkit_ROOT=/opt/cuda -DCUDA_TOOLKIT_ROOT_DIR=/opt/cuda "-DCMAKE_CUDA_HOST_COMPILER=$cxx" "-DDORADO_3RD_PARTY_DOWNLOAD=$work/dependencies" -DGIT_SUBMODULE=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
fi
test -f "$build/build.ninja"
rg -qxF 'CMAKE_BUILD_TYPE:STRING=Release' "$build/CMakeCache.txt"
rg -qxF "CMAKE_HOME_DIRECTORY:INTERNAL=$input" "$build/CMakeCache.txt"
rg -qxF '#define DORADO_VERSION "2.1.2+8b8fc5d"' "$build/dorado_version/dorado_version.h"
reserve 7516192768
"$record" source-build-compile "${build_env[@]}" uv run cmake --build "$build" --config Release --parallel "$jobs"
for module in "${!transformations[@]}"; do
    test "$(git -C "$input/$module" diff --binary HEAD | sha256sum | cut -d ' ' -f 1)" = "${transformations[$module]}"
done
"$record" source-build-version env CUDA_VISIBLE_DEVICES= "$build/bin/dorado" --version
"$record" source-build-help env CUDA_VISIBLE_DEVICES= "$build/bin/dorado" --help
# shellcheck disable=SC2016
"$record" source-build-ldd bash -c 'set -euo pipefail; libs=$(ldd "$1"); printf "%s\n" "$libs"; [[ "$libs" != *"not found"* ]]' -- "$build/bin/dorado"
"$record" source-build-ctest-inventory ctest --test-dir "$build" --show-only=json-v1
filter='Test generate_*,Test stitch_chunks*,[seq_utils],[TensorUtils],[BasecallModelConfig],[BatchParams],[ModelKits],[ModelMetadata]'
(
    cd "$input"
    "$record" source-build-upstream-test-inventory env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 "$build/tests/dorado_tests" --list-tests --verbosity high
    "$record" source-build-cpu-test-selection env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 "$build/tests/dorado_tests" "$filter" --list-tests --verbosity high
    "$record" source-build-cpu-tests env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 "$build/tests/dorado_tests" "$filter" --reporter junit --out "$work/evidence/cpu-tests.xml"
)
test -z "$(git -C "$canonical" status --porcelain=v1 --untracked-files=all)"
"$record" source-build-final-space du -sb "$work/archives" "$work/dependencies" "$work/source-input-gcc15" "$work/build-gcc15" "$work/toolchain-gcc15" "$work/ccache"
df -B1 "$work"
reserve 0
