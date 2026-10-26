# Confidence-aware candidate decisions

F2 selects from an externally produced candidate union. It does not decode scores, generate graph paths, localize a read, or read truth. The initial implementation supports synthetic engineering qualification. Genuine F1 integration and biological qualification remain held.

## Design alternatives

One alternative puts location trust into F1's persistent beam rank. That can preserve alternatives during search, but couples policy to decoder state and changes the candidate union. Such an experiment cannot isolate a policy improvement from candidate generation.

The selected alternative uses a pure C++23 `decide(Batch, Policy)` boundary. F1 supplies frozen candidates with genuine marginalized neural likelihoods. F2 returns a candidate ID and assessments. Fixed and adaptive arms consume the identical raw batch FilePin. The separate JSON boundary validates provenance and availability before calling the numerical core.

For F1's state boundary, the alternative sent to Root retains one session with rolling released rows, independent free and contextual beams, CRF state, marginalized mass, and per-path edit-distance rows. `append(ChunkRelease)` advances only new released rows. `localize(EmittedPrefix)` updates locations for the next block. A common-prefix commit releases obsolete rows and prefix nodes. Only `finalize()` applies terminal rules. The existing guarded decoder's local `Item`, future-dependent `guide.b/q`, and right guards cannot establish this behavior. A replay-from-prefix window is a useful oracle but loses the persistent state required for an equivalent streaming decoder. F2 owns none of this decoder state.

## Candidate roles and policy

`reference_free_candidate_id` names the genuine independently advancing F1 free producer. `union_nn_candidate_id` names the actual neural argmax over the full supplied union. The core verifies the latter with native-first, sequence-lexicographic ties. These IDs can differ.

Disabled mode passes through the available native segment's SEQ and Q exactly. Prior-none selects the actual union neural winner and can edit. Fixed and adaptive modes use the genuine free candidate as their fallback and deficit baseline. An empty location set selects that genuine free candidate, even if the union neural winner differs.

For candidate `i`, `J_i = L_i - w * context_cost_i`. Context cost is the producer's nonnegative panel distance over every declared location. All candidates must bind the same location-ID set. The producer receipt must describe its graph paths and continuity treatment. Existing HPRC paths are already present upstream. This policy does not introduce the first graph prior.

Fixed mode preserves the original constants: weight 0.5, maximum neural deficit 0.5, and minimum objective improvement 0.5. It examines the top objective candidate and falls back if that candidate fails. Compatibility describes the decision rule on the supplied candidate map. It does not claim identical historical candidate generation, center-bound abstention, or completed calls.

Adaptive mode predeclares `w = 0.5 * min(location.support)` with a configurable maximum no greater than 0.5. Support is a declared heuristic in [0,1], never a posterior probability. Lowering any declared support cannot increase the weight. The genuine producer must freeze its support and haplotype-continuity recipe before science. This implementation does not derive or calibrate that feature from mapping quality.

Adaptive mode uses a maximum deficit of 0.5 from genuine free and a margin of 0.0. A changed candidate must still improve the objective strictly. It checks every candidate that meets the producer eligibility reasons, deficit, and margin constraints. It ranks eligible candidates by objective, then native identity, then sequence. It retains genuine free when no candidate qualifies. The external union may contain a stronger neural candidate, whose deficit from genuine free is negative.

The neural budget is relative to genuine free. When the union neural winner differs, this is not a 0.5 bound against that union winner. The prior-none arm measures that separate comparison.

The zero adaptive margin is an explicit new experiment. With support 1, free `L=0,cost=1`, and alternative `L=-0.25,cost=0`, adaptive admits the alternative's 0.25 objective improvement. Fixed rejects it because 0.25 is below 0.5. Weight adaptation alone would not repair that case.

A wrong confident reference can win within the 0.5 neural budget. The named wrong-reference control exposes that limitation. Private SNV, INS, and DEL controls with a 0.75 conflicting deficit retain the signal-supported allele. These synthetic controls cannot establish biological variant safety.

## Exact feedback-next/1 boundary

The executable takes `context-policy decide REQUEST EXPECTED_REQUEST_SHA256` with the worktree as cwd. The command's request hash is an independent admission pin. REQUEST contains exactly `schema`, `batch_pin`, `expected_binding`, `expected_batch_sha256`, and `policy`. `batch_pin` is an absolute `FilePin{path,size,sha256}` for exact raw UTF-8 JSON bytes. SHA256 excludes no fields because the batch has no self-hash. The independent expected hash must match the FilePin and actual bytes. Candidate permutations have different raw hashes and invariant semantic decisions.

