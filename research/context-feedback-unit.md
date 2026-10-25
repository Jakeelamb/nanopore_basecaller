# Offline location-conditioned decoder unit

NP Retrieval owns this source unit. It tests feedback from a tentative native call and its likely genomic location into decoding of a saved native CRF score interval. A completed catalogue bridge supplies input custody. It does not answer this scientific question.

The worktree is `/home/jake/Projects/nanopore_basecaller-context-feedback`, branch `experiment/context-feedback-decoder`, based on `0ec40a69d6a43440cafc790c4614d516e8137011`. Stock and all successful producers stay unchanged. This document admits isolated source preparation only. It grants no build, data checkpoint, native process or GPU execution.

Jake explicitly selected native C++ for this new decoder to support speed work and direct Dorado integration. This user instruction supersedes the earlier Rust implementation choice for this unit. No new Rust decoder was written before that correction. Existing Rust sources and independent baseline checkers remain read-only and may supply oracle evidence. The CPU-only saved-frame experiment still needs its own qualification before native Dorado integration or a performance claim.

## Ownership

NP Retrieval owns only the following new paths in this worktree.

- `tools/context_decoder/` contains the native C++ decoder, CLI, CMake/CTest definition, formatting policy, independent arithmetic oracle and source tests.
- `scripts/context-feedback.py` coordinates the CLI and validates outputs through UV and the maintained command recorder.
- `config/context-feedback-dev-v1.json` declares inputs, mechanisms, controls, bounds and an initially non-runnable checkpoint.
- `tests/test_context_feedback.py` checks the orchestration boundary.
- `research/context-feedback-experiment.md` records the prospective hypothesis and actual results separately.
- `logs/context-feedback/` and `results/context-feedback/` retain this unit's ignored receipts and outputs.

Caller-stock owns the finished flank, coverage and private-allele source/evidence and the separate exact-output CRF performance study in `nanopore_basecaller-score-speed`. Caller-reference owns ordered mapping/observer proofs, the wider-proposal lane, raw-current and private-insertion diagnostics. Caller-reference explicitly confirmed that the new context-feedback worktree and assigned paths do not overlap its active lanes. Keep shared decoder/export kernels read-only. Bind each frame to its exact plan hash, query ID, parent, chunk, tensor, interval, initial context state, orientation and location-producer receipt. Query 0 is shared with the raw-current diagnostic and is exploratory development evidence, not an independent confirmation. NP Retrieval must report any new conflict.

Coral's `nanopore_basecaller-coral` worktree contains a learned DNA output-history/training-data assessment. Its inspected source proposes a trained decoder and grouped-token work. It has no implemented location-conditioned feedback decoder in the inspected tracked/untracked file inventory. Its dirty files belong to that lane and must not be changed. No identity is assigned to an unnamed pane.

## Mechanism and small data shape

The proposed data flow is tentative native sequence, source-bound location evidence, local reference and anonymous pangenome walks, then context-conditioned CRF path search over the original saved signal scores. The output must make the context's effect on search observable. Retain the unconditioned decoder as a complete matched control.

Use small explicit domain types for a location observation, retrieved context, score frame, decoding policy and decoded path. Parse and bind external records at the boundary. Keep genotype, truth ALT, desired winner, GIAB labels and observed accuracy outside inference. Location must come from tentative native-call alignment and its genuine producer, not from truth coordinates supplied as an oracle.

The new decoder must search paths during decoding rather than choose only among the old finite H. A graph or sequence prior may influence partial-path expansion, context state or the coupled decoding objective. The owner must freeze its precise formula and explain why the controls distinguish that mechanism from a final fixed-panel membership bonus. Preserve a separately maintained reference-free escape search and an exact context-disabled parity mode. Unavailable or ambiguous location/context must fall back by an explicit rule.

Keep the initial experiment CPU-only and offline. It reuses the native neural encoder's retained DGS1 transition scores. It does not feed context into or rerun the encoder. State that boundary in every result. Native Dorado beam-search integration is a later separately qualified unit.

