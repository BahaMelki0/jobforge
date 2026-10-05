# JobForge

Recent additions: conservative exact-content cross-source vacancy merging with retained source observations; relevant profile/project retrieval for local AI; application follow-up dates and interview notes; and certification checks that preserve CPTS as ongoing. New source observations populate on subsequent scans; older duplicate rows are not mass-merged automatically. Existing owner profiles can be enriched from supplied facts with `python scripts/enrich_personal_profile.py`, which saves a JSON backup first.

JobForge shares the **Obsidian Signal** project identity with APK Sentinel and Detection Forge: graphite surfaces, signal red, consistent severity colors, and a dark-first workspace. Canonical shared tokens live in `app/static/obsidian.css`; JobForge layouts and overrides live in `app/static/app.css` and `app/static/design-system.css`.

## Live discovery and recruiter studio

### Automatic board coverage

Cards and job details show the publisher's **posting date**, separately from first discovery. Offers older than 30 days are removed at each scan/import, as requested. Explicit publisher deadlines and clear closed/inactive statuses also remove offers from active discovery; unknown status is labelled for a manual check with a direct link to the publisher. Tracked application history remains archived.

The catalog now includes **LinkedIn public jobs**, **APEC**, **Welcome to the Jungle sitemap discovery**, and **CyberSecurityJobsite France**, in addition to company ATS feeds. They use the same startup/two-hour scan worker and database. No login cookies, proxy rotation or challenge bypass is used.

- LinkedIn: paginated public search and descriptions. Stops on an access restriction and reports partial coverage.
- APEC: paginated public search. If the publisher blocks description access, jobs retain a labelled search summary. Scores then have less evidence than full descriptions.
- WTTJ: scans published job sitemaps and attempts public JobPosting extraction. When descriptions are blocked, the app stores **unverified links**, using a title derived from the URL. These are not confirmed open jobs or confirmed France locations: `/fr/` is a language path. They remain unranked and cannot generate AI messages/packages until a description is imported. This is automatic discovery, not complete WTTJ extraction.
- CyberSecurityJobsite: paginated France listings and structured descriptions, with role filtering and advertised-expiry checks.

The source panel exposes **Edit search & limits**. Defaults are 100 LinkedIn jobs (four pages per query), 150 APEC jobs (five pages per query), 150 WTTJ links (nine sitemaps), and 100 CyberSecurityJobsite jobs (eight pages). Company SmartRecruiters limits were raised from 35 to 150. Scan history shows fetched/filtered counts, pages, content completeness, warnings and **LIMIT REACHED**. A result cap is a collection budget, not the total market or the best-ranked set.

Open `http://127.0.0.1:8000`. **Live sources** offers one-click connections for Devoteam, Sopra Steria and Datadog. Connecting a catalog source hides demo jobs. **Scan live sources** returns immediately and displays progress, per-source counts, failures and next-run time. Scan history persists in SQLite. Startup scans and manual scans share one worker; subsequent scheduled scans run two hours after completion. Collection is polling, not a push feed. SmartRecruiters collection limits and queries are configurable; current catalog defaults allow up to 150 listings per company.

**Draft outreach** on a job opens the Recruiter studio: choose French/English and a tone, optionally name the recipient, then generate a connection note, recruiter message and email with local Ollama. Edit, copy and save drafts independently of application packages. The default model is `qwen3.5:9b`; choose the 4B Fast option in the studio for quicker drafts. `run.ps1` starts Ollama if needed. Generation failures are shown explicitly, without a template masquerading as AI output. Messages are never sent. Seed profile facts still require your review.

Use **Import a listing** to add copied job descriptions or enrich a discovered link. It deduplicates, ranks and enables the same drafting workflow. No mailbox integration is configured.

Validation from the October 5 implementation pass: 68 Python tests plus UI interaction and formatting checks passed. These checks do not establish current live-board coverage or visual correctness.

