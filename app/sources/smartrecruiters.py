from datetime import datetime
from urllib.parse import quote
import time

import httpx
from bs4 import BeautifulSoup

from .base import NormalizedJob
from .public_boards import cyber_role


class SmartRecruitersSource:
    """Public published jobs, bounded pagination and France filtering before detail requests."""

    def fetch(self, config):
        self.diagnostics = {'examined': 0, 'filtered': 0, 'pages': 0, 'capped': False, 'warnings': []}
        company = config['company_identifier']
        base = f'https://api.smartrecruiters.com/v1/companies/{quote(company, safe="")}/postings'
        limit = min(1000, max(1, int(config.get('max_jobs', 150))))
        out, seen = [], set()
        with httpx.Client(timeout=25, follow_redirects=True) as client:
            for query in config.get('queries', ['cyber', 'security']):
                for offset in range(0, 1000, 100):
                    response = client.get(base, params={'q': query, 'country': 'fr', 'limit': 100, 'offset': offset})
                    response.raise_for_status()
                    data = response.json()
                    self.diagnostics['pages'] += 1
                    for item in data.get('content', []):
                        self.diagnostics['examined'] += 1
                        if item['id'] in seen or item.get('location', {}).get('country', '').lower() != 'fr':
                            continue
                        if not cyber_role(item.get('name', '')):
                            self.diagnostics['filtered'] += 1
                            continue
                        seen.add(item['id'])
                        detail = client.get(f'{base}/{item["id"]}')
                        detail.raise_for_status()
                        job = detail.json()
                        sections = job.get('jobAd', {}).get('sections', {})
                        text = '\n\n'.join(BeautifulSoup(section.get('text', ''), 'html.parser').get_text('\n', strip=True) for section in sections.values() if isinstance(section, dict))
                        location = job.get('location', {})
                        out.append(NormalizedJob(
                            source_job_id=item['id'], title=job.get('name', item['name']),
                            company=job.get('company', {}).get('name', company),
                            location=location.get('fullLocation') or f"{location.get('city', '')}, France",
                            url=job.get('applyUrl') or f'https://jobs.smartrecruiters.com/{company}/{item["id"]}',
                            description=text,
                            requirements=BeautifulSoup(sections.get('qualifications', {}).get('text', ''), 'html.parser').get_text('\n', strip=True),
                            employment_type=job.get('typeOfEmployment', {}).get('label', ''),
                            remote='Hybrid' if location.get('hybrid') else 'Remote' if location.get('remote') else 'On-site',
                            published_at=datetime.fromisoformat(job['releasedDate'].replace('Z', '+00:00')) if job.get('releasedDate') else None,
                            raw={**job, 'source_status': 'open'},
                        ))
                        if len(out) >= limit:
                            self.diagnostics['capped'] = True
                            return out
                        time.sleep(0.15)
                    if offset + 100 >= data.get('totalFound', 0):
                        break
        return out
