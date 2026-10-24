"""Exercise the completed frozen qualifier and audit immutable owned evidence.

Run only inside the canonical outer flock and temporary performance hold.
An external execve trace separately observes whether any native producer ran.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path('/home/jake/Projects/nanopore_basecaller')
RUN = ROOT / 'results/source-qualification/20261023-performance'
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qualify_source', ROOT / 'scripts/qualify-source.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
q.b.require(q.b.digest(q.__file__) == '58d38686ebec1d868d027a002fca68c7e48a724a252b43074849d05adabc3b51', 'Changed sealed adapter')
q.b.require(Path('/sys/firmware/acpi/platform_profile').read_text().strip() == 'performance', 'Missing performance hold')
original = q.b.read(RUN / 'qualification.json')
q.b.require(original['through'] == 'full', 'Full qualification must finish before completed-run proof')

def snapshot():
    protected = {}
    for directory in ('source/units', 'official-smoke/units', 'score-evidence', 'accuracy'):
        for path in sorted((RUN / directory).rglob('*')):
            if not path.is_file():
                continue
            st = path.stat()
            item = {'size': st.st_size, 'mtime_ns': st.st_mtime_ns, 'device': st.st_dev, 'inode': st.st_ino}
            if path.suffix == '.json':
                item['sha256'] = q.b.digest(path)
            protected[str(path.relative_to(RUN))] = item
    return protected

before = snapshot()
started = datetime.now(timezone.utc).isoformat()
print(json.dumps({'event': 'begin', 'started_utc': started, 'script': q.b.pin(Path(__file__))}, sort_keys=True), flush=True)
resumed = q.qualify(ROOT / 'provenance/source-build-20261023.json', RUN, 'full', 'source:full-development-hac:calmd')
after_resume = snapshot()
q.b.require(before == after_resume, 'Completed resume changed retained unit/score evidence')
q.b.require(resumed == original, 'Completed resume changed qualification projection')
report_before_audit = (RUN / 'qualification.json').read_bytes()
audited = q._audit(RUN)
after_audit = snapshot()
q.b.require(before == after_audit, 'Read-only audit changed retained unit/score evidence')
q.b.require((RUN / 'qualification.json').read_bytes() == report_before_audit, 'Read-only audit changed qualification projection')
q.b.require(audited == resumed, 'Audit result differs from resumed qualification')
result = {
    'schema': 1, 'status': 'verified', 'scope': 'completed-run evidence preservation and frozen read-only audit',
    'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
    'script': q.b.pin(Path(__file__)),
    'protected_files': len(before),
    'protected_json_files': sum('sha256' in x for x in before.values()),
    'new_or_changed_unit_or_score_files': 0,
    'snapshot_sha256': hashlib.sha256(json.dumps(before, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    'qualification': q.b.pin(RUN / 'qualification.json'),
    'qualification_gates': {k: v for k, v in audited.items() if k != 'pins'},
    'native_producer_count': 'requires independent execve trace inspection',
}
q.b.write(RUN / 'completed-resume-proof.json', result)
print(json.dumps(result, sort_keys=True, indent=2))
