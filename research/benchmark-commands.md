# Run the fixed stock benchmark

Run these commands from `/home/jake/Projects/nanopore_basecaller`. Use the pinned UV environment.

## Complete preparation

Finish acquisition, asset verification, native signal inspection, model extraction, and full-reference qualification before creating a plan. The coordinator also supplies a qualified minimap2 index and genuine FASTA versus MMI parity receipts for both tiers. See [the accepted design](benchmark-design.md).

After `scripts/bootstrap.sh`, create the two genuine development warmups and qualify the reference/index handoff. These warmups are separate from the five measured repetitions:

```sh
set -euo pipefail
parity_hac_run=$(scripts/record-command.sh parity-hac software/bin/dorado basecaller \
  models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0 \
  data/raw/HG002/PAW70337/PAW70337_66b2eea5_de8117b1_33.pod5 \
  --read-ids data/splits/smoke.txt --device cuda:0 --batchsize 0 --min-qscore 0 --trim all -v)
parity_sup_run=$(scripts/record-command.sh parity-sup software/bin/dorado basecaller \
  models/dna_r10.4.1_e8.2_400bps_sup@v5.2.0 \
  data/raw/HG002/PAW70337/PAW70337_66b2eea5_de8117b1_33.pod5 \
  --read-ids data/splits/smoke.txt --device cuda:0 --batchsize 0 --min-qscore 0 --trim all -v)
uv run --locked scripts/prepare-reference.py \
  --parity-bam "$parity_hac_run/stdout" --parity-bam "$parity_sup_run/stdout"
```

`config/stock-benchmark.json` names the installed executables, exact models, full reference, qualified index, and genuine source split fixture. Keep batch size zero and stock chunk settings fixed. The runner uses 16 Dorado aligner threads and three additional samtools sort threads, with 256 MiB per sort thread.

Each reference receipt contains `status: "verified"`, a complete `dictionary`, and nonempty `pins` entries with `path`, `size`, and `sha256`. Pin paths are repository-relative or absolute. The runner resolves relative paths against the repository root.

The index receipt contains the compressed `reference_sha256` and exactly two verified `parity` entries, one per configured tier. Each entry names its exact `tier` and `model`, positive `mapped_records`, `input`, `input_decode`, four `outputs`, `input_producer_run`, `producer_runs`, and flattened `pins`. The runner checks all nested artifact and recorder pins, complete zero-exit producer receipts, native Dorado version and model headers, mapped counts, complete dictionaries, and canonical FASTA versus MMI record equality. The maintained `scripts/prepare-reference.py` emits this format.

Create a new plan after all inputs pass:

```sh
uv run --locked python scripts/benchmark.py prepare results/stock/stock-20261022
```

The command prints the plan path. It refuses an existing output directory, changed asset lock, unconfigured POD5, wrong source revision, changed submodules, overlapping membership, or altered deterministic subset. It re-decodes every acquired POD5 signal and compares its UUID, sample count, acquisition metadata, calibration, and signal extrema with the complete inventory and signal receipt. Full membership must equal the actual cohort before subset selection. The runner also compares each extracted model file and the complete file list with its verified stock ZIP. It then freezes the smoke and benchmark lists, model trees, packaged libraries, binaries, input bytes, reference receipts, and an initial runner-source snapshot. Changing a frozen input requires a new plan and preserves the previous attempt.

The runner checks for active acquisition and GPU compute processes before GPU execution. It holds `results/stock/host.lock` throughout each invocation. Keep all other owned GPU work stopped. The lock coordinates runner instances; it cannot prevent an unrelated program from starting later.

Keep at least 30 GiB free. Admission adds 8 GiB of headroom, and every native stage monitors the 30 GiB floor. Full SAM traversals remain in the recorder logs. If measured output growth requires more headroom, revise the configuration before freezing the plan.

## Qualify genuine native outputs

Run the two development smoke units and the genuine split fixture:

```sh
uv run --locked python scripts/benchmark.py run results/stock/stock-20261022/plan.json --scope smoke
uv run --locked python scripts/benchmark.py run results/stock/stock-20261022/plan.json --scope fixture
uv run --locked python scripts/benchmark.py qualify-native results/stock/stock-20261022/plan.json
```

`qualify-native` reuses retained producers. It requires multiple genuine split children with native `pi` and `sp` tags. It derives mutation controls from the actual native BAMs, encodes them with samtools, and rejects foreign parents, duplicate primaries, wrong models, invalid split intervals, removed split identity, truncated BAMs, wrong reference dictionaries, and inconsistent NM. Removing a represented parent changes its absence ledger. An empty result fails verification.

The installed stock build is exactly `2.1.2+8b8fc5d`. The verifier checks that full CLI/BAM version, including the source hash. The known informational message about an unavailable optimal batch-size benchmark is retained as batch-selection diagnostics. Other failure, error, and skip messages remain unresolved loader diagnostics. Stock batch size zero uses its fallback on this host; no optimized batch profile or model-tier winner is claimed.

If the installed model does not split the source fixture, qualification fails. Retain that result and establish a compatible native fixture or model before full execution. A synthetic tag test does not close this gate.

## Execute the fixed schedule

