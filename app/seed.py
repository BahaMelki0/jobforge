from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CandidateProfile, Source


def ensure_seed_data(db: Session) -> None:
    profile = db.scalar(select(CandidateProfile).limit(1))
    if not profile:
        profile = CandidateProfile(
            name="Bahaeddine Melki",
            headline="Telecommunications Engineer | Digital Security | Offensive & Cloud Security",
            summary=(
                "Cybersecurity engineer focused on offensive security, cloud and identity security, Microsoft Entra ID, "
                "Microsoft 365, Active Directory and security tooling. Recent work includes development of an internal "
                "Microsoft Graph-based security assessment framework with reusable authentication, persistence and provenance."
            ),
            preferred_locations=["France", "Paris, France", "Île-de-France, France", "Lyon, France", "Toulouse, France", "Sophia Antipolis, France"],
            categories={
                "Offensive Security / Pentest / Red Team": 1.0,
                "Cloud & Identity Security": 1.0,
                "Blue Team / SOC / Detection": 1.0,
                "Networking / Systems": 1.0,
                "IT Support / Help Desk": 1.0,
                "Cybersecurity / Security Consulting": 0.85,
            },
            skills=[
                "offensive security", "red team", "penetration testing", "Active Directory", "Microsoft Entra ID",
                "Microsoft 365", "Microsoft Graph", "cloud security", "identity security", "Python", "PowerShell",
                "Linux", "Windows", "networking", "vulnerability assessment", "security tooling", "SIEM", "incident response"
            ],
            must_have_keywords=[],
            nice_to_have_keywords=["Microsoft Graph", "Entra ID", "Active Directory", "Azure", "Microsoft 365", "Python"],
            exclude_keywords=["7+ years", "8+ years", "10+ years", "director", "vp of", "head of security"],
            target_seniority=["graduate", "junior", "entry-level", "0-2 years"],
            preferred_employment=["CDI", "full-time", "permanent"],
            languages=["English", "French"],
            education=[
                {"degree": "Telecommunications Engineering", "school": "SUP'COM", "year": "2026"},
                {"degree": "Specialized Engineering Program in Digital Security", "school": "EURECOM", "year": "2026"},
            ],
            experience=[
                {
                    "role": "Offensive Security Intern",
                    "company": "RandoriSec",
                    "summary": "Developed and improved an internal Microsoft Graph-based assessment framework for Microsoft Entra ID and Microsoft 365.",
                    "bullets": [
                        "Refactored and extended an internal Microsoft cloud security assessment framework.",
                        "Built reusable authentication flows, CLI execution, tenant/session-aware persistence and provenance tracking.",
                        "Worked with Microsoft Graph, Entra ID, Microsoft 365, cloud identity permissions and controlled red-team workflows.",
                    ],
                }
            ],
            projects=[
                {
                    "name": "Azure Gathering",
                    "summary": "Microsoft Graph-based security assessment framework for Entra ID and Microsoft 365.",
                    "bullets": [
                        "Unified enumeration, exploitation and controlled red-team operations under a shared CLI.",
                        "Designed SQLite persistence linking authentication context, sessions, canonical objects and artifacts.",
                        "Validated representative workflows in a dedicated Microsoft cloud test tenant.",
                    ],
                }
            ],
            certifications=[],
            resume_text="",
        )
        from .personal_profile import enrich
        enrich(profile)
        db.add(profile)

    if not db.scalar(select(Source).where(Source.name == "Demo cybersecurity jobs")):
        db.add(Source(name="Demo cybersecurity jobs", kind="demo", config={}, enabled=True))
    db.commit()
