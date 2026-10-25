# Controlled stock baseline

**Complete:** 19/19 stock units verified with the current native verifier; six full cohort/model outputs scored in both fixed truth domains. The accuracy wrapper qualifies native execution and exact ledgers. Scientific scope is the bounded endpoint described below.

Plan `1c995eba5d6454a6ef8a8fc6dcd767fd9e9aead811389da38f3906ddaf6815e0`. Inputs `66056a2fd8883969bd6ac6dbee9415e2189e1090bf29f25c7183d541c4b5461c`. [Machine-readable evidence](../provenance/verification/controlled-baseline-20261023.json) retains every Q bin, stratum, artifact SHA-256 and native receipt path. Local [stock report](/home/jake/Projects/nanopore_basecaller/results/stock/controlled-20261022/report.json), [plan](/home/jake/Projects/nanopore_basecaller/results/stock/controlled-20261022/plan.json), [native qualification](/home/jake/Projects/nanopore_basecaller/results/stock/controlled-20261022/qualification.json) and [truth qualification](/home/jake/Projects/nanopore_basecaller/results/accuracy/controlled-20261022-v1.1-frozen/truth-qualified.json). Export validation: all retained pins rehashed.

Endpoint: **GIAB-supported reference-identical local-primary accuracy outside fixed unsupported-star confidence neighborhoods**. Conditional on publisher donor labels and accepted primary autosomal mappings (MAPQ 30–254). Variants, known reference errors, non-ACGT truth and fixed unsupported-star confidence neighborhoods are excluded. Unknown reference errors and mapping errors remain possible. This is neither whole-read diploid accuracy nor variant calling; vendor training exclusion is unknown. HG005 is reported as a stock control and selects no candidate.

Accuracy is M/(M+X+I+D), where X is substitution, I inserted bases and D deleted bases. Query exposure is M+X+I; reference exposure is M+X+D. Insertions need both flanks in one eligible interval; deletions count eligible reference positions. Split children combine by original parent. Aggregate and mean-parent rates differ. The 95% parent bootstrap intervals use 2,000 fixed-seed replicates and quantify within-pilot technical resampling only; genomic dependence, duplex relationships, flowcell and population variation, truth and donor uncertainty are not covered.

## Repeated process timing

Five fresh processes per tier use all 2,608 development parents and 641,769,607 electrical samples each. Filesystem inputs/models/reference/index were explicitly warmed outside timing. ACAD external power and balanced laptop profile were sampled continuously; the observed power ceiling is 100 W. Stock DVFS, fan control and clocks remain dynamic. Three one-second idle GPU observations at ≤40 C and ≤5% utilization gate each start outside the native clock. Our benchmark team paused other owned CPU-heavy work during repeated timings. The host remained shared, and background CPU contention was not excluded; sampled CPU/load evidence remains available. The disclosed owned check during the full HG005 SUP observation appears below. This is process throughput, including startup, loading, input/output and shutdown, with no isolated-kernel or model-winner claim.

| Tier | Five native wall clocks s | Wall median [range] s | Sample SD s | CV % | Signal MSamples/s median [range] | Called bases/s median [range] |
| --- | --- | --- | --- | --- | --- | --- |
| hac | 35.36, 34.93, 35.63, 35.4, 35.45 | 35.4 [34.93, 35.63] | 0.258515 | 0.731219 | 18.1291 [18.0121, 18.373] | 1.42829e+06 [1.41907e+06, 1.44751e+06] |
| sup | 173.95, 174.33, 173.36, 173.3, 173.04 | 173.36 [173.04, 174.33] | 0.528328 | 0.304343 | 3.70195 [3.68135, 3.70879] | 292551 [290923, 293092] |

| Repetition | Native wall s | Signal MSamples/s | Called bases | Called bases/s | Input/represented parents |
| --- | --- | --- | --- | --- | --- |
| timing-1-hac | 35.36 | 18.1496 | 50561593 | 1.42991e+06 | 2608/2608 |
| timing-1-sup | 173.95 | 3.68939 | 50716622 | 291559 | 2608/2608 |
| timing-2-sup | 174.33 | 3.68135 | 50716622 | 290923 | 2608/2608 |
| timing-2-hac | 34.93 | 18.373 | 50561593 | 1.44751e+06 | 2608/2608 |
| timing-3-hac | 35.63 | 18.0121 | 50561593 | 1.41907e+06 | 2608/2608 |
| timing-3-sup | 173.36 | 3.70195 | 50716622 | 292551 | 2608/2608 |
| timing-4-sup | 173.3 | 3.70323 | 50716622 | 292652 | 2608/2608 |
| timing-4-hac | 35.4 | 18.1291 | 50561593 | 1.42829e+06 | 2608/2608 |
| timing-5-hac | 35.45 | 18.1035 | 50561593 | 1.42628e+06 | 2608/2608 |
| timing-5-sup | 173.04 | 3.70879 | 50716622 | 293092 | 2608/2608 |

<details><summary>All 13 native stages: clock, CPU, RSS and observer scope</summary>

Values are medians [minimum, maximum] over five repetitions. Native GNU time clocks have 0.01 s resolution; zero is below that resolution. Observer elapsed includes setup/telemetry overhead and is a separate boundary; host RSS is native maximum resident memory.

