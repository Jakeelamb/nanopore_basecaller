# Prefix CPU runtime review

Verdict: **PASS_BOUNDED_PREFIX_CPU_RUNTIME** for the frozen artifacts below. A genuine detached q0 prefix reached native CPU FP32 inference and native CPU decoding at each predeclared horizon. Each horizon has four executed forwards, byte-identical baseline/reset/future-poison scores, and a finite nonzero admitted-sample effect. This qualifies the declared prefix boundary on one development molecule at two horizons. It does not qualify stock CUDA parity, production streaming, location feedback, output commitment, biological accuracy or speed.

Review root: `/home/jake/Projects/nanopore_basecaller-context-feedback-prefix`; branch `experiment/context-feedback-prefix`; HEAD `6a8c23e8a34d37bef76f25c30cc007bf429deae5`. Prefix sources and protocol are untracked, so HEAD alone does not identify the artifact. Existing `prefix-source.md`, immutable `prefix-source-cut/` and `prefix-source-build-delta.md` were read and preserved. Only this report and `prefix-runtime-audit.py` were written. No compiler, formatter, CTest, native executable, POD5 reader/decoder, model, NN forward, producer/replay, GPU query or host-lock operation ran during this review.

## Frozen identities

Native binary: `results/context-feedback/prefix-engineering-2/build/context-prefix`, 201726248 bytes, SHA256 `7bc5f6827ac9234f54ea92367fce4715de1c75d03b05b88ff84d74a906f1e9f7`. Retained Dorado source HEAD was independently read as `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`.

All completion rows below are under `results/context-feedback/`:

| Artifact | SHA256 |
| --- | --- |
| prefix-engineering-2/complete.json | `123a275c75ad59c79d6085c0a48482193713c31ded6b52b5c4938da0585329e3` |
| prefix-q0-request-1/complete.json | `0efb7838e19ba37310defa399319fab710eb92181eb175a272a0e94d3c205a11` |
| prefix-q0-contracts-1/complete.json | `82c2ee7a63d142a0976cfd90c8a3b4e7b19bd92f922c6c2677ea3582571a6daa` |
| prefix-input-controls-1/complete.json | `8a2e7812702b2f18a8d058c92071dfa89571604908c42dbcd3a0794dcc2c3cf8` |
| prefix-forward-4096-1/complete.json | `3587736f26c0780fbe404a1d06ad3f274cc6c2b362fefe899c48d6484f23464e` |
| prefix-forward-12288-1/complete.json | `8edb4e91dc5209e650cf3ddd3c1d4f52cb58ff50f0791f1dce2dd2cf3dd8bb84` |
| prefix-q0-request-1/request/complete.json | `910162dd75971b2ebbc0103bfdc21a12a6235450d9132bfd0fc4ea9b1fa3da58` |
| prefix-q0-request-1/request/custody.json | `73fe2bb25b177f24249df5ef3d4aef16c6f1b782e9226c40cd24493400123d90` |
| prefix-q0-contracts-1/native/complete.json | `1c9d597ba0e6482df8c2181f19fcea0d8834994a87ac39f84987fa4341453726` |

| Native forward completion | SHA256 |
| --- | --- |
| `results/context-feedback/prefix-forward-4096-1/native/complete.json` | `74030e03a55908ffb2eca3f45ded92656aceca1f3859bae1a3418b95597d556c` |
| `results/context-feedback/prefix-forward-12288-1/native/complete.json` | `b6d6d7ad9f9fc9299d0b776b863c53208209c378c02e03ffecbebf8fafad7330` |

Current source census, independently rehashed against executed attempt/completion pins:

