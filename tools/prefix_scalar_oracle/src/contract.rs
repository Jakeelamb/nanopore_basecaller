use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FilePin {
    pub path: PathBuf,
    pub size: u64,
    pub sha256: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Prior {
    UniformAllStates,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Query {
    pub id: String,
    pub sequence: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Binding {
    pub tensor: FilePin,
    pub read_id: String,
    pub parent_id: String,
    pub chunk_index: usize,
    pub block_index: usize,
    pub row_begin: usize,
    pub row_end: usize,
    pub chunk_row_begin: usize,
    pub chunk_row_end: usize,
    pub available_score_end: usize,
    pub available_signal_end: usize,
    pub chunk_signal_begin: usize,
    pub chunk_signal_end: usize,
    pub declared_chunk_lookahead: usize,
    pub orientation: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Segment {
    pub binding: Binding,
    pub release_receipt: FilePin,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReleaseReceipt {
    pub schema: String,
    pub read_id: String,
    pub tensor: FilePin,
    pub binding: Binding,
    pub original_tensor: FilePin,
    pub metadata: FilePin,
    pub original_row_begin: usize,
    pub original_row_end: usize,
    pub recipe: String,
    pub signal_geometry_qualification: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub schema: String,
    pub prior: Prior,
    pub state_length: usize,
    pub stride: usize,
    pub channels: usize,
    pub read_id: String,
    pub chunk_index: usize,
    pub tensor: FilePin,
    pub metadata: FilePin,
    pub original_header: String,
    pub row_begin: usize,
    pub row_end: usize,
    pub chunk_row_begin: usize,
    pub chunk_row_end: usize,
    pub selection_receipt: FilePin,
    pub query_receipt: FilePin,
    pub segments: Vec<Segment>,
    pub queries: Vec<Query>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "kebab-case", deny_unknown_fields)]
pub enum Scalar {
    Finite { decimal: String, bits: String },
    Impossible,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StateScore {
    pub initial_state: usize,
    pub score: Scalar,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QueryScore {
    pub id: String,
    pub sequence: String,
    pub sequence_sha256: String,
    pub score: Scalar,
    pub per_initial_state: Vec<StateScore>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourcePin {
    pub path: String,
    pub sha256: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CompilerIdentity {
    pub path: PathBuf,
    pub sha256: String,
    pub version: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ComparisonTolerance {
    pub absolute: f64,
    pub relative: f64,
    pub rule: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Response {
    pub schema: String,
    pub request: Request,
    pub request_pin: FilePin,
    pub interpretation: String,
    pub comparison_tolerance: ComparisonTolerance,
    pub compiled_sources: Vec<SourcePin>,
    pub compiled_source_root: PathBuf,
    pub compiler: CompilerIdentity,
    pub executable: FilePin,
    pub consumed_payload_sha256: String,
    pub segment_payload_sha256: Vec<String>,
    pub scores: Vec<QueryScore>,
    pub limits: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Completion {
    pub schema: String,
    pub request: FilePin,
    pub request_copy: FilePin,
    pub scores: FilePin,
    pub executable: FilePin,
}
