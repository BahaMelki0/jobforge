from __future__ import annotations

import asyncio
import logging

from ..config import settings
from ..db import SessionLocal
from .ingest import run_all_sources
from . import discovery

logger = logging.getLogger(__name__)


def refresh_in_background():
    with SessionLocal() as db:
        return run_all_sources(db)


async def scheduler_loop(stop_event: asyncio.Event):
    first = True
    while not stop_event.is_set():
        try:
            due = discovery.next_run()
            from datetime import datetime, timezone
            if first or (due is not None and datetime.now(timezone.utc) >= due):
                discovery.start_scan('startup' if first else 'scheduled')
                first = False
        except Exception:
            logger.exception("Scheduled refresh failed; the next refresh will still run")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
    await asyncio.to_thread(discovery.join_scan)
