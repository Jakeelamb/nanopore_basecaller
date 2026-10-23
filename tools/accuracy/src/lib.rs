use anyhow::{bail, ensure, Context, Result};
use serde::Serialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::File,
    io::{BufRead, BufReader, BufWriter, Write},
    path::Path,
};

pub type Regions = BTreeMap<String, Vec<(usize, usize)>>;
#[derive(Default)]
pub struct Reference {
    pub names: Vec<String>,
    pub seq: BTreeMap<String, Vec<u8>>,
}
fn lines(path: &Path) -> Result<std::io::Lines<BufReader<File>>> {
    Ok(
        BufReader::new(File::open(path).with_context(|| format!("open {}", path.display()))?)
            .lines(),
    )
}
impl Reference {
    pub fn load(path: &Path) -> Result<Self> {
        let mut r = Self::default();
        let mut name = String::new();
        for l in lines(path)? {
            let l = l?;
            if let Some(h) = l.strip_prefix('>') {
                name = h
                    .split_whitespace()
                    .next()
                    .context("empty FASTA name")?
                    .to_owned();
                ensure!(!r.seq.contains_key(&name), "duplicate FASTA contig {name}");
                r.names.push(name.clone());
                r.seq.insert(name.clone(), Vec::new());
            } else {
                ensure!(!name.is_empty(), "FASTA sequence before header");
                let s = r.seq.get_mut(&name).context("missing FASTA contig")?;
                for b in l.bytes() {
                    let b = b.to_ascii_uppercase();
                    ensure!(b"ACGTRYSWKMBDHVN".contains(&b), "invalid FASTA base");
                    s.push(b);
                }
            }
        }
        ensure!(
            !r.names.is_empty() && r.seq.values().all(|s| !s.is_empty()),
            "empty FASTA"
        );
        Ok(r)
    }
    fn get(&self, n: &str) -> Result<&[u8]> {
        self.seq
            .get(n)
            .map(Vec::as_slice)
            .with_context(|| format!("unknown contig {n}"))
    }
}
pub fn autosome(s: &str) -> bool {
    s.strip_prefix("chr")
        .and_then(|s| s.parse::<u8>().ok())
        .is_some_and(|n| (1..=22).contains(&n))
}
pub fn canonical(b: u8) -> bool {
    b"ACGT".contains(&b)
}
pub fn merge(v: &mut Vec<(usize, usize)>) {
    v.sort_unstable();
    let mut o: Vec<(usize, usize)> = Vec::new();
    for &(s, e) in v.iter() {
        if let Some(p) = o.last_mut() {
            if s <= p.1 {
                p.1 = p.1.max(e);
                continue;
            }
        }
        o.push((s, e));
    }
    *v = o;
}
pub fn bases(r: &Regions) -> u64 {
    r.values()
        .flat_map(|v| v.iter())
        .map(|(s, e)| (e - s) as u64)
        .sum()
}
pub fn contains(v: &[(usize, usize)], p: usize) -> Option<usize> {
    let i = v.partition_point(|x| x.0 <= p);
    if i > 0 && p < v[i - 1].1 {
        Some(i - 1)
    } else {
        None
    }
}
#[derive(Default, Serialize)]
pub struct BedDiagnostics {
    pub input_intervals: u64,
    pub input_bases: u64,
    pub out_of_order: u64,
    pub merged_intervals: u64,
    pub union_bases: u64,
}
pub fn bed(path: &Path, r: &Reference, autosomal_only: bool) -> Result<(Regions, BedDiagnostics)> {
    let mut out = Regions::new();
    let mut d = BedDiagnostics::default();
    let mut previous = None;
    for (i, l) in lines(path)?.enumerate() {
        let l = l?;
        if l.is_empty() || l.starts_with('#') || l.starts_with("track ") {
            continue;
        }
        let f: Vec<_> = l.split_whitespace().collect();
        ensure!(f.len() >= 3, "BED line {}", i + 1);
        ensure!(
            !autosomal_only || autosome(f[0]),
            "nonautosomal confident/eligible BED contig {}",
            f[0]
        );
        let s = f[1].parse::<usize>()?;
        let e = f[2].parse::<usize>()?;
        ensure!(
            s < e && e <= r.get(f[0])?.len(),
            "BED bounds line {}",
            i + 1
        );
        let rank = r
            .names
            .iter()
            .position(|n| n == f[0])
            .context("BED contig")?;
        if previous.is_some_and(|p| p > (rank, s)) {
            d.out_of_order += 1;
        }
        previous = Some((rank, s));
        out.entry(f[0].to_owned()).or_default().push((s, e));
        d.input_intervals += 1;
        d.input_bases += (e - s) as u64;
    }
    for v in out.values_mut() {
        merge(v);
        d.merged_intervals += v.len() as u64;
    }
    d.union_bases = bases(&out);
    Ok((out, d))
}
fn add_mask(m: &mut Regions, c: &str, s: usize, e: usize, padding: usize, len: usize) {
    m.entry(c.to_owned()).or_default().push((
        s.saturating_sub(padding),
        e.saturating_add(padding).min(len),
    ));
}
/// Return union of original anchored footprint and every equivalent pure-indel
/// placement. Rotating a motif one base across matching reference proves the
/// shifted allele gives the identical local haplotype; extension stops at ambiguity.
pub fn variant_footprint(seq: &[u8], pos: usize, rf: &[u8], alt: &[u8]) -> Result<(usize, usize)> {
    ensure!(
        !rf.is_empty() && !alt.is_empty() && rf.iter().chain(alt).all(|b| canonical(*b)),
        "non-concrete allele"
    );
    ensure!(
        pos.checked_add(rf.len()).is_some_and(|e| e <= seq.len())
            && &seq[pos..pos + rf.len()] == rf,
        "VCF REF mismatch"
    );
    let (mut a, mut b) = (rf, alt);
    let mut p = pos;
    while !a.is_empty() && !b.is_empty() && a[0] == b[0] {
        a = &a[1..];
        b = &b[1..];
        p += 1;
    }
    while !a.is_empty() && !b.is_empty() && a.last() == b.last() {
        a = &a[..a.len() - 1];
        b = &b[..b.len() - 1];
    }
    let mut start = pos;
    let mut end = pos + rf.len();
    if a.is_empty() != b.is_empty() {
        let motif = if a.is_empty() { b } else { a };
        let k = motif.len();
        let deleted = if a.is_empty() { 0 } else { k };
        let mut left = p;
        let mut shift = 0;
        while left > 0
            && canonical(seq[left - 1])
            && seq[left - 1] == motif[(k - 1 - (shift % k)) % k]
        {
            left -= 1;
            shift += 1;
        }
        let mut right = p;
        shift = 0;
        while right + deleted < seq.len()
            && canonical(seq[right + deleted])
            && seq[right + deleted] == motif[shift % k]
        {
            right += 1;
            shift += 1;
        }
        // Insertion has zero reference footprint; include both potential anchor sides.
        start = start.min(left.saturating_sub(usize::from(deleted == 0)));
        end = end.max((right + deleted + usize::from(deleted == 0)).min(seq.len()));
    }
    Ok((start, end))
}
#[derive(Default, Serialize)]
pub struct TruthDiagnostics {
    pub schema: u32,
    pub sample: String,
    pub padding: usize,
    pub confidence: BedDiagnostics,
    pub original_footprints: Option<BedDiagnostics>,
    pub spanning_policy: SpanningPolicy,
    pub spanning_star_records: u64,
    pub spanning_star_alleles: u64,
    pub spanning_removed_intervals: Vec<SpanningRemoval>,
    pub spanning_removed_union_bases: u64,
    pub eroded_bases: u64,
    pub records: u64,
    pub ref_checked: u64,
    pub filters: BTreeMap<String, u64>,
    pub genotypes: BTreeMap<String, u64>,
    pub variant_types: BTreeMap<String, u64>,
    pub exclusion_tracks: Vec<BedDiagnostics>,
    pub non_acgt_bases: u64,
    pub mask_intervals: u64,
    pub ordered_domain_bases: BTreeMap<String, u64>,
    pub variant_mask_input_bases: u64,
    pub variant_mask_union_bases: u64,
    pub all_mask_union_bases: u64,
    pub eligible_bases: u64,
    pub eligible_intervals: u64,
}
pub struct TruthSources<'a> {
    pub vcf: &'a Path,
    pub confident: &'a Path,
    pub original_footprints: Option<&'a Path>,
    pub spanning_policy: SpanningPolicy,
}
pub fn truth(
    reference: &Reference,
    sources: TruthSources<'_>,
    sample: &str,
    exclusions: &[String],
    padding: usize,
    output: &Path,
) -> Result<TruthDiagnostics> {
    ensure!(sample == "HG002" || sample == "HG005", "unsupported sample");
    let (mut eligible, confidence) = bed(sources.confident, reference, true)?;
    let mut d = TruthDiagnostics {
        schema: 1,
        sample: sample.into(),
        padding,
        confidence,
        spanning_policy: sources.spanning_policy,
        ..Default::default()
    };
    let mut stars = Regions::new();
    let mut masks = Regions::new();
    let mut dictionary = BTreeMap::new();
    let mut header = false;
    let mut last = None;
    for (i, l) in lines(sources.vcf)?.enumerate() {
        let l = l?;
        if let Some(s) = l.strip_prefix("##contig=<") {
            let fields: BTreeMap<_, _> = s
                .trim_end_matches('>')
                .split(',')
                .filter_map(|x| x.split_once('='))
                .collect();
            let id = *fields.get("ID").context("VCF contig ID")?;
            let len = fields
                .get("length")
                .context("VCF contig length")?
                .parse::<usize>()?;
            ensure!(
                dictionary.insert(id.to_owned(), len).is_none(),
                "duplicate VCF contig"
            );
            continue;
        }
        if l.starts_with("##") {
            continue;
        }
        if l.starts_with("#CHROM\t") {
            ensure!(!header, "duplicate VCF sample header");
            let f: Vec<_> = l.split('\t').collect();
            ensure!(f.len() == 10 && f[9] == sample, "VCF sample mismatch");
            for n in reference.names.iter().filter(|n| autosome(n)) {
                ensure!(
                    dictionary.get(n) == Some(&reference.get(n)?.len()),
                    "VCF autosomal dictionary mismatch {n}"
                );
            }
            header = true;
            continue;
        }
        ensure!(header, "VCF record before sample header");
        let f: Vec<_> = l.split('\t').collect();
        ensure!(f.len() == 10, "VCF fields at line {}", i + 1);
        ensure!(autosome(f[0]), "nonautosomal VCF record");
        let seq = reference.get(f[0])?;
        let pos = f[1]
            .parse::<usize>()?
            .checked_sub(1)
            .context("VCF POS zero")?;
        let rank = reference
            .names
            .iter()
            .position(|n| n == f[0])
            .context("VCF contig")?;
        ensure!(
            last.is_none_or(|p| p <= (rank, pos)),
            "unsorted VCF coordinates"
        );
        last = Some((rank, pos));
        let rf = f[3].as_bytes();
        ensure!(
            !rf.is_empty()
                && rf.iter().all(|b| canonical(*b))
                && pos.checked_add(rf.len()).is_some_and(|e| e <= seq.len())
                && &seq[pos..pos + rf.len()] == rf,
            "VCF REF mismatch line {}",
            i + 1
        );
        let alts: Vec<_> = f[4].split(',').collect();
        ensure!(!alts.is_empty(), "empty ALT");
        let fmt: Vec<_> = f[8].split(':').collect();
        let vals: Vec<_> = f[9].split(':').collect();
        ensure!(fmt.len() == vals.len(), "VCF FORMAT value count");
        let gi = fmt.iter().position(|x| *x == "GT").context("missing GT")?;
        let gt = vals[gi];
        let alleles: Vec<_> = gt.split(['|', '/']).collect();
        ensure!(
            alleles.len() == 2
                && alleles
                    .iter()
                    .all(|a| a.parse::<usize>().is_ok_and(|a| a <= alts.len())),
            "invalid diploid GT {gt}"
        );
        ensure!(
            !f[7].split(';').any(|s| s.starts_with("END=")),
            "unsupported VCF END"
        );
        if alts.contains(&"*") {
            d.spanning_star_records += 1;
        }
        for alt in alts {
            if alt == "*" {
                ensure!(
                    sources.spanning_policy == SpanningPolicy::ExcludeConfidenceNeighborhood,
                    "unsupported spanning deletion star under strict policy at {}:{}",
                    f[0],
                    pos + 1
                );
                d.spanning_star_alleles += 1;
                stars
                    .entry(f[0].into())
                    .or_default()
                    .push((pos, pos + rf.len()));
                add_mask(&mut masks, f[0], pos, pos + rf.len(), padding, seq.len());
                *d.variant_types.entry("spanning_star".into()).or_default() += 1;
                continue;
            }

            let (s, e) = variant_footprint(seq, pos, rf, alt.as_bytes())
                .with_context(|| format!("VCF allele line {}", i + 1))?;
            add_mask(&mut masks, f[0], s, e, padding, seq.len());
            let kind = if alt.len() == rf.len() {
                "substitution"
            } else if alt.len() > rf.len() {
                "insertion"
            } else {
                "deletion"
            };
            *d.variant_types.entry(kind.into()).or_default() += 1;
        }
        d.records += 1;
        d.ref_checked += 1;
        *d.filters.entry(f[6].into()).or_default() += 1;
        *d.genotypes.entry(gt.into()).or_default() += 1;
    }
    ensure!(header && d.records > 0, "empty VCF truth");
    if let Some(path) = sources.original_footprints {
        let (original, diag) = bed(path, reference, true)?;
        ensure!(
            diag.input_intervals > 0,
            "empty original variant footprints"
        );
        for (c, v) in original {
            let len = reference.get(&c)?.len();
            for (s, e) in v {
                add_mask(&mut masks, &c, s, e, padding, len);
            }
        }
        d.original_footprints = Some(diag);
    }

    d.ordered_domain_bases
        .insert("0_confident_union".into(), d.confidence.union_bases);
    d.spanning_removed_intervals = exclude_spanning_neighborhoods(&mut eligible, &stars);
    d.spanning_removed_union_bases = d
        .spanning_removed_intervals
        .iter()
        .map(|r| (r.end - r.start) as u64)
        .sum();
    d.ordered_domain_bases.insert(
        "0a_after_spanning_star_neighborhoods".into(),
        bases(&eligible),
    );
    for v in eligible.values_mut() {
        *v = v
            .iter()
            .filter_map(|&(s, e)| {
                if e - s > padding.saturating_mul(2) {
                    Some((s + padding, e - padding))
                } else {
                    None
                }
            })
            .collect();
    }
    d.eroded_bases = bases(&eligible);
    d.ordered_domain_bases
        .insert("1_after_erosion".into(), bases(&eligible));
    d.variant_mask_input_bases = bases(&masks);
    for v in masks.values_mut() {
        merge(v);
    }
    d.variant_mask_union_bases = bases(&masks);
    subtract_masks(&mut eligible, &masks);
    d.ordered_domain_bases
        .insert("2_after_variants".into(), bases(&eligible));
    for path in exclusions {
        let (r, diag) = bed(Path::new(path), reference, false)?;
        d.exclusion_tracks.push(diag);
        for (c, v) in r {
            if !autosome(&c) {
                continue;
            }
            let len = reference.get(&c)?.len();
            for (s, e) in v {
                add_mask(&mut masks, &c, s, e, padding, len);
            }
        }
    }
    for v in masks.values_mut() {
        merge(v);
    }
    subtract_masks(&mut eligible, &masks);
    d.ordered_domain_bases
        .insert("3_after_reference_exclusions".into(), bases(&eligible));
    for c in reference.names.iter().filter(|c| autosome(c)) {
        let seq = reference.get(c)?;
        let mut p = 0;
        while p < seq.len() {
            if canonical(seq[p]) {
                p += 1;
                continue;
            }
            let s = p;
            while p < seq.len() && !canonical(seq[p]) {
                p += 1;
            }
            d.non_acgt_bases += (p - s) as u64;
            add_mask(&mut masks, c, s, p, padding, seq.len());
        }
    }
    for v in masks.values_mut() {
        merge(v);
        d.mask_intervals += v.len() as u64;
    }
    subtract_masks(&mut eligible, &masks);
    d.ordered_domain_bases
        .insert("4_after_non_acgt".into(), bases(&eligible));
    trim_homopolymer_boundaries(&mut eligible, reference)?;
    d.ordered_domain_bases
        .insert("5_after_homopolymer_boundaries".into(), bases(&eligible));
    d.all_mask_union_bases = bases(&masks);
    d.eligible_bases = bases(&eligible);
    d.eligible_intervals = eligible.values().map(|v| v.len() as u64).sum();
    ensure!(d.eligible_bases > 0, "truth has no eligible bases");
    std::fs::create_dir_all(output)?;
    let mut w = BufWriter::new(File::create(output.join("eligible.bed"))?);
    for c in &reference.names {
        if let Some(v) = eligible.get(c) {
            for (s, e) in v {
                writeln!(w, "{c}\t{s}\t{e}")?;
            }
        }
    }
    w.flush()?;
    json(&output.join("truth.json"), &d)?;
    Ok(d)
}
pub fn json(path: &Path, value: &impl Serialize) -> Result<()> {
    let mut w = BufWriter::new(File::create(path)?);
    serde_json::to_writer_pretty(&mut w, value)?;
    writeln!(w)?;
    w.flush()?;
    Ok(())
}

