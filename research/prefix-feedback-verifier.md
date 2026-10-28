# Resume the frozen genuine prefix experiment

`scripts/verify-prefix-feedback.py` provides two fixed verification operations after accepted block0. `locate` consumes a sealed snapshot from block0, 1, or 2. `advance-next` consumes its completed location update and advances block1, 2, or 3 once. It refuses advance0. This is an experimental verification path.

The driver imports canonical F1 `scripts/prefix-feedback.py` with importlib and uses its unchanged `locate`, `bounded_cli.RetainedCommands`, and `joint.Stages.f1`. It adds no decoder, scorer, supervisor, receipt conversion, scheduler, dependency, or environment. Existing `normalize` owns legacy receipt projection. The accepted block0 producer is never replayed.

## Payload and admission

F1 is `/home/jake/Projects/nanopore_basecaller-next-prefix-loop`. The payload cwd is F1. Root supplies the existing F4 outer `bounded.py run` unit, source and input pins, monitored result roots, and canonical NONBLOCK host lock. `io.admitted_worker()` runs before worker body work. This CLI does not grant execution authority.

```sh
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 \
  /home/jake/.local/bin/uv run \
  --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python \
  /home/jake/Projects/nanopore_basecaller-completion-20261028/scripts/verify-prefix-feedback.py \
  --spec ABS_SPEC --spec-sha256 SPEC_SHA256 --output FRESH_F1_RESULT_DIRECTORY
```

Only these three flags exist. Every invocation needs a fresh output directory directly or indirectly under `F1/results/prefix-feedback`. Existing empty and partial attempts refuse overwrite. Locate work uses a separate fixed directory under the same monitored root. The helper retains the existing engineering profile of 4 GiB RAM and 8 GiB address space. Actual mapper execution needs a separate F4 mapping grant with 16 GiB RAM and 24 GiB address space. Existing CPU, wall, disk, swap, and reserve bounds remain unchanged.

## Closed spec

A FilePin is exactly `{"path":"ABS_CANONICAL_PATH","size":INTEGER,"sha256":"LOWERCASE_HEX64"}`. Root supplies the independent SHA256 of the entire spec. Unknown spec, expected-binding, retained-input, next-block, config, and execution-index fields refuse admission.

The common spec fields are exactly these.

| Field | Meaning |
| --- | --- |
| `schema` | `prefix-feedback-verifier-spec/1` |
| `operation` | `locate` or `advance-next` |
| `plan` | Original prepared `plan.json` FilePin |
| `binary` | Unchanged F1 executable FilePin |
| `source_sha256` | Compiled source identity listed below |
| `source_pins` | Unique FilePins for this driver, canonical F1 script, bounded_cli, joint, qualification, guard, F4, compiled witness sources, and frozen dependency closure |
| `retained` | Exactly `state`, `snapshot`, `complete`, and `producer`, each a FilePin. `complete` is native advance completion. `producer` is its strict stage-0 receipt |
| `predecessor_sources` | Exact ordered `source_pins` from that producer's actual command, independently supplied |
| `expected` | Independent binding fields below |

`expected` has exactly `read_id`, `parent_id`, `chunk_index`, `block_index`, `row_begin`, `row_end`, `available_score_end`, `available_signal_end`, `plan_sha256`, `previous_state_sha256`, and `state_sha256`. Parent and read IDs match the frozen selected parent. Chunk index is 0. For retained block n in 0..2, rows are `[497*n,497*(n+1))`, available score end is the row end, and available signal end is 12222. State IDs are native canonical JSON hashes, distinct from FilePin hashes. `previous_state_sha256` comes from the retained snapshot. `plan_sha256` is the config/session identity below, distinct from the plan file hash.

Locate adds exactly `work_directory`, an absolute fixed directory, and `execution_index`, a FilePin of `prefix-command-index/1`. That index has exactly `schema`, `source_pins`, and `commands`. Each command entry has exactly `proposal` and `complete`, both FilePins. Root owns it. Its immutable source closure includes F4, the decoder, mapper, samtools, and every plan `producer_sources` pin. Start with an empty command list. Appending accepted receipt pairs changes the index pin and spec hash, but leaves the source closure and work identity unchanged.

Advance-next adds exactly `location_result`, `update`, and `next_block`. The first two are FilePins of the completed locate result and its exact `prefix-location/1` JSON. `next_block` is exactly `{"block_index":n+1,"row_begin":497*(n+1),"row_end":497*(n+2)}`. It cannot change the frozen next plan block. The native request carries the actual retained state Pin, returned update object, and `expected_previous_state_sha256` from the retained snapshot's `state_sha256`.

Before query creation or proposals, admission checks the actual plan/config pins, config role `development-HG002`, `hg005_selection:false`, `truth_input:null`, and `promotion:false`. It checks the selected parent, k4 session and fixed policy, all four release ownership ranges, consumed state, snapshot bindings, compiled witness, and exact original producer command, environment, inputs, outputs, source closure, clocks, exit, cleanup, and raw pins. UUID text is never used to infer a sample role. No truth or completed native SEQ operand is accepted. No parent refill or parameter change exists.

## Instantiate the first locate

All values below come from small retained metadata inspected for this implementation. Native binaries and scientific data bodies were not rehashed or executed in this task. Runtime admission verifies consumed bytes.

