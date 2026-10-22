# Human nanopore basecaller experiment

This workspace prepares a reproducible human raw-signal pilot and an unchanged Oxford Nanopore Dorado control. The current phase acquires and verifies inputs, then runs stock basecalling and alignment. Candidate training and improvement experiments come later.

The public repository is [Jakeelamb/nanopore_basecaller](https://github.com/Jakeelamb/nanopore_basecaller). Changes use feature branches and pull requests. `main` requires a pull request and the `cpu-contracts` check. See [the contribution instructions](CONTRIBUTING.md).

## Inputs

| Input | Pinned choice |
|---|---|
| Stock basecaller | Dorado 2.1.2, official Linux x64 binary and matching source |
| Models | R10.4.1 E8.2 400bps HAC v6.0.0 and SUP v5.2.0 |
| Development | HG002, flowcell PAW70337, raw POD5 shard 33 |
| Validation | HG002, independent flowcell PAW71238, raw POD5 shard 10 |
| Test control | HG005, flowcell PAW87816, raw POD5 shard 52 |
| Raw signals | 3,209,530,648 bytes, native 5 kHz, LSK114 |
| Alignment reference | Full GRCh38 no-ALT analysis set from GIAB, including publisher FAI and GZI |
| Future variant benchmarks | Sample-specific GIAB v4.2.1 GRCh38 VCF, tabix index, and confident-region BED |

`config/assets.json` is the acquisition manifest. It contains exact URLs, expected sizes, source-object ETags, intended roles, and publisher checksums where supplied. The frozen local hash lock is created only after acquisition passes. Partial downloads are not accepted inputs.

These are size-selected pilot shards, not random whole-genome samples. HG002 and HG005 may have appeared in vendor training. GRCh38 disagreement includes natural human variation and alignment error. The stock benchmark therefore reports reference agreement as a proxy. Biological base accuracy and variant-calling accuracy require separate qualification.

The stock run uses the official native Dorado executable. Its matching C++ source and recursive submodules are present locally for future changes. The native index producer was built from pinned source; rebuilding Dorado itself is a separate, currently unqualified step.

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

Raw POD5, reference files, and model archives stay separate from derived outputs. `data/splits/` contains frozen UUID membership and a deterministic development timing subset. `results/stock/` is reserved for stock observations. Every native command records UTC start and end, exit status, resource timing, stdout, and stderr through `scripts/record-command.sh`. Failed attempts remain evidence. Reporting errors are repaired from retained outputs rather than triggering another GPU run.

Large inputs, software distributions, model weights, generated results, and raw local receipts are excluded from Git. Public verification summaries identify their local receipt paths and exact commands. GitHub's CPU workflow checks acquisition, real POD5 decoding, and native BAM contracts. Full-reference integration and GPU qualification run locally and retain separate evidence.

The user authorized stock processing of all acquired files, including HG005. That opens the test control, so this is not a fully blinded study. Future candidate selection must use development and validation. The planned runtime baseline has five interleaved development repetitions per tier plus one full run per file and tier. No speedup or accuracy improvement is established by setup alone.

## Attribution

Raw human signals are from [Oxford Nanopore's GIAB 2025.01 release](https://epi2me.nanoporetech.com/giab-2025.01/), accessed 2026-10-22. The [AWS registry](https://registry.opendata.aws/ont-open-data/) lists CC BY-NC 4.0. The vendor software license is retained in `provenance/Dorado-LICENCE.txt` and the source checkout. Reference and benchmark provenance are retained from [NIST GIAB](https://www.nist.gov/programs-projects/genome-bottle).
