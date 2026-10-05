"""Durable AI work records with a single GPU worker, deduplication and cancellation."""
import hashlib
import json
import queue
import time
import uuid
from datetime import datetime, timezone
from threading import Event, Lock, Thread

from sqlalchemy import select
from ..db import SessionLocal
from ..models import AITask, CandidateProfile, Job, MessageDraft, Application
from ..schemas import MessageRequest
from .llm import LLMService, GenerationCancelled, model_status
from .ranking import rank_job, save_score, RankingResult

_queue = queue.Queue(maxsize=8)
_lock = Lock()
_worker = None
_stop = Event()
_cancellations = {}
PROMPT_VERSION = 'applicant-studio-v3'


def now():
    return datetime.now(timezone.utc)


def start_worker():
    global _worker, _queue
    with _lock:
        if _worker and _worker.is_alive():
            return
        _stop.clear()
        _queue = queue.Queue(maxsize=8)
        with SessionLocal() as db:
            for task in db.scalars(select(AITask).where(AITask.status.in_(['queued', 'running']))).all():
                task.status = 'failed'
                task.error = 'The app restarted before this request finished. Retry to generate again.'
                task.finished_at = now()
            db.commit()
        _worker = Thread(target=_loop, name='jobforge-local-ai', daemon=True)
        _worker.start()


def stop_worker():
    _stop.set()
    with _lock:
        for event in _cancellations.values():
            event.set()
    if _worker:
        _worker.join(timeout=35)


def submit(job_id, request):
    status = model_status()
    model = status['fast_model'] if request.quality == 'fast' else status['quality_model']
    if not status['online'] or model not in status['installed']:
        raise RuntimeError(status.get('error') or f'Install the local model {model} before generating.')
    with _lock, SessionLocal() as db:
        job = db.get(Job, job_id)
        profile = db.scalar(select(CandidateProfile).limit(1))
        if not job or not profile:
            raise LookupError('Job or profile no longer exists')
        if job.detail_status == 'link_only':
            raise ValueError('Add the full job description before using local AI.')
        profile_data = {c.name: getattr(profile, c.name) for c in profile.__table__.columns if c.name not in ('updated_at', 'id')}
        request_data = request.model_dump(exclude={'force'})
        key = hashlib.sha256(json.dumps([PROMPT_VERSION, job_id, model, request_data, profile_data,
            job.title, job.company, job.description, job.requirements], sort_keys=True, default=str).encode()).hexdigest()
        prior = db.scalar(select(AITask).where(AITask.cache_key == key, AITask.status.in_(['queued', 'running', 'succeeded'])).order_by(AITask.created_at.desc()))
        if prior and prior.status != 'succeeded':
            return prior, False
        if prior and not request.force:
            valid = prior.kind in ('analysis', 'agent_review') or (prior.kind == 'message' and db.get(MessageDraft, prior.result.get('draft_id'))) or (prior.kind == 'application' and db.get(Application, prior.result.get('application_id')))
            if valid:
                return prior, True
        if _queue.full():
            raise ValueError('The local AI queue is full. Wait for a request to finish.')
        task = AITask(id=uuid.uuid4().hex, job_id=job_id, kind=request.kind, cache_key=key,
                      request=request_data, model=model, status='queued', progress='Queued for local AI')
        db.add(task); db.commit(); db.refresh(task)
        _cancellations[task.id] = Event()
        _queue.put_nowait(task.id)
        return task, False


def cancel(task_id):
    with _lock, SessionLocal() as db:
        task = db.get(AITask, task_id)
        if not task:
            raise LookupError('Task not found')
        if task.status in ('queued', 'running'):
            event = _cancellations.get(task_id)
            if event:
                event.set()
            task.status = 'cancelled'
            task.progress = 'Cancellation requested'
            task.finished_at = now()
            db.commit()
        return task


