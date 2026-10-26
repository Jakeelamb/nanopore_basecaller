use anyhow::{ensure, Context, Result};
use std::{collections::BTreeMap, fs, io::Write, path::Path, process::Command};

#[allow(dead_code)]
#[path = "/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/crf.rs"]
mod crf;
#[allow(dead_code)]
#[path = "/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/scores.rs"]
mod scores;

const CRF_PATH: &str = "/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/crf.rs";
const CRF_SHA: &str = "3171343d81477d4d967e300466e9ba3e3d770164f34438dcedd0867ca5ea8a99";
const SCORES_PATH: &str = "/home/jake/Projects/nanopore_basecaller-reference/tools/graph_prior/src/scores.rs";
const SCORES_SHA: &str = "2122831be9c1fad80e953268cf2138909665f703b697b5f803604b9450f0fa2e";

fn digest(path: &Path) -> Result<String> {
    ensure!(path.is_absolute() && path.is_file() && !path.is_symlink(), "absolute nonsymlink file required");
    let output = Command::new("/usr/bin/sha256sum").arg("--").arg(path).output()?;
    ensure!(output.status.success(), "independent SHA256 utility failed");
    let stdout = String::from_utf8(output.stdout)?;
    let hash = stdout.split_whitespace().next().context("empty SHA256 output")?;
    ensure!(hash.len() == 64 && hash.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()), "invalid SHA256 output");
    Ok(hash.to_owned())
}
fn fields(path: &Path, schema: Option<&str>) -> Result<BTreeMap<String, String>> {
    ensure!(fs::metadata(path)?.len() <= 4_194_304, "request/metadata byte bound");
    let bytes = fs::read_to_string(path)?;
    ensure!(bytes.ends_with('\n') && !bytes.contains('\r'), "metadata LF required");
    let mut lines = bytes.lines();
    if let Some(expected) = schema { ensure!(lines.next() == Some(expected), "request schema differs"); }
    let mut result = BTreeMap::new();
    for line in lines {
        let (key, value) = line.split_once('\t').context("malformed metadata pair")?;
        ensure!(!key.is_empty() && !value.contains('\t') && result.insert(key.to_owned(), value.to_owned()).is_none(), "duplicate/malformed metadata field");
    }
    Ok(result)
}
fn field<'a>(values: &'a BTreeMap<String, String>, key: &str) -> Result<&'a str> {
    values.get(key).map(String::as_str).with_context(|| format!("missing field {key}"))
}
fn number(values: &BTreeMap<String, String>, key: &str) -> Result<usize> { Ok(field(values,key)?.parse()?) }
fn check_pin(values: &BTreeMap<String, String>, prefix: &str) -> Result<()> {
    let path = Path::new(field(values,&format!("{prefix}_path"))?);
    ensure!(fs::metadata(path)?.len() == field(values,&format!("{prefix}_size"))?.parse::<u64>()? && digest(path)? == field(values,&format!("{prefix}_sha256"))?, "independent consumed-file pin differs");
    Ok(())
}
fn fresh(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut output=fs::OpenOptions::new().write(true).create_new(true).open(path)?;
    output.write_all(bytes)?;output.sync_all()?;Ok(())
}
fn main() -> Result<()> {
    let args: Vec<String>=std::env::args().collect();
    ensure!(args.len()==8 && args[1]=="score" && args[2]=="--request" && args[4]=="--request-sha256" && args[6]=="--output", "score --request ABS --request-sha256 SHA --output ABS_NEW_DIR");
    let request=Path::new(&args[3]); let expected=&args[5]; let output=Path::new(&args[7]);
    ensure!(digest(request)? == *expected && output.is_absolute() && !output.exists(), "request pin/output differs");
    ensure!(digest(Path::new(CRF_PATH))?==CRF_SHA && digest(Path::new(SCORES_PATH))?==SCORES_SHA, "unchanged independent oracle source differs");
    let values=fields(request,Some("context-scalar-request/1"))?;
    let expected_keys=["plan_sha256","query_index","parent","chunk_index","t_start","t_end","initial_context","initial_state","sequence","token","time_offset","T","C","tensor_path","tensor_size","tensor_sha256","metadata_path","metadata_size","metadata_sha256"];
    ensure!(values.len()==expected_keys.len() && expected_keys.iter().all(|key| values.contains_key(*key)), "unknown/missing request field");
    check_pin(&values,"tensor")?;check_pin(&values,"metadata")?;
    let meta=fields(Path::new(field(&values,"metadata_path")?),None)?;
    ensure!(field(&meta,"format")?=="DGM1" && field(&meta,"read_id")?==field(&values,"parent")? && field(&meta,"chunk_index")?==field(&values,"chunk_index")?, "DGM parent/chunk differs");
    for key in ["token","time_offset","T","C"] {ensure!(field(&meta,key)?==field(&values,key)?,"DGM request geometry differs");}
    let tensor=Path::new(field(&values,"tensor_path")?);
    ensure!(tensor.file_name().and_then(|name|name.to_str())==Some(field(&meta,"score_file")?),"DGM tensor filename differs");
    let score=scores::load(tensor)?;
    ensure!(score.header.t==number(&values,"T")? && score.header.c==number(&values,"C")? && score.header.token==field(&values,"token")? && score.header.offset==number(&values,"time_offset")?, "DGS/DGM geometry differs");
    let start=number(&values,"t_start")?;let end=number(&values,"t_end")?;
    ensure!(start<end && end<=score.header.t && end-start<=256,"independent base timestep bounds");
    let initial_context=field(&values,"initial_context")?;
    ensure!(initial_context.len()==4,"native initial context length differs");
    let initial=crf::state(initial_context.as_bytes(),4)?;
    ensure!(initial==number(&values,"initial_state")?,"native initial k4 state differs");
    let moves=field(&meta,"MOVES")?;
    ensure!(moves.bytes().all(|value|value==b'0'||value==b'1'),"nonbinary native MOVES");
    let emitted:Vec<usize>=moves.bytes().enumerate().filter_map(|(index,value)|if value==b'1'{Some(index)}else{None}).collect();
    let a=emitted.iter().position(|&value|value==start).context("base start emission absent")?;
    let b=emitted.iter().position(|&value|value==end).context("base end emission absent")?;
    let sequence=field(&values,"sequence")?;let native=field(&meta,"SEQ")?;
    ensure!(a>=4 && a<b && b<=native.len() && emitted.len()==native.len() && &native[a..b]==sequence && &native[a-4..a]==initial_context,"actual new base sequence/context differs");
    let window=crf::ScoreWindow::new(&score.values[start*1024..end*1024],end-start,4,initial,score.header.blank)?;
    let value=window.likelihood(sequence.as_bytes())?;
    ensure!(value.is_finite() || value==f64::NEG_INFINITY,"unexpected independent scalar nonfinite");
    let decimal=if value==f64::NEG_INFINITY {"impossible".to_owned()} else {value.to_string()};
    fs::create_dir(output)?;
    fresh(&output.join("retained-scalar.tsv"),format!("{sequence}\t{decimal}\n").as_bytes())?;
    let audit=format!("context-scalar-audit/1\nrequest_sha256\t{expected}\nplan_sha256\t{}\nquery_index\t{}\nparent\t{}\nchunk_index\t{}\ntensor_sha256\t{}\nmetadata_sha256\t{}\nt_start\t{start}\nt_end\t{end}\ninitial_context\t{initial_context}\ninitial_state\t{initial}\nsequence\t{sequence}\nvalue\t{decimal}\nbits\t{:016x}\nDGS_T\t{}\nDGS_C\t{}\nDGS_blank\t{}\nDGS_clamp\t{}\nDGS_token\t{}\nDGS_slot\t{}\nDGS_offset\t{}\ncrf_sha256\t{CRF_SHA}\nscores_sha256\t{SCORES_SHA}\n",field(&values,"plan_sha256")?,field(&values,"query_index")?,field(&values,"parent")?,field(&values,"chunk_index")?,field(&values,"tensor_sha256")?,field(&values,"metadata_sha256")?,value.to_bits(),score.header.t,score.header.c,score.header.blank,score.header.clamp,score.header.token,score.header.slot,score.header.offset);
    fresh(&output.join("audit.tsv"),audit.as_bytes())?;
    ensure!(digest(request)?==*expected,"request changed during independent scalar consumption");
    println!("unchanged_original_Rust_scalar\t{decimal}\t{:016x}",value.to_bits());
    Ok(())
}
