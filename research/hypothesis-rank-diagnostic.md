# Retained-score hypothesis rank diagnostic

Predeclared on 2026-10-23 before diagnostic results. The exact config is `config/hypothesis-rank-dev-v1.json`. The question is whether exact distance-two expansion improves retained likelihood maxima or changes the four registered finite-policy decisions relative to original H. No biological endpoint is inspected.

The diagnostic joins 451 development rows by query index and UUID, including 331 scored and 120 excluded rows. It requires every old sequence, presence bit and f64 likelihood bit to survive. It reports per-class best sequence and native-relative gap, added counts, and policy argmax and emitted-choice changes. Native wins exact ties, then lexical sequence order breaks nonnative ties. It reconstructs complete UUID/SEQ/Q outputs under unchanged splicing and uncalibrated `!` edited-core quality, compares actual retained outputs, and looks for exact source-policy identity matches. Historical 0.0-deficit rules and the original scoring SAM baseline are separate comparisons.

An unchanged maximum is a useful negative result. For real arithmetic, unchanged class representatives imply unchanged binary-prior winners at all weights for the same prior classes. Literal f64 addition can collapse or perturb distinctions at extreme weights or near boundaries. This is not universal numerical or proposal-space exhaustion.

Throughput checkpoint. One streaming Rust scan with bounded 120-second CPU, 2-GiB address-space limit, output cap 100 MiB, 30-GiB disk floor and canonical host lock. No GPU. Source tracing and development continue if lock admission fails. Meaningful controls add improving panel/nonpanel hypotheses, exercise native and lexical ties, and reject a changed inherited score. Prove It Works requires actual rows and complete output identity comparisons.

## Measured result

Exact inheritance passes for all 47,230 original hypotheses. The expanded catalogue has 3,118,978 retained hypotheses. It adds 3,071,748 hypotheses, all graph-absent. The diagnostic joins all 451 unique development rows and preserves the 120 original exclusions.

The graph-absent best likelihood and representative change in 10 windows. The graph-present best likelihood and representative never change. The linear-reference-absent class changes in four windows. The linear-reference-present class never changes. These are strict score changes, rather than only lexical changes on equal scores. Four windows change the actual argmax under each of the four registered finite policies. Zero windows change their edit flag or emitted sequence. All four complete outputs remain identical between old and expanded H across every one of the 64 UUID/SEQ/Q records. The actual expanded-H emitted SAMs also match the independent reconstruction.

| Registered finite policy | Argmax changes | Emitted-window changes | Complete-parent changes |
| --- | ---: | ---: | ---: |
| native-preservation | 4 | 0 | 0 |
| compound-reference-free | 4 | 0 | 0 |
| compound-panel-100 | 4 | 0 | 0 |
| compound-linear-100 | 4 | 0 | 0 |

The actual four historical original-H arms reconstruct with zero complete-parent SEQ/Q differences. This holds using either the cohort-native SAM or the original likelihood producer's scoring SAM. Their files have different byte hashes, but their full 64-parent SEQ/Q maps are identical. The historical arms use a zero allowed neural deficit. The registered panel and linear policies allow 0.5. Historical-policy differences must therefore remain separate from the measured zero expansion effect.

## Exact source-output reuse

The diagnostic reads and compares all 614 complete source candidate artifacts. It compares full UUID/SEQ/Q maps before recording compact length-prefixed identity hashes. Counts alone play no role in declaring matches. Three actual source artifacts match the four expanded-H outputs.

| Expanded-H output | Exact source-policy matches | Source SAM SHA256 |
| --- | --- | --- |
| native-preservation and compound-reference-free | historical-neutral and historical-025, plus the source zero-edit frontier outputs | `a2f7cdb61c14d901095f1c65dd5ed8b716bd12546feb993d9959813f411f54a6` |
| compound-panel-100 | panel-deficit-050, frontier-panel-00194-boundary, frontier-panel-00195-interval | `61354b3522e0c97bd8cc22bf7803672992e03acfe41066691f40844ba8f1d283` |
| compound-linear-100 | linear-deficit-050, frontier-linear-00196-boundary, frontier-linear-00197-interval | `ffcfaba4e571a74bbeeec4efce1247177f2753fde59bb1e9c3646512879551a6` |

