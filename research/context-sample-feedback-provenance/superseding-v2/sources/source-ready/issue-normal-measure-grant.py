"""Issue one fresh grant from the fixed reviewed five-measure packet."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'


def fresh(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def pin(path):
    return dict(path=str(path), size=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def issue(arm):
    path = READY/'normal-five-canonical-measures-ready.json'
    assert pin(path)['sha256'] == '9d611034ecc21e93696c8ae889a5733c54b60a1628557271f09f39c1b185974e'
    ready = json.loads(path.read_text())
    arms = [unit['arm'] for unit in ready['units']]
    index = arms.index(arm)
    assert index > 0, 'Initial disabled unit is already retained'
    prior = json.loads((READY/('measure-'+arms[index-1]+'-1-audit.json')).read_text())
    assert prior['complete'] and prior['actual_exec_parent_exit'] == 0
    assert prior['current_owned_results_bytes'] < 4*1024**3
    unit = ready['units'][index]
    assert not Path(unit['output']).exists(), 'Never replay an existing unit'
    now = datetime.now(timezone.utc)
    identity = 'measure-'+arm+'-1-'+now.strftime('%Y%m%dT%H%M%S%fZ')+'-'+secrets.token_hex(4)
    grant = dict(schema='context-sample-feedback-admission/1', id=identity,
        phase='measure', scope='all', config=ready['config'],
        sources_sha256=ready['source_identity'], output=unit['output'],
        qualification=ready['qualification'], inputs=unit['input_pins'],
        not_before_utc=now.isoformat(), expires_utc=(now+timedelta(seconds=300)).isoformat(),
        cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-sample-feedback-'+identity+'.service',
        case_id=None, source_audit=None, arm=arm, recovery=None, **unit['caps'])
    grant_path = Path(unit['future_grant_path'])
    fresh(grant_path, grant)
    launch_path = READY/('measure-'+arm+'-launch.json')
    fresh(launch_path, dict(command=unit['command'], shell_argv=shlex.split(unit['command']),
        cwd=str(ROOT), grant=pin(grant_path), ready=pin(path), issued_utc=now.isoformat(),
        launch_immediately_under_root_policy=True))
    return dict(command=unit['command'], grant=pin(grant_path), launch=pin(launch_path), id=identity)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', required=True, choices=('combined', 'wrong_source_control'))
    arguments = parser.parse_args()
    print(json.dumps(issue(arguments.arm)))
