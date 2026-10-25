# Fixed Model A whole-parent native measurement

Model A fails the unchanged promotion gates. Its graph and reference outputs improve the native mapping-conditioned error rate by 0.6821% in domain 100 and 0.5327% in domain 500. Both miss the 1% target. They preserve all 829 native ALT observations, but none of those observations overlaps a changed center. The prior withheld private query 21 failure also remains a failure. No model is promoted.

The eight fixed policies have three distinct complete-parent SAMs. Both graph profiles share 43 changed centers. Both reference profiles share 45. Both None and both foreign-context profiles share the historical reference-free bytes with 9 changed centers. Aliases reuse a single qualified mapping. The two new native mappings produce identical scored endpoints despite their different emitted and mapped SAM bytes.

The executable source census consists of `tools/context_decoder/model_measure.py` and `tests/test_context_model_measure.py`. This document records the protocol and final evidence without changing that executable source identity. The 40-file C++ model census and existing observers remain unchanged. The original observer is imported at its original absolute source root. Its maintained producer verification checks raw stage receipts, native attempts, actual commands, retained source, and outer terminal evidence. The new emission is checked through its actual native stage and raw stdout, plus the external terminal and launcher cleanup. All 64 parent sequences and qualities are reconstructed from the emitted edit ledgers and independently spliced before mapping. The disabled output must preserve native SEQ/Q. Mapping must preserve every emitted primary SEQ/Q, including reverse orientation.

The frozen snapshot is `/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json`, SHA256 `f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324`. Every consumed reference, index, truth, eligible mask, parent list, executable, native SAM, reference-free mapping, baseline observation and historical output is checked against its actual pin. Actual `ldd` output and each resolved runtime library are retained for Dorado, samtools, pairer and observer. No neural or GPU producer runs.

Each unique new output uses the original native command contract. Samtools converts the emitted SAM to BAM. Dorado aligns with the existing whole-reference index, two threads, `--no-sort`, and `--mm2-opts '-x lr:hq -I 16G --eqx -Y'`. Samtools emits the aligned SAM. The unchanged pairer scores native and historical reference-free comparators in both fixed eligible domains 100 and 500, then summarizes all 64 parents. The unchanged variant observer observes the aligned SAM and compares with native and reference-free observations.

The endpoint is conditional on native mapping and frozen invariant masks. Error fraction is `(x+i+d)/(m+x+i+d)`. The paired reference exposure and each comparator's separate column denominator are retained. Native pairer summaries retain parent and genomic 1 Mb block bootstrap intervals. These are technical resamples of the same exposed HG002 flowcell, not independent biological confirmation. Zero-exposure parents remain explicit.

Native ALT preservation uses the frozen 829 observations, split into 740 SNVs, 50 insertions and 39 deletions. Changed-footprint support conservatively projects each edited native query interval and one query base on each side through the original primary CIGAR. It joins that span to the unchanged observer's variant window. Unmapped or wholly clipped footprints remain unavailable. Counts are observation pairs, not independent sites. A retained ALT count outside a changed footprint supplies no local edit-safety evidence. The unchanged requirement of 100 productive observations per class remains visible alongside the 1% relative improvement target in both masks and strictly negative technical uncertainty upper bounds. A failed or unsupported gate stays failed.

The ignored copied controller admits one unit at a time with a fresh identity and nonblocking canonical `/home/jake/Projects/nanopore_basecaller/results/stock/host.lock`. It rejects an existing service name before launch without touching that service. Its start receipt pins the actual recorder. The controller enforces 300 seconds outer wall time, two CPUs, 16 GiB kernel memory, 24 GiB address space, zero swap, 512 MiB aggregate existing and new worktree outputs, and 30 GiB disk reserve. The worker has 280 seconds. Native stages retain the actual recorder's eight required raw files, including cwd, clocks, GNU time and stderr. The controller writes durable terminal proof before projecting cleanup and retains the lock until both the worker cgroup and launcher tree are terminal. A failed attempt remains on disk.

The coordinator ran these exact commands successively from the v5 worktree.

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python logs/context-feedback/program-runs/run-measure-bounded.py \
  v5-measure-graph-1 tools/context_decoder/model_measure.py measure \
  --arm graph --output results/context-feedback/v5-measure-graph-1 \
  --admission-id v5-measure-graph-1
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python logs/context-feedback/program-runs/run-measure-bounded.py \
  v5-measure-reference-1 tools/context_decoder/model_measure.py measure \
  --arm reference --output results/context-feedback/v5-measure-reference-1 \
  --admission-id v5-measure-reference-1
```

Each worker first executes the exact engineering command below. No skip is accepted.

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python -m unittest discover -s tests -p test_context_model_measure.py -v
```