| Tier | Stage | n | Native wall s | Observer elapsed s | User CPU s | System CPU s | Max RSS KiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hac | align | 5 | 13.85 [13.53, 14.68] | 15.3366 [15.3196, 16.3775] | 46.42 [44.49, 48.15] | 3.44 [2.32, 3.88] | 1.31588e+07 [1.29669e+07, 1.3285e+07] |
| hac | aligned-decode | 5 | 0.28 [0.26, 0.48] | 2.46945 [2.46636, 2.49113] | 0.24 [0.22, 0.3] | 0.04 [0.02, 0.05] | 4416 [4152, 4536] |
| hac | aligned-quickcheck | 5 | 0 [0, 0] | 1.45058 [1.35388, 1.48549] | 0 [0, 0] | 0 [0, 0] | 3756 [3556, 3848] |
| hac | aligned-summary | 5 | 0.33 [0.31, 0.33] | 2.46996 [1.41763, 2.48944] | 1.67 [1.63, 1.78] | 0.1 [0.08, 0.12] | 670104 [666244, 670300] |
| hac | base-decode | 5 | 0.23 [0.19, 0.27] | 1.28852 [1.27518, 1.29363] | 0.2 [0.16, 0.22] | 0.02 [0.02, 0.03] | 4360 [4100, 4412] |
| hac | base-quickcheck | 5 | 0 [0, 0] | 1.28379 [1.25813, 1.29693] | 0 [0, 0] | 0 [0, 0] | 3628 [3576, 3760] |
| hac | base-summary | 5 | 0.26 [0.24, 0.28] | 1.28345 [1.27234, 1.29249] | 0.75 [0.7, 0.83] | 0.07 [0.06, 0.08] | 671920 [669500, 678756] |
| hac | basecall | 5 | 35.4 [34.93, 35.63] | 39.758 [39.5382, 75.724] | 42.59 [42.06, 43.05] | 0.69 [0.68, 0.74] | 3.2426e+06 [3.23992e+06, 3.24535e+06] |
| hac | calmd | 5 | 4.26 [4.21, 4.42] | 6.50347 [6.49908, 6.59218] | 4.01 [3.99, 4.06] | 0.2 [0.19, 0.23] | 485136 [484808, 485272] |
| hac | calmd-decode | 5 | 0.31 [0.27, 0.36] | 2.47565 [2.35152, 2.50536] | 0.26 [0.22, 0.31] | 0.03 [0.02, 0.05] | 4380 [4192, 4548] |
| hac | flagstat | 5 | 0.21 [0.2, 0.22] | 2.48585 [2.46873, 2.49359] | 0.2 [0.19, 0.21] | 0 [0, 0] | 3916 [3880, 3920] |
| hac | sort | 5 | 1.08 [0.93, 1.23] | 2.47991 [2.43166, 3.48604] | 2.96 [1.62, 3.09] | 0.04 [0.04, 0.06] | 132544 [132380, 133216] |
| hac | stats | 5 | 9.77 [9.7, 9.85] | 11.5159 [11.4099, 11.5494] | 9.65 [9.56, 9.69] | 0.09 [0.08, 0.11] | 302792 [302556, 303464] |
| sup | align | 5 | 15.05 [14.69, 15.3] | 16.3905 [16.3185, 17.3836] | 49.16 [43.39, 49.5] | 4.33 [2.61, 4.74] | 1.31814e+07 [1.30058e+07, 1.32718e+07] |
| sup | aligned-decode | 5 | 0.3 [0.27, 0.38] | 2.47961 [1.33302, 2.48147] | 0.21 [0.19, 0.23] | 0.04 [0.03, 0.04] | 4464 [4160, 4548] |
| sup | aligned-quickcheck | 5 | 0 [0, 0] | 1.46809 [1.41483, 1.48333] | 0 [0, 0] | 0 [0, 0] | 3644 [3492, 3752] |
| sup | aligned-summary | 5 | 0.32 [0.31, 0.32] | 2.47384 [2.36454, 2.49302] | 1.6 [1.54, 1.68] | 0.1 [0.09, 0.1] | 670908 [669228, 674924] |
| sup | base-decode | 5 | 0.19 [0.17, 0.22] | 1.28174 [1.27544, 1.28416] | 0.17 [0.13, 0.18] | 0.02 [0.02, 0.03] | 4352 [4128, 4404] |
| sup | base-quickcheck | 5 | 0 [0, 0] | 1.2646 [1.24932, 1.29495] | 0 [0, 0] | 0 [0, 0] | 3608 [3552, 3644] |
| sup | base-summary | 5 | 0.26 [0.25, 0.27] | 1.31685 [1.2846, 1.33165] | 0.73 [0.73, 0.75] | 0.08 [0.07, 0.08] | 671060 [670132, 673916] |
| sup | basecall | 5 | 173.36 [173.04, 174.33] | 180.896 [176.712, 282.508] | 180.48 [180.08, 181.67] | 0.92 [0.85, 1.03] | 3.60454e+06 [3.60042e+06, 3.60873e+06] |
| sup | calmd | 5 | 4.73 [4.61, 4.75] | 6.50935 [6.49657, 6.53258] | 4.48 [4.35, 4.52] | 0.21 [0.18, 0.25] | 485268 [484824, 485372] |
| sup | calmd-decode | 5 | 0.3 [0.27, 0.38] | 2.47238 [2.46143, 2.50342] | 0.22 [0.2, 0.28] | 0.04 [0.03, 0.05] | 4476 [4300, 4548] |
| sup | flagstat | 5 | 0.18 [0.17, 0.22] | 1.47 [1.35122, 1.49629] | 0.17 [0.17, 0.22] | 0 [0, 0] | 3848 [3684, 3856] |
| sup | sort | 5 | 1.3 [1.12, 1.71] | 3.47722 [2.35383, 3.48659] | 3.45 [2, 3.76] | 0.05 [0.03, 0.05] | 134668 [134232, 135112] |
| sup | stats | 5 | 9.83 [9.48, 9.9] | 11.5133 [11.5058, 11.6121] | 9.69 [9.36, 9.75] | 0.09 [0.08, 0.09] | 306684 [306500, 306868] |

The 13 core stages are always required. `calmd-reference-iupac` is an additional native samtools faidx stage only when the verifier records a coordinate-confirmed reference ambiguity; it remains subject to the same measurement and receipt requirements.

</details>

<details><summary>GPU and host observations, limiter evidence and batch choices</summary>

GPU core peaks and arithmetic sample means cover the required synchronous device-wide samples before native launch, during the process and after exit. This required sample window starts after GPU cooldown and includes prelaunch/postexit sampling overhead. These values are not instantaneous maxima or isolated process allocations. One-second sampling and a 2.5 s maximum gap cannot resolve subsecond events. Optional thermal/power probes, samplers and snapshots span a broader observer interval beginning before cooldown. Their counter deltas include that broader interval and must not be divided by native wall time to estimate a native throttle fraction. Counter activity supports limiter observations but supplies no kernel-profiler evidence or causal bottleneck diagnosis. CPU load snapshots and full thermal/power samples remain in the evidence/receipts. Total observer elapsed includes setup and cooldown; native wall is the separate process boundary.

| Unit | GPU peak MiB | Peak/mean W | Peak/mean utilization % | Peak/mean SM MHz | Peak C | Samples | Batch selection |
| --- | --- | --- | --- | --- | --- | --- | --- |
| timing-1-hac | 6637 | 100.4/94.3432 | 100/95.3514 | 2707/2348.65 | 72 | 37 | precomputed_benchmark_unavailable |
| timing-2-hac | 6637 | 100.54/95.047 | 100/96.0811 | 2790/2331.22 | 75 | 37 | precomputed_benchmark_unavailable |
| timing-3-hac | 6637 | 100.68/95.3538 | 100/95.0811 | 2782/2340.11 | 72 | 37 | precomputed_benchmark_unavailable |
| timing-4-hac | 6637 | 100.56/94.9149 | 100/93.9189 | 2782/2333.65 | 73 | 37 | precomputed_benchmark_unavailable |
| timing-5-hac | 6637 | 100.76/94.837 | 100/94.8108 | 2775/2325.35 | 75 | 37 | precomputed_benchmark_unavailable |
| timing-1-sup | 2077 | 100.22/97.8847 | 100/98.8457 | 2535/2260.89 | 86 | 175 | precomputed_benchmark_unavailable |
| timing-2-sup | 2901 | 100.62/97.7372 | 100/98.3182 | 2527/2259.43 | 88 | 176 | precomputed_benchmark_unavailable |
| timing-3-sup | 4181 | 100.19/97.8311 | 100/98.3486 | 2512/2279.41 | 86 | 175 | precomputed_benchmark_unavailable |
| timing-4-sup | 2753 | 100.14/97.994 | 100/98.5714 | 2512/2276.07 | 85 | 175 | precomputed_benchmark_unavailable |
| timing-5-sup | 2849 | 100.18/98.0361 | 100/98.9195 | 2385/2265.7 | 86 | 174 | precomputed_benchmark_unavailable |

| Unit | Counter | Delta | Scope |
| --- | --- | --- | --- |
| timing-1-hac | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-1-hac | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-1-hac | sw_power_cap | 1.24248e+07 | microseconds / observer boundary |
| timing-1-hac | sw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-2-hac | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-2-hac | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-2-hac | sw_power_cap | 1.36276e+07 | microseconds / observer boundary |
| timing-2-hac | sw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-3-hac | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-3-hac | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-3-hac | sw_power_cap | 1.24602e+07 | microseconds / observer boundary |
| timing-3-hac | sw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-4-hac | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-4-hac | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-4-hac | sw_power_cap | 1.37984e+07 | microseconds / observer boundary |
| timing-4-hac | sw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-5-hac | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-5-hac | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-5-hac | sw_power_cap | 1.33223e+07 | microseconds / observer boundary |
| timing-5-hac | sw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-1-sup | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-1-sup | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-1-sup | sw_power_cap | 1.2125e+08 | microseconds / observer boundary |
| timing-1-sup | sw_thermal_slowdown | 477531 | microseconds / observer boundary |
| timing-2-sup | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-2-sup | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-2-sup | sw_power_cap | 1.22904e+08 | microseconds / observer boundary |
| timing-2-sup | sw_thermal_slowdown | 385237 | microseconds / observer boundary |
| timing-3-sup | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-3-sup | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-3-sup | sw_power_cap | 1.20428e+08 | microseconds / observer boundary |
| timing-3-sup | sw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-4-sup | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-4-sup | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-4-sup | sw_power_cap | 1.20663e+08 | microseconds / observer boundary |
| timing-4-sup | sw_thermal_slowdown | 20144 | microseconds / observer boundary |
| timing-5-sup | hw_power_brake_slowdown | 0 | microseconds / observer boundary |
| timing-5-sup | hw_thermal_slowdown | 0 | microseconds / observer boundary |
| timing-5-sup | sw_power_cap | 1.22193e+08 | microseconds / observer boundary |
| timing-5-sup | sw_thermal_slowdown | 0 | microseconds / observer boundary |

