# Independent review of the retained-score coverage diagnostic

Verdict on 23 October 2026. **PASS for the identified retained-score diagnostic. No biological or speed claim is established.** Source inspection, a fresh execution of the actual diagnostic, and a separate Python reconstruction agree. This is an independent same-family review, not a cross-family panel.

The worktree is `/home/jake/Projects/nanopore_basecaller-coverage`, branch `experiment/retrieval-coverage-diagnostic`, at HEAD `ae423705147cd61e1290c426ec40b2e09a274780` plus the uncommitted diagnostic source and config. The frozen implementation is identified by `logs/hypothesis-coverage/final-source-executable-pins.sha256`. The diagnostic source SHA256 is `7bfab260b0e64f04ab291039fd59635530c5bacfa1a721f485a943735273cbe3`. Its actual executable SHA256 is `abae5602325126181a32acaf848c452f6ad8af1f41a2a8cbf406ef1a6d8d17f5`.

The reviewed final result is `results/hypothesis-coverage/final-v1/result.json`, SHA256 `e25dae6517fbeca588125a1fe012f5aea9f615466c1ac7b5f9fb963987dcf4f7`. The adjacent `windows.jsonl` and `pins.json` are part of the evidence. Source pins were rechecked against the actual source, config, wrapper, upstream decision/input modules, and executable.

## Exact executed evidence

The reviewer owns only this report and review evidence under `/home/jake/Projects/nanopore_basecaller-flank/logs/flank-review/`. No implementation, stock control, protocol, or maintained acceptance check was edited.

From `/home/jake/Projects/nanopore_basecaller-flank`, the exact orchestration commands were:

```sh
uv run --no-sync python logs/flank-review/run_coverage.py
uv run --no-sync python logs/flank-review/run_coverage_recovery.py
```

The first command acquires the canonical stock host lock with a bounded 10-second wait. Under that lock it executes the actual retained binary from the coverage worktree:

```sh
/home/jake/Projects/nanopore_basecaller-coverage/logs/hypothesis-coverage/hypothesis-coverage config/hypothesis-rank-dev-v1.json /home/jake/Projects/nanopore_basecaller-flank/logs/flank-review/20261023T170556Z-coverage/native-rerun
```

The diagnostic exits 0. All three regenerated files are byte-identical to the original `result.json`, `windows.jsonl`, and `pins.json`. The native stdout reports 331 scored rows, 120 exclusions, 47,230 old hypotheses, 3,118,978 expanded hypotheses, zero added panel hypotheses, four argmax changes and zero emitted changes per policy, 614 source artifacts checked, and 796 verified pins. Its raw output, time, command, clock, and exit remain in `logs/flank-review/20261023T170556Z-coverage/`.

A separate Python reader joins the actual old and new row files by query index and UUID. It verifies every inherited sequence, graph-presence bit, and f64 likelihood bit, then derives linear-reference membership from the pinned reference span. It independently recomputes all four binary-class maxima, finite-policy argmax and gate decisions, and complete parent SEQ/Q assemblies. It parses and compares all 614 actual source SAM artifacts to find exact output reuse matches. It does not inspect truth outcomes or rerun any scientific producer.

The first reviewer projection exits 1 at its final negative-control message assertion. The native checker correctly rejects the corrupted input with `size/hash mismatch`, while the reviewer expected `pin mismatch`. That failed attempt and its exact frozen reader remain intact. Only the reviewer-owned wording assertion changed. The recovery reuses the successful native rerun artifacts and finishes with exit 0 at `2026-10-23T17:07:24.754451+00:00`.

The completed independent result is `/home/jake/Projects/nanopore_basecaller-flank/logs/flank-review/20261023T170718Z-coverage/review-result.json`, SHA256 `416547fe7e6f52a81a3457104e3341a060ca9664f0bf91fc21fccdc8b6c25c2d`. Its frozen reader SHA256 is `413f2cd5f2b1ae8d6c08602718ada3e51b0fe693b6f82a05e24f58c39af7193b`. Both attempts preserve command receipts and raw output. The wrapper uses one CPU, a 4-GiB address-space cap, a 120-second CPU cap, and the 30-GiB free-space floor. No new GPU, tensor, scalar-score, or neural work ran. The final review data checks ended well before 17:15 UTC.

