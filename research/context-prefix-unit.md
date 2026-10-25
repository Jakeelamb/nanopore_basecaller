# Prefix-only native encoder handoff

This source unit is isolated in `/home/jake/Projects/nanopore_basecaller-context-feedback-prefix`, branch `experiment/context-feedback-prefix`, baseline `6a8c23e`. It owns only `tools/context_prefix/` and this report. Shared Dorado, exporter, decoder kernels, retained builds, caches, weights and input data remain read-only. The coordinator owns admission, execution, independent review and integration. No formatter, compiler, CTest, native executable, model, GPU query, download or host lock has run for this unit.

The hypothesis is limited. A genuine available raw prefix can reach the native encoder and decoder without inaccessible future samples influencing normalization, padding or model input. A successful handoff would enable a later feedback experiment. It would not establish accuracy, useful localization, continual hidden-state streaming, bounded output commitment, stock CUDA parity or improved throughput.

## Implemented surface

`context-prefix qualify --output NEWDIR` runs synthetic CPU controls without reading a request, POD5 or model weights. It uses the retained native int16-to-half utility, including SIMD tails and integer extrema. The exhaustive shape loop covers horizons11 through103 under three calibrations. Controls check exact half bits against independent scalar half conversion, FP32 conversion, trim/padding, poisoned future tails, trimmed-sample independence, admitted-sample sensitivity and rejection of whole-row buffers, invalid horizons/calibration, nonfinite comparisons and foreign acquisition tuples. Counts are calculated at runtime. CTest runs the same native control function and must actually execute.

`context-prefix contracts --request FILE --request-sha256 SHA --output NEWDIR` performs a genuine POD5-prefix handoff at both predeclared horizons4096 and12288. It parses model configuration but never instantiates a model or reads tensors through the model loader. Input pins include the complete weight-file manifest and are checked as bytes. An independent offline `pod5_get_read_complete_signal` fixture compares the extracted prefix with the complete record, capped at10million samples. That full-record branch is used only by `contracts`; it never reaches normalization or inference and its physical read count is disclosed separately.

`context-prefix forward --request FILE --request-sha256 SHA --horizon 4096 --output NEWDIR` first repeats the genuine detached-input handoff for the selected horizon, then loads one native CPU FP32 model. It runs four forwards using baseline, identical reset, poisoned inaccessible future tail and one changed admitted sample. H12288 is a separate command with a distinct output directory and never repeats H4096. The coordinator must inspect the first unit's actual cost before admitting the larger unit.

Native CPU decoding uses the existing `create_decoder(CPU, config)` implementation and its uniform initial-state forward/backward algorithm. It does not inject a known native four-base context at the read start. It emits native CPU `SEQ`, `Q` and `MOVES` for the prefix. These are exploratory CPU/no-open-pore variant outputs, not full-read stock controls or newly calibrated qualities.

## Availability and normalization

The only admitted parent is original development query0 UUID `7214d805-8331-49aa-af61-478be074d7a6`. It is a member of the original64-parent allowlist, not a fresh confirmation molecule. Its old edit center lies far into the read; the new prefixes are different windows. Do not describe their calls as a matched numerical replay of that old center.

The source POD5 is the original HG002 PAW70337 shard33, acquisition `de8117b1abf27d6d4ac91526772636b9a5ca7fde`, at5000Hz. The reader checks exact unique UUID metadata before planning traversal, checks the returned UUID and acquisition/flowcell/sample-rate tuple, and reads only signal rows intersecting `[0,H)`. A compressed row must be decompressed in full. This physical overread is explicit. Only a detached copy of the firstH samples leaves the reader. The original future buffer is poisoned before a second detached view is constructed; no future signal bytes are exported or passed to the normalizer/model.

