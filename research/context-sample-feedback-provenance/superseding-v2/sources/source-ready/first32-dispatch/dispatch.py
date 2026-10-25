"""Dispatch the fixed first32 units through the existing bounded CLI, serially."""
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
PROPOSAL = READY/'first32-ready-proposal.json'
PROPOSAL_SHA = '27678857219ef30053562acdb7c60e93157ff319bbb79902f03b6ebca4a694f7'
IDS = (1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 20, 22, 23, 24, 25, 27, 30, 31)
CASES = tuple('ordinary/'+str(number)+'/ordinary' for number in IDS)
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
    require(pin(PROPOSAL)['sha256'] == PROPOSAL_SHA, 'Fixed first32 proposal changed')
    proposal = read(PROPOSAL)
    require(tuple(proposal['case_ids']) == CASES and proposal['count'] == 21, 'Frozen case census differs')
    require(proposal['source_identity'] == '63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2', 'Frozen source differs')
    require(proposal['config']['sha256'] == 'be23fcfb3f38f9ad8c686ba9f7f4d4a8571088d1ed08baaa4015fcc43ef1cf15', 'Frozen config differs')
    require(proposal['qualification']['sha256'] == '9ebecc2b9037459c51d06879ca3a6bde95aff6c03eb1b36d006d516d1609cc47', 'Frozen qualification differs')
    require(proposal['prepared']['sha256'] == '274552e58bf492a150441494e7e6298e7d95ee25ef76a9c2161bd5b7544a64d1', 'Frozen preparation differs')
    require(proposal['query0_checkpoint']['sha256'] == 'e10ddc6f255277e14d03c65b0cb79ac8331a64c2b7d178e291008b5fa9e2a85a', 'Frozen query0 checkpoint differs')
    for key in ('source_inventory', 'config', 'qualification', 'prepared', 'query0_checkpoint'):
        checked(proposal[key])
    for key, phase in (('qualification', 'qualify'), ('prepared', 'prepare'), ('query0_checkpoint', 'checkpoint')):
        outer = read_pin(proposal[key])
        worker = read_pin(outer['worker'])
        require(outer['complete'] is True and outer['phase'] == phase and worker['complete'] is True
                and worker['phase'] == phase and worker['sources_sha256'] == proposal['source_identity'],
                'Retained baseline metadata closure differs')
        for row in worker['files']:
            checked(row)
    units = []
    for number, item in zip(IDS, proposal['units'], strict=True):
        price = ROOT/('results/context-sample-feedback/sample-price-first32-ordinary-'+str(number)+'-1')
        infer = ROOT/('results/context-sample-feedback/sample-first32-ordinary-'+str(number)+'-1')
        require(item['case_id'] == 'ordinary/'+str(number)+'/ordinary'
                and item['price_output'] == str(price) and item['infer_output'] == str(infer), 'Case/output transposition')
        units.append(dict(case_id=item['case_id'], price_output=str(price), infer_output=str(infer)))
    return dict(schema='context-sample-feedback-first32-dispatch/1', proposal=pin(PROPOSAL),
        source_identity=proposal['source_identity'], source_inventory=proposal['source_inventory'],
        config=proposal['config'], qualification=proposal['qualification'], prepared=proposal['prepared'],
        query0_checkpoint=proposal['query0_checkpoint'], units=units,
        checkpoint_output=str(ROOT/'results/context-sample-feedback/sample-checkpoint-first32-1'),
        checkpoint_inputs=[str(ROOT/'results/context-sample-feedback/sample-query0-1')]+[item['infer_output'] for item in units],
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
    require(grant['phase'] == phase and grant['scope'] == 'first32' and grant['case_id'] == case_id
            and grant['output'] == str(output) and grant['sources_sha256'] == manifest['source_identity']
            and grant['config'] == manifest['config'] and grant['qualification'] == manifest['qualification']
            and grant['inputs'] == inputs and all(grant[key] == value for key, value in CAPS.items()), 'Original admission differs')
    worker = read_pin(outer['worker'])
    require(worker['complete'] is True and worker['phase'] == phase and worker['scope'] == 'first32'
            and worker['sources_sha256'] == manifest['source_identity']
            and worker['qualification'] == manifest['qualification'] and worker['inputs'] == inputs, 'Worker source/input closure differs')
    for row in worker['files']:
        checked(row)
    summary = read(output/'summary.json')
    require(summary['phase'] == phase and summary['scope'] == 'first32' and summary['case_id'] == case_id, 'Summary identity differs')
    q0_binary = read(Path(manifest['query0_checkpoint']['path']).parent/'checkpoint.json')['binary']
    require(summary['binary'] == q0_binary, 'Qualified binary differs')
    if phase == 'checkpoint':
        require(summary['stages'] == summary['native'] == [], 'Checkpoint unexpectedly launched a producer')
        value = summary['checkpoint']
        expected_cases = sorted(['ordinary/0/ordinary', *CASES])
        require(value['scope'] == 'first32' and value['case_ids'] == expected_cases and value['inputs'] == inputs
                and value['binary'] == q0_binary and value['forecast_is_bound'] is False
                and value['further_execution_requires_fresh_coordinator_grant'] is True, 'Checkpoint case/input closure differs')
        return pin(output/'execution-complete.json'), value
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
    identifier = 'first32-'+phase+'-'+('all' if case_id is None else case_id.split('/')[1])+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]
    directory = run_directory/identifier
    directory.mkdir()
    start = datetime.now(timezone.utc)
    grant = dict(schema='context-sample-feedback-admission/1', id=identifier, phase=phase, scope='first32',
        config=manifest['config'], sources_sha256=manifest['source_identity'], output=str(output),
        qualification=manifest['qualification'], inputs=inputs, not_before_utc=start.isoformat(),
        expires_utc=(start+timedelta(seconds=300)).isoformat(),
        cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/context-sample-feedback-'+identifier+'.service',
        case_id=case_id, source_audit=None, arm=None, recovery=None, **CAPS)
    grant_path = directory/'admission.json'
    fresh(grant_path, grant)
    argv = ['uv', 'run', '--no-sync', 'python', 'scripts/context-sample-feedback.py', phase,
            '--scope', 'first32', '--qualification', str(Path(manifest['qualification']['path']).parent)]
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


