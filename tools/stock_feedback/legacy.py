"""Bounded metadata bridge to retained native receipts; scientific bodies are STAT-only."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex

from bounded import require

RAW = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt')


class Metadata:
    def __init__(self):
        self.bytes = 0

    def text(self, expected):
        path = Path(expected['path'])
        require(path.is_absolute() and path.is_file() and not path.is_symlink(), 'metadata path differs')
        size = path.stat().st_size
        require(size == expected['size'] and size <= 8 * 1024**2, 'metadata size differs')
        require(self.bytes + size <= 32 * 1024**2, 'metadata pass exceeds32MiB')
        self.bytes += size
        data = path.read_bytes()
        require(len(data) == size and hashlib.sha256(data).hexdigest() == expected['sha256'],
                'metadata hash differs: ' + str(path))
        return data.decode()

    def read(self, expected):
        def pairs(items):
            value = {}
            for key, item in items:
                require(key not in value, 'duplicate metadata field')
                value[key] = item
            return value
        return json.loads(self.text(expected), object_pairs_hook=pairs,
                          parse_constant=lambda _x: require(False, 'nonfinite metadata'))


def stat_artifact(item):
    """Presence/size is not a new content-hash or biological qualification."""
    path = Path(item['path'])
    require(path.is_absolute() and path.is_file() and path.stat().st_size == item['size'],
            'missing or size-changed linked artifact: ' + str(path))
    return dict(pin=item, current_check='STAT-size-only', content_hash_rechecked=False)


def raw_closure(reader, values, directory, argv, cwd):
    paths = {item['path']: item for item in values}
    require(len(paths) == len(values), 'duplicate raw receipt pin')
    raw = {}
    for name in RAW:
        path = str(Path(directory) / name)
        require(path in paths, 'missing raw recorder pin: ' + name)
        raw[name] = paths[path]
        stat_artifact(raw[name])
    # stdout can be BAM/SAM and is never opened by this metadata importer.
    require(shlex.split(reader.text(raw['command.sh'])) == argv, 'raw command/argv differs')
    require(reader.text(raw['cwd.txt']).strip() == cwd, 'raw cwd differs')
    require(reader.text(raw['exit-status.txt']).strip() == '0', 'raw producer exit failed')
    start = datetime.fromisoformat(reader.text(raw['start.txt']).strip().replace('Z', '+00:00'))
    end = datetime.fromisoformat(reader.text(raw['end.txt']).strip().replace('Z', '+00:00'))
    require(start <= end, 'raw clock order differs')
    require(reader.text(raw['time.txt']).strip(), 'missing native time receipt')
    reader.text(raw['stderr'])
    return raw


def stock_finish(reader, receipt_pin, cwd):
    """Original graph/stock finish.json, not a synthesized replacement receipt."""
    receipt = reader.read(receipt_pin)
    require(receipt['status'] == 'finished' and receipt['exit'] == 0 and receipt['failure'] is None,
            'stock producer failed or incomplete')
    require(receipt['native_end_monotonic_ns'] >= receipt['native_launch_monotonic_ns'],
            'stock native monotonic clocks missing')
    raw = raw_closure(reader, receipt['pins'], receipt['recorder'], receipt['argv'], cwd)
    require(receipt['stdout'] == raw['stdout']['path'], 'stock stdout link differs')
    return dict(receipt=receipt_pin, argv=receipt['argv'], cwd=cwd, raw=raw,
                context=receipt['context'], result=raw['stdout'],
                status='retained-success-metadata-validated', scientific_bodies_read=False)


def uncertainty_command(reader, receipt_pin, cwd):
    """Original TARGET512 native command receipt and its retained dependency/runtime pins."""
    receipt = reader.read(receipt_pin)
    require(receipt['schema'] == 'uncertainty-feedback-command/1' and receipt['complete'] is True
            and receipt['exit_status'] == 0, 'TARGET512 native command failed or incomplete')
    directory = Path(receipt_pin['path']).parent
    raw = raw_closure(reader, receipt['raw_files'], directory, receipt['argv'], cwd)
    for item in receipt['inputs'] + [receipt['binary'], receipt['runtime'], receipt['dependency_manifest']]:
        stat_artifact(item)
    return dict(receipt=receipt_pin, argv=receipt['argv'], cwd=cwd, raw=raw, result=raw['stdout'],
                inputs=receipt['inputs'], binary=receipt['binary'], runtime=receipt['runtime'],
                dependency_manifest=receipt['dependency_manifest'],
                status='retained-success-metadata-validated', scientific_bodies_read=False)


def comparable_settings(argv):
    require('basecaller' in argv and '--read-ids' in argv, 'not a declared basecaller/read-set producer')
    offset = argv.index('basecaller')
    def option(name, default):
        return argv[argv.index(name) + 1] if name in argv else default
    return dict(model=argv[offset + 1], pod5=argv[offset + 2],
                parents=option('--read-ids', None), trim=option('--trim', 'all'),
                disable_read_splitting='--disable-read-splitting' in argv,
                emit_moves='--emit-moves' in argv, batchsize=option('--batchsize', '0'),
                min_qscore=option('--min-qscore', '0'))


def inventory(config):
    """Reuse provenance without replay; preserve all original parents and every incompatibility."""
    reader = Metadata()
    parent_text = None
    try:
        candidate_parents = reader.text(config['parents_pin']).splitlines()
        require(len(candidate_parents) == len(set(candidate_parents)) == 64, 'original64 parent universe differs')
        parent_text = candidate_parents
        return _inventory(config, reader, parent_text)
    except (ValueError, KeyError, OSError) as caught:
        # Invalid custody is an explicit unavailable result, never a positive-only replacement cohort.
        return dict(schema='stock-feedback-legacy-inventory/1', population_expected=64,
                    parent_universe_unavailable=parent_text is None, metadata_bytes=reader.bytes,
                    arms=[dict(arm=arm, status='unqualified', gaps=[str(caught)],
                               parents=[] if parent_text is None else
                               [dict(parent=p, status='unqualified') for p in parent_text])
                          for arm in ('native-hac', 'hac-context', 'stock-sup')],
                    scientific_bodies_read=False, producer_replayed=False, matched_three_arm_comparison=False,
                    biological_promotion=False, model_winner=None)


def _inventory(config, reader, parent_text):
    spec = config['legacy']
    snapshot = reader.read(spec['snapshot'])
    experiment = reader.read(spec['experiment'])
    stock = reader.read(spec['stock_inputs'])
    evidence = reader.read(spec['targeting_evidence'])
    require(snapshot['schema'] == 'flank-observer-input-snapshot/1'
            and snapshot['role'] == 'development', 'wrong original observation snapshot')
    require(snapshot['parents'] == config['parents_pin'] and snapshot['native'] == spec['native_sam'],
            'wrong original parent/native source')
    require(experiment['cohorts']['development']['ids'] == config['parents_pin']
            and experiment['cohorts']['development']['raw'] == config['pod5_pin'], 'POD5/parent experiment differs')
    require(snapshot['eligible'] == config['truth_domains']['eligible']
            and snapshot['reference'] == config['truth_domains']['reference']
            and snapshot['truth'] == config['truth_domains']['truth']
            and snapshot['confident'] == config['truth_domains']['confident'], 'fixed truth/mask domains differ')
    require(set(snapshot['eligible']) == {'100', '500'} and config['masks'] == [100, 500], 'mask set differs')
    domain_pins = [snapshot[k] for k in ('reference', 'truth', 'confident', 'pairer', 'observer', 'recorder')]
    domain_pins += list(snapshot['eligible'].values()) + list(snapshot['tools'].values())
    for item in domain_pins + snapshot['baseline_observation_pins']:
        stat_artifact(item)
    native = [stock_finish(reader, item, spec['native_cwd']) for item in spec['native_receipts']]
    for stage in native:
        for item in stage['context']['sources'] + stage['context']['executables']:
            stat_artifact(item)
    require(native[0]['context']['experiment'] == experiment['identity'], 'native experiment/source identity differs')
    settings = comparable_settings(native[0]['argv'])
    require(settings['model'] == experiment['model'] == spec['hac_model']
            and settings['pod5'] == config['pod5_pin']['path']
            and settings['parents'] == config['parents_pin']['path'], 'scored native model/raw/read set differs')
    require(settings['trim'] == config['settings']['trim']
            and settings['disable_read_splitting'] == config['settings']['disable_read_splitting']
            and settings['emit_moves'] == config['settings']['emit_moves']
            and settings['batchsize'] == str(config['settings']['batchsize'])
            and settings['min_qscore'] == str(config['settings']['min_qscore']), 'scored native settings differ')
    require(native[0]['result']['path'] in native[1]['argv'] and native[1]['result']['path'] in native[2]['argv']
            and native[2]['result'] == snapshot['native'], 'native basecall/map/SAM lineage differs')
    require(native[1]['argv'][0] == snapshot['tools']['dorado']['path']
            and native[1]['argv'][2] == snapshot['tools']['index']['path']
            and native[1]['argv'][-1] == config['mapper']['mm2_opts'], 'native mapper/index/options differ')
    require(config['mapper']['binary'] == snapshot['tools']['dorado']
            and config['mapper']['index'] == snapshot['tools']['index'], 'configured mapper tool pins differ')
    hac_config = next(p for p in experiment['model_pins'] if p['path'].endswith('/config.toml'))
    require(hac_config == spec['hac_config'], 'HAC config pin differs')
    for item in experiment['model_pins']:
        stat_artifact(item)
    context_map = reader.read(spec['context_map'])
    require(context_map['complete'] and context_map['parents'] == 64 and context_map['population_complete']
            and context_map['aliases'] == ['final_rerank', 'selected'], 'context complete parent/alias census differs')
    records = {name: uncertainty_command(reader, context_map['records'][name], spec['context_cwd'])
               for name in ('sam-to-bam', 'align', 'mapped-sam')}
    require(records['sam-to-bam']['inputs'] == [context_map['emitted']]
            and records['sam-to-bam']['result'] in records['align']['inputs']
            and records['align']['result'] in records['mapped-sam']['inputs']
            and records['mapped-sam']['result'] == context_map['mapped'], 'context emitted/map/SAM lineage differs')
    require(records['align']['binary'] == snapshot['tools']['dorado']
            and snapshot['tools']['index'] in records['align']['inputs']
            and records['align']['argv'][-1] == config['mapper']['mm2_opts'], 'context mapper/index/options differ')
    outer = reader.read(evidence['final_report_outer'])
    strict = reader.read(evidence['final_report_strict'])
    actual = reader.read(evidence['observations'])
    require(actual['schema'] == 'root-targeting-observation-actual-closure/1' and actual['complete'],
            'prior actual observation closure missing')
    require(any(unit['result'] == spec['context_map'] and unit['actual_exit'] == 0
                and unit['arm'] == 'final_rerank' and unit['phase'] == 'map' for unit in actual['units']),
            'context map is not the accepted actual producer')
    require(outer['schema'] == 'targeting-data-execution/1' and outer['complete']
            and outer['result'] == evidence['final_report'] == spec['prior_report']
            and outer['controller'] == evidence['observation_controller']
            and outer['source_manifest'] == evidence['scientific_source_manifest']
            and outer['unlock_only_after_terminal_and_raw_assertions'], 'accepted report/result closure differs')
    require(strict['complete'] and strict['outer'] == evidence['final_report_outer']
            and strict['parent']['parent_exit'] == 0 and strict['heavy_bodies_read'] is False,
            'prior report strict outer closure differs')
    for item in (evidence['final_report'], evidence['matrix_review'], evidence['actual_custody_review'],
                 context_map['emitted'], context_map['mapped']):
        stat_artifact(item)
    sup = stock_finish(reader, stock['cohorts']['development']['tiers']['sup']['basecall']['receipt'], spec['stock_cwd'])
    sup_settings = comparable_settings(sup['argv'])
    sup_config = next(p for p in stock['model_pins'] if p['path'] == spec['sup_config']['path'])
    require(sup_config == spec['sup_config'] and sup_settings['model'] == spec['sup_model'], 'SUP model/config differs')
    for item in stock['model_pins']:
        stat_artifact(item)
    gaps = [key + ' differs' for key in ('parents', 'trim', 'disable_read_splitting', 'emit_moves', 'batchsize')
            if sup_settings[key] != settings[key]]
    gaps += ['SUPv5.2 differs from HACv6 generation; no equal-generation SUP assumed',
             'no same-settings SUP paired100/500 or changed-footprint ALT observation exists in this closure']
    arms = [dict(arm='native-hac', status='retained-reuse-available', receipt=native, settings=settings),
            dict(arm='hac-context', status='retained-reuse-available', receipt=records,
                 mapped=context_map['mapped'], aliases=context_map['aliases']),
            dict(arm='stock-sup', status='incompatible-retained-control', receipt=sup, settings=sup_settings, gaps=gaps)]
    for arm in arms:
        arm['parents'] = [dict(parent=p, status=arm['status']) for p in parent_text]
    return dict(schema='stock-feedback-legacy-inventory/1', arms=arms, population=64,
                metadata_bytes=reader.bytes, scientific_bodies_read=False, producer_replayed=False,
                content_hash_rechecked=False, source_ready_for_metadata_admission=True,
                prior_report=evidence['final_report'], prior_report_outer=evidence['final_report_outer'],
                prior_report_strict=evidence['final_report_strict'], prior_matrix_review=evidence['matrix_review'],
                domains={k: snapshot[k] for k in ('parents', 'eligible', 'reference', 'truth', 'confident', 'pairer', 'observer')},
                model_configs=dict(hac=hac_config, sup=sup_config), matched_three_arm_comparison=False,
                biological_promotion=False, model_winner=None,
                limits=['metadata/stat closure reuses retained prior acceptance; no new scientific content verification',
                        'native mapper threads4 and context mapper threads2 are retained as actually accepted',
                        'current chemistry compatibility is declared from prior stock evidence, not remeasured'])
