# Unchanged source qualification

Smoke qualification passes. Full development/validation qualification is waiting for other experiments to finish on the shared host. This document separates build acceptance, native runtime support, exact vendor equivalence, bounded accuracy, yield, and comparative performance. It introduces no candidate algorithm.

## Accepted build and trace

The [build manifest](../provenance/source-build-20261023.json) identifies unchanged upstream input commit `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`, 22 recursive submodules, and ten declared upstream build patches. The Release executable reports `2.1.2+8b8fc5d`. Its SHA-256 is `2da85ebceb6e0bc9bbba00d982f92bbb83bbe1e7d0c498a56f35309b8883957e`.

The full 582-task build, incremental rerun, help/version checks, 29-library ELF closure, and 55 selected upstream CPU cases pass. The other 555 main-binary cases were not run. GCC 16 failed on an upstream missing include; isolated GCC 15 passed without authored source fixes or compiler bypass flags. [Build notes](source-build-notes.md) preserve the toolchain choice and failures. The current artifact is qualified against its recorded dependency/compiler file manifests. The build lever does not independently verify every reused extraction/cache setting, and a clean-machine rebuild has not been established.

This CUDA 13 source stack uses prebuilt Koi, Torch, and FlashAttention dependencies. It differs from the vendor CUDA 12 distribution. Compiling public Dorado does not rebuild or expose the opaque kernels. [The source trace](dorado-code-path.md) identifies these boundaries and the active calibration, chunking, decoding, splitting, trimming, filtering, and writer path for both model tiers.

[Separate diagnostics](source-runtime-diagnostics.md) verify ordinary HAC and CUDA/NVTX-only HAC/SUP smoke outputs, each representing all 32 requested parents. They establish observed FLSTM and tiled transformer/FP8 kernel families on this GPU. An OS-runtime profiling crash and corrected observation remain recorded. No diagnostic duration supplies a benchmark timing or hardware bottleneck claim.

## Native qualification contract

`scripts/qualify-source.py` calls the frozen native runner and Rust accuracy coordinator unchanged. Its two plans keep fresh official smoke and source outputs separate. The source arm contains two 32-parent development smoke units, one genuine split fixture, and four full HG002 development/validation units. HG005 is not executed or used for selection.

The first root, `results/source-qualification/20261023`, passed genuine scorer/comparator handoff but its first fresh native launch was blocked before execution. The host's profile had changed externally from the historical `balanced` policy to `performance`. That root and its failed preflight remain intact. A new root, `results/source-qualification/20261023-performance`, prospectively freezes the observed profile for both fresh arms. The adapter admits only balanced or performance at sealing, then requires that exact profile throughout native work. It changes no host setting or historical stock plan. Native clocks from different policies are not compared as a speed experiment.

Before GPU execution, genuine retained official smoke and split outputs must pass native comparator positives and reject sequence, quality, child identity, split-offset, removed-record, version, decoder-pin, and foreign-parent controls. A new unchanged-scorer smoke handoff must reproduce the accepted deterministic scores/tables. Fresh source/official native corruption qualification finishes before scoring pins their observations. Source-owned FASTA-versus-index parity must pass separately for both tiers.

Exact comparison retains every mandatory SAM field and typed auxiliary tag. It ignores only record order, auxiliary-tag order, and independently validated header provenance. Basecalls, aligned records, parent ledgers, accuracy metrics, and native score tables receive separate equal/different results. A mismatch is a completed failed equivalence test. It does not become equality through a post hoc tolerance. Native contract failures remain execution/observation failures.

Full admission requires 39 GiB free, including the 30 GiB reserve. The four source units are followed by eight scores across the already qualified 100 bp and 500 bp domains. The original masks, references, stock observations, and scorer remain unchanged. Accepted observations are audited without calling functions that rewrite their bytes.

## Results

The accepted smoke report is `results/source-qualification/20261023-performance/qualification.json`, contract `4bd255279f022fc0e94e29b27dc493ee612931aa3d9a530c4950de0d1eafdf72`. Its raw CLI receipt, `logs/20261023T030425Z-source-qualification-performance-smoke-DQ5yjU`, exits zero.

| Gate | Observed result |
| --- | --- |
| Build custody and ordinary version | Verified |
| Fresh source/vendor HAC and SUP smoke | Verified; all 32 original parents represented per unit |
| Genuine source split fixture | Two children from one original parent; split corruption controls reject |
| Source FASTA/index parity | Verified for both tiers; 55 HAC and 57 SUP mapped smoke records |
| Smoke basecalls, alignments, and parent ledgers | Exact canonical equality for both tiers |
| Smoke accuracy | Both fixed domains verified; all metrics and seven native tables equal per unit/domain |
| Full development/validation | Pending; one successful development HAC basecall retained, no complete full unit accepted yet |
| Comparative performance | Not run |

