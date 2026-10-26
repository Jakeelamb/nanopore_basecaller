# F3 source-ready cut and qualification request

Status: SOURCE-READY UNFORMATTED; tests actually executed0. No PASS is claimed. This source cut is an implementation handoff, not runtime/science qualification.

Worktree `/home/jake/Projects/nanopore_basecaller-next-indel-decoder`; branch `experiment/next-indel-decoder`; initial head `c62b8c16c59fbeadffe56fff67d78a9f4ba35296`. Draft PR17: https://github.com/Jakeelamb/nanopore_basecaller/pull/17. The immutable delivery head is the commit containing this file, to be relayed separately by its actual Git ID. No merge, rebase, force push, retarget or ready transition is authorized.

## Implemented source

- C++23 classifier consumes native pairer parent-specific `matched.bed`, frozen parent IDs and `parents.tsv`, independently walks SAM EQX and reconciles every parent's m/x/i/d and reference exposure. All zero-exposure parents remain explicit. Both-flank insertion and basewise deletion rules match the traced pairer.
- Counts distinguish eligible bases and eligible CIGAR events. Deletion events crossing domains remain one event; eligible bases remain exact. Homopolymer compatibility, short tandem context and unknown mechanism are overlapping annotations. Pure API accepts actual query geometry for boundary/overlap attributes. CLI geometry is currently null/unknown, never inferred from frame counts.
- Bounded, truth-free single-indel and run-length ±2 nomination; exact fixed-initial-state CRF marginal likelihood over identical available rows; deterministic deduplication; candidate overflow rejects rather than truncates.
- Full forward/reverse SEQ/Q edit reconstruction with separate splice/reverse-replacement checks, overlap rejection and exact disabled identity. Changed Q remains uncalibrated `!`.
- Input adapter binds raw batch FilePin, independent expected batch hash and full expected binding; DGS/DGM producer identities and released row availability; native segment identity; original candidate likelihood recomputation. Output is an F1-consumed extension sidecar. F1 owns location costs, union merge and complete feedback-next/1 emission. No policy or persistent decoder clone.
- Fourteen named C++ control groups include a tiny exhaustive long-double path census and total marginal mass conservation, repeated paths, impossible sequences, known2/3/4 runs, nonrepeat indel, boundary/reverse/adjacent-indel/two-flank/zero exposure and full edits. Seven UV unittest methods exercise actual C++ consumed fixtures and independent-hash/binding/counter corruption rejection. Missing binary fails, with no skip path.

## Frozen dependencies traced

Read complete `research/indel-decoder-unit.md`, Root execution-plan/preferences, frozen TARGET outcomes and evidence manifest. Baseline remains PR15 `400063e97c476303c6a113fb0aab5d0698f0984f`; final report SHA256 `446dbb7fd62d5969663571b4e2edb1ae6e22e7cbb95ef6b61653286c38c99850`. Native-relative selected gains do not establish extra partial-search benefit or biological promotion.

Root-relayed F2 schema is frozen at `58fc6058e9c3852bcc5abe5d82210026188a2151`, under `/home/jake/Projects/nanopore_basecaller-next-context-policy/research/context-policy-design.md`. F3 imports no mutable sibling header. The extension carries its original source batch pin; final F1 merge must consume immutable sibling source pins.

Native pairer source `/home/jake/Projects/nanopore_basecaller-reference/tools/reference_pair/src/lib.rs`,31594bytes, SHA256 `53ec152057c37d6c5d8d987c9bd9399d2444fd2e5139e5782a504f04d1841da4`, explicitly writes `matched.bed` with parent column and complete `parents.tsv`. Registered binary is1055816bytes, SHA256 `e1bfe5f55a1c6c4b6e74a3622ac991f0b5860ea4695de805fff287ad74fa4979`; binary body was not opened. Original CRF source is `/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/crf.rs`,4878bytes, SHA256 `3171343d81477d4d967e300466e9ba3e3d770164f34438dcedd0867ca5ea8a99`. It remains unchanged.

## First exact admission request: format only

Cwd is the F3 worktree above. Environment `PATH=/usr/bin:/bin LC_ALL=C HOME=/home/jake`. Execute exactly:

```sh
/usr/bin/clang-format -i tools/indel_feedback/include/indel_feedback/core.h tools/indel_feedback/src/core.cpp tools/indel_feedback/src/classifier.cpp tools/indel_feedback/src/proposals.cpp tools/indel_feedback/src/io.cpp tools/indel_feedback/src/main.cpp tools/indel_feedback/src/controls.cpp
```

This is the complete explicit seven-file owned C++ census. Formatter expected SHA256 `cd50c00c4b3475329257d717f9e778769d00d1eff5c03436ebc39b023ddd6394`. Cap60s, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, free reserve30GiB. Exact immutable input is this source-cut head. Root must admit a fresh unit; do not run while F4's known launcher-group cleanup blocker is open. Re-freeze formatted source before any compile.