| Unit | Observer loadavg 1m median [range] | Host samples | Maximum host sample gap s | External power samples | Platform profiles |
| --- | --- | --- | --- | --- | --- |
| timing-1-hac | 3.66 [3.44, 3.96] | 37 | 1.05843 | 1 | balanced |
| timing-2-hac | 3.71 [3.59, 4] | 37 | 1.06268 | 1 | balanced |
| timing-3-hac | 3.94 [3.85, 4.04] | 37 | 1.06002 | 1 | balanced |
| timing-4-hac | 3.42 [3.22, 3.48] | 37 | 1.05998 | 1 | balanced |
| timing-5-hac | 2.98 [2.9, 3.08] | 37 | 1.06146 | 1 | balanced |
| timing-1-sup | 2.58 [2.47, 3.04] | 175 | 1.06283 | 1 | balanced |
| timing-2-sup | 2.74 [2.2, 3.4] | 176 | 1.06159 | 1 | balanced |
| timing-3-sup | 3.76 [3.39, 3.93] | 175 | 1.0598 | 1 | balanced |
| timing-4-sup | 3.67 [3.5, 3.85] | 175 | 1.05983 | 1 | balanced |
| timing-5-sup | 3.73 [3.28, 3.9] | 174 | 1.05845 | 1 | balanced |

The known batchsize-0 precomputed-benchmark fallback is reported separately from native loader errors. Exact effective batch/chunk debug lines are retained in each stock observation. A known fallback diagnostic alone does not mean a loader failure.

| Unit | Complete work | Native loader error lines | Effective batch/chunk settings |
| --- | --- | --- | --- |
| full-development-hac | verified | 0 | [2026-10-22 18:01:38.664] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 18:01:38.929] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| full-development-sup | verified | 0 | [2026-10-22 18:03:18.628] [debug] cuda:0 using chunk size 12288, batch size 32 |
| full-validation-hac | verified | 0 | [2026-10-22 18:08:57.185] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 18:08:57.455] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| full-validation-sup | verified | 0 | [2026-10-22 18:11:03.772] [debug] cuda:0 using chunk size 12288, batch size 32 |
| full-sealed_test-hac | unavailable: absent parents or native loader diagnostics | 0 | [2026-10-22 18:16:32.487] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 18:16:32.756] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| full-sealed_test-sup | verified | 0 | [2026-10-22 18:20:43.985] [debug] cuda:0 using chunk size 12288, batch size 32 |
| timing-1-hac | verified | 0 | [2026-10-22 18:37:40.971] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 18:37:41.236] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| timing-1-sup | verified | 0 | [2026-10-22 18:39:19.067] [debug] cuda:0 using chunk size 12288, batch size 32 |
| timing-2-sup | verified | 0 | [2026-10-22 18:44:57.683] [debug] cuda:0 using chunk size 12288, batch size 32 |
| timing-2-hac | verified | 0 | [2026-10-22 18:49:30.592] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 18:49:30.861] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| timing-3-hac | verified | 0 | [2026-10-22 18:51:12.352] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 18:51:12.620] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| timing-3-sup | verified | 0 | [2026-10-22 18:52:48.408] [debug] cuda:0 using chunk size 12288, batch size 32 |
| timing-4-sup | verified | 0 | [2026-10-22 18:57:17.307] [debug] cuda:0 using chunk size 12288, batch size 32 |
| timing-4-hac | verified | 0 | [2026-10-22 19:01:51.105] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 19:01:51.375] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| timing-5-hac | verified | 0 | [2026-10-22 19:03:29.614] [debug] cuda:0 using chunk size 12288, batch size 576<br>[2026-10-22 19:03:29.883] [debug] cuda:0 using chunk size 6144, batch size 1024 |
| timing-5-sup | verified | 0 | [2026-10-22 19:05:05.356] [debug] cuda:0 using chunk size 12288, batch size 32 |

</details>

## Full cohort accuracy and exposure

Full-cohort process clocks are additional single observations per cohort/model, separate from the five repeated development timing estimates.

| Full unit | Parents submitted | Signal samples | Native basecall wall s | Clock qualification | Called bases | Represented/absent parents | Complete work |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 2608 | 641769607 | 35.23 | controlled process observation | 50561593 | 2608/0 | verified |
| full-development-sup | 2608 | 641769607 | 173.46 | controlled process observation | 50716622 | 2608/0 | verified |
| full-validation-hac | 2027 | 553650293 | 31.5 | controlled process observation | 43928382 | 2027/0 | verified |
| full-validation-sup | 2027 | 553650293 | 149.7 | controlled process observation | 43969306 | 2027/0 | verified |
| full-sealed_test-hac | 16319 | 2554852800 | 128.56 | controlled process observation | 182649650 | 16302/17 | unavailable: absent parents or native loader diagnostics |
| full-sealed_test-sup | 16319 | 2554852800 | 714.83 | descriptive_with_owned_cpu_interference | 184568747 | 16319/0 | verified |

Disclosed measurement incidents qualify the affected clock without discarding its observed output or subsequent source-bound accuracy scores. The uncertainty window overlaps the observer interval; this conservative qualification does not reconstruct instantaneous native contention. Required AC/profile/GPU telemetry qualification is separate from CPU isolation. Annotated full-cohort clocks are descriptive; the ten primary timing repetitions must start after confirmed worker termination and carry no such incident.

| Unit/stage | Status | PID | UTC window | Precision | Worker stopped before UTC | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| full-sealed_test-sup/basecall | descriptive_with_owned_cpu_interference | 672880 | 2026-10-23T00:23:00Z to 2026-10-23T00:33:00Z | approximate | 2026-10-23T00:33:00Z | An ad hoc report warmup-join check performed a quadratic path-resolution loop. Its owner observed about 43 seconds at one CPU core and terminated it. The owner also reported a subsequent 49-test report-fixture run taking 17.9 seconds wall and a later one-second-capped attempt, with CPU time unrecorded. The interval conservatively covers the reported approximate 00:23-00:25 metadata window and all disclosed fixture work before the coordinator's 00:33:00 confirmation of the owner's execution freeze; it does not assert continuous load throughout that interval. The command is the owner's reported form; exact stdin was not retained. Treat this full-cohort native clock as descriptive. Preserve the actual produced reads and accuracy analysis, with no counterfactual claim about unaffected numerical accuracy. |

