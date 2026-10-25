import importlib.util,json,sys,tempfile
from pathlib import Path
from unittest import mock
r=Path.cwd();s=importlib.util.spec_from_file_location('receiver',r/'tools/support_context/transport_fetch_v3.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
pin=dict(path=str(r/'results/support-context/paw71238-inspect-1/0a98559380be4cf68d53f879f1664e1d/complete.json'),size=6965,sha256='e4369d3e7f73ec2519350130242bf5d0f4863c179d67d55b63b4f1de1b8fc950');t.check(pin)
class ReadyBeforeNetwork(Exception):pass
class NoNetwork:
 maximum_request=1024*1024
 def __init__(self):self.calls=[]
 def fetch(self,*args):self.calls.append(args);raise ReadyBeforeNetwork()
base=r/'results/context-feedback/support-fetch-v3-controls-1';d=base/'handoff';d.mkdir()
positive=NoNetwork()
try:t.fetch_ranges(t.source(),positive,d,pin,500000000)
except ReadyBeforeNetwork:pass
else:raise ValueError('Genuine adapter did not reach fetch boundary')
t.require(len(positive.calls)==1,'Positive handoff did not reach exactly first fetch')
original=t.read
negative=NoNetwork()
def altered(path):
 value=original(path)
 if Path(path)==Path(pin['path']):value=dict(value,controller=dict(t.PREVIOUS_CONTROLLER,sha256='0'*64))
 return value
with mock.patch.object(t,'read',side_effect=altered):
 try:t.fetch_ranges(t.source(),negative,d,pin,500000000)
 except ValueError as error:reason=str(error)
 else:raise ValueError('Unregistered controller was accepted')
t.require(not negative.calls and reason=='Qualified inspect manifest required','Wrong producer guard or fetch happened')
t.fresh(base/'handoff.json',dict(positive_genuine_input=pin,first_fetch_range=list(positive.calls[0][2:]),negative_rejection=reason,negative_fetch_calls=0,actual_network_requests=0,readonly_observation_injection=True,old_producer_replayed=False))
print(json.dumps(dict(result=t.pin(base/'handoff.json'))))
