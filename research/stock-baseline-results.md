# Stock baseline results

Snapshot: **COMPLETE**. Completion counts verified planned observations. Per-unit complete-work status and represented input parents are reported separately. This exporter displays retained verifier results; it does not revalidate artifacts or qualify scientific endpoints.

Local artifact sources: `results/stock/stock-20261022/plan.json`, `results/stock/stock-20261022/report.json`, `results/stock/stock-20261022/qualification.json`. Raw artifacts and receipts are excluded from Git. Report bytes SHA-256: `a2ec3043e590520d8494f280bdd250b162e114c7a90b2f06459bde768a6ae9e6`. Plan identity: `fb6985a6c83e9ae2d340e0df5941883800ebc7b58ee7aead834194cdd1a68f4b`.

Qualification status: **verified**; qualification verifier SHA-256 `7623a939d4dca46e64d57a2be312b37a7c84d64aac9401e22d5c5b0e4a65ca55`. Observation verifier SHA-256: `7623a939d4dca46e64d57a2be312b37a7c84d64aac9401e22d5c5b0e4a65ca55`.

Native Dorado version: `2.1.2+8b8fc5d`. Models: hac: `dna_r10.4.1_e8.2_400bps_hac@v6.0.0`; sup: `dna_r10.4.1_e8.2_400bps_sup@v5.2.0`.

Input cohort: 3 flowcells; 20,954 parents; 3,750,272,700 signal samples. Each tier receives this same cohort.

| Scope | Planned | Verified | Statuses |
| --- | --- | --- | --- |
| timing | 10 | 10 | {'verified': 10} |
| full | 6 | 6 | {'verified': 6} |
| smoke | 2 | 2 | {'verified': 2} |
| fixture | 1 | 1 | {'verified': 1} |

This size-selected pilot has two individuals and three flowcells. Reads within each flowcell are technical observations; this cohort does not support population-level conclusions. Vendor training contamination is unknown. HG005 stock processing is authorized; candidate selection must remain on development and validation. Shared workstation; earlier runs warmed caches and cache state is uncontrolled. GPU sampling observes utilization, but the limiting code path has not been profiled. Biological accuracy, intrinsic throughput, model winners, and speedups remain unqualified.

Host power snapshots changed between setup and completion; see [the retained snapshots](../provenance/verification/stock-power-snapshots-20261022T222833Z.json). The exact transition time and per-attempt power source were not recorded. These clocks are descriptive observations under uncontrolled power conditions. Establish a fresh matched control on fixed external power before testing a candidate speedup.

| Tier | Verified repetitions | Basecall wall s median [range] | Failed basecall attempts | Complete work |
| --- | --- | --- | --- | --- |
| hac | 5/5 | 11.46 [11.14, 11.53] | 0 | True |
| sup | 5/5 | 27.09 [27.03, 27.31] | 0 | True |

Timing uses five fresh processes per tier on the frozen development subset. Median [minimum, maximum] below includes verified observations with retained successful native-stage resources. Missing observations are UNAVAILABLE. GNU time reports wall seconds to 0.01 seconds; <0.01 marks a value below that reporting resolution. Basecall process wall includes startup, loading, input/output and shutdown. Each stage has a separate native process clock.

