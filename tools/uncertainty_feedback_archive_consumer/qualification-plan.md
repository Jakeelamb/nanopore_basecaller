# Proposed source qualification and genuine q0 seam

These commands are proposals, not executed checks. Root must first freeze the
exact source closure, review its delta and issue a fresh CPU grant. Keep the
canonical lock, recorder, process supervision and monitored output roots. Stop
on a failed gate. Retain failed raw receipts and partial outputs. Do not rerun
the successful scientific q0 producer.

The proposed qualification ceiling is300s wall time, CPU2, RAM4GiB, address
space8GiB, swap0, ordinary growth100MiB, whole-program cumulative4GiB and free
disk floor30GiB. These are requested limits, not measured cost or capacity.
Build artifacts, controls, raw/gzip overlap, own receipts and SAM outputs all
count. No source preparation step acquired a lock or execution grant.

## Configure, build, format and synthetic controls

Use a fresh namespace under `results/context-feedback`, here predeclared as
`targeting-archive-consumer-qualification-v1`. The controller must refuse an
existing namespace rather than overwrite it. Set the exact request path and
hash in its frozen input closure before execution.

```sh
/usr/bin/cmake -S /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/tools/uncertainty_feedback_archive_consumer -B /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback/targeting-archive-consumer-qualification-v1/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/c++ -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DBUILD_TESTING=ON
/usr/bin/cmake --build /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback/targeting-archive-consumer-qualification-v1/build --parallel 2
/usr/bin/cmake --build /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback/targeting-archive-consumer-qualification-v1/build --target format-check --parallel 2
/usr/bin/ctest --test-dir /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback/targeting-archive-consumer-qualification-v1/build --parallel 1 --output-on-failure --no-tests=error --output-junit /home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2/results/context-feedback/targeting-archive-consumer-qualification-v1/ctest.xml
```

CMake checks the explicit owned C++ census and full source/protocol list. It
generates an own witness from those files plus the exact JSON and zlib headers.
It requires the pinned compiler, formatter, zlib library and Crypto library.
Library Pins copied from the accepted old runtime are historical identity
evidence only until the admitted configure and new runtime inspection verify
their current bytes. C++23 Release uses `-Wall -Wextra -Wpedantic -Wconversion
-Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off`.

`format-check` invokes the pinned `/usr/bin/clang-format --dry-run --Werror` on
every owned C++ file. No formatting command ran during preparation. A later
format correction changes the own closure and requires a refreshed freeze.

CTest registers one test, `archive_consumer_synthetic_controls`, timeout60s.
The source declares47 cases,7 acceptance and40 rejection. All remain unexecuted
during source preparation. Two repinned `/./` and `/../` path controls first
confirm the same synthetic file size/SHA, then require normalization rejection
at the central Pin boundary rather than a hash mismatch.
Its sole command is the new executable's `controls --scratch ABSOLUTE_BUILD_PATH/synthetic-controls`.
The control command uses exclusive synthetic files and retains `report.json`.
Require exactly one executed test, no failed, skipped, disabled or missing tests,
and all named report cases passed. A repeated run needs another fresh admitted
build/control namespace. Synthetic controls do not establish genuine producer
or biological acceptance.

The source controls cover Raw/Gzip identity, stale compressed Pin versus
repinned CRC failure, truncation, deterministic header, trailing bytes, a second
gzip member, raw size and hash mismatch, raw/compressed hard limits, absent/raw
symlink files, malformed codec/proof/JSON/descriptor, missing/extra/duplicate
trace entries, native3/producer4 catalogue omissions/extras/duplicates, wrong
producer/result/stdout/source32, native geometry, foreign frame/PLAN/construction,
zero scalar comparisons, own-versus-old witness, substitutions, insertions,
deletions, two edits, reverse order, identity and overlap rejection.

Record new compiler/backend/linker, dependency and runtime inspection using
the existing recorder. Pin the new binary and its actual runtime libraries.
Retain configure/build/format/CTest argv, start/end/exit, stdout/stderr/time,
compile_commands, CMake cache and generated own witness. The exact accepted old
source43/binary/runtime/controls and old decoder manifest/source32/binary stay
input dependencies; they are not newly generated witnesses.
Retain compiler dependency files and pin the actual read-only system headers
and link inputs that they identify. The hand-written own census covers the
module plus JSON/zlib headers; it does not claim to enumerate the compiler's
entire implicit standard-library/OpenSSL header closure before a build exists.

## Genuine partial q0 comparison

Freeze literal absolute paths and hashes for `PLAN`, genuine `Q0_PART` and the
two requests before launch. The old binary is
`results/context-feedback/targeting-engineering-1/build-native-v2-4/uncertainty-feedback`
with accepted cb480 identity. Use the full genuine512 PLAN and the authentic
`results/context-feedback/targeting-q0-finalize-v2-1/sealed-decoded/complete.json`.
Requests use exactly that part and PLAN, first Raw and then Gzip for the one
original trace. No PLAN rewrite, shortened completion or synthetic511 rows is
allowed. The controller must price the observed input, native trace, temporary
gzip and five64-parent output sizes before admitting this separate seam.

```sh
"$OLD_BINARY" apply --plan "$PLAN" --plan-sha256 "$PLAN_SHA256" --decoded "$Q0_PART" --decoded-sha256 "$Q0_PART_SHA256" --output "$OLD_RAW_OUTPUT"
"$NEW_BINARY" apply --request "$RAW_REQUEST" --request-sha256 "$RAW_REQUEST_SHA256" --output "$NEW_RAW_OUTPUT"
"$NEW_BINARY" apply --request "$GZIP_REQUEST" --request-sha256 "$GZIP_REQUEST_SHA256" --output "$NEW_GZIP_OUTPUT"
```

Variables above are frozen controller fields, not caller-selected alternatives.
Run only under a separate priced ROOT grant. Convert the genuine trace only
through the sibling verified, durable archive state machine. The original
native attempt/result/completion/producer/raw stdout remain unchanged.

Compare exact bytes of all five SAMs, all5x64 named SEQ/Q rows, all edit lists and
union diagnostics among old Raw, new Raw and new Gzip. Verify the actual headers
before interpreting byte differences. Every completion must report one decoded
row,512 nominations, population incomplete and64 parents. Compare genuine part,
row/native complete, seal catalogue, producer catalogue and stdout Pins before
and after. Retain the original genuine q0 raw trace as the native anchor. The Gzip
request must use and validate its archive even while that anchor exists. A bad
gzip must reject without raw fallback. The synthetic missing-Raw control covers
absence without deleting q0. A genuine old-apply missing-Raw rejection remains a
separate deferred gate that cannot justify changing the retained q0 anchor.
Never delete raw before durable archive verification.

Mutate genuine small descriptors with fresh own receipts to exercise missing,
extra and duplicate trace entries, changed original trace Pin, wrong native
completion/producer/stdout, shortened legacy completion, changed PLAN/frame,
old/new source/binary/runtime/ordered input and raw exit guards. Test stale
archive Pin separately from repinned deep gzip CRC/hash/size failures. Rejections
must occur without a successful parent completion. Do not edit accepted native
files to construct controls. A control requiring changed payload uses a fresh
owned copy and an explicitly synthetic provenance chain.

Complete512 input fit, complete population outputs, context-enabled numerical
coverage, matched accuracy/ALT results and biological promotion remain open.
Neither the q0 seam nor CPU qualification closes them.
