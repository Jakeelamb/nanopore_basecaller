# Location feedback during C++ decoding

The location-feedback mechanism works in the offline C++ decoder, but this first frozen prototype does not improve stock Dorado accuracy. Context removes eight errors relative to its matched reference-free decoder in the 100 domain and two in the 500 domain. The complete selected output still has three and two more errors than native. It retains all 829 observed baseline ALT calls, with inadequate local variant support. This is a completed development experiment and a failed promotion, not evidence that genomic feedback cannot improve a better decoder. No GPU, neural encoder, exporter or historical producer was replayed.

## Measured calling result

The frozen checkpoint selects original queries 0 through 31. Twenty-four eligible windows decode, eight original exclusions remain, and all 64 full parents enter the unchanged mapping and biological observer. The experiment changes only those selected windows; it does not claim complete-cohort context decoding. All 120 original exclusions remain in the full 451-row ledger.

| Complete output | Invariant errors, 100 domain | Invariant errors, 500 domain |
| --- | ---: | ---: |
| Original native call | 8,785 | 3,939 |
| Matched reference-free decoder | 8,796 | 3,943 |
| Context-conditioned selection | 8,788 | 3,941 |

These are substitutions plus insertions plus deletions from the unchanged mapping-conditioned invariant-column endpoint. Both domains have full paired reference exposure. The observer reports normalized error rates with its own denominators, so relative error reduction is not calculated by dividing only the integer error-count difference above.

| Context selection compared with | Relative error reduction, 100 | Relative error reduction, 500 |
| --- | ---: | ---: |
| Native | -0.033225% | -0.049863% |
| Matched reference-free | +0.090835% | +0.050723% |

The required 1% improvement against both comparators fails. Both parent and genomic-block technical intervals cross zero against native. Against the matched reference-free decoder their upper error-delta bounds are exactly zero, which fails the strictly negative requirement. These intervals resample observed parents or blocks and do not establish generalization to another donor or flowcell.

Both new arms preserve all 64 parents and 100% of the accepted paired reference exposure. The 100 domain has 53 positive-exposure parents and 11 zero-exposure parents; the 500 domain has 50 and 14 respectively. Three of the 64 primary records are unmapped in each new mapping. The native baseline has 740 SNV, 50 insertion and 39 deletion ALT observations, at the same respective numbers of distinct sites. Both new arms retain all 829, with zero observed ALT loss. Only one baseline ALT observation, a retained SNV, overlaps any edited window in either arm. No baseline ALT insertion or deletion overlaps these edits. The full-parent count therefore supplies very little local safety evidence. The unchanged requirement of at least 100 observations per class fails for both indel classes. Neither arm is promoted.

Context changes partial search in all 24 decoded frames and final calls in five relative to the independent reference-free escape. This establishes feedback during search on genuine retained scores. It does not establish streaming behavior, encoder feedback or native Dorado integration. The location observation uses the completed tentative native call, so causality for live simultaneous decoding remains unqualified.

Thirteen of the 16 reference-free edits are single-base extensions at the saved window's right edge. Thirteen of the 17 selected edits have the same pattern. The selected output has eight more invariant insertions than native in the 100 domain, offset by three fewer substitutions and two fewer deletions. This pattern makes saved-window endpoint handling a concrete next diagnostic. It does not prove that endpoint handling caused every error. The frozen experiment literally spliced complete decoded intervals and made no anchor trimming, endpoint repair or outcome-dependent gate change.

The strong private substitution/insertion/deletion controls pass on synthetic scores. A weaker synthetic example still demonstrates that this prior can erase a real allele. An escape branch and zero observed losses here do not establish private-allele protection. HG002 is exposed development; query 0 is shared with another development diagnostic. HG005 was not used and HG001 remains reserved.

The successful CPU-only observation receipts are `results/context-feedback/observation-v1/reference_free/execution-complete.json` and `results/context-feedback/observation-v1/selected/execution-complete.json`. Their native summaries and variant comparisons are under the corresponding arm directories. Each new complete output was aligned exactly once, with the retained native baseline reused. The two admitted services stayed below their separate 300-second limits, two-CPU quota, 16 GiB memory and 24 GiB address-space ceilings, with zero swap. This is execution accounting, not a speedup benchmark.

## Scope and language

The isolated worktree is `/home/jake/Projects/nanopore_basecaller-context-feedback`, branch `experiment/context-feedback-decoder`, baseline `0ec40a69d6a43440cafc790c4614d516e8137011`. NP Retrieval owns the new C++ decoder, source/input/controller helpers, wrapper, protocol, tests, this report and ignored context-feedback outputs. Caller-reference explicitly confirmed no overlap. Other owners' files and all successful scientific producers remain unchanged.

