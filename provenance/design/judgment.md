# Independent design judgment

2026-10-22. Verdict: **use B as the base, with the three bounded grafts below. Design accepted for implementation; runtime and scientific acceptance remain unproved.** The task is a completed stock human benchmark, so keep one fixed runner and native metrics.

## Reviewed artifacts and scores

Read the brief and both candidates end to end. SHA-256 identities:

```text
benchmark-brief.md 6396253b0c16074b31f5f0db0ddc7c050e17a6636e706bcb1dbc96d3bdb41ef3
candidate-a.md     198d1f7185b883e3273805990f55c993afe509f8aae3c9c232fde3a4eb69548e
candidate-b.md     11f239df5ce03c22c773513f07f96a0359a8c19fae8df8ec10c2b951f2240698
```

| Criterion, 1–5 | A | B | Reason |
|---|---:|---:|---|
| Native-interface correctness | 4 | 3 | Both trace actual Dorado interfaces. A chooses stock auto batch; B invents an untested 64 policy. B's index command remains conditional on a different-version source example. A's cited effective-batch logging location is Metal, not CUDA. |
| Observable work/failure accounting | 4 | 5 | B separates a completed observation, missing-parent accounting, and scientific/metric qualification, and recognizes undetectable missing split siblings. A risks making legitimate stock filtering block all useful completion. |
| Clear scientific limits | 5 | 5 | Both retain reference disagreement as a proxy and mark biological/variant endpoints NOT VERIFIED. |
| Restartable evidence | 4 | 5 | Both preserve attempts and verify before skip. B more clearly separates observation failure from producer failure and repairs reports without GPU replay. |
| Minimal maintained code | 3 | 4 | B allows streaming full decode rather than a giant extra SAM, and uses native calmd. A's broad fixture/model-acquisition program and complete SAM retention risk delaying the actual benchmark. |
| Total | **20** | **22** | Scores assess design, not execution. |

## Three grafts and required corrections

1. **A's stock-auto starting policy.** Initial genuine HAC/SUP development smoke uses `--batchsize 0 -v`; record every effective chunk/batch pair from `dorado/basecall/CudaCaller.cpp:162` and the complete logs. Freeze the observed policy before measured repetitions. Do not infer a single batch from the request value. Any compatibility failure remains immutable before an empirical policy revision; no silent OOM retry or outcome-driven throughput search.
2. **A's clean-processing distinction, without its completion dead end.** Always retain finished stock observations with the exact absent-parent ledger and unresolved reasons. Native <5-base filtering does not identify why a particular parent is absent. Mark clean complete-processing/throughput qualification unavailable when unsupported; still complete the requested stock observation and disclose drops. Submitted signal-seconds/s is an input-work ratio, not proof every sample was successfully called.
3. **A's exact index producer provenance.** Build in a separate copy from the pinned ONT/nested minimap source, recording patches/build/binary. Use the same explicit `lr:hq`, `-I 16G`, EQX and clipping policy for FASTA/MMI parity. Reject wrong dictionary or k/w warning. If qualified MMI reuse fails, retain the failure and use the complete FASTA with indexing included in alignment wall time; do not create another index implementation.

Both designs' `config/raw-assets.json` checks and proposed finite-calibration additions are stale: the actual inspector reads only `config/assets.json` and already checks finite scale/offset. Reuse its existing `benchmark.txt` writer (first 256 of its fixed hash ranking) rather than introduce a second subset rule. Freeze the actual generated list/hash before outcomes. At review time the production `data/splits/benchmark.txt` did not yet exist; a code path is not an acquired-data receipt.

## Architectural screen

Screened against `/home/jake/.codex/plugins/pstack/skills/architect/references/design-red-flags.md`. Keep one owner of plan/attempt state and one source of asset/subset truth; duplicate raw manifests are the concrete hand-synced-list/split-ownership risk. Native producer stages are legitimate artifact/failure boundaries, but should remain a fixed private sequence, not grow stage plug-ins, an importable adapter framework, or configurable DAG. Public plan/run/verify/report verbs may share one runner; callers must not manually coordinate internal receipt transitions. Keep one execution path and one report path. Do not require a new Rust computation crate, scorer, database, multiple aligner backends, or unrelated fixture model merely to launch stock processing.

## Exact implementation acceptance