## Independently verified result

| Check | Observed result |
| --- | --- |
| Original scored hypotheses inherited exactly | 47,230 |
| Expanded scored hypotheses | 3,118,978 |
| Added hypotheses | 3,071,748 |
| Added graph-present hypotheses | 0 |
| Rows joined | 451 unique query indices and UUID matches |
| Original exclusions preserved | 120 |
| Graph-absent best score changes | 10 |
| Graph-present best score changes | 0 |
| Linear-reference-absent best score changes | 4 |
| Linear-reference-present best score changes | 0 |
| Argmax changes per registered policy | 4 |
| Edit-flag or emitted-window changes per policy | 0 |
| Old/new/actual expanded full-parent identity | All 64 UUID/SEQ/Q records for each policy |
| Actual source SAM artifacts independently compared | 614 |

The source maintains separate old/new inherited rows and checks f64 bits, not approximate equality. Native-first and lexical ties are explicit. The four finite policies use their declared margins and deficits. Historical zero-deficit policies remain separate. Complete parent reconstruction uses unchanged baseline Q outside edits and `!` within edited cores, then compares actual saved outputs.

The independent reader reproduces the three actual source-output matches. Native preservation and reference-free match source artifact `a2f7cdb61c14d901095f1c65dd5ed8b716bd12546feb993d9959813f411f54a6`. Panel matches `61354b3522e0c97bd8cc22bf7803672992e03acfe41066691f40844ba8f1d283`. Linear matches `ffcfaba4e571a74bbeeec4efce1247177f2753fde59bb1e9c3646512879551a6`. This is full map equality, not a count or filename comparison.

The public native negative control changes the old cohort's expected decision-file checksum in a retained copied config. The actual diagnostic exits 1 with `Error: size/hash mismatch ...` and produces no result file. The independent inheritance checker also rejects a one-ULP mutation of an inherited likelihood. Source review and the retained terminal test receipt cover improving added hypotheses, native/lexical ties, and changed-score rejection. The same-source build receipt reports all three Rust tests passing, formatting, strict clippy, and the release build. These historical tests were inspected, while the genuine diagnostic and separate data reconstruction were freshly executed.

## Findings, limits, and next step

No blocking engineering defect was found in this diagnostic or its final result. The initial reviewer-only rejection-message mismatch is resolved and preserved as a failed evidence attempt. No broken external tool prevented completion.

The result disproves complete score saturation of this finite proposal expansion. Some added graph-absent alternatives have better likelihoods. Their ranking changes do not cross the registered emission conditions. It therefore supplies no evidence of an expansion benefit in emitted reads. The four changed argmax cases are below the 0.5 objective margin. General statements about all candidate sequences, arbitrary weights, or likelihood correctness would exceed this evidence.

The source's binary-class argument is valid in real arithmetic for fixed classes and unchanged class representatives. It is not a proof for extreme finite f64 weights, rounding boundaries, a continuous prior, altered neural context, or a different hypothesis set. Full signal-likelihood correctness and private variants outside finite H remain untested.

An exact emitted-output match permits reuse of an existing deterministic downstream observation only when its mapping, reference, scorer, cohort, and actual input provenance also match. This review does not inspect endpoint values. It does not establish biological accuracy, ALT preservation, Q calibration, speed improvement, independent signal evidence, or generalization. Historical validation and HG005 are excluded from this diagnostic's selection inputs.

The next informative intervention should change and predeclare the suspected likelihood/context bottleneck while keeping controls and evaluation boundaries fixed. Reobserving the unchanged outputs cannot demonstrate an expansion gain. Lowering a gate would be a different intervention requiring its own safety evidence.

Prove It Works required the actual retained rows, complete outputs, and negative controls. No further delegation occurred. UV created the coverage worktree's ignored `.venv` during a small read-only projection; no tracked source changed as a result.
