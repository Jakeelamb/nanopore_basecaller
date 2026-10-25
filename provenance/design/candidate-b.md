# Candidate B: one evidence runner, native computation

Design only. Owner: candidate B. Written against the 2026-10-22 brief and the pinned Dorado source. No execution or installation is claimed here.

## Usage and decision

Add one small `scripts/benchmark.py` command, using the existing UV project and standard-library Python for subprocess orchestration, identity checks, TSV/JSON joins, and presentation. Keep `scripts/record-command.sh` as the subprocess recorder. Dorado performs basecalling, mapping, and sequencing summaries; samtools performs BAM decoding, sorting, reference-tag recalculation, and native statistics. There is no new aligner, biological scorer, task scheduler, or database.

Proposed public interface:

```sh
uv run --frozen python scripts/benchmark.py plan --output results/stock-20261022
uv run --frozen python scripts/benchmark.py run results/stock-20261022/plan.json
uv run --frozen python scripts/benchmark.py verify results/stock-20261022/plan.json
uv run --frozen python scripts/benchmark.py report results/stock-20261022/plan.json
```

`plan` checks readiness and freezes all identities/settings before running anything expensive. `run` consumes that immutable plan and runs sequentially. `verify` can repair missing projections from retained native artifacts without basecalling again. `report` reads receipts; it cannot promote an unverified attempt. These are proposed commands, not existing interfaces.

Why this shape: an ad-hoc shell chain can preserve a final BAM yet lose which producer failed, confuse a nonempty file with completion, or rerun a successful GPU job after a reporting error. One recorder plus explicit stage receipts resolves those failure modes without a workflow framework. Native tools remain responsible for substantial computation.

## Source-backed native interfaces

All local paths below are relative to `/home/jake/Projects/nanopore_basecaller`. Dorado source pin: `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`.

| Source | Verified contract and consequence |
|---|---|
| `software/dorado-src/dorado/cli/cli_lib/basecaller.cpp:130-182,252-284,1175-1195` | `basecaller MODEL DATA`; MODEL may be an existing model directory; DATA may be one POD5. `--read-ids` is newline-delimited; `--max-reads 0` is unlimited; `--min-qscore 0` disables quality thresholding; `--batchsize` is chunks/batch; `--trim all` is explicit default DNA trimming. Splitting stays enabled by omitting `--disable-read-splitting`. |
| `.../cli_lib/include/cli/utils/cli_utils.h:161-219` | `--device cuda:0` is explicit; `auto` can fall back to CPU. Basecaller has no public `--threads` in this parser. Preserve host CPU/affinity configuration rather than inventing a thread argument. |
| `.../cli_lib/basecall_output_args.cpp:15-26,59-109`; `.../hts_writer/HtsFileWriterBuilder.cpp:53-81` | BAM is default; there is no `--emit-bam`. A regular stdout file gets compressed BAM; a pipe changes it to uncompressed BAM. `--emit-summary` writes into the output directory or cwd. Use a regular file sink through the existing recorder and run `dorado summary` separately to avoid hidden cwd artifacts. |
| `.../cli_lib/aligner.cpp:80-138,175-228` | `aligner INDEX READS`; INDEX supports FASTA/FASTQ/MMI. `--threads` budgets alignment/writing. `--no-sort` is valid. Native aligner can exit zero for no inputs; nonempty validated output is therefore mandatory. |
| `.../alignment/minimap2_args.cpp:18,20-43,85-136` | `--mm2-opts` takes one quoted string and allows `-x`, `-I`, `--eqx`, `-Y`, and secondary options. Pin `-x lr:hq -I 16G --eqx`. Dorado already requests CIGAR and MD tags. There is **no `-d` index-writing option** in this allowlist. |
| `.../alignment/Minimap2Index.cpp:30-35,60-95,215-239` | Dorado can read MMI. A prebuilt index's differing k/w only produces a warning; it does not fail. MMI-derived headers omit M5/UR, so names/lengths alone do not prove reference sequence identity. Index provenance and a FASTA/index parity check are necessary. |
| `.../splitter/splitter_utils.cpp:34-39,62-66,108`; `.../splitter/DuplexReadSplitter.cpp:650-660`; `.../read_pipeline/base/messages.cpp:166-171` | Split QNAMEs are derived UUIDs, with original input UUID in `pi:Z`, original-signal start in `sp:i`, and signal sample count in `ns:i`. Matching only QNAME to input UUID is wrong. |
| `.../cli_lib/basecaller.cpp:628-635`; `.../utils/include/utils/parameters.h:14`; `.../read_pipeline/nodes/ReadFilterNode.cpp:32-39` | Even at Q-score threshold zero, stock filters sequences shorter than five bases. Missing parents/children must be counted; absence alone does not prove a specific failure reason. |
| `.../cli_lib/summary.cpp:25-34,109-113`; `.../hts_writer/SummaryFileWriter.cpp:215-230,330-420` | `summary BAM` writes TSV. It omits secondary/supplementary alignments, uses `pi` or QNAME for parent, and exposes primary alignment counts/identity/accuracy. Preserve those native names in raw TSV; report them as reference-agreement proxies. |
| `.../cli_lib/ProgressTracker.cpp:35-76`; `.../cli_lib/basecaller.cpp:1006-1064`; `.../utils/stats.cpp:78-112` | Native reported speed starts after initialization. External process timing is the runtime baseline. `--dump_stats_file` is supported but sampled at 100 ms and capped at 100,000 records; its last row is not guaranteed final. Treat it as diagnostics, not an exact final-read audit. |

