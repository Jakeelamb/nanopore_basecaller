# Current-resource attestation from retained legacy evidence

Design and bounded metadata inventory only. No reference/gzip/MMI body hash, decompressor,faidx,indexer,mapper,model/neural producer,test or new qualification ran. Existing F4 code/config/tests/evidence and all source-owner/F1 files remain unchanged. Heavy files were STAT-only; three7804-byte FAI metadata files were hashed and limited FAI rows inspected.

A small explicit current-resource attestation appears feasible without rebuilding resources. The old index metadata already records the final MMI body pin. All three current FAI paths have the same registered FAI bytes. Remaining decisive observations are fresh large-file pin checks plus streamed gzip-content equality under a newly admitted supervised unit. This would qualify the currently observed resource bytes/provenance for a later consumer,not recreate old process admission or terminal evidence. F1's present strict guard remains held until its owner and Root accept an explicit new contract branch.

## Exact inventory

Paths use B=`/home/jake/Projects/nanopore_basecaller`,R=`/home/jake/Projects/nanopore_basecaller-reference`,D=`B/logs/20261022T232044Z-accuracy-reference-decompress-2BpPCr`.

| Resource | Bytes | SHA256 and present observation |
|---|---:|---|
| B/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz | 886344618 | Registered `3c8def6d325c5d1e934b2dd530c4d1709f027677a15859467071fddf3fff2026`;current size matches,no body hash here |
| D/stdout | 3144230986 | Registered `9cce8b926416dd96b152deea85188495b75f7ac8d634cc723a017067be8702b7`;current size matches,no body hash here |
| B/references/GRCh38-lr-hq.mmi | 5756270073 | index-built registered final-output `611b2a45bc41e8bbd3048ef96efebcfae4cf611360d81c3553285932de4a63aa`;current size matches,no body hash here |
| B/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz.fai | 7804 | Current metadata hash `502a1b8fb73ccd53285c28a0f12df90c818b4fe3de1e862ef47c593ef1a0a4b4` |
| R/results/reference-assisted/pilot-v1/reference.fai | 7804 | Same current metadata hash `502a1b8fb73ccd53285c28a0f12df90c818b4fe3de1e862ef47c593ef1a0a4b4` |
| D/stdout.fai (F1 configured path) | 7804 | Same current metadata hash `502a1b8fb73ccd53285c28a0f12df90c818b4fe3de1e862ef47c593ef1a0a4b4` |

The configured FAI's bytes therefore match the registered/publisher FAI metadata now. Its problem is missing path/producer custody,not observed different FAI contents. `reference-qualified.json` records195contigs and3099922541bases,including chr1 length248956422 and chrEBV171823. Old index stderr reports the same195targets/3099922541bases. A new attestation must compare the complete FAI contig-name/length mapping with that registered dictionary; total/count equality alone is insufficient. Stream-byte equivalence to the exact decompressed FASTA would also preserve FAI offsets/line layout; no new faidx production is needed merely to establish that equivalence.

Registered metadata/source pins:

| Artifact | Bytes | SHA256 |
|---|---:|---|
| B/provenance/index-built.json | 2270 | `230fa45b7c8f0419029b1fdc7374ed5c4d773fae2090041cf623b77f802406a6` |
| B/provenance/index-qualified.json | 55432 | `cd003cf4a6c3f49be322345ab833cbaacc5861e6141aa79199fb97c3f93e77b2` |
| B/provenance/reference-qualified.json | 7248 | `b384876db13821c6dcc27db9cb04badec1280e61f1d62221e7ee26f7df884b53` |
| R/results/reference-assisted/pilot-v1/shared/stages/reference-faidx/1792723830849909908-c9a7e25f/finish.json | 10771 | `56d45a4997f32e3d80641994c85106c61e8c2517b54943495fcf8a339e8b6ca5` |
| B/scripts/prepare-reference.py (current source) | 12278 | `2467d465aa2bbe3ea47653d91858db235c55e3f4df775f74dda956ac20bbb84e` |
| B/scripts/record-command.sh and R/scripts/record-command.sh | 716 each | `f3e0f628d3a32ef0551537ad4acb8585c0690b9203e3f48f765110703e397833` |
| F1 research/prefix-loop-reference-lineage.md | 4033 | `4458287ce29bcdee49cda8fd941580bbdaa5f74445b881c8422c5ffdeeec952d` |

