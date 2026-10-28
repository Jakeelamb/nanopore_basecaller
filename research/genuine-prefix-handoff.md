# Genuine block0 handoff

The companion consumes `genuine-prefix-first-advance/1`, including its original `prefix-stage-receipt/1`. It calls unchanged F1 `emit-free-input`, F1 `normalize`, F3 `nominate-prefix`, F1 `merge-indels`, and four F2 `decide` commands. The existing `joint.Stages` recorder owns each child command, clock, raw stream, terminal cleanup proof, and receipt. There is one production script and no continuation engine.

## Invoke the admitted worker

The controller freezes the companion commit and authors the closed spec before a fresh F4 grant. Run the payload from `/home/jake/Projects/nanopore_basecaller-next-prefix-loop`, abbreviated F1 below.

```sh
UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run \
  --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python \
  /home/jake/Projects/nanopore_basecaller-completion-20261028/scripts/genuine-prefix-handoff.py \
  --spec ABS_SPEC --spec-sha256 SPEC_SHA256 \
  --output F1/results/prefix-feedback/FRESH_ATTEMPT
```

This is the worker payload, not a direct execution grant. `io.admitted_worker()` requires F1 cwd and the existing F4 service cgroup. The unchanged public F4 `bounded.py run --request ABS_GRANT --request-sha256 SHA --output FRESH_OUTER` owns the canonical NONBLOCK host lock, service, environment, caps, and output monitoring. Use its engineering profile and existing limits. No lock, service, grant, scheduler, native rebuild, or neural replay is added here.

All child outputs remain under the fresh F1 result directory. F2 cwd is `/home/jake/Projects/nanopore_basecaller-next-context-policy`. F3 cwd is `/home/jake/Projects/nanopore_basecaller-next-indel-decoder`. Their binaries and source pins are external spec operands. Existing attempts, including empty directories, refuse overwrite.

## Build the closed spec

Every FilePin is exactly `{"path": "ABS", "size": INTEGER, "sha256": "HEX64"}`. The top-level fields are exactly these.

| Field | Value |
| --- | --- |
| `schema` | `genuine-prefix-handoff-spec/1` |
| `advance_spec` | FilePin of the controller's frozen `advance-spec-02.json` |
| `advance_complete` | FilePin of the completed helper's `complete.json` |
| `expected_producer` | Independently supplied FilePin of that advance's `stage-0/receipt.json` |
| `f1`, `f2`, `f3` | Unchanged qualified executable FilePins |
| `f2_cwd`, `f3_cwd` | Exact canonical sibling directories above |
| `source_pins` | Unique FilePins of the companion, loaded recorder modules, guard, F4, and complete frozen native dependency closures |
| `f3_source_files` | Exact ordered F3 compiled source witness pins, also present in `source_pins` |
| `source_sha256` | F1 compiled source-witness hash, not a Git commit hash |
| `expected` | Independently pinned read, parent, block, endpoint, and previous-state fields below |
| `policy` | Exact predeclared policy object below |

`expected` contains exactly `read_id`, `parent_index`, `chunk_index`, `block_index`, `row_begin`, `row_end`, `previous_state_sha256`, and `plan_sha256`. For this first unit, parent/chunk/block indices and row_begin are zero. `row_end` is the retained first release endpoint in 1..512. `previous_state_sha256` comes from the completed snapshot and identifies the initial native state. It is a hash even though the advance request's `state` and `expected_previous_state_sha256` are null. `plan_sha256` is the plan's session/config identity, not the FilePin hash of `plan.json`.

```json
{
  "maximum_context_weight": 0.5,
  "maximum_neural_deficit": 0.5,
  "minimum_objective_margin": 0.5,
  "parameter_status": "predeclared_unfitted",
  "quality_status": "uncalibrated"
}
```

The four mode-specific requests use this policy. Only fixed keeps margin 0.5. Adaptive, prior-none, and disabled use predeclared margin 0.0, matching the existing native joint consumer.

Wait for the controller to certify that the first advance task finished before inspecting its artifacts. The expected retained root is `F1/results/prefix-feedback/genuine-first-advance-20261028-02`. Pin its `complete.json` and `stage-0/receipt.json`. Obtain the plan from `advance-spec-02.json`; match its selected parent and first block against the actual snapshot and state. Supply the actual previous-state hash independently in `expected`. Never substitute another parent on abstention, cap exclusion, or failure.

The intake reconstructs only the original fixed `advance` request and exact producer argv, cwd, environment, source/input/output pins, known exit, cleanup, and clocks. It checks k4, the first-block endpoints, retained empty context, snapshot identity, and the compiled source witness. It does not invent an F4-to-native projection. The native bridge independently restores the original state and checks the producer again. Extra spec/plan fields, holdout labels, changed policy, foreign parent, stale state, and changed endpoints refuse admission.

## Freeze the dependencies