A full local-first job discovery, ranking, application-generation and tracking app built for cybersecurity job hunting.

## What it does

- Pulls jobs from multiple source types: Greenhouse, Lever, RSS, schema.org `JobPosting` pages, optional JobSpy, plus a built-in demo source.
- Normalizes and deduplicates listings into one database.
- Ranks jobs using explainable deterministic scoring for role family, skills, priority keywords, geography, seniority and employment type.
- Optionally enriches fit analysis with an LLM.
- Generates a complete application package per job: tailored CV text/PDF, cover letter text/PDF, recruiter message, email, why-company paragraph and interview-prep JSON.
- Tracks application status from `generated` through interview stages to `offer`/`rejected`.
- Runs as a browser dashboard with a REST API.
- Includes automated tests and a seeded profile/demo source so the whole workflow is testable without external credentials.

## Quick start

```bash
cd jobforge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open: `http://127.0.0.1:8000`

Startup automatically refreshes enabled sources and ranks new or changed listings. The demo source creates four fictional cybersecurity jobs. Configure real sources in the Sources tab for live collection.

On Windows, after installing dependencies and copying `.env.example` to `.env`, run `./run.ps1` from PowerShell. No virtual-environment activation is needed. Leave that terminal running; closing the browser does not stop collection. Press Ctrl+C in the terminal to stop. Relaunching triggers a fresh scan against the same database. Use one app process/worker per database; the scan lock is process-local. `--reload` is for development and each reload triggers a startup scan.

## Run tests

```bash
pytest -q
```

The test suite checks ranking behavior, deduplication fingerprints, API startup/demo ingestion and end-to-end application package generation.

## Docker

```bash
cp .env.example .env
mkdir -p runtime generated_applications
docker compose up --build
```

Then open `http://127.0.0.1:8000`.

## LLM configuration

The app works without an LLM using deterministic ranking and template-based application generation.

Local Ollama is the configured default. A legacy optional hosted provider exists in the code, but is not needed for the local workflow.

For a local Ollama server:

```env
JOBFORGE_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_FAST_MODEL=qwen3.5:4b
```

For no external model:

```env
JOBFORGE_LLM_PROVIDER=none
```

## Adding sources

Use the **Sources** tab in the web UI.

### Greenhouse

```json
{
  "board_token": "company-board-token",
  "company": "Company Name"
}
```

### Lever

```json
{
  "site": "company-site-name",
  "company": "Company Name"
}
```

### RSS

```json
{
  "url": "https://example.com/jobs.rss",
  "company": "Company Name",
  "location": "France"
}
```

### JSON-LD

For job pages that publish schema.org `JobPosting` JSON-LD:

```json
{
  "url": "https://example.com/careers/job-page",
  "company": "Company Name"
}
```

or multiple pages:

```json
{
  "urls": [
    "https://example.com/jobs/1",
    "https://example.com/jobs/2"
  ]
}
```

### Optional JobSpy source

JobSpy can aggregate several public job sites, but these sites can change markup, rate-limit or restrict automated access. Use it only where permitted by the site's terms/robots requirements and expect occasional breakage.

Install:

```bash
pip install -r requirements-full.txt
```

Enable in `.env`:

```env
JOBFORGE_ENABLE_JOBSPY=true
```

Example source config:

```json
{
  "queries": [
    "junior penetration tester",
    "cloud security engineer",
    "identity security engineer",
    "SOC analyst cybersecurity"
  ],
  "sites": ["indeed", "linkedin", "glassdoor", "google"],
  "location": "France",
  "results_wanted": 50,
  "hours_old": 168
}
```

## Profile/ranking design

The seeded profile is oriented around four role families:

- Offensive Security / Pentest / Red Team
- Cloud & Identity Security
- Blue Team / SOC / Detection
- Cybersecurity / Security Consulting

Edit the entire profile in the UI. The ranking engine deliberately keeps hard/observable constraints separate from LLM analysis:

