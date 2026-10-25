# Neural uncertainty nomination from retained scores

This source-only C++23 unit nominates intervals from the frozen HG002 development exports. It changes no basecall or gate, reads no reference FASTA or truth label, and invokes no neural producer. Retained complete-chunk tensors contain future information. This is an offline completed-chunk diagnostic, not causal streaming.

This v2 source lives in the separate `experiment/context-feedback-uncertainty-v2` worktree. The original uncertainty worktree, its14-file source closure, engineering3/4, preparation2 and failed/refused chunk0 attempts remain unchanged. Both attempted scans stopped before any native scanner: the old verifier required a FILEPATH cache entry, while installed CMake deliberately normalizes an explicitly supplied existing compiler to STRING. Supplying an explicit FILEPATH command argument did not change that behavior. The retained source trace is `logs/context-feedback/program-runs/UNCERTAINTY_CMAKE_CACHE_TYPE_ROOT_CAUSE_4.md` in the original worktree. No v2 formatter, build, control, preparation, scan or payload qualification has run.

## Defined uncertainty

The CRF starts uniformly over all k-mer states and ends unrestricted. Each timestep has one stay transition with the exported `blank_score` and four emitted-base transitions. The channel is `4*next_state + oldest_predecessor_base`, matching pinned Dorado and the existing independent context decoder. It is not `4*previous_state+base`. Exported clamp0 or5 is applied to finite FP16 neural values before the calculation. The pinned HACv6 configuration has k4, stride6 and blank score2.

Scaled log-space forward/backward recurrences compute the partition and marginalized transitions. Conditional base entropy is calculated from log masses, so a tiny emitted mass does not create an undefined division. The optional per-edge array is retained only by exhaustive controls. A transition table is validated once at the boundary, rather than allocating validation strings inside every edge update.

For each timestep, the predeclared v1 proxy is `0.5*H(base|emit)/ln(4) + 0.5*H(stay)/ln(2)`. The score of a21-called-base center is its time-weighted mean between the native move at its start and the native move immediately after its end. This is a conditional-CRF uncertainty proxy, not calibrated base-error probability or raw-current likelihood. No quality, reference mismatch, truth, private case or outcome enters ranking.

Only centers with four native initial-context bases, ten left-guard bases and twenty right-guard bases fully within one retained chunk are proposed. The expanded interval must fit256timesteps. Both mapped guards must be continuous and unclipped in the unchanged native alignment. Center insertions/deletions are allowed and genomic ownership derives from anchor cuts. Exact native/reference base equality remains a later graph-attachment check. The nominator does not fetch reference sequence to establish it.

Rank by decreasing proxy, then SHA256 of the declared parent/read-start/chunk identity. Accept up to512nonoverlapping owned21-base intervals. Retained chunk ownership is independently reconstructed from all DGM records and checked against DGP `SEQ/Q/MOVES`; neighboring chunks' retained read intervals are disjoint. A chunk-local greedy prefix of at most512therefore preserves the global greedy result when merged. Expanded guards can overlap; local or chunk posterior masses are never multiplied into a whole-read likelihood.

## Custody and source boundary

The original registered native-call artifact SHA256 is `f8470d591314a24e95ec594c5334d4969e0336be95115b644509da18e5543adf`. Its3,179pins cover1,557DGS tensors,1,557DGM records,64DGP parents and the export session. The v2 availability inventory was metadata-only and is not used as qualification.

`prepare.py prepare` imports the maintained reference auditor at its original absolute source location and checks its exact source pin. `qualify_original()` validates the registered producer/source/raw-command ancestry, current export membership and metadata pins without replaying a producer. Its historical plan/score metadata are read for custody only and do not enter the selector's records. The new input manifest contains only pinned metadata, original score hashes, original native alignment and source proof. It contains no graph or truth hypotheses. Score payloads are not parsed or newly hashed during preparation.

