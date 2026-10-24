# Private-allele challenge independent review

The fixed withheld binary prior has a real insertion-erasure counterexample. Independent inspection of the final case, all 153 saved hypotheses and likelihood values, graph prototypes, baseline observation, and five decision rows confirms the local failure mechanism. Full independent pipeline qualification remains **not qualified** because the broader reader audit did not run. This is not a biological safety pass.

This review owns only this file and `logs/private-allele-review/`. It changes no experiment source, frozen targets, thresholds, stock controls, or acceptance checks. No child agents were used. No HG005 or historical validation artifacts were opened.

## Revision and scope

The worktree is `/home/jake/Projects/nanopore_basecaller-private`, branch `experiment/retrieval-private-alleles`, based at `ae423705147cd61e1290c426ec40b2e09a274780`. Experiment files were untracked when reviewed. A base commit alone therefore does not identify the implementation.

The retained `actual-v3-attachment` producer source has these SHA-256 pins.

| File | SHA-256 |
| --- | --- |
| `src/main.rs` | `0cec1c2632792fd73479a0feffde58ee9a1c2eed196c70adaa941aada9dfca15` |
| `src/challenge.rs` | `fc562b3672449595ab639b46445095cc2449392e02f11428643edeeeb0853fde` |
| `src/attach.rs` | `be57916c54da526b31b093c7f6b9624a70d65841b8b90aa75abb9c279dfa170f` |
| `src/flank_snapshot.rs` | `f6f5d7564a45ac287d0f4b6abd8c2c25bc4f66bb1f8421d0ace97c0ed3a52f06` |
| `scripts/private-allele-challenge.py` | `45d3a0e8abb2044700dc5fbbef4485421d4e71dd1269a759374feb687640e1e1` |
| `config/private-allele-dev-v1.json` | `d86d0ee557a6c4af7bc9e84b0aa0ab8933c9d43fc286c2380ee04699776c84ee` |

The subsequent source adds an `additional` entry point and routes the same builder over the new attached frames. Its reviewed source pins at 17:15:40 UTC are `f2a0b2606eae953bb4b7cbf416ffd28ab2168f54ee6478e3395681a2b01bc2ad` for `main.rs` and `c4ebe9b3cf57af06536a7130d3e679c3da70fbbf4473e3f447e6df981787e685` for `challenge.rs`. These are distinct from the source retained by the original diagnostic. The full source list is in [source-pins.txt](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/source-pins.txt). Later current-file pins are retained separately in [current-source-pins.txt](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/current-source-pins.txt).

The actual artifacts inspected as JSON or source were:

- `results/private-allele/actual-v2-flank/{complete.json,source-retention.json,output/report.json,output/inventory.json}`.
- `results/private-allele/actual-v3-attachment/{complete.json,admission.json,source-retention.json}` and attachment metadata.
- `results/private-allele/additional-graph-v1/complete.json` and the guarded extraction implementation.
- `results/private-allele/additional-original-score-v2/{complete.json,candidates/summary.json}`.
- Final `results/private-allele/additional-challenge-v1/{complete.json,source-retention.json,cases.jsonl,inference.jsonl,decisions.jsonl,report.json,challenge-build.json}` and the exact query-21 records from the new score and graph files.

The final additional challenge completion SHA-256 is `e9ddc984abf902cef59e2703265dc0b2b20868abe7a99500a0631b95a014b7e1`. Its retained `main.rs` and `challenge.rs` pins are the reviewed later pins above. Direct reads establish what the reports contain. The targeted query-21 comparison independently checks the numerical mechanism and its immediate input binding. It does not establish the complete upstream producer chain.

## Confirmed insertion loss

The failing observation is query `additional_original/21`, parent `447e365e-a659-4717-ae0a-d106e7ee5990`, variant `chr17:75510527:T:TC`. The original native observer row directly contains `alt`, with one ALT and one total observation. The attached target is original frozen target 28. It uses chunk 3, bases 199 through 241, and saved timesteps 362 through 431 in `p1061436_b14_s29.scores`. The forward-oriented native string has 42 bases. The exact reference has 41.

```text
Native     AACTTTCTGATACACAGAGTCCCCAGGCCCTCTGTGATGAGT
Reference  AACTTTCTGATACACAGAGTCCCAGGCCCTCTGTGATGAGT
Withheld   AACTTTCTGATACACAGAGTCCCAGGCCCTCTGTGATGAGT
```

