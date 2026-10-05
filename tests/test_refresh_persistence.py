from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Application, Job, Source
from app.services.ingest import upsert_jobs, run_source
from app.sources.base import NormalizedJob


def test_changed_listing_and_repeated_batch_preserve_application():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        source = Source(name='Test', kind='demo', config={})
        db.add(source)
        db.commit()
        item = NormalizedJob(source_job_id='123', title='Security Engineer', company='Test', location='Paris', url='https://example.com/123')
        assert upsert_jobs(db, source, [item, item]) == (1, 1)
        job = db.scalar(select(Job))
        app = Application(job_id=job.id, status='technical', package_dir='saved-package')
        db.add(app)
        db.commit()
        item.title = 'Junior Security Engineer'
        item.location = 'Lyon'
        assert upsert_jobs(db, source, [item]) == (0, 1)
        assert len(db.scalars(select(Job)).all()) == 1
        db.refresh(app)
        assert app.status == 'technical'
        assert app.package_dir == 'saved-package'
        db.refresh(job)
        assert job.title == item.title


def test_failed_source_does_not_prevent_next_source():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        bad = Source(name='Broken', kind='unknown', config={})
        good = Source(name='Demo', kind='demo', config={})
        db.add_all([bad, good])
        db.commit()
        assert 'error' in run_source(db, bad)
        assert run_source(db, good)['created'] == 4
