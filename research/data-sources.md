# Human native-signal data selection

Verified 2026-10-22 using anonymous S3 ListObjectsV2 and HTTP HEAD. No POD5 object was downloaded during this investigation. This is a bounded pilot dataset, not a representative whole-genome benchmark.

## Recommendation: 3,209,530,648 bytes of raw signal

Use two HG002 flow cells for development and validation and an HG005 flow cell for a sealed cross-sample test. HG003 is HG002's father; HG005 comes from the other GIAB trio and is the stronger sample holdout. The [ONT release announcement](https://epi2me.nanoporetech.com/giab-2025.01/) (published 2025-01-05) identifies HG002 as GM24385, HG003 as GM24149 and HG005 as GM24631; it specifies PromethION, SQK-LSK114, R10.4.1 E8.2 400bps v5.0.0 basecalling and two flow cells per sample. The files below are raw POD5, not FASTQ or move tables.

| Role | Sample / flow cell | Bytes | S3 LastModified UTC | ETag (quotes omitted) |
|---|---|---:|---|---|
| Development | HG002 / PAW70337 / shard 33 | 555,013,832 | 2025-01-15T00:23:04Z | e5491bb43a46f9579defeff48d251065-67 |
| Validation | HG002 / PAW71238 / shard 10 | 479,362,680 | 2025-01-15T02:24:55Z | 02fd156f4b0d185668d8361023ade697-58 |
| Sealed test | HG005 / PAW87816 / shard 52 | 2,175,154,136 | 2025-01-16T01:53:11Z | 17dad61a6610ce9aea855441b3aca1f6-260 |

Exact download URLs:

- https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG002/PAW70337/pod5/PAW70337_66b2eea5_de8117b1_33.pod5
- https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG002/PAW71238/pod5/PAW71238_a8351990_11d77535_10.pod5
- https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG005/PAW87816/pod5/PAW87816_017ec17c_cb358aeb_52.pod5

Total is 3.210 decimal GB / 2.989 GiB. HTTP HEAD returned 200 and exactly these Content-Length values; see [retained headers](../provenance/selected-pod5-heads.json). Multipart ETags are object identifiers, **not file MD5 checksums**; compute SHA-256 after download. Recheck size/ETag before transfer and fail if they drift.

Selection rule: enumerate every `pod5/` object for the two HG002 flow cells; sort by `(Size, Key)` and take the smallest per flow cell. Enumerate both HG005 flow cells and take their global minimum by the same rule. Listings are complete (`IsTruncated=false`): HG002 PAW70337 156 objects, PAW71238 149; HG005 PAW87816 53, PAW88001 53. No complete HG005 shard is in the requested 0.5–1.5 GB range; the alternative flow cell's minimum is 2,602,686,144 bytes. Retained [listing retrieval URLs/times](../provenance/listing-retrievals.json) point to exact XML snapshots in `provenance/`.

The HG005 minimum is the highest numbered shard (52 of 0–52), consistent with a final partial output container; shard numbering alone does not establish acquisition-time coverage. Smallest-shard selection minimizes transfer, but may overrepresent a run's final, low-yield, short-read, or otherwise unusual batch. Those mechanisms are plausible **inferences**, not established by filenames or byte size. Inspect read count, acquisition IDs, channel/start-time, duration, signal length and mapping distributions after download; retain this selection as a smoke-test cohort, and expand using a predeclared random shard/read sample before making generalization claims. Do not select shards based on observed accuracy. An object is a container, not a random biological sample.

## Chemistry and acquisition evidence