Current prepare-reference.py:128-135 calls output.rename(index),then pins the final index and writes index-built.json. That source path explains the temporary/final registration shape. No historical controller-source pin was recorded in index-built.json,so the current source is explanatory evidence,not independent proof that this exact source executed then. The metadata directly registers the final MMI pin,so a fresh current MMI digest can be compared with an existing old output pin; inventing a temporary-file pin is unnecessary.

## Original producer tuples and raw eight

I=`B/logs/20261022T203644Z-reference-minimap-index-MuzBtu`;F=`R/logs/20261023T025030Z-stock-662c2e1a84ea4ba59671b42d47dd505b-60XKon`. All listed raw files exist at these sizes. Raw metadata hashes were checked; D/stdout's large scientific body was only statted,with its declared output pin retained.

| Raw filename | I bytes / SHA256 | D bytes / SHA256 | F bytes / SHA256 |
|---|---|---|---|
| command.sh | 273 / `09bc7e12864d5ca06c4692c72615cc1c7e3acb90d05c52f03d0f069392fc21ea` | 74 / `17f0c4920a4235c5559812004b699c5a6926153177857d6c6c65ce75be72eb6c` | 241 / `a7ed76d13cf142260bf68809d42aeecfa9624c421fbc5fecff20e82ffbe838f5` |
| cwd.txt | 40 / `bd073809cf999aea145c499a706348860b7480951370b2d599a82a0e4d7cd8e4` | 40 / `bd073809cf999aea145c499a706348860b7480951370b2d599a82a0e4d7cd8e4` | 50 / `4969ee9fdf64dcbba9d0d63b74eb5c33b8b000e13023b0957f7343303b7f4ae1` |
| start.txt | 21 / `f42b76150244c676eaadf157a37fc05d191d67b24fee863cda4da5ca16f183dc` | 21 / `2013a059500d50e90cdc53c9d34b10743246f04cbe6365ea5ee1a20bd6d7bce6` | 21 / `61a9d647b9c4bf84d65a565e266437a07fa0817dd424d5a4bed98ddb46fdcdc3` |
| end.txt | 21 / `14c8d854cc740c7b6f4ddb3bf0ad9a9395bb043c814861601d0640dd209f03ca` | 21 / `9477467e9d96ad2ccfcd9c4107d28be64dd3d84d9f19edb0fe0122a817586ce1` | 21 / `b57f5acbb563e33bfb7898847c18502318abdd2174bbe798e8c5f663dfa73166` |
| time.txt | 1009 / `4a59e66b74b46d4c9d7a5320d5586b04aef77352cfb848cd15b0b05dcd0600c2` | 796 / `6e6884c6ab017ac893f46d88731d5b3f05cf4ba80f41778e83bf5b42d5a165c8` | 955 / `0114f00297e47d29e09b344ba5c5441d42311164ebc14f8b7969a8173cea2fa9` |
| exit-status.txt | 2 / `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` | 2 / same exit0 hash | 2 / same exit0 hash |
| stdout | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 3144230986 / registered `9cce8b926416dd96b152deea85188495b75f7ac8d634cc723a017067be8702b7` (not rehashed) | 0 / same empty hash |
| stderr | 784 / `533ea2c1eaf1f5ef2f32465f76793807a6cb145de82d5be8bc0e88d811a8eef0` | 0 / same empty hash | 0 / same empty hash |

Exact old argv,cwd and recorded clocks/exit:

```
I: cwd B; 2026-10-22T20:36:44Z..20:37:49Z; exit0
B/software/bin/minimap2 -x lr:hq -I 16G -t 16 -d B/results/reference-6sc5nylu/reference.mmi B/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz
D: cwd B; 2026-10-22T23:20:44Z..23:20:56Z; exit0
gzip -cd references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz
F: cwd R; actual native clocks 2026-10-23T02:50:30.850957+00:00..02:50:33.102715+00:00; exit0
/usr/bin/samtools faidx --fai-idx R/results/reference-assisted/pilot-v1/reference.fai D/stdout
```

