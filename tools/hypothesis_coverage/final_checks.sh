#!/usr/bin/env bash
set -eu
export CARGO_BUILD_JOBS=1
export RUSTFLAGS='-C link-arg=-Wl,--threads=1'
cargo fmt --check --manifest-path tools/hypothesis_coverage/Cargo.toml
cargo test --offline --locked --manifest-path tools/hypothesis_coverage/Cargo.toml --target-dir /tmp/hypothesis-coverage-build
cargo clippy --offline --locked --all-targets --manifest-path tools/hypothesis_coverage/Cargo.toml --target-dir /tmp/hypothesis-coverage-build -- -D warnings
cargo build --release --offline --locked --manifest-path tools/hypothesis_coverage/Cargo.toml --target-dir /tmp/hypothesis-coverage-build
cp /tmp/hypothesis-coverage-build/release/hypothesis-coverage logs/hypothesis-coverage/hypothesis-coverage
logs/hypothesis-coverage/hypothesis-coverage config/hypothesis-rank-dev-v1.json results/hypothesis-coverage/final-v1
jq '{score_change_counts_prior_then_absent_present,changed_maxima,changed_winners:[.changed_winners[]|select(.policy=="compound-reference-free")],policies:[.policies[]|del(.parent_inventory)]}' results/hypothesis-coverage/final-v1/result.json
sha256sum config/hypothesis-rank-dev-v1.json tools/hypothesis_coverage/src/main.rs tools/hypothesis_coverage/Cargo.toml tools/hypothesis_coverage/Cargo.lock tools/hypothesis_coverage/run_locked.sh tools/hypothesis_coverage/final_checks.sh tools/graph_frontier/src/decision.rs tools/graph_frontier/src/input.rs logs/hypothesis-coverage/hypothesis-coverage > logs/hypothesis-coverage/final-source-executable-pins.sha256
