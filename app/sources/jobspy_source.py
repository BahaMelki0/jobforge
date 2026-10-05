from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import NormalizedJob


class JobSpySource:
    def fetch(self, config: dict[str, Any]) -> list[NormalizedJob]:
        try:
            from jobspy import scrape_jobs
        except ImportError as exc:
            raise RuntimeError("JobSpy is optional. Install requirements-full.txt to enable it.") from exc

        queries = config.get("queries") or [config.get("query", "cybersecurity")]
        sites = config.get("sites") or ["indeed", "linkedin", "glassdoor", "google"]
        location = config.get("location", "France")
        results_wanted = int(config.get("results_wanted", 50))
        hours_old = int(config.get("hours_old", 168))
        out: list[NormalizedJob] = []
        for query in queries:
            df = scrape_jobs(
                site_name=sites,
                search_term=query,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="France",
            )
            for _, row in df.fillna("").iterrows():
                date = row.get("date_posted")
                dt = None
                if date:
                    try:
                        dt = datetime.fromisoformat(str(date)).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                source_job_id = str(row.get("id") or row.get("job_url") or f"{query}-{len(out)}")
                out.append(NormalizedJob(
                    source_job_id=source_job_id,
                    title=str(row.get("title") or "Untitled role"),
                    company=str(row.get("company") or ""),
                    location=str(row.get("location") or ""),
                    remote=str(row.get("is_remote") or ""),
                    employment_type=str(row.get("job_type") or ""),
                    salary=" - ".join(str(x) for x in [row.get("min_amount"), row.get("max_amount"), row.get("currency")] if x not in (None, "")),
                    url=str(row.get("job_url") or ""),
                    description=str(row.get("description") or ""),
                    published_at=dt,
                    raw={k: (None if str(v) == "nan" else v) for k, v in row.to_dict().items()},
                ))
        return out
