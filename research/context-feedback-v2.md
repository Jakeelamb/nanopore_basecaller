# Guarded context decoding, version 2

This experiment repairs the mismatch between a cropped score interval and the part of the original read it owns. Version 1 and its results remain immutable in `/home/jake/Projects/nanopore_basecaller-context-feedback`, commit `cb052f5b308b7d02368e7411fafca7f7e65f2138`. This work uses the separate `experiment/context-feedback-boundaries` branch and worktree. Shared Dorado/exporter kernels, source owners' files and successful producers stay read-only.

Jake authorized autonomous implementation, execution and evaluation. Every substantial host unit still acquires the canonical stock host lock nonblocking, retains raw commands/exits/clocks/errors and terminates its owned tree before release. CPU decoder units initially retain a 300-second ceiling, two CPUs, 4 GiB memory, 8 GiB address space and zero swap. Larger-memory CPU-only mapping units use the separately established 16/24 GiB envelope. No encoder, exporter or GPU run is needed for retained ordinary or private fixtures. A held lock is a refusal, not authority to bypass another owner.

## Predicate and workflow

1. Preserve the version-1 source, producer receipts, negative accuracy result and diagnostic failures.
2. Compare typed boundary designs before implementation. The chosen model must preserve literal outside-core SEQ/Q, keep novel center variants searchable and account for alignment mass without duplicate handoff timing.
3. Freeze the first repaired policy before its outcome. Use native first ten bases as left guard, native last ten plus ten genuine following native bases as right guard, and the corresponding expanded retained score interval. Replace only the original mutable center. Keep beam width 128 and context weight, signal deficit and objective margin all 0.5. Project graph paths through their CIGAR onto the editable genomic center; do not trim a fixed number of graph characters across indels.
4. Implement and independently qualify the guarded arithmetic/search, native consumption and complete-parent reconstruction. Tiny exhaustive enumeration must compare the full center census, marginalized masses and context ranks. Include center/suffix ambiguity, indels, state-dependent guide, private variants, neutral parity and unavailable guards.
5. Run a genuine first-32 handoff, retaining all original exclusions and explicit new abstentions. Compare native, matched guarded reference-free, final-context-reranking and context-during-search. The last two use the same final objective and gates, isolating the contribution of search.
6. Run the complete retained ordinary development plan with accounting for all 451 rows, including 120 original exclusions. Keep the first-32 subset visible. Evaluate the same unchanged invariant-error and ALT endpoints on complete parents.
7. Add a separately bound genuine private-allele stress-test from retained enriched fixtures. Truth can construct/select the stress-test and evaluate its outputs, but cannot enter inference records or decide a winner. Retain every attachment/scoring/guard exclusion and distinguish ordinary from withheld context.
8. Examine measured failures, make only separately declared changes, and repeat appropriate units. Preserve earlier variants and results. Finish with independent source/runtime/scientific review, exact evidence pins and a draft PR. No merge is authorized.

Engineering success requires the repaired boundary model to pass independent arithmetic, consumed-input and reconstruction controls. Scientific improvement requires measured gains against stock and matched reference-free while retaining tested ALT calls. The unchanged promotion target is at least 1% relative error reduction in both frozen domains, strictly negative technical parent/block upper bounds, complete parent accounting and adequate per-class ALT support. Missing support or failed gates stay failures. No blinded confirmation, population safety or streaming integration follows from exposed HG002 development.

The old diagnostic showed that shared right continuation reverses all 14 examined trailing-base preferences. It did not run a repaired beam or establish biological improvement. The new experiment must measure those outcomes rather than assume them. Its first boundary repair does not lower acceptance gates or increase the reference weight.

## Throughput checkpoint

Retained ordinary frames are small; source-bound full-plan decoding and complete traces may exceed the original 100 MiB output envelope. Price actual work and output after the genuine repaired handoff. A larger declared output stop threshold or bounded partitions may be used before intake, never silently after a boundary. Reuse valid completed phases and window artifacts rather than replay successful native producers. Keep accurate source/compiled/input/output closure for each new version.