After the outer tree is terminal, `model_measure.py review --output OUTPUT --admission-id IDENTITY` rechecks completion pins, all source and data evidence, the exact 19-stage command chain, executable runtime closure, external raw recorder and terminal proof, denominators and gate projections. The final bounded review passes. The independent same-family verdict is `PASS_EVIDENCE_FOR_REJECTED_DEVELOPMENT_CANDIDATE`; [the final evidence summary](context-model-final-evidence.md) records its pins and limits. The earlier reviewed document is preserved at `logs/context-feedback-program/reviews/model-measurement-reviewed-a176959d.md`.

## Observed endpoints

Both graph and reference outputs have the following exact endpoint counts. Each row uses its own insertion-inclusive denominator. The reference exposure is 863,283 in domain 100 and 438,366 in domain 500 for both sides of every pairing.

| Domain | Output | Errors | Column denominator | Error fraction |
| --- | --- | ---: | ---: | ---: |
| 100 | Native | 8,785 | 865,579 | 0.010149275802670813 |
| 100 | Historical reference-free | 8,784 | 865,580 | 0.010148108782550428 |
| 100 | Graph or reference | 8,725 | 865,571 | 0.010080051203194192 |
| 500 | Native | 3,939 | 439,381 | 0.008964884690052596 |
| 500 | Historical reference-free | 3,935 | 439,382 | 0.008955760591011922 |
| 500 | Graph or reference | 3,918 | 439,379 | 0.008917130768653030 |

Graph and reference each reduce the error rate by 0.682064% and 0.532677% against native in domains 100 and 500. Against historical reference-free, the reductions are 0.670643% and 0.431340%. All four reductions fall below 1%. All 64 parents remain accounted for. Domain 100 has 53 positive-exposure and 11 zero-exposure parents. Domain 500 has 50 and 14. Neither mapping has an absent parent. Dorado writes 64 reads, with 98 records, 61 mapped primary records and 3 unmapped primary records.

For both outputs, the native candidate-minus-baseline error-fraction 95% technical intervals are as follows.

| Domain | Parent bootstrap | Genomic 1 Mb block bootstrap |
| --- | --- | --- |
| 100 | [-0.00009997548479459724, -0.00004130419822593635] | [-0.00010033850837496382, -0.000040539655877486896] |
| 500 | [-0.00008409493384328379, -0.000016975115827965945] | [-0.00008278023245555932, -0.000017565143675210386] |

The upper bounds are negative, but this does not override the failed improvement and variant-support gates. All 829 native ALT observations are retained, with zero changed-footprint overlaps for SNVs, insertions and deletions. All 830 reference-free ALT observations are retained. One reference-free SNV observation at `chr1:14135554:A:T` overlaps `ordinary/148/ordinary` and remains ALT. No insertion or deletion observation overlaps a changed footprint. No edit footprint is unavailable. Neither the two masks nor the repeated profiles create independent biological observations.

## Execution evidence

The executable source SHA256 values are `e05619d9a04501d7f740daa0cda10f02bb853d122b257743c023575d62366f1c` for the measurement adapter and `1a7f60d9ddf3cabf03cb9b8c401cd076207176976d0ecb16e2d9bba502701736` for its controls. The copied ignored controller is `logs/context-feedback/program-runs/run-measure-bounded.py`, SHA256 `04c0ff7e44003e7361d330bdca5c9d05c4f4e7273958dd99d7c88e01ef26be73`. Both workers execute 17 controls with zero skips before native mapping. Both units complete with exit 0, no outer error, inactive or unloaded worker services, zero worker/control PIDs and terminal launcher cleanup.

The graph completion is `results/context-feedback/v5-measure-graph-1/complete.json`, SHA256 `d1cac4af5d61634e9c281ab6ed40e3b7181d31f7335ea63eaca848237633b7b4`. The reference completion is `results/context-feedback/v5-measure-reference-1/complete.json`, SHA256 `76ca9c3490c7b191f8a60c66399301cf1beeb7f8c6d50269cd9c21483dca4617`. Their `result.json` files contain native and reference-free summaries, exact input and mapping pins, runtime closures, aliases and changed-footprint ALT observations. Each `complete.json` pins all native stages and output files. The external `logs/context-feedback/program-runs/run-v5-measure-{graph,reference}-1/` directories retain start, terminal and cleanup receipts.

The raw whole-worker recorder directories are `logs/context-feedback/recorder-root/logs/20261025T003317Z-v5-measure-graph-1-YrcBR7/` and `logs/context-feedback/recorder-root/logs/20261025T003502Z-v5-measure-reference-1-SPbJ9w/`. Their GNU time records report elapsed times of 1:17.07 and 1:18.92, with maximum RSS of 12,298,752 and 12,334,540 kbytes. These are bounded execution receipts, not a speed comparison or throughput claim. Every native stage retains its own command, cwd, start/end, exit, stdout, stderr and time record. Stock, model, historical mappings and private-challenge outputs remain unchanged.
