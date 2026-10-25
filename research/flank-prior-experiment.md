# Development flank compatibility experiment

This implements the independently reviewed `flank-conditioned-prior-design.md` in a separate Rust crate. Stock controls, graph-prior, graph-frontier and the catalogue bridge are unchanged. The hypothesis is that disjoint unchanged native flanks can distinguish indexed path centers that binary panel presence treats equally. This is empirical neural/prior score fusion. Alternating recurrent neural layers mean that disjoint called bases are not independent signal evidence.

Before inspecting compatibility, query indices 0 through 31 were fixed in the task and protocol. Development data only are read. No validation or HG005 outcomes are inputs. The fixed rule uses weight one, objective margin 0.5 and allowed neural deficit 0.5. Off-panel hypotheses remain admitted with zero bonus. Tied best flank distances receive exactly one. Left/right disagreement abstains to binary presence. Identical flank/center triples are deduplicated without donor labels or copy counts. Anonymous indexed thread fragments support local linkage, not independent donor frequencies.

`FlankEvidence` contains only left/right strings, reference/read intervals and custody hashes. It has a strict deserialization boundary. Central bases, neural likelihoods, truth, Q and multiplicity do not enter that type or the compatibility function. Central likelihoods enter only the separate objective decoder. Native, every existing hypothesis and impossible negative-infinity scores remain in the fixed catalogue.

Reference intervals are `[ref_start-100, ref_start-50)` and `[ref_end+50, ref_end+100)`. Extraction takes the read slice from the matched base at the left reference boundary through the matched base before the right boundary. It retains interior insertions/deletions. An insertion at either boundary, or a deletion covering either boundary base, is ambiguous and causes whole-window abstention. Reference skips overlapping a flank, hard clips, missing coverage, noncanonical bases, any flank over 64 bases, or more than 256 distinct prototypes also abstain. Native read intervals are converted back to original sequencing orientation for exclusion accounting. All planned central edit intervals of the parent are excluded in both coordinate systems. The original fixed-anchor panel conditions are retained.

The mapped SAM is resolved from the original planner's `--sam` receipt, not from the unaligned cohort-native SAM. Its SHA256 is `db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe`. Before extraction, all 64 original parent forward sequences and qualities match exactly between those two sources. Graph walks and windows match the qualified cohort pins. The reviewed full bridge completion SHA256 is `4e1284e3b9bf953dd9bb606f07740647394b7d4e53664f44d1dabac9ec347829`.

## Actual checkpoints

The first 32-query unit completed at 2026-10-23T16:48:35Z with exit zero. It retained 32/32 cases, with 18 eligible and one informative. Fourteen abstained. Three had boundary indels, eight failed the original panel anchor/core conditions, and three overlapped another planned edit. Raw receipt and GNU time output are in `logs/flank-prior/20261023T164834Z-checkpoint/`. Peak RSS was 18,916 KiB and elapsed time 0.05 seconds. These are resource observations for this one extraction unit, not a performance comparison. Seven Rust synthetic controls passed before the real input was read.

The separately retained all-451 unit completed at 16:49:09Z with exit zero. There were 275 eligible windows, 18 informative windows and 176 binary abstentions. This denominator includes existing graph/panel failures, including 84 anchor and nine core-bound failures. The plan artifact retains every per-window reason. Raw receipt is `logs/flank-prior/20261023T164909Z-eligibility/`. This diagnostic establishes coverage of the saved windows, not biological improvement.

The source freeze of the first checkpoint is under `logs/flank-prior/20261023T164834Z-checkpoint/frozen-source/flank_prior/`. The initial executable's hash is retained in its completion but that shared build path was later rebuilt. Final data units preserve their actual executable in each immutable raw log directory. The original successful checkpoint and its source are retained. The final immutable executable reproduces its evidence, prototypes, compatibility and exclusions exactly after ignoring only the strengthened per-window custody hash. The initial `window_sha256` held the full window-inventory hash. The final version pins each exact original window row instead. This metadata correction changes no extracted bases or score.

## Reproduction and controls

Run these through `uv` from this worktree. Every substantial build, test and data unit acquires the canonical stock host lock with a bounded wait.

```sh
uv run --no-sync python scripts/flank-prior.py build-test --wait-lock-seconds 30
uv run --no-sync python scripts/flank-prior.py checkpoint --wait-lock-seconds 30
uv run --no-sync python scripts/flank-prior.py eligibility --wait-lock-seconds 30
uv run --no-sync python scripts/flank-prior.py emit --plans results/flank-prior/DECLARED-eligibility/plans.jsonl --wait-lock-seconds 30
```

Synthetic controls cover linked-flank swapping, duplicates and order invariance, masked-center/copy-count noninputs, exact equal-flank binary parity over 363 score/native combinations, impossible scores, indel boundaries, reverse coordinates, private advantage greater than one and the known private-allele erasure counterexample at advantage 0.25. The latter is expected to erase under the frozen gates and prevents a false universal safety claim. The Python CLI tests reject changes to the frozen weights/gates and unregistered checkpoint sizes before accessing inputs.

The full emission budget is declared before execution as one CPU, 4 GiB address space, 600 seconds, 2 GiB outputs and a 30 GiB free-space floor. It consumes retained central scores and does not replay neural/tensor/catalogue producers. The output includes native identity, reference-free, binary-panel and continuous flank-conditioned full-parent SAMs. Independent sort/rank and independent forward-assembly splice checks compare against the production argmax and reverse-order replacement code. Native, reference-free and binary complete SEQ/Q must match the qualified expanded-H bridge arms. Q on changed bases is `!` and remains uncalibrated.

