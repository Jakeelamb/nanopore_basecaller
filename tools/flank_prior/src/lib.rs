use anyhow::{ensure, Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Span {
    pub start: usize,
    pub end: usize,
}
impl Span {
    pub fn overlaps(&self, other: &Self) -> bool {
        self.start < other.end && other.start < self.end
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FlankEvidence {
    pub left: String,
    pub right: String,
    pub reference_intervals: [Span; 2],
    pub read_intervals: [Span; 2],
    pub mapped_sam_sha256: String,
    pub window_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(deny_unknown_fields)]
pub struct WalkPrototype {
    pub left: String,
    pub center: String,
    pub right: String,
    pub source_walk_sha256: String,
    pub source_cigar: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Compatibility {
    pub mode: String,
    pub distances: BTreeMap<String, usize>,
    pub bonuses: BTreeMap<String, f64>,
    pub left_best: BTreeSet<String>,
    pub right_best: BTreeSet<String>,
}

pub fn edit(a: &str, b: &str) -> usize {
    let mut row: Vec<usize> = (0..=b.len()).collect();
    for (i, x) in a.bytes().enumerate() {
        let mut previous = row[0];
        row[0] = i + 1;
        for (j, y) in b.bytes().enumerate() {
            let old = row[j + 1];
            row[j + 1] = (row[j] + 1)
                .min(old + 1)
                .min(previous + usize::from(x != y));
            previous = old;
        }
    }
    row[b.len()]
}
pub fn bonus(delta: usize) -> f64 {
    if delta == 0 {
        1.0
    } else {
        ((std::f64::consts::E - 1.0) * (-(3.0_f64.ln()) * delta as f64).exp()).ln_1p()
    }
}
pub fn compatibility(e: &FlankEvidence, prototypes: &[WalkPrototype]) -> Result<Compatibility> {
    ensure!(prototypes.len() <= 256, "prototype cap");
    ensure!(
        [&e.left, &e.right]
            .iter()
            .all(|s| !s.is_empty() && s.len() <= 64 && s.bytes().all(|b| b"ACGT".contains(&b))),
        "invalid native flank"
    );
    let mut distances = BTreeMap::<String, usize>::new();
    let mut left = BTreeMap::<String, usize>::new();
    let mut right = BTreeMap::<String, usize>::new();
    for p in prototypes {
        ensure!(
            [&p.left, &p.right]
                .iter()
                .all(|s| !s.is_empty() && s.len() <= 64 && s.bytes().all(|b| b"ACGT".contains(&b))),
            "invalid graph flank"
        );
        let l = edit(&e.left, &p.left);
        let r = edit(&e.right, &p.right);
        for (map, d) in [(&mut distances, l + r), (&mut left, l), (&mut right, r)] {
            map.entry(p.center.clone())
                .and_modify(|old| *old = (*old).min(d))
                .or_insert(d);
        }
    }
    let best = |map: &BTreeMap<String, usize>| -> BTreeSet<String> {
        let m = map.values().min();
        map.iter()
            .filter(|(_, d)| Some(*d) == m)
            .map(|(h, _)| h.clone())
            .collect()
    };
    let left_best = best(&left);
    let right_best = best(&right);
    let abstain = !distances.is_empty() && left_best.is_disjoint(&right_best);
    let min = distances.values().copied().min().unwrap_or(0);
    let bonuses = distances
        .iter()
        .map(|(h, d)| (h.clone(), if abstain { 1.0 } else { bonus(d - min) }))
        .collect();
    Ok(Compatibility {
        mode: if distances.is_empty() {
            "empty-neutral"
        } else if abstain {
            "left-right-disagreement-binary"
        } else {
            "conditioned"
        }
        .into(),
        distances,
        bonuses,
        left_best,
        right_best,
    })
}

pub fn cigar(text: &str) -> Result<Vec<(usize, u8)>> {
    let mut out = Vec::new();
    let mut n = 0usize;
    for b in text.bytes() {
        if b.is_ascii_digit() {
            n = n
                .checked_mul(10)
                .and_then(|x| x.checked_add((b - b'0') as usize))
                .context("CIGAR overflow")?;
        } else {
            ensure!(n > 0 && b"MIDNSHP=X".contains(&b), "invalid CIGAR");
            out.push((n, b));
            n = 0;
        }
    }
    ensure!(n == 0 && !out.is_empty(), "unfinished CIGAR");
    Ok(out)
}

pub fn extract(
    sequence: &str,
    text: &str,
    reference_start: usize,
    span: &Span,
) -> Result<(String, Span)> {
    ensure!(
        sequence.is_ascii() && span.start < span.end,
        "invalid extraction input"
    );
    let mut r = reference_start;
    let mut q = 0usize;
    let mut start = None;
    let mut end = None;
    for (n, op) in cigar(text)? {
        ensure!(n <= 10_000_000, "CIGAR operation cap");
        match op {
            b'M' | b'=' | b'X' => {
                for _ in 0..n {
                    if r == span.start {
                        start = Some(q);
                    }
                    if r == span.end - 1 {
                        end = Some(q + 1);
                    }
                    r += 1;
                    q += 1;
                }
            }
            b'I' => {
                ensure!(r != span.start && r != span.end, "boundary insertion");
                q += n;
            }
            b'D' | b'N' => {
                ensure!(
                    op != b'N'
                        || !(Span {
                            start: r,
                            end: r + n
                        })
                        .overlaps(span),
                    "reference skip"
                );
                ensure!(
                    !(r <= span.start && span.start < r + n || r < span.end && span.end <= r + n),
                    "boundary deletion"
                );
                r += n;
            }
            b'S' => q += n,
            b'H' => anyhow::bail!("hard clipping"),
            b'P' => {}
            _ => anyhow::bail!("unsupported CIGAR"),
        }
        ensure!(q <= sequence.len(), "CIGAR/sequence overrun");
    }
    ensure!(q == sequence.len(), "CIGAR/sequence length mismatch");
    let a = start.context("uncovered left boundary")?;
    let b = end.context("uncovered right boundary")?;
    let s = sequence.get(a..b).context("extraction slice")?;
    ensure!(
        s.bytes().all(|x| b"ACGT".contains(&x)),
        "noncanonical extraction"
    );
    Ok((s.into(), Span { start: a, end: b }))
}
pub fn revcomp(s: &str) -> Result<String> {
    s.bytes()
        .rev()
        .map(|b| {
            Ok(match b {
                b'A' => 'T',
                b'C' => 'G',
                b'G' => 'C',
                b'T' => 'A',
                _ => anyhow::bail!("noncanonical reverse complement"),
            })
        })
        .collect()
}

#[derive(Clone, Debug)]
pub struct Hypothesis {
    pub sequence: String,
    pub likelihood: f64,
}
#[derive(Clone, Debug, Serialize)]
pub struct Decision {
    pub winner: String,
    pub winner_likelihood: f64,
    pub bonus: f64,
    pub objective_margin: f64,
    pub neural_delta: f64,
    pub edited: bool,
    pub gate: String,
}
pub fn choose(stock: &str, h: &[Hypothesis], bonuses: &BTreeMap<String, f64>) -> Result<Decision> {
    let native = h
        .iter()
        .find(|h| h.sequence == stock)
        .context("native absent")?;
    ensure!(native.likelihood.is_finite(), "native score nonfinite");
    let objective =
        |h: &Hypothesis| h.likelihood + bonuses.get(&h.sequence).copied().unwrap_or(0.0);
    let mut winner = native;
    for x in h {
        ensure!(
            x.likelihood.is_finite() || x.likelihood == f64::NEG_INFINITY,
            "invalid likelihood"
        );
        if objective(x) > objective(winner)
            || (objective(x) == objective(winner)
                && winner.sequence != stock
                && x.sequence < winner.sequence)
        {
            winner = x;
        }
    }
    let margin = objective(winner) - objective(native);
    let delta = winner.likelihood - native.likelihood;
    let gate = if winner.sequence == stock {
        "native"
    } else if margin < 0.5 {
        "objective_margin"
    } else if delta < -0.5 {
        "neural_deficit"
    } else {
        "edit"
    };
    Ok(Decision {
        winner: winner.sequence.clone(),
        winner_likelihood: winner.likelihood,
        bonus: bonuses.get(&winner.sequence).copied().unwrap_or(0.0),
        objective_margin: margin,
        neural_delta: delta,
        edited: gate == "edit",
        gate: gate.into(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn evidence(l: &str, r: &str) -> FlankEvidence {
        FlankEvidence {
            left: l.into(),
            right: r.into(),
            reference_intervals: [Span { start: 0, end: 1 }, Span { start: 2, end: 3 }],
            read_intervals: [Span { start: 0, end: 1 }, Span { start: 2, end: 3 }],
            mapped_sam_sha256: "x".into(),
            window_sha256: "x".into(),
        }
    }
    fn proto(l: &str, c: &str, r: &str) -> WalkPrototype {
        WalkPrototype {
            left: l.into(),
            center: c.into(),
            right: r.into(),
            source_walk_sha256: "hash".into(),
            source_cigar: "1M".into(),
        }
    }
    #[test]
    fn linkage_swap_duplicates_and_order() -> Result<()> {
        let p = vec![proto("AAAA", "A", "AAAA"), proto("CCCC", "C", "CCCC")];
        let a = compatibility(&evidence("AAAA", "AAAA"), &p)?;
        let b = compatibility(&evidence("CCCC", "CCCC"), &p)?;
        assert!(a.bonuses["A"] > a.bonuses["C"]);
        assert!(b.bonuses["C"] > b.bonuses["A"]);
        let mut duplicate = p.clone();
        duplicate.reverse();
        duplicate.extend(p);
        assert_eq!(
            a.bonuses,
            compatibility(&evidence("AAAA", "AAAA"), &duplicate)?.bonuses
        );
        Ok(())
    }
    #[test]
    fn disagreement_and_equal_are_exact_binary() -> Result<()> {
        let p = vec![proto("A", "A", "A"), proto("C", "C", "C")];
        let x = compatibility(&evidence("A", "C"), &p)?;
        assert_eq!(x.mode, "left-right-disagreement-binary");
        assert!(x.bonuses.values().all(|x| *x == 1.0));
        let y = compatibility(&evidence("G", "G"), &p)?;
        assert!(y.bonuses.values().all(|x| *x == 1.0));
        Ok(())
    }
    #[test]
    fn indel_boundary_and_interior() -> Result<()> {
        let s = Span { start: 1, end: 4 };
        assert_eq!(extract("AACGTT", "2M1I3M", 0, &s)?.0, "ACGT");
        assert!(extract("AACGTT", "1M1I4M", 0, &s).is_err());
        assert!(extract("AACGTT", "4M1I1M", 0, &s).is_err());
        assert_eq!(
            extract("ACGT", "2M1D2M", 0, &Span { start: 1, end: 4 })?.0,
            "CG"
        );
        assert!(extract("ACGT", "1M1D3M", 0, &s).is_err());
        Ok(())
    }
    #[test]
    fn private_override_and_erasure_counterexample() -> Result<()> {
        for delta in [1.01, 0.25] {
            let h = vec![
                Hypothesis {
                    sequence: "T".into(),
                    likelihood: 0.0,
                },
                Hypothesis {
                    sequence: "A".into(),
                    likelihood: -delta,
                },
            ];
            let d = choose("T", &h, &BTreeMap::from([("A".into(), 1.0)]))?;
            assert_eq!(d.edited, delta == 0.25);
        }
        Ok(())
    }
    #[test]
    fn bounded_bonus_and_impossible() -> Result<()> {
        for i in 0..10000 {
            assert!((0.0..=1.0).contains(&bonus(i)));
        }
        assert_eq!(bonus(0), 1.0);
        let d = choose(
            "A",
            &[
                Hypothesis {
                    sequence: "A".into(),
                    likelihood: 0.0,
                },
                Hypothesis {
                    sequence: "C".into(),
                    likelihood: f64::NEG_INFINITY,
                },
            ],
            &BTreeMap::from([("C".into(), 1.0)]),
        )?;
        assert_eq!(d.winner, "A");
        Ok(())
    }
    #[test]
    fn evidence_rejects_center_fields() {
        let mut v = serde_json::to_value(evidence("A", "C")).expect("fixture");
        v["central_score"] = 0.into();
        assert!(serde_json::from_value::<FlankEvidence>(v).is_err());
    }
    #[test]
    fn reverse_coordinates() -> Result<()> {
        assert_eq!(revcomp("AACG")?, "CGTT");
        let span = Span { start: 2, end: 4 };
        let len = 9;
        assert_eq!((len - span.end, len - span.start), (5, 7));
        Ok(())
    }
    #[test]
    fn equal_flank_original_panel_parity_and_ties() -> Result<()> {
        let p = vec![proto("A", "A", "A"), proto("C", "C", "C")];
        let conditioned = compatibility(&evidence("G", "G"), &p)?.bonuses;
        let binary = BTreeMap::from([("A".into(), 1.0), ("C".into(), 1.0)]);
        for native in ["A", "C", "T"] {
            for la in -5..=5 {
                for lc in -5..=5 {
                    let h = vec![
                        Hypothesis {
                            sequence: "A".into(),
                            likelihood: la as f64 / 4.0,
                        },
                        Hypothesis {
                            sequence: "C".into(),
                            likelihood: lc as f64 / 4.0,
                        },
                        Hypothesis {
                            sequence: "T".into(),
                            likelihood: 0.0,
                        },
                    ];
                    let a = choose(native, &h, &conditioned)?;
                    let b = choose(native, &h, &binary)?;
                    assert_eq!(serde_json::to_value(a)?, serde_json::to_value(b)?);
                }
            }
        }
        Ok(())
    }
    #[test]
    fn masked_center_and_copy_count_are_unreadable() -> Result<()> {
        let first: serde_json::Value =
            serde_json::from_str(r#"{"left":"A","right":"C","center":"AAAA","copy_count":1}"#)?;
        let second: serde_json::Value =
            serde_json::from_str(r#"{"left":"A","right":"C","center":"TTTT","copy_count":999}"#)?;
        let p = [proto("A", "A", "C"), proto("T", "C", "T")];
        let score = |v: &serde_json::Value| -> Result<Compatibility> {
            compatibility(
                &evidence(
                    v["left"].as_str().context("left")?,
                    v["right"].as_str().context("right")?,
                ),
                &p,
            )
        };
        assert_eq!(score(&first)?.bonuses, score(&second)?.bonuses);
        Ok(())
    }
}
