# Final retained runtime evidence audit

Verdict is **PASS_EVIDENCE_FOR_SUBTHRESHOLD_DEVELOPMENT_CANDIDATE**. The candidate is **NOT PROMOTED**. The retained engineering and native measurement receipts support a small development-cohort improvement, below the predeclared 1% point threshold in both masks. Productive ALT support is also insufficient. This is an evidence audit, not a new biological experiment or a throughput benchmark.

Actual final measurement completion is `results/context-feedback/decision-measure-feasible-1/execution-complete.json`, SHA256 `f9fd250779bb702274a81362b242004b4ffb8fb55ec88b90515e49dc288bf397`, 3965 bytes. Controller SHA256 is `e5d6812d89617f8023b753f26d8f6b1fba193a28a6c9b93fe58acdcf6316be82`. The immutable source52 and source55 identities remain `6357128e0c6c5151001866a1f8e1fe1603807747ed38cd39919c29a42017c6ff` and `8e8607ebe49e9c990605777876f8657b0530138cf4a712c8ca42386103c92a1f`. HEAD/base remains `6a8c23e8a34d37bef76f25c30cc007bf429deae5`. Untracked source is identified by those inventories, not HEAD alone.

## Independently checked outcomes

| Mask | Native errors / denominator | Candidate errors / denominator | Relative reduction | Positive / zero-exposure parents |
|---|---:|---:|---:|---:|
| 100 | 8785 / 865579 | 8718 / 865563 | 0.760829% | 53 / 11 |
| 500 | 3939 / 439381 | 3915 / 439375 | 0.607934% | 50 / 14 |

Integer m/x/i/d totals agree across parent and block TSVs and the native summaries. Every parent has the same matched reference exposure in both arms. Insertions produce different alignment-column denominators. Per-parent block sums, aggregate rates, relative reductions and mean-parent deltas were recomputed arithmetically from retained tables. A one-count in-memory corruption failed the independent conservation check. No CIGAR or truth was re-scored.

All four parent/block bootstrap delta upper bounds against native are negative. These are technical resampling bounds from the retained native producer. The two masks share the same parents and are not independent validation. Their point reductions remain below 1%; the audit did not rerun the 2000 bootstrap replicates.

Native baseline ALT preservation is 829/829, comprising 740 SNVs, 50 insertions and 39 deletions, with zero losses in the actual paired TSV. The historical-free baseline retains 830/830, comprising 741/50/39. Changed-footprint ALT support is 0 against native and one SNV against historical free, at `ordinary/148/ordinary`. The retained footprint outputs do not satisfy the declared productive-support requirement for any class. This preserves observed baseline support; it is not F1 or whole-genome variant safety.

Both feasible arms retain ALT for all 26 withheld private witnesses, with zero loss and zero unresolved consequences. All 912 emitted private-label rows were checked against the actual qualified input labels by case, digest and event. These are retained label joins, not new variant calls or an independent biological cohort.

| Newly changed ordinary choice | Mask 100 accepted effect / exposure | Mask 500 accepted effect / exposure |
|---|---|---|
| ordinary/35/ordinary | helpful / 21 | helpful / 21 |
| ordinary/107/ordinary | unresolved / 21 | no_exposure / 0 |
| ordinary/127/ordinary | helpful / 21 | helpful / 21 |
| ordinary/164/ordinary | no_exposure / 0 | no_exposure / 0 |
| ordinary/399/ordinary | no_exposure / 0 | no_exposure / 0 |

Cases 35 and 127 are helpful in both retained masks. Case 107 remains unresolved in both. The five changes explain 37 old raw-veto edits becoming 42 feasible edits; they do not independently establish a larger gain.

## Actual producer and output custody

- The original format and engineering qualification receipts bind the current 52-file source, strict C++23 flags, actual compiler/cache/compile commands, binary `d9ffafc9b70b0d3a83a3fcf129f8c10ee60507792b5e3772a79fd0e93c8742e3`, 2941 native controls, all 12 Python controls and one structured CTest case with zero skips. No check was rerun.
- Price covered all three scopes. Inference covered disjoint 1, 21 and 346 cases. All three units replayed the same 368 cases and all six historical roles; their actual historical TSV bytes match. Actual inference completion precedes the observer intake. Source, fixed thresholds and the pre-outcome comparator clarification remain unchanged.
- The feasible arms share one exact full-parent SAM, SHA256 `e451d61479f5bf25205265c0a11d7ef0d8e3c3f3c7f54ffa5b5eb84604fa9ece`. All 64 normalized primary SEQ/Q records match the actual native input for the disabled arm. Both free and feasible emissions reconstruct from those native records and their actual edit ledgers, preserving untouched SEQ/Q and assigning uncalibrated `!` to replacements. Edit counts are 42 feasible, 37 old raw-veto, 9 historical free and 0 disabled. Historical-free SAM bytes also match the retained original free SAM. Private frames are excluded from parent emission.
- The single new complete-parent mapper chain preserves all 64 primary SEQ/Q records. Native measurement has both feasible aliases and both masks against native and historical free, actual variant observation/comparison outputs, and the frozen native ALT census. There was no duplicate mapper execution in this audit.
- Actual kernel records at worker entry and exit show CPU quota 200000/100000, RAM 16 GiB, address space 24 GiB and swap zero. The worker verified the retained parent canonical lock before substantive work. Terminal records show exit 0, no error, empty/unloaded whole-worker cgroup and terminal launcher tree while lock custody remained held. Final owned output was 30,346,462 bytes, below 512 MiB, with over 30 GiB disk free.
- Whole-worker GNU time records 1:00.91 elapsed, 49.86 user CPU seconds, 9.05 system CPU seconds, 12,317,404 KiB peak RSS and zero swaps. These describe this bounded unit, including synchronous hashing and validation; they are not a basecaller performance benchmark.
- The audit checked 42 distinct stage receipts, including whole-worker raw8 and the separately named union linked-runtime receipt. Actual argv, cwd, recorder identity/symlink, UTC clocks, exit status, stdout, stderr, GNU-time CPU/wall/RSS and launcher cleanup are retained and linked. Nonempty stderr is preserved rather than treated as a hidden failure. The coordinator reported its outer CLI closed 0; the independently checked durable controller evidence proves worker/service and launcher terminal status.
- The completion files are written last and synced. No rename-atomic publication guarantee is claimed.

