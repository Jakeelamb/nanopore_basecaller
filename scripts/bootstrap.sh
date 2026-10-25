#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
mkdir -p logs software/archives software/bin models data/raw references truth results provenance
uv sync --locked
if [[ ! -d software/dorado-src/.git ]]; then
    scripts/record-command.sh source-clone git clone --depth 1 --branch v2.1.2 https://github.com/nanoporetech/dorado.git software/dorado-src
fi
scripts/record-command.sh source-submodules git -C software/dorado-src submodule update --init --recursive --depth 1 --jobs 4
scripts/build-index-tool.sh
mapfile -t assets < <(uv run --locked python -c 'import json; print("\n".join(x["id"] for x in json.load(open("config/assets.json"))))')
for asset in "${assets[@]}"; do
    scripts/record-command.sh acquire uv run --locked scripts/fetch.py "$asset"
done
if [[ -e provenance/assets.lock.json ]]; then
    scripts/record-command.sh verify-assets uv run --locked scripts/verify-assets.py
else
    scripts/record-command.sh freeze-assets uv run --locked scripts/verify-assets.py --freeze
fi
scripts/record-command.sh unpack-dorado tar -xzf software/archives/dorado-2.1.2-linux-x64.tar.gz -C software
uv run --locked python - <<'PY'
from pathlib import Path
import json
import zipfile
for asset in json.loads(Path('config/assets.json').read_text()):
    if asset['role'] == 'stock_model':
        with zipfile.ZipFile(asset['path']) as archive:
            archive.extractall('models')
PY
ln -sfn ../dorado-2.1.2-linux-x64/bin/dorado software/bin/dorado
scripts/record-command.sh installed-version software/bin/dorado --version
scripts/record-command.sh signal-inventory uv run --locked scripts/inspect-signals.py
printf 'Acquisition and installation steps completed. GPU and benchmark qualification are separate checks.\n'
