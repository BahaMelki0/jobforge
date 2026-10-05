from __future__ import annotations

import json
import re
from xml.sax.saxutils import escape
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from ..models import Application, CandidateProfile, Job
from .llm import LLMService


OUT_ROOT = Path("generated_applications")


def _safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_")[:80] or "application"


def _fallback(profile: CandidateProfile, job: Job) -> dict:
    matched = [s for s in (profile.skills or []) if s.lower() in (job.description or "").lower()]
    summary = profile.summary or profile.headline
    cover = (
        f"Dear Hiring Team,\n\nI am applying for the {job.title} position at {job.company}. "
        f"My background in {', '.join(matched[:6]) if matched else 'cybersecurity engineering'} aligns with several areas described in the role. "
        f"My recent experience includes {profile.experience[0].get('summary','security engineering work') if profile.experience else 'security engineering projects'}.\n\n"
        "I would welcome the opportunity to discuss how my background can contribute to your team.\n\n"
        f"Best regards,\n{profile.name}"
    )
    return {
        "tailored_summary": summary,
        "selected_skills": matched[:12] or (profile.skills or [])[:12],
        "experience_bullets": [{"role": e.get("role", "Experience"), "bullets": e.get("bullets", [e.get("summary", "")])} for e in (profile.experience or [])],
        "project_bullets": [{"project": p.get("name", "Project"), "bullets": p.get("bullets", [p.get("summary", "")])} for p in (profile.projects or [])],
        "cover_letter": cover,
        "recruiter_message": f"Hi, I’m {profile.name}. I’m interested in the {job.title} role at {job.company}. My background focuses on cybersecurity engineering, offensive/cloud security and automation. I’d be glad to connect and discuss the role.",
        "email_subject": f"Application – {job.title} – {profile.name}",
        "email_body": f"Hello,\n\nPlease find my application for the {job.title} role at {job.company}. I have attached my tailored CV and cover letter.\n\nBest regards,\n{profile.name}",
        "why_company": f"The listing emphasizes areas that overlap with my cybersecurity background and the responsibilities described for {job.title}.",
        "interview_prep": {
            "likely_questions": ["Walk me through your most relevant security project.", "Why are you interested in this role?"],
            "technical_topics": matched[:8],
            "stories_to_prepare": ["A difficult technical problem you debugged", "A project where you designed or improved a security workflow"],
        },
    }


def _pdf(path: Path, title: str, body: str) -> None:
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT, spaceAfter=5)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=10)
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    story = [Paragraph(escape(title), h1), Spacer(1, 4)]
    for para in body.split("\n"):
        if para.strip():
            story.append(Paragraph(para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), normal))
        else:
            story.append(Spacer(1, 6))
    doc.build(story)


def _render_cv(profile: CandidateProfile, job: Job, data: dict) -> str:
    lines = [profile.name, profile.headline, "", data.get("tailored_summary", ""), "", "CORE SKILLS"]
    lines.append(" • ".join(data.get("selected_skills", [])))
    lines += ["", "EXPERIENCE"]
    for e in profile.experience or []:
        role = e.get("role", "")
        company = e.get("company", "")
        lines.append(f"{role} — {company}".strip(" —"))
        chosen = next((x for x in data.get("experience_bullets", []) if x.get("role") == role), None)
        bullets = (chosen or {}).get("bullets") or e.get("bullets") or ([e.get("summary")] if e.get("summary") else [])
        lines.extend([f"• {b}" for b in bullets if b])
    if profile.projects:
        lines += ["", "PROJECTS"]
        for p in profile.projects:
            name = p.get("name", "Project")
            lines.append(name)
            chosen = next((x for x in data.get("project_bullets", []) if x.get("project") == name), None)
            bullets = (chosen or {}).get("bullets") or p.get("bullets") or ([p.get("summary")] if p.get("summary") else [])
            lines.extend([f"• {b}" for b in bullets if b])
    if profile.education:
        lines += ["", "EDUCATION"]
        for e in profile.education:
            lines.append(" — ".join(x for x in [e.get("degree", ""), e.get("school", ""), e.get("year", "")] if x))
    if profile.certifications:
        lines += ["", "CERTIFICATIONS"]
        for c in profile.certifications:
            lines.append(f"• {c if isinstance(c, str) else c.get('name','')}")
    lines += ["", f"Target role: {job.title} — {job.company}"]
    return "\n".join(lines)


def generate_application(db: Session, profile: CandidateProfile, job: Job, use_llm: bool = True, llm=None) -> Application:
    llm = llm or LLMService()
    if use_llm:
        if not llm.available():
            raise RuntimeError('Local AI is unavailable. Start Ollama or choose the profile-only package.')
        data = llm.generate_application(profile, job)
    else:
        data = _fallback(profile, job)
    data['_generation'] = {'mode': 'local_ai' if use_llm else 'profile_template', 'model': llm.model if use_llm else None}

    app = Application(job_id=job.id)
    cv_text = _render_cv(profile, job, data)
    app.cv_text = cv_text
    app.cover_letter = data.get("cover_letter", "")
    app.recruiter_message = data.get("recruiter_message", "")
    app.email_body = data.get("email_body", "")
    app.why_company = data.get("why_company", "")
    app.interview_prep = data.get("interview_prep", {})
    db.add(app)
    db.commit()
    db.refresh(app)

    folder = OUT_ROOT / f"{app.id}_{_safe(job.company)}_{_safe(job.title)}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "application.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "tailored_cv.txt").write_text(cv_text, encoding="utf-8")
    (folder / "cover_letter.txt").write_text(app.cover_letter, encoding="utf-8")
    (folder / "recruiter_message.txt").write_text(app.recruiter_message, encoding="utf-8")
    (folder / "email.txt").write_text((data.get("email_subject", "") + "\n\n" + app.email_body).strip(), encoding="utf-8")
    (folder / "interview_prep.json").write_text(json.dumps(app.interview_prep, ensure_ascii=False, indent=2), encoding="utf-8")
    _pdf(folder / "tailored_cv.pdf", f"{profile.name} — Tailored CV", cv_text)
    _pdf(folder / "cover_letter.pdf", f"Application — {job.title} at {job.company}", app.cover_letter)
    app.package_dir = str(folder.resolve())
    db.commit()
    db.refresh(app)
    return app
