# Independent benchmark implementation review

Verdict: **NEEDS CORRECTION** at the reviewed file revision below. The 17 focused tests pass, but the real reference-receipt handoff is incompatible, and the runner can lose input census and failure/current-verifier accounting. No GPU Dorado, genuine Dorado split, full-reference alignment, or scientific endpoint is qualified by this review.

Reviewed on 2026-10-22 against `research/benchmark-brief.md`, `research/benchmark-design.md`, the protocol, and the existing producer interfaces. Ownership was limited to this evidence file; implementation and acceptance tests were not changed. The repository has no commit yet: `git rev-parse --verify HEAD` exits 128 (`fatal: Needed a single revision`). File SHA-256 values identify the reviewed artifact:

| File | SHA-256 |
| --- | --- |
| `scripts/benchmark.py` | `8f22ddb91482e41ec233f56ac25ac474c8c4d7034eaa4f4e67cbab319600d086` |
| `config/stock-benchmark.json` | `665f4a2fdcf1f1f8ef6bca80123ee91386a55f4e3feaf596895822e1cbbc4ae9` |
| `tests/test_benchmark.py` | `62b77f1bdb3305d1eb48076d6cf5c93d40ec30300d3066c969c6b650742420a1` |
| `research/benchmark-commands.md` | `3e5eafc70ea1de45c095814bfeb80ea741ba62b424a6bc0ac5deba2995fdca73` |

## Reproduction and evidence

Commands run from `/home/jake/Projects/nanopore_basecaller`:

```sh
scripts/record-command.sh benchmark-review-tests uv run --locked python -m unittest discover -s tests -p test_benchmark.py -v
scripts/record-command.sh benchmark-review-replay-check bash logs/20261022T202835Z-benchmark-review-replayable-HXxcbr/command.sh
sha256sum scripts/benchmark.py config/stock-benchmark.json tests/test_benchmark.py research/benchmark-commands.md
```

The first command exited 0: **17 tests, OK**, with no skipped tests, in 1.264 seconds reported by unittest. Its retained recorder directory is [`logs/20261022T202436Z-benchmark-review-tests-WXNCvV`](../logs/20261022T202436Z-benchmark-review-tests-WXNCvV/). `stderr` contains each result; `exit-status.txt`, UTC clocks, and `time.txt` preserve execution evidence.

The second command exited 0 and reran the independently constructed controls. The complete replayable Python `-c` argument is retained verbatim in [`logs/20261022T202835Z-benchmark-review-replayable-HXxcbr/command.sh`](../logs/20261022T202835Z-benchmark-review-replayable-HXxcbr/command.sh); no reproduction-script file or test was added. The verified replay's raw results, stderr, clocks, and exit are in [`logs/20261022T202844Z-benchmark-review-replay-check-Bgw6ly`](../logs/20261022T202844Z-benchmark-review-replay-check-Bgw6ly/). Its controls use temporary directories and the existing preparation fixture with its existing mocked external commands. Only the GPU CSV, generic process execution, and samtools tests are live native observations; these are not genuine Dorado outputs. Initial explorations are retained in `logs/20261022T202634Z-benchmark-review-controls-l3tCrZ` and `logs/20261022T202736Z-benchmark-review-restart-WmUMjX`; their stdin scripts were not captured by the recorder, so use the replayable command above.

Environment evidence is [`logs/20261022T202904Z-benchmark-review-environment-rtqfR0`](../logs/20261022T202904Z-benchmark-review-environment-rtqfR0/): POD5 **0.3.49**, samtools **1.24**, minimap2 **2.31-r1302**. At that observation, the Dorado binary, signal inventory, asset lock, qualified-reference receipt, and qualified-index receipt were absent. The source checkout itself was inspected at `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`, with an empty `git status --porcelain --ignore-submodules=none` result.

## Findings

### P1 — Real reference producer receipts cannot enter preparation

**Location:** `scripts/benchmark.py:49`, `scripts/benchmark.py:54`, `scripts/benchmark.py:307`; documentation contract at `research/benchmark-commands.md:11`.

`prepare-reference.py:23-38` emits repository-relative pin paths. `check_pins()` compares those dictionaries directly against `pin()`, which always produces absolute paths. Thus an unchanged genuine receipt is rejected as changed evidence. The commands document instead demands absolute paths, which conflicts with the maintained producer.

**Observed control:** create a real small FASTA, calculate its actual size and SHA-256 with `pin()`, replace only its path with the producer's `path.relative_to(root)` representation, and call `check_pins()`. It raises `Changed evidence: tmp.../reference.fa`, despite unchanged bytes.

**Required verification after correction:** accept an unchanged receipt emitted by the actual reference producer, then reject a changed referenced file. The existing preparation test manufactures absolute pins (`tests/test_benchmark.py:203-205`) and therefore misses this integration failure. Preserve one consistent producer/consumer path contract.