1. Readiness must retain successful `scripts/record-command.sh verify-assets uv run --frozen python scripts/verify-assets.py` and `scripts/record-command.sh inspect-signals uv run --frozen python scripts/inspect-signals.py` receipts, full decoded-signal inventory, frozen memberships/subset, verified binary/model tree identities, complete compressed FASTA/dictionary/random-access evidence, and final recursive source/submodule pins. Source HEAD alone is insufficient. Alert the user when the genuine prerequisites pass and continue existing stock authorization, including HG005.
2. Use the traced native shape: `DORADO basecaller MODEL POD5 --read-ids IDS --device cuda:0 --batchsize 0 --min-qscore 0 --trim all -v`, initially on smoke; then the frozen policy for measured/full runs. Preserve a regular-file BAM, argv, environment, exit, UTC, raw `/usr/bin/time -v`, monotonic wall, logs, header and hashes. Six full units are mandatory: three complete raw memberships × both exact model directories. No `--run-for`, input cap, `--resume-from`, integrated alignment, or hidden retry in measured units.
3. Accept untouched genuine native output and demonstrate rejection/accounting change on derived copies: truncated BAM, foreign parent, duplicate child/primary, removed represented parent, wrong model/reference identity, and altered NM. Full decode is required in addition to quickcheck. Resolve split membership through `pi`, validate native `sp/ns/ts` against input samples, and qualify genuine split output from the local compatible `tests/data/single_split_read/single_split_read.pod5` using the installed exact model; no extra fixture model is needed. Do not pass this branch vacuously if the producer emits no split. Missing one split sibling may be undetectable from membership alone.
4. Align every full stock BAM through the verified native shape `DORADO aligner INDEX BAM --threads N --no-sort --mm2-opts '-x lr:hq -I 16G --eqx -Y'`, with N frozen from the host budget. Require complete reference SN/LN, exactly one primary-or-unmapped record per basecalled child, preserved parent membership and strand-normalized primary sequence/quality. Use native Dorado summary, samtools flagstat/stats and calmd consistency; retain raw outputs and their exact denominators. Structural CIGAR arithmetic must reconcile on an inspected native fixture; avoid a new biological scorer.
5. Execute the frozen 256-parent development schedule `H,S; S,H; H,S; S,H; H,S` as fresh, serialized processes. Preserve all attempts and report planned/success/failed counts. Fewer than five qualified successful repetitions per tier leaves that baseline incomplete; a later replacement is explicit. Wall includes startup/model load/POD5 I/O/output/process shutdown; index, alignment and report clocks stay separate. Record sampled GPU telemetry, RSS, power/cache/contention limits, disk admission and reserve monitoring. No own concurrent GPU work or unfinished acquisition; preserve at least 30 GiB free.
6. Restart controls must prove verified-unit reuse spawns no producer; changed artifact/parent hash and interrupted/no-exit attempt cannot skip; observation/report failure repairs from retained BAM without repeating GPU work. Report each cohort/tier, molecule and child counts, drops, mapping/clipping/length/NM/CIGAR metrics and limits. No HAC/SUP winner/speedup, biological accuracy, Q calibration, or variant-calling claim follows.

## Checks actually run and remaining evidence

`uv run --frozen python -m unittest discover -s tests -p test_signals.py -v` exited **0: 5 tests, OK, 1.929 s**. This includes genuine POD5 decoding and negative controls for nonphysical calibration (NaN/Inf/zero scale and NaN offset), 4 kHz rate, duplicated UUID, and mutated frozen membership. These tests qualify existing inspector fixture behavior, not the acquired human signals or benchmark runner.

Independently decoded the local split-source fixture with this exact command (exit 0):

```sh
uv run --frozen python -c 'from pathlib import Path; import pod5; p=Path("software/dorado-src/tests/data/single_split_read/single_split_read.pod5"); r=pod5.Reader(p); reads=list(r.reads()); print({"path":str(p),"reads":len(reads),"records":[{"id":str(x.read_id),"samples":len(x.signal),"sample_rate":x.run_info.sample_rate,"kit":x.run_info.sequencing_kit,"flowcell_type":x.run_info.flow_cell_product_code} for x in reads]}); r.close()'
```

Observed one UUID `c31a90ab-b786-4dcd-b996-2d05d97e7e53`, 365157 nonempty decoded samples, 5000 Hz, sqk-lsk114, FLO-PRO114M. This establishes local signal compatibility; genuine emitted split BAM behavior still requires stock GPU execution.

`git -C software/dorado-src rev-parse HEAD` returned `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. `git -C software/dorado-src status --short` and `git ... submodule status --recursive` showed transient submodule changes/mismatches during active hydration; B's `source_dirty=false` cannot be claimed from that observation. Reinspect after the recorded hydration command exits. Local inspection verified native batch-zero semantics, single-string minimap options, split tags/sample bounds, summary denominators and nested minimap CLI; no executable/model/reference/GPU/MMI compatibility or human-run timing has been accepted here.

Evidence output: `/tmp/nanopore-benchmark-design/judgment.md`; input evidence: the exact candidate/brief paths above and source/tests named here. Two read commands failed because a project-relative read used the source checkout as cwd, and because the production benchmark list was absent; the former was corrected. No broken tool was observed. Test fixtures are temporary and their bytes are not retained in this judgment; the command/results and maintained tests are the available evidence. No project implementation or acceptance check was changed.
