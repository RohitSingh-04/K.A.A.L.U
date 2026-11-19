from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BasicDetails(BaseModel):
    """Personal and contact details of the user."""
    name: str = Field(default="", description="Full name of the user")
    email: str = Field(default="", description="Primary email address")
    phone: str = Field(default="", description="Phone number")
    location: str = Field(default="", description="City, State, Country or current residence")
    headline: str = Field(default="", description="Professional title or headline")
    summary: str = Field(default="", description="Executive summary or bio")


class UserURLs(BaseModel):
    """Online presence, portfolio, and social links."""
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[str] = Field(default=None, description="GitHub profile URL")
    portfolio: Optional[str] = Field(default=None, description="Personal portfolio or website URL")
    website: Optional[str] = Field(default=None, description="Blog or personal website URL")
    other: List[str] = Field(default_factory=list, description="Other relevant links (Twitter, Kaggle, etc.)")


class Education(BaseModel):
    """Academic background and qualifications."""
    degree: str = Field(default="", description="Degree name (e.g., B.Tech, B.S., M.S.)")
    institution: str = Field(default="", description="University, college, or school name")
    field_of_study: Optional[str] = Field(default=None, description="Major, department, or field of study")
    start_year: Optional[str] = Field(default=None, description="Start year")
    end_year: Optional[str] = Field(default=None, description="Graduation year or expected graduation")
    grade: Optional[str] = Field(default=None, description="GPA, percentage, or honors")


class Experience(BaseModel):
    """Professional work history."""
    company: str = Field(default="", description="Employer or company name")
    role: str = Field(default="", description="Job title or role held")
    location: Optional[str] = Field(default=None, description="Location of work (e.g. Remote, City)")
    start_date: Optional[str] = Field(default=None, description="Start date (e.g., 'Jan 2022')")
    end_date: Optional[str] = Field(default=None, description="End date (e.g., 'Present' or 'Dec 2024')")
    current: bool = Field(default=False, description="Whether this is the current job")
    description: Optional[str] = Field(default=None, description="Summary of work or responsibilities")
    highlights: List[str] = Field(default_factory=list, description="Key achievements and bullet points")


class Certification(BaseModel):
    """Professional certifications and licenses."""
    name: str = Field(default="", description="Name of the certification")
    issuer: Optional[str] = Field(default=None, description="Issuing organization (e.g., AWS, Google, Coursera)")
    issue_date: Optional[str] = Field(default=None, description="Date issued")
    url: Optional[str] = Field(default=None, description="Verification URL or credential ID")


class Project(BaseModel):
    """Personal, open-source, or academic software projects."""
    name: str = Field(default="", description="Project title or name")
    description: Optional[str] = Field(default=None, description="Project summary / architecture")
    technologies: List[str] = Field(default_factory=list, description="Technologies or tech stack used")
    url: Optional[str] = Field(default=None, description="GitHub repository or live URL")
    highlights: List[str] = Field(default_factory=list, description="Key features or achievements")
    stars: Optional[int] = Field(default=0, description="GitHub stars count if fetched from repository")
    language: Optional[str] = Field(default=None, description="Primary programming language")


class Skills(BaseModel):
    """Categorized skill sets."""
    technical: List[str] = Field(default_factory=list, description="Programming languages, CS core concepts")
    frameworks_and_tools: List[str] = Field(default_factory=list, description="Libraries, frameworks, databases, developer tools")
    soft_skills: List[str] = Field(default_factory=list, description="Interpersonal and management skills")
    languages: List[str] = Field(default_factory=list, description="Spoken/natural languages")
    categories: Dict[str, List[str]] = Field(default_factory=dict, description="Custom skill categories e.g. {'AI & LLMs': ['LangChain']}")

    def all_categories(self) -> Dict[str, List[str]]:
        """Returns all skill categories including standard and custom groupings."""
        cats = {}
        if self.technical:
            cats["Technical / Languages"] = self.technical
        if self.frameworks_and_tools:
            cats["Frameworks & Tools"] = self.frameworks_and_tools
        if self.soft_skills:
            cats["Soft Skills"] = self.soft_skills
        if self.languages:
            cats["Spoken Languages"] = self.languages
        for k, v in self.categories.items():
            if k not in cats and v:
                cats[k] = v
        return cats

    def remove_category(self, category_name: str) -> bool:
        """
        Removes a skill category by name (case-insensitive) from standard or custom categories.
        Returns True if a category was found and removed, False otherwise.
        """
        norm = category_name.strip().lower()
        removed = False

        if norm in ("technical", "technical_skills", "technical / languages", "programming languages"):
            if self.technical:
                self.technical = []
                removed = True
        elif norm in ("frameworks", "tools", "frameworks_and_tools", "frameworks & tools", "frameworks, cloud & developer tools"):
            if self.frameworks_and_tools:
                self.frameworks_and_tools = []
                removed = True
        elif norm in ("soft_skills", "soft skills", "soft skills & methodologies"):
            if self.soft_skills:
                self.soft_skills = []
                removed = True
        elif norm in ("languages", "spoken languages"):
            if self.languages:
                self.languages = []
                removed = True

        # Check in custom categories
        for k in list(self.categories.keys()):
            if k.strip().lower() == norm:
                del self.categories[k]
                removed = True

        return removed


