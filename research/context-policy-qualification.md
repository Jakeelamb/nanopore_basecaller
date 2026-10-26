# F2 source-ready qualification request

## Explicit JSON string extraction, 2026-10-26

The actual `qualification-03` unit passed the namespace control and configure, then failed strict compilation at `protocol.cpp`'s two hash comparisons between `std::string` and JSON values. The retained build errors are `results/context-policy/qualification-03/stages/build/stderr`; the failed attempt remains unchanged. Tests did not start.

All JSON string comparisons in the F2 boundary now extract strings through the existing `str()` validator, which calls `get<std::string>()`. The two C++ fixture assertions also extract their selected ID explicitly. JSON-to-JSON whole-binding equality stays intact. Policy algorithms, constants and gates are unchanged. Root must first admit formatting of exactly `tools/context_policy/src/protocol.cpp` and `tools/context_policy/tests/controls.cpp`, then refreeze the source before a fresh full engineering unit. No formatter or build was run by this source fix.

## Stage directory correction, 2026-10-26

The admitted `qualification-02` attempt failed after configure succeeded with exit0. Its build receipt directory collided with CMake's existing `build/` directory, so compilation and tests did not start. The failed attempt remains at `results/context-policy/qualification-02`, its outer receipt at `qualification-02-outer`, and its macro receipt at `/home/jake/Projects/nanopore_basecaller-retrieval/logs/20261026T195129Z-feedback-f2-qualification-02-TIDkPo`. The earlier `qualification-01` outer attempt also remains failed; its tool-metadata path rejection occurred before the qualifier launched.

Stage receipts now use `stages/<name>/`, separate from CMake's `build/` artifacts. Stage setup is inside the error handler. The top-level terminal record identifies the attempted stage, argv and directory even when setup fails. Existing receipt directories are rejected without modifying their contents.

Before configure, an admitted local namespace control creates a build directory and runs one empty Python child through the production stage recorder. It then rejects an attempted duplicate stage before launching another child and checks that all retained records are unchanged. Its evidence is `namespace-control.json` and `namespace-control/stages/build/`. This control is prepared and has not run at this source handoff.

The next child command is the fixed-UV command below with `--output /home/jake/Projects/nanopore_basecaller-next-context-policy/results/context-policy/qualification-03`. Expected links now include `namespace-control.json`, `stages/{configure,build,format-check,ctest,uv-tests}/{command.json,cwd.txt,start.txt,end.txt,exit-status.txt,stdout,stderr,time.txt,terminal.json,complete.json}`, plus the existing top-level terminal, completion, JUnit, unittest and compile-command files. Root supplies a fresh in-root `TMPDIR`. Caps and the frozen F4 boundary are unchanged. A fresh configure binds the corrected qualifier into the compiled source witness. No formatter or numerical source changed in this correction.

## Formatted engineering handoff, 2026-10-26

Root's format-only attempt `results/context-policy/format-01` completed with exit0. Its admission SHA256 is `7a63728f7bcdb9730d9293f3cecb787c9cf72d925b621e0e4175c9d312fa09b1`. `terminal.json` retains the actual exit and cleanup, and `outer-terminal.json` records both groups empty before unlock with no error. The raw wrapper receipt is `/home/jake/Projects/nanopore_basecaller-retrieval/logs/20261026T193529Z-feedback-f2-format-01-f7UELD`. Seven owned C++ files changed. Independent whitespace, comment and include-order normalized comparison against the reviewed head passed. No numerical change was made.

`tools/context_policy/qualify.py` now runs the five existing stages sequentially. It writes each stage's eight raw command, cwd, start, end, exit-status, stdout, stderr and GNU time files, then its terminal record, before projecting success. A failure stops the chain and preserves its directory. This runner adds no lock, process-group manager, kernel limit or timeout. Root must launch it through frozen F4 `bounded.py` SHA256 `8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4` at F4 revision `d190ab3f8175f1af7b5d4057b893ef6424b9d41f`.

