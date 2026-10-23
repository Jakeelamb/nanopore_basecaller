# Independent benchmark correction review

Verdict: **PASS for the seven local contract corrections. Native Dorado qualification remains pending.** No additional blocking defect was demonstrated in the inspected execution path. This verdict permits the next native compatibility and rejection checks. It does not qualify GPU inference, complete human processing, performance, or biological accuracy.

This is an independent same-family Sol review on 2026-10-22. It is not a cross-model-family review. Ownership was limited to this evidence file. No implementation or acceptance check was changed, and no agents were delegated. The Prove It Works principle changed the review method: the reviewer reran the maintained producer handoff and separate rejection controls instead of accepting the worker's passing-test summary.

Throughput checkpoint: n/a, read-only investigation.

## Identified artifact

The repository acquired policy commit `c6abd1bd96b397dc9b4f9564901003ccd5c30057` during review. The inspected scientific files were still untracked on `setup/stock-baseline`; that commit does not identify their contents. These SHA-256 values identify the actual reviewed revision. They matched before and after the checks.

| File | SHA-256 |
| --- | --- |
| `scripts/benchmark.py` | `c3249067d2b12f6b1f69671022b23d844529013b0392f9742daca7863b51af8f` |
| `scripts/prepare-reference.py` | `c2a5097cf610c7a1cb8c4d8779e2f68caae4ab5c704e4109a2d2cc22217dccae` |
| `tests/test_benchmark.py` | `1e6aef33965c2d0824ae5689210ea0e0ce1bf04d6657303678291115c3623e7d` |
| `tests/test_reference.py` | `492c5e3709956bb2fba65000736db787bb26bbf6fe64824f5978f48d28bc36f4` |
| `scripts/record-command.sh` | `f3e0f628d3a32ef0551537ad4acb8585c0690b9203e3f48f765110703e397833` |
| `config/stock-benchmark.json` | `665f4a2fdcf1f1f8ef6bca80123ee91386a55f4e3feaf596895822e1cbbc4ae9` |
| `research/benchmark-commands.md` | `5048becad9001b910d72aa24c5134821049784926cd640e062659b5751a5a7c8` |