## Actual results

The repaired development experiment improves the native calling endpoint modestly. Context reduces the scored error rate by 0.6814% in the frozen 100 domain and 0.5068% in the 500 domain. Both fall short of the unchanged 1% promotion target. Feedback during search produces exactly the same complete calls as final context reranking. This is positive development evidence for retrieved context with repaired boundaries, with no observed added benefit from context-guided candidate discovery.

| Complete output | Invariant errors, 100 domain | Invariant errors, 500 domain |
| --- | ---: | ---: |
| Native | 8,785 | 3,939 |
| Guarded reference-free | 8,784 | 3,935 |
| Final context reranking | 8,725 | 3,919 |
| Context during search | 8,725 | 3,919 |

The selected and final-rerank complete SAM inputs are byte-identical. They share the actual rerank mapping and observer result by that explicit identity; a third mapping was not run. These are substitution, insertion and deletion counts from the unchanged mapping-conditioned invariant-column endpoint. Its normalized error rate includes its own denominator, so dividing only the integer error-count difference does not reproduce the reported relative rate reduction.

Relative to matched guarded reference-free, context reduces the scored error rate by 0.6700% and 0.4055%. Both domains have 100% paired reference exposure. Parent and genomic-block technical bootstrap upper bounds on the aggregate error-rate difference are strictly negative for context versus both controls. These are observed-flowcell resampling intervals, not population uncertainty or blinded confirmation. All 64 parents remain. Positive exposure covers 53 parents in the 100 domain and 50 in the 500 domain.

The full plan retains all 451 rows. It decodes 311, preserves 120 original exclusions, and explicitly excludes 20 whose fixed native guards are gapped or clipped in the native mapping. It reuses the successful first-32 checkpoint rather than decoding those frames again. Neither search reaches its center cap. Both beams prune and remain approximate. Full phase masses, ranks and retained center censuses remain in the native traces.

Reference-free changes nine centers and context changes 37. Context changes partial search on all 311 decoded frames. Every raw context winner is already an escape finalist and equals the final-rerank winner, even before final gates. Sixteen changed selected sequences are absent from the old retained scalar panel, showing that the implementation can leave the historical finite H; that novelty comes through the expanded escape search in these observations. It does not establish an advantage for context during search.

## Same-cohort repair check

A separate scoring unit uses the same planned query IDs 0–31 and complete 64 parents as version 1. Guarded reference-free is literal native SEQ/Q in this subset, so its retained native mapping is reused after explicit molecule-identity checks. Final reranking and in-search SAMs are byte-identical, so one new context mapping supplies both results. The original version-1 mappings are preserved.

| First-32 output | Errors, 100 domain | Errors, 500 domain |
| --- | ---: | ---: |
| Native / repaired reference-free | 8,785 | 3,939 |
| Version-1 reference-free | 8,796 | 3,943 |
| Version-1 selected context | 8,788 | 3,941 |
| Repaired selected context | 8,781 | 3,937 |

The repair changes version 1's net harm into four and two fewer errors than native. In this subset there are two fewer deletions and two fewer substitutions in the 100 domain, and two fewer substitutions in the 500 domain, with no insertion increase. Relative rate reductions are only 0.04553% and 0.05077%; technical bootstrap upper difference bounds equal zero, so this subset fails strict-negative and 1% criteria.

This is a repair-bundle comparison. The planned cohort is unchanged, but version 2 decodes 22 windows versus version 1's 24. Ordinary query IDs 7 and 21 now abstain because native guards are gapped/clipped. Context edits queries 0 and 24. The result does not isolate additional continuation from fixed guards, revised ownership and explicit abstention as separate causal factors.

## Variant preservation

Both scored arms retain all 829 observed native ALT calls: 740 SNVs, 50 insertions and 39 deletions. Across all decoded editable centers, 37 baseline ALT sites are wholly contained: 34 SNVs, one insertion and two deletions, over 16 parents. None intersects a center that either arm actually edits. Global ALT retention therefore supplies no direct evidence of safe editing at these variant sites.

