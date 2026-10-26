"""Seal one explicitly requested genuine case from an unchanged multirow frame completion.

Run before trace conversion; this produces owned metadata, not a native seal.
"""
from pathlib import Path

def same_catalogue(actual, expected, require):
    def catalogue(rows):
        require(type(rows) is list and len(rows)==32,'Exactly32 original decoder source pins required')
        result={}
        for item in rows:
            require(type(item) is dict and set(item)=={'path','size','sha256'} and type(item['path']) is str
                    and Path(item['path']).is_absolute() and type(item['size']) is int and item['size']>=0
                    and type(item['sha256']) is str and len(item['sha256'])==64
                    and all(value in '0123456789abcdef' for value in item['sha256']),'Malformed decoder source FilePin')
            require(item['path'] not in result,'Duplicate decoder compiled source path')
            result[item['path']]=item
        return result
    return catalogue(actual)==catalogue(expected)


def seal_case(args, driver, provenance):
    require, pin, completed, read = driver.require, driver.pin, driver.completed, driver.read
    check, qualified_decoder, receipt = driver.check, driver.qualified_decoder, driver.receipt
    runtime, owned_output, fresh = driver.runtime, driver.owned_output, driver.fresh
    command_environment = driver.command_environment
    check(provenance); request=read(provenance['path'])
    require(set(request)=={'schema','query_index','frames','runs','output','source'}
            and request['schema']=='targeting-decoder-case-seal-request/1' and type(request['query_index']) is int
            and 0<=request['query_index']<512 and request['source']==pin(Path(__file__).resolve())
            and request['frames']==pin(args.frames) and request['runs']==pin(args.runs) and request['output']==args.output,
            'Exact owned one-case seal request differs')
    require(pin(args.frames)['sha256'] == args.frames_sha256, 'Frame completion pin differs')
    frames = completed(read(args.frames), 'uncertainty-feedback-frames/1'); check(frames['frames'])
    all_frames=read(frames['frames']['path']); all_queries=[row['query_index'] for row in all_frames]
    require(all_queries and len(all_queries)==len(set(all_queries)) and request['query_index'] in all_queries,
            'Authentic frame population/declared singleton join differs')
    expected = {row['query_index']: row for row in all_frames if row['query_index']==request['query_index']}
    manifest = qualified_decoder(); runs = read(args.runs); rows = []
    require(type(runs) is list and len(runs)==1 and runs[0]['query_index']==request['query_index'],'Exactly the declared one native case required')
    for run in runs:
        query = run['query_index']; require(query in expected and query not in {row['query_index'] for row in rows}, 'Foreign/duplicate decoded run')
        frame = expected[query]; check(frame['frame']); check(frame['base_frame']); check(run['producer'])
        producer = read(run['producer']['path']); directory = Path(run['output'])
        argv = [manifest['binary']['path'], 'decode-guarded', '--frame', frame['frame']['path'], '--frame-sha256', frame['frame']['sha256'],
                '--output', str(directory), '--beam', '128', '--min-center', '0', '--max-center', '108', '--weight', '0.5', '--deficit', '0.5', '--margin', '0.5']
        receipt(producer, manifest['binary'], argv, [frame['frame'], *manifest['compiled_sources']])
        require(producer['environment'] == command_environment() and producer['extra_runtimes'] == [], 'Decoder actual environment/runtime census differs')
        runtime(producer['runtime'], manifest['binary'])
        seal = read(directory / 'complete.json')
        require(seal['schema'] == 'context-decoder-complete/1' and seal['complete'], 'Decoder completion missing')
        for item in seal['files']:
            check(item)
            require(item in producer['produced_files'], 'Decoded output not bound by actual producer')
        attempt = read(directory / 'attempt.json')
        require(attempt['schema']=='context-decoder-attempt/1' and attempt['binary'] == manifest['binary'] and attempt['argv'] == argv
                and same_catalogue(attempt['compiled_sources'], manifest['compiled_sources'], require), 'Decoder compiled witness/argv differs')
        rows.append(dict(query_index=query, frame=frame['frame'], base_frame=frame['base_frame'], construction=frame['construction'],
                         producer=run['producer'], completion=pin(directory / 'complete.json'), result=pin(directory / 'result.json')))
    require(set(expected) == {row['query_index'] for row in rows}, 'Incomplete decoded frame population')
    output = owned_output(args.output)
    fresh(output / 'complete.json', dict(schema='uncertainty-feedback-decoded/1', complete=True,
          source_witness=frames['source_witness'], plan=frames['plan'],
          plan_sha256=frames['plan_sha256'], frames=pin(args.frames), rows=rows, unchanged_decoder=manifest['binary'], truth_input=False, metadata_sealer=pin(Path(__file__).resolve()), metadata_seal_request=provenance, sealed_query_indices=[request['query_index']], frame_query_indices=all_queries, population_complete=False))