Jake directed C++ for native integration and speed. The pinned native Dorado source is commit `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. Its `/home/jake/Projects/nanopore_basecaller/software/dorado-src/CMakeLists.txt`, SHA256 `5dfc5f68f9ab03ee8fa2f79799c7960e35dc8c22639cf944856769ed20fad589`, sets `CMAKE_CXX_STANDARD 23` at line 61. This standalone decoder also requires C++23. Existing Rust code and qualified checkers are read-only. No new Rust context implementation exists.

The C++ library accepts a score frame, retrieved local paths and a frozen search policy. It does not link Torch, CUDA or a model. OpenSSL Crypto supplies hashing. UV Python validates the retained producer chain, constructs the narrow input records and coordinates C++ execution. The native Dorado encoder and decoder are not changed in this first experiment. Full native integration, streaming causality, trained reference conditioning and calibrated qualities are later work.

## Prospective mechanism

`decoder.h` defines the frame, retrieved context, policy, partial prefix, search trace and outcome. The score frame binds to the original saved k4 transition scores. Search extends stays and A/C/G/T emissions and sums retained alignment-path mass for each identical emitted prefix. A neural backward guide ranks future possibilities before pruning.

The conditioned beam uses this fixed objective during partial search:

`retained signal log mass + 0.5 * context potential + neural backward guide`.

For an unfinished emitted prefix, context potential is negative minimum Levenshtein distance to any prefix of a retrieved local path. At termination it is negative minimum distance to a complete local path. The potential is recomputed from emitted sequence and added once. It is not accumulated on stays. Duplicated or permuted paths cannot create additional support. This is a sequence-distance heuristic, not a calibrated genomic probability model.

The separate escape beam has the same width and length bounds with context disabled. Final candidates are the conditioned finalists, escape finalists and immutable original native sequence. Every finalist is rescored with the complete unpruned scalar CRF recurrence before selection. The final context objective uses the same distance potential. A context winner must beat the reference-free winner by objective margin 0.5 while losing at most 0.5 signal log likelihood. Otherwise the reference-free result is retained. Final ties prefer native, then lexical sequence; partial ties are lexical.

The frozen width is 128 for each beam, emitted length is 20 through 128, and context weight is 0.5. Context missing, ambiguous or weight zero takes the explicitly matched reference-free path. Reaching the emitted-symbol bound on an attempted expansion, or finding no eligible escape finalist, abstains to the original native sequence. Beam pruning is explicitly approximate and records generated, merged, retained and pruned counts plus every retained-prefix census at each timestep. It does not claim a global optimum. Final exact rescoring does not make the earlier pruned search exact.

This differs from the old finite-H panel bonus. Context can change which partial prefixes survive before a complete sequence exists. The synthetic separation case searches CCC outside its supplied historical comparison set AAA/AAC. That set supplies a control only and never defines the new search space. The reference-free search can emit arbitrary canonical alternatives under the declared bounds.

## Input and location custody

The genuine query 0 consumed the exact registered 84-timestep interval, parent `7214d805-8331-49aa-af61-478be074d7a6`, and DGS1 file `p1061436_b6_s23.scores` of 4,112,461 bytes with SHA256 `2155a435c42aae305635e41f3c79507a4ad249eb2fd84d8e5935898effcc9edd`. The separately admitted native loader checked the actual payload and retained scalar controls. Query 0 is shared with the raw-current diagnostic and is exploratory development, never independent confirmation.

The Python constructor starts with the reviewed bridge handoff and actual successful producer chain. It checks the original cohort and plan, mapped native SAM and its successful location producer, graph source, original decisions, full catalogue window receipts, native parent metadata, selected chunk metadata and retained attachment. It derives genomic location from the mapped native call. It checks parent, orientation, contig, CIGAR/read interval, stock sequence, native SEQ/Q/MOVES, exact score identity and time interval, and original initial k4 context. Truth, desired allele and validation labels cannot enter the inference record.

The historical receipt auditor is loaded from its registered original source path after checking the full exact pin. Its original ROOT and raw cwd equality remain intact. Loading a byte-identical relocated helper would change that check and is prohibited. A hermetic source-location/cwd control explicitly covers this distinction.

The C++ consumer independently hashes the actual DGS1 file and metadata, checks the consumed tensor geometry/token/slot/chunk, reconstructs the initial state, reads and clamps actual FP16 transition values, and verifies every frame/context linkage field. The binding includes exact plan hash, query, parent, chunk, tensor, interval, initial state, orientation, reference span and location-producer receipt. Consumed inputs are checked again after loading. Original retained hypotheses are supplied only as bit-exact scalar controls against the previously qualified Rust observations, not as the decoder's candidate space.

The narrow TSV record is constructor output. Direct use of the generic C++ CLI does not itself establish registered ancestry. The admitted wrapper plus actual constructor/native producer receipts supply that chain. Hermetic native-consumption fixtures are explicitly synthetic and do not stand in for the genuine query-0 handoff.

The first-32 phase covers original query IDs 0 through 31 while a full 451-row inventory retains every one of the 120 original exclusions. Other originally scored rows remain explicitly not selected. New decoder abstentions remain separate. Original parent controls stay untouched. No corrected whole-parent SAM or biological accuracy claim follows from this decoder-only checkpoint.

## Controls prepared for execution

The C++ oracle independently enumerates stay/step paths, sums probabilities by emitted string in long double, and compares full unpruned sequence census, every finalist's marginalized signal mass, terminal context state and terminal rank. It covers k 1 through 4, timesteps 0 through 4 and two initial states per k. Independent nonzero-context comparison tolerance is `1e-11 * (1 + abs(independent log probability or objective))`. Disabled-context calls compare exact scalar bits and complete traces. Impossible and empty/short behavior remain explicit.

A state-dependent pruned-search control detects omission of the neural backward guide. At k1/T2/beam1, native AA, t0 A=0/C=-0.1 and t1 C-to-C=4 with other emissions=-4, the guide must retain C and produce CC with signal score 3.9. An independently constructed zero-guide witness yields AA at -4. This was added in response to independent source review; neither a mutation nor these controls has yet executed.

Prepared cases also cover native and lexical ties, no eligible finalist, emitted-symbol-bound abstention, context path permutation and aliases, changed valid sequence context, an alternative outside old H, unavailable/ambiguous locations, nonfinite data, and strong private substitutions, insertions and deletions absent from every context path. The weak ambiguous-signal example remains an explicit private-allele failure warning. Keeping an escape beam does not prove variant preservation.

The Python suite currently defines 17 cases, including six direct C++ consumed-frame cases. Qualification supplies the actual immutable C++ executable and requires all 17 tests to execute with skipped0. Missing linked-stage evidence and missing recorder files are bounded synthetic controls. The latter checks that durable terminal status survives a projection failure, then checks the linked raw-file rejection after repinning its fixture. These mocked control-plane cases do not qualify real process shutdown.

## Process and resource boundary

An outer controller retains the canonical stock host.lock through nonblocking intake and through positive terminal evidence for the entire worker cgroup. The whole worker, including synchronous input parsing, source/data hashing and frame construction, runs in a transient user service with Type=exec, ExitType=cgroup, KillMode=control-group, RuntimeMaxSec, TimeoutStopSec=1s, SendSIGKILL=yes and final SIGKILL. The controller validates actual worker properties and cgroup CPU/memory/swap limits. It continuously monitors aggregate owned output and disk reserve outside the worker's synchronous phases. The whole-unit timer is not a stage-polling timer.

Worker stage cleanup uses an exact snapshot of the source-bound CPU subreaper/group helper. Source origin SHA256 is `dd90a7c50cd1b3044178e3ee248e7f5e948840496b1ad0cee3b99dadad6a14e9`; origin/snapshot/receipt pins are in `tools/context_decoder/process-guard-provenance.json`. That earlier, distinct CPU observation reaped an ignored-TERM orphan after its recorder leader exited and preserved an unrelated group. It does not qualify this adapted controller, its service boundary or GPU behavior. No new shutdown canary has run.

The outer controller records actual terminal service state, empty or removed worker cgroup, and terminal launcher group before releasing the lock. If termination evidence cannot be obtained, it retains custody and records the failure. It never releases solely because a recorder leader exited or a nominal deadline passed. Stage terminal exit/clocks are synced before raw receipt assertions. A projection failure preserves its execution observation and partial raw files; it is not an instruction to replay the command.

Completion files are written last and synced. They are not published through an atomic rename. A partial or missing completion remains unqualified, and every downstream reuse checks the linked files rather than trusting the presence of a filename.

Successful phase reuse requires execution-complete.json from the outer controller, the worker seal, successful terminal proof, every linked stage finish and raw command/clock/exit/time pin, native attempt/result pins, compiled source census, actual compiler and runtime-library closure, and the immutable executed binary. It recursively checks the prerequisite phases. A missing linked file, stale source or failed outer execution cannot admit a later phase.

The public systemd contracts behind this boundary are [ExitType and RuntimeMaxSec](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) and [control-group termination](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html). Actual worker intake records verify these properties, CPU/memory/swap limits and the retained outer lock. Positive terminal receipts verify successful worker exit and an empty or removed cgroup before release. Forced limit-breach and observation-loss shutdown behavior was not dynamically exercised by the context unit.

## Three separately admitted commands

Jake subsequently authorized coordination of independent review and successive bounded CPU engineering, query-0 and first-32 units. Each requires a fresh source-bound intake and canonical nonblocking lock. Native Dorado/model replay and GPU execution remain held. The command forms below describe the three phases; actual attempts and outcomes are recorded separately.

Use the existing UV environment, without creating or changing it:

`UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv`.

1. `qualify` builds Release C++ with strict warnings, no fast math and contraction off; runs the pinned formatter dry-run over the explicit owned source census, CTest parallel1, all 18 UV Python controls with skipped0, native arithmetic controls and compiler/runtime closure observation. It does not load the historical bridge audit, genuine q0 tensor or other scientific data. The ceiling is 300s, worker CPU quota 2, 8GiB address space, 4GiB kernel memory, zero swap, a monitored 100MiB aggregate owned-output stop threshold and 30GiB reserve. The outer monitor's control-plane work is recorded separately from the worker quota. The hard worker interval reserves time for teardown. Aggregate output monitoring is polled, so the stop threshold is not a filesystem quota.
2. `query0` requires successful deep engineering qualification and a fresh separate admission. It performs historical custody admission, genuine q0 construction, conservative work accounting and real C++ decode. It does not rerun the encoder, exporter, graph producer, catalogue or engineering build. Context edit-distance work is potentially dominant, so this is not bundled into the engineering ceiling. Its own maximum remains 300s under a separate grant, with the same memory/output/floor bounds. The source rejects any frame whose conservative edit-cell bound exceeds one billion, and stops at the actual wall boundary; no larger resource grant is inferred.
3. `checkpoint` requires successful query0 and engineering seals plus another fresh admission. It preserves and reuses the qualified q0 output and decodes the remaining admitted original first32 queries with all exclusions retained. Actual pricing is retained in `results/context-feedback/first32-price-v2.json`. Eligible frames have at most 588,531,840 context edit-cell operations each and 3,380,381,824 in total by the conservative bound. All completed within the unchanged 300-second unit. These operation counts are bounds, not observed executed cells or a speed claim.

The public wrapper constructs the service envelope and checks the private worker intake. It cannot be run as an unsupervised scientific worker by adding a free-form flag without the matching outer lock holder, actual source-bound admission and service identity.

Exact command forms from this worktree are:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
uv run --no-sync python scripts/context-feedback.py qualify \
  --config config/context-feedback-dev-v1.json \
  --output results/context-feedback/DECLARED-qualification \
  --admission /ABSOLUTE/FRESH-ENGINEERING-ADMISSION.json

UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
uv run --no-sync python scripts/context-feedback.py query0 \
  --config config/context-feedback-dev-v1.json \
  --output results/context-feedback/DECLARED-query0 \
  --qualification results/context-feedback/DECLARED-qualification \
  --admission /ABSOLUTE/FRESH-Q0-ADMISSION.json

UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
uv run --no-sync python scripts/context-feedback.py checkpoint \
  --config config/context-feedback-dev-v1.json \
  --output results/context-feedback/DECLARED-first32 \
  --qualification results/context-feedback/DECLARED-qualification \
  --query0 results/context-feedback/DECLARED-query0 \
  --admission /ABSOLUTE/FRESH-FIRST32-ADMISSION.json
```

