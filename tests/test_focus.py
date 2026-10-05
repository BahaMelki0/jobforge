import pytest
from app.models import Job
from app.services.focus import assess, required_years, target_role
from app.services.ranking import rank_job,save_score
from tests.test_ranking import profile


def job(title='Analyste SOC junior',location='Lyon',description='Debutants acceptes. SIEM et supervision des incidents.'):
    return Job(title=title,location=location,description=description,requirements='',company='Test',employment_type='CDI',remote='')


@pytest.mark.parametrize('title',['Technicien support informatique','Help desk technician','Administrateur reseaux junior','Junior Network Engineer','Junior Pentester','Analyste SOC N1','Blue Team Analyst','Red Team junior'])
def test_target_families(title):
    assert target_role(title)


@pytest.mark.parametrize('title',['Agent de securite incendie','Security Sales Specialist','Commercial reseaux','Business Development Cybersecurity'])
def test_irrelevant_roles(title):
    assert not target_role(title)


def test_conservative_focus():
    assert assess(job())['status']=='junior_france'
    assert assess(job(location='Remote Europe'))['status']=='review'
    assert assess(job(location='Paris, Canada'))['status']=='excluded'
    assert assess(job(title='Senior SOC Analyst'))['status']=='excluded'
    assert assess(job(title='Analyste SOC',description='Experience exigee : 3 a 5 ans.'))['status']=='excluded'
    assert assess(job(title='Stage analyste SOC'))['status']=='training'
    assert assess(job(title='Analyste SOC',description='SIEM et gestion des incidents'))['status']=='review'


@pytest.mark.parametrize('text,expected',[("2 ans d'experience minimum",2),('Experience de 3 a 5 ans',3),('Requires 5+ years of experience',5),('Experience: 0-2 years',0),('Founded 20 years ago. Join our team.',None),('Contrat de 3 ans',None)])
def test_experience_extraction(text,expected):
    assert required_years(text)==expected


def test_score_and_categories():
    p=profile()
    assert rank_job(p,job(title='Senior SOC Lead')).total<=39
    assert rank_job(p,job(location='London')).total<=39
    assert rank_job(p,job(title='Technicien support informatique junior')).category=='IT Support / Help Desk'
    assert rank_job(p,job(title='Junior Network Engineer')).category=='Networking / Systems'


def test_live_scan_regressions():
    assert assess(job(title='Squad Leader Cybersecurite'))['status']=='excluded'
    assert assess(job(title='Technicien Supply Chain - Defense & Securite'))['status']=='excluded'
    assert rank_job(profile(),job(title='Pentester Web Junior')).category=='Offensive Security / Pentest / Red Team'
    assert assess(job(title='Technicien Help Desk',description='Support utilisateur et gestion des tickets'))['status']=='review'
