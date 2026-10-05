from fastapi.testclient import TestClient
from app.main import app


def test_health_and_seeded_profile():
    with TestClient(app) as c:
        r=c.get('/api/health'); assert r.status_code==200 and r.json()['ok'] is True
        p=c.get('/api/profile'); assert p.status_code==200 and p.json()['name']


def test_followup_round_trip_and_invalid_date_preserves_notes():
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Application, Job
    with TestClient(app) as client:
        client.post('/api/sources/refresh-all')
        with SessionLocal() as db:
            job = db.scalars(select(Job)).first()
            application = Application(job_id=job.id)
            db.add(application)
            db.commit()
            application_id = application.id
        url = f'/api/applications/{application_id}/followup'
        saved = {'followup_date': '2026-10-12', 'notes': 'Revise KQL for technical interview.'}
        assert client.put(url, json=saved).status_code == 200
        assert client.get(url).json() == saved
        for invalid in ['2026-02-30', '20261012']:
            assert client.put(url, json={'followup_date': invalid, 'notes': 'overwrite'}).status_code == 422
            assert client.get(url).json() == saved
        assert client.get('/api/applications/999999999/followup').status_code == 404


def test_demo_flow():
    with TestClient(app) as c:
        r=c.post('/api/sources/refresh-all'); assert r.status_code==200
        r=c.post('/api/jobs/rank-all?use_llm=false'); assert r.status_code==200
        jobs=c.get('/api/jobs').json(); assert len(jobs)>=4
        assert any(j.get('score') for j in jobs)


def test_dashboard_and_combined_filters():
    with TestClient(app) as c:
        assert c.get('/').status_code == 200
        c.post('/api/sources/refresh-all')
        jobs = c.get('/api/jobs').json()
        category = jobs[0]['score']['category']
        response = c.get('/api/jobs', params={'category': category, 'min_score': 1})
        assert response.status_code == 200
        assert response.json()
        assert all(j['score']['category'] == category for j in response.json())


def test_unknown_fresh_offer_import_and_old_offer_retention():
    from datetime import datetime, timedelta, timezone
    with TestClient(app) as c:
        imported = c.post('/api/import-job', json={
            'title': 'Junior SOC Analyst', 'company': 'Lifecycle Test', 'location': 'Lyon, France',
            'url': 'https://example.com/lifecycle-test',
            'description': 'Junior SOC role in France. Monitor alerts and document investigations with a senior team.',
            'published_at': (datetime.now(timezone.utc)-timedelta(days=10)).isoformat(),
        })
        assert imported.status_code == 200, imported.text
        jobs = c.get('/api/jobs', params={'application_status': 'unknown'}).json()
        job = next(item for item in jobs if item['id'] == imported.json()['id'])
        assert job['application_status'] == 'unknown'
        assert job['active'] is True
        old = c.post('/api/import-job', json={
            'title': 'Junior SOC Analyst', 'company': 'Lifecycle Test', 'location': 'Lyon, France',
            'url': 'https://example.com/lifecycle-test-old',
            'description': 'Junior SOC role in France. Monitor alerts and document investigations with a senior team.',
            'published_at': (datetime.now(timezone.utc)-timedelta(days=90)).isoformat(),
        })
        assert old.status_code == 422
