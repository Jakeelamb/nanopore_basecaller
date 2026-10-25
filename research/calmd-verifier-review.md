# MD verifier delta review

Verdict: **PASS for the narrow verifier change**, independently checked on 2026-10-22. No implementation fixes are required by this review. This verdict qualifies the observation adapter; it does not establish biological accuracy or a completed full benchmark.

The reviewed artifact is the uncommitted `scripts/benchmark.py` delta from repository HEAD `f10630a2778fa215beeb7135d64f490dbf2a4ea9`. Its SHA-256 is `7623a939d4dca46e64d57a2be312b37a7c84d64aac9401e22d5c5b0e4a65ca55` (60,725 bytes). Reviewed `tests/test_benchmark.py` SHA-256 is `b34b0c6b11d0bce7d354d22e83e0267e006dbd57f104831fcae25f96dffa2b1e` (41,912 bytes). The independent real-pair check pinned the verifier before execution and required the same bytes afterward. This review changed neither implementation nor acceptance checks.

## Implementation findings

`verify_calmd` compares primary membership, all stored primary fields, and auxiliary tag types exactly. It compares every auxiliary tag value other than MD exactly, including NM. The stored first nine SAM fields preserve alignment, mate, and template fields; identical flags plus identical strand-normalized sequence and quality preserve the remaining two core fields. The parser now retains auxiliary tag types, closing a value-only comparison gap.

For changed MD strings, the verifier requires unchanged numeric runs and deletion structure. It walks the complete MD span against EQX CIGAR operations. Insertions and soft clipping advance query coordinates, deletions advance reference coordinates and have no query coordinate, reference skips advance only the reference coordinate, and hard clipping and padding advance neither. Changed bases must be stock `N` to one of `RYSWKMBDHV`. The same coordinate must contain that exact calmd symbol in native faidx output. Wrong, missing, duplicate, or reordered faidx coordinate headers are rejected by the implementation. The observation retains every exception and sets `exact_md_agreement=false`.

`run_unit` obtains faidx through the existing immutable stage mechanism. Its arguments contain the configured reference path and exact queried regions; its context contains the frozen plan/unit identity. Plan loading verifies the pinned reference and tools. A successful stage retains command, stdout, stderr, clocks, exit status, and pins; reuse rechecks those pins. `execute=False` cannot fill in a missing faidx stage. The observation pins the stage receipt and raw stage evidence.

The original failure file remains unchanged. Reporting includes its complete error, verifier identity, path, and pin even when a later observation succeeds. A stale verifier observation cannot qualify. A newer failed observation retires an older success. Expensive run admission still requires native qualification for the current verifier SHA.

## Independent commands and receipts

All commands ran from `/home/jake/Projects/nanopore_basecaller`. Python ran through `uv`. No GPU basecall, alignment, or original producer was repeated by this reviewer.

The independent test command was:

```sh
scripts/record-command.sh calmd-independent-tests env PYTHONPATH=tests NANOPORE_NATIVE_BAM=/home/jake/Projects/nanopore_basecaller/logs/20261022T210643Z-manual-dev32-hac-sxfbo5/stdout NANOPORE_CALMD_PLAN=/home/jake/Projects/nanopore_basecaller/results/stock/stock-20261022/plan.json uv run --locked python -m unittest discover -s tests -v
```

Observed: exit 0; **58 tests passed, zero skips**, 20.930 seconds. Raw receipt: `logs/20261022T220022Z-calmd-independent-tests-DoiBJ7`. Its stderr SHA-256 is `a95fdcad4f270f9b5151f6f62299276a05648a2ddbc5af1229a258f173eaf15f`. This includes genuine retained validation SAM and native stock BAM checks, native calmd fixtures, native coordinate fetch/replay/missing-evidence checks, canonical/count/deletion/NM/field/type/wrong-reference rejection, and current-observation failure reporting.

Two independent assertion programs are retained in full as shell-escaped `uv run --locked python -c` commands. These exact replay commands recover their entire programs:

```sh
bash logs/20261022T220134Z-calmd-independent-real-pair-A92zqg/command.sh
bash logs/20261022T220333Z-calmd-current-qualification-review-PfN3xH/command.sh
git diff --check
```

Both recorded programs and `git diff --check` exited 0. The real-pair command's `command.sh` SHA-256 is `3030688ba5cacbc67ef16dabed08e3a6ddd104cfb8eb9b805c1faa87cf8619cb`; stdout SHA-256 is `90862fa5d22a57a2eaef6cb34d151156ab6269cd8981cbaea17cb5c80c0e47aa`. Its retained result is `logs/calmd-independent-evidence-cwl129vq/review-result.json`. The qualification command stdout SHA-256 is `a98c3db298025927ec6294b424f705e7950bccb50ea5cd6ba8b0fc713fae54b7`. Each recorder directory retains the original execution status, clocks, stdout, and stderr. Replaying the real-pair command creates a new isolated evidence directory and repeats only lightweight native fixture/coordinate work.

## Genuine validation pair

The independent program verified the plan identity, the reference pin, and every pin of the successful retained `basecall`, `base-decode`, `align`, `sort`, `aligned-decode`, `calmd`, and `calmd-decode` receipts for `full-validation-hac`. These receipts and their exact output pins are embedded in its JSON result.

