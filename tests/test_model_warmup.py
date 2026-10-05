import time
import pytest
from app.services import llm


def test_warmup_uses_configured_local_model(monkeypatch):
    monkeypatch.setattr(llm,'model_status',lambda:{'online':True,'fast_model':'small:4b','quality_model':'test:9b','installed':['test:9b','small:4b']})
    monkeypatch.setattr(llm,'_warm_state',{'status':'idle','model':None,'error':None})
    seen=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,json):
            seen.append((url,json))
            return self
        def raise_for_status(self):pass
        def json(self):return {'done':True}
    monkeypatch.setattr(llm.httpx,'Client',Client)
    llm.warm_model()
    for _ in range(100):
        if llm._warm_state['status']!='loading':break
        time.sleep(.01)
    assert llm._warm_state['status']=='ready'
    assert seen[0][1]['model']=='test:9b'
    assert seen[0][1]['prompt']==''
    assert seen[0][1]['options']['num_ctx']==4096


def test_warmup_offline_does_not_start_work(monkeypatch):
    monkeypatch.setattr(llm,'model_status',lambda:{'online':False,'quality_model':'missing','installed':[]})
    with pytest.raises(RuntimeError):llm.warm_model()