### P1 — Full membership may omit inventoried molecules and still appear complete

**Location:** `scripts/benchmark.py:78-83`, `scripts/benchmark.py:329-343`, `scripts/benchmark.py:479`.

`parents()` filters inventory rows to the already selected IDs before checking membership equality. Preparation never compares a full-role membership file against the complete role inventory, and it pins `signal-inventory.json` without reading or validating its census or membership hashes. An accidentally shortened full membership list therefore defines its own smaller denominator; the output can represent every planned parent and receive complete-work qualification while an inventoried molecule was never submitted.

**Observed control:** add development UUID `00000000-0000-0000-0000-000000000004`, with 777777 samples, to the existing preparation fixture's inventory while leaving its membership list untouched. Preparation succeeds and `full-development-hac` contains **1 planned parent despite 2 development inventory rows**. The control invokes the existing full preparation test and its external-command mocks; it does not claim actual human inputs were omitted.

**Required verification after correction:** remove one UUID from a frozen full-role list while preserving the inventory and signal receipt; reject preparation. Also bind the accepted metadata/signal inventory to the acquired POD5 identities. The current successful test explicitly accepts non-POD5 placeholder raw bytes and never proves that binding.

### P1 — A failed current verification can leave a stale successful report

**Location:** `scripts/benchmark.py:568-578`, `scripts/benchmark.py:594`, `scripts/benchmark.py:636-638`.

`report()` trusts an observation's stored status after checking only its plan and listed pins. It neither requires the current `verifier_sha256` nor accounts for a newer `observation-failure-*.json`. When verification fails after a verifier correction, `main()` records that failure and calls `report()` without retiring the prior observation. The unchanged old artifacts can therefore remain reported as verified and included in timing success counts.

**Observed control:** an observation whose verifier hash is 64 zeroes remains `unit_status: verified`, `successful: 1`, after a newer failure record identifies the actual current verifier. This is a direct report-path control with a real generic producer receipt; the changed verifier/failure record is constructed, not an executed Dorado re-verification. The source trace above establishes how the CLI creates the same stale-observation situation.

**Required verification after correction:** retain successful native producers, but make a current failed or missing observation verification unavailable in the report. Rechecking under a new verifier must be explicit and successful before the old observation contributes a verified timing result.

### P2 — Model pinning establishes future stability, not initial stock identity

**Location:** `scripts/benchmark.py:295-299`, `scripts/benchmark.py:323-328`, `scripts/benchmark.py:418`.

The downloaded model archives are pinned, but the independently scanned model directories are not compared with those archives or an extraction receipt binding their contents. Any tree with `config.toml` is frozen as the initial model; the BAM check later validates only the model basename in `@RG DS`. A model altered before preparation can therefore be labeled as the requested stock model.

**Observed control:** existing preparation accepts `config.toml` containing only `fixture=true`, without any model weights. This demonstrates that this gate does not authenticate a stock model; it does not demonstrate an actual modified vendor model running on the GPU.

**Required verification after correction:** bind the prepared tree to the verified stock archive contents or an equally concrete extraction record, and reject a changed extracted model file before a new plan is accepted. The generic changed-model-tree-membership test only protects changes after freezing.

### P2 — Native index parity evidence is accepted as an arbitrary truthy value

**Location:** `scripts/benchmark.py:303-311`, `research/benchmark-commands.md:7`.

Preparation requires only that `index['parity']` be truthy. It does not check the parity entries' statuses, input/output pins, genuine mapped work, or coverage of both stock tiers. Moreover, the maintained reference producer stores parity input/output pins nested under `parity`, while its top-level `pins` contains only the MMI. The runner checks only the top-level pins. Changing or deleting the parity artifacts can therefore escape plan validation.

**Observed control:** preparation and subsequent `load_plan()` accept `parity: ['fixture receipt']`. This is the existing test fixture's value, also printed by the replay. The missing nested validation follows directly from the producer/consumer source, rather than a real parity run.

**Required verification after correction:** accept genuine native FASTA/MMI parity receipts for both tiers and reject missing or changed referenced parity artifacts. The runner need not invent a new scorer or workflow layer.

### P2 — A successful retry removes the earlier failure from report counts

**Location:** `scripts/benchmark.py:584-599`.

The stage directory keeps every attempt, but the report projects only the most recent receipt. Consequently `failed_basecall` counts current failing units rather than failed basecaller attempts. After an explicit retry succeeds, the earlier failure disappears from the report's failure count, even though its receipt is preserved on disk. Five later successes could yield a baseline with zero reported basecall failures after an earlier failed measured attempt.

