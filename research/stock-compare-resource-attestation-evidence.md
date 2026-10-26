# Current resource attestation evidence

The genuine read-only resource unit passed at source `96440b0ea0e928ea4f3fb2ba12bdbf606dce83dc`; independent review passed 289 metadata checks. Root reported 39156 CLOSED0/652e03. This establishes current byte identity and compressed/decompressed equivalence at that recorded run. F1 has not consumed the proof; mapping remains unqualified.

All commands used cwd `/home/jake/Projects/nanopore_basecaller-next-stock-compare`, `UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv`, `UV_OFFLINE=1`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONDONTWRITEBYTECODE=1`, `LC_ALL=C`, and fresh contained TMPDIR. Root caps were 300s, CPU2, RAM4GiB, AS8GiB, swap0, growth100MiB, cumulative4GiB, reserve30GiB.

Actual genuine child command, retained rather than rerun:

```text
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python /home/jake/Projects/nanopore_basecaller-next-stock-compare/tools/stock_feedback/resource_attestation.py verify --spec /home/jake/Projects/nanopore_basecaller-next-stock-compare/tools/stock_feedback/resource-attestation-hg002-v1.json --grant /home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes/grants/f4-resource-current-01.json --output /home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/resource-current-01
```

The admitted worker checked 34 unique input pins totalling 9,786,954,328B, including the six current resource pins and authenticated legacy tuples/raw records. Native gzip/SHA exited 0/0; the stream contained 3,144,230,986 bytes with SHA256 `9cce8b926416dd96b152deea85188495b75f7ac8d634cc723a017067be8702b7`, equal to the current decompressed reference pin. The complete FAI map matched 195 contigs/3,099,922,541 bases; reference-file bytes and contig bases are different counts. No index, FAI, alignment, model or neural output was produced.

The worker interval was 2026-10-26T23:32:22.676026+00:00 through 23:32:46.045470+00:00. Actual kernel 4/8GiB, CPU2, swap0 matched admission. Both native stages retain command, cwd, clocks, known exits, time, full stderr and terminal cleanup. Worker/outer exit0, errornull, missing-worker-records empty; launcher group/service cgroup were empty before unlock. These clocks are audit evidence, not performance measurements.

Let `R=results/stock-feedback` and `S=/home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes`. Exact retained pins:

| Artifact | Bytes | SHA256 |
|---|---:|---|
| R/resource-current-01/complete.json | 32409 | `ef7d4e16c9fcc54c7633fa356343fda387999e11d41c1a4fcd193b05d2a57b9a` |
| R/resource-current-01-outer/complete.json | 7364 | `114339b3e068d5eaff796914facfb660e24eece9109848b0f3721121b35c125d` |
| R/resource-current-01-outer/outer-terminal.json | 20041 | `62d6341425880a0436674bff76d5f249f74ffe56573a0bdba48af920b0d138b0` |
| S/grants/f4-resource-current-01.json | 34142 | `e573650a1774eb809c9c851059ad9c8f31e6dfa100afc4183a7977dedc3999f7` |
| S/reviews/F4-resource-current-actual-v1/REPORT.md | 12834 | `3f662f8bd161a47582a8feb3ec769ceae95097b92c9aca881b44e3cc57df7aa2` |
| S/reviews/F4-resource-hermetic-retained-actual-v2/REPORT.md | 11350 | `4dc98ced609ba9349c770ef1a4a943324a2b49e98b425b1d4a434b657a5c0cfe` |

The preceding retention02 unit actually passed 12 controls/skips0; independent review passed 730 checks, including retained native positive, deep-digest negative, gzip-failure and CLI-source rejection records. Its actual command was:

```text
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python -m unittest discover -s /home/jake/Projects/nanopore_basecaller-next-stock-compare/tests -p test_stock_feedback_resource_attestation.py -v
```

Verifier SHA256 `493f81f77b43a8397d81a054fff94bf811b372ccc4803e1c45160f0aed43cbef` and adapter `8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4` remain unchanged. The genuine review's first checker failed on its own underscore/hyphen role-label assumption; preserved checker-v1-error.json records that failure. Corrected verify_actual_v2.py passed without producer replay.

Historical index terminal/admission/source qualification remains false/null; old temporary MMI and terminal files remain missing. Retention01's parent 12-test PASS survives, but its deleted native receipts remain unqualified. Fresh Root preflight numerical records/file ordering were checked; no explicit preflight_utc exists and historical global census was not independently recomputed. Older preflight gaps remain unrepaired. This proves neither mapping/index semantics, library closure, biological accuracy, speed nor forced-deadline/OOM behavior. F1 needs its separately reviewed tagged consumer with modern R1 intact and fresh pilot admission. This documentation turn ran no tests, native scientific commands or resource/tool-binary body hashes and changed no existing source/evidence file.
