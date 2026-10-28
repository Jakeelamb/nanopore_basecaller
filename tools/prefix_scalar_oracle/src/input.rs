use crate::{contract::*, digest, scores};
use anyhow::{ensure, Context, Result};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Read,
    path::Path,
};

pub const RECIPE: &str = "floor(i*T/4),i=0..4,first-retained-chunk-only";
pub const QUALIFICATION: &str = "static-export-geometry-only-no-acquisition-clock";

pub fn read_pinned(pin: &FilePin, maximum: u64) -> Result<Vec<u8>> {
    ensure!(
        pin.path.is_absolute() && fs::canonicalize(&pin.path)? == pin.path,
        "absolute canonical nonsymlink file required"
    );
    ensure!(
        pin.sha256.len() == 64
            && pin
                .sha256
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),
        "lowercase SHA256 required"
    );
    let file = fs::File::open(&pin.path)?;
    let metadata = file.metadata()?;
    ensure!(
        metadata.is_file() && metadata.len() == pin.size && pin.size <= maximum,
        "input type/size bound"
    );
    let mut bytes = Vec::new();
    file.take(maximum + 1).read_to_end(&mut bytes)?;
    ensure!(
        bytes.len() as u64 == pin.size && digest(&bytes) == pin.sha256,
        "input hash/size differs"
    );
    Ok(bytes)
}

pub fn pin(path: &Path) -> Result<FilePin> {
    let bytes = fs::read(path)?;
    Ok(FilePin {
        path: path.to_owned(),
        size: bytes.len() as u64,
        sha256: digest(&bytes),
    })
}

fn header(bytes: &[u8]) -> Result<(&str, &[u8])> {
    let end = bytes
        .iter()
        .take(4096)
        .position(|&b| b == b'\n')
        .context("DGS header bound")?
        + 1;
    Ok((std::str::from_utf8(&bytes[..end])?, &bytes[end..]))
}

fn metadata(bytes: &[u8]) -> Result<BTreeMap<&str, &str>> {
    let text = std::str::from_utf8(bytes)?;
    ensure!(
        text.ends_with('\n') && !text.contains('\r'),
        "DGM LF required"
    );
    let mut fields = BTreeMap::new();
    for line in text.lines() {
        let (key, value) = line.split_once('\t').context("DGM field separator")?;
        ensure!(
            !key.is_empty() && !value.contains('\t') && fields.insert(key, value).is_none(),
            "DGM duplicate/malformed field"
        );
    }
    Ok(fields)
}
fn field<'a>(meta: &BTreeMap<&str, &'a str>, key: &str) -> Result<&'a str> {
    meta.get(key)
        .copied()
        .with_context(|| format!("missing DGM {key}"))
}
fn number(meta: &BTreeMap<&str, &str>, key: &str) -> Result<usize> {
    Ok(field(meta, key)?.parse()?)
}

pub struct Consumed {
    pub values: Vec<f64>,
    pub rows: usize,
    pub blank: f64,
    pub payload_sha256: String,
    pub segment_payload_sha256: Vec<String>,
}

