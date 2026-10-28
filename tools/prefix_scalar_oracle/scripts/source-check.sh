#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd -- "$root"
printf '%s\n' \
    '3171343d81477d4d967e300466e9ba3e3d770164f34438dcedd0867ca5ea8a99  vendor/crf.rs' \
    '2122831be9c1fad80e953268cf2138909665f703b697b5f803604b9450f0fa2e  vendor/scores.rs' | sha256sum --check
rustfmt +nightly-2026-10-25 --edition 2021 --check build.rs src/main.rs src/lib.rs tests/controls.rs
bash -n scripts/verify.sh scripts/source-check.sh
while IFS= read -r file; do
    set +e
    diagnostic=$(git diff --no-index --check -- /dev/null "$file" 2>&1)
    code=$?
    set -e
    if [[ $code -gt 1 || -n $diagnostic ]]; then
        printf '%s\n' "$diagnostic" >&2
        exit 1
    fi
done < <(rg --files --hidden -g '!target/**' -g '!.git/**')