#[derive(Default, Clone, Copy, Serialize, Debug, PartialEq, Eq)]
pub struct Counts {
    pub m: u64,
    pub x: u64,
    pub i: u64,
    pub d: u64,
}
impl Counts {
    pub fn columns(self) -> u64 {
        self.m + self.x + self.i + self.d
    }
    pub fn errors(self) -> u64 {
        self.x + self.i + self.d
    }
    pub fn rate(self) -> Option<f64> {
        (self.columns() > 0).then(|| self.errors() as f64 / self.columns() as f64)
    }
    fn add(&mut self, c: Self) {
        self.m += c.m;
        self.x += c.x;
        self.i += c.i;
        self.d += c.d;
    }
}
#[derive(Default, Clone, Serialize)]
pub struct Losses {
    pub query_bases: u64,
    pub aligned_query_bases: u64,
    pub soft_clipped: u64,
    pub hard_clipped: u64,
    pub excluded_query_bases: u64,
    pub excluded_deletion_bases: u64,
    pub deletion_events: u64,
    pub crossing_deletion_events: u64,
    pub excluded_insertion_events: u64,
    pub unmapped_query_bases: u64,
    pub policy_excluded_query_bases: u64,
    pub reference_skips: u64,
}
impl Losses {
    fn add(&mut self, c: &Self) {
        self.query_bases += c.query_bases;
        self.aligned_query_bases += c.aligned_query_bases;
        self.soft_clipped += c.soft_clipped;
        self.hard_clipped += c.hard_clipped;
        self.excluded_query_bases += c.excluded_query_bases;
        self.excluded_deletion_bases += c.excluded_deletion_bases;
        self.deletion_events += c.deletion_events;
        self.crossing_deletion_events += c.crossing_deletion_events;
        self.excluded_insertion_events += c.excluded_insertion_events;
        self.unmapped_query_bases += c.unmapped_query_bases;
        self.policy_excluded_query_bases += c.policy_excluded_query_bases;
        self.reference_skips += c.reference_skips;
    }
}
#[derive(Default, Clone, Serialize)]
pub struct QCounts {
    pub query_columns: u64,
    pub errors_x_i: u64,
    pub expected_error_sum: f64,
}
#[derive(Default, Serialize)]
pub struct Observation {
    pub parent: String,
    pub child: String,
    pub status: String,
    pub flag: u16,
    pub mapq: u8,
    pub contig: String,
    pub start: usize,
    pub native_qscore: Option<f64>,
    pub counts: Counts,
    pub losses: Losses,
    pub secondary_records: u64,
    pub supplementary_records: u64,
}
#[derive(Default)]
struct Child {
    parent: String,
    primary: Option<Observation>,
    secondary: u64,
    supplementary: u64,
}
#[derive(Default, Serialize)]
pub struct Parent {
    pub parent: String,
    pub children: u64,
    pub selected_children: u64,
    pub status: String,
    pub counts: Counts,
    pub losses: Losses,
    pub error_fraction: Option<f64>,
}
#[derive(Serialize)]
pub struct Summary {
    pub schema: u32,
    pub endpoint: String,
    pub policy: String,
    pub min_mapq: u8,
    pub expected_parents: u64,
    pub represented_parents: u64,
    pub absent_parents: u64,
    pub children: u64,
    pub selected_children: u64,
    pub positive_denominator_parents: u64,
    pub counts: Counts,
    pub losses: Losses,
    pub alignment_columns: u64,
    pub eligible_query_columns: u64,
    pub eligible_reference_columns: u64,
    pub aggregate_accuracy: Option<f64>,
    pub parent_mean_accuracy: Option<f64>,
    pub aggregate_error_fraction: Option<f64>,
    pub parent_mean_error_fraction: Option<f64>,
    pub parent_error_quantiles: BTreeMap<String, f64>,
    pub bootstrap: serde_json::Value,
    pub statuses: BTreeMap<String, u64>,
    pub qscore: BTreeMap<u8, QCounts>,
    pub length_strata: BTreeMap<String, Counts>,
    pub native_qscore_strata: BTreeMap<String, Counts>,
    pub homopolymer_context: BTreeMap<String, Counts>,
    pub homopolymer_length_endpoint: serde_json::Value,
    pub homopolymer_length_counts: BTreeMap<String, HpCounts>,
}
fn cigar(s: &str) -> Result<Vec<(usize, u8)>> {
    let mut out = Vec::new();
    let mut n = 0usize;
    for b in s.bytes() {
        if b.is_ascii_digit() {
            n = n
                .checked_mul(10)
                .and_then(|n| n.checked_add((b - b'0') as usize))
                .context("CIGAR overflow")?;
        } else {
            ensure!(
                n > 0 && b"=XIDSHNP".contains(&b),
                "unsupported/non-EQX CIGAR {s}"
            );
            out.push((n, b));
            n = 0;
        }
    }
    ensure!(n == 0 && !out.is_empty(), "invalid CIGAR {s}");
    Ok(out)
}
fn hp_label(n: usize) -> &'static str {
    match n {
        1 => "1",
        2..=3 => "2-3",
        4..=6 => "4-6",
        7..=10 => "7-10",
        _ => "11+",
    }
}
fn hp_run(seq: &[u8], p: usize) -> (usize, usize) {
    let mut s = p;
    let mut e = p + 1;
    while s > 0 && seq[s - 1] == seq[p] {
        s -= 1;
    }
    while e < seq.len() && seq[e] == seq[p] {
        e += 1;
    }
    (s, e)
}
fn add_q(q: &mut BTreeMap<u8, QCounts>, qual: u8, error: bool) {
    let v = q.entry(qual).or_default();
    v.query_columns += 1;
    v.errors_x_i += u64::from(error);
    v.expected_error_sum += 10f64.powf(-(qual as f64) / 10.0);
}
/// SAM SEQ and QUAL already use alignment orientation, even on flag 16.
/// Every deletion position is independently eligible; insertions need both
/// neighboring reference positions inside one eligible interval.
pub fn walk(
    seq: &[u8],
    qual: &[u8],
    reference: &[u8],
    start: usize,
    cigar_text: &str,
    eligible: &[(usize, usize)],
    strata: (&mut BTreeMap<u8, QCounts>, &mut BTreeMap<String, Counts>),
) -> Result<(Counts, Losses, u64)> {
    let (q, contexts) = strata;
    ensure!(seq.len() == qual.len(), "SEQ/QUAL length mismatch");
    ensure!(qual.iter().all(|q| (33..=126).contains(q)), "invalid QUAL");
    ensure!(
        seq.iter().all(|b| b"ACGTN".contains(b)),
        "unsupported query alphabet"
    );
    let ops = cigar(cigar_text)?;
    let mut rp = start;
    let mut qp = 0usize;
    let mut c = Counts::default();
    let mut loss = Losses {
        query_bases: seq.len() as u64,
        ..Default::default()
    };
    let mut nm = 0u64;
    let mut hp = (0, 0);
    for (n, op) in ops {
        match op {
            b'=' | b'X' => {
                ensure!(
                    rp.checked_add(n).is_some_and(|e| e <= reference.len())
                        && qp.checked_add(n).is_some_and(|e| e <= seq.len()),
                    "CIGAR cursor out of bounds"
                );
                for _ in 0..n {
                    let equal =
                        canonical(seq[qp]) && canonical(reference[rp]) && seq[qp] == reference[rp];
                    ensure!(
                        (op == b'=') == equal,
                        "EQX disagrees with SEQ/reference at {rp}"
                    );
                    nm += u64::from(!equal);
                    loss.aligned_query_bases += 1;
                    if contains(eligible, rp).is_some() {
                        ensure!(canonical(reference[rp]), "noncanonical eligible reference");
                        if rp >= hp.1 {
                            hp = hp_run(reference, rp);
                        }
                        let ct = contexts.entry(hp_label(hp.1 - hp.0).into()).or_default();
                        if equal {
                            c.m += 1;
                            ct.m += 1;
                        } else {
                            c.x += 1;
                            ct.x += 1;
                        }
                        add_q(q, qual[qp] - 33, !equal);
                    } else {
                        loss.excluded_query_bases += 1;
                    }
                    rp += 1;
                    qp += 1;
                }
            }
            b'I' => {
                ensure!(
                    qp.checked_add(n).is_some_and(|e| e <= seq.len()),
                    "insertion query bounds"
                );
                nm += n as u64;
                loss.aligned_query_bases += n as u64;
                let ok = rp > 0
                    && rp < reference.len()
                    && contains(eligible, rp - 1)
                        .is_some_and(|i| contains(eligible, rp) == Some(i));
                if ok {
                    c.i += n as u64;
                    let run = hp_run(reference, rp - 1);
                    contexts
                        .entry(hp_label(run.1 - run.0).into())
                        .or_default()
                        .i += n as u64;
                    for quality in &qual[qp..qp + n] {
                        add_q(q, *quality - 33, true);
                    }
                } else {
                    loss.excluded_query_bases += n as u64;
                    loss.excluded_insertion_events += 1;
                }
                qp += n;
            }
            b'D' => {
                ensure!(
                    rp.checked_add(n).is_some_and(|e| e <= reference.len()),
                    "deletion reference bounds"
                );
                nm += n as u64;
                loss.deletion_events += 1;
                let before_d = c.d;
                for p in rp..rp + n {
                    if contains(eligible, p).is_some() {
                        ensure!(canonical(reference[p]), "noncanonical eligible reference");
                        c.d += 1;
                        if p >= hp.1 {
                            hp = hp_run(reference, p);
                        }
                        contexts.entry(hp_label(hp.1 - hp.0).into()).or_default().d += 1;
                    } else {
                        loss.excluded_deletion_bases += 1;
                    }
                }
                if c.d - before_d > 0 && c.d - before_d < n as u64 {
                    loss.crossing_deletion_events += 1;
                }
                rp += n;
            }
            b'S' => {
                ensure!(
                    qp.checked_add(n).is_some_and(|e| e <= seq.len()),
                    "soft clip bounds"
                );
                qp += n;
                loss.soft_clipped += n as u64;
            }
            b'H' => bail!("hard clipping violates frozen -Y contract"),
            b'N' | b'P' => bail!("unsupported reference skip/padding in DNA alignment"),
            _ => bail!("unsupported CIGAR operation"),
        }
    }
    ensure!(qp == seq.len(), "CIGAR query consumption mismatch");
    ensure!(
        c.m + c.x + c.i + loss.excluded_query_bases + loss.soft_clipped == seq.len() as u64,
        "query conservation failed"
    );
    Ok((c, loss, nm))
}
fn uuid(s: &str) -> bool {
    s.len() == 36
        && s.bytes().enumerate().all(|(i, b)| {
            if [8, 13, 18, 23].contains(&i) {
                b == b'-'
            } else {
                b.is_ascii_hexdigit()
            }
        })
}
fn quantile(v: &[f64], p: f64) -> f64 {
    v[((v.len() - 1) as f64 * p).floor() as usize]
}
fn bootstrap(ps: &[&Parent]) -> serde_json::Value {
    if ps.is_empty() {
        return serde_json::json!({"status":"unavailable","reason":"no_positive_denominator_parents"});
    }
    let mut state = 0x4e414e4f504f5245u64;
    let mut means = Vec::with_capacity(2000);
    let mut aggregate = Vec::with_capacity(2000);
    for _ in 0..2000 {
        let mut c = Counts::default();
        let mut sum = 0.0;
        for _ in 0..ps.len() {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let p = ps[(state % ps.len() as u64) as usize];
            c.add(p.counts);
            sum += p.counts.errors() as f64 / p.counts.columns() as f64;
        }
        means.push(sum / ps.len() as f64);
        aggregate.push(c.errors() as f64 / c.columns() as f64);
    }
    means.sort_by(f64::total_cmp);
    aggregate.sort_by(f64::total_cmp);
    serde_json::json!({"status":"available","replicates":2000,"seed":"0x4e414e4f504f5245","rng":"xorshift64","unit":"positive_denominator_source_parent","scope":"technical_within_flowcell_only","not_covered":["genomic_correlation","truth_uncertainty","donor_assignment","biological_between_flowcell_and_population_variation"],"parent_mean_error_fraction_95_percentile":[quantile(&means,0.025),quantile(&means,0.975)],"aggregate_error_fraction_95_percentile":[quantile(&aggregate,0.025),quantile(&aggregate,0.975)]})
}
pub fn score(
    reference: &Reference,
    eligible_path: &Path,
    sam: &Path,
    parents_path: &Path,
    output: &Path,
    min_mapq: u8,
) -> Result<Summary> {
    let (eligible, _) = bed(eligible_path, reference, true)?;
    ensure!(bases(&eligible) > 0, "empty eligible BED");
    for (c, v) in &eligible {
        let seq = reference.get(c)?;
        for (s, e) in v {
            ensure!(
                seq[*s..*e].iter().all(|b| canonical(*b)),
                "noncanonical eligible reference"
            );
        }
    }
    let mut parents: BTreeMap<String, Parent> = BTreeMap::new();
    for l in lines(parents_path)? {
        let p = l?;
        ensure!(uuid(&p), "invalid parent UUID {p}");
        ensure!(
            parents
                .insert(
                    p.clone(),
                    Parent {
                        parent: p,
                        ..Default::default()
                    }
                )
                .is_none(),
            "duplicate source parent"
        );
    }
    ensure!(!parents.is_empty(), "empty source parent universe");
    let mut children: BTreeMap<String, Child> = BTreeMap::new();
    let mut dictionary = BTreeMap::new();
    let mut records = false;
    let mut q = BTreeMap::new();
    let mut contexts = BTreeMap::new();
    let mut lengths: BTreeMap<String, Counts> = BTreeMap::new();
    let mut nativeqs: BTreeMap<String, Counts> = BTreeMap::new();
    let mut hpcounts: BTreeMap<String, HpCounts> = BTreeMap::new();
    std::fs::create_dir_all(output)?;
    let mut hw = BufWriter::new(File::create(output.join("homopolymer.tsv"))?);
    writeln!(
        hw,
        "parent\tchild\tcontig\tstart0\treference_length\tquery_length\toutcome"
    )?;
    let mut hp_observations = 0u64;
    let mut aw = BufWriter::new(File::create(output.join("alternate-alignments.tsv"))?);
    writeln!(
        aw,
        "parent\tchild\tflag\tcontig\tstart0\tend0\tmapq\tcigar\tsoft_clipped\thard_clipped"
    )?;
    for (line, l) in lines(sam)?.enumerate() {
        let l = l?;
        if l.starts_with('@') {
            ensure!(!records, "SAM header after records");
            if l.starts_with("@SQ\t") {
                let fields: BTreeMap<_, _> = l
                    .split('\t')
                    .skip(1)
                    .filter_map(|s| s.split_once(':'))
                    .collect();
                let n = fields.get("SN").context("SAM SQ SN")?;
                let len = fields.get("LN").context("SAM SQ LN")?.parse::<usize>()?;
                ensure!(
                    dictionary.insert((*n).to_owned(), len).is_none(),
                    "duplicate SAM SQ"
                );
            }
            continue;
        }
        if !records {
            ensure!(
                dictionary.len() == reference.names.len(),
                "SAM/FASTA dictionary size mismatch"
            );
            for n in &reference.names {
                ensure!(
                    dictionary.get(n) == Some(&reference.get(n)?.len()),
                    "SAM/FASTA dictionary mismatch {n}"
                );
            }
            records = true;
        }
        let f: Vec<_> = l.split('\t').collect();
        ensure!(f.len() >= 11, "SAM fields line {}", line + 1);
        let flag = f[1].parse::<u16>()?;
        ensure!(flag & 1 == 0, "paired SAM unsupported");
        let pi = f[11..]
            .iter()
            .filter_map(|s| s.strip_prefix("pi:Z:"))
            .collect::<Vec<_>>();
        ensure!(pi.len() <= 1, "duplicate parent tag");
        let parent = pi.first().copied().unwrap_or(f[0]);
        ensure!(parents.contains_key(parent), "foreign parent {parent}");
        ensure!(!f[0].is_empty() && uuid(f[0]), "invalid child UUID");
        let ch = children.entry(f[0].into()).or_insert_with(|| Child {
            parent: parent.into(),
            ..Default::default()
        });
        ensure!(ch.parent == parent, "child parent changed");
        if flag & 0x900 != 0 {
            let start = f[3].parse::<usize>()?.saturating_sub(1);
            let mut span = 0usize;
            let mut soft = 0usize;
            let mut hard = 0usize;
            if f[5] != "*" {
                for (n, op) in cigar(f[5])? {
                    match op {
                        b'=' | b'X' | b'D' | b'N' => {
                            span = span.checked_add(n).context("alternate span overflow")?
                        }
                        b'S' => soft += n,
                        b'H' => hard += n,
                        _ => {}
                    }
                }
                ensure!(
                    start
                        .checked_add(span)
                        .is_some_and(|e| reference.get(f[2]).is_ok_and(|r| e <= r.len())),
                    "alternate alignment bounds"
                );
            }
            writeln!(
                aw,
                "{parent}\t{}\t{flag}\t{}\t{start}\t{}\t{}\t{}\t{soft}\t{hard}",
                f[0],
                f[2],
                start + span,
                f[4],
                f[5]
            )?;
            ch.secondary += u64::from(flag & 0x100 != 0);
            ch.supplementary += u64::from(flag & 0x800 != 0);
            continue;
        }
        ensure!(ch.primary.is_none(), "duplicate primary child {}", f[0]);
        ensure!(
            f[9] != "*" && f[10] != "*" && f[9].len() == f[10].len(),
            "missing/mismatched primary SEQ/QUAL"
        );
        ensure!(
            f[10].bytes().all(|b| (33..=126).contains(&b)),
            "invalid primary QUAL"
        );
        ensure!(
            f[9].bytes().all(|b| b"ACGTN".contains(&b)),
            "invalid primary query alphabet"
        );
        let mapq = f[4].parse::<u8>()?;
        let qs = f[11..]
            .iter()
            .find_map(|s| s.strip_prefix("qs:f:"))
            .map(str::parse::<f64>)
            .transpose()?;
        ensure!(qs.is_none_or(|v| v.is_finite()), "nonfinite qs tag");
        let mut obs = Observation {
            parent: parent.into(),
            child: f[0].into(),
            flag,
            mapq,
            contig: f[2].into(),
            native_qscore: qs,
            ..Default::default()
        };
        if flag & 4 != 0 {
            ensure!(f[5] == "*", "unmapped record with CIGAR");
            obs.status = "unmapped".into();
            obs.losses.query_bases = f[9].len() as u64;
            obs.losses.unmapped_query_bases = f[9].len() as u64;
        } else {
            let seq = reference.get(f[2])?;
            let start = f[3]
                .parse::<usize>()?
                .checked_sub(1)
                .context("mapped POS zero")?;
            obs.start = start;
            let status = if !autosome(f[2]) {
                "nonautosomal"
            } else if mapq == 255 {
                "unknown_mapq"
            } else if mapq < min_mapq {
                "low_mapq"
            } else {
                "selected"
            };
            let selected = status == "selected";
            let empty = Vec::new();
            let intervals = if selected {
                eligible.get(f[2]).unwrap_or(&empty)
            } else {
                &empty
            };
            let mut discarded_q = BTreeMap::new();
            let mut discarded_context = BTreeMap::new();
            let (counts, mut loss, nm) = walk(
                f[9].as_bytes(),
                f[10].as_bytes(),
                seq,
                start,
                f[5],
                intervals,
                if selected {
                    (&mut q, &mut contexts)
                } else {
                    (&mut discarded_q, &mut discarded_context)
                },
            )
            .with_context(|| format!("SAM line {} child {}", line + 1, f[0]))?;
            let nms: Vec<_> = f[11..]
                .iter()
                .filter_map(|s| s.strip_prefix("NM:i:"))
                .collect();
            ensure!(
                nms.len() == 1 && nms[0].parse::<u64>()? == nm,
                "whole-record NM mismatch {}",
                f[0]
            );
            if !selected {
                loss.policy_excluded_query_bases = loss.aligned_query_bases;
                loss.excluded_query_bases = 0;
            }
            obs.counts = counts;
            obs.losses = loss;
            obs.status = if selected && counts.columns() == 0 {
                "no_eligible_columns".into()
            } else {
                status.into()
            };
            if selected {
                for h in homopolymers(f[9].as_bytes(), seq, start, f[5], intervals)? {
                    let k = hp_label(h.reference_length).to_owned();
                    let v = hpcounts.entry(k).or_default();
                    match h.outcome.as_str() {
                        "correct" => v.correct += 1,
                        "under" => v.under += 1,
                        "over" => v.over += 1,
                        _ => v.complex += 1,
                    };
                    writeln!(
                        hw,
                        "{parent}\t{}\t{}\t{}\t{}\t{}\t{}",
                        f[0], f[2], h.start0, h.reference_length, h.query_length, h.outcome
                    )?;
                    hp_observations += 1;
                }
                let len = f[9].len();
                let k = if len < 1000 {
                    "0-999"
                } else if len < 10000 {
                    "1000-9999"
                } else if len < 50000 {
                    "10000-49999"
                } else {
                    "50000+"
                };
                lengths.entry(k.into()).or_default().add(counts);
                let k = match qs {
                    None => "unavailable",
                    Some(q) if q < 10. => "<10",
                    Some(q) if q < 20. => "10-<20",
                    Some(q) if q < 30. => "20-<30",
                    _ => "30+",
                };
                nativeqs.entry(k.into()).or_default().add(counts);
            }
        }
        ch.primary = Some(obs);
    }
    ensure!(records, "empty SAM");
    std::fs::create_dir_all(output)?;
    let mut w = BufWriter::new(File::create(output.join("children.tsv"))?);
    writeln!(w,"parent\tchild\tstatus\tflag\tmapq\tcontig\tstart0\tm\tx\ti\td\terror_fraction\tquery_bases\tsoft_clipped\texcluded_query_bases\texcluded_deletion_bases\tunmapped_query_bases\tpolicy_excluded_query_bases\tsecondary_records\tsupplementary_records\tnative_qscore")?;
    let mut total = Counts::default();
    let mut losses = Losses::default();
    let mut statuses = BTreeMap::new();
    let mut selected_children = 0;
    for ch in children.values_mut() {
        let mut o = ch
            .primary
            .take()
            .context("child has only secondary/supplementary records")?;
        o.secondary_records = ch.secondary;
        o.supplementary_records = ch.supplementary;
        let p = parents.get_mut(&o.parent).context("parent vanished")?;
        p.children += 1;
        if o.status == "selected" || o.status == "no_eligible_columns" {
            p.selected_children += 1;
            selected_children += 1;
        }
        p.counts.add(o.counts);
        p.losses.add(&o.losses);
        total.add(o.counts);
        losses.add(&o.losses);
        *statuses.entry(o.status.clone()).or_default() += 1;
        writeln!(
            w,
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
            o.parent,
            o.child,
            o.status,
            o.flag,
            o.mapq,
            o.contig,
            o.start,
            o.counts.m,
            o.counts.x,
            o.counts.i,
            o.counts.d,
            opt(o.counts.rate()),
            o.losses.query_bases,
            o.losses.soft_clipped,
            o.losses.excluded_query_bases,
            o.losses.excluded_deletion_bases,
            o.losses.unmapped_query_bases,
            o.losses.policy_excluded_query_bases,
            ch.secondary,
            ch.supplementary,
            opt(o.native_qscore)
        )?;
    }
    w.flush()?;
    let mut w = BufWriter::new(File::create(output.join("parents.tsv"))?);
    writeln!(w,"parent\tchildren\tselected_children\tstatus\tm\tx\ti\td\terror_fraction\tquery_bases\tsoft_clipped\texcluded_query_bases\texcluded_deletion_bases\tunmapped_query_bases\tpolicy_excluded_query_bases")?;
    for p in parents.values_mut() {
        p.status = if p.children == 0 {
            "absent"
        } else if p.counts.columns() == 0 {
            "no_eligible_columns"
        } else {
            "scored"
        }
        .into();
        p.error_fraction = p.counts.rate();
        writeln!(
            w,
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
            p.parent,
            p.children,
            p.selected_children,
            p.status,
            p.counts.m,
            p.counts.x,
            p.counts.i,
            p.counts.d,
            opt(p.error_fraction),
            p.losses.query_bases,
            p.losses.soft_clipped,
            p.losses.excluded_query_bases,
            p.losses.excluded_deletion_bases,
            p.losses.unmapped_query_bases,
            p.losses.policy_excluded_query_bases
        )?;
    }
    w.flush()?;
    let positive: Vec<_> = parents
        .values()
        .filter(|p| p.counts.columns() > 0)
        .collect();
    let mut rates: Vec<_> = positive.iter().filter_map(|p| p.error_fraction).collect();
    rates.sort_by(f64::total_cmp);
    let mut quantiles = BTreeMap::new();
    if !rates.is_empty() {
        for (k, p) in [
            ("p05", 0.05),
            ("p25", 0.25),
            ("p50", 0.5),
            ("p75", 0.75),
            ("p95", 0.95),
        ] {
            quantiles.insert(k.into(), quantile(&rates, p));
        }
    }
    let represented = parents.values().filter(|p| p.children > 0).count() as u64;
    let summary=Summary{schema:1,endpoint:"giab_invariant_sequence_alignment_column_error".into(),policy:format!("primary_autosomal_mapq_{}_to_254; secondary/supplementary_records_retained_but_not_scored; basewise_deletion_eligibility; insertion_both_flanks_same_interval",min_mapq),min_mapq,expected_parents:parents.len()as u64,represented_parents:represented,absent_parents:parents.len()as u64-represented,children:children.len()as u64,selected_children,positive_denominator_parents:positive.len()as u64,counts:total,losses,alignment_columns:total.columns(),eligible_query_columns:total.m+total.x+total.i,eligible_reference_columns:total.m+total.x+total.d,aggregate_accuracy:total.rate().map(|e|1.0-e),parent_mean_accuracy:if rates.is_empty(){None}else{Some(1.0-rates.iter().sum::<f64>()/rates.len()as f64)},aggregate_error_fraction:total.rate(),parent_mean_error_fraction:if rates.is_empty(){None}else{Some(rates.iter().sum::<f64>()/rates.len()as f64)},parent_error_quantiles:quantiles,bootstrap:bootstrap(&positive),statuses,qscore:q,length_strata:lengths,native_qscore_strata:nativeqs,homopolymer_context:contexts,homopolymer_length_endpoint:serde_json::json!({"status":if hp_observations==0{"unavailable"}else{"available"},"observations":hp_observations,"definition":"maximal_reference_runs_length_2_to_1000; two_exact_aligned_bases_each_flank; entire_flanked_span_one_eligible_interval; non_run_base_interior_is_complex","scope":"subordinate_alignment_conditional_endpoint"}),homopolymer_length_counts:hpcounts};
    ensure!(
        summary
            .qscore
            .values()
            .map(|q| q.query_columns)
            .sum::<u64>()
            == total.m + total.x + total.i
            && summary.qscore.values().map(|q| q.errors_x_i).sum::<u64>() == total.x + total.i,
        "Q conservation failed"
    );
    ensure!(
        summary
            .homopolymer_context
            .values()
            .map(|c| c.columns())
            .sum::<u64>()
            == total.columns(),
        "context conservation failed"
    );
    ensure!(
        total.m
            + total.x
            + total.i
            + summary.losses.excluded_query_bases
            + summary.losses.soft_clipped
            + summary.losses.unmapped_query_bases
            + summary.losses.policy_excluded_query_bases
            == summary.losses.query_bases,
        "whole query conservation failed"
    );
    hw.flush()?;
    aw.flush()?;
    json(&output.join("score.json"), &summary)?;
    let mut w = BufWriter::new(File::create(output.join("qscore.tsv"))?);
    writeln!(
        w,
        "q\tquery_columns\terrors_x_i\texpected_error_sum\tobserved_error_fraction"
    )?;
    for (k, v) in &summary.qscore {
        writeln!(
            w,
            "{k}\t{}\t{}\t{}\t{}",
            v.query_columns,
            v.errors_x_i,
            v.expected_error_sum,
            v.errors_x_i as f64 / v.query_columns as f64
        )?;
    }
    w.flush()?;
    let mut w = BufWriter::new(File::create(output.join("context.tsv"))?);
    writeln!(w, "reference_homopolymer_length_bin\tm\tx\ti\td")?;
    for (k, v) in &summary.homopolymer_context {
        writeln!(w, "{k}\t{}\t{}\t{}\t{}", v.m, v.x, v.i, v.d)?;
    }
    w.flush()?;
    Ok(summary)
}
fn opt(v: Option<f64>) -> String {
    v.map(|x| x.to_string()).unwrap_or_else(|| "NA".into())
}