1. deterministic score is calculated first;
2. optional LLM semantic fit is requested;
3. final score = 70% deterministic + 30% semantic;
4. the UI shows strengths, gaps and the score breakdown.

That prevents the LLM from silently overriding obvious constraints such as seniority or geography.

## Application generation

Open a role, then click **Generate package**. A package is written to `generated_applications/` and can be downloaded as ZIP from the Applications tab.

Generated files:

```text
application.json
cover_letter.txt
cover_letter.pdf
email.txt
interview_prep.json
recruiter_message.txt
tailored_cv.txt
tailored_cv.pdf
```

The LLM prompt explicitly prohibits inventing credentials, employers, dates, client work or quantified achievements. Always review generated application material before sending it.

## Scheduled collection

Set:

```env
JOBFORGE_AUTO_REFRESH=true
JOBFORGE_SCRAPE_INTERVAL_MINUTES=120
```

The FastAPI lifespan immediately starts a background refresh, then waits two hours after each completed cycle before the next scan. `.env` is loaded automatically; existing environment variables take precedence. Scans execute off the web event loop and manual/scheduled collection is serialized. Shutdown waits for an in-progress scan to finish. Jobs, application statuses and packages persist; unchanged jobs retain existing AI scores. Failed or empty fetches do not mark listings closed. Restarting always scans again. For a large deployment, replace this with an external worker/queue.

Local defaults use Ollama with `qwen3.5:9b` for stronger writing and tool use. The `qwen3.5:4b` Fast option is available in the studio. When Ollama is stopped or a model is missing, deterministic ranking remains available; AI generation reports an error. Explicit provider `none` selects template workflows. The included candidate profile is seed material: verify its education, dates and experience before using generated applications.

## API highlights

- `GET /api/health`
- `GET/PUT /api/profile`
- `GET/POST /api/sources`
- `POST /api/sources/{id}/refresh`
- `POST /api/sources/refresh-all`
- `GET /api/jobs`
- `POST /api/jobs/{id}/rank`
- `POST /api/jobs/rank-all`
- `POST /api/jobs/{id}/application`
- `GET /api/jobs/{id}/observations`
- `GET/PUT /api/applications/{id}/followup`
- `GET /api/applications`
- `PATCH /api/applications/{id}/status`
- `GET /api/applications/{id}/download`

FastAPI also exposes interactive API documentation at `/docs`.

## Notes on scraping

The stable adapters use public ATS endpoints or structured job metadata. Sites such as LinkedIn/Indeed can use anti-bot measures and contractual restrictions, so the optional aggregation adapter is separated from the core application. Prefer ATS APIs, company career pages, RSS feeds and job-alert ingestion where possible.

## Production hardening ideas

The supplied project is runnable and testable as-is. For an Internet-facing multi-user deployment, add authentication, CSRF protection, secret management, a queue/worker, rate limiting, encrypted profile storage, PostgreSQL and source-specific retry/backoff policies.


## Local AI performance and refinement

The France/junior ranking rules remain deterministic. No fine-tuning has been performed; generation uses your saved profile evidence.

Recruiter studio generates one selected draft at a time. Work is queued on a single model worker, with progress and cancellation visible above the workspace. You can continue browsing. Identical requests reuse saved results; changed profile/job/options invalidate the cache. Interrupted requests are marked failed after restart. Failed application generation reports an error instead of silently substituting templates.

The default listing view includes full descriptions; use Listing completeness to see summaries or discovered links. Lists paginate at 24 results and can sort by posting date. Unknown dates remain explicitly unknown. Scans still run on startup and every 120 minutes while the app remains running; publisher restrictions appear in source diagnostics.

Validation: `.\.venv\Scripts\python.exe -m pytest -q`; UI interaction checks: `npm ci` then `node tests/ui.cjs` (DOM tests, not visual browser tests).


## France / junior focus