F1 source remains at base `666e56ccca2274ef974790640277b5684dce557a`. Its compiled closure remains `tools/prefix_feedback/source-files.json`, plus the original CMake witness dependencies. The companion is outside that closure and must be independently pinned in F4 and `source_pins`.

The planned unchanged binaries are recorded below. These identities come from the completed frontier report and frozen advance spec. This implementation task did not rehash or execute the binaries. Admission verifies the actual bytes.

| Component | Canonical result path | SHA256 |
| --- | --- | --- |
| F1 | `results/prefix-feedback/resource-qualification-01/build/prefix-feedback` | `84f89ca38c361a7534dd0222c7fb8b25a1c1581fefeeadd0969604426f23aae5` |
| F2 | `results/context-policy/qualification-04/build/context-policy` | `f4c5ad6943377002048189df55d93328010a4d1eb06eaf590f5654ac1235b3f3` |
| F3 | `results/indel-feedback/prefix-qualification-01/build/indel-feedback` | `c69e9a4a32e3c0defb1d930282076d4efe80e173c863fd9da65fe99734bcef73` |

Use each sibling's complete existing qualification closure, including its compiled source witness and exact dependencies. Do not replace F3's `source_files` order with a sorted or partial list. Include canonical F1 `bounded_cli.py`, `joint.py`, `qualification.py`, `io.GUARD`, and `io.F4`. The fixed UV project supplies the existing interpreter. There is no new dependency or environment manifest.

## Inspect the results

A complete included handoff has exactly ten stage receipts under `records/stage-0` through `records/stage-9`. Stages 0..3 are emission, normalization, nomination, and merge. Stages 4..7 are fixed, adaptive, prior-none, and disabled. Stages 8..9 are intentional F3 foreign-read and stale-previous-state refusals with exit 1. Their altered batch files and requests are resealed. Their independently expected binding remains the original binding. The consumer also checks the specific binding-refusal diagnostic and absence of a sidecar.

The expected success census is 87 files.

- Each stage retains six files, `command.json`, `terminal.json`, `receipt.json`, `stdout`, `stderr`, and `time.txt`. Total 60 files.
- `records/request-0.json`, `records/request-1.json`, and `records/request-3.json` retain the three F1 requests.
- `emitted` contains `tensor.dgs`, `panels.json`, `identity.json`, `emission.json`, and `complete.json`.
- Each of `normalized` and `merged` contains `batch.json`, `descriptor.json`, `report.json`, and `complete.json`.
- The result root contains `nominate-request.json`, `nominate-sidecar.json`, and four `decision-MODE-request.json` files.
- Each of `foreign-read` and `stale-previous-state` has a `-batch.json` and `-request.json` file at the result root.
- The result root's `complete.json` is written last. `records/tmp` is the recorder's temporary directory and has no declared output files.

F2 decisions remain actual pinned stage stdout records. The summary records H and U independently, equality, original/final counts, additions, and pins to the raw merge report, sidecar, batches, decisions, controls, and retained advance. It permits H==U and zero additions. It checks unchanged original candidate objects, including their scores, costs, edits, and eligibility. Prior-none must select actual U. Disabled must preserve exact available H sequence and quality. Empty-context fixed and adaptive must select H.

An abstained snapshot produces a completion with zero stages and `transport_qualified=false`. An overlong available H produces native `arm-excluded.json` and completion through one emission stage, also unqualified. F3 and merge cap exclusions remain recorded in their unchanged raw reports; they do not qualify transport. No clipping, parent refill, parameter tuning, or fallback occurs.

On failure, `failed.json` pins completed receipts, every retained stage file, generated payloads, and exact request recovery operands. It preserves successful upstream work and any exit-0 projection gap. There is no automatic reuse or rerun. A separately authorized recovery must authenticate the retained fixed-stage operands. Unknown exits and incomplete cleanup remain held. No completed manifest is emitted on failure.

## Evidence limits

F1 retains the exact uniform-all-CRF-states, consumed-prefix scalar scorer. F3 nominates unscored last-32-base indels. Its full-prefix limit is 512 bases, consumed-row limit 2048, unique-addition limit 512, result length 1..514, and complete union limit 4096. All native exclusions and impossible-mass exclusions stay intact. The companion changes neither scoring nor policy math.

Block0 has empty context. Success qualifies transport only. Whole-chunk saved-score lookahead remains disclosed. There is no acquisition-causal inference, complete-parent stitching, whole-read output qualification, calibrated quality, native-stock quality, biological accuracy, performance, or promotion claim. The existing private-insertion erasure failure remains an unresolved scientific gate. This companion does not establish an improving caller.

The local unit tests check closed spec parsing, dependency refusal, tampering, foreign/stale bindings, candidate preservation, fresh-attempt refusal, and failure evidence retention. They run with fixed retrieval UV under a 60-second bound and canonical NONBLOCK host lock. They use metadata fixtures and never simulate successful native acceptance. The controller must run genuine native integration separately after freezing the source.
