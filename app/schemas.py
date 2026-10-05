from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FollowupUpdate(BaseModel):
    followup_date: str = Field(default='', max_length=10)
    notes: str = Field(default='', max_length=10000)


class ProfileUpdate(BaseModel):
    name: str
    headline: str = ""
    summary: str = ""
    preferred_locations: list[str] = Field(default_factory=list)
    categories: dict[str, float] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    must_have_keywords: list[str] = Field(default_factory=list)
    nice_to_have_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    target_seniority: list[str] = Field(default_factory=list)
    preferred_employment: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any] | str] = Field(default_factory=list)
    resume_text: str = ""


class ProfileOut(ProfileUpdate, ORMModel):
    id: int
    updated_at: datetime


class SourceCreate(BaseModel):
    name: str
    kind: str
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class SourceOut(ORMModel):
    id: int
    name: str
    kind: str
    config: dict[str, Any]
    enabled: bool
    last_run_at: datetime | None
    last_error: str | None
    jobs_seen: int


class ScoreOut(ORMModel):
    total: float
    category: str
    breakdown: dict[str, Any]
    strengths: list[str]
    gaps: list[str]
    rationale: str
    llm_used: bool


class JobOut(ORMModel):
    focus: dict[str, Any] = Field(default_factory=dict)
    id: int
    detail_status: str = 'full'
    source_id: int | None = None
    source_job_id: str
    title: str
    company: str
    location: str
    remote: str
    employment_type: str
    salary: str
    url: str
    description: str
    requirements: str
    published_at: datetime | None
    application_status: str = 'unknown'
    application_deadline: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    active: bool
    score: ScoreOut | None = None


class ApplicationOut(ORMModel):
    id: int
    job_id: int
    status: str
    cv_text: str
    cover_letter: str
    recruiter_message: str
    email_body: str
    why_company: str
    interview_prep: dict[str, Any]
    package_dir: str
    created_at: datetime
    updated_at: datetime


class MessageRequest(BaseModel):
    channel: Literal['all', 'connection_note', 'recruiter_message', 'email_body'] = 'all'
    language: Literal['fr', 'en'] = 'fr'
    tone: Literal['professional', 'warm', 'concise'] = 'professional'
    recruiter_name: str = Field(default='', max_length=100)


class MessageContent(BaseModel):
    connection_note: str = Field(default='', max_length=300)
    recruiter_message: str = Field(default='', max_length=2500)
    email_subject: str = Field(default='', max_length=200)
    email_body: str = Field(default='', max_length=5000)


class AITaskRequest(MessageRequest):
    kind: Literal['message', 'analysis', 'application', 'agent_review'] = 'message'
    channel: Literal['all', 'connection_note', 'recruiter_message', 'email_body'] = 'recruiter_message'
    quality: Literal['fast', 'quality'] = 'quality'
    force: bool = False


class JobImport(BaseModel):
    published_at: datetime | None = None
    title: str = Field(min_length=1, max_length=500)
    company: str = Field(min_length=1, max_length=300)
    location: str = Field(default='France', max_length=300)
    url: str = Field(default='', max_length=2000)
    description: str = Field(min_length=50, max_length=40000)
