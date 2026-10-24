# Candidate A: native stages with immutable attempt receipts

Design only, 2026-10-22. Writable ownership is this file only. No project files were edited and no basecalling or benchmark was launched.

## Recommendation and usage

Use one small Python orchestration/report script, the existing command recorder, stock Dorado, stock samtools, and a minimap2 executable built from Dorado's exact nested source revision. Keep the data path native: POD5 -> stock unaligned BAM -> stock aligned BAM -> native summaries. Python joins identities, verifies evidence, and formats reports. Do not introduce a biological scorer, workflow engine, database, Rust computation crate, or candidate basecaller yet.

The proposed public surface is three commands, not implemented by this design:

```sh
uv run --frozen scripts/benchmark.py prepare --plan config/stock-benchmark.json
uv run --frozen scripts/benchmark.py run --plan config/stock-benchmark.json
uv run --frozen scripts/benchmark.py report --plan config/stock-benchmark.json
```

`prepare` checks assets, freezes native metadata/read UUIDs, prepares reference/index, qualifies adapters on tiny genuine producer artifacts, and prints a readiness receipt. The coordinator then alerts the user that the stock binary, all signals, models, and complete reference passed. The current instruction already authorizes the subsequent stock runs, including HG005; the alert is informational, not another approval gate. `run` executes a fixed schedule serially. `report` can repair derived summaries from retained successful BAMs without repeating GPU execution. Any failed or interrupted attempt stops the schedule and remains immutable; an explicitly requested new attempt gets a new directory.

The 2026-10-22 benchmark brief supersedes the older setup-only deferrals in `research/protocol.md`, including the HG005 stock-processing deferral. It does not authorize future candidate selection from held-out stock outcomes. Record that scope override in the plan. Preserve the development/validation/sealed-test labels and future training boundaries.

## Grounded tool contract

All Dorado source pointers below are relative to `software/dorado-src`, HEAD `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`, verified with `git rev-parse HEAD` in this review. The actual stock executable/archive/model trees still require qualification; source inspection is not binary execution evidence.

