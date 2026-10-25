# Independent review of the frozen flank emitter

Verdict on 23 October 2026. **PASS for the identified engineering artifact. Biological benefit and private-allele safety remain unqualified.** No blocking implementation defect was found in the inspected source or independently reconstructed outputs. This is a same-family review, not a cross-family panel.

The reviewed worktree is `/home/jake/Projects/nanopore_basecaller-flank`, branch `experiment/retrieval-flank-pilot`, at base HEAD `ae423705147cd61e1290c426ec40b2e09a274780` plus the uncommitted files identified below. HEAD alone does not identify this implementation. Stock files and acceptance checks were not edited by this reviewer.

## Exact artifact

| Item | SHA256 |
| --- | --- |
| `tools/flank_prior/src/lib.rs` | `f6f5d7564a45ac287d0f4b6abd8c2c25bc4f66bb1f8421d0ace97c0ed3a52f06` |
| `tools/flank_prior/src/main.rs` | `1a29abbd0f8c5bc44f22f28cdef053fbeed9671af89d02423fae0329319a30fb` |
| `config/flank-prior-dev-v1.json` | `b53ae10ca5237030177b40df7db0e784395cf3c3b7d02f115713cebed370d22a` |
| `logs/flank-prior/20261023T165833Z-emit/flank-prior` | `b0f517b8f49db29b26661e5e5b8f3de994e1ce00f11231c64427509e7582ac6b` |
| `results/flank-prior/20261023T165833Z-emit/complete.json` | `c0d27c96c9f5e42a1eec0d0c7e24cd75f61b6e7d02aede6c8f0b5053f8fd953a` |
| Same directory, `execution-complete.json` | `c7966850b2036c6dd9f839cf26f3a71988cc99b6c069a25429f1637ec64b2c58` |
| Same directory, `summary.json` | `b43d6d52d5bccce2e3f9e992d80fdafb81ff0a672f317ce2c85ba2d02fe4ae9a` |
| Same directory, `flank-conditioned.sam` and `binary-panel.sam` | `08b75908223366a86d1380dd004ebf2870839db0199081828111f809b2383493` |

The final diagnostic units are `results/flank-prior/20261023T165826Z-checkpoint/` and `20261023T165826Z-eligibility/`. The emission consumes the latter's `plans.jsonl`, SHA256 `2d0ed8ec93974799d47c14474b4264b8f969999d60368518cbef7eb1382558e8`. The retained score input is the genuine compound transform's `decisions.jsonl`, SHA256 `2cd445b430f8538660495bccb3995bdd7484c7e4d5d22a6f6a4838c39b04ceaf`. No neural, tensor, catalogue, or scalar producer was replayed.

## Independently executed checks

From the flank worktree, the exact top-level command was:

```sh
uv run --no-sync python logs/flank-review/run_audit.py
```

Its recorded child command acquired `/home/jake/Projects/nanopore_basecaller/results/stock/host.lock` through `flock -E 75 -w 10`, then ran `timeout 120s /usr/bin/time -v ... uv run --no-sync python logs/flank-review/audit_flank.py ...`. It constrained the reader to one CPU and 4 GiB address space. The audit completed with exit 0 at `2026-10-23T17:02:23.347008+00:00`. Exact argv, clock, exit, raw output, and GNU time remain in `logs/flank-review/20261023T170217Z/`.

The reviewer independently performed these comparisons against the actual files:

- Rehashed 52 unique pins, including final diagnostic and emission output seals, actual immutable executables, raw stdout/stderr, completion files, and the prior admitted candidate SAMs. The producer stdout binds each final completion and summary. Each final data receipt reports exit 0 under the canonical lock. Embedded compiled source hashes match both the immutable source snapshots and current source files.
- Parsed both mapped and original native SAMs and compared all 64 forward UUID/SEQ/Q records. They agree exactly. Rebuilt all 275 eligible native flank pairs using a separate reference-position-to-read-position alignment map, including 136 reverse windows. Verified each recorded read/reference interval and its exclusion from every planned edit of that parent.
- Re-extracted all 825 retained prototypes from their hashed full source walk and CIGAR. Recomputed Levenshtein distances, best exemplars, left/right disagreement, bonuses, and informative flags. Floating bonus comparisons allow at most `5e-16` absolute difference. Recorded decisions and margins subsequently match exactly.
- Checked all 331 scored windows, 120 exclusions, and 3,118,978 retained hypotheses. Recomputed all four arms' native-first then lexical argmax, objective margin, neural-deficit gate, pre-gate winner, and actual source-row hashes. This uses the original supplied scores, including impossible values, without filtering H.
- Independently assembled each complete parent from unchanged original sequence and quality plus edits in forward sequencing coordinates. All four actual emitted SAMs match for all 64 parents. The native and reference-free arms have zero edits. Binary and flank each have 35 edited windows.
- Compared each complete UUID/SEQ/Q map with the actual prior admitted artifact, rather than comparing counts. Native and reference-free equal `seq-q-a2f7cdb61c14d901095f1c65dd5ed8b716bd12546feb993d9959813f411f54a6.sam`. Both binary and flank equal `seq-q-61354b3522e0c97bd8cc22bf7803672992e03acfe41066691f40844ba8f1d283.sam`. SAM headers differ, so this identity claim concerns the full 64-parent UUID/SEQ/Q maps.
- Reran the actual immutable CLI with weight changed to 7. It exits 1 with `flank-prior: frozen protocol` and creates no output directory. The evidence checker also rejects an intentionally corrupted SAM checksum. These controls demonstrate detection of a frozen-rule violation and a corrupted artifact pin.