Freeze the context weight, escape rule, beam/state caps, tie rule, chunk boundaries and final decision policy before the genuine checkpoint. Resource limits reject or abstain rather than silently drop a control, hypothesis or target. Do not claim that retaining an escape branch alone proves variant preservation.

## Genuine retained fixture

Start with development query 0, parent `7214d805-8331-49aa-af61-478be074d7a6`, from caller-reference's original admitted windows. Its retained native score file is:

`/home/jake/Projects/nanopore_basecaller-reference/results/graph-prior/pilot-v1/development/native-export/p1061436_b6_s23.scores`

The registered whole-file SHA-256 is `2155a435c42aae305635e41f3c79507a4ad249eb2fd84d8e5935898effcc9edd`, size 4,112,461 bytes. Its admitted interval has 84 timesteps. Resolve the exact interval, initial state, blank, clamp, original SEQ/Q/MOVES, mapped orientation and graph-query binding from the genuine window and producer manifests. A registered hash in this note is not a new payload check.

The frozen original windows are `/home/jake/Projects/nanopore_basecaller-reference/results/graph-prior/pilot-v1/development/windows/windows.jsonl`, registered SHA-256 `0740fa50b0611fcb41ab023d5f567b8b596635a81416305ff2b58d00cb7e5874`. The source-bound development cohort is `results/reference-frontier/decision-v2/development-cohort.json` in that worktree. It binds original graph walks, reference assets, native call/mapping receipts and accepted tensors. The mapped original SAM SHA-256 is `db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe`; the unaligned cohort SAM is not a genomic-location observation.

The qualified expanded catalogue completion is `results/reference-frontier/catalogue-v1/full-roundtrip/complete.json`, SHA-256 `949ad1b4528f968b77abc5bf2971e53de540ac40bf02c18d96ad094bdd871efc`. It can supply comparison/control sequences and custody. Its finite H must not become the new decoder's entire search space. No model, exporter, catalogue or graph producer needs to be replayed for the first saved-frame checkpoint.

After engineering qualification, a separately frozen checkpoint may cover original query IDs 0 through 31, retaining all original exclusions and adding explicit new context/decoder abstentions. This is development only. A single genuine frame demonstrates the handoff, not a biological improvement. HG005 and exposed historical validation cannot supply blinded candidate confirmation.

## Required acceptance surface

These are commands for the new implementation to supply, not commands that have already run or an execution grant.

```sh
cmake -S tools/context_decoder -B results/context-feedback/build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_FLAGS='-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off'
cmake --build results/context-feedback/build --parallel 2
cmake --build results/context-feedback/build --target format-check --parallel 1
ctest --test-dir results/context-feedback/build --output-on-failure --parallel 1
PYTHONPATH=tests uv run --no-sync python -m unittest test_context_feedback -v
uv run --no-sync python scripts/context-feedback.py qualify --config config/context-feedback-dev-v1.json --output results/context-feedback/DECLARED-qualification
uv run --no-sync python scripts/context-feedback.py query0 --config config/context-feedback-dev-v1.json --qualification results/context-feedback/DECLARED-qualification --output results/context-feedback/DECLARED-query0
uv run --no-sync python scripts/context-feedback.py checkpoint --config config/context-feedback-dev-v1.json --output results/context-feedback/DECLARED-development
```

The new CMake project must define a `format-check` target that runs the pinned available `clang-format` with `--dry-run --Werror` over an explicit census of its owned C++ sources and headers. Use the C++ language standard supported by the pinned Dorado integration target and record that source decision. Keep fast math and contraction disabled for numerical qualification. Record the actual C++ compiler, flags, linked math/runtime libraries and source closure. Rust baseline controls are separate read-only oracle checks; the new unit does not replace or silently rebuild their qualified historical executable.