The command-template admission paths above are placeholders. Actual expired grants remain under `results/context-feedback/admissions/`; they are evidence rather than reusable reservations. Canonical config has no default runnable admission. The formatter executable is SHA256 `cd50c00c4b3475329257d717f9e778769d00d1eff5c03436ebc39b023ddd6394` at `/usr/bin/clang-format`; CMake pinned and rechecked it during the successful format-check stage. Mechanical formatting also exited zero under the canonical lock and a 20-second CPU service. `logs/context-feedback/format-20261023-v1/terminal.json` records inactive service, zero main/control PIDs and before/after source pins.

## Review and next checkpoint

Actual engineering execution completed at 20:40:25 UTC. `results/context-feedback/engineering-v1/execution-complete.json`, SHA256 `8a4b13ee4ee6addce3860a38179857c203b8c48e3f43e8e65698914858e88847`, closes seven successful recorded stages. CMake Release compilation, the pinned formatting target, CTest, all 18 Python controls with skipped0 and native controls passed. The native result has 3,624 independent sequence-census, marginalized-mass and rank comparisons. The same-family review in `logs/context-feedback/review-delta.md` independently verified 130 linked hashes and the exact 22 compiled sources. Forced shutdown and resource-breach paths remain source-reviewed rather than dynamically exercised in this unit.

