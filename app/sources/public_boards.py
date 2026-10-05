"""Bounded public-page collectors. No accounts, proxy rotation or challenge bypass."""
import gzip
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from .base import NormalizedJob


def text(value):
    return BeautifulSoup(value or '', 'html.parser').get_text(' ', strip=True)


def cyber_role(title):
    from ..services.focus import target_role
    return target_role(title)


def parsed_date(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def canonical(url):
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip('/'), '', ''))


class Board:
    def __init__(self):
        self.diagnostics = {'examined': 0, 'filtered': 0, 'pages': 0, 'capped': False, 'warnings': []}

    def client(self):
        return httpx.Client(timeout=20, follow_redirects=True, headers={'User-Agent': 'JobForge/1.1 (personal job discovery)'})

    def warn(self, message):
        if message not in self.diagnostics['warnings']:
            self.diagnostics['warnings'].append(message)

    def get(self, client, url, **kwargs):
        response = client.get(url, **kwargs)
        response.raise_for_status()
        return response


class LinkedInSource(Board):
    def fetch(self, config):
        out, seen = [], set()
        maximum = min(500, int(config.get('max_jobs', 100)))
        page_limit = min(20, int(config.get('max_pages_per_query', 4)))
        detail_blocked = False
        with self.client() as client:
            for query in config.get('queries', ['cybersecurity', 'pentest', 'SOC analyst', 'identity security']):
                for page in range(page_limit):
                    try:
                        response = self.get(client, 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search', params={
                            'keywords': query, 'location': config.get('location', 'France'),
                            'start': page * 10, 'f_TPR': f'r{int(config.get("days", 30))*86400}', 'sortBy': 'DD'})
                    except httpx.HTTPError as exc:
                        if not out:
                            raise
                        self.warn(f'Search stopped: {exc.__class__.__name__}. Collected results retained.')
                        return out
                    self.diagnostics['pages'] += 1
                    cards = BeautifulSoup(response.text, 'html.parser').select('.base-search-card')
                    if not cards:
                        if not out and any(x in response.text.lower() for x in ['captcha', 'authwall', 'sign in to linkedin']):
                            raise RuntimeError('LinkedIn requires sign-in or a challenge; collection stopped.')
                        break
                    fresh = 0
                    for card in cards:
                        self.diagnostics['examined'] += 1
                        title = card.select_one('.base-search-card__title')
                        link = card.select_one('a.base-card__full-link')
                        if not title or not link:
                            continue
                        title = title.get_text(' ', strip=True)
                        if not cyber_role(title):
                            self.diagnostics['filtered'] += 1
                            continue
                        job_id = card.get('data-entity-urn', '').rsplit(':', 1)[-1]
                        if not job_id or job_id in seen:
                            continue
                        seen.add(job_id)
                        fresh += 1
                        company = card.select_one('.base-search-card__subtitle')
                        location = card.select_one('.job-search-card__location')
                        date = card.select_one('time[datetime]')
                        description, employment = '', ''
                        if not detail_blocked:
                            try:
                                detail = self.get(client, f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}')
                                soup = BeautifulSoup(detail.text, 'html.parser')
                                body = soup.select_one('.show-more-less-html__markup')
                                description = body.get_text('\n', strip=True) if body else ''
                                for criteria in soup.select('.description__job-criteria-item'):
                                    if 'Employment type' in criteria.get_text():
                                        employment = criteria.get_text(' ', strip=True).replace('Employment type', '').strip()
                            except httpx.HTTPError:
                                detail_blocked = True
                                self.warn('LinkedIn detail access unavailable; remaining results are marked link-only.')
                            time.sleep(0.4)
                        out.append(NormalizedJob(job_id, title, company.get_text(' ', strip=True) if company else '',
                            location.get_text(' ', strip=True) if location else '', canonical(link['href']),
                            description=description, employment_type=employment,
                            published_at=parsed_date(date.get('datetime')) if date else None,
                            raw={'detail_status': 'full' if description else 'link_only', 'discovery_query': query, 'source_status': 'open'}))
                        if len(out) >= maximum:
                            self.diagnostics['capped'] = True
                            return out
                    if not fresh and page > 0:
                        break
                    if page == page_limit - 1:
                        self.diagnostics['capped'] = True
                    time.sleep(0.5)
        return out


