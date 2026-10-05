from __future__ import annotations

from datetime import datetime, timezone

from .base import NormalizedJob


class DemoSource:
    def fetch(self, config: dict) -> list[NormalizedJob]:
        now = datetime.now(timezone.utc)
        return [
            NormalizedJob(
                source_job_id="demo-cloud-identity-1",
                title="Junior Cloud & Identity Security Engineer",
                company="DemoSec France",
                location="Paris, France",
                remote="Hybrid",
                employment_type="CDI",
                salary="45k-52k EUR",
                url="https://example.com/jobs/cloud-identity",
                description=(
                    "Join the security engineering team to assess Microsoft Entra ID and Microsoft 365 environments. "
                    "You will work with Microsoft Graph, identity permissions, Azure security, PowerShell/Python automation, "
                    "security assessments and remediation guidance. Knowledge of Active Directory and offensive security is valued."
                ),
                published_at=now,
            ),
            NormalizedJob(
                source_job_id="demo-pentest-2",
                title="Junior Penetration Tester",
                company="Hexa Offensive",
                location="Lyon, France",
                remote="Hybrid",
                employment_type="CDI",
                url="https://example.com/jobs/pentest",
                description=(
                    "Perform web, infrastructure and Active Directory penetration tests. Build tooling in Python, write clear reports, "
                    "and contribute to red-team exercises. 1-2 years experience preferred. OSCP/CRTO/CRTP-style knowledge is a plus."
                ),
                published_at=now,
            ),
            NormalizedJob(
                source_job_id="demo-soc-3",
                title="SOC Analyst L1/L2",
                company="BlueWatch",
                location="Toulouse, France",
                remote="On-site",
                employment_type="CDI",
                url="https://example.com/jobs/soc",
                description=(
                    "Monitor SIEM alerts, investigate Windows and cloud telemetry, create detection rules and support incident response. "
                    "Experience with Microsoft Sentinel, Entra ID, networking and scripting is useful."
                ),
                published_at=now,
            ),
            NormalizedJob(
                source_job_id="demo-senior-4",
                title="Senior Red Team Lead",
                company="Demo Offensive Labs",
                location="Paris, France",
                employment_type="CDI",
                url="https://example.com/jobs/senior-redteam",
                description=(
                    "Lead advanced adversary simulation engagements. Requires 7+ years of professional red-team experience, "
                    "team leadership, exploit development and client ownership."
                ),
                published_at=now,
            ),
        ]
