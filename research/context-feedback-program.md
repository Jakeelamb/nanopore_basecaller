# Context feedback implementation and evaluation program

Jake authorized the complete research program on 2026-10-24, including autonomous implementation and evaluation. This unit uses `experiment/context-feedback-program` in `/home/jake/Projects/nanopore_basecaller-context-feedback-v3`, based on `050bc68cae40edda96c83257c79ec5db49404659`. Version 2, its source-bound binary, successful producers and results remain immutable in their original worktree. Stock, shared native kernels, source-owner files and other agents' changes stay read-only.

The target is location-aware improvement of uncertain molecule sequence with explicit support for DNA absent from the reference. Completion requires actual evidence for each supported implementation stage, independent review, exact source and command closure, and a draft PR. A failed or inconclusive scientific gate remains a result. No promotion follows from engineering checks. The existing 1% improvement target, paired technical uncertainty, parent accounting and variant-safety requirements remain unchanged. HG005 cannot select candidates or policy.

## Workflow and state

- [x] Ground the frozen baseline, research findings and current resource state.
- [x] Compare two architecture sketches for candidate/truth diagnostics and select one coherent interface.
- [ ] Implement and independently qualify the retained-candidate oracle and orchestration.
- [ ] Run the complete ordinary and private diagnostic without repeating neural producers.
- [ ] Implement and compare uncertainty targeting, contextual scoring and correction decisions as separately declared variants.
- [ ] Implement and qualify joint latent-state inference against equivalent late scoring before testing genuine retained frames.
- [ ] Implement bounded prefix feedback and validate signal availability, lookahead, state continuity, location proposals and output commitments.
- [ ] Build independently sourced sample context where overlap and custody support it, with physical-molecule exclusion and graph versioning.
- [ ] Evaluate complete matched outputs, biological tradeoffs and actual resource costs. Freeze evidence, obtain independent review and open a draft PR.

Each stage follows its predeclared dependency. A diagnostic can reject a proposed mechanism or show that its prerequisite is absent. Such a finding stops the unsupported claim, preserves the attempt, and directs the next implementation. It does not justify declaring an unexecuted stage verified. New signal producers or data acquisition are separately bounded units with exact inputs and caps, under Jake's standing authorization.

## First unit

The initial data shape separates inference from evaluation. A `CandidateCase` contains a source-bound native window, anonymous context paths, proposed sequence strings, their origins and optional retained neural scores. An `OracleTruth` contains reference fragments, fixed masks or exact private haplotypes. Truth records never enter the inference scorer or choose a deployable output.

The existing packet contains 311 ordinary cases with 39,808 escape-finalist entries and 6,631 additional conditioned-only strings. Native and graph strings supplement that union. The private diagnostic preserves its 60/40/31/26 funnel and both context modes. A candidate without a qualified neural score stays unscored for inference. Its truth label may still reveal missing candidate support.

A local sequence diagnostic and an exact private-haplotype diagnostic are different endpoints. Neither equals the complete-parent mapping-conditioned accuracy endpoint. The local diagnostic must preserve reference coordinates, strand and insertion-flank conventions and disclose ambiguity among optimal alignments. Private ALT-support loss must not be silently reclassified as proven allele erasure when exact haplotype matching becomes unresolved. Useful/harmful/neutral/unresolved labels retain those distinctions.

The initial throughput checkpoint is about 47,000 ordinary candidate entries plus the 57 private frames, short bounded reference fragments and two fixed masks. The preparer computes the actual unique-string and DP-cell counts before execution. The actual count is validated from packets. The first genuine case and first32 cases price the complete diagnostic before the full set. C++23 performs substantial scoring; UV Python binds inputs, invokes tools and checks receipts. There is no predicted runtime or accuracy gain.

## Resource and evidence contract

Every substantial host unit acquires `/home/jake/Projects/nanopore_basecaller/results/stock/host.lock` nonblocking and retains it until the owned worker cgroup and launcher descendants are terminal. No free lock, stale grant or elapsed reservation grants authority over another worker. At intake on 2026-10-24, no holder appeared in the read-only lock inventory. This observation is not a reservation.

CPU engineering and retained-score units start with at most 300 worker seconds, two CPUs, 4 GiB kernel memory, 8 GiB address space, zero swap, a declared aggregate output stop threshold and a 30 GiB disk reserve. Whole-reference mapping, prefix encoding, GPU work or larger memory have exact separately priced caps before execution. A supervisor covers synchronous hashing and preparation as well as child stages. Terminal observations precede receipt projection, and failed raw command, status, clocks, stdout, stderr and time remain retained. Completion is written last and synced, not rename-atomic.

The controller reuses the qualified process-guard and terminal primitives. It does not infer adapted failure-path acceptance from earlier tests. New source binds the actual compiler, flags, runtime, native binary and all consumed data. Existing v2 execution validation must run through its original source location and ROOT semantics. Historical native and graph producers are not rerun to repair projection or orchestration failures.

The canonical decision trail is `logs/context-feedback-program/decisions.tsv`. Source readiness, engineering qualification, scientific development outcomes, confirmation and deployment remain distinct states.

## Selected first-unit architecture

The independent judge selects design B, the bounded full-guard optimal-edit DAG, at 23/25 over A at 21/25. Adopt A's separate inference target, explicit scored/unscored state and exact original-v2 auditor import. Use one native alignment implementation for masked count envelopes and exact private event-cut projection. Ambiguous boundary placement remains unresolved. The evaluator never emits a truth-selected FASTA or deployable action. Historical inference ranks native plus escape before considering conditioned-only strings, matching the saved implementation.

The owned native module is `tools/context_decoder/study/`. The Python packet boundary is `tools/context_decoder/program_inputs.py`. The root owns `scripts/context-program.py`, resource supervision and evidence. The native worker owns a single wire-schema census consumed by both parsing boundaries. Subsequent model/targeting stages derive a new isolated worktree after freezing this one, preserving absolute source paths needed to revalidate earlier compiled producers.