#[derive(Default, Serialize)]
pub struct HpCounts {
    pub correct: u64,
    pub under: u64,
    pub over: u64,
    pub complex: u64,
}
#[derive(Serialize)]
pub struct HpObservation {
    pub start0: usize,
    pub reference_length: usize,
    pub query_length: usize,
    pub outcome: String,
}
/// Subordinate endpoint: maximal reference runs of 2..=1000 bp, two exact
/// aligned bases on each flank, whole flanked span in one eligible interval.
/// All insertions adjoining the run are assigned to that run; a non-run
/// nucleotide inside it is complex, never a favorable length-only call.
pub fn homopolymers(
    seq: &[u8],
    reference: &[u8],
    start: usize,
    cigar_text: &str,
    eligible: &[(usize, usize)],
) -> Result<Vec<HpObservation>> {
    let mut rp = start;
    let mut qp = 0;
    let mut calls: Vec<Option<u8>> = Vec::new();
    let mut insertions: BTreeMap<usize, Vec<u8>> = BTreeMap::new();
    for (n, op) in cigar(cigar_text)? {
        match op {
            b'=' | b'X' => {
                ensure!(
                    qp + n <= seq.len() && rp + n <= reference.len(),
                    "HP cursor bounds"
                );
                calls.extend(seq[qp..qp + n].iter().copied().map(Some));
                qp += n;
                rp += n;
            }
            b'D' => {
                calls.extend(std::iter::repeat_n(None, n));
                rp += n;
            }
            b'I' => {
                ensure!(qp + n <= seq.len(), "HP insertion bounds");
                insertions
                    .entry(rp)
                    .or_default()
                    .extend_from_slice(&seq[qp..qp + n]);
                qp += n;
            }
            b'S' => qp += n,
            _ => bail!("unsupported HP CIGAR"),
        }
    }
    let mut out = Vec::new();
    let mut p = start;
    while p < rp {
        let (s, e) = hp_run(reference, p);
        p = e;
        if e - s < 2 || e - s > 1000 || s < start + 2 || e.checked_add(2).is_none_or(|b| b > rp) {
            continue;
        }
        if contains(eligible, s - 2).is_none_or(|i| contains(eligible, e + 1) != Some(i)) {
            continue;
        }
        let flanks = [s - 2, s - 1, e, e + 1];
        if !flanks
            .iter()
            .all(|&j| canonical(reference[j]) && calls[j - start] == Some(reference[j]))
        {
            continue;
        }
        // Insertions between either pair of anchoring bases invalidate anchors.
        if insertions.contains_key(&(s - 1)) || insertions.contains_key(&(e + 1)) {
            continue;
        }
        let base = reference[s];
        let mut n = 0;
        let mut complex = false;
        for c in calls[s - start..e - start].iter().flatten() {
            n += 1;
            if *c != base {
                complex = true;
            }
        }
        for (_, v) in insertions.range(s..=e) {
            for b in v {
                n += 1;
                if *b != base {
                    complex = true;
                }
            }
        }
        let outcome = if complex {
            "complex"
        } else if n < e - s {
            "under"
        } else if n > e - s {
            "over"
        } else {
            "correct"
        };
        out.push(HpObservation {
            start0: s,
            reference_length: e - s,
            query_length: n,
            outcome: outcome.into(),
        });
    }
    Ok(out)
}

