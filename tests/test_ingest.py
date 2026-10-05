from app.sources.base import NormalizedJob
from app.services.ingest import fingerprint


def test_fingerprint_is_stable():
    a=NormalizedJob(source_job_id='1',title=' Security  Engineer ',company='ACME',location='Paris',url='https://x/1')
    b=NormalizedJob(source_job_id='1',title='security engineer',company='acme',location='paris',url='https://x/1')
    assert fingerprint(a)==fingerprint(b)
