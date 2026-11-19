import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ResumeSnapshot(BaseModel):
    """Snapshot of resume content tailored for a specific target job."""
    template: Optional[str] = Field(default="Technical", description="Resume template used (e.g. Technical, Minimal ATS, Modern)")
    headline: Optional[str] = Field(default=None, description="Tailored candidate headline")
    summary: Optional[str] = Field(default=None, description="Tailored professional summary")
    skills: List[str] = Field(default_factory=list, description="Targeted skills selected for this job")
    projects: List[str] = Field(default_factory=list, description="Targeted projects highlighted for this job")
    custom_highlights: List[str] = Field(default_factory=list, description="Custom bullet points or achievement highlights")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Raw tailored resume snapshot from builder")


class JobApplicationRecord(BaseModel):
    """
    Central record of a job application, linking the exact tailored resume,
    target opportunity data, application status, and timestamps.
    """
    application_id: str = Field(
        default_factory=lambda: f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        description="Unique identifier for the job application"
    )
    company: str = Field(..., description="Target hiring company or organization")
    position: str = Field(..., description="Target job role / position title")
    job_description: Optional[str] = Field(default=None, description="Full or extracted job description text")
    job_url: Optional[str] = Field(default=None, description="URL of the job posting or application portal")
    location: Optional[str] = Field(default=None, description="Location of the job (e.g. Remote, City)")
    created_date: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp when resume/application was generated"
    )
    applied_date: Optional[str] = Field(
        default=None,
        description="Timestamp when application was submitted"
    )
    status: str = Field(
        default="generated",
        description="Lifecycle status: 'generated', 'downloaded', 'applied', 'interviewing', 'rejected'"
    )
    resume_path: Optional[str] = Field(
        default=None,
        description="Absolute path to the exact stored resume file (PDF or DOCX)"
    )
    resume_filename: Optional[str] = Field(
        default=None,
        description="Basename of the stored resume document"
    )
    resume_snapshot: Optional[ResumeSnapshot] = Field(
        default=None,
        description="Structured content of the tailored resume"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional context or notes for downstream agents"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata for cross-agent collaboration"
    )
