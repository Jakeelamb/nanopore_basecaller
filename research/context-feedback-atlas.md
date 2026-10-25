# Retained-candidate diagnostic, first source unit

This development unit preserves the C++ candidate diagnostic and its actual query-0 and first32 handoffs before boundary corrections. It does not improve the basecaller or complete the context-feedback program. The next isolated unit must correct recursive custody validation and a reference-coordinate boundary defect before running the complete cohort. The previous v2 accuracy result remains below the unchanged 1% target.

The source is in `tools/context_decoder/study/`, `tools/context_decoder/program_inputs.py`, `scripts/context-program.py`, `config/context-program-v1.json` and their two Python control files. C++23 matches pinned Dorado revision `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. Python coordinates tools and validates evidence. A separate inference executable cannot link the truth evaluator. Input packets are written before reference fragments and private labels are loaded. The evaluator emits diagnostics, never a truth-selected calling output.

The alignment diagnostic retains every optimal global edit alignment across the complete bounded guard. It reports direct minimum/maximum masked M/X/I/D/error counts. It does not add independent class extrema to estimate total error. Ambiguous core boundaries stay unresolved. Private calls distinguish exact ALT, exact REF, other and unresolved. These local endpoints are separate from whole-parent remapping accuracy and do not estimate an attainable improvement ceiling.

## Executed evidence

All paths below are relative to this immutable worktree. Generated inputs and results remain ignored.

| Unit | Evidence | Outcome |
| --- | --- | --- |
| Engineering | `results/context-feedback/v3-engineering-1/execution-complete.json` | Strict Release C++23 build and formatting, CTest, 7,287 assertions over 1,275 exhaustive alignments, 33 Python controls, zero skips. |
| Whole-tree timeout | `logs/context-feedback/program-runs/control-check-1/result.json` and `logs/context-feedback/program-supervisor-v3-controller-control-1/terminal.json` | A separate-session child ignored TERM, its cgroup became terminal after escalation, and the unrelated sentinel survived. This expected failure is not a normal scientific completion. |
| Genuine preparation | `results/context-feedback/v3-prepare-q0-1/prepared/manifest.json` | Original-location v2 auditor and historical evidence checked at production; one batch reference extraction; inference/truth packets separated. |
| Genuine evaluation | `results/context-feedback/v3-evaluate-q0-1/native-atlas/complete.json` | Historical replay exactly matches the truth-free executable; 148 unique candidate sequences. |
| First32 | `results/context-feedback/v3-prepare-first32-2` and `results/context-feedback/v3-evaluate-first32-1` | 22 retained native cases, 15 parents, 3,271 unique strings; historical replay passes. Two contextual alternatives are accepted and five blocked. |
| Coordination refusal | `logs/context-feedback/program-supervisor-v3-prepare-first32-1/refused.json` | Another owner's native build held the canonical lock. No scientific producer started. |
| Full preparation failure | `logs/context-feedback/program-supervisor-v3-prepare-all-1/terminal.json` and its `stderr` | Terminal failure before reference extraction or packet output. A center endpoint touches a native insertion and is incorrectly required to map to a reference base. |

The engineering outer receipt SHA256 is `3a484da7f852614fd2c6b6d5883752bf654e28f7fa41d7dd0de675ca84479aff`. Its closed 28-file inventory is `bca738ce49583248219110430806b6bdf2d625566b03d2e82c15de91b0076a2a`. Query-0 cases SHA256 is `6cb703748d825f2cfb1d92bd152d32509a437335c293c345280ec7309474b8c1`.

Actual controller commands used `UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv`, `uv run --no-sync python scripts/context-program.py`, a fresh exact admission JSON, and the raw `record-command.sh` wrapper. Phases were `qualify`, `prepare --scope query0`, and `evaluate --scope query0`. Preparation/evaluation linked the engineering output through `--qualification`; evaluation linked preparation through `--prepared`. Every unit had its own `--output` and `--admission`. Actual argv, cwd, UTC clocks, exit, stdout, stderr and GNU time remain in `logs/context-feedback/recorder-root/logs/`. The first formatting helper attempt failed before formatting because its recorder directory was absent; its retained retry succeeded. Failed attempts were not overwritten.

Successful units used a nonblocking canonical host lock and external whole-worker systemd supervision with at most 300 seconds, two CPUs, 4 GiB memory, 8 GiB address space, zero swap, a 4 GiB aggregate output threshold and 30 GiB free-disk floor. Lock release follows owned-cgroup and launcher terminal observations. Completion is written last and synced, not rename-atomic.

## First real diagnostic

Query 0 is shared exposed HG002 development. Under mask 100, native has two local deletion errors and the accepted contextual candidate has zero. The saved contextual margin is approximately 0.977188. Across all 148 strings, 20 are conservatively helpful, 49 harmful, 28 neutral and 51 unresolved relative to native. These are alternative sequences for one case, not 148 independent observations or 20 corrected errors. Mask 500 has no exposure. No private event occurs in this query. It cannot establish variant safety or whole-read accuracy.

## Review and unresolved reuse defect

Independent same-family source reviews and actual runtime reviews are retained under `logs/context-feedback-program/reviews/`. They are not cross-family reviews. Math review found no demonstrated algorithm defect in this cut and independently reconstructed the query-0 result. Source checks and engineering tests do not establish biological qualification.

Boundary review found that `completed(prepared)` checks flat packet pins but does not recursively traverse `inference-manifest.proofs` back through the original v2 executions and raw stage receipts. Those receipts were checked during the actual preparation and remain present. Removing a nested original receipt after preparation would not necessarily make this consumer reject reuse. The current source is therefore not accepted as enforcing complete historical custody on reuse. The preparer's completion record also needs an anchored file census rather than relying solely on an unpinned completion file.

Full preparation additionally exposed an invalid coordinate assumption. Exact left/right anchors define a reference core even when its first or last emitted native base is an insertion. Requiring those emitted bases to map is too strict. Derive the core from the reference anchor boundaries and test both orientations with boundary insertions/deletions. Keep optimal-alignment ambiguity reporting intact.

Preserve this worktree and successful producers byte-for-byte. Implement the corrections in the next isolated source unit, with missing-linked-file rejection controls and exact original auditor semantics. Reuse the genuine retained artifacts without replaying neural or graph producers. Full-cohort diagnostics remain pending. This report does not close the original catalogue-bridge unit.