| Source | SHA256 |
| --- | --- |
| tools/context_prefix/.clang-format | `39cc1dcfff0d7b805a86adf5e42a4f05475a1aa1335805ab1ba52a7a57539ffe` |
| tools/context_prefix/CMakeLists.txt | `a6e40b4a20e13bff58acbb86242f3dc80bcd2e3a542c259e43c380cc4f849360` |
| tools/context_prefix/derive_build.py | `77aa70d06525f945f17c82b582982a45a727ce04a8f5bed164e3ae237cd2e404` |
| tools/context_prefix/include/context_prefix/prefix.h | `17b7ed6c4cfaeb1d4f62a748867f243b5c25fe00e7c8ac0d39f399ed372f9554` |
| tools/context_prefix/make_request.py | `082d8e406a9cf035925f30acea0fd5b6d4d0ab224cab48eaf7c18a5872a308ec` |
| tools/context_prefix/source-files.json | `ca4b025dec7166c47b80b5b1dc115431896f64940b984b2e4633dfe021a599d3` |
| tools/context_prefix/src/main.cpp | `3fd4dbc4688f321a1223f2eabd794bfb28a0e0c94a899018fbe5abc6965b292c` |
| tools/context_prefix/src/native.cpp | `91a4b47ffa26046bb9a826ccdf73540ce8741572645ef6835914408c52c63675` |
| tools/context_prefix/src/prefix.cpp | `473a254d1ad7e3199f177f02e41ed199c423a4f840b2e1e4fa9e9ed95d9da70e` |
| tools/context_prefix/tests/controls.cpp | `a62ab16472b56ddc46ea1470fe85c4a79826621ee2dee6c09365f3cedcab80d2` |
| tools/context_prefix/tests/main.cpp | `737ea3fb5a1a51879c94d9d58eca62a9b37467e77630795e6ffd6ad4295f3fd7` |
| tools/context_prefix/verify_formatter.cmake | `83cbaa1d9befbc7e5b406c61f66665b2bdab234c2006c7c6c11e766d86a31de9` |
| research/context-prefix-unit.md | `9f0248f1ab17ead95bf61860852586d6109a0f1f32a7b7f4f57d80f8ec54b8a9` |

The `a6e40b...` CMake and `77aa70...` derivation fix are the already reviewed two-file delta. Five actual compile entries retain Release `-O3 -DNDEBUG`, C++23, all strict warnings through `-Werror`, `-fno-fast-math` and `-ffp-contract=off`. The actual `native.cpp` command contains all 18 paired system include operands. GCC15 is pinned to `7c1ff2182981fb185022a8cdd699abaab64b8ea0965e30855754dd95a6c09d15`.

`build/generated/native-build.json` is `b19b8b0a34c3bcd78f92c5d7c938a7396b1de67b8dfbcf32891d4b331481d6b3`. Its 55 native asset pins were read and rehashed, as were all 30 file-backed libraries in `runtime-libraries.json` (`8d93063793ae4203c4d2fd8fe7f7a74fe0a2de4f1f0ce567901e4adde6da1525`). The retained actual `ldd` output has no unresolved library and its resolved-path census equals those 30 pins, including transitive CUDA libraries. The VDSO is not a file-backed library.

Actual link commands are `build/CMakeFiles/context-prefix.dir/link.txt` (`ea7c267a6f8c868e260711fa76941cedc0eaa63699b0b3505b3c182548b957e5`) and `context-prefix-tests.dir/link.txt` (`3b181f0b2e300dbd317ba3d9ddc3d0ff8b84ee56e4bce9e40113cb0284642063`). Every essential derived operand occurs in each actual command, including wrapped Torch no-as-needed operands and RPATHs. Exact original token ordering is not claimed: CMake emits one of the three repeated `--as-needed` markers and rearranges/repeats some operands. Two exploratory ordered-token checks stopped on that difference; the final audit records the actual link commands and checks essential-operand presence plus actual resolved closure. This does not rebuild or establish source equivalence of the retained native archives.

## Commands and raw execution evidence

All recorded commands below used cwd `/home/jake/Projects/nanopore_basecaller-context-feedback-prefix`. Every producer has the actual eight raw recorder files: `command.sh`, `cwd.txt`, `start.txt`, `end.txt`, `exit-status.txt`, `stdout`, `stderr`, `time.txt`. The offline review checked file pins, exact argv/cwd, ordered UTC clocks, GNU time command/exit/RSS, raw stdout completion linkage, stage terminal and launcher-group cleanup, native attempt/binary/source/result/file/input linkage, and whole-unit completion.

Recorded commands, **not rerun by this review**:

