# Growing-read prefix loop design

Status is source preparation. Build, tests, mapper and scientific executions are 0.

## Workflow

1. Ground. Read the frozen decoder, mapper frame constructor, DGS reader and native stitch boundaries.
2. Sketch. Compare the two complete shapes below before implementation.
3. Agree. Select the persistent shape on engineering and information constraints. F2 supplies its independent sketch through Root. No nested agents are authorized.
4. Implement. Own the session, candidate producer and orchestration in the F1 paths.
5. Scrap. Replace the shape if a genuine fixture cannot bind each query, retained position and next-block state without completed calls.

## Existing flow and limits

PR15 is read-only at 400063e97c476303c6a113fb0aab5d0698f0984f. Its `tools/uncertainty_feedback/src/plan.cpp` reads a completed native SAM, then joins completed DGM SEQ/MOVES and parent Q. `frames.cpp` 183-260 derives a native initial k-mer, ten future bases and a right guard. `tools/context_decoder/src/guarded.cpp` 51-85 creates backward completion guides. That input cannot be relabeled online.

Native Dorado `dorado/basecall/decode/beam_search.cpp` initializes from backward guides and uses future guides while pruning. `dorado/read_pipeline/base/stitch.cpp` gives each adjacent overlap's rear floor-half to the next chunk and its remaining front portion to the current chunk. These are timestep ownership boundaries. F1 computes them from chunk offsets, raw sizes, stride and total signal length, never native emission counts. A persistent forward state crosses the seam. This is a new score-domain decoder, not native beam or native chunk-reset parity.

A saved DGS chunk already includes within-chunk reverse recurrence. F1 releases only declared score rows after that chunk's declared signal endpoint. All reports call this chunk-delayed saved-score replay. F1 makes no raw-acquisition or zero-lookahead claim.

## Caller usage first

```cpp
Session s{SessionSpec{read_id, source_hash, plan_hash, k, stay, policy}};
// Uniform log prior over all 4^k CRF states. No selected native k-mer.
auto batch = s.advance(released_block, std::nullopt);
auto query = batch.provisional_prefix; // real current conditioned prefix
// Real minimap2 sees exactly this query, its length and hash.
LocationUpdate update = mapper(query, batch.state_hash, batch.available);
batch = s.advance(next_released_block, update);
```

The wire producer emits `feedback-next/1`. A batch binds source and plan hashes, read and parent ID, chunk/block, tensor pin, owned row interval, available score/signal endpoints, declared chunk lookahead, previous state hash, orientation, exact mapper receipt and all retained positions. Candidate IDs derive from sequence and batch identity. Each candidate has its exact marginalized neural likelihood over consumed rows, contextual search mass/cost, eligibility and edits relative to the independently advancing signal-only output. F2 chooses a candidate by whole-batch hash. F1's provisional choice only supplies the next mapper query and does not claim calibrated confidence.

## Shape A. Persistent joint sequence/location beam

One session owns two forward beams. The free beam advances on every owned row without a context parameter. The contextual beam retains sequence, CRF state, current location channel and weighted log mass. At a mapper update, marginalize the old location channels and redistribute their masses over the new retained positions with an explicitly uniform location prior. Each new emitted base pays a position-specific mismatch penalty against that channel's read-oriented reference continuation. Stays pay no context penalty. Channel exhaustion makes the channel neutral and records a bound. Missing mappings make all channels neutral. Position changes and competing locations remain explicit in the update history.

Beam pruning acts on complete sequence groups, after marginalizing their CRF/location channels. Ties use lexical sequence order. No future rows or backward scores enter ranking. A separate exact forward scalar recomputes each finalist's neural mass over the already consumed rows. This distinguishes search pruning from the reported neural likelihood and avoids counting duplicate location channels as additional neural paths.

The mapper query is the current contextual winner. All retained positions must map exactly that query. They are not pretended to align each other sequence in the beam. Context is only applied to future emitted positions at or beyond the mapped query length. This is an explicit shared-prefix proposal prior, with no posterior-location claim. Prefix strings remain provisional and may be revised between updates. No immutable base-emission API is exposed.

Cost is bounded by beam width, location cap, symbol cap and released rows. State persists across block boundaries, which makes identical-policy split stepping an exact check. Tiny unpruned enumeration can independently count all strings and all stay/emission paths.

## Shape B. Rolling undecided suffix

Commit a stable common prefix, retain a suffix score window and its complete CRF-state distribution, remap the provisional prefix, and redecode the undecided suffix at every update. This can revise past suffix bases more directly. Its public operation would be `revise(ReleasedWindow, PrefixLocation, CommittedCut)` and return a new committed cut plus suffix beam.

This shape also needs custody for the old cut's state marginal, score replay endpoints, overlap ownership and a rule proving discarded paths cannot change the committed prefix. A fixed lag alone does not prove commitment. Whole-window rescoring risks counting rows twice and can silently use the new map on old emissions. Exact split-step equivalence becomes conditional on replay and commit policy. A safe initial implementation would need an explicit no-commit mode, leaving more state than Shape A.

## Choice

Choose A. It has one row-ownership rule and no score replay or commitment claim. Real current prefix mapping affects the next partial expansion. The free path cannot inherit contextual pruning. B is rejected for this unit because its committed-cut proof and replay state add risk without creating new available information. This decision does not use HG002 truth or HG005.

The model-the-domain principle changed the organizing structure to a session with a consumed-row cursor, rather than independent fixed-window decodes. The architect red-flag screen rejected split writers for state and two independent inference paths. Python only binds metadata and external commands. Numerical search, scalar marginalization, CIGAR projection and edit reconstruction are C++23.

## Explicit first-cut limits

The first pilot uses four contiguous 128-row releases from the lexically first metadata-eligible HG002 parent, with at least three real prefix mappings before subsequent releases. All releases wait for the complete first chunk's signal endpoint. This gives matched availability to signal-only, fixed-context rerank and partial-feedback. It is a prefix mechanism pilot, not complete-parent accuracy or speed evidence. A future complete-parent run requires separate admission.

The disabled parent SEQ/Q identity check belongs to a separately admitted output-control stage. Parent native calls may be read there as outputs to preserve, never into inference. F3 owns broader indel proposals and F2 owns trust decisions. Integration consumes frozen sibling commits only after Root supplies pins.
