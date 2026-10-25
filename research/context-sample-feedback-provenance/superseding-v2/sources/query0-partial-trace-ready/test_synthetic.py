import importlib.util, json, struct
from pathlib import Path
spec=importlib.util.spec_from_file_location('comparison',Path(__file__).with_name('compare.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def fixture(center='A',potential=0.):
 b=bytearray(b'sample-guarded-exact-trace/1\n')
 def integer(n): b.extend(struct.pack('<Q',n))
 def real(n): b.extend(struct.pack('<d',n))
 def seq(s): integer(len(s)); b.extend(s.encode())
 integer(1); integer(0); integer(103)
 for step in range(1,104):
  integer(step); integer(1); integer(1); integer(0)
  integer(1); real(0.)
  integer(1); seq(center); real(0.); integer(1); real(0.)
  real(0.); real(potential); real(potential)
 integer(1); seq(center); integer(0); real(0.); real(potential); real(potential)
 return bytes(b)
a=m.trace(fixture(),1,1); b=m.trace(fixture(potential=9.),1,1); c=m.trace(fixture('C'),1,1)
assert m.compare(a['prefix_sets'],b['prefix_sets'])['changed_steps']==0
r=m.compare(a['prefix_sets'],c['prefix_sets']); assert r['changed_steps']==102 and r['first_changed_step']==1
checks=2
for data in (b'',fixture()[:-1],fixture()+b'x'):
 try: m.trace(data,1,1)
 except (AssertionError,UnicodeDecodeError,struct.error): checks+=1
 else: raise AssertionError('malformed trace accepted')
assert len(a['prefix_sets'])==103 and set(a['finalists'])<=a['prefix_sets'][-1]; checks+=1
print(json.dumps(dict(synthetic_checks=checks,passed=checks,genuine_trace_reads=0)))