| Interface | Exact source-backed behavior | Consequence |
|---|---|---|
| `dorado basecaller MODEL DATA` | `dorado/cli/cli_lib/basecaller.cpp:128-166` accepts an explicit model directory, one POD5 or directory, and newline UUID file through `--read-ids`; zero max reads means unlimited. | Pass one acquired POD5 and its entire frozen UUID manifest per full unit. Never use moving `hac`/`sup` aliases. |
| Device, quality, trim, splitting | `basecaller.cpp:170-174,242-252,267-271,1190-1195`; `cli/cli_lib/include/cli/utils/cli_utils.h:149-164`. `--device cuda:0`, `--min-qscore 0`, `--trim all`, `--batchsize 0` are valid. Splitting is enabled unless `--disable-read-splitting` is passed. | Keep default stock splitting enabled and explicitly pin trimming and quality settings. `0` batch size is stock automatic selection, not a fixed numeric batch. |
| Native length filtering | `basecaller.cpp:629-635`, `utils/include/utils/parameters.h:14`, `read_pipeline/nodes/ReadFilterNode.cpp:32-39` enforce a five-base minimum independently of Q score. | A zero Q threshold does not guarantee every raw molecule emits a record. Enumerate missing parents. Do not invent individual drop reasons. |
| BAM output | `cli/cli_lib/basecall_output_args.cpp:97-105` chooses BAM when no alternative emit type is set. `hts_writer/HtsFileWriterBuilder.cpp:52-81` writes a regular redirected stdout file as BAM but does not sort it; a pipe changes the output mode. | Redirect the recorder's stdout to a regular file, preserve it as the BAM, and sort as a distinct native stage. Avoid an untracked pipeline. |
| `dorado aligner INDEX READS` | `cli/cli_lib/aligner.cpp:90-94,124-135,170-191` accepts FASTA/FASTQ/MMI and an HTS input file, `--no-sort`, `--threads`, and `--mm2-opts`. | Use separate alignment, explicit preset/options, bounded threads, and no inference that stdout is sorted. |
| Minimap options | `alignment/minimap2_args.cpp:18,60-80,85-124,138-159,196-220`: `--mm2-opts` consumes exactly one argv string; accepts `-x`, `-I`, `--eqx`, `-Y`, `--secondary`, etc.; not `-d`. MD tags are always enabled at lines 20-25. | Use the single string `-x lr:hq -I 16G --eqx -Y`. Retain secondary alignments using preset defaults and count them separately. There is no Dorado CLI index writer. |
| Prebuilt index | `alignment/Minimap2Index.cpp:60-97,209-235` loads minimap indexes; a k/w mismatch only warns and continues. MMI-backed BAM headers omit M5/UR. | Reject a k/w mismatch warning; pin MMI hash and producer receipt independently. Compare every output `@SQ` SN/LN with the publisher FAI; do not require M5 on MMI output. |
| Split identity | `read_pipeline/base/messages.cpp:166-171` writes `pi:Z` and `sp:i`; `splitter/DuplexReadSplitter.cpp:652-660` derives child UUIDs from parent UUID and child index. `splitter/splitter_utils.cpp:35-39` preserves the original parent on successive splits. | Raw UUID membership is `pi` if present, otherwise QNAME. An emitted UUID need not occur in POD5. |
| Native summary | `cli/cli_lib/summary.cpp:24-29,94-116` implements `dorado summary FILE`. `hts_writer/SummaryFileWriter.cpp:215-254` skips secondary/supplementary records and emits parent UUID, child QNAME, sequence length and Q score. Lines 374-385 use native CIGAR/NM counts. | Retain basecall and aligned summaries. Join by child UUID. Native field `alignment_accuracy` must be presented as reference agreement, not biological accuracy. |
| Native operation counts | `hts_utils/bam_utils.cpp:235-286` sums M/=X aligned columns, I, D and derives substitutions as NM-I-D. | The new script need not implement edit distance or compare sequence to reference. A tiny structural parser can independently reconcile EQX CIGAR and NM, not score biology. |
| Exit is insufficient | `data_loader/DataLoader.cpp:529-591` can log POD5 errors and continue. `aligner.cpp:204-207` and `summary.cpp:60-63` can successfully process no inputs. | Require complete logs, nonempty decoded records, identity/content checks, and error-free native traversal. Exit zero or file existence alone cannot qualify a unit. |

The host currently exposes `/usr/bin/samtools` version 1.24/htslib 1.24. Its live `stats`, `view`, `quickcheck`, `flagstat`, `sort`, `idxstats`, and `faidx` usage was inspected. Freeze executable SHA-256, version/build output, and native usage in preparation. A later system package replacement invalidates affected plan units rather than silently changing their tool version.

## Exact proposed native commands

The runner resolves all variables to absolute paths before execution and records the resolved argv array. `$D` is the verified stock 2.1.2 binary; `$S=/usr/bin/samtools`; `$MODEL` is one of the two verified extracted model directories; `$RAW` is exactly one manifest POD5; `$IDS` is that file's full frozen UUID list or the predetermined development subset; `$REF` is the original complete pinned compressed FASTA. `$BAM` variables below point to verified parent-stage recorder `stdout` files. No shell interpolation is used by the implementation. The concrete layout follows `scripts/bootstrap.sh:20-31`:

```sh
ROOT=/home/jake/Projects/nanopore_basecaller
D="$ROOT/software/dorado-2.1.2-linux-x64/bin/dorado"
S=/usr/bin/samtools
MODEL_HAC="$ROOT/models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0"
MODEL_SUP="$ROOT/models/dna_r10.4.1_e8.2_400bps_sup@v5.2.0"
REF="$ROOT/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz"
```

Full units use each of the following rows once with `$MODEL_HAC` and once with `$MODEL_SUP`; all six exact pairs must be present in the frozen schedule:

