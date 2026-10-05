import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from ..models import Job, Application, MessageDraft

MAX_AGE_DAYS = 30


def cutoff(now=None):
    return (now or datetime.now(timezone.utc)) - timedelta(days=MAX_AGE_DAYS)


def expired(published_at, now=None):
    """Legacy 30-day age check retained for compatibility, never used to close a job."""
    if published_at is None:
        return False
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at < cutoff(now)


def purge_expired(db, now=None):
    """Remove stale/closed untracked jobs; preserve tracked rows for application history."""
    removed_stale, removed_closed, archived_stale, archived_closed = 0, 0, 0, 0
    now = now or datetime.now(timezone.utc)
    for job in db.scalars(select(Job)).all():
        status, deadline = application_state(job, now)
        if deadline and job.application_deadline != deadline:
            job.application_deadline = deadline
        stale = expired(job.published_at, now)
        if stale:
            job.application_status = 'stale'
        elif status != job.application_status:
            job.application_status = status
        if stale or status in {'expired', 'closed'}:
            tracked = db.scalar(select(Application.id).where(Application.job_id == job.id).limit(1))
            if tracked is None:
                db.execute(delete(MessageDraft).where(MessageDraft.job_id == job.id))
                db.delete(job)
                if stale:
                    removed_stale += 1
                else:
                    removed_closed += 1
                continue
            job.active = False
            if stale:
                archived_stale += 1
            else:
                archived_closed += 1
    db.commit()
    return {'removed_expired': removed_stale, 'removed_closed': removed_closed,
            'archived_stale': archived_stale, 'archived_closed': archived_closed,
            'archived_tracked': archived_stale + archived_closed}


def application_state(job, now=None):
    """Classify only strong publisher/page signals; unknown and age alone remain reviewable."""
    now = now or datetime.now(timezone.utc)
    raw = job.raw if isinstance(job.raw, dict) else {}
    deadline = _parse_datetime(raw.get('valid_through') or raw.get('validThrough') or raw.get('application_deadline'))
    if deadline and deadline <= now:
        return 'expired', deadline
    closed_signals = (
        r'job\s+(?:is\s+)?no\s+longer\s+available', r'position\s+(?:is\s+)?closed',
        r'application(?:s)?\s+(?:are\s+)?closed', r'no longer accepting applications',
        r'this job posting is no longer available', r'cette offre(?: d\x27emploi)? n\x27est plus disponible',
        r"candidatures? (?:sont )?closes?", r"l'offre est expir", r"recrutement termin",
    )
    # Match page status only, not arbitrary description text that may discuss old openings.
    status_values = [str(raw.get(key, '')).lower() for key in ('status', 'state', 'application_status', 'posting_status', 'source_status')]
    closed_status = any(value.strip() in {'closed', 'expired', 'inactive', 'filled', 'archived', 'removed'} for value in status_values)
    is_active = raw.get('isActive', raw.get('active'))
    if is_active is False:
        closed_status = True
    body = getattr(job, 'description', '') or ''
    page_signal = any(re.search(pattern, body, re.I) for pattern in closed_signals)
    explicitly_open = any(value.strip() in {'open', 'active', 'published', 'accepting_applications'} for value in status_values)
    return ('closed' if closed_status or page_signal else 'open' if explicitly_open or (deadline and deadline > now) else 'unknown'), deadline


def _parse_datetime(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (TypeError, ValueError):
        return None
