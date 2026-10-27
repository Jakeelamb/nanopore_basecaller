# F1 first source review candidate

Status is SOURCE-READY FOR REVIEW, UNQUALIFIED. Root requested this immutable cut to release the active agent slot. F1 retains ownership of corrections, qualification, real-path integration and PR16. This cut is not acceptance or scientific promotion.

The implementation contains a C++23 persistent forward sequence/location beam, a separately advancing signal-only beam, an exact consumed-row neural marginal, a declared uniform state prior, PAF/CIGAR position validation, both-strand continuation transport, stable candidate IDs, edit reconstruction and a `feedback-next/1` candidate producer. It prepares independent full-census tiny controls and genuine C++ producer/consumer wire controls. UV Python prepares frozen released score blocks and the proposed real-prefix loop. Owned source only changed. Predecessor PR15, stock, Rust oracles, shared kernels and all scientific artifacts remain read-only.

The source design compares persistent channels with rolling suffix replay. It chooses persistent channels because row/state ownership is simpler and no committed-cut or replay proof is needed. Prefixes are entirely provisional. There is no early immutable-base claim.

## Actual work and outcomes

- Build executions0, numerical controls0, Python tests0, CTest0, formatting0, mapper0 and genuine pilot0. No command is called PASS.
- `git diff --check` ran as a source whitespace inspection and emitted no error. It does not qualify C++ formatting, compilation or behavior.
- Read-only manifest inventory found the lexical parent `025d40d8-9380-4590-a82f-8291ba16acd9` and first DGS size4171853, SHA256 `655601ed280ac0b09ea168963e9fb803af7f2f42d23ba3ae98e3f084f4273f9e`. Its DGM metadata is4463 bytes, SHA256 `4cbdf5395679fc40b703f1078ad4669644a441715e09f59c92ce5cc27f48ea50`. Neither DGS nor DGM body was opened.
- The observed size suggests about2037 rows under1024 binary16 channels. This is a guess from size, not accepted T. The admitted prepare worker must verify actual T and freeze exact cutoffs before mapping or truth.
- The read-only PR15 source HEAD is `400063e97c476303c6a113fb0aab5d0698f0984f`. Its dependency manifest SHA256 is `f9a7bb78dfa8d5da15dc40541a2097f31ab9619d77602a62cbb3a2921a49ffd9` and the CMake configuration rejects another manifest.

## First prospective unit

Source formatting only. Cwd is `/home/jake/Projects/nanopore_basecaller-next-prefix-loop`. Explicit source census is six files.

```sh
/usr/bin/clang-format -i tools/prefix_feedback/include/prefix_feedback/session.h tools/prefix_feedback/src/io.cpp tools/prefix_feedback/src/session.cpp tools/prefix_feedback/src/location.cpp tools/prefix_feedback/src/main.cpp tools/prefix_feedback/tests/controls.cpp
```

Root must pin formatter/source input files, preserve raw argv/cwd/start/end/exit/stderr/time, and verify token/AST preservation in the admitted source-format unit. Suggested cap is30seconds, CPU1, RAM1GiB, AS2GiB, swap0, growth1MiB. No formatting ran in this source turn. The explicit census and the owned `.clang-format` exclude legacy sources.

## Prospective engineering qualification

Cwd is the F1 worktree. Fresh output root is `results/prefix-feedback/qualification`. Caps are300seconds per admitted unit, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, cumulative4GiB and free reserve30GiB. Root owns the canonical NONBLOCK lock and fresh F4 adapter grant.

```sh
cmake -S tools/prefix_feedback -B results/prefix-feedback/qualification/build -DCMAKE_BUILD_TYPE=Release -DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results -DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format
cmake --build results/prefix-feedback/qualification/build --parallel 2
cmake --build results/prefix-feedback/qualification/build --target format-check --parallel 1
ctest --test-dir results/prefix-feedback/qualification/build --parallel 1 --output-on-failure --no-tests=error --output-junit results/prefix-feedback/qualification/ctest.xml
```

The Python command is exact and has no default skips. A missing genuine C++ binary is a failure.

```sh
env UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv PREFIX_FEEDBACK_BINARY=/home/jake/Projects/nanopore_basecaller-next-prefix-loop/results/prefix-feedback/qualification/build/prefix-feedback /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python -m unittest discover -s /home/jake/Projects/nanopore_basecaller-next-prefix-loop/tests -p test_prefix_feedback.py -v
```

## Preparation and genuine pilot requests

The preparation command below is prospective and requires its own fresh whole-unit grant. It opens DGM/DGS bodies and hashes full references only inside that admitted worker. Its inputs are the committed configuration/manifest pins and exact role-bound paths in `config/prefix-feedback-dev-v1.json`. CPU2, RAM4GiB, AS8GiB,300seconds apply. Native mapping later needs separate RAM16GiB, AS24GiB grants. The complete hashing and preparation unit must share those exact enforced caps and terminal proof.

```sh
env UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python scripts/prefix-feedback.py prepare --config config/prefix-feedback-dev-v1.json --output results/prefix-feedback/pilot-prepare-1
```

Preparation must emit `plan.json`, four independently pinned released tensors, four release receipts, selected parent, actual T, exact quarter cutoffs, all exclusions, mapper/FAl pins and no truth access. No selection may use a positive location result. Query0 overlaps old diagnostics and cannot establish independent confirmation. Existing HG005 and native/GPU holds remain.

An exact genuine pilot runner command cannot be admitted from this cut. The proposed `Executor.run_command` callback does not match F4's public CLI. F4 currently exposes the source-only, unqualified shape below. Root will relay its corrected commit and exact keys after independent review and canary qualification.

```text
fixed UV -> python /home/jake/Projects/nanopore_basecaller-next-stock-compare/tools/stock_feedback/bounded.py run --request ABS_ROOT_GRANT --request-sha256 ROOT_GRANT_SHA256 --output FRESH_ABS_ATTEMPT
```

The grant schema is `bounded-command/1`. It binds root/cwd/argv/env, source/input pins, expected files, output roots, exact caps, clocks and a fresh nonblocking lock. F1 will adapt the producer to this public boundary without a second supervisor. Current pilot placeholders are not execution commands or qualified integration.

## Remaining acceptance gaps

The first cut has no runtime evidence. It has not demonstrated three actual prefix-derived location updates, a nonempty genuine context, reference revisions, biological accuracy or latency. Wrong-location, no-location, ambiguity, tie, no-finalist, permutation and future-tail controls are prepared but unrun. A future-tail mutation in a separate unavailable block must preserve all preceding raw batches and mapper query/state bindings. Source-root corruption must be tested separately from wrong-request-root rejection.

Full-parent disabled SEQ/Q identity is not yet a separately admitted consumer. Available-native passthrough is null and no completed call is read by inference. Genuine edits need independent reconstruction against the matched available segment and, later, complete-parent output on both strands. F2's frozen sibling policy is not integrated. F3 indel proposals are not integrated. These are follow-up work, not implied PASS.

The real-path comparison must keep matched score availability/delay for signal-only, first-snapshot fixed-policy rerank and partial feedback. Saved complete-chunk scores contain reverse recurrence. The experiment is a decoder-prefix feedback mechanism with chunk lookahead, not zero-lookahead raw-signal causality. No biological promotion follows source or CI acceptance.
