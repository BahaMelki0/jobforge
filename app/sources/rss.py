from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from .base import NormalizedJob


class RSSSource:
    def fetch(self, config: dict) -> list[NormalizedJob]:
        url = config["url"]
        company_default = config.get("company", "RSS")
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        out: list[NormalizedJob] = []
        for i, item in enumerate(items):
            def txt(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None and el.text else ""
            title = txt("title")
            link = txt("link")
            guid = txt("guid") or link or str(i)
            desc = BeautifulSoup(txt("description"), "html.parser").get_text("\n", strip=True)
            pub = txt("pubDate")
            dt = None
            if pub:
                try:
                    dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
                except Exception:
                    pass
            out.append(NormalizedJob(
                source_job_id=guid,
                title=title or "Untitled role",
                company=company_default,
                location=config.get("location", ""),
                url=link,
                description=desc,
                published_at=dt,
                raw={"title": title, "link": link, "description": desc, "pubDate": pub},
            ))
        return out
