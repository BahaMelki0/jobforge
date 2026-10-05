import json
from types import SimpleNamespace
from app.services.llm import LLMService
from app.schemas import MessageRequest


def test_wrong_sender_is_retried_and_validated(monkeypatch):
    p=SimpleNamespace(name='Bahaeddine Melki', headline='', summary='', skills=[], experience=[], projects=[], certifications=[])
    j=SimpleNamespace(title='Security Engineer', company='Example', description='A security role')
    good={'connection_note':'Bonjour, je souhaite échanger sur votre poste.', 'recruiter_message':'Bonjour, je vous contacte pour candidater.', 'email_subject':'Candidature', 'email_body':'Bonjour, je souhaite candidater. Bahaeddine Melki'}
    responses=iter([json.dumps({**good,'recruiter_message':'Bonjour Bahaeddine, nous recrutons.'}),json.dumps(good)])
    calls=[]
    def fake_call(self,instructions,payload):
        calls.append(instructions)
        return next(responses)
    monkeypatch.setattr(LLMService,'_call',fake_call)
    assert LLMService().recruiter_messages(p,j,MessageRequest())==good
    assert len(calls)==2
