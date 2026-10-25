# Feasible contextual decisions over retained candidates

This is a separate development experiment from base revision
`6a8c23e8a34d37bef76f25c30cc007bf429deae5`. Its hypothesis and endpoints are
recorded before new decision outcomes. Historical results and the original three
experimental arms remain unchanged. HG005 does not select any policy or parameter.

The historical weak policy maximizes `L(s) - 0.5 min_path distance(s, path)` and
then vetoes its winner when the neural deficit exceeds 0.5. A lower-ranked
candidate can satisfy both unchanged gates and remain unused. The new policy
maximizes the same objective over candidates satisfying `L(s) - L(free) >= -0.5`,
then requires objective improvement of at least 0.5 against the actual matched
reference-free candidate. This is a decision change, with no new signal model,
mutation model, neural evaluation, candidate generation, threshold, or fitting.

`feasible_escape` uses native plus escape finalists. `feasible_partial` adds the
retained, scored conditioned finalists. Graph-only unscored strings remain
ineligible. Both arms retain native-first and lexical tie breaking, center-bound
abstention, and the existing eligibility constraints. Missing or ambiguous context
returns the actual matched reference-free arm, which can differ from native.
The disabled-edits control preserves native SEQ and Q. Both zero-weight controls
return matched reference-free SEQ, including when a conditioned cap exists.

Before either new arm is emitted, C++ replays all six historical roles for all
368 retained cases and checks sequence, gates, abstention, and scores against the
saved packet. Failure stops the unit. `raw_veto_escape` and `raw_veto_partial`
remain explicit comparison arms. The 311 ordinary, 31 private ordinary, and 26
private withheld cases all enter inference without truth or mask labels.

The input packet is
`/home/jake/Projects/nanopore_basecaller-context-feedback-v4/results/context-feedback/v4-prepare-all-1/prepared/cases.tsv`,
SHA256 `9cda8f2adcad2c495e300b208e85f009d924d7dd39d46dad8099310817257dd7`.
Its source preparation and execution must be qualified at the immutable v4
program's actual location. The new scorer reuses unchanged local C++ study
packet, replay, edit-distance, and SHA256 code. The explicit source census includes
the original absolute source paths retained in that study's source census.

## Endpoints and interpretation

First report exact historical replay, finite candidate eligibility, feasible pool
counts, policy choices, changes relative to matched free and historical arms,
and query-slice resource receipts. Join frozen choices to existing qualified
C++ atlas labels by case identity and DNA digest only after inference finishes.
Report both mask100 and mask500 local helpful, harmful, neutral, no-exposure,
and unresolved classifications. Join private event labels separately and retain
all 26 withheld witnesses, including any loss. Private results do not tune arms.

Full measurement splices only the 311 ordinary centers into all 64 original
parents. Private diagnostics do not alter ordinary parent outputs. Preserve
unchanged native sequence and quality spans. Changed centers carry `!`, which is
uncalibrated. Reject overlapping edits, mismatched native attachment, duplicate
parents, missing parents, and no-op edit ledger entries. Deduplicate exact SAM
bytes before mapping. Reuse a historical mapping only when exact SAM bytes and
the frozen input snapshot both match.

The input snapshot remains
`/home/jake/Projects/nanopore_basecaller-reference/results/reference-frontier/flank-seam-v1/input-snapshot-v2.json`.
Native aligned-read metrics cover both 100 and 500 masks, with native and actual
reference-free comparators. The unchanged biological gates require at least 1%
relative error-rate reduction in both domains, strictly negative technical
parent/block upper bounds, at least 100 productive ALT observations per class,
and all private26 safety checks. Engineering qualification is separate from
these gates. Failure is retained; no gate or parameter changes follow outcomes.

## Execution sequence

Source preparation runs no experiment, compiler, neural model, GPU, or download.
The coordinator reviews a frozen source cut after a format-only unit. A separate
engineering unit then builds Release C++23 with all strict warning flags,
`-fno-fast-math`, and `-ffp-contract=off`, runs the independent finite candidate
census, reads structured CTest JUnit, and checks Python boundary controls.
Compiler, formatter, compile commands, runtime libraries, source closure, binary,
cwd, clocks, time, exit status, and raw stderr/stdout remain pinned.

New policy inference proceeds in disjoint scopes: `query0` is ordinary query0,
`first32` contains ordinary queries1 through31, and `remaining` contains later
ordinary cases and all private diagnostics. These names refer to original
numeric query IDs, not lexical packet positions. Price all scopes without truth,
then admit query0, the first32 checkpoint, and the remaining scope separately.
Reuse successful retained scope outputs. Do not infer fit from pricing alone.

Every normal unit has a fresh external admission, a nonblocking canonical host
lock, 300 seconds, two CPUs, 4 GiB RAM, 8 GiB address space, zero swap, 100 MiB
new output growth, a 4 GiB total output ceiling, and 30 GiB free disk. Mapping
requires a separate reviewed 16 GiB RAM, 24 GiB address space, two-CPU,
300-second, 512 MiB source envelope. The controller retains the canonical lock
until both the whole worker cgroup and the launcher tree are terminal.

All Python commands use the existing retrieval environment:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/context-decision.py source-inventory
```

Execution and independent review remain queued with the coordinator until it
grants a unit. There are no new accuracy or speed results in this source cut.

The native price reports union distance cells and a conservative distance-cell
upper bound that includes whole-packet historical replay and every new ranking.
The hard native cap is 2,000,000,000 cells per invocation. Query-slice runtime
receipts determine subsequent admission.