A build attempt at 16:52:26 failed on a Rust reference/type mismatch in the newly added parity check. The receipt is retained and the source correction changes only that reference. A later build and a queued emission each exhausted their bounded host-lock wait with exit 75 before any scientific producer started. No lock was bypassed. All failures remain under `logs/flank-prior/`.

## Biological limits and next gate

Call changes and finite private support do not prove accuracy or ALT preservation. The qualified batch observer currently admits original registered policies. A new continuous producer needs honest new admission and cannot borrow that contract by repointing frozen inputs. The coordinator owns that seam. Once emitted, the exact changed editable cores and full parent sequences go to the independent actual-score withheld-ALT challenge. Any biological observation reuse requires exact complete parent UUID/SEQ/Q identity, not matching counts. No promotion is claimed.


## Final frozen full-unit result

The final build receipt is `logs/flank-prior/20261023T165810Z-build-test/finish.json`. All five stages exited zero. They include nine Rust tests, two Python CLI contracts, the offline locked release build and strict all-target Clippy. Earlier strict Clippy found one nonminimal boolean expression. That failure is preserved in `logs/flank-prior/20261023T165652Z-build-test/`; the equivalent expression was simplified and all checks then passed.

The final immutable 32-query and full-451 units are `results/flank-prior/20261023T165826Z-checkpoint/` and `results/flank-prior/20261023T165826Z-eligibility/`. Both exited zero. All 275 flank-eligible windows belong to the 331 admitted scored windows. Of those 275, 105 have multiple distinct panel centers. Eighteen are informative under the fixed rule. One eligible multicenter case abstains because left-only and right-only preferred center sets disagree.

The full emission completed at 2026-10-23T16:58:38Z with exit zero. It retained all 451 windows, 331 scored windows, 120 original exclusions, 3,118,978 hypotheses and all 64 complete parents. Exact input scores were consumed without replay. The raw receipt is `logs/flank-prior/20261023T165833Z-emit/finish.json`. Its immutable executable, source snapshot, command, stdout attestation and GNU time record are in the same directory. The completion, raw receipt, executable and all outputs are bound by `results/flank-prior/20261023T165833Z-emit/execution-complete.json`.

| Arm | Edited windows | Difference from binary |
| --- | ---: | ---: |
| Native identity | 0 | n/a |
| Reference-free | 0 | n/a |
| Binary panel | 35 | 0 |
| Flank-conditioned | 35 | 0 |

Binary-panel and flank-conditioned SAMs are byte-identical, SHA256 `08b75908223366a86d1380dd004ebf2870839db0199081828111f809b2383493`. The summary SHA256 is `b43d6d52d5bccce2e3f9e992d80fdafb81ff0a672f317ce2c85ba2d02fe4ae9a`; the producer completion SHA256 is `c0d27c96c9f5e42a1eec0d0c7e24cd75f61b6e7d02aede6c8f0b5053f8fd953a`. The summary records exact complete-parent UUID/SEQ/Q parity with all three qualified original bridge arms. Independent ranking/gating, independent forward-assembly splicing, emitted readback and native identity all pass. The subsequent separate output audit script is retained at `logs/flank-prior/final-artifact-audit.py`; its actual zero-exit result verifies all 1,804 policy/window decision rows and the original/final compatibility equality.

The full emission used one CPU with 374,252 KiB peak RSS and 5.07 seconds elapsed under the declared 4 GiB/600-second budget. These are single-unit resource observations. They do not establish a speedup.

## Why informative flanks did not change calls

A separate Rust scan of the retained actual central scores is preserved in `logs/flank-prior/mechanism/`. It does not emit candidates or replay producers. Every maximum-neural-score panel center in all 18 informative windows already has the best flank distance, hence exact bonus one. Native bonuses are unchanged. Every downweighted center trails the binary winner's objective by 3.4211 to 21.9064. Consequently, all binary winners, objective margins and calls stay unchanged. All panel centers are present in the admitted expanded hypothesis set.

Distance separation across centers is one edit in 14 windows, two edits in three windows and four edits in one window. The lowest center bonus per window ranges from 0.0209915 to 0.4528324. The rule therefore distinguishes centers, but it downweights centers that are already noncompetitive under the actual central scores. Among the 18 windows, 14 keep native as the pre-gate winner, two emit the same edits as binary, and two reject the same nonnative winner on objective margin. None fail the neural-deficit gate. The two edit queries are 138 and 148; the two margin queries are 27 and 434.

This negative result is caused by the same argmax at the score-competitive centers. It is not caused by the 0.5 gates or missing panel-center catalogue coverage in these 18 windows. It does not rule out correct private hypotheses missing beyond this finite H, inaccurate flanks, or a different prospectively defined rule on other data. No weight or gate was changed in response.

The independent actual-score withheld-ALT owner received the strict evidence/prototype API and final plans. Challenge panels must remove every full-walk prototype carrying a withheld ALT, recompute compatibility and binary membership, and retain all original H and likelihoods. Ordinary-call identity does not qualify that challenge. The coordinator owns biological observer admission and any exact-identity reuse of existing observations. No mapping, truth observation, new acquisition, GPU job or biological promotion occurred in this unit.
