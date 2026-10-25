# Retained-union neural comparator

This diagnostic separates candidate-pool expansion from contextual ranking. It
uses the unchanged, finite neural scores in the qualified v4 candidate packet.
It selects the maximum over each unique sequence with native, escape, or
conditioned provenance. Native wins an exact score tie. Other ties use lexical
sequence order. Empty DNA is a legitimate candidate. Graph-only sequences remain
ineligible even when they have a finite score.

The diagnostic is conditional on the retained pool. It does not generate missing
finalists. Cap and empty-finalist flags do not alter its argmax. Every census row
reports all four flags, their OR as `cap_or_empty_flags`, and marks
`retained_pool_only` as `1` even when all flags are zero. A valid packet
always contains a finite native candidate. Missing native, empty scored union,
unscored eligible candidates, and nonfinite eligible scores reject the unit.
The historical free arm keeps its original cap and empty-finalist abstention.

Before any diagnostic decisions are written, all six historical roles replay
for every case. Sequence, gates, and abstention must match exactly. Numerical
scores use the original absolute tolerance of 1e-11. `historical.tsv` preserves
that replay. `decisions.tsv` separately emits `union_nn`, `reference_free`, and
`disabled_edits`. `union-census.tsv` reports the change from historical free,
scores, unique candidate count, origin counts, and excluded graph-only count.
Origin counts overlap when a sequence has several genuine provenance bits.

No context reward, deficit threshold, margin threshold, truth, mask, event label,
or new neural evaluation enters the union choice. The qualified 52-file decision
source and its source manifest remain unchanged. The diagnostic links only the
unchanged study inference library. Its own explicit census and the study census
form a separate compiled closure. Strict C++23 flags, formatter identity, compiler
identity, and file hashes remain attached to the executable.

The native commands are:

```sh
cmake -S tools/context_decision_union -B NEW_BUILD -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build NEW_BUILD --parallel 2
cmake --build NEW_BUILD --target format-check
ctest --test-dir NEW_BUILD --output-on-failure --parallel 1 --output-junit NEW_JUNIT
NEW_BUILD/context-decision-union qualify --output NEW_CONTROL_OUTPUT
NEW_BUILD/context-decision-union diagnose --cases /home/jake/Projects/nanopore_basecaller-context-feedback-v4/results/context-feedback/v4-prepare-all-1/prepared/cases.tsv --cases-sha256 9cda8f2adcad2c495e300b208e85f009d924d7dd39d46dad8099310817257dd7 --output NEW_DIAGNOSTIC_OUTPUT
```

These commands require coordinator admission and the reviewed external bounded
controller. They are not an execution grant. Normal units have 300 seconds,
two CPUs, 4 GiB RAM, 8 GiB address space, zero swap, 100 MiB output growth,
4 GiB cumulative output, and 30 GiB free disk. The canonical host lock uses a
nonblocking acquisition and remains held until the worker cgroup and launcher
tree are terminal. Historical replay has a conservative native cap of
2,000,000,000 distance cells. The neural argmax uses no edit-distance work.

Tiny native controls cover conditioned improvements, native and lexical ties,
empty DNA, provenance merging and duplicate rejection through the real packet
parser, scored and unscored graph-only exclusion, every cap/empty flag combination,
availability independence, nonfinite rejection, all six historical replay roles,
an independent Cartesian argmax census, actual diagnostic census fields for all
16 flag combinations, and the replay work cap. Tiny diagnostic outputs remain in
the CTest build directory or the native qualification output directory. These controls
establish software behavior only.

Only exact sequence identity across all ordinary cases permits reuse of the
historical free full-parent output, followed by exact SAM-byte and frozen-snapshot
identity checks. Any ordinary difference requires an independent full 64-parent
union comparator and native truth measurement under separate alignment admission.
Private witnesses remain diagnostics and never alter those parent outputs.