| Operand | Accepted identity |
| --- | --- |
| Plan | `F1/results/prefix-feedback/genuine-prepare-20261028-01/plan.json`, size 66585, SHA256 `5ee39340d675d8313e385fded9c4036d89a6c5649b72fe143bb22691b2cc08ee` |
| Config/session | `/home/jake/Projects/nanopore_basecaller-retrieval/logs/completion-herdr-20261028/development-config-resource-03.json`, size 26019, SHA256 `96997e360a66f6c321977f256023f8d17df122357f50c4a91ca5f2f88939598d` |
| Compiled source | `b1106cb351a8d9acb20284562a08c6e41acbe900a341cbac85ce5d02cdcb86e4` |
| Binary | `F1/results/prefix-feedback/resource-qualification-01/build/prefix-feedback`, size 1708640, SHA256 `84f89ca38c361a7534dd0222c7fb8b25a1c1581fefeeadd0969604426f23aae5` |
| Parent/read | `025d40d8-9380-4590-a82f-8291ba16acd9` |
| State semantic ID | `027df2ac7b1e0652d31875d4c54e245f72170b7dc454692adab9998584a6a25a` |
| Previous state ID | `3ab2567478f5bffc7fc89ba1788b8e34210a14f79b2b077fcdb737ca97724439` |

Use retained root `F1/results/prefix-feedback/genuine-first-advance-20261028-02` and these exact operands.

| Retained key | Relative path | Size | SHA256 |
| --- | --- | --- | --- |
| `state` | `advance/state.json` | 77094 | `04766f49ad4d269f212ba1f1bf4c4809f9c4768756cbf26dd3193b4efab51d6a` |
| `snapshot` | `advance/snapshot.json` | 138560 | `b536031020d892432669648d82994ac53b817490e6ffa470063135e024833753` |
| `complete` | `advance/complete.json` | 6212 | `c72022de5423cb2996462878600993ad9348f5a5e9d2ad12ebd0bd1e68a7b6a4` |
| `producer` | `stage-0/receipt.json` | 2480 | `109675eb71ae1cbfdf2a1213ad0b79b2b7936dfcf0f97f03de797ca88e748c3d` |

Take `predecessor_sources` without reordering from controller `advance-spec-02.json`, also retained in that producer's pinned command. Build the current source closure by preserving the native dependencies and adding the new driver plus any missing canonical orchestration sources. Pin the new script separately. Do not alter the C++ source witness or rebuild the executable. Choose a new work path, for example `F1/results/prefix-feedback/genuine-location-block0-20261028-01`, and a separate fresh invocation output path. Populate expected chunk/block/row-begin as 0, row-end/available-score-end as 497, and available-signal-end as 12222.

## Propose, grant, and resume

1. Run locate inside the engineering F4 unit. Its result is `awaiting-fresh-Root-grant` with the exact proposal FilePin. The proposal is data with `authorization:false`. No proposed command executes in the helper.
2. Root inspects the proposal, authors the exact fresh F4 grant, and runs it under the required profile. Preserve the proposed cwd, environment, semantic roles, argv, source/input pins, attempt path, and expected files. Never substitute a command or rerun accepted advance0.
3. Root appends the proposal Pin and successful F4 `complete.json` Pin to a newly pinned index. Freeze the updated spec and invoke locate with the same work directory and a new result directory. Existing query, proposal, accepted F4 outputs, and legacy projections must match. An existing attempt without an accepted receipt remains held.
4. Repeat only on explicit Root action for the fixed existing mapper, decoder-locations, and required faidx consumers. The helper has no retry loop. When they finish, it writes exactly the returned `prefix-location/1` update to `work_directory/location.json`, then writes its result last.
5. Pin that completed result and update in an advance-next spec. Run once into a fresh output directory. For a later locate, take `retained` from the advance result's `produced`, `expected` from `produced_expected`, and `predecessor_sources` from that advance spec's `source_pins`. Block3 ends this path.

The controller must separately test actual positive and meaningfully rejected genuine metadata before expensive mapping. Hermetic metadata tests do not replace that check.

## Results and evidence

Every admitted invocation writes `result.json` last with `producer_replay_permitted:false`. Locate completion includes the update Pin, current retained state and expected binding, and actual/usable location counts. Zero locations or zero nonempty continuations remain observations. `observed-no-eligible-prefix` has no update or query. Pending results pin the exact proposal and execution index. They state that no native command executed and give no authorization.

Advance completion has status `completed-advance`. It retains one native request, one stage receipt and its six raw/terminal files under `records`, and native `advance/state.json`, `snapshot.json`, and `complete.json`. Including the last result, this is 11 files. Its result pins the actual producer and outputs, produced binding, input update, candidate census, consumed mapper-update census, location counts, and abstention. No native result is synthesized.

Failed results retain the error, spec/recovery operands, completed receipts, and pins of partial invocation files, including requests, raw streams, and terminal records. Locate work remains at the explicit recovery work path with its execution-index Pin. Root must inspect an exit-0 projection gap or unknown exit before deciding a new action. Fresh-attempt refusal preserves the old directory. No automatic producer replay is permitted.

## Limits

The endpoint still requires three real prefix mapper updates consumed by later blocks. Useful locations, reference continuations, changed search, productive indels, and endpoint completion are not guaranteed. `mechanism_qualified` and `scientific_qualified` remain false in this driver. Whole-chunk saved-score lookahead remains disclosed. Revised-prefix bridge projection remains unsupported. F2 and F3 are unchanged and are not called here. This is not a full caller, full-parent output, biological accuracy result, private-allele safety result, speed result, or promotion claim. Existing failed and private-insertion-erasure evidence remains binding.

The source tests use pure metadata and rejection controls. They exercise closed parsing, pin mismatches, foreign/stale bindings, block/endpoints, explicit pending proposals, augmented-index reuse, held unknown output, no native call in locate, admission, and fresh-attempt refusal. They do not fabricate successful native acceptance from mocked receipts.

The implementation task's sole test attempt stopped before discovery on 2026-10-28. Fixed retrieval UV exited 2 because its cache at `/home/jake/.cache/uv` was read-only. No tests ran. The task brief required stopping tests on refusal. The controller retains this verification gap and must run the tests separately before acceptance.
