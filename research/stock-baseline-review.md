# Independent stock baseline artifact review

Verdict: **PASS for the identified stock observation and descriptive-results artifact**, independently checked on 2026-10-22. No blocker was found in the final report, exporter, or displayed figures. This does not qualify biological accuracy, complete successful processing of every HAC input parent, intrinsic throughput, a model winner, or a speedup.

The review targets the final working-tree artifacts on branch `setup/stock-baseline`, based on repository HEAD `f10630a2778fa215beeb7135d64f490dbf2a4ea9`. The content hashes below identify the reviewed revision independently of its later commit. No implementation or acceptance check was changed by this reviewer. Native basecalling and alignment were not repeated. Original native artifacts and the coordinator's final Markdown were not modified.

| Reviewed artifact | SHA-256 |
| --- | --- |
| `scripts/benchmark.py` | `7623a939d4dca46e64d57a2be312b37a7c84d64aac9401e22d5c5b0e4a65ca55` |
| `scripts/summarize-benchmark.py` | `352d9758b5bb6bb3ab6c80f0371bb655be736a95db483f231e0997ff0a870616` |
| `research/stock-baseline-results.md` | `9b422491a5f890e2c5e124c930c5dbe7548269087df2e2adb9fe09868388472f` |
| `results/stock/stock-20261022/report.json` | `a2ec3043e590520d8494f280bdd250b162e114c7a90b2f06459bde768a6ae9e6` |
| `results/stock/stock-20261022/plan.json` | `763cc30ef8ecd5356b91e5ce938271acbda94a78ea6435ddf3d426145af7ca08` |
| `results/stock/stock-20261022/qualification.json` | `6ad407d86d8a96f7a0c18d7fc693a31b853870e7ce323f0fc17795e8f9020792` |
| [Power snapshots](../provenance/verification/stock-power-snapshots-20261022T222833Z.json) | `3bfa216a5eb1faabace75caeef3321d3555381e2ff6422a38bdf77fc0b22a3c4` |

Plan identity is `fb6985a6c83e9ae2d340e0df5941883800ebc7b58ee7aead834194cdd1a68f4b`. The reviewed stock Dorado source remains clean at `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`; the native version and model identities remain the configured stock controls.

## Commands and retained evidence

These exact top-level commands ran from `/home/jake/Projects/nanopore_basecaller` and exited 0:

```sh
scripts/record-command.sh stock-independent-report uv run --locked python scripts/benchmark.py report results/stock/stock-20261022/plan.json
scripts/record-command.sh stock-independent-native-audit uv run --locked python logs/stock-baseline-audit-20261022/audit.py
scripts/record-command.sh stock-independent-exporter-audit uv run --locked python logs/stock-baseline-audit-20261022/exporter-audit.py
scripts/record-command.sh stock-independent-supplement uv run --locked python logs/stock-baseline-audit-20261022/supplement.py
```

| Check | Raw recorder directory | Observed result |
| --- | --- | --- |
| Maintained report CLI | `logs/20261022T222751Z-stock-independent-report-CsE26E` | Exit 0; fresh `load_plan` checks current plan inputs and model membership; observation and successful-stage pin checks pass; report bytes remain exactly `a2ec3043…a6ae9e6` |
| Native artifact and numeric audit | `logs/20261022T223023Z-stock-independent-native-audit-M76avc` | Exit 0; all six full native decode/summary/ledger/calmd comparisons and displayed numeric tables pass |
| Actual exporter and rejection controls | `logs/20261022T223117Z-stock-independent-exporter-audit-ee4AAv` | Exit 0; positive render and all four expected CLI rejections pass |
| Raw diagnostics, flagstat and stock source | `logs/20261022T223254Z-stock-independent-supplement-KX6wi1` | Exit 0; all 19 diagnostics, six flagstat joins, exact filter count and clean source pass |

The full audit programs, all assertion results, exact native command arrays, stage receipt paths, decode counts and MD exceptions are retained under `logs/stock-baseline-audit-20261022/`. They are isolated evidence programs, not changes to maintained acceptance checks. The principal result files are:

