# Independent native build contract review

Verdict: **PASS for the strict native version delta.** The corrected contract accepts the installed stock `2.1.2+8b8fc5d` binary output and both genuine GPU BAMs, and rejects bare or different build identities. The genuine two-tier FASTA/MMI receipt also passes the production consumer. No blocker was demonstrated in this delta. Full-shard processing, the declared timing experiment, and biological accuracy remain unqualified by this review.

This independent same-family Sol review ran on 2026-10-22. Scope was the four-file diff from `174d6950abaac7454fa21534c6578dfe48bd6d19` on `setup/stock-baseline`, following the seven accepted corrections in [the preceding review](implementation-delta-review.md). Only this assigned research document and local command receipts were written; implementation and maintained acceptance checks were unchanged. No child agents were delegated. No commit or merge was performed. The Prove It Works principle was applied by reading actual producer artifacts, rerunning checks, and reproducing the defect against the base revision.

## Identified revision

The reviewed implementation was a working-tree delta, so the base commit alone does not identify it. The exact four-file `git diff --no-ext-diff HEAD -- ...` was 13,572 bytes with SHA-256 `718fe0b6c983cf9698a49605eebc7c3c73026a755f015e1cd6ab6eda813eca9c`. [Artifact pins and the scoped comment check](../logs/20261022T211123Z-native-contract-review-artifact-pins-naKINw/) identify the reviewed files:

| File | SHA-256 |
| --- | --- |
| `scripts/benchmark.py` | `de401cef99ef5a0c71491410cdc572bdb447ad8418f893c3030f501bbd08a06f` |
| `scripts/prepare-reference.py` | `2467d465aa2bbe3ea47653d91858db235c55e3f4df775f74dda956ac20bbb84e` |
| `tests/test_benchmark.py` | `b660d3da2e20fab0c14b3b000182111220b133673cf06fdac1dd519b76d8a0e9` |
| `tests/test_reference.py` | `21e9dc3ce61008db9af6b8495cfa3d96726b6a74191ec077cb51756f9de24edd` |

The installed `software/bin/dorado` resolves to the distribution binary with SHA-256 `08fef6060d9672f1e7b1772470b93ff0750d28d15f2e64cef1d02533a03ebb49`. The stock source checkout was clean at `8b8fc5d36a9c0baab262a743cb175b5878e38ca6`. The retained BAM hashes were HAC `6abadbbe18684ab642f3a05a66ab8d04627d4efc3b3706009376677f8f035888` and SUP `30310da8e56925e8944f7c7a9933b4c0eb8176cec31fa0f12d2f3c202df51fb4`.

[Final pin replay](../logs/20261022T211545Z-native-contract-review-final-pins-Jt4kUq/) exited 0 after all checks. `cmp logs/20261022T211123Z-native-contract-review-artifact-pins-naKINw/stdout logs/20261022T211545Z-native-contract-review-final-pins-Jt4kUq/stdout` exited 0, confirming the same base, diff digest, four file hashes, installed binary, and clean stock source at completion.

## Commands and results

Commands ran from `/home/jake/Projects/nanopore_basecaller`. Each receipt retains its full command, CWD, stdout, stderr, exit status, clocks, and GNU time record. These exact commands were independently executed:

```sh
scripts/record-command.sh native-contract-review-tests env NANOPORE_NATIVE_BAM=logs/20261022T210643Z-manual-dev32-hac-sxfbo5/stdout uv run --locked python -m unittest discover -s tests -p test_benchmark.py -v
scripts/record-command.sh native-contract-review-reference-tests uv run --locked python -m unittest discover -s tests -p test_reference.py -v
scripts/record-command.sh native-contract-review-controls-replay bash logs/20261022T211103Z-native-contract-review-independent-controls-3ADGkz/command.sh
scripts/record-command.sh native-contract-review-parity-base-replay bash logs/20261022T211312Z-native-contract-review-parity-base-controls-final-l7PRQT/command.sh
```

| Check | Observed result | Receipt |
| --- | --- | --- |
| Benchmark tests with genuine HAC input enabled | Exit 0; 26 tests; no skips; unittest reports 6.700 s | [Raw test evidence](../logs/20261022T211011Z-native-contract-review-tests-C4VeV7/) |
| Reference tests | Exit 0; 10 tests; no skips; unittest reports 4.328 s | [Raw test evidence](../logs/20261022T211011Z-native-contract-review-reference-tests-CMyAOB/) |
| Actual binary, both GPU BAMs, and independent rejection controls | Initial and exact Bash replay exit 0 | [Original complete command and output](../logs/20261022T211103Z-native-contract-review-independent-controls-3ADGkz/), [replay](../logs/20261022T211335Z-native-contract-review-controls-replay-4A1w97/) |
| Parity-consumer rejection and base-revision reproduction | Initial corrected control and exact Bash replay exit 0 | [Complete command and output](../logs/20261022T211312Z-native-contract-review-parity-base-controls-final-l7PRQT/), [replay](../logs/20261022T211335Z-native-contract-review-parity-base-replay-297pkS/) |
| Genuine two-tier parity through production `parity_evidence` | Exit 0; exact headers, nested pins, mapped work, reference dictionary, and canonical FASTA/MMI equality accepted | [Complete command and output](../logs/20261022T211421Z-native-contract-review-genuine-parity-consumer-1TfuYn/) |

