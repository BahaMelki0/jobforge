import asyncio
from datetime import datetime, timedelta, timezone
from app.services import scheduler


def test_startup_repeat_and_stop(monkeypatch):
    calls=[]
    async def scenario():
        stop=asyncio.Event()
        def start(trigger):
            calls.append(trigger)
            return True
        async def wait(awaitable,timeout):
            assert timeout==1
            awaitable.close()
            if len(calls)==2:stop.set()
            else:raise asyncio.TimeoutError
        monkeypatch.setattr(scheduler.discovery,'start_scan',start)
        monkeypatch.setattr(scheduler.discovery,'next_run',lambda:datetime.now(timezone.utc)-timedelta(seconds=1))
        monkeypatch.setattr(scheduler.discovery,'join_scan',lambda:None)
        monkeypatch.setattr(scheduler.asyncio,'wait_for',wait)
        await scheduler.scheduler_loop(stop)
    asyncio.run(scenario())
    assert calls==['startup','scheduled']
