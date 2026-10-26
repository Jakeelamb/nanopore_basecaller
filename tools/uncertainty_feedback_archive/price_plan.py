"""Source-only storage pricing from the frozen PLAN geometry, never scientific payloads."""
import hashlib
import json
from pathlib import Path

ROOT=Path('/home/jake/Projects/nanopore_basecaller-context-feedback-targeting-v2')
PLAN=ROOT/'results/context-feedback/targeting-plan-v2-1/complete.json'
PLAN_SHA='63a63ba088094fe466a8db8c60609a1f6381b3f8a44967773002ddcf57328caa'

def pin(path):
    data=Path(path).read_bytes()
    if len(data)>8*1024**2: raise ValueError('Bounded source/metadata only')
    return dict(path=str(path),size=len(data),sha256=hashlib.sha256(data).hexdigest())

def price():
    plan_pin=pin(PLAN)
    if plan_pin['sha256']!=PLAN_SHA: raise ValueError('Frozen PLAN changed')
    plan=json.loads(PLAN.read_text()); joins=plan['joins']
    if pin(joins['path'])!=joins: raise ValueError('Frozen PLAN joins changed')
    rows=json.loads(Path(joins['path']).read_text())
    if len(rows)!=512 or [r['query_index'] for r in rows]!=list(range(512)): raise ValueError('Fixed census differs')
    # main.cpp phase_trace: two searches, uint64 counters/lengths, 10 left and20 right masses,
    # <=128 retained bundles, each center<=108. Context-disabled also serializes both searches.
    header=len(b'guarded-phase-trace/2\n')+2*8
    bundle=8+108+8+(8+20*8)+3*8
    step=4*8+(8+10*8)+8+128*bundle
    intervals=[r['expanded_t_end']-r['expanded_t_start'] for r in rows]
    upper=[header+2*t*step for t in intervals]
    q0_raw=5229790; q0_result=510384; q0_t=intervals[0]
    def q(percent): return sorted(intervals)[(len(intervals)-1)*percent//100]
    return dict(schema='targeting-frozen-storage-price/1',source=pin(Path(__file__).resolve()),plan=plan_pin,joins=joins,
        candidates=512,order_frozen=True,truth_used=False,scientific_payloads_read=False,
        intervals=dict(sum=sum(intervals),min=min(intervals),median=q(50),p95=q(95),max=max(intervals),over_decoder_256=[i for i,t in enumerate(intervals) if not 0<t<=256]),
        trace_upper_formula=dict(header_bytes=header,bundle_bytes=bundle,step_bytes=step,searches=2,bytes_per_timestep=2*step),
        source_shape_upper=dict(full512_raw_trace_bytes=sum(upper),maximum_case_trace_bytes=max(upper),checkpoint1_7_trace_bytes=sum(upper[1:8])),
        descriptive_q0_projection=dict(observed_t=q0_t,observed_raw_trace_bytes=q0_raw,observed_result_bytes=q0_result,
            full512_raw_trace_bytes=q0_raw*sum(intervals)//q0_t,full512_result_bytes=q0_result*sum(intervals)//q0_t,
            caveat='Linear size illustration only; neither branching nor compression ratio is a capacity guarantee.'),
        unchanged_caps=dict(maximum_growth_bytes=104857600,cumulative_output_bytes=4294967296),
        capacity_guaranteed=False,archive_compression_ratio_measured=False,
        execution_strategy='One native decoder then archive/verify per case; charge simultaneous raw+gzip plus all metadata, builds, failures and parent outputs; stop if next reservation or observed hard cap cannot fit; no refill/cap increase/evidence omission',
        provisional_case_reservation=dict(trace_raw_upper_bytes=max(upper),gzip_bound='No claimed compression guarantee; reserve raw upper + 1MiB codec overhead, enforce output maximum while streaming',
            result_metadata_bytes=16777216,other_metadata_bytes=8388608,conversion_peak_bytes=2*max(upper)+1048576+16777216+8388608),
        graph_checkpoint=dict(queries=list(range(1,8)),raw_file_count=16,maximum_growth_bytes=104857600,unmeasured_branching=True))

if __name__=='__main__': print(json.dumps(price(),indent=2,sort_keys=True))