| Evidence file | SHA-256 |
| --- | --- |
| `audit-result.json` | `69d43ce5f09c9799e55ecaf5b68c7c0b95f7fe7fbdfa6a0e436f3e6b4b9e47fc` |
| `exporter-result.json` | `a1459dcc19ea9b272454c90aa4be70815662c854a3b433acd42b9aa10032cd0b` |
| `supplement-result.json` | `3ce7e86a974599a82412b2331a382c875b3b7c2cadc38694e044bdc002f05a57` |

The maintained report was invoked only after the coordinator confirmed the final native stages had finished and the host lock was free. It re-created identical report bytes. The earlier 58-test result and independent MD review were read for scope; this review did not repeat that broad suite or treat it as evidence of final-run completion.

## Direct observations

All **19 planned units** have successful observations from the current frozen verifier: ten timing, six full, two smoke and one genuine split fixture. Qualification is current, with **21 controls and 630 evidence-pin entries** independently checked. Every retained unit attempt has a complete zero-exit native recorder. The report's **298 tracked benchmark native attempts** comprise **295 finished processes and three expected truncated-BAM quickcheck failures, each exit 16**. There are no retries or unavailable exits. Those totals include 249 unit-stage attempts, 33 qualification-control processes and 16 preparation processes. Independent review commands are outside this benchmark census.

The frozen inventory, full-role UUID lists and both tiers' planned parent/sample dictionaries agree: three POD5 cohorts, **20,954 parents and 3,750,272,700 signal samples per tier**. Development has 2,608 parents / 641,769,607 samples; validation has 2,027 / 553,650,293; HG005 has 16,319 / 2,554,852,800. Exact native basecaller and aligner arguments, model paths, read-ID paths and input paths agree with the plan and each recorder's shell-escaped command. The two tiers use identical full inputs and membership for each role.

All six retained full unaligned, aligned and calmd SAM decodes were freshly parsed; both native summary tables per unit were checked against the decoded children. Every `parents.tsv` row was reconciled with input samples and emitted child counts. CIGAR/NM numerator and alignment-column denominator were recomputed separately from parsed primary records. Native flagstat total, primary, secondary and supplementary counts also agree. The report's full-row clocks, counts, ratios, clipping and unmapped figures match this evidence.

| Full unit | Input parents | Represented parents | Absent parents | Emitted children |
| --- | --- | --- | --- | --- |
| development HAC | 2,608 | 2,608 | 0 | 2,614 |
| development SUP | 2,608 | 2,608 | 0 | 2,617 |
| validation HAC | 2,027 | 2,027 | 0 | 2,039 |
| validation SUP | 2,027 | 2,027 | 0 | 2,041 |
| HG005 HAC | 16,319 | 16,302 | 17 | 16,346 |
| HG005 SUP | 16,319 | 16,319 | 0 | 16,373 |

SUP represents all 20,954 full-input parents. HAC represents 20,937. HG005 HAC's raw native log explicitly says `Simplex reads filtered: 18`; this is an output-event counter, not an explanation for each of the 17 absent parent UUIDs. The final artifact correctly keeps that unit's complete-work qualification unavailable. All other full units have complete parent representation, subject to the unresolved split-sibling limit.

Both validation models have **false exact MD agreement**, exactly seven coordinate-confirmed reference ambiguity exceptions in two primary records each, and otherwise equal primary fields and tags. All other full units have exact MD agreement. Retained native faidx output was used when rechecking the exceptions; no new reference command was needed. The original validation HAC observation failure remains byte-identical at SHA-256 `a05d3564655f0d8d33b8dfc02b941a8449dfd58e84d17438f5c151196b023626`, with its old verifier identity and error displayed separately from native process exits.

All ten timing observations are distinct fresh native processes in the predeclared interleaved order. Raw GNU time clocks independently reproduce:

