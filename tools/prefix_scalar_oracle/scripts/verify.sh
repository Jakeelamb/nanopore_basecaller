#!/usr/bin/env bash
set -euo pipefail
mode=${1:?edit or final}
out=${2:?absolute fresh external evidence directory}
case "$mode" in edit|final) ;; *) exit 2 ;; esac
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
case "$out" in /*) ;; *) exit 2 ;; esac
case "$out/" in "$root/"*) exit 2 ;; esac
mkdir -- "$out"
cd -- "$root"
export RUSTUP_TOOLCHAIN=nightly-2026-10-25
RUSTC=$(rustup which rustc)
export RUSTC
export CARGO_TARGET_DIR="$out/target"
export CARGO_NET_OFFLINE=true
export CARGO_BUILD_JOBS=1
export RUST_TEST_THREADS=1
export TMPDIR="${TMPDIR:-$out/tmp}"
mkdir -p -- "$TMPDIR"
run() {
    local name=$1
    shift
    date -u +%FT%TZ > "$out/$name.start"
    printf '%q ' "$@" > "$out/$name.argv"
    printf '\n' >> "$out/$name.argv"
    set +e
    "$@" 2>&1 | head -c 1048576 > "$out/$name.log"
    local codes=("${PIPESTATUS[@]}")
    set -e
    printf '%s\n' "${codes[0]}" > "$out/$name.status"
    date -u +%FT%TZ > "$out/$name.end"
    sha256sum -- "$out/$name.log" > "$out/$name.log.sha256"
    if [[ ${codes[0]} != 0 || ${codes[1]} != 0 || $(wc -c < "$out/$name.log") -ge 1048576 ]]; then
        printf 'Failed or output cap reached. Inspect %s\n' "$out/$name.log" >&2
        return 1
    fi
}
run compiler "$RUSTC" -vV
run cargo cargo -vV
run boxington env -u MISE_SHELL -u MISE_CONFIG_FILE mbx setup --status
run blaze-status cargo blaze status
if [[ $mode == edit ]]; then
    run blaze-build cargo blaze build --offline --locked -j 1
    run blaze-test cargo blaze test --offline --locked -j 1 -- --test-threads=1
else
    run check env RUSTC_WORKSPACE_WRAPPER= cargo check --offline --locked -j 1 --all-targets
    run test env RUSTC_WORKSPACE_WRAPPER= cargo test --offline --locked -j 1 -- --test-threads=1
    run clippy env RUSTC_WORKSPACE_WRAPPER= cargo clippy --offline --locked -j 1 --all-targets -- -D warnings
    run fmt cargo fmt --all -- --check
    run release env RUSTC_WORKSPACE_WRAPPER= cargo build --release --offline --locked -j 1
    sha256sum -- "$CARGO_TARGET_DIR/release/prefix-scalar-oracle" > "$out/binary.sha256"
fi
printf '%s\n' "$mode" > "$out/complete"
