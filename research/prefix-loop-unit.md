# F1: Growing-read feedback

Worktree: /home/jake/Projects/nanopore_basecaller-next-prefix-loop
Branch: experiment/next-prefix-loop
Base: main c6abd1bd96b397dc9b4f9564901003ccd5c30057
Status: source preparation; this brief is not an execution grant.

## Goal
Implement a real growing-read location-feedback session using available neural score blocks, with multiple location hypotheses and a separately advancing signal-only escape. It must alter partial-path decoding, not merely rescore a fixed completed panel.

## Ownership
Own tools/prefix_feedback/, scripts/prefix-feedback.py, config/prefix-feedback-dev-v1.json, tests/test_prefix_feedback.py and research/prefix-loop-*.md in this worktree. Shared and predecessor code remain read-only. Use C++ for decoding; UV Python coordinates.

## Design and implementation
Compare a persistent joint sequence/location beam against a rolling undecided suffix with periodic remapping. Choose using complexity, information availability and meaningful tiny controls, not measured truth outcomes. Keep available-score boundaries explicit. Initial context must be a declared prior or previously emitted state, never a k-mer selected from the completed native call. Specify chunk overlap/stitch ownership; never double-count scores.

At each update align only the actual provisional prefix. Bind the real mapper's receipt, query hash, CIGAR, orientation and all retained positions to the next decode block. No completed-read alignment, future native bases/MOVES, right guards or offline future-completion guides may enter inference. Whole-chunk lookahead already inside saved neural scores must be disclosed. Chunk-delayed score replay is not strict raw-acquisition causality.

The initial genuine pilot is the lexically first metadata-eligible development parent with a predeclared set of at least three successive available blocks. Freeze identity/cutoffs before opening truth. Query0 overlaps earlier development diagnostics and cannot be independent confirmation. Do not use a mock locator as the only real-path acceptance. Retain full output parent/SEQ/Q identity for disabled edits and independently reconstruct actual edits on both strands.

## Acceptance and behavioral tests
- Tiny unpruned independent enumeration equals complete finalist sequence census, per-finalist marginalized neural mass and final rank within a declared numerical tolerance.
- Split-block stepping and one-pass decoding agree when locations/policy are held equal; score rows are owned exactly once.
- Modifying unavailable future blocks leaves all preceding outputs and mapper requests identical. Missing/foreign prefix, endpoint, state, tensor, orientation or receipt rejects.
- At least three genuine prefix-derived location updates are recorded; competing/revised locations are represented rather than silently fixed to native location.
- A plausible wrong-location fixture preserves signal-only escape or explicit abstention. Include no-location, ambiguous-location, tie, no-finalist and path-permutation controls.
- Context acts only on emitted bases, never stays. Beam pruning, symbol bounds and any truncation are reported explicitly.
- Compare signal-only, fixed-policy rerank and partial-feedback at matched availability/delay; a positive outcome is not required. Report accuracy and latency separately. Never attribute an accuracy gain to online scheduling alone.

## Exact engineering commands to implement
cmake -S tools/prefix_feedback -B results/prefix-feedback/qualification/build -DCMAKE_BUILD_TYPE=Release -DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results -DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format
cmake --build results/prefix-feedback/qualification/build --parallel 2
cmake --build results/prefix-feedback/qualification/build --target format-check --parallel 1
ctest --test-dir results/prefix-feedback/qualification/build --parallel 1 --output-on-failure --no-tests=error --output-junit results/prefix-feedback/qualification/ctest.xml
Provide the exact fixed-UV Python test command and exact genuine pilot request/runner commands at source freeze. Engineering cap300s/2CPU/4GiB/AS8GiB; mapper phases may request16GiB/AS24GiB separately.

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
