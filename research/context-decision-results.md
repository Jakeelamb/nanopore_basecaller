# Feasible retained-candidate decisions: development result

The candidate is **not promoted**. Complete-parent error rates improve on this
exposed HG002 development cohort, but both reductions fall below the predeclared
1% threshold. Productive ALT support also fails the required 100 observations
per class. Independent review accepts the retained evidence as a subthreshold
development result.

The [protocol](context-decision-experiment.md) and
[pre-outcome comparator clarification](context-decision-comparators.md) remain
unchanged. This experiment changes the decision over retained candidates. It
adds no neural evaluation, candidate generation, context search, threshold fitting,
basecalling, GPU work, or HG005 selection.

## Complete-parent accuracy

Both feasible arms produce the same 42-edit SAM over all 64 original parents.
One new native alignment therefore measures both aliases. Private diagnostic
frames do not alter these parents. The historical raw-veto arm has 37 edits,
historical reference-free has 9, and disabled edits has 0.

| Mask | Native errors / alignment columns | Feasible errors / alignment columns | Relative error-rate reduction against native | Reduction against historical free |
|---|---:|---:|---:|---:|
| 100 | 8785 / 865579 | 8718 / 865563 | 0.760829% | 0.749417% |
| 500 | 3939 / 439381 | 3915 / 439375 | 0.607934% | 0.506674% |

Matched reference exposure is equal for each parent. Insertions account for the
different alignment-column denominators. All parent and genomic-block 95% delta
upper bounds against native and historical free are negative. These technical
resampling bounds do not make the point reductions exceed 1%. The two masks
share parents and do not constitute independent validation.

The full-parent outputs reconstruct exactly from the native SEQ and Q plus the
edit ledgers. Untouched spans retain their original bytes. Replacement spans use
uncalibrated `!` quality. The mapper preserves all 64 primary SEQ and Q records.
The disabled arm matches native, and historical-free SAM bytes match its retained
original mapping input. The feasible SAM SHA256 is
`e451d61479f5bf25205265c0a11d7ef0d8e3c3f3c7f54ffa5b5eb84604fa9ece`.

## Allele and local evidence

All 829 native baseline ALT observations remain ALT: 740 SNVs, 50 insertions and
39 deletions. Historical free retains 830 of 830: 741 SNVs, 50 insertions and
39 deletions. Changed-footprint support is zero ALT observations against native
and one SNV against historical free. Baseline preservation is not productive
edited-site support, F1, or whole-genome allele safety.

All 26 withheld private witnesses retain ALT, with zero loss and zero unresolved
consequences. These are retained diagnostic label joins. They are not an
independent biological cohort.

Five ordinary choices differ from the historical raw-veto decision:

| Case | Mask 100 | Mask 500 |
|---|---|---|
| `ordinary/35/ordinary` | helpful, exposure 21 | helpful, exposure 21 |
| `ordinary/107/ordinary` | unresolved, exposure 21 | no exposure |
| `ordinary/127/ordinary` | helpful, exposure 21 | helpful, exposure 21 |
| `ordinary/164/ordinary` | no exposure | no exposure |
| `ordinary/399/ordinary` | no exposure | no exposure |

The two newly helpful local cases explain part of the decision change. Local
labels do not replace the complete-parent endpoint or its failed gates.

## Same-universe neural comparator

The separate diagnostic selects the neural maximum over the finite retained
native, escape and conditioned union. It excludes graph-only sequences, preserves
empty DNA, and uses native-first then lexical ties. Every census row explicitly
states that the maximum is conditional on the retained pool.

All 368 cases replay all six historical roles. The diagnostic makes zero new
neural calls. Its neural maximum equals historical free in all 368 cases,
including every ordinary case. No case has a cap or empty-finalist flag. Exact
ordinary choice identity permits reuse of the already verified historical-free
full-parent output. No additional union mapping is needed. This result does not
establish a global neural maximum or quality calibration.

## Qualification and retained commands

The original decision source passed strict Release C++23, the formatter check,
one structured CTest case with zero skips, 2941 native controls and 12 Python
controls. Disjoint inference scopes contain 1, 21 and 346 cases. Each scope
replays the complete 368-case historical packet before new output.

The union source passed strict Release C++23, exact compiler and formatter
identity checks, one structured CTest case with zero skips and 189 native
controls. Its separate diagnostic contains 1104 rows across three arms.

The native measurement worker passed its six Python controls and measured both
masks against native and historical free, plus allele observation and comparison.
The whole worker ran with two CPUs, 16 GiB RAM, 24 GiB address space, zero swap,
at most 300 seconds, 512 MiB aggregate output and a 30 GiB disk floor. Actual
kernel checks, canonical nonblocking lock custody, whole-cgroup termination,
launcher cleanup and all eight raw recorder files are retained. The corresponding
normal units used 4 GiB RAM, 8 GiB address space and 100 MiB growth caps.

These are the successful native measurement and union entry commands from the
worktree `/home/jake/Projects/nanopore_basecaller-context-feedback-decision`.
Their admissions are expired retained receipts, not permission to rerun:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/program/run-measure-bounded.py run --arm feasible_escape --emission results/context-feedback/decision-emit-all-1 --output results/context-feedback/decision-measure-feasible-1 --admission logs/context-decision/source-ready/measure-admission-feasible-1.json
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/program/run-union-bounded.py qualify --output results/context-feedback/decision-union-qualify-2 --admission logs/context-decision/source-ready/union-qualify-admission-3.json
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python logs/context-decision/program/run-union-bounded.py diagnose --output results/context-feedback/decision-union-diagnose-1 --qualification results/context-feedback/decision-union-qualify-2 --admission logs/context-decision/source-ready/union-diagnose-admission-1.json
```

The [independent final audit](../logs/context-decision/reviews/runtime-final.md)
records actual commands, outcomes, raw receipt custody, limits and failed
observations. Its [pins](../logs/context-decision/reviews/runtime-final-pins.json)
and the [result manifest](context-decision-results.pins.json) identify the exact
sources and retained completion files. Raw data, references, binaries, mappings
and generated result tables remain outside Git.

Four retained lock refusals remain separate from successful execution: two price
attempts, one observer attempt and one union qualification attempt. An
unused prepared union grant is not counted as an attempt. Reviewer guard and
timestamp failures are retained, and successful native producers were not replayed
to repair observations. Large inputs retain producer-bound hashes and current-size
checks. Runtime library evidence is `ldd`, not loaded-memory maps. Completion files
are written last and synced; rename-atomic publication is not claimed.

This branch extends the source inherited through [PR #6](https://github.com/Jakeelamb/nanopore_basecaller/pull/6)
and targets `main` under repository policy. CPU CI verifies only the contracts
listed in its workflow. It does not establish native GPU execution, full input
processing, biological accuracy, a speedup, independent validation or promotion.