Exact proposed native commands, dispatched individually as argv arrays, not a shell pipeline. Resolve the two model directories to `/home/jake/Projects/nanopore_basecaller/models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0` and `/home/jake/Projects/nanopore_basecaller/models/dna_r10.4.1_e8.2_400bps_sup@v5.2.0` after verified extraction; the plan stores the actual resolved paths and complete file-tree hashes:

```sh
# MODEL is one exact absolute directory, never the alias hac/sup.
# IDS is the frozen complete UUID list for this shard, or the fixed dev subset.
# ATTEMPT is a fresh directory. Recorder stdout is logically calls.bam.
scripts/record-command.sh stock-basecall \
  "$DORADO" basecaller "$MODEL" "$POD5" \
  --read-ids "$IDS" --device cuda:0 --batchsize 64 \
  --min-qscore 0 --trim all --verbose \
  --dump_stats_file "$ATTEMPT/dorado-stats.csv"

# BASECALL_BAM points to that producer's retained binary stdout.
scripts/record-command.sh stock-basecall-header samtools view -H "$BASECALL_BAM"
scripts/record-command.sh stock-basecall-summary "$DORADO" summary "$BASECALL_BAM"
scripts/record-command.sh stock-basecall-quickcheck samtools quickcheck -u -v "$BASECALL_BAM"

# INDEX is the qualified full-reference MMI, never a chromosome-only substitute.
scripts/record-command.sh stock-align \
  "$DORADO" aligner "$INDEX" "$BASECALL_BAM" \
  --threads 16 --no-sort --mm2-opts '-x lr:hq -I 16G --eqx'

scripts/record-command.sh stock-sort samtools sort \
  -@ 7 -m 512M -T "$ATTEMPT/sort-tmp" -o "$SORTED_BAM" "$ALIGN_BAM"
scripts/record-command.sh stock-align-quickcheck samtools quickcheck -v "$SORTED_BAM"
scripts/record-command.sh stock-align-decode samtools view "$SORTED_BAM"
scripts/record-command.sh stock-align-header samtools view -H "$SORTED_BAM"
scripts/record-command.sh stock-align-summary "$DORADO" summary "$SORTED_BAM"
scripts/record-command.sh stock-flagstat samtools flagstat -O json "$SORTED_BAM"
scripts/record-command.sh stock-stats samtools stats -F 0x900 -r "$REFERENCE_GZ" "$SORTED_BAM"
scripts/record-command.sh stock-calmd samtools calmd -b "$SORTED_BAM" "$REFERENCE_GZ"
```

Native command stdout stays in recorder evidence; names such as `calls.bam` and `native-summary.tsv` are logical artifact labels that point to those retained paths. A stage that writes `SORTED_BAM` is additionally hashed and recorded. For basecall verification, also run full `samtools view BASECALL_BAM`; quickcheck alone checks the ends, not the interior. Full SAM output may be streamed into the verifier rather than retained as a second giant text file, but retain its command, exit, record count, incremental hash, parser receipt, and raw stderr. The underlying BAM remains replayable.

