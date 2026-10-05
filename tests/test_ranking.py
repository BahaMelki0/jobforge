from app.models import CandidateProfile, Job
from app.services.ranking import rank_job


def profile():
    return CandidateProfile(
        name='Test',
        preferred_locations=['France','Paris, France'],
        categories={
            'Offensive Security / Pentest / Red Team':1.0,
            'Cloud & Identity Security':1.0,
            'Blue Team / SOC / Detection':0.7,
            'Cybersecurity / Security Consulting':0.8,
        },
        skills=['Microsoft Entra ID','Microsoft Graph','Active Directory','Python','penetration testing'],
        must_have_keywords=['security','cloud','identity'],
        exclude_keywords=['10+ years'],
        preferred_employment=['CDI','full-time'],
    )


def test_cloud_identity_role_scores_higher_than_senior_lead():
    p=profile()
    good=Job(id=1,fingerprint='a',title='Junior Cloud Identity Security Engineer',company='X',location='Paris, France',url='x',employment_type='CDI',description='Microsoft Entra ID Microsoft Graph cloud security identity Python Active Directory')
    bad=Job(id=2,fingerprint='b',title='Senior Red Team Lead',company='Y',location='Paris, France',url='y',employment_type='CDI',description='Requires 10+ years red team leadership')
    assert rank_job(p,good).total > rank_job(p,bad).total
    assert rank_job(p,good).category == 'Cloud & Identity Security'


def test_exclusion_penalty_is_applied():
    p=profile()
    j=Job(id=3,fingerprint='c',title='Security Engineer',company='X',location='Paris, France',url='x',description='Cloud security. Requires 10+ years.')
    r=rank_job(p,j)
    assert r.breakdown['penalties'] < 0
    assert any('exclusion' in x.lower() for x in r.gaps)