The [HG002 PAW70337 final summary](https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG002/PAW70337/final_summary_PAW70337_66b2eea5_de8117b1.txt) gives FLO-PRO114M / SQK-LSK114 / 400, instrument PC48LILITH, acquisition `de8117b1abf27d6d4ac91526772636b9a5ca7fde`, starting 2024-06-19T13:42:14.753153+01:00. The [HG005 PAW87816 final summary](https://ont-open-data.s3.amazonaws.com/giab_2025.01/flowcells/HG005/PAW87816/final_summary_PAW87816_017ec17c_cb358aeb.txt) gives the same protocol chemistry, instrument PCAMP151, sample `hg005`, acquisition `cb358aebdab3a85a68a2180f8cfcf5dae3cd451c`, starting 2024-09-11T11:29:15.634661Z. Thus the holdout is separated by both sample and acquisition/device.

The [pinned Dorado v0.8.2 model table](https://github.com/nanoporetech/dorado/blob/v0.8.2/README.md#available-basecalling-models) identifies v5.0.0 R10.4.1 E8.2 400bps models as 5 kHz. Model compatibility alone is weaker than raw metadata: after download require every selected POD5 run-info entry to report sample_rate=5000 and the expected flow cell, kit and acquisition. Record its internal sample identifier separately from the published donor assignment. Do not resample 4 kHz signal into this cohort. The report JSON for each selected flow cell directly reports `sample_rate=5000` in all four acquisition entries; exact source URLs and JSON pointers are retained in [report-sample-rate-evidence.json](../provenance/report-sample-rate-evidence.json). Final summaries are also retained under `provenance/`.

Every acquired read was subsequently decoded with POD5 0.3.49. All 20,954 reads have nonempty signals, matching sample counts, 5 kHz run metadata, the expected flowcell and LSK114 kit, and finite physical-current calibration with positive scale. No read UUID overlaps the three groups. Frozen membership hashes and full metadata summaries are in `provenance/signal-inventory.json`; raw read-level metadata and membership lists stay in `data/splits/`. The execution receipt is `logs/20261022T205930Z-complete-human-signal-inventory-hVM6Sz`.

| Role | Reads | Electrical samples | Internal POD5 sample ID | Observed read-start range, seconds into acquisition |
|---|---:|---:|---|---|
| Development | 2,608 | 641,769,607 | ONLL08362 | 31,931.3184 to 32,178.2158 |
| Validation | 2,027 | 553,650,293 | ONLL08364 | 4,838.5176 to 34,944.0874 |
| Test control | 16,319 | 2,554,852,800 | hg005 | 181,924.5594 to 188,159.2176 |

The total is 3,750,272,700 electrical samples. These observed ranges and unequal read counts confirm that the shards cover different acquisition periods and distributions; they do not establish random sampling. Donor labels come from ONT's published sample/flowcell mapping, rather than the literal internal sample-ID strings or an independently genotyped identity check.

## Reference and truth

The initial investigation considered the [GIAB masked-v2 FASTA](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/references/GRCh38/GCA_000001405.15_GRCh38_no_alt_analysis_set_maskedGRC_exclusions_v2.fasta.gz). The accepted protocol instead pins the unmasked `GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz` supplied by GIAB, including its publisher `.fai` and `.gzi`, as a common alignment baseline. See [the final protocol](protocol.md) for that explicit choice and its limitations. Preserve the exact contig dictionary; do not mix similarly named GRCh38 revisions. The [NIST GIAB page](https://www.nist.gov/programs-projects/genome-bottle), updated 2026-05-12, identifies GIAB references and currently states that HG002 v5.0q supersedes v4.2.1. Pinning v4.2.1 below is a matched historical pilot choice for HG002 and HG005, not a claim it is the latest HG002 truth.

Verified exact benchmark directory contents via HTTPS (browser fetch failed, curl succeeded):

- [HG002 v4.2.1 GRCh38](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/GRCh38/): `HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz`, `.tbi`, and `HG002_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed`.
- [HG005 v4.2.1 GRCh38](https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/ChineseTrio/HG005_NA24631_son/NISTv4.2.1/GRCh38/): `HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz`, `.tbi`, and `HG005_GRCh38_1_22_v4.2.1_benchmark.bed`.

Scientific interpretation: GRCh38 is not the individual's diploid sequence. A reference alignment mismatch conflates true genotype variation, alignment ambiguity, reference error, and basecalling error. For training labels, prefer validated sample-specific phased haplotype sequence within confident regions; a plain GRCh38 label is reference-biased supervision. Restrict an initial reference-identity metric to confident autosomal regions, mask known variant sites with suitable indel context, and report that it is a proxy. Variant VCF/BED truth evaluates downstream variant calling; it does not provide signal-to-base alignment or complete per-read truth. Never label a read by blindly applying both unphased alleles to one reference.

## Split and contamination boundaries

Freeze a manifest before model tuning. Development uses only PAW70337; validation only PAW71238; sealed test only HG005 PAW87816. Deduplicate read UUIDs across files before accepting the split, and keep every chunk/window from a read and its duplex partner in one split. Flow-cell isolation prevents run overlap but HG002 validation still shares the individual's genome. Predeclare disjoint chromosome/interval subsets if assessing sequence novelty, including a buffer against overlapping read/chunk leakage. HG005 is a cross-sample check, not proof of novel sequence: human genomes share most sequence.

For a teacher-supervised pilot, Dorado outputs are pseudo-labels, so gains against those labels show teacher agreement. No opened source provides a sample/run-level vendor training manifest excluding HG002 or HG005. Both are widely published benchmark samples; contamination of vendor models by these samples, related runs or their sequences is unresolved. Do not call either a clean vendor-unseen test. A newly collected independently consented run with documented training exclusion would be needed for that stronger claim.

## Rights and unresolved checks

The [AWS registry entry](https://registry.opendata.aws/ont-open-data/) lists the bucket license as **CC BY-NC 4.0**, anonymous access and EU-West-1 hosting. Attribute Oxford Nanopore Technologies, record access date, and preserve the license reference. Public access is not a commercial-use grant; this source does not establish commercial training permission. The registry is bucket-level and has older sample descriptions; no separate dataset-specific license object was found in the top-level `giab_2025.01/` listing. This is the observed licensing evidence, not a legal determination.

Remaining gates: inspect POD5 read/run metadata and nonempty read counts, verify hashes and split disjointness, qualify label construction, inspect distribution bias, pin all model/reference/truth revisions, and document commercial rights if required. No large raw-data download, basecalling, training or accuracy experiment was performed by this investigation.
