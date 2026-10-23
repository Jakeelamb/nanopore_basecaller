# Reproduce the controlled stock baseline

Use fresh names for each measurement series. Keep the original `stock-20261022` run and every failed or superseded analysis revision. The frozen method is in [the controlled plan](controlled-benchmark-plan.md). The current stock plan is `results/stock/controlled-20261022/plan.json`; raw accuracy inputs are `results/accuracy/controlled-20261022/inputs.json`; the accepted accuracy revision is `results/accuracy/controlled-20261022-v1.1-frozen`.

Acquire and qualify the unchanged stock inputs using [the original commands](benchmark-commands.md). The new steps require Rust 1.96.0 and bcftools 1.24. `scripts/build-accuracy-tools.sh` builds the checksum-pinned native release on a fresh installation. Its existing build directory is deliberately preserved rather than overwritten. The installed build and raw receipts are pinned in `provenance/accuracy-tools.json`.

Build and check the exact scorer before freezing any plan:

```sh
cargo +1.96.0 test --locked --manifest-path tools/accuracy/Cargo.toml
cargo +1.96.0 build --release --locked --manifest-path tools/accuracy/Cargo.toml
PYTHONPATH=tests uv run --locked python -m unittest \
  test_benchmark.ControlledMeasurementTests test_accuracy -v
```

For a fresh series, substitute new stock, input and analysis directory names throughout:

```sh
uv run --locked scripts/benchmark.py prepare results/stock/NEW-SERIES \
  --config config/controlled-stock-benchmark.json
uv run --locked scripts/accuracy.py prepare \
  --output results/accuracy/NEW-INPUTS
uv run --locked scripts/accuracy.py spans \
  --inputs results/accuracy/NEW-INPUTS/inputs.json
uv run --locked scripts/accuracy.py truth \
  --inputs results/accuracy/NEW-INPUTS/inputs.json \
  --analysis-root results/accuracy/NEW-ANALYSIS
```

Preparation records native complete FASTA decoding, both complete VCF REF checks/normalization, publisher-checked reference exclusions, and original variant footprints. The `truth` action creates both fixed domains for both donors. It retains read-only copies of its executable and source files and executes that copied binary. A later build cannot replace the recorded producer. Unsupported input, changed pins or incomplete evidence stops qualification.

Run the small genuine handoffs before sustained work:

```sh
uv run --locked scripts/benchmark.py run results/stock/NEW-SERIES/plan.json --scope smoke
uv run --locked scripts/benchmark.py run results/stock/NEW-SERIES/plan.json --scope fixture
uv run --locked scripts/benchmark.py qualify-native results/stock/NEW-SERIES/plan.json
uv run --locked scripts/accuracy.py run \
  --inputs results/accuracy/NEW-INPUTS/inputs.json \
  --analysis-root results/accuracy/NEW-ANALYSIS \
  --plan results/stock/NEW-SERIES/plan.json --scope smoke
```

Require four positive-denominator smoke scores and exact native/Rust parent-ledger closure, alongside the qualified native split fixture and mutation controls. CPU tests alone cannot satisfy these genuine-data gates.

With external power connected, the existing balanced platform profile, no foreign GPU compute and adequate disk reserve, run the sustained schedule:

```sh
uv run --locked scripts/warm-stock-inputs.py results/stock/NEW-SERIES/plan.json
uv run --locked scripts/benchmark.py run results/stock/NEW-SERIES/plan.json --scope full
uv run --locked scripts/benchmark.py run results/stock/NEW-SERIES/plan.json --scope timing
```

The warmup reads actual runtime inputs to `/dev/null` outside measured native processes. Do not flush system caches. This series uses explicitly reread files and fresh native processes; physical cache residency and driver cache contents are not independently measured. Use a new plan and warmup for a new series, particularly after reboot or a long interruption. Reusing an old warmup receipt does not establish a newly warmed cache.

The runner holds the host lock, waits for the declared cool/idle GPU condition, and samples required host/GPU controls before, during and after each native stage. A rejected attempt remains failed. Diagnose it and use an explicit retry only when appropriate; do not silently replace an outlier or successful producer. All ten timing processes use the same 2,608 development parents, in `H,S; S,H; H,S; S,H; H,S` order. No heavy scoring, compilation, acquisition or unrelated owned GPU work should overlap these measurements.

After every GPU job completes, score all full outputs and development repetitions:

```sh
uv run --locked scripts/accuracy.py run \
  --inputs results/accuracy/NEW-INPUTS/inputs.json \
  --analysis-root results/accuracy/NEW-ANALYSIS \
  --plan results/stock/NEW-SERIES/plan.json --scope full
uv run --locked scripts/accuracy.py run \
  --inputs results/accuracy/NEW-INPUTS/inputs.json \
  --analysis-root results/accuracy/NEW-ANALYSIS \
  --plan results/stock/NEW-SERIES/plan.json --scope timing
uv run --locked scripts/benchmark.py report results/stock/NEW-SERIES/plan.json
```

The score action binds the exact decoder receipt and SAM pinned by the current verified stock observation. It does not select a newer arbitrary decoder file. It checks the original input-parent universe and exact per-parent native child counts. Absences, unmapped records, clips, excluded bases and zero denominators remain explicit. Repetitions describe stock variability; they are not independent human samples.

Use `accuracy.py verify` with the same arguments to check retained scoring artifacts without executing a missing Rust stage. Use `verify-truth` to check retained truth artifacts. Changed source or executable pins require a deliberately new analysis revision. A report projection repair should reuse successful producers when their actual inputs and computation remain unchanged.

Final scientific acceptance requires exactly six full cohort/model outputs times both truth domains, positive eligible exposure for each, five complete-work timing observations per model, qualified native measurement evidence, and current source identities. Passing execution with an empty accuracy denominator does not qualify accuracy. Whole-read diploid accuracy, downstream variant calling and population conclusions remain outside this pilot.