class ApecSource(Board):
    def fetch(self, config):
        out, seen = [], set()
        maximum = min(1000, int(config.get('max_jobs', 150)))
        pages = min(30, int(config.get('max_pages_per_query', 5)))
        detail_blocked = False
        with self.client() as client:
            for query in config.get('queries', ['cybersecurite', 'pentest', 'analyste SOC', 'IAM']):
                for page in range(pages):
                    criteria = {'motsCles': query, 'typeClient': 'CADRE', 'activeFiltre': True,
                        'pagination': {'startIndex': page * 20, 'range': 20},
                        'sorts': [{'type': 'DATE', 'direction': 'DESCENDING'}]}
                    response = client.post('https://www.apec.fr/cms/webservices/rechercheOffre', json=criteria)
                    response.raise_for_status()
                    data = response.json()
                    if 'resultats' not in data:
                        raise RuntimeError('APEC search response changed: missing resultats')
                    self.diagnostics['pages'] += 1
                    rows = data['resultats']
                    for item in rows:
                        self.diagnostics['examined'] += 1
                        if not cyber_role(item.get('intitule', '')):
                            self.diagnostics['filtered'] += 1
                            continue
                        job_id = item['numeroOffre']
                        if job_id in seen:
                            continue
                        seen.add(job_id)
                        description = text(item.get('texteOffre'))
                        detail_status = 'summary'
                        if not detail_blocked:
                            try:
                                detail = self.get(client, 'https://www.apec.fr/cms/webservices/offre/public', params={'numeroOffre': job_id}).json()
                                parts = [detail.get(k) for k in ('texteHtml', 'texteOffre', 'descriptifPoste', 'profilRecherche', 'texteProfil', 'texteEntreprise') if isinstance(detail.get(k), str)]
                                if parts and len(text(' '.join(parts))) > len(description):
                                    description, detail_status = text('\n'.join(parts)), 'full'
                            except (httpx.HTTPError, ValueError):
                                detail_blocked = True
                                self.warn('APEC job details blocked; search summaries retained and labelled summary-only.')
                            time.sleep(0.3)
                        location = item.get('lieuTexte', '')
                        out.append(NormalizedJob(job_id, item['intitule'], item.get('nomCommercial', ''), location,
                            f'https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{job_id}',
                            description=description, salary=item.get('salaireTexte', ''), published_at=parsed_date(item.get('datePublication')),
                            raw={'detail_status': detail_status, 'discovery_query': query, 'source_status': 'open'}))
                        if len(out) >= maximum:
                            self.diagnostics['capped'] = True
                            return out
                    if (page+1)*20 >= data.get('totalCount', 0) or not rows:
                        break
                    if page == pages-1:
                        self.diagnostics['capped'] = True
                    time.sleep(0.3)
        return out


def jobposting(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.get_text())
        except ValueError:
            continue
        queue = payload if isinstance(payload, list) else [payload]
        while queue:
            obj = queue.pop()
            if not isinstance(obj, dict):
                continue
            queue.extend(obj.get('@graph', []))
            if obj.get('@type') != 'JobPosting':
                continue
            locations = obj.get('jobLocation') or []
            if isinstance(locations, dict):
                locations = [locations]
            names = []
            for loc in locations:
                address = loc.get('address') or {}
                names.append(', '.join(str(address[k]) for k in ('addressLocality', 'addressRegion', 'addressCountry') if address.get(k)))
            identifier = obj.get('identifier') or url
            if isinstance(identifier, dict):
                identifier = identifier.get('value') or url
            employment = obj.get('employmentType', '')
            return NormalizedJob(str(identifier), obj.get('title', ''), (obj.get('hiringOrganization') or {}).get('name', ''),
                '; '.join(names), canonical(url), description=text(obj.get('description')),
                employment_type=', '.join(employment) if isinstance(employment, list) else employment,
                published_at=parsed_date(obj.get('datePosted')), raw={'detail_status': 'full', 'valid_through': obj.get('validThrough')})
    return None