The default shortlist requires a France location plus junior or 0-2 years experience evidence. Security, cloud/identity, blue team/SOC, offsec/pentesting/red team, networking/systems and IT support/help desk are separate role families. Unknown locations and unstated seniority go to Needs verification; internships/apprenticeships have a separate view. Explicit senior titles, requirements above two years, foreign locations and unrelated job families are outside the default focus. No job history is deleted by these filters. French-language text alone does not establish a France location. Location matching is conservative and some unrecognized French towns require review.

Scores are capped at 39 for excluded roles and 69 for uncertain roles, including AI-enriched scores. Experience parsing handles French/English ranges while ignoring durations without experience context. Source queries prioritize junior France searches, including support and networking. Rules are heuristics: verify the original offer before applying.


## AI studio update (24 September 2026)

Configured quality model: `qwen3.5:9b`, installed locally. Model choice and latency depend on available hardware. `qwen3.5:4b` is available as an explicitly selected Fast mode. The application uses the local Ollama endpoint; no cloud inference or fine-tuning is used. Models run with a 4096-token context, thinking disabled, bounded output and one generation worker, with only one model loaded to reduce memory pressure. The 9B model also powers the read-only tool-calling job-fit review.

Earlier benchmark outputs are stored under `runtime/`. The October 5 review found student wording and excessive mastery claims, prompting graduation-fact and wording corrections. Five revised workflows passed, and support outreach passed its targeted retest; these small local checks are not a factual-accuracy score or a guarantee for every job. Drafts still need review, especially claims about experience and transferable skills. Keep Fast mode available if other programs compete for GPU memory or you need lower latency.

Model availability: use `ollama list` to confirm the configured tags on your machine.

The Local AI studio shows model readiness and recent work. Prepare model loads it ahead of drafting. Job-specific writing uses a brief/editor split, saved versions, character and word counts, explicit regeneration, and unsaved-edit protection. Career history uses structured editable cards, preserving additional metadata. AI work remains local and nothing is sent to recruiters automatically.

Reproduce the benchmark: `.\.venv\Scripts\python.exe scripts/benchmark_local_ai.py --models qwen3.5:4b qwen3.5:9b`. Detailed generated outputs stay under `runtime/`. UI verification uses DOM interaction tests; the in-app browser was unavailable for visual screenshot QA in this session.


## Read-only agent review

On a selected full listing, use **Investigate fit with agent**. A local Ollama tool-calling loop retrieves the saved candidate evidence, the selected job requirements, and the deterministic France/junior eligibility result. It then produces a structured review with evidence, gaps and next steps. Saved results open from Local AI studio.

The tool registry is fixed: `read_candidate_profile`, `read_job_requirements`, `check_career_focus`. These tools accept no arguments and cannot access other files, arbitrary URLs, a shell, email or application submission. The loop allows at most three tool-selection rounds and six tool calls, enforces the configured timeout and cancellation, and refuses to finish without retrieving all three evidence sources. The review does not change rankings or submit applications. It remains an AI assessment to review, not verified fact.

Quality mode is now the default for every AI workflow, including model preparation. Faster mode is explicit. If `run.ps1` starts Ollama, it enables flash attention and limits loaded models to one to reduce GPU memory pressure.


## Current UI and handover

Discovery uses one dark canvas with elevated cards; hover and focus follow the red brand accent. Job-detail badges and listing actions share centered alignment; narrow screens wrap actions and stack fit cards. Dialog close controls use a fixed dark square and visible focus. Follow-up/interview notes and source provenance use dialogs.

The local profile enrichment includes supplied RandoriSec internship work, KPMG experience, portfolio evidence, certifications and graduate status. Evidence selection prefers relevant saved projects. Credential and modest-wording checks cover selected mistakes, not all possible invented claims. Review every generated sentence and PDF before sending.

See [local AI operation and validation](docs/LOCAL_AI.md). No fine-tuning has been performed. Clean installation, browser visual review and live-board coverage remain manual release checks. Repository: https://github.com/BahaMelki0/jobforge.