## Completed retained-union diagnostic

Actual union QUALIFY2 completion is `c90866321f4785e7340bfc43fc372289475d3784aa654bf3860529ae705d121d`. Actual DIAGNOSE1 completion is `750f2475e0e1d70efd8a59d5f038b61583f177e7f248802e3df7ea9f0c4eac7a`. Binary SHA256 is `fb3c0cb01577798a22c5041604d6f93c4536a3d2af815c5d427f462b9b43e64d`. The current formatted source63 identity is `2d5bc2d87edb398af03015fe36465cc2a613b64af174800ec5b0229b334b20cd`. The actual 37-source witness, compiler and both formatter cache entries match configuration. All three formatted C++ files have the same token sequences as the exact pre-format reviewed cut. Native controls report 189, structured CTest has zero skips, and strict actual compile commands are retained.

All 368 cases replay six historical roles, use zero new neural calls and have zero cap/empty flags. All 1104 actual diagnostic rows match the expected native or historical-free role. The retained-union neural maximum equals historical free for every ordinary case and all 368 cases. This closes the finite retained-pool comparator diagnostic and permits reuse of the already verified historical-free full-parent output. It does not prove a global neural maximum or quality calibration. No second full-parent alignment is needed for identical choices. The earlier foreign-lock refusal is preserved; the successful qualification is a separate actual attempt.

## Bounds, failed observations and limits

The conservative cumulative read upper bound, including failed attempts, metadata rechecks and the final packaging allowance, is **104,442,212 bytes**, below **104,857,600 bytes**. Ordinary files were limited to 8 MiB. Root explicitly authorized one exact-file exception for the 16,085,465-byte upstream native SAM, SHA256 `db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe`. It was streamed once and only the expected 64 primary records were parsed. Large reference/index/corpus/model inputs, the 429 MB Dorado binary and oversized libraries were not independently rehashed; their producer-bound hashes and current sizes are identified in the snapshot. Runtime dependency evidence is actual ldd closure, not loaded-memory maps or a full dlopen census.

The initial guard correctly refused the native SAM before the explicit exception. A later audit timestamp-key error occurred after the stream hash and 64-record identity checks passed. Its exact failed script is retained, and the successful read was not repeated. Another supplemental audit reached the format-token check after its metadata assertions passed, then an overbroad raw-literal guard matched a normal message ending in OR. The final small check corrected that reviewer guard and verified all three token sequences. The initial stage index also keyed by name; the distinct union linked-runtime receipt was subsequently checked separately. These are disclosed reviewer observation failures. No native producer or scientific computation was replayed. `runtime-final-audit-failures.json` retains the failed checks.

The original source and execution evidence remain intact. No implementation, acceptance check, manifest, CI file or other worktree was edited. Only assigned runtime-final evidence and its metadata scripts were written. No product module was imported, no native producer/tool was invoked and no neural, GPU, mapping, resampling, download or fresh truth-scoring work ran.

This audit accepts the retained matched development observation. It does not promote the candidate, establish independent validation, calibrate replacement qualities, prove private-allele safety beyond the retained witnesses, or validate the larger future research program.

## Exact audit commands

All commands used cwd `/home/jake/Projects/nanopore_basecaller-context-feedback-decision` and the environment below. The first command was initially run with `-i`; its guard failure is retained separately. The corrected main command, final seal check and distinct receipt check exited 0. The two supplemental failures exited 1 and are retained.

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/reviews/runtime-final-audit.py
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/reviews/runtime-final-completion-attempt-1.py
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/reviews/runtime-final-completion-attempt-2.py
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/reviews/runtime-final-seal-check.py
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/reviews/runtime-final-last-receipts.py
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/reviews/runtime-final-package.py
```

`runtime-final-pins.json` binds this report, the final verdict/receipt evidence and the exact metadata scripts. `runtime-final-snapshot.json` contains the full per-stage observations and large-input exceptions; its already observed pin is carried forward without another large read. There were no broken tools. Initial missing-result/metadata filename lookups, display truncation and the reviewer check failures are observation gaps repaired or explicitly bounded above.
