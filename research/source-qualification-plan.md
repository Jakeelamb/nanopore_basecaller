# Source-build qualification and prospective experiment

This run qualifies the unchanged Dorado source and prepares prospective accuracy, speed and yield experiments. It does not introduce a candidate algorithm or claim publication readiness beyond the evidence obtained.

## Workflow

- [x] Read the Principles section of Poteto Mode.
- [x] Phase A: Frame.
- [x] Phase B: Design the workflow.
- [x] Phase C: Run the loop.
- [x] Phase D: Keep the audit trail.
- [x] Phase E: Verify and hand back.

## Completion predicate

1. Trace the active simplex path for the exact frozen HAC/SUP models and command options, with source symbols/lines, inputs/outputs, inactive branches and opaque dependency boundaries. Independently check the resulting explanation.
2. Build exact unchanged input commit `8b8fc5d36a9c0baab262a743cb175b5878e38ca6` and its pinned submodules in an isolated path, with the ten declared upstream build patches. Preserve compiler, flags, dependencies, receipts, input custody, transformations, executable and runtime-library hashes. A successful compiler exit alone does not qualify runtime behavior.
3. Exercise the built executable on genuine development/validation signals. Check native BAM contracts, original-parent yield, sequence/quality/split semantics, mapping and the existing fixed accuracy domains against official controls. No HG005 candidate or build selection.
4. Keep successful stock producers immutable. Declare vendor/source semantic equivalence only if the frozen exact comparison passes. A valid executable with different outputs remains a distinct build baseline; do not invent a tolerance after seeing differences.
5. Provide a prospective experiment with fixed hypotheses, units, data roles, controls, accuracy/speed/yield estimands, repeat schedule, uncertainty, multiplicity, failure/selection rules and publication claim limits. Test its required handoffs on genuine outputs and reject corrupted inputs.
6. Independently review final code, actual source-build evidence, trace, experiment specification and any measured comparisons. Complete appropriate checks on the feature PR. Leave the PR unmerged.

## Scope and throughput checkpoint

The current pilot has two donors and three size-selected shards. Development and validation are different flowcells from HG002. They are not independent donor replication. HG005 has already been opened for stock benchmarking and is excluded from candidate selection in this run.

Initial host inventory has 24 logical CPUs, about 76 GiB available RAM and 47 GiB free disk. Preserve at least 30 GiB free. Budget downloaded archives, extraction and build products before transfers. No deletion of scientific artifacts or unrelated work is authorized. The official binary ships CUDA 12.8 libraries while the system toolkit is 13.4. Toolchain compatibility and available disk are the first build risks.

Two source explorers own disjoint read-only trace slices. One build owner owns an isolated compilation and its records. The coordinator owns the shared GPU, experiment interfaces, scientific protocol, integration and PR. Native timing starts only after owned compilation, downloads and heavy CPU checks stop. Profiling uses separate diagnostic processes and never supplies benchmark timings.

Build preparation may take tens of minutes. Runtime work is admitted after the actual dependency footprint and executable are known. Begin with small genuine handoffs, then complete development/validation qualification. Reassess the timing schedule against disk and observed runtimes before launching a long series. Record the chosen schedule before execution; do not select favorable repetitions.

## Designed units

1. Inventory the exact build requirements, source/submodule identities, model configurations and supported toolchain. Verify dependency downloads against upstream hashes.
2. Trace loader/preprocessing/model execution separately from decoding/stitching/splitting/filtering/output. Synthesize one source-backed explanation and identify research intervention seams.
3. Compile the isolated release build, inventory dependencies and run applicable upstream CPU tests. Keep test selection and unavailable coverage explicit.
4. Freeze the source-build runtime comparison contract and its executable checks before genuine GPU execution. Reuse maintained native execution and accuracy interfaces instead of replacing them.
5. Run small official/source genuine comparisons and a negative comparison control. Diagnose differences rather than weakening a failed exact-equivalence gate.
6. Qualify full development/validation outputs and fixed accuracy domains as resource limits permit. Treat any source/vendor build effect separately from a future algorithm effect.
7. Run separate diagnostics for source paths and performance hypotheses. Distinguish sampled GPU activity from kernel-level bottleneck attribution.
8. Freeze the prospective research experiment and its reporting/acceptance rules. Separate pilot technical uncertainty from donor/flowcell generalization.
9. Audit artifacts, ledger, source trace and report with a separate same-family verifier. Commit concise evidence and update the existing feature PR.

## Controls preserved

The official Dorado distribution, model trees, reference, masks, source checkout, historical observations and retained scorer stay unchanged. New source-build outputs, comparison artifacts and diagnostics use new paths. Existing accuracy computation remains in the frozen Rust scorer. New substantial comparison computation must use Rust. Python may coordinate native tools and validate their outputs.

The selected adapter design uses the exact ordinary emitted version and calls the frozen native runner and scorer unchanged. A version-aware fork was considered and rejected as unnecessary for this build. Source and fresh-official smoke plans have separate owners. Source index compatibility gets new two-tier FASTA/index evidence. Smoke corruption controls finish before scoring; accepted observations are then audited without rewriting them. Full admission requires 39 GiB actually free, including the 30 GiB reserve. Historical official full outputs support exact semantic comparisons, not a contemporary speed ratio. The prospective candidate experiment is defined in [the experiment protocol](prospective-experiment.md).

`decisions.tsv` remains the canonical decision trail. A failed build, runtime check, equivalence comparison or projection remains evidence. Publication-level biological claims require a prospectively reserved external cohort and an analysis suited to donor/flowcell replication; this pilot alone cannot supply those claims.

## Final execution checkpoint

After recovery, the user explicitly requested resumption, superseding the prior waiting instruction. The retained held controller reused the successful HAC basecall, retried the rejected CPU reference check, and completed all four full native observations and eight fixed-domain scores. Original-parent processing is complete in every unit. Full canonical basecalls, alignments, and ledgers are equal; every numerical score field is equal.

The frozen full accuracy-artifact gate completed with a **different** result and CLI exit 1. Six alternate-alignment tables have identical headers and row multisets but different row order; 50 of 56 table files are byte-identical. This diagnosis does not alter the frozen endpoint. The experiment is complete with a retained failed literal-artifact gate, rather than an overall equivalence pass.

The completed-run resume and frozen read-only audit pass: 6,127 protected files are unchanged, and a complete process execution trace contains only uv and Python, with zero native producer launches. Final review and pins are summarized in [the qualification report](source-qualification-results.md) and [the full evidence manifest](../provenance/verification/source-qualification-full-20261023.json). Successful native producers and all rejected attempts remain retained. Comparative performance is not run. PR 1 remains unmerged.
