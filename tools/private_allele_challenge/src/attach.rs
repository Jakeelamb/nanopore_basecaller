use super::*;
use graph_prior::{native, planner};
use std::io::{Read, Seek, SeekFrom, Write};

fn reference_slice(
    path: &Path,
    index: &BTreeMap<String, (u64, usize, usize)>,
    contig: &str,
    start: usize,
    end: usize,
) -> Result<String> {
    let &(offset, bases, bytes) = index.get(contig).context("FAI contig")?;
    ensure!(bases > 0 && bytes >= bases && start < end, "FAI bounds");
    let mut file = File::open(path)?;
    let mut cursor = start;
    let mut out = Vec::new();
    while cursor < end {
        let len = (bases - cursor % bases).min(end - cursor);
        file.seek(SeekFrom::Start(
            offset + (cursor / bases * bytes + cursor % bases) as u64,
        ))?;
        let old = out.len();
        out.resize(old + len, 0);
        file.read_exact(&mut out[old..])?;
        cursor += len;
    }
    ensure!(
        out.iter().all(|b| b"ACGT".contains(b)),
        "noncanonical reference slice"
    );
    Ok(String::from_utf8(out)?)
}
fn proposal(
    target: &Value,
    s: &native::Sam,
    e: &native::Export,
    reference: &str,
    index: usize,
) -> Result<planner::Window> {
    ensure!(
        s.flag & 4 == 0
            && (30..=254).contains(&s.mapq)
            && s.contig == target["contig"].as_str().context("target contig")?,
        "primary mapping exclusion"
    );
    let core_start = target["proposed_core_start0"]
        .as_u64()
        .context("target core")? as usize;
    let core_end = target["proposed_core_end0"]
        .as_u64()
        .context("target core")? as usize;
    let start = core_start.checked_sub(10).context("reference underflow")?;
    let end = core_end + 10;
    let (mut rp, mut qp) = (s.pos, 0usize);
    let mut map = BTreeMap::new();
    for (n, op) in native::cigar(&s.cigar)? {
        match op {
            b'=' | b'X' => {
                for k in 0..n {
                    if start <= rp + k && rp + k < end {
                        map.insert(rp + k, qp + k);
                    }
                }
                rp += n;
                qp += n;
            }
            b'I' | b'S' => qp += n,
            b'D' => rp += n,
            _ => anyhow::bail!("non-EQX target alignment"),
        }
    }
    ensure!(qp == s.aligned.len(), "CIGAR length mismatch");
    let a = *map.get(&start).context("left target anchor missing")?;
    let z = map.get(&(end - 1)).context("right target anchor missing")? + 1;
    ensure!(
        z >= a + 20 && z <= s.aligned.len() && (z - a - 20) <= 32 && (z - a - 20).abs_diff(21) <= 5,
        "core size exclusion"
    );
    for k in 0..10 {
        ensure!(
            map.get(&(start + k)) == Some(&(a + k))
                && map.get(&(end - 10 + k)) == Some(&(z - 10 + k)),
            "gapped target anchor"
        );
    }
    ensure!(
        s.aligned[a..a + 10] == reference[..10]
            && s.aligned[z - 10..z] == reference[reference.len() - 10..],
        "inexact target anchor"
    );
    let (read_start, read_end) = if s.reverse() {
        (s.seq.len() - z, s.seq.len() - a)
    } else {
        (a, z)
    };
    let stock = s.seq[read_start..read_end].to_owned();
    let mut w = planner::Window {
        schema: "graph-prior-window/1".into(),
        query_index: index,
        read_id: s.id.clone(),
        contig: s.contig.clone(),
        ref_start: start,
        ref_end: end,
        core_start,
        core_end,
        read_start,
        read_end,
        stock,
        reverse: s.reverse(),
        chunk_index: 0,
        chunk_start: 0,
        chunk_end: 0,
        t_start: 0,
        t_end: 0,
        context: String::new(),
        score_file: String::new(),
    };
    planner::attach(&mut w, e)?;
    Ok(w)
}