The next exact child command, with this worktree as cwd, is:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python tools/context_policy/qualify.py --output /home/jake/Projects/nanopore_basecaller-next-context-policy/results/context-policy/qualification-01
```

The fresh build is `qualification-01/build`. Configure explicitly selects `/usr/bin/c++`, `/usr/bin/make`, Release and compile-command export. The UV test stage sets `CONTEXT_POLICY_BINARY` to that exact new binary. Acceptance requires the exact12 CTest names with no failure/error/skip and exactly10 successful UV unittest methods with no skips or expected failures. The unit retains `ctest.xml`, `unittest.json`, `build/compile_commands.json`, each stage's raw files and `terminal.json`; it writes `complete.json` last and syncs it. F4's separate terminal-tree proof remains required.

Requested whole-unit caps remain wall300s, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, aggregate4GiB and reserve30GiB. Use the canonical NONBLOCK lock once, without retries. Only Root admits and launches this command. Tests actually run at this source handoff remain0. The qualifier is included in `source-files.json`, so compiled source validation binds its exact bytes. Registered tool/header pins come from `ready-native-v2-4/tools.json` under targeting-v2 and PR15's `tools/uncertainty_feedback/dependencies.json`; executable bodies remain stat-only during preparation. Dynamic compiler/system-header/OpenSSL dependency closure requires separate retained evidence and is not inferred from these entries.

Everything below records the original unformatted source request. Genuine F1 integration, calibration, biological accuracy and performance remain held.

Status: SOURCE-READY, execution not admitted. Tests actually run: 0. Build, format-check, CTest, UV tests, genuine producer integration, calibration, and scientific pilot have not run. This report is preparation evidence, not PASS.

The first source cut adds the pure C++23 policy, strict raw-FilePin consumer, synthetic independent candidate-map oracle, CLI controls, UV coordinator, and predeclared development configuration. The initial candidate-map oracle enumerates 150 exact quarter-unit cases and checks objectives, full eligibility reasons, decisions, and candidate permutations. Twelve CTests and ten UV unittest methods are prepared without skip paths. Execution will establish their actual outcome.

## Requested CPU unit

Cwd: `/home/jake/Projects/nanopore_basecaller-next-context-policy`.

Environment: `UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv`.

Root must admit the immutable source commit and supervise the whole unit, including source, executable, dependency and input hashing. Caps are wall 300 seconds, two CPUs, RAM 4 GiB, address space 8 GiB, swap 0, growth 100 MiB, cumulative program output 4 GiB, and free reserve 30 GiB. Use the canonical host lock NONBLOCK. Refusal ends the unit without retry. No GPU, model execution, download, or heavy scientific input is requested.

The unit uses these exact commands in order:

```sh
cmake -S tools/context_policy -B results/context-policy/qualification/build -DCMAKE_BUILD_TYPE=Release -DFEEDBACK_BASE_ROOT=/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results -DFEEDBACK_CLANG_FORMAT=/usr/bin/clang-format
cmake --build results/context-policy/qualification/build --parallel 2
cmake --build results/context-policy/qualification/build --target format-check --parallel 1
ctest --test-dir results/context-policy/qualification/build --parallel 1 --output-on-failure --no-tests=error --output-junit results/context-policy/qualification/ctest.xml
uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python -m unittest discover -s /home/jake/Projects/nanopore_basecaller-next-context-policy/tests -p test_context_policy.py -v
```

Expected outputs are two static libraries, `context-policy`, `context-policy-controls`, twelve executed CTests with skipped 0, JUnit at `results/context-policy/qualification/ctest.xml`, and ten executed Python tests with skipped 0. The tests include a genuine invocation of this C++ policy from a synthetic producer and a separately bound stale-input rejection. They do not substitute for a genuine F1 producer fixture.

The admitted unit must retain exact argv, cwd, environment, source and tool pins, start/end, return code, full stderr/time, kernel caps, and terminal process-tree evidence. The Python adapter records its command before projection and writes completion last with fsync. It delegates process-tree supervision and admission to Root's outer unit. Its timeout result explicitly remains unqualified for process-tree closure.

Formatting was not executed during source preparation. Root may need a separate source-formatting grant after the first `format-check` observation. Any failed attempt remains failed; fixes need an immutable new source pin and fresh execution admission.

## Source and dependency inputs

The branch starts from `b5acc27c956ea8f4efda57cdf0c4e51cd287068f`. The delivered commit ID is the immutable source pin relayed with this report. `tools/context_policy/source-files.json` declares all compiled and orchestration sources. Configure hashes and embeds that census and the pinned external JSON header. The CLI verifies actual source bytes and cwd before consumption.

Read-only dependency source is PR15 `400063e97c476303c6a113fb0aab5d0698f0984f` at `/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-results`. Its dependency metadata supplies nlohmann JSON 3.11.3 at `/home/jake/Projects/tools/clang-uml-src/thirdparty/nlohmann/json.hpp`, SHA256 `9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6`. OpenSSL Crypto is a local system dependency. No network fetch occurs. The qualifier must pin the actual compiler and OpenSSL runtime because no new runtime qualification exists yet.

The registered formatter pin is rechecked by CMake inside the admitted unit. During preparation, the engineer mistakenly ran `sha256sum /usr/bin/clang-format` once, reading 104608 executable bytes outside the stat-only preparation boundary. This was a preparation violation. It executed no formatter, compiler, test, model, or scientific binary. No later executable body hashing occurred in preparation. The local preparation note preserves this failure instead of describing preparation as entirely stat-only.

## Scientific pilot remains held

There are no immutable genuine F1 development input pins. `development_input_pins` is empty, which prohibits a development run. Root must first relay a frozen producer source and batch FilePins. The first later pilot is bounded to four original parents, sixteen batches, 4096 candidates and 64 locations per batch, and 8 MiB per raw JSON file under the same 300-second CPU caps. It must run genuine producer consumption plus a rejection before any expansion.

For each admitted request, the exact child command is:

```sh
uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python scripts/context-policy.py --binary ABSOLUTE_QUALIFIED_BINARY --binary-sha256 FROZEN_BINARY_SHA256 --request ABSOLUTE_FROZEN_REQUEST --request-sha256 FROZEN_REQUEST_SHA256 --output ABSOLUTE_FRESH_OUTPUT --timeout 15
```

The uppercase operands are unresolved immutable inputs, so this is a command template and cannot currently be admitted. No biological or performance result is claimed. The synthetic wrong-confident-reference case is expected to choose the wrong allele inside the declared neural budget. That is an explicit policy limitation, not a safety success.