The clean stock source remained at `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. POD5 reported version `0.3.49`. At the recorded environment observation, `software/bin/dorado` was absent. The pin and environment evidence is [the artifact receipt](../logs/20261022T204655Z-benchmark-delta-artifact-pins-3INmMU/).

## Commands and observed results

Commands ran from `/home/jake/Projects/nanopore_basecaller`.

```sh
scripts/record-command.sh benchmark-delta-tests uv run --locked python -m unittest discover -s tests -p test_benchmark.py -v
scripts/record-command.sh benchmark-delta-reference-tests uv run --locked python -m unittest discover -s tests -p test_reference.py -v
scripts/record-command.sh benchmark-delta-control-replay bash logs/20261022T204601Z-benchmark-delta-independent-controls-N4h2eK/command.sh
sha256sum scripts/benchmark.py scripts/prepare-reference.py tests/test_benchmark.py tests/test_reference.py
```

The first command exited **0**, with **23 tests, OK**, no skips, and 3.710 seconds reported by unittest. The raw result is [the benchmark test receipt](../logs/20261022T204449Z-benchmark-delta-tests-DD9msY/).

The second command exited **0**, with **9 tests, OK**, no skips, and 2.476 seconds reported by unittest. It exercises native bgzip, samtools, and minimap2 on a two-contig reference spanning multiple BGZF blocks. The raw result is [the reference test receipt](../logs/20261022T204449Z-benchmark-delta-reference-tests-DIgLOL/).

The independent control command was initially executed through `scripts/record-command.sh benchmark-delta-independent-controls uv run --locked python -c ...` and exited **0**. Its complete, shell-quoted Python argument is retained in [the replayable command](../logs/20261022T204601Z-benchmark-delta-independent-controls-N4h2eK/command.sh). The third command above reran that exact entry point and exited **0**, retained in [the replay receipt](../logs/20261022T204843Z-benchmark-delta-control-replay-oy6iy1/). The [initial raw output and execution receipt](../logs/20261022T204601Z-benchmark-delta-independent-controls-N4h2eK/) retain all printed positive and negative outcomes, the live GPU CSV, exit status, clocks, and GNU time evidence.

These controls execute the existing tiny preparation fixture, then independently mutate its inputs and call the production consumer. The fixture creates real POD5 Writer files, real ZIP archives, a BGZF reference, a native minimap2 index, and samtools BAMs. Its Dorado executable is an explicit substitute. Source/version subprocess checks are mocked only by the preparation fixture. None of those constructed Dorado headers or substitute outputs constitutes genuine Dorado evidence. Temporary fixture directories were cleaned; the outer replay command and raw observations remain retained.

## Disposition of the seven findings

| Earlier finding | Inspected correction | Independently observed result | Disposition |
| --- | --- | --- | --- |
| Relative producer pins fail the consumer | `benchmark.py:56` resolves relative paths against `ROOT` and compares byte identity. `prepare-reference.py:24` retains portable relative pins. | Four pins emitted by the maintained reference producer were accepted with the process CWD changed to `/`. The focused integration test then changes the referenced file and observes rejection. | Closed locally. |
| Full membership loses raw input molecules | `benchmark.py:78` re-decodes acquired POD5, compares every metadata row and complete signal summary, and requires full UUID equality before subsets. | Removing one of two development UUIDs fails with `Full membership/inventory mismatch`. Adding an unacquired inventory UUID fails with `Inventory includes unacquired molecules`. The accepted plan contains both actual development parents and six full units. Tests also reject changed sample counts, signal-summary totals, and 4 kHz chemistry. | Closed locally. |
| A stale success survives a current verification failure | `benchmark.py:689` requires the current verifier hash and a successful observation newer than every retained failure. | Reported timing successes were exactly `[0, 1, 0, 1]` for old verifier, current verifier, newer failure, and later successful verification. Tests also reject missing pinned artifacts. | Closed locally. |
| Extracted models are not bound to stock archives | `benchmark.py:123` hashes every ZIP member and requires the exact extracted file census. | Changing a weight before preparation fails with `Extracted model differs from stock ZIP`. Tests reject extra and missing files. Valid fixture archive extraction is accepted. | Closed locally. |
| Arbitrary or unpinned parity evidence is accepted | `prepare-reference.py:143` records both tiers, native producer receipts, decoded inputs, outputs, mapped work, and flattened pins. `benchmark.py:144` validates the complete structure and canonical aligned records. | A changed nested SUP parity BAM is rejected after plan freeze. Pending HAC parity and a missing SUP input producer are rejected. Tests reject the old truthy string, a missing tier, missing nested pins, zero mapped records, and changed decoded evidence. Reference tests reject samtools-only and failed producers. | Closed as a producer/consumer contract. Genuine native parity is still required. |
| Successful retries conceal earlier failures | `benchmark.py:703` projects every stage attempt, its supersession state, and separate unit and attempt counts. | A real generic process exits `[7, 0]` on its first invocation and explicit retry. The report retains both attempts and returns `failed_basecall=1`, `basecall_attempts=2`. Tests additionally retain an interrupted attempt and native process resources. | Closed locally. |
| GPU values with units are discarded | `benchmark.py:500` accepts supported native units and counts unavailable fields separately. | The actual query returned `294 MiB`, `2 %`, `18.65 W`, `48`, and `2377 MHz`. The projection returned those five numeric values, each with zero unavailable samples. Tests separately exercise unavailable fields. These are idle review observations, not a GPU benchmark. | Closed locally. |

The meaningful rejection controls failed for the intended reason. A passing build or agent agreement was not used as the proof.

## Native path inspection and limits

Source inspection at the pinned Dorado revision supports the planned handoff. `read_pipeline/base/messages.cpp:117` emits `ns` as retained signal plus trimmed samples, `ts` as trimmed samples, and `pi` with `sp` for split children. `hts_writer/SummaryFileWriter.cpp:216` skips secondary and supplementary records. Its alignment counts at line 379 agree with the runner's primary-child EQX summary checks. `hts_utils/bam_utils.cpp:269` includes both `=` and `X` in aligned matches and derives substitutions from NM after indels. The basecaller CLI exposes the selected read IDs, minimum quality, trim, and batch-size options. The aligner exposes `--no-sort`. These are source conclusions; installed executable compatibility remains a runtime question.

The updated report includes native attempt clocks, CPU times, RSS, sampled GPU fields, preparation processes, and qualification controls. Inspection confirms the fixed interleaved timing order and no automatic retry of failed stages. Tests execute real generic child interruption and immutable producer reuse. They do not establish real Dorado batching, native timing throughput, GPU peak memory, or freedom from later external contention.

Required runtime evidence remains open:

- Verified installation and extraction of the official Dorado distribution and exact models.
- Complete human signal inventory and frozen plan using the acquired inputs.
- Genuine native FASTA versus MMI parity for both stock tiers on the complete reference.
- Genuine split children under the exact selected model and rejection controls derived from those outputs.
- Both smoke units, all ten fresh-process timing observations, and all six full shard/model units.
- Actual native loader diagnostics, input absence ledgers, effective batch and chunk settings, wall clocks, resource samples, and reserve checks during those runs.

The native qualification gate must run before expensive full or timing execution. It can still reveal a source-assumption or platform mismatch. Retain such a failure and its producer evidence. This review supplies no measured performance comparison and no model winner.

Reference disagreement remains conditional on mapped emitted primary children. Biological base accuracy, biological quality calibration, variant-aware accuracy, and variant-calling accuracy remain **NOT VERIFIED**. The declared pilot size and flowcell selection do not establish population representativeness or unseen training data.

No required tool was broken during the successful checks. Exploratory `rg` commands initially named nonexistent source paths and exited 2; subsequent `rg --files` discovery found and inspected the correct paths. A `git show HEAD:scripts/...` probe confirmed those files were absent from the policy commit; the empty downstream pipe hash was not used as a file identity. Missing native Dorado evidence and uncommitted scientific files are disclosed limitations.

## Scoped comment disposition

The six internal or test narration comments named by the earlier review are absent from the corrected benchmark and test files. One deletion suggestion remains at `scripts/benchmark.py:1`, the module narration reused as argparse's description. It is a nonblocking prose issue. No application refactor is indicated. Comments were not edited. New `MUST KILL` findings: **0**. Child comment agents: **0**, per the explicit no-delegation assignment.
