# Stock verification benchmark brief

The user extended the task on 2026-10-22. Alert them when stock Dorado, sufficient human raw electrical signal, and a complete reference are installed and verified. Then run every acquired POD5 through the native stock basecaller and provide legitimate reproducible verification benchmarks. No candidate modification is requested yet.

Inputs are in `config/assets.json`. Read `research/protocol.md` and `scripts/record-command.sh`. Stock Dorado is 2.1.2, HAC v6.0.0 and SUP v5.2.0. Three native 5kHz POD5 shards total 3.21 GB. The complete pinned GRCh38 is gzip-compressed and has publisher FAI/GZI indexes. Host has an RTX5070 Laptop 8GB GPU, CUDA13.4 driver/toolkit, 24 logical CPUs, ~96GB RAM, ~85GB initial free disk.

Design a small reproducible benchmark workflow and artifact schema. Native computation should use stock Dorado and samtools where those already provide correct metrics. Prefer avoiding a new biological scoring implementation. Python is permitted for orchestration and report glue; Rust is preferred if new substantial computation is genuinely needed. No implementation yet. Give exact proposed CLI commands only after tracing current source interfaces in `software/dorado-src/dorado/cli/cli_lib/{basecaller,aligner}.cpp`, not recalled syntax.

Required behavior:

- Verify native metadata and nonempty decoded signal and freeze read UUIDs before basecalling.
- Run every raw file through both exact model paths, preserve complete command/exits/UTC/logs/BAM headers, and validate BAM contents against input molecule membership, including stock read splitting.
- Align stock outputs to the complete fixed reference with an explicit pinned preset. Reuse a verified native minimap index if supported.
- Report BAM and mapping counts, read failures/drops, clipping, lengths, CIGAR/NM reference disagreement and native summary outputs. Label reference disagreement as a proxy, never biological accuracy.
- Sample known variant-aware confident regions only if the procedure is fixed and independently verified. Otherwise classify that scientific endpoint as NOT VERIFIED without inventing a truth score. GIAB VCF/BED files are available for future biological evaluation but sparse pilot data do not qualify variant-calling accuracy.
- Runtime baselines must demonstrate real work, count failures, include startup/I/O boundaries, retain raw clocks and resource observations, and provide at least five interleaved repetitions on a fixed deterministic development subset. Full-cohort runs may be single-run qualification with clear labels. No speedup/winner claim between accuracy tiers.
- Keep raw immutable inputs, stock controls, and future candidate outputs distinct. User explicitly authorizes stock processing of all acquired files, including HG005. This opens stock outputs only. Do not use held-out outcomes to choose future candidate changes.
- Make restarts skip only demonstrably successful verified units, never outputs that merely exist. Preserve failures and avoid silent retries of expensive execution. Include rejection controls on genuine native artifacts.
- Keep at least 30GiB free disk and do not run GPU benchmarks concurrently with other own GPU work or unfinished acquisition.

Write an independently reviewable design with usage, minimal data shapes, exact source-backed interfaces, completion predicates, and known limits. Each candidate owns a different file under `/tmp/nanopore-benchmark-design/` and does not edit the project. No child agents.
