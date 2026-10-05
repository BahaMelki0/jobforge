from datetime import datetime, timezone, timedelta
from threading import Lock, Thread

from sqlalchemy import select
from ..db import SessionLocal
from ..models import ScanRun
from ..config import settings
from .ingest import run_all_sources

_lock = Lock()
_thread = None
_next_run = None


def start_scan(trigger='manual'):
    global _thread, _next_run
    with _lock:
        if _thread and _thread.is_alive():
            return False
        _next_run = None
        _thread = Thread(target=_scan, args=(trigger,), name='jobforge-discovery', daemon=False)
        _thread.start()
        return True


def _scan(trigger):
    global _next_run
    with SessionLocal() as db:
        scan = ScanRun(trigger=trigger, results=[])
        db.add(scan)
        db.commit()
        def progress(source, results):
            scan.current_source = source
            scan.results = list(results)
            db.commit()
        try:
            results = run_all_sources(db, on_result=progress)
            scan.results = results
            scan.status = 'partial' if any('error' in r or r.get('warnings') for r in results) else 'completed'
        except Exception as exc:
            db.rollback()
            scan.status = 'failed'
            scan.error = str(exc)
        finally:
            scan.current_source = None
            scan.finished_at = datetime.now(timezone.utc)
            db.commit()
            _next_run = scan.finished_at + timedelta(minutes=settings.scrape_interval_minutes) if settings.auto_refresh else None


def running():
    return bool(_thread and _thread.is_alive())


def next_run():
    return _next_run


def join_scan():
    if _thread:
        _thread.join()


def recover_interrupted(db):
    for scan in db.scalars(select(ScanRun).where(ScanRun.status == 'running')).all():
        scan.status = 'interrupted'
        scan.finished_at = datetime.now(timezone.utc)
        scan.error = 'App stopped before this scan finished. A new startup scan will run.'
    db.commit()
