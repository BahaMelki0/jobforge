CATALOG = [
    {'key': 'linkedin', 'name': 'LinkedIn Jobs · France', 'kind': 'linkedin', 'description': 'Public job search: cybersecurity, pentest, SOC and identity roles. Stops on access challenges.', 'config': {'queries': ['cybersecurity', 'pentest', 'SOC analyst', 'identity security'], 'location': 'France', 'max_jobs': 100, 'max_pages_per_query': 4, 'days': 30}},
    {'key': 'apec', 'name': 'APEC · Cybersecurity', 'kind': 'apec', 'description': 'Public French cadre job search. Summaries are labelled when full descriptions are unavailable.', 'config': {'queries': ['cybersecurite', 'pentest', 'analyste SOC', 'IAM'], 'max_jobs': 150, 'max_pages_per_query': 5}},
    {'key': 'wttj', 'name': 'Welcome to the Jungle · Discovery', 'kind': 'wttj', 'description': 'Automatically discovers cyber roles from public sitemaps. Blocked descriptions stay unranked; French language does not confirm France location.', 'config': {'max_jobs': 150, 'max_sitemaps': 9}},
    {'key': 'cybersecurityjobsite', 'name': 'CyberSecurityJobsite · France', 'kind': 'cybersecurityjobsite', 'description': 'Security-specific job board: France listings with full published job descriptions.', 'config': {'max_jobs': 100, 'max_pages': 8}},
    {'key': 'devoteam', 'name': 'Devoteam · Cyber Trust', 'kind': 'smartrecruiters', 'description': 'France cybersecurity consulting, cloud and identity roles.', 'config': {'company_identifier': 'Devoteam', 'queries': ['cyber', 'security'], 'max_jobs': 150}},
    {'key': 'sopra', 'name': 'Sopra Steria · Cybersecurity', 'kind': 'smartrecruiters', 'description': 'France security engineering, consulting and graduate opportunities.', 'config': {'company_identifier': 'SopraSteria1', 'queries': ['cyber'], 'max_jobs': 150}},
    {'key': 'datadog', 'name': 'Datadog · France Security', 'kind': 'greenhouse', 'description': 'Security engineering roles published on the company career board.', 'config': {'board_token': 'datadog', 'company': 'Datadog', 'location_contains': ['france', 'paris'], 'title_contains': ['security', 'detection', 'identity']}},
]


# Search intent, not claimed candidate skills. Keep each public query bounded.
FRANCE_JUNIOR_QUERIES = ['analyste SOC junior', 'technicien support informatique', 'administrateur reseaux junior', 'pentester junior', 'cybersecurite junior', 'blue team junior', 'red team junior', 'helpdesk', 'network engineer junior']
for item in CATALOG:
    if item['kind'] in ('linkedin', 'apec'):
        item['config']['queries'] = list(FRANCE_JUNIOR_QUERIES)
        item['config']['max_pages_per_query'] = 1
        item['config']['max_jobs'] = 180
    elif item['kind'] == 'smartrecruiters':
        item['config']['queries'] = ['SOC', 'support informatique', 'reseaux', 'pentest', 'cyber', 'security']
