use anyhow::{ensure, Context, Result};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::{BufRead, BufReader},
    path::Path,
};
mod attach;
mod challenge;
#[path = "../../graph_frontier/src/decision.rs"]
#[allow(dead_code)]
mod decision;
#[allow(dead_code)]
mod flank_snapshot;

#[derive(Debug, Deserialize)]
struct Window {
    query_index: usize,
    read_id: String,
    contig: String,
    core_start: usize,
    core_end: usize,
    ref_start: usize,
    ref_end: usize,
    stock: String,
    reverse: bool,
}
#[derive(Debug)]
struct Variant {
    id: String,
    contig: String,
    pos: usize,
    rf: String,
    alt: String,
    kind: String,
    start: usize,
    end: usize,
    alt_hap: String,
}
fn table(path: &Path) -> Result<Vec<Vec<String>>> {
    BufReader::new(File::open(path)?)
        .lines()
        .skip(1)
        .map(|s| Ok(s?.split('\t').map(String::from).collect()))
        .collect()
}
fn load_jsonl<T: serde::de::DeserializeOwned>(path: &Path) -> Result<Vec<T>> {
    BufReader::new(File::open(path)?)
        .lines()
        .map(|s| Ok(serde_json::from_str(&s?)?))
        .collect()
}
fn event(v: &Variant) -> (usize, usize) {
    let (r, a) = (v.rf.as_bytes(), v.alt.as_bytes());
    let mut left = 0;
    while left < r.len().min(a.len()) && r[left] == a[left] {
        left += 1;
    }
    let mut right = 0;
    while right < (r.len() - left).min(a.len() - left)
        && r[r.len() - 1 - right] == a[a.len() - 1 - right]
    {
        right += 1;
    }
    (v.pos + left, v.pos + r.len() - right)
}
fn overlaps(v: &Variant, w: &Window) -> bool {
    if v.contig != w.contig {
        return false;
    }
    let (s, e) = event(v);
    if s == e {
        w.core_start <= s && s < w.core_end
    } else {
        s < w.core_end && w.core_start < e
    }
}
fn main() -> Result<()> {
    let args: Vec<_> = std::env::args().collect();
    if args.get(1).is_some_and(|s| s == "additional") {
        ensure!(args.len() == 4, "additional REFERENCE_WORKTREE OUTPUT");
        let root = Path::new(&args[2]);
        let out = Path::new(&args[3]);
        fs::create_dir(out)?;
        let observer = root.join("results/graph-prior/pilot-v1/development/alleles/native");
        let variants: Vec<Variant> = table(&observer.join("variants.tsv"))?
            .into_iter()
            .map(|f| {
                Ok(Variant {
                    id: f[0].clone(),
                    contig: f[1].clone(),
                    pos: f[2].parse()?,
                    rf: f[3].clone(),
                    alt: f[4].clone(),
                    start: f[6].parse()?,
                    end: f[7].parse()?,
                    kind: f[8].clone(),
                    alt_hap: f[10].clone(),
                })
            })
            .collect::<Result<_>>()?;
        let observations: BTreeMap<_, _> = table(&observer.join("observations.tsv"))?
            .into_iter()
            .map(|f| ((f[0].clone(), f[1].clone()), f[2].clone()))
            .collect();
        let windows=load_jsonl::<Window>(Path::new("/home/jake/Projects/nanopore_basecaller-private/results/private-allele/actual-v3-attachment/output/additional-attached-windows.jsonl"))?;
        return challenge::build(root, out, &windows, &variants, &observations, true);
    }
    if args.get(1).is_some_and(|s| s == "infer") {
        ensure!(args.len() == 4, "infer INPUT OUTPUT");
        return challenge::infer(Path::new(&args[2]), Path::new(&args[3]));
    }
    if args.get(1).is_some_and(|s| s == "report") {
        ensure!(args.len() == 5, "report CASES DECISIONS OUTPUT");
        return challenge::report(
            Path::new(&args[2]),
            Path::new(&args[3]),
            Path::new(&args[4]),
        );
    }
    ensure!(
        args.len() == 3,
        "usage: private-allele-challenge REFERENCE_WORKTREE OUTPUT"
    );
    let root = Path::new(&args[1]);
    let out = Path::new(&args[2]);
    fs::create_dir(out).context("fresh output required")?;
    let pilot = root.join("results/graph-prior/pilot-v1/development");
    let observer = pilot.join("alleles/native");
    let variants: Vec<Variant> = table(&observer.join("variants.tsv"))?
        .into_iter()
        .map(|f| {
            Ok(Variant {
                id: f[0].clone(),
                contig: f[1].clone(),
                pos: f[2].parse()?,
                rf: f[3].clone(),
                alt: f[4].clone(),
                start: f[6].parse()?,
                end: f[7].parse()?,
                kind: f[8].clone(),
                alt_hap: f[10].clone(),
            })
        })
        .collect::<Result<_>>()?;
    let observations: BTreeMap<_, _> = table(&observer.join("observations.tsv"))?
        .into_iter()
        .map(|f| ((f[0].clone(), f[1].clone()), f[2].clone()))
        .collect();
    let windows: Vec<Window> = load_jsonl(&pilot.join("windows/windows.jsonl"))?;
    let parents: Vec<_> = fs::read_to_string(pilot.join("parents.ids"))?
        .lines()
        .map(String::from)
        .collect();
    let mut scored = BTreeSet::new();
    let mut edited = BTreeSet::new();
    for row in load_jsonl::<Value>(&pilot.join("candidates/decisions.jsonl"))? {
        let q = row["query_index"].as_u64().context("query index")? as usize;
        if row["status"] == "scored" {
            scored.insert(q);
        }
        if row["arms"]
            .as_array()
            .is_some_and(|a| a.iter().any(|a| a["edited"] == true))
        {
            edited.insert(q);
        }
    }
    let mut current_edits: BTreeMap<String, BTreeSet<usize>> = BTreeMap::new();
    let current=Path::new("/home/jake/Projects/nanopore_basecaller-retrieval/results/compound-frontier/20261023T160645Z-full-b2ea3920/admission/candidates/decisions.jsonl");
    for row in load_jsonl::<Value>(current)? {
        let id = row["policy_id"].as_str().context("current policy")?;
        if ["compound-panel-100", "compound-linear-100"].contains(&id)
            && row["decision"]["edited"] == true
        {
            current_edits
                .entry(id.into())
                .or_default()
                .insert(row["query_index"].as_u64().context("current query")? as usize);
        }
    }
    let current_union: BTreeSet<_> = current_edits
        .values()
        .flat_map(|s| s.iter().copied())
        .collect();
    let mut flank_edits = BTreeSet::new();
    for row in load_jsonl::<Value>(Path::new("/home/jake/Projects/nanopore_basecaller-flank/results/flank-prior/20261023T165833Z-emit/decisions.jsonl"))? {if row["policy_id"]=="flank-conditioned" && row["decision"]["edited"]==true {flank_edits.insert(row["query_index"].as_u64().context("flank query")? as usize);}}
    let all_current_union: BTreeSet<_> = current_union.union(&flank_edits).copied().collect();
    let mut rows = Vec::new();
    let mut stats: BTreeMap<String, Value> = BTreeMap::new();
    for scope in [
        "all_parents",
        "planned_core",
        "scored_core",
        "historically_edited_core",
        "current_panel_edited_core",
        "current_linear_edited_core",
        "current_edited_union",
        "current_flank_edited_core",
        "current_panel_linear_flank_union",
    ] {
        for kind in ["snv", "insertion", "deletion"] {
            let mut sites = BTreeSet::new();
            let mut reads = BTreeSet::new();
            let mut support = 0;
            for v in variants.iter().filter(|v| v.kind == kind) {
                for p in &parents {
                    if observations
                        .get(&(p.clone(), v.id.clone()))
                        .is_none_or(|c| c != "alt")
                    {
                        continue;
                    }
                    let ws: Vec<_> = windows
                        .iter()
                        .filter(|w| w.read_id == *p && overlaps(v, w))
                        .collect();
                    let include = scope == "all_parents"
                        || ws.iter().any(|w| match scope {
                            "planned_core" => true,
                            "scored_core" => scored.contains(&w.query_index),
                            "historically_edited_core" => edited.contains(&w.query_index),
                            "current_panel_edited_core" => current_edits
                                .get("compound-panel-100")
                                .is_some_and(|s| s.contains(&w.query_index)),
                            "current_linear_edited_core" => current_edits
                                .get("compound-linear-100")
                                .is_some_and(|s| s.contains(&w.query_index)),
                            "current_edited_union" => current_union.contains(&w.query_index),
                            "current_flank_edited_core" => flank_edits.contains(&w.query_index),
                            _ => all_current_union.contains(&w.query_index),
                        });
                    if include {
                        sites.insert(v.id.clone());
                        reads.insert(p.clone());
                        support += 1;
                    }
                    if scope == "planned_core" {
                        for w in ws {
                            rows.push(json!({"parent":p,"variant":v.id,"stratum":kind,"query_index":w.query_index,"scored":scored.contains(&w.query_index),"historically_edited":edited.contains(&w.query_index),"current_panel_edited":current_edits.get("compound-panel-100").is_some_and(|s|s.contains(&w.query_index)),"current_linear_edited":current_edits.get("compound-linear-100").is_some_and(|s|s.contains(&w.query_index)),"truth_window_fully_inside_scored_window":w.ref_start<=v.start && v.end<=w.ref_end}));
                        }
                    }
                }
            }
            stats.insert(format!("{scope}/{kind}"),json!({"parent_site_observations":support,"distinct_sites":sites.len(),"distinct_parents":reads.len()}));
        }
    }
    let summary = json!({"schema":"private-allele-inventory/1","role":"development","parents":parents.len(),"planned_windows":windows.len(),"scored_windows":scored.len(),"historically_edited_windows":edited.len(),"current_policy_edited_cores":current_edits,"current_edited_union_cores":current_union,"current_flank_edited_cores":flank_edits,"all_current_edited_union_cores":all_current_union,"strata":stats,"local_alt_cores":rows,"parent_ledger":table(&observer.join("parents.tsv"))?,"truth_exclusion_rows":table(&observer.join("excluded.tsv"))?.len()});
    fs::write(
        out.join("inventory.json"),
        serde_json::to_vec_pretty(&summary)?,
    )?;
    challenge::build(root, out, &windows, &variants, &observations, false)?;
    println!("{}", serde_json::to_string(&summary["strata"])?);
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    fn v(r: &str, a: &str) -> Variant {
        Variant {
            id: "x".into(),
            contig: "chr1".into(),
            pos: 100,
            rf: r.into(),
            alt: a.into(),
            kind: "".into(),
            start: 90,
            end: 111,
            alt_hap: "".into(),
        }
    }
    #[test]
    fn normalized_event_excludes_anchor() {
        assert_eq!(event(&v("A", "AT")), (101, 101));
        assert_eq!(event(&v("AT", "A")), (101, 102));
        assert_eq!(event(&v("A", "C")), (100, 101));
    }
    #[test]
    fn fixed_gate_retains_native_ties_and_rejects_deficit() {
        use decision::*;
        let hs = vec![
            Hypothesis {
                sequence: "A".into(),
                panel: false,
                linear: false,
                likelihood: 1.,
            },
            Hypothesis {
                sequence: "C".into(),
                panel: true,
                linear: false,
                likelihood: 0.4,
            },
        ];
        let p = Policy {
            id: "panel".into(),
            prior: Prior::Panel,
            lambda: 1.,
            neural_deficit: Some(0.5),
            margin: 0.5,
        };
        assert!(!choose("A", &hs, &p).expect("valid").edited);
    }
}
