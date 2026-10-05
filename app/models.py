from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    headline: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    categories: Mapped[dict] = mapped_column(JSON, default=dict)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    must_have_keywords: Mapped[list] = mapped_column(JSON, default=list)
    nice_to_have_keywords: Mapped[list] = mapped_column(JSON, default=list)
    exclude_keywords: Mapped[list] = mapped_column(JSON, default=list)
    target_seniority: Mapped[list] = mapped_column(JSON, default=list)
    preferred_employment: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    education: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    projects: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    resume_text: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(50))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_job_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    source_job_id: Mapped[str] = mapped_column(String(500), default="")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    company: Mapped[str] = mapped_column(String(300), index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    remote: Mapped[str] = mapped_column(String(100), default="")
    employment_type: Mapped[str] = mapped_column(String(100), default="")
    salary: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_status: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    source = relationship("Source")
    score = relationship("JobScore", back_populates="job", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    observations = relationship('JobObservation', cascade='all, delete-orphan')

    @property
    def focus(self):
        from .services.focus import assess
        return assess(self)

    @property
    def detail_status(self):
        return (self.raw or {}).get('detail_status', 'full')


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True, index=True)
    total: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    category: Mapped[str] = mapped_column(String(100), default="Other")
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    job = relationship("Job", back_populates="score")


class JobObservation(Base):
    __tablename__ = 'job_observations'
    __table_args__ = (UniqueConstraint('source_id', 'identity', name='uq_source_observation'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id', ondelete='CASCADE'), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('sources.id'), index=True)
    identity: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="generated", index=True)
    cv_text: Mapped[str] = mapped_column(Text, default="")
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    recruiter_message: Mapped[str] = mapped_column(Text, default="")
    email_body: Mapped[str] = mapped_column(Text, default="")
    why_company: Mapped[str] = mapped_column(Text, default="")
    interview_prep: Mapped[dict] = mapped_column(JSON, default=dict)
    package_dir: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    job = relationship("Job", back_populates="applications")
    followup = relationship("ApplicationFollowup", cascade="all, delete-orphan", uselist=False)


class ScanRun(Base):
    __tablename__ = 'scan_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default='running')
    trigger: Mapped[str] = mapped_column(String(30), default='manual')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    results: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ApplicationFollowup(Base):
    __tablename__ = 'application_followups'
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id'), primary_key=True)
    followup_date: Mapped[str] = mapped_column(String(10), default='')
    notes: Mapped[str] = mapped_column(Text, default='')


class MessageDraft(Base):
    __tablename__ = 'message_drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'), index=True)
    language: Mapped[str] = mapped_column(String(10))
    tone: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AITask(Base):
    __tablename__ = 'ai_tasks'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[str] = mapped_column(String(300), default='Waiting for local model')
    model: Mapped[str] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