The requested batch size 64 is a conservative starting setting, **not a demonstrated 8 GiB fit**. First qualify both tiers on the existing 32 development smoke UUIDs. Record any native batch-size adjustment and effective value. If either fails or adjusts incompatibly, retain the attempt and explicitly revise/freeze the batch policy before the repeated series; no automatic OOM retries or tuning by timing outcomes. Keep chunk sizes and variable-chunk behavior at each exact model's stock defaults and hash its config. This is a model-specific baseline, not matched architecture or a maximum-throughput search.

`samtools 1.24` and HTSlib 1.24 were observed on PATH during design; freeze resolved binary hash/version/build details at execution. `DORADO`, both extracted model directories, and the index producer are resolved and hashed only after installation completes.

## Reference/index qualification

Keep the publisher compressed FASTA, FAI, and GZI unchanged. Verify pinned file hashes and upstream MD5; native sequential FASTA parsing must enumerate exactly the publisher dictionary and total lengths, including every contig. Exercise indexed retrieval of the first and last base of every contig using `samtools faidx` with publisher indexes. No single-chromosome reduction. Asset hash plus full decoding plus dictionary equality is the identity proof; a small retrieval smoke test alone is insufficient.

Prefer an index producer built in a **separate build/copy directory** from the exact minimap2 nested within the pinned Dorado `ont-minimap2` submodule. The top-level gitlink is `3a7e4e229de46f4565ec7db727748e2122181d4f`. Its recursive acquisition was still in progress while this design was written; inspect its actual nested CLI and pin its git commit/build/binary before implementation. Do not treat a fetched tip or an incomplete checkout as that pin.

If that CLI exposes the standard native options, proposed producer shape is:

```sh
scripts/record-command.sh reference-index \
  "$PINNED_MINIMAP2" -x lr:hq -k 19 -w 19 -I 16G -t 16 \
  -d "$REFERENCE_MMI" "$REFERENCE_GZ"
```