The separate truth-enriched private diagnostic retains the entire 60-selected / 40-attached / 31-scored / 26-unambiguous funnel. Ordinary context decodes 31 frames; withholding ALT-supporting paths decodes the same 26 unambiguous cases and retains five explicit challenge exclusions. Each mode retains nine original graph/scoring exclusions. The 26 cases contain 12 SNVs, eight insertions and six deletions, at distinct sites over 12 parents. Per-class parent support is two, five and six respectively. Selection and withholding were frozen before decoding. Truth and genotype never entered the decoder frame or winner computation.

All three arms in both modes preserve every native parent SEQ/Q exactly. The actual six complete emission files are checked against the pinned native mapping in molecule orientation. Its existing mapping and allele observations are reused; no identical native producer is replayed. This demonstrates preservation by abstention, with no calling gain on this diagnostic and insufficient support for broad variant safety.

The known withheld insertion at private query 21 remains a useful warning. The raw context winner deletes a genuine C from `TACACAGAGTCCCCAGGCCCTC`, reducing signal score from 288.18225866987535 to 287.74686875953023. Its context objective gains only 0.06461008965488, below the frozen 0.5 margin, so the final output preserves native. The reference-free branch alone does not protect this allele; the final gate protects this particular case. We retain the synthetic weak-private loss control and make no general safety claim.

## Engineering and custody

The new C++23 implementation uses fixed native guards around an unrestricted editable center. It marginalizes stay/step alignment paths for `left + center + right`, without duplicate epsilon handoffs. Only the owned center is emitted. Ten genuine following native bases are included in the scored right continuation. Outside-center sequence and quality remain literal. Graph centers are projected through CIGAR, including indels, rather than trimmed by graph character count. Empty centers remain legal.

The frozen beam width is 128. Context weight, maximum signal deficit and minimum objective margin are all 0.5. Final reranking and in-search feedback use the same objective and gates. Missing context takes the matched reference-free path. Explicit disabled-context controls preserve its exact bits and trace. Reference-free is allowed to make real neural edits; it is not forced to match native.

