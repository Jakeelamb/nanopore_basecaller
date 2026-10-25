# Independent final causal-prefix runtime review

Verdict: **PASS_EVIDENCE_FOR_BOUNDED_PREFIX_NO_GAIN**.

The retained experiment demonstrates prefix-derived context changing the local partial beam, with qualified command-boundary H4096->H12288 reset-session history. It produced **no accepted SEQ/Q change and no measured accuracy gain** on either prefix. Native, matched free, final rerank and partial search are identical at both H. Biological qualification, private-variant safety and candidate promotion remain **false**.

Reviewed artifact: `/home/jake/Projects/nanopore_basecaller-context-feedback-causal`, branch `experiment/context-feedback-causal`, baseline HEAD `6a8c23e8a34d37bef76f25c30cc007bf429deae5`, with the uncommitted frozen format3 source cut. The actual native binary is `20f5d45bc54088cbf60e4141f6cf9c1c58ef51dc10c9a45ea1be98826d01424d`; source cut `5bc74865aea40e1e02da33cb78b74bd429a52b6c14e6344c13cee75a71996ea1`; native driver `0f518bac6c428a2cfd66dea20ea5e230aa2a6fce307c09274613057cdf4fc173`; evaluator `3d55337f6547eece73e48732e183da09b9fde347aad9be431e7351299c7a0fb6`. All20 native and14 evaluation closure pins match the current files.

## Actual evidence audited

The independent audit checked613 distinct original source/tool/receipt/output pins,7 successful unit completions,31 new successful stages,1 correctly reused Python stage, and39 complete raw8 receipt sets (32 stage receipts plus7 parent receipts). It checked exact expanded argv, cwd, exit, clocks, GNU time, stage terminal/group cleanup, parent terminal/service state, actual kernel CPU/memory/swap, AS/FSIZE and live service policy. The retained order is engineering2, H4096 inference, H12288 inference, H4096 emission, H12288 emission, H4096 score, H12288 score, each parent terminal before the next starts. Both emissions were frozen before either score phase.

All7 parents have exit0/error null, service MainPID0/ControlPID0 and empty ControlGroup, and terminal launcher cleanup. CPU quota is2 and swap0 throughout; engineering/inference use4GiB memory/8GiB AS, emission/scoring16GiB/24GiB. Actual AS and FSIZE match8/24GiB and512MiB. The retained wrappers implement NONBLOCK canonical admission and worker280s/service290s/outer300s, cumulative512MiB output and30GiB disk floor checks. This review did not acquire the lock or perform a fresh host process inventory; terminal claims are tied to the retained observations.

| Successful unit | Completion SHA256 |
| --- | --- |
| `causal-engineering-2` | `7b3861aa909fafbe2cb003f97e79bd1c29b0058b938a657769ce1821141080a4` |
| `causal-infer-4096-1` | `2fa66f0fd5adaa9347155d7e7eb78e05bd02b9a3a7c1b8e56688657e192ff534` |
| `causal-infer-12288-1` | `6ca79d430047f5edd722654e461fa346b010bb5230d5376fa29d2d73b88d5bd6` |
| `causal-emit-4096-1` | `1b64ffbfc7d3de4ae5bc8ee5178cf1c861a983c9cb6f822b62cd83a210447e37` |
| `causal-emit-12288-1` | `42d53e7e26604ef5d86826a3a1ded577ea910bc46d8190a59a24b383fcee6d6b` |
| `causal-score-4096-1` | `759f7475aeb14915daf9bb3b2265d40f618265fa48ac64b344bc0746d371590e` |
| `causal-score-12288-1` | `8b3ca468b4112303495a12b3fc063b9d11535c79f81298913cb856cfc6de4e17` |

Engineering2's actual compile database lists exactly8 required translation units, each with the pinned GCC15 compiler and `-O3 -DNDEBUG -std=c++23 -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off`. Release cache,3 actual link/archive command files and the generated source witness were independently read and hashed. The witness's20 path/size/SHA entries match format3, including both tool identities. Runtime receipts for executable/test and both inference invocations resolve11 file-backed libraries; saved ldd path sets and current library hashes match. Pairer/observer runtime receipts and library pins also match.

