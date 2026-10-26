# F1 R1-R3 source correction candidate

This is a source-only correction of review `F1-session-v1`, SHA256 `ac72f92bd7d057cf22f2fcb2bd8f58402766438be9d5b5b0c997a8e30ff437fc`. The prior cut `34e83cd738159ab9d00e9b76289ac41e6f2c3427` remains in branch history. Independent exact-delta review is requested. None of the corrected controls has executed.

Actual build, formatting, CTest, Python tests, mapper, scientific-body, lock and GPU execution counts in this correction round are0. `git diff --check` is the only source whitespace inspection. It emits no error and is not behavioral qualification. No binary, DGS, DGM, reference, index or truth body was opened or hashed in this source turn. File-hash calls added to consumers run only inside a later admitted worker.

## R1. Current input pins and reference lineage

The session specification now carries an immutable `resource_manifest` FilePin. Its `prefix-resources/1` record binds the declared plan hash and the mapper, mapper index, reference FASTA, FAI, samtools, index/reference provenance and producer source pins. The pin travels through persisted state and candidate binding. Relocation validates current mapper/index pins and compares them with this frozen resource record. Restoration of contextual state validates the same resource manifest.

`validate_resources` checks current pins for every resource. It consumes a pinned `prefix-reference-lineage/1` record that connects the exact index and FAI to the exact reference/tool pins. The index build receipt must name the declared mapper, reference and produced index, including its declared `-d INDEX REFERENCE` argv relationship. The FAI build receipt must name the declared samtools, reference and produced FAI. Both must retain exact command custody, source pins and terminal evidence. A matching contig name, reference length, path string or caller-written completion flag alone does not satisfy these checks.

Every nonempty continuation validates its reference, FAI and samtools pins, their frozen identities, the reference/index lineage identity and the full ordered `receipt.inputs` tuple `[reference, FAI, samtools]`. The mapper receipt requires `[query, mapper, index]`. Producer source pins and stdout/stderr/time/terminal-proof files are checked. Terminal proof binds the full command identity and reports reaping plus empty process group/cgroup. This is a consumer contract for later qualified producer evidence, not a new supervisor.

Prepared controls first accept both-strand nonempty literal continuations and an actual C++ session update, then mutate one declared reference/FAI/samtools/mapper/index hash. They assert the current-pin guard rather than a source-root hash failure. Other controls reseal metadata to exercise foreign input tuples, foreign terminal-command identity, a reference/index identity mismatch, and a coherent foreign reference that still fails the index-build relationship. A changed literal mapper body with unchanged declared pin also targets the current-pin guard.

Literal receipts in these engineering fixtures explicitly say `synthetic-not-native-execution`. Their acceptance will test consumer behavior only. They do not prove that a mapper or index build happened. The genuine path still needs qualified producer receipts under Root's fresh unit.

The current configuration deliberately has `index_provenance:null` and no qualified producer source pins. Preparation rejects before scientific bodies while these are missing. Root must supply a retained qualified index/FAI relationship, or separately admit its production. No relationship is fabricated from the existing GRCh38 index filename. F4 CLI integration remains an existing held feature gap.

## R2. Actual search mass and accepted rebinding

The independent probability-domain enumerator now retains a full `(sequence, CRF state, location ID)` census. It enumerates each initial CRF state, stay/emission path, and uniform location choice at every declared update. It does not call production transition, penalty, merger or scalar likelihood code.

The control compares every actual retained node mass with its oracle log mass, checks every state/location key exactly once, marginalizes every sequence and checks each grouped rank value. Existing scalar-rescore, complete eligible sequence census and winner checks remain. The zero-length all-stay path remains in the internal state census even though it is not an eligible emitted candidate under R3. The log-space comparison is `abs(actual-expected) <= 1e-10 * max(1, abs(expected))`.

Accepted synthetic updates enter `relocate` through its full query/state/endpoint/receipt/resource checks. The sequence is two competing locations on both strands, one revised location, then no location. Every intermediate signal and conditioned state/marginal is compared with independent enumeration. The signal-only state remains equal to a separately advancing location-free session. Another accepted control permutes the same location positions and compares all semantic location/state masses. Split stepping at identical update boundaries compares retained masses and ranks. Python wire controls use the actual C++ `locations` and `advance` producers across three persisted-state updates, including removal. Those wire checks also remain unrun.

## R3. Explicit zero-prefix abstention

Winner absence is an `optional<string>`, separate from sequence data. A zero-length internal path is not an eligible output candidate, even when minimum and maximum symbol bounds are both0. The batch then reports empty candidates, `abstained:true`, null named candidate IDs and `mapper_request_eligible:false`. It retains an explicit `empty_prefix_contract`. The pilot orchestration records this abstention without requesting a mapper or downstream decision. It does not invent three updates.

Controls cover the valid `{maximum_symbols:0, minimum_symbols:0}` policy and a valid positive minimum that no available path can reach. The old no-finalist fixture no longer mutates a valid specification into an invalid one. A separate impossible-sequence scalar check remains. Eligible candidates must have finite neural mass rather than serialize an impossible mass into an invalid F2 candidate.

## Next admitted source-format unit

The explicit C++ census is still exactly six files. No CMake/source-census scope expansion occurred. Cwd is `/home/jake/Projects/nanopore_basecaller-next-prefix-loop`.

```sh
/usr/bin/clang-format -i tools/prefix_feedback/include/prefix_feedback/session.h tools/prefix_feedback/src/io.cpp tools/prefix_feedback/src/session.cpp tools/prefix_feedback/src/location.cpp tools/prefix_feedback/src/main.cpp tools/prefix_feedback/tests/controls.cpp
```

Prospective caps are30seconds, CPU1, RAM1GiB, AS2GiB, swap0, growth1MiB, with Root's exact source/tool pins, raw receipt and token/AST preservation check. This command has not run. The existing CMake `format-check` target checks the pinned formatter and only this owned census.

## Later engineering unit

The exact four CMake/build/format-check/CTest commands and fixed-UV unittest command remain in `research/prefix-loop-source-ready.md`. They must bind the corrected immutable source head returned with this report. Caps remain300seconds, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, cumulative4GiB and free reserve30GiB. A missing real C++ binary is a Python test failure, not a skip. Fresh CTest JUnit must prove tests executed and skipped0.

This correction does not qualify actual first-chunk T, three genuine mapper updates, F4 integration, full-parent disabled SEQ/Q, F2/F3 integration, matched stock comparisons, biological accuracy, performance or native/GPU behavior. The saved-score causality label and entirely provisional prefix semantics are unchanged. The older first-cut readiness report remains historical and is supplemented by this correction report.
