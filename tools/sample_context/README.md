The `sample-context` C++23 tool constructs descriptive DNA context paths from additional molecules in a separately declared acquisition. It does not decode target signals, select an inference arm, estimate haplotype probabilities, or evaluate accuracy. `pipeline.py` validates metadata and orchestrates file preparation without launching tools or accessing the network. Native samtools performs reference extraction and CRAM decoding.

The input is the immutable v4 candidate packet, not its truth packet. All 368 cases remain: 311 ordinary, 31 private ordinary and 26 private withheld. Only target identity, orientation, native guard DNA and genomic geometry enter preparation. A withheld HPRC allele can occur in this new molecule source; that is new development information and changes the interpretation of that withholding control.

`pipeline.py` has four phases. Each takes `--request FILE --request-sha256 SHA --output NEWDIR`. All file-valued request fields are exact `{path,size,sha256}` pins. Outputs live beneath `results/sample-context/`. Every phase writes an attempt first, a failure record when possible, and a completion last with file and directory fsync. This is written-last and synced, not a rename-atomic transaction. The caller must provide the existing whole-unit supervisor, canonical nonblocking host lock, CPU/memory/address-space/output limits, terminal tree proof and durable raw command receipts.

| Phase | Request fields | Result |
|---|---|---|
| `plan` | `cases`, `execution`, `auditor`, `parents`, `inspect`, optional `fetch` | `plan.json`, acquired-context `targets.bed`, all-case `regions.txt` |
| `reference` | `plan`, `snapshot`, preexisting `fai`, `dictionary_stage` | `reference.json`, binding every CRAM SQ length/M5 to native stock dictionary |
| `assemble` | `plan`, `reference`, `fetch`, `eof_receipt` | `selected.cram`, `assembly.json` with original byte ranges and derivative hash |
| `packet` | `plan`, `reference`, `assembly`, `bed`, `regions`, `quickcheck_stage`, `faidx_stage`, `decode_stage`, optional `lineage` and `context_role` | `cases.tsv`, `prepared.json` with exact native SAM pin |

The plan can be priced before acquisition; its BED is empty until containers are retained. Reference-fragment regions include every case even when encoded support containers are missing. Native decoding filters only completely acquired contexts. Missing ranges are explicit, not evidence that an allele is absent. Extra ranges are priced from the same retained CRAI; no index/header replay or full-object fallback exists here. A reprice after an additional qualified acquisition uses a new request/output and preserves the old plan.

The registered inspect completion is `results/support-context/paw71238-inspect-1/0a98559380be4cf68d53f879f1664e1d/complete.json`, SHA256 `e4369d3e7f73ec2519350130242bf5d0f4863c179d67d55b63b4f1de1b8fc950`, 6965 bytes. Its original 259,192,705-byte / 81-container price applies to the 311 ordinary acquisition seeds, not proven coverage of all 368 cases. The pipeline rechecks retained complete-container coverage for each case.

The exact retained original v4 auditor must remain `/home/jake/Projects/nanopore_basecaller-context-feedback-v4/scripts/context-program.py`. It verifies its original completed preparation and source inventory `695b709b50d0b2cfbc3e227ec6e3ca94b89e5e37db6296fb7c4a771c7c8784aa`. Relocating its source or changing its `ROOT` is prohibited. The packet is `.../results/context-feedback/v4-prepare-all-1/prepared/cases.tsv`, SHA256 `9cda8f2adcad2c495e300b208e85f009d924d7dd39d46dad8099310817257dd7`.

Prospective native commands, each recorded separately, are:

```sh
/usr/bin/samtools dict STOCK_REFERENCE
/usr/bin/samtools quickcheck -v SELECTED_CRAM
/usr/bin/samtools faidx -r ALL_CASE_REGIONS STOCK_REFERENCE
/usr/bin/samtools view -h --no-PG -T STOCK_REFERENCE -L ACQUIRED_CONTEXT_BED SELECTED_CRAM
```

`STOCK_REFERENCE` is the exact uncompressed reference pin in the registered snapshot. Its existing `.fai` must be separately pinned before any faidx call; do not create an index in the shared source directory. All CRAM SQ M5 values must match native dictionary output before decoding support DNA. Do not substitute a downloaded reference, whole-file/index fallback, variant file or truth fragment. Run samtools with remote reference lookup/cache disabled and the local `-T` reference fixed. The pipeline requires successful linked stage terminal/group cleanup and all eight raw recorder files; outer unit terminal proof remains the coordinator's responsibility.

