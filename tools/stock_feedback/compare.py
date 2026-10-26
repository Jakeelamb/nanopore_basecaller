"""Validate comparison custody; native tools own all alignment/error/ALT computation."""
import hashlib
import json
from pathlib import Path

from bounded import pin, require
import legacy

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
    return dict(schema='stock-feedback-inventory/1', evidence=result, scientific_bodies_read=False,
                retained_closure=legacy.inventory(config) if 'legacy' in config else None)


def producer(item):
    """Consume the original receipt schemas; no fresh scientific body verification is implied."""
    reader = legacy.Metadata()
    receipt = reader.read(item['receipt'])
    if receipt.get('schema') == 'uncertainty-feedback-command/1':
        imported = legacy.uncertainty_command(reader, item['receipt'], item['cwd'])
        inputs = receipt['inputs']
        source = dict(witness=receipt['source_witness'], sources=receipt['sources'],
                      binary=receipt['binary'], runtime=receipt['runtime'], dependency=receipt['dependency_manifest'])
    else:
        imported = legacy.stock_finish(reader, item['receipt'], item['cwd'])
        manifest = reader.read(item['experiment_manifest'])
        require(receipt['context']['experiment'] == manifest['identity'], 'stock experiment closure differs')
        cohort = manifest['cohorts'][item['role']]
        inputs = [cohort['ids'], cohort['raw'], *manifest['model_pins']]
        source = dict(sources=receipt['context']['sources'], executables=receipt['context']['executables'])
    require(imported['argv'] == item['argv'] and imported['result'] == item['result'], 'producer argv/result differs')
    require(source == item['source'] and inputs == item['input_pins'], 'producer source/input tuple differs')
    return identity(dict(source=source, inputs=inputs, argv=item['argv'], cwd=item['cwd']))


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
            elif 'legacy' in config:
                kind = 'sup' if arm == 'stock-sup' else 'hac'
                if (item['model']['name'] != Path(config['legacy'][kind + '_model']).name
                        or item['model']['config_pin'] != config['legacy'][kind + '_config']):
                    gaps.append('model identity does not match declared arm')
            if not gaps:
                try:
                    legacy.stat_artifact(item['model']['config_pin'])
                    key = producer(item['producer'])
                    if key in aliases:
                        alias = aliases[key]
                    else:
                        aliases[key] = arm
                        alias = None
                except (ValueError, KeyError, OSError) as caught:
                    gaps.append(str(caught))
        arms.append(dict(arm=arm, status='unqualified' if gaps else 'retained-metadata-valid', gaps=gaps,
                         alias_of=alias if not gaps else None,
                         parents=[dict(parent=p, status='unqualified' if gaps else 'retained-metadata-valid') for p in universe]))
    return dict(schema='stock-feedback-plan/1', config_hash=identity(config), arms=arms,
                population=64, masks=[100, 500], no_parent_dropped=True, native_replay=False,
                retained_closure=legacy.inventory(config) if 'legacy' in config else None,
                scientific_content_reverified=False)


def report(config, planned, observations):
    require(planned['config_hash'] == identity(config), 'stale comparison plan')
    keys = [(row['arm'], row['mask']) for row in observations]
    require(len(keys) == len(set(keys)) and all(arm in ARMS and mask in config['masks'] for arm, mask in keys),
            'duplicate or unknown observation arm/domain')
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
            matrix.append(dict(arm=arm['arm'], mask=mask, status='unqualified' if gaps else 'retained-metadata-valid', gaps=gaps,
                               parent_rows=arm['parents'], native_observation=observation if not gaps else None))
    return dict(schema='stock-feedback-report/1', matrix=matrix, biological_promotion=False,
                model_winner=None, hg005_selection=False, no_parent_dropped=True,
                retained_closure=planned.get('retained_closure'), scientific_content_reverified=False)