Keep synthetic engineering qualification, genuine query 0 and the first-32 development checkpoint separately invocable and separately admitted. Engineering qualification builds the code and runs synthetic arithmetic, search, orchestration and consumed-frame rejection controls. Genuine query 0 adds the retained historical custody audit and actual native tensor decode. The first-32 checkpoint follows a successful genuine handoff. Source designs and proposed commands do not prove that any phase fits its resource ceiling.

The wrapper must record exact commands, UTC clocks, exits, work/error counts, sources, compiled artifact and input/output pins. It must reject existing output directories, stale admission and incoherent producer/score/context pins. It must enforce the actual canonical host lock, not create a second lock path. The lock owner must retain it until the complete owned worker tree is terminal, including timeout/error paths. A whole-unit supervisor must cover synchronous hashing and input construction as well as subprocess stages. Waiting only for a recorder leader does not establish that descendants are terminal. Preserve failed command receipts even if validating their raw evidence fails. Leave the canonical checkpoint non-runnable until its concrete source, fixture and resource admission exists.

Acceptance across engineering qualification and the separately admitted genuine handoff must include all of the following controls. A synthetic-only pass cannot close the genuine fixture requirement.

- Exhaustive tiny path enumeration independently checks stay/step CRF probability, context state and the declared objective. Use exact bits for context-disabled calls to unchanged arithmetic, and an explicitly justified tolerance only for independently summed nonzero-context path probabilities.
- Context disabled reproduces the reference-free decoder at identical beam/tie/cap settings. It preserves impossible paths and empty/short interval behavior.
- A controlled ambiguous-signal example demonstrates that changing valid location-linked sequence context changes partial-path search, not only a final membership bonus. Log the relevant expansion/control evidence.
- Independently wrong sequence context and independently wrong graph-path linkage test distinct failure modes. Input permutation/duplicate aliases cannot manufacture evidence or change scores through path multiplicity.
- A strong signal-supported private allele absent from all retrieved paths survives the declared escape/final decision rule. Weaker examples may expose failure and must remain visible. Do not turn the one known binary-prior insertion loss into the only control or tune the policy to that outcome.
- Truth-bearing inference fields, stale locations, missing/ambiguous context, swapped same-shape tensors and corrupted consumed payloads reject or take the frozen reference-free fallback as appropriate. Test actual consumed data and source associations, not only self-written manifests.
- The genuine query-0 fixture validates native tensor geometry, location and graph bindings, emits all matched controls and accounts for every path/window outcome. No accuracy claim follows from its CLI or arithmetic tests.

## Resource admission

The current grant is SOURCE ONLY with no lock reservation or queued execution. Caller-reference and H2 coordinate existing host work. P01 native and S01 CUDA holds remain unchanged.

Once source and source review are ready, submit the exact immutable synthetic qualification command and caps for one fresh CPU-only unit. The proposed ceiling is 300 seconds total, two CPU quota, 8 GiB address space, 4 GiB kernel memory, zero swap, 100 MiB outputs and a 30 GiB disk floor. Acquire the existing canonical lock nonblocking at fresh intake. If it is held, retain rejection and coordinate another boundary. These caps are a proposal, not an accepted reservation. The eventual C++ qualification command must explicitly include its bounded CMake host-compiler checks, C++ compilation/linking, formatting, CTest, wrapper controls and the precise supervisor/terminal-release contract. It does not authorize downloads, Koi/Torch compiler probes, Dorado, graph/index load, models or GPU work.

Price genuine query 0 separately after engineering qualification passes, then price the first-32 development checkpoint separately after the genuine handoff passes. Include conservative context-distance work bounds before admitting either real-data phase. Submit concrete geometry, work/output bounds, immutable command, admitted artifacts and a fresh terminal boundary. Do not reuse an expired grant, infer one from a free GPU or label source readiness as scientific completion. Preserve failed attempts and return terminal release to caller-reference and H2.

NP Retrieval owns this task through implementation, real qualification, its bounded development checkpoint, independent review and a draft PR handoff. Caller-stock coordinates shared resource boundaries and preserved evidence. No merge is authorized.
