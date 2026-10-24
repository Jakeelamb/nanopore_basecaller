use anyhow::{ensure, Context, Result};
use std::{
    fs::File,
    io::{BufRead, BufReader, Read},
    path::Path,
};

#[derive(Clone, Debug)]
pub struct Header {
    pub t: usize,
    pub c: usize,
    pub blank: f64,
    pub clamp: f64,
    pub token: String,
    pub slot: usize,
    pub offset: usize,
}
#[derive(Debug)]
pub struct Scores {
    pub header: Header,
    pub values: Vec<f64>,
}
fn finite(s: &str) -> Result<f64> {
    let x = s.parse::<f64>()?;
    ensure!(x.is_finite(), "nonfinite decoder option");
    Ok(x)
}
pub fn parse_header(line: &str) -> Result<Header> {
    ensure!(
        line.ends_with('\n') && !line.contains('\r'),
        "header LF required"
    );
    let f: Vec<_> = line.trim_end_matches('\n').split('\t').collect();
    ensure!(f.len() == 15 && f[0] == "DGS1", "DGS1 header fields");
    let t = f[1].parse::<usize>()?;
    let c = f[2].parse::<usize>()?;
    ensure!(
        t > 0 && t <= 1_000_000 && c == 1024 && f[3] == "4" && f[4] == "6",
        "HAC k4/C1024/stride6 only"
    );
    let blank = finite(f[5])?;
    ensure!(f[6].parse::<usize>()? > 0, "invalid beam width");
    ensure!(finite(f[7])? > 0.0, "invalid beam cut");
    finite(f[8])?;
    finite(f[9])?;
    ensure!(matches!(f[10], "0" | "1"), "move_pad must be boolean");
    let clamp = finite(f[11])?;
    ensure!(clamp == 0.0 || clamp == 5.0, "unsupported clamp");
    let offset = f[12].parse()?;
    let token = f[13];
    let (pid, batch) = token
        .strip_prefix('p')
        .and_then(|s| s.split_once("_b"))
        .context("invalid score token")?;
    ensure!(
        !pid.is_empty()
            && !batch.is_empty()
            && pid.bytes().chain(batch.bytes()).all(|b| b.is_ascii_digit()),
        "invalid score token"
    );
    let slot = f[14].parse()?;
    Ok(Header {
        t,
        c,
        blank,
        clamp,
        token: token.to_owned(),
        slot,
        offset,
    })
}
pub fn header(path: &Path) -> Result<Header> {
    let mut r = BufReader::new(File::open(path)?);
    let mut l = String::new();
    r.by_ref().take(4096).read_line(&mut l)?;
    let h = parse_header(&l)?;
    let expected = (l.len() as u64)
        .checked_add((h.t * h.c * 2) as u64)
        .context("score size overflow")?;
    ensure!(
        r.get_ref().metadata()?.len() == expected,
        "score payload length mismatch"
    );
    ensure!(
        path.file_name().and_then(|x| x.to_str())
            == Some(format!("{}_s{}.scores", h.token, h.slot).as_str()),
        "score filename/token mismatch"
    );
    Ok(h)
}
pub fn half(bits: u16) -> f64 {
    let sign = if bits & 0x8000 == 0 { 1.0 } else { -1.0 };
    let e = ((bits >> 10) & 31) as i32;
    let f = (bits & 1023) as f64;
    match e {
        0 => sign * f * 2f64.powi(-24),
        31 => {
            if f == 0.0 {
                sign * f64::INFINITY
            } else {
                f64::NAN
            }
        }
        _ => sign * (1.0 + f / 1024.0) * 2f64.powi(e - 15),
    }
}
pub fn load(path: &Path) -> Result<Scores> {
    let h = header(path)?;
    let mut r = BufReader::new(File::open(path)?);
    let mut line = String::new();
    r.read_line(&mut line)?;
    let mut bytes = Vec::new();
    r.read_to_end(&mut bytes)?;
    let mut values = Vec::with_capacity(h.t * h.c);
    for p in bytes.chunks_exact(2) {
        let v = half(u16::from_le_bytes([p[0], p[1]]));
        ensure!(v.is_finite(), "nonfinite score payload");
        values.push(if h.clamp == 0.0 {
            v
        } else {
            v.clamp(-h.clamp, h.clamp)
        });
    }
    Ok(Scores { header: h, values })
}
