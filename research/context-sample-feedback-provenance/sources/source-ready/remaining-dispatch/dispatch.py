"""Dispatch one fixed remaining resource block through the existing bounded CLI."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import uuid

ROOT = Path('/home/jake/Projects/nanopore_basecaller-context-feedback-sample')
READY = ROOT/'logs/context-sample-feedback/source-ready'
PROPOSAL = READY/'remaining-ready-proposal.json'
PROPOSAL_SHA = 'bf8e67988c292944727e92e75755eb43df05b92c057442b50df4451c1bba3ea1'
SCOPE = 'remaining'
CASE_COUNT = 346
CASE_IDS_SHA = 'a3feb48fa0265729370a01268e33a75e5ab05b093cc367bdd4a920349f7c2b85'
BLOCK_SIZE = 32
ENV = dict(UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv',
           UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', PYTHONDONTWRITEBYTECODE='1')
CAPS = dict(maximum_wall_seconds=300, maximum_output_bytes=4294967296,
            maximum_growth_bytes=104857600, memory_bytes=4294967296,
            address_space_bytes=8589934592, swap_bytes=0, cpu_quota=2)
META_LIMIT = 2*1024**2


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve(strict=True)
    require(path.stat().st_size <= META_LIMIT, 'Not a small metadata file: '+str(path))
    data = path.read_bytes()
    require(len(data) <= META_LIMIT, 'Metadata grew while reading')
    return dict(path=str(path), size=len(data), sha256=hashlib.sha256(data).hexdigest())


def checked(row):
    require(pin(row['path']) == row, 'Metadata pin differs: '+row['path'])
    return Path(row['path'])


def read(path):
    pin(path)
    return json.loads(Path(path).read_text())


def read_pin(row):
    return read(checked(row))


def fresh(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def expected_manifest():
    require(pin(PROPOSAL)['sha256'] == PROPOSAL_SHA, 'Fixed remaining proposal changed')
    proposal = read(PROPOSAL)
    cases = proposal['case_ids']
    case_hash = hashlib.sha256(json.dumps(cases, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(len(cases) == len(set(cases)) == proposal['count'] == CASE_COUNT
            and case_hash == CASE_IDS_SHA, 'Frozen complete remaining census differs')
    require(proposal['ordinary_count'] == 289 and proposal['private_count'] == 57, 'Remaining domain census differs')
    require(proposal['source_identity'] == '63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2', 'Frozen source differs')
    require(proposal['config']['sha256'] == 'be23fcfb3f38f9ad8c686ba9f7f4d4a8571088d1ed08baaa4015fcc43ef1cf15', 'Frozen config differs')
    require(proposal['qualification']['sha256'] == '9ebecc2b9037459c51d06879ca3a6bde95aff6c03eb1b36d006d516d1609cc47', 'Frozen qualification differs')
    require(proposal['prepared']['sha256'] == '274552e58bf492a150441494e7e6298e7d95ee25ef76a9c2161bd5b7544a64d1', 'Frozen preparation differs')
    require(proposal['first32_checkpoint']['sha256'] == '04689aab40043d0075c70e4e52c1580e512cc48842f499553b6a91fa4e1c9673', 'Frozen first32 checkpoint differs')
    for key in ('source_inventory', 'config', 'qualification', 'prepared', 'first32_checkpoint'):
        checked(proposal[key])
    for key, phase in (('qualification', 'qualify'), ('prepared', 'prepare'), ('first32_checkpoint', 'checkpoint')):
        outer = read_pin(proposal[key])
        worker = read_pin(outer['worker'])
        require(outer['complete'] is True and outer['phase'] == phase and worker['complete'] is True
                and worker['phase'] == phase and worker['sources_sha256'] == proposal['source_identity'],
                'Retained baseline metadata closure differs')
        for row in worker['files']:
            checked(row)
    previous = read(Path(proposal['first32_checkpoint']['path']).parent/'checkpoint.json')
    require(previous['scope'] == 'first32' and previous['case_ids'] == proposal['reused_completed_case_ids']
            and len(previous['case_ids']) == 22 and not set(cases) & set(previous['case_ids']), 'Retained case partition differs')
    units = []
    for case, item in zip(cases, proposal['units'], strict=True):
        slug = case.replace('/', '-')
        price = ROOT/('results/context-sample-feedback/sample-price-remaining-'+slug+'-1')
        infer = ROOT/('results/context-sample-feedback/sample-remaining-'+slug+'-1')
        require(item['case_id'] == case and item['price_output'] == str(price)
                and item['infer_output'] == str(infer), 'Case/output transposition')
        units.append(dict(case_id=case, price_output=str(price), infer_output=str(infer)))
    blocks = [dict(id=start//BLOCK_SIZE+1, start=start, end=min(start+BLOCK_SIZE, CASE_COUNT),
                   case_ids=cases[start:start+BLOCK_SIZE], count=len(cases[start:start+BLOCK_SIZE]))
              for start in range(0, CASE_COUNT, BLOCK_SIZE)]
    require([block['count'] for block in blocks] == [32]*10+[26], 'Fixed resource partition differs')
    return dict(schema='context-sample-feedback-remaining-dispatch/1', proposal=pin(PROPOSAL),
        source_identity=proposal['source_identity'], source_inventory=proposal['source_inventory'],
        config=proposal['config'], qualification=proposal['qualification'], prepared=proposal['prepared'],
        first32_checkpoint=proposal['first32_checkpoint'], units=units, blocks=blocks,
        block_size=BLOCK_SIZE, scope=SCOPE, no_per_block_checkpoint=True,
        caps=CAPS, disk_floor_bytes=32212254720, canonical_lock_nonblocking=True,
        keep_all_original_exclusions=True, no_availability_or_outcome_filter=True)


def price_result(value, case_id):
    require(value['schema'] == 'context-sample-feedback-price/1' and value['case_id'] == case_id
            and value['searches'] == 4 and value['tensor_loaded'] is False and value['truth_available'] is False,
            'Price identity or no-inference contract differs')
    size = value['maximum_raw_trace_bytes']
    require(type(size) is int and 0 < size < CAPS['maximum_growth_bytes']//2, 'Price exceeds strict raw headroom')
    return value


def accepted(output, phase, case_id, inputs, manifest):
    output = Path(output)
    outer = read(output/'execution-complete.json')
    require(outer['complete'] is True and outer['phase'] == phase
            and outer['whole_worker_cgroup_terminal'] is True, 'Outer completion is not accepted')
    for row in outer['files']:
        checked(row)
    terminal = read_pin(outer['terminal'])
    require(terminal['exit'] == 0 and terminal['error'] is None and terminal['owned_cgroup_terminal'] is True
            and terminal['canonical_lock_retained'] is True, 'Original whole unit failed')
    properties = terminal['proof'].get('unloaded_empty_group', terminal['proof'])['properties']
    require(properties.get('MainPID', '0') == properties.get('ControlPID', '0') == '0'
            and properties.get('Result') == 'success' and properties.get('ActiveState') == 'inactive', 'Worker terminal proof differs')
    cleanup_pin = next(row for row in outer['files'] if row['path'].endswith('/launcher-cleanup.json'))
    require(read_pin(cleanup_pin)['terminal'] is True, 'Launcher is not terminal')
    intake = read_pin(outer['worker_intake'])
    require(intake['verified'] is True and intake['parent_lock_retained'] is True, 'Worker intake differs')
    grant = read_pin(intake['admission'])
    require(grant['phase'] == phase and grant['scope'] == SCOPE and grant['case_id'] == case_id
            and grant['output'] == str(output) and grant['sources_sha256'] == manifest['source_identity']
            and grant['config'] == manifest['config'] and grant['qualification'] == manifest['qualification']
            and grant['inputs'] == inputs and all(grant[key] == value for key, value in CAPS.items()), 'Original admission differs')
    worker = read_pin(outer['worker'])
    require(worker['complete'] is True and worker['phase'] == phase and worker['scope'] == SCOPE
            and worker['sources_sha256'] == manifest['source_identity']
            and worker['qualification'] == manifest['qualification'] and worker['inputs'] == inputs, 'Worker source/input closure differs')
    for row in worker['files']:
        checked(row)
    summary = read(output/'summary.json')
    require(summary['phase'] == phase and summary['scope'] == SCOPE and summary['case_id'] == case_id, 'Summary identity differs')
    q0_binary = read(Path(manifest['first32_checkpoint']['path']).parent/'checkpoint.json')['binary']
    require(summary['binary'] == q0_binary, 'Qualified binary differs')
    require(len(summary['stages']) == len(summary['native']) == 1, 'Case producer census differs')
    stage = read_pin(summary['stages'][0])
    require(stage['exit'] == 0 and stage['failure'] is None and stage['projection_error'] is None
            and not stage['missing_raw'] and stage['name'] == 'sample-'+phase, 'Original native stage failed')
    require(set(stage['raw']) == {'command.sh', 'cwd.txt', 'start.txt', 'end.txt', 'exit-status.txt', 'stdout', 'stderr', 'time.txt'}, 'Raw-eight census differs')
    for row in stage['raw'].values():
        checked(row)
    require(shlex.split(checked(stage['raw']['command.sh']).read_text()) == stage['argv']
            and checked(stage['raw']['cwd.txt']).read_text().strip() == str(ROOT)
            and checked(stage['raw']['exit-status.txt']).read_text().strip() == '0', 'Original raw command/cwd/status differs')
    checked(stage['terminal'])
    require(read_pin(stage['group_cleanup'])['terminal'] is True, 'Native launcher is not terminal')
    native = read_pin(summary['native'][0])
    attempt = read_pin(native['attempt'])
    inventory = read_pin(manifest['source_inventory'])
    require(native['complete'] is True and attempt['argv'] == stage['argv'] and attempt['binary'] == q0_binary
            and attempt['source'] == native['source'] and native['source']['compiled_sources'] == inventory['sources'], 'Native source/binary/argv closure differs')
    value = read_pin(native['result'])
    if phase == 'price':
        return pin(output/'execution-complete.json'), price_result(value, case_id)
    flags = read_pin(manifest['config'])['qualification_flags']
    require(value['schema'] == 'context-sample-feedback-result/1' and value['case_id'] == case_id
            and value['historical_six_roles_verified'] is True and value['scalar_comparisons'] > 0
            and value['truth_available'] is False and all(value[key] is False for key in flags), 'Inference result contract differs')
    traces = read(output/'native-case/trace-archives.json')
    originals = {row['path']:row for row in native['files'] if row['path'].endswith('-trace.bin')}
    require(traces['lossless'] is True and len(traces['archives']) == len(originals) and len(originals) >= 2, 'Enabled trace archive census differs')
    for row in traces['archives']:
        require(originals.get(row['original']['path']) == row['original']
                and Path(row['archive']['path']).stat().st_size == row['archive']['size'], 'Trace metadata closure differs')
    return pin(output/'execution-complete.json'), value


def invoke(argv, directory):
    fresh(directory/'command.json', dict(argv=argv, cwd=str(ROOT), start_utc=datetime.now(timezone.utc).isoformat(), explicit_env=ENV))
    with (directory/'stdout').open('xb') as stdout, (directory/'stderr').open('xb') as stderr:
        process = subprocess.run(argv, cwd=ROOT, env=dict(os.environ, **ENV), stdout=stdout, stderr=stderr)
    fresh(directory/'closed.json', dict(exit=process.returncode, end_utc=datetime.now(timezone.utc).isoformat(),
          actual_subprocess_run_returned=True, stdout=str(directory/'stdout'), stderr=str(directory/'stderr')))
    require(process.returncode == 0, 'Existing CLI parent returned '+str(process.returncode)+'; retained '+str(directory))
    value = read(directory/'stdout')
    return value['completion']


def run_unit(phase, case_id, output, inputs, manifest, run_directory):
    output = Path(output)
    if output.exists():
        require((output/'execution-complete.json').is_file(), 'Partial existing output requires root coordination: '+str(output))
        completion, value = accepted(output, phase, case_id, inputs, manifest)
        return dict(completion=completion, value=value, reused=True)
    identifier = 'remaining-'+phase+'-'+('all' if case_id is None else case_id.split('/')[1])+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]
    directory = run_directory/identifier
    directory.mkdir()
    start = datetime.now(timezone.utc)
    grant = dict(schema='context-sample-feedback-admission/1', id=identifier, phase=phase, scope=SCOPE,
        config=manifest['config'], sources_sha256=manifest['source_identity'], output=str(output),
        qualification=manifest['qualification'], inputs=inputs, not_before_utc=start.isoformat(),
        expires_utc=(start+timedelta(seconds=300)).isoformat(),
        cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-sample-feedback-'+identifier+'.service',
        case_id=case_id, source_audit=None, arm=None, recovery=None, **CAPS)
    grant_path = directory/'admission.json'
    fresh(grant_path, grant)
    argv = ['uv', 'run', '--no-sync', 'python', 'scripts/context-sample-feedback.py', phase,
            '--scope', SCOPE, '--qualification', str(Path(manifest['qualification']['path']).parent)]
    if case_id is not None:
        argv += ['--case-id', case_id]
    for row in inputs:
        argv += ['--input', str(Path(row['path']).parent)]
    argv += ['--output', str(output), '--admission', str(grant_path)]
    print(json.dumps(dict(launch=dict(phase=phase, case_id=case_id, grant=pin(grant_path), argv=argv))), flush=True)
    completion = invoke(argv, directory)
    require(completion['path'] == str(output/'execution-complete.json'), 'Parent completion path transposed')
    checked(completion)
    checked_completion, value = accepted(output, phase, case_id, inputs, manifest)
    require(checked_completion == completion, 'Parent completion differs after acceptance')
    fresh(directory/'accepted.json', dict(completion=completion, metadata_only=True,
          trace_byte_revalidation_delegated_to_existing_bounded_cli=True))
    return dict(completion=completion, value=value, reused=False)


def selected_block(manifest, block_id):
    require(type(block_id) is int and 1 <= block_id <= len(manifest['blocks']), 'Explicit fixed block ID required')
    block = manifest['blocks'][block_id-1]
    units = manifest['units'][block['start']:block['end']]
    require([item['case_id'] for item in units] == block['case_ids'] and len(units) == block['count'], 'Block membership differs')
    return units


def preceding_accepted(manifest, block_id):
    start = manifest['blocks'][block_id-1]['start']
    for item in manifest['units'][:start]:
        price = pin(Path(item['price_output'])/'execution-complete.json')
        accepted(item['infer_output'], 'infer', item['case_id'],
                 [manifest['prepared'], price, manifest['first32_checkpoint']], manifest)


def dispatch(manifest, run_phase, block_id):
    products = []
    for item in selected_block(manifest, block_id):
        price = run_phase('price', item['case_id'], item['price_output'], [manifest['prepared']])
        price_result(price['value'], item['case_id'])
        infer = run_phase('infer', item['case_id'], item['infer_output'],
                          [manifest['prepared'], price['completion'], manifest['first32_checkpoint']])
        products.append(dict(case_id=item['case_id'], price=price, infer=infer))
    return dict(block_id=block_id, cases=products)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--block-id', type=int)
    args = parser.parse_args()
    require(pin(__file__)['sha256'] == args.source_sha256, 'Reviewed sequencer source changed')
    require(pin(args.manifest)['sha256'] == args.manifest_sha256, 'Dispatch manifest pin differs')
    manifest = read(args.manifest)
    require(manifest == expected_manifest(), 'Dispatch manifest differs from fixed proposal')
    if not args.execute:
        print(json.dumps(dict(plan_only=True, manifest=pin(args.manifest), sequencer=pin(__file__),
              cases=CASE_COUNT, native_units=CASE_COUNT*2, blocks=len(manifest['blocks']),
              selected_block=args.block_id, no_per_block_checkpoint=True, no_product_launched=True)))
        return
    block_units = selected_block(manifest, args.block_id)
    directory = ROOT/'logs/context-sample-feedback'/('remaining-dispatch-block-'+str(args.block_id)+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    directory.mkdir()
    fresh(directory/'start.json', dict(manifest=pin(args.manifest), sequencer=pin(__file__),
          utc=datetime.now(timezone.utc).isoformat(), block_id=args.block_id,
          case_ids=[item['case_id'] for item in block_units]))
    try:
        preceding_accepted(manifest, args.block_id)
        result = dispatch(manifest, lambda phase, case, output, inputs:run_unit(phase, case, output, inputs, manifest, directory), args.block_id)
    except BaseException as error:
        fresh(directory/'failed.json', dict(utc=datetime.now(timezone.utc).isoformat(), error=repr(error),
              further_execution_stopped=True, automatic_retry=False))
        raise
    fresh(directory/'complete.json', dict(complete=True, utc=datetime.now(timezone.utc).isoformat(),
          products=result, no_scientific_or_promotion_claim=True))
    print(json.dumps(dict(dispatch_completion=pin(directory/'complete.json'))), flush=True)


if __name__ == '__main__':
    main()
