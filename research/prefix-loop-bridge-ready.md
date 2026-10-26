# F1 bridge source cut

Source-only implementation follows Root's `S/briefs/F1-F3-integration.md`, where S is `/home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes`. The old qualified `ec5e8b84df49567dc9d5161fe117751bbb74094d` and all qualification01 failures/qualification02 successes remain retained. Independent actual review of that cut is `S/reviews/F1-engineering-actual-v1/REPORT.md`, SHA256 `ad0a61be592772f680c774b0c40bdb0cbfb857e64eee0196d0e94852d1a950ff`. New bridge format/build/component/joint executions:0. Only source reads and `git diff --check` were performed.

The new numerical/validation implementation is `include/prefix_feedback/bridge.h`, `src/bridge.cpp` and `tests/bridge_controls.cpp`. The existing likelihood/scoring kernel is unchanged. Main/CMake/source census, the source cwd guard, raw snapshot schema/path, Python stage orchestration and tests are updated. No sibling source/header is imported or modified. Raw decoder output is `prefix-snapshot/1` in `snapshot.json`; strict normalized F2 output is separately `feedback-next/1` candidate-batch in `batch.json`.

`emit-free-input`, `normalize`, `merge-indels` and the explicit synthetic `bridge-fixture` use `--request ABS --request-sha256 SHA --output FRESH_DIR`. The free identity is the actual independent branch, all-`!` Q, kind `pipeline-free-input`, quality_status `uncalibrated`. Actual producer proof consumes the binary/request/source-complete, command, input/output pins, raw stdout/stderr/time and a successful command-bound original-guard terminal stage. The later joint unit retains the outer F4 admission/cgroup closure. It emits identity before F2 selection; no stock-native quality or future native SEQ/MOVES is substituted.

Current mapper projection requires the original query to be an exact prefix of the current free identity, with all query extents inside it. Other revisions explicitly refuse. Frame export retains all consumed rows, copies original binary16 payloads and validates one-chunk codec/options; it does not truncate a row tail. Over512 prefix bases or2048 consumed rows emits `arm-excluded.json` linking the intact original state/snapshot/H, with no invented identity or downstream batch. Missing H/identity, unsupported geometry and overlarge original unions refuse without inventing an F2 batch. The complete panel mixture uses the approved unit emitted-position mismatches, canonical ID ordering and neutral-exhaustion coverage. It is separate from historical pruned rank and edit-distance priors.

F3 replacements are validated in full-prefix coordinates. New scores use F1's existing uniform scalar once per new string. Impossible strings are counted as explicit neural exclusions. New-arm/union bound exclusions preserve every original candidate object and H. U uses F2's native-first/sequence tie rule. Limits remain512 full-prefix bases,2048 rows,32-base nomination tail,512 new unique proposals,514 result bases and4096 final candidates. Existing conditional-DGM sidecars reject.

## First Root unit: format only

The explicit C++ census is9 files. The old `src/location.cpp` and `tests/controls.cpp` are unchanged; the other7 are changed/new. Exact full-census formatter argv, cwd `/home/jake/Projects/nanopore_basecaller-next-prefix-loop`:

```sh
/usr/bin/clang-format -i tools/prefix_feedback/include/prefix_feedback/session.h tools/prefix_feedback/include/prefix_feedback/bridge.h tools/prefix_feedback/src/io.cpp tools/prefix_feedback/src/session.cpp tools/prefix_feedback/src/location.cpp tools/prefix_feedback/src/main.cpp tools/prefix_feedback/src/bridge.cpp tools/prefix_feedback/tests/controls.cpp tools/prefix_feedback/tests/bridge_controls.cpp
```

Root must pin the actual nine source bytes, style file and registered formatter/runtime closure, retain actual format output and refreeze before compiling. Proposed fresh attempt `results/prefix-feedback/bridge-format-01`; caps30s/2CPU/RAM4GiB/AS8GiB/swap0, growth100MiB, aggregate4GiB, reserve30GiB. No formatter ran during source preparation.

## Component qualifier, independent of sibling artifacts

After format freeze, through a fresh Root F4 grant, exact payload cwd is F1:

