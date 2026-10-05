import time
import uuid
from threading import Event
from fastapi.testclient import TestClient
from app.main import app
from app.services import ai_tasks
from app.services.llm import LLMService, GenerationCancelled


def setup_job(c):
    return c.post('/api/import-job', json={'title':'Junior Cloud Security', 'company':'Queue test', 'location':'Paris', 'url':'https://example.com/'+uuid.uuid4().hex, 'description':'Junior cloud security role using Microsoft Entra ID, Azure and Python automation.'}).json()['id']


def wait_done(c, task_id):
    for _ in range(100):
        task=c.get('/api/ai-tasks/'+task_id).json()
        if task['status'] not in ('queued','running'):
            return task
        time.sleep(.02)
    raise AssertionError('Worker did not complete')


def status():
    return {'online':True,'installed':['fixture'],'fast_model':'fixture','quality_model':'fixture'}


def test_queue_cache_and_changed_inputs(monkeypatch):
    monkeypatch.setattr(ai_tasks,'model_status',status)
    calls=[]
    def generate(self,*args):
        calls.append(True)
        return {'recruiter_message':'Bonjour, je souhaite discuter de ce poste.'}
    monkeypatch.setattr(LLMService,'recruiter_messages',generate)
    with TestClient(app) as c:
        job=setup_job(c)
        url=f'/api/jobs/{job}/ai-tasks'
        a=c.post(url,json={}).json()
        done=wait_done(c,a['task']['id'])
        assert done['status']=='succeeded',done
        cached=c.post(url,json={}).json()
        assert cached['cached'] and cached['task']['id']==done['id']
        assert len(calls)==1
        different=c.post(url,json={'tone':'warm'}).json()
        assert different['task']['id']!=done['id']
        assert wait_done(c,different['task']['id'])['status']=='succeeded'
        assert c.get(f'/api/jobs/{job}/messages').json()[0]['content']['recruiter_message']


def test_cancel_and_worker_recovers(monkeypatch):
    monkeypatch.setattr(ai_tasks,'model_status',status)
    entered=Event()
    def generate(self,*args):
        entered.set()
        for _ in range(200):
            if self.cancel():
                raise GenerationCancelled('Cancelled')
            time.sleep(.01)
        return {'recruiter_message':'Draft'}
    monkeypatch.setattr(LLMService,'recruiter_messages',generate)
    with TestClient(app) as c:
        job=setup_job(c)
        task=c.post(f'/api/jobs/{job}/ai-tasks',json={}).json()['task']
        assert entered.wait(2)
        assert c.post('/api/ai-tasks/'+task['id']+'/cancel').json()['status']=='cancelled'
        assert wait_done(c,task['id'])['status']=='cancelled'
        monkeypatch.setattr(LLMService,'recruiter_messages',lambda *a:{'recruiter_message':'Recovered'})
        retry=c.post(f'/api/jobs/{job}/ai-tasks',json={'force':True}).json()['task']
        assert wait_done(c,retry['id'])['status']=='succeeded'


def test_offline_is_explicit(monkeypatch):
    monkeypatch.setattr(ai_tasks,'model_status',lambda:{**status(),'online':False,'error':'Ollama offline'})
    with TestClient(app) as c:
        assert c.post('/api/jobs/1/ai-tasks',json={}).status_code==503


def test_quality_is_default_and_fast_is_explicit(monkeypatch):
    monkeypatch.setattr(ai_tasks,'model_status',lambda:{'online':True,'installed':['quality:9b','fast:4b'],'fast_model':'fast:4b','quality_model':'quality:9b'})
    monkeypatch.setattr(LLMService,'recruiter_messages',lambda *args:{'recruiter_message':'Bonjour, je souhaite candidater.'})
    with TestClient(app) as c:
        job=setup_job(c)
        default=c.post(f'/api/jobs/{job}/ai-tasks',json={}).json()['task']
        assert default['model']=='quality:9b'
        assert wait_done(c,default['id'])['status']=='succeeded'
        fast=c.post(f'/api/jobs/{job}/ai-tasks',json={'quality':'fast'}).json()['task']
        assert fast['model']=='fast:4b'
        assert fast['id']!=default['id']
        assert wait_done(c,fast['id'])['status']=='succeeded'


def test_agent_review_is_queued_and_cached_without_application(monkeypatch):
    from app.services import agent_review
    monkeypatch.setattr(ai_tasks,'model_status',status)
    result={'report':{'summary':'Evidence-based review of the selected junior role.','evidence':['Profile evidence'],'gaps':['Needs verification'],'next_steps':['Review requirements']},'tools':[{'tool':'read_candidate_profile','status':'completed'}],'focus':{'status':'junior_france','reasons':[]}}
    monkeypatch.setattr(agent_review,'review_job',lambda *args,**kwargs:result)
    with TestClient(app) as c:
        job=setup_job(c)
        request={'kind':'agent_review'}
        task=c.post(f'/api/jobs/{job}/ai-tasks',json=request).json()['task']
        done=wait_done(c,task['id'])
        assert done['status']=='succeeded',done
        assert done['result']==result
        assert c.post(f'/api/jobs/{job}/ai-tasks',json=request).json()['cached'] is True
        assert all(a['job_id']!=job for a in c.get('/api/applications').json())
