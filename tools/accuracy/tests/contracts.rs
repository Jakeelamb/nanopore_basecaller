use accuracy::*;
use std::{
    collections::BTreeMap,
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static NEXT: AtomicU64 = AtomicU64::new(0);
const P: &str = "00000000-0000-0000-0000-000000000001";
const A: &str = "00000000-0000-0000-0000-000000000002";
fn dir() -> PathBuf {
    let p = std::env::temp_dir().join(format!(
        "accuracy-contract-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&p).unwrap();
    p
}
fn fixture() -> (PathBuf, Reference) {
    let p = dir();
    fs::write(p.join("ref"), ">chr1\nACGTAACCGGTTAACCGGTTACGT\n").unwrap();
    let r = Reference::load(&p.join("ref")).unwrap();
    (p, r)
}
fn run(
    seq: &str,
    rf: &str,
    c: &str,
    e: &[(usize, usize)],
) -> (Counts, Losses, u64, BTreeMap<u8, QCounts>) {
    let mut q = BTreeMap::new();
    let mut context = BTreeMap::new();
    let (counts, loss, nm) = walk(
        seq.as_bytes(),
        &vec![b'I'; seq.len()],
        rf.as_bytes(),
        0,
        c,
        e,
        (&mut q, &mut context),
    )
    .unwrap();
    (counts, loss, nm, q)
}
#[test]
fn exact_subset_ignores_whole_nm() {
    let (c, l, nm, _) = run("ACGTTCGT", "ACGTACGT", "4=1X3=", &[(0, 4)]);
    assert_eq!(
        c,
        Counts {
            m: 4,
            ..Default::default()
        }
    );
    assert_eq!(nm, 1);
    assert_eq!(l.excluded_query_bases, 4);
}
#[test]
fn deletion_is_basewise_and_deletion_only_kept() {
    let (c, l, nm, _) = run("ACGT", "ACAAAAGT", "2=4D2=", &[(3, 5)]);
    assert_eq!(
        c,
        Counts {
            d: 2,
            ..Default::default()
        }
    );
    assert_eq!(c.rate(), Some(1.));
    assert_eq!(l.excluded_deletion_bases, 2);
    assert_eq!(nm, 4);
}
#[test]
fn insertions_need_same_interval_both_flanks() {
    for (e, i) in [
        (vec![(0, 4)], 2),
        (vec![(0, 2)], 0),
        (vec![(2, 4)], 0),
        (vec![(0, 2), (2, 4)], 0),
    ] {
        let (c, _, _, _) = run("ACAAGT", "ACGT", "2=2I2=", &e);
        assert_eq!(c.i, i);
    }
}
#[test]
fn terminal_insertions_excluded() {
    let (c, l, _, _) = run("AACGTT", "ACGT", "1I4=1I", &[(0, 4)]);
    assert_eq!(c.i, 0);
    assert_eq!(l.excluded_query_bases, 2);
}
#[test]
fn query_n_is_error_and_q_conserves() {
    let (c, _, nm, q) = run("ANGT", "ACGT", "1=1X2=", &[(0, 4)]);
    assert_eq!(c.x, 1);
    assert_eq!(nm, 1);
    assert_eq!(q[&40].errors_x_i, 1);
    assert_eq!(q[&40].query_columns, 4);
}
#[test]
fn invalid_cursors_eqx_nm_inputs_reject() {
    for (c, s) in [
        ("5=", "ACGT"),
        ("3=", "ACGT"),
        ("4M", "ACGT"),
        ("1H4=", "ACGT"),
        ("1N4=", "ACGT"),
        ("4X", "ACGT"),
    ] {
        assert!(walk(
            s.as_bytes(),
            b"IIII",
            b"ACGT",
            0,
            c,
            &[(0, 4)],
            (&mut BTreeMap::new(), &mut BTreeMap::new())
        )
        .is_err());
    }
}
#[test]
fn repeat_placements_extend_beyond_padding() {
    let mut rf = b"C".to_vec();
    rf.extend(vec![b'A'; 350]);
    rf.push(b'C');
    assert_eq!(variant_footprint(&rf, 150, b"A", b"AA").unwrap(), (0, 352));
    assert_eq!(variant_footprint(&rf, 150, b"AA", b"A").unwrap(), (1, 351));
}
#[test]
fn dinucleotide_repeat_rotation() {
    let rf = b"CATATATATG";
    let (s, e) = variant_footprint(rf, 4, b"T", b"TAT").unwrap();
    assert!(s <= 1 && e >= 9);
}
#[test]
fn reject_symbolic_ambiguous_wrong_ref() {
    for (r, a) in [
        ("C", "A"),
        ("A", "<DEL>"),
        ("A", "*"),
        ("A", "N"),
        ("A", "A[chr1:1["),
    ] {
        assert!(variant_footprint(b"AAAA", 0, r.as_bytes(), a.as_bytes()).is_err());
    }
}
#[test]
fn interval_union_property_and_cursor_conservation() {
    for mask in 0u16..256 {
        let mut e = Vec::new();
        for p in 0..8 {
            if mask & (1 << p) != 0 {
                e.push((p, p + 1));
            }
        }
        merge(&mut e);
        let (c, l, _, _) = run("ACGTACGT", "ACGTACGT", "8=", &e);
        assert_eq!(c.m, mask.count_ones() as u64);
        assert_eq!(c.m + l.excluded_query_bases, 8);
        for p in 0..8 {
            assert_eq!(contains(&e, p).is_some(), mask & (1 << p) != 0);
        }
    }
}
#[test]
fn flanked_hp_under_over_complex_and_boundary() {
    for (s, c, outcome, n) in [
        ("CGAAAATC", "8=", "correct", 4),
        ("CGAAATC", "2=1D5=", "under", 3),
        ("CGAAAAATC", "4=1I4=", "over", 5),
        ("CGAACATC", "4=1X3=", "complex", 4),
    ] {
        let h = homopolymers(s.as_bytes(), b"CGAAAATC", 0, c, &[(0, 8)]).unwrap();
        assert_eq!(h.len(), 1);
        assert_eq!(h[0].outcome, outcome);
        assert_eq!(h[0].query_length, n);
    }
    assert!(homopolymers(b"CGAAAATC", b"CGAAAATC", 0, "8=", &[(1, 8)])
        .unwrap()
        .is_empty());
}
fn vcf(sample: &str, pos: &str, rf: &str, alt: &str, gt: &str) -> String {
    format!("##fileformat=VCFv4.2\n##contig=<ID=chr1,length=24>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample}\nchr1\t{pos}\t.\t{rf}\t{alt}\t.\tPASS\t.\tGT\t{gt}\n")
}
#[test]
fn truth_rejection_controls() {
    for text in [
        vcf("HG005", "5", "A", "T", "0/1"),
        vcf("HG002", "0", "A", "T", "0/1"),
        vcf("HG002", "5", "T", "A", "0/1"),
        vcf("HG002", "5", "A", "<DEL>", "0/1"),
        vcf("HG002", "5", "A", "T", "."),
        vcf("HG002", "5", "A", "T", "0/2"),
        vcf("HG002", "5", "A", "T", "0/1") + "chr1\t2\t.\tC\tT\t.\tPASS\t.\tGT\t0/1\n",
    ] {
        let (p, r) = fixture();
        fs::write(p.join("vcf"), text).unwrap();
        fs::write(p.join("bed"), "chr1\t0\t24\n").unwrap();
        assert!(truth(
            &r,
            TruthSources {
                vcf: &p.join("vcf"),
                confident: &p.join("bed"),
                original_footprints: None,
                spanning_policy: SpanningPolicy::Reject,
            },
            "HG002",
            &[],
            0,
            &p.join("out")
        )
        .is_err());
    }
}
#[test]
fn truth_erosion_mask_and_bed_diagnostics() {
    let (p, r) = fixture();
    fs::write(p.join("vcf"), vcf("HG002", "5", "A", "T", "0/1")).unwrap();
    fs::write(p.join("bed"), "chr1\t10\t24\nchr1\t0\t15\n").unwrap();
    let d = truth(
        &r,
        TruthSources {
            vcf: &p.join("vcf"),
            confident: &p.join("bed"),
            original_footprints: None,
            spanning_policy: SpanningPolicy::Reject,
        },
        "HG002",
        &[],
        1,
        &p.join("out"),
    )
    .unwrap();
    assert_eq!(d.confidence.out_of_order, 1);
    assert_eq!(d.confidence.merged_intervals, 1);
    assert_eq!(d.eligible_bases, 19);
    assert_eq!(
        fs::read_to_string(p.join("out/eligible.bed")).unwrap(),
        "chr1\t1\t3\nchr1\t6\t23\n"
    );
}
fn sam(flag: u16, nm: u64, qual: &str) -> String {
    format!("@SQ\tSN:chr1\tLN:24\n{P}\t{flag}\tchr1\t1\t60\t4=1X3=\t*\t0\t0\tACGTTACC\t{qual}\tNM:i:{nm}\tqs:f:20\n")
}
fn score_fixture(text: &str, ids: &str) -> anyhow::Result<Summary> {
    let (p, r) = fixture();
    fs::write(p.join("sam"), text)?;
    fs::write(p.join("ids"), ids)?;
    fs::write(p.join("bed"), "chr1\t0\t24\n")?;
    score(
        &r,
        &p.join("bed"),
        &p.join("sam"),
        &p.join("ids"),
        &p.join("out"),
        30,
    )
}
#[test]
fn absent_parent_remains_and_reverse_quality_not_reversed() {
    let s = score_fixture(&sam(16, 1, "!III5III"), &format!("{P}\n{A}\n")).unwrap();
    assert_eq!(s.absent_parents, 1);
    assert_eq!(s.counts.x, 1);
    assert_eq!(s.qscore[&20].errors_x_i, 1);
    assert_eq!(s.qscore[&0].errors_x_i, 0);
    assert_eq!(s.losses.query_bases, 8);
}
#[test]
fn foreign_duplicate_empty_nm_and_dictionary_reject() {
    let good = sam(0, 1, "IIIIIIII");
    for (s, ids) in [
        (good.clone(), format!("{A}\n")),
        (
            good.clone() + good.lines().last().unwrap() + "\n",
            format!("{P}\n"),
        ),
        (good.clone(), String::new()),
        (sam(0, 2, "IIIIIIII"), format!("{P}\n")),
        (good.replace("LN:24", "LN:25"), format!("{P}\n")),
        (good, format!("{P}\n{P}\n")),
    ] {
        assert!(score_fixture(&s, &ids).is_err());
    }
}
#[test]
fn supplementary_retained_primary_scores_once() {
    let mut text = sam(0, 1, "IIIIIIII");
    text.push_str(&format!("{P}\t2048\tchr1\t1\t60\t8=\t*\t0\t0\t*\t*\n"));
    let s = score_fixture(&text, &format!("{P}\n")).unwrap();
    assert_eq!(s.children, 1);
    assert_eq!(s.counts.columns(), 8);
}
#[test]
fn low_mapq_accounted_with_clips() {
    let s = score_fixture(
        &sam(0, 1, "IIIIIIII").replace("\t60\t", "\t10\t"),
        &format!("{P}\n"),
    )
    .unwrap();
    assert_eq!(s.aggregate_error_fraction, None);
    assert_eq!(s.losses.policy_excluded_query_bases, 8);
    assert_eq!(s.parent_mean_error_fraction, None);
}
#[test]
fn reference_iupac_allowed_outside_eligible() {
    let p = dir();
    fs::write(p.join("ref"), ">chr1\nACGTRYN\n").unwrap();
    assert!(Reference::load(&p.join("ref")).is_ok());
}
#[test]
fn masked_boundary_removes_entire_cut_homopolymer() {
    let p = dir();
    fs::write(p.join("ref"), ">chr1\nCGAAAAATC\n").unwrap();
    let r = Reference::load(&p.join("ref")).unwrap();
    let mut e = Regions::from([("chr1".into(), vec![(3, 9)])]);
    trim_homopolymer_boundaries(&mut e, &r).unwrap();
    assert_eq!(e["chr1"], vec![(7, 9)]);
    let mut e = Regions::from([("chr1".into(), vec![(0, 5)])]);
    trim_homopolymer_boundaries(&mut e, &r).unwrap();
    assert_eq!(e["chr1"], vec![(0, 2)]);
}
#[test]
fn split_child_combines_parent_and_unmapped_is_visible() {
    let mut text = sam(0, 1, "IIIIIIII");
    text.push_str(&format!("{A}\t4\t*\t0\t0\t*\t*\t0\t0\tNN\t!!\tpi:Z:{P}\n"));
    let s = score_fixture(&text, &format!("{P}\n")).unwrap();
    assert_eq!(s.children, 2);
    assert_eq!(s.expected_parents, 1);
    assert_eq!(s.losses.unmapped_query_bases, 2);
    assert_eq!(s.losses.query_bases, 10);
}
#[test]
fn original_replacement_footprint_survives_normalization() {
    let p = dir();
    let seq = "ACGT".repeat(250);
    fs::write(p.join("ref"), format!(">chr1\n{seq}\n")).unwrap();
    let r = Reference::load(&p.join("ref")).unwrap();
    fs::write(p.join("bed"), "chr1\t0\t1000\n").unwrap();
    fs::write(p.join("vcf"),"##fileformat=VCFv4.2\n##contig=<ID=chr1,length=1000>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tHG002\nchr1\t401\t.\tA\tT\t.\tPASS\t.\tGT\t0/1\n").unwrap();
    fs::write(p.join("original"), "chr1\t300\t401\n").unwrap();
    let d = truth(
        &r,
        TruthSources {
            vcf: &p.join("vcf"),
            confident: &p.join("bed"),
            original_footprints: Some(&p.join("original")),
            spanning_policy: SpanningPolicy::Reject,
        },
        "HG002",
        &[],
        100,
        &p.join("out"),
    )
    .unwrap();
    assert_eq!(d.eligible_bases, 499);
    assert_eq!(
        fs::read_to_string(p.join("out/eligible.bed")).unwrap(),
        "chr1\t100\t200\nchr1\t501\t900\n"
    );
    assert_eq!(d.original_footprints.unwrap().input_intervals, 1);
}
fn neighborhood(
    intervals: &[(usize, usize)],
    spans: &[(usize, usize)],
) -> (Vec<(usize, usize)>, Vec<usize>) {
    let mut c = Regions::from([("chr1".into(), intervals.to_vec())]);
    let s = Regions::from([("chr1".into(), spans.to_vec())]);
    let removed = exclude_spanning_neighborhoods(&mut c, &s);
    (
        c.remove("chr1").unwrap(),
        removed
            .into_iter()
            .map(|r| r.original_merged_index)
            .collect(),
    )
}
#[test]
fn spanning_inside_removes_intersections_and_original_neighbors() {
    let v = [(0, 10), (20, 30), (40, 50), (60, 70), (80, 90)];
    let (kept, removed) = neighborhood(&v, &[(41, 42)]);
    assert_eq!(removed, vec![1, 2, 3]);
    assert_eq!(kept, vec![(0, 10), (80, 90)]);
    let (_, removed) = neighborhood(&v, &[(25, 65)]);
    assert_eq!(removed, vec![0, 1, 2, 3, 4]);
}
#[test]
fn spanning_gap_edges_and_nonrecursive_selection() {
    let v = [(0, 10), (20, 30), (40, 50), (60, 70), (80, 90)];
    let (kept, removed) = neighborhood(&v, &[(31, 32), (32, 33), (31, 32)]);
    assert_eq!(removed, vec![1, 2]);
    assert_eq!(kept, vec![(0, 10), (60, 70), (80, 90)]);
    assert_eq!(neighborhood(&v, &[(10, 20)]).1, vec![0, 1]);
    assert_eq!(neighborhood(&v, &[(0, 1)]).1, vec![0, 1]);
    assert_eq!(neighborhood(&v, &[(99, 100)]).1, vec![4]);
}
#[test]
fn spanning_multiple_stars_union_without_cascading() {
    let v = [
        (0, 10),
        (20, 30),
        (40, 50),
        (60, 70),
        (80, 90),
        (100, 110),
        (120, 130),
    ];
    let (kept, removed) = neighborhood(&v, &[(21, 22), (101, 102), (21, 22)]);
    assert_eq!(removed, vec![0, 1, 2, 4, 5, 6]);
    assert_eq!(kept, vec![(60, 70)]);
}
#[test]
fn actual_orphan_star_pattern_strict_reject_and_amended_gap_exclusion() {
    // HG002 normalized chr1:93847010 G>* GT1/0 and93847011 T>* GT1/0,
    // both in confidence gap[93846875,93847079), have no deletion witness.
    // Condense the coordinates, retaining real alleles/GT and their gap relationship.
    let p = dir();
    let mut seq = "ACGT".repeat(50).into_bytes();
    seq[109] = b'G';
    seq[110] = b'T';
    fs::write(
        p.join("ref"),
        format!(">chr1\n{}\n", String::from_utf8(seq).unwrap()),
    )
    .unwrap();
    let r = Reference::load(&p.join("ref")).unwrap();
    fs::write(
        p.join("bed"),
        "chr1\t0\t30\nchr1\t40\t80\nchr1\t130\t170\nchr1\t180\t200\n",
    )
    .unwrap();
    fs::write(p.join("vcf"),"##fileformat=VCFv4.2\n##contig=<ID=chr1,length=200>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tHG002\nchr1\t110\t.\tG\t*\t50\tPASS\t.\tGT\t1/0\nchr1\t111\t.\tT\t*\t50\tPASS\t.\tGT\t1/0\n").unwrap();
    let vcf_path = p.join("vcf");
    let bed_path = p.join("bed");
    let sources = |policy| TruthSources {
        vcf: &vcf_path,
        confident: &bed_path,
        original_footprints: None,
        spanning_policy: policy,
    };
    assert!(truth(
        &r,
        sources(SpanningPolicy::Reject),
        "HG002",
        &[],
        1,
        &p.join("strict")
    )
    .is_err());
    let d = truth(
        &r,
        sources(SpanningPolicy::ExcludeConfidenceNeighborhood),
        "HG002",
        &[],
        1,
        &p.join("amended"),
    )
    .unwrap();
    assert_eq!(d.spanning_star_records, 2);
    assert_eq!(d.spanning_star_alleles, 2);
    assert_eq!(d.spanning_removed_union_bases, 80);
    assert_eq!(
        d.spanning_removed_intervals
            .iter()
            .map(|v| v.original_merged_index)
            .collect::<Vec<_>>(),
        vec![1, 2]
    );
    assert_eq!(
        d.ordered_domain_bases["0a_after_spanning_star_neighborhoods"],
        50
    );
    assert_eq!(d.eroded_bases, 46);
    assert_eq!(d.eligible_bases, 46);
    assert_eq!(d.ref_checked, 2);
}
#[test]
fn ambiguous_ref_star_cannot_bypass_concrete_ref_validation() {
    let p = dir();
    fs::write(p.join("ref"), ">chr1\nACGTNNACGT\n").unwrap();
    let r = Reference::load(&p.join("ref")).unwrap();
    fs::write(p.join("bed"), "chr1\t0\t4\nchr1\t6\t10\n").unwrap();
    fs::write(p.join("vcf"),"##contig=<ID=chr1,length=10>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tHG002\nchr1\t5\t.\tN\t*\t.\tPASS\t.\tGT\t0/1\n").unwrap();
    let err = truth(
        &r,
        TruthSources {
            vcf: &p.join("vcf"),
            confident: &p.join("bed"),
            original_footprints: None,
            spanning_policy: SpanningPolicy::ExcludeConfidenceNeighborhood,
        },
        "HG002",
        &[],
        0,
        &p.join("out"),
    )
    .err()
    .unwrap();
    assert!(err.to_string().contains("VCF REF mismatch"));
}
