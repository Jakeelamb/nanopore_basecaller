# Human nanopore basecaller pilot protocol

Version 0.2. Prepared before any experimental basecaller change. The user first requested acquisition and preparation, then authorized complete stock processing and verification benchmarks. This document defines setup and a proposed future candidate comparison. No candidate training or tuning is part of this run.

## Question and experimental unit

Can a specified change improve canonical human DNA basecalling relative to an unchanged, pinned Oxford Nanopore Dorado control under matched conditions?

Each future experiment must state one falsifiable hypothesis and its primary outcome before execution. A read is the paired comparison unit. Windows from the same read are dependent observations. Reads from one flowcell are technical observations, not independent biological replicates. Duplex partners must remain together. The current pilot has two individuals and three flowcells and cannot support population-level conclusions.

## Inputs and controls

Use `config/assets.json` for exact URLs, expected byte sizes, upstream checksums where available, and source-object ETags. Use `provenance/assets.lock.json` for the acquired local SHA-256 values. Multipart S3 ETags are not file MD5 values.

The stock executable is Dorado 2.1.2. Its matching source is commit `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. Preserve this checkout unchanged. Make future source edits in a separate checkout or Git worktree.

Pin the following controls independently rather than using moving `hac` or `sup` aliases:

- `dna_r10.4.1_e8.2_400bps_hac@v6.0.0`.
- `dna_r10.4.1_e8.2_400bps_sup@v5.2.0`.

These are the newest respective HAC and SUP versions listed by the pinned Dorado source. They have different architectures and version numbers. A gain over HAC alone does not establish a gain over SUP. The original data release used v5.0.0 models. Rebasecall original signals with the pinned controls for a matched comparison.

Use native SQK-LSK114 human DNA, R10.4.1 E8.2 400 bases per second, at 5,000 signal samples per second. Preserve unmodified POD5 inputs and the metadata needed to convert ADC values into physical current. Do not conflate sampling frequency with DNA translocation speed.

Donor assignments use the publisher's sample/flowcell mapping. Retain internal POD5 sample identifiers independently; for example, PAW70337 reports `ONLL08362`, rather than the literal string HG002. Flowcell and acquisition metadata checks do not establish donor identity by genotyping.

## Frozen pilot roles

| Role | Sample | Flowcell | POD5 shard | Allowed use |
|---|---|---|---|---|
| Development | HG002 | PAW70337 | 33 | Runtime smoke checks, future training and hypothesis development |
| Validation | HG002 | PAW71238 | 10 | Future model selection and stopping decisions |
| Sealed test | HG005 | PAW87816 | 52 | One final evaluation after model and analysis rules are frozen |

Roles attach to the entire source object. Freeze read UUID membership in `data/splits/`. Check for duplicates before accepting the split. Metadata inventory and raw-signal integrity checks are permitted on all objects during setup. The user's follow-up authorizes stock basecalling and alignment of all acquired files, including HG005. Retain these as immutable stock control results. Candidate selection must use development and validation only. This stock processing opens the test control, so do not describe the resulting workflow as a fully blinded study.

The selection rule chooses the smallest object by byte size, with the key as a tie breaker, per selected flowcell. HG005 selection considers both available flowcells. This minimizes storage and transfer, but is not random sampling. End-of-run and read-length bias are unresolved until metadata inspection. An expansion study must predeclare random sampling across run time and enough unrelated individuals, instruments, and runs before examining accuracy.

Separate flowcells reduce acquisition leakage. HG002 validation still shares the donor genome with development. For experiments that claim sequence generalization, add nonoverlapping chromosome or interval partitions with buffers large enough for the read context, and exclude reads that cross a partition boundary. Do this before creating training windows.

Public HG002 and HG005 may have contributed to vendor model development. The vendor's complete sample-level training membership is unavailable in the sources inspected here. The test is held out from our future tuning, but is not established as unseen by the stock model.

## Reference and ground truth

The alignment reference is the complete NCBI GRCh38 no-ALT analysis set supplied by GIAB as `GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz`, upstream MD5 `3a3347eae0893f96ecf495d1c39e2284`. Retain the original compressed file and its publisher indexes. This fixed choice includes all contigs in that analysis set. It is not a single chromosome and it is not the individual's diploid genome.

GIAB also supplies masked and corrected GRCh38 references. The initial setup deliberately pins the unmasked analysis set for a simple common coordinate baseline. Masked references and T2T assemblies are potential separate reference sensitivity analyses. Do not silently replace the FASTA under an existing result.

Acquire GIAB v4.2.1 autosomal small-variant VCFs, tabix indexes, and the corresponding confident-region BED for both samples. This is a matched historical release available for both individuals. It is not the latest HG002 benchmark. NIST currently lists HG002 v5.0q. Preserve the exact BED variant, including HG002's `noinconsistent` filename.

GRCh38 alignment errors are a proxy. They include real genotype differences, mapping errors, and reference errors as well as basecalling errors. A VCF and BED provide variant benchmark truth, not per-sample signal-to-base labels. Avoid treating a teacher basecall as ground truth.

Before a confirmatory basecalling-accuracy experiment, qualify sample-specific phased haplotype sequence or a defensible variant-aware scoring method in confident regions. Record haplotype assignment, ambiguous alignments, structural variation, and excluded intervals. If only GRCh38 is used initially, mask known variant neighborhoods and reference problem regions by a rule fixed in advance, label the result as reference agreement, and retain the unmasked result for sensitivity analysis. Do not tune that masking rule to favor a candidate.

## Proposed outcomes

The first comparison is exploratory until biological truth and sample size are qualified. Record every input UUID, including failed and unmapped reads.

- For qualified haplotype scoring, use per-read base error rate `(substitutions + insertions + deletions) / (matches + substitutions + insertions + deletions)` as the primary paired outcome. Specify handling of clipping, supplementary alignments, low mapping quality, and haplotype ties before running. This denominator measures alignment columns and must not be relabeled as reference-base error rate.
- Report both the mean of per-read errors and the aggregate error fraction, with their different weighting made explicit. Also report unaligned and clipped bases, failed reads, and mapped fractions. An apparent gain from dropping difficult reads fails acceptance.
- Report substitutions, insertions, deletions, and homopolymer-length errors separately. Stratify by predeclared length, quality, GC, homopolymer length, and genomic region. Report sample and flowcell separately.
- Check emitted quality-score calibration against observed errors on independently qualified labels. A higher reported Q score alone is not an accuracy gain.
- For a future performance experiment, report end-to-end signal-seconds and called bases per second, elapsed time, startup and model-load time, peak GPU and host memory, exact batch size, and hardware power state. State whether alignment and file I/O are included. Warm and cold measurements answer different questions.
- Treat variant precision and recall as a downstream endpoint requiring adequate coverage, a fixed variant caller, and matched benchmark regions. These sparse pilot shards cannot establish whole-genome variant performance.

For a future accuracy comparison, predeclare the minimum meaningful gain, tolerated performance or memory regression, failure-rate bound, and compute budget before looking at the candidate result. Compare the same reads with identical processing. Use paired uncertainty estimates clustered by molecule and genomic block. With one flowcell per role, intervals quantify technical variation within this pilot, not biological variation across humans. Correct for repeated hypothesis testing or reserve a single confirmatory test. Record null and harmful changes.

## Execution and evidence

Every experiment gets a new result directory. Preserve the hypothesis, source diff or commit, model hashes, input and reference hashes, split manifest, complete command, environment, UTC start and end, exit status, raw output, and stderr. `scripts/record-command.sh` captures command execution. Failure logs remain evidence and do not become successful results after a retry.

Stock and candidate must use the same read selection, trimming, splitting, modified-base settings, alignment rules, thread budget, and device. Capture the program header from BAM. Use explicit model paths. Do not silently tune only the candidate batch size when claiming a model accuracy gain or speedup.

Setup smoke checks run on a small deterministic development read list. They check GPU execution and valid output, not scientific accuracy or throughput. Keep smoke outputs separate from full stock baseline results. The later user-authorized stock benchmark processes all files. Report only qualified reference-agreement proxies on the test control, and keep future candidate selection independent of that result.

## Phase boundary

Setup acceptance requires verified assets, native nonempty decoded signal, compatible chemistry, disjoint read IDs, a usable full reference and its indexes, model checksum verification, and successful GPU output from both stock tiers. After setup, choose the first specific hypothesis and qualify training labels before changing the basecaller. No improvement is claimed by this workspace preparation.

## Primary sources

- [Dorado 2.1.2 release](https://github.com/nanoporetech/dorado/releases/tag/v2.1.2).
- [Pinned model registry](https://github.com/nanoporetech/dorado/blob/8b8fc5d36a9c0baab262a743cb175b5878e38ca6/dorado/models/models.cpp).
- [ONT human raw-signal release](https://epi2me.nanoporetech.com/giab-2025.01/).
- [GIAB reference documentation](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/references/README_GIAB_Mapping_References.md).
- [GIAB v4.2.1 documentation](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/README_v4.2.1.txt).
- [NIST benchmark status](https://www.nist.gov/programs-projects/genome-bottle).
- [ONT data attribution and license](https://registry.opendata.aws/ont-open-data/).