def dispatch(manifest, run_phase, with_checkpoint):
    products = []
    for item in manifest['units']:
        price = run_phase('price', item['case_id'], item['price_output'], [manifest['prepared']])
        price_result(price['value'], item['case_id'])
        infer = run_phase('infer', item['case_id'], item['infer_output'],
                          [manifest['prepared'], price['completion'], manifest['query0_checkpoint']])
        products.append(dict(case_id=item['case_id'], price=price, infer=infer))
    checkpoint = None
    if with_checkpoint:
        inputs = [pin(Path(path)/'execution-complete.json') for path in manifest['checkpoint_inputs']]
        checkpoint = run_phase('checkpoint', None, manifest['checkpoint_output'], inputs)
    return dict(cases=products, checkpoint=checkpoint)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--with-checkpoint', action='store_true')
    args = parser.parse_args()
    require(pin(__file__)['sha256'] == args.source_sha256, 'Reviewed sequencer source changed')
    require(pin(args.manifest)['sha256'] == args.manifest_sha256, 'Dispatch manifest pin differs')
    manifest = read(args.manifest)
    require(manifest == expected_manifest(), 'Dispatch manifest differs from fixed proposal')
    if not args.execute:
        print(json.dumps(dict(plan_only=True, manifest=pin(args.manifest), sequencer=pin(__file__),
              cases=21, native_units=42, optional_checkpoint_units=1, no_product_launched=True)))
        return
    directory = ROOT/'logs/context-sample-feedback'/('first32-dispatch-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    directory.mkdir()
    fresh(directory/'start.json', dict(manifest=pin(args.manifest), sequencer=pin(__file__),
          utc=datetime.now(timezone.utc).isoformat(), with_checkpoint=args.with_checkpoint))
    try:
        result = dispatch(manifest, lambda phase, case, output, inputs:run_unit(phase, case, output, inputs, manifest, directory), args.with_checkpoint)
    except BaseException as error:
        fresh(directory/'failed.json', dict(utc=datetime.now(timezone.utc).isoformat(), error=repr(error),
              further_execution_stopped=True, automatic_retry=False))
        raise
    fresh(directory/'complete.json', dict(complete=True, utc=datetime.now(timezone.utc).isoformat(),
          products=result, no_scientific_or_promotion_claim=True))
    print(json.dumps(dict(dispatch_completion=pin(directory/'complete.json'))), flush=True)


if __name__ == '__main__':
    main()