The targeted jq comparison checks every sequence and likelihood pair in this 153-member H against the genuine score row. All 153 likelihoods are finite and nonzero. The score row's raw SHA-256 is `c05b434909b74ad4d4d103a7f51aa4d07d1cc09d55b6b272e0bad4df6eb7e106`, exactly matching the case's saved-row binding. The whole 545,683-byte score file hashes to the final completion's registered value `2e47b22dfd68715a2c19218cb6363460f88476f84740f8e930e42e61e64924ed`.

Native and reference both have ordinary panel support. Withholding removes native support and retains reference support. Sorting the objectives across all 153 members independently selects exact reference as the withheld argmax.

| Value | Native | Reference |
| --- | ---: | ---: |
| Saved likelihood | 232.28041915893718 | 231.84502924859206 |
| Ordinary bonus | 1 | 1 |
| Withheld bonus | 0 | 1 |
| Withheld objective | 232.28041915893718 | 232.84502924859206 |

The reference's neural delta is `-0.43538991034512264`. Its objective gain is `0.5646100896548774`. These clear the fixed maximum deficit 0.5 and minimum gain 0.5. Native wins under neutral and ordinary panel. Withheld panel emits reference and loses the inserted C. Exactly one row exists for each of the five arms for this case.

The reference interval's haplotype is `ATACACAGAGTCCCAGGCCCT`. Native contains `ATACACAGAGTCCCCAGGCCCT`, the exact truth ALT haplotype. An independent one-gap argument checks the projection. Removing native base 20, 21, 22, or 23 yields exact reference. Those are all four one-edit alignments, all inside the truth interval boundaries 9 and 30. Because the strings differ in length by one and have edit distance one, every optimal alignment is one of these insertions. Every optimal alignment therefore projects the same ALT interval. Emitted reference has the identity alignment and lacks the extra C. This avoids choosing one arbitrary placement inside the C repeat.

The actual graph record has four full walks. Their CIGARs are `343M`, `217M1I126M`, `343M`, and `217M1I126M`. Independent center slices match the four recorded prototype centers. Both full walks with the insertion are removed, including the one with copy count 1. The two retained centers spell reference. Recomputed SHA-256 hashes of all four full sequences match the case's four prototype hashes. Copy counts do not enter inference.

The case explicitly records `abstain-binary` with reason `new diagnostic frame has no qualified disjoint flank plans`. Its `withheld_flank` label therefore repeats the binary failure. It does not establish failure of continuous flank conditioning.

This actual withholding case is a negative variant-retention result. The neutral and ordinary arms provide matched retaining controls at identical H and saved scores. This supports rejecting an unconditional preservation claim for the fixed withheld binary prior. It does not estimate ordinary-panel error or population error rate.

Evidence is retained in [targeted-case21.json](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/targeted-case21.json), [targeted-projection21.json](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/targeted-projection21.json), [graph-center-projection21-v2.json](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/graph-center-projection21-v2.json), [graph-prototype-hashes21.txt](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/graph-prototype-hashes21.txt), and [targeted-input-pins.txt](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/targeted-input-pins.txt). The attached window, original baseline observation, raw saved score row, and graph query are copied into the same evidence directory.

## Source conclusions

The truth-aware builder and truth-free inference process are separate CLI modes. `InferenceCase` and `InferenceHypothesis` both deny unknown fields. Inference receives sequence, saved likelihood, ordinary and withheld membership, and numeric prior bonuses. It receives no genotype, variant identifier, truth haplotype, or event coordinates. Truth determines this diagnostic's cohort and intervention, so the challenge is deliberately truth-enriched. That does not make it an unbiased accuracy evaluation.

The builder retains every saved hypothesis and its likelihood, including impossible hypotheses represented by null likelihoods. Inference maps null to negative infinity. The expanded set must retain every original sequence, membership flag, and likelihood. `serde_json` enables `float_roundtrip`. Source inspection supports preservation, but the prepared bitwise comparison over the actual 334 MiB expanded decisions file remains unrun.