fn subtract_masks(eligible: &mut Regions, masks: &Regions) {
    for (c, v) in eligible.iter_mut() {
        let empty = Vec::new();
        let m = masks.get(c).unwrap_or(&empty);
        let mut out = Vec::new();
        for &(s, e) in v.iter() {
            let mut p = s;
            for &(a, b) in m[m.partition_point(|(_, b)| *b <= s)..]
                .iter()
                .take_while(|(a, _)| *a < e)
            {
                if a > p {
                    out.push((p, a.min(e)));
                }
                p = p.max(b);
                if p >= e {
                    break;
                }
            }
            if p < e {
                out.push((p, e));
            }
        }
        *v = out;
    }
}

pub fn trim_homopolymer_boundaries(eligible: &mut Regions, reference: &Reference) -> Result<()> {
    for (c, v) in eligible.iter_mut() {
        let seq = reference.get(c)?;
        let mut out = Vec::new();
        for &(mut s, mut e) in v.iter() {
            if s > 0 && canonical(seq[s]) && seq[s] == seq[s - 1] {
                s = hp_run(seq, s).1;
            }
            if e < seq.len() && canonical(seq[e - 1]) && seq[e - 1] == seq[e] {
                e = hp_run(seq, e - 1).0;
            }
            if s < e {
                out.push((s, e));
            }
        }
        *v = out;
    }
    Ok(())
}