The audit result is `logs/flank-review/20261023T170217Z/result.json`, SHA256 `95e3ae19b69bb8386853079196b3b41825444b608916c65936d42aff72415ef1`. Its checked-pin inventory is `pins.json`, SHA256 `8c98b3de298a0c11af82daa76b0a95bfeaae73eff7f53a9b538c8c42dd5920cd`. The frozen audit reader's SHA256 is `19dfa079b98d2828f948989ae9a595a0f1f87cf6a1180c5c478ffa9a15a3dd43`.

The separate secondary audit ran:

```sh
uv run --no-sync python logs/flank-review/run_coverage.py
uv run --no-sync python logs/flank-review/run_coverage_recovery.py
```

The native coverage diagnostic passes. The first reviewer projection exits 1 because its rejection-message assertion expected `pin mismatch`; the actual correct rejection says `size/hash mismatch`. The failed reader and all raw output remain in `logs/flank-review/20261023T170556Z-coverage/`. Only the reviewer-owned message assertion was corrected. The recovery reuses the successful native diagnostic artifacts and exits 0 at `17:07:24.754451+00:00`. It independently checks the mechanism below while scanning the same retained score rows. No implementation or maintained acceptance check changed. Its report is `logs/flank-review/20261023T170718Z-coverage/review-result.json`, SHA256 `416547fe7e6f52a81a3457104e3341a060ca9664f0bf91fc21fccdc8b6c25c2d`.

## Source findings and scientific result

The source implements the frozen reference intervals with 50-base guards. Native and graph flank strings stay in reference orientation. Only the center is reverse-complemented for central neural scoring. Extraction retains interior indels and rejects insertions at either boundary, deletions covering a boundary base, reference skips through a flank, hard clipping, missing coverage, and noncanonical bases. Over-cap extraction abstains instead of truncating. The runtime reconstruction verifies the accepted cases, while source review and retained synthetic controls cover the rejection convention.

`FlankEvidence` excludes native central sequence, central likelihoods, truth, Q, donor labels, and copy counts. Its deserializer rejects unknown fields. The compatibility function uses only the two flank strings and fixed prototypes. Center likelihoods enter the separate objective once. Deduplication and minimum distance prevent multiplicity weighting. The scorer assigns graph-absent hypotheses zero bonus, keeps impossible scores impossible, gives best ties exactly one, and uses binary presence after extraction or left/right disagreement abstention. The emitter checks its panel centers against original H membership.

No blocking engineering defect was found for this exact artifact. Two limitations affect the breadth of that verdict:

- The emitter does not independently reopen the diagnostic execution seal or re-extract the plans. Its general CLI admission is weaker than the independent checks performed here. This verdict admits only the identified plans and emission, not arbitrary self-consistent plan directories.
- The build freeze does not include `tests/test_flank_prior.py`. The retained raw receipt shows two Python tests passing, but their historical source custody is weaker than the Rust tests embedded in the pinned crate source. The actual immutable CLI negative control above was independently rerun. The 176 abstention reasons were source-reviewed and counted, but not independently replayed one by one. Exhaustive malformed-CIGAR and arbitrary-prototype rejection remain unproven.

The actual retained result is a null effect relative to binary presence. There are 18 informative admitted windows, yet none changes the pre-gate winner, objective margin, emitted call, or complete parent output. In every informative window, the best neural panel center already receives the maximum flank bonus of one. Their gates are 14 native, two edit, and two objective-margin rejection. For each window, even its strongest downweighted center is 3.4211225675 to 21.9064313085 objective units below the binary winner. All individual downweighted centers span gaps up to 26.6521944553. These are distinct denominator choices, not conflicting measurements.

The complete output identity supports reuse of an existing deterministic downstream measurement only after the coordinator verifies that observation's exact input, mapper, reference, scorer, and cohort provenance. This review does not inspect or qualify biological endpoint values.

## Unproven claims and next step

Disjoint called-base intervals do not make signal evidence independent. Native mapping, mismatch nomination, and recurrent neural context can all select or correlate these observations. A positive prior over finite H establishes support only. The retained synthetic counterexample explicitly permits a wrong panel allele to erase a private native allele with neural advantage 0.25. No universal ALT-retention claim follows.

This review does not establish neural likelihood correctness, Q calibration, biological accuracy, variant preservation, speed improvement, donor/population generalization, or outcome-unseen confirmation. The 64 development parents and 18 informative windows provide no genome-wide safety guarantee. Validation and HG005 did not enter this review's selection or diagnostic inputs. The original first checkpoint executable was subsequently rebuilt and is not independently recoverable; the final immutable units above are the admitted revision.

Reuse qualified existing observations for the identical panel/flank output. Keep any actual-score withheld-ALT challenge separate, with its own truth-blind inference input and central-edit exposure denominators. Any new context, likelihood, or gate experiment requires a new predeclared development intervention and exact artifact review. The unchanged current outputs cannot demonstrate a flank benefit.

Prove It Works required direct reconstruction of the actual artifact. The no-comments subagent workflow was not run because the assigned review prohibits further delegation and implementation edits. No external or broken tool prevented the completed checks. All native work in this review ended before the 17:15 UTC cutoff.
