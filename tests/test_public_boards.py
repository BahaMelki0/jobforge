import httpx
from app.sources.public_boards import ApecSource, LinkedInSource, WttjSource, jobposting, cyber_role


def transport_for(adapter, handler):
    adapter.client = lambda: httpx.Client(transport=httpx.MockTransport(handler))


def test_apec_summaries_survive_blocked_details():
    calls=[]
    def handle(request):
        calls.append(request.url.path)
        if request.method == 'POST':
            return httpx.Response(200,json={'totalCount':2,'resultats':[
                {'numeroOffre':str(i),'intitule':'Analyste SOC','nomCommercial':'Example','lieuTexte':'Paris','texteOffre':'A brief summary.'} for i in range(2)]})
        return httpx.Response(403)
    adapter=ApecSource();transport_for(adapter,handle)
    jobs=adapter.fetch({'queries':['SOC'],'max_pages_per_query':1})
    assert len(jobs)==2
    assert all(j.raw['detail_status']=='summary' for j in jobs)
    assert calls.count('/cms/webservices/offre/public')==1
    assert adapter.diagnostics['warnings']


def test_linkedin_pages_and_detail_extraction():
    def handle(request):
        if 'seeMoreJobPostings' in request.url.path:
            assert request.url.params['location']=='France'
            return httpx.Response(200,text='''<div class="base-search-card" data-entity-urn="urn:li:jobPosting:123"><h3 class="base-search-card__title">Junior pentester</h3><h4 class="base-search-card__subtitle">Example</h4><span class="job-search-card__location">Paris, France</span><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123?tracking=abc"></a><time datetime="2026-09-22"></time></div>''')
        return httpx.Response(200,text='<div class="show-more-less-html__markup">Pentest Active Directory networks.</div>')
    adapter=LinkedInSource();transport_for(adapter,handle)
    jobs=adapter.fetch({'queries':['pentest'],'max_jobs':1})
    assert jobs[0].description=='Pentest Active Directory networks.'
    assert jobs[0].url=='https://www.linkedin.com/jobs/view/123'
    assert jobs[0].raw['detail_status']=='full'
    assert adapter.diagnostics['capped']


def test_wttj_blocked_detail_is_unverified_not_fake_france_job():
    requests=[]
    def handle(request):
        requests.append(request.url.path)
        if 'index.xml' in request.url.path:
            return httpx.Response(200,text='<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://www.welcometothejungle.com/sitemaps/job-listings.0.xml.gz</loc></sitemap></sitemapindex>')
        if 'job-listings' in request.url.path:
            return httpx.Response(200,text='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://www.welcometothejungle.com/fr/companies/example/jobs/pentest-engineer_paris</loc><lastmod>2026-09-22</lastmod></url></urlset>')
        return httpx.Response(403)
    adapter=WttjSource();transport_for(adapter,handle)
    jobs=adapter.fetch({})
    assert len(jobs)==1
    assert jobs[0].location=='Location unverified'
    assert jobs[0].raw['detail_status']=='link_only'
    assert jobs[0].description==''
    assert adapter.diagnostics['warnings']


def test_structured_job_and_noise_filters():
    assert cyber_role('Ingénieur cybersécurité')
    assert not cyber_role('Agent de sécurité incendie')
    job=jobposting('''<script type="application/ld+json">{"@type":"JobPosting","title":"Security Engineer","description":"<p>Security work</p>","hiringOrganization":{"name":"Example"},"jobLocation":{"address":{"addressCountry":"FR"}},"identifier":{"value":"123"}}</script>''','https://example.com/jobs/123')
    assert job.source_job_id=='123' and job.location=='FR'
    assert job.description=='Security work'