| Unit | Domain bp | M | X | I | D | C | Query denom | Reference denom | Accuracy % | 95% technical CI % | Mean-parent accuracy % | Mean-parent 95% technical CI % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 30941670 | 155405 | 105160 | 165179 | 31367414 | 31202235 | 31262254 | 98.6427 | 98.525262–98.749555 | 98.579 | 98.471158–98.684023 |
| full-development-hac | 500 | 13131664 | 67186 | 45228 | 70780 | 13314858 | 13244078 | 13269630 | 98.6241 | 98.477999–98.764012 | 98.5911 | 98.474474–98.707294 |
| full-development-sup | 100 | 31039304 | 118817 | 83602 | 123916 | 31365639 | 31241723 | 31282037 | 98.9596 | 98.845295–99.068165 | 98.8853 | 98.773017–98.990564 |
| full-development-sup | 500 | 13174977 | 52304 | 35559 | 54033 | 13316873 | 13262840 | 13281314 | 98.9345 | 98.788513–99.068354 | 98.8905 | 98.764923–99.001577 |
| full-validation-hac | 100 | 26571802 | 140504 | 94754 | 141126 | 26948186 | 26807060 | 26853432 | 98.6033 | 98.450083–98.751348 | 98.3135 | 98.148132–98.470183 |
| full-validation-hac | 500 | 10871889 | 56233 | 38084 | 57164 | 11023370 | 10966206 | 10985286 | 98.6258 | 98.443678–98.790225 | 98.3358 | 98.165152–98.499359 |
| full-validation-sup | 100 | 26679105 | 115908 | 83369 | 117121 | 26995503 | 26878382 | 26912134 | 98.828 | 98.688074–98.970646 | 98.5113 | 98.346455–98.675480 |
| full-validation-sup | 500 | 10907910 | 45363 | 32502 | 46672 | 11032447 | 10985775 | 10999945 | 98.8712 | 98.700792–99.027759 | 98.4995 | 98.322318–98.676117 |
| full-sealed_test-hac | 100 | 105820467 | 793900 | 513204 | 732497 | 107860068 | 107127571 | 107346864 | 98.109 | 98.015591–98.201685 | 98.2145 | 98.154408–98.273269 |
| full-sealed_test-hac | 500 | 41701505 | 323632 | 208401 | 295800 | 42529338 | 42233538 | 42320937 | 98.0535 | 97.934758–98.169116 | 98.0937 | 98.017071–98.170701 |
| full-sealed_test-sup | 100 | 106266896 | 623301 | 402078 | 609775 | 107902050 | 107292275 | 107499972 | 98.4846 | 98.394483–98.568310 | 98.5707 | 98.513836–98.628486 |
| full-sealed_test-sup | 500 | 41886563 | 255289 | 163399 | 247617 | 42552868 | 42305251 | 42389469 | 98.4342 | 98.322583–98.544981 | 98.4732 | 98.398528–98.546581 |

100 bp is the fixed primary domain; 500 bp is the predeclared sensitivity domain. Both are reported regardless of which looks better. All-called fractions below divide retained eligible query labels by every emitted primary child base, so mapping, clipping and mask losses stay visible. Input absence is a parent count, not an inferred biological error.

| Unit | Domain bp | Input/represented/positive parents | Children | Called bases | Scored query/all-called % | Absent parents | Unmapped bases | Soft clips | Policy-excluded bases | Masked query bases | Child statuses |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 2608/2608/2186 | 2614 | 50561593 | 61.7113 | 0 | 153589 | 2095522 | 3210228 | 13900019 | {"low_mapq": 87, "no_eligible_columns": 69, "nonautosomal": 141, "selected": 2191, "unmapped": 126} |
| full-development-hac | 500 | 2608/2608/2039 | 2614 | 50561593 | 26.1939 | 0 | 153589 | 2095522 | 3210228 | 31858176 | {"low_mapq": 87, "no_eligible_columns": 216, "nonautosomal": 141, "selected": 2044, "unmapped": 126} |
| full-development-sup | 100 | 2608/2608/2190 | 2617 | 50716622 | 61.6006 | 0 | 80835 | 2203867 | 3277403 | 13912794 | {"low_mapq": 93, "no_eligible_columns": 70, "nonautosomal": 141, "selected": 2195, "unmapped": 118} |
| full-development-sup | 500 | 2608/2608/2043 | 2617 | 50716622 | 26.1509 | 0 | 80835 | 2203867 | 3277403 | 31891677 | {"low_mapq": 93, "no_eligible_columns": 217, "nonautosomal": 141, "selected": 2048, "unmapped": 118} |
| full-validation-hac | 100 | 2027/2027/1743 | 2039 | 43928382 | 61.0245 | 0 | 71310 | 1842977 | 2586458 | 12620577 | {"low_mapq": 90, "no_eligible_columns": 57, "nonautosomal": 88, "selected": 1753, "unmapped": 51} |
| full-validation-hac | 500 | 2027/2027/1624 | 2039 | 43928382 | 24.9638 | 0 | 71310 | 1842977 | 2586458 | 28461431 | {"low_mapq": 90, "no_eligible_columns": 176, "nonautosomal": 88, "selected": 1634, "unmapped": 51} |
| full-validation-sup | 100 | 2027/2027/1752 | 2041 | 43969306 | 61.1299 | 0 | 78799 | 1720796 | 2566617 | 12724712 | {"low_mapq": 88, "no_eligible_columns": 62, "nonautosomal": 82, "selected": 1762, "unmapped": 47} |
| full-validation-sup | 500 | 2027/2027/1632 | 2041 | 43969306 | 24.9851 | 0 | 78799 | 1720796 | 2566617 | 28617319 | {"low_mapq": 88, "no_eligible_columns": 182, "nonautosomal": 82, "selected": 1642, "unmapped": 47} |
| full-sealed_test-hac | 100 | 16319/16302/11564 | 16346 | 182649650 | 58.6519 | 17 | 1135993 | 8413014 | 12287335 | 53685737 | {"low_mapq": 966, "no_eligible_columns": 620, "nonautosomal": 743, "selected": 11593, "unmapped": 2424} |
| full-sealed_test-hac | 500 | 16319/16302/9490 | 16346 | 182649650 | 23.1227 | 17 | 1135993 | 8413014 | 12287335 | 118579770 | {"low_mapq": 966, "no_eligible_columns": 2696, "nonautosomal": 743, "selected": 9517, "unmapped": 2424} |
| full-sealed_test-sup | 100 | 16319/16319/11647 | 16373 | 184568747 | 58.1313 | 0 | 608967 | 10319071 | 12534267 | 53814167 | {"low_mapq": 1001, "no_eligible_columns": 647, "nonautosomal": 752, "selected": 11682, "unmapped": 2291} |
| full-sealed_test-sup | 500 | 16319/16319/9535 | 16373 | 184568747 | 22.9211 | 0 | 608967 | 10319071 | 12534267 | 118801191 | {"low_mapq": 1001, "no_eligible_columns": 2761, "nonautosomal": 752, "selected": 9568, "unmapped": 2291} |

<details><summary>Truth census and fixed star removals</summary>

| Domain | Original confident bases | Star records | Removed original intervals | Removed union bases | After erosion | Eligible bases | Eligible intervals |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HG002-100 | 2542242843 | 512 | 213 | 435490 | 2449036059 | 1863510986 | 2574668 |
| HG002-500 | 2542242843 | 512 | 213 | 435490 | 2138151913 | 780218537 | 681497 |
| HG005-100 | 2503728811 | 610 | 209 | 463611 | 2355747019 | 1811077559 | 2627497 |
| HG005-500 | 2503728811 | 610 | 209 | 463611 | 1895330448 | 714930975 | 679810 |