| Tier | Native stage | Verified n/planned | Wall seconds median [range] | Unavailable | Attempts | Nonzero exits | Retries |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hac | align | 5/5 | 21.69 [21.05, 22.45] | 0 | 5 | 0 | 0 |
| hac | aligned-decode | 5/5 | 0.11 [0.10, 0.13] | 0 | 5 | 0 | 0 |
| hac | aligned-quickcheck | 5/5 | <0.01 [<0.01, <0.01] | 0 | 5 | 0 | 0 |
| hac | aligned-summary | 5/5 | 0.48 [0.44, 0.51] | 0 | 5 | 0 | 0 |
| hac | base-decode | 5/5 | 0.05 [0.04, 0.06] | 0 | 5 | 0 | 0 |
| hac | base-quickcheck | 5/5 | <0.01 [<0.01, <0.01] | 0 | 5 | 0 | 0 |
| hac | base-summary | 5/5 | 0.48 [0.42, 0.48] | 0 | 5 | 0 | 0 |
| hac | basecall | 5/5 | 11.46 [11.14, 11.53] | 0 | 5 | 0 | 0 |
| hac | calmd | 5/5 | 6.78 [6.61, 6.81] | 0 | 5 | 0 | 0 |
| hac | calmd-decode | 5/5 | 0.10 [0.09, 0.10] | 0 | 5 | 0 | 0 |
| hac | flagstat | 5/5 | 0.05 [0.05, 0.06] | 0 | 5 | 0 | 0 |
| hac | sort | 5/5 | 0.21 [0.20, 0.22] | 0 | 5 | 0 | 0 |
| hac | stats | 5/5 | 3.23 [3.22, 3.33] | 0 | 5 | 0 | 0 |
| sup | align | 5/5 | 21.56 [21.29, 22.72] | 0 | 5 | 0 | 0 |
| sup | aligned-decode | 5/5 | 0.09 [0.08, 0.11] | 0 | 5 | 0 | 0 |
| sup | aligned-quickcheck | 5/5 | <0.01 [<0.01, <0.01] | 0 | 5 | 0 | 0 |
| sup | aligned-summary | 5/5 | 0.48 [0.48, 0.63] | 0 | 5 | 0 | 0 |
| sup | base-decode | 5/5 | 0.04 [0.04, 0.05] | 0 | 5 | 0 | 0 |
| sup | base-quickcheck | 5/5 | <0.01 [<0.01, <0.01] | 0 | 5 | 0 | 0 |
| sup | base-summary | 5/5 | 0.47 [0.46, 0.52] | 0 | 5 | 0 | 0 |
| sup | basecall | 5/5 | 27.09 [27.03, 27.31] | 0 | 5 | 0 | 0 |
| sup | calmd | 5/5 | 6.84 [6.81, 6.90] | 0 | 5 | 0 | 0 |
| sup | calmd-decode | 5/5 | 0.09 [0.08, 0.11] | 0 | 5 | 0 | 0 |
| sup | flagstat | 5/5 | 0.04 [0.04, 0.05] | 0 | 5 | 0 | 0 |
| sup | sort | 5/5 | 0.26 [0.25, 0.26] | 0 | 5 | 0 | 0 |
| sup | stats | 5/5 | 3.21 [3.20, 3.23] | 0 | 5 | 0 | 0 |

Full-cohort clocks below are single runs, not five-repetition performance estimates. Reference disagreement is conditional on mapped primary children: disagreement alignment columns / alignment columns. It includes genotype, mapping and reference differences. Clipping and unmapped output are reported separately; absent-parent causes and split-sibling completeness remain unresolved.

| Unit | Status | Basecall wall s | Input parents | Represented parents | Absent parents | Children | Mapped children | Secondary | Supplementary | Disagreement fraction | Disagreement columns | Alignment columns | Soft-clipped bases | Unmapped children | Unmapped bases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | verified | 51.72 | 2608 | 2608 | 0 | 2614 | 2488 | 643 | 372 | 0.0226731 | 1105818 | 48772212 | 2095522 | 126 | 153589 |
| full-development-sup | verified | 249.27 | 2608 | 2608 | 0 | 2617 | 2499 | 651 | 403 | 0.0201353 | 983711 | 48855039 | 2203867 | 118 | 80835 |
| full-validation-hac | verified | 45.72 | 2027 | 2027 | 0 | 2039 | 1988 | 532 | 335 | 0.0242253 | 1028086 | 42438543 | 1842977 | 51 | 71310 |
| full-validation-sup | verified | 148.24 | 2027 | 2027 | 0 | 2041 | 1994 | 544 | 320 | 0.0220127 | 936653 | 42550618 | 1720796 | 47 | 78799 |
| full-sealed_test-hac | verified | 128.19 | 16319 | 16302 | 17 | 16346 | 13922 | 3817 | 1874 | 0.0291473 | 5104075 | 175113264 | 8413014 | 2424 | 1135993 |
| full-sealed_test-sup | verified | 720.2 | 16319 | 16319 | 0 | 16373 | 14082 | 4027 | 2200 | 0.026087 | 4578703 | 175516564 | 10319071 | 2291 | 608967 |

A verified observation can include absent parents. The complete-work field remains unavailable for such units, and the per-unit parents.tsv retains every input UUID with its emitted or not_emitted status. Native filtered-output counts can also include a split sibling whose parent is still represented; they need not equal absent-parent counts.

The calmd check requires identical primary fields, NM and other tags. An MD exception is accepted only when the stock N corresponds to a coordinate-confirmed IUPAC reference symbol. Exact MD agreement remains false for those units. The original rejection and its source investigation remain in [the discrepancy report](calmd-discrepancy.md).

| Unit | Primary records checked | Exact MD agreement | Reference ambiguity records | Reference ambiguity bases | Reference check stage |
| --- | --- | --- | --- | --- | --- |
| full-development-hac | 2614 | True | 0 | 0 | not required |
| full-development-sup | 2617 | True | 0 | 0 | not required |
| full-validation-hac | 2039 | False | 2 | 7 | calmd-reference-iupac |
| full-validation-sup | 2041 | False | 2 | 7 | calmd-reference-iupac |
| full-sealed_test-hac | 16346 | True | 0 | 0 | not required |
| full-sealed_test-sup | 16373 | True | 0 | 0 | not required |

