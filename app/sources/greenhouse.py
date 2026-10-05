from __future__ import annotations

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from .base import NormalizedJob


class GreenhouseSource:
    def fetch(self, config: dict) -> list[NormalizedJob]:
        token = config["board_token"]
        company = config.get("company", token)
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
        out = []
        for item in data.get("jobs", []):
            desc = BeautifulSoup(item.get("content") or "", "html.parser").get_text("\n", strip=True)
            loc = ((item.get("location") or {}).get("name") or "").strip()
            # updated_at is an edit timestamp, not the job's publication date.
            updated = item.get("first_published")
            dt = None
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    pass
            out.append(NormalizedJob(
                source_job_id=str(item.get("id", "")),
                title=item.get("title") or "Untitled role",
                company=company,
                location=loc,
                url=item.get("absolute_url") or "",
                description=desc,
                published_at=dt,
                raw={**item, 'source_status': 'open'},
            ))
        return out
