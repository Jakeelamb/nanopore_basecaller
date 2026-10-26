# Uncertainty-targeted reference feedback results

Reference-guided decoding reduced measured errors modestly on this fixed HG002 development cohort. The selected and final-rerank arms pass the predeclared point-error and technical-uncertainty gates against native calls. Partial-search feedback produced exactly the same complete calls as final reranking. This experiment does not implement continuous localization of a growing read, establish biological promotion, or demonstrate a speedup.

All 512 frozen windows and all 64 original parents are accounted for. All 15 logical arm/baseline comparisons finished. Three byte-distinct complete SAMs required three mappings and three allele observations. Six distinct scientific comparison tuples were executed; nine exact aliases reused their accepted outputs with zero new native commands. Failed attempts remain separate.

## Accuracy and controls

These counts use the unchanged invariant 100/500 masks and paired matched reference domains. Errors are substitutions plus insertions plus deletions. The error-fraction denominator is matches plus errors. Reference exposure excludes inserted columns, so the two denominators differ legitimately after indel edits.

| Complete-read arm | Errors100 / columns | Relative error reduction vs native | Errors500 / columns | Relative error reduction vs native |
|---|---:|---:|---:|---:|
| Native | 8785 / 865579 | Baseline | 3939 / 439381 | Baseline |
| Disabled edit | 8785 / 865579 | 0% | 3939 / 439381 | 0% |
| Reference-free | 8764 / 865554 | 0.236162% | 3925 / 439374 | 0.353833% |
| Union-NN diagnostic | Same as reference-free | 0.236162% | Same as reference-free | 0.353833% |
| Final rerank | 8672 / 865524 | 1.280011% | 3887 / 439364 | 1.316314% |
| Partial-search selected | Same as final rerank | 1.280011% | Same as final rerank | 1.316314% |

The selected arm has 113 and 52 fewer errors than native in the two domains. Its error fraction changes from 1.014928% to 1.001936% and from 0.896488% to 0.884688%. Those are absolute improvements of 0.012991 and 0.011801 percentage points, not1.28/1.32 percentage points of accuracy.

The selected/native point reduction exceeds 1% in both domains. The parent and genomic 1 Mb block technical 95% upper bounds on candidate-minus-native error fraction are strictly negative in both domains. These are technical resamples of this observed flowcell, not independent biological replications or a confidence guarantee of at least1% improvement. The same statement holds for the byte-identical final-rerank arm. Reference-free/native fails the 1% threshold and both technical-upper-bound checks.

The independently scored selected/reference-free comparison gives1.046319% and 0.965899% relative reductions. Both technical-upper-bound checks favor selected, but the 500 point result is below 1%; this comparison does not pass the two-domain 1% gate. Context versus union-NN is diagnostic rather than a pure matched-policy attribution because the original context gates retain the escape-H baseline.

All 64 parents remain present, including zero-exposure rows. Masks 100/500 have53/50 positive-exposure parents and 11/14 zero-exposure parents. Common reference exposures are863283/438366 bases. Independent counter sums conserve the 43 target and 21 nontarget strata. Nontarget21 component counts are unchanged in selected/native in both domains. Masks and duplicated molecules are not independent replications. HG005 remained sealed.

## What the feedback changed

The genuine query 1 mechanism canary found86 conditioned-only candidate strings and 102 changed nonterminal retained sets over116 steps, starting at step14. Its selected call stayed reference-free after the signal-deficit fallback. This proves partial-search influence for that query, not a full-cohort novelty census.

Across the full512 cohort, selected and final-rerank complete SAM bytes are identical. Union-NN diagnostic and reference-free bytes are also identical. Therefore partial-search feedback supplies no additional final-call benefit beyond final reranking here. Reference-free edits78 windows in21 parents; final-rerank/selected edits102 windows in23 parents. Edit counts alone do not measure correctness. Changed bases retain the declared uncalibrated `!` quality.

