# Development experiments with retained signal scores

Three separate worktrees tested proposal coverage, flank conditioning and local private-allele safety on 23 October 2026. These are development diagnostics. No candidate is promoted. Stock controls and the original successful neural, tensor and compound-catalogue producers remain unchanged.

The integration branch is `experiment/retrieval-development`, based on `ae423705147cd61e1290c426ec40b2e09a274780`. It depends on the unmerged [compound bridge PR](https://github.com/Jakeelamb/nanopore_basecaller/pull/2). Each source unit and its actual outputs retain separate identities. This report describes observed outcomes; it is not a retrospective preregistration.

## Findings

| Development question | Actual result | Interpretation |
| --- | --- | --- |
| Does expanded H change the frozen policy outputs? | 3,071,748 additional hypotheses; four changed argmaxes per policy; zero emitted changes | Added proposals do not improve the outputs under these frozen rules. |
| Do unchanged flanks distinguish graph centers? | 275 eligible windows, 105 multicenter, 18 informative; zero winner, margin or output changes | The neural-best panel centers already receive the best flank bonus. |
| Do original scored ALT cores test local edit safety? | 38 ALT observations; zero edits under ordinary or withheld binary and continuous priors | Zero loss here has zero edited-core exposure. |
| Can additional retained-signal cores expose a private-allele failure? | 60 frozen targets, 40 attached, 31 scored, 26 unambiguous challenge cases; one insertion erased after panel withholding | The frozen binary prior has a real local counterexample, now verified through the retained-artifact audit. |

All additional targets were screened within the original 64 observed development parents. The 2,608-parent split is a membership universe, not the number of parents screened for this diagnostic. All 18 selected source parents already had retained full-parent signal exports. No new neural inference, GPU export, raw acquisition, validation exploration or HG005 selection was required.

## Proposal coverage and flank mechanism

The [coverage diagnostic](hypothesis-rank-diagnostic.md) preserves all 47,230 original hypotheses and their exact f64 likelihood bits. Expansion adds only graph-absent hypotheses. The four changed maxima improve by less than the frozen objective margin of 0.5 and do not change any complete output. An [independent review](hypothesis-rank-review.md) reconstructs the actual decisions and all 64 complete parent SEQ/Q maps, with comparison against 614 existing source artifacts. This is a finite-H result, not proof of proposal exhaustion.

The [flank experiment](flank-prior-experiment.md) retains all 451 windows, 331 scored windows, 120 original exclusions and 3,118,978 hypotheses. Its frozen weight is one, with objective margin 0.5 and maximum neural deficit 0.5. Binary and flank each edit 35 windows and produce byte-identical complete SAMs. Native and matched reference-free controls have zero edits. Every neural-best panel center in the 18 informative windows already has the minimum flank distance and bonus one. The strongest downweighted alternative in each window trails the binary winner by 3.4211 to 21.9064 objective units. The extra flank evidence therefore acts on alternatives that were already noncompetitive.

The [flank review](flank-prior-review.md) independently reconstructs native extraction, graph prototypes, decisions and complete parents for the identified immutable plans and emission. It does not qualify arbitrary self-consistent plan directories. The build freeze omits historical Python test-source custody, and abstention reasons were not independently replayed individually. Complete call identity permits reuse of deterministic biological observations only when their exact mapper, reference, scorer, cohort and input provenance also qualify. It does not create a new accuracy result.

## Local private-allele challenge

Truth-aware construction identifies a supported local ALT and removes every ALT-carrying panel prototype. Inference receives all unchanged candidate strings and scores, with recomputed panel membership or flank bonuses, and no truth fields. Naturally absent and deliberately withheld alleles remain separate strata. The original 38 observations comprise 35 SNVs, one insertion and two deletions. Both original and expanded H retain them, but no core is edited. The ordinary panel, linear and flank edited-core union also contains zero baseline ALT observations.

The additional diagnostic fixes 20 targets per class without replacing exclusions. Twenty fail signal attachment or core eligibility. Nine more fail graph/native scoring eligibility, and five have ambiguous local event projection or panel representation. The remaining 26 cases contain 12 SNVs, eight insertions and six deletions. One SNV is naturally panel-absent; the others are engineered withholding cases. These enriched denominators do not estimate an unbiased error rate or satisfy the promotion support requirements.

The producer reports an insertion loss at `chr17:75510527 T>TC`, case `additional_original/21`, parent `447e365e-a659-4717-ae0a-d106e7ee5990`. Native and ordinary-panel calls retain the insertion. After withholding ALT-carrying prototypes, the reference sequence wins despite having a lower neural likelihood. The native likelihood is `232.28041915893718`; the winning reference likelihood is `231.84502924859206`. A prior bonus of one overcomes the neural deficit `0.43538991034512264`, leaving objective gain `0.5646100896548774`. Both frozen 0.5 gates permit the edit. The emitted sequence deletes the observed inserted base.

The additional frame has no qualified extracted flank evidence. Its explicitly binary fallback shares this loss. It must not be reported as an empirical failure of the tested continuous flank conditioner. The completed [retained-artifact audit](private-allele-full-audit.md) checks 384,952 hypothesis/likelihood comparisons, 636 registered DGS1 tensors, 606 full walks and all 510 unique decision rows. It independently reconstructs the event projections and all 60 target outcomes. The 102 case records include original and expanded H over the same 38 cores; they are not 102 independent biological observations. Some large-file hashes are explicitly reused from earlier closure with current size/mtime checks.

## Execution and limits

The original score retry failed under a 4 GiB address-space limit before scoring. A separately admitted retry used 8 GiB address space with a kernel-enforced 4 GiB memory limit and no swap. The scorer, targets and scientific gates stayed unchanged; the successful graph output was reused. This was an explicit resource-admission revision, not a biological gate change.

The final additional challenge receipt records start `17:16:21Z`, end `17:16:31Z` and exit zero. Its 17:16:30 boundary was exceeded by one recorded second. Preserve that deviation. It ended before the then-reserved Harness2 interval at 17:18. Harness2 later released its unused reservation. A separate reader grant began at `18:00:19.722672Z` and released at `18:03:14.435Z`, before its own hard end.

The reader's six data phases pass, but the main command remains exit one because a retained executable copy lacked execute permission. Its first tensor registration lookup also omitted the original native-call manifest. A separate exit-zero supplement uses an exact-hash executable copy for both truth-field rejection controls and closes registration against that manifest. The original failure and output remain unchanged. The [report and archived verifier source](private-allele-full-audit.md) identify this composite scope, exact commands, retained failures and build/neural limits. No producer was replayed to repair observations.

The actual additional evidence remains outside Git in `/home/jake/Projects/nanopore_basecaller-private/results/private-allele/`. Successful graph extraction is `additional-graph-v1`; successful native scoring is `additional-original-score-v2`; the fixed additional challenge is `additional-challenge-v1`. Failed address-space admission and all command receipts remain retained. No comparative speed claim follows from these resource clocks.

The scientific next step is to test a separately declared intervention that addresses the preserved private-allele failure mechanism. Enlarging H or lowering a margin is not justified by these results alone. Any proposed accuracy gain must also meet the unchanged exposure, paired error, technical uncertainty and variant-retention gates. Exposed historical validation and HG005 cannot supply outcome-blind candidate confirmation.