| Asset | `$RAW` relative to `$ROOT` | `$IDS` relative to `$ROOT` |
|---|---|---|
| development | `data/raw/HG002/PAW70337/PAW70337_66b2eea5_de8117b1_33.pod5` | `data/splits/development.txt` |
| validation | `data/raw/HG002/PAW71238/PAW71238_a8351990_11d77535_10.pod5` | `data/splits/validation.txt` |
| sealed_test, stock authorized | `data/raw/HG005/PAW87816/PAW87816_017ec17c_cb358aeb_52.pod5` | `data/splits/sealed_test.txt` |

Input preparation reuses existing interfaces:

```sh
scripts/record-command.sh verify-assets uv run --frozen scripts/verify-assets.py
scripts/record-command.sh inspect-signals uv run --frozen scripts/inspect-signals.py
```

Before running `inspect-signals.py`, assert its `config/raw-assets.json` entries are exactly the raw-file entries of `config/assets.json`, including path, role, sample and flowcell. Its current Reader loop already decodes each signal, checks nonempty length, 5kHz, kit, flowcell, positive calibration scale and global UUID uniqueness, and freezes sorted membership (`scripts/inspect-signals.py:24-57`). Add finite calibration offset/scale and metadata identity checks in a future implementation if absent. Ensure inventory outputs are published together only after all objects pass; current per-role intermediate writes are not a complete preparation receipt. Freeze SHA-256 for inputs, full membership files, per-read sample counts and inventory.

For reference qualification, hash/check all three publisher files, verify gzip integrity, stream the complete FASTA to check every contig name and length against its FAI, then prove random access across the first/last base of every contig using `samtools faidx`. FAI/GZI are compressed-FASTA indexes, not minimap indexes. Never overwrite publisher indexes. Use a copied reference/index set if a native tool would regenerate indexes.