The matched panel-deficit-050 and linear-deficit-050 policies use lambda 1, margin 0.5 and allowed neural deficit 0.5. The historical identity matches use different parameter settings. Equality here is actual emitted output equality, not equivalence of policy rules or candidate rankings. The corresponding three named `development/evaluated/seq-q-*.json` files exist. This diagnostic does not inspect their biological outcomes. Reusing an existing deterministic downstream measurement still requires its mapping, reference, scorer and input provenance to match.

## Scientific implication

Distance-two proposal expansion does improve some retained candidate scores, so complete score saturation would be a false conclusion. The expansion gives zero additional graph-present support and zero additional emitted edits at the registered settings. Repeating the same biological evaluation for these unchanged outputs would not create evidence of an expansion benefit.

The strongest next intervention is to test the scoring context and candidate ranking on development data. Keep H fixed while testing whether more signal context or corrected anchor/state assumptions produce a meaningful neural separation for candidate alternatives. Predeclare that intervention and preserve stock controls. Further unguided radius expansion is less informative until the likelihood and gate bottleneck is addressed. This result does not show that all useful candidates are exhausted, that reducing a gate is biologically safe, or that the retained likelihoods are independently correct.

## Reproduction and retained failures

Run from `/home/jake/Projects/nanopore_basecaller-coverage`.

```sh
bash tools/hypothesis_coverage/run_locked.sh generate cargo generate-lockfile --offline --manifest-path tools/hypothesis_coverage/Cargo.toml
bash tools/hypothesis_coverage/run_locked.sh final-single-linker-thread bash tools/hypothesis_coverage/final_checks.sh
```

The wrapper records exact argv, cwd, UTC clocks, raw stdout/stderr, exit status and GNU time under `logs/hypothesis-coverage/`. It uses the canonical stock host lock with a 10-second admission timeout. The executable and exact source/config pins remain in the same log tree. Initial real data execution finished successfully in 5.47 seconds with 51,572 KiB peak RSS. This is a resource observation for this diagnostic, not a comparative performance claim.

The retained `20261023T164819Z-windows` lock admission exits 75 without running its data projection. The initial strict clippy command exits 101 for a needless borrow, then the source removes the borrow. The first terminal check exits 101 because LLD cannot create a thread under the 2-GiB address-space cap. The final script bounds Cargo and linker threads to one. Failed attempts remain intact. No producer replay, scalar rescoring, tensor computation, native GPU work, validation, HG005 selection, or truth endpoint inspection occurs.

Model the Domain shaped the typed row join and binary class representatives. Prove It Works required actual inherited likelihood bits and full-parent output comparisons.

The four new global winners occur at queries 7, 150, 417 and 423. Their native-relative likelihood gains are respectively 0.1094694602, 0.0046105960, 0.0046602687 and 0.0702397250. Each is below the 0.5 objective margin. The remaining six improved graph-absent representatives still trail the native likelihood by 0.7956 to 8.4507. No changed representative reaches the registered emission conditions.

Final evidence is `results/hypothesis-coverage/final-v1/result.json`, the complete per-window score/string/gap/decision ledger `windows.jsonl`, and `pins.json`. The final pinned diagnostic verifies 796 unique file pins, including genuine catalogue and bridge source, binary and raw receipt closure, original ancestry, all source candidate SAMs, its own executable and sources. The four original-H historical reconstruction checks each compare all 64 actual UUID/SEQ/Q records. The registered panel output differs from historical graph-100 in 21 parent records because of the declared neural-deficit policy change. It remains identical to the matched original-H panel-deficit-050 output, proving that this historical difference is not caused by distance-two expansion.

The terminal command `bash tools/hypothesis_coverage/run_locked.sh final-single-linker-thread bash tools/hypothesis_coverage/final_checks.sh` exits 0. Its receipt is `logs/hypothesis-coverage/20261023T165055Z-final-single-linker-thread/`. Formatting, all three behavior controls, strict all-target clippy, release build, and the final genuine-data diagnostic pass. `final-source-executable-pins.sha256` identifies the frozen source and executable. The three output identity matches are reuse opportunities only. Biological correctness, ALT retention, likelihood correctness, large-weight f64 behavior and effects of any new context/model remain outside this evidence.
