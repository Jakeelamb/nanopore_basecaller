use std::io::{self, BufRead, Write};

fn classify(reference: &[u8], query: &[u8], start: usize, end: usize, alt: &[u8]) -> &'static str {
    assert!(start < end && end <= reference.len());
    if !query.windows(alt.len()).any(|x| x == alt) { return "other"; }
    let n = query.len();
    let m = reference.len();
    let width = n + 1;
    let mut prefix = vec![0u16; (m + 1) * width];
    let mut suffix = prefix.clone();
    for i in 0..=m { prefix[i * width] = i as u16; suffix[i * width + n] = (m - i) as u16; }
    for j in 0..=n { prefix[j] = j as u16; suffix[m * width + j] = (n - j) as u16; }
    for i in 1..=m { for j in 1..=n {
        prefix[i * width + j] = (prefix[(i - 1) * width + j] + 1)
            .min(prefix[i * width + j - 1] + 1)
            .min(prefix[(i - 1) * width + j - 1] + u16::from(reference[i - 1] != query[j - 1]));
    }}
    for i in (0..m).rev() { for j in (0..n).rev() {
        suffix[i * width + j] = (suffix[(i + 1) * width + j] + 1)
            .min(suffix[i * width + j + 1] + 1)
            .min(suffix[(i + 1) * width + j + 1] + u16::from(reference[i] != query[j]));
    }}
    let cost = prefix[m * width + n];
    let cuts = |i: usize| (0..=n).filter(|&j| prefix[i * width + j] + suffix[i * width + j] == cost).collect::<Vec<_>>();
    let left = cuts(start);
    let right = cuts(end);
    if left.len() != 1 || right.len() != 1 { return "ambiguous"; }
    assert!(left[0] <= right[0]);
    if &query[left[0]..right[0]] == alt { "alt" } else { "other" }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let stdin = io::stdin();
    let mut output = io::BufWriter::new(io::stdout());
    for line in stdin.lock().lines() {
        let line = line?;
        let f = line.split('\t').collect::<Vec<_>>();
        assert_eq!(f.len(), 5);
        assert!(!f[3].is_empty() && f.iter().all(|s| s.len() < 4096));
        writeln!(output, "{}", classify(f[0].as_bytes(), f[4].as_bytes(), f[1].parse()?, f[2].parse()?, f[3].as_bytes()))?;
    }
    Ok(())
}
