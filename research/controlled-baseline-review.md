# Controlled baseline acceptance review

Accepted on 2026-10-23 UTC for unchanged stock execution, controlled process timings, and the bounded GIAB-supported reference-identical accuracy endpoint. An independent native Sol verifier checked the implementation and actual artifacts separately from their authors. This was same-family review.

Read the [results](controlled-baseline-results.md), [machine-readable evidence](../provenance/verification/controlled-baseline-20261023.json), [method](controlled-benchmark-plan.md), and [reproduction commands](controlled-commands.md). The earlier stock report remains unchanged historical evidence.

## Accepted identities

| Artifact | SHA-256 |
|---|---|
| Frozen stock plan | `1c995eba5d6454a6ef8a8fc6dcd767fd9e9aead811389da38f3906ddaf6815e0` |
| Native runner | `39cb086598e5de0ae8c8d113f86c06a2d7721f34799e7cb258ea5dee744fb9fc` |
| Accuracy orchestration | `b5c6da542cdcb81689a93f5c7667e2933a91aedb5bb4f172e348c3de6ec3b49b` |
| Retained Rust scorer executable | `cad645ab14c775822cdab6a953879037a5b8291ec6efa1e4cad718fa82303a5c` |
| Exporter | `c7f5886294685f69a74312c8ff0085d9782a769b53fab44880d8bd83ff4e6321` |
| Results Markdown | `870cf4649ef6e7438673e39bc2fc00873ac5cf6b8bf0e5b22f52f86c5b5c3488` |
| Evidence JSON | `514ad2b0c2c61092e583c1a5c63d5f02577698dbc02644223ca0210b05f21fed` |
| Retained independent accuracy review | `729b3836799e7f08e24390ebe8907f007b807e01dd3ca91c8c552681f532b9f7` |
| Retained independent report review | `af70838e3b62ce1fc2198e4c95f2e79df09c3f58da4922649f1314a54659bf36` |

The scorer executes a retained read-only copy with retained source identities. A later build cannot silently replace its producer. No candidate basecaller or model was selected or modified.

## Native execution and timings

All 19 observations passed their current verifier: six full jobs, ten timing jobs, two smoke jobs and one genuine split fixture. The auditor checked 249 successful measured stages, including the two additional coordinate-confirmed validation IUPAC checks, and all 21 native qualification controls. Raw commands, working directories, stage identities, UTC/monotonic boundaries, GNU time exits and resources, required telemetry and input/output membership agree. The 298 retained stock-package attempts comprise 295 successful processes and three expected truncated-BAM rejection processes; no measured basecall failed or was silently replaced.

The native/plan/qualification audit rehashed 14,982 pin entries covering 36,309,179,197 bytes. Every retained hash matched. Full-cohort SUP represents all 20,954 submitted parents. HAC represents 20,937, with exactly 17 HG005 parents absent. Native filtered-output events do not establish a cause for each missing UUID; complete-work qualification for that unit remains unavailable.

| Tier | Five raw native basecall clocks, seconds | Median | Range |
|---|---|---|---|
| HAC | 35.36, 34.93, 35.63, 35.40, 35.45 | 35.40 s | 34.93–35.63 s |
| SUP | 173.95, 174.33, 173.36, 173.30, 173.04 | 173.36 s | 173.04–174.33 s |

Every repetition represents all 2,608 development parents and 641,769,607 signal samples. All ten observer and native windows begin after the incident's conservative 00:33:00 UTC stop bound; the earliest observer begins at 00:37:34.960 UTC and its native process at 00:37:37.638 UTC.

Required host/core GPU samples begin after cooldown and bracket native execution. Optional counters/snapshots begin before cooldown and have a broader scope. The report distinguishes these windows. Power/thermal counters do not establish a kernel bottleneck or a native throttle fraction. The host remained shared; unrelated CPU contention was not excluded.

## Accuracy and uncertainty

Both donors' 100 bp and 500 bp domains passed complete truth qualification before cohort scoring. Original REF footprints, repeat-equivalent indel masks, known reference-error tracks, noncanonical reference sequence and the fixed v1.1 spanning-star neighborhood exclusions remain bound to their sources. The earlier strict star failure and superseded executable-custody attempt remain retained.