The fixed cohort has 320 usable contexts and 192 explicit missing contexts. The missing cases comprise191 native/reference guard mismatches and one guarded-center bound case, query 367. Each still has a genuine reference-free decode. No exclusion was refilled. These constraints are an observed limitation, not permission to relax this experiment's gates.

The frozen objective is `J = L - 0.5 * minimum_panel_edit_distance`, with maximum neural deficit0.5 and minimum objective improvement0.5. In exact arithmetic, a one-edit candidate with lower neural likelihood cannot clear that margin; at least two edits of prior-distance improvement are needed for a lower-neural candidate. Binary64 boundary rounding is a qualification. The policy tests the top contextual candidate and then falls back, rather than searching eligible runners-up. These source facts help explain conservative behavior but are not measured per-case rejection counts. No thresholds were changed after outcomes.

## The growing-read loop is still missing

The implemented constructor takes one completed native alignment per parent. It projects nominated windows through that fixed map. The guarded decoder receives one fixed location, future scores, ten future bases and a 20-base native right guard. It has no callback that repeatedly localizes its evolving output.

The exact boundaries are `tools/uncertainty_feedback/src/plan.cpp:328-391`, `tools/uncertainty_feedback/src/frames.cpp:183-213,254-260`, and `tools/context_decoder/src/guarded.cpp:51-85,229`. This is an offline conditional decoder experiment, not the requested simultaneous growing-read localization system or a direct live Dorado integration.

The next mechanism must locate only the prefix already available, retain competing positions and a signal-only path, and feed those locations into decoding of the next available block. Completed alignments, future native bases and right guards must be hidden from that process. A changed future continuation must leave earlier decisions unchanged. A plausible wrong-location control must retain escape or abstention.

Saved neural scores also have a causality limit. Native Dorado revision `8b8fc5d36a9c0baab262a743cb175b5878e38ca6` has reverse recurrence within its chunks. Cropping saved score rows therefore cannot prove raw-signal causality. Releasing complete chunks after their signal endpoint can test a chunk-delayed loop with an explicit delay; strict within-chunk acquisition causality needs newly produced bounded-lookahead scores. No such replay or result is claimed here.

## Variant evidence and promotion

All 829 observed baseline ALT calls remain:740 SNV,50 INS and 39 DEL, with zero observed losses. However, changed edit footprints contain zero ALT observations in every class. This establishes off-edit retention, not safety at edited variants. The predeclared100 productive observations in each class remain unmet; the available INS/DEL baseline counts cannot meet them.

The final report authenticates the 26 original private witnesses in both ordinary and withheld modes:12 SNV,8 INS and 6 DEL per mode. Their original outputs and native choices remain unchanged. They are retained original evidence, not freshly generated TARGET512 private controls or proof of safety for these 102 edited centers.

The qualified CLI has no genuine full512 wrong-context arm. It is reported unavailable, not fabricated by swapping frame identities. Biological promotion remains false. The present evidence supports a modest reference-guided gain in this exposed development setting, with no demonstrated extra benefit from partial-search expansion.

## Qualification and preserved failures

The C++23 source 22 manifest remains `43b1a8c194ef9dd0fb5939382ac4b958dbd70a61fb5294d45ae98c4e36729235`; PLAN remains `63a63ba088094fe466a8db8c60609a1f6381b3f8a44967773002ddcf57328caa`. Beam 128, center 0..108 and all 0.5 policy values remain unchanged. C++23 matches native Dorado revision `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`, whose `CMakeLists.txt` SHA256 is `5dfc5f68f9ab03ee8fa2f79799c7960e35dc8c22639cf944856769ed20fad589` and sets `CMAKE_CXX_STANDARD 23` at line61. No stock/shared kernel, model, GPU or neural-export replay was performed by the downstream observations.

Retained native engineering evidence executes 26 controls and one CTest without skips. Python engineering executes 18 tests without skips/failures/errors. The archive consumer has 47 qualified controls. The mechanism sidecar has 33 direct qualified controls; its old enclosing qualification failure remains failed. All 512 new frame intervals passed the original C++/independent Rust scalar comparison. Runtime/custody review covers the entire fixed cohort in bounded deltas. Scientific worker caps are enforced; metadata-supervisor kernel caps are not proven.

