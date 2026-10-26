# F3: Indel-aware correction

Worktree: /home/jake/Projects/nanopore_basecaller-next-indel-decoder
Branch: experiment/next-indel-decoder
Base: main c6abd1bd96b397dc9b4f9564901003ccd5c30057
Status: source preparation; this brief is not an execution grant.

## Goal
Classify remaining insertions/deletions without losing or double-counting errors, then implement a signal-supported indel proposal mechanism that can be tested independently of policy changes.

## Ownership
Own tools/indel_feedback/, scripts/indel-feedback.py, config/indel-feedback-dev-v1.json, tests/test_indel_feedback.py and research/indel-decoder-*.md. Do not edit F1 decoder, F2 policy, F4 runner or frozen predecessor sources.

## Design and implementation
The accepted selected-arm counters are I2241/D3236/X3195 in mask100 and I998/D1459/X1430 in mask500. Indels are about63% of remaining errors, not necessarily all homopolymer mistakes. First implement a C++ classifier over admitted native/selected mapped artifacts and frozen domains. Separate base counts from event counts. Classify run-length, other repeat/context and chunk-boundary attributes without claiming overlapping attributes partition the total. Preserve an unknown class.

Then implement bounded variable-length proposals based on available CRF stay/emission evidence and sequence context, e.g. alternative run lengths. Do not call neural timestep occupancy a measured raw-current dwell time. Do not use posthoc truth error locations to nominate candidates. Freeze the pilot window/parent list and run-length bounds before scoring. Use genuine frame geometry and independent original scalar checks; original Rust computation remains read-only.

Keep old guard exclusions intact in the old arm. A gapped-anchor or wider candidate mechanism is a new declared arm with a matched baseline, not a way to restamp excluded old frames. Emit indel candidates into feedback-next/1 so F1/F2 remain separate owners.

## Acceptance and behavioral tests
- Classifier sums exactly to admitted I/D/X counters on each unchanged paired domain. Preserve all64 parents and zero-exposure rows; insertion two-flank convention equals the qualified pairer.
- Synthetic CIGAR fixtures cover insertions/deletions at both boundaries, reverse strand, adjacent indels, repeats, chunk overlap and no exposure. Event/base count and overlapping annotations cannot double-count.
- Known2/3/4-base homopolymer fixtures produce correct alternative lengths from signal; a nonrepeat ambiguity fixture prevents assuming every indel is a run-length error.
- Independent tiny exhaustive path census and sequence-likelihood oracle check candidate masses/ranks, repeated paths and impossible sequences.
- Disabled edits are exact identity; prior-none remains actual signal ranking. Forward/reverse edits reconstruct complete SEQ/Q exactly; invalid overlap/foreign parent/chunk/tensor rejects.
- A fixed small genuine development pilot compares original candidates, added-indel candidates without reference prior, and added-indel candidates with unchanged fixed policy. No tuning old thresholds.
- Report changes in substitutions as well as I/D, regression parents, edited variants, abstention, runtime and candidate counts. A valid negative result is accepted; no variant-safety claim from off-edit retention.

## Exact engineering commands to implement
cmake -S tools/indel_feedback -B results/indel-feedback/qualification/build -DCMAKE_BUILD_TYPE=Release -DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results -DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format
cmake --build results/indel-feedback/qualification/build --parallel 2
cmake --build results/indel-feedback/qualification/build --target format-check --parallel 1
ctest --test-dir results/indel-feedback/qualification/build --parallel 1 --output-on-failure --no-tests=error --output-junit results/indel-feedback/qualification/ctest.xml
Provide fixed-UV tests and exact source-pinned classifier/pilot commands. Engineering300s/2CPU/4GiB/AS8GiB; full-reference classification may request16GiB/AS24GiB separately.

## Shared interface and data contract
The authoritative program plan is /home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes/execution-plan.md and standing orders /home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes/preferences.md. They are Root-owned. Interface version is feedback-next/1; propose changes to Root before implementing incompatible variants.

A candidate batch binds schema version, source/plan hash, input tensor pin, read ID, parent/chunk/block index, available score/signal endpoint and declared chunk lookahead, previous state hash, orientation, and exact location-producer receipt. Each location includes contig, strand, mapped query extent, reference interval and a confidence feature with its meaning. Each candidate has a stable ID, sequence, marginalized neural log likelihood, context cost, edits and eligibility reasons; the genuine signal-only candidate is named explicitly. A decision binds the entire candidate-batch hash and selects a candidate ID with reason and confidence. Do not call MAPQ or an uncalibrated neural margin a posterior probability.

F1 owns the streaming/session implementation and candidate-batch producer. F2 owns the pure candidate decision policy and calibration. F3 owns indel proposals and error classification. F4 owns stock comparisons and a minimal reusable bounded process adapter, reusing the qualified process-guard primitives. Interfaces are small versioned requests/results; no lane mutates another package. Initial engineering fixtures may implement this contract independently; real integration consumes frozen sibling commits only after Root relays pins. There is one decoder in F1, not four competing copies.