Actual CTest/JUnit records one `causal_prefix_controls` testcase, status `run`, zero failed/disabled/skipped cases. JUnit truncates its `system-out` at1024 bytes; the full native JSON was independently parsed from retained raw CTest stdout. It reports local session/reset/PFS rejections and23 tiny raw-path frames,3262 phase-mass comparisons,1288 state-dependent-rank comparisons and339 finalist-census comparisons, with disabled identity, strong synthetic SNV/insertion/deletion controls and the weak counterexample retained. This verifies execution of those bounded controls; it does not establish genuine-prefix variant safety.

The10 Python session/JUnit tests were correctly **reused**, not rerun. Engineering2's `python-controls.json` equals the previously independently audited retained observer result, including4 rejected summary corruptions and `original_attempt_passed:false`. The original engineering1 parent still has exit1 and no completion. Its successful test stage is preserved separately. Both later emission units actually executed their12 naming/splicing/prerequisite tests with zero skips.

## Runtime behavior and objective checks

The native attempt/complete/raw records bind the actual binary, all20 compiled source pins, exact prepared packet and SHA-bound session file. Work-price records bind the exact engineering and preparation completions. Preparation still binds the accepted location completion; selected packet and preparation pins are unchanged.

H4096 starts from H0 with empty revision/commitments. H12288 names the exact qualified H4096 completion/native result, source/binary and prepared/engineering chain. Its previous revision equals the actual360-base H4096 full-prefix result. The two output sessions contain360 and1070 revisable bases, reset true, empty committed SEQ/Q and0 irreversible commits. Four corruptions of the genuine prior result were required to reject before H12288 decoding. Independently repeating only those pure metadata guards against the actual retained prior rejected wrong H, parent, revision and commitment. No encoder/decoder hidden state is carried across H.

The reviewer recomputed retained-center set differences and finalist membership from the actual output traces, without rerunning search:

| H | Local rows | Changed retained sets | Conditioned finalists outside free escape | Selected/full-prefix change |
| --- | ---: | ---: | ---: | --- |
|4096|87|75|6|None|
|12288|93|80|16|None|

All candidate objectives were independently recomputed as `O=L-0.5*edit_distance(center,context)`, with finite-score and unique-candidate checks. Raw winners were recomputed over native+free finalists for rerank and over the combined free/conditioned pool for partial search, including the native/lexical tie rule. Both raw winners equal native/free at both H. The0.5 deficit and0.5 objective-margin gates were recomputed against the contextual objective of the same free baseline; both actual margins are0 and both gates correctly report `objective_margin_fallback`.

| H | Native/free/raw winners | Reference context | Exact-reference signal loss | Reference objective delta |
| --- | --- | --- | ---: | ---: |
|4096|`GTCATCTAAGCCATATCTGC`|`GTGATCTAAGCCATATCTGC`|0.6433322342988959|-0.14333223429889586|
|12288|`CAAAAGCCTTAGAAGTCTAT`|`CAAAAACCTTAGAAGTCTAT`|2.4894033566414464|-1.9894033566414464|

Each reference alternative differs by one edit and occurs in **both** finalist sets. Its0.5 context benefit does not offset its scalar signal loss; each alternative also exceeds the0.5 deficit limit. The actual raw winner was already unchanged, so this is not a changed winner rejected only by the margin gate. The scalar likelihoods here are retained executed scores whose objective arithmetic was checked; they were not independently recomputed from PFS bodies. Reference disagreement does not determine the true donor allele.

Wrong-context rotation changes74/80 retained sets and its reported margin/deficit fallback choices are consistent with independently recomputed objectives. Missing context returns the free choice with identical free/conditioned traces. The native disabled-weight versus missing-context serialized equality assertion executed successfully in the pinned producer; a separate complete disabled-weight outcome was not retained, so this review cannot independently reconstruct that comparison byte-for-byte.

## Arm custody and observed endpoint

The3 evaluation prerequisite equality edges hold on the actual artifacts. Each emitted manifest has4 arms, all aliasing the identical same-H native SAM, with identical full-prefix sequence hashes. The reviewer compared every renamed SAM field against the original prefix mapping, allowing only the documented UUID analysis rename, and compared original SEQ and Q against the exact native TSV. No placeholder Q was needed in this unit.

H4096 aliased SAM SHA256: `f32d11add1ee3b94c908fe07c6eb9db84bb407fa50e6f4a8addfe014eefd257c`; H12288: `29be4291b5b4c7e61271edb9db92d7f9a6e12473631265f0be55e8fd69ca2359`. Every audited score command used the same SAM for baseline and candidate. None of the31 new stages invokes Dorado aligner or a neural forward. This supports zero new mapping/NN invocation in this audited chain; it is not GPU tracing or a global host activity claim.

