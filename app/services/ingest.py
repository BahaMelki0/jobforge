from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterable
from threading import RLock
from functools import wraps

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job, JobScore, Source, JobObservation
from ..sources import ADAPTERS
from ..sources.base import NormalizedJob
from .retention import application_state, expired, purge_expired

_refresh_lock = RLock()


def serialized_refresh(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _refresh_lock:
            return fn(*args, **kwargs)
    return wrapped


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def fingerprint(job: NormalizedJob) -> str:
    # URL + source id when present, otherwise a stable content identity.
    base = "|".join([
        _norm(job.url),
        _norm(job.source_job_id),
        _norm(job.company),
        _norm(job.title),
        _norm(job.location),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def cross_source_match(db, source, item):
    # Conservative exact-content identity: similar titles alone cannot establish a shared vacancy.
    if len(_norm(item.description)) < 100 or item.raw.get('detail_status', 'full') != 'full':
        return None
    for candidate in db.scalars(select(Job).where(Job.source_id != source.id)).all():
        if all(_norm(getattr(candidate, field)) == _norm(getattr(item, field)) for field in ('company', 'title', 'location', 'description')):
            if candidate.published_at and item.published_at and abs((candidate.published_at.replace(tzinfo=timezone.utc) - item.published_at.replace(tzinfo=timezone.utc)).days) > 7:
                continue
            return candidate
    return None


def record_observation(db, source, item, job, status, now):
    identity = hashlib.sha256((item.source_job_id or item.url).encode()).hexdigest()
    row = db.scalar(select(JobObservation).where(JobObservation.source_id == source.id, JobObservation.identity == identity))
    if row is None:
        row = JobObservation(source_id=source.id, identity=identity, job_id=job.id, url=item.url)
        db.add(row)
    row.job_id, row.status, row.checked_at, row.url = job.id, status, now, item.url


@serialized_refresh
def upsert_jobs(db: Session, source: Source, jobs: Iterable[NormalizedJob]) -> tuple[int, int]:
    purge_expired(db)
    created = 0
    updated = 0
    now = datetime.now(timezone.utc)
    for item in jobs:
        application_status, application_deadline = application_state(item, now)
        fp = fingerprint(item)
        existing = None
        observation_id = hashlib.sha256((item.source_job_id or item.url).encode()).hexdigest()
        observation = db.scalar(select(JobObservation).where(JobObservation.source_id == source.id, JobObservation.identity == observation_id))
        if observation:
            existing = db.get(Job, observation.job_id)
        if existing is None and item.source_job_id:
            existing = db.scalar(select(Job).where(
                Job.source_id == source.id, Job.source_job_id == item.source_job_id
            ))
        if existing is None and item.url:
            existing = db.scalar(select(Job).where(Job.url == item.url))
        if existing is None:
            existing = db.scalar(select(Job).where(Job.fingerprint == fp))
        if existing is None:
            existing = cross_source_match(db, source, item)
        if existing:
            record_observation(db, source, item, existing, application_status, now)
            db.flush()
            if existing.source_id != source.id:
                # Preserve canonical content and its publisher state; retain secondary evidence independently.
                existing.last_seen_at = now
                updated += 1
                continue
        if existing and application_status in {'expired', 'closed'}:
            existing.application_status = application_status
            existing.application_deadline = application_deadline
            existing.active = False
            existing.last_seen_at = now
            existing.raw = item.raw
            updated += 1
            continue
        if expired(item.published_at, now) or application_status in {'expired', 'closed'}:
            continue
        if existing:
            if existing.description and existing.detail_status == 'full' and item.raw.get('detail_status') in {'summary', 'link_only'}:
                # A temporary access failure must not replace previously fetched/imported full content.
                existing.last_seen_at = now
                existing.application_status, existing.application_deadline = application_status, application_deadline
                if existing.application_status not in {'expired', 'closed'}:
                    existing.active = True
                else:
                    existing.active = False
                updated += 1
                continue
            changed = any(getattr(existing, field) != getattr(item, field) for field in (
                "title", "company", "location", "remote", "employment_type", "salary", "description", "requirements"
            ))
            if changed:
                score = db.scalar(select(JobScore).where(JobScore.job_id == existing.id))
                if score is not None:
                    db.delete(score)
            existing.title = item.title
            existing.company = item.company
            existing.location = item.location
            existing.remote = item.remote
            existing.employment_type = item.employment_type
            existing.salary = item.salary
            existing.url = item.url
            existing.description = item.description
            existing.requirements = item.requirements
            existing.published_at = item.published_at or existing.published_at
            existing.application_status, existing.application_deadline = application_status, application_deadline
            existing.last_seen_at = now
            existing.active = existing.application_status not in {'expired', 'closed'}
            existing.raw = item.raw
            existing.source_id = source.id
            updated += 1
        else:
            new_job = Job(
                source_id=source.id,
                source_job_id=item.source_job_id,
                fingerprint=fp,
                title=item.title,
                company=item.company,
                location=item.location,
                remote=item.remote,
                employment_type=item.employment_type,
                salary=item.salary,
                url=item.url,
                description=item.description,
                requirements=item.requirements,
                published_at=item.published_at,
                application_status=application_status,
                application_deadline=application_deadline,
                first_seen_at=now,
                last_seen_at=now,
                active=application_status not in {'expired', 'closed'},
                raw=item.raw,
            )
            db.add(new_job)
            db.flush()
            record_observation(db, source, item, new_job, application_status, now)
            created += 1
        db.flush()
    source.last_run_at = now
    source.last_error = None
    source.jobs_seen = created + updated
    db.commit()
    return created, updated


@serialized_refresh
def run_source(db: Session, source: Source) -> dict:
    retention = purge_expired(db)
    if not source.enabled:
        return {"source": source.name, "skipped": True, "reason": "disabled"}
    try:
        cls = ADAPTERS.get(source.kind)
        if not cls:
            raise ValueError(f"Unknown source kind: {source.kind}")
        adapter = cls()
        jobs = adapter.fetch(source.config or {})
        fetched_count = len(jobs)
        expired_count = sum(expired(job.published_at) or application_state(job)[0] == 'expired' for job in jobs)
        closed_count = sum(application_state(job)[0] == 'closed' for job in jobs)
        jobs = [job for job in jobs if not expired(job.published_at)]
        cfg = source.config or {}
        if cfg.get('location_contains'):
            jobs = [j for j in jobs if any(term.lower() in j.location.lower() for term in cfg['location_contains'])]
        if cfg.get('title_contains'):
            jobs = [j for j in jobs if any(term.lower() in j.title.lower() for term in cfg['title_contains'])]
        created, updated = upsert_jobs(db, source, jobs)
        from ..models import CandidateProfile
        from .ranking import rank_job, save_score
        profile = db.scalar(select(CandidateProfile).limit(1))
        if profile:
            for job in db.scalars(select(Job).where(Job.source_id == source.id, Job.active.is_(True))).all():
                if job.detail_status == 'link_only':
                    continue
                if db.scalar(select(JobScore).where(JobScore.job_id == job.id)) is None:
                    save_score(db, job, rank_job(profile, job), llm_used=False)
        return {"source": source.name, "created": created, "updated": updated, "fetched": fetched_count,
                "accepted": len(jobs), "filtered_after_fetch": fetched_count-len(jobs),
                "full_descriptions": sum(j.raw.get('detail_status', 'full') == 'full' for j in jobs),
                "summaries": sum(j.raw.get('detail_status') == 'summary' for j in jobs),
                "link_only": sum(j.raw.get('detail_status') == 'link_only' for j in jobs),
                "expired_filtered": expired_count, "closed_filtered": closed_count, **retention,
                **getattr(adapter, 'diagnostics', {})}
    except Exception as exc:
        db.rollback()
        source.last_run_at = datetime.now(timezone.utc)
        source.last_error = f"{type(exc).__name__}: {exc}"
        db.commit()
        return {"source": source.name, "error": source.last_error}


@serialized_refresh
def run_all_sources(db: Session, on_result=None) -> list[dict]:
    retention = purge_expired(db)
    sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
    priority = {'linkedin': 0, 'apec': 1, 'wttj': 2, 'cybersecurityjobsite': 3}
    sources.sort(key=lambda source: priority.get(source.kind, 4))
    results = []
    if any(retention.values()):
        results.append({'source': '30-day and closed-offer cleanup', **retention})
    for source in sources:
        if on_result:
            on_result(source.name, results)
        results.append(run_source(db, source))
        if on_result:
            on_result(None, results)
    return results
