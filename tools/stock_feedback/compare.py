"""Validate comparison custody; native tools own all alignment/error/ALT computation."""
import hashlib
import json
from pathlib import Path

from bounded import check, linked_files, pin, read, require

ARMS = ('native-hac', 'hac-context', 'stock-sup')
CONTRACT_KEYS = ('parents_pin', 'pod5_pin', 'chemistry', 'settings', 'mapper', 'masks', 'truth_domains')


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def parents(path):
    path = Path(path)
    require(path.stat().st_size <= 65536, 'parent metadata exceeds cap')
    values = path.read_text().splitlines()
    require(len(values) == 64 and len(set(values)) == 64 and all(values), 'exact original64 parent universe required')
    return values


def inspect(config):
    """STAT only for scientific artifacts. Presence never qualifies their bodies."""
    result = []
    for item in config['retained']:
        path = Path(item['pin']['path'])
        result.append(dict(id=item['id'], declared=item['pin'], exists=path.is_file(),
                           observed_size=path.stat().st_size if path.is_file() else None,
                           status='unqualified', gaps=item['gaps']))
    return dict(schema='stock-feedback-inventory/1', evidence=result, scientific_bodies_read=False)


def producer(item):
    """Validate a linked producer closure without rerunning it. Caller must be in admitted worker."""
    check(item['receipt'])
    receipt = read(item['receipt']['path'])
    require(receipt['argv'] == item['argv'] and receipt['cwd'] == item['cwd'], 'producer argv/cwd differs')
    require(receipt['exit'] == 0 and receipt['complete'] is True, 'producer did not complete')
    require(receipt['source_pins'] == item['source_pins'] and receipt['input_pins'] == item['input_pins'],
            'producer source/input tuple differs')
    for value in receipt['source_pins'] + receipt['input_pins'] + receipt['files']:
        check(value)
    names = {Path(value['path']).name for value in receipt['files']}
    require({'command.json', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'} <= names,
            'incomplete producer raw recorder')
    require(receipt['start'] < receipt['end'] and receipt['terminal_tree_empty'] is True, 'producer clocks/tree incomplete')
    require(receipt['result'] == item['result'], 'linked producer result differs')
    check(receipt['result'])
    return identity(dict(source=item['source_pins'], inputs=item['input_pins'], argv=item['argv'], cwd=item['cwd']))


def plan(config, supplied):
    universe = parents(config['parents_pin']['path'])
    require(pin(config['parents_pin']['path']) == config['parents_pin'], 'original parent pin differs')
    require(config['masks'] == [100, 500] and config['hg005_selection'] is False, 'fixed endpoint contract differs')
    require(len(supplied) == len({x['arm'] for x in supplied}), 'duplicate arm')
    require({x['arm'] for x in supplied} <= set(ARMS), 'unknown arm')
    arms = []
    aliases = {}
    for arm in ARMS:
        item = next((x for x in supplied if x['arm'] == arm), None)
        gaps = []
        if item is None:
            gaps.append('no qualified same-molecule producer closure supplied')
        else:
            for key in CONTRACT_KEYS:
                if item.get(key) != config.get(key):
                    gaps.append('mismatched ' + key)
            if item.get('parents') != universe:
                gaps.append('missing, reordered or extra original parent identities')
            if not item.get('model', {}).get('name') or not item.get('model', {}).get('config_pin'):
                gaps.append('model/config declaration missing')
            if not gaps:
                try:
                    check(item['model']['config_pin'])
                    key = producer(item['producer'])
                    if key in aliases:
                        alias = aliases[key]
                    else:
                        aliases[key] = arm
                        alias = None
                except (ValueError, KeyError, OSError) as caught:
                    gaps.append(str(caught))
        arms.append(dict(arm=arm, status='unqualified' if gaps else 'qualified', gaps=gaps,
                         alias_of=alias if not gaps else None,
                         parents=[dict(parent=p, status='unqualified' if gaps else 'qualified') for p in universe]))
    return dict(schema='stock-feedback-plan/1', config_hash=identity(config), arms=arms,
                population=64, masks=[100, 500], no_parent_dropped=True, native_replay=False)


def report(config, planned, observations):
    require(planned['config_hash'] == identity(config), 'stale comparison plan')
    matrix = []
    universe = parents(config['parents_pin']['path'])
    for arm in planned['arms']:
        for mask in config['masks']:
            observation = next((x for x in observations if x['arm'] == arm['arm'] and x['mask'] == mask), None)
            gaps = list(arm['gaps'])
            if observation is None:
                gaps.append('native paired observation unavailable')
            elif not gaps:
                require(observation['parents'] == universe and observation['domains'] == config['truth_domains'],
                        'observation parent/domain mismatch')
                require(observation['masks'] == config['masks'] and observation['zero_exposure_preserved'] is True,
                        'observation mask/exposure mismatch')
                require(observation['denominator'] == 'M+X+I+D' and observation['errors'] == 'X+I+D',
                        'observation denominator mismatch')
                require(set(observation['technical_bounds']) == {'parent', 'genomic_block'}, 'technical bounds missing')
                require(set(observation['strata']) == {'target43', 'nontarget21'}, 'target strata missing')
                require(set(observation['changed_footprint_alt']) == {'SNV', 'INS', 'DEL'}, 'actual changed-footprint ALT missing')
                producer(observation['producer'])
            matrix.append(dict(arm=arm['arm'], mask=mask, status='unqualified' if gaps else 'qualified', gaps=gaps,
                               parent_rows=arm['parents'], native_observation=observation if not gaps else None))
    return dict(schema='stock-feedback-report/1', matrix=matrix, biological_promotion=False,
                model_winner=None, hg005_selection=False, no_parent_dropped=True)
