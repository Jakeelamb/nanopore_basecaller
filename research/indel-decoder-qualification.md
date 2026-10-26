# F3 source-ready cut and qualification request

## Stage directory correction, 2026-10-26

F2's first launched qualifier exposed a receipt/artifact collision before compilation. F3 shared that recorder structure and is corrected before its first launch. Stage receipts now use `stages/<name>/`, separate from CMake's `build/` artifacts. Stage setup is inside the error handler. The top-level terminal record identifies the attempted stage, argv and directory even when setup fails. Existing receipt directories are rejected without modifying their contents.

Before configure, an admitted local namespace control creates a build directory and runs one empty Python child through the production stage recorder. It then rejects an attempted duplicate stage before launching another child and checks that all retained records are unchanged. Its evidence is `namespace-control.json` and `namespace-control/stages/build/`. This control is prepared and has not run at this source handoff.

The next child command remains the fixed-UV command below with `--output /home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification-01`. Expected links now include `namespace-control.json`, `stages/{configure,build,format-check,ctest,uv-tests}/{command.json,cwd.txt,start.txt,end.txt,exit-status.txt,stdout,stderr,time.txt,terminal.json,complete.json}`, plus the existing top-level terminal, completion, JUnit, unittest and compile-command files. Root supplies a fresh in-root `TMPDIR`. Caps and the frozen F4 boundary are unchanged. A fresh configure binds the corrected qualifier into the compiled source witness. No formatter or numerical source changed in this correction.

## Formatted engineering handoff, 2026-10-26

Root's format-only attempt `results/indel-feedback/format-01` completed with exit0. Its admission SHA256 is `ba6b7d8099d9109c4224f71d07a1775fecb12ebfa18f17104b59376522ea48e2`. `terminal.json` retains the actual exit and cleanup, and `outer-terminal.json` records both groups empty before unlock with no error. The raw wrapper receipt is `/home/jake/Projects/nanopore_basecaller-retrieval/logs/20261026T193536Z-feedback-f3-format-01-K5gzz6`. Seven owned C++ files changed. Independent comparison against the reviewed head passed after normalizing whitespace, comments, include order and adjacent string-literal splitting. The first comparison omitted string-literal joining and failed on `io.cpp` and `main.cpp`; inspection traced both differences to formatter splitting, and the corrected comparison passed. No numerical change was made.

`tools/indel_feedback/qualify.py` now runs the five existing stages sequentially. Each stage retains eight raw command, cwd, start, end, exit-status, stdout, stderr and GNU time files plus its terminal record before projecting success. A failure stops the chain and preserves its directory. This runner adds no lock, process-group manager, kernel limit or timeout. Root must launch it through frozen F4 `bounded.py` SHA256 `8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4` at F4 revision `d190ab3f8175f1af7b5d4057b893ef6424b9d41f`.

The next exact child command, with this worktree as cwd, is:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python tools/indel_feedback/qualify.py --output /home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification-01
```

The fresh build is `qualification-01/build`. Configure explicitly selects `/usr/bin/c++`, `/usr/bin/make`, Release and compile-command export. The UV test stage sets `INDEL_FEEDBACK_BINARY` to that exact new binary. Acceptance requires one successful CTest `indel_controls` with skipped0, its exact14 named `PASS` groups and `controls_executed=14 skipped=0` retained in JUnit, and exactly7 successful UV unittest methods with no skips or expected failures. Fourteen control groups are not fourteen CTests. The unit retains `ctest.xml`, `unittest.json`, `build/compile_commands.json`, each stage's raw files and `terminal.json`; it writes `complete.json` last and syncs it. F4's separate terminal-tree proof remains required.

Requested whole-unit caps remain wall300s, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, aggregate4GiB and reserve30GiB. Use the canonical NONBLOCK lock once, without retries. Only Root admits and launches this command. Tests actually run at this source handoff remain0. The CMake source witness now includes this qualifier, the existing wrapper, UV tests and predeclared config. Registered tool/header pins come from `ready-native-v2-4/tools.json` under targeting-v2 and PR15's `tools/uncertainty_feedback/dependencies.json`; executable bodies remain stat-only during preparation. Dynamic compiler/system-header/OpenSSL dependency closure requires separate retained evidence and is not inferred from these entries.

Everything below records the original unformatted source request. Genuine64-parent reconciliation, original native Rust scalar parity, F1/F2 integration, biological accuracy and performance remain held.

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
