import json
from types import SimpleNamespace
import pytest
from app.services.llm import validate_applicant_voice

@pytest.mark.parametrize('text',[
    'Bonjour Monsieur Melki, votre candidature a retenu notre attention.',
    'Bonjour Bahaeddine, nous recrutons pour ce poste.',
    'Dear Mr. Melki, your application is relevant to our team.',
    'Bonjour, votre profil correspond a nos attentes.',
    'Bonjour [recruteur], je souhaite candidater.'
])
def test_recruiter_role_reversal_rejected(text):
    with pytest.raises(ValueError):
        validate_applicant_voice(text,'Bahaeddine Melki')

@pytest.mark.parametrize('text',[
    'Bonjour, je souhaite rejoindre votre equipe. Mon stage chez RandoriSec correspond au poste.',
    'Hello, I am applying for this junior position. I would be happy to discuss my experience.'
])
def test_valid_applicant_voice(text):
    validate_applicant_voice(text,'Bahaeddine Melki')