| Tier | Raw basecall wall seconds, repetition order | Median | Range |
| --- | --- | --- | --- |
| HAC | 11.14, 11.36, 11.51, 11.53, 11.46 | 11.46 s | 11.14–11.53 s |
| SUP | 27.09, 27.08, 27.28, 27.31, 27.03 | 27.09 s | 27.03–27.31 s |

Every displayed timing-stage median/range was recomputed from raw native clocks. Every displayed process RSS and GPU peak was recomputed from native time receipts and retained GPU CSV samples. Process exits, command arguments, working directories, UTC ordering, positive monotonic durations and stage identity hashes were checked. Zero-resolution short stage clocks remain labeled below 0.01 s in the repeated-stage table. The optional faidx stage is absent from timing requirements and explicitly not required for exact-MD full units.

The final power snapshot is byte-identical to its zero-exit native-glue recorder stdout. Its initial snapshot matches the frozen plan. ACAD online changed from 0 to 1; USB port 4 is online in the final snapshot. The final text states that the transition time and each attempt's power source were not recorded. It correctly treats the clocks as descriptive observations under uncontrolled power conditions.

## Exporter behavior and negative controls

The actual final exporter CLI exited 0, rendered **COMPLETE; 19/19 verified units**, and matched the coordinator's final artifact after resolving the expected relative provenance-link differences caused by the isolated output directory. The final artifact hash remained unchanged. Exact positive command is retained in `logs/20261022T223117Z-stock-independent-export-oO0Kla/command.sh`; the output is `logs/stock-baseline-audit-20261022/rendered.md`.

| Isolated mutation | Actual CLI exit | Observed error / raw receipt |
| --- | --- | --- |
| Wrong report plan identity | 1 | `Report, qualification and planned unit identities must match`; `logs/20261022T223117Z-stock-export-wrong-report-identity-j9Feoj` |
| One planned report unit removed | 1 | Same identity/census error; `logs/20261022T223117Z-stock-export-wrong-census-1KVPMs` |
| Wrong power plan identity | 1 | `Power observation must match the frozen plan`; `logs/20261022T223117Z-stock-export-wrong-power-identity-sWmnEe` |
| Changed initial power snapshot | 1 | Same power identity error; `logs/20261022T223118Z-stock-export-wrong-power-snapshot-537wOu` |

Each rejected export left its requested output absent. The program also changed one sequence length in a copied genuine full native summary; maintained summary verification rejected it with `Native summary sequence length mismatch`. A copied genuine smoke record with a foreign parent rejected with `Foreign parent: 00000000-0000-0000-0000-000000000000`. Originals were untouched. These show that the exercised checks detect failures rather than merely accepting the positive snapshot.

## What remains unproven

The exporter displays retained observations; it does not independently revalidate them. In particular, the maintained `report` command does not itself check qualification pins, which is why this audit checked all 630 entries separately. Future exports still need current maintained verification and appropriate evidence review.

All four biological endpoints remain **NOT VERIFIED**. GRCh38 disagreement is conditional on mapped primary children and includes genotype, mapping and reference differences. Absent-parent causes and split-sibling completeness remain unresolved. The pilot contains two individuals and three size-selected flowcells; vendor training overlap and population generalization remain unknown. HG005 stock processing does not authorize future candidate selection using HG005 outcomes.

Power source, caches and shared-host contention were uncontrolled. Per-attempt power source and its transition time are missing evidence; observed power differences do not establish their cause. Device-wide 1 Hz samples cannot establish instantaneous or process-isolated peaks, and utilization does not identify the limiting code path. Full-cohort clocks are single runs. These observations cannot establish intrinsic throughput, a model winner or a candidate speedup. A future speedup experiment requires a fresh matched control on fixed external power and the same predeclared processing conditions.

The calmd adapter enforces primary-record equality and narrowly qualified MD exceptions. This audit did not extend that contract to every nonprimary MD annotation or prove every legal CIGAR/MD combination. Pinned native producers remain trusted dependencies. No broken tool or missing evidence required for this bounded final-artifact verdict was encountered; the scientific and environmental gaps above remain explicit.
