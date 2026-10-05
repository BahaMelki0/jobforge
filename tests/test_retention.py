from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Job, JobScore, Application, MessageDraft, Source
from app.services.retention import purge_expired, expired
from app.services.ingest import upsert_jobs
from app.sources.base import NormalizedJob


def test_age_limit_and_explicit_deadline_archive():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    now=datetime.now(timezone.utc)
    with Session(engine) as db:
        jobs=[Job(fingerprint=str(i),title='Security',company='Example',url=f'https://example.com/{i}',published_at=date,
                  raw=({'valid_through': (now-timedelta(days=1)).isoformat()} if i == 2 else {}))
              for i,date in enumerate([now-timedelta(days=90),now-timedelta(days=31),now-timedelta(days=30),None])]
        db.add_all(jobs);db.commit()
        old_id,expired_id=jobs[0].id,jobs[2].id
        db.add(JobScore(job_id=old_id,total=90))
        db.add(Application(job_id=expired_id,status='technical'))
        db.commit()
        result=purge_expired(db,now)
        assert result['archived_closed']==1
        assert result['removed_expired']==2
        assert db.get(Job,old_id) is None
        assert db.get(Job,expired_id).active is False
        assert db.get(Job,expired_id).application_status=='expired'
        assert db.scalar(select(Application)).status=='technical'
        assert db.scalar(select(JobScore)) is None
        assert len(db.scalars(select(Job).where(Job.active.is_(True))).all())==1


def test_refresh_cannot_reinsert_old_offer_and_unknown_date_is_kept():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with Session(engine) as db:
        source=Source(name='Retention test',kind='demo',config={});db.add(source);db.commit()
        old=NormalizedJob('old','Security','Example','France','https://example.com/old',published_at=datetime.now(timezone.utc)-timedelta(days=91))
        unknown=NormalizedJob('unknown','Security','Example','France','https://example.com/unknown')
        assert upsert_jobs(db,source,[old,unknown])==(1,0)
        assert upsert_jobs(db,source,[old,unknown])==(0,1)
        assert db.scalar(select(func.count()).select_from(Job))==1
        assert expired(None) is False


def test_closed_description_and_unknown_status():
    from app.services.retention import application_state
    assert application_state(Job(description='This job posting is no longer available.'))[0]=='closed'
    assert application_state(Job(description='Junior SOC Analyst. Apply now.'))[0]=='unknown'


def test_refresh_archives_existing_offer_when_source_reports_closed():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with Session(engine) as db:
        source=Source(name='Closure test',kind='demo',config={});db.add(source);db.commit()
        open_offer=NormalizedJob('same','Junior SOC Analyst','Example','Lyon, France','https://example.com/same',
                                 description='Monitor SOC alerts and document investigation notes.',
                                 raw={'source_status':'open'})
        assert upsert_jobs(db,source,[open_offer])==(1,0)
        job=db.scalar(select(Job));assert job.application_status=='open'
        closed=NormalizedJob('same','Junior SOC Analyst','Example','Lyon, France','https://example.com/same',
                             description='This job posting is no longer available.',
                             raw={'source_status':'closed'})
        assert upsert_jobs(db,source,[closed])==(0,1)
        assert job.active is False and job.application_status=='closed'
