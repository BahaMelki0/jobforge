from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import CandidateProfile, Job
from app.services.application_generator import generate_application


def test_application_package_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    eng=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(eng)
    S=sessionmaker(bind=eng)
    db=S()
    p=CandidateProfile(name='Candidate',headline='Security Engineer',summary='Security engineer',skills=['Python','Entra ID'],experience=[{'role':'Intern','company':'Lab','summary':'Built security tools.'}],education=[],projects=[],certifications=[])
    j=Job(fingerprint='f',title='Cloud Security Engineer',company='ACME',location='Paris, France',url='https://example.com',description='Python and Entra ID security')
    db.add_all([p,j]);db.commit();db.refresh(j)
    a=generate_application(db,p,j,use_llm=False)
    folder=Path(a.package_dir)
    assert (folder/'tailored_cv.pdf').exists()
    assert (folder/'cover_letter.pdf').exists()
    assert (folder/'application.json').exists()