The separately admitted query-0 handoff completed successfully. Its outer seal is `results/context-feedback/query0-v1/execution-complete.json`, SHA256 `fd873c6dddfbdb767ab71b1509b067c8f39dce8e17ed6551371296cb13600d49`. It consumed the registered native tensor and original-location historical auditor, checked 137 retained Rust likelihoods at exact f64 bits, and changed partial search at 81 timesteps. It selected a sequence different from both native and the matched escape. This shared query remains exploratory development.

The next separately admitted checkpoint completed at 20:42:24 UTC in `results/context-feedback/first32-v1/`. All original query IDs 0 through 31 are accounted for, with 24 constructed/decoded windows, eight original exclusions and zero new decoder abstentions. The full 451-row inventory retains all 120 original exclusions. These windows cover 15 parents. Across the actual consumed frames, 3,330 retained Rust scalar comparisons passed, and partial search changed in all 24 windows. Five context selections differ from matched reference-free, while 15 objective-margin and four signal-deficit fallbacks retain the free result. The final selected sequences differ from stock in 17 windows; the remaining differences are introduced by the matched reference-free search. No margin, deficit, context weight, beam or boundary policy was adjusted after these outcomes.

The separate observation adapter `tools/context_decoder/observe.py` prepared complete 64-parent matched arms. It literally replaces each entire declared decoded interval, preserves all outside-window SEQ/Q, uses uncalibrated `!` quality only for changed windows and independently reconstructs each parent in reverse edit order. It does not trim anchors, reinterpret trailing emissions or repair outcomes after observing truth. This is a separately pinned producer, outside the compiled decoder's source closure. Biological scoring used the unchanged historical pairer and variant observer, with native and matched reference-free controls. Jake explicitly admitted the two larger-memory CPU-only mapping/scoring units before execution. The services reported 11.7 and 11.6 GiB memory peaks and zero swap, within their 16 GiB ceilings.

