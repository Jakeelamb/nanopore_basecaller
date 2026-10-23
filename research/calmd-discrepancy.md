# Stock validation MD discrepancy

Investigation completed on 2026-10-22 at approximately 21:53 UTC. The investigated unit is `full-validation-hac` in `results/stock/stock-20261022`.

The retained Dorado alignment and samtools `calmd` output have identical alignment fields, sequences, qualities, NM values, and other tags. Exactly two primary records differ in their MD tags. Seven reference ambiguity symbols appear as `N` in Dorado and as `Y`, `W`, or `K` after `calmd`. Native `samtools faidx` confirms every replacement against the pinned reference.

This is a loss of reference alphabet information in minimap2 MD generation. The observed difference does not change the reference disagreement counts. Exact MD agreement with the original reference remains false. Calling the two MD annotations identical would overstate the evidence.

## Retained evidence

The original verifier `5b0c5cd0a3fd5869cee3d545a3c4e3b0c4b5eb1dbe73addeb314c548b9233f2e` rejected the unit with `Native calmd changed primary NM/MD or alignment`. The failure remains in `results/stock/stock-20261022/units/full-validation-hac/observation-failure-1792705439201061764.json`. All investigated native producer receipts have exit status zero.

Two recorded diagnostics inspect the existing outputs. They do not repeat basecalling or alignment, and they do not modify the original artifacts.

- `logs/20261022T215126Z-calmd-discrepancy-exact-afyDiw` verifies every pin in the base decode, aligned decode, calmd, and calmd decode finish receipts. It compares primary records, walks the MD and CIGAR coordinates, and executes native `samtools faidx` for the seven changed positions. Exit status is zero. Its JSON stdout SHA-256 is `8a1ad2e77dc14916bbda3adc6d06b174d852cebd478e90cc9c2970bb67d036e0`.
- `logs/20261022T215228Z-calmd-discrepancy-all-records-CC4Esi` compares every record in order. It requires equality of all 11 SAM core fields and checks that only the two known MD tags differ. It also verifies the seven replacements against the retained faidx output and inspects the pinned minimap2 encoding table. Exit status is zero. Its stdout SHA-256 is `99b20ed86b89145ec2184544ae9e9e5db90a5918c0d5917ea454b4f4ea867b79`.

Each directory contains the complete replayable `command.sh`, command clocks, stdout, stderr, and exit status. Replay with `bash <directory>/command.sh` from the recorded `cwd.txt`.

The compared SAM files contain 2,906 records each. There are 2,039 primary records and 867 nonprimary records. Both changed records are primary. The other 2,904 records have identical core fields and tag values. Header changes introduced by samtools program records do not enter this comparison.

| Producer output | Retained path | SHA-256 |
| --- | --- | --- |
| Dorado alignment decoded as SAM | `logs/20261022T214310Z-stock-61b976bd45534773a49d2c08bb4acb55-VLjiYW/stdout` | `a3598bc4d50f3398402604ac9cfdeed3760b383326b4927359adbeaffc354b0b` |
| calmd decoded as SAM | `logs/20261022T214352Z-stock-c54371500fad4e5d894c5341df246cbc-RkmedW/stdout` | `51bccd355327b36f5793be57f4e4a08d5f0ea9d40169912734c52fe31c1e4228` |
| calmd stderr with both MD warnings | `logs/20261022T214342Z-stock-3e34acd7f26b43aeb281eebf6668456e-WVpYCj/stderr` | `7a842d3a96935e2213cc9fc131fdda6a91f14f63152815cad4000cabf0495a7e` |
| Complete reference FASTA gzip | `references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz` | `3c8def6d325c5d1e934b2dd530c4d1709f027677a15859467071fddf3fff2026` |

## Exact differences

Read `2f607612-55f6-44ba-9ebb-b3c70b3000bf` has flag 0 and begins at `chr2:233132096`. Its NM is 1,342 before and after `calmd`. Read `9717a5f0-f3ae-400f-bba4-077c91352810` has flag 16 and begins at `chr12:122069298`. Its NM is 267 before and after `calmd`.

All positions below are one based. Query positions refer to the SAM sequence in reference orientation, including soft clipping. Every changed position has CIGAR operation `X` before and after `calmd`.

