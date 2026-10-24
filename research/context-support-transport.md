# Bounded independent-flowcell context transport

This is source readiness for a support-data unit. No downloader, compiler, model, native sequencing command, test suite, lock acquisition or data observation was executed here. The coordinator owns exact runtime admission, host supervision, independent review and the PR. Existing producer sources and receipts remain read-only.

The unit implements one Python orchestration path in `tools/support_context/transport.py`, a frozen source descriptor in `tools/support_context/source.json`, and twenty hermetic controls in `tests/test_support_transport.py`. Python performs HTTP, metadata binding, CRAI parsing and command orchestration. Native samtools reads the CRAM SAM header. No Python sequence decoder, sequence aligner or biological scorer is introduced.

## Source and scope

The source is ONT's exposed HG002 SUP PAW71238 release, a different acquisition/flowcell from all 64 retained PAW70337 targets. It is same-donor development support, not independent donor confirmation. The descriptor retains exact version IDs, object sizes, ETags and Last-Modified values from the earlier header lookup, whose SHA256 is `b45addbd1918f5cc55d23fd6b36349fc553bfcddb7f6108b3944842236729c87`. Multipart ETags are object identifiers, not content MD5s.

The [CRAM](https://ont-open-data.s3.amazonaws.com/giab_2025.01/analysis/wf-human-variation/sup/HG002/PAW71238/output/SAMPLE.haplotagged.cram) has 89,968,340,536 bytes. Its [CRAI](https://ont-open-data.s3.amazonaws.com/giab_2025.01/analysis/wf-human-variation/sup/HG002/PAW71238/output/SAMPLE.haplotagged.cram.crai) has 537,321 bytes. No whole-CRAM request exists in this controller.

The target set consists of the 311 previously admitted ordinary v2 core intervals, each with fixed 100 bp reference flanks. All 451 planned ordinary outcomes remain accounted for by the original source-bound full execution; this acquisition unit does not recover the 120 original and twenty boundary exclusions. It reads `original_window` coordinates from pinned construction metadata. It does not read benchmark truth, private haplotypes, candidate scores or observed correction outcomes. Before acquisition and on inspect reuse, it invokes the historical v2 auditor from its original absolute path and verifies its source inventory and recursive full-execution evidence. It never changes that auditor's ROOT.

## Transport and pricing

Every body request has an explicit half-open byte range converted to one HTTP Range, a maximum 1 MiB body, `Accept-Encoding: identity`, `If-Match`, `If-Unmodified-Since`, and the pinned S3 version ID. Redirects are refused. Status must be 206. Content-Range, Content-Length, ETag, Last-Modified, version and encoding must match before any application body read. A 200 response is rejected before its body is read. Requested payload length plus one overrun-detection byte is durably reserved before each HTTP operation. Failed attempts retain partial bytes and reserve budget on resume. These are application payload bounds, not TCP/TLS traffic accounting.

Each successful range has an immutable content pin and request/response receipt. Resume reuses only the exact object, range and payload hash. Corruption rejects reuse; it does not silently overwrite or redownload an allegedly successful chunk. New attempts retain their own files and errors. Output has an exclusive local writer lock. That lock does not replace the canonical host lock held by the coordinator.

The first inspect downloads the complete small CRAI, decompresses at most 16 MiB, and obtains a CRAM prefix ending at the first indexed container, capped at 4 MiB. This prefix boundary relies on the index's completeness. It does not independently prove the absence of an earlier unindexed container. Pinned samtools executes `view --no-PG -H` through the existing raw recorder. Only the SAM header is inspected; no supporting alignment record, allele or read sequence is decoded. Raw command, cwd, exit, clocks, stderr, stdout and GNU time are checked and pinned. The actual CRAM reference dictionary and read groups must identify HG002/PAW71238 and provide valid reference M5 fields. A BAM dictionary is not substituted.

The [primary CRAM specification](https://samtools.github.io/hts-specs/CRAMv3.pdf) defines CRAI slice offsets relative to the end of a container header. Consequently CRAI alone does not determine minimal absolute slice byte extents. This controller prices complete containers from a selected indexed container offset to the next distinct indexed container offset. The last container extends through EOF. It coalesces adjacent ranges and explicitly includes unselected slices and compression headers. Overlap uses CRAI one-based coordinates converted to half-open coordinates. These are indexed container costs, not useful read coverage or allele support.

The separate `fetch` phase requires the exact successful inspect-manifest hash and a fresh explicit payload cap, at most 512 MiB. It fetches only the priced coalesced ranges in at most 1 MiB requests. It retains encoded byte chunks and their original offsets. It does not claim to produce a standalone decoded regional CRAM; assembling a valid derivative and native decoding remain later work. A complete inspect manifest, target custody and all direct output pins are checked again before acquisition.

## Exact prospective commands and caps

Use the shared UV environment. Run these commands only inside the coordinator's exact source-bound CPU supervisor, with fresh nonblocking canonical host-lock acquisition and terminal-tree proof before lock release. Proposed engineering limits are 300 seconds, two CPUs, 4 GiB memory, 8 GiB address space, zero swap, 100 MiB aggregate output stop threshold and a 30 GiB disk reserve. No GPU, model or stock producer is invoked. Qualification is one unit, followed by a separately declared inspect unit under the same host limits. These are ready commands, not executed acceptance evidence.

```bash
cd /home/jake/Projects/nanopore_basecaller-context-feedback-support
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python -m unittest discover -s tests -p test_support_transport.py -v
```

All twenty controls must execute with zero skips. They cover HTTP 200/header drift rejection before body reads, reservation-directory synchronization before HTTP, request and aggregate caps, truncation and overrun, partial-attempt accounting, exact resume, corruption rejection, redirects, CRAI field/decompression bounds, half-open overlap, complete-container overfetch/coalescing, and actual-header dictionary identity requirements. These mocked controls do not qualify real ONT HTTP responses or real samtools header extraction.

```bash
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/support_context/transport.py inspect \
  --output results/support-context/paw71238-inspect-1 \
  --maximum-network-bytes 8388608 \
  --samtools /usr/bin/samtools \
  --samtools-sha256 e839773cc27090fa109588cae8b8240b0d48de816a25b962045867a4c3b7e1ff
```

At most 537,321 CRAI bytes and 4 MiB of CRAM prefix can be requested by a successful fresh inspect, plus one reserved detection byte per request. The fixed 8 MiB budget allows limited retained failed requests and refuses further requests once reservations exhaust it. `--resume` is explicit, uses the same output directory and budget, and writes a separate attempt directory. It never resets prior reservations. The actual successful completion path is printed as a content pin; use that exact pin for later fetch.

```bash
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv \
  uv run --no-sync python tools/support_context/transport.py fetch \
  --output results/support-context/paw71238-fetch-1 \
  --maximum-network-bytes 536870912 \
  --maximum-payload-bytes 500000000 \
  --inspect-manifest ACTUAL_INSPECT_COMPLETION_PATH \
  --inspect-manifest-sha256 ACTUAL_INSPECT_COMPLETION_SHA256
```

The fetch example is a command surface, not an admitted full-set transfer. Price must fit the exact separately declared byte, runtime and disk caps first. If complete-container costs exceed the bound, freeze a smaller region subset before inspecting supporting reads; do not silently extend the budget or select regions using their alleles.

Completion is written last and synced, not rename-atomic. A failed operation writes a durable terminal/error record when Python remains able to handle the exception. Hard kills and native descendant cleanup are covered by the coordinator's external whole-unit supervisor and raw receipt, not by an internal success assertion.

## Remaining scientific gates

Actual full CRAI integrity, native header extraction, expected reference MD5 equality, regional transport costs and useful overlap remain unobserved. Header M5 presence is not reference sequence equality. Regional native decoding must use the exact matching reference and source-bound samtools after that identity check. No supporting sequence has yet been inspected or retained.

Before graph construction, qualify physical-family exclusions for every target, including split children, complements, duplex consensus and derived consensuses. QNAME inequality is insufficient. Different flowcells reduce direct acquisition overlap but do not prove family closure or correct donor/library labelling. Inspect producer `pi`/`dx` and lineage metadata, deduplicate rebasecalls and count physical molecules separately from alignment records. Haplotags are inferred context, not truth. Rare and absent alleles need explicit controls. Freeze support graph/version and partitions before target calling. None of those gates is satisfied by this transport source.

The source lookup reported the ONT AWS registry's CC BY-NC 4.0 terms. Preserve ONT attribution and access dates. Public endpoints do not establish commercial-training or unrestricted redistribution rights. No rights assurance beyond the retained source lookup is made here.

A local metadata-inspection attempt initially assumed flat CRAM response records. The retained lookup instead nests `cram`/`crai` inside response entries. That traversal was corrected before source pins were written. No network operation or scientific producer ran during the correction.
