from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .models import Application, CandidateProfile, Job, JobScore, Source, ScanRun, MessageDraft
from .schemas import ApplicationOut, JobOut, ProfileOut, ProfileUpdate, SourceCreate, SourceOut
from .seed import ensure_seed_data
from .services.application_generator import generate_application
from .services.ingest import run_all_sources, run_source
from .services.retention import application_state
from .services.llm import LLMService
from .services.ranking import RankingResult, rank_job, save_score
from .services.scheduler import scheduler_loop
from .services import discovery, ai_tasks
from .services.llm import model_status, warm_model
from .models import AITask
from .schemas import AITaskRequest
from .schemas import MessageRequest, MessageContent, JobImport
from .source_catalog import CATALOG
from .models import ApplicationFollowup, JobObservation
from .schemas import FollowupUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Small forward-only SQLite migration for existing personal databases.
    if engine.dialect.name == 'sqlite':
        from sqlalchemy import inspect, text
        columns = {column['name'] for column in inspect(engine).get_columns('jobs')}
        with engine.begin() as connection:
            if 'application_status' not in columns:
                connection.execute(text("ALTER TABLE jobs ADD COLUMN application_status VARCHAR(30) NOT NULL DEFAULT 'unknown'"))
            if 'application_deadline' not in columns:
                connection.execute(text('ALTER TABLE jobs ADD COLUMN application_deadline DATETIME'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_jobs_application_status ON jobs (application_status)'))
    db = SessionLocal()
    try:
        ensure_seed_data(db)
        for job in db.scalars(select(Job).where(Job.application_status == 'unknown')).all():
            status, deadline = application_state(job)
            job.application_status = status
            job.application_deadline = deadline
            if status in {'expired', 'closed'}:
                job.active = False
        db.commit()
        from .services.retention import purge_expired
        purge_expired(db)
        discovery.recover_interrupted(db)
    finally:
        db.close()
    stop = asyncio.Event()
    ai_tasks.start_worker()
    task = None
    if settings.auto_refresh:
        task = asyncio.create_task(scheduler_loop(stop))
    yield
    stop.set()
    await asyncio.to_thread(ai_tasks.stop_worker)
    if task:
        try:
            await task
        except Exception:
            pass
    else:
        await asyncio.to_thread(discovery.join_scan)


app = FastAPI(title="JobForge", version="1.0.0", lifespan=lifespan)
BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


@app.get('/api/jobs/{job_id}/observations')
def job_observations(job_id: int, db: Session = Depends(get_db)):
    if db.get(Job, job_id) is None:
        raise HTTPException(404, 'Job not found')
    return [{'source_id': row.source_id, 'url': row.url, 'status': row.status, 'checked_at': row.checked_at}
            for row in db.scalars(select(JobObservation).where(JobObservation.job_id == job_id)).all()]


@app.get('/api/applications/{application_id}/followup')
def get_followup(application_id: int, db: Session = Depends(get_db)):
    if db.get(Application, application_id) is None:
        raise HTTPException(404, 'Application not found')
    row = db.get(ApplicationFollowup, application_id)
    return {'followup_date': row.followup_date if row else '', 'notes': row.notes if row else ''}


@app.put('/api/applications/{application_id}/followup')
def save_followup(application_id: int, payload: FollowupUpdate, db: Session = Depends(get_db)):
    from datetime import date
    if db.get(Application, application_id) is None:
        raise HTTPException(404, 'Application not found')
    if payload.followup_date:
        try:
            if date.fromisoformat(payload.followup_date).isoformat() != payload.followup_date:
                raise ValueError('Noncanonical date')
        except ValueError:
            raise HTTPException(422, 'Follow-up date must be YYYY-MM-DD')
    row = db.get(ApplicationFollowup, application_id)
    if row is None:
        row = ApplicationFollowup(application_id=application_id)
        db.add(row)
    row.followup_date, row.notes = payload.followup_date, payload.notes
    db.commit()
    return payload


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/api/health")
def health():
    llm = LLMService()
    return {
        "ok": True,
        "version": "1.0.0",
        "llm_provider": settings.llm_provider,
        "llm_available": llm.available(),
        "auto_refresh": settings.auto_refresh,
        "model": settings.ollama_model,
        "interval_minutes": settings.scrape_interval_minutes,
    }


@app.get('/api/ai/status')
def ai_status():
    return model_status()


@app.post('/api/ai/warmup', status_code=202)
def prepare_ai_model():
    try:
        return warm_model()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post('/api/jobs/{job_id}/ai-tasks', status_code=202)
def queue_ai(job_id: int, payload: AITaskRequest):
    try:
        task, cached = ai_tasks.submit(job_id, payload)
        return {'task': task, 'cached': cached}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get('/api/ai-tasks')
def list_ai_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(AITask).order_by(desc(AITask.created_at)).limit(30)).all()


@app.get('/api/ai-tasks/{task_id}')
def get_ai_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(AITask, task_id)
    if not task:
        raise HTTPException(404, 'Task not found')
    return task


@app.post('/api/ai-tasks/{task_id}/cancel')
def cancel_ai_task(task_id: str):
    try:
        return ai_tasks.cancel(task_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    p = db.scalar(select(CandidateProfile).limit(1))
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@app.put("/api/profile", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    p = db.scalar(select(CandidateProfile).limit(1))
    if not p:
        p = CandidateProfile(name=payload.name)
        db.add(p)
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@app.get("/api/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.scalars(select(Source).order_by(Source.name)).all()


@app.get('/api/source-catalog')
def source_catalog():
    return CATALOG


@app.post('/api/source-catalog/{key}/enable')
def enable_catalog(key: str, db: Session = Depends(get_db)):
    item = next((x for x in CATALOG if x['key'] == key), None)
    if not item:
        raise HTTPException(404, 'Unknown catalog source')
    source = db.scalar(select(Source).where(Source.name == item['name']))
    if not source:
        source = Source(name=item['name'], kind=item['kind'], config=item['config'])
        db.add(source)
    source.enabled = True
    for demo in db.scalars(select(Source).where(Source.kind == 'demo')).all():
        demo.enabled = False
        for job in db.scalars(select(Job).where(Job.source_id == demo.id)).all():
            job.active = False
    db.commit()
    return {'ok': True, 'source_id': source.id}


@app.patch('/api/sources/{source_id}/enabled')
def toggle_source(source_id: int, enabled: bool, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, 'Source not found')
    source.enabled = enabled
    db.commit()
    return {'ok': True}


@app.get('/api/scans')
def scans(db: Session = Depends(get_db)):
    return {'running': discovery.running(), 'next_run_at': discovery.next_run(),
            'interval_minutes': settings.scrape_interval_minutes,
            'runs': db.scalars(select(ScanRun).order_by(desc(ScanRun.id)).limit(20)).all()}


@app.post('/api/scans', status_code=202)
def start_scan():
    return {'started': discovery.start_scan(), 'running': True}


@app.post('/api/import-job')
def import_job(payload: JobImport, db: Session = Depends(get_db)):
    from .sources.base import NormalizedJob
    from .services.ingest import upsert_jobs
    from urllib.parse import urlparse
    import hashlib
    from .services.retention import expired, purge_expired
    purge_expired(db)
    if expired(payload.published_at):
        raise HTTPException(422, 'This listing was posted more than 30 days ago and has left your discovery window.')
    if payload.url and urlparse(payload.url).scheme not in {'http', 'https'}:
        raise HTTPException(422, 'Listing URL must use http or https')
    source = db.scalar(select(Source).where(Source.name == 'Imported listings'))
    if not source:
        source = Source(name='Imported listings', kind='manual', enabled=False, config={})
        db.add(source)
        db.commit()
    identity = hashlib.sha256((payload.url or f'{payload.company}|{payload.title}|{payload.location}').encode()).hexdigest()
    upsert_jobs(db, source, [NormalizedJob(source_job_id=identity, **payload.model_dump())])
    job = db.scalar(select(Job).where(Job.url == payload.url)) if payload.url else db.scalar(select(Job).where(Job.source_id == source.id, Job.source_job_id == identity))
    profile = db.scalar(select(CandidateProfile).limit(1))
    if profile:
        save_score(db, job, rank_job(profile, job))
    return {'id': job.id}


@app.get('/api/jobs/{job_id}/messages')
def messages(job_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(MessageDraft).where(MessageDraft.job_id == job_id).order_by(desc(MessageDraft.id))).all()


@app.post('/api/jobs/{job_id}/messages')
def generate_messages(job_id: int, payload: MessageRequest, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    profile = db.scalar(select(CandidateProfile).limit(1))
    if not job or not profile:
        raise HTTPException(404, 'Job or profile not found')
    if job.detail_status == 'link_only':
        raise HTTPException(409, 'This source only exposed a listing link. Import its full description before generating messages.')
    if settings.llm_provider != 'ollama':
        raise HTTPException(503, 'Recruiter studio requires the local Ollama provider.')
    llm = LLMService()
    if not llm.available():
        raise HTTPException(503, f'Start Ollama and install {settings.ollama_model} to generate local AI messages.')
    try:
        content = llm.recruiter_messages(profile, job, payload)
    except Exception as exc:
        raise HTTPException(502, f'Local model could not produce a valid draft ({type(exc).__name__}). Please retry.') from exc
    draft = MessageDraft(job_id=job_id, language=payload.language, tone=payload.tone, model=settings.ollama_model, content=content)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@app.put('/api/messages/{draft_id}')
def edit_message(draft_id: int, payload: MessageContent, db: Session = Depends(get_db)):
    draft = db.get(MessageDraft, draft_id)
    if not draft:
        raise HTTPException(404, 'Draft not found')
    draft.content = payload.model_dump()
    db.commit()
    return {'ok': True}


@app.post("/api/sources", response_model=SourceOut)
def add_source(payload: SourceCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Source).where(Source.name == payload.name)):
        raise HTTPException(409, "A source with that name already exists")
    src = Source(name=payload.name, kind=payload.kind, config=payload.config, enabled=payload.enabled)
    db.add(src)
    db.commit(); db.refresh(src)
    return src


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    db.delete(src); db.commit()
    return {"ok": True}


@app.put('/api/sources/{source_id}', response_model=SourceOut)
def edit_source(source_id: int, payload: SourceCreate, db: Session = Depends(get_db)):
    from .sources import ADAPTERS
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, 'Source not found')
    if payload.kind not in ADAPTERS:
        raise HTTPException(422, 'Unsupported source type')
    other = db.scalar(select(Source).where(Source.name == payload.name, Source.id != source_id))
    if other:
        raise HTTPException(409, 'A source with that name already exists')
    for key, value in payload.model_dump().items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source


@app.post("/api/sources/{source_id}/refresh")
def refresh_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    return run_source(db, src)


@app.post("/api/sources/refresh-all")
def refresh_all(db: Session = Depends(get_db)):
    return {"results": run_all_sources(db)}


@app.get("/api/jobs", response_model=list[JobOut])
def list_jobs(
    q: str = "",
    category: str = "",
    min_score: float = 0,
    active: bool = True,
    application_status: str = '',
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(Job).options(selectinload(Job.score)).outerjoin(JobScore).where(Job.active.is_(active))
    if application_status:
        stmt = stmt.where(Job.application_status == application_status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.company.ilike(like), Job.location.ilike(like), Job.description.ilike(like)))
    if category:
        stmt = stmt.where(JobScore.category == category)
    if min_score > 0:
        stmt = stmt.where(JobScore.total >= min_score)
    stmt = stmt.order_by(desc(JobScore.total), desc(Job.first_seen_at)).limit(limit)
    return db.scalars(stmt).unique().all()


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.scalar(select(Job).options(selectinload(Job.score)).where(Job.id == job_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def _rank_with_optional_llm(db: Session, profile: CandidateProfile, job: Job, use_llm: bool) -> JobScore:
    if job.detail_status == 'link_only':
        raise HTTPException(409, 'Import the job description before ranking this discovered link.')
    base = rank_job(profile, job)
    used = False
    if use_llm:
        llm = LLMService()
        if llm.available():
            try:
                sem = llm.semantic_fit(profile, job)
                llm_score = float(sem.get("semantic_score", base.total))
                # Keep hard constraints meaningful: deterministic 70%, semantic 30%.
                total = round(max(0.0, min(100.0, base.total * 0.7 + llm_score * 0.3)), 1)
                base = RankingResult(
                    total=total,
                    category=sem.get("category") or base.category,
                    breakdown={**base.breakdown, "llm_semantic": round(llm_score, 1)},
                    strengths=list(dict.fromkeys(base.strengths + list(sem.get("strengths") or [])))[:12],
                    gaps=list(dict.fromkeys(base.gaps + list(sem.get("gaps") or [])))[:12],
                    rationale=(base.rationale + " " + str(sem.get("rationale") or "")).strip(),
                )
                used = True
            except Exception as exc:
                base.rationale += f" LLM enrichment failed; deterministic score retained ({type(exc).__name__})."
    return save_score(db, job, base, llm_used=used)


@app.post("/api/jobs/{job_id}/rank")
def rank_one(job_id: int, use_llm: bool = True, db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).limit(1))
    job = db.get(Job, job_id)
    if not profile or not job:
        raise HTTPException(404, "Profile or job not found")
    return _rank_with_optional_llm(db, profile, job, use_llm)


@app.post("/api/jobs/rank-all")
def rank_all(use_llm: bool = False, db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).limit(1))
    if not profile:
        raise HTTPException(404, "Profile not found")
    jobs = [job for job in db.scalars(select(Job).where(Job.active.is_(True))).all() if job.detail_status != 'link_only']
    for job in jobs:
        _rank_with_optional_llm(db, profile, job, use_llm)
    return {"ranked": len(jobs), "llm_requested": use_llm}


@app.post("/api/jobs/{job_id}/application", response_model=ApplicationOut)
def create_application(job_id: int, use_llm: bool = True, db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).limit(1))
    job = db.get(Job, job_id)
    if not profile or not job:
        raise HTTPException(404, "Profile or job not found")
    if job.detail_status == 'link_only':
        raise HTTPException(409, 'Import the job description before generating an application package.')
    return generate_application(db, profile, job, use_llm=use_llm)


@app.get("/api/applications", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.scalars(select(Application).order_by(desc(Application.created_at))).all()


@app.patch("/api/applications/{application_id}/status")
def set_application_status(application_id: int, status: str, db: Session = Depends(get_db)):
    row = db.get(Application, application_id)
    if not row:
        raise HTTPException(404, "Application not found")
    allowed = {"generated", "reviewed", "applied", "hr", "technical", "final", "offer", "rejected", "archived"}
    if status not in allowed:
        raise HTTPException(400, f"Status must be one of: {', '.join(sorted(allowed))}")
    row.status = status
    db.commit()
    return {"ok": True, "status": status}


@app.get("/api/applications/{application_id}/download")
def download_application(application_id: int, db: Session = Depends(get_db)):
    row = db.get(Application, application_id)
    if not row or not row.package_dir:
        raise HTTPException(404, "Application package not found")
    src = Path(row.package_dir)
    if not src.exists():
        raise HTTPException(404, "Package directory missing")
    tmp = Path(tempfile.gettempdir()) / f"jobforge_application_{application_id}.zip"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src.iterdir():
            if p.is_file(): z.write(p, p.name)
    return FileResponse(tmp, filename=f"jobforge_application_{application_id}.zip", media_type="application/zip")
