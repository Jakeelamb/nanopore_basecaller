# Retained-likelihood frontier

`graph-frontier` emits complete parent candidates from pinned, previously scored hypotheses. This experimental crate has no dependency on `graph_prior` and does not read truth, score tensors, infer signals, map reads, or select a biological winner.

```sh
cargo build --offline --locked --release \
  --manifest-path tools/graph_frontier/Cargo.toml \
  --target-dir tools/graph_frontier/target
tools/graph_frontier/target/release/graph-frontier --help
flock -n /home/jake/Projects/nanopore_basecaller/results/stock/host.lock \
  tools/graph_frontier/target/release/graph-frontier emit \
  --cohort /absolute/development-cohort.json \
  --protocol /absolute/protocol.json \
  --output /absolute/fresh-output
```

Builds and tests also require the shared host lock when run on the research host. Each attempt requires a new output directory. A failure retains partial files and omits `complete.json`. Consumers must require and verify that final seal before using `summary.json`.

## Input contracts

The cohort schema is `graph-frontier-cohort/1`. `role` is `development` or `validation`. `pins` contains `parents`, `native_sam`, `windows`, `decisions`, and `graph_walks`. Each pin has an absolute `path`, byte `size`, and lowercase `sha256`. An optional `producer_receipt` pin can be top level or inside `pins`. Every supplied pin is checked before admission.

`historical_sams` is an optional object with pins named `neutral`, `graph-025`, `graph-050`, and `graph-100`. If supplied, all four are required. Historical parity checks every scored decision even when historical SAMs are absent. The parity report distinguishes decision parity from complete parent sequence and quality parity.

The parent file contains one unique ID per line, in output order, with 1 through 64 IDs. Native SAM records must belong to those parents and provide one primary record per parent with full sequence and quality. Secondary and supplementary records are ignored after parent membership checks. Reverse primary SAM records are converted to original read orientation, including reversed quality. Output SAM records are unmapped in that original orientation. `window.reverse` independently determines how the forward genomic reference becomes a hypothesis.

The importer accepts the retained `graph-prior-window/1`, `hprc-local-paths/1`, and unversioned historical decision formats. It joins query indices and verifies parent IDs, stock substrings, anchors, expanded reference spans, native hypotheses, exact linear-reference hypotheses, finite native likelihoods, and nonoverlapping planned windows. Linear reference is clipped from the saved expanded reference in forward genomic coordinates before reverse complementation. It must have panel membership. Null hypothesis likelihood means impossible. Null native likelihood is rejected.

The CLI accepts generic pinned inputs. Hash equality alone does not prove that the cited producer emitted those inputs. Supplied producer receipts must have `status: finished` and `exit: 0`. The emitter does not bind payloads to that receipt's argv or output seals. `summary.json` labels that gap with `input_custody.producer_output_binding_verified: false`. A qualified coordinator must establish that binding before use. The emitter also does not replay tensor scores, validate the original exporter, or independently compare the saved reference against a FASTA.

## Decision policies

The protocol schema is `graph-frontier-protocol/1`. `policies` is an array of unique `id`, `prior`, `lambda`, `neural_deficit`, and `margin` objects. Priors are `none`, `linear`, or `panel`. All numeric weights must be finite and nonnegative. `neural_deficit: null` allows an unbounded deficit.

Each policy maximizes `L + lambda * prior_presence` over the unchanged hypotheses. Exact ties retain native, then choose the lexical sequence. After argmax, an edit requires a different sequence, the objective margin, and the allowed neural deficit. A rejected winner can mask a feasible runner-up. Diagnostics count those alternatives without changing the rule.

`frontier` optionally contains `enabled`, unique `priors` drawn from `linear` and `panel`, `margin`, and `neural_deficit`. Enabled frontiers union events across every admitted window. Events include zero, crossings of the two within-prior-class likelihood maxima, and each nonnegative objective-margin threshold against native. Every event receives a global policy, as does a midpoint in every representable open interval and a finite point beyond the last event. There is no fixed lambda cap. Open intervals between adjacent floats have no representable interior and receive no numeric policy. Each emitted arm records its actual weights.

This event inventory covers the stated binary-prior family in real arithmetic on retained hypotheses and boundaries. The evaluator preserves literal historical `f64` addition and exact tie comparisons. Very large bonuses can collapse unequal scores within a prior class. Cancellation can change a decision next to an event. Tests retain those counterexamples. `frontier.json` compares each finite terminal sample against a symbolic terminal winner. A mismatch is exposed in that diagnostic and does not establish strength exhaustion. No claim covers arbitrary floating-point lambda values, new hypotheses, or different boundaries. `serde_json` uses `float_roundtrip` so saved decimal likelihoods recover their original `f64` values without widening parity tolerances.

## Output contracts

`summary.json` uses `graph-frontier-batch/1` with `role`, parent count and ordered IDs, `arms`, `artifacts`, top-level `cohort` and `protocol` pins, original `input_pins`, a parity pin, and `complete: true`.

Each arm contains `id`, `prior`, `lambda`, `neural_deficit`, `margin`, `artifact_id`, a SAM pin, `edited_windows`, and `edited_parents`. Identical full parent outputs share an artifact. The artifact identity hashes a deterministic serialization of ordered parent IDs, sequence, and quality with fixed SAM columns. Each unique SAM is written once. Every parent is present, including parents without edits. Exclusions preserve native sequence and quality. Edits use original parent coordinates and replace core quality with `!`, preserving sequence and quality outside cores.

`attempt.json` records the executable pin and source pins embedded at compilation. `parity.json` checks the four old policies. `frontier.json` records events and policy aliases. `decisions.jsonl` records every arm and window. `diagnostics.json` counts exclusions, hypotheses, gates, and masked alternatives. `complete.json` is written last and pins the metadata and unique SAM artifacts. There is no reusable completion until that file exists. After the seal is synced, the CLI prints exactly one JSON item containing `completion: {path, size, sha256}`. A native command recorder can pin that stdout to bind the completed payload to the actual process. Failed emission prints no completion item.

## Checks

Run each command under the shared host lock on the research host.

```sh
cargo fmt --check --manifest-path tools/graph_frontier/Cargo.toml
cargo test --offline --locked --manifest-path tools/graph_frontier/Cargo.toml \
  --target-dir tools/graph_frontier/target
cargo clippy --offline --locked --all-targets \
  --manifest-path tools/graph_frontier/Cargo.toml \
  --target-dir tools/graph_frontier/target -- -D warnings
```

Tests cover ties, deficit rescue, margin boundaries, argmax masking, impossible scores, nonfinite rejection, event coverage against dense scans of randomized small inputs, cancellation, symbolic terminal behavior, reverse linear reference, original-coordinate indels, unchanged quality, excluded fallback, duplicate and missing parents, altered pins, and incomplete attempts. Genuine retained development emission additionally requires exact four-arm decision parity and complete parent sequence and quality parity. Native mapping, complete-input processing, biological accuracy, ALT retention, and performance require separate coordinator evidence.
