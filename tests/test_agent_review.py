import json
from types import SimpleNamespace
import pytest
from app.services import agent_review
from app.services.llm import LLMService,GenerationCancelled


def fixtures():
    profile=SimpleNamespace(name='Candidate',headline='Junior',summary='Internship',skills=['Python'],certifications=[],experience=[],projects=[])
    job=SimpleNamespace(title='Junior SOC Analyst',company='Test',location='Paris',description='SIEM monitoring and incident triage.',requirements='0-2 years of experience',employment_type='CDI')
    return profile,job


def tool_response(names):
    return {'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':name,'arguments':{}}} for name in names]}}


def mock_client(monkeypatch,responses):
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,json,**kwargs):
            calls.append(json)
            result=next(responses)
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:result)
    monkeypatch.setattr(agent_review.httpx,'Client',Client)
    return calls


def test_review_reads_all_evidence_before_final_report(monkeypatch):
    report={'summary':'The profile has transferable skills but operational experience needs verification.','evidence':['Python is listed in the saved profile.'],'gaps':['No production SOC experience documented.'],'next_steps':['Ask about junior training.']}
    responses=iter([tool_response(list(agent_review.TOOL_DESCRIPTIONS)),{'message':{'content':json.dumps(report)},'eval_count':80}])
    calls=mock_client(monkeypatch,responses)
    llm=LLMService(model='fixture');p,j=fixtures()
    result=agent_review.review_job(llm,p,j)
    assert result['report']==report
    assert len(result['tools'])==3
    assert result['focus']['status']=='junior_france'
    assert 'tools' in calls[0] and 'format' in calls[1]
    assert 'tools' not in calls[1]
    assert llm.metrics['tool_calls']==3


def test_unknown_tool_never_executes(monkeypatch):
    mock_client(monkeypatch,iter([tool_response(['delete_database'])]))
    with pytest.raises(ValueError,match='outside this review'):
        agent_review.review_job(LLMService(model='fixture'),*fixtures())


def test_tool_arguments_are_rejected(monkeypatch):
    response=tool_response(['read_candidate_profile'])
    response['message']['tool_calls'][0]['function']['arguments']={'path':'private.txt'}
    mock_client(monkeypatch,iter([response]))
    with pytest.raises(ValueError,match='do not accept arguments'):
        agent_review.review_job(LLMService(model='fixture'),*fixtures())


def test_missing_evidence_cannot_produce_report(monkeypatch):
    responses=iter([{'message':{'content':'I know enough already'}}]*3)
    mock_client(monkeypatch,responses)
    with pytest.raises(ValueError,match='all required evidence'):
        agent_review.review_job(LLMService(model='fixture'),*fixtures())


def test_cancellation_releases_model_lock(monkeypatch):
    mock_client(monkeypatch,iter([]))
    with pytest.raises(GenerationCancelled):
        agent_review.review_job(LLMService(model='fixture',cancel=lambda:True),*fixtures())
    assert agent_review._generation_lock.acquire(blocking=False)
    agent_review._generation_lock.release()