```sh
env UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python /home/jake/Projects/nanopore_basecaller-next-prefix-loop/scripts/prefix-feedback.py qualify --output /home/jake/Projects/nanopore_basecaller-next-prefix-loop/results/prefix-feedback/bridge-qualification-01
```

`tools/prefix_feedback/engineering-plan.json` supplies the non-authorizing plan. Root pins the full current source closure and the existing registered tool/PR15 dependency closure. Hermetic input pins are empty. Full unit caps300s/2CPU/RAM4GiB/AS8GiB/swap0/growth100MiB/aggregate4GiB/reserve30GiB. Expected outputs retain configure/build/format-check/CTest/UV raw stages, binary, JUnit, LastTest.log and complete written last. Required actual census is2 CTests, the old13 C++ groups plus8 bridge groups, all old15 Python methods plus5 new producer/consumer methods, skipped0, and22 retained new F1 subprocess receipts/inputs. No dependency absence becomes a skip.

## Separate later actual cross-lane unit

`joint.py` invokes actual F1 advance/free-emission/normalize, F3 nomination, F1 merge and F2 decisions. Its independently hashed external manifest has exactly `schema=prefix-joint-spec/1`, FilePins `f1,f2,f3`, exact `f2_cwd,f3_cwd`, full `source_pins`, exact F3 `f3_source_files`, `fixture=uniform-binary16-t4-k1-beam1-v1`, and `rejections=true`. Root must author this metadata after the F1 binary exists; no future binary hash is embedded in the compiled source closure.

Registered actual sibling operands, copied from retained metadata only:

- F3 `/home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/prefix-qualification-01/build/indel-feedback`,681464bytes, SHA256 `c69e9a4a32e3c0defb1d930282076d4efe80e173c863fd9da65fe99734bcef73`; source `90b985a6` relayed by Root. Its full compiled source FilePin array must be independently supplied in the joint manifest.
- F2 `/home/jake/Projects/nanopore_basecaller-next-context-policy/results/context-policy/qualification-04/build/context-policy`,385904bytes, SHA256 `f4c5ad6943377002048189df55d93328010a4d1eb06eaf590f5654ac1235b3f3`; current frozen source `7acca691937543ff7117cd6fd59a78897c6bc9ab`.

The concrete payload shape, with a later Root-authored absolute manifest/hash, is fixed UV `python scripts/prefix-feedback.py joint-controls --spec ABS_ROOT_MANIFEST --spec-sha256 ROOT_MANIFEST_SHA --output /home/jake/Projects/nanopore_basecaller-next-prefix-loop/results/prefix-feedback/bridge-joint-01`. Cwd is F1; child F3/F2 cwd is each canonical source root, all outputs stay under F1. Caps are the same300s/2CPU/4GiB/AS8GiB. No supervisor, service or lock is nested.

The actual positive must add a previously absent indel, preserve H and produce H!=U, then verify prior-none U, disabled SEQ/Q, no-context free escape and resealed permutation invariance. Rejections exercise binding, raw hash, prior, future whole-SEQ fields/scope, unavailable endpoints, missing H and sidecar pins. The finite joint census is16 controls across25 retained subprocess stages. Component controls separately cover complete nonempty panels on both strands, replacement corruption, permutation, absent identity/H and whole-union exclusion. The joint runner's private SNV/INS/DEL policy counterfactuals are explicitly synthetic constants; they are not F1 neural or biological evidence.

## Cost and held work

There is no measured runtime capacity. For a fixed string length L and k<=4, the existing scalar visits at most `T * (sum_{j=0}^{k-1} 4^(k-j) + max(0,L+1-k))` state cells. At k4/T2048/L514, this is1,744,896 cells per call;512 such calls admit an upper bound893,386,752 cell visits, with up to two map updates per cell. Normalization/base verification adds its own scalar calls. This is a source loop bound, not a speed estimate or permission for that workload. The tiny joint fixture is four rows/k1. The512 proposal guard is not claimed reachable or executed under F3's32-base grammar.

Source-root corruption qualification, general revision projection, current human first-chunk T, reference/index/FAI custody, genuine native/mapping inputs, three genuine prefix-derived location updates, full-parent stock identity, accuracy, private-variant safety and latency remain separately held. No streaming/raw-causality, calibration, speed or biological claim follows from this source cut.