The first full development HAC basecaller succeeded with qualified measurement receipts. Its successful attempt remains unique and unchanged. A later `calmd` check was interrupted when the profile changed from performance to balanced. A temporary native Power Profiles daemon hold was then tested under the canonical lock. It entered performance for its command and restored balanced afterward. The resumed `calmd` computation exited zero, but its measurement was rejected because another GPU process appeared during the check. Both attempts remain retained. No successful GPU basecaller was repeated to repair these downstream failures.

The tested hold does not override an explicit user profile change. Native measurement checks continue to fail closed on profile drift or foreign GPU activity. The failed reference checks therefore remain unqualified even where a native computation exited zero. There is no active hold or owned native job at this waiting checkpoint; the host is balanced. Full source outputs, eight full accuracy scores, full equivalence, read-only final audit, and completed-run resume proof remain open.

Historical official full outputs supply semantic controls, while a speed ratio requires fresh paired repeated arms. New source process clocks are descriptive only. The [prospective protocol](prospective-experiment.md) defines the separate timing experiment.

## Reproduce and audit

```sh
scripts/build-dorado-source.sh
scripts/record-command.sh source-qualification-smoke uv run --locked python scripts/qualify-source.py \
  --build provenance/source-build-20261023.json --output results/source-qualification/20261023-performance --through smoke
scripts/record-command.sh source-qualification-full uv run --locked python scripts/qualify-source.py \
  --build provenance/source-build-20261023.json --output results/source-qualification/20261023-performance --through full
scripts/record-command.sh source-qualification-audit uv run --locked python scripts/qualify-source.py \
  --output results/source-qualification/20261023-performance --verify-only
```

The CLI returns 0 for exact equivalence, 1 for a retained difference, and 2 for an incomplete/invalid operation. Inspect the separate gate fields. It acquires the canonical host lock and fails before execution if another experiment owns it. Preserve that attempt and wait for the lock. The full outputs and all failed attempts remain outside Git.

Native `UNIT:STAGE` retry and fresh accuracy-attempt retry are exposed by the CLI. Failed adapter-owned comparison, source-FASTA, or corruption-control stages need explicit retained-stage repair; the CLI does not provide a generic retry for them. Repair a successful producer's projection from its retained outputs. Do not repeat a GPU producer merely to repair an observation.

After the other experiments finish, resume the interrupted reference check and the remaining full work with the exact retained controller below. The outer `flock` owns the canonical lock for the entire profile hold. The controller calls the unchanged adapter function directly, so it does not acquire the CLI's lock a second time. It checks adapter hash `58d38686…` and the live profile before resuming. Its [public snapshot](../provenance/verification/source-qualification-resume-20261023.py) is byte-identical to the executed local helper, SHA-256 `e122e64a2e3d7056ef9ef62294331b38ebb0f8f0622537c9977b8ee8920af588`.

```sh
scripts/record-command.sh source-qualification-performance-held \
  flock -n results/stock/host.lock \
  powerprofilesctl launch --profile performance \
  --reason 'Nanopore source qualification control' --appid org.nanopore.source-qualification \
  uv run --locked python provenance/verification/source-qualification-resume-20261023.py
```

This retries only `source:full-development-hac:calmd`. The retained HAC basecall and other successful native stages are reused. The hold is released on command completion. The [Power Profiles daemon API](https://upower.pages.freedesktop.org/power-profiles-daemon/gdbus-org.freedesktop.UPower.PowerProfiles.html) documents the hold and explicit-user-change behavior. The successful hold probe is `logs/20261023T032415Z-source-profile-hold-probe-ZJYfDY`; the actual held attempt is `logs/20261023T032715Z-source-qualification-performance-held-veqpNW`. Keep both failed `calmd` attempts when resuming.

## Research scope

The [prospective protocol](prospective-experiment.md) defines hypotheses, paired accuracy/time/yield, full-process timing blocks, exposure guards, uncertainty, multiplicity, and external confirmation. It remains unarmed until a specific intervention and its margins are registered. Paired common-support accuracy and the separate outer end-to-end endpoint require additional qualified implementation before their confirmatory claims. Two HG002 flowcells and size-selected shards cannot establish generalization across human donors. No paper-level biological claim follows from CI, compilation, or this engineering qualification alone.
