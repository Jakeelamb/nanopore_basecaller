use anyhow::{ensure, Result};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Prior {
    None,
    Linear,
    Panel,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Policy {
    pub id: String,
    pub prior: Prior,
    pub lambda: f64,
    pub neural_deficit: Option<f64>,
    pub margin: f64,
}

impl Policy {
    pub fn validate(&self) -> Result<()> {
        ensure!(
            !self.id.is_empty() && self.id.len() <= 200,
            "invalid policy ID"
        );
        for x in [Some(self.lambda), self.neural_deficit, Some(self.margin)]
            .into_iter()
            .flatten()
        {
            ensure!(
                x.is_finite() && x >= 0.0,
                "policy weights must be finite and nonnegative"
            );
        }
        Ok(())
    }
}

#[derive(Clone, Debug)]
pub struct Hypothesis {
    pub sequence: String,
    pub panel: bool,
    pub linear: bool,
    pub likelihood: f64,
}

impl Hypothesis {
    fn presence(&self, prior: Prior) -> f64 {
        f64::from(match prior {
            Prior::None => false,
            Prior::Linear => self.linear,
            Prior::Panel => self.panel,
        })
    }
    fn objective(&self, policy: &Policy) -> f64 {
        self.likelihood + policy.lambda * self.presence(policy.prior)
    }
}

#[derive(Debug, Serialize)]
pub struct Decision {
    pub winner: String,
    pub winner_likelihood: f64,
    pub winner_graph_presence: bool,
    pub objective_margin: f64,
    pub neural_delta: f64,
    pub edited: bool,
    pub gate: &'static str,
    pub masked_feasible: usize,
    pub native_exact_ties: usize,
}

pub fn choose(stock: &str, hypotheses: &[Hypothesis], policy: &Policy) -> Result<Decision> {
    policy.validate()?;
    let native = hypotheses
        .iter()
        .find(|h| h.sequence == stock)
        .ok_or_else(|| anyhow::anyhow!("native hypothesis absent"))?;
    ensure!(
        native.likelihood.is_finite(),
        "native likelihood must be finite"
    );
    let mut winner = native;
    for h in hypotheses {
        ensure!(
            h.likelihood.is_finite() || h.likelihood == f64::NEG_INFINITY,
            "invalid hypothesis likelihood"
        );
        let objective = h.objective(policy);
        ensure!(
            objective.is_finite() || objective == f64::NEG_INFINITY,
            "objective overflow"
        );
        let current = winner.objective(policy);
        if objective > current
            || (objective == current && winner.sequence != stock && h.sequence < winner.sequence)
        {
            winner = h;
        }
    }
    let margin = winner.objective(policy) - native.objective(policy);
    let delta = winner.likelihood - native.likelihood;
    ensure!(
        margin.is_finite() && delta.is_finite(),
        "decision delta overflow"
    );
    let gate = if winner.sequence == stock {
        "native"
    } else if margin < policy.margin {
        "objective_margin"
    } else if policy.neural_deficit.is_some_and(|d| delta < -d) {
        "neural_deficit"
    } else {
        "edit"
    };
    let masked = if gate == "edit" {
        0
    } else {
        hypotheses
            .iter()
            .filter(|h| {
                h.sequence != stock
                    && h.sequence != winner.sequence
                    && h.likelihood.is_finite()
                    && h.objective(policy) - native.objective(policy) >= policy.margin
                    && policy
                        .neural_deficit
                        .is_none_or(|d| h.likelihood - native.likelihood >= -d)
            })
            .count()
    };
    Ok(Decision {
        winner: winner.sequence.clone(),
        winner_likelihood: winner.likelihood,
        winner_graph_presence: winner.panel,
        objective_margin: margin,
        neural_delta: delta,
        edited: gate == "edit",
        gate,
        masked_feasible: masked,
        native_exact_ties: hypotheses
            .iter()
            .filter(|h| h.sequence != stock && h.objective(policy) == native.objective(policy))
            .count(),
    })
}

pub fn events(
    stock: &str,
    hypotheses: &[Hypothesis],
    prior: Prior,
    margin: f64,
) -> Result<Vec<f64>> {
    let native = hypotheses
        .iter()
        .find(|h| h.sequence == stock)
        .ok_or_else(|| anyhow::anyhow!("native absent"))?;
    let mut maxima = [f64::NEG_INFINITY; 2];
    for h in hypotheses.iter().filter(|h| h.likelihood.is_finite()) {
        let class = usize::from(h.presence(prior) == 1.0);
        maxima[class] = maxima[class].max(h.likelihood);
    }
    let mut points = vec![0.0];
    if maxima.iter().all(|x| x.is_finite()) {
        points.push(maxima[0] - maxima[1]);
    }
    for (class, score) in maxima
        .into_iter()
        .enumerate()
        .filter(|(_, l)| l.is_finite())
    {
        let slope = class as f64 - native.presence(prior);
        if slope != 0.0 {
            points.push((native.likelihood + margin - score) / slope);
        }
    }
    ensure!(
        points.iter().all(|x| x.is_finite()),
        "frontier event overflow"
    );
    points.retain(|x| *x >= 0.0);
    points.sort_by(f64::total_cmp);
    points.dedup_by(|a, b| *a == *b);
    Ok(points)
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct TerminalDecision {
    pub winner: String,
    pub edited: bool,
}

pub fn symbolic_terminal(
    stock: &str,
    hypotheses: &[Hypothesis],
    policy: &Policy,
) -> Result<TerminalDecision> {
    policy.validate()?;
    let native = hypotheses
        .iter()
        .find(|h| h.sequence == stock)
        .ok_or_else(|| anyhow::anyhow!("native absent"))?;
    ensure!(native.likelihood.is_finite(), "native must be finite");
    let mut winner = native;
    for h in hypotheses.iter().filter(|h| h.likelihood.is_finite()) {
        let prior = h.presence(policy.prior);
        let current_prior = winner.presence(policy.prior);
        if prior > current_prior
            || (prior == current_prior
                && (h.likelihood > winner.likelihood
                    || (h.likelihood == winner.likelihood
                        && winner.sequence != stock
                        && h.sequence < winner.sequence)))
        {
            winner = h;
        }
    }
    let slope = winner.presence(policy.prior) - native.presence(policy.prior);
    let neural_delta = winner.likelihood - native.likelihood;
    let clears_margin = slope > 0.0 || (slope == 0.0 && neural_delta >= policy.margin);
    Ok(TerminalDecision {
        winner: winner.sequence.clone(),
        edited: winner.sequence != stock
            && clears_margin
            && policy.neural_deficit.is_none_or(|d| neural_delta >= -d),
    })
}

pub fn representatives(points: &[f64]) -> Result<Vec<(f64, &'static str)>> {
    let mut out = Vec::new();
    for (i, &point) in points.iter().enumerate() {
        out.push((point, "boundary"));
        if let Some(&next) = points.get(i + 1) {
            let midpoint = point + (next - point) / 2.0;
            if point < midpoint && midpoint < next {
                out.push((midpoint, "interval"));
            } else {
                ensure!(point.next_up() == next, "unrepresentable frontier interval");
            }
        }
    }
    let last = *points
        .last()
        .ok_or_else(|| anyhow::anyhow!("empty frontier"))?;
    let terminal = last + last.abs().max(1.0);
    ensure!(
        terminal.is_finite() && terminal > last,
        "terminal frontier interval has no finite representative"
    );
    out.push((terminal, "terminal"));
    Ok(out)
}