```sh
cmake -S /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/tools/context_prefix -B /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build --parallel 1
cmake --build /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build --target format-check --parallel 1
ldd /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix
ctest --test-dir /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build --output-on-failure --parallel 1
/home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix qualify --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/native-controls
uv run --no-sync python /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/tools/context_prefix/make_request.py --prepared /home/jake/Projects/nanopore_basecaller-context-feedback-v4/results/context-feedback/v4-prepare-all-1/execution-complete.json --prepared-sha256 14e4fc1c4f9de03c789cbb20dc9df71d953a78002ce8278873cbb7ac6d30ae45 --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-q0-request-1/request
/home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix contracts --request /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-q0-request-1/request/request.tsv --request-sha256 efad10f05aab2b0709269f30fb789cfcc9ecc64a9fbdb59aa84e73940a21689e --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-q0-contracts-1/native
/home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix forward --request /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-q0-request-1/request/request.tsv --request-sha256 efad10f05aab2b0709269f30fb789cfcc9ecc64a9fbdb59aa84e73940a21689e --horizon 4096 --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-forward-4096-1/native
/home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix forward --request /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-q0-request-1/request/request.tsv --request-sha256 efad10f05aab2b0709269f30fb789cfcc9ecc64a9fbdb59aa84e73940a21689e --horizon 12288 --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-forward-12288-1/native
```

| Stage | Exit | Raw GNU wall | Eight-file raw directory |
| --- | --- | --- | --- |
| cmake -S | 0 | 0:01.47 | `logs/context-feedback/recorder-root/logs/20261024T230521Z-prefix-cmake-configure-Hi5TUG` |
| cmake --build | 0 | 0:15.61 | `logs/context-feedback/recorder-root/logs/20261024T230522Z-prefix-cmake-build-4uLJHD` |
| cmake --build | 0 | 0:00.11 | `logs/context-feedback/recorder-root/logs/20261024T230538Z-prefix-format-BrpvLu` |
| /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix | 0 | 0:00.00 | `logs/context-feedback/recorder-root/logs/20261024T230538Z-prefix-runtime-closure-9QFEeQ` |
| --test-dir | 0 | 0:01.21 | `logs/context-feedback/recorder-root/logs/20261024T230540Z-prefix-ctest-uzpWiM` |
| qualify | 0 | 0:01.30 | `logs/context-feedback/recorder-root/logs/20261024T230541Z-prefix-native-controls-YXM3FF` |
| run | 0 | 0:06.03 | `logs/context-feedback/recorder-root/logs/20261024T231948Z-prefix-make-request-fYzUSi` |
| contracts | 0 | 0:01.81 | `logs/context-feedback/recorder-root/logs/20261024T232249Z-prefix-contracts-YmJbOy` |
| forward | 0 | 0:05.49 | `logs/context-feedback/recorder-root/logs/20261025T001312Z-prefix-forward4096-cVDnYk` |
| forward | 0 | 0:10.38 | `logs/context-feedback/recorder-root/logs/20261025T002252Z-prefix-forward12288-Iaixnv` |

All ten successful stage stderrs are empty. The CTest raw stdout records an actual 1/1 test pass. Its retained `build/Testing/Temporary/LastTest.log` contains the executed test binary and control JSON: **15516 assertions, 279 normalization shapes, 279 poisoned-tail cases, 295 rejections**. Controls use throwing checks that remain active in Release; this is not an assertion-disabled build claim.

Whole-unit receipts independently checked:

| Unit | Outer exit | Raw GNU wall | Max RSS KiB | Eight-file outer raw directory |
| --- | --- | --- | --- | --- |
| prefix-engineering-2 | 0 | 0:21.82 | 1346160 | `logs/context-feedback/recorder-root/logs/20261024T230521Z-prefix-engineering-2-mdrFHR` |
| prefix-q0-request-1 | 0 | 0:08.82 | 51892 | `logs/context-feedback/recorder-root/logs/20261024T231946Z-prefix-q0-request-1-okpPZw` |
| prefix-q0-contracts-1 | 0 | 0:10.50 | 580716 | `logs/context-feedback/recorder-root/logs/20261024T232241Z-prefix-q0-contracts-1-QTI64L` |
| prefix-input-controls-1 | 0 | 0:07.87 | 574288 | `logs/context-feedback/recorder-root/logs/20261025T000632Z-prefix-input-controls-1-oy3irU` |
| prefix-forward-4096-1 | 0 | 0:16.65 | 636284 | `logs/context-feedback/recorder-root/logs/20261025T001301Z-prefix-forward-4096-1-I3QDke` |
| prefix-forward-12288-1 | 0 | 0:20.55 | 695448 | `logs/context-feedback/recorder-root/logs/20261025T002243Z-prefix-forward-12288-1-6rUqjY` |