The C++ boundary independently binds every chunk/parent to the original registered pin array and exact file census. The registry's complete byte hash fixes its canonical JSON layout; a deliberately narrow pin-triple extractor admits exactly 3,179 objects from that fixed format. It is not a general JSON parser. A changed registry rejects before extraction. The native alignment and HAC configuration also have exact fixed original hashes. Native mapped parent `SEQ/Q` must equal the reconstructed DGP parent in molecule orientation. The original autosomal scope, chr1 through chr22, and MAPQ 30 through 254 are retained. Other parents retain an explicit exclusion reason.

A scan hashes each selected complete score file against its original producer hash before reading it, validates all header/metadata/length/finite fields, applies clamp, and processes one bounded chunk at a time. Unselected score payloads remain unqualified by that scan. An excluded parent still has its scanned payload verified but receives no posterior proposals. Final native receipts pin every consumed source, metadata file, score and output. Completion is written last and synced, not rename-atomic.

`prepare.py collect` joins each actual native scan attempt to its admitted worker, raw producer stage, successful outer worker and qualified engineering binary/runtime closure. A successful terminal from another unit is insufficient. Repeated chunk IDs reject rather than replay. The native merge requires all1,557disjoint qualified chunk rows before publishing the global top512. A partial scan is useful for throughput and contract qualification; it is not a complete nomination population.

The retained-start boundary is `core_begin >= chunk_start + 14`: the four prior-context bases precede the ten-base left guard. A nonzero retained start of20 therefore excludes starts30through33 and admits34 when other guards are valid, on either orientation.

## Prospective bounded commands

No formatter, compiler, CTest, native scanner, preparation or data qualification command has executed for this source handoff. Root first formats the owned C++ census, freezes its hashes and obtains an independent exact review. All commands below require fresh nonblocking canonical host-lock intake and whole-unit supervision through synchronous preparation/hashing and child processes. Caps are300seconds, two CPUs,4GiB memory,8GiB address space, zero swap,100MiB output stop and30GiB free-disk reserve. A free lock is not a reservation.

```sh
cmake -S tools/context_uncertainty -B results/context-feedback/uncertainty-v2-engineering-1/build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build results/context-feedback/uncertainty-v2-engineering-1/build --parallel 2
cmake --build results/context-feedback/uncertainty-v2-engineering-1/build --target format-check --parallel 1
ctest --test-dir results/context-feedback/uncertainty-v2-engineering-1/build --output-on-failure --parallel 1
results/context-feedback/uncertainty-v2-engineering-1/build/context-uncertainty qualify --output results/context-feedback/uncertainty-v2-engineering-1/native-controls
ldd results/context-feedback/uncertainty-v2-engineering-1/build/context-uncertainty
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv uv run --no-sync python tools/context_uncertainty/prepare.py controls
```

All owned sources compile under `-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off`. The source census drives the pinned formatter and runtime source guard, including actual compiler and flags. Root must retain actual compile commands, linked runtime libraries and their hashes; the source witness alone does not qualify dynamic resolution.

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/context_uncertainty/prepare.py prepare \
  --output results/context-feedback/uncertainty-v2-inputs-1

results/context-feedback/uncertainty-v2-engineering-1/build/context-uncertainty scan \
  --manifest results/context-feedback/uncertainty-v2-inputs-1/inputs.tsv \
  --manifest-sha256 ACTUAL_MANIFEST_SHA256 --begin 0 --count 1 \
  --output results/context-feedback/uncertainty-v2-chunk0-1
