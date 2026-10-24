#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
source_path="$root/software/dorado-src/dorado/3rdparty/ont-minimap2/src/3rdparty/minimap2"
expected=3c28777e7e2dcc90f825de1b9f17a89cca7d4452
[[ $(git -C "$source_path" rev-parse HEAD) == "$expected" ]] || { echo 'Wrong minimap2 source revision' >&2; exit 1; }
[[ -z $(git -C "$source_path" status --porcelain) ]] || { echo 'Index producer source has changes' >&2; exit 1; }
mkdir -p software/build software/bin
build=$(mktemp -d "$root/software/build/minimap2-XXXXXX")
scripts/record-command.sh minimap-source-copy bash -o pipefail -c 'git -C "$1" archive HEAD | tar -xf - -C "$2"' -- "$source_path" "$build"
scripts/record-command.sh minimap-build make -C "$build" -j 8
install -m 755 "$build/minimap2" software/bin/minimap2
scripts/record-command.sh minimap-version software/bin/minimap2 --version
