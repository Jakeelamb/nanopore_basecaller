pub mod contract;
#[allow(dead_code)]
#[path = "../vendor/crf.rs"]
pub mod crf;
pub mod input;
#[allow(dead_code)]
#[allow(
    clippy::chunks_exact_to_as_chunks,
    reason = "Preserve unchanged original vendor source fidelity."
)]
#[path = "../vendor/scores.rs"]
pub mod scores;
pub mod identity {
    include!(concat!(env!("OUT_DIR"), "/identity.rs"));
}

use anyhow::{ensure, Result};
use contract::{Query, QueryScore, Scalar, StateScore};
use sha2::{Digest, Sha256};
use std::{fs, path::Path};

pub fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn verify_sources() -> Result<()> {
    for (path, sha256) in identity::SOURCE_PINS {
        ensure!(
            digest(&fs::read(Path::new(env!("CARGO_MANIFEST_DIR")).join(path))?) == *sha256,
            "compiled source differs: {path}"
        );
    }
    Ok(())
}

pub fn scalar(value: f64) -> Result<Scalar> {
    if value == f64::NEG_INFINITY {
        Ok(Scalar::Impossible)
    } else {
        ensure!(value.is_finite(), "unexpected nonfinite scalar");
        Ok(Scalar::Finite {
            decimal: format!("{value:.17e}"),
            bits: format!("{:016x}", value.to_bits()),
        })
    }
}

pub fn uniform(
    values: &[f64],
    rows: usize,
    blank: f64,
    sequence: &[u8],
) -> Result<(f64, Vec<f64>)> {
    ensure!(
        rows <= 2048 && sequence.len() <= 512 && sequence.iter().all(|b| b"ACGT".contains(b)),
        "scalar input bound"
    );
    let per_state: Vec<f64> = (0..256)
        .map(|initial| crf::ScoreWindow::new(values, rows, 4, initial, blank)?.likelihood(sequence))
        .collect::<Result<_>>()?;
    let maximum = per_state.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let value = if maximum == f64::NEG_INFINITY {
        f64::NEG_INFINITY
    } else {
        maximum
            + per_state
                .iter()
                .map(|value| (value - maximum).exp())
                .sum::<f64>()
                .ln()
            - 256f64.ln()
    };
    scalar(value)?;
    Ok((value, per_state))
}

pub fn score(consumed: &input::Consumed, queries: &[Query]) -> Result<Vec<QueryScore>> {
    queries
        .iter()
        .map(|query| {
            let (value, states) = uniform(
                &consumed.values,
                consumed.rows,
                consumed.blank,
                query.sequence.as_bytes(),
            )?;
            let per_initial_state = states
                .into_iter()
                .enumerate()
                .map(|(initial_state, value)| {
                    Ok(StateScore {
                        initial_state,
                        score: scalar(value)?,
                    })
                })
                .collect::<Result<_>>()?;
            Ok(QueryScore {
                id: query.id.clone(),
                sequence: query.sequence.clone(),
                sequence_sha256: digest(query.sequence.as_bytes()),
                score: scalar(value)?,
                per_initial_state,
            })
        })
        .collect()
}