The independent same-family numerical/source cut at 19:39:49 UTC is retained in `/home/jake/Projects/nanopore_basecaller-score-speed/logs/hillclimb/cpp-math-review.md`. It found no proven algorithm defect and a P2 guide-control gap. The guide, dedicated ties/no-finalist/permutation and k3/k4 controls subsequently passed. The original final-census/mass oracle remains. The boundary cut at 19:51:07 UTC is retained in `cpp-boundary-review.md`; its complete-tree, whole-unit/output monitoring, deep reuse and durable-projection findings drove the changes above. The exact final decoder delta and engineering receipts have independent review in `logs/context-feedback/review-delta.md`. The observation adapter and whole-parent emission have a separate review in `logs/context-feedback/observer-review.md`. These are same-family reviews, not independent biological replication.

The final handoff records frozen source, actual command/receipt pins, engineering outcomes and the failed biological promotion above. `tools/context_decoder/evidence-manifest.json` binds the compiled source inventory, immutable binary, actual phase/observation seals, native summaries and independent reviews. Successful compilation and runtime checks bind the exact decoder source revision. Shutdown canaries were not run for the adapted supervisor; the reused process-guard component's distinct prior evidence remains identified above. The measured calling endpoint, not the bridge or compiler result, determines the scientific conclusion.

The independent final retained-runtime/scientific review is `logs/context-feedback/observer-science-review.md`, SHA256 `ae3780777303480c2d043025e430dede9c0387be1ee4e4e71af1ba247d6a4331`. Its verdict qualifies the observed development producer chains and confirms failure of the frozen scientific gates. It independently checks all 22 observation commands, complete SEQ/Q for 64 parents, all 24 actual decoder source closures, the raw receipts and native endpoint recounts. The preserved source review is SHA256 `a533af620a7f653c3cd13683e4343bc0f212d5a35c8219924920d554a613f944`. Neither review is a new biological replicate.

Prove It Works changed the endpoint to actual calling accuracy. Foundational Thinking separated score, location, context and producer evidence before decoding. The draft PR targets `main` from the assigned baseline `0ec40a69d6a43440cafc790c4614d516e8137011`. Earlier open stock, bridge and retained-diagnostic changes are ancestors; this unit's owned diff starts at that baseline. No merge is authorized.
