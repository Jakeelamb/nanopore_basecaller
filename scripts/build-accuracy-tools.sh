#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
mkdir -p logs software/bin
archive=software/bcftools-1.24.tar.bz2
expected=8caddc22610ee2851666047c859bb91da0c1e32d0c2ec553db6f153ad130e46f
if [[ ! -f "$archive" ]]; then
  scripts/record-command.sh bcftools-source-download curl -fL --retry 3 \
    https://github.com/samtools/bcftools/releases/download/1.24/bcftools-1.24.tar.bz2 -o "$archive"
fi
actual=$(sha256sum "$archive")
[[ ${actual%% *} == "$expected" ]] || { echo 'Wrong bcftools release bytes' >&2; exit 1; }
[[ ! -e software/bcftools-1.24 ]] || { echo 'Build directory exists; preserve it and use its retained build receipt' >&2; exit 1; }
scripts/record-command.sh bcftools-source-build bash -c '
  set -euo pipefail
  tar -xjf software/bcftools-1.24.tar.bz2 -C software
  cd software/bcftools-1.24
  ./configure --disable-libgsl --disable-perl-filters
  make -j4
  ln -sfn ../bcftools-1.24/bcftools ../bin/bcftools
  ../bin/bcftools --version
'