```

Fill the hash from the actual successful preparation completion. The first genuine chunk must prove accepted producer handoff and a separately pinned corruption rejection before more computation. Inspect its actual clocks, peak memory and output before running chunks1through31. That checkpoint reuses chunk0. Continue later with disjoint slices, ordinarily at most32chunks per admitted unit, after checkpoint cost is known. The native scanner refuses any slice exceeding20million state-timestep cells before score payload reads or DP, regardless of a larger requested count. These bounds are resource declarations, not measured runtime estimates.

For final collection provide a pinned JSON list of `{completion,receipt,unit,engineering}` pins for successful, disjoint scan units. `completion` is the native scan completion, `receipt` its maintained raw-stage finish, `unit` the scan worker completion and `engineering` the qualified engineering worker completion. Retain failed units separately. No skipped or missing batch may be counted complete.

Both worker completions use schema `uncertainty-worker/1` and fields `complete:true`, `phase` (`engineering` or `scan`), `admission_id`, `sources`, `source_id`, `driver`, `binary`, `stages` and `native`. `sources` is exactly the14-file native census, including the read-only evidence helper; the external driver has its own additional pin. The controller may import this module at its actual source location and call `sources()` and `source_identity(sources())` to get the canonical ordered pins and identity. The identity hashes concatenated UTF-8 `path<TAB>size<TAB>sha256<LF>` records in that order. The scan worker also pins `engineering`; engineering instead pins `build_closure`.

Engineering stages, in exact order, are `uncertainty-cmake-configure`, `uncertainty-cmake-build`, `uncertainty-format`, `uncertainty-ctest`, `uncertainty-native-controls`, `uncertainty-runtime-libraries`, `uncertainty-python-controls`. The runtime stage directly runs the resolved pinned `ldd` executable with the qualified binary as its sole argument. Python controls must emit exactly `{"controls":16,"failed":0,"skipped":0,"synthetic_only":true}`. Every maintained stage includes `admission_id` equal to its worker and `recorder_source` pin equal to the actual owned recorder. The worker `native` pin is the unique exact `qualify` or `scan` producer completion. Scan receipt membership and qualified binary/source equality are checked explicitly.

The engineering `build_closure` contains `binary`, `compiled_sources`, `compiler`, `cache`, `compile_commands`, `runtime_tool`, `runtime_producer` and nonempty `runtime_libraries`. The compiler/hash matches the compiled witness. The actual CMake cache must contain exactly one `CMAKE_CXX_COMPILER` entry, of type STRING or FILEPATH, with a value exactly equal to the native compiled-witness compiler path. It must contain exactly one `CMAKE_BUILD_TYPE` entry, of type STRING and value Release. Missing, duplicate, wrong-type and wrong-value entries reject. Compiler resolution/hash and actual compile-command checks remain mandatory; the cache is never rewritten to satisfy this validator. Installed `CMakeDetermineCXXCompiler.cmake` calls `_cmake_find_compiler_path(CXX)`, whose `CMakeDetermineCompiler.cmake` implementation forces an existing explicit compiler's cached type to STRING. Actual compile commands must cover every owned C++ translation unit with the strict flags. `runtime_producer` is the exact admitted runtime stage pin. Its full actual `ldd` stdout must resolve exactly the supplied unique canonical library pins; unresolved or unknown lines reject. Binary and every compiler/cache/compile-command/runtime-library file are rehashed before reuse.

The v2 external worker verifies its live expected cgroup, CPU quota2, memory4GiB, address space8GiB and zero swap through the maintained kernel-limit function before importing this scientific boundary or hashing its source census. It retains actual `/proc/self/cgroup`, `cpu.max`, `memory.max`, `memory.swap.max`, AS/FSIZE soft/hard limits and live service policy in a pinned `kernel-limits.json` referenced by worker start and completion. Its actual FSIZE limit is the4GiB retained aggregate grant; the outer separately stops at100MiB new total output growth and4GiB retained aggregate across all owned results/logs. Every v2 admission ID starts with `uncertainty-v2-`; its recorder alias points to this worktree's maintained recorder. The canonical stock lock and original reference-auditor ROOT remain unchanged.

Outer evidence retains the existing generic-controller layout at `logs/context-feedback/program-runs/run-<admission_id>/{start.json,terminal.json,cleanup.json,stdout}`. `start.json` has `argv`, `cwd`, pinned `worker`, `controller`, `recorder` and `caps` with `cpu`, `memory`, `address_space`, `swap`, `wall_seconds`, `maximum_output_bytes`. Its actual command uses `systemd-run --wait --pipe`, the exact owned recorder followed by the admission ID and worker command, `KillMode=control-group`, `ExitType=cgroup`, the declared CPU/memory/swap/address-space limits and a runtime bound within the whole-unit wall limit with one second for cleanup. `cleanup.json` must report terminal launcher group. The terminal service proof must have successful inactive state, zero main/control PIDs and empty ControlGroup. The launcher stdout identifies the actual recorder directory; all eight raw files are pinned, and argv/cwd/UTC clocks/GNU-time fields are checked. Most importantly its recorded worker stdout must equal `{"completion": <exact unit pin>}`. This binds the terminal proof to this source-pinned worker and its stages rather than to an unrelated successful format command. Completion remains written-last/synced, not rename-atomic.

Before wider scans, verify one genuine scan record and its engineering ancestry without requiring a complete cohort:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/context_uncertainty/prepare.py verify-unit \
  --prepared results/context-feedback/uncertainty-v2-inputs-1/complete.json \
  --prepared-sha256 ACTUAL_PREPARED_SHA256 --scans CHUNK0_RECORD.json \
  --scans-sha256 ACTUAL_RECORD_SHA256 --output results/context-feedback/uncertainty-v2-chunk0-verification-1
```

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/context_uncertainty/prepare.py collect \
  --prepared results/context-feedback/uncertainty-v2-inputs-1/complete.json \
  --prepared-sha256 ACTUAL_PREPARED_SHA256 --scans SCAN_RECORDS.json \
  --scans-sha256 ACTUAL_SCAN_RECORDS_SHA256 --output results/context-feedback/uncertainty-v2-parts-1