Counts were independently conserved across each raw parent row, genomic block row, matched BED intervals and summary. Error is `(X+I+D)/(M+X+I+D)`; matched reference exposure is `M+X+D`.

| H | Domains | Matched reference exposure | M/X/I/D, both sides | Error, both sides | Delta / relative reduction |
| --- | --- | ---: | --- | ---: | --- |
|4096|100 and500|316|297/13/13/6|0.0972644376899696|0 /0|
|12288|100 and500|1035|960/48/29/27|0.09774436090225563|0 /0|

One physical parent and one observed block contribute at each H. These overlapping prefixes are correlated observations of the same exposed development molecule; their counts are not independent donor replication. Any bootstrap intervals in the maintained summaries concern this technical observed unit and add no biological confirmation.

The observer retained1231 variants but0 observable parent-variant calls at both H. Baseline ALT, ALT retained and ALT lost are all0 in SNV/insertion/deletion strata; paired ALT tables have no data rows. There is no ALT safety denominator and no changed footprint. Neither this zero-exposure observation nor synthetic controls close private-variant safety or the previous genuine private-query counterexample.

## Exact independent commands and evidence paths

The final audit command was:

```sh
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run --no-sync python logs/context-feedback-program/reviews/causal-runtime-final-audit.py
```

Observed exit0, verdict `PASS_EVIDENCE_FOR_BOUNDED_PREFIX_NO_GAIN`. The stdlib-only audit script SHA256 is `9ade794429b1de14db08d6279faae868a66a5e3492c13f6485e01578394f61e6`. Eight negative controls rejected:4 genuine-prior corruptions,3 independently repinned prerequisite mismatches and1 wrong completion SHA. These exercised pure guards and metadata comparisons in memory, changing no producer, source, acceptance check or scientific payload.

The handoff identity is `bdcbd1e97a1b9b0458117089a9a99b7b3ad8deee44eb5dead600ea62037c722e`; protocol identity is `264f9f57747ee253b2387869a35cc9a2efb72e1ce55ef2fa82bd700c19256e0a`. Both were verified before use. The handoff's summary claims were then checked against the underlying files rather than accepted as evidence alone.

Independent outputs are under `logs/context-feedback-program/reviews/causal-runtime-final-20261025T021202Z/`:

- `audit.json`: SHA256 `7244ffec7f8fb83f8d56de4ac3eb8d157d7dd463c82c6873eb9852679195be79` (356,779 bytes). `stage_commands` retains exact expanded argv/raw pins/time for31 new stages plus the1 reused stage; `units` retains exact parent worker argv and terminal/kernel pins for all7 units. This includes compiler/configure/build/format/CTest/ldd, both native decode commands with packet/session SHA, both12-test emission commands and all maintained posthoc pairer/observer commands.
- `pins.json`: SHA256 `9b474cb05cd3943d07aee27547ac812bf41e46d76db7d99283273dbce10dbdb1` (170,232 bytes), recording615 pins:613 original artifact identities plus the audit and its script. The final terminal print also pinned this manifest itself.

Other review operations were `cat`, `sed -n`, `rg`, `sha256sum`, Git read-only identity/status commands, and explicit shared-environment stdlib scripts that projected small retained JSON/TSV/raw records. No tests, compilation, native command, original producer407-pin audit, NN, alignment, PFS/model/full-reference/truth payload read, lock, network or deletion was performed by this reviewer. No tools failed during this runtime audit. Earlier failed attempts/reviews and the incidental `.venv` were left intact.

## Limits

This verdict qualifies the retained bounded engineering/runtime dataflow and its concrete no-gain outcome. It does not independently rescore PFS tensors, rehash scientific source preimages, attest all process mappings throughout execution or provide a new live process inventory. Those source preimages rely on the earlier qualified prefix/reference custody, whose407-pin producer audit was intentionally not replayed. Saved ldd receipts establish the resolved file closure observed for these commands, not complete dynamic loading behavior.

No accepted edit, changed-site ALT safety, independent donor confirmation,64-parent promotion endpoint, whole-parent accuracy, full-input processing, stock CUDA parity, persistent streaming state or production readiness is established. H/5000 is nominal signal availability; retained single-run costs are not a speedup, throughput or end-to-end latency claim. There is no durable global prior-consumption ledger; the once-only execution queue remains coordinator-owned. No threshold, weight, gate or window change was made in this review.