The native integration target is Dorado commit `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. Its CMakeLists.txt SHA256 `5dfc5f68f9ab03ee8fa2f79799c7960e35dc8c22639cf944856769ed20fad589` requires C++23. No new Rust decoder, neural encoder, exporter, model or GPU execution is involved. This remains offline saved-score decoding, not streaming Dorado integration.

Engineering attempt 3 binds source inventory `7a1b9c6f05597dd70e5eb96c894c2ed9e0cf811c28cc7735354fa1aed1f0164b` and binary SHA256 `41c45b2d459291cb4d0375b5163f522bb2f6fd7467761e8b294f8099226177cb`. Strict Release compilation, pinned formatting, CTest, all 31 required UV Python tests with skipped0, native independent controls, and actual compiler/runtime closure passed. The guarded oracle independently checks 3,262 phase masses, 1,288 state-dependent ranks and 339 finalist census/mass/rank comparisons across 23 tiny frames, with declared relative tolerance. It includes executed bad-epsilon recurrence, state-dependent guide, isolated margin/deficit gates, private SNV/indel, ties, empty paths and cap controls. Independent source review cleared both arithmetic and wrapper boundaries. The full observer has four additional hermetic controls and its own source review.

The first real handoff failed before decoding because the retained reconstruction collection includes its exact DGP parent entry alongside DGM chunks. The corrected parser accepts only that exact parent pin, retains the full chunk census and reproduces all parent SEQ/Q/MOVES. That failure, the earlier source cuts and all successful attempts remain retained. A review also caught legitimate gapped/clipped future guards; construction now records explicit boundary exclusions and C++ consumption remains strict. No outcome gate was changed.

All substantial units acquire the existing canonical lock nonblocking. Whole-unit systemd and outer monitoring cover input hashing, frame construction, native stages and cleanup. The controller retains the lock until the complete worker cgroup is terminal and owned launcher descendants are reaped. CPU decoding uses two CPUs, 4 GiB memory, 8 GiB address space and zero swap; mapping uses two CPUs and 16/24 GiB. Each worker unit has a 300-second hard ceiling, a 4 GiB polled aggregate output stop threshold and 30 GiB disk reserve. Controller terminal observation and final receipt projection are separate control-plane work outside the worker cgroup, with the canonical lock retained. The stop threshold is not a filesystem quota. Successful completion is written last and synced, not rename-atomic. No new adapted-supervisor timeout canary was run; distinct prior process-guard evidence is not promoted into such a claim.

Actual full decoding took 167.461 seconds, with 175.386 CPU seconds and a 2.5 GiB service peak; private decoding took 38.037 seconds. Reference-free and context full mapping/scoring units took 53.670 and 61.236 seconds, peaking at 13.9 and 13.6 GiB. These are bounded-unit observations, not encoder throughput or an end-to-end speedup. Full decoding includes evidence checks, construction, new frame decoding and trace output, and reuses the prior checkpoint.

## Evidence and commands

The local retained roots are `results/context-feedback/v2-engineering-3`, `v2-query0-2`, `v2-first32-1`, `v2-full-1`, `v2-private-1`, `v2-emit-full-1`, `v2-emit-private-ordinary-1`, `v2-emit-private-withheld-1`, and `v2-observe-full-1`. `v2-summary-1.json` binds the measured summaries and explicit identity reuse. Native raw recorder command/cwd/start/end/exit/stdout/stderr/GNU-time files and durable stage finish records are linked by each seal; source, compiler, runtime and full outer terminal evidence are checked before reuse.

The Python prefix for every command is `UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv uv run --no-sync python`. Each execution also receives its own immutable, freshly timed `--admission` JSON and is wrapped by the maintained raw command recorder.

```sh
scripts/context-feedback.py qualify --config config/context-feedback-dev-v2.json --output results/context-feedback/v2-engineering-3
scripts/context-feedback.py query0 --config config/context-feedback-dev-v2.json --qualification results/context-feedback/v2-engineering-3 --output results/context-feedback/v2-query0-2
scripts/context-feedback.py checkpoint --config config/context-feedback-dev-v2.json --qualification results/context-feedback/v2-engineering-3 --query0 results/context-feedback/v2-query0-2 --output results/context-feedback/v2-first32-1
scripts/context-feedback.py full --config config/context-feedback-dev-v2.json --qualification results/context-feedback/v2-engineering-3 --checkpoint results/context-feedback/v2-first32-1 --output results/context-feedback/v2-full-1
scripts/context-feedback.py private --config config/context-feedback-dev-v2.json --qualification results/context-feedback/v2-engineering-3 --output results/context-feedback/v2-private-1
```

`observe.py prepare` reconstructs complete parents for each phase/mode. Its `arm` command maps and scores the distinct complete outputs. `summarize.py` deep-checks the retained source/execution graph and reports outcomes without repeating producers. The exact raw commands and source pins, including explicit admissions, are authoritative over these shortened examples.

The repaired first-32 truth supplement is `v2-first32-score-1`, with its exact identity reuse, nine native stages and successful outer terminal receipt. It took 45.256 seconds and peaked at 11.7 GiB. Its separate maintained adapter has three hermetic controls and an independent source review. The independent same-family scientific audit checked 406 actual raw stages and independently recounted 512 parent comparison rows from EQX CIGAR against the matched reference masks. It found no blocking source/evidence contradiction and confirmed the limited scientific verdict. Its retained report is `logs/context-feedback/v2-design/scientific-review-v2.md`, SHA256 `16969883f58ca58633a29435e21c896df838e2a6a5ae49efb6725fc9aec7eef5`. [The evidence manifest](../tools/context_decoder/guarded-evidence-manifest.json) binds the final source, binary, actual phase/observer seals, summaries and independent reviews. No promotion, blinded validation or native integration is inferred from the results above.
