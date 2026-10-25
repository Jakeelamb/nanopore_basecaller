# Stock benchmark design

The independent native Sol reviewer selected candidate B, scoring it 22 of 25 against candidate A's 20. The coordinator read both designs and accepts the same choice. The criteria were native interface correctness, work and failure accounting, scientific limits, restartable evidence, and maintained code size. The full candidates and judgment are retained in `provenance/design/`. This is independent same-family review, not cross-family review.

## Accepted shape

One fixed Python runner coordinates existing native programs and the existing command recorder. Dorado performs basecalling, alignment, and native summaries. Samtools performs BAM traversal, sorting, statistics, and reference NM/MD recalculation. Python validates identities and joins native metrics. No new biological scorer, workflow engine, database, or performance winner selection is needed.

The runner owns `results/stock/`. Immutable raw assets, UUID lists, model trees, binaries, and reference inputs are pinned in a plan. Each attempt preserves commands, producer exits, UTC and monotonic clocks, raw output, resource observations, and hashes. A reporting failure repairs observation from the retained producer artifact. A verified unit can be reused only after its current bytes and inputs match its receipt. Failed or interrupted native work remains visible and is not silently retried.

## Grafts from candidate A

1. Begin genuine development smoke checks with stock `--batchsize 0 -v`. Record effective batch and chunk sizes from CUDA logs. Freeze this policy before measured runs. Retain any failure before an evidence-driven compatibility revision.
2. Keep a finished native observation distinct from complete-processing qualification. List absent input UUIDs. Stock's five-base sequence filter is a possible cause, not an established per-read explanation. Report submitted-input rates and output rates with drop counts. Do not claim every submitted signal was successfully called when evidence is incomplete.
3. Pin the exact native index producer and its reference build receipt. The Dorado wrapper exposes no index-dump flag. Build minimap2 from nested source commit `3c28777e7e2dcc90f825de1b9f17a89cca7d4452` in a separate copy, preserving the stock source checkout. Record whether ONT patches were applied. The unpatched upstream index producer may be used only after native FASTA versus MMI parity qualification. Native input format compatibility and correct reference provenance matter separately.

## Fixed processing

Use source-backed `dorado basecaller MODEL POD5 --read-ids IDS --device cuda:0 --batchsize 0 --min-qscore 0 --trim all -v`. Preserve a regular-file unaligned BAM. Keep read splitting enabled. Raw parent identity is `pi` when present, otherwise QNAME. Verify the complete BAM, split tags, quality and sequence lengths, and exact source membership. Qualify split semantics using the genuine compatible POD5 fixture in the pinned source, not a fabricated split claim.

Use separate `dorado aligner INDEX BAM --threads 16 --no-sort --mm2-opts '-x lr:hq -I 16G --eqx -Y'`. Pin the full reference and compare its complete contig dictionary. Reconcile one primary or unmapped record per emitted child, strand-normalized sequence and quality, native CIGAR/NM counts, and samtools calmd. Report secondary and supplementary records separately. Retain native Dorado summary, samtools flagstat and primary-only stats.

Perform six complete single-run qualifications, one per raw shard and model. Perform five fresh-process repetitions per model on the existing deterministic development `benchmark.txt` subset in order `H,S; S,H; H,S; S,H; H,S`. Do not invent a second subset rule. Basecalling wall includes startup, model loading, input access, GPU work, output, and shutdown. Alignment, indexing, validation and report clocks are separate. Caches are observed, not forcibly cleared. Do not benchmark alongside unfinished acquisition or other owned GPU work. Preserve 30 GiB of free storage.

The prospective performance claim is a descriptive stock baseline: median and range of complete native process wall time for this fixed subset and configuration on this host, with verified input/output counts and all attempted executions. It is not a HAC versus SUP winner selection or an improvement claim. Reference preparation and full-cohort runs have single-run clocks, not repeated performance estimates.

This is a shared workstation. Record load, core count and active process resource use before measured work, retain GPU utilization, power, clocks and memory during each basecaller, and use the interleaved schedule to distribute drift. Do not terminate unrelated work. If contention or the limiting resource cannot be qualified, retain the observations and state that limit; do not infer an intrinsic hardware or algorithmic speed difference.

## Acceptance

Before full GPU execution, accept a genuine native producer fixture and reject truncated BAM, foreign parent, duplicate primary, removed represented parent, wrong model or reference identity, and inconsistent NM. Removing a represented parent must change the absence ledger; it need not be assigned an invented failure reason. Missing split siblings are not always observable from parent membership alone. Prove retained-artifact reuse and interruption handling on small controls.

Retain all ten planned timing observations and all six full cohort outputs. Show successful and failed counts, median and range, input and output counts, sampled GPU resources, host RSS, and contention limits. Do not silently replace failures or publish a model speedup ranking. Every native and projected endpoint has its own verified or unavailable status.

GRCh38 disagreement is a reference-agreement proxy. Biological base accuracy, biological quality calibration, variant-aware confident-region accuracy, and variant calling accuracy remain NOT VERIFIED. GIAB VCF and BED inputs do not establish those endpoints by themselves. The user has authorized stock processing of HG005, but candidate selection remains confined to development and validation.

## Observed verification amendment

The full validation HAC run triggered an exact MD comparison failure on 2026-10-22. An independent investigation found seven stock `N` symbols where the original reference contains `Y`, `W`, or `K`. All other record fields and tags, including NM, were identical. The pinned minimap2 index reduces the reference alphabet to `ACGTN`. Samtools calmd retains the original reference symbols. See [the complete investigation](calmd-discrepancy.md).

The corrected verifier permits only an unchanged MD structure with stock `N` versus a non-ACGT IUPAC symbol confirmed at the exact native faidx reference coordinate. Every other primary field and tag must remain identical. Observations record each exception and explicitly report false exact MD agreement. The original failure and original verifier remain retained. This amendment changes observation of existing stock artifacts; it does not change native basecalls, alignment, NM, or the reference disagreement endpoint.
