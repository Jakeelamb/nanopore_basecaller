# Controlled stock benchmark rerun

The user requested a thorough, reusable timing and accuracy baseline on 2026-10-22 after the first stock run. Preserve that run unchanged. No candidate basecaller changes are authorized by this benchmark request.

## Workflow

- [x] Read the Principles section of Poteto Mode.
- [x] Phase A: Frame.
- [x] Phase B: Design the workflow.
- [x] Phase C: Run the loop.
- [x] Phase D: Keep the audit trail.
- [x] Phase E: Verify and hand back.

Accuracy design uses Architect Ground, Sketch, Agree, Implement, and Scrap. Agree proceeds without a human checkpoint for this authorized work. The arena stages are Frame, Fan out, Cross-judge, Pick, Graft, and Verify. Two independent native Sol designs and one independent reviewer will establish the accuracy contract before expensive execution. This is same-family review.

## Completion predicate

Use new result directories and freeze the protocol before measured execution. Both unchanged stock models must process every acquired signal cohort again. Repeated timings must include at least five fresh processes per tier on a workload large enough to expose sustained work. Each accepted timing must have continuous external-power and platform-profile evidence, a bounded idle GPU starting temperature, resource and throttle observations, complete native receipts, and reconciled input/output membership. Retain rejected attempts without silently replacing them.

The accuracy benchmark must qualify explicit truth and alignment denominators, count substitutions and indels separately, retain absent/unmapped/clipped reads, and produce per-cohort results with uncertainty and quality/length/context strata where evidence supports them. Source-backed native tools or independently checked Rust computation must perform sequence scoring. Qualify a bounded accuracy endpoint instead of relabeling plain GRCh38 disagreement as biological truth. Keep unsupported endpoints explicit.

The verification package must include genuine stock inputs and negative controls, a reproducible CLI, raw evidence pins, an independently audited report, and passing PR checks. Do not merge without authorization.

## Throughput checkpoint

The existing cohort contains 20,954 parents and 3,750,272,700 electrical samples. The host currently has about 60 GiB free, a 30 GiB reserve, and connected external power. Expect approximately one hour for preparation, repeated larger timing workloads, complete stock reruns, accuracy evaluation, and review. Reassess after truth selection and the first powered full-development run. Additional truth acquisition must fit the reserve and must not overlap measured GPU timing.

The runtime runner and immutable native-stage mechanism are already established. Extend their measurement boundary rather than introduce another execution framework.

## Frozen analysis contract

Two independently prepared designs were read in full. The independent same-family judge scored A 24/30 and B 25/30 across truth validity, denominator correctness, observable losses, verification, resource feasibility, and maintained complexity. Use A's single Rust scorer and existing execution boundary; incorporate B's reference-error exclusions, repeat-equivalent indel masks, and basewise deletion counting. The unmodified original benchmark remains historical evidence.

The endpoint is **GIAB-supported reference-identical interval accuracy, conditional on publisher donor labels and accepted primary mappings**. The v4.2.1 release explicitly supports homozygous-reference calls inside its matching confident BED. VCF absence outside that BED supplies no truth label. This endpoint excludes variants rather than constructing uncertain haplotypes. Whole-read diploid accuracy, variant precision/recall, population generalization, and vendor training exclusion remain unsupported. [GIAB release documentation](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/README_v4.2.1.txt).

Freeze both donors' domains before new scoring. The primary rule erodes merged confident intervals by 100 bp and subtracts every VCF REF span and equivalent pure-indel placement range with 100 bp padding. A second, predeclared domain repeats this with 500 bp erosion/padding. Native `bcftools norm --check-ref e -f ORIGINAL_REFERENCE -m -any` checks all REF alleles and splits multiallelics; Rust also validates the resulting reference, sample, diploid genotype, dictionary, and coordinate bounds. After trimming common allele sequence, rotate pure insertion/deletion motifs through every equivalent placement, union the original anchored footprint, and pad. Concrete complex replacements retain their full reference footprint. Unsupported symbolic/breakend syntax fails qualification. Extend exclusion boundaries through homopolymers they cut. Never select the favorable domain after examining results.