These are observed command costs for resource admission, not a throughput benchmark. Each outer `logs/context-feedback/program-runs/run-UNIT/start.json` retains the exact worker/controller pins and full `systemd-run` launch argv. Each corresponding `terminal.json` reports no controller error, exit0, inactive/dead/not-found service and zero MainPID/ControlPID; `cleanup.json` records terminal launcher-tree cleanup. The outer raw stdout binds that unit's precise completion pin. No producer was repeated to repair observation evidence.

Actual hard launch settings are `Type=exec`, `ExitType=cgroup`, `KillMode=control-group`, `CollectMode=inactive`, `RuntimeMaxSec=290s`, `TimeoutStopSec=1s`, `CPUQuota=200%`, `MemoryMax=4294967296`, `MemorySwapMax=0`, `LimitAS=8589934592`. The controller records a 300-second whole-unit boundary; the engineering/request/contracts/forward worker grant is 280 seconds. The controller source retains the canonical nonblocking lock until worker-cgroup terminal/absent and launcher-tree cleanup.

Do not read the successful unloaded service's `RuntimeMaxUSec=infinity`, `ExitType=main` and `TimeoutStopUSec=1min 30s` defaults as settings observed while the job ran. Caps are supported by actual start argv and the executed, pinned worker kernel checks. Engineering2 additionally retains raw kernel values in `kernel-limits.json`: `cpu.max=200000 100000`, `memory.max=4294967296`, `memory.swap.max=0`, RLIMIT_AS soft/hard 8589934592. Request/contracts/forward call the same `cgroup_limits` function before native work: exact `/proc/self/cgroup`, kernel CPU/memory/swap limits and RLIMIT_AS are checked/set. They do not retain separate raw kernel-value snapshots. Input rejection controls use the same outer hard launch settings but do not execute that worker kernel-read function. No successful loaded-unit supervisor-property snapshot is retained; this is an observation limit, not a reason to substitute unloaded defaults.

Actual output grants are **536870912 bytes, 512 MiB, cumulative worktree results+logs**, set in launch environment and worker grant before execution. This is not proof of the prospective protocol's 100 MiB new-output stop per request/contracts/forward unit. The 30 GiB reserve and cumulative output bound are checked by the pinned supervisor/worker code; no continuous independent telemetry trace is retained.

Engineering1 remains a failed attempt. Actual raw `logs/context-feedback/recorder-root/logs/20261024T225604Z-prefix-cmake-build-uvM5OS/` retains exit2 and missing `config/BasecallModelConfig.h`/bare include-path warnings; its outer terminal retains exit1 and `Result=exit-code`. Engineering2 does not relabel that failure.

## Original request custody and native rejection controls

The request is `results/context-feedback/prefix-q0-request-1/request/request.tsv`, 1339 bytes, SHA256 `efad10f05aab2b0709269f30fb789cfcc9ecc64a9fbdb59aa84e73940a21689e`. Model manifest is `d84423c637e5ba077b6947792f6c63c4155dacf4a85e135eb2a613dbfed6fe6b`; custody pins 51 model config/tensor files, the original POD5, allowlist and original native producer. The POD5 pin is `6146625e08d8628cef8474ac6782a1f1c4843c2f499784b803ab64b58e5ecc8e`, 555013832 bytes.

The review imported `make_request.py`'s upstream auditor from its actual original v4 location and reran **only its offline `completed(..., 'prepare')` validator**. Original ROOT and boundary ROOT remained v4, and the original source-inventory guard `695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa` passed. Its script-file pin is `a20d19996b7f317b49a441332b5161373fbcff41a2f48e351d53e3b190e3b4e6`. The validated full-preparation execution pin is `14e4fc1c4f9de03c789cbb20dc9df71d953a78002ce8278873cbb7ac6d30ae45`. The exact original inference-manifest q0 case equals custody and has UUID `7214d805-8331-49aa-af61-478be074d7a6`. It remains an original 64-parent development molecule, not an independent confirmation.

The actual old v5 `tools/context_decoder/model_observe.py` is unchanged at `d20da3f3ce5581504d659917b0ee1cd6d7fce773a66a437c790a195fa0ae1abf`. The review used its read-only `outer_unit` function with the genuine prefix execution module; observer ROOT remained v5. No ROOT override or relocated auditor was used. Native attempt sources equal the engineering source/native-asset closure for every successful native phase and both rejection attempts.

Two retained **native** negative commands:

```sh
/home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix contracts --request /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-q0-request-1/request/request.tsv --request-sha256 0000000000000000000000000000000000000000000000000000000000000000 --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-input-controls-1/bad-checksum
/home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-engineering-2/build/context-prefix contracts --request /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-input-controls-1/unknown-field.tsv --request-sha256 86c83aacb3f4339855763e9aa1f0f7ffb68097f4ea9596c2037139bb96d1b937 --output /home/jake/Projects/nanopore_basecaller-context-feedback-prefix/results/context-feedback/prefix-input-controls-1/unknown-field
```

Bad checksum: raw `20261025T000632Z-prefix-bad-checksum-SmlFWw/`, exit2, stderr `context-prefix: Request SHA256 differs`, wall1.99s. Correctly hashed request with appended unknown field: raw `20261025T000634Z-prefix-unknown-field-XG8Bhg/`, exit2, stderr `context-prefix: Unknown or missing request field`, wall5.58s. Both raw directories are under the recorder root above. Their terminal group proofs are true; failure records have `complete:false`, `model_forward_calls:0`, and no native `complete.json`. Source inspection places these guards before model metadata, POD5 extraction and model construction. The unknown-field case's correct supplied hash ensures it reached its own field guard.

## Actual prefix arrays, scores and decoded outputs

The genuine metadata binds q0 to acquisition `de8117b1abf27d6d4ac91526772636b9a5ca7fde`, PAW70337, sample ONLL08362, 5000 Hz, batch0/read-row415. Each horizon reads signal row1177, stored88347 bytes, decompressing102400 samples. Physical tail overread is real; only H detached int16 samples are exported. Poisoned tails are98304 and90112 samples. Future exported bytes are0. These are logical-input causality controls, not physical no-overread or streaming-I/O claims.

Contracts compares each detached prefix against an independent complete-record POD5 API read of378536 samples, then exports only H samples. Forward metadata records0 offline-full-record samples. The retained contract and forward raw/half/FP32 arrays match exactly at the same H. This review independently recomputed FP32 scale/shift, every normalized half bit and every half-to-FP32 input byte from retained raw int16 samples, using only that prefix, trim10 and repeat padding.

| H | Valid after trim | Padded S | Repeat padding | Actual score shape | Values per arm | Reset max abs | Future max abs | Positive max abs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4096 | 4086 | 4086 | 0 | [1,681,1024] | 697344 | 0 | 0 | 4.068917155265808 |
| 12288 | 12278 | 12282 | 4 | [1,2047,1024] | 2096128 | 0 | 0 | 9.188859939575195 |

H12288 repeats the first four retained post-trim samples. The old source review's statement that both genuine horizons need no padding is incorrect; that old cut is preserved. The implementation and actual artifacts use the correct four-sample padding.

All eight actual score arrays have the exact PFS1 header, expected payload size and finite little-endian FP32 values. Baseline/reset/future-poison are byte-identical within each horizon, stronger than the declared1e-6 comparison. Positive arrays differ by the exact recomputed maxima above.

| H | Arms | Whole file bytes | SHA256 |
| --- | --- | --- | --- |
| 4096 | baseline, repeat, future-poison | 2789424 each | `b7a7eba620dbbce58646da1be535559ecb9ab635a783450512709ca61ffd925a` |
| 4096 | admitted-positive | 2789424 | `f960af7f1049dabb0d4d13441ee48a429925926f1f454ab2ae682cfc5f7c5b77` |
| 12288 | baseline, repeat, future-poison | 8384564 each | `48fedef39ba1382c3f8f4eb72cfb15b8862253ca63944abc75a2728636d54031` |
| 12288 | admitted-positive | 8384564 | `20a83ded02b96d0cc171279d644fb2cb707ca39fa45e2074aadc278cf0c4231b` |

Actual baseline decoded outputs:

| Native TSV | SEQ=Q bases | MOVES entries | Q ASCII range | SHA256 |
| --- | --- | --- | --- | --- |
| `results/context-feedback/prefix-forward-4096-1/native/horizon-4096.native.tsv` | 360 | 681 | 35–63 | `becf66a0a7bd626613352c4c348767003344015a2d4634b6b95d586d4be3ce1c` |
| `results/context-feedback/prefix-forward-12288-1/native/horizon-12288.native.tsv` | 1070 | 2047 | 35–70 | `e6a76fc254c6731f00178204a9d3b52bce27b5f663afb03c00ed3f62d528ab39` |

