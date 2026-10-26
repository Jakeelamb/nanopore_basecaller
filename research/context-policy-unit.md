# F2: Confidence-aware reference guidance

Worktree: /home/jake/Projects/nanopore_basecaller-next-context-policy
Branch: experiment/next-context-policy
Base: main c6abd1bd96b397dc9b4f9564901003ccd5c30057
Status: source preparation; this brief is not an execution grant.

## Goal
Implement confidence-aware reference guidance and eligible-alternative selection, keeping fixed-policy, prior-none and disabled-edit controls separate. This is a new predeclared policy experiment, not an outcome-driven edit to the frozen old gates.

## Ownership
Own tools/context_policy/, scripts/context-policy.py, config/context-policy-dev-v1.json, tests/test_context_policy.py and research/context-policy-*.md. F1 owns decoding, F3 indel generation and F4 stock comparison. Do not duplicate a decoder or edit their worktrees.

## Design and implementation
Consume the versioned candidate batch, genuine marginalized signal likelihoods, context cost and explicitly defined uncertainty/location features. Implement a pure deterministic C++ policy with fixed-policy compatibility and adaptive mode. Provide bounded confidence-dependent prior strength and an explicit signal evidence budget; calibrate only on declared development partitions. Separate proposed policy from a fitted/calibrated model, and freeze any fitted parameters before evaluation. Existing64 parents are exposed development even under cross-validation. No HG005 selection.

The current single global0.5 margin can reject lower-neural one-edit corrections; testing eligible runners-up is a concrete change. Do not merely increase reference weight. Check all eligible alternatives and retain a named genuine reference-free fallback. Never treat population membership as proof against an unrepresented allele. Existing HPRC paths are already present; test weighting/haplotype continuity rather than claiming the first graph prior.

Give Root an independent alternative design for F1's session/state boundary early, then proceed with your pure policy. Integrate through frozen requests/results or a pinned library boundary; no hidden access to truth or source owner's globals.

## Acceptance and behavioral tests
- Disabled editing preserves input SEQ/Q; prior-none selects the actual neural winner and may legitimately edit.
- Constructive top-candidate-fails/second-candidate-passes case chooses the eligible runner-up rather than falling back immediately.
- Lower location confidence cannot silently increase reference influence; strong conflicting signal enforces the declared escape/budget. Confidence semantics and calibration limits are explicit.
- Exact ties are deterministic; candidate order/path permutations do not change decisions; missing/nonfinite/foreign/stale input or batch hash rejects.
- Independent tiny candidate-map oracle checks objective, eligibility and every decision, including no eligible finalist and empty context.
- Wrong confident reference and private SNV/INS/DEL controls show how novel signal-supported sequence survives; report actual failures.
- Candidate-union, signal scores and evaluation domains are identical in fixed/adaptive ablations. Policy versus candidate-generation improvements remain separate.
- Quality recalibration is implemented only if qualified labels exist; otherwise edited confidence stays explicitly uncalibrated.
- All-parent error components, zero exposure, changed-footprint ALT and technical parent/block bounds are retained. Existing100-per-class productive-ALT gates remain unmet if support is insufficient.

## Exact engineering commands to implement
cmake -S tools/context_policy -B results/context-policy/qualification/build -DCMAKE_BUILD_TYPE=Release -DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results -DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format
cmake --build results/context-policy/qualification/build --parallel 2
cmake --build results/context-policy/qualification/build --target format-check --parallel 1
ctest --test-dir results/context-policy/qualification/build --parallel 1 --output-on-failure --no-tests=error --output-junit results/context-policy/qualification/ctest.xml
Provide fixed-UV Python tests, calibration split specification, immutable development input pins and exact pilot commands/caps. No full tensor/trace reads outside Root-admitted units.

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