A batch contains exactly these keys:

- `schema`: `feedback-next/1`.
- `kind`: `candidate-batch`.
- `binding`: the fields described below.
- `native`: `sequence`, `quality`, and `scope=available_input_segment`.
- `reference_free_candidate_id`: the genuine F1 free candidate.
- `union_nn_candidate_id`: the deterministic neural winner over the union.
- `locations`: the location records described below.
- `candidates`: the candidate records described below.

Binding contains exactly `source_sha256`, `plan_sha256`, `input_tensor`, `read_id`, `parent_index`, `chunk_index`, `block_index`, `availability`, `previous_state_sha256`, `prefix_sha256`, `prefix_length`, `orientation`, `location_producer`, `reference_free_producer`, and `identity_input`. Every `*_sha256` is 64 lowercase hexadecimal characters. The tensor, producer receipts, and identity input are absolute FilePins. Orientation is `forward` or `reverse`. The entire binding must equal the independently supplied expected binding, including source, prefix, state, input, and producer identities.

Availability contains exactly `kind=released-score-block`, `row_begin`, `row_end`, `available_row_end`, `chunk_lookahead=whole_chunk`, and `signal_geometry=null`. Row indices satisfy `row_begin <= row_end <= available_row_end`. Unknown sample geometry remains null. This is a released-score replay contract, not a raw-signal causality claim. Stronger availability kinds require a separately qualified sample geometry and an interface extension.

Each location contains exactly `id`, `contig`, `strand`, `query_begin`, `query_end`, `reference_begin`, `reference_end`, and `confidence`. Query endpoints are bounded by the available prefix length. Reference intervals are half-open and ordered. Strand is `+` or `-`. Confidence contains `feature=declared-location-support`, finite `value` in [0,1], and `meaning=bounded_support_not_probability`. The producer receipt fixes the feature recipe. Neither an uncalibrated margin nor MAPQ is interpreted as a posterior.

Each candidate contains exactly `id`, `sequence`, finite `neural_log_likelihood`, nonnegative finite `context_cost`, `location_ids`, `edits`, and `eligibility_reasons`. Empty eligibility reasons mean eligible for policy consideration. All IDs and sequences are unique. Every candidate uses all declared locations. Empty context requires zero context costs. Edits are ordered, non-overlapping records with exactly `operation`, `query_position`, `reference`, and `alternate`. Operation is `SNV`, `INS`, or `DEL`. Applying the declared edits to the native segment must reconstruct the candidate exactly.

Policy contains exactly `mode`, `maximum_context_weight`, `maximum_neural_deficit`, `minimum_objective_margin`, `parameter_status=predeclared_unfitted`, and `quality_status=uncalibrated`. The source rejects fitted or calibrated claims. Future fitting needs separate qualified inputs and a frozen parameter artifact.

The decision binds the exact raw batch SHA256, full binding, and policy hash. It returns both free and union IDs, selected candidate ID, SEQ, Q, reason, effective context weight, and per-candidate objective, deficit, and rejection reasons. Changed sequences get `!` throughout. Unchanged native sequences preserve supplied Q. No Q recalibration is claimed.

The boundary rejects duplicate JSON keys, unknown or missing fields, nonfinite numbers, stale raw bytes, rehashed foreign state, unavailable rows or prefix, missing candidate roles, inconsistent edits, and foreign location IDs. The executable also checks the compiled source census against actual source bytes and requires its compiled source root as cwd.

## Development and evaluation limits

`config/context-policy-dev-v1.json` predeclares the policy before outcomes. The existing 64 HG002 parents are exposed development data. Any five-way parent-hash split remains development diagnostics. No qualified fitting labels or genuine F1 candidate-batch pins exist at the initial cut, so fitting, Q calibration, and development execution remain unavailable. HG005 remains sealed.

A later matched policy ablation must preserve candidate union, likelihoods, all parents and exclusions, the 100 and 500 domains, error components, zero exposure, changed-footprint ALT, and parent and genomic-block technical bounds. The existing 100 productive ALT observations per class remain required. Candidate-generation gains require a separate experiment. Engineering controls do not qualify complete input processing, biological accuracy, runtime performance, or promotion.
