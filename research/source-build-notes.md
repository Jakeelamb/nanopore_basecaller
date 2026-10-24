# Unchanged Dorado source build

This qualification builds unchanged upstream input at Dorado commit `8b8fc5d36a9c0baab262a743cb175b5878e38ca6` and its 22 pinned recursive submodule commits, with declared upstream build transformations. Isolated copies protect the canonical source tree. The official Dorado distribution and stock models remain unchanged. Build artifacts, downloads, compiler cache, and raw receipts stay outside Git.

The Release build and scripted rerun passed. The binary reports exactly `2.1.2+8b8fc5d`. Help runs and ELF dependencies resolve. All 55 predeclared CPU test cases passed. The main upstream test binary inventories 610 cases, so 555 cases remain unqualified. The selected names, explicit unselected names, source locations, JUnit report, and raw receipts are pinned in `provenance/source-build-20261023.json`.

## Build decision

Use the installed CUDA 13.4.92 toolkit and an isolated GCC 15.3.0 compatibility toolchain from locally cached, hashed Arch packages. The unchanged source selects its CUDA 13.0 Torch 2.9.0, Koi 0.7.5, and FlashAttention archives when the toolkit is at least 13.0. The [NVIDIA CUDA 13.4 installation guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html#host-compiler-support-policy) lists GCC major versions 6 through 16. Compile-only CUDA probes passed with both GCC 16 and GCC 15, without a compiler bypass flag. Arch Linux itself is outside NVIDIA's listed qualified distributions.

The first full build used installed GCC 16.2.1. It failed because upstream `ModBaseContext.h` uses `uint8_t` without including `<cstdint>`. GCC 15's existing transitive includes permit this header. The isolated GCC 15 header probe passed before a fresh source copy and build directory were created. No forced include, warning suppression, or source fix was used. The failed GCC 16 input and build remain intact.

This is a separate CUDA 13 build stack. The official binary loads its bundled CUDA 12 runtime. A successful source build does not reproduce the vendor binary, rebuild the opaque Koi or Torch kernels, establish GPU parity, or qualify biological accuracy or performance.

The compilation database records 489 C++ and 39 C translation units, with zero CUDA translation units. The default upstream build uses prebuilt Koi, Torch, and FlashAttention kernels. CUDA C++20 was exercised by the compiler probes, while the Dorado sources compile as C++23. A metadata check initially assumed a CUDA translation unit existed. Its failed receipt is retained, and the final record describes the observed compilation database.

CUDA 12.8 was not installed locally. Its standalone installer is 5,412,604,598 bytes before extraction. Its source-pinned Torch archive and expanded files require another 5,445,146,427 bytes. It also needs an older host compiler. The CUDA 13 stack uses the existing toolkit and is the least costly source-supported choice under the disk constraint.

## Upstream build transformations

The upstream CMake files apply ten bundled patches to four submodules. Seven patches modify nested minimap2. Three others modify cxxpool, edlib, and toml11. Both isolated inputs were compared with independent clean clones after applying exactly these bundled patches. Their complete Git diffs match. No other tracked, staged, or untracked source changes were present. The patch hashes, resulting diff hashes, and replay location are in `software/source-build-qualification-20261023/evidence/vendor-transformations.json`.

Before each configure, all 23 Git repositories in the source copy were checked. Every Git directory, worktree, and resolved `core.worktree` stayed inside its owned copy. This prevents the upstream patch commands from changing canonical metadata or files.

The first configure computes the generated Dorado version before these upstream patches run. The accepted GCC 15 configure generated exactly `2.1.2+8b8fc5d`, checked before compilation. Reconfiguring an already transformed source copy can add `+dirty`. The rerun script reuses a successful existing configuration and checks the exact generated version. A changed configuration requires a new pristine input copy. No version string is rewritten.

## Resource budget

At inventory, the filesystem had 49,701,539,840 bytes available. The required reserve is 30 GiB. The initial conservative allocation was 12 GiB, including retained archives, expanded dependencies, 6 GiB for objects and links, and a 1 GiB isolated compiler cache. Six compile jobs limit memory pressure. The upstream HTSlib external build independently uses one quarter of the detected processor count.

The configured cache limit is decimal 1 GB. The 1 GiB figure above is its conservative budget. At acceptance, 44,263,702,528 bytes remained available, above the runtime admission threshold of 30 GiB reserve plus 8 GiB headroom. Logical allocations were 2,831,499,908 bytes for archives, 2,721,324,273 for dependencies, 1,174,150,240 for the accepted build, 188,088,016 for GCC 15, and 52,786,842 for the cache. Failed attempts and both input copies remain present. Later available space increased externally. This owner deleted nothing, and free-space deltas do not establish unique build allocation.

Remote ZIP directory checks measured these sizes before large downloads.

| Archive | Compressed bytes | Expanded bytes |
| --- | ---: | ---: |
| Torch CUDA 13.0 | 1,281,640,079 | 2,151,486,149 |
| Torch CUDA 12.8, rejected alternative | 2,016,718,479 | 3,428,427,948 |
| FlashAttention CUDA 13.0 | 22,810,302 | 119,686,143 |

The ZIP inventory is retained at `software/source-build-qualification-20261023/evidence/remote-zip-budget.json`. The Torch sequential transfer was deliberately cancelled after it projected approximately 17 minutes. The incomplete file and exit-143 receipt remain available. Four bounded HTTP ranges replaced it. Their retained parts and assembled archive add temporary duplicate storage within the allocation.

## Execution evidence

- Initial source, submodule, host, compiler, package, and official-binary dependency inventory passed in `logs/20261023T015816Z-source-build-inventory-SP8OJn`.
- Source and recursive submodule archive hashes passed in `logs/20261023T020107Z-source-build-source-pins-m608pz`.
- The CUDA compile-only probe passed in `logs/20261023T020105Z-source-build-cuda-compiler-probe-ZryiZl`. It did not execute a GPU kernel.
- The cancelled sequential Torch download is `logs/20261023T015850Z-source-build-fetch-torch-th5IRQ`.
- The GCC 16 full-build failure is `logs/20261023T021005Z-source-build-compile-3VP8tc`.
- The successful GCC 15 header and CUDA probes are `logs/20261023T021430Z-source-build-gcc15-header-probe-0gALek` and `logs/20261023T021508Z-source-build-cuda-gcc15-probe-0wBuB4`.
- GCC 15 configuration passed in `logs/20261023T021522Z-source-build-configure-gcc15-9jeI6i`. Its exact version header passed in `logs/20261023T021552Z-source-build-gcc15-version-header-VGpzHm`.
- All upstream source transformations passed independent replay in `logs/20261023T021647Z-source-build-all-vendor-transformations-FErTmw`.
- The full GCC 15 build passed all 582 tasks in `logs/20261023T021552Z-source-build-compile-gcc15-bH5YBZ`.
- The rerunnable build and acceptance lever passed in `logs/20261023T022540Z-source-build-rerun-acceptance-gpe3ZE`. An earlier wrapper used `bin/dorado_tests` instead of upstream's actual `tests/dorado_tests` path. Its exit-127 attempt remains recorded.
- The CPU selection passed with zero errors, failures, or skipped selected cases in `logs/20261023T022546Z-source-build-cpu-tests-nWePnH`. Catch's JUnit `tests` attribute counts assertions, which totaled 6,750,655. It does not count the 55 selected cases.

Run `scripts/build-dorado-source.sh` to repeat the pinned build and CPU acceptance using the isolated GCC 15 prefix. Its extraction command and package hashes are in the provenance record and raw receipts. The lever preserves the existing successful configuration, validates source transformations, verifies dependency archives, and records every build and acceptance command. An independent clean-machine rebuild remains unqualified.
