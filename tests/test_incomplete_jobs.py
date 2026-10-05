from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal
from app.models import Source,Job,JobScore
from app.sources.base import NormalizedJob
from app.services.ingest import upsert_jobs


def test_missing_description_blocks_generation_and_does_not_erase_full_content():
    with TestClient(app) as client:
        with SessionLocal() as db:
            source=db.scalar(select(Source).where(Source.name=='Incomplete fixture'))
            if source is None:
                source=Source(name='Incomplete fixture',kind='wttj',enabled=False,config={})
                db.add(source);db.commit()
            url='https://example.com/jobs/incomplete'
            item=NormalizedJob('incomplete','Pentester','Example','Unverified',url,raw={'detail_status':'link_only'})
            # Unique URL across reruns, clear description for this fixture only.
            existing=db.scalar(select(Job).where(Job.url==url))
            if existing:
                existing.description='';existing.raw={'detail_status':'link_only'};db.commit()
            upsert_jobs(db,source,[item])
            job=db.scalar(select(Job).where(Job.url==url));job_id=job.id
        assert client.post(f'/api/jobs/{job_id}/messages',json={'language':'fr'}).status_code==409
        assert client.post(f'/api/jobs/{job_id}/application').status_code==409
        assert client.post(f'/api/jobs/{job_id}/rank').status_code==409
        with SessionLocal() as db:
            source=db.get(Source,source.id)
            full=NormalizedJob('incomplete','Pentester','Example','Paris, France',url,description='Full imported cybersecurity description.',raw={})
            upsert_jobs(db,source,[full]);upsert_jobs(db,source,[item])
            job=db.get(Job,job_id);db.refresh(job)
            assert job.description==full.description
            assert job.detail_status=='full'