The short Python entry points for artifact pins and genuine parity were invoked through `scripts/record-command.sh ... uv run --locked python -c ...`; their complete, shell-quoted arguments are in the linked `command.sh` files. They can be rerun exactly with:

```sh
bash logs/20261022T211123Z-native-contract-review-artifact-pins-naKINw/command.sh
bash logs/20261022T211421Z-native-contract-review-genuine-parity-consumer-1TfuYn/command.sh
```

## Native behavior and negative cases

The installed binary emits stdout `2.1.2+8b8fc5d\n` and an informational `Running: "--version"` line on stderr. The new stdout-only equality accepts the genuine value. The preceding substring check did not bind the build; merging stderr into the comparison would also prevent exact equality. The production preparation function accepted the captured native stdout in the maintained small fixture. Substituting each of `2.1.2`, `2.1.2+0000000`, `2.1.20+8b8fc5d`, and `2.1.2+8b8fc5d-dirty` caused `Wrong Dorado version`. Source/version subprocesses in this preparation fixture remain substitutes; this is not a full acquired-data plan execution.

Both actual GPU producer receipts exited 0 and record `--device cuda:0`, the stock model path, and the selected development read IDs. Independent native `samtools view -h` decoding and production `parse_sam` gave:

| Genuine GPU artifact | Represented/requested parents | Emitted primary children | Split parents | Parser complete processing |
| --- | --- | --- | --- | --- |
| [HAC native BAM](../logs/20261022T210643Z-manual-dev32-hac-sxfbo5/) | 32/32 | 32 | 0 | true |
| [SUP native BAM](../logs/20261022T210702Z-manual-dev32-sup-gGvtpN/) | 32/32 | 33 | 1 | true |

For each BAM, changing only its `@PG` version fields to each of the four values above caused `Wrong/missing Dorado version`. The fixture parity consumer accepted exact-build evidence, then rejected bare and wrong-build headers with `Parity lacks native Dorado version` after all affected fixture hashes were updated consistently. This proves the version check is reached independently of byte-pin rejection. The maintained reference tests separately reject retained parity inputs with bare, wrong-build, and wrong-release headers before native parity alignment.

The reviewer also loaded `scripts/benchmark.py` directly from base commit `174d6950abaac7454fa21534c6578dfe48bd6d19` into an isolated module. It rejected both genuine native BAMs with `Wrong/missing Dorado version`, but accepted each when only the header was changed to bare `2.1.2`. The current artifact reverses those outcomes as required. Neither implementation revision was edited for this comparison.

The coordinator's full native reference producer finished successfully in [its retained receipt](../logs/20261022T210832Z-qualify-native-reference-parity-PmUVmA/). The reviewer independently read `provenance/index-qualified.json`, SHA-256 `cd003cf4a6c3f49be322345ab833cbaacc5861e6141aa79199fb97c3f93e77b2`, and passed it through the actual benchmark consumer. It accepted 204 nested pin entries and equal canonical aligned records for both tiers, against 195 reference contigs totaling 3,099,922,541 bases. HAC had 55 mapped alignment records; SUP had 57. Those counts include supplementary alignments and are not parent counts. The original, FASTA-aligned, and MMI-aligned headers all contain the exact stock build. Native processes were not rerun merely to duplicate their retained artifacts.

## Scoped comments and limitations

Python tokenization and AST docstring comparison against the base revision found unchanged comments and docstrings in all four files. `git diff --check HEAD --` for those files exited 0 with no output. No new narration comment or docstring was added. The existing benchmark module description remains the preceding review's nonblocking prose observation. New scoped `MUST KILL` comment findings: 0. No comment framework or child reviewer was introduced.

Two exploratory evidence probes failed and remain retained. The [first](../logs/20261022T211215Z-native-contract-review-parity-and-base-controls-a1StR5/) used a relative-versus-absolute path comparison while repinning its temporary fixture, so it reached `Unpinned parity producer logs` rather than the intended header guard. A [wrapper attempt](../logs/20261022T211242Z-native-contract-review-parity-and-base-controls-corrected-u7661o/) then failed its own source-replacement assertion because Python `shlex` does not decode the recorder's Bash ANSI-C string quoting. The corrected direct probe and exact Bash replays passed. These were reviewer harness errors; no implementation correction was made. No required tool was broken.

This review verifies the version contract and the selected native handoff. It does not rerun the full acquired-data preparation scan, independently rehash the multi-gigabyte reference/index/asset corpus, prove the authenticity of arbitrary forged version headers, or qualify complete shard processing. The native parity comparison covers these selected reads and this complete reference; it does not prove parity for all possible inputs. The genuine SUP split proves this parser accepts one observed split case; dedicated split-fixture qualification and downstream rejection controls remain separate work. The declared fresh-process timing observations, reserve/resource evidence during those runs, effective settings across all units, and all six full-shard/model units require their own evidence. No throughput comparison, model winner, biological base accuracy, quality calibration, variant-aware accuracy, or variant-calling accuracy is claimed.
