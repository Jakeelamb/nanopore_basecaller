# Retained F1 format-only result

Root executed the exact six-file formatter once. The retained worker and outer receipts both report exit0, no error, no missing worker records and empty-before-unlock. This owner inspected those receipts and matched every formatted file's current SHA256 with `complete.json.linked`. No formatter replay occurred.

- Input source head was `8187e2045862fd0832f210b3eb9f2e1a3f26aea3`.
- Root grant is `/home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes/grants/f1-format-01.json`, SHA256 `0caa216c02b0bf4622f5f9c0072401b6bb747b7f2a91410c9c0c1b92e239a40b`.
- Retained attempt is `results/prefix-feedback/format-01`. Root macro is `/home/jake/Projects/nanopore_basecaller-retrieval/logs/20261026T193806Z-feedback-f1-format-01-DGjYtm`.
- Frozen F4 source is `d190ab3f8175f1af7b5d4057b893ef6424b9d41f`, adapter SHA256 `8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4`.
- Actual caps were30seconds, CPU2, RAM4GiB, AS8GiB and swap0. The earlier proposed1CPU/1GiB values were never used.

The six formatted files are `include/prefix_feedback/session.h`, `src/io.cpp`, `src/session.cpp`, `src/location.cpp`, `src/main.cpp` and `tests/controls.cpp`, relative to `tools/prefix_feedback`. The text delta contains formatting and include regrouping. The owner inspected the actual source diff; no build or AST qualification is inferred from a formatter exit. Numerical, Python, CTest, native mapper and biological execution remain pending.
