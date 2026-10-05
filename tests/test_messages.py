from fastapi.testclient import TestClient
from app.main import app
from app.services.llm import LLMService
from app.config import settings


CONTENT = {'connection_note': 'Bonjour, votre poste en cybersécurité m’intéresse.',
           'recruiter_message': 'Bonjour, je souhaite échanger au sujet de votre poste.',
           'email_subject': 'Candidature cybersécurité', 'email_body': 'Bonjour, voici ma candidature.'}


def test_generate_save_and_read_draft(monkeypatch):
    # Frozen dataclass instances require object.__setattr__ for this isolated override.
    old = settings.llm_provider
    object.__setattr__(settings, 'llm_provider', 'ollama')
    monkeypatch.setattr(LLMService, 'available', lambda self: True)
    monkeypatch.setattr(LLMService, 'recruiter_messages', lambda *args: CONTENT)
    try:
        with TestClient(app) as c:
            c.post('/api/sources/refresh-all')
            job = c.get('/api/jobs').json()[0]
            r = c.post(f'/api/jobs/{job["id"]}/messages', json={'language': 'fr', 'tone': 'warm'})
            assert r.status_code == 200
            draft = r.json()
            assert draft['content'] == CONTENT
            edited = {**CONTENT, 'email_body': 'Bonjour, voici mon texte révisé.'}
            assert c.put(f'/api/messages/{draft["id"]}', json=edited).status_code == 200
            assert c.get(f'/api/jobs/{job["id"]}/messages').json()[0]['content'] == edited
            assert c.put(f'/api/messages/{draft["id"]}', json={**edited, 'connection_note': 'x'*301}).status_code == 422
    finally:
        object.__setattr__(settings, 'llm_provider', old)


def test_import_listing_and_reimport_updates_without_duplicates():
    with TestClient(app) as c:
        payload = {'title': 'Security Analyst', 'company': 'Fixture Company', 'location': 'Paris, France',
                   'url': 'https://example.com/careers/security-fixture',
                   'description': 'Junior security analyst working with Microsoft Entra ID, Python and Active Directory.'}
        a = c.post('/api/import-job', json=payload)
        b = c.post('/api/import-job', json={**payload, 'title': 'Junior Security Analyst'})
        assert a.status_code == b.status_code == 200
        assert a.json()['id'] == b.json()['id']
        job = c.get('/api/jobs/'+str(a.json()['id'])).json()
        assert job['score'] and job['title'] == 'Junior Security Analyst'
        assert c.post('/api/import-job', json={**payload, 'url': 'javascript:alert(1)'}).status_code == 422
