# Normalized context scoring remains rejected

Both frozen Model A policies fail promotion. Their complete outputs reduce the native error rate by 0.682064% and 0.532677% in the two development masks, below the unchanged 1% target. They also accept an incorrect reference haplotype in the withheld private-allele diagnostic. No candidate is promoted.

This unit evaluates normalized context scoring over the qualified native and escape candidate union. Genuine prefix feedback, uncertainty targeting and additional-molecule context remain separate program units.

The model uses fixed mutation rates of 0.001 and 0.01, a 0.5 uniform-DNA mixture component, strength 1 and the existing 0.5 margin and signal-deficit gates. It evaluates graph, reference, missing and foreign contexts on matched candidates and neural scores. The score is a conditional context feature, not a calibrated allele posterior.

All 368 cases complete. The eight policies produce three unique complete-parent SAMs. Graph and reference require two new native mappings; the other policies reuse the byte-identical qualified reference-free output. Graph and reference have identical scored endpoints despite 43 and 45 changes relative to native.

| Development mask | Native errors | Graph or reference errors | Relative error-rate reduction |
| --- | ---: | ---: | ---: |
| 100 | 8,785 | 8,725 | 0.682064% |
| 500 | 3,939 | 3,918 | 0.532677% |

All 64 parents remain accounted for. The parent and genomic-block technical interval upper bounds are negative. These resamples describe the exposed development flowcell and do not establish biological replication. Exact column denominators, counts, commands and intervals are in [the native measurement report](context-model-measurement.md).

All 829 native ALT observations survive, but none overlaps a changed footprint. The required productive variant support therefore remains absent. The private failure is an insertion ALT at `chr17:75510527:T:TC`. Both rates accept exact REF under withheld graph and reference context. Reference context also accepts REF in the ordinary private diagnostic. These repeated rows concern one allele. The positive uniform-DNA component does not establish rare-allele safety.

The final bounded receipt review passes at `results/context-feedback/v5-measure-review-1/complete.json`, SHA256 `0c813b385c81c32b4dfb107de7fd1b5d35ae0db43bbec8181c5c4a0e54163b4d`. It revalidates both actual 19-stage chains, all raw recorder files, source and runtime pins, exact parent sequence and quality custody, and endpoint projections. Each measurement executes 17 controls with zero skips before native work. The observer sibling executes 40 controls with zero skips; the earlier observer failure remains retained.

An independent same-family review returns `PASS_EVIDENCE_FOR_REJECTED_DEVELOPMENT_CANDIDATE`. Its report is retained at `logs/context-feedback-program/reviews/model-final.md`, SHA256 `665b968def752e261a43ce1a4673730f2612f5be60fbe3f8398225e458d901d8`. The independent audit checks 4,808 small-file hashes, 304 raw native files, 2,944 decisions, parent and block count conservation, aliases and private labels. Twelve large external objects receive size checks in that independent pass; the inspected bounded validation separately rehashes their registered pins.

The successful mapping units use two CPUs, 16 GiB RAM, 24 GiB address space, zero swap and a 300-second outer envelope. Output and disk stops are sampled thresholds. Their terminal and launcher proofs pass. Failure-mode saturation and a hard bound on a broken terminal-observation retry loop remain unqualified. No native neural producer or GPU producer is replayed, and no comparative speed claim is made.

[The machine-readable evidence pins](context-model-result-pins.json) identify the retained artifacts. These results do not close the catalogue bridge or the wider context-feedback program.