This exact option shape is independently source-backed by [minimap2 v2.30 main.c](https://raw.githubusercontent.com/lh3/minimap2/v2.30/main.c) (`-d`, `-I`, `-t`, `-k`, `-w`) and [options.c](https://raw.githubusercontent.com/lh3/minimap2/v2.30/options.c) (`lr:hq`: non-HPC, k=19, w=19); it is **not yet proof of the incoming nested producer's interface or compatibility**. Verify that producer locally before adopting this command. Do not add a bespoke index writer. A separately pinned native producer is an acceptable fallback only after the same compatibility checks; otherwise use the fixed FASTA directly and report index reuse NOT VERIFIED.

Qualify the MMI once against both tiers' genuine development smoke BAMs: run the same Dorado aligner and settings with FASTA and MMI; compare complete sequence dictionaries to publisher FAI and compare canonical sorted alignment records (QNAME, FLAG, contig, POS, MAPQ, CIGAR, NM, MD, SEQ/QUAL), ignoring order and reference-container-dependent header fields. Require no index-parameter warning and no record differences. Store both complete producer receipts and both alignment outputs. Hash MMI plus its exact FASTA build receipt. Parity on smoke reads is a compatibility check; the construction provenance supplies reference identity beyond those read locations.

## Immutable inputs and minimal data shapes

Use `config/assets.json` as the acquired-object census and verify its raw-POD5 entries agree with `config/raw-assets.json`, which the existing signal inspector actually reads. Reject an extra complete raw POD5 or a missing configured one. Exclude download partial files. Reuse `uv run --frozen python scripts/verify-assets.py` and `... scripts/inspect-signals.py` before GPU work. The latter actually decodes every `read.signal`, checks 5 kHz, flowcell, LSK114, nonempty length, and positive calibration scale, rejects UUID duplication, and freezes membership. Snapshot/hash its inventory and lists into the plan, and additionally check finite offset/scale and metadata evidence for the declared chemistry. Keep observed sample IDs separate from release-derived sample identity and reject unexplained conflicts. Let native Dorado compatibility checks remain enabled.

Four small data products suffice:

```text
plan.json
  schema_version, plan_sha256, authorized_scope="stock-all-acquired"
  asset_lock_sha256, source_commit, source_dirty=false
  binary identities, model file-tree identities, reference/index identities
  per-object role/sample/flowcell/path/sha256/read-list hash/num_samples
  deterministic subset rule, ordered unit schedule, argv/settings, resource policy

attempts/<unit>/<attempt-id>/receipt.json
  unit_key, plan_sha256, attempt_id, predecessor_attempt_id|null
  state = running|command_failed|interrupted|observation_failed|verified
  argv[], cwd, explicit_env, start_utc, end_utc, monotonic_elapsed_ns
  recorder_path, producer_exit_status, raw evidence hashes
  artifacts[{logical_name,path,size,sha256}], verification{version,checks[],status}

parents.tsv
  input_uuid, object_id, num_samples, role, output_children, status, reason|null
  status = emitted|not_emitted; unknown reasons stay null

metrics.json
  identity links; cohort/tier/repetition; command/verification status
  requested/represented/not-emitted molecule counts; record/child/mapping counts
  native-output pointers; proxy denominators; wall/resource observations
  scientific_endpoint = {biological_base_accuracy:"NOT VERIFIED",
                         variant_calling_accuracy:"NOT VERIFIED"}
```

One `run_unit(UnitSpec) -> AttemptReceipt` and one `verify_artifacts(UnitSpec, AttemptReceipt) -> Verification` hide subprocess/evidence mechanics. `render_report(verified_receipts)` performs explicit sums and medians only. No generic DAG engine; stages are a fixed ordered list. Paths are resolved once, raw artifacts are append-only, and verification receipts name both verifier version/hash and exact artifact hashes. Candidate outputs later use another result root and source identity; they never share stock attempt directories.

## Verification and completion predicates

1. **Preflight:** every acquisition is finished and asset verification passes; stock source is pinned/unchanged; extracted binary/model manifests are frozen; full reference qualified; all native signals decoded; disjoint UUID sets frozen. Existing smoke manifests contain only development UUIDs. Brief authorization supersedes the older protocol's stock HG005 prohibition; preserve the role label and candidate holdout policy.
2. **Basecalling:** producer exit zero; complete UTC/exits/clocks/log pins; nonempty BAM; quickcheck plus full native decode succeeds; expected Dorado version/model in `@PG`/`@RG` and exact command receipt; nonempty SEQ/QUAL lengths match; unaligned stock records have expected primary/unmapped flags. Every record resolves to an input parent using `pi` when present, otherwise QNAME. Reject foreign parents, duplicate child QNAMEs, invalid/missing split tags, mixed unsplit/split representation of one parent, or signal intervals outside parent `[0,num_samples)`. Split intervals `[sp,sp+ns)` must be disjoint; gaps from trimming/splitting are allowed and counted, not claimed as dropped molecules. `0 <= ts <= ns`; finite `qs`; known RG. Do not equate children with molecules.
3. **Accounting:** output-parent union is a subset of requested UUIDs. Persist exact missing UUIDs and all observed children. `requested = represented + not_emitted`. There must be positive genuine output. Missing records are not silently waived or assigned invented reasons: stock's native filtered counters/logs are reported separately because a filtered child is not a missing parent. Recognized loader errors invalidate complete-processing qualification even if Dorado exits zero; unresolved missing-parent causes are explicit limits. A finished run with drops remains a completed observation, visibly qualified with its drop counts; it is not evidence that every requested molecule produced sequence.
4. **Mapping:** exact fixed reference/index/preset; full decode and quickcheck; dictionary equality to FAI; exactly one primary-or-unmapped record per basecalled child. Output QNAME/parent membership exactly matches basecall children. Reverse-complement/normalize primary SEQ and QUAL by FLAG 0x10 and compare to the basecall input; do not reject a correctly reverse-oriented mapping. Secondary/supplementary records are additional alignments of those children, never new molecules. Validate CIGAR consumption against SEQ length and coordinates; do not require stored SEQ in secondary/supplementary records. Primary length/clipping plus unmapped bases account for basecalled child sequence; do not sum overlapping supplementary alignments as extra sequence.
5. **Metrics:** native summaries join one-to-one to primary child IDs; native flag/count totals reconcile. Compare original primary NM/MD against native `samtools calmd` output keyed by the alignment fields and preserve discrepancies. Missing/invalid NM or disagreement makes that metric NOT VERIFIED until diagnosed; repairing a projection must not replace the raw alignment or trigger rebasecalling. Store stdout/stderr/exits for every native analysis command. The metric receipt is separate from producer qualification.

Controls run before full GPU execution, using a genuine Dorado smoke BAM. Accept the untouched artifact. Then demonstrate rejection of (a) truncated BAM, (b) one valid record renamed to a foreign UUID/parent, (c) a duplicate primary child, (d) all records for one previously represented parent removed, (e) a split child with missing/foreign `pi` or invalid/overlapping `sp` range, (f) mismatched model/reference identity, and (g) altered NM/MD. The deletion must change the missing-UUID ledger and prevent a falsely complete molecule result even if the BAM decodes. The BAM has no declared expected child-count tag: removing only one of several split siblings cannot always be distinguished from an allowed signal gap, so do not claim exact split-child completeness from BAM membership alone. Use a genuine stock split fixture if smoke has no split outputs; never pass a split branch vacuously. Keep an interrupted-attempt/no-exit receipt control and a parser-failure control that prove restart re-verifies retained output without relaunching its producer. Controls are derived copies in a disposable verification directory; immutable producers stay unchanged.

## Runtime experiment and resource boundaries

Freeze 256 development parent UUIDs using ascending SHA-256 of `nanopore-stock-runtime-v1:` plus canonical UUID, with UUID as tie-breaker; use all if fewer exist and report actual N. Keep the existing 32-ID smoke list separate. This samples read membership deterministically, not donor/run diversity. Use the same exact POD5 and UUID list for every timed call; selection/scanning I/O is included.

After one smoke/warm-up for each exact model, launch fresh processes in this fixed order: `H,S; S,H; H,S; S,H; H,S`. That is five measured attempts per tier, interleaved, never concurrent. Every timing attempts real stock basecalling; `--max-reads` and `--run-for` are absent. Report every attempt, failed attempts and incomplete verification, and median/IQR/range only for the explicitly identified successful verified set with `n_success/n_planned/n_failed`. Fewer than five successful verified repetitions means the five-repetition baseline is incomplete; failed slots are not invisibly replaced. An explicit new attempt can fill a failed slot while retaining its failure record. Do not discard a slow first repetition or stop when numbers look favorable.

Record external process wall from spawn through wait, including startup, model load, POD5 access, GPU computation, BAM compression/writes, and shutdown. The wrapper's `/usr/bin/time -v` and raw clocks remain available; runner monotonic time is higher-resolution and includes wrapper overhead. It excludes post-run hashing, verification, mapping, summary generation, and physical-disk flush beyond process exit; report those stage times separately. Native Samples/s excludes initialization and remains a separately labeled diagnostic. File caches are warmed/observed, not controlled cold-cache measurements. Do not flush Jake's host caches.

Show input signal-seconds divided by full process wall as **submitted-input signal-seconds/s**, plus emitted child bases/s and represented molecules/s, with missing-parent counts adjacent. Do not assert that submitted samples were all processed if output/diagnostics leave that uncertain. Retain native sample counters as diagnostics; no throughput claim from output existence, timeout, a failed run, or fewer input reads. No speedup, overall winner, or scientific ranking between HAC v6.0.0 and SUP v5.2.0; these are distinct accuracy tiers/models.

Pin the GPU UUID/device, executable/model hashes, requested/effective batch policy, CPU affinity/online CPU topology, aligner/samtools thread settings, driver/toolkit, temperature/power/clock state, AC/battery condition and contention observations. Observe GPU state at one-second cadence plus before/after `nvidia-smi -q -x`; retain sampler UTCs, exit and raw log. Report maximum sampled GPU memory as sampled, not an exact peak. `/usr/bin/time -v` provides process maximum RSS. Missing/unsupported telemetry is unavailable, never zero. The basecaller has no public thread-count knob; keep host/affinity constant and state this limit.

Run one full qualification for each of three POD5 shards × two exact models, using each complete frozen UUID list. Map and summarize all six. Label these **single-run full-cohort qualification**, not repeated runtime estimates. Report each flowcell/sample separately. Reuse the qualified index and already verified full outputs on restart.

Before any GPU stage, acquire one kernel-backed exclusive runner lock, prove acquisition jobs have ended, and check no other owned GPU job is active. Record other GPU clients; do not kill them. Keep at least `30 * 1024^3` free bytes, plus a conservative estimate for this stage's new BAM/log/temp outputs. Check free space before every stage and during execution; stop the active process group cleanly before violating the reserve, retain the failed/interrupted attempt, and do not retry silently. Never delete raw files, stock outputs, or failed evidence to manufacture capacity. Samtools temp files live under their own attempt directory; removing them after a verified final artifact is an explicit recorded cleanup. No GPU benchmark alongside own GPU work or unfinished acquisition.

## Resume, report, and scientific limits

Create every attempt exclusively. A unit key hashes stage, plan, exact upstream artifact hashes, settings, and verifier identity. Write a `verified` receipt atomically only after command success and all required checks; a `.bam` file or old `.done` flag never qualifies a skip. On restart, rehash linked artifacts and recheck receipt invariants before skipping. A running unit with no complete receipt is interrupted/unknown; preserve it and require an explicit resume decision to launch a new expensive attempt. A producer with sound exit/evidence but failed projection goes to `observation_failed`: repair/re-run verification first. A changed plan/verifier can create a new verification receipt against existing producer bytes; it must not masquerade as a new basecall.

Report requested molecules, represented molecules, exact not-emitted count, split parents/children, BAM records by primary/secondary/supplementary/unmapped/QC flag, primary mapped fraction, lengths, MAPQ, query clipping (soft and hard separately), unmapped query bases, native I/D/NM and reference disagreement, native summary/flagstat/stats links, and timing/failures/resources for each cohort/tier. Per-read primary reference disagreement is `NM / (M + = + X + I + D)` with zero denominators and missing NM unscored and counted. Aggregate fraction uses summed numerators/denominators; mean per-read fraction weights each emitted child equally and is labeled accordingly. Preserve native `samtools stats` error rate with its own denominator; do not relabel it as the same metric. Show secondary/supplementary mapping counts without adding their overlapping bases into primary fractions. All-called length is distinct from aligned length, clipping, trimming, and missing input molecules.

Known biology: the complete pinned GRCh38 release is a haploid common reference, not either donor's diploid sequence. Reference disagreement conflates genotype, mapping, reference, and basecalling differences. Retain raw native `alignment_accuracy` fields, but the visible endpoint is **reference disagreement proxy**. Do not interpret Q scores as empirical accuracy/calibration. These small, size-selected shards and repeated technical runs cannot establish population or whole-genome variant performance; HG002 validation shares a donor with development and vendor training exposure is unknown.

For this first stock benchmark, set variant-aware confident-region accuracy and variant-calling accuracy to **NOT VERIFIED**. Merely having GIAB VCF/BED is insufficient. Do not approximate a variant-aware truth score by filtering overlapping reads with a BED, subtracting known variants, or masking after seeing outcomes. A future fixed, independently verified haplotype/variant-aware method needs its own qualification before execution. Stock HG005 observations are now authorized, but cannot select future candidate edits, hyperparameters, masks, thresholds, or sample selection.

Authoritative metric references consulted: [samtools quickcheck](https://www.htslib.org/doc/samtools-quickcheck.html) for its limited corruption coverage; [samtools calmd](https://www.htslib.org/doc/samtools-calmd.html) for native NM/MD recalculation and missing-sequence limits; [samtools stats](https://www.htslib.org/doc/samtools-stats.html) for record filters/native denominators; [SAM tag specification](https://github.com/samtools/hts-specs/blob/master/SAMtags.tex) for NM and clipping semantics. Archive exact documentation/source hashes with implementation rather than depending on moving web pages.

## Rejected alternatives and remaining gaps

- Reject a second biological scoring library: native summary/stats/calmd plus bounded consistency checks meet this stock endpoint.
- Reject piping basecall straight into mapping: it merges failure/timing boundaries, loses a reusable stock control, and changes Dorado stdout compression behavior.
- Reject a generic workflow/database framework: fixed stages plus append-only receipts are sufficient for three files and two models.
- Reject QNAME-only input validation, exact child-count-equals-input assumptions, quickcheck-only validation, and summary-only BAM counting.
- Reject stock `--resume-from` as benchmark recovery: it mixes prior work with the timing numerator and can hide interrupted processing. Resume at verified whole units.
- Remaining execution gaps: installed Dorado/model identities, effective GPU batch sizes, incoming pinned index producer interface/build and compatibility, complete native signal/reference receipts, and genuine acceptance/rejection controls have not been proved by this design. Biological accuracy is intentionally unqualified. No runtime number is reported here.