Normalization reuses `dorado::utils::shift_scale_tensor_i16_to_f16_inplace`. Its FP32 scalar operations are `scale=24/calibration_scale` and `shift=94/calibration_scale-calibration_offset`. The helper then removes ten samples, repeats the retained prefix from its start to a multiple of six, and casts the native-rounded half values to FP32. It uses fixed HACv6 mean94/stdev24. It computes no whole-read median, MAD or quantiles. Open-pore adjustment is disabled because availability of that metadata atH is unqualified. Every arm shares this declared variant. Total read length is recorded as metadata and never chooses the horizons.

The corresponding `[1,1,S]` input sizes are4086 and12282. Expected output is `[1,681,1024]` and `[1,2047,1024]`. The helper rejects actual shape, device, dtype, contiguity or finite-value disagreement. The CPU model includes its configured clamp, unlike some CUDA export paths.

The output score format is distinct `PFS1`, little-endian IEEE FP32. Its header fields are `PFS1,T,1024,4,6,cpu,float32,H,10,valid,padded`, tab separated, followed by contiguous `[1,T,1024]` values. It is never labelled native CUDA DGS1. Each of the four actual score arrays is retained and pinned. Reset and future-tail maximum absolute differences must be at most1e-6, with identical native prefix `SEQ/Q/MOVES`. The admitted positive must change at least one finite score. Same-horizon comparisons alone are required; earlier rows are not required to match those of a longer prefix. The FLSTM's reverse layers make that a different experiment.

## Native build closure

The pinned native revision is `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`, whose Dorado target uses C++23. The retained exporter build is `/home/jake/Projects/nanopore_basecaller-reference/software/graph-prior/build`. `derive_build.py` structurally parses its exact `GraphScoreReplay.cpp` entry in `compile_commands.json` and the matching linker block in `build.ninja`. It preserves definitions, C++23, cxx11 ABI, archive order, Torch `--no-as-needed` treatment, CUDA link dependencies and RPATH. It changes source/output ownership and marks read-only native include directories as system headers so the new strict warning policy applies to owned code. It adds only the POD5 shared library and explicit interface includes. It never invokes Ninja or writes in the retained build or ccache.

The required compiler is the retained GCC15 binary under `stock/software/source-build-qualification-20261023/toolchain-gcc15/usr/bin/g++-15`, SHA256 `7c1ff2182981fb185022a8cdd699abaab64b8ea0965e30855754dd95a6c09d15`. All owned sources, the compiler, formatter, retained build metadata, link archives/direct shared objects and relevant native interfaces/source files are hashed during private configuration. The binary checks those exact pins before native work. The generated `build/generated/native-build.json` records the transformed compile/link argv and source/asset pins. This is a retained-archive integration, not a rebuild or newly established source qualification of all Dorado dependencies.

`-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off` applies to the new target. The owned source census drives both compilation witnessing and the pinned clang-format dry-run target. Final source pins must be frozen after coordinator formatting. No namespace closing labels are generated.

A CPU command uses a CUDA-linked binary. The helper selects CPU tensors and never requests a CUDA model, stream, benchmark or autotuning. Shared-library initialization behavior and actual dynamic resolution have not been measured. Before genuine execution the coordinator must retain actual compiler/compile commands/link command, `ldd` results and hashes of every resolved runtime library, including transitive dependencies. Passing synthetic controls alone does not establish runtime closure or zero device activity.

## Ready commands and caps

All following commands are prospective. Execute inside the coordinator's whole-unit hard supervisor with a fresh nonblocking canonical host lock and retained raw wrapper. A free lock is not a reservation. Hold it until worker cgroup and launcher tree are terminal. Existing reference producer outputs must not be replayed to repair observation failures.

Engineering starts at300seconds, two CPUs,4GiB memory,8GiB address space, zero swap,512MiB new build-output stop and30GiB free-disk floor. This is a bounded proposal, not proof that Torch compilation/linking fits. Use at most two build jobs and one test job. Stop on caps and retain failure. The retained CUDA-linked libraries may consume significant address space; do not silently raise it after a refusal.