Each SEQ contains only A/C/G/T, Q is printable and equal length, MOVES contains only 0/1, MOVES length equals T and its number of 1s equals SEQ length. Initial state metadata is `uniform_native_cpu`. The executed native assertion compares baseline/reset/future sequence, Q and MOVES; only baseline strings are separately persisted, so offline review cannot independently decode the other three arms without a prohibited native replay. Identical score bytes and the pinned native comparison support that bounded equality claim; no quality calibration claim follows.

## Reproduction performed by this reviewer

From the root above:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-feedback-program/reviews/prefix-runtime-audit.py
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-feedback-program/reviews/prefix-runtime-audit.py --negative-pfs-header
```

Final positive invocation: exit 0, `PASS_BOUNDED_PREFIX_CPU_RUNTIME`, **407 unique independently hashed pins**, six outer-unit receipts, ten successful stage receipts, two native rejection receipts, 12 compiled sources, 55 native assets, 30 resolved runtime libraries, five compile entries, both native TSVs and eight actual score payloads checked. Existing read-only stage/outer/prepared validators were rerun, alongside independent normalization/PFS1/SEQ-Q-MOVES checks. No acceptance check changed.

Negative invocation changes only an in-memory copy of PFS1 magic to DGS1: exit1, `ValueError: PFS1 header contract failed`. It shows this audit rejects a mislabelled retained score format; it does not qualify a new native corruption guard. Script SHA256 is `83b3a30a1f4fd6d89a5c4d341370ca000b67774602e6b14f1c4a3eda6a85faa8`.

Read-only inspection also used `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, `cat`, bounded `sed`/`rg` and `sha256sum` on the paths named here. No broken tool blocked review. A requested per-outer kernel-limits file was absent; only the engineering result snapshot exists, as qualified above. Initial bulk reads were truncated and decisive sections were reread. The two unsuccessful supplemental link-order metadata checks are disclosed above; neither changed artifacts or ran a linker. Raw failed attempts remain in the session/tool record and original producer receipt tree.

## Next minimal causal consumer seam and uncovered risks

Create the next consumer in a new owned module/worktree, keeping these qualified producer paths read-only. Its location input must be each actual prefix TSV's own SEQ/Q, bound to its native completion/request/H. Return a bounded location-candidate set, including **unknown** and **multimap**, against a predeclared pinned reference/index. Do not obtain the location from whole-read alignment, the old q0 center12333, historical case coordinates, future signal or truth. MOVES can bind base indices to nominal stride rows; it does not establish exact event boundaries or committed bases.

PFS1 adapter metadata must remain distinct from the old DGS1 parser:

```text
PFS1\t681\t1024\t4\t6\tcpu\tfloat32\t4096\t10\t4086\t4086
PFS1\t2047\t1024\t4\t6\tcpu\tfloat32\t12288\t10\t12278\t12282
```

Payloads are rank3 contiguous NTC `[1,T,1024]`, time-major after the singleton batch, IEEE little-endian FP32; this is not a half-precision CUDA DGS1 payload. State length4 gives256 states, alphabet A/C/G/T=0/1/2/3, stride6 and1024 transition channels. The pinned native beam source indexes a move from state s by `next=((s<<2)&255)|base`, `channel=4*next+(s>>6)`; stays use the model's fixed blank score2.0, which is not a PFS1 header field. Consumer provenance must therefore include the pinned model/config and uniform native CPU start-state semantics, rather than inventing a known four-base read-start context. PFS1 also does not encode quality calibration or claim CUDA score/clamp parity. Any subsequent partial-path decoder needs a declared uniform-state contract; the old center-window fixed-state contract cannot be silently reused.

Both horizons recompute/reset the encoder; reverse FLSTM layers can use all samples inside their available prefix. Same-H future-tail invariance does not prove cross-H early-score stability, continuing hidden state, an anytime output commitment rule or causal convolution/LSTM streaming. Prefix acquisition/calibration availability in a real live feed remains outside this offline POD5 proof. CUDA-linked initialization/device behavior was not traced; a CPU tensor/decoder path and pinned CUDA-linked runtime closure do not prove zero GPU activity. No location consumer, feedback intervention, biological correctness/ALT retention, independent molecule, complete input processing, HG005 selection, GPU parity or performance endpoint was executed. These are the remaining substantive boundaries; no material blocker was found for consuming the frozen CPU prefix artifacts under the next declared causal unit.