All 12 full-cohort/domain pairs and all 20 timing/domain pairs have positive alignment-column exposure. The independent audit closed every native/Rust parent, child and loss ledger; checked the 16 unique observation-bound SAM metadata/alternate-alignment joins; and reconciled per-parent M/X/I/D statistics with reported counts and rates. It rehashed 455 new accuracy outputs covering 17,675,085,999 bytes.

A retained standalone Rust arithmetic checker independently reproduced both 2,000-replicate parent-bootstrap intervals for every score from the actual parent sufficient statistics. It detected a deliberate interval change of 0.001. These are within-pilot technical intervals. They do not cover truth/donor uncertainty, genomic dependence, flowcell variation or population uncertainty.

Sequence-to-counts behavior is qualified by independent source review, 26 Rust tests, native counterexamples and genuine perfect/nonzero-error witnesses. HP/context evidence additionally has fixed-bin/count checks and content hashes. An optional independent scan of all 17.4 GB of HP event rows was stopped after 138.7 seconds, after native measurements had ended; the entire event ledger was not independently recomputed. That interruption and its limited coverage remain in the detailed review.

## Report behavior and retained checks

The independent verifier reconstructed the complete evidence JSON and rendered Markdown from current retained metadata and the recorded CLI arguments. Tuple-to-array JSON conversion and construction order were accounted for in the audit harness; its earlier failed assumptions remain recorded. The published artifacts match the accepted hashes above.

Six final adverse edits were rejected: a missing full score pair, denominator drift, negative parent-mean error, omitted incident annotation, foreign scorer arguments and a conflicting artifact checksum. A separate altered-bootstrap control was also detected. None required repeating a successful native producer.

| Check | Result and local receipt |
|---|---|
| Acquisition/reference/native contracts with both genuine-data environment variables | 75 passed, zero skips; `logs/20261022T235204Z-controlled-all-local-contracts-QtO3xW` |
| Retained accuracy-tool/receipt contracts | 6 passed; `logs/20261022T235756Z-accuracy-retained-tool-contracts-a2TieM` |
| Final exporter contracts | 61 passed; `logs/20261023T012611Z-controlled-report-tests-final-ZqE1CE`; independently repeated with 61 passes |
| Complete stock rerun | Exit 0; `logs/20261023T000054Z-controlled-sustained-stock-aMmIp6` |
| Full and timing accuracy execution | Exit 0; `logs/20261023T011024Z-accuracy-complete-controlled-sjbt7T` |
| Final export with `--verify-pins` | Exit 0, all 15,853 deduplicated pins checked; `logs/20261023T012622Z-controlled-report-export-reviewed-24Emhm` |
| Artifact/source/link checks | Exit 0; `logs/20261023T012917Z-controlled-report-artifact-check-4wTR07` |

Exact local commands, checker source, raw outcomes, failed attempts and review limits are retained in `logs/controlled-design-20261022/accuracy-review.md` and `report-review.md`. Genuine probes remain under `logs/accuracy-probes-20261022/`. These local receipts and large scientific artifacts are intentionally excluded from Git. GitHub CPU CI covers its listed contracts; GPU and full-reference acceptance comes from the retained local evidence.

## Limits carried forward

The [owned CPU incident](../provenance/verification/controlled-measurement-notes-20261023.json) makes the single full HG005 SUP clock of 714.83 s descriptive. Its raw CPU-check receipt is missing; the reported interval is conservative and approximate. The actual produced reads are scored, without a counterfactual claim that interference could not affect their numerical accuracy. All ten primary timing windows follow the confirmed stop bound.

Accuracy remains conditional on publisher donor labels, accepted primary mappings and retained reference-identical intervals. Clipped, unmapped, excluded and absent material cannot be assigned these percentages. Whole-read diploid accuracy, variant calling, independent donor genotyping, vendor-training exclusion and population generalization remain unsupported. HG005 is an opened stock control and must not select future candidates. The official Dorado binary is qualified; rebuilding Dorado from its matching source remains a separate future check. Future speedup claims require fresh matched controls and predeclared yield/selection rules.