ALT projection compares a truth haplotype at its reference interval after orienting the sequence to the reference. It computes forward and reverse edit-distance tables. Both interval cuts must have exactly one coordinate among all optimal global alignments. Ambiguous repeat boundaries are excluded. The insertion and deletion overlap test removes shared VCF prefix and suffix before testing the edited core. Reverse sequence handling uses a canonical reverse complement. Existing source tests cover a shifted insertion, an ambiguous repeat boundary, reverse-complement involution, and rejection of a truth field. Those tests were inspected but were not rerun by this reviewer.

The panel is checked against the complete graph-walk center set. Every prototype whose center projects to ALT is removed. Thus duplicate full walks with the same ALT center are removed together. No ALT sequence is removed from the finite hypothesis set. Ordinary and withheld binary memberships are built separately. For eligible flank cases, compatibility is recomputed from the retained full prototypes after ablation. The ordinary recomputation must equal the frozen flank plan. The code does not assume that ordinary call identity proves unchanged withheld scores.

Binary inference calls the maintained `graph_frontier::decision::choose`. It maximizes the objective over all hypotheses before gating. Native wins an exact objective tie. Remaining non-native ties use lexical sequence order. The fixed weight is 1. The objective margin must be at least 0.5 and neural deficit at most 0.5. The copied flank chooser applies the same tie and gate rules. Its snapshot pin is the exact qualified flank source pin.

`attach.rs` calls the maintained `native::reconstruct` and `planner::attach`. Reconstruction requires exact native parent SEQ, Q, and MOVES, exact score token and slot metadata, and exact chunk stitching. Attachment requires 25 retained bases at both chunk edges, an exact stock slice, four preceding context bases, and a saved interval no longer than 256 timesteps. Target construction also requires exact, contiguous 10-base anchors, a bounded core length, and no overlap with an earlier admitted target. These are source findings, not a fresh replay or tensor validation.

The additional entry point reads the new 40-window frame and the successful `additional-original-score-v2` output. It deliberately supplies `abstain-binary` for every new frame because it lacks qualified disjoint flank evidence. Results from that lane must not be described as new continuous flank evidence.

## Findings and scientific limits

1. **A preservation claim fails.** The actual additional insertion case above changes baseline ALT to reference under the fixed withheld binary prior. Its immediate H, saved score row, prototype ablation, objective maximum, gate, and emitted sequence were independently checked. This is a scientific counterexample, not evidence that the implementation misapplies its declared prior. The complete original and expanded catalogue, tensor bytes, full registered receipt closure, and a fresh truth-field rejection remain unverified. There is no overall independent runtime PASS.

2. **The 38-core cohort has no edited-core safety exposure.** The inspected report contains 380 rows, which equals 76 cases times five arms. Per hypothesis set there are 35 SNVs, one insertion, and two deletions. One SNV is naturally absent from the panel. The remaining 34 SNVs, one insertion, and two deletions are engineered withholding cases. Every group reports zero edited cores and zero ALT losses. The inventory also reports zero baseline ALT observations at current panel, linear, flank, and union edited cores. Retaining ALT while making zero edits provides no local safety pass at edited cores.

3. **The 2,608-parent field is a membership universe.** `additional()` checks membership against the 2,608-parent development split, but enumerates candidate variants and observations from the existing 64-parent pilot observer. The new 60 targets therefore come from 64 observed parents. They are not 60 observations selected after observing 2,608 parents. All 18 selected parents already have saved exports.

4. **Keep all 60 targets in the new denominator.** The attachment metadata retains 40 attached targets and 20 excluded targets. The worker reported 15 SNVs, 14 insertions, and 11 deletions attached. The directly inspected score summary contains 31 scored windows, nine exclusions, and zero ordinary edits in every historic arm. The final challenge build contains 26 unambiguous cases and five further exclusions. The final report has one withheld binary insertion loss among eight engineered insertion cases. The 26-case class split is 12 SNVs, eight insertions, and six deletions. One SNV is naturally panel-absent. The new cohort stays separate from the original and expanded 38-core results. All 20 attachment exclusions, nine score exclusions, and five representation exclusions remain inside the 60-target accounting without replacement. Full per-target closure remains part of the pending larger audit.

5. **The standalone reporting API has a coverage gap in the reviewed producer revision.** In source `c4ebe9b3cf57af06536a7130d3e679c3da70fbbf4473e3f447e6df981787e685`, `report()` does not enforce unique case and arm pairs or require all five arms for every case. Duplicate case labels collapse into a map. A truncated decision input can therefore produce a partial report without a coverage error. This is a source-observed robustness risk. It is not evidence that the inspected 380-row artifact is incomplete. The prepared independent reader checks uniqueness and complete coverage. Any later integration fix is a separate revision outside this report's source verdict.

