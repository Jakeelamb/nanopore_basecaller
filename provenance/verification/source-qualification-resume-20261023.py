"""One retained recovery call; outer flock and PPD launch own the job lifetime."""
import importlib.util
import json
from pathlib import Path
import sys

root = Path('/home/jake/Projects/nanopore_basecaller')
sys.path.insert(0, str(root / 'scripts'))
spec = importlib.util.spec_from_file_location('qualify_source', root / 'scripts/qualify-source.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
q.b.require(q.b.digest(q.__file__) == '58d38686ebec1d868d027a002fca68c7e48a724a252b43074849d05adabc3b51', 'Changed sealed adapter')
q.b.require(Path('/sys/firmware/acpi/platform_profile').read_text().strip() == 'performance', 'Missing performance hold')
result = q.qualify(root / 'provenance/source-build-20261023.json', root / 'results/source-qualification/20261023-performance', 'full', 'source:full-development-hac:calmd')
print(json.dumps(result, sort_keys=True, indent=2))
sys.exit(1 if 'different' in result['exact_equivalence'].values() else 0)
