from threading import Event
from app.services import discovery


def test_repeated_scan_request_does_not_start_overlapping_workers(monkeypatch):
    entered, release = Event(), Event()
    def worker(trigger):
        entered.set()
        assert release.wait(3)
    monkeypatch.setattr(discovery, '_scan', worker)
    try:
        assert discovery.start_scan('manual') is True
        assert entered.wait(2)
        assert discovery.start_scan('manual') is False
        assert discovery.running() is True
    finally:
        release.set()
        discovery.join_scan()
    assert discovery.running() is False