6. **No biological promotion follows.** This is a development-only truth-enriched stress test using saved signal scores. It does not establish population generalization, unbiased accuracy, Q calibration, full input processing, complete-reference behavior, throughput, validation acceptance, or live readiness. No HG005 selection was performed by this review.

## Commands and observed results

The source-only check ran successfully.

```sh
bash logs/private-allele-review/20261023T1713Z/source-check.sh
```

It exited 0 at 17:15:40 UTC. The exact commands are in [source-check.sh](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/source-check.sh). In particular:

```sh
git diff --exit-code ae423705147cd61e1290c426ec40b2e09a274780 -- tools/graph_prior tools/accuracy tools/graph_frontier/src/decision.rs scripts/benchmark.py
```

That command exited 0 and wrote an empty [maintained-controls.diff](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/maintained-controls.diff). It verifies unchanged tracked source in that scope relative to the identified base. It does not prove a native runtime, a compiled binary's source closure, or unchanged external inputs.

The original reader admission expired while the authorized producer retry held priority. The coordinator then admitted a separate reader unit capped at 25 seconds and 4 GiB, with a hard finish of 17:16:00 UTC. The reviewer attempted:

```sh
timeout --signal=TERM --kill-after=2s 25s /usr/bin/time -v -o logs/private-allele-review/20261023T1713Z/time.txt uv run --no-sync python logs/private-allele-review/20261023T1713Z/audit.py > logs/private-allele-review/20261023T1713Z/stdout 2> logs/private-allele-review/20261023T1713Z/stderr
```

It exited 1 in 0.03 seconds with 36,212 KiB peak RSS. The start-deadline assertion rejected the expired launch before opening the canonical lock or reading the actual artifact. The exact failure is retained in [stderr](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/stderr), with [time.txt](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/time.txt). This is a successful rejection of an expired reader launch. It is not a successful data audit or inference negative control. No second launch followed the rejection.

The prepared [audit.py](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/audit.py) would check completion-file pins and retained source hashes, preserve all H and compare likelihood bits to original and expanded score rows, recalculate all five objective decisions, require complete case and arm coverage, retain the 60-target attachment denominator, and run a truth-field rejection against the retained binary. It currently contains the expired admission dates. It has no passing result and is not a maintained acceptance check.

The later, separately authorized targeted file inspection used jq and SHA-256 only. It read the 545,683-byte new score file and bounded case, inference, decision, and graph records. It compared the actual 153-member case and its matched controls. It ran no native inference, tests, model, exporter, tensor replay, or large catalogue audit. The targeted comparisons exited 0. Their exact commands and output paths are retained in [targeted-commands.sh](/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-review/20261023T1713Z/targeted-commands.sh). Prove It Works determined the use of actual saved rows, matched controls, and an independent objective calculation instead of accepting the producer summary.

One initial graph-center jq filter had a syntax error. Its combined shell call returned 0 because the final `cat` succeeded, so that shell status is not a passing projection check. The error and empty first projection output are preserved. The corrected filter produced `graph-center-projection21-v2.json`, with both center and withholding comparisons true. See `graph-center-projection21.failed.txt`. No tool was broken.

The final producer's actual raw command, start, end, exit, and stderr were read directly. It compiled the new binary and ran additional construction, inference, and reporting under the canonical lock. It exited 0 with start 17:16:21 and end 17:16:31 UTC. That is one recorded second past the coordinator's 17:16:30 boundary. The deviation appears in the final completion and is preserved. It is not an on-time execution claim. The AS 4 GiB scoring failure and successful hard-memory-capped retry remain producer evidence. This reviewer did not rerun either native score producer.

## Next action

After the protected Harness slot ends at 18:23 UTC, obtain a fresh coordinator admission for one replay-free reader under the canonical host lock. Preserve the failed reader attempt unchanged. Run a fresh immutable evidence unit against the identified source pins and completed separate cohorts, including the sealed additional challenge. Recompute event projection and full-walk withholding on the remaining actual saved inputs, check the complete raw receipt and source binding, compare likelihood bits, and execute a meaningful truth-field rejection. Do not replay a model, exporter, tensor catalogue, or graph producer.