Subtract padded known reference-error tracks and padded non-ACGT sequence. Keep the original full alignment reference/index. The exact three v3.5 false-duplication/collapse tracks and GRC/T2T exclusions are pinned separately in `config/accuracy-v1.json`. These exclusions reduce documented reference errors; they cannot prove all reference errors are known. [Reference documentation](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/references/README_GIAB_Mapping_References.md), [track definitions](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/genome-stratifications/v3.5/GRCh38@all/OtherDifficult/GRCh38_OtherDifficult_README.md).

Score autosomal primary alignments with MAPQ 30–254. Secondary/supplementary records add no columns, but their presence, clips, unmapped outputs, low/unknown MAPQ, zero denominators, and absent parents remain visible. This is a local-primary mapping policy, not proof of unique origin or complete-molecule reconstruction. The native verifier independently binds model, source parent, split tags, query/quality, reference dictionary, NM, and complete producer receipts.

Rust traverses SAM-oriented query/qualities and the actual reference, validates EQX, and counts eligible matches M, substitutions X, inserted bases I, and deleted bases D. An insertion requires both existing flanks in the same eligible interval. Each eligible deleted reference position counts, including the eligible part of a deletion crossing a mask. Query N is an error at an eligible canonical truth base. Soft clips are excluded and counted. The alignment-column denominator is `C=M+X+I+D`, error is `(X+I+D)/C`, and accuracy is `1-error`. Zero C gives an unavailable rate. Aggregate and mean-parent rates are separate. All split-child contributions are combined by original parent before parent statistics.

Report fixed called-length/native-qs strata, integer emitted-Q reliability, homopolymer contexts, and matched-flank homopolymer length projections. Query quality labels use `(X+I)/(M+X+I)` and expected `10^(-Q/10)`; deletions have no emitted Q and are reported separately. Preserve every input/output parent and child, called/scored/excluded/clipped/unmapped base counts, and exact ledger conservation. Query-Q reliability is conditional on retained labels and is not whole-read calibration.

Use 2,000 fixed-seed parent bootstrap replicates per cohort/tier for aggregate and mean-parent errors. Preserve per-parent sufficient statistics. These intervals quantify within-pilot technical resampling only; genomic dependence, unidentified duplex relationships, flowcell variation, and population uncertainty are not covered. Future candidates require paired input UUID comparisons and predeclared yield/selection bounds on development and validation. This stock run selects no candidate using HG005.

## Controlled execution

Keep Dorado `2.1.2+8b8fc5d`, exact model trees, batchsize 0, trimming, splitting, mapping, and thread budget unchanged. Timing uses all 2,608 development parents and 641,769,607 samples per process. Preserve the original 256-parent membership file. Run five fresh processes per tier in `H,S; S,H; H,S; S,H; H,S` order. The six full cohort/tier jobs provide additional independently retained workload observations.

Warm the read-only input/model/reference/index files explicitly outside measured processes. Declare warmed filesystem and fresh processes; do not flush global caches. Each basecaller waits outside its native clock for three one-second GPU samples at <=40 C and <=5% utilization. Require ACAD online=1, the existing balanced platform profile, frozen CPU affinity, and no foreign GPU compute before/during/after each native stage. Preserve one-second host/GPU samples with a maximum 2.5-second gap. Required telemetry failures or changed controls reject the attempt; no automatic retry. Read-only observations do not lock DVFS, fan speed, clocks, or thermal state during sustained work. Record power ceiling, temperature, clocks, utilization, memory, and available power/thermal counters. Explain stock laptop thermal/power limiting from those traces.

GNU time's native process clock includes startup, model loading, input, computation, regular-file output, and shutdown. Alignment, sorting, summaries, complete decoding, stats, and calmd keep separate clocks. Cooldown, observer setup, telemetry, verification, and hashing are not native basecalling time; report observer elapsed separately. One-second samples cannot exclude subsecond control changes. No claim of isolated-kernel throughput or optimal batch tuning follows from these process measurements.

## Acceptance and reproducibility

