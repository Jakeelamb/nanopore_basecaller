# Source qualification review

Independent same-family Sol reviewers checked the source trace/build, adapter implementation, experiment design, and actual smoke artifacts. These are separate scoped reviews. They are not cross-model validation or a claim that all source code and biological behavior are proven.

## Accepted scope

- The source/build review checked 72 immutable source links, consequential pipeline branches, model/configuration hashes, 71 retained build receipts, declared transformations in both isolated source copies, and the selected CPU inventory. The accepted upstream test scope is 55 of 610 main-binary cases. The other 555 cases, clean-machine reproduction, and opaque GPU kernel internals remain unqualified.
- The adapter review independently reran all 18 CPU contracts. It also exercised the real native comparator on genuine retained smoke and split records. Record/tag permutations pass; changed sequence, quality, typed tags, and split offsets produce differences. Frozen benchmark, accuracy, Rust, and stock configuration files remain unchanged.
- Actual smoke artifacts show both new arms using the same captured performance profile and CPU affinity. Native source/vendor smoke outputs pass with all 32 parents represented per tier. Source SUP smoke contains 33 children from 32 parents; the separate genuine HAC split fixture contains two children from one parent. The parser and parent ledger preserve that distinction.
- Source-owned FASTA/index evidence passes the unchanged two-tier parity interface. Every smoke basecall/alignment canonical comparison and parent-ledger comparison is equal. All four unit/domain accuracy comparisons have equal metrics and all seven native score tables equal. Successful raw producer exits and actual contexts were inspected. An exhaustive independent rehash of the final full graph has not been run.
- The prospective protocol passes review as an unarmed experiment. It separates original-parent technical uncertainty from donor/flowcell replication, fixes data roles and masks, requires paired time/accuracy/yield, and leaves concrete candidate margins and external confirmation to registration. The current exact-version source qualifier does not automatically admit future source candidates.

The accepted adapter SHA-256 is `58d38686ebec1d868d027a002fca68c7e48a724a252b43074849d05adabc3b51`. Its tests are `127c5adad192971330e3059770fdd751a6c019dedbf668c7adeef1053da971b3`. The frozen native verifier remains `39cb086598e5de0ae8c8d113f86c06a2d7721f34799e7cb258ea5dee744fb9fc`; the accuracy coordinator remains `b5c6da542cdcb81689a93f5c7667e2933a91aedb5bb4f172e348c3de6ec3b49b`.

## Retained failures and waiting scope

The first balanced-policy native launch was rejected before a producer started after the host became performance. A new prospectively sealed performance root passed smoke qualification. Its first full development HAC basecall succeeded and remains retained exactly once. A later CPU reference check was interrupted by profile drift, then a held retry exited zero but failed its measurement gate for foreign GPU activity. A successful native exit does not override that failed gate.

The native profile-hold probe entered performance only for its guarded command and returned to balanced. The actual hold has been released. Other experiments still use the shared host, and the user requested waiting before native resumption. No successful basecaller is repeated to repair a downstream observation.

The [waiting manifest](../provenance/verification/source-qualification-waiting-20261023.json) binds the accepted smoke report, source plans, exact successful HAC basecall receipt, both unqualified reference-check attempts, CI receipt, and byte-identical recovery-controller snapshot. The [qualification report](source-qualification-results.md) contains the precise resume command.

Full native observations, eight full fixed-domain scores, full source/vendor equivalence, independent final pin audit, read-only final audit, and completed-run zero-producer resume proof remain pending. Comparative performance is not run. Publication-level generalization remains outside this pilot.

## Evidence locations

The detailed independent reports remain locally at:

- `logs/source-qualification-20261023/trace-build-review.md`
- `logs/source-qualification-20261023/design/judgment.md`
- `logs/source-qualification-20261023/design/protocol-review.md`
- `logs/source-qualification-20261023/adapter-review.md`

Their SHA-256 identities are respectively `868916199161d47e64e8dddc41150bfcf996c3c19258af1204f02ff363ffacde`, `e8872ca6a046251d85ebf99f5affc3a16e647a93df48804194652ea7c1fdcffd`, `5e1520308a9d9d3b0701ed384589de3d374e33a4f03ee9a20889dfef5ee13696`, and `eab4a9b654a7861fa8e81c2ecd32ca4e1f124f5de1556201338311838d5fc795`.

Build the Lever kept native execution and scoring in their maintained owners. Prove It Works required genuine native positives and rejection controls. Attack the Premise tested the failed assumption that an observed host profile would remain stable, then used a scoped native hold. Separate Before Serializing Shared State kept outputs separate while one canonical lock coordinated the GPU. The foreign-process failure demonstrates the remaining limit of that coordination on a shared host.

Adapter CPU contracts passed in `logs/20261023T030232Z-source-adapter-policy-cpu-contracts-1scpN4`. [CPU CI on f5b9ebc](https://github.com/Jakeelamb/nanopore_basecaller/actions/runs/39892964226) passes its listed contracts, including the source adapter and Rust scorer tests. That is CPU evidence only. Native smoke acceptance is `logs/20261023T030425Z-source-qualification-performance-smoke-DQ5yjU`, exit zero. Raw failed commands, native outputs, and diagnostic profiles remain outside Git.
