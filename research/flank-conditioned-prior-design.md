# Flank-conditioned graph compatibility with private-allele escape

Source-only design, 23 October 2026. No inference, scoring, biological observation, download, training or GPU run occurred. All existing development and validation are exposed and exploratory. HG005 is exposed and excluded from selection. Throughput checkpoint is n/a for this investigation.

## Decision

Test whether unchanged, disjoint flanks can distinguish two graph-supported central sequences that receive the same binary presence bonus. Keep the complete admitted hypothesis set and central neural scores fixed. The treatment only reduces the bonus of flank-incompatible graph strings. This tests linkage beyond presence without changing search or increasing maximum prior strength.

This is a heuristic compatibility prior, not a calibrated haplotype posterior. [GBWT](https://academic.oup.com/bioinformatics/article/36/2/400/5538990) motivates preserving observed haplotype walks rather than freely recombining graph edges. It establishes neither this scoring rule nor nanopore accuracy. No additional literature survey is needed beyond the [existing source assessment](/home/jake/Projects/nanopore_basecaller-reference/research/reference-frontier-sources.md).

Reject another presence-weight sweep because it cannot distinguish two panel strings. Reject copy-weighted donor inference because donor identities are absent. Keep search expansion with its existing owner so the new comparison isolates conditioning.

## Actual information and missing information

The inspected [extractor](/home/jake/Projects/nanopore_basecaller-reference/tools/graph_resource/src/main.rs:53) saves full sequence, reference-coordinate CIGAR, completeness and `copy_count`, with 100 bp graph context. Existing [panel construction](/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/graph.rs:91) trims this to fixed anchors and loses flank linkage. Retain the full strings before that trim.

The TSV's apparent haplotype names do not restore donors. The inspected development query `0000.walks.tsv` contains `unknown` with integer identifiers. [Pinned gbz-base 0.6.2 source](https://github.com/jltsiren/gbz-base/blob/2b48da95bfca5b1fef717a4b6006233b7535a385/src/subgraph.rs) explicitly makes nonreference walks anonymous and defines weight as collapsed identical paths. Neither those identifiers nor copy counts establish independent donor frequency. Deduplicate identical extracted flank/core triples, including reference duplicates. Never join anonymous identifiers across queries.

The walks nevertheless preserve indexed linkage. [`extract_paths`](/home/jake/Projects/nanopore_basecaller-reference/software/graph-prior/graph-resource/gbz-base-source/src/subgraph.rs:1260) decompresses GBWT records and follows each full node/offset position's successor until it exits the subgraph. `Distinct` subsequently merges identical paths. This extracts contiguous indexed-thread fragments rather than enumerating recombinant graph-edge choices. It does not independently prove each thread's biological provenance. Retain the existing graph-origin and membership qualification, including reference-path distinctions.

The [planner](/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/planner.rs:88) supplies native coordinates, orientation, anchors and tensor intervals. Its ten-base anchors equal reference and therefore cannot provide useful haplotype discrimination. Extra native flank sequence requires the pinned original primary SAM, not the 41-reference-base window string alone. The [frontier interface](/home/jake/Projects/nanopore_basecaller-reference/tools/graph_frontier/src/decision.rs:5) supports only binary priors. Continuous compatibility requires a separate implementation and schema, not reinterpretation of existing receipts.

## Frozen data and inference contract

Define `flank-prior-plan/1` with input hashes, parent/query identity, original window hash, orientation and two reference/read intervals. In reference orientation, choose exactly `[ref_start-100,ref_start-50)` and `[ref_end+50,ref_end+100)`. Each flank spans 50 reference bases with a 50-base guard outside the existing scored window. Require complete native and graph coverage. Reject ambiguous boundary indels, clipping and noncanonical bases. Interior indels remain in the extracted strings. Use one documented CIGAR boundary convention for native and graph extraction, validated on indel fixtures.

Both reference and read flank intervals must avoid every planned editable interval of that parent. Freeze them once from original native output. Candidate edits never update conditioning evidence. Convert reverse reads to reference orientation for comparison and back only for central scoring.

Define `WalkPrototype` as the hashed full source walk plus extracted left flank, central fixed-anchor string and right flank. Keep only the already admitted complete panel paths. A failed extraction, any flank string longer than 64 bases or more than 256 prototypes causes whole-window conditioning abstention, never truncation. Source strings, CIGAR and hashes remain auditable. Multiplicity and donor-like labels cannot enter the inference type.

Define `FlankEvidence` with only the two native strings, coordinates and custody hashes. Its scorer cannot read central native bases, central scores, truth, modified Q or candidate outputs. For prototype `p`, set `d_p = edit(F_left,p_left) + edit(F_right,p_right)` with unit Levenshtein costs. For panel center string `h`, let `d_h` be the minimum `d_p` among prototypes carrying `h`, and `d_min` the minimum over all prototypes. This best-exemplar rule uses no path frequency or invented recombination.

Set `r_h = exp(-ln(3)*(d_h-d_min))` and `B_F(h)=ln(1+(e-1)*r_h)`. Off-panel strings receive zero. Thus `0 <= B_F <= 1`; explicitly return exactly one when `d_h=d_min`. The edit penalty is a declared heuristic, not a base-error probability. If left-only and right-only best center sets have empty intersection, abstain from conditioning and use binary presence. Equal distances recover binary presence exactly.

Use the unchanged expanded catalogue `H`, including original H, every distance-two native-core alternative and native itself. No flank score filters H. The [catalogue](/home/jake/Projects/nanopore_basecaller-reference/tools/frontier_catalogue/src/catalogue.rs:41) is finite, so longer or more distant private alleles remain outside scope. For every finite-score hypothesis, `P_F(h) proportional to exp(B_F(h))` is positive. This escape preserves support, not biological correctness.

Compare native output, `J_N=L`, `J_P=L+G`, and `J_F=L+B_F`. Freeze weight one, objective margin 0.5 and maximum neural deficit 0.5 for both prior arms. Retain native-first ties, then lexicographic ties, and existing argmax-then-gate behavior. Record all pre-gate winners and reasons. Do not tune these parameters on challenge outcomes. No new neural/scalar computation is needed once the compound producer and import bridge are qualified.

## Leakage and safety limits

Central `L` enters the objective once. Disjoint sequence intervals do not establish independent signal evidence. [Dorado's alternating recurrent layers](/home/jake/Projects/nanopore_basecaller-reference/software/graph-prior/source/dorado/nn/FLSTMStack.cpp:83) allow native flank calls to depend on wider chunk signal. Native mapping and mismatch-based nomination also condition eligibility. Report empirical score fusion, not Bayes factor multiplication or unbiased genome-wide sampling. Center-masked remapping and independently generated flank evidence would require separate qualification.

The bounded bonus proves only that a graph-absent candidate with neural advantage strictly greater than one over every competitor cannot lose to the prior. A private native allele with advantage 0.25 can still lose to a wrong graph allele under the declared gates. Wrong flanks, recombination, graph omissions and native flank errors remain mechanisms of variant erasure. Modified Q contributes no evidence of accuracy.

## Smallest development-only falsification

First implement a Rust read-only adapter on 32 predeclared development query indices, chosen by query index before reading their flank compatibility or truth. Keep missing cases and denominators. No GBZ load, tensor scoring or candidate emission is needed. Stop this unit if no window has two distinct panel centers and informative, valid flanks. This rejects that unit's feasibility, not the remaining saved windows or general hypothesis.

Require synthetic controls before real scoring. Swapping linked flanks must reverse center preference at equal central scores. Duplicating walks, changing `copy_count`, reordering records and changing masked center input must leave the prior identical. Equal flanks must reproduce panel decisions exactly. Neutral must reproduce the admitted neutral artifact. Impossible likelihoods remain negative infinity.

Then run a frozen actual-score withheld-ALT challenge at central windows, using qualified retained scores rather than fabricated scores. An isolated truth-aware challenge builder identifies development baseline ALT-supporting cores and removes every prototype carrying that ALT from the challenge panel. Preserve native and the entire original H with their original scores, including withheld ALT strings. Recompute challenge graph membership; retain original membership only as provenance. Bind an ablation manifest. The inference process receives no truth. Empty panels produce neutral scores. Single-center panels still test erasure safety but cannot identify linkage benefit. Report unavailable or unscored ALT hypotheses as coverage failures, never preserved alleles.

Evaluate the union of centers edited by either prior arm, with local ALT observations overlapping each editable core, plus the full parent denominators. Compare ordinary and ablated panels, matched neutral, binary presence and conditioned prior. Any conditioned-arm baseline ALT loss fails this development safety challenge, including losses shared with binary presence. Distant unchanged ALTs cannot satisfy its denominator. Report SNVs and indels separately, wrong-allele changes, native fallback and exclusions. Zero losses with sparse edited-site support remains unresolved. All historical validation stays exploratory; confirmation requires an outcome-unseen cohort and the unchanged registered biological gates.

## Dependencies and budget

Require pinned development parents, original primary SAM, windows, full `graph/walks.jsonl`, graph exclusion/membership seal and reference identity. Candidate emission additionally requires the qualified compound completion/import bridge and batch observer, with exact source ancestry and original score hashes. The inspected handoff identified `arms=[]` import and observer-admission blockers. Obtain their owners' fresh verdicts before execution. Reuse their evidence; do not repeat producers.

Resolve exact mapped SAM and reference paths through [`development/artifacts/windows.json`](/home/jake/Projects/nanopore_basecaller-reference/results/graph-prior/pilot-v1/development/artifacts/windows.json). The frontier cohort's `native_sam` points to the unaligned call and is not the planner's mapped `--sam`. Preserve both producer identities and verify their parent SEQ/Q relationship before extracting flanks.

The inspected graph JSONL is 2,881,651 bytes and windows JSONL 196,033 bytes. Proposed adapter work is at most `32 * 256 * 2 * 64^2` edit-distance cells, plus parsing. This is an operation bound, not measured runtime. Request one CPU, 1 GiB RSS, 60 seconds and 100 MiB output for that first unit; abort rather than truncate. Later mapping/scoring needs its own measured admission under the shared host lock. No GPU, new data, training or biological run is authorized by this design.

Inspection pins and commands are retained in ignored `logs/retrieval-haplotype/source-pins.txt`. Foundational Thinking determined the separate flank-only input type. Prove It Works determined the duplicate, center-masking and actual-score ALT challenges. Their execution remains pending.
