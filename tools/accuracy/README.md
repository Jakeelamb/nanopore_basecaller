# Exact invariant-sequence scorer

The Rust executable constructs a sample-specific, reference-identical interval domain and scores accepted primary SAM alignment columns in it. It estimates GIAB-supported invariant-sequence error conditional on publisher donor assignment, selected mappings and the frozen domain. It does not establish whole-read diploid accuracy, unique genomic origin, independent donor identity, variant-call accuracy or biological population uncertainty.

```sh
cargo test --locked --manifest-path tools/accuracy/Cargo.toml
cargo clippy --locked --manifest-path tools/accuracy/Cargo.toml --all-targets -- -D warnings
cargo build --locked --release --manifest-path tools/accuracy/Cargo.toml

tools/accuracy/target/release/accuracy truth \
  --reference reference.fa --vcf normalized.vcf --original-footprints original-spans.bed \
  --confident confident.bed \
  --sample HG002 --spanning-policy exclude-confidence-neighborhood \
  --exclusions reference-errors.bed --padding 100 --output truth-100

tools/accuracy/target/release/accuracy score \
  --reference reference.fa --eligible truth-100/eligible.bed \
  --sam aligned.sam --parents frozen-read-ids.txt --output score-100
```

Inputs are plaintext. The orchestration layer owns native gzip/bcftools handoffs, SHA-256 pins, acquisition validation, immutable stage receipts and exact closure against the native parent ledger. The required original-footprint BED comes from native `bcftools query -f '%CHROM\t%POS0\t%END\n' original.vcf.gz`; native normalization must first validate every original REF. Rust unions these padded original spans with normalized variant masks, preserving reference footprints trimmed during normalization. Repeat `--exclusions` for multiple tracks. Repeat truth/scoring with padding 500 for the frozen sensitivity domain. Use fresh output directories; a completed JSON output is never overwritten. Partial outputs from failed/interrupted invocations are unqualified.

Truth validates every record's REF, autosomal coordinates, declared sample, called diploid GT indexes, sorted positions and concrete alleles. It validates autosomal VCF dictionary lengths and all BED bounds. BED overlaps and input order are recorded before deterministic merging. It first applies the declared unsupported-star policy to the original merged confident intervals, then erodes retained confident intervals and excludes all record footprints regardless of genotype/filter, expands pure-indel repeat-equivalent placements by reference/motif rotation, adds padded reference-error and non-ACGT exclusions, and removes partial homopolymers at eligible boundaries. Concrete replacements retain their complete REF footprint; padding is a finite exclusion assumption, not proof against all unknown variants or mapping shifts. `truth.json` records the remaining bases after each ordered operation and mask input/union sizes; `eligible.bed` is half-open.

The scorer requires the complete SAM dictionary to equal FASTA and validates primary EQX/SEQ/QUAL/NM against the actual reference. Source-parent UUIDs must be unique and nonempty. Every emitted child requires one primary/unmapped record and consistent `pi:Z:` ownership (or QNAME ownership without `pi`). It rejects foreign parents and duplicate primaries. Unobserved source parents remain in `parents.tsv`; missing split siblings cannot be inferred from a represented parent. Root orchestration compares child counts with its independently verified native ledger.

The main policy selects mapped autosomal primaries with MAPQ 30–254 (`--min-mapq` can explicitly change the lower threshold). Secondary/supplementary records contribute no columns; their presence does not remove an accepted primary. `alternate-alignments.tsv` preserves their flags, spans and clips. SAM SEQ/QUAL already follow reference orientation, including reverse records. Unsupported primary M/H/N/P CIGAR operations fail qualification.

Correct, substitution, insertion and deletion columns are `m`, `x`, `i`, `d`. Error is `(x+i+d)/(m+x+i+d)`; query and reference denominators are `m+x+i` and `m+x+d`. Query N is an error at an eligible canonical reference position. Insertions require both existing flanks in one eligible interval. Deletions are scored per reference base, retaining crossing-mask and deletion-only segments. Clips, policy losses, excluded query/D bases and crossing deletion events remain explicit. Query conservation is checked per primary and in aggregate.

`score.json` explicitly publishes alignment/query/reference denominators, aggregate accuracy/error, mean parent accuracy/error, and mean and quantiles of parent errors, component counts, losses, dispositions, emitted-Q calibration and fixed length/native-qs/reference-homopolymer-context bins. `children.tsv` and `parents.tsv` retain counts, selection and absence; no eligible denominator yields null JSON error / `NA` TSV error. Calibration uses `(x+i)/(m+x+i)` and expected probabilities `10^(-Q/10)`; deletions have no emitted Q. `qscore.tsv` and `context.tsv` retain the component tables.

`homopolymer.tsv` contains the subordinate maximal-reference-run projection: run length 2–1000, two exact aligned bases on each flank, whole flanked span in one eligible interval, and no insertion between either pair of anchoring bases. Interior non-run bases yield `complex`; otherwise projected query length classifies `correct`, `under` or `over`. All insertion columns between run edges, including adjoining insertions, enter the projection. Empty exposure is explicitly unavailable. Runs longer than 1000 and runs without complete qualified flanks do not belong to this bounded endpoint.

The 2,000 fixed-seed xorshift64 bootstrap resamples positive-denominator source parents, keeping split children together, for aggregate and mean-parent error. Its percentile intervals cover technical parent resampling within the observed flowcell only. They do not cover genomic correlation, donor assignment, truth uncertainty, other flowcells or populations. Parent counts suffice to reproduce the resampling without rerunning SAM traversal.

The required `--spanning-policy reject|exclude-confidence-neighborhood` records an explicit choice. `reject` preserves strict rejection of ALT `*`. Under the pre-results neighborhood amendment, each star REF span removes every intersected original merged confident interval and the closest strictly left and right original intervals. A star in a gap removes its two adjacent intervals. All removals are selected from the original intervals, unioned and deduplicated before erosion; removals never recurse. Star REF/sample/GT/coordinates remain validated and their REF spans remain padded masks. Diagnostics retain star record/allele counts, removed original interval coordinates/indexes, removed union bases and ordered domain exposure. This endpoint measures invariant sequence outside these fixed unsupported-star confidence neighborhoods. It does not reconstruct an orphan star's missing upstream deletion or prove its unknown extent; donor/truth/mapping assumptions remain conditional. Other symbolic and breakend alleles still fail.

The small tests exercise exact interval columns, target-NM counterexamples, boundary insertions, crossing/deletion-only segments, query N, asymmetric reverse-strand quality, reference/mask conservation, repeat equivalence beyond 100 bp, homopolymer projections/boundaries, sample/REF/GT/dictionary rejection, absent/foreign/duplicate parents and secondary/supplementary accounting. These CPU contracts require separate full-truth, genuine native-handoff and full-cohort evidence before endpoint qualification.
