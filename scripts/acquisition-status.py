"""Show acquired and in-progress asset bytes without declaring verification."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
assets = json.loads((root / "config/assets.json").read_text())
total = 0
acquired = 0
for asset in assets:
    target = root / asset["path"]
    if target.exists():
        present = target.stat().st_size
        state = "downloaded; verification separate"
    else:
        parts = target.with_name(target.name + ".parts")
        present = sum(path.stat().st_size for path in parts.glob("*")
                      if path.name.isdigit() or path.suffix in (".partial", ".remainder"))
        state = "acquiring" if present else "pending"
    total += asset["bytes"]
    acquired += min(present, asset["bytes"])
    print(f"{asset['id']}: {present:,}/{asset['bytes']:,} bytes, {state}")
print(f"TOTAL {acquired:,}/{total:,} bytes, {100 * acquired / total:.1f}%")