def _loop():
    while not _stop.is_set():
        try:
            task_id = _queue.get(timeout=0.25)
        except queue.Empty:
            continue
        try:
            _execute(task_id)
        except Exception:
            # Database trouble must not permanently kill the queue.
            import logging
            logging.getLogger(__name__).exception('AI worker failed while updating a task')
        finally:
            with _lock:
                _cancellations.pop(task_id, None)
            _queue.task_done()


def _execute(task_id):
    with SessionLocal() as db:
        task = db.get(AITask, task_id)
        if not task or task.status != 'queued':
            return
        task.status = 'running'; task.started_at = now(); task.progress = 'Preparing relevant evidence'
        db.commit()
        job, profile = db.get(Job, task.job_id), db.scalar(select(CandidateProfile).limit(1))
        request, model, kind = task.request, task.model, task.kind
    event = _cancellations.get(task_id, Event())
    last_update = [0.0]
    def progress(stage, tokens=0):
        if event.is_set() or _stop.is_set():
            raise GenerationCancelled('Cancelled')
        if time.monotonic()-last_update[0] < 0.5:
            return
        last_update[0] = time.monotonic()
        with SessionLocal() as db:
            task = db.get(AITask, task_id)
            if task.status == 'running':
                task.progress = stage + (f' · {tokens} tokens received' if tokens else '')
                task.metrics = {'output_chunks': tokens}
                db.commit()
    llm = LLMService(model=model, progress=progress, cancel=lambda: event.is_set() or _stop.is_set())
    try:
        if not job or not profile:
            raise ValueError('The offer or profile was removed before generation started.')
        if kind == 'message':
            content = llm.recruiter_messages(profile, job, MessageRequest.model_validate(request))
            progress('Saving your draft')
            with SessionLocal() as db:
                if not db.get(Job, job.id):
                    raise ValueError('The offer was removed while drafting.')
                draft = MessageDraft(job_id=job.id, language=request['language'], tone=request['tone'], model=model, content=content)
                db.add(draft); db.commit(); db.refresh(draft)
                result = {'draft_id': draft.id}
        elif kind == 'agent_review':
            from .agent_review import review_job
            result = review_job(llm, profile, job, request.get('language', 'fr'))
        elif kind == 'analysis':
            semantic = llm.semantic_fit(profile, job)
            progress('Saving fit analysis')
            base = rank_job(profile, job)
            result_score = RankingResult(round(base.total*0.7+semantic['semantic_score']*0.3, 1), base.category,
                {**base.breakdown, 'llm_semantic': semantic['semantic_score']},
                list(dict.fromkeys(base.strengths+semantic['strengths']))[:8],
                list(dict.fromkeys(base.gaps+semantic['gaps']))[:8], semantic['rationale'])
            with SessionLocal() as db:
                current = db.get(Job, job.id)
                if not current:
                    raise ValueError('The offer was removed while analysis was running.')
                save_score(db, current, result_score, llm_used=True)
                result = {'job_id': job.id}
        else:
            from .application_generator import generate_application
            with SessionLocal() as db:
                current = db.get(Job, job.id)
                if not current:
                    raise ValueError('The offer was removed before package generation.')
                application = generate_application(db, profile, current, use_llm=True, llm=llm)
                result = {'application_id': application.id}
        with SessionLocal() as db:
            task = db.get(AITask, task_id)
            if task.status != 'cancelled':
                task.status = 'succeeded'; task.result = result; task.progress = 'Ready'
                task.metrics = llm.metrics; task.finished_at = now(); db.commit()
    except Exception as exc:
        if isinstance(exc, GenerationCancelled):
            message = 'Generation cancelled'
        elif isinstance(exc, TimeoutError):
            message = str(exc)
        else:
            import httpx
            message = 'Ollama stopped responding. Check the local AI status and retry.' if isinstance(exc, httpx.HTTPError) else str(exc)
        with SessionLocal() as db:
            task = db.get(AITask, task_id)
            task.status = 'cancelled' if event.is_set() or isinstance(exc, GenerationCancelled) else 'failed'
            task.error = message[:1000]; task.progress = task.status.title(); task.finished_at = now(); db.commit()