Assembly concatenates the retained header prefix once, selected whole containers in original offset order, and the exact original 38-byte source EOF tail when it is not already present. It verifies each HTTP response's version, ETag, date, length and range and each original payload hash. EOF verification follows the CRAM v3 HTSlib template, including its documented low-nibble comparison at byte 9; the derivative retains the actual fetched bytes unchanged. A qualified exact-tail acquisition is supplied by the existing transport API. This tool makes no network request.

The optional `sample-producer-lineage/1` contract is a machine-verifiable evidence contract, not a request for human certification. Required identity fields are:

```json
{
  "schema": "sample-producer-lineage/1",
  "supporting_run": "11d77535b149da7c6f7153939924a9fe29559cc7",
  "supporting_flowcell": "PAW71238",
  "target_flowcell": "PAW70337",
  "donor": "HG002",
  "semantics": "pi_original_read_dx_zero_simplex_v1",
  "tag_writer_version": "0.8.2",
  "pi_dx_relationships_preserved": true,
  "read_level_contract_qualified": true,
  "independent_donor_confirmation": false
}
```

It also includes exact actual header `groups`, the target64 `target_parents` pin, `known_target_family_names`, and nonempty pin lists under `evidence.actual_pg_chain`, `pi_dx_tag_writer`, `tag_preservation`, `publisher_library_protocol`, and `target_family_closure`. The actual retained native header pin must be in `actual_pg_chain`. The coordinator must establish these semantics from the actual @PG chain, Dorado 0.8.2 tag-writer source, preservation pipeline and publisher protocol. The contract states that a preserved `pi` is the original physical-read identity; an absent record for that original ID is not an invented second independent family. Missing `dx`, missing RG, inconsistent lineage, cycles/depth beyond 64, duplex/complement marks, and target-connected components are ineligible. Without the qualified producer contract, the default strict role emits no usable path. Missing or unqualified contracts produce explicit unavailable status. No contract claims absence of unobservable library duplicates or independent donor replication.

The actual frozen lineage investigation is unqualified: `logs/context-feedback-program/design/proposed-lineage-contract.json`, SHA256 `8cbcfbda13da45069104d3c61b8604008abfb9f8915acba13fdf5a673d5b4640`, has `read_level_contract_qualified=false`. It does not prove intact upstream lineage or absence of unknown complements. Root separately predeclared a secondary `exploratory_published_protocol` role before data outcomes. This role requires an explicit packet request `context_role`, the pinned contract's supported operational declaration, nonempty `exploratory_assumptions`, declared root rule and all evidence pins. Only the producer-preservation/root interpretation is assumed; no missing/unknown dx, foreign RG, target connection, lineage contradiction or duplex/complement mark is rescued. A missing exploratory contract remains unavailable.

Strict and exploratory packets use separate fresh output directories and the same retained native producer artifacts. `sample-context-cases/2` binds role and lineage mode in its header. The C++ tool also requires `--context-role exploratory_published_protocol` to consume an exploratory packet; omitted role means strict. Every exploratory path carries `context_role=exploratory_published_protocol`, `assumption_tag=published_protocol_pi_dx_preservation_v1`, `strict_read_level_qualified=0` and `promotion_eligible=0`. Results retain `consumer_ready=false` for strict use and expose only `exploratory_consumer_ready`. A downstream inference consumer must explicitly opt into this role. These outputs measure information potential under stated provenance assumptions; they do not establish read-level independence, accuracy improvement or confirmation. No allele gate, support threshold or source weight changes between roles.

The predeclared native support rule is primary, unpaired, nonduplicate, non-QC-failed records, MAPQ at least 30 (255 unavailable), and Phred+33 at least 10 for every observed base from the left guard through the complete right/future guard. Both genomic orientations are supported; SAM SEQ is reference-oriented and output DNA follows the target's native orientation. The left native guard is 10 bases and the right is 20, comprising the original 10-base guard plus 10 future bases. Exact contiguous native guards must map by CIGAR to the fixed genomic cuts. Reference skips, clipped/gapped/mismatched guards, ambiguous reference DNA and unsafe cut placements are explicit exclusions.

For indels, the tool independently computes all optimal global unit-edit alignments of the bounded observed/reference fragment. The reference-cut entry and exit query positions must each be unique across all optimal paths and must agree with the CIGAR-projected core. This avoids letting one arbitrary homopolymer CIGAR choose the ownership of a boundary insertion or deletion. It does not rank paths by truth. Two million DP cells and 4096 DNA bases are explicit exclusion bounds, not silent truncation.