Before expensive reruns, require complete truth qualification, Rust behavior/property tests, the native target-statistics counterexample, deletion-only/cross-mask and insertion-boundary controls, reverse quality/orientation checks, wrong REF/sample/dictionary/GT/symbolic rejection, repeat-equivalence beyond fixed padding, foreign/duplicate membership rejection, changed-pin/interrupted-stage rejection, and genuine stock perfect and nonzero-error witnesses. `samtools stats -t` is disallowed as an interval error scorer: actual native probes show whole-read NM survives target restriction while the denominator shrinks. [Native samtools source](https://github.com/samtools/samtools/blob/dc71c7274044d1050ccb64901731373ec7e915b6/stats.c#L1288-L1435).

`scripts/accuracy.py` coordinates native decoding, full REF validation, immutable inputs, the Rust CLI, and exact parent-ledger joins through the maintained stage recorder. `tools/accuracy/` owns sequence computation. No separate execution framework or Python sequence scorer is introduced. New accuracy and timing outputs use fresh directories. Final acceptance requires all six new full outputs, both fixed truth domains, positive exposure, exact ledgers, complete receipts, independent review, and passing PR checks. Raw sequences, masks, per-read results, binaries and logs remain ignored; concise evidence and reproducible code are public.

## Pre-results truth amendments

Independent review reproduced a normalization defect: trimming a long shared REF/ALT prefix can remove part of the original footprint from a normalized-only mask. Native `bcftools query -f '%CHROM\t%POS0\t%END\n'` now supplies every original REF footprint. Rust unions those spans with normalized and equivalent-placement masks before padding. A regression reproduces the 100 bp exposure error and checks the corrected domain. Original native normalization outputs remain unchanged.

The first complete strict truth pass at scorer `d1b42b4e1a54cd74936956e7f13183e996d86bd7f591cabbf50d91e707a49e00` correctly failed on HG002 spanning `*` alleles at chr1:93847010 and chr1:93847011. Native queries and independent scans found no covering concrete deletion. Both loci lie in the confident-BED gap `[93846875,93847079)`. No complete new cohort accuracy score existed at this point.

Version 1.1 narrows the domain by the fixed, independently reviewed rule in `config/accuracy-v1.1.json`: for every star REF span, remove all intersected original merged confident intervals and the closest strictly left and right original intervals. In a gap this removes its two neighbors. Select from the original set once, union/deduplicate globally, and never expand recursively. Apply before either 100/500 bp erosion. Retain star-anchor padding and all concrete/original/equivalent masks. Other symbolic/breakend alleles still fail. Publish star counts, removed interval IDs/bases, and ordered losses. This trusts GIAB homozygous-reference assertions only in the retained domain; it does not reconstruct missing deletion extents. The first two stars remove original neighboring intervals totaling 12,232 bases before other operations.

The strict failed native attempt remains under the original analysis directory. The amended analysis has a fresh directory and shares unchanged native input producers read-only. All four amended truth domains require fresh qualification. The endpoint name explicitly includes exclusion of unsupported-star confidence neighborhoods. The [VCF specification](https://github.com/samtools/hts-specs/blob/master/VCFv4.3.tex) defines `*` as an allele missing because of an overlapping deletion; it supplies no upstream extent itself. GIAB's release documentation also explains that its VCF contains variants outside confident regions to support boundary comparisons.

## Completion record

The controlled rerun completed on 2026-10-23 UTC. All 19 stock observations, 12 full accuracy pairs and 20 timing accuracy pairs passed the bounded acceptance gates. Both 100/500 bp domains and every parent-bootstrap interval were retained; an independent arithmetic replay reproduced all intervals. See [the final results](controlled-baseline-results.md) and [acceptance review](controlled-baseline-review.md) for exact identities, commands, tests and limits.

The full HG005 SUP clock remains descriptive because of the disclosed owned CPU incident. All ten primary timing windows start after its conservative confirmed stop bound. The host remained shared. Required core GPU samples start after cooldown; optional counters have a broader observer window. These scope statements correct report projections without changing measured producers or analysis policy. No candidate improvement or Dorado source-build qualification follows from this completed stock baseline.
