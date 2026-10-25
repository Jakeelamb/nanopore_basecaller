# Development private-allele diagnostic

The real withheld-ALT challenge fails at an insertion. At fixed weight 1, objective margin 0.5, and maximum neural deficit 0.5, removing the ALT-carrying panel prototype changes a baseline-correct insertion to the reference sequence. This is a truth-enriched diagnostic counterexample, not a population error-rate estimate. No candidate is promoted.

The failing observation is `chr17:75510527:T:TC` on original source parent `447e365e-a659-4717-ae0a-d106e7ee5990`, new query 21. Native has the inserted C. Neutral and the ordinary panel retain it. The withheld panel contains the reference sequence and removes the prototype carrying the insertion. The exact reference hypothesis has saved likelihood 231.84502924859206 and neural delta -0.43538991034512264. Its objective gain becomes 0.5646100896548774, which passes both frozen gates. Every original hypothesis and likelihood remains available. Positive support alone does not prevent reference erasure.

```text
Native    AACTTTCTGATACACAGAGTCCCCAGGCCCTCTGTGATGAGT
Reference AACTTTCTGATACACAGAGTCCCAGGCCCTCTGTGATGAGT
Withheld  AACTTTCTGATACACAGAGTCCCAGGCCCTCTGTGATGAGT
```

## Actual denominators

The original 64 observed development parents contain 829 qualified baseline ALT parent-site observations. There are 740 SNVs, 50 insertions, and 39 deletions. Only 51 overlap planned editable cores. Of those, 38 were scored, comprising 35 SNVs, one insertion, and two deletions. The other 13 have no saved scored H and are coverage failures. Every scored baseline ALT case retains the exact native hypothesis with a finite original score. No truth-generated candidate was added.

The one historical edit has zero baseline ALT observations inside its editable core. The current compound panel and linear arms each edit 35 cores. Their union and the subsequent 35-edit flank arm also contain zero baseline ALT observations inside edited cores. Distant, unchanged parent ALTs do not qualify these denominators.

On the original 38 local ALT cores, the isolated builder ran both the original and expanded saved H. One SNV is naturally panel-absent. The engineered-withholding group has 34 SNVs, one insertion, and two deletions. All 38 remain ALT under neutral, ordinary panel, withheld panel, ordinary continuous flank, and withheld continuous flank. All five arms make zero edits on those 38 cores. This result supplies no edited-core safety evidence.

For those original cores, 33 have qualified flank evidence and five abstain to binary presence. There are 76 dataset-cases because each core is tested on two H sets. Exact flank compatibility is recomputed after removing every ALT-carrying prototype, including its new minimum and left/right disagreement rule. Twelve hypothesis bonus entries differ from binary presence across the 76 dataset-cases. Output identity was not used as evidence that the bonuses or ablation are identical.

## Frozen additional targets and actual new scores

The follow-on frame freezes 60 additional baseline ALT targets, 20 per class, outside all original planned cores. It selects 18 parents from the same 64 observed parents. All 18 belong to the frozen 2,608-parent development split. The 2,608 count is a membership universe, not a screened or observed cohort for this diagnostic. Selection is truth-informed and lexicographic within class. No target is replaced after eligibility, graph, score, or challenge outcomes are read.

| Stage | SNV | Insertion | Deletion | Total |
|---|---:|---:|---:|---:|
| Frozen targets | 20 | 20 | 20 | 60 |
| Attached existing tensors | 15 | 14 | 11 | 40 |
| Scored original H | See pinned decisions | See pinned decisions | See pinned decisions | 31 |
| Unambiguous local ALT challenge | 12 | 8 | 6 | 26 |

The 20 attachment exclusions are five retained-chunk edge failures, two overlaps with an earlier frozen target, four gapped anchors, two original parent SEQ/Q reconstruction failures, and seven core-size exclusions. All 18 requested parents occur in the old export; sixteen reconstruct successfully. No GPU, raw acquisition, model evaluation, tensor production, or old score replay was needed. The existing selected-parent tensors total 2,047,766,063 bytes and their metadata 4,019,207 bytes.

The new graph extraction loads the unchanged qualified GBZ once and queries only the 40 attached windows. The unchanged original scalar decoder then scores the new windows against their genuine retained tensor intervals. It scores 31 and excludes nine. The challenge excludes another five for ambiguous native or panel representation. These exclusions remain inside the original 60-target accounting. One of the 26 eligible cases is a naturally absent SNV. Engineered cases contain 11 SNVs, eight insertions, and six deletions. The engineered withheld binary panel loses one of the eight insertions. It has one edited ALT core and one ALT loss. Neutral and the ordinary panel lose none.

This new frame has no qualified disjoint native flank plans. Its `ordinary_flank` and `withheld_flank` output labels explicitly use binary abstention. Their shared insertion loss is not an evaluated continuous-conditioning result. No expanded-H catalogue was produced for these new windows. The original 3,118,978-hypothesis catalogue remains unchanged.

## Method and invariants

The planner, likelihood producer, and original native observer all name the same mapped SAM, SHA256 `db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe`. The cohort `native_sam` points to the unaligned call and is not substituted. Admission binds registered original producer receipts, normalized GIAB truth, source VCF, confident BED, reference, parent membership, raw POD5, model files, and exact retained tensors and moves.

