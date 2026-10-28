# Unchanged fixed-state scorer and DGS parser

Copied byte-for-byte from `/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/` on 2026-10-28.

- `crf.rs` SHA256 is `3171343d81477d4d967e300466e9ba3e3d770164f34438dcedd0867ca5ea8a99`.
- `scores.rs` SHA256 is `2122831be9c1fad80e953268cf2138909665f703b697b5f803604b9450f0fa2e`.

The adapter calls `ScoreWindow` for every fixed initial state. It does not modify these files or copy the production C++ recurrence. Existing upstream conditional tests remain unchanged in the original repository.

`Cargo.lock` copies the original graph_prior lock with only its local package and unused accuracy package replaced. Exact registry versions and checksums are retained. Cargo has not validated this prepared lockfile.
