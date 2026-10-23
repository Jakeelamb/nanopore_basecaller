# Retained private-allele artifact audit

The retained-data checks pass within the scope below. An unconditional ALT-preservation claim for the fixed withheld binary prior fails on one actual insertion core. This verifies the local counterexample and its saved-artifact chain. It does not establish a general accuracy or speed improvement, neural-score correctness, or biological safety.

This report follows the earlier [targeted review](private-allele-review.md), which remains unchanged historical evidence. That review's unexecuted broader audit was superseded by a separately coordinated reader. No scientific producer was replayed. Stock controls, targets, hypotheses, scores, inference rules and thresholds stayed unchanged.

## Verified scope

| Check | Retained observation |
| --- | --- |
| Raw execution chain | 15 recorder sets checked against argv, cwd, UTC clocks, exit, stdout bindings and genuine prerequisites; failed scoring attempt and successful retry retained. |
| Native tensors | 636 complete DGS1 headers and 268 saved windows associated with 23 relevant parents. Twenty-two parents reconstruct exact SEQ, Q and MOVES. One previously failed parent stays excluded with its two target exclusions. |
| Original registration | All 636 whole-file DGS1 hashes match the original registered native-call export manifest. The supplement freshly checks 659 metadata and parent pins. |
| Hypotheses and scores | 384,952 sequence/likelihood comparisons are bit-exact, including null impossible scores. Original H remains inside expanded H. |
| Withholding and projection | 606 complete graph-walk records checked, including duplicate ALT walks; every ALT-carrying full prototype is removed without deleting ALT hypotheses. All optimal boundary cuts are independently projected. |
| Flanks | 66 qualified case records independently checked for disjoint extraction, full-walk prototypes and recomputed compatibility. New frames without qualified flank plans remain binary fallbacks. |
| Decisions and reports | 510 unique rows cover exactly five registered arms for each of 102 case records. Complete-H argmaxes, ties, fixed 0.5 margin and deficit gates, events and group counts agree. Missing and duplicate decision controls reject. |
| Target accounting | All 60 additional targets are retained: 26 included, 20 attachment exclusions, nine score exclusions and five representation/projection exclusions. No replacements. |
| Truth-free inference | The actual retained binary rejects a top-level `genotype` and a hypothesis-level `truth_alt`, with unknown-field errors and zero decision bytes. |

The 102 case records comprise 38 original-H cases, 38 expanded-H cases over the same original cores, and 26 additional cases. They are not 102 independent biological observations. The additional targets were selected from 18 of the original 64 observed parents; 2,608 denotes split membership only. The final 26 cases comprise 12 SNVs, eight insertions and six deletions, including one naturally panel-absent SNV. Truth-enriched selection supports a counterexample rather than an unbiased error-rate estimate.

The main reader made 2,940 pin comparisons. It newly hashed 610,431,977 bytes and reused 572 earlier successful SHA checks after current size and modification-time checks. The earlier closure read approximately 12 GB. This is documented operational reuse, not fresh content hashing of every large resource in the final unit. The native registration supplement compares already computed whole-tensor hashes to their original manifest; it does not rehash tensor payloads. The nine score exclusions remain bound to genuine producer outputs rather than independently rescored.

## Confirmed failure

Case `additional_original/21`, parent `447e365e-a659-4717-ae0a-d106e7ee5990`, is the supported insertion `chr17:75510527 T>TC`. Native and ordinary-panel calls retain it. After both ALT-carrying full prototypes are withheld, exact reference wins despite its lower neural likelihood.

| Quantity | Value |
| --- | ---: |
| Native saved likelihood | 232.28041915893718 |
| Reference saved likelihood | 231.84502924859206 |
| Reference neural delta | -0.43538991034512264 |
| Reference prior bonus | 1 |
| Objective gain over native | 0.5646100896548774 |

Both frozen gates permit the edit, deleting the supported inserted C. All 153 hypotheses and saved likelihood bits in this case are unchanged. There is one lost insertion observation among the eight additional insertion cases. The two withheld report rows represent this same core and same binary policy. The flank-labelled arm has no qualified disjoint flank plan and explicitly falls back to binary. It is not an observed continuous-flank failure. Neither this enriched fraction nor the zero-edit original cohort estimates ordinary-panel or whole-genome safety.

## Commands and observation repairs

The exact command receipts remain beneath `/home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5/`. The [executed methods source](../tools/private_allele_audit/retained-20261023/README.md) is archived byte for byte in Git. The original worktree and its UV environment supplied these commands; the archive alone is not their input dataset or an active grant.

