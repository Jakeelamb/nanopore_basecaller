import hashlib,json
from pathlib import Path
O=Path(__file__).parent.resolve(); R=O.parents[2]
def pin(p):
 b=p.read_bytes(); return dict(path=str(p),size=len(b),sha256=hashlib.sha256(b).hexdigest())
command=['uv','run','--no-sync','python',str(O/'compare.py'),'--output',str(O/'comparison.json')]
ready=dict(schema='query0-partial-trace-source-ready/1',source_only=True,runtime_authorized=False,
 hypothesis='Other context may change the DNA prefix sets actually retained at nonterminal search steps versus free search, even if no final accepted winner changes.',
 endpoint='Exact set equality at every step 1..102: counts, first changed step, cardinalities, directional set differences and sorted JSON set SHA256. Step103 is parsed and validated but excluded from endpoint.',
 cwd=str(R),environment=dict(UV_PROJECT_ENVIRONMENT='/home/jake/Projects/nanopore_basecaller-retrieval/.venv',UV_OFFLINE='1',UV_PYTHON_DOWNLOADS='never',PYTHONDONTWRITEBYTECODE='1'),argv=command,
 files=[pin(O/n) for n in ('compare.py','input-pins.json','test_synthetic.py','prepare.py','seal_ready.py')],
 expected_output=dict(path=str(O/'comparison.json'),schema='query0-retained-prefix-comparison/1',complete=True,comparisons=['population','sample','combined'],nonterminal_steps_compared=102,changed_steps='UNOBSERVED: 0..102 per comparison',first_changed_step='UNOBSERVED: null or 1..102',output_sha256='UNOBSERVED until admitted execution'),
 expected_input=dict(completion_sha256='c0b6b57391b0247d2583269a9cb7f0b30351dcfea59db1e25f72339476bf4f44',source_identity='63daa48719914a01c1b21ec208a1bacd2a4415b390f257798477f0cd786f2dc2',binary_sha256='001af437a02fcf615f78617af1fad164af0ad60f18d1beba6ce9ff2fcae1f475',traces=4,steps_each=103,finalists_each=128,raw_bytes=10481596,gzip_bytes=3803511),
 caps_proposal=dict(maximum_wall_seconds=300,cpu_quota=2,memory_bytes=4*1024**3,address_space_bytes=8*1024**3,swap_bytes=0,maximum_growth_bytes=100*1024**2,maximum_output_bytes=4*1024**3,minimum_free_bytes=30*1024**3),
 supervision='Existing separately admitted whole-unit supervisor must cover all metadata/hash/decompression/comparison work; this helper does not acquire locks or create supervision.',
 validation=dict(command='uv run --no-sync python '+str(O/'test_synthetic.py'),exit_status=0,synthetic_checks=6,genuine_trace_reads=0),
 source_read_budget=dict(maximum_total_bytes=64*1024**2,maximum_file_bytes=8*1024**2,observed_metadata_pinning_bytes=312222,conservative_total_source_read_upper_bound_bytes=1024**2,trace_body_bytes=0,scientific_execution=False),
 limits=['All beams were pruned: no global optimum claim.','Producer scientific correctness remains prior producer evidence. Runtime source/binary identities are verified from sealed metadata, not rehashed source/binary payloads.','No beam, scalar, potential, native model, tensor, truth or alignment producer rerun.','No acceptance/promotion/independence claim.','Archive bodies will be read only under separate runtime admission.'])
(O/'ready.json').write_text(json.dumps(ready,indent=2)+'\n')
print(json.dumps(pin(O/'ready.json')))
