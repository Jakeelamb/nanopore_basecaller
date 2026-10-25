"""Check published continuation snapshots without running scientific tools."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def check(path, expected):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if path.stat().st_size != expected['size'] or digest != expected['sha256']:
        raise ValueError('Changed source snapshot '+str(path))


def verify(root, live=False):
    manifest = json.loads((root/'manifest.json').read_text())
    if manifest['schema'] != 'context-sample-feedback-published-source-snapshots/1':
        raise ValueError('Unknown source snapshot schema')
    seen = set()
    for row in manifest['snapshots']:
        path = (root/row['snapshot']).resolve(strict=True)
        if not path.is_relative_to(root.resolve()) or path in seen:
            raise ValueError('Duplicate or escaping snapshot path')
        seen.add(path)
        check(path, row['original'])
        if live:
            check(Path(row['original']['path']), row['original'])
    if live:
        for row in manifest['compiled_sources']:
            check(Path(row['path']), row)
    return dict(complete=True, snapshots=len(seen), live_sources_checked=live,
                compiled_source_identity=manifest['compiled_source_identity'],
                scientific_tools_executed=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--manifest', type=Path, default=HERE/'manifest.json')
    args = parser.parse_args()
    if args.manifest.name != 'manifest.json':
        raise ValueError('Expected manifest.json within a preserved version')
    print(json.dumps(verify(args.manifest.resolve().parent, args.live)))
