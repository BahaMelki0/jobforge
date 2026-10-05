"""Facts supplied by the workspace owner; no inferred dates or experience duration."""
CERTIFICATIONS = ['SC-200', 'CRTP', 'CARTP', 'eJPT', 'PT1', 'CPTS (ongoing)']
EXPERIENCE = {'role': 'IT / Cybersecurity experience', 'company': 'KPMG Tunisia',
              'summary': 'Network troubleshooting, Active Directory and access-control administration.',
              'bullets': ['Worked on network troubleshooting, Active Directory and access-control administration.']}
PROJECTS = [
    {'name': 'Detection Forge', 'summary': 'Detection-as-code for Entra ID, Windows and Sysmon, hybrid correlation and investigation workflows.'},
    {'name': 'APK Sentinel', 'summary': 'Android AppSec assessment with static evidence, interception and request replay.'},
    {'name': 'Windows 11 call-graph toolkit', 'summary': 'Windows call-graph construction and reverse engineering.'},
    {'name': 'SecurePipeline', 'summary': 'DevSecOps security gates and pipeline automation.'},
    {'name': 'Voice spoof detection', 'summary': 'LLM-based voice spoof detection project.'},
    {'name': 'ZK-SNARK research', 'summary': 'ZK-SNARK and polynomial commitment research.'},
]
SKILLS = ['Microsoft Sentinel', 'KQL', 'Defender XDR', 'Sysmon', 'MITRE ATT&CK', 'IAM', 'OAuth', 'OIDC', 'Rust', 'C/C++', 'Bash', 'SQL', 'threat modeling', 'DevSecOps']


def enrich(profile):
    profile.headline = 'Recently graduated Telecommunications Engineer | Cybersecurity | Cloud & Identity / SOC / AppSec'
    profile.summary = ('Recently graduated Telecommunications Engineer specialized in Cybersecurity. End-of-studies internship at RandoriSec: '
                       'refactored 15+ modules of an internal Microsoft Graph / Entra ID / Microsoft 365 security assessment framework, '
                       'including authentication, enumeration, permissions, service principals, artifact collection and SQLite persistence. '
                       'Prior KPMG Tunisia experience covered network troubleshooting, Active Directory and access-control administration.')
    profile.certifications = list(dict.fromkeys((profile.certifications or []) + CERTIFICATIONS))
    profile.skills = list(dict.fromkeys((profile.skills or []) + SKILLS))
    profile.preferred_employment = list(dict.fromkeys((profile.preferred_employment or []) + ['CDI', 'CDD']))
    if not any('kpmg' in str(item.get('company', '')).casefold() for item in profile.experience):
        profile.experience = list(profile.experience) + [EXPERIENCE]
    names = {item.get('name', '').casefold() for item in profile.projects}
    profile.projects = list(profile.projects) + [item for item in PROJECTS if item['name'].casefold() not in names]
    profile.categories = {**(profile.categories or {}), 'AppSec / DevSecOps': 1.0}