The qualified native observer supplies baseline ALT labels. Hypothesis matching uses the full anchored haplotype and optimal edit-alignment boundaries, so shifted indels are assessed as sequences. Ambiguous boundary representations are excluded with reasons. It makes no phasing or donor-frequency inference.

The truth-aware builder and inference are separate processes. The inference input has native sequence, the entire unchanged H, unchanged finite or impossible likelihoods, recomputed ordinary/ablated membership, and frozen flank bonuses. Strict inference schemas reject genotype and other extra fields. Removing all prototypes carrying an ALT does not delete that ALT hypothesis. Native-first ties, lexicographic ties, and argmax-then-gate behavior reuse the existing decision source. The continuous scorer is a byte-identical snapshot of the qualified flank implementation, origin SHA256 `f6f5d7564a45ac287d0f4b6abd8c2c25bc4f66bb1f8421d0ace97c0ed3a52f06`.

Model the Domain determined the separate truth-label and inference structures. Prove It Works determined the real native observations, unchanged-score ablation, and concrete insertion counterexample.

## Commands and retained evidence

All substantial builds, tests, scans, and native computation used the canonical stock host lock. Raw receipts preserve argv, exit, clocks, stdout, stderr, and resources. No commits, pushes, merges, frozen gate changes, validation outcomes, or HG005 outcomes were used.

- The seven original Rust tests passed. They cover shifted-indel haplotype matching, ambiguous repeat boundaries, ablation without dropping H or changing likelihood bits, tie/gate behavior, reverse orientation, and strict inference input. The imported flank source tests also passed in the continuous extension. The three Python contracts passed, including a genuine inference erasure fixture, genotype-field rejection, and corrupted saved-score pin rejection.
- Original and expanded actual-score challenges completed with exits 0. Final source snapshots and inputs are retained in `results/private-allele/actual-v3-attachment/{complete.json,admission.json,source-retention.json,retained-sources/}`. The original continuous result is `output/report.json` there. The frozen target, exact move/tensor attachment, and export manifest are `output/{additional-windows.json,additional-attachment.json,followon-export.json}`.
- Graph extraction used `tools/private_allele_challenge/guarded_extract.py` and completed successfully. `results/private-allele/additional-graph-v1/complete.json` binds the native stage, qualified extractor, GBZ, queries, and every graph output. Its raw native recorder is `logs/20261023T170943Z-stock-07d562f3017b421f8e147a1c04e71e2a-cQqtGY`. The live monitor had a 48 GiB address-space cap, 16 GiB RSS cap, 30 GiB free floor, and absolute deadline. A fresh genuine monitor failure control stopped its owner with exit 73 and reaped its child before this run.
- The first new-window scoring attempt failed its 4 GiB address-space limit before scoring. Its allocation failure and peak RSS of 2,967,900 KiB remain in `results/private-allele/additional-original-score-v1/` and `logs/20261023T171103Z-stock-0504488174304fcfa220262cba562892-z33Wj5/`.
- The explicitly admitted retry used the same scorer and inputs with an 8 GiB address-space limit and hard cgroup `memory.max=4294967296`, `memory.swap.max=0`, printed and asserted before execution. It finished at 17:14:04.856338 UTC with exit 0. See `results/private-allele/additional-original-score-v2/complete.json` and `logs/20261023T171358Z-stock-49e2aa1f02864475bf3de847b2be51f6-Ytm8dT/`. Saved new decisions SHA256 is `2e47b22dfd68715a2c19218cb6363460f88476f84740f8e930e42e61e64924ed`.
- The final new-case builder, pure inference, and report commands are retained verbatim in `logs/20261023T171621Z-private-allele-additional-challenge-KvHhkB/command.sh`. They exit 0. `results/private-allele/additional-challenge-v1/report.json` contains the real insertion failure. This unit's recorder reports start 17:16:21 and end 17:16:31, one recorded second past the coordinator's 17:16:30 final boundary. The deviation is preserved. No further native work ran afterward.

Final additional-case code compiled and ran against genuine artifacts. No final broad test or formatting rerun occurred during the reserved Harness interval. Independent source review and artifact verification are recorded separately in `research/private-allele-review.md` when available. The counterexample is sufficient to reject an unconditional variant-preservation claim for the fixed withheld binary prior. It does not estimate ordinary-panel error, compare overall accuracy, establish a population bound, or show the conditioned treatment repairs the failure.


## Integration source revision

The integration branch imports the producer source before making a separate reporting correction. `report` now rejects duplicate or empty case identifiers, foreign cases, unregistered arms, duplicate case and arm pairs, and missing arms. Each case requires exactly one decision from each of `neutral`, `ordinary_panel`, `withheld_panel`, `ordinary_flank`, and `withheld_flank`. Rejection occurs before writing a report. Positive and corrupt-input CLI controls exercise this boundary.

This correction changes no inference, scoring, weights, gates, original result, or retained producer seal. The old binaries and successful result snapshots do not contain this correction. Integration formats only the new `main.rs`, `challenge.rs`, and `attach.rs` files. The byte-identical `flank_snapshot.rs` and inherited decision, graph, and accuracy sources remain unchanged. The pre-edit import manifest is retained locally at `logs/integration-source-copies.json` in the integration worktree. CPU CI builds this new revision and verifies its hermetic contracts; it does not replay or qualify the native scientific evidence.