```sh
cmake -S tools/context_prefix -B results/context-feedback/prefix-engineering-1/build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build results/context-feedback/prefix-engineering-1/build --parallel 2
cmake --build results/context-feedback/prefix-engineering-1/build --target format-check --parallel 1
ctest --test-dir results/context-feedback/prefix-engineering-1/build --output-on-failure --parallel 1
results/context-feedback/prefix-engineering-1/build/context-prefix qualify --output results/context-feedback/prefix-engineering-1/native-controls
ldd results/context-feedback/prefix-engineering-1/build/context-prefix
```

CMake invokes metadata derivation through UV using the existing `/home/jake/Projects/nanopore_basecaller-retrieval/.venv`. No environment creation, dependency synchronization or downloads are intended.

Request preparation requires the frozen original-location v4 full prepared execution and exact SHA256. It revalidates that full upstream chain at its original root and takes q0 identity only from the inference manifest. No truth sequence enters the request. The request pins the original native-caller input tuple, POD5, allowlist, current complete model-file manifest and source/custody record. Native code rejects unknown fields, foreign policy/data locations and any changed input pin.

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv uv run --no-sync python tools/context_prefix/make_request.py --prepared /home/jake/Projects/nanopore_basecaller-context-feedback-v4/results/context-feedback/v4-prepare-all-1/execution-complete.json --prepared-sha256 ACTUAL_FROZEN_SHA256 --output results/context-feedback/prefix-request-1
results/context-feedback/prefix-engineering-1/build/context-prefix contracts --request results/context-feedback/prefix-request-1/request.tsv --request-sha256 ACTUAL_REQUEST_SHA256 --output results/context-feedback/prefix-contracts-1
results/context-feedback/prefix-engineering-1/build/context-prefix forward --request results/context-feedback/prefix-request-1/request.tsv --request-sha256 ACTUAL_REQUEST_SHA256 --horizon 4096 --output results/context-feedback/prefix-forward-4096-1
```

The coordinator fills the SHA placeholders from retained completed artifacts, never from a guessed value. Request preparation and genuine CPU contracts are separate units under the same300second/CPU2/memory4GiB/address-space8GiB/zero-swap limits, with100MiB new result output and30GiB disk reserve. Their hashing reads the pinned complete POD5 and weight files, which is input I/O rather than output or model inference. The full-record CPU fixture is capped at20MiB of int16 samples per call. Genuine prefix extraction must not silently load an entire record in the forward verb.

The first forward is oneH4096 unit, four CPU model forwards, with the same300second/CPU2/4GiB/8GiB/zero-swap cap and100MiB new output stop. Its four score payloads are about10.6MiB from their declared shapes. After terminal evidence prices that actual path, a separate H12288 command may use the same caps and a new output directory. Its four payloads are about32MiB. These are shape-derived output sizes, not latency, throughput or measured allocation predictions. No H12288 execution is inferred from H4096 success. A cap failure remains a result and requires a separately declared next unit.

## Receipts and remaining work

The native attempt is written before source/data assertions. It records exact argv, resolved binary pin, start UTC and compiled source/native asset closure. Failed assertions produce `failure.json` when the output boundary has been established; raw stderr and outer exit/clocks remain mandatory. Successful completion pins request/input files, native result, raw admitted samples, normalized half/input FP32 arrays, metadata, all four score arrays and native decoded prefix. Completion is written last and file/directory synced, not rename-atomic.

No runtime qualification exists in this handoff. Root must first format, freeze and independently review this cut, then execute engineering and genuine CPU contracts with actual recorder/terminal proof. Independent source review should inspect response derivation, POD5 traversal and both causal data paths. Prefix forward still needs actual shape/dtype/finite, reset and suffix-invariance evidence at one horizon before scaling. Useful location proposals, new context partial-path decoding, biological outcomes, private-allele controls, streaming hidden-state continuation, commitment latency and speed remain separate later contracts.