For index generation use an independently built executable from the exact ONT submodule, not a modified stock checkout. The parent tree pins ONT minimap2 `3a7e4e229de46f4565ec7db727748e2122181d4f`; that tree pins lh3 minimap2 `3c28777e7e2dcc90f825de1b9f17a89cca7d4452`. The [ONT CMake source](https://raw.githubusercontent.com/nanoporetech/ont-minimap2/3a7e4e229de46f4565ec7db727748e2122181d4f/CMakeLists.txt) exposes `ONT_MM2_EXE=ON`, target `minimap2_exe`, and output name `minimap2`. Its [nested main.c](https://raw.githubusercontent.com/lh3/minimap2/3c28777e7e2dcc90f825de1b9f17a89cca7d4452/main.c) parses `-x`, `-I`, `-d`, and `-t` at lines 142-187. Its [lr:hq preset](https://raw.githubusercontent.com/lh3/minimap2/3c28777e7e2dcc90f825de1b9f17a89cca7d4452/options.c) sets k/w to 19/19 at lines 103-106. Build in a separate source/build path because the ONT CMake step applies patches to nested source.

```sh
scripts/record-command.sh reference-mmi "$MM2" -x lr:hq -I 16G -t 20 -d "$MMI" "$REF"
```

The MMI preparation is a native CPU stage with its own clock, output hash and producer receipt. Qualify it by aligning the same small, genuine basecalled fixture against both `$REF` and `$MMI` with the exact options below: SN/LN dictionaries must match the complete FAI; all SAM alignment fields/tags must agree after normalization of order and expected header M5/UR/PG differences. Include a one-contig or wrong-k/w index rejection. Reuse only the passing exact MMI. If matching builder acquisition fails, retain a clearly labeled FASTA alignment fallback with index construction included in each alignment clock; do not claim MMI reuse occurred.

Run six full qualification units: 3 acquired POD5 files × 2 explicit model paths. Include HG005. Each basecaller is a fresh process with stock trimming/splitting, canonical bases only, no barcoding/modified-base/duplex flags:

```sh
scripts/record-command.sh full-hac-development "$D" basecaller "$MODEL" "$RAW" --device cuda:0 --read-ids "$IDS" --min-qscore 0 --trim all --batchsize 0 -v
scripts/record-command.sh align-hac-development "$D" aligner "$MMI" "$UNALIGNED_BAM" --threads 20 --no-sort --mm2-opts '-x lr:hq -I 16G --eqx -Y'
```

The example labels expand deterministically to every tier/asset. Source-backed flags stay identical across tiers; model paths and stock automatic batch decisions differ. Capture requested batch `0` and every native effective batch size from raw logs (`dorado/api/runner_creation.cpp:91-95`), including variable chunk-size behavior; do not collapse multiple effective values into one invented scalar. For future same-model candidate comparisons, prefreeze the batch policy and compare like-for-like. No HAC/SUP speedup or winner claim is permitted.

Separate native checks and projections, all through the recorder:

```sh
scripts/record-command.sh check-unaligned "$S" quickcheck -u -v "$UNALIGNED_BAM"
scripts/record-command.sh header-unaligned "$S" view -H "$UNALIGNED_BAM"
scripts/record-command.sh decode-unaligned "$S" view "$UNALIGNED_BAM"
scripts/record-command.sh summary-unaligned "$D" summary "$UNALIGNED_BAM"
scripts/record-command.sh check-aligned "$S" quickcheck -v "$ALIGNED_BAM"
scripts/record-command.sh header-aligned "$S" view -H "$ALIGNED_BAM"
scripts/record-command.sh decode-aligned "$S" view "$ALIGNED_BAM"
scripts/record-command.sh flagstat-aligned "$S" flagstat -O json "$ALIGNED_BAM"
scripts/record-command.sh stats-primary "$S" stats -F 2304 -r "$REF" "$ALIGNED_BAM"
scripts/record-command.sh summary-aligned "$D" summary "$ALIGNED_BAM"
scripts/record-command.sh sort-aligned "$S" sort -@ 3 -m 1G -T "$ATTEMPT/sort-tmp" -o "$SORTED_BAM" "$ALIGNED_BAM"
scripts/record-command.sh index-aligned "$S" index -@ 3 "$SORTED_BAM"
scripts/record-command.sh idxstats-aligned "$S" idxstats "$SORTED_BAM"
```

Keep regular-file stdout BAMs immutable. Sort/index output paths are in the new attempt, never overwrite a parent BAM. `2304=0x900` excludes secondary and supplementary from the primary metric universe. Retain `flagstat` on all records. Quickcheck verifies header/EOF only; full `view` traversal plus downstream projections catches internal corruption. A successful full decode must have nonzero records and no stderr decode error. Record commands separately rather than piping away stage exits. Optional native `samtools stats` across all records must get a distinct label; do not add supplementary counts to the primary denominator.

## Minimal data shapes and ownership

One coordinator owns plan creation, GPU scheduling, command recording, and completion receipts. Native tools own derived sequence processing. The script is the sole writer of each attempt directory. Other agents may inspect retained evidence and write separate reports but never mutate these attempt directories or run competing own GPU work. A process-local lock is insufficient: use one host-visible advisory lock covering acquisition completion checks and all benchmark scheduling, plus preflight observations of active acquisitions and GPU compute processes. If another process is found, wait visibly; do not kill it or assume it is harmless.

```text
Plan {
  schema: 1, id, scope: "stock-only", protocol_sha256, authorization_note,
  assets_lock_sha256, source_commit, tool_pins[], model_tree_pins[], reference_pin,
  index_pin?, per_asset_membership_pins[], development_subset_pin,
  basecaller_argv_policy, alignment_argv_policy,
  execution_schedule[], minimum_free_bytes: 32212254720,
  biological_accuracy: "NOT VERIFIED", variant_calling_accuracy: "NOT VERIFIED"
}
ToolPin { path, sha256, version_receipt, build_or_release_receipt }
ArtifactPin { path, size_bytes, sha256, producer_attempt_id? }
UnitKey = hash(plan + stage + asset + tier + subset/full + repetition + parent_artifact_pins)
Attempt {
  unit_key, attempt_id, status: "started"|"failed"|"interrupted"|"verified"|"unqualified",
  recorder_dir, parent_pins[], start_utc, end_utc?, exit_status?,
  monotonic_start_ns, monotonic_end_ns?, output_pins[], verification_receipts[],
  resource_log_pin, failure_reason?, replaces_attempt_id?
}
MembershipRow { raw_uuid, child_uuid, split_point?, native_record_count,
                status: "emitted"|"missing-output", reason: "native-unresolved"? }
```

No generic DAG abstraction is needed: the stage order is a fixed list in the runner. Store plan JSON once, per-attempt JSON once at start and atomically publish a final receipt, plus TSV membership joins and native tool outputs. A final receipt is a claim backed by hashes, not mutable authority. Existing `scripts/record-command.sh:9-23` already supplies a unique directory, escaped command, cwd, UTC start/end, `/usr/bin/time -v`, exit, raw stdout and stderr. The runner adds argv JSON, monotonic clocks, process lifecycle/termination state, input/model/output pins and resource observation. It must retain the recorder path even when the child fails; the current shell helper prints it before returning the child's nonzero code. A host crash before an exit file makes an interrupted attempt, never success.

Suggested paths:

```text
data/raw/                         immutable acquired POD5
data/splits/                      immutable raw UUID memberships and chosen subset
results/stock/<plan>/plan.json
results/stock/<plan>/attempts/<unit>/<attempt>/receipt.json
results/stock/<plan>/attempts/<unit>/<attempt>/membership.tsv
results/stock/<plan>/attempts/<unit>/<attempt>/resources.csv
results/stock/<plan>/report.json
results/stock/<plan>/report.md
logs/<existing-recorder-unique-name>/  commands, raw clocks, stdout/BAM, stderr
results/candidate/                 absent now; separate future authority
```

Pin model trees by sorted relative path, byte count and SHA-256 of every extracted file, in addition to upstream archive hashes. Pin the actual executable and relevant packaged library inventory; preserve source and submodule revision receipts. A source checkout name is not proof the downloaded executable matches it; the release/archive provenance and binary hash are separate facts.

## Completion predicates and failure boundaries

Preparation passes only if every acquired asset matches its frozen local lock/upstream checks where supplied; stock binary version is 2.1.2; exact models load on the selected GPU; all POD5 signals decode with correct chemistry; UUID sets are nonempty/disjoint; full reference and indexes qualify; tiny producer/rejection controls pass; acquisitions have ended; and disk/GPU admission passes. Emit the user readiness alert then proceed under existing authorization.

Basecall verification requires exit zero, complete UTC/monotonic/time evidence, actual nonempty BAM data, retained headers matching the requested model/version, successful full decode and summary, sequence/quality lengths valid, all expected records unaligned, each child UUID unique, and all emitted roots in that unit's frozen raw manifest. For an unsplit record, `pi` is absent and QNAME is a raw UUID. For a split record, `pi` must be a raw UUID, `sp` must be nonnegative/in signal bounds, and child identity must differ from the parent. Reject contradictory parent/child mappings, foreign IDs, duplicate child records, and mixed split/unsplit representation of one root. Do not require one record per raw UUID. Count emitted roots, children per root, split roots, and missing raw UUIDs separately. Preserve each missing UUID as a drop; stock logs may not assign a per-molecule reason, so mark it unresolved.

Native traversal errors veto qualification even if exit is zero. A unit with unexplained missing molecules can retain a verified BAM and useful drop counts but is `unqualified` for clean runtime throughput and complete-molecule qualification. Do not rerun it automatically. The only strict successful skip requires either complete expected parent coverage or a separately fixed, evidenced native failure-accounting policy; the first implementation should use complete coverage. Native <5-base filtering is a possible explanation, not evidence that a particular missing molecule was filtered for that reason.

Alignment verification requires a verified unaligned parent, zero exit, full decode, the complete SN/LN dictionary, no index mismatch, one primary-or-unmapped record for each emitted child QNAME, no unknown/missing child QNAME, preserved root identity and primary sequence/quality under strand normalization, valid coordinates/flags/CIGAR, and successful native summary/statistics. Secondary/supplementary alignments can repeat a child QNAME and must retain the same root identity; accept omitted secondary SEQ/QUAL under native defaults. Validate mapped records' NM and EQX CIGAR consistency. Unmapped records need no NM. Count primary mapped/unmapped, secondary, supplementary, records and distinct children independently; never treat total alignment records as molecule count.

For restart, the runner rehashes every expected input/parent/output, checks the exact UnitKey, recorded exit/clock completion, nonempty artifact content, all required verification receipts, and `status=verified`. Only then skip that exact stage/repetition. A BAM file or receipt alone is insufficient. Verified basecalls may be reused to rebuild a failed report/summary. A failed alignment can be retried explicitly without redoing a verified basecall. Missing or corrupt retained outputs invalidate a skip; the runner reports this and stops instead of silently spending another GPU run. Separate successful verification of a native artifact from scientific validity.

## Metrics without a new biological scorer

Retain native output names verbatim in raw files. The public report translates `alignment_accuracy` to **primary reference-agreement proxy** and `1-alignment_accuracy` to **primary reference-disagreement fraction**. The fixed reference is not the donor genome. Report full-cohort sample/flowcell/tier separately.

For primary mapped emitted children, native counts define A=M+=+X columns, I insertions, D deletions, S=NM-I-D substitutions, E=S+I+D, C=A+I+D. Report both mean child fraction mean(E/C) and aggregate sum(E)/sum(C), together with mapped child count and denominator. Native summary provides A, A-S, I, D, sequence length, alignment strand start/end and Q score. Aggregate its exact counts in Python; no dynamic programming or variant-aware scoring is introduced. Per-molecule coverage/drop accounting remains separate from these child-weighted metrics; do not label child averages as molecule averages. Always retain the complete raw UUID population N as the denominator for emitted-root, dropped-root and mapped-root fractions. Missing roots, including legitimate stock filters, remain listed and counted; the disagreement fraction is explicitly conditional on mapped emitted children and is never promoted to an all-input biological accuracy score. Do not impute a reference-error fraction to missing molecules. If a molecule metric is later wanted, predefine the treatment of multiple children first.

Use EQX consistency and native summary reconciliation as adapter validation, not a second accuracy implementation. Clipping is reported on primary alignments: soft-clipped query bases are sequence length minus the query bases participating in the primary CIGAR; hard-clipped bases are a separate field and never counted as observed sequence. With `-Y`, supplementary alignments use soft clipping; report supplementary clipping separately without summing overlapping alignments into unique query bases. Add total called bases, primary aligned query bases, unmapped called bases, per-child length/Q distributions, CIGAR operation totals, NM missing/inconsistent counts, and mapping-quality distributions. Retain native `samtools stats` distributions (lengths, indels, mismatch/error outputs), `flagstat`, `idxstats`, BAM headers and both native Dorado summaries. A tiny SAM field/CIGAR tokenizer is structural glue; the reference scoring remains native.

Do not use samtools stats' native field named `error rate` as a biological result. Label it reference disagreement and retain its native denominator definition alongside the exact raw file, rather than assuming it matches the custom displayed alignment-column fraction. Do not average native percentage fields when an aggregate count ratio is intended. Check that any native NaN/sentinel for zero aligned columns becomes an explicit unavailable value, not zero error.

For this benchmark, variant-aware confident-region accuracy is **NOT VERIFIED**, quality calibration against biological truth is **NOT VERIFIED**, and variant precision/recall is **NOT VERIFIED**. GIAB files remain pinned future inputs. No BED-only masking, nearest-VCF-base subtraction, or sparse variant-calling score is added. Dorado's optional `--bed-file` records overlap counts (`aligner.cpp:116-120`); that is not confident-region variant-aware scoring.

## Runtime schedule and real-work qualification

Freeze the development subset before any timing results: smallest 256 development UUIDs by `(SHA256("nanopore-stock-runtime-v1:" + UUID), UUID)`, or all if fewer than 256. Retain exact IDs, their original POD5 path, per-read sample counts, total signal samples and seconds. Do not alter the subset after viewing runtime, lengths or Q. Existing 32-read deterministic smoke remains a separate compatibility artifact.

Run at least five fresh-process repetitions per tier, interleaved as H,S / S,H / H,S / S,H / H,S. The fixed ten-entry schedule is in the plan. Keep the original development POD5 as input for every repetition with `--read-ids` selecting the same UUIDs. Label this as **selection from the original shard**, because POD5 traversal/I/O can exceed the selected signal bytes. Do not claim a compact-subset I/O benchmark. Execute all native checks after each repeat; prove selected signal population is fixed, outputs are nonempty, and no unknown drop/invalid record is hidden by the timing.

No invisible warmup runs. If the 32-read smoke runs first, record that fact; timings are fresh-process but OS/device-cache state is uncontrolled/warm, not cold-cache. Model load, native startup, signal decode, compute, BAM compression/write and process exit are included in basecall wall time. OS durable `fsync` is not included unless explicitly added as a different timed boundary. Reference indexing is excluded from basecall time; MMI construction, alignment, sorting, reporting and validation have separately reported clocks. Do not claim model-load time separately unless a genuine native marker is qualified; otherwise it is included but not separable. Full-cohort runs are single-run qualification, not repetition-based performance estimates.

The existing recorder's raw `/usr/bin/time -v` output is authoritative process clock/RSS evidence. The runner also captures monotonic nanoseconds around the recorder process and labels recorder overhead separately if different. Retain GPU/device/driver/CUDA, CPU model and affinity, RAM, storage/filesystem, battery/AC and power state. Do not silently force performance clocks or clear system caches. Freeze the CPU affinity/thread policy from actual allowed CPUs; aligner uses 20 workers total and samtools uses the explicit smaller budgets shown above. Basecaller has no ordinary `--threads` flag in the traced interface, so do not invent one; record its observed worker configuration/native defaults and any fixed affinity.

Start `nvidia-smi` observation before spawning the recorder, terminate/join it after exit, and retain sampler exit plus raw CSV. Installed query help verifies these fields:

```sh
nvidia-smi --query-gpu=timestamp,uuid,name,driver_version,pstate,temperature.gpu,power.draw,clocks.current.sm,clocks.current.memory,memory.used,utilization.gpu --format=csv --loop-ms=500
```

Unsupported/N/A fields remain unavailable. Sampled peak VRAM is a sampled observation, not a guaranteed instantaneous maximum. Record GPU compute-process snapshots before/after each attempt and reject overlap with other own GPU jobs. An advisory lock prevents own cooperating runners; external GPU activity can still contaminate a run and must be reported. Native process exit, sampler termination and verification exits are separate fields.

Report individual elapsed/RSS/VRAM observations, completed repetitions versus planned, failure/drop counts, median and range per tier, and requested input signal-seconds/elapsed and emitted called-bases/elapsed. Call the former attempted-signal throughput whenever any input drop remains; do not imply every signal sample was successfully called. A qualified clean runtime baseline requires complete parent coverage or a separately qualified explicit drop policy. Report failures among the five attempts; never replace failed repetitions silently. A successful rerun is an additional, explicitly labeled attempt. No cross-tier winner, speedup, or accuracy-ranking conclusion follows.

Disk admission requires all acquisition producers finished and free space above 30GiB plus a conservative estimate for the entire next unit's BAMs, full SAM traversal logs, sort temporaries and receipts. Build the MMI before timing admission estimates. Keep one full cohort unit active at a time; no basecall/alignment/sort overlap with another unit. Monitor free space during every writer and stop starting new work above the hard floor with several GiB of safety margin. Retain partial files/failure receipts and stop on a reserve breach; do not delete raw inputs/failures to create room. `view` SAM logs can be large, so include them explicitly in the estimate; after verification a compact structural projection may replace a future copy, but never silently discard the original raw evidence policy. Uncoordinated external disk writers prevent an absolute free-space guarantee; flag that operational limit and use a reservation/quota if a hard invariant is required.

## Independent verification and rejection controls

No GPU benchmark or full raw acquisition is rerun to debug report glue. First qualify the adapter on tiny artifacts:

1. **Exact native metric fixture.** Create a fixed small reference with unique flanks and fixed query sequences: one exact match, one substitution, insertion, deletion, soft-clipped query, unmapped query, and a multi-mapping/supplementary case. Use sufficiently long unique anchors for `lr:hq` to align reliably. Generate the BAM using the pinned native Dorado aligner and preserve producer argv/exit/header. Independently inspect its actual CIGAR/NM and compute expected integers by hand in a fixture table. Verify Dorado summary and samtools counts against those exact values, including mismatch fraction denominators and clipping; compare REF versus MMI output. Do not assume the aligner must choose the edit layout intended by the fixture: freeze and verify its real layout. An arithmetic control for the structural tokenizer is `5S20=1X10=2I10=3D15=4S` with NM=6: A=56, I=2, D=3, S=1, query length=67, clipped query bases=9, E/C=6/61. That control supplements the genuine native producer, not replaces it. This qualifies the adapter, not biology.
2. **Genuine split fixture.** Basecall the pinned source `tests/data/single_split_read/single_split_read.pod5` or `tests/data/split/DOR-1569/split_read.pod5` using its compatible pinned native model, preserving source fixture hash. Assert the genuine BAM contains `pi`/`sp`, native summary root equals source POD5 UUID, multiple derived child UUIDs are accepted, and one raw parent is counted once. Alternatively use a real split found during the development smoke, but never fabricate a split fixture by editing a parent tag alone. Qualification may require acquiring the fixture-compatible model; lack of one remains an explicit gap.
3. **Rejection controls derived from the genuine artifacts.** Work only on copies: truncate a BAM EOF; corrupt an interior BGZF block while retaining EOF; remove one selected child; duplicate a child; replace `pi` with a foreign frozen UUID; strip split `pi`; alter reference SN/LN; alter NM so it conflicts with EQX; provide an empty but valid BAM. Re-encode semantic mutants with native samtools. Assert exact validator rejection and failed receipt; demonstrate quickcheck alone does not catch all controls. Preserve the untouched producer BAM, mutant hash, generator command and rejection evidence.
4. **Restart controls.** After a verified tiny attempt, rerun the plan and prove no child native process is spawned. Mutate one output byte or one parent pin and prove skip is rejected without an automatic expensive retry. Interrupt a tiny producer and prove the absent exit/verification receipt never qualifies. Delete only a derived report and prove it can be repaired from retained BAM without rebasecalling.
5. **Signal gates.** Reuse existing `tests/test_signals.py` native POD5-writer fixtures (real decoded signal, changed sample rate, duplicate UUID, frozen membership mutation). Extend only for additional preparation behaviors actually introduced. The full acquired assets still require their own native inspection receipts; fixture success is not acquisition acceptance.

## Alternatives, tradeoffs and verification gaps

**Chosen:** separate unaligned and aligned stock BAMs with native summaries. It costs disk and a second native read/write but isolates basecaller runtime, preserves the unaligned stock output, permits alignment/report repair, and makes native identity conservation reviewable.

**Rejected alternative:** `dorado basecaller --reference ...` integrated alignment. Its CLI is supported (`basecaller.cpp:179-187`), but it entangles GPU basecalling and CPU alignment timing, prevents reusing the exact unaligned producer artifact, and makes the most useful failure boundary harder to inspect. It is smaller in command count, not in evidence complexity.

**Rejected alternative:** a new Rust BAM/edit-distance scorer. This is substantial new scientific computation, introduces denominator/strand/supplementary/variant truth decisions, and duplicates native counts already available. Python structural joining is sufficient. If native summaries fail tiny exact-value qualification, fix the projection or narrow the displayed endpoint before adding a scorer.

Known live gaps at review time: acquisition directories contain `.parts`/partial assets; `software/bin` is empty; `data/splits` and `provenance/signal-inventory.json` are absent; nested minimap source hydration is in progress by the coordinator; no stock native GPU fixture, MMI handoff, full reference access qualification or runtime execution has been reviewed by this candidate. These are observations of preparation state, not claims of failed biological/software behavior. No final biological accuracy score is designed or qualified. The design needs implementation and an independent review of genuine producer/rejection receipts before full processing.
