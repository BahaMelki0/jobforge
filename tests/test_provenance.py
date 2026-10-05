from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Job, JobObservation, Source
from app.services.evidence import relevant
from app.services.llm import validate_credentials
from app.services.llm import calibrate_junior_wording
import pytest
from app.services.ingest import upsert_jobs
from app.sources.base import NormalizedJob


def test_identical_full_cross_source_vacancy_keeps_two_observations():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first, second = Source(name='A', kind='rss'), Source(name='B', kind='rss')
        db.add_all([first, second]); db.commit()
        description = 'Junior Entra ID security engineer in France. ' * 8
        for source, url in [(first, 'https://a.test/1'), (second, 'https://b.test/2')]:
            item = NormalizedJob(source_job_id=url, title='Junior Security Engineer', company='Example', location='Paris, France',
                                 url=url, description=description, published_at=datetime.now(timezone.utc), raw={'status': 'open'})
            upsert_jobs(db, source, [item])
        assert len(db.scalars(select(Job)).all()) == 1
        assert len(db.scalars(select(JobObservation)).all()) == 2


def test_evidence_retrieval_prefers_relevant_project_over_position():
    entries = [{'name': 'Research', 'summary': 'Polynomial commitments'}, {'name': 'Detection Forge', 'summary': 'Sentinel KQL SOC detection'}]
    job = SimpleNamespace(title='SOC detection analyst', description='Sentinel and KQL')
    assert relevant(entries, job, 1)[0]['name'] == 'Detection Forge'


def test_credentials_cannot_be_upgraded_or_invented():
    profile = SimpleNamespace(name='Bahaeddine Melki', certifications=['SC-200', 'CPTS (ongoing)'])
    with pytest.raises(ValueError): validate_credentials('I hold OSCP.', profile)
    with pytest.raises(ValueError): validate_credentials('I hold CPTS.', profile)
    validate_credentials('CPTS en cours, SC-200.', profile)
    with pytest.raises(ValueError): validate_credentials('Je suis étudiant en cybersécurité.', profile)
    with pytest.raises(ValueError): validate_credentials('Ma maîtrise de tous les systèmes.', profile)
    assert calibrate_junior_wording('Je maîtrise Windows.') == "J'ai des connaissances sur Windows."