| Artifact | SHA-256 |
| --- | --- |
| Retained aligned SAM, `logs/20261022T214310Z-stock-61b976bd45534773a49d2c08bb4acb55-VLjiYW/stdout` | `a3598bc4d50f3398402604ac9cfdeed3760b383326b4927359adbeaffc354b0b` |
| Retained calmd SAM, `logs/20261022T214352Z-stock-c54371500fad4e5d894c5341df246cbc-RkmedW/stdout` | `51bccd355327b36f5793be57f4e4a08d5f0ea9d40169912734c52fe31c1e4228` |
| Pinned complete reference gzip | `3c8def6d325c5d1e934b2dd530c4d1709f027677a15859467071fddf3fff2026` |
| Original `observation-failure-1792705439201061764.json` | `a05d3564655f0d8d33b8dfc02b941a8449dfd58e84d17438f5c151196b023626` |

Observed: **2,906 records**, including **2,039 primary records**. An additional direct all-record comparison required exact equality of all 11 core fields and all non-MD tag values/types for every record in order. Only the two documented primary MD tags differed. The production helper returned seven exceptions in those two records and explicitly returned `exact_md_agreement=false`.

The exceptions exactly matched the investigation: chr2 reference positions 233142970, 233143703, 233143709, 233143729, 233144847, and 233145086; chr12 position 122093260. Their query positions were 11030, 11765, 11771, 11791, 12968, 13207, and 24008. Their symbols were Y, W, Y, Y, K, W, and Y, all at CIGAR X operations.

Native reference command:

```sh
/usr/bin/samtools faidx /home/jake/Projects/nanopore_basecaller/references/GCA_000001405.15_GRCh38_no_alt_analysis_set.fasta.gz chr12:122093260-122093260 chr2:233142970-233142970 chr2:233143703-233143703 chr2:233143709-233143709 chr2:233143729-233143729 chr2:233144847-233144847 chr2:233145086-233145086
```

Observed native exit 0 with exact symbols. Recorder: `logs/20261022T220141Z-stock-ce91e5687ba64f7d8cb9065af130d75f-eSSeGG`; stdout SHA-256 `76eb9910ff5d06373c14049f3437f518cb53707bf0568be12474c0780cb43b04`. Stage receipt: `logs/calmd-independent-evidence-cwl129vq/calmd-reference-iupac/1792706501494001825-bd424874/finish.json`, SHA-256 `deac2a3ac250376a0551dd9a42bce6ef16e022988dc6e106bdc52ae58dfc31af`. Repeating the verifier with `execute=False` returned the identical result and left exactly one native attempt. A separate empty evidence directory rejected with `Missing retained stage: calmd-reference-iupac`.

## Independent rejection and coordinate controls

The independent real-pair program made isolated in-memory copies of the genuine parsed pair. It rejected a canonical MD replacement, changed match run, changed deletion structure, changed NM, added/removed tag, changed MD/NM tag type, changed sequence/quality, changed membership, and changes to each stored alignment core field 1 through 8. It also rejected reversed IUPAC-to-N substitution. Invalid structural/field controls were required to reject before reference fetching. Exact error text for every control is retained in `review-result.json`.

A separate wrong-symbol FASTA output with correct coordinate headers rejected with `MD ambiguity differs from pinned reference`. A native wrong-reference faidx control on the edge fixture rejected with the same error.

The edge fixture used native samtools BAM encoding, calmd, and faidx with CIGAR `2H3S2=1I1X2=1P2D3N1=1X2S1H`, start 101, NM 5, and stock MD `2N2^NN1N0`. Native calmd produced `2Y2^WK1H0`. The verifier returned exactly:

| Reference position | Query position | Operation | Reference symbol |
| --- | --- | --- | --- |
| 103 | 7 | X | Y |
| 106 | none | D | W |
| 107 | none | D | K |
| 112 | 11 | X | H |

This exercises coordinate movement across hard/soft clipping, insertion, padding, multi-base deletion, reference skip, and mismatches together. All fixture files and native receipts remain under `logs/calmd-independent-evidence-cwl129vq`; originals were untouched.

An isolated report control copied the original failure without changing it. A stale-verifier observation returned `evidence_changed: Current successful verifier observation required`; a later current-verifier observation returned `verified` while retaining the original failure; adding a still newer failure returned `evidence_changed: Newer observation verification failed`. The real original failure's pin was required to remain unchanged. Its original verifier snapshot was also hash-checked as `5b0c5cd0a3fd5869cee3d545a3c4e3b0c4b5eb1dbe73addeb314c548b9233f2e`.

## Current qualification and limits

The independent read-only qualification check inspected the actual final `results/stock/stock-20261022/qualification.json`, SHA-256 `6ad407d86d8a96f7a0c18d7fc693a31b853870e7ce323f0fc17795e8f9020792`. It required the frozen plan identity and reviewed verifier SHA, checked **630 evidence pins**, and observed **21 qualification controls**. The two smoke observations and genuine split-fixture observation all use the reviewed verifier and have exact MD agreement. This is evidence of current native adapter qualification; it is not acceptance of unexecuted full units.

The production comparison remains primary-only, as before this change. The direct all-record check qualifies this retained pair's nonprimary records; it does not extend production enforcement to future nonprimary MD differences. Native calmd and faidx remain trusted external producers with pinned artifacts. Exact unchanged MD annotations follow the prior equality path rather than the new coordinate exception walk. Tests cover the real seven-base case and bounded native fixtures; they are not an exhaustive proof over every legal CIGAR/MD combination or every IUPAC symbol.

This review does not establish biological base or variant accuracy, complete processing of remaining full cohorts, performance comparisons, or behavior of future source revisions. No broken tools or missing required review evidence were encountered. No raw signal, model, reference, native stock artifact, implementation file, or acceptance check was modified by this reviewer.
