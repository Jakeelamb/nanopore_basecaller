# F4 design and retained-source trace

Source preparation only. Tests executed:0. No model, native, GPU, download, build, host-lock or scientific-body read was performed during preparation.

Two designs were considered. Relocating the historical process supervisor is small but invalid: it derives ROOT from its source path, hardcodes4/8GiB and assumes its own CLI/receipt contract. The selected design imports only the registered original process_guard and wraps one explicit root/cwd/argv request in an external systemd cgroup. The outer process owns the NONBLOCK lock and monitors output/deadline while all full source/input hashes and synchronous preparation execute in the worker cgroup. It retains terminal failure before result projection. This adapter remains unqualified until its own actual unit canary passes.

The comparator validates custody and projects a complete3arm x2mask x64parent matrix. It does not calculate alignments, edit distance, bootstrap bounds, biological counts, or neural scores in Python. Existing unchanged native producers compute those endpoints. Missing closures remain unqualified, with all parent rows retained. A native command can be run only by an externally authored, hash-bound request. There is no native replay fallback.

## Original guard and evidence inspected

Original path `/tmp/nanopore-frontier/private-raw-case/cpu-qualification-prep-v1/process_guard.py`:3443bytes, SHA256 `dd90a7c50cd1b3044178e3ee248e7f5e948840496b1ad0cee3b99dadad6a14e9`. Adapter imports that original source; no copy is imported and no ROOT is patched.

Original controller `run.py`:12241bytes, `4c4cb53f0965f89914d34dc895912e05004b7750d3ff0c0776b2936df57b86a1`. Original admission `/tmp/nanopore-frontier/private-raw-case/qualification-attempt-1/admission.json`:1632bytes, `2f3ffd26a4fb020e602f29dfcf3226212ec1deb0c27132f46c9b2702aa9614f6`. Its controller array binds the guard, controller, policy, launch and check source.

Original cleanup receipt `qualification-attempt-1/process-controls.json`:1879bytes, `f34edfed2d3ed41c9d17d5084ca90307773e368cc804d4050853bcfa03a8c74d`. It records leader exited, TERM then KILL, reaped2211133/status9, terminal process group and unrelated2211132 surviving. These are prior receipts only. They do not qualify the new adapter.

Historical supervisor `/home/jake/Projects/nanopore_basecaller-context-feedback/tools/context_decoder/process_supervisor.py`:14149bytes, `876d1845cd2337e14186ad8e6f52701aa3d2629bf95aa3a1a0be5def0bf8ec3c`. Its `ROOT`, LOGS, worker argv and4/8GiB constraints explain why moving or monkey-patching it is invalid. It is left unchanged and is not imported.

## Scored native model, traced independently from tensors

The bridge admission at `/home/jake/Projects/nanopore_basecaller-retrieval/results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/bridge-admission.json` records `original.scoring_baseline_sam` as mapped SAM `db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe`,16085465bytes. Its scoring_baseline_producers binds native-sam finish `6b7650233fe72054347ea360af8e0be65b53b226249dc6b0ee689131d8c453ee` at `.../reference/results/graph-prior/pilot-v1/development/stages/native-sam/1792727956586205678-a76a1b54/finish.json`.

The native-sam argv is samtools view -h of native-align output `/home/jake/Projects/nanopore_basecaller-reference/logs/20261023T035904Z-stock-e0df1f36f1f64c0b810528344e0affaa-pRpndV/stdout`. Native-align uses stock Dorado2.1.2 binary `08fef6060d9672f1e7b1772470b93ff0750d28d15f2e64cef1d02533a03ebb49`, GRCh38-lr-hq.mmi, threads4, no-sort and mm2 `-x lr:hq -I 16G --eqx -Y`.

Its input is native-call output `/home/jake/Projects/nanopore_basecaller-reference/logs/20261023T035245Z-stock-93a930bbfb534b19b7632efd46c28906-pFic21/stdout`. The native-call finish is `.../stages/native-call/1792727565988902543-35ec027c/finish.json`. Its argv independently declares HAC `dna_r10.4.1_e8.2_400bps_hac@v6.0.0`, exact retained parents.ids, same PAW70337 POD5, batchsize32, min-qscore0, trimnone, disable-read-splitting and emit-moves. Actual calling binary is graph-export build `/home/jake/Projects/nanopore_basecaller-reference/software/graph-prior/build/bin/dorado`, pin `75083954c9aef62f11fadeef005af078a8acb54cd796a646c9f8eb09f78e9b8f`,390816192bytes. It must not be silently relabeled as the stock distributed binary. Metadata were inspected; scientific binary/model/POD5/SAM bodies were not.

The cohort parent pin is2368bytes, SHA256 `c8c0522c01a446b35517cee773f5e7d8014d390796c650b394fa4562a83a9d4a`. The POD5 pin is555013832bytes, `6146625e08d8628cef8474ac6782a1f1c4843c2f499784b803ab64b58e5ecc8e`. Config records chemistry as a required declaration, not a newly established compatibility result; original native run-info/model-config closure must independently confirm it.

Broader frozen stock manifest `/home/jake/Projects/nanopore_basecaller-reference/results/reference-assisted/inputs-native-frozen-v1.json` includes genuine HACv6/SUPv5.2 full-development outputs. Their basecall settings are trimall and default splitting; their full readlist differs from the64parent cohort. SUP is real but direct comparability is unqualified. No same-generation SUP is assumed. Do not compare positive-only subsets, reinterpret HAC tensors as SUP, or infer a SUP win.

## Qualification and science boundaries

Focused tests distinguish source-pin corruption (root/hash guard), mismatched read/model declaration (comparison contract), ordinary-vs-large profile mismatch (driver profile guard), stale/cwd guards, and absent success-linked result/recorder after a genuine synthetic producer. A real orphan test uses the original guard, allows the leader to exit, requires TERM-ignoring descendant KILL/reaping/group-empty and unrelated PID survival. Tests do not skip. The worker fixture kernel check is explicitly mocked for the focused projection tests; only a real external adapter unit can qualify systemd/kernel supervision.

Known source-cut limitations: no retained native producer has yet been admitted and consumed by F4. The generic qualified-comparison receipt contract still requires a bridge to the original scientific producer closure; the stock finish schema is not treated as an automatic acceptance certificate. Exact original mask/truth/mapper closure is still absent from config and explicitly unqualified. Inventory/plan/report can produce honest missing matrices; they cannot yet establish a qualified three-model biological comparison. No biological promotion or speed claim follows from engineering checks.
