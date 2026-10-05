from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CandidateProfile, Job, JobScore
from .focus import assess, cap_score, required_years, plain


CATEGORY_TERMS = {
    'AppSec / DevSecOps': ['appsec', 'devsecops', 'application security', 'securite applicative', 'sast', 'dast', 'software composition analysis', 'secure sdlc', 'threat modeling'],
    "Networking / Systems": ["network", "reseau", "reseaux", "routing", "switching", "cisco", "tcp/ip", "administrateur system", "networking"],
    "IT Support / Help Desk": ["helpdesk", "help desk", "service desk", "support informatique", "support utilisateur", "support technique informatique", "support it", "technicien informatique", "desktop support"],
    "Offensive Security / Pentest / Red Team": [
        "penetration test", "penetration tester", "pentest", "pentester", "pentesting", "red team", "offensive security", "adversary simulation",
        "web security", "active directory", "burp", "bloodhound", "exploit", "security assessment",
    ],
    "Cloud & Identity Security": [
        "entra", "azure ad", "identity", "iam", "microsoft 365", "m365", "microsoft graph",
        "cloud security", "conditional access", "oauth", "openid", "azure security",
    ],
    "Blue Team / SOC / Detection": [
        "soc", "analyste soc", "blue team", "siem", "detection", "incident response", "sentinel", "splunk", "edr", "xdr",
        "threat hunting", "security monitoring", "dfir",
    ],
    "Cybersecurity / Security Consulting": [
        "cybersecurity consultant", "security consultant", "risk assessment", "security audit",
        "security engineer", "cybersecurite", "securite informatique", "cyber security", "security assessment", "consulting",
    ],
}

SENIOR_TERMS = ["senior", "lead", "principal", "manager", "head of", "architect"]
JUNIOR_TERMS = ["junior", "graduate", "entry level", "entry-level", "l1", "analyst i"]


@dataclass
class RankingResult:
    total: float
    category: str
    breakdown: dict[str, float]
    strengths: list[str]
    gaps: list[str]
    rationale: str


def _text(job: Job) -> str:
    return " ".join(str(x or "") for x in [job.title, job.company, job.location, job.remote, job.employment_type, job.description, job.requirements]).lower()


def _contains(text: str, term: str) -> bool:
    return term.lower() in text


def classify_category(profile: CandidateProfile, text: str) -> tuple[str, float]:
    scores: dict[str, float] = {}
    for category, terms in CATEGORY_TERMS.items():
        matches = sum(1 for t in terms if re.search(r"(?<!\w)" + re.escape(plain(t)) + r"(?!\w)", plain(text)))
        weight = float((profile.categories or {}).get(category, 0.5))
        scores[category] = matches * weight
    if not scores or max(scores.values()) == 0:
        return "Other", 0.0
    cat = max(scores, key=scores.get)
    return cat, scores[cat]


def rank_job(profile: CandidateProfile, job: Job) -> RankingResult:
    text = _text(job)
    title = job.title.lower()
    breakdown: dict[str, float] = {}
    strengths: list[str] = []
    gaps: list[str] = []

    category, cat_raw = classify_category(profile, title)
    if category == 'Other':
        category, cat_raw = classify_category(profile, text)
    cat_weight = float((profile.categories or {}).get(category, 0.35 if category == "Other" else 0.5))
    breakdown["role_fit"] = min(30.0, 12.0 + cat_raw * 4.0) if category != "Other" else 7.0
    if category != "Other":
        strengths.append(f"Strong alignment with {category}")

    skills = [s for s in (profile.skills or []) if len(s.strip()) >= 2]
    matched_skills = [s for s in skills if _contains(text, s)]
    skill_ratio = len(matched_skills) / max(1, min(len(skills), 18))
    breakdown["skills"] = min(25.0, 7.0 + 25.0 * skill_ratio)
    if matched_skills:
        strengths.append("Matches: " + ", ".join(matched_skills[:8]))

    must = [k for k in (profile.must_have_keywords or []) if k.strip()]
    must_hits = [k for k in must if _contains(text, k)]
    breakdown["must_have"] = 15.0 * (len(must_hits) / max(1, len(must))) if must else 10.0
    if must and len(must_hits) < max(1, math.ceil(len(must) * 0.3)):
        gaps.append("Few of the highest-priority keywords appear in the listing")

    focus = assess(job)
    breakdown['location'] = 10.0 if focus['country']=='france' else 0.0
    if focus['country']=='france':
        strengths.append(f"France location: {job.location}")
    breakdown['seniority'] = 15.0 if focus['level']=='junior' else 8.0 if focus['level']=='training' else 3.0 if focus['level']=='unknown' else 0.0

    employment = (job.employment_type or "").lower()
    prefs = [x.lower() for x in (profile.preferred_employment or [])]
    if not employment:
        breakdown["employment"] = 4.0
    elif any(p in employment or employment in p for p in prefs):
        breakdown["employment"] = 5.0
    else:
        breakdown["employment"] = 2.0

    exclude_hits = [k for k in (profile.exclude_keywords or []) if _contains(text, k)]
    penalty = min(25.0, 8.0 * len(exclude_hits))
    if exclude_hits:
        gaps.append("Potential exclusion: " + ", ".join(exclude_hits[:4]))
    breakdown["penalties"] = -penalty

    # Small boost for priority category weight while keeping the result explainable.
    priority_bonus = max(0.0, min(5.0, (cat_weight - 0.5) * 10.0))
    breakdown["priority_bonus"] = priority_bonus

    focus = assess(job)
    breakdown['location'] = 10.0 if focus['country']=='france' else 0.0
    breakdown['seniority'] = 15.0 if focus['level']=='junior' else 8.0 if focus['level']=='training' else 3.0 if focus['level']=='unknown' else 0.0
    if focus['status']=='junior_france':
        strengths.append('France-based role with junior / 0-2 years evidence')
    gaps.extend(focus['reasons'])
    raw_total = max(0.0, min(100.0, sum(breakdown.values())))
    total = cap_score(job, raw_total)
    breakdown['focus_cap'] = total - raw_total
    rationale = (
        f"Deterministic fit score based on role family, matched skills, priority keywords, location, "
        f"seniority and employment type. Classified as {category}."
    )
    return RankingResult(round(total, 1), category, {k: round(v, 1) for k, v in breakdown.items()}, strengths, gaps, rationale)


def save_score(db: Session, job: Job, result: RankingResult, llm_used: bool = False) -> JobScore:
    row = db.scalar(select(JobScore).where(JobScore.job_id == job.id))
    if not row:
        row = JobScore(job_id=job.id)
        db.add(row)
    row.total = cap_score(job, result.total)
    row.category = result.category
    row.breakdown = result.breakdown
    row.strengths = result.strengths
    row.gaps = result.gaps
    row.rationale = result.rationale
    row.llm_used = llm_used
    db.commit()
    db.refresh(row)
    return row
