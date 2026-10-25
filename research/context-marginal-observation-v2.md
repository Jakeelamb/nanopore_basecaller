# Observe the fixed marginal context policies, version 2

This separate observer consumes sealed inference outputs from `tools/context_decoder/model/`. It joins the C++ atlas labels after every model score and decision has been sealed. It never selects a model, changes a gate, scores a sequence, or constructs a truth-selected output. The scorer's frozen 40-file inventory remains `54e022509ac9735381bd4da1408190c64a5495d183c790dfc50c0442139bb664`. The observer is outside that compiled census and has its own source pin and qualification.

The unversioned observer, its 38-test cut, failed annotation, and original protocol remain unchanged at their original paths. Version 2 corrects only the observer's self-baseline classification assumption and names profile and decision counts separately.

The model run covers 368 lexical case IDs in three disjoint units. Query0 owns index 0. The checkpoint owns indices 1 through 31. The full unit owns 32 through 367. The observer verifies the exact union before reading labels. All eight profiles use mutation rates 0.001 or 0.01 and graph, reference, none, or foreign context. These are fixed exposed-development policies, not selected candidates or independent confirmations.

## Source and receipt contract

`tools/context_decoder/model_observe_v2.py` provides `load_corpus()`, `annotate(corpus, output)`, `emit(corpus, output)`, and `completed(completion_pin, phase)`. The CLI has `annotate` and `emit` phases. An external whole-worker supervisor owns admission, canonical locking, clocks, raw recording, resource stops, and terminal-tree cleanup. The observer invokes no sequencing executable or child process.

The model source, compiler/runtime closure, engineering controls, outer terminal and launcher cleanup, eight raw recorder files, native attempt, consumed input, output files, declared batches, and exact case coverage are revalidated. Outer raw stdout binds each otherwise-unanchored unit completion. The source guard imports the v4 controller and original v2 observer at their actual absolute locations. It never reassigns ROOT or relaxes cwd checks. Existing model and native producers remain unchanged.

Every model arm must contain the complete native-plus-escape sequence pool and the exact saved neural doubles. Candidate, parent, case, geometry, context assignment, model parameters, pool digest, raw choice, accepted choice, and score-component rows must agree. None preserves the matched reference-free choice. It can legitimately differ from the original native call.

`annotate` joins model choices to qualified `v4-evaluate-all-1/native-atlas/candidates.tsv` and `private.tsv` by exact case and candidate digest. No alignment or haplotype comparison is reimplemented. Raw and accepted effects remain separate. Helpful, harmful, neutral, unexposed and unresolved local effects remain separate. An identical reference-free self-baseline can remain unresolved when its boundary is ambiguous. A helpful or harmful self-baseline rejects. Private exact ALT-to-REF, loss of an exact ALT match to other sequence, and unresolved calls remain separate. Event rows and repeated context modes do not become independent biological observations.

`emit` reconstructs each of the eight ordinary-policy outputs across all 64 original parents. It validates every one of the 311 ordinary owned centers, applies only actual accepted sequence changes, and leaves all other bases and qualities unchanged. Private diagnostic frames are not added to these edits. Both None profiles must reproduce the historical reference-free SAM byte-for-byte. An explicit disabled-edit SAM preserves the original native SEQ and Q exactly.

The emitter uses the original `splice` and independently ordered `independent_splice` functions. Changed centers receive uncalibrated `!` qualities, as in the maintained comparator. No-op ledger entries reject, so a disabled edit cannot silently change Q. Duplicate or overlapping edits reject. Output byte equality creates an explicit alias to one canonical SAM. An identical historical reference-free output can reuse its original mapped producer. An alias never creates a new mapping receipt.

## Exact prospective CPU qualification

The prior observer cut passed 38 controls, then genuine annotation failed before output because it incorrectly rejected an unresolved self-baseline. That failed attempt and its source snapshot remain retained. The current source correction and following commands are unexecuted. Run each inside the coordinator's exact pinned supervisor with fresh nonblocking canonical host-lock intake. CPU limits are 300 seconds, two CPUs, 4 GiB memory, 8 GiB address space, zero swap, a declared 256 MiB aggregate output threshold, and 30 GiB free disk. The threshold includes the already-retained model outputs in this worktree. A successful engineering qualifier requires all 40 methods and zero skips.

```sh
cd /home/jake/Projects/nanopore_basecaller-context-feedback-v5
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  CONTEXT_MODEL_OBSERVER_FIXTURE=1 \
  uv run --no-sync python -m unittest discover -s tests -p test_context_model_observe_v2.py -v
```