After native qualification passes, run the ten interleaved timing observations and six full shard/model units:

```sh
uv run --locked python scripts/benchmark.py run results/stock/stock-20261022/plan.json --scope timing
uv run --locked python scripts/benchmark.py run results/stock/stock-20261022/plan.json --scope full
uv run --locked python scripts/benchmark.py report results/stock/stock-20261022/plan.json
```

The timing order is `H,S; S,H; H,S; S,H; H,S`. Each basecaller is a fresh process. Basecalling wall time comes from `/usr/bin/time -v` and includes startup, model loading, input, GPU work, regular-file BAM output, and shutdown. Recorder elapsed time is separate. Alignment, sorting, summaries, full BAM traversal, statistics, and calmd have separate stage clocks. Cache state remains uncontrolled.

`report.json` lists all planned units, individual outcomes, timing success counts, medians, and ranges. Unit completion counts remain separate from native attempt counts. Failed, interrupted, and superseded attempts remain in every stage history after an explicit retry. Each attempt exposes native wall and CPU clocks, host RSS, GPU observations, and its raw receipt. Reference, index parity, and qualification-control processes have separate entries in `other_native_processes`. Each verified unit has `parents.tsv` and `observation.json`. Absence stays explicit, with unresolved causes and unavailable complete-work qualification. Submitted-signal throughput includes all requested signal. Emitted-base throughput counts only actual output. No HAC versus SUP speedup or winner is reported.

## Resume retained work

Verify retained native artifacts without executing missing stages:

```sh
uv run --locked python scripts/benchmark.py verify results/stock/stock-20261022/plan.json --scope timing
```

Use `run` to create a missing derived stage after an observation failure. A verifier correction records a new source snapshot and rechecks retained native producers under the same input plan. Requalify native controls after a verifier correction before starting new full or timing work. A report counts only a successful observation from the current verifier. A newer observation failure makes the prior success unavailable until a later successful verification. Successful stages reuse only matching commands, plan identity, complete producer exits, clocks, and current evidence hashes. Existing output alone never qualifies. A failed or interrupted stage stops the invocation. It does not receive an automatic retry.

After diagnosing a failed native stage, request a new immutable attempt explicitly:

```sh
uv run --locked python scripts/benchmark.py run results/stock/stock-20261022/plan.json --scope full --retry full-development-hac:align
```

The example retries only a failed development HAC alignment. Its successful basecall remains retained. Changed successful evidence fails reuse even with `--retry`.

Inspect `units/UNIT/STAGE/ATTEMPT/start.json` and `finish.json` for commands, exit status, monotonic clocks, recorder location, and pins. The recorder directory retains raw stdout, stderr, UTC clocks, and native resource timing. Each stage also retains a GPU CSV, sampler stderr, and sampler exit status. The GPU projection accepts the native CSV values with units and counts unavailable samples for each field. Unsupported GPU fields remain unavailable. Native batch and chunk log lines remain in the observation.

Render the retained 2026-10-22 snapshot without native execution:

```sh
uv run --locked scripts/summarize-benchmark.py results/stock/stock-20261022 \
  --output research/stock-baseline-results.md \
  --power-observation provenance/verification/stock-power-snapshots-20261022T222833Z.json
```

The exporter displays retained results and checks report/plan identity. It does not requalify artifacts. Use the maintained runner's `report` action for current input and observation pin validation. The power observation records initial and final host snapshots only. Their observed change prevents a fixed-power performance claim; no timing result was replaced after that finding.

## Check the runner locally

```sh
scripts/record-command.sh benchmark-tests uv run --locked python -m unittest discover -s tests -p test_benchmark.py -v
```

The complete local check on the retained 2026-10-22 artifacts enables both genuine-data tests. The native BAM path below is the recorded HAC warmup in this workspace:

```sh
scripts/record-command.sh all-local-contracts env PYTHONPATH=tests \
  NANOPORE_NATIVE_BAM=logs/20261022T210643Z-manual-dev32-hac-sxfbo5/stdout \
  NANOPORE_CALMD_PLAN=results/stock/stock-20261022/plan.json \
  uv run --locked python -m unittest discover -s tests -v
```

Without those environment variables, the two genuine-data tests are explicitly skipped. Small native fixtures still run in CPU CI. The full validation artifact also exercises the [coordinate-confirmed MD ambiguity check](calmd-discrepancy.md), with native faidx evidence and rejection controls. The original failed observation remains separate from native command failures.

Local tests use real POD5 Writer files, ZIP extraction, bgzip, samtools-produced BAMs, native calmd, and a live GPU CSV query. Preparation tests execute the maintained reference producer and minimap2 on a tiny reference. Those parity-contract tests use an explicit substitute for the unavailable Dorado executable. They do not qualify genuine Dorado output. They exercise parent accounting, absence, strand normalization, CIGAR arithmetic, corruption, model and reference identity, summary joins, immutable reuse, failed attempts, and process interruption. Their constructed SAM headers and split tags test the adapter. Genuine Dorado production and split behavior require the native qualification commands above.

Reference disagreement is a proxy conditional on mapped emitted children. Biological base accuracy, biological quality calibration, variant-aware accuracy, and variant calling accuracy remain `NOT VERIFIED`.
