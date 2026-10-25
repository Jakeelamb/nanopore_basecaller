use anyhow::{ensure, Context, Result};
use std::collections::{BTreeMap, BTreeSet};

pub fn base(b: u8) -> Result<usize> {
    b"ACGT"
        .iter()
        .position(|&x| x == b)
        .context("noncanonical sequence")
}
pub fn state(seq: &[u8], k: usize) -> Result<usize> {
    ensure!(
        seq.len() >= k && (1..=8).contains(&k),
        "insufficient kmer context"
    );
    seq[seq.len() - k..]
        .iter()
        .try_fold(0, |s, &b| Ok((s << 2) | base(b)?))
}
pub fn transition(old: usize, b: u8, k: usize) -> Result<(usize, usize)> {
    ensure!(
        (1..=8).contains(&k) && old < (1usize << (2 * k)),
        "invalid CRF state"
    );
    let new = ((old << 2) & ((1 << (2 * k)) - 1)) | base(b)?;
    Ok((new, 4 * new + (old >> (2 * (k - 1)))))
}
fn add(a: f64, b: f64) -> f64 {
    if a == f64::NEG_INFINITY {
        b
    } else if b == f64::NEG_INFINITY {
        a
    } else {
        let m = a.max(b);
        m + ((a - m).exp() + (b - m).exp()).ln()
    }
}
/// Exact sum over all stay/step paths emitting y, with fixed initial state.
pub fn likelihood(
    scores: &[f64],
    t: usize,
    k: usize,
    initial: usize,
    y: &[u8],
    blank: f64,
) -> Result<f64> {
    ScoreWindow::new(scores, t, k, initial, blank)?.likelihood(y)
}

/// Validates a shared score interval once, then scores every hypothesis over it.
pub struct ScoreWindow<'a> {
    scores: &'a [f64],
    c: usize,
    k: usize,
    initial: usize,
    blank: f64,
}
impl<'a> ScoreWindow<'a> {
    pub fn new(scores: &'a [f64], t: usize, k: usize, initial: usize, blank: f64) -> Result<Self> {
        ensure!((1..=8).contains(&k), "invalid k");
        let c = 1usize << (2 * (k + 1));
        ensure!(
            t.checked_mul(c) == Some(scores.len())
                && blank.is_finite()
                && initial < (1usize << (2 * k))
                && scores.iter().all(|v| v.is_finite()),
            "invalid score slice/state"
        );
        Ok(Self {
            scores,
            c,
            k,
            initial,
            blank,
        })
    }
    pub fn likelihood(&self, y: &[u8]) -> Result<f64> {
        let mut indices = Vec::with_capacity(y.len());
        let mut s = self.initial;
        for &b in y {
            let (n, i) = transition(s, b, self.k)?;
            indices.push(i);
            s = n;
        }
        let mut dp = vec![f64::NEG_INFINITY; y.len() + 1];
        dp[0] = 0.0;
        for row in self.scores.chunks_exact(self.c) {
            for j in (1..=y.len()).rev() {
                dp[j] = add(dp[j] + self.blank, dp[j - 1] + row[indices[j - 1]]);
            }
            dp[0] += self.blank;
        }
        Ok(dp[y.len()])
    }
}
/// Presence-only panel; all single-base escapes mutate only the stock core.
pub fn hypotheses(stock: &str, panel: &BTreeSet<String>) -> Result<BTreeMap<String, bool>> {
    ensure!(
        stock.is_ascii() && stock.len() >= 20 && stock.bytes().all(|b| b"ACGT".contains(&b)),
        "invalid stock"
    );
    let core = &stock.as_bytes()[10..stock.len() - 10];
    ensure!(core.len() <= 32 && panel.len() <= 16, "hypothesis bounds");
    let mut h = BTreeMap::new();
    h.insert(stock.to_owned(), panel.contains(stock));
    for s in panel {
        h.insert(s.clone(), true);
    }
    let mut put = |c: Vec<u8>| -> Result<()> {
        let mut s = stock.as_bytes()[..10].to_vec();
        s.extend(c);
        s.extend(&stock.as_bytes()[stock.len() - 10..]);
        h.entry(String::from_utf8(s)?).or_insert(false);
        Ok(())
    };
    for i in 0..core.len() {
        for b in b"ACGT" {
            if *b != core[i] {
                let mut c = core.to_vec();
                c[i] = *b;
                put(c)?;
            }
        }
        let mut c = core.to_vec();
        c.remove(i);
        put(c)?;
    }
    for i in 0..=core.len() {
        for b in b"ACGT" {
            let mut c = core.to_vec();
            c.insert(i, *b);
            put(c)?;
        }
    }
    ensure!(h.len() <= 277, "hypothesis count cap");
    Ok(h)
}
pub fn choose<'a>(
    stock: &str,
    h: &'a [(String, bool, f64)],
    lambda: f64,
) -> Result<(&'a str, bool, f64)> {
    let (_, g, l) = h.iter().find(|x| x.0 == stock).context("stock absent")?;
    let stock_j = *l + lambda * usize::from(*g) as f64;
    let mut winner = h.iter().find(|x| x.0 == stock).context("stock absent")?;
    for candidate in h {
        let j = candidate.2 + lambda * usize::from(candidate.1) as f64;
        let w = winner.2 + lambda * usize::from(winner.1) as f64;
        if j > w || (j == w && winner.0 != stock && candidate.0 < winner.0) {
            winner = candidate;
        }
    }
    let margin = winner.2 + lambda * usize::from(winner.1) as f64 - stock_j;
    let edit = winner.0 != stock && margin >= 0.5 && winner.2 >= *l;
    Ok((winner.0.as_str(), edit, margin))
}
