# Independent retrieval design review

VERIFIED within the declared source-only design scope. No substantive mathematical defect was identified. The citation and coordination-evidence findings below were resolved during review. This review does not admit acquisition, implementation, confirmation, biological promotion, or a performance claim.

Reviewed on 23 October 2026 by the assigned native `gpt-6.1-sol` reviewer at `xhigh`. This is a fresh same-family review. It is not cross-family corroboration. No children were delegated. Only this report and ignored `logs/retrieval-design-review/` were written.

The worktree is `/home/jake/Projects/nanopore_basecaller-retrieval`, branch `experiment/frontier-retrieval`, HEAD `6a40e6e5ae79019d8ab43f236deb2792c92a3e7e`. The reviewed documents are uncommitted. HEAD alone does not identify them.

| Reviewed artifact | SHA256 |
|---|---|
| `research/flank-conditioned-prior-design.md` | `3628176be67b8da8e99443319be145fa89a12b35c48ce33766d543c9841761c7` |
| `research/retrieval-confirmation-design.md` | `1d3f65076150dd51166d63c1bd93296aef4628b80d07576f2f61ba5ad14925cc` |
| `research/retrieval-priority-run.md` | `687b49e3e63ac37be97ee6a10af41800ed1a343cda7e2632f0d900fec185ef18` |
| `research/catalogue-bridge-brief.md` | `c4cf74a7f94b88e07503b66daf74c6a01a2a578a22a923d2c96ffc9602f924b8` |
| `decisions.tsv` | `54db7c268202185bc8501a59c5546d1bd05e967279c1441e142f3de604408c2e` |
| `logs/retrieval-confirmation/HG001-acquisition-manifest.json` | `a826603dd9d1b3c77969f5acc20b00524ec9d379f213873ecf974899c6bb33cc` |

## Resolved evidence findings

1. Resolved. Initial confirmation SHA256 `a3c0487c7a1ce068f721c4f85f7576ae0b4b89e457a7ddbe4f9a2e5af7f20ed1` called HG001's phase-transfer VCF explicitly draft phasing without established accuracy. The linked directory establishes existence, and retained `giab421-readme.txt` line 9 establishes phase transfer, but neither inspected source supports that explicit warning. The final revision now says phase accuracy is unqualified here. Direct inspection confirmed this minimal correction. The phase-block qualification requirement remains.
2. Resolved. The initially cited runtime receipt establishes only `herdr agent list` at 15:53:58 UTC. The coordinator supplied `logs/retrieval-priority/runtime-observations.jsonl`, SHA256 `46cb453e58ccb6cd9d0eadef59dcb1c478670d0f1a8985b9e77f14f828603686`. I independently matched all six extracted events and source-line hashes against the specified coordinator rollout. Source lines 9125 and 9143 establish tab creation and agent startup. Lines 9168 and 9169 establish Go and Harness prompt submissions with exit zero at 15:52:21 and 15:52:22 UTC. Line 9176 establishes the visible brief-read at 15:52:47 UTC. Line 9218 records the worker's cwd and native thread-writer lock. These records predate or accompany the dispatch report and support its external-worker assertions. Submission still does not establish acknowledgment or a permanent reservation. No command was replayed.

Neither correction requires changing a scientific endpoint. Existing implementation and acceptance checks were left unchanged.

## Scientific design findings

The flank design correctly separates observed index linkage from donor frequencies. Current bytes match all eight source pins in `logs/retrieval-haplotype/source-pins.txt`. The inspected `subgraph.rs` follows full GBWT node/offset successors, then merges identical paths into weights. Its documentation calls nonreference paths anonymous. A four-line development TSV check shows `unknown` identifiers and collapsed weights, not donor IDs. This supports contiguous indexed fragments and does not qualify their biological origin. The [GBWT paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7223266/) supports haplotype-path indexing and warns that unrestricted graph paths can represent recombinations. It does not validate this proposed nanopore prior.

The source trace confirms that panel construction trims complete walks to the fixed anchors. `FLSTMStack.cpp` reverses sequence direction across recurrent layers. Therefore, disjoint called-base intervals do not establish independent signal observations. The design appropriately calls the score heuristic fusion, keeps central neural likelihood in the objective once, and acknowledges mapping and nomination selection. The planned flank-only input type is an enforceable future boundary, not an implemented guarantee.

The proposed bonus lies in `[0,1]`. Equal best distances give bonus one. Off-panel hypotheses retain finite support in the stated finite distribution. Deduplicating prototypes makes a best-exemplar minimum insensitive to path multiplicity. Retaining fixed H separates conditioning from search expansion. These facts do not ensure allele retention under deterministic decoding. An independent calculation reproduces the stated failure example. Native private likelihood zero and wrong panel likelihood minus 0.25 yield an objective margin of 0.75 and neural deficit 0.25. Both fixed gates admit the wrong allele. The strict neural-advantage bound greater than one is valid because no competitor can gain more than one from the prior.

The withheld-ALT challenge preserves original H and actual central scores, recomputes ablated membership, and counts absent correct hypotheses as coverage failures. Its edited-core union prevents distant unchanged alleles from satisfying local safety. Sparse SNV or indel support remains unresolved. The 32-query feasibility unit and operation budget are proposals. No extraction fixture, implementation, score, or biological result was verified here.

