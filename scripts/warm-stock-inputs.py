#!/usr/bin/env python3
"""Read actual stock runtime inputs outside the measured native processes."""
import argparse
import fcntl
from pathlib import Path

import benchmark as b


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('plan', type=Path)
    args = cli.parse_args()
    with (b.ROOT / 'results/stock/host.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = b.load_plan(args.plan)
        b.require(plan['config'].get('measurement_policy', {}).get('cache_policy') == 'warmed-filesystem', 'Plan does not declare warmed filesystem')
        b.admission(plan['config'])
        config = plan['config']
        paths = {b.ROOT / config['reference'], b.ROOT / config['index'], Path(config['dorado']), Path(config['samtools'])}
        paths.update(b.ROOT / unit['asset']['path'] for unit in plan['units'])
        for tree in plan['model_trees'].values():
            paths.update(Path(tree['path']) / file for file in tree['files'])
        paths.update(path for path in (Path(config['dorado']).parent.parent / 'lib').rglob('*') if path.is_file())
        paths.update(b.ROOT / (config['reference'] + suffix) for suffix in ('.fai', '.gzi'))
        files = sorted(str(path.resolve()) for path in paths)
        pins = [b.pin(path) for path in files]
        context = {'plan': plan['sha256'], 'warmup_source': b.pin(__file__), 'inputs': pins,
                   'policy': 'sequential native cat of runtime inputs; stdout discarded; no cache flush'}
        result = b.stage(args.plan.resolve().parent, 'filesystem-warmup',
                         ['bash', '-c', 'cat -- "$@" > /dev/null', '--', *files], context,
                         reserve=config['reserve_gib'] * 1024**3)
        b.write(args.plan.resolve().parent / 'filesystem-warmup.json',
                {'status': 'verified', 'context': context, 'native': result,
                 'files': len(files), 'bytes': sum(p['size'] for p in pins), 'pins': result['pins']})
        print(result['recorder'])


if __name__ == '__main__':
    main()