| Domain | Ordered subtraction census |
| --- | --- |
| HG002-100 | {"0_confident_union": 2542242843, "0a_after_spanning_star_neighborhoods": 2541807353, "1_after_erosion": 2449036059, "2_after_variants": 1866723111, "3_after_reference_exclusions": 1865938119, "4_after_non_acgt": 1865938119, "5_after_homopolymer_boundaries": 1863510986} |
| HG002-500 | {"0_confident_union": 2542242843, "0a_after_spanning_star_neighborhoods": 2541807353, "1_after_erosion": 2138151913, "2_after_variants": 781059548, "3_after_reference_exclusions": 780841221, "4_after_non_acgt": 780841221, "5_after_homopolymer_boundaries": 780218537} |
| HG005-100 | {"0_confident_union": 2503728811, "0a_after_spanning_star_neighborhoods": 2503265200, "1_after_erosion": 2355747019, "2_after_variants": 1814256536, "3_after_reference_exclusions": 1813580096, "4_after_non_acgt": 1813580096, "5_after_homopolymer_boundaries": 1811077559} |
| HG005-500 | {"0_confident_union": 2503728811, "0a_after_spanning_star_neighborhoods": 2503265200, "1_after_erosion": 1895330448, "2_after_variants": 715674980, "3_after_reference_exclusions": 715547112, "4_after_non_acgt": 715547112, "5_after_homopolymer_boundaries": 714930975} |

For every spanning * REF span, the frozen v1.1 rule removes intersected original merged confident intervals and the closest strictly left/right original neighbors; selection happens once before erosion, never recursively. Star REF padding and all concrete/original/repeat-equivalent masks remain. Exact removed interval coordinates and native qualification receipts are in the evidence. This does not reconstruct the missing upstream deletion extent.

</details>

<details><summary>Quality reliability, length/native-Q strata and homopolymers</summary>

Emitted-Q reliability uses (X+I)/(M+X+I), with expected error 10^(−Q/10). D has no emitted Q and is reported separately. These labels are alignment/domain conditional and do not establish whole-read calibration. Full integer-Q histograms are in the evidence JSON; strata below preserve all M/X/I/D counts.

| Unit | Domain bp | Query labels | Observed X+I | Observed error % | Expected error % | D without emitted Q | Emitted Q bins |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 31202235 | 260565 | 0.835084 | 1.23296 | 165179 | 50 |
| full-development-hac | 500 | 13244078 | 112414 | 0.848787 | 1.25666 | 70780 | 50 |
| full-development-sup | 100 | 31241723 | 202419 | 0.647912 | 0.960485 | 123916 | 50 |
| full-development-sup | 500 | 13262840 | 87863 | 0.662475 | 0.994703 | 54033 | 50 |
| full-validation-hac | 100 | 26807060 | 235258 | 0.877597 | 1.28004 | 141126 | 50 |
| full-validation-hac | 500 | 10966206 | 94317 | 0.86007 | 1.24953 | 57164 | 50 |
| full-validation-sup | 100 | 26878382 | 199277 | 0.741403 | 1.09564 | 117121 | 50 |
| full-validation-sup | 500 | 10985775 | 77865 | 0.70878 | 1.05039 | 46672 | 50 |
| full-sealed_test-hac | 100 | 107127571 | 1307104 | 1.22014 | 1.77039 | 732497 | 50 |
| full-sealed_test-hac | 500 | 42233538 | 532033 | 1.25974 | 1.82499 | 295800 | 50 |
| full-sealed_test-sup | 100 | 107292275 | 1025379 | 0.955688 | 1.43683 | 609775 | 50 |
| full-sealed_test-sup | 500 | 42305251 | 418688 | 0.989683 | 1.49362 | 247617 | 50 |

| Unit | Domain bp | Called length | M | X | I | D | Accuracy % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 0-999 | 25553 | 128 | 74 | 124 | 98.7403 |
| full-development-hac | 100 | 1000-9999 | 1851124 | 12914 | 8138 | 12841 | 98.202 |
| full-development-hac | 100 | 10000-49999 | 27115459 | 132796 | 90470 | 143267 | 98.6663 |
| full-development-hac | 100 | 50000+ | 1949534 | 9567 | 6478 | 8947 | 98.7343 |
| full-development-hac | 500 | 0-999 | 10289 | 60 | 30 | 62 | 98.5442 |
| full-development-hac | 500 | 1000-9999 | 715248 | 5331 | 3153 | 5060 | 98.1416 |
| full-development-hac | 500 | 10000-49999 | 11442297 | 56908 | 38694 | 61206 | 98.6481 |
| full-development-hac | 500 | 50000+ | 963830 | 4887 | 3351 | 4452 | 98.7005 |
| full-development-sup | 100 | 0-999 | 26242 | 94 | 54 | 84 | 99.1237 |
| full-development-sup | 100 | 1000-9999 | 1865919 | 11252 | 6912 | 10905 | 98.466 |
| full-development-sup | 100 | 10000-49999 | 27205365 | 101767 | 72908 | 107148 | 98.9747 |
| full-development-sup | 100 | 50000+ | 1941778 | 5704 | 3728 | 5779 | 99.2227 |
| full-development-sup | 500 | 0-999 | 10327 | 39 | 15 | 47 | 99.0315 |
| full-development-sup | 500 | 1000-9999 | 724701 | 5064 | 2853 | 4634 | 98.2976 |
| full-development-sup | 500 | 10000-49999 | 11482281 | 44416 | 30826 | 46502 | 98.9508 |
| full-development-sup | 500 | 50000+ | 957668 | 2785 | 1865 | 2850 | 99.2229 |
| full-validation-hac | 100 | 0-999 | 20921 | 202 | 184 | 198 | 97.2844 |
| full-validation-hac | 100 | 1000-9999 | 1280364 | 10821 | 6723 | 10118 | 97.8852 |
| full-validation-hac | 100 | 10000-49999 | 22816429 | 119654 | 80836 | 121174 | 98.6098 |
| full-validation-hac | 100 | 50000+ | 2454088 | 9827 | 7011 | 9636 | 98.9327 |
| full-validation-hac | 500 | 0-999 | 6405 | 96 | 66 | 93 | 96.1712 |
| full-validation-hac | 500 | 1000-9999 | 530682 | 4236 | 2664 | 3988 | 97.9895 |
| full-validation-hac | 500 | 10000-49999 | 9296976 | 47949 | 32538 | 49159 | 98.6247 |
| full-validation-hac | 500 | 50000+ | 1037826 | 3952 | 2816 | 3924 | 98.9803 |
| full-validation-sup | 100 | 0-999 | 21713 | 192 | 126 | 215 | 97.6041 |
| full-validation-sup | 100 | 1000-9999 | 1295336 | 10942 | 6322 | 10775 | 97.8813 |
| full-validation-sup | 100 | 10000-49999 | 22902088 | 98039 | 71922 | 99324 | 98.8379 |
| full-validation-sup | 100 | 50000+ | 2459968 | 6735 | 4999 | 6807 | 99.2519 |
| full-validation-sup | 500 | 0-999 | 6433 | 76 | 52 | 86 | 96.7805 |
| full-validation-sup | 500 | 1000-9999 | 537069 | 4399 | 2778 | 4423 | 97.8858 |
| full-validation-sup | 500 | 10000-49999 | 9323932 | 38286 | 27759 | 39473 | 98.881 |
| full-validation-sup | 500 | 50000+ | 1040476 | 2602 | 1913 | 2690 | 99.3123 |
| full-sealed_test-hac | 100 | 0-999 | 412960 | 2521 | 1756 | 2306 | 98.4309 |
| full-sealed_test-hac | 100 | 1000-9999 | 12531944 | 90529 | 61544 | 84720 | 98.1455 |
| full-sealed_test-hac | 100 | 10000-49999 | 80459142 | 619846 | 398832 | 569208 | 98.0647 |
| full-sealed_test-hac | 100 | 50000+ | 12416421 | 81004 | 51072 | 76263 | 98.3498 |
| full-sealed_test-hac | 500 | 0-999 | 166526 | 1020 | 724 | 927 | 98.4214 |
| full-sealed_test-hac | 500 | 1000-9999 | 4814156 | 36414 | 23597 | 33793 | 98.0887 |
| full-sealed_test-hac | 500 | 10000-49999 | 31805607 | 250938 | 162517 | 228868 | 98.0204 |
| full-sealed_test-hac | 500 | 50000+ | 4915216 | 35260 | 21563 | 32212 | 98.2208 |
| full-sealed_test-sup | 100 | 0-999 | 431656 | 2081 | 1300 | 1958 | 98.7782 |
| full-sealed_test-sup | 100 | 1000-9999 | 12613144 | 71932 | 47606 | 70986 | 98.512 |
| full-sealed_test-sup | 100 | 10000-49999 | 80842971 | 490067 | 316437 | 478532 | 98.4353 |
| full-sealed_test-sup | 100 | 50000+ | 12379125 | 59221 | 36735 | 58299 | 98.7692 |
| full-sealed_test-sup | 500 | 0-999 | 174181 | 840 | 500 | 799 | 98.7869 |
| full-sealed_test-sup | 500 | 1000-9999 | 4839053 | 29285 | 19216 | 28449 | 98.4347 |
| full-sealed_test-sup | 500 | 10000-49999 | 31964320 | 199640 | 127705 | 193879 | 98.3955 |
| full-sealed_test-sup | 500 | 50000+ | 4909009 | 25524 | 15978 | 24490 | 98.6735 |