The existing baseline is read-only PR15, commit400063e97c476303c6a113fb0aab5d0698f0984f, checked out at /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results. Scientific artifacts remain at /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2; read research/context-feedback-targeting-v2-outcomes.md and its evidence manifest before work. Final report SHA446dbb7fd62d5969663571b4e2edb1ae6e22e7cbb95ef6b61653286c38c99850. Selected==rerank, unionNN==free. Native-relative gains1.280011%/1.316314%; selected/free1.046319%/.965899%, so the latter two-domain1% gate fails. Zero productive ALT at changed footprints; no biological promotion.

## Common qualification recipe
For C++ lanes implement Release CMake with C++23 and -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror, -fno-fast-math and -ffp-contract=off. A format-check target uses pinned clang-format --dry-run --Werror and an explicit owned source census. No legacy-source formatting. Configure a fresh results/<tool>/qualification/build directory, build --parallel 2, format-check, then CTest --parallel 1 --output-on-failure --no-tests=error with JUnit proving tests executed and skipped0. All dependencies are pinned local paths; no network fetch.

Python orchestration tests use the fixed UV environment and unittest discover -s <lane>/tests -p test_<tool>.py -v. Tests defaulting to skips do not qualify consumed-frame or process behavior. Source-only hermetic control preparation is allowed; actual test/native execution waits for Root's exact fresh slot.

Before expensive science, run one genuine producer-to-consumer fixture plus a rejection control. Test full input/source/cwd/argv/time/stderr custody and source-root corruption separately from deeper guards. The complete unit must supervise synchronous hashing/input preparation as well as child stages; TERM/KILL/reap and group/cgroup-empty proof precede lock release even when the leader exits early.

## Delivery sequence
1. Read instructions and frozen evidence; write two design alternatives and select a small interface-compatible design before nontrivial search changes.
2. Implement within your ownership; do not wait for another lane to create your own numerical controls and disabled/reference-free fixtures.
3. Freeze source and submit exact CPU qualification command/caps. Return source-ready so Root can release the native agent slot while retaining your ownership.
4. After Root grants execution, run/fix only the admitted unit. Preserve failures and successful producer outputs. Genuine development runs follow engineering acceptance, first a fixed small pilot, then a predeclared bounded expansion.
5. Review another lane only when Root assigns a read-only delta. Address your own independent review findings, push draft updates, and leave exact evidence.

## Standing orders
1. Root is the only coordinator for branches, PR metadata, shared-host execution and scientific acceptance. Own your lane end to end; do not spawn children.
2. You are not alone. Write only your worktree and allowed paths. Preserve every unrelated file and all frozen predecessor artifacts. Never edit another lane or source owner's files.
3. New numerical/search code is C++23, matching pinned Dorado. Python is UV orchestration/validation only. Existing Rust scalars remain read-only independent oracles.
4. All four branches start from main c6abd1bd96b397dc9b4f9564901003ccd5c30057. Predecessor PR15 and its exact source/evidence are read-only dependencies, not ancestors to import wholesale. Do not merge, rebase, force-push, retarget or close PRs.
5. No stock/shared Dorado, decoder, export kernel or .github edits. No native neural replay, model download/training or GPU launch. Existing P01/S01 and native holds remain; Root coordinates any later execution separately.
6. Initial authorization is source preparation and bounded metadata inspection. Before compiling, running tests/native tools, opening heavy scientific bodies, or starting a checkpoint, submit immutable source pins, exact argv/cwd/environment, input pins, expected outputs and resource caps. Root grants a fresh bounded execution slot without asking Jake again.
7. CPU qualification defaults are 300s, two CPUs, RAM4GiB, AS8GiB, swap0. Existing whole-reference mapping/scoring may request RAM16GiB/AS24GiB. Growth100MiB, program cumulative4GiB and free reserve30GiB apply. Canonical host.lock is NONBLOCK, never waited for or stolen; no automatic retries after refusals.
8. Use /home/jake/Projects/nanopore_basecaller-retrieval/.venv with UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 and uv run --no-sync. Do not create another environment or download dependencies.
9. Metadata/source reads are pre-sized <=8MiB/file and <=32MiB/pass, with repeated bytes counted. Binary/model/DGS/reference/truth/SAM/GFA/gzip/trace bodies are STAT-only outside admitted workers under exact role pins. Do not bypass by suffix, prefix or caching a mutable inode.
10. Keep raw commands, cwd, source/recorder pins, start/end, exit, full stderr/time, kernel caps and terminal-tree evidence. Write terminal failures before projection; reuse successful producers rather than rerun them. Complete is written-last and synced, not rename-atomic.
11. Development HG002 is exposed; do not select using HG005. Freeze new hypotheses and policies before scoring, preserve all parents/exclusions, use actual matched reference-free and disabled-identity arms separately. Do not weaken old gates to improve outcomes.
12. Report honest negative results and unqualified evidence. No streaming claim from completed alignment or future-dependent rows; no biological promotion from off-edit ALT retention; no speed claim from engineering proxies.
13. Push owned source commits to your draft branch after checks; do not mark ready or merge. Return the exact head, tests actually run, failures, immutable receipts, limitations, next command/caps, and PR link. Root owns the single canonical decision trail.