| Read UUID prefix | Reference coordinate | SAM query position | Query base | Dorado MD | calmd MD | Native faidx |
| --- | --- | --- | --- | --- | --- | --- |
| `2f607612` | `chr2:233142970` | 11030 | C | N | Y | Y |
| `2f607612` | `chr2:233143703` | 11765 | T | N | W | W |
| `2f607612` | `chr2:233143709` | 11771 | T | N | Y | Y |
| `2f607612` | `chr2:233143729` | 11791 | C | N | Y | Y |
| `2f607612` | `chr2:233144847` | 12968 | G | N | K | K |
| `2f607612` | `chr2:233145086` | 13207 | T | N | W | W |
| `9717a5f0` | `chr12:122093260` | 24008 | C | N | Y | Y |

The MD match counts, mismatch positions, and deletion strings otherwise agree. The diagnostic retains the full old and new MD strings rather than only these excerpts.

## Source mechanism

Dorado source revision is `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. Its ONT minimap2 wrapper revision is `3a7e4e229de46f4565ec7db727748e2122181d4f`. The nested minimap2 source revision is `3c28777e7e2dcc90f825de1b9f17a89cca7d4452`.

- `software/dorado-src/dorado/aligner/Minimap2Aligner.cpp:642` calls `mm_gen_MD` for the BAM MD tag. `dorado/alignment/minimap2_args.cpp:25` enables native MD output.
- Nested minimap2 `sketch.c:9` defines `seq_nt4_table`. Its entries encode A, C, G, and T as 0 through 3. All reference ambiguity symbols tested here encode as 4.
- Nested minimap2 `index.c:359` stores reference sequence through that table. The index therefore loses the distinction between Y, W, K, and N.
- Nested minimap2 `format.c:302` generates MD using the alphabet `ACGTN`. Both mismatch and deletion reference bases come from that reduced alphabet. `format.c:333` obtains the reference sequence from the index.

Samtools is the installed version 1.24 with htslib 1.24. The [official 1.24 calmd source](https://github.com/samtools/samtools/blob/1.24/bam_md.c#L83) reads the original reference bases and writes their uppercase symbols to MD. Its reference fetch occurs in `get_ref`, and its MD comparison reports the two warnings. The official [calmd manual](https://www.htslib.org/doc/samtools-calmd.html) identifies version 1.24 as released on 2026-07-09 and documents those warnings.

The fetched official source is retained by `logs/20261022T215228Z-calmd-official-source-TKRmsK`, with exit status zero. Its stdout SHA-256 is `3f2ade44f1d26a8b511a6b27194103eb838d6836a8ea84041f08ac402bf8206a`. The source trace diagnostic also retains hashes of each relevant local Dorado and minimap2 source file.

The [SAM optional fields specification](https://samtools.github.io/hts-specs/SAMtags.pdf), revision `a71164e` dated 2024-09-09, defines MD as the mismatched and deleted reference bases. Its NM definition counts ambiguous reference symbols as mismatches even when compatible with the query base. Thus the seven `X` operations and unchanged NM counts agree with that definition. The two MD strings preserve the same alignment disagreement positions, but Dorado cannot reconstruct the exact original ambiguity symbols from its index.

## Scientific disposition

The observed failure does not establish a basecalling or alignment error. It establishes a stock MD annotation limitation at seven ambiguous reference bases. Both alignments and every NM value agree with native calmd across this unit. Its existing reference disagreement proxy, which derives from NM and EQX CIGAR counts, is unchanged by these seven annotations.

A verifier can distinguish this case without discarding the reference check. It would require exact equality of every other record field and tag, unchanged NM, unchanged MD run structure, and a retained coordinate check showing that each stock `N` replaces the actual non-ACGT reference symbol reported by calmd. Every difference would remain an explicit exception in the observation. A blanket removal of MD checking, global replacement of every MD ambiguity symbol, or acceptance of arbitrary N substitutions would exceed this evidence.

The original failed observation remains a failed observation under its original verifier. A corrected observation can reuse these pinned native producer artifacts after a separately tested verification change. There is no scientific reason in this discrepancy to repeat the GPU basecall.

This investigation qualifies only this retained unit and its exact differences. It does not establish basecalling truth, variant accuracy, reference completeness beyond the existing reference qualification, or behavior on other unexamined stock outputs. It does not alter the stock controls, protocol, runner, or tests.