The final observation controller is `05501e17b569f7929d6df18207e0ae68ee8d07872e5ebfcba5c41fa0fa59f877`, observer `0f7143c36874f72351986e09fdf682dff79df4d5fc43ceea4314538fbeabd064`. Its resource adapter uses the existing recorder memory-profile API while retaining actual CPU 2/RAM16 GiB/AS24 GiB/swap0,300 s per unit,100 MiB growth,4 GiB cumulative output and 30 GiB free reserve. Each new unit took a fresh canonical NONBLOCK lock. Final completion is written-last and synced, not rename-atomic; final sync occurs after the last wall check.

Important failed evidence remains separate:

- The original query 0 enclosing unit has missing final whole-unit resource evidence. Later metadata finalization does not repair it.
- Tail scalar478's original clock receipt was unqualifiable. Recovery reused23 qualified records and ran35 new commands, including the declared replacement; the old attempt remains unchanged.
- The Pin-cache prototype is held. A shared writable mmap counterexample changed bytes without changing its chosen stat identity. Original full hashing stayed in use. No cache speedup is claimed.
- The first postrun observation auditor rejected its own outer stdout/stderr classification. The corrected bounded metadata observer reused successful producer files. Scientific stdout remained stat-only outside admitted workers.
- The first mapping wrapper failed before any scientific command because ordinary4/8 GiB recorder limits conflicted with the 16/24 GiB worker. The exact existing larger-memory request API fixed the adapter;49 controls and genuine subsequent observations passed. No original failure was restamped.
- One Root metadata scheduling call lost its immediate console result. No grant or unit existed before the later fresh accepted run; its original reason is unknown and is not labeled a lock refusal. Its gap record is retained.
- Source/binary corruption negatives that fail the registered root hash establish that root guard, not an unvisited deeper guard.

The earlier chronological report and exact failed attempts are retained locally and pinned by the evidence manifest. Model-capacity interruption delayed Root coordination while the final decoding macro completed; no decoding was repeated to recover it.

## Exact evidence

[Evidence manifest](context-feedback-targeting-v2-evidence.json) records complete paths, SHA256 and sizes. Generated data and raw command receipts remain outside Git.

| Artifact | SHA256 |
|---|---|
| Full 512 collection outer | `e09c459dc0c8b07bb4f4c2a62661b807d29ffe891ace19c30518b10ba6e272ee` |
| Complete 64-parent apply outer | `38c0c7f287d72f40954bdad0015c668655f391b49a8943b1350d6e71a011a998` |
| Final 15-outcome report | `446dbb7fd62d5969663571b4e2edb1ae6e22e7cbb95ef6b61653286c38c99850` |
| Final report outer, ROOT 13421 CLOSED0 | `e95796b326ad181fe24752dfea28231d238f8723d066f1667e887f9e923e7a45` |
| Final strict observation | `fb34c75df165bcdba75c650b59942cd7b811eb8acfb2fdf1dd533dfc2d42219c` |
| All 22 actual observation units | `0ba0e632b6b31c446cc9dbb0e96b672c4da5be66754ee9c8dc3cc159007c67b6` |
| Independent 15-outcome matrix review | `0a6b1bfaa4152ef94131a5682b3d78c3a0e65016272b6d6f67bfa89b943dca6e` |

The final report is `results/context-feedback/targeting-observation-report-3/complete.json`. Its strict raw/runtime proof is `logs/context-feedback-targeting/targeting-observation-report-v3-01/observation-strict-metadata-observation-v4.json`. Independent review is under `logs/context-feedback-targeting/reviews/full512-accuracy-actual-independent-01/`. This review is same-family and metadata-bounded; heavy current artifacts are stat-only outside scientific workers. It does not independently reproduce ROOT's session handles or regenerate bootstrap samples.
