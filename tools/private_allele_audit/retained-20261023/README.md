# Executed private-allele audit source

These are byte-identical copies of the reader, independent Rust projection helper, and observation supplement executed on 23 October 2026. `SHA256SUMS` identifies the exact revisions. The [audit report](../../../research/private-allele-full-audit.md) states the observed results and limits.

This is historical methods source, not a portable audit CLI or a new execution grant. It depends on retained artifacts outside Git, absolute paths in the original worktrees, immutable prior hash receipts, and dated admission files. No raw data, output, binary, or admission file is included here. CI does not execute this archive.

The original attempt directory is `/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5/`. There, `audit.py` takes its output directory as its sole argument and reads that directory's `grant.json`; `project.rs` must be beside the reader. `supplement.py` reads its own directory's retained observations and grant. Both check the canonical host lock and expired clock bounds. The main reader compiles the projection helper. The supplement runs two malformed-input rejection controls against a byte-identical copy of the retained inference executable. Neither replays a scientific producer.

The main reader exited 1 after six successful data phases because the retained inference executable lacked execute permission. Its first tensor registration count also omitted the native-call artifact manifest. The separate supplement exited 0 and closes these two observation gaps. Its success does not rewrite the main reader's exit or result.

Inspect the source and retained receipts before designing a future audit. Any future execution needs a separately identified reader revision, fresh resource coordination and admission, and a new output directory. Preserve this archive, all prior failures, and successful producers unchanged.