class WttjSource(Board):
    """Discover public sitemap URLs even when the publisher blocks description access."""
    def fetch(self, config):
        candidates, seen, out = [], set(), []
        maximum = min(1000, int(config.get('max_jobs', 150)))
        maps = min(30, int(config.get('max_sitemaps', 9)))
        with self.client() as client:
            index = self.get(client, 'https://www.welcometothejungle.com/sitemaps/index.xml.gz')
            root = self.xml(index.content)
            urls = [n.text for n in root.iter() if n.tag.endswith('}loc') and '/job-listings.' in (n.text or '')]
            self.diagnostics['capped'] = len(urls) > maps
            for sitemap in urls[:maps]:
                if urlsplit(sitemap).netloc != 'www.welcometothejungle.com':
                    continue
                root = self.xml(self.get(client, sitemap).content)
                self.diagnostics['pages'] += 1
                for node in root:
                    loc = node.find('{*}loc')
                    if loc is None or '/fr/companies/' not in (loc.text or '') or '/jobs/' not in loc.text:
                        continue
                    url = loc.text
                    role = unquote(url.split('/jobs/')[-1].split('_')[0]).replace('-', ' ')
                    self.diagnostics['examined'] += 1
                    if not cyber_role(role):
                        self.diagnostics['filtered'] += 1
                        continue
                    if url in seen:
                        continue
                    seen.add(url)
                    modified = node.find('{*}lastmod')
                    candidates.append((modified.text if modified is not None else '', url, role))
                time.sleep(0.2)
            candidates.sort(reverse=True)
            self.diagnostics['candidate_links'] = len(candidates)
            self.diagnostics['capped'] |= len(candidates) > maximum
            blocked = False
            for _, url, role in candidates[:maximum]:
                job = None
                if not blocked:
                    try:
                        response = self.get(client, url)
                        job = jobposting(response.text, url)
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code in (403, 429):
                            blocked = True
                            self.warn('WTTJ blocks job descriptions. Sitemap links are discovered automatically but remain unverified, unranked and ineligible for AI drafts until a description is imported.')
                        elif exc.response.status_code in (404, 410):
                            continue
                        else:
                            self.warn('Some WTTJ descriptions could not be fetched.')
                    except httpx.HTTPError:
                        self.warn('Some WTTJ descriptions timed out.')
                    time.sleep(0.3)
                if job:
                    if job.location and not re.search(r'\bFR\b|France', job.location, re.I):
                        self.diagnostics['filtered'] += 1
                        continue
                    job.raw = {**job.raw, 'source_status': 'open'}
                else:
                    company_slug = url.split('/companies/')[1].split('/')[0]
                    job = NormalizedJob(url, role.capitalize(), company_slug.replace('-', ' ').title(), 'Location unverified', url,
                        description='', raw={'detail_status': 'link_only', 'title_from_url': True, 'country_unverified': True})
                out.append(job)
        return out

    @staticmethod
    def xml(content):
        return ET.fromstring(gzip.decompress(content) if content[:2] == b'\x1f\x8b' else content)


class CyberSecurityJobsiteSource(Board):
    def fetch(self, config):
        out, seen = [], set()
        maximum = min(500, int(config.get('max_jobs', 100)))
        max_pages = min(30, int(config.get('max_pages', 8)))
        with self.client() as client:
            for page in range(1, max_pages+1):
                url = 'https://www.cybersecurityjobsite.com/jobs/france/' + (f'{page}/' if page > 1 else '')
                response = self.get(client, url)
                soup = BeautifulSoup(response.text, 'html.parser')
                self.diagnostics['pages'] += 1
                anchors = soup.select('a[href]')
                for anchor in anchors:
                    href = anchor.get('href', '').strip()
                    if not href.startswith('/job/'):
                        continue
                    target = canonical(urljoin(url, href))
                    if target in seen:
                        continue
                    seen.add(target)
                    self.diagnostics['examined'] += 1
                    if not cyber_role(anchor.get_text(' ', strip=True)):
                        self.diagnostics['filtered'] += 1
                        continue
                    try:
                        job = jobposting(self.get(client, target).text, target)
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code in (404, 410):
                            continue
                        raise
                    if job:
                        job.raw = {**job.raw, 'source_status': 'open'}
                        expiry = parsed_date(job.raw.get('valid_through'))
                        if expiry and expiry < datetime.now(timezone.utc):
                            self.diagnostics['filtered'] += 1
                            continue
                        out.append(job)
                    if len(out) >= maximum:
                        self.diagnostics['capped'] = True
                        return out
                    time.sleep(0.3)
                if not any(a.get_text(strip=True) == 'Next' for a in anchors):
                    break
                if page == max_pages:
                    self.diagnostics['capped'] = True
        return out