class UserProfile(BaseModel):
    """
    Standard centralized User Profile schema accessible by all Project Kaalu agents
    (Kaalu Orchestrator, David Browser Agent, Faulkner System Agent, RGS Hub).
    """
    basic_details: BasicDetails = Field(default_factory=BasicDetails)
    urls: UserURLs = Field(default_factory=UserURLs)
    skills: Skills = Field(default_factory=Skills)
    experiences: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    educations: List[Education] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    resume_path: Optional[str] = Field(default=None, description="Path to the source resume document")
    last_updated: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

    def to_prompt_context(self) -> str:
        """
        Formats a rich, structured summary for Kaalu's LLM context,
        enabling personalized career guidance, job filtering, and user awareness.
        """
        lines = ["[VERIFIED USER PROFILE]"]
        b = self.basic_details
        if b.name:
            lines.append(f"Name: {b.name}")
        if b.headline:
            lines.append(f"Headline: {b.headline}")
        if b.location:
            lines.append(f"Location: {b.location}")
        if b.email:
            lines.append(f"Email: {b.email}")
        if b.phone:
            lines.append(f"Phone: {b.phone}")
        if b.summary:
            lines.append(f"Bio/Summary: {b.summary}")

        # Online URLs
        u = self.urls
        url_entries = []
        if u.linkedin:
            url_entries.append(f"LinkedIn: {u.linkedin}")
        if u.github:
            url_entries.append(f"GitHub: {u.github}")
        if u.portfolio:
            url_entries.append(f"Portfolio: {u.portfolio}")
        if url_entries:
            lines.append(f"Profiles: {', '.join(url_entries)}")

        # Skills & Categories
        cats = self.skills.all_categories()
        if cats:
            lines.append("Skills & Expertise:")
            for cat_name, cat_skills in cats.items():
                if cat_skills:
                    lines.append(f"  - {cat_name}: {', '.join(cat_skills)}")

        # Recent Experience
        if self.experiences:
            exp_strs = []
            for exp in self.experiences[:3]:
                comp = exp.company
                role = exp.role
                dates = f" ({exp.start_date} - {exp.end_date or 'Present'})" if exp.start_date else ""
                exp_strs.append(f"{role} at {comp}{dates}")
            lines.append(f"Recent Experience: {'; '.join(exp_strs)}")

        # Key Projects
        if self.projects:
            proj_strs = []
            for proj in self.projects[:3]:
                t_str = f" ({', '.join(proj.technologies[:3])})" if proj.technologies else ""
                proj_strs.append(f"{proj.name}{t_str}")
            lines.append(f"Key Projects: {'; '.join(proj_strs)}")

        # Education
        if self.educations:
            edu_strs = [f"{e.degree} from {e.institution}" for e in self.educations[:2]]
            lines.append(f"Education: {'; '.join(edu_strs)}")

        # Certifications
        if self.certifications:
            cert_strs = [c.name for c in self.certifications[:3]]
            lines.append(f"Certifications: {', '.join(cert_strs)}")

        return "\n".join(lines)

    def get_form_fill_map(self) -> Dict[str, str]:
        """
        Returns a normalized semantic mapping of field labels to user profile values.
        Useful for David and Faulkner to autonomously autofill web forms or application inputs.
        """
        b = self.basic_details
        u = self.urls
        name_parts = b.name.split() if b.name else ["", ""]
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        recent_exp = self.experiences[0] if self.experiences else None
        recent_edu = self.educations[0] if self.educations else None
        all_skills = []
        for cat_skills in self.skills.all_categories().values():
            all_skills.extend(cat_skills)
        top_skills = ", ".join(all_skills)

        mapping = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": b.name,
            "name": b.name,
            "email": b.email,
            "phone": b.phone,
            "telephone": b.phone,
            "mobile": b.phone,
            "location": b.location,
            "address": b.location,
            "headline": b.headline,
            "summary": b.summary,
            "linkedin": u.linkedin or "",
            "github": u.github or "",
            "portfolio": u.portfolio or "",
            "website": u.website or u.portfolio or "",
            "company": recent_exp.company if recent_exp else "",
            "current_company": recent_exp.company if recent_exp else "",
            "role": recent_exp.role if recent_exp else "",
            "title": recent_exp.role if recent_exp else "",
            "job_title": recent_exp.role if recent_exp else "",
            "school": recent_edu.institution if recent_edu else "",
            "university": recent_edu.institution if recent_edu else "",
            "college": recent_edu.institution if recent_edu else "",
            "degree": recent_edu.degree if recent_edu else "",
            "skills": top_skills,
        }
        return {k: v for k, v in mapping.items() if v}

    def get_target_job_queries(self) -> List[str]:
        """
        Constructs tailored job search queries based on the user's headline and core skills.
        """
        queries = []
        b = self.basic_details
        skills = self.skills.technical + self.skills.frameworks_and_tools

        if b.headline:
            queries.append(f"{b.headline} jobs")

        if skills:
            primary_skill = skills[0]
            secondary_skill = skills[1] if len(skills) > 1 else ""
            queries.append(f"{primary_skill} developer jobs remote")
            if secondary_skill:
                queries.append(f"{primary_skill} {secondary_skill} engineer openings")

        if not queries:
            queries.append("software engineer jobs remote")

        return queries
