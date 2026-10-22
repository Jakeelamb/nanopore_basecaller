# Run the fixed stock benchmark

Run these commands from `/home/jake/Projects/nanopore_basecaller`. Use the pinned UV environment.

## Complete preparation

Finish acquisition, asset verification, native signal inspection, model extraction, and full-reference qualification before creating a plan. The coordinator also supplies a qualified minimap2 index and genuine FASTA versus MMI parity receipts for both tiers. See [the accepted design](benchmark-design.md).

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

## Check the runner locally

```sh
scripts/record-command.sh benchmark-tests uv run --locked python -m unittest discover -s tests -p test_benchmark.py -v
```

Local tests use real POD5 Writer files, ZIP extraction, bgzip, samtools-produced BAMs, native calmd, and a live GPU CSV query. Preparation tests execute the maintained reference producer and minimap2 on a tiny reference. Those parity-contract tests use an explicit substitute for the unavailable Dorado executable. They do not qualify genuine Dorado output. They exercise parent accounting, absence, strand normalization, CIGAR arithmetic, corruption, model and reference identity, summary joins, immutable reuse, failed attempts, and process interruption. Their constructed SAM headers and split tags test the adapter. Genuine Dorado production and split behavior require the native qualification commands above.

Reference disagreement is a proxy conditional on mapped emitted children. Biological base accuracy, biological quality calibration, variant-aware accuracy, and variant calling accuracy remain `NOT VERIFIED`.