| Unit | Domain bp | Native qs | M | X | I | D | Accuracy % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 10-<20 | 7194227 | 80099 | 50489 | 81537 | 97.1359 |
| full-development-hac | 100 | 20-<30 | 23245270 | 42691 | 38412 | 53567 | 99.424 |
| full-development-hac | 100 | 30+ | 3492 | 15 | 0 | 2 | 99.5155 |
| full-development-hac | 100 | <10 | 498681 | 32600 | 16259 | 30073 | 86.3348 |
| full-development-hac | 500 | 10-<20 | 3000117 | 34080 | 21560 | 34315 | 97.0889 |
| full-development-hac | 500 | 20-<30 | 9905361 | 17754 | 16252 | 22380 | 99.434 |
| full-development-hac | 500 | 30+ | 1554 | 15 | 0 | 2 | 98.9179 |
| full-development-hac | 500 | <10 | 224632 | 15337 | 7416 | 14083 | 85.9119 |
| full-development-sup | 100 | 10-<20 | 5011520 | 50898 | 36770 | 51906 | 97.2904 |
| full-development-sup | 100 | 20-<30 | 24937837 | 31918 | 28502 | 39704 | 99.6001 |
| full-development-sup | 100 | 30+ | 523527 | 156 | 245 | 255 | 99.8749 |
| full-development-sup | 100 | <10 | 566420 | 35845 | 18085 | 32051 | 86.8208 |
| full-development-sup | 500 | 10-<20 | 2099757 | 22148 | 15115 | 22115 | 97.2499 |
| full-development-sup | 500 | 20-<30 | 10591936 | 13377 | 11955 | 16773 | 99.6041 |
| full-development-sup | 500 | 30+ | 232049 | 88 | 111 | 119 | 99.8631 |
| full-development-sup | 500 | <10 | 251235 | 16691 | 8378 | 15026 | 86.2373 |
| full-validation-hac | 100 | 10-<20 | 4730328 | 57825 | 37561 | 56922 | 96.8806 |
| full-validation-hac | 100 | 20-<30 | 21153402 | 34631 | 32531 | 42724 | 99.4832 |
| full-validation-hac | 100 | 30+ | 20911 | 4 | 8 | 22 | 99.8377 |
| full-validation-hac | 100 | <10 | 667161 | 48044 | 24654 | 41458 | 85.3893 |
| full-validation-hac | 500 | 10-<20 | 1888917 | 23210 | 14773 | 23312 | 96.857 |
| full-validation-hac | 500 | 20-<30 | 8713053 | 14630 | 13823 | 17918 | 99.4706 |
| full-validation-hac | 500 | 30+ | 14802 | 3 | 5 | 17 | 99.8314 |
| full-validation-hac | 500 | <10 | 255117 | 18390 | 9483 | 15917 | 85.35 |
| full-validation-sup | 100 | 10-<20 | 3178684 | 35730 | 31813 | 34770 | 96.8816 |
| full-validation-sup | 100 | 20-<30 | 21618188 | 25430 | 24805 | 31597 | 99.6229 |
| full-validation-sup | 100 | 30+ | 1055430 | 239 | 437 | 488 | 99.8898 |
| full-validation-sup | 100 | <10 | 826803 | 54509 | 26314 | 50266 | 86.3148 |
| full-validation-sup | 500 | 10-<20 | 1258702 | 14737 | 11865 | 14579 | 96.8319 |
| full-validation-sup | 500 | 20-<30 | 8892218 | 10619 | 10633 | 13335 | 99.6125 |
| full-validation-sup | 500 | 30+ | 444297 | 101 | 198 | 205 | 99.8867 |
| full-validation-sup | 500 | <10 | 312693 | 19906 | 9806 | 18553 | 86.6286 |
| full-sealed_test-hac | 100 | 10-<20 | 30940182 | 282620 | 193239 | 261859 | 97.6712 |
| full-sealed_test-hac | 100 | 20-<30 | 70590269 | 173274 | 150250 | 195611 | 99.2699 |
| full-sealed_test-hac | 100 | 30+ | 10834 | 0 | 5 | 3 | 99.9262 |
| full-sealed_test-hac | 100 | <10 | 4279182 | 338006 | 169710 | 275024 | 84.5367 |
| full-sealed_test-hac | 500 | 10-<20 | 12238139 | 113831 | 77005 | 105281 | 97.6375 |
| full-sealed_test-hac | 500 | 20-<30 | 27734772 | 69298 | 61197 | 77474 | 99.2557 |
| full-sealed_test-hac | 500 | 30+ | 5975 | 0 | 1 | 1 | 99.9665 |
| full-sealed_test-hac | 500 | <10 | 1722619 | 140503 | 70198 | 113044 | 84.1795 |
| full-sealed_test-sup | 100 | 10-<20 | 16771130 | 186594 | 129460 | 179578 | 97.1296 |
| full-sealed_test-sup | 100 | 20-<30 | 85347468 | 148170 | 126042 | 176505 | 99.4747 |
| full-sealed_test-sup | 100 | 30+ | 448921 | 108 | 361 | 204 | 99.8503 |
| full-sealed_test-sup | 100 | <10 | 3699377 | 288429 | 146215 | 253488 | 84.3161 |
| full-sealed_test-sup | 500 | 10-<20 | 6553738 | 76144 | 52376 | 72973 | 97.0172 |
| full-sealed_test-sup | 500 | 20-<30 | 33665739 | 59625 | 50330 | 70135 | 99.4679 |
| full-sealed_test-sup | 500 | 30+ | 197565 | 45 | 259 | 85 | 99.8035 |
| full-sealed_test-sup | 500 | <10 | 1469521 | 119475 | 60434 | 104424 | 83.7881 |