#[derive(Default, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum SpanningPolicy {
    #[default]
    Reject,
    ExcludeConfidenceNeighborhood,
}
#[derive(Serialize, Debug, PartialEq, Eq)]
pub struct SpanningRemoval {
    pub contig: String,
    pub original_merged_index: usize,
    pub start: usize,
    pub end: usize,
}
/// Selection is against the original merged intervals, once per star REF span.
/// Removed neighbors never become anchors for further recursive removals.
pub fn exclude_spanning_neighborhoods(
    confidence: &mut Regions,
    stars: &Regions,
) -> Vec<SpanningRemoval> {
    let mut removed = Vec::new();
    for (c, spans) in stars {
        if let Some(v) = confidence.get_mut(c) {
            let mut selected = BTreeSet::new();
            for &(s, e) in spans {
                let lo = v.partition_point(|(_, b)| *b <= s);
                let hi = v.partition_point(|(a, _)| *a < e);
                selected.extend(lo..hi);
                if lo > 0 {
                    selected.insert(lo - 1);
                }
                if hi < v.len() {
                    selected.insert(hi);
                }
            }
            for &i in &selected {
                let (s, e) = v[i];
                removed.push(SpanningRemoval {
                    contig: c.clone(),
                    original_merged_index: i,
                    start: s,
                    end: e,
                });
            }
            *v = v
                .iter()
                .enumerate()
                .filter_map(|(i, &x)| (!selected.contains(&i)).then_some(x))
                .collect();
        }
    }
    removed
}
