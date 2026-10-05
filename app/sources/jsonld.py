from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import NormalizedJob


class JSONLDSource:
    """Extracts schema.org JobPosting blocks from a page or list of pages."""

    def fetch(self, config: dict) -> list[NormalizedJob]:
        urls = config.get("urls") or ([config["url"]] if config.get("url") else [])
        company_default = config.get("company", "")
        out: list[NormalizedJob] = []
        with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "JobForge/1.0"}) as client:
            for page_url in urls:
                r = client.get(page_url)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
                    try:
                        payload = json.loads(tag.string or tag.get_text())
                    except Exception:
                        continue
                    blocks = payload if isinstance(payload, list) else [payload]
                    for block in blocks:
                        if not isinstance(block, dict):
                            continue
                        graph = block.get("@graph") if isinstance(block.get("@graph"), list) else [block]
                        for obj in graph:
                            if not isinstance(obj, dict) or obj.get("@type") != "JobPosting":
                                continue
                            org = obj.get("hiringOrganization") or {}
                            company = org.get("name") if isinstance(org, dict) else ""
                            loc = ""
                            jl = obj.get("jobLocation")
                            first = jl[0] if isinstance(jl, list) and jl else jl
                            if isinstance(first, dict):
                                addr = first.get("address") or {}
                                if isinstance(addr, dict):
                                    loc = ", ".join(str(addr.get(k, "")) for k in ("addressLocality", "addressRegion", "addressCountry") if addr.get(k))
                            desc = BeautifulSoup(obj.get("description") or "", "html.parser").get_text("\n", strip=True)
                            date = obj.get("datePosted")
                            dt = None
                            if date:
                                try:
                                    dt = datetime.fromisoformat(str(date).replace("Z", "+00:00")).astimezone(timezone.utc)
                                except ValueError:
                                    pass
                            target_url = obj.get("url") or page_url
                            out.append(NormalizedJob(
                                source_job_id=str(obj.get("identifier") or target_url),
                                title=obj.get("title") or "Untitled role",
                                company=company or company_default,
                                location=loc,
                                employment_type=str(obj.get("employmentType") or ""),
                                url=urljoin(page_url, target_url),
                                description=desc,
                                published_at=dt,
                                raw={**obj, 'detail_status': 'full', 'valid_through': obj.get('validThrough')},
                            ))
        return out
