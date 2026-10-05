from __future__ import annotations

from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from .base import NormalizedJob


class LeverSource:
    def fetch(self, config: dict) -> list[NormalizedJob]:
        site = config["site"]
        company = config.get("company", site)
        url = f"https://api.lever.co/v0/postings/{site}?mode=json"
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
        out = []
        for item in data:
            cats = item.get("categories") or {}
            loc = cats.get("location") or ""
            commitment = cats.get("commitment") or ""
            text_parts = [item.get("descriptionPlain") or ""]
            for lst in item.get("lists") or []:
                text_parts.append(lst.get("text") or "")
                text_parts.append(BeautifulSoup(lst.get("content") or "", "html.parser").get_text("\n", strip=True))
            created = item.get("createdAt")
            dt = datetime.fromtimestamp(created / 1000, tz=timezone.utc) if created else None
            out.append(NormalizedJob(
                source_job_id=item.get("id") or "",
                title=item.get("text") or "Untitled role",
                company=company,
                location=loc,
                employment_type=commitment,
                url=item.get("hostedUrl") or item.get("applyUrl") or "",
                description="\n".join(p for p in text_parts if p),
                published_at=dt,
                raw={**item, 'source_status': 'open'},
            ))
        return out