Identical oriented genomic windows and native guards deduplicate across case/parent/source geometry identities. Every case retains its original geometry hash and its computed physical-window hash. A physical family supplies at most one resolved DNA string per such window. Contradictory split/duplicate calls make the family unresolved. Any known target, duplex/complement or invalid-lineage member blocks its entire connected family. This includes cycle/depth failures discovered by the bounded lineage walk: a descendant beyond 64 nodes blocks otherwise shorter ancestors in the same component. Every unambiguous observed DNA string survives, including a single-family string and the empty core of a complete deletion. Counts are descriptive only; no frequency weight or minimum-support threshold is applied.

The outputs are `contexts.tsv` (anonymous DNA path and family IDs per case), `cases.tsv` (all-case coverage/availability census), `families.tsv` (per-window family resolution), `observations.tsv` (per-read projection decisions), `lineage.tsv` (full read-name/source lineage census), and `excluded.tsv` (reason counts). The lineage audit includes sorted `observed_parent_ids_json` and `parent_absent_seen`. Conflicting records retain every observed pi edge for component closure and leave `parent_id` unavailable rather than inventing one ancestry from the first record. `None`/unknown/unavailable context means the downstream consumer must preserve its reference-free baseline. This unit does not implement that later inference choice.

The source owner did not run the formatter. The coordinator first formats the explicit six-file C++ census, freezes the resulting source for review, and then performs engineering qualification inside one freshly coordinated bounded CPU unit:

```sh
/usr/bin/clang-format -i tools/sample_context/include/sample_context/context.h tools/sample_context/src/context.cpp tools/sample_context/src/main.cpp tools/sample_context/src/runtime.cpp tools/sample_context/tests/controls.cpp tools/sample_context/tests/main.cpp
```

Prospective qualification after that source freeze:

```sh
cmake -S tools/sample_context -B results/sample-context/QUALIFY/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/c++ -DSAMPLE_FORMATTER=/usr/bin/clang-format
cmake --build results/sample-context/QUALIFY/build --parallel 2
cmake --build results/sample-context/QUALIFY/build --target format-check
ctest --test-dir results/sample-context/QUALIFY/build --output-on-failure --parallel 1
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never /home/jake/.local/bin/uv run --no-sync python -m unittest discover -s tools/sample_context/tests -p test_pipeline.py -v
results/sample-context/QUALIFY/build/sample-context qualify --output results/sample-context/QUALIFY/arithmetic
```

The C++ controls compare all optimal cut positions against an independent exhaustive edit-path enumerator, exercise forward/reverse SNV/indel projection, boundary ownership, clips/gaps/ambiguous anchors, reference ambiguity, low quality, missing/wrong RG, target ancestors, duplex/complements, unknown lineage, duplicate/split-family collapse, contradictory calls, ordering and rare-path retention. They also check separately tagged exploratory paths without strict readiness and exclusion of missing dx under that role. Twelve Python tests use only synthetic metadata/files, including default-strict unavailable versus explicit exploratory assumptions; they do not import a historical auditor or read a genuine packet. Qualification must retain actual test counts, skipped 0, compile commands, compiler/cache/runtime library pins and final compiled source census. No build, format, test, native or DNA-data execution has been performed by the source owner.

Accepted source review added actual full-build 66-read chains in both declared roles, requiring zero ancestor votes and the depth reason on every connected member. Complete-core deletion controls use disjoint guard/core alphabets so the optimal-DAG cut is uniquely empty; they verify both orientations and retain an empty sequence/hash/count row in actual table builds under both roles. Conflicting-parent fixtures include both candidate roots, their siblings and both records of the disputed QNAME, in forward and reversed order under both roles. They require zero votes from either root/component, both observed parent edges, no invented single conflict ancestry, and invariant path/edge evidence. The control result separately reports `deep_lineage_component_cases` (expected 2), `complete_core_deletion_cases` (expected 4) and `conflicting_parent_order_cases` (expected 4), in addition to the executed assertion count. These fixtures are prepared and remain unexecuted in this source-only handoff.

The worktree has no local `.venv`. Reuse the already retained retrieval environment explicitly for every Python phase, with no sync, offline mode and Python downloads disabled. Source-only environment inspection pins `/home/jake/.local/bin/uv` SHA256 `3e801df892439f5cde65d8b51ea69b69abff199ef37cc3cae4481be15d592df0`; retrieval `.venv/pyvenv.cfg` SHA256 `e665a42a1e82bf4c624ffaec0a7b4d2901bae2eda723569917aa75defc93d573`; and its resolved interpreter `/home/jake/.local/share/uv/python/cpython-3.12.8-linux-x86_64-gnu/bin/python3.12` SHA256 `efd84018e2568d7338abc5cf086f7d6b9f5245ab63433f349259d833162b50c8`. The configuration declares CPython 3.12.8; no interpreter or UV version command was executed in this source unit. Root must retain the actual launched environment/tool pins.
