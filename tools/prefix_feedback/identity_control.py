"""Disabled-edit full-parent output control. Never supply native calls to inference."""
import hashlib
from pathlib import Path
import bounded_cli as io


def metadata(path):
    io.require(Path(path).stat().st_size <= 1024**2, "parent metadata bound")
    result = {}
    for line in Path(path).read_text().splitlines():
        cells = line.split("\t")
        io.require(len(cells) == 2 and cells[0] not in result, "parent field census differs")
        result[cells[0]] = cells[1]
    return result


def sam_identities(data, parents):
    identities = {}
    secondary = 0
    for line in data.decode("ascii").splitlines():
        if line.startswith("@"):
            continue
        fields = line.split("\t")
        io.require(len(fields) >= 11 and fields[0] in parents, "foreign/malformed full-parent SAM record")
        flag = int(fields[1])
        io.require(0 <= flag <= 65535, "SAM flag bound")
        if flag & 0x900:
            secondary += 1
            continue
        parent = fields[0]
        io.require(parent not in identities, "duplicate primary parent")
        sequence, quality = fields[9:11]
        io.require(sequence != "*" and len(sequence) == len(quality) and set(sequence) <= set("ACGT"), "full-parent SEQ/Q absent")
        if flag & 16:
            sequence = sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]
            quality = quality[::-1]
        io.require((sequence, quality) == parents[parent], "full-parent SEQ/Q differs from native export")
        identities[parent] = dict(sequence=sequence, quality=quality, reverse=bool(flag & 16))
    io.require(set(identities) == set(parents), "full-parent primary census differs")
    return identities, secondary


def run(request_path, request_sha256, output):
    io.require(io.pin(request_path)["sha256"] == request_sha256, "disabled request root differs")
    request = io.read(request_path)
    io.require(request["schema"] == "prefix-disabled-identity/1" and request["mode"] == "disabled"
               and request["edits"] == [], "disabled control refuses any edit")
    io.check(request["manifest"])
    io.check(request["aligned_sam"])
    parents = {}
    consumed = []
    for line in Path(request["manifest"]["path"]).read_text().splitlines():
        cells = line.split("\t")
        if cells[0] != "PARENT":
            continue
        io.require(len(cells) == 5 and cells[1] not in parents, "full parent manifest census differs")
        item = dict(path=cells[2], size=int(cells[3]), sha256=cells[4])
        io.check(item)
        value = metadata(item["path"])
        io.require(value["format"] == "DGP1" and value["read_id"] == cells[1], "full parent identity differs")
        sequence, quality = value["SEQ"], value["Q"]
        io.require(sequence and set(sequence) <= set("ACGT") and len(sequence) == len(quality)
                   and all(33 <= ord(base) <= 126 for base in quality), "invalid native parent SEQ/Q")
        parents[cells[1]] = (sequence, quality)
        consumed.append(item)
    io.require(len(parents) == request["expected_parents"] and parents, "full requested population differs")
    io.require(Path(request["aligned_sam"]["path"]).stat().st_size <= 32 * 1024**2, "full SAM role bound")
    data = Path(request["aligned_sam"]["path"]).read_bytes()
    before, secondary = sam_identities(data, parents)
    output = Path(output)
    output.mkdir()
    target = output / "disabled.sam"
    io.fresh_bytes(target, data)
    after, secondary_after = sam_identities(target.read_bytes(), parents)
    io.require(before == after and secondary == secondary_after and target.read_bytes() == data,
               "disabled full-parent output identity differs")
    io.check(request["manifest"])
    io.check(request["aligned_sam"])
    for item in consumed:
        io.check(item)
    io.require(io.pin(target)["sha256"] == request["aligned_sam"]["sha256"], "disabled byte identity differs")
    io.fresh(output / "complete.json", dict(schema="prefix-disabled-identity-result/1", complete=True,
        request=io.pin(request_path), manifest=request["manifest"], aligned_sam=request["aligned_sam"],
        output=io.pin(target), parent_count=len(parents), secondary_records=secondary, changed_parents=0,
        full_seq_q_identity=True, full_sam_byte_identity=True, inference_inputs_exposed=False,
        parent_identity_sha256={parent: hashlib.sha256((sequence + "\0" + quality).encode()).hexdigest()
                                for parent, (sequence, quality) in sorted(parents.items())},
        qualification="disabled-output-control-only; no candidate accuracy or inference claim"))
