# Human nanopore basecaller experiment

This workspace contains a pinned human raw-signal pilot and an unchanged Oxford Nanopore Dorado control. Stock basecalling and alignment have completed on every acquired file with both model tiers. Candidate training and improvement experiments come later.

The public repository is [Jakeelamb/nanopore_basecaller](https://github.com/Jakeelamb/nanopore_basecaller). Changes use feature branches and pull requests. `main` requires a pull request and the `cpu-contracts` check. See [the contribution instructions](CONTRIBUTING.md).

## Inputs

| Input | Pinned choice |
|---|---|
| Stock basecaller | Dorado `2.1.2+8b8fc5d`, official Linux x64 binary and matching source |
| Models | R10.4.1 E8.2 400bps HAC v6.0.0 and SUP v5.2.0 |
| Development | HG002, flowcell PAW70337, raw POD5 shard 33 |
| Validation | HG002, independent flowcell PAW71238, raw POD5 shard 10 |
| Test control | HG005, flowcell PAW87816, raw POD5 shard 52 |
| Raw signals | 3,209,530,648 bytes, native 5 kHz, LSK114 |
| Alignment reference | Full GRCh38 no-ALT analysis set from GIAB, including publisher FAI and GZI |
| Accuracy truth | Sample-specific GIAB v4.2.1 GRCh38 VCF, tabix index, and matching confident-region BED |

`config/assets.json` is the acquisition manifest. It contains exact URLs, expected sizes, source-object ETags, intended roles, and publisher checksums where supplied. The frozen local hash lock is created only after acquisition passes. Partial downloads are not accepted inputs.

These are size-selected pilot shards, not random whole-genome samples. HG002 and HG005 may have appeared in vendor training. Accuracy is measured only in GIAB-supported reference-identical intervals outside fixed variant, reference-error and unsupported-star confidence neighborhoods. It is conditional on publisher donor labels and accepted primary mappings. Whole-read diploid accuracy, variant calling and population generalization remain unsupported.

The stock run uses the official native Dorado executable. Its matching C++ source and recursive submodules are present locally for future changes. An isolated unchanged-input Release build now passes compilation and selected CPU contracts. [Build evidence](research/source-build-notes.md) distinguishes its CUDA 13 dependency stack from the official CUDA 12 distribution; native GPU and accuracy qualification have separate gates.

## Reproduce acquisition

Use `uv` and the pinned project environment. Native prerequisites are Git, curl, GNU time, a C compiler and make, samtools, bgzip, and a compatible NVIDIA driver. The verified host environment and native executable hashes are retained under `logs/` and `provenance/`.

```sh
uv sync --locked
uv run --locked scripts/acquisition-status.py
scripts/bootstrap.sh
```

Bootstrap acquires the exact inputs, verifies their hashes, restores the stock binary and model files from verified archives, hydrates pinned source submodules, builds the matching native index tool in a separate copy, and inventories signals. It reinstalls stock controls, so keep future edited models and binaries in separate candidate paths. Do not start a second acquisition or bootstrap while the current acquisition jobs are running.

The acquisition transfers about 8.1 decimal GB before source dependencies and requires more space for extraction, reference indexing, and results. The scripts preserve a 30 GiB free-space reserve. They download source objects using resumable checked byte ranges and reject changed object ETags or wrong publisher checksums.

After bootstrap:

```sh
uv run --locked scripts/verify-assets.py
uv run --locked scripts/inspect-signals.py
uv run --locked scripts/prepare-reference.py
uv run --locked python -m unittest discover -s tests -v
```

`prepare-reference.py` verifies full native reference decoding and indexed access, then builds the minimap index. Native Dorado FASTA versus MMI parity still needs genuine development smoke BAMs supplied through repeated `--parity-bam` arguments. A built index is kept separate from a qualified index.

## Evidence and experiment rules

Read [the protocol](research/protocol.md) before changing a basecaller. Read [the accepted benchmark design](research/benchmark-design.md) for the stock run and its completion predicates. [Data selection evidence](research/data-sources.md) records sample provenance, selection bias, licensing, and vendor-training uncertainty. [The setup plan](research/setup-plan.md) tracks the authorized phases. `decisions.tsv` is the append-only decision trail.

[The source trace](research/dorado-code-path.md) follows current calibration, chunking, both neural architectures, decoding, splitting, trimming, filtering, and output accounting. [The prospective experiment](research/prospective-experiment.md) defines paired accuracy, speed, yield, selection, uncertainty, and external confirmation requirements. Register a concrete hypothesis and endpoint before candidate development; freeze the full registration before validation. No candidate is registered by that document.

[Source qualification](research/source-qualification-results.md) separates the unchanged-input build, native source runtime, exact vendor equivalence, fixed-domain accuracy, parent yield, and comparative performance. All four full development/validation observations and eight accuracy scores are verified. Canonical calls and numerical scores match official controls exactly; the frozen literal artifact gate remains failed because six diagnostic tables differ only in row order. Comparative performance is not run. [CUDA diagnostics](research/source-runtime-diagnostics.md) preserve successful kernel-path traces and the failed OS-runtime tracing attempt. [The independent review](research/source-qualification-review.md) identifies accepted and pending scopes. CPU CI exercises the source adapter's contracts; GPU and biological claims require the distinct local receipts.

[Controlled baseline results](research/controlled-baseline-results.md) report the repeated timings, bounded accuracy, technical confidence intervals, quality reliability, length/context strata, homopolymer projections, input/output accounting, controls and retained failures. Read [the frozen method](research/controlled-benchmark-plan.md), [reproduction commands](research/controlled-commands.md), and [independent audit](research/controlled-baseline-review.md). The [original stock results](research/stock-baseline-results.md) remain unchanged historical evidence from the earlier run with uncontrolled power. The [MD discrepancy investigation](research/calmd-discrepancy.md) records a stock reference-annotation limitation and its narrowly verified exception.

The completed cohort has 20,954 input parents and 3,750,272,700 electrical samples. SUP represents every input parent. HAC represents 20,937 parents, leaving 17 HG005 UUIDs absent from output. Their ledgers and unresolved causes remain explicit. The new series contains six full jobs, ten timing jobs, two smoke jobs and one genuine split fixture. Native qualification includes 21 controls. Accuracy uses both predeclared 100 bp and 500 bp exclusion/erosion domains; parent bootstrap intervals describe within-pilot technical resampling, not population uncertainty.

On the RTX 5070 Laptop GPU with a recorded 100 W power ceiling and balanced profile, all five timing processes per tier represent all 2,608 development parents and 641,769,607 signal samples:

| Stock tier | Native basecall median | Five-run range |
|---|---|---|
| HAC | 35.40 s | 34.93–35.63 s |
| SUP | 173.36 s | 173.04–174.33 s |

These are fresh-process clocks with warmed filesystem inputs, including stock batch selection and output. Cooldown and observer overhead have separate clocks. Other hardware, thermals, batch settings or workloads require new measurements.

Primary 100 bp domain accuracy, conditional on the truth and mapping policy above:

| Cohort | HAC | SUP |
|---|---|---|
| HG002 development | 98.64% | 98.96% |
| HG002 validation | 98.60% | 98.83% |
| HG005 stock control | 98.11% | 98.48% |

The full report includes both domains, their scored exposure, technical confidence intervals and losses. These percentages do not describe every emitted base or absent read.

Raw POD5, reference files, and model archives stay separate from derived outputs. `data/splits/` contains frozen UUID membership and the original smaller timing subset. Controlled timings use all 2,608 development parents in five fresh processes per model, in the frozen interleaved order. `results/stock/` and `results/accuracy/` hold separate native observations and scoring artifacts. Every native command records UTC start and end, exit status, resource timing, stdout, and stderr through `scripts/record-command.sh`. Failed attempts remain evidence. Reporting errors are repaired from retained outputs rather than triggering another GPU run.

Large inputs, software distributions, model weights, generated results, and raw local receipts are excluded from Git. Public verification summaries identify their local receipt paths and exact commands. GitHub's CPU workflow checks acquisition, real POD5 decoding, and native BAM contracts. Full-reference integration and GPU qualification run locally and retain separate evidence.

The user authorized stock processing of all acquired files, including HG005. That opens the test control, so this is not a fully blinded study. Future candidate selection must use development and validation. The controlled rerun requires connected external power, the balanced profile, a cool idle GPU start and continuous host/GPU evidence. Laptop clocks and fans remain stock, and the host is shared. One full HG005 SUP clock is explicitly descriptive because an owned CPU check overlapped it; the [measurement note](provenance/verification/controlled-measurement-notes-20261023.json) preserves the missing receipt and timing uncertainty. All ten primary timing windows must follow its confirmed stop bound. No candidate improvement or model winner is claimed; future speedup claims require fresh matched controls.

## Reference-assisted research

Reference and pangenome assistance is the current priority. The [compound-catalogue bridge](research/compound-frontier-bridge.md) admits retained hypotheses with genuine producer custody and complete-parent checks. Its [independent engineering review](research/compound-frontier-bridge-review.md) states the qualified scope. The unchanged stock controls remain authoritative. Candidate accuracy, variant retention, yield and end-to-end speed require separate development experiments and reserved confirmation.

The [retained-score development experiments](research/retrieval-development-wave.md) test expanded hypothesis coverage, a [flank-conditioned graph compatibility prior](research/flank-prior-experiment.md), and explicit private-allele challenges. Coverage and conditioning produce no additional calls under the frozen rules. The enlarged local challenge exposes an insertion erased after panel withholding. The [completed artifact audit](research/private-allele-full-audit.md) verifies the saved scores, registered tensors, projections, decisions and target accounting, preserving the main reader failure and successful observation supplement separately. These results do not establish an accuracy or speed improvement. A [prospective confirmation design](research/retrieval-confirmation-design.md) and [frozen HG001 sampling manifest](config/retrieval-confirmation-hg001-v1.json) define an outcome-blind acquisition option. No acquisition or confirmation result is implied. The [design review](research/retrieval-design-review.md) qualifies source and metadata checks only. The [priority run](research/retrieval-priority-run.md) records ownership and holds.

CPU CI lists the bridge, coverage, flank and private-allele Rust contracts and hermetic boundary tests. Genuine retained-producer controls, native emission, biological scoring and GPU measurements require their distinct local receipts.

## Attribution

Raw human signals are from [Oxford Nanopore's GIAB 2025.01 release](https://epi2me.nanoporetech.com/giab-2025.01/), accessed 2026-10-22. The [AWS registry](https://registry.opendata.aws/ont-open-data/) lists CC BY-NC 4.0. The vendor software license is retained in `provenance/Dorado-LICENCE.txt` and the source checkout. Reference and benchmark provenance are retained from [NIST GIAB](https://www.nist.gov/programs-projects/genome-bottle).