pub fn load(request: &Request) -> Result<Consumed> {
    ensure!(
        request.schema == "prefix-scalar-request/1" && request.prior == Prior::UniformAllStates,
        "request schema/prior differs"
    );
    ensure!(
        (request.state_length, request.stride, request.channels) == (4, 6, 1024)
            && request.chunk_index == 0,
        "only first-chunk k4/stride6/C1024 supported"
    );
    ensure!(
        request.read_id.len() == 36
            && request.read_id.bytes().enumerate().all(|(i, b)| {
                if [8, 13, 18, 23].contains(&i) {
                    b == b'-'
                } else {
                    b.is_ascii_digit() || (b'a'..=b'f').contains(&b)
                }
            }),
        "canonical UUID required"
    );
    ensure!(
        request.row_begin == 0
            && (1..=2048).contains(&request.row_end)
            && request.chunk_row_begin < request.chunk_row_end
            && request.chunk_row_end <= 8192
            && request.chunk_row_end - request.chunk_row_begin == request.row_end,
        "consumed interval bound"
    );
    ensure!(
        (1..=4).contains(&request.segments.len()) && (1..=8).contains(&request.queries.len()),
        "segment/query count bound"
    );
    let mut ids = BTreeSet::new();
    for query in &request.queries {
        ensure!(
            !query.id.is_empty()
                && query.id.len() <= 128
                && query.id.bytes().all(|b| b.is_ascii_graphic())
                && ids.insert(&query.id)
                && query.sequence.len() <= 512
                && query.sequence.bytes().all(|b| b"ACGT".contains(&b)),
            "query ID/string bound"
        );
    }
    read_pinned(&request.selection_receipt, 4_194_304)?;
    read_pinned(&request.query_receipt, 4_194_304)?;
    let original = read_pinned(&request.tensor, 4096 + 8192 * 2048)?;
    let (original_header, original_payload) = header(&original)?;
    ensure!(
        original_header == request.original_header,
        "original header differs"
    );
    let parsed = scores::parse_header(original_header)?;
    ensure!(
        parsed.t <= 8192 && request.chunk_row_end <= parsed.t,
        "original row bound"
    );
    let meta_bytes = read_pinned(&request.metadata, 4_194_304)?;
    let meta = metadata(&meta_bytes)?;
    ensure!(
        field(&meta, "format")? == "DGM1"
            && field(&meta, "read_id")? == request.read_id
            && number(&meta, "chunk_index")? == request.chunk_index
            && number(&meta, "chunk_count")? > request.chunk_index
            && field(&meta, "token")? == parsed.token
            && number(&meta, "time_offset")? == parsed.offset
            && number(&meta, "T")? == parsed.t
            && number(&meta, "C")? == parsed.c
            && request.tensor.path.file_name().and_then(|n| n.to_str())
                == Some(field(&meta, "score_file")?),
        "DGM tensor/geometry differs"
    );
    ensure!(
        matches!(field(&meta, "variable_chunk_sizes")?, "0" | "1"),
        "DGM variable geometry differs"
    );
    let signal_begin = number(&meta, "input_offset")?;
    let signal_end = signal_begin
        .checked_add(number(&meta, "raw_chunk_size")?)
        .context("signal overflow")?
        .min(number(&meta, "signal_samples")?);
    ensure!(signal_begin < signal_end, "DGM signal bounds");
    let decoded = scores::load(&request.tensor.path)?;
    ensure!(
        decoded.header.t == parsed.t
            && decoded.header.c == parsed.c
            && decoded.header.blank.to_bits() == parsed.blank.to_bits()
            && decoded.header.clamp.to_bits() == parsed.clamp.to_bits()
            && decoded.header.token == parsed.token
            && decoded.header.slot == parsed.slot
            && decoded.header.offset == parsed.offset
            && original_payload.len() == parsed.t * 2048,
        "original payload size differs"
    );
    for (bytes, &value) in original_payload
        .as_chunks::<2>()
        .0
        .iter()
        .zip(&decoded.values)
    {
        let expected = scores::half(u16::from_le_bytes([bytes[0], bytes[1]]));
        let expected = if parsed.clamp == 0.0 {
            expected
        } else {
            expected.clamp(-parsed.clamp, parsed.clamp)
        };
        ensure!(
            expected.to_bits() == value.to_bits(),
            "decoded original bytes differ"
        );
    }
    let mut row_cursor = 0;
    let mut chunk_cursor = request.chunk_row_begin;
    let mut concatenated = Vec::with_capacity(request.row_end * 2048);
    let mut payload_pins = Vec::new();
    for (index, segment) in request.segments.iter().enumerate() {
        let binding = &segment.binding;
        ensure!(
            binding.row_begin == row_cursor
                && binding.row_begin < binding.row_end
                && binding.row_end <= request.row_end
                && binding.row_end - binding.row_begin <= 512
                && binding.chunk_row_begin == chunk_cursor
                && binding.chunk_row_end > binding.chunk_row_begin
                && binding.chunk_row_end <= request.chunk_row_end
                && binding.chunk_row_end - binding.chunk_row_begin
                    == binding.row_end - binding.row_begin
                && binding.block_index == index
                && binding.chunk_index == request.chunk_index
                && binding.read_id == request.read_id
                && binding.parent_id == request.read_id
                && binding.orientation == "signal-forward"
                && binding.available_score_end == binding.row_end
                && binding.chunk_signal_begin == signal_begin
                && binding.chunk_signal_end == signal_end
                && binding.available_signal_end == signal_end
                && binding.declared_chunk_lookahead == signal_end - signal_begin,
            "release interval/order/geometry differs"
        );
        let receipt: ReleaseReceipt =
            serde_json::from_slice(&read_pinned(&segment.release_receipt, 65_536)?)?;
        ensure!(
            receipt.schema == "prefix-release/1"
                && receipt.read_id == request.read_id
                && receipt.tensor == binding.tensor
                && receipt.binding == *binding
                && receipt.original_tensor == request.tensor
                && receipt.metadata == request.metadata
                && receipt.original_row_begin == binding.chunk_row_begin
                && receipt.original_row_end == binding.chunk_row_end
                && receipt.recipe == RECIPE
                && receipt.signal_geometry_qualification == QUALIFICATION,
            "release receipt binding differs"
        );
        let bytes = read_pinned(&binding.tensor, 4096 + 512 * 2048)?;
        let (released_header, payload) = header(&bytes)?;
        let mut expected_fields: Vec<_> = original_header
            .trim_end_matches('\n')
            .split('\t')
            .map(str::to_owned)
            .collect();
        expected_fields[1] = (binding.row_end - binding.row_begin).to_string();
        let expected_header = expected_fields.join("\t") + "\n";
        ensure!(
            released_header == expected_header,
            "release header/options differ"
        );
        let expected_payload =
            &original_payload[binding.chunk_row_begin * 2048..binding.chunk_row_end * 2048];
        ensure!(
            payload == expected_payload,
            "release original payload bytes differ"
        );
        concatenated.extend_from_slice(payload);
        payload_pins.push(digest(payload));
        row_cursor = binding.row_end;
        chunk_cursor = binding.chunk_row_end;
    }
    ensure!(
        row_cursor == request.row_end
            && chunk_cursor == request.chunk_row_end
            && concatenated
                == original_payload[request.chunk_row_begin * 2048..request.chunk_row_end * 2048],
        "complete consumed interval differs"
    );
    read_pinned(&request.tensor, 4096 + 8192 * 2048)?;
    read_pinned(&request.metadata, 4_194_304)?;
    Ok(Consumed {
        values: decoded.values[request.chunk_row_begin * 1024..request.chunk_row_end * 1024]
            .to_vec(),
        rows: request.row_end,
        blank: decoded.header.blank,
        payload_sha256: digest(&concatenated),
        segment_payload_sha256: payload_pins,
    })
}