The confirmation design correctly treats reused HG002 validation and HG005 as exposed. HG001 is a proposed project holdout pending exposure and graph exclusion audits. Searching current `config`, `research`, and asset metadata found its aliases only in the new design, which is insufficient to prove historical nonexposure or absence from vendor training. The [ONT release](https://epi2me.nanoporetech.com/giab-2025.01/) supports the seven donor identities, two flowcells each, and LSK114 chemistry. The [ONT registry](https://registry.opendata.aws/ont-open-data/) supports CC BY-NC 4.0. Retained GIAB metadata establishes HG001 autosomal GRCh38 benchmark BED and VCF availability. Canonical asset files match this worktree byte-for-byte and name the same no-ALT reference MD5. No REF-allele, genotype-identity, raw-integrity, or phase-accuracy qualification followed from those metadata checks.

Independent ranking of all 146 retained POD5 objects reproduced initial indices 69 and 30, totaling 27,969,992,840 bytes. Independent minima in each declared index stratum reproduced all eight expansion objects, totaling 134,316,381,872 bytes. The original metadata checker does not verify the expansion's stratum-minimum rule, so this was checked separately. Index time, random sampling assumptions, adequate local ALT support, and the reported disk budget remain unqualified. Deterministic outcome-independent ranking does not establish that the seed was prospectively immutable. The manifest's limited two-file scope and the distinction between one donor and two flowcells are appropriate.

The zero-loss calculation is consistent. One hundred independent sites permit a one-sided 95% upper loss bound of 2.9513%. About 2,995 independent sites are needed for a bound below 0.1%. Repeated reads do not create those independent sites. The document appropriately leaves donor-level power and multiplicity to a frozen development-derived plan.

## Commands and observed results

Commands ran from the retrieval worktree. Unmodified copies of the author's checker and its metadata dependencies were placed under the assigned ignored evidence directory so the author's `verification.json` was not overwritten.

```sh
git status --short
git rev-parse HEAD
git branch --show-current
git diff -- decisions.tsv
uv run --no-sync python logs/retrieval-design-review/positive/verify-metadata.py
uv run --no-sync python logs/retrieval-design-review/negative/verify-metadata.py
herdr agent list > logs/retrieval-design-review/herdr-agent-list.json 2> logs/retrieval-design-review/herdr-agent-list.stderr
sha256sum research/flank-conditioned-prior-design.md research/retrieval-confirmation-design.md research/retrieval-priority-run.md research/catalogue-bridge-brief.md decisions.tsv
```

The positive metadata check exited zero for 146 frame records and two selected files. The negative copy changes only the first full-frame byte count by one. It exited one at checker line 32 with `AssertionError`, detecting disagreement with the retained S3 listing. The checker copies retain the author's original embedded receipt-command string. Actual argv and exits are recorded separately in `logs/retrieval-design-review/checks.json`.

`checks.json` also retains the independent stratum selections, sums, bonus calculation, erasure counterexample, and binomial calculation. `source-and-runtime-checks.json` retains source-pin comparison, canonical asset equality, runtime observations, and prose scan results. `reference-source-pins.txt` retains the exact current dependency SHA256 values. No trailing whitespace or scoped HTML comments, lint suppressions, or special comment constraints were found.

`coordination-receipt-check.json` retains the verified six original command strings, exits, timestamps and source-line hashes. A later visible-read receipt shows the worker reporting bridge progress, and a Go visible-read receipt shows its reported priority hold. Those terminal statements were not used as independent proof of bridge correctness. That implementation has a separate reviewer.

The first final-pin assertion failed when the coordinator corrected the confirmation citation during review. Reconstructing the old document by reversing that single sentence reproduces its exact prior SHA256. The subsequent check passed for all other scoped pins. `final-pin-check.json` preserves this observation and the final document pin. This was revision drift during a live review, not a scientific-check failure.

Small producer metadata was checked without reading the 349,853,905-byte decisions payload. The retained catalogue recorder exited zero and binds completion SHA256 `949ad1b4528f968b77abc5bf2971e53de540ac40bf02c18d96ad094bdd871efc`. That completion binds summary SHA256 `7bd79a0bf462fffa5de4c8bff8a6e981e446cab00508a679c3b7377368012124`. The summary reports 331 scored windows, 120 exclusions, 64 parents and 3,118,978 distinct hypotheses, matching the brief. `producer-metadata-check.json` retains this check. It does not independently requalify payload hashes, scorer correctness, source ancestry, or bridge admission.

The bridge brief changed during review. Its final reviewed revision correctly separates disabled-edit identity from a reference-free expanded-H neural argmax, which can legitimately edit. The appended 16:05:14 decision records that clarification. The review did not modify or relax either control.

## Execution prerequisites and coverage limits

Before acquisition, retain the frozen manifest with its hash, complete the HG001 alias and exposure audit, verify donor-contribution exclusion, adopt endpoints and blinding responsibilities, and budget raw files plus indexes, tensors, outputs and failed attempts. After acquisition, qualify raw metadata, read identities, truth/reference compatibility and local variant support. Before flank execution, qualify CIGAR boundaries and orientation, pin the mapped SAM and original SEQ/Q relationship, implement the stated invariance and erasure controls, and obtain fresh bridge and observer admission. These are predeclared dependencies, not newly imposed biological gates.

The named Comment Sicko runtime is unavailable. I directly performed its scoped prose/comment/constraint read. Deletions, restored comments, suppressions, and encodings are all zero. The scientific safety constraints remain proposed contracts requiring future implementation checks. No upstream named agent ran. Prove It Works shaped the unchanged-checker rerun, corruption control, current source pins, and independent arithmetic checks.

Web access was incomplete. Direct Oxford article access failed after an inaccessible redirect. Search returned the primary GBWT paper text. PMC and GIAB direct fetches were inconsistent or returned access challenges, so retained primary metadata and pinned local source were used for the narrow claims described above. No broad literature validation is claimed.

No scientific producer, build, GPU job, substantial data scan, acquisition, or biological scoring was run. Current metadata and selected source inspection cannot prove every historical command, absence of all prior donor exposure, genetic independence, variant preservation, accuracy improvement, or speedup. These conclusions are limited to the exact document and manifest revisions above.
