# Archive-aware parent emission

This isolated C++23 consumer accepts genuine targeting PLAN and decoded-part
Pins with an explicit storage descriptor for each original native phase trace.
It produces `uncertainty-feedback-archive-parent-emission/1`. Its own compiled
witness and executable Pin identify the new consumer. They do not identify the
unchanged scientific producer.

Status is source preparation only. No configure, compile, formatter, CTest,
archive codec, native apply, scientific payload read or GPU qualification ran
during preparation. See [qualification-plan.md](qualification-plan.md).

## Request contract

The CLI is `uncertainty-feedback-archive-consumer apply --request ABSOLUTE_PATH
--request-sha256 SHA256 --output FRESH_ABSOLUTE_DIRECTORY`.

The request has exactly these keys.

```text
schema = "uncertainty-feedback-archive-apply-request/1"
legacy_plan = FilePin
legacy_decoded_parts = [FilePin, ...]
legacy_source_binding = dependencies.json.legacy_source_binding
old_decoder_manifest = FilePin
traces = [Trace, ...]

FilePin = {path: absolute normalized path, size: nonnegative integer,
           sha256: 64 lowercase hexadecimal characters}
Trace = {query_index: integer in [0,512), native_completion: FilePin,
         producer: FilePin, storage: Storage}
Storage = {codec: "raw", original: FilePin}
        | {codec: "gzip", original: FilePin, archive: FilePin}
```

`legacy_source_binding` has exactly the frozen fields `source_manifest`,
`qualification`, `native_result`, `controls`, `binary`, `runtime` and
`source_witness`. The first six are FilePins. The last is the original compiled
source/compiler witness. The frozen object is in [dependencies.json](dependencies.json).
The request cannot replace it with another producer witness. Source43, accepted
native outer efd8, native result f769, controls f0e8, binary cb480 and runtime6991
remain separate from this consumer's new source and qualification.

Every decoded part keeps its original bytes and original native completion.
Parts must use the identical full512 PLAN and old decoder binary. Every query
appears once. Every supplied trace descriptor is consumed once. Duplicate part,
query, original trace and compressed storage paths reject.

Only the original `phase-trace.bin` Pin has storage resolution. The native seal
has exactly attempt, result and trace. The producer has exactly those three plus
the authentic native completion. All paths are unique. Native stdout is exactly
the JSON object `{"completion": originalNativeCompletionFilePin}`. The result,
seal, producer and descriptor must all name the identical original trace Pin.
Attempt source32 comparison uses unique exact path maps. The actual producer
input tuple remains in its original order.

Gzip verification opens a nonsymlink regular file, verifies the compressed
SHA/size, rewinds the same descriptor, then streams raw bytes through SHA256 and
zlib's gzip CRC/end checks. It rejects bytes beyond the declared raw size as soon
as they appear. It rejects concatenated members, trailing bytes and incomplete
streams. The exact gzip header is `1f8b08000000000000ff`, matching empty filename,
mtime0, level6 XFL0 and OS255. Raw and compressed traces each have a hard100MiB
bound. The decoder buffers two64KiB blocks and never materializes a restored
trace. These are source contracts, pending execution evidence.

The consumer retains the old full512 PLAN and full64 parent guards, raw8 command
receipts, literal decoder argv/inputs, clean environment/runtime, frame geometry
and positive independent scalar comparison guard. It additionally joins the
original construction record to the PLAN, guarded frame and base frame.

## Output contract

All five existing arms retain the same union diagnostic tie rules, edits and
SEQ/Q reconstruction. Changed owned centers receive uncalibrated `!`; off-edit
native Q stays unchanged. Each SAM contains all64 original parents. Current old
and new source write the identical constant `@HD` header and no dynamic `@PG`
header. Therefore exact SAM byte parity is a declared q0 endpoint, pending the
actual baseline and candidate runs. Completion bytes have distinct schemas and
provenance and are not a byte parity endpoint.

Output completion records the own source witness and `consumer_binary`, request
Pin, original decoded-part Pins, trace descriptors, full PLAN, five arm Pins and
edit lists, union diagnostic Pin, actual decoded query IDs and counts. Genuine
q0 must yield `decoded_rows=1`, `nomination_rows=512`,
`population_complete=false`, and all64 parents. No unprocessed query is invented.

The outer qualification/controller must bind the new executable, compiled
source closure, build receipt, runtime inspection and exact input tuple. This
module cannot inherit source43's qualification. Archive conversion and durable
pruning belong to sibling `tools/uncertainty_feedback_archive`. The C++ consumer
does not compress or prune scientific files.