**Observed control:** run a real generic producer that exits 7 on its first invocation and 0 on an explicit same-command retry. Retained exits are **[7, 0]**; the report returns `successful: 1`, `failed_basecall: 0`. This is native process/receipt execution, not a Dorado performance claim. The reported 2-second observation value is constructed solely to exercise counting and is not a measured benchmark result.

**Required verification after correction:** retain unit completion counts and expose all failed/interrupted measured attempts, including those superseded by successful explicit retries. No automatic retry was observed; the defect is report accounting.

### P2 — Supported GPU resource values are discarded

**Location:** `scripts/benchmark.py:251`, `scripts/benchmark.py:463-470`.

The sampler requests `--format=csv`, which includes units in each value. The parser accepts only bare `[0-9.]+`, rejecting every normal memory, utilization, and power value. This marks available observations unavailable and prevents the promised resource summary.

**Observed exact native query:**

```sh
nvidia-smi --query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw,temperature.gpu,clocks.sm --format=csv
```

The replay saw `0 %`, `294 MiB`, and `6.84 W`; all three returned `False` under the runner's numeric predicate. Raw samples remain retained, so this is a reparable projection failure and does not require another producer run.

**Required verification after correction:** pass an actual sampler row through the projection and assert its memory/utilization/power numbers; preserve unsupported-field availability separately.

## What passed and what remains unproven

The focused suite supplies meaningful negative controls for foreign parents, duplicate primaries, empty output, model/version labels, split interval overlap/bounds, strand-normalized sequence/quality, reference dictionary changes, NM arithmetic, CIGAR/query mismatch, truncated/interior-corrupt BAM, summary length mismatch, pinned evidence changes, failed stages, and interruptions. The MD control actually runs samtools calmd and observes the reference-recomputed tag changing. The CIGAR control verifies the alignment-column denominator, clipping exclusion, and primary aligned-query counts. Source inspection confirms native Dorado summary skips secondary/supplementary records, matching the intended primary-child join.

These tests do not close genuine Dorado production. They construct Dorado headers, tags, and summary rows; the preparation test mocks source/version/native commands and accepts placeholder raw/model/reference/index bytes. The test named `test_native_summary_join_rejects_parent_and_count_changes` changes only sequence length, so its name does not establish a parent-mutation test. Native qualification is correctly designed as a separate required gate, but it has not run here.

Unverified runtime gates: installed official Dorado and model extraction identity; all-human-POD5 decoded signal and complete UUID census; genuine splitting with these exact model versions and valid native `pi/sp/ns/ts`; complete reference and publisher indexes; native FASTA/MMI parity for both tiers; the native rejection controls; GPU smoke work, effective batch/chunk settings and compatibility; all ten fresh-process interleaved timing observations; all six full shard/model outputs; workload contention and 30 GiB reserve during those runs; and real peak resource/throughput observations. Source inspection supports the fixed `H,S; S,H; H,S; S,H; H,S` schedule, explicit paths/options, separate native clocks, exclusive runner lock, and retained stage attempts, but cannot establish their eventual runtime behavior.

The reference-disagreement endpoint is explicitly a mapped-primary-child reference-agreement proxy. Biological base accuracy, biological quality calibration, variant-aware accuracy, and variant-calling accuracy remain **NOT VERIFIED**. Split sibling completeness is also explicitly unobservable from parent membership alone. This review found no demonstrated denominator defect in the primary EQX/NM/calmd calculation; supplementary reference recalculation is not the reported proxy endpoint.

No required runtime tool was broken during the local checks. The missing git commit and absent acquired/qualified artifacts are evidence limitations. An exploratory search used a nonexistent `dorado/summary` path (exit 2); the correct `dorado/hts_writer/SummaryFileWriter.cpp` was subsequently inspected. No broader acquisition suite was run because it was outside this assignment and under concurrent repair.

## Scoped comment audit

Applied only the exception rules in `/home/jake/.codex/plugins/pstack/agents/comment-sicko.md`; no source comments were changed. Seven removable narration comments/docstrings were found:

| Location | Action |
| --- | --- |
| `scripts/benchmark.py:1` | Delete module narration. |
| `scripts/benchmark.py:92` | Delete internal parser narration; native calmd ownership is already expressed by the actual call path. |
| `scripts/benchmark.py:227` | Delete internal reuse narration. |
| `scripts/benchmark.py:485` | Delete internal control-generation narration. |
| `tests/test_benchmark.py:1` | Delete module narration. |
| `tests/test_benchmark.py:226` | Delete narration of the following changed-reference assertion. |
| `tests/test_benchmark.py:253` | Delete narration of the following projection deletion/reuse operations. |

Deletion candidates: **7**; performed deletions: **0**; `MUST KILL` implementation/refactor flags: **0**. None documents a public API contract, license, suppression, external platform constraint, or issue/RFC restriction. Configuration has no comments; prose documentation is outside the code-comment audit. No child agents were used.