GPU values are device-wide peaks among 1 Hz samples, not true instantaneous peaks or isolated process allocations; RSS is native process maximum resident memory. Missing fields remain UNAVAILABLE. Stock `--batchsize 0` can select a heuristic fallback when precomputed timings are unavailable; the exact batch_selection_status is retained below, without assuming every tier took the same selection path.

| Unit | Status | Complete work | Batch selection status | GPU MiB | GPU W | GPU utilization % | SM MHz | Temperature C | RSS KiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 51.47 | 100 | 2422 | 69 | 3.24565e+06 |
| full-development-sup | verified | verified | precomputed_benchmark_unavailable | 4925 | 50.53 | 100 | 2407 | 72 | 3.61036e+06 |
| full-validation-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 50.15 | 100 | 1957 | 69 | 2.86467e+06 |
| full-validation-sup | verified | verified | precomputed_benchmark_unavailable | 5549 | 100.39 | 100 | 2520 | 82 | 3.3236e+06 |
| full-sealed_test-hac | verified | unavailable: absent parents or native loader diagnostics | precomputed_benchmark_unavailable | 6637 | 100.56 | 100 | 2790 | 86 | 4.74508e+06 |
| full-sealed_test-sup | verified | verified | precomputed_benchmark_unavailable | 4169 | 100.64 | 100 | 2482 | 92 | 4.96816e+06 |
| smoke-1-hac | verified | verified | precomputed_benchmark_unavailable | 5411 | 50.17 | 100 | 2325 | 52 | 1.3359e+06 |
| smoke-1-sup | verified | verified | precomputed_benchmark_unavailable | 2987 | 49.47 | 100 | 2362 | 54 | 1.71262e+06 |
| timing-1-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 50.43 | 100 | 2032 | 55 | 1.40206e+06 |
| timing-1-sup | verified | verified | precomputed_benchmark_unavailable | 4903 | 50.17 | 100 | 2400 | 61 | 1.77122e+06 |
| timing-2-sup | verified | verified | precomputed_benchmark_unavailable | 4469 | 50.71 | 100 | 2385 | 65 | 1.77664e+06 |
| timing-2-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 51.56 | 100 | 2430 | 63 | 1.40204e+06 |
| timing-3-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 50.98 | 100 | 2415 | 64 | 1.40307e+06 |
| timing-3-sup | verified | verified | precomputed_benchmark_unavailable | 4439 | 52.72 | 100 | 2407 | 65 | 1.76651e+06 |
| timing-4-sup | verified | verified | precomputed_benchmark_unavailable | 3067 | 50.24 | 100 | 2362 | 67 | 1.77357e+06 |
| timing-4-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 50.32 | 100 | 2587 | 64 | 1.40504e+06 |
| timing-5-hac | verified | verified | precomputed_benchmark_unavailable | 6637 | 51.38 | 100 | 2550 | 64 | 1.40545e+06 |
| timing-5-sup | verified | verified | precomputed_benchmark_unavailable | 3615 | 50.8 | 100 | 2370 | 67 | 1.77179e+06 |
| split-fixture-hac | verified | verified | precomputed_benchmark_unavailable | 5393 | 50.21 | 100 | 2437 | 53 | 1.29229e+06 |

Qualification control outcomes are copied verbatim; removed-parent absence accounting is not relabeled as rejection. The genuine smoke and split fixture units above establish retained producer checks, not biological accuracy. Full-reference parity evidence is retained in [index qualification](../provenance/index-qualified.json) and [reference qualification](../provenance/reference-qualified.json).

| Unit | Control | Outcome |
| --- | --- | --- |
| smoke-1-hac | foreign | rejected |
| smoke-1-hac | duplicate | rejected |
| smoke-1-hac | model | rejected |
| smoke-1-hac | truncated | rejected |
| smoke-1-hac | reference | rejected |
| smoke-1-hac | NM | rejected |
| smoke-1-hac | removed-parent | absence recorded or empty rejected |
| smoke-1-sup | foreign | rejected |
| smoke-1-sup | duplicate | rejected |
| smoke-1-sup | model | rejected |
| smoke-1-sup | truncated | rejected |
| smoke-1-sup | reference | rejected |
| smoke-1-sup | NM | rejected |
| smoke-1-sup | removed-parent | absence recorded or empty rejected |
| split-fixture-hac | foreign | rejected |
| split-fixture-hac | duplicate | rejected |
| split-fixture-hac | model | rejected |
| split-fixture-hac | split-sp | rejected |
| split-fixture-hac | split-pi | rejected |
| split-fixture-hac | truncated | rejected |
| split-fixture-hac | removed-parent | absence recorded or empty rejected |

| Process category | Attempts | Nonzero exits | Exit unavailable |
| --- | --- | --- | --- |
| preparation | 16 | 0 | 0 |
| qualification_control | 33 | 3 | 0 |