pub(super) fn run(root: &Path, work: &Path) -> Result<()> {
    let additional: Value =
        serde_json::from_reader(File::open(work.join("additional-windows.json"))?)?;
    let pilot = root.join("results/graph-prior/pilot-v1/development");
    let inputs: Value = serde_json::from_reader(File::open(
        root.join("results/reference-assisted/inputs-native-frozen-v1.json"),
    )?)?;
    let reference = Path::new(
        inputs["reference"]["path"]
            .as_str()
            .context("reference path")?,
    );
    let mut index = BTreeMap::new();
    for line in BufReader::new(File::open(reference.with_extension("fai"))?).lines() {
        let l = line?;
        let f: Vec<_> = l.split('\t').collect();
        ensure!(f.len() == 5, "FAI fields");
        index.insert(
            f[0].to_owned(),
            (f[2].parse()?, f[3].parse()?, f[4].parse()?),
        );
    }
    let ids = native::parents(&pilot.join("parents.ids"))?;
    let mapped=Path::new("/home/jake/Projects/nanopore_basecaller-reference/logs/20261023T035916Z-stock-fe30a2dbcb664128bf187fdaf8f68340-CoVGDR/stdout");
    let sams = native::sam(mapped, &ids)?;
    let dir = pilot.join("native-export");
    let inventory = native::inventory(&dir, &ids)?;
    let wanted: BTreeSet<_> = additional["targets"]
        .as_array()
        .context("targets")?
        .iter()
        .map(|t| {
            t["source_uuid"]
                .as_str()
                .map(String::from)
                .context("source UUID")
        })
        .collect::<Result<_>>()?;
    let mut exports = BTreeMap::new();
    let mut parent_results = Vec::new();
    for p in &wanted {
        ensure!(
            ids.contains(p),
            "selected parent outside existing export cohort"
        );
        let result = native::reconstruct(&dir, &sams[p], &inventory[p]).map_err(|e| e.to_string());
        parent_results.push(
            json!({"source_uuid":p,"reconstructed":result.is_ok(),"reason":result.as_ref().err()}),
        );
        exports.insert(p.clone(), result);
    }
    let mut plan = File::create(work.join("additional-attached-windows.jsonl"))?;
    let mut queries = File::create(work.join("additional-queries.tsv"))?;
    let mut rows = Vec::new();
    let mut admitted: Vec<planner::Window> = Vec::new();
    for (target_id, t) in additional["targets"]
        .as_array()
        .context("targets")?
        .iter()
        .enumerate()
    {
        let parent = t["source_uuid"].as_str().context("parent")?;
        let attempt = (|| -> Result<planner::Window> {
            let export = exports[parent]
                .as_ref()
                .map_err(|e| anyhow::anyhow!("parent reconstruction: {e}"))?;
            let cs = t["proposed_core_start0"].as_u64().context("start")? as usize;
            let ce = t["proposed_core_end0"].as_u64().context("end")? as usize;
            let rf = reference_slice(
                reference,
                &index,
                t["contig"].as_str().context("contig")?,
                cs.checked_sub(10).context("left context")?,
                ce + 10,
            )?;
            let w = proposal(t, &sams[parent], export, &rf, admitted.len())?;
            ensure!(
                !admitted.iter().any(|old| old.read_id == w.read_id
                    && old.read_start < w.read_end
                    && w.read_start < old.read_end),
                "overlap with earlier frozen target"
            );
            Ok(w)
        })();
        match attempt {Ok(w)=>{serde_json::to_writer(&mut plan,&w)?;writeln!(plan)?;writeln!(queries,"GRCh38\t{}\t{}\t{}",w.contig,w.ref_start,w.ref_end)?;rows.push(json!({"target_id":target_id,"status":"attached-existing-scores","query_index":w.query_index,"source_uuid":parent,"variant":t["variant"],"stratum":t["stratum"],"score_file":dir.join(&w.score_file),"score_metadata":dir.join(format!("{}.meta.tsv",w.score_file)),"parent_moves":dir.join(format!("{parent}.parent.tsv")),"read_start":w.read_start,"read_end":w.read_end,"chunk_index":w.chunk_index,"chunk_start":w.chunk_start,"chunk_end":w.chunk_end,"t_start":w.t_start,"t_end":w.t_end,"raw_signal_reused":true}));admitted.push(w);},Err(e)=>rows.push(json!({"target_id":target_id,"status":"excluded","source_uuid":parent,"variant":t["variant"],"stratum":t["stratum"],"reason":e.to_string()}))}
    }
    fs::write(
        work.join("additional-attachment.json"),
        serde_json::to_vec_pretty(
            &json!({"schema":"private-allele-target-attachment/1","role":"development","source_parents":2608,"existing_export_parents":64,"selected_parents":wanted.len(),"selected_parent_overlap_existing_export":wanted.len(),"selected_targets":rows.len(),"attached_targets":admitted.len(),"excluded_targets":rows.len()-admitted.len(),"parent_reconstruction":parent_results,"targets":rows,"new_gpu_required":false,"new_graph_extraction_and_likelihood_completion_required":true,"new_scoring_executed":false,"admissible_candidate":false}),
        )?,
    )?;
    Ok(())
}
