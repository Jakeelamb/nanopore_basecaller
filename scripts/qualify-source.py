#!/usr/bin/env python3
"""Qualify the pinned ordinary-version source build through the frozen tools."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
from types import SimpleNamespace

import accuracy as a
import benchmark as b

ROOT = b.ROOT
BASE = ROOT / 'results/stock/controlled-20261022/plan.json'
INPUTS = ROOT / 'results/accuracy/controlled-20261022/inputs.json'
TRUTH = ROOT / 'results/accuracy/controlled-20261022-v1.1-frozen/truth-qualified.json'
BASE_ID = '1c995eba5d6454a6ef8a8fc6dcd767fd9e9aead811389da38f3906ddaf6815e0'
INPUT_ID = '66056a2fd8883969bd6ac6dbee9415e2189e1090bf29f25c7183d541c4b5461c'
FROZEN = {'benchmark.py': '39cb086598e5de0ae8c8d113f86c06a2d7721f34799e7cb258ea5dee744fb9fc',
          'accuracy.py': 'b5c6da542cdcb81689a93f5c7667e2933a91aedb5bb4f172e348c3de6ec3b49b'}
FULL_IDS = {f'full-{role}-{tier}' for role in ('development', 'validation') for tier in ('hac', 'sup')}
SMOKE_IDS = {'smoke-1-hac', 'smoke-1-sup'}
FIXTURE_ID = 'split-fixture-hac'
RESERVE = 30 * 1024**3
FULL_BUDGET = 9 * 1024**3
NATIVE_NAMES = ('command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'time.txt', 'exit-status.txt', 'stdout', 'stderr')
# Every mandatory value and every typed tag survives. Only tag/record order changes.
CANONICAL_AWK = r'''BEGIN { FS=OFS="\t" }
/^@/ { next }
NF < 11 { exit 65 }
{ for(i=12;i<=NF;i++) for(j=i+1;j<=NF;j++) if($i>$j) {t=$i;$i=$j;$j=t} print }'''
COMPARE_SH = r'''set -euo pipefail
mkdir -p -- "$4"
LC_ALL=C "$1" view "$2" | LC_ALL=C "$5" "$6" | LC_ALL=C "$7" -T "$4" > "$4/left.sam"
LC_ALL=C "$1" view "$3" | LC_ALL=C "$5" "$6" | LC_ALL=C "$7" -T "$4" > "$4/right.sam"
set +e
"$8" -s "$4/left.sam" "$4/right.sam"
status=$?
set -e
if ((status > 1)); then exit "$status"; fi
printf '%s\n' "$status" > "$4/cmp-exit.txt"
"$9" "$4/left.sam" "$4/right.sam"
printf 'left_bytes='; "${12}" -c < "$4/left.sam"
printf 'right_bytes='; "${12}" -c < "$4/right.sam"
if ((status == 1)); then
  set +e
  "${10}" -u "$4/left.sam" "$4/right.sam" | "${11}" -c 4096 > "$4/difference.txt"
  set -e
  "$9" "$4/difference.txt"
fi
"${13}" -- "$4/left.sam" "$4/right.sam"
printf 'cmp_exit=%s\n' "$status"
'''


def _frozen_tools():
    for name, expected in FROZEN.items():
        b.require(b.digest(ROOT / 'scripts' / name) == expected, f'Changed frozen {name}')


def _check_documents(pins, seen=None):
    """Audit the complete retained evidence graph without executing or writing."""
    seen = set() if seen is None else seen
    b.check_pins(pins)
    for item in pins:
        path = Path(item['path'])
        if path in seen or path.suffix != '.json':
            continue
        seen.add(path)
        if path.name == 'finish.json':
            starts = sorted(path.parent.parent.glob('*/start.json'))
            b.require(starts and starts[-1].parent == path.parent, 'Newer attempt invalidates retained evidence')
        def walk(value):
            if isinstance(value, dict):
                if isinstance(value.get('pins'), list):
                    _check_documents(value['pins'], seen)
                for key, child in value.items():
                    if key != 'pins':
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(b.read(path))


def _pin_declared(value, prefix=ROOT):
    path = prefix / value['path']
    actual = b.pin(path)
    b.require(actual['sha256'] == value['sha256'], f'Changed build evidence: {path}')
    if 'bytes' in value:
        b.require(actual['size'] == value['bytes'], f'Changed build size: {path}')
    return actual


def _build(path, base):
    """Accept the completed build handoff; no binary or source rewriting."""
    value = b.read(path)
    b.require(value['qualification_status'] == 'source_build_and_selected_cpu_contracts_passed', 'Build unfinished')
    source, build = value['source'], value['build']
    b.require(source['commit'] == b.SOURCE and source['canonical_clean_after_acceptance'], 'Wrong/dirty source custody')
    b.require(build['version'] == b.STOCK_VERSION, f'Ineligible source version: {build["version"]}')
    b.require(not any(build[key] for key in ('authored_source_patches', 'unsupported_compiler_bypass_flags', 'basecalling_components_disabled')), 'Unsupported source build changes')
    expected = {line.split()[1]: line.split()[0] for line in base['source_submodules'].splitlines()}
    actual = {item['path']: item['commit'] for item in source['recursive_submodules']}
    b.require(len(actual) == source['recursive_submodule_count'] == len(expected) and actual == expected, 'Changed source submodule inputs')
    acceptance = value['acceptance']
    b.require(acceptance['full_release_build'] == 'passed_582_tasks' and acceptance['version'] == 'passed_exact', 'Build acceptance missing')
    b.require(acceptance['cpu_tests']['status'] == 'passed' and acceptance['cpu_tests']['failures'] == acceptance['cpu_tests']['errors'] == 0, 'CPU build contracts failed')
    pins = [b.pin(path)]
    def collect(obj):
        if isinstance(obj, dict):
            if 'path' in obj and 'sha256' in obj:
                pins.append(_pin_declared(obj))
            else:
                for child in obj.values():
                    collect(child)
        elif isinstance(obj, list):
            for child in obj:
                collect(child)
    for key in ('build', 'dependency_archives', 'dependency_file_manifest', 'compiler_file_manifest', 'compiler_packages', 'runtime_elf_dependencies', 'acceptance'):
        collect(value[key])
    for key in ('vendor_transformations_evidence', 'copied_git_isolation_evidence'):
        pins.append(_pin_declared(source[key]))
        b.require(b.read(ROOT / source[key]['path'])['status'] == 'passed', 'Unqualified source transformations/isolation')
    transforms = b.read(ROOT / source['vendor_transformations_evidence']['path'])
    b.require(transforms['transformations'] == source['vendor_transformations'], 'Changed source transformations')
    for entry in source['vendor_transformations']:
        for patch in entry['patches']:
            pins.append(_pin_declared(patch, ROOT / source['canonical_path']))
    for key in ('dependency_file_manifest', 'compiler_file_manifest'):
        for line in (ROOT / value[key]['path']).read_text().splitlines():
            checksum, filename = line.split('  ', 1)
            pins.append(_pin_declared({'path': filename, 'sha256': checksum}))
    version_runs = []
    for receipt in value['receipts']:
        run = ROOT / receipt['path']
        b.require(all((run / name).is_file() for name in NATIVE_NAMES), 'Incomplete build receipt')
        b.require((run / 'exit-status.txt').read_text().strip() == str(receipt['exit_status']), 'Changed build exit')
        b.require(b.digest(run / 'command.sh') == receipt['command_sha256'], 'Changed build command')
        b.require((run / 'start.txt').read_text().strip() == receipt['started_utc'] and (run / 'end.txt').read_text().strip() == receipt['finished_utc'], 'Changed build clocks')
        b.require('Elapsed (wall clock)' in (run / 'time.txt').read_text(), 'Missing build resource clock')
        pins.extend(b.pin(run / name) for name in NATIVE_NAMES)
        if '-source-build-version-' in run.name and receipt['exit_status'] == 0:
            command = shlex.split((run / 'command.sh').read_text())
            if command[:2] == ['env', 'CUDA_VISIBLE_DEVICES=']:
                command = command[2:]
            if command == [build['binary']['path'], '--version'] or command == [str((ROOT / build['binary']['path']).resolve()), '--version']:
                b.require((run / 'stdout').read_text().strip() == b.STOCK_VERSION, 'Wrong retained source version')
                version_runs.append(str(run))
    b.require(version_runs and value['runtime_elf_dependencies'], 'Missing source version/runtime evidence')
    return {'manifest': b.pin(path), 'executable': _pin_declared(build['binary']), 'version': build['version'],
            'version_runs': version_runs, 'pins': list({p['path']: p for p in pins}.values())}


def _units(base, arm):
    wanted = SMOKE_IDS | (FULL_IDS | {FIXTURE_ID} if arm == 'source' else set())
    units = [copy.deepcopy(u) for u in base['units'] if u['id'] in wanted]
    b.require(len(units) == len(wanted) and {u['id'] for u in units} == wanted, 'Wrong allowed unit census')
    for unit in units:
        b.require(unit['tier'] in ('hac', 'sup'), 'Unknown tier')
        b.require(set(b.ids(unit['ids'])) == set(unit['parents']), 'Changed parent membership')
        if unit['id'] == FIXTURE_ID:
            b.require(unit['scope'] == 'fixture' and unit['tier'] == 'hac' and len(unit['parents']) == 1 and (ROOT / unit['asset']['path']).resolve() == (ROOT / base['config']['split_fixture']).resolve(), 'Wrong genuine split fixture')
            continue
        asset = unit['asset']
        b.require(asset['sample'] == 'HG002' and asset['role'] in ('development', 'validation'), 'Forbidden sample/role')
        b.require(unit['scope'] in ('smoke', 'full') and unit['id'] == (f'smoke-1-{unit["tier"]}' if unit['scope'] == 'smoke' else f'full-{asset["role"]}-{unit["tier"]}'), 'Wrong unit identity')
        full_unit = next(u for u in base['units'] if u['id'] == f'full-{asset["role"]}-{unit["tier"]}')
        b.require(asset == full_unit['asset'] and all(isinstance(samples, int) and samples > 0 and full_unit['parents'].get(parent) == samples for parent, samples in unit['parents'].items()), 'Changed parent signal samples/asset')
        if unit['scope'] == 'smoke':
            b.require(asset['role'] == 'development' and len(unit['parents']) == 32, 'Wrong development smoke')
    full = [u for u in units if u['scope'] == 'full']
    if full:
        role_sets = {role: set(next(u for u in full if u['asset']['role'] == role)['parents']) for role in ('development', 'validation')}
        b.require(not role_sets['development'] & role_sets['validation'], 'Cross-role parent overlap')
        for unit in full:
            peers = [u for u in full if u['asset']['role'] == unit['asset']['role']]
            b.require(len(peers) == 2 and peers[0]['parents'] == peers[1]['parents'], 'Unpaired parent samples')
    return units


def _policy(base, current):
    """Freeze the observed supported profile while preserving every other control."""
    b.require(base == b.CONTROLLED_POLICY, 'Unsupported qualification measurement policy')
    b.require(current in ('balanced', 'performance'), f'Unsupported observed platform profile: {current}')
    policy = copy.deepcopy(base)
    policy['platform_profile']['required'] = current
    return policy


def _seal(build_path, root):
    _frozen_tools()
    path = root / 'contract.json'
    if path.exists():
        contract = b.read(path)
        b.check_pins(contract['pins'])
        b.require(contract['sha256'] == b.identity({k: v for k, v in contract.items() if k != 'sha256'}), 'Changed qualification contract')
        if build_path:
            b.require(b.pin(build_path) == contract['build']['manifest'], 'Changed build handoff')
        return contract
    b.require(build_path is not None, '--build required for a new qualification')
    b.require(not root.exists() or not any(root.iterdir()), 'New qualification root must be empty')
    base = b.load_plan(BASE)
    b.require(base['sha256'] == BASE_ID, 'Foreign official baseline')
    profile_path = Path(base['config']['measurement_policy']['platform_profile']['path'])
    profile = profile_path.read_text().strip()
    policy = _policy(base['config']['measurement_policy'], profile)
    profile_observation = {'path': str(profile_path), 'value': profile, 'captured_utc': b.utc()}
    build = _build(build_path, base)
    inputs, truth = a.load_inputs(INPUTS), b.read(TRUTH)
    b.require(inputs['identity'] == INPUT_ID and inputs['config']['padding_and_confidence_erosion_bp'] == [100, 500], 'Changed fixed accuracy domains')
    b.require(truth['status'] == 'verified' and truth['inputs_identity'] == inputs['identity'] and a.source_pins() == truth['sources'], 'Unqualified frozen truth/scorer')
    b.check_pins(truth['pins'])
    root.mkdir(parents=True, exist_ok=True)
    version, version_pin = _native(root / 'build-admission', 'version', [build['executable']['path'], '--version'], {'executable': build['executable']})
    b.require(Path(version['stdout']).read_text().strip() == b.STOCK_VERSION, 'Ineligible actual source version')
    pins = [b.pin(BASE), b.pin(INPUTS), b.pin(TRUTH), b.pin(__file__), version_pin, *version['pins'], *build['pins']]
    plans = {}
    for arm in ('source', 'official-smoke'):
        plan = copy.deepcopy(base)
        plan.pop('sha256')
        plan.update(scope='source-qualification-' + arm, created_utc=b.utc(), units=_units(base, arm))
        plan['environment']['environment'] = {key: os.environ.get(key) for key in ('CUDA_VISIBLE_DEVICES', 'OMP_NUM_THREADS', 'LD_LIBRARY_PATH')}
        plan['environment']['cpu_affinity'] = sorted(os.sched_getaffinity(0))
        plan['environment']['qualification_capture_utc'] = b.utc()
        plan['environment']['qualification_platform_profile'] = copy.deepcopy(profile_observation)
        plan['config']['headroom_gib'] = 1
        plan['config']['measurement_policy'] = copy.deepcopy(policy)
        if arm == 'source':
            plan['config']['dorado'] = build['executable']['path']
            plan['tool_versions']['dorado'] = build['version'] + '\n'
        plan['pins'] += pins
        plan['qualification_lineage'] = {'base': b.pin(BASE), 'build': build['manifest'], 'arm': arm}
        plan['sha256'] = b.identity(plan)
        plan_path = root / arm / 'plan.json'
        b.write(plan_path, plan)
        b.load_plan(plan_path)
        plans[arm] = b.pin(plan_path)
        pins.append(plans[arm])
    tools = {name: b.pin(shutil.which(name)) for name in ('bash', 'awk', 'sort', 'cmp', 'sha256sum', 'diff', 'head', 'wc', 'rm')}
    pins.extend(tools.values())
    contract = {'schema': 1, 'created_utc': b.utc(), 'build': build, 'plans': plans, 'tools': tools,
                'base': b.pin(BASE), 'inputs': b.pin(INPUTS), 'borrowed_truth': b.pin(TRUTH),
                'measurement_policy': policy, 'platform_profile_observation': profile_observation,
                'budget': {'reserve_bytes': RESERVE, 'full_additional_bytes': FULL_BUDGET, 'full_admission_bytes': RESERVE + FULL_BUDGET},
                'canonical_awk': CANONICAL_AWK, 'comparator': COMPARE_SH, 'pins': pins}
    contract['sha256'] = b.identity(contract)
    b.write(path, contract)
    return contract


def _observation(plan, unit, root):
    path = root / 'units' / unit['id'] / 'observation.json'
    observation = b.read(path)
    b.require(observation['status'] == 'verified' and observation['plan'] == plan['sha256'] and observation['unit'] == unit['id'], 'Foreign/unverified observation')
    b.require(observation['verifier_sha256'] == FROZEN['benchmark.py'], 'Changed observation verifier')
    b.check_pins(observation['pins'])
    for item in observation['pins']:
        bound = Path(item['path'])
        if bound.name != 'finish.json':
            continue
        receipt = b.read(bound)
        b.require(receipt['status'] == 'finished' and receipt['exit'] == 0 and receipt['context'] == {'plan': plan['sha256'], 'unit': unit['id']}, 'Invalid bound native attempt')
        starts = sorted(bound.parent.parent.glob('*/start.json'))
        b.require(starts and starts[-1].parent == bound.parent, 'Newer native attempt invalidates observation')
        if 'measurement_policy' in plan['config']:
            b.measurement_evidence(receipt, {**plan['config']['measurement_policy'], 'cpu_affinity': plan['environment']['cpu_affinity']})
    for name in ('basecall', 'base-decode', 'aligned-decode', 'sort'):
        a.observation_stage(observation, root / 'units' / unit['id'], name)
    for name in ('base-decode', 'aligned-decode'):
        _, receipt = a.observation_stage(observation, root / 'units' / unit['id'], name)
        with Path(receipt['stdout']).open() as handle:
            for line in handle:
                if not line.startswith('@'):
                    break
                if line.startswith('@PG\t'):
                    program = b.header_record(line)
                    b.require(program.get('PN') != 'dorado' or program.get('VN') == b.STOCK_VERSION, 'Ineligible emitted Dorado program version')
    return observation


def _ensure_unit(plan, unit, root, retry=None):
    if (root / 'units' / unit['id'] / 'observation.json').exists():
        return _observation(plan, unit, root)
    b.admission(plan['config'])
    return b.run_unit(plan, unit, root, retry=retry)


def _native(root, name, argv, context, execute=True, retry=False):
    result = b.stage(root, name, list(map(str, argv)), context, execute=execute, retry=retry, reserve=RESERVE)
    paths = [p for p in (root / name).glob('*/finish.json') if b.read(p) == result]
    b.require(len(paths) == 1, 'Ambiguous retained native receipt')
    return result, b.pin(paths[0])


def _compare(root, name, left, right, config, tools, execute=True):
    directory = root / name
    argv = [tools['bash']['path'], '-c', COMPARE_SH, '--', config['samtools'], left, right,
            directory / 'canonical', tools['awk']['path'], CANONICAL_AWK,
            *[tools[key]['path'] for key in ('sort', 'cmp', 'sha256sum', 'diff', 'head', 'wc', 'rm')]]
    context = {'left': b.pin(left), 'right': b.pin(right), 'tools': tools, 'canonical': CANONICAL_AWK}
    result, receipt = _native(root, name, argv, context, execute)
    scratch = directory / 'canonical'
    status = int((scratch / 'cmp-exit.txt').read_text())
    b.require(status in (0, 1) and Path(result['stdout']).read_text().endswith(f'cmp_exit={status}\n'), 'Malformed comparator result')
    lines = Path(result['stdout']).read_text().splitlines()
    canonical = {}
    for index, side in enumerate(('left', 'right')):
        checksum, filename = lines[index].split('  ', 1)
        b.require(re.fullmatch('[0-9a-f]{64}', checksum) and filename == str(scratch / (side + '.sam')), 'Malformed canonical digest')
        b.require(lines[index + 2].startswith(side + '_bytes='), 'Missing canonical stream size')
        canonical[side] = {'sha256': checksum, 'size': int(lines[index + 2].split('=', 1)[1])}
    if status == 1:
        b.require(lines[4] == f'{b.digest(scratch / "difference.txt")}  {scratch / "difference.txt"}', 'Changed difference diagnostic')
    pins = [b.pin(p) for p in scratch.iterdir() if p.is_file()]
    return {'status': 'equal' if status == 0 else 'different', 'cmp_exit': status,
            'left': context['left'], 'right': context['right'], 'canonical': canonical,
            'pins': [receipt, *result['pins'], *pins]}


def _qualify_smoke(plan, root):
    path = root / 'qualification.json'
    if not path.exists():
        b.qualify(plan, root)
    value = b.read(path)
    b.require(value['status'] == 'verified' and value['plan'] == plan['sha256'] and value['verifier_sha256'] == FROZEN['benchmark.py'], 'Wrong smoke qualification')
    b.check_pins(value['pins'])
    if any(u['id'] == FIXTURE_ID for u in plan['units']):
        fixture = {row['control'] for row in value['controls'] if row['unit'] == FIXTURE_ID}
        b.require({'split-sp', 'split-pi'} <= fixture, 'Genuine split controls not exercised')
    return b.pin(path)


def _parity(plan, root):
    path = root / 'source-index-parity.json'
    if path.exists():
        value = b.read(path)
        b.parity_evidence(value, plan['config'])
        return b.pin(path)
    entries = []
    for unit in [u for u in plan['units'] if u['scope'] == 'smoke']:
        observation = _observation(plan, unit, root)
        directory = root / 'units' / unit['id']
        bound = {name: a.observation_stage(observation, directory, name)[1] for name in ('basecall', 'base-decode', 'align', 'aligned-decode')}
        calls = bound['basecall']['stdout']
        context = {'plan': plan['sha256'], 'unit': unit['id'], 'input': b.pin(calls)}
        fasta, fpin = _native(root / 'index-parity', unit['tier'] + '-fasta', [plan['config']['dorado'], 'aligner', ROOT / plan['config']['reference'], calls, '--threads', '16', '--no-sort', '--mm2-opts', '-x lr:hq -I 16G --eqx -Y'], context)
        decoded, dpin = _native(root / 'index-parity', unit['tier'] + '-decode', [plan['config']['samtools'], 'view', '-h', fasta['stdout']], {'bam': b.pin(fasta['stdout'])})
        base = b.parse_sam(bound['base-decode']['stdout'], Path(plan['config']['models'][unit['tier']]).name, unit['parents'])
        mapped = b.parse_sam(decoded['stdout'], Path(plan['config']['models'][unit['tier']]).name, unit['parents'], plan['dictionary'], base['children'])
        stages = [*bound.values(), fasta, decoded]
        pins = [fpin, dpin, *[p for stage in stages for p in stage['pins']]]
        entries.append({'tier': unit['tier'], 'status': 'verified', 'model': Path(plan['config']['models'][unit['tier']]).name,
                        'mapped_records': mapped['metrics']['mapped_records'], 'input': b.pin(calls),
                        'input_decode': b.pin(bound['base-decode']['stdout']),
                        'outputs': [b.pin(bound['align']['stdout']), b.pin(bound['aligned-decode']['stdout']), b.pin(fasta['stdout']), b.pin(decoded['stdout'])],
                        'producer_runs': list(dict.fromkeys(stage['recorder'] for stage in stages)),
                        'input_producer_run': bound['basecall']['recorder'], 'pins': pins})
    value = {'status': 'verified', 'dictionary': plan['dictionary'], 'reference_sha256': b.digest(ROOT / plan['config']['reference']), 'parity': entries}
    b.parity_evidence(value, plan['config'])
    b.write(path, value)
    return b.pin(path)


def _score(root, phase, plan_path, scope, retry=False):
    receipt_path = root / 'score-evidence' / (phase + '.json')
    if receipt_path.exists():
        value = b.read(receipt_path)
        _check_documents(value['pins'])
        return b.pin(receipt_path)
    attempts = root / 'accuracy' / phase
    b.require(retry or not attempts.exists() or not any(attempts.iterdir()), 'Failed/interrupted accuracy phase; --retry accuracy requires a fresh attempt root')
    analysis = attempts / str(time.time_ns())
    analysis.mkdir(parents=True)
    shutil.copyfile(TRUTH, analysis / 'truth-qualified.json')
    b.require(b.pin(analysis / 'truth-qualified.json')['sha256'] == b.digest(TRUTH), 'Borrowed truth bytes differ')
    summary = a.score(SimpleNamespace(inputs=INPUTS, plan=plan_path, analysis_root=analysis, scope=scope), execute=True)
    report = analysis / ('report-' + summary['plan'] + '-' + scope + '.json')
    pins = [b.pin(TRUTH), b.pin(analysis / 'truth-qualified.json'), b.pin(report)]
    pins.extend(p for unit in summary['units'] for p in unit['pins'])
    for unit in summary['units']:
        pins.append(b.pin(analysis / 'scores' / summary['plan'] / unit['unit'] / str(unit['padding']) / 'observation.json'))
        stage_root = analysis / 'score-stages' / summary['plan'] / unit['unit'] / str(unit['padding'])
        matches = [p for p in stage_root.glob('*/finish.json') if b.read(p) == unit['producer']]
        b.require(len(matches) == 1, 'Ambiguous retained accuracy producer')
        pins.append(b.pin(matches[0]))
    b.write(receipt_path, {'status': 'verified', 'scope': scope, 'plan': summary['plan'], 'analysis_root': str(analysis), 'pins': pins})
    return b.pin(receipt_path)


def _preflight(contract, root, retry=False):
    """Real retained official producers prove the adapter before a GPU launch."""
    path = root / 'handoff.json'
    if path.exists():
        value = b.read(path)
        b.check_pins(value['pins'])
        return b.pin(path)
    base = b.load_plan(BASE)
    pins, controls = [], []
    retained_qualification = BASE.parent / 'qualification.json'
    qualified = b.read(retained_qualification)
    b.require(qualified['status'] == 'verified' and qualified['plan'] == BASE_ID and qualified['verifier_sha256'] == FROZEN['benchmark.py'], 'Retained genuine controls unqualified')
    b.check_pins(qualified['pins'])
    required_controls = {'foreign', 'duplicate', 'model', 'truncated', 'reference', 'NM', 'removed-parent'}
    b.require(required_controls <= {row['control'] for row in qualified['controls'] if row['unit'] == 'smoke-1-hac'}, 'Missing genuine smoke rejection controls')
    b.require({'split-pi', 'split-sp'} <= {row['control'] for row in qualified['controls'] if row['unit'] == FIXTURE_ID}, 'Missing genuine split rejection controls')
    pins.extend([b.pin(retained_qualification), *qualified['pins']])
    for uid in ('smoke-1-hac', FIXTURE_ID):
        unit = next(u for u in base['units'] if u['id'] == uid)
        observation = _observation(base, unit, BASE.parent)
        directory = BASE.parent / 'units' / uid
        source = Path(a.observation_stage(observation, directory, 'base-decode')[1]['stdout'])
        parsed = b.parse_sam(source, Path(base['config']['models'][unit['tier']]).name, unit['parents'])
        if uid == FIXTURE_ID:
            b.require(parsed['metrics']['split_parents'] > 0, 'Genuine preflight fixture has no split child')
        text = source.read_text()
        headers = [line for line in text.splitlines() if line.startswith('@')]
        records = [line.split('\t') for line in text.splitlines() if not line.startswith('@')]
        variants = {'self': text,
                    'permutation': '\n'.join(headers + ['\t'.join(row[:11] + list(reversed(row[11:]))) for row in reversed(records)]) + '\n'}
        for name, column, replacement in [('sequence', 9, 'N'), ('quality', 10, '!'), ('child', 0, '00000000-0000-0000-0000-000000000000')]:
            changed = copy.deepcopy(records)
            changed[0][column] = (replacement if column == 0 else (replacement if changed[0][column][0] != replacement else ('A' if column == 9 else '"')) + changed[0][column][1:])
            variants[name] = '\n'.join(headers + ['\t'.join(row) for row in changed]) + '\n'
        variants['removed'] = '\n'.join(headers + ['\t'.join(row) for row in records[1:]]) + '\n'
        if uid == FIXTURE_ID:
            variants['split'] = re.sub(r'sp:i:\d+', 'sp:i:999999999', text, count=1)
        for name, mutant in variants.items():
            sam = root / 'handoff-controls' / uid / (name + '.sam')
            sam.parent.mkdir(parents=True, exist_ok=True)
            sam.write_text(mutant)
            compared = _compare(root / 'handoff-controls' / uid, name, source, sam, base['config'], contract['tools'])
            expected = 'equal' if name in ('self', 'permutation') else 'different'
            b.require(compared['status'] == expected, 'Comparator control failed: ' + name)
            pins.extend([b.pin(sam), *compared['pins']])
            controls.append({'unit': uid, 'control': name, 'status': expected})
        wrong = root / 'handoff-controls' / uid / 'wrong-version.sam'
        wrong.write_text(text.replace('VN:' + b.STOCK_VERSION, 'VN:ineligible'))
        try:
            b.parse_sam(wrong, Path(base['config']['models'][unit['tier']]).name, unit['parents'])
        except ValueError as exc:
            b.require('Dorado version' in str(exc), 'Wrong version rejection reason')
        else:
            raise ValueError('Wrong-version control accepted')
        pins.extend([b.pin(wrong), b.pin(source), b.pin(directory / 'observation.json')])
    # Genuine aligned source, corrupted only after its original pin was bound.
    unit = next(u for u in base['units'] if u['id'] == 'smoke-1-hac')
    observation = _observation(base, unit, BASE.parent)
    aligned = Path(a.observation_stage(observation, BASE.parent / 'units' / unit['id'], 'aligned-decode')[1]['stdout'])
    copied = root / 'handoff-controls' / 'decoder' / 'aligned-decode' / '001' / 'finish.json'
    copied.parent.mkdir(parents=True, exist_ok=True)
    sam = copied.parent / 'aligned.sam'
    shutil.copyfile(aligned, sam)
    b.write(copied, {'stdout': str(sam), 'pins': [b.pin(sam)]})
    bound = {'pins': [b.pin(copied), b.pin(sam)]}
    sam.write_text(sam.read_text() + '\n')
    try:
        a.observation_stage(bound, copied.parent.parent.parent, 'aligned-decode')
    except ValueError as exc:
        b.require('not bound' in str(exc), 'Wrong decoder rejection reason')
    else:
        raise ValueError('Changed decoder accepted')
    pins.append(_score(root, 'retained-official-smoke', BASE, 'smoke', retry))
    evidence = b.read(root / 'score-evidence' / 'retained-official-smoke.json')
    rescored_report = Path(evidence['analysis_root']) / f'report-{BASE_ID}-smoke.json'
    accepted_report = TRUTH.parent / f'report-{BASE_ID}-smoke.json'
    rescored, accepted = b.read(rescored_report), b.read(accepted_report)
    for result in rescored['units']:
        peer = next(row for row in accepted['units'] if (row['unit'], row['padding']) == (result['unit'], result['padding']))
        b.require(result['score'] == peer['score'], 'Genuine score handoff changed deterministic metrics')
        for name in ('parents.tsv', 'children.tsv', 'homopolymer.tsv', 'qscore.tsv', 'context.tsv', 'alternate-alignments.tsv'):
            pair = [next(p for p in row['pins'] if Path(p['path']).name == name) for row in (result, peer)]
            b.check_pins(pair)
            b.require(pair[0]['sha256'] == pair[1]['sha256'], 'Genuine score handoff changed native table: ' + name)
            pins.extend(pair)
    pins.extend([b.pin(rescored_report), b.pin(accepted_report)])
    # A genuine aligned molecule becomes foreign to the actual Rust scorer.
    foreign = root / 'handoff-controls' / 'foreign.sam'
    lines = aligned.read_text().splitlines()
    for index, line in enumerate(lines):
        if not line.startswith('@'):
            fields = line.split('\t')
            fields[0] = '00000000-0000-0000-0000-000000000000'
            fields[11:] = ['pi:Z:' + fields[0] if tag.startswith('pi:Z:') else tag for tag in fields[11:]]
            lines[index] = '\t'.join(fields)
            break
    foreign.write_text('\n'.join(lines) + '\n')
    truth, inputs = b.read(TRUTH), a.load_inputs(INPUTS)
    out = root / 'handoff-controls' / 'foreign-score'
    argv = [truth['binary'], 'score', '--reference', inputs['reference'], '--eligible', Path(truth['truth']['HG002-100']['directory']) / 'eligible.bed', '--sam', foreign, '--parents', unit['ids'], '--output', out, '--min-mapq', '30']
    control = root / 'handoff-controls' / 'rust'
    prior = sorted((control / 'foreign-parent').glob('*/finish.json'))
    if not prior:
        try:
            _native(control, 'foreign-parent', argv, {'foreign': b.pin(foreign), 'truth': b.pin(TRUTH)})
        except ValueError:
            pass
        prior = sorted((control / 'foreign-parent').glob('*/finish.json'))
    b.require(bool(prior), 'Missing Rust rejection attempt')
    failure = b.read(prior[-1])
    b.require(failure['status'] == 'command_failed' and failure['exit'] != 0 and 'parent' in (Path(failure['recorder']) / 'stderr').read_text().lower(), 'Rust foreign-parent control did not reject foreign parent')
    b.check_pins(failure['pins'])
    pins.extend([b.pin(foreign), b.pin(prior[-1]), *failure['pins']])
    b.write(path, {'status': 'verified', 'controls': controls, 'rust_foreign_parent': 'rejected', 'decoder_mutation': 'rejected', 'pins': pins})
    return b.pin(path)


def _pairs(contract, root, scope):
    source_path = Path(contract['plans']['source']['path'])
    source = b.load_plan(source_path)
    official_path = Path(contract['plans']['official-smoke']['path']) if scope == 'smoke' else BASE
    official = b.load_plan(official_path)
    outcomes = []
    for unit in [u for u in source['units'] if u['scope'] == scope]:
        other = next(u for u in official['units'] if u['id'] == unit['id'])
        b.require(unit == other, 'Unpaired source/official unit')
        observations = [_observation(plan, unit, path.parent) for plan, path in ((source, source_path), (official, official_path))]
        checks = {}
        for label, stage in (('basecall', 'basecall'), ('alignment', 'sort')):
            files = [a.observation_stage(obs, path.parent / 'units' / unit['id'], stage)[1]['stdout'] for obs, path in zip(observations, (source_path, official_path))]
            checks[label] = _compare(root / 'comparisons' / scope, unit['id'] + '-' + label, *files, source['config'], contract['tools'])
        ledgers = [b.pin(path.parent / 'units' / unit['id'] / 'parents.tsv') for path in (source_path, official_path)]
        checks['parents'] = {'status': 'equal' if ledgers[0]['sha256'] == ledgers[1]['sha256'] else 'different', 'pins': ledgers}
        outcomes.append({'unit': unit['id'], 'checks': checks})
    path = root / ('comparison-' + scope + '.json')
    b.write(path, {'status': 'equal' if all(check['status'] == 'equal' for item in outcomes for check in item['checks'].values()) else 'different', 'units': outcomes,
                   'pins': [pin for item in outcomes for check in item['checks'].values() for pin in check['pins']]})
    return b.pin(path)


def _accuracy_comparison(contract, root, scope):
    source_evidence = b.read(root / 'score-evidence' / ('source-' + scope + '.json'))
    source_plan = b.read(contract['plans']['source']['path'])['sha256']
    source_report = Path(source_evidence['analysis_root']) / f'report-{source_plan}-{scope}.json'
    if scope == 'smoke':
        official_evidence = b.read(root / 'score-evidence' / 'official-smoke-smoke.json')
        official_plan = b.read(contract['plans']['official-smoke']['path'])['sha256']
        official_report = Path(official_evidence['analysis_root']) / f'report-{official_plan}-smoke.json'
    else:
        official_report = TRUTH.parent / f'report-{BASE_ID}-full.json'
    source, official = b.read(source_report), b.read(official_report)
    rows, pins = [], [b.pin(source_report), b.pin(official_report)]
    for unit in source['units']:
        peer = next(row for row in official['units'] if (row['unit'], row['padding']) == (unit['unit'], unit['padding']))
        b.require(unit['sample'] == peer['sample'] == 'HG002' and unit['tier'] == peer['tier'], 'Foreign accuracy comparator')
        b.check_pins(peer['pins'])
        fields = sorted(set(unit['score']) | set(peer['score']))
        differences = [key for key in fields if unit['score'].get(key) != peer['score'].get(key)]
        tables = {}
        for name in ('score.json', 'parents.tsv', 'children.tsv', 'homopolymer.tsv', 'qscore.tsv', 'context.tsv', 'alternate-alignments.tsv'):
            pair = [next(p for p in record['pins'] if Path(p['path']).name == name) for record in (unit, peer)]
            pins.extend(pair)
            tables[name] = {'status': 'equal' if pair[0]['sha256'] == pair[1]['sha256'] else 'different', 'source': pair[0], 'official': pair[1]}
        rows.append({'unit': unit['unit'], 'padding': unit['padding'], 'different_score_fields': differences,
                     'source_score': unit['score'], 'official_score': peer['score'], 'tables': tables})
    path = root / ('accuracy-comparison-' + scope + '.json')
    b.write(path, {'status': 'equal' if all(not row['different_score_fields'] and all(t['status'] == 'equal' for t in row['tables'].values()) for row in rows) else 'different', 'units': rows, 'pins': pins})
    return b.pin(path)


def _audit(root):
    _frozen_tools()
    contract = b.read(root / 'contract.json')
    b.require(contract['sha256'] == b.identity({k: v for k, v in contract.items() if k != 'sha256'}), 'Changed qualification contract')
    b.check_pins(contract['pins'])
    report = b.read(root / 'qualification.json')
    b.require(report['contract'] == contract['sha256'], 'Foreign qualification report')
    _check_documents(report['pins'])
    for arm, pinned in contract['plans'].items():
        plan = b.load_plan(pinned['path'])
        for unit in plan['units']:
            if unit['scope'] != 'full' or report['through'] == 'full':
                _observation(plan, unit, Path(pinned['path']).parent)
    return report


def qualify(build_path, root, through='smoke', retry=None):
    contract = _seal(build_path, root)
    pins = [b.pin(root / 'contract.json'), _preflight(contract, root, retry == 'accuracy')]
    for arm in ('official-smoke', 'source'):
        plan_path = Path(contract['plans'][arm]['path'])
        plan = b.load_plan(plan_path)
        native_root = plan_path.parent
        for unit in plan['units']:
            if unit['scope'] in ('smoke', 'fixture'):
                _ensure_unit(plan, unit, native_root, retry.removeprefix(arm + ':') if retry and retry.startswith(arm + ':') else None)
        pins.append(_qualify_smoke(plan, native_root))
    source_path = Path(contract['plans']['source']['path'])
    source = b.load_plan(source_path)
    pins.append(_parity(source, source_path.parent))
    pins.append(_pairs(contract, root, 'smoke'))
    for arm in ('official-smoke', 'source'):
        pins.append(_score(root, arm + '-smoke', Path(contract['plans'][arm]['path']), 'smoke', retry == 'accuracy'))
    pins.append(_accuracy_comparison(contract, root, 'smoke'))
    if through == 'full':
        remaining = [u for u in source['units'] if u['scope'] == 'full' and not (source_path.parent / 'units' / u['id'] / 'observation.json').exists()]
        if remaining:
            b.require(shutil.disk_usage(ROOT).free >= RESERVE + FULL_BUDGET, 'Full qualification requires 39 GiB free (30 GiB reserve plus 9 GiB allocation)')
        for index, unit in enumerate(remaining):
            b.require(shutil.disk_usage(ROOT).free >= RESERVE + FULL_BUDGET * (len(remaining) - index) / 4, 'Remaining full allocation unavailable')
            _ensure_unit(source, unit, source_path.parent, retry.removeprefix('source:') if retry and retry.startswith('source:') else None)
        pins.append(_pairs(contract, root, 'full'))
        if not (root / 'score-evidence' / 'source-full.json').exists():
            b.require(shutil.disk_usage(ROOT).free >= RESERVE + 4 * 1024**3, 'Full score allocation unavailable')
        pins.append(_score(root, 'source-full', source_path, 'full', retry == 'accuracy'))
        pins.append(_accuracy_comparison(contract, root, 'full'))
    comparisons = {scope: b.read(root / ('comparison-' + scope + '.json'))['status'] for scope in (('smoke', 'full') if through == 'full' else ('smoke',))}
    comparisons.update({'accuracy_' + scope: b.read(root / ('accuracy-comparison-' + scope + '.json'))['status'] for scope in (('smoke', 'full') if through == 'full' else ('smoke',))})
    observations = []
    for arm, pinned in contract['plans'].items():
        plan = b.load_plan(pinned['path'])
        for unit in plan['units']:
            if unit['scope'] in ('smoke', 'fixture') or through == 'full':
                observation = _observation(plan, unit, Path(pinned['path']).parent)
                pins.append(b.pin(Path(pinned['path']).parent / 'units' / unit['id'] / 'observation.json'))
                if arm == 'source' and unit['scope'] != 'fixture':
                    observations.append(observation)
    report = {'schema': 1, 'contract': contract['sha256'], 'through': through, 'build_custody': 'verified', 'version_eligibility': 'verified',
              'native_smoke': 'verified', 'source_index_compatibility': 'verified', 'fixed_domain_accuracy': 'verified',
              'source_genuine_split_controls': 'verified', 'official_smoke_split_controls': 'not_exercised: no fixture in official smoke arm',
              'full_native': 'verified' if through == 'full' else 'not_run', 'exact_equivalence': comparisons,
              'complete_input_processing': 'verified' if all(o['complete_work_qualification'] == 'verified' for o in observations) else 'unavailable: absent parents or loader diagnostics',
              'comparative_performance': 'not_run', 'pins': pins}
    b.write(root / 'qualification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--through', choices=('smoke', 'full'), default='smoke')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--retry', help='source:UNIT:STAGE, official-smoke:UNIT:STAGE, or accuracy (fresh score attempt)')
    args = parser.parse_args()
    root = args.output.resolve()
    b.require(root.is_relative_to(ROOT / 'results/source-qualification'), 'Output belongs under results/source-qualification')
    lock_path = ROOT / 'results/stock/host.lock'
    with lock_path.open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = _audit(root) if args.verify_only else qualify(args.build, root, args.through, args.retry)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if 'different' in result['exact_equivalence'].values() else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