## Subsequent engineering request, after formatted source admission

These commands are proposed only; all are unexecuted. Cwd is F3 worktree. Environment `PATH=/usr/bin:/bin LC_ALL=C HOME=/home/jake UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv`. UV executable `/home/jake/.local/bin/uv`. No dependency fetch, environment creation, GPU or raw replay.

```sh
/usr/bin/cmake -S tools/indel_feedback -B results/indel-feedback/qualification/build -DCMAKE_BUILD_TYPE=Release -DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results -DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format
/usr/bin/cmake --build results/indel-feedback/qualification/build --parallel 2
/usr/bin/cmake --build results/indel-feedback/qualification/build --target format-check --parallel 1
/usr/bin/ctest --test-dir results/indel-feedback/qualification/build --parallel 1 --output-on-failure --no-tests=error --output-junit /home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification/ctest.xml
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python -m unittest discover -s /home/jake/Projects/nanopore_basecaller-next-indel-decoder/tests -p test_indel_feedback.py -v
```

UV stage additionally sets `INDEL_FEEDBACK_BINARY=/home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification/build/indel-feedback`. Cap300s per admitted complete unit, CPU2, RAM4GiB, AS8GiB, swap0. Growth100MiB, cumulative program4GiB and reserve30GiB. Canonical NONBLOCK lock admission is Root-owned. Required outputs include configure/build/format/CTest/UV stdout+stderr/time+start/end/exit receipts, compile source census, JUnit with executed>0/skipped0, and terminal tree/cgroup-empty proof before release. A failed first attempt must be preserved and reported as failed.

Tiny fixture bodies are generated only inside admitted tests. Each DGS is under32KiB. Total test data is under1MiB. The pinned local JSON header is919975bytes, SHA256 `9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6`; no download. Numerical oracle is independent tiny path enumeration in C++23 using linear long-double mass. It is not the unchanged original Rust control; genuine native scalar parity remains separately required.

## Classification and pilot input requests

Exact scientific execution is held until Root supplies/adopts external immutable request FilePins and role pins. The source-pinned CLI is:

```sh
/home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification/build/indel-feedback classify ABSOLUTE_REQUEST EXPECTED_REQUEST_SHA256 ABSOLUTE_NEW_OUTPUT
/home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification/build/indel-feedback propose ABSOLUTE_REQUEST EXPECTED_REQUEST_SHA256 ABSOLUTE_NEW_OUTPUT
```

For the first classification: need selected/native mapped SAM pins, FASTA pin, exact64-parent ledger pin, each comparison's mask100/mask500 parent-specific `matched.bed` and `parents.tsv`, and arm-side declarations. Do not substitute a global mask, nominated union or observer `coverage.bed`. Reference bodies remain stat-only until this grant. Full-reference classifier loads FASTA and therefore requests its own RAM16GiB/AS24GiB unit, CPU2, wall300s; no full-reference run is requested under ordinary4/8GiB controls. Expected accepted selected totals are I2241/D3236/X3195 and I998/D1459/X1430; native counters come from actual pairer outputs, never inferred from these differences. All64 per-parent counters and zero rows must reconcile before any claim.

For a genuine proposal fixture/pilot: need a frozen F1 candidate batch and independent expected binding, released DGS/DGM and native identity pins, original-Rust native scalar receipt, and a pre-scoring explicit parent/window list (including exclusions) from the exposed HG002 development set. Then qualify one genuine producer-to-consumer fixture plus a rejection before expansion. Freeze original/addindel-prior-none/addindel-fixed-policy arms and unchanged0.5 thresholds before scoring. No HG005 selection. Null pilot list in `config/indel-feedback-dev-v1.json` is an explicit hold, not a runtime default.

## Unresolved gaps and preserved inspection error

- Unformatted and uncompiled; source controls and wrapper have not run. Runtime bugs remain possible.
- CLI chunk geometry remains unknown; pure geometry API controls cannot establish genuine chunk annotation.
- F3 extension edits use begin/end replacement records; F1 must normalize them into the frozen feedback-next/1 SNV/INS/DEL wire records and compute context costs. Complete F1/F2 consumed integration is unqualified.
- Original Rust native-frame scalar comparison, full64-parent classifier reconciliation, matched genuine pilot, variant-footprint evidence, runtime/performance and biological improvement are unqualified. Candidate bounds are predeclared; no positive outcome is assumed.
- A preparation `rg` mistakenly descended generated `reference/tools/**/target` metadata, producing a truncated large result. Total preparation bytes read are unknown. No scientific binary/SAM/DGS/reference body was intentionally opened and no test/native computation was run. Subsequent reads were narrowed to exact pre-sized source/metadata paths. This incident remains a preparation-boundary failure; it is not restamped as a bounded PASS.
