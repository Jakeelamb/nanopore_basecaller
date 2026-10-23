# Local graph-prior signal reranker

This HAC-only Rust experiment scores a finite set of local haplotypes against
untouched Dorado F16 transition scores. It writes four complete parent SAMs;
λ=0 is the exact local reranker, and is not a native Koi identity claim.
Native saved-score replay, biological accuracy and performance require separate
runtime evidence.

```sh
cargo build --offline --locked --release --manifest-path tools/graph_prior/Cargo.toml
BIN=tools/graph_prior/target/release/graph-prior
"$BIN" plan --reference reference.fa --sam native.eqx.sam \
  --export export --parents parents.txt --namespace graph-prior-v1/development \
  --output plan
software/graph-prior/graph-resource/gbz-base-source/target/release/hprc-interval-extract \
  graph.gbz plan/queries.tsv graph-context
"$BIN" decode --reference reference.fa --sam native.eqx.sam \
  --export export --parents parents.txt --windows plan/windows.jsonl \
  --graph graph-context/walks.jsonl --output calls
```

The parent file contains up to 64 unique IDs, one per line, without a header.
Both output directories must be new. Queries have four columns, no header:
`GRCh38`, contig, 0-based start, exclusive end. The coordinator owns parent
selection, successful native receipts, input/model/config hashes and export
quota enforcement. This command does not infer export completion from files.

The planner uses primary autosomal alignments with MAPQ 30–254 and native EQX
X/I/D centers. Each core spans exactly 21 reference bases plus two 10-base exact,
gapless anchors. Stock core length differs by at most five bases and is at most
32. Windows are ordered by SHA256(namespace/UUID/contig/core_start), selected
greedily without overlap on each parent and capped at 512. This list freezes
before export-context eligibility; exclusions never trigger replacement.
`diagnostics.json` retains all exclusions and frozen counts.

Dorado `DGS1`, `DGM1` and `DGP1` records are required. The parser admits only
HAC k=4, C=1024 and stride=6; rejects malformed identities, duplicate accepted
chunks, truncated tensors and nonfinite scores; and applies the exported native
clamp. It reproduces move-based native half-overlap stitching and final stride
cropping, then requires reconstructed SEQ/Q/moves to match the exported parent
and normalized primary SAM. A parent mismatch excludes all its edits and keeps
its SAM sequence. An absent/duplicate primary fails because complete parent
output cannot then be established.

A window must lie at least 25 retained bases inside one chunk and consume at
most 256 timesteps. The four bases before its first emission establish the
starting state. All hypotheses consume the same native move-derived timestep
interval and share the final state through their common right anchor.

The full expanded graph reference path must exactly match FASTA. Walks are
trimmed by their CIGAR. Every traversal marked `both_anchors` must have canonical,
exact, gapless stock anchors and fit the core bounds; otherwise the entire
context is excluded. More than 16 distinct complete graph strings also excludes
the context. Incomplete traversals contribute no graph support. Copy counts and
donor frequencies are unused. All graph strings are deduplicated.

H contains stock, all admitted graph strings and every single SNV and one-base
insertion/deletion of the stock core (at most 277 strings). Exact log-sum-exp
stay/step likelihoods use the native transition encoding and blank score.
Each arm maximizes `L(y)+λ*graph_presence(y)`, for λ=0, .25, .5 and 1. Objective
ties prefer stock, then lexical sequence order. An edit requires an objective
margin of at least .5 over stock and likelihood at least stock's likelihood.
Missing or ineligible graph context preserves the parent and records an exclusion.

Outputs are `neutral.sam`, `graph-025.sam`, `graph-050.sam`, `graph-100.sam`,
`decisions.jsonl` and `summary.json`. Each SAM has one unmapped record per
requested ID, in requested order, with SEQ/Q in original signal orientation.
Only admitted cores change. Changed cores get explicit uncalibrated `!` Q;
all other bases keep native Q. Alignment/move auxiliary tags are discarded.
Decisions retain all hypothesis likelihoods, graph presence, margins, score
SHA256 and original parent edit coordinates. Impossible likelihoods are JSON
null. No output modifies the stock controls.

```sh
cargo test --offline --locked --manifest-path tools/graph_prior/Cargo.toml
cargo fmt --manifest-path tools/graph_prior/Cargo.toml --check
cargo clippy --offline --locked --manifest-path tools/graph_prior/Cargo.toml --all-targets -- -D warnings
```

Tests cover exhaustive tiny stay/step path agreement, transition encoding,
private SNV/insertion/deletion escape against wrong graph support, parser
rejection controls, odd overlap and partial-stride retention, forward/reverse
full synthetic pipelines, unchanged/context-unavailable behavior and absence
of edits outside admitted cores. Synthetic fixtures are not native exporter or
biological qualification.
