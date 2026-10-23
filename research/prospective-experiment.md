# Prospective accuracy, speed, and yield experiment

This protocol defines candidate evaluation after the unchanged source build is qualified. No candidate algorithm is registered or selected by this document. The source qualification is an engineering control experiment. Its source/vendor comparisons cannot establish an algorithm improvement because the dependency stacks differ.

The current data support mechanism development and technical validation. Publication claims about other people or sequencing runs require a prospectively reserved external cohort. The design follows the separation of evaluation criteria, datasets, implementation, and reproducibility recommended in [Essential guidelines for computational method benchmarking](https://arxiv.org/abs/1812.00661v4).

## Data roles and independence

| Role | Frozen material | Permitted use |
| --- | --- | --- |
| Development | HG002, PAW70337, selected shard, 2,608 original parents | Trace mechanisms, tune candidates, estimate technical variance, select one candidate per registered hypothesis. |
| Validation | HG002, PAW71238, selected shard, 2,027 original parents | Evaluate a frozen candidate and decision rule once. This is a different flowcell from the same person. |
| Exposed historical material | HG005, PAW87816 | Historical stock control only. Excluded from build qualification and candidate selection in this experiment. |
| External confirmation | Not acquired or assigned | Reserve new donor/flowcell identities and sampling rules before candidate evaluation. Required for broader biological claims. |

The pilot shards were selected partly by size. They are not a random sample of all human sequencing. A read, a split child, a model run, and a repeated basecall of the same signal are not independent people. Vendor sample labels are acquisition metadata. Their genetic identity and overlap with vendor training data have not been independently established here.

Before external acquisition, register the target population, chemistry, instrument, library protocol, donor eligibility, independent library/flowcell replication, and shard sampling procedure. Assign all files from one donor to one role when testing donor generalization. Assign all related libraries consistently. Record exclusions before looking at candidate performance. Determine the required donor and flowcell counts from control-only variance, a registered effect size, and power simulations using the intended hierarchical analysis. Do not infer a biological sample size from the number of bases. Until that design exists, results remain pilot results.

## Register a concrete intervention

Before the first candidate development execution, declare the mechanism hypothesis, changed source boundary, data role, and endpoint in its feature PR. Complete and freeze the full registration below before its first candidate validation call. An amendment creates a new dated registration and retains the old one. Required fields are:

1. Candidate commit, control commit, model/weight hashes, compiler, dependency closure, build commands, and the exact source boundary changed.
2. A mechanism prediction that can fail, the intended model and hardware scope, and whether the intervention changes inference, decoding, splitting, trimming, filtering, or mapping.
3. One primary objective, a minimum meaningful effect, and the direction and margin for every accuracy, time, and yield decision. An empty margin or an unspecified candidate leaves the experiment unarmed.
4. All candidates tried on development, the finite validation family, the selection rule, and the multiplicity procedure. Development failures and rejected candidates remain visible.
5. Frozen input membership, masks, mapping policy, complete command schedule, cache policy, exclusions, failure/retry rules, uncertainty procedure, and analysis source hashes.
6. An external confirmation plan and the exact claims it can support. Publication criteria must not be inferred from pilot success.

For a dual-improvement hypothesis, the default decision is superiority on both registered primary accuracy error and native basecaller time, with the registered practical thresholds, plus all yield guards. For a speed-only hypothesis, register an accuracy noninferiority margin and a practically meaningful speed threshold. For an accuracy-only hypothesis, register a latency limit. A tradeoff is reported as a tradeoff. It cannot be relabeled a dual improvement after evaluation.

Use the qualified source build as the unchanged control. Put candidate code and outputs in separate paths. Keep weights, toolchain, dependencies, CLI options, signal IDs, reference, mapper executable, mapping flags, and scorer fixed except for the declared intervention. Compare a candidate to a freshly built control with the same stack. The official CUDA 12 distribution and the unchanged CUDA 13 source build are distinct controls. A dependency change is a separate treatment.

The current source-qualification runner uses each arm's own aligner to qualify that executable. Future basecaller research must use one pinned mapper for both arms. Otherwise a mapping change can masquerade as a basecalling gain. Register filter, trim, and alignment changes as such. Model training requires its own split and training-data custody, including a fresh external test set.

## Measure accuracy and exposure together

The primary pilot error is `(X + I + D) / (M + X + I + D)`, aggregated over the frozen eligible alignment columns. Report accuracy as `1 - error`. Use the existing retained Rust scorer and GIAB v4.2.1 truth policy, with mapping quality at least 30 and the fixed 100 bp exclusion domain. The 500 bp domain is a required sensitivity analysis. Neither mask can be chosen after seeing a candidate result.

This endpoint measures disagreement with the reference outside the declared truth neighborhoods, conditional on alignment and eligibility. It is not whole-genome base accuracy, personal-haplotype accuracy, or variant-calling accuracy. GIAB benchmark regions cover a defined subset of genomic variation and retain difficult-region limitations, as described in [Benchmarking challenging small variants with linked and long reads](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=930585). A new truth release or mask is a separately registered analysis, never a silent replacement after results.

For every arm, model, cohort, and domain, retain M, X, I, D, reference/query denominators, evaluated parents, C=0 parents, mapped/unmapped dispositions, clipping, and excluded work. Report aggregate error and parent-mean error separately. Retain the scorer's quality calibration and bounded homopolymer endpoint as secondary metrics. State their conditioning and unsupported cases. Report strata fixed in advance, such as control-derived read-length bins, Q bins, and annotated repeat classes. Do not define strata using the candidate's favorable outcomes.

Use the same original UUID universe for both arms, including parents without output or eligible columns. Never assign missing or C=0 parents perfect accuracy or invented error. Report their counts and their signal samples explicitly. Split children stay with their original parent for analysis and resampling.

Accuracy decisions require exposure guards. At minimum, the candidate must meet its registered limits for represented parents, evaluable parents, emitted query bases, eligible query/reference exposure, clipping, and unmapped output. Report gained and lost evaluable-parent sets and common-parent results beside whole-arm results. A higher conditional accuracy with reduced exposure does not pass a dual-improvement claim merely because a read count remains similar.

For a confirmatory accuracy claim, also register a paired common-support sensitivity analysis that identifies which reference positions are evaluable in both arms. Its implementation and allele/indel accounting must be qualified on genuine data before that claim is armed. The current aggregate scorer does not implement that cross-arm coordinate intersection. An unchanged total denominator alone cannot rule out exchanging difficult positions for easy ones. The pilot can report its existing bounded endpoint while this additional confirmatory endpoint remains unavailable.

## Measure yield from original inputs

The denominator is the frozen original-parent universe and its original signal samples. Resolve output lineage using `pi` where present and QNAME otherwise. Preserve the parent-to-child ledger and child intervals. Do not substitute Dorado's displayed unique-read counter, which has different split/filter semantics.

Required yield outputs are:

- Submitted, represented, absent, mapped, and evaluable original parents, with exact UUID lists and fractions.
- Child records, split parents, emitted bases, aligned query bases, eligible bases, and clipping/unmapped counts.
- Emitted and eligible bases per original input sample and per recorded acquisition duration, with units and conditioning.
- Gained/lost output and evaluability sets between arms, plus total and stratum-specific denominators.

The default pilot guard is no additional absent parent and no reduction in evaluable-parent count or eligible-query exposure relative to the paired control. Register any scientifically justified tolerance before validation, with its rationale and interval procedure. Even when the guard passes, inspect gained/lost sets and common support. This is an operational guard, not proof of equal biological coverage.

Loader errors, incomplete decoding, malformed output, foreign parents, and unexplained missing required work invalidate a complete-processing claim. A native process exit zero is necessary but insufficient. A legitimate final length rejection remains a measured yield loss. Diagnose its cause with separate evidence rather than removing the parent from the denominator.

## Measure speed in paired fresh processes

The primary speed endpoint is native basecaller wall time from process launch through exit, with output fully materialized on the declared filesystem. It includes model loading, automatic batch selection, input scanning, inference, decoding, splitting, trimming, and output. Report samples per second using the same submitted sample denominator only when complete-processing checks pass. Also report accepted bases per second so dropping difficult reads cannot create an unqualified throughput win.

Use the existing controlled process recorder, GPU-idle admission, cooldown, affinity, telemetry, and 30 GiB disk reserve. Record CPU/GPU model, driver, power mode, clocks/temperature, toolkit/runtime, effective batch dimensions, environment, and competing processes. `--batchsize 0` is an automatic policy, not a fixed batch size. Hold the policy fixed and record its actual choices. A fixed-batch mechanism experiment is a different registered comparison.

For each registered model and cohort, schedule ten matched control/candidate blocks over two sessions of five blocks. Each process starts fresh. Within each session, balance AB and BA as closely as five blocks permit, with the second session reversing the imbalance. Generate the order before execution with a public seed, such as `20261023`, and retain the actual schedule and its hash. Do not reorder after observing runtimes. Report all ten paired times, median, range, paired log-time ratio, and uncertainty. Five completed pairs is the minimum for an explicitly preliminary timing report, not an automatic early-stop rule.

Warm the filesystem once according to the frozen policy before measured blocks. Do not call this a cold-cache measurement. Hold stdout topology and compression fixed. No owned build, download, scorer, test suite, report hashing, or profiler runs concurrently with a timed basecaller. Interleave arms to reduce residual drift, record external contention, and preserve contaminated attempts. Predeclare replacement rules based on objective telemetry or execution failure, without inspecting which arm won. Report original and replacement results.

Pair correctness, accuracy, and yield with every timed output. If repeated decoding is identical, prove that with pinned canonical records before reusing deterministic score results. Do not assume determinism from matching aggregate accuracy. A failed/partial run is counted in the failure rate and cannot contribute a successful fast time. Missing arms make their block incomplete. A rerun does not erase the first attempt.

Report a separate end-to-end endpoint for the actual workflow a user waits on: basecall, fixed mapping, and sorting, with one outer clock and the same output policy. The existing thirteen-stage audit also performs full decodes and consistency checks. Adding its stage clocks is not the ordinary user pipeline latency. Implement and qualify this outer workflow before a confirmatory end-to-end claim. Internal kernel timings and profiled runs never replace native process or end-to-end measurements.

Profile in separate diagnostic invocations. Map CUDA/NVTX regions and CPU work back to [the source trace](dorado-code-path.md), while identifying opaque Koi/Torch boundaries. Report a speed result as descriptive or inconclusive if its limiter, correctness, or completed work cannot be established. Do not infer memory bandwidth, occupancy, or a kernel bottleneck from sampled GPU utilization alone.

## Uncertainty and decisions

For pilot accuracy, resample the same original-parent indices jointly for both arms, keeping all children together. Recompute both aggregate errors and their difference/ratio in each resample. Use 20,000 resamples, seed `20261023`, and a predeclared percentile interval. Report zero-denominator resamples and do not turn them into zero error. Existing single-arm 2,000-resample intervals are descriptive context; they are not paired candidate tests.

For time, resample complete paired blocks within each session, preserving arm pairing and the session structure. Analyze log candidate/control time ratios and back-transform for reporting. Parent-level accuracy uncertainty and process-level time uncertainty answer different questions. Repeated identical sequences increase timing replication, not biological accuracy replication. Pilot intervals describe these flowcells conditional on the fixed truth and mapping policy.

Choose one candidate per registered hypothesis on development. Freeze its commit, selection history, analysis, and validation rule before any candidate validation output. Validation is a single decision at the registered sample size. Do not keep revising the candidate against PAW71238 and continue calling it held out. A revision after validation starts a new development study and requires a new confirmation set for a clean confirmatory claim.

Register the complete family of candidates, models, and primary claims. A simple default is Bonferroni adjustment across that family, using two-sided confidence intervals at `1 - 0.05/K` for K registered primary comparisons and applying each directional threshold to the corresponding bound. List guard endpoints and their interval or exact-count rules separately. Do not choose K after results. With few technical blocks, precision can be poor even when the observed effect is large. Publish the interval and all raw points rather than treating a threshold as certainty.

External confirmation needs an analysis that resamples or models donors and flowcells at their actual replication levels. Freeze that model and power calculation before candidate outcomes. Read-level bootstrap intervals do not establish donor generalization. Separate exploratory strata and secondary endpoints from registered confirmatory claims.

## Execution gates and retained evidence

Before candidate validation, the PR must contain the completed registration, a qualified control and candidate build, genuine native and scorer handoffs, corruption rejection controls, exact input/model/reference pins, the frozen schedule, and a resource admission record. It must also contain qualified paired-accuracy analysis and common-support sensitivity analysis for every accuracy superiority or noninferiority claim, including a speed-only study's accuracy guard. Qualify the outer end-to-end workflow before its confirmatory timing endpoint is armed. A primary native-process claim can proceed with that separate endpoint explicitly unavailable. Retain unsuccessful builds and executions. Every observation binds actual successful command receipts, clocks, output hashes, parent ledgers, and source identities. Audit accepted observations without rewriting them after scores pin their bytes.

The current source qualification has a separate 39 GiB admission gate and four full source units. It does not fund the prospective timing experiment. Ten pairs across two models and two cohorts require 80 full basecaller processes, their downstream verification, and space for retained evidence. Forecast this from measured artifact sizes with scratch/retry allowance and preserve the 30 GiB floor. Provision another volume if needed. Never delete failed or unfavorable runs to fit the experiment.

CPU CI verifies only the contracts it actually lists. Selected upstream CPU tests do not qualify GPU kernels. Compilation does not qualify full inputs. BAM validity does not qualify biological accuracy. Bounded accuracy does not qualify whole-genome variants or generalization. A reproducible pilot is the starting point for published research, and the external confirmation gates remain explicit work.