```sh
timeout --signal=TERM --kill-after=1s 295s /usr/bin/time -v -o /home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5/time.txt uv run --no-sync python /home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5/audit.py /home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5
timeout --signal=TERM --kill-after=1s 35s /usr/bin/time -v -o /home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5/supplement-time.txt uv run --no-sync python /home/jake/Projects/nanopore_basecaller-private/logs/private-allele-full-audit/20261023T1740Z/attempt-5/supplement.py
```

The main command ran from `18:00:19.722672` to `18:00:24.938914` UTC and exited **1**. Its six data phases passed, then the truth-rejection launch raised `PermissionError` on the retained executable, mode 0644. The supplement ran from `18:03:14.366810` to `18:03:14.434943` UTC and exited **0**. It made a byte-identical audit-owned executable copy, set only that copy's execute bit, and passed both actual rejection controls. The original binary is unchanged. The supplement also opens the originally omitted native-call manifest and verifies the registration chain. The original reader output's zero registration count remains preserved alongside the correction.

Both commands used the canonical host lock, one CPU, 4 GiB address-space limits, a 30 GiB disk floor and the admitted output budget, before the fresh `18:05:19.722672` UTC hard end. RSS limits were set as well; they are not a Linux kernel cgroup memory guarantee. Terminal release was sent to Harness2 and Go at `18:03:14.435` UTC. No later data audit or build ran in this unit.

Earlier reader attempts remain exit 1 with their exact source. One assumed an unsupported one-second raw clock envelope; another assumed the wrong native alignment input and argv position. Source review corrected those reader assumptions and checked genuine and negative fixtures before the final launch. Unexecuted candidates 3 and 4 are distinct from executed attempt 5. No scientific output was regenerated to repair the observations.

The successful scientific challenge's original raw end remains `17:16:31 UTC`, one recorded second beyond its `17:16:30` boundary. The allocation-failed score command remains exit 134. Neither deviation is converted to a policy pass.

## Evidence identities

Raw results, binary and recorder files stay outside Git. The original worktree is `/home/jake/Projects/nanopore_basecaller-private`, branch `experiment/retrieval-private-alleles`, based on `ae423705147cd61e1290c426ec40b2e09a274780`. Its experiment files were untracked, so that base commit alone does not identify the executed implementation.

| Evidence | SHA-256 |
| --- | --- |
| Original full report, `research/private-allele-full-audit.md` in that worktree | `62496737818fa0f614ee8b86b217f641b4346430623552c26a08e7e590f38efd` |
| Final composite `attempt-5/qualification.json` | `fb3f8f0f4a3a36d4684a9eab2431fdb2d7fb1e29d89e305718398488d1507c81` |
| Main `attempt-5/result.json` | `deb1fe813020e7b909dbc1843514299c6b1f4537357812ddb14640722c02ae0d` |
| `attempt-5/supplement-result.json` | `6cf838c7c87b278f6bde8dbee49ae55c19cf8a9574d76beec278af46b59bab2b` |
| Reader `audit.py` | `acacc13eb41d03528e064857f1c8de6fffb5d0b92cd93ec23646e89cf13f77ca` |
| Independent helper `project.rs` | `9a502785800aff2fcccdd1b17249e095aed3169bc306c23e51552dadf9ea73d4` |
| Observation `supplement.py` | `aab7c96fdc22f05a723ecb090ade156e6a13ece45e2fccd5d61d91669e3fea0b` |
| Auditor source review, `logs/private-allele-full-audit/source-review/review.md` | `0723fa2a72d63e50ad37f0ac66ca93aa4fca5c31e56134ca1a422bf915fb37bf` |
| Genuine/negative fixture result beside that review | `5e0ac27005a974c45f9c5a31f78720a8832fe3fdc2556278f3c3d3a4332f55fa` |
| Final scientific `results/private-allele/additional-challenge-v1/complete.json` | `e9ddc984abf902cef59e2703265dc0b2b20868abe7a99500a0631b95a014b7e1` |
| Retained inference executable | `daf48610c43a757df605ba97f93da998e35535793bb0077ece5318572333118f` |

The original full report details all five scientific completion pins, registered pilot and native-call manifest pins, 35 qualification proofs, source drift, exclusion reasons and command receipts. The earlier targeted review and stock-source comparison remain unchanged. The later integration report-coverage guard is a separate source revision and is not attributed to the original binary.

Prove It Works required actual saved rows, complete decision coverage, independent projection and genuine parser rejection. Source and artifact custody remain separate from a reproducible source-to-binary build or independent proof of every native CRF likelihood. No native GPU rerun, full-input benchmark, Q calibration, population validation, speed comparison, or candidate promotion follows. Exposed historical validation and HG005 remain unsuitable for outcome-blind candidate confirmation.
