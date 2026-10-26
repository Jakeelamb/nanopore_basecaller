# F1 qualification01: retained compile failure and source fix

Root's first engineering attempt failed at source `1a90d3e3f4cb13c9b22eb268a157fd373902ce57`. Configure exited0; strict Release compilation exited2. Format-check, CTest and Python tests did not execute. The source fix below has not been compiled, formatted or tested. No native mapper, full-parent identity, reference-body verification, genuine pilot or GPU execution is inferred.

## Retained evidence

The Root unit is90165/CLOSED1, with macro `/home/jake/Projects/nanopore_basecaller-retrieval/logs/20261026T201854Z-feedback-f1-qualification-01-Z6xffd`. Grant `/home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes/grants/f1-qualification-01.json` is29499bytes, SHA256 `8c2f3ec037bc31ca3fc7b090625eb0ae47bb7ebc947c7fd3a7a0e6dda3e51d61`.

The failed build argv was `/usr/bin/cmake --build /home/jake/Projects/nanopore_basecaller-next-prefix-loop/results/prefix-feedback/qualification-01/build --parallel 2`, cwd `/home/jake/Projects/nanopore_basecaller-next-prefix-loop`. Its stage command retains the exact environment. Start was `2026-10-26T20:18:55.798514+00:00`; end was `2026-10-26T20:19:13.608517+00:00`. Exit2 is known and child cleanup is terminal. The F4 worker exited1, with cleanup terminal; outer exit1 records launcher-group-empty, service-cgroup-empty and empty-before-unlock true, failures[], worker_complete false and missing complete.json. These are failure/cleanup receipts, not a successful completion.

All paths below are relative to the F1 worktree. Full ignored evidence remains in place.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `results/prefix-feedback/qualification-01/stage-1/stderr` | 2124 | `20686459ac960504327d4f3804d5d271361af9d2961cd36450895f6adeb14910` |
| `results/prefix-feedback/qualification-01/stage-1/terminal.json` | 319 | `4dcc7c49190ae0b19e5ba7f2837c69d1a4162d729b0072c87045e0748e8f36fa` |
| `results/prefix-feedback/qualification-01/failed.json` | 535 | `178386ae0dc4b706f7f5b05a55fab39cff595ec27e5a939c4410d4078e03678e` |
| `results/prefix-feedback/qualification-01-outer/terminal.json` | 374 | `8df644f277d6666cfd20c82aa40862b54047d870d266627661a828c790e79453` |
| `results/prefix-feedback/qualification-01-outer/outer-terminal.json` | 27012 | `4e725e47e52d96fa1756d5563d5bbbddbae87f40550baf6972685eedc8922c1d` |

## Source decision

All three compiler diagnostics are `-Werror=dangling-pointer=` at the end of the accepted-successive-location-rebind fixture, naming the conditional temporary vectors at old lines599-600. The fixture now declares `initial_locations`, `revised_locations` and `no_locations` before the loop, then selects a const reference among those named objects. Every selected vector remains alive through `Fixture::update` and the rest of the loop. The three actual fixture requests remain two locations on opposite strands, one revised location, then no locations.

The probability-domain oracle, complete retained-state/marginal/rank comparisons, decoder and warning flags are unchanged. Disabling the diagnostic or relaxing strict compilation would not establish the required lifetime. The narrow source trace found no corresponding conditional vector temporary in `src/session.cpp` or `src/location.cpp`; their beam/location references refer to named containers or their live session/request inputs. This is source inspection, not runtime proof or a claim about whether the compiler's previous warning was a false positive.

Only `tools/prefix_feedback/tests/controls.cpp` changed among the six C++ files. The other five still equal the retained format commit `6360ad61286b2dacbab548bb0fbd6c470901319d`. No formatter or execution ran in this correction round. `git diff --check` passed; that is only a whitespace check.

## Next Root format-only unit

Root must author a fresh bounded-command/1 grant through the frozen F4 public CLI. Proposed cwd is the F1 worktree, with the same exact registered formatter/runtime source closure as format01. The sole mutating argv is:

```sh
/usr/bin/clang-format -i /home/jake/Projects/nanopore_basecaller-next-prefix-loop/tools/prefix_feedback/tests/controls.cpp
```

The attempt must be fresh, e.g. `results/prefix-feedback/format-02`. Expected produced source is only the absolute `tests/controls.cpp` path above. Caps: wall30seconds, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, cumulative4GiB, reserve30GiB. The style input is `tools/prefix_feedback/.clang-format`,778bytes, SHA256 `645bc190cb3512908d47b1ebf53f31da633c0398908bf5c2099e5f282204dea6`. The registered formatter pin remains104608bytes/SHA256 `cd50c00c4b3475329257d717f9e778769d00d1eff5c03436ebc39b023ddd6394`. Its body must be checked only inside the admitted worker.

The explicit C++ census before that unit is below, relative to `tools/prefix_feedback`. The same six files remain the CMake format-check census. Root must retain the actual one-file format result and freeze its output source before qualification02; these pre-format pins are not claimed to be the post-format pins.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `include/prefix_feedback/session.h` | 3331 | `0c17eab3cc35acbea493ee6f882ba6c70873cfead6f36c598d258eab31a287ea` |
| `src/io.cpp` | 10604 | `f6e26e39908f07343eb2aa30b4e4913bcd5e87f3e8185ec1dd7061851ddc50cd` |
| `src/session.cpp` | 30729 | `57d116e5cac7bbdd06811d8f75e71e8100466b16bdbb03d6e4d89db0936e944c` |
| `src/location.cpp` | 15255 | `23daceb3e620e06cd44728cee7cb4650e74b57e246f2575bae29f4b5f73b4bc7` |
| `src/main.cpp` | 4312 | `9d76eff3ac75ce288470e322d8b4ee0227e1fc375341b18093f71701776f3632` |
| `tests/controls.cpp` | 41587 | `18681ac229fcafc40c4fd50bd69913acb71ee94dd19f20fffc80dab5b458b332` |

## Fresh qualification02 after format freeze

`tools/prefix_feedback/engineering-plan.json` now names fresh payload `results/prefix-feedback/qualification-02` and outer attempt `results/prefix-feedback/qualification-02-outer`. It is a proposal, not an execution grant. Root must pin the newly frozen source/tool closure and author a fresh grant. The exact payload is:

```sh
env UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python /home/jake/Projects/nanopore_basecaller-next-prefix-loop/scripts/prefix-feedback.py qualify --output /home/jake/Projects/nanopore_basecaller-next-prefix-loop/results/prefix-feedback/qualification-02
```

The qualifier still requires the same configure, strict Release build parallel2, owned format-check, CTest parallel1/no-tests=error/JUnit and fixed-UV consumed controls. Required actual outcomes remain13 C++ groups,15 Python tests and skipped0. Whole-unit caps remain300seconds, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, cumulative4GiB and reserve30GiB. Hermetic input pins are empty; all source/tool pins and kernel limits are checked by F4 inside the worker. No old successful producer is replayed by this source correction, and the failed qualification01 records are preserved.

The historical reference/index/FAI custody gap, separately admitted source-root corruption control, genuine producer/consumer handoff,64-parent disabled identity and three genuine prefix-derived location updates remain open. Engineering success would not close any scientific, native/GPU, accuracy, latency or raw-signal causality gate.
