# F3 consumed-prefix unscored nomination

Status: new source prepared, unformatted and unexecuted. The previous conditional-mode engineering evidence at `352a749242e89bbbb4fd4b244dee996de1c210e9` remains valid only for its old source/artifact. No normalization or cross-lane integration has been qualified for this new mode.

## Ownership and modes

`indel-feedback nominate-prefix REQUEST EXPECTED_REQUEST_SHA256 NEW_OUTPUT` consumes absolute metadata paths from the canonical F3 source cwd. NEW_OUTPUT may be a fresh absolute file under a separately admitted F1 results root. This CLI writes only that file. Root's frozen F4 boundary owns admission, limits, output monitoring, cleanup and the lock.

This mode performs no likelihood or context scoring. It has a separate `UnscoredProposal` type with no score member. Existing `propose`, conditional fixed-initial-state `Frame` likelihood, DGM/MOVES input and fourteen original control groups retain their existing behavior. F1 owns its one uniform-prefix scalar, reference-panel costs, edit normalization, union merge, union neural winner U and full-parent emission. Its genuine independent reference-free H remains distinct from U.

## Exact request and metadata

Request has exactly these keys:

```json
{
  "schema": "indel-prefix-nomination-request/1",
  "mode": "consumed-prefix-unscored-v1",
  "batch_pin": {"path": "ABSOLUTE_BATCH", "size": 0, "sha256": "RAW_BATCH_SHA256"},
  "expected_batch_sha256": "INDEPENDENT_RAW_BATCH_SHA256",
  "expected_binding": {},
  "scoring_descriptor": {},
  "expected_scoring_descriptor": {}
}
```

The uppercase strings and empty objects above are unresolved illustrative operands, not an admissible fixture. The CLI's independent request SHA covers exact raw request bytes. FilePins use canonical absolute regular non-symlink paths, exact size and lowercase64 SHA256. Request/batch/identity JSON metadata are bounded to8MiB per file. Batch and identity raw bytes are hashed and rechecked; the input tensor and other producer receipts receive metadata/descriptor binding only in F3. F1 and the admitted outer chain must authenticate and consume those bodies under their own role pins.

The batch is exact `feedback-next/1` candidate-batch shape. Native contains only `sequence,quality,scope`, with scope `available_input_segment`. Its sequence is the current available pipeline-free identity, not completed DGM SEQ. F3 validates the complete independently expected binding, all source/plan/state/prefix hashes, read/parent/chunk/block identity, orientation, FilePins and availability. Prefix SHA/length mean SHA256/length of this current identity sequence. F3 requires row_begin0 and row_end=available_row_end. Geometry stays null and lookahead is declared whole_chunk. Older localization coordinates remain F1 producer-chain facts.

Descriptor has exactly:

- `schema=consumed-prefix-descriptor/1`, `prior=uniform-all-states`, integer `state_length`1..4.
- `row_begin,row_end,available_row_end`, exactly matching the binding's consumed availability.
- `source_sha256,plan_sha256,input_tensor`, exactly matching binding.
- `producers`, exactly `location_producer,reference_free_producer,identity_input`, each equal to its binding FilePin.

The entire descriptor must equal the independent expected descriptor. F3 does not enumerate CRF states or convert a conditional prior. Extra DGM, MOVES, initial-context, future-SEQ, score or other request fields reject.

The actual identity_input JSON has exactly `schema,kind,quality_status,source_sha256,plan_sha256,input_tensor,read_id,parent_index,chunk_index,block_index,availability,previous_state_sha256,prefix_sha256,prefix_length,orientation,sequence,quality`. Schema is `feedback-prefix-identity/1`, kind `pipeline-free-input`, and quality_status `uncalibrated`. Every copied binding field must match. SEQ/Q match native exactly, every Q character is `!`, and prefix SHA/length match SEQ. The identity artifact excludes its own FilePin to avoid self-hash recursion. F1 must actually produce this free-mode identity before guided selection; these declarations alone cannot establish that provenance.

