# Registered reference and index lineage trace

This is a source/metadata-only trace. No mapper, faidx, decompressor, index build, reference hash or scientific body read ran in this turn. The current genuine pilot remains held.

The registered index metadata exists at `/home/jake/Projects/nanopore_basecaller/provenance/index-built.json`,2270bytes. It records final index `references/GRCh38-lr-hq.mmi`,5756270073bytes, SHA256 `611b2a45bc41e8bbd3048ef96efebcfae4cf611360d81c3553285932de4a63aa`. It names producer `logs/20261022T203644Z-reference-minimap-index-MuzBtu` and pins command/cwd/clocks/time/exit/stdout/stderr plus minimap2. `index-qualified.json` preserves that build and later native parity metadata.

The recorded build command is:

```text
/home/jake/Projects/nanopore_basecaller/software/bin/minimap2 -x lr:hq -I 16G -t 16 -d /home/jake/Projects/nanopore_basecaller/results/reference-6sc5nylu/reference.mmi /home/jake/Projects/nanopore_basecaller/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz
```

The build metadata records compressed-reference SHA256 `3c8def6d325c5d1e934b2dd530c4d1709f027677a15859467071fddf3fff2026`. It does not record an index build at the final index path against the decompressed FASTA in the current F1 resource contract. The original command output index was a temporary path. This does not show that the retained index is wrong. It shows that the current exact-path producer tuple and F4 terminal contract cannot be filled by relabeling this metadata.

A source-turn stat census found all eight original raw files present at their registered sizes. It returned1 for the absent temporary `results/reference-6sc5nylu/reference.mmi` and absent `terminal.json`/`outer-terminal.json` in the original build run. The metadata's index pin names the final MMI. No separately named temporary-output body pin or terminal tree proof was found in that registered build record. Missing old terminal fields are not reconstructed from a new verification.

The configured decompressed FASTA is `/home/jake/Projects/nanopore_basecaller/logs/20261022T232044Z-accuracy-reference-decompress-2BpPCr/stdout`, SHA256 `9cce8b926416dd96b152deea85188495b75f7ac8d634cc723a017067be8702b7`. Its retained74-byte command is `gzip -cd references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz`. A qualified transformation/custody record connecting those two reference file pins and the temporary/final index is still required by the strict F1 consumer. No new transformation or producer is authorized here.

A registered faidx stage exists at `/home/jake/Projects/nanopore_basecaller-reference/results/reference-assisted/pilot-v1/shared/stages/reference-faidx/1792723830849909908-c9a7e25f/finish.json`,10771bytes. It reports exit0 and actual clocks for:

```text
/usr/bin/samtools faidx --fai-idx /home/jake/Projects/nanopore_basecaller-reference/results/reference-assisted/pilot-v1/reference.fai /home/jake/Projects/nanopore_basecaller/logs/20261022T232044Z-accuracy-reference-decompress-2BpPCr/stdout
```

That FAI output differs from the current configured `.../stdout.fai`. The metadata does not supply an exact produced-file pin for the configured FAI plus a normalized source/terminal proof satisfying `prefix-reference-lineage/1`. The original index receipt also lacks F4-style group/cgroup/reap terminal proof. It is historical build/parity evidence, not a fabricated new F4 completion.

Precise blocking artifacts are a qualified retained custody/transform record for compressed reference to configured FASTA and temporary to final index, an exact produced pin/producer for the configured FAI, and available source/terminal evidence accepted by the strict consumer. `index_provenance:null` and `producer_sources:[]` remain unchanged. Resolving historical custody may require a separately reviewed consumer extension; it must preserve these limits and use retained successful producers rather than repeat them automatically. No new index or faidx production is proposed by this source trace.
