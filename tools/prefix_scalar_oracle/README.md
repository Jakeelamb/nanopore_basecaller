# Uniform prefix scalar oracle

Status is SOURCE_PREPARED. Compilation, tests, genuine scoring, and C++ parity have not run.
This independent Rust control leaves the native CLI, production math, and existing conditional tests unchanged.

For a canonical string `y` and exactly the consumed score rows `X`, this tool calls the unchanged Rust fixed-state `ScoreWindow` for each initial state `s=0..255`. It returns `logsumexp(L_s(X,y))-ln(256)`. All rows are consumed. The final state is unconstrained. There is no row normalization, preceding context, right anchor, native SEQ equality, emission alignment, graph cost, or beam rank.

## Runtime contract

The exact invocation is:

```sh
ABS_BINARY score --request ABS_REQUEST.json --request-sha256 LOWERCASE_SHA256 --output ABS_FRESH_DIR
```

The request must be an absolute canonical file. Its externally supplied hash freezes the full request bytes. The output directory must not exist. The parent must exist. Failures return a nonzero exit status. Failed output directories are retained and cannot be reused.

`src/contract.rs` is the authoritative request shape. JSON structs reject unknown fields, including nested fields and receipt fields. Duplicate fields also reject. Required top-level fields are:

- `schema` is `prefix-scalar-request/1`. `prior` is exactly `uniform-all-states`.
- `state_length`, `stride`, and `channels` are exactly 4, 6, and 1024. `chunk_index` is exactly 0. `read_id` is a lowercase canonical UUID.
- `tensor` and `metadata` are original DGS and DGM FilePins. Each FilePin has exactly `path`, `size`, and `sha256`. The original tensor filename must be `TOKEN_sSLOT.scores`, as required by the unchanged parser. Released filenames are never passed to that parser.
- `original_header` is the complete original DGS header string, including LF. The DGM must agree on UUID, chunk, token, offset, T, C, filename, and signal geometry. Native SEQ, Q, and MOVES are not used as conditions.
- `row_begin` is 0. `row_end` is 1 through 2048. `chunk_row_begin` and `chunk_row_end` describe the same number of rows in the original tensor. Original T is at most 8192. This rejects unsupported geometry without truncation.
- `selection_receipt` and `query_receipt` are opaque FilePins for Root's frozen selection and candidate evidence. The tool checks their bytes and retains their identity. It does not parse or qualify their scientific conclusions. Root must choose actual H and the lexical-first distinct candidate from an actual native batch before comparison.
- `segments` contains one through four ordered `Segment` objects. Each has `binding` and `release_receipt`. `Binding` is the exact native block object without `release_receipt`; its fields are listed in `src/contract.rs`. Session rows begin at zero, block indices begin at zero, and both session and original rows are contiguous. Each release has at most 512 rows. No gaps, reorder, refill, or shortening is allowed.
- `queries` contains one through eight objects with unique nonempty ASCII-graphic `id` and exact canonical `sequence`. Each sequence is at most 512 bases. Empty sequences are allowed. Queries longer than the consumed interval return `impossible`.

The native `prefix-release/1` receipt must bind the original DGS, DGM, exact release FilePin, and every endpoint. The recipe is `floor(i*T/4),i=0..4,first-retained-chunk-only`. The qualification string is `static-export-geometry-only-no-acquisition-clock`. The tool checks the declared recipe identity and consumed intervals; it does not independently derive retained ownership or validate a selection policy. Root must preserve that upstream evidence. Signal endpoints must agree with DGM `input_offset`, `raw_chunk_size`, and `signal_samples`.

Each released header must equal the original header byte-for-byte except for T, which becomes its row count. This binds stay, clamp, all decoder options, token, slot, and offset. Each payload must equal the corresponding original binary16 row bytes. Concatenated release payloads must equal the complete original consumed interval. Float agreement alone cannot pass this check. The unchanged parser loads the pinned original and applies its existing clamp and finite-value rules. FilePins establish file custody only; they do not establish producer biology.

## Outputs and source identity

`request.json` copies the exact request bytes. `scores.json` retains the typed request, request pin, exact sequence strings and sequence hashes, scalar interpretation, ordered per-initial-state scores, payload hashes, compiler identity, executable FilePin, and compiled source pins. Finite scores have 18 significant decimal digits and all 64 bits as 16 hexadecimal digits. Impossible scores have the explicit status `impossible`. JSON never represents NaN or infinity as a number.

`complete.json` is written last and pins the request copy, scores file, original request, and executable. Every output uses exclusive creation. Consumers must require completion and verify its pins. A complete scalar output does not establish C++ parity or biological accuracy.

`build.rs` pins every adapter compilation source, the lockfile, manifest, toolchain file, and unchanged vendored files. It records the actual nightly compiler path, binary hash, and `rustc -vV` output. Runtime verifies those source bytes. The source root must remain available at its compile-time absolute path. Cargo.lock retains the original graph_prior registry versions; anyhow supplies errors, serde supplies typed boundary parsing, serde_json supplies JSON, and sha2 supplies file custody hashes. No dependency has been fetched or resolved for this prepared unit.

## Deferred verification

Root must first issue a bounded host/build/runtime grant. This script does not acquire the host lock or grant execution authority. Under that grant, run from this repository with a fresh external absolute directory for each invocation:

```sh
tools/prefix_scalar_oracle/scripts/verify.sh edit /tmp/prefix-oracle-edit-ATTEMPT
tools/prefix_scalar_oracle/scripts/verify.sh final /tmp/prefix-oracle-final-ATTEMPT
```

The edit loop uses explicit Blaze build and test commands through the Mr Boxington Cargo shim. Final check, test, clippy, and release commands set `RUSTC_WORKSPACE_WRAPPER=` and keep Mr Boxington active. Both modes select `nightly-2026-10-25`, offline locked Cargo, one job, and one test thread. Target and synthetic fixtures live outside tracked source. Each command records argv, UTC start/end, raw combined output, exit status, and log hash. Output is capped at 1 MiB per command; reaching the cap fails the script. Root's maintained execution wrapper supplies host limits and custody. The script is not a resource supervisor.

The prepared synthetic controls check analytic empty and impossible boundaries, zero-score binomial path counts, and a state-dependent k4 mixture that separates a deliberately fixed-state control using the frozen tolerance. CLI fixtures check query identity, completion pins, overwrite refusal, request-hash corruption, unknown truth/genotype fields, a resealed prior mismatch, unsupported geometry, release corruption, resealed payload/header/interval mismatches, and gaps or reordered releases. These tests have not run. The upstream conditional API and tests remain unchanged.

The eventual C++ comparison must use `abs_error <= 1e-8 + 1e-10*max(abs(L_cpp),abs(L_rust))`. Impossible statuses must agree. Different reduction order does not require bit equality. Do not widen this tolerance after observing values. The planned genuine interval is original rows 0 through 1988, split into four releases of 497. This task has not opened those scientific bodies, produced genuine values, or claimed parity.