Nonzero qualification_control exits are expected native negative-control processes, separate from measured unit attempts. Inspect control outcomes above before interpreting them. Preparation processes below are individual single-run clocks, including failed attempts; they are not five-repetition estimates.

| Preparation receipt | Exit | Wall s | RSS KiB |
| --- | --- | --- | --- |
| `logs/20261022T203644Z-reference-minimap-index-MuzBtu` | 0 | 64.86 | 1.20629e+07 |
| `logs/20261022T210643Z-manual-dev32-hac-sxfbo5` | 0 | 18.48 | 1.337e+06 |
| `logs/20261022T210702Z-manual-dev32-sup-gGvtpN` | 0 | 19.32 | 1.69656e+06 |
| `logs/20261022T210835Z-reference-gzip-integrity-KWCDJp` | 0 | 16.54 | 2504 |
| `logs/20261022T210852Z-reference-dictionary-ZKNn8m` | 0 | 32.7 | 248124 |
| `logs/20261022T210924Z-reference-random-access-HWlLOg` | 0 | 0.01 | 4100 |
| `logs/20261022T210948Z-reference-index-parity-p63lOF` | 0 | 92.48 | 1.43962e+07 |
| `logs/20261022T210948Z-reference-parity-input-gwRoSf` | 0 | 0 | 4344 |
| `logs/20261022T211121Z-reference-index-parity-5O53OJ` | 0 | 21.83 | 1.23178e+07 |
| `logs/20261022T211121Z-reference-parity-decode-CmnpcD` | 0 | 0.01 | 4300 |
| `logs/20261022T211143Z-reference-index-parity-WO9S6S` | 0 | 93.72 | 1.41868e+07 |
| `logs/20261022T211143Z-reference-parity-decode-v0kWQK` | 0 | 0.02 | 4288 |
| `logs/20261022T211143Z-reference-parity-input-xcPgWC` | 0 | 0 | 4028 |
| `logs/20261022T211317Z-reference-index-parity-6tswlp` | 0 | 21.5 | 1.2319e+07 |
| `logs/20261022T211317Z-reference-parity-decode-XFiGnr` | 0 | 0.01 | 4420 |
| `logs/20261022T211338Z-reference-parity-decode-DVFuWa` | 0 | 0.01 | 4544 |

Unit attempt receipts retain retries, failures and resource records. Large native artifacts remain outside Git.

| Unit | Native attempts | Nonzero exits | Retries | Receipt directory |
| --- | --- | --- | --- | --- |
| full-development-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/full-development-hac` |
| full-development-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/full-development-sup` |
| full-validation-hac | 14 | 0 | 0 | `results/stock/stock-20261022/units/full-validation-hac` |
| full-validation-sup | 14 | 0 | 0 | `results/stock/stock-20261022/units/full-validation-sup` |
| full-sealed_test-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/full-sealed_test-hac` |
| full-sealed_test-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/full-sealed_test-sup` |
| smoke-1-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/smoke-1-hac` |
| smoke-1-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/smoke-1-sup` |
| timing-1-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-1-hac` |
| timing-1-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-1-sup` |
| timing-2-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-2-sup` |
| timing-2-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-2-hac` |
| timing-3-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-3-hac` |
| timing-3-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-3-sup` |
| timing-4-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-4-sup` |
| timing-4-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-4-hac` |
| timing-5-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-5-hac` |
| timing-5-sup | 13 | 0 | 0 | `results/stock/stock-20261022/units/timing-5-sup` |
| split-fixture-hac | 13 | 0 | 0 | `results/stock/stock-20261022/units/split-fixture-hac` |

Observation failures below are verifier failures, separate from native process exits. A later successful observation does not remove the earlier failure.

| Unit | UTC | Verifier SHA-256 | Error | Failure receipt |
| --- | --- | --- | --- | --- |
| full-validation-hac | 2026-10-22T21:43:59.201079+00:00 | 5b0c5cd0a3fd5869cee3d545a3c4e3b0c4b5eb1dbe73addeb314c548b9233f2e | Native calmd changed primary NM/MD or alignment | `results/stock/stock-20261022/units/full-validation-hac/observation-failure-1792705439201061764.json` |

| Scientific endpoint | Status |
| --- | --- |
| biological_base_accuracy | NOT VERIFIED |
| biological_quality_calibration | NOT VERIFIED |
| variant_aware_accuracy | NOT VERIFIED |
| variant_calling_accuracy | NOT VERIFIED |

Additional retained limits: Reference disagreement is a conditional mapped-child proxy. Cache state uncontrolled; no model-tier speedup or winner claim. Absent parents have unresolved causes. Split sibling completeness cannot be established by parent membership alone. Sampler fields may be unavailable; inspect raw logs.