The old minimap2 binary pin is1136248bytes/`d17e2cc99b5fcc840b6506dc884203657fdec57d92faa826f6b9dcb1d2daddba`,source3c28777e7e2dcc90f825de1b9f17a89cca7d4452. It is historical producer identity; no indexer is proposed for execution. The FAI finish preserves original source/command metadata and raw eight but has no produced-file pin for reference.fai. The three current FAI hashes supply a new metadata observation,not a retroactive old produced-file receipt.

## Small proposed contract and unit

Propose an explicit new `prefix-legacy-resource-attestation/1` record accepted only through a separately reviewed F1 contract branch. Its input roles are compressed-reference,decompressed-reference,current-final-mmi,current-configured-fai,registered-publisher-fai,registered-faidx-output,legacy-index-built,legacy-index-qualified,legacy-reference-qualified,legacy-faidx-receipt,and the exact original raw-eight metadata/source pins above. Link the fresh Root grant/source/worker completion and outer-terminal proof. Retain old argv/cwd/clocks/exit and the old missing-artifact list as facts.

The new record should assert only: current full compressed/decompressed/MMI pins equal their registered pins; gzip's streamed uncompressed digest equals the exact current decompressed reference digest; current FAI bytes match the registered502a1b8f pin and their complete contig names/lengths equal the registered dictionary. Bind all paths explicitly,including the configured FAI alias. Record `historical_resource_terminal_available:false`, `historical_admission_requalified:false`, `new_index_built:false`,and observation time/source. Do not manufacture old F4 complete/terminal JSON or relabel the old compressed-input/temporary-output command as a decompressed-input/final-path command.

Use frozen F4 adapter SHA `8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4`,a Root-authored fresh request/digest and fresh global preflight. Its existing input-pin checks can perform the fresh large-file hashing inside the supervised service; do not duplicate those hashes in a second receipt framework. A tiny later-authorized attestation coordinator can parse small FAI/dictionary metadata and launch only this proposed native streaming verification:

```
/usr/bin/bash --noprofile --norc -o pipefail -c '/usr/bin/gzip -cd -- "$1" | /usr/bin/sha256sum; codes=("${PIPESTATUS[@]}"); printf "pipeline-exit %s %s\n" "${codes[0]}" "${codes[1]}"; test "${codes[0]}" = 0 && test "${codes[1]}" = 0' resource-attestation /home/jake/Projects/nanopore_basecaller/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz
```

Require one complete SHA256 output,expected9cce8b92...,both pipeline exits0,and no decompressed output file. This is a prospective command,not executed or qualified here. `/usr/bin/gzip`109768bytes and `/usr/bin/bash`1195144bytes were statted; current executable content pins must still be obtained under Root admission and frozen before use. The coordinator source and new F1 acceptance branch also do not yet exist in this F4 scope. No source implementation was authorized by this design unit.

Proposed hash-unit caps: <=300s,CPU2,RAM4GiB,AS8GiB,swap0,growth100MiB,cumulative4GiB,free reserve30GiB. No MMI is loaded by an aligner and no3GB decompressed artifact is written. Keep output roots in a fresh owned F4 attempt,including TMPDIR; retain raw command/cwd/time/stdout/fullstderr/exit and new group/cgroup-empty proof. Root separately reports a later16/24GiB engineering-profile canary passed23controls/0skip,complete `d61318aa814aeb699a9a1421b4ef511e3d5a3bd6d3ae98d1fc7ca82995225298`,with fresh global preflight. That is supplied profile evidence,not reference-body verification or repair of the earlier global-preflight gap. The actual mapper/pilot still needs separate admitted resource evidence and its own command; this attestation would not establish biological behavior.

## Exact unresolved historical artifacts

Source-turn stat returned ENOENT for B/results/reference-6sc5nylu/reference.mmi,I/terminal.json and I/outer-terminal.json. The build metadata supplies a final-output pin but no separately registered temporary-output pin or old controller source pin. The faidx finish lacks a produced-file pin for reference.fai. Fresh bytes/equality checks can support a new current attestation if they pass; they cannot resolve those historical absences. If F1's contract continues to require old process-terminal evidence rather than an explicit current-attestation variant,the pilot remains blocked by precisely those missing old artifacts. No guard was changed here.