## Nomination and result

The declared whole-prefix bound is1..512 bases and consumed rows1..2048. The deterministic nomination tail is `[max(0,L-32),L)`. It is a declared algorithm window, not resource-based clipping. Emit all single-base deletions and A/C/G/T insertions in that tail, plus visible maximal homopolymer replacements at lengths1..6 within±2 of the visible run length. A run crossing tail_begin is not expanded by the run-length mechanism and gets explicit `left-open-run` provenance. Single indels remain eligible. Empty results get per-mechanism `empty-result` exclusions.

Every edit uses full-prefix coordinates and the supplied sequence orientation. Reconstruct the entire proposed prefix before deduplicating. Preserve all bases before the tail. Deduplicate by full sequence, omit sequences already in the original candidate set, sort by sequence, and use `prefix-indel-` plus SHA256(sequence) IDs. Output results have1..514 bases. Any full-prefix, row or512-new-unique bound failure excludes the whole new arm with empty proposals and reasons; there is no truncation or refill. The512 count guard is unreachable under the current32-base single-indel/run grammar, so no executed512-overflow control is claimed.

Response keys are exactly `schema,mode,scoring_status,status,source_batch,binding,scoring_descriptor,reference_free_candidate,tail,limits,counts,arm_exclusions,exclusions,proposals`, followed by standard CLI `request_sha256,source_files,complete`. Schema is `indel-prefix-proposals/1`, scoring_status `unscored`, status `ready` or `excluded`. H echo contains only `id,sequence,source_batch_sha256`; F1 preserves its original scored record separately. No likelihood, context cost, U, selected output or Q fields are emitted.

Each proposal has `id,sequence,edit,mechanism`; edit has `query_begin,query_end,reference,alternate`. Counts satisfy `visited=eligible+excluded` and `eligible=unique+duplicate`. Duplicate includes original-candidate matches, separately counted as original_duplicates. Each concrete edit is one visit; a tail-open run contributes one skipped-mechanism visit and exclusion record.

## Prepared acceptance and future integration

Prepared CTest census is2 tests: old `indel_controls` with its14 named groups, and `indel_prefix_controls` with6 new groups. UV census is17 methods, retaining all7 existing methods and adding10 prefix metadata/consumer methods. New controls cover full reconstruction, candidate-order invariance, exact bounds and whole-arm exclusions, tail-open/empty provenance,132 unique strings without an old128-count clip, prior/hash/binding/identity rejection and no tensor/other-producer body dependency. All require skipped0. These are source-prepared controls; none has run.

Before build, Root must admit formatting exactly:

```sh
/usr/bin/clang-format -i tools/indel_feedback/include/indel_feedback/core.h tools/indel_feedback/src/main.cpp tools/indel_feedback/src/prefix.cpp tools/indel_feedback/src/prefix_controls.cpp
```

After refreeze, the proposed full engineering child is:

```sh
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python tools/indel_feedback/qualify.py --output /home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/prefix-qualification-01
```

Use fixed offline retrieval UV environment, in-root TMPDIR and a fresh Root grant: whole wall300s, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, aggregate4GiB, reserve30GiB, canonical NONBLOCK lock. Formatter can use a separate30s unit with the same resource profile. All numerical source is C++23. No new environment, download, GPU or scientific body read is requested during preparation.

A later fresh admitted positive/rejection chain must consume a real F1 normalized batch, invoke this frozen F3 binary from F3 cwd, return the sidecar to F1's monitored output root, score with F1's exact uniform-prefix scalar, normalize edits/costs/U, and invoke F2. All raw bytes, expected bindings, prior/consumed descriptors, genuine free identity and source cuts must be frozen first. Synthetic fixtures do not establish genuine F1 normalization. Private/genuine science, full processing, calibration, accuracy, variants, speed and promotion remain held.