| Unit | Domain bp | Reference homopolymer context | M | X | I | D | Accuracy % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 1 | 15572315 | 86666 | 63631 | 70719 | 98.6006 |
| full-development-hac | 100 | 11+ | 47818 | 81 | 36 | 2068 | 95.6303 |
| full-development-hac | 100 | 2-3 | 12239483 | 55237 | 35130 | 61488 | 98.7745 |
| full-development-hac | 100 | 4-6 | 2873124 | 12790 | 5934 | 26898 | 98.4369 |
| full-development-hac | 100 | 7-10 | 208930 | 631 | 429 | 4006 | 97.6327 |
| full-development-hac | 500 | 1 | 6604601 | 37586 | 27416 | 30203 | 98.579 |
| full-development-hac | 500 | 11+ | 23248 | 36 | 18 | 1017 | 95.596 |
| full-development-hac | 500 | 2-3 | 5187770 | 23793 | 15031 | 26329 | 98.7597 |
| full-development-hac | 500 | 4-6 | 1225992 | 5502 | 2553 | 11557 | 98.4255 |
| full-development-hac | 500 | 7-10 | 90053 | 269 | 210 | 1674 | 97.665 |
| full-development-sup | 100 | 1 | 15621902 | 65247 | 49767 | 52787 | 98.9373 |
| full-development-sup | 100 | 11+ | 47791 | 69 | 35 | 2150 | 95.4961 |
| full-development-sup | 100 | 2-3 | 12275432 | 43126 | 28038 | 45776 | 99.0564 |
| full-development-sup | 100 | 4-6 | 2884408 | 9845 | 5436 | 19914 | 98.7945 |
| full-development-sup | 100 | 7-10 | 209771 | 530 | 326 | 3289 | 98.0623 |
| full-development-sup | 500 | 1 | 6626657 | 28694 | 21773 | 22957 | 98.9041 |
| full-development-sup | 500 | 11+ | 23247 | 29 | 16 | 1078 | 95.3919 |
| full-development-sup | 500 | 2-3 | 5203768 | 18964 | 11740 | 19991 | 99.0352 |
| full-development-sup | 500 | 4-6 | 1230866 | 4390 | 1890 | 8657 | 98.801 |
| full-development-sup | 500 | 7-10 | 90439 | 227 | 140 | 1350 | 98.1369 |
| full-validation-hac | 100 | 1 | 13360760 | 78093 | 57543 | 59892 | 98.5577 |
| full-validation-hac | 100 | 11+ | 40999 | 66 | 34 | 1842 | 95.4775 |
| full-validation-hac | 100 | 2-3 | 10514555 | 50273 | 31740 | 52846 | 98.7336 |
| full-validation-hac | 100 | 4-6 | 2475748 | 11510 | 5068 | 23079 | 98.4234 |
| full-validation-hac | 100 | 7-10 | 179740 | 562 | 369 | 3467 | 97.6116 |
| full-validation-hac | 500 | 1 | 5461830 | 31206 | 23268 | 24359 | 98.5772 |
| full-validation-hac | 500 | 11+ | 19506 | 39 | 12 | 897 | 95.3652 |
| full-validation-hac | 500 | 2-3 | 4300644 | 20306 | 12749 | 21259 | 98.7528 |
| full-validation-hac | 500 | 4-6 | 1015500 | 4460 | 1937 | 9242 | 98.4833 |
| full-validation-hac | 500 | 7-10 | 74409 | 222 | 118 | 1407 | 97.706 |
| full-validation-sup | 100 | 1 | 13414804 | 63402 | 49768 | 49858 | 98.7993 |
| full-validation-sup | 100 | 11+ | 41004 | 50 | 18 | 1904 | 95.4114 |
| full-validation-sup | 100 | 2-3 | 10554865 | 42353 | 28205 | 43749 | 98.9286 |
| full-validation-sup | 100 | 4-6 | 2487819 | 9586 | 5128 | 18483 | 98.6832 |
| full-validation-sup | 100 | 7-10 | 180613 | 517 | 250 | 3127 | 97.8895 |
| full-validation-sup | 500 | 1 | 5479926 | 24938 | 18582 | 19748 | 98.8586 |
| full-validation-sup | 500 | 11+ | 19480 | 25 | 12 | 939 | 95.2288 |
| full-validation-sup | 500 | 2-3 | 4314131 | 16541 | 11082 | 17413 | 98.9669 |
| full-validation-sup | 500 | 4-6 | 1019693 | 3664 | 2724 | 7350 | 98.6706 |
| full-validation-sup | 500 | 7-10 | 74680 | 195 | 102 | 1222 | 98.0065 |
| full-sealed_test-hac | 100 | 1 | 53240886 | 442221 | 303757 | 323444 | 98.0309 |
| full-sealed_test-hac | 100 | 11+ | 93769 | 231 | 189 | 4002 | 95.4965 |
| full-sealed_test-hac | 100 | 2-3 | 41939054 | 284329 | 176441 | 277870 | 98.2693 |
| full-sealed_test-hac | 100 | 4-6 | 9864718 | 63931 | 30948 | 112144 | 97.9445 |
| full-sealed_test-hac | 100 | 7-10 | 682040 | 3188 | 1869 | 15037 | 97.1382 |
| full-sealed_test-hac | 500 | 1 | 20977370 | 180388 | 124692 | 131207 | 97.9626 |
| full-sealed_test-hac | 500 | 11+ | 40061 | 116 | 88 | 1726 | 95.4038 |
| full-sealed_test-hac | 500 | 2-3 | 16512304 | 116056 | 70712 | 111943 | 98.2231 |
| full-sealed_test-hac | 500 | 4-6 | 3899454 | 25704 | 12161 | 44936 | 97.9208 |
| full-sealed_test-hac | 500 | 7-10 | 272316 | 1368 | 748 | 5988 | 97.11 |
| full-sealed_test-sup | 100 | 1 | 53472532 | 340185 | 233126 | 269771 | 98.4478 |
| full-sealed_test-sup | 100 | 11+ | 93672 | 229 | 118 | 4253 | 95.3191 |
| full-sealed_test-sup | 100 | 2-3 | 42101734 | 228502 | 141872 | 232011 | 98.5894 |
| full-sealed_test-sup | 100 | 4-6 | 9913348 | 51764 | 25644 | 90627 | 98.3332 |
| full-sealed_test-sup | 100 | 7-10 | 685610 | 2621 | 1318 | 13113 | 97.5732 |
| full-sealed_test-sup | 500 | 1 | 21073912 | 139592 | 97114 | 109476 | 98.3838 |
| full-sealed_test-sup | 500 | 11+ | 39977 | 114 | 45 | 1861 | 95.1901 |
| full-sealed_test-sup | 500 | 2-3 | 16579797 | 93240 | 56340 | 94432 | 98.5496 |
| full-sealed_test-sup | 500 | 4-6 | 3919165 | 21277 | 9353 | 36476 | 98.3166 |
| full-sealed_test-sup | 500 | 7-10 | 273712 | 1066 | 547 | 5372 | 97.5116 |

The subordinate homopolymer length endpoint requires a maximal reference run of length 2–1000, two exact aligned bases on each flank, and the entire flanked span in one eligible interval. A non-run interior base is complex. It covers only these qualifying aligned runs, with no genome-wide repeat-reconstruction claim.