The hermetic controls reject missing profiles, omitted candidates, changed neural values, geometry mismatches, duplicate joins, missing files, no-op Q changes, overlapping edits, wrong stock attachments, corrupt raw commands, missing recorder fields, and incomplete parent accounting. They preserve unresolved self-baselines and reject helpful or harmful self-baselines. The consumed fixture controls validate the actual 368-frame and 2944-decision handoff, byte-identical None reconstruction, and read-only injection of a missing genuine native result. A full smoke control executes both actual annotation and emission CLI entrypoints and revalidates their completions. Annotation reports eight profiles and 2,944 decisions separately. A default skip is not accepted qualification.

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/context_decoder/model_observe_v2.py annotate \
  --output results/context-feedback/DECLARED-model-annotation
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/context_decoder/model_observe_v2.py emit \
  --output results/context-feedback/DECLARED-model-emission
```

The actual output directories must be fresh. Completion is written last and synced, not rename-atomic. The external recorder and terminal receipt preserve a failure if a source, input, projection, or native-proof check raises. Repair a retained observation when possible. Do not rerun a scientific producer to replace a projection failure.

## Native whole-parent observation commands

Native mapping and truth scoring are later separately bounded units. The original snapshot is `/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json`, SHA256 `f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324`. Every consumed snapshot pin and tool must be checked before execution. The original observer implementation is `/home/jake/Projects/nanopore_basecaller-context-feedback-v2/tools/context_decoder/observe.py`. Its `worker` function supplies the maintained command contract. Its old manifest schema and arm names cannot be forged to admit these new outputs.

For each unique canonical SAM that does not already match a qualified historical mapping, the actual stage argv is as follows. Names in capitals are values obtained from the pinned emission or snapshot, not shell defaults.

```text
SAMTOOLS view -b CANONICAL_SAM
DORADO aligner INDEX PREVIOUS_BAM_STDOUT --threads 2 --no-sort --mm2-opts "-x lr:hq -I 16G --eqx -Y"
SAMTOOLS view -h PREVIOUS_ALIGNED_STDOUT
PAIRER score --reference REFERENCE --eligible ELIGIBLE --left LEFT_MAPPED_SAM --right CANDIDATE_MAPPED_SAM --parents PARENTS --output PAIRS_OUTPUT
PAIRER summarize --pairs PAIRS_OUTPUT --selected all --output SUMMARY_OUTPUT
OBSERVER observe --reference REFERENCE --vcf TRUTH --confident CONFIDENT --sam CANDIDATE_MAPPED_SAM --parents PARENTS --output ALLELES_OUTPUT
OBSERVER compare --baseline BASELINE_OBSERVATIONS --candidate ALLELES_OUTPUT --output COMPARISON_OUTPUT
```

Run the score and summarize pair for both fixed eligible domains 100 and 500. Use native and, where different, historical reference-free mappings as the two left comparators. Preserve all 64 complete parents and check mapper SEQ/Q against the emitted SAM. The snapshot binds Dorado `08fef6060d9672f1e7b1772470b93ff0750d28d15f2e64cef1d02533a03ebb49`, samtools `e839773cc27090fa109588cae8b8240b0d48de816a25b962045867a4c3b7e1ff`, pairer `e1bfe5f55a1c6c4b6e74a3622ac991f0b5860ea4695de805fff287ad74fa4979`, observer `6a328b715c98aa30dc3489b2d75a0c3659b91bd6dbde29dbb29e2999ea7b9ba4`, and the whole-reference index `611b2a45bc41e8bbd3048ef96efebcfae4cf611360d81c3553285932de4a63aa`.

Proposed native unit limits are 300 seconds, two CPUs, 16 GiB kernel memory, 24 GiB address space, zero swap, an explicitly priced output stop threshold and 30 GiB free disk. Whole-reference mapping previously exceeded 4 GiB. Each unique output needs an actual successful producer and raw command closure; CPU engineering does not qualify it. Resource limits reject or retain a failed unit rather than silently dropping arms or parents. Canonical aliases require validated byte equality and the same snapshot before reusing any retained mapping or observation.

The local annotation is not whole-parent accuracy. New calling policies still need the unchanged 1% target in both domains, technical parent/block uncertainty, complete accounting, and useful variant-bearing edit support. The two masks share parents. Private stress modes share events. Neither is fresh biological confirmation. This unit does not implement live partial-path feedback, qualify causal-prefix scores, establish allele safety, or close the catalogue bridge.
