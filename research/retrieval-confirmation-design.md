# Prospective confirmation and reference-bias design

Prepared 23 October 2026. This is a proposed protocol, not evidence of improvement or acquisition authorization. Metadata checks used anonymous HTTP listings, JSON reports, directory indexes, and HEAD requests. No raw signals, truth records, or candidate outcomes were downloaded or scored. Throughput checkpoint is not applicable to this investigation.

## HG001 is the strongest immediately identifiable donor holdout

HG002 development and validation share a donor and have been reused. HG005 is exposed. Historical `sealed_test` labels in `config/assets.json` and `research/protocol.md` do not restore blinding. The current [reference handoff](../../nanopore_basecaller-reference/research/reference-frontier-current-handoff.md) takes precedence. The requested `accuracy-and-yield-protocol.md` is absent. Canonical asset manifests match this worktree byte-for-byte.

The [ONT release dated 5 January 2025](https://epi2me.nanoporetech.com/giab-2025.01/) supplies PromethION, LSK114, R10.4.1 E8.2 400 bps POD5 for seven GIAB donors. Complete, untruncated S3 listings verified these prospective options. Sizes below count POD5 only, in decimal TB.

| Donor and raw manifest | Flowcells | Raw TB | Donor-matched GRCh38 truth | Limitation |
|---|---|---:|---|---|
| [HG001](https://ont-open-data.s3.amazonaws.com/?list-type=2&prefix=giab_2025.01/flowcells/HG001/&max-keys=1000) | PAW79146, PAW81754 | 2.428 | [GIAB v4.2.1](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/) | Strongest immediate option, subject to project exposure audit. |
| [HG003](https://ont-open-data.s3.amazonaws.com/?list-type=2&prefix=giab_2025.01/flowcells/HG003/&max-keys=1000) | PAY87794, PAY87954 | 2.610 | [GIAB v4.2.1](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG003_NA24149_father/NISTv4.2.1/GRCh38/) | Father of development donor. |
| [HG004](https://ont-open-data.s3.amazonaws.com/?list-type=2&prefix=giab_2025.01/flowcells/HG004/&max-keys=1000) | PAY87778, PAY88428 | 2.462 | [GIAB v4.2.1](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG004_NA24143_mother/NISTv4.2.1/GRCh38/) | Mother of development donor. |
| [HG006](https://ont-open-data.s3.amazonaws.com/?list-type=2&prefix=giab_2025.01/flowcells/HG006/&max-keys=1000) | PAY77227, PBA16846 | 2.062 | [GIAB v4.2.1](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/ChineseTrio/HG006_NA24694_father/NISTv4.2.1/GRCh38/) | Father of exposed HG005. |
| [HG007](https://ont-open-data.s3.amazonaws.com/?list-type=2&prefix=giab_2025.01/flowcells/HG007/&max-keys=1000) | PAY12990, PBA20413 | 2.415 | [GIAB v4.2.1](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/ChineseTrio/HG007_NA24695_mother/NISTv4.2.1/GRCh38/) | Mother of exposed HG005. |

HG001 reports for [PAW79146](https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG001/PAW79146/report_PAW79146_20240911_1129_c6420e1f.json) and [PAW81754](https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG001/PAW81754/report_PAW81754_20240911_1129_150d2e3f.json) record 11 September 2024 generation, 5,000 Hz, compatible 400 bps configurations, and 3,600-second POD5 batches. Other donors' first-flowcell reports also record 5,000 Hz. Second-flowcell internal metadata and all raw integrity remain acquisition gates. Publisher labels establish provenance, not genotype identity.

The [GIAB README](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/README_v4.2.1.txt) and [2022 methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC9706577/) describe independent historical integration using short reads, linked reads, and HiFi. The 2021 benchmark predates these signals. Historical ONT contributed some exclusion and curation evidence, so this is not wholly platform-independent truth. HG001's [HiFi phase-transfer VCF](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/SupplementaryFiles/) has not had its phase accuracy qualified here. Use qualified phase blocks only. Preserve the canonical [GRCh38 no-ALT analysis set](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/references/GRCh38/), MD5 `3a3347eae0893f96ecf495d1c39e2284`, and matching autosomal BED/VCF. Qualify contigs, REF alleles, and haplotype scoring before claiming basecalling accuracy.

The [ONT registry](https://registry.opendata.aws/ont-open-data/) specifies CC BY-NC 4.0 with attribution. [NIST permits publication without embargo](https://www.nist.gov/programs-projects/faqs-genome-bottle). ONT's license still governs ONT signals.

For broader replication, the [HPRC ONT manifest](https://raw.githubusercontent.com/human-pangenomics/hprc_intermediate_assembly/70ee19647152ee24b4f9085b3d6eb69d734bb3dd/data_tables/sequencing_data/data_ont_release2_v1.0.index.csv), revised 25 June 2026, lists 288 R1041 records across 73 donors. All 929 records are BAM. A complete HG00097 nanopore-prefix listing contained BAM and summaries, without POD5/FAST5. The [phased assembly manifest](https://raw.githubusercontent.com/human-pangenomics/hprc_intermediate_assembly/2a7e3a5b1ca10454762699176b1a0a1027ccbf21/data_tables/assemblies_release2_v1.0.index.csv) exists, and [HPRC permits public-domain reuse](https://humanpangenome.org/data-use/). This bounded search did not establish a downloadable, chemistry-qualified raw-signal cohort with independent truth. Raw object manifests, sampling rates, and assembly dependence on evaluated ONT data remain missing. A BAM under `raw_data` is insufficient.

## Freeze a feasible sampling frame before acquisition

Use seed `retrieval-confirmation/HG001/v1/2026-10-23`. Rank keys by SHA256 of UTF-8 seed, newline, and complete key. Break ties lexicographically. Include every simplex parent in selected files. Group known duplex partners for uncertainty. The [machine-readable acquisition manifest](../logs/retrieval-confirmation/HG001-acquisition-manifest.json) retains every eligible object's rank, URL, size, ETag, and the selection limits. It is proposed and unacquired.

Without a size filter, the first of 73 objects per flowcell is [PAW79146 shard 69](https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG001/PAW79146/pod5/PAW79146_c6420e1f_4af91fd6_69.pod5), 2,507,317,056 bytes, and [PAW81754 shard 30](https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG001/PAW81754/pod5/PAW81754_150d2e3f_062ac2e7_30.pod5), 25,462,675,784 bytes. Total is 27,969,992,840 bytes, 26.05 GiB.

Reserve those two files as the initial prospective cohort. A separate expansion uses four nominal run-time strata per flowcell, indices 0-17, 18-35, 36-53, and 54-72. Choose the minimum hash within each stratum without size filtering.

| Flowcell | Selected indices | Respective bytes |
|---|---|---|
| PAW79146 | 16, 21, 48, 69 | 19,407,049,528; 15,532,929,728; 10,358,548,568; 2,507,317,056 |
| PAW81754 | 1, 30, 38, 57 | 34,282,176,592; 25,462,675,784; 19,597,053,736; 7,168,630,880 |

Total is 134,316,381,872 bytes, 125.09 GiB. Verify actual read timestamps after acquisition. Index strata are nominal hourly strata, not verified timestamps. The reported 317 GiB free with a 30 GiB floor leaves about 162 GiB after raw acquisition. Independently budget tensors, graph indexes, native outputs, and retained failures. Metadata size alone cannot establish enough workspace.

An initial option restricts eligibility to objects at most 3 GiB before ranking. Nine and four objects qualify. It selects shard 69 in both flowcells, totaling 5,293,068,328 bytes, 4.93 GiB. Truth, draft phase VCF, and indexes add approximately 0.27 GiB. This late-run restricted sample is useful for qualification, not a representative paper cohort. No outcome-based rerolls or post-failure replacements are allowed.

## Freeze the caller and keep truth outside it

Before confirmation, freeze source, weights, hypothesis construction, graph revision, thresholds, score margins, flanks, abstention, masking, and statistical plan. Keep scored-core bases out of flank inference. Audit HG001/NA12878/GM12878 aliases, both haplotypes, relatives, duplicates, and derived graphs. Rebuild the prior from retained donors. Removing path names alone does not remove donor contributions to alleles or counts. Shared alleles supported by retained donors remain. Public vendor training membership remains unknown, so claim holdout from this project's selection only.

An independent evaluator holds truth and arm identities until outputs and execution receipts are final. Maintainers receive integrity reports without accuracy results. Audit prior exposure before calling HG001 prospective. Any unblinding spends this confirmation set. Later tuning requires a new holdout.

Compare unchanged native HAC and SUP, the frozen treatment, and a matched reference-free control. Declare the targeted native tier before freezing. A HAC gain does not establish SUP superiority. Treatment and reference-free control share hypotheses, native inference, emission, margins, and compute settings. Only the prior differs. Preserve native hypotheses and escape alternatives even when absent from the panel. Truth never inserts a candidate hypothesis.

## Challenge private alleles near actual edits

Predeclare distinct strata and report each separately.

1. Naturally panel-absent alleles are truth-supported HG001 alleles absent from all allowed panel sequences under equivalent haplotype representations. The evaluator identifies them without exposing labels to the caller. Report retention of native-correct ALT and recovery of native-missed ALT.
2. Held-out real alleles remove every panel occurrence of predeclared alleles and linked paths before prior construction. Preserve raw signals and identical hypotheses. This tests real molecules under deliberately incomplete panels. Truth-targeted removal is an engineered challenge, not natural allele novelty.
3. Wrong-prior controls use predeclared incompatible haplotypes or reversed prior support on real signals. Require abstention or retention of signal-supported ALT. Keep synthetic sequence/current corruption and oracle truth-in-hypothesis diagnostics separate. Neither establishes biological generalization.

Use representation-aware local haplotype matching. Report changed cores, 100/500-base neighborhoods, and untouched windows separately. Count missing correct hypotheses as coverage failures, not successful abstentions. Gains elsewhere never compensate for ALT-to-REF conversion or ALT loss. Abundant distant unchanged ALT observations cannot satisfy local safety.

## Hard gates and limits of inference

Require every parent accounted for, unchanged failures disclosed, at least 99.5% matched reference exposure, and zero baseline ALT-window losses. Retain existing 1% invariant-error improvement and strictly negative parent-cluster and 1 Mb block upper error-delta bounds in both 100/500 domains, against native and the matched reference-free control. Label invariant error as a reference-agreement proxy. Independently qualified haplotype error and allele retention are necessary for biological claims.

Require at least 100 ALT observations at 20 distinct sites per SNV, insertion, and deletion class. Additionally require those denominators in edited or near-edit private-allele challenges. Unsupported classes remain unresolved. Reads, duplex molecules, sites, blocks, flowcells, and donors are different units. Use paired molecule and genomic-block uncertainty within donors. Donors, with family clustering, support generalization. Two HG001 flowcells remain one donor.

Zero losses among 100 independent sites still permits approximately 3% loss at a one-sided 95% bound. Roughly 3,000 independent sites are needed to bound loss below 0.1%; repeated reads do not supply those sites. No donor-level power calculation is currently qualified. Estimate paired effects and variance using development only, then freeze sample size and multiplicity before confirmation. The five prospective GIAB donors cover only three family groups and cannot establish broad population safety.

Measure complete signal-to-output time, including inference, retrieval, prior construction, correction, I/O, and any required mapping. Separate one-time graph preparation, cold starts, and steady-state runs. Use matched repeated runs and report signal-seconds, accepted bases, failures, clipping, peak memory, and disk. A speedup claim requires a paired confidence bound favoring total runtime with all accuracy/yield gates satisfied. Cached tensor replay timing cannot supply that claim.

The next acquisition gate is independent review of the frozen 26.05 GiB HG001 manifest, an exposure audit, verified donor exclusion, adopted endpoints, and an output/storage budget. The 125.09 GiB expansion remains separate and requires its own reserve. Keep outputs blinded. After acquisition, verify POD5 integrity, sampling metadata, read/duplex identity, and sufficient near-edit truth support before admitting confirmation. No GPU or data acquisition ran here.

Local metadata evidence and all proposed selections are retained in ignored `logs/retrieval-confirmation/`. S3 listings preserve sizes, ETags, and modification dates; multipart ETags are not MD5 checksums. `uv run --no-sync python logs/retrieval-confirmation/verify-metadata.py` passed all 146 frame records and both selections. This resolves metadata consistency and cost, not native decoding or scientific validity.