| Unit | Domain bp | Run length | Correct | Under | Over | Complex |
| --- | --- | --- | --- | --- | --- | --- |
| full-development-hac | 100 | 11+ | 1197 | 1107 | 1187 | 45 |
| full-development-hac | 100 | 2-3 | 5201218 | 21778 | 12424 | 35668 |
| full-development-hac | 100 | 4-6 | 611795 | 12625 | 4164 | 7311 |
| full-development-hac | 100 | 7-10 | 23007 | 1859 | 1082 | 406 |
| full-development-hac | 500 | 11+ | 573 | 535 | 572 | 23 |
| full-development-hac | 500 | 2-3 | 2208817 | 9385 | 5338 | 15322 |
| full-development-hac | 500 | 4-6 | 261849 | 5503 | 1773 | 3174 |
| full-development-hac | 500 | 7-10 | 9962 | 776 | 476 | 187 |
| full-development-sup | 100 | 11+ | 1401 | 1164 | 976 | 33 |
| full-development-sup | 100 | 2-3 | 5268576 | 15703 | 8730 | 26914 |
| full-development-sup | 100 | 4-6 | 624866 | 9239 | 2934 | 5548 |
| full-development-sup | 100 | 7-10 | 23932 | 1628 | 837 | 336 |
| full-development-sup | 500 | 11+ | 655 | 575 | 479 | 15 |
| full-development-sup | 500 | 2-3 | 2237426 | 6881 | 3812 | 11634 |
| full-development-sup | 500 | 4-6 | 267368 | 4009 | 1249 | 2422 |
| full-development-sup | 500 | 7-10 | 10386 | 672 | 356 | 144 |
| full-validation-hac | 100 | 11+ | 1044 | 956 | 1003 | 34 |
| full-validation-hac | 100 | 2-3 | 4462807 | 19154 | 10917 | 31661 |
| full-validation-hac | 100 | 4-6 | 527027 | 10746 | 3574 | 6289 |
| full-validation-hac | 100 | 7-10 | 19788 | 1598 | 943 | 329 |
| full-validation-hac | 500 | 11+ | 474 | 456 | 485 | 11 |
| full-validation-hac | 500 | 2-3 | 1830796 | 7784 | 4450 | 12838 |
| full-validation-hac | 500 | 4-6 | 217224 | 4439 | 1448 | 2491 |
| full-validation-hac | 500 | 7-10 | 8235 | 682 | 398 | 121 |
| full-validation-sup | 100 | 11+ | 1195 | 1031 | 820 | 28 |
| full-validation-sup | 100 | 2-3 | 4517069 | 14936 | 7937 | 24865 |
| full-validation-sup | 100 | 4-6 | 537443 | 8152 | 2497 | 4964 |
| full-validation-sup | 100 | 7-10 | 20442 | 1413 | 753 | 274 |
| full-validation-sup | 500 | 11+ | 550 | 496 | 389 | 11 |
| full-validation-sup | 500 | 2-3 | 1852132 | 6076 | 3217 | 9948 |
| full-validation-sup | 500 | 4-6 | 221399 | 3356 | 1045 | 1956 |
| full-validation-sup | 500 | 7-10 | 8515 | 564 | 335 | 105 |
| full-sealed_test-hac | 100 | 11+ | 2752 | 2012 | 2537 | 132 |
| full-sealed_test-hac | 100 | 2-3 | 17564387 | 95958 | 48648 | 169974 |
| full-sealed_test-hac | 100 | 4-6 | 2063468 | 48884 | 15472 | 33469 |
| full-sealed_test-hac | 100 | 7-10 | 73191 | 6387 | 3843 | 1823 |
| full-sealed_test-hac | 500 | 11+ | 1179 | 856 | 1084 | 62 |
| full-sealed_test-hac | 500 | 2-3 | 6921896 | 38438 | 19628 | 68566 |
| full-sealed_test-hac | 500 | 4-6 | 818002 | 19604 | 6107 | 13391 |
| full-sealed_test-hac | 500 | 7-10 | 29121 | 2588 | 1561 | 786 |
| full-sealed_test-sup | 100 | 11+ | 3234 | 2251 | 1952 | 100 |
| full-sealed_test-sup | 100 | 2-3 | 17854060 | 72629 | 35392 | 130093 |
| full-sealed_test-sup | 100 | 4-6 | 2115714 | 36912 | 11080 | 25539 |
| full-sealed_test-sup | 100 | 7-10 | 76530 | 5668 | 2968 | 1434 |
| full-sealed_test-sup | 500 | 11+ | 1396 | 965 | 822 | 46 |
| full-sealed_test-sup | 500 | 2-3 | 7038201 | 29679 | 14398 | 52769 |
| full-sealed_test-sup | 500 | 4-6 | 838850 | 14928 | 4453 | 10357 |
| full-sealed_test-sup | 500 | 7-10 | 30431 | 2349 | 1236 | 606 |

</details>

<details><summary>Development accuracy variability across the five timing outputs</summary>

| Tier-domain | Metric | n | Median [range] |
| --- | --- | --- | --- |
| hac-100 | aggregate_accuracy | 5 | 0.986427 [0.986427, 0.986427] |
| hac-100 | alignment_columns | 5 | 31367414 [31367414, 31367414] |
| hac-100 | children | 5 | 2614 [2614, 2614] |
| hac-100 | represented_parents | 5 | 2608 [2608, 2608] |
| hac-100 | positive_denominator_parents | 5 | 2186 [2186, 2186] |
| hac-500 | aggregate_accuracy | 5 | 0.986241 [0.986241, 0.986241] |
| hac-500 | alignment_columns | 5 | 13314858 [13314858, 13314858] |
| hac-500 | children | 5 | 2614 [2614, 2614] |
| hac-500 | represented_parents | 5 | 2608 [2608, 2608] |
| hac-500 | positive_denominator_parents | 5 | 2039 [2039, 2039] |
| sup-100 | aggregate_accuracy | 5 | 0.989596 [0.989596, 0.989596] |
| sup-100 | alignment_columns | 5 | 31365639 [31365639, 31365639] |
| sup-100 | children | 5 | 2617 [2617, 2617] |
| sup-100 | represented_parents | 5 | 2608 [2608, 2608] |
| sup-100 | positive_denominator_parents | 5 | 2190 [2190, 2190] |
| sup-500 | aggregate_accuracy | 5 | 0.989345 [0.989345, 0.989345] |
| sup-500 | alignment_columns | 5 | 13316873 [13316873, 13316873] |
| sup-500 | children | 5 | 2617 [2617, 2617] |
| sup-500 | represented_parents | 5 | 2608 [2608, 2608] |
| sup-500 | positive_denominator_parents | 5 | 2043 [2043, 2043] |

These are repeated observations of the same development input, not independent biological replicates or a population confidence interval.

</details>

<details><summary>All retained attempts, failures and reproducibility pins</summary>

| Process status | Count |
| --- | --- |
| command_failed | 3 |
| finished | 295 |
| total | 298 |

| Unit | Stage | Status | Exit | Failure | Retained receipt |
| --- | --- | --- | --- | --- | --- |

All native attempts, superseded attempts, verifier failures, preparation processes and qualification controls remain in the evidence JSON. Expected negative-control native exits are separate from measured process failures. Completion requires the latest native attempts to pass; retained earlier failures remain visible.

The original strict ALT-* truth attempt failed with exit 1; [retained receipt](/home/jake/Projects/nanopore_basecaller/logs/20261022T234349Z-stock-44358f6f256c42b0accb56ba4421d1ac-zIK8uS). The frozen v1.1 confidence-neighborhood amendment and current source snapshot supersede earlier analysis revisions. Earlier failed or superseded accuracy attempts are not qualified by this report.

| Tool | Version |
| --- | --- |
| dorado | 2.1.2+8b8fc5d |
| samtools | samtools 1.24 |

| Tier | Model tree | Files |
| --- | --- | --- |
| hac | /home/jake/Projects/nanopore_basecaller/models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0 | 51 |
| sup | /home/jake/Projects/nanopore_basecaller/models/dna_r10.4.1_e8.2_400bps_sup@v5.2.0 | 158 |

Reproduce export with `uv run python scripts/summarize-controlled.py --stock results/stock/controlled-20261022 --accuracy results/accuracy/controlled-20261022-v1.1-frozen --inputs results/accuracy/controlled-20261022/inputs.json --output REPORT.md --evidence EVIDENCE.json --verify-pins`. Full pin verification reads large artifacts and must run outside GPU measurement. Raw signals, references, model trees, BAMs, ledgers and native logs stay outside Git.

</details>