results/context-feedback/uncertainty-v2-engineering-1/build/context-uncertainty merge \
  --manifest results/context-feedback/uncertainty-v2-inputs-1/inputs.tsv \
  --manifest-sha256 ACTUAL_MANIFEST_SHA256 \
  --parts results/context-feedback/uncertainty-v2-parts-1/parts.tsv \
  --parts-sha256 ACTUAL_PARTS_SHA256 --output results/context-feedback/uncertainty-v2-nominations-1
```

## Controls and acceptance limit

Synthetic controls independently enumerate every neural path for tiny k1, k2 and k4 frames. They compare the complete edge census and partition, check a finite-difference partition derivative, analytic symmetric probabilities and state-dependent future evidence. A wrong channel layout must disagree. High-dynamic-range cases exercise log-space conditional entropy. Half zero/subnormal/extreme/nonfinite values, actual DGS clamp/length handling, both-strand boundary indels, clipped guards, ownership, permutation/tie behavior and batched-versus-global greedy selection are included.

The source-corruption fixture deliberately exercises the original root hash. Separate independently pinned nonfinite, trailing and truncated fixtures must reach the deeper half/length errors. The16Python boundary controls independently build explicitly synthetic receipt chains. The original seven controls remain: a complete accepted chain, swapped unrelated outer completion, absent scan stage, empty runtime census, absent binary, wrong stage admission and absent runtime file. The accepted default cache uses the STRING style observed in retained genuine CMake output; a second positive chain proves FILEPATH compatibility. Eight additional negatives cover wrong compiler type/path, duplicate/missing compiler entry and duplicate/missing/wrong-type/wrong-value build-type entry. Each negative re-pins its synthetic changed cache/closure/outer chain so the intended semantic guard must reject. These synthetic controls do not substitute for the genuine chunk0 `verify-unit` handoff. No executed v2 mutation or guard acceptance is claimed in this handoff. Genuine full payload qualification, new error exposure, graph attachment, decoding, complete-parent edits, accuracy, ALT preservation and throughput remain coordinator obligations.
