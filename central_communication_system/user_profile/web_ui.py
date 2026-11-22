import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from user_profile.schemas import (
    BasicDetails,
    Certification,
    Education,
    Experience,
    Project,
    Skills,
    UserProfile,
    UserURLs,
)


def build_user_profile_from_dict(
    data: Dict[str, Any],
    existing_profile: Optional[UserProfile] = None
) -> UserProfile:
    """
    Constructs or updates a UserProfile instance from either a structured JSON payload
    or a form dictionary, supporting dynamic multiple experiences, projects, educations,
    certifications, and custom skill categories.
    """
    if "basic_details" in data and isinstance(data.get("basic_details"), dict):
        return UserProfile.model_validate(data)

    base = existing_profile or UserProfile()

    def split_csv(val: Any) -> List[str]:
        if isinstance(val, list):
            return val
        if not val or not isinstance(val, str):
            return []
        return [item.strip() for item in val.split(",") if item.strip()]

    # Basic details
    name = data.get("name") if data.get("name") is not None else base.basic_details.name
    headline = data.get("headline") if data.get("headline") is not None else base.basic_details.headline
    email = data.get("email") if data.get("email") is not None else base.basic_details.email
    phone = data.get("phone") if data.get("phone") is not None else base.basic_details.phone
    location = data.get("location") if data.get("location") is not None else base.basic_details.location
    summary = data.get("summary") if data.get("summary") is not None else base.basic_details.summary

    # URLs
    linkedin = data.get("linkedin", base.urls.linkedin)
    github = data.get("github", base.urls.github)
    portfolio = data.get("portfolio", base.urls.portfolio)
    website = data.get("website", base.urls.website)

    # Standard Skills (respect explicit removals where value is None or empty)
    if "technical_skills" in data or "technical" in data:
        raw_tech = data.get("technical_skills") if "technical_skills" in data else data.get("technical")
        tech = split_csv(raw_tech)
    else:
        tech = list(base.skills.technical)

    if "frameworks_and_tools" in data or "frameworks" in data:
        raw_fw = data.get("frameworks_and_tools") if "frameworks_and_tools" in data else data.get("frameworks")
        frameworks = split_csv(raw_fw)
    else:
        frameworks = list(base.skills.frameworks_and_tools)

    if "soft_skills" in data:
        soft = split_csv(data.get("soft_skills"))
    else:
        soft = list(base.skills.soft_skills)

    if "languages" in data:
        lang = split_csv(data.get("languages"))
    else:
        lang = list(base.skills.languages)

    # Custom Categories
    if "custom_categories" in data and isinstance(data["custom_categories"], dict):
        custom_categories = {
            k.strip(): split_csv(v)
            for k, v in data["custom_categories"].items()
            if k.strip()
        }
    else:
        custom_categories = dict(base.skills.categories)

    # Experiences
    experiences: List[Experience] = []
    if "experiences" in data and isinstance(data["experiences"], list):
        for e in data["experiences"]:
            if isinstance(e, dict):
                experiences.append(Experience.model_validate(e))
            elif isinstance(e, Experience):
                experiences.append(e)
    elif "exp_company" in data or "exp_role" in data:
        dates = data.get("exp_dates", "")
        start_d, end_d = (dates.split("-", 1) if "-" in dates else (dates, None))
        experiences.append(
            Experience(
                company=data.get("exp_company", "Company"),
                role=data.get("exp_role", "Role"),
                location=data.get("exp_location"),
                start_date=start_d.strip() if start_d else None,
                end_date=end_d.strip() if end_d else None,
                description=data.get("exp_description")
            )
        )
    else:
        experiences = list(base.experiences)

    # Projects
    projects: List[Project] = []
    if "projects" in data and isinstance(data["projects"], list):
        for p in data["projects"]:
            if isinstance(p, dict):
                # Ensure technologies is a list
                p_copy = dict(p)
                if isinstance(p_copy.get("technologies"), str):
                    p_copy["technologies"] = split_csv(p_copy["technologies"])
                projects.append(Project.model_validate(p_copy))
            elif isinstance(p, Project):
                projects.append(p)
    else:
        projects = list(base.projects)

    # Educations
    educations: List[Education] = []
    if "educations" in data and isinstance(data["educations"], list):
        for ed in data["educations"]:
            if isinstance(ed, dict):
                educations.append(Education.model_validate(ed))
            elif isinstance(ed, Education):
                educations.append(ed)
    elif "edu_degree" in data or "edu_institution" in data:
        years = data.get("edu_years", "")
        sy, ey = (years.split("-", 1) if "-" in years else (years, None))
        educations.append(
            Education(
                degree=data.get("edu_degree", "Degree"),
                institution=data.get("edu_institution", "University"),
                start_year=sy.strip() if sy else None,
                end_year=ey.strip() if ey else None,
                grade=data.get("edu_grade")
            )
        )
    else:
        educations = list(base.educations)

    # Certifications
    certifications: List[Certification] = []
    if "certifications" in data and isinstance(data["certifications"], list):
        for c in data["certifications"]:
            if isinstance(c, dict):
                certifications.append(Certification.model_validate(c))
            elif isinstance(c, Certification):
                certifications.append(c)
    elif "cert_name" in data:
        certifications.append(
            Certification(
                name=data.get("cert_name", "Certification"),
                issuer=data.get("cert_issuer")
            )
        )
    else:
        certifications = list(base.certifications)

    return UserProfile(
        basic_details=BasicDetails(
            name=name or "",
            email=email or "",
            phone=phone or "",
            location=location or "",
            headline=headline or "",
            summary=summary or ""
        ),
        urls=UserURLs(
            linkedin=linkedin or None,
            github=github or None,
            portfolio=portfolio or None,
            website=website or None
        ),
        skills=Skills(
            technical=tech,
            frameworks_and_tools=frameworks,
            soft_skills=soft,
            languages=lang,
            categories=custom_categories
        ),
        experiences=experiences,
        projects=projects,
        educations=educations,
        certifications=certifications,
        resume_path=base.resume_path
    )


_CSS_STYLES = """
:root {
    --bg: #0b0f19;
    --card-bg: #151d30;
    --card-border: #1e293b;
    --item-bg: #0f172a;
    --input-bg: #0b0f19;
    --input-border: #334155;
    --text: #f8fafc;
    --text-muted: #94a3b8;
    --primary: #6366f1;
    --primary-hover: #4f46e5;
    --accent: #38bdf8;
    --success: #10b981;
    --error: #ef4444;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background-color: var(--bg);
    color: var(--text);
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
nav {
    background: #111827;
    border-bottom: 1px solid var(--card-border);
    padding: 0.85rem 1.75rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 50;
}
.nav-brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-weight: 700;
    font-size: 1.15rem;
    color: #fff;
    text-decoration: none;
}
.nav-brand span {
    background: linear-gradient(135deg, #6366f1, #38bdf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.nav-links {
    display: flex;
    gap: 0.75rem;
}
.nav-links a {
    color: var(--text-muted);
    text-decoration: none;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font-size: 0.9rem;
    transition: all 0.2s;
}
.nav-links a:hover, .nav-links a.active {
    color: #fff;
    background: #1e293b;
}
.container {
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1.25rem;
    width: 100%;
    flex: 1;
}
.card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 1.75rem;
    margin-bottom: 1.75rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
}
.card-header-flex {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.25rem;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 0.75rem;
}
.card-title {
    font-size: 1.15rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #f1f5f9;
}
.item-card {
    background: var(--item-bg);
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    position: relative;
}
.item-header-flex {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
}
.grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}
.grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1rem;
}
@media (max-width: 768px) {
    .grid-2, .grid-3 { grid-template-columns: 1fr; }
}
.form-group {
    margin-bottom: 1rem;
}
label {
    display: block;
    font-size: 0.825rem;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 0.35rem;
}
input[type="text"], input[type="email"], input[type="tel"], textarea {
    width: 100%;
    padding: 0.6rem 0.8rem;
    background: var(--input-bg);
    border: 1px solid var(--input-border);
    border-radius: 6px;
    color: #fff;
    font-size: 0.9rem;
    transition: border-color 0.2s;
}
input:focus, textarea:focus {
    outline: none;
    border-color: var(--primary);
}
textarea {
    resize: vertical;
    min-height: 75px;
}
.btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.55rem 1.15rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
    text-decoration: none;
}
.btn-primary {
    background: linear-gradient(135deg, var(--primary), #8b5cf6);
    color: #fff;
}
.btn-primary:hover {
    opacity: 0.92;
    transform: translateY(-1px);
}
.btn-secondary {
    background: #1e293b;
    color: #e2e8f0;
}
.btn-secondary:hover {
    background: #334155;
}
.btn-add {
    background: rgba(99, 102, 241, 0.1);
    color: var(--accent);
    border: 1px dashed rgba(56, 189, 248, 0.4);
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    transition: all 0.2s;
}
.btn-add:hover {
    background: rgba(56, 189, 248, 0.2);
    border-color: var(--accent);
    color: #fff;
}
.btn-github {
    background: #24292e;
    color: #fff;
    border: 1px solid #444d56;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    transition: all 0.2s;
}
.btn-github:hover {
    background: #2f363d;
    border-color: #8b949e;
}
.btn-remove {
    background: rgba(239, 68, 68, 0.12);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 0.3rem 0.65rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    transition: all 0.2s;
}
.btn-remove:hover {
    background: rgba(239, 68, 68, 0.28);
    color: #fff;
}
.alert {
    padding: 0.85rem 1.2rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.alert-success {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid var(--success);
    color: #6ee7b7;
}
.alert-error {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid var(--error);
    color: #fca5a5;
}
.drop-zone {
    border: 2px dashed #334155;
    border-radius: 12px;
    padding: 3rem 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: rgba(15, 23, 42, 0.6);
}
.drop-zone.dragover, .drop-zone:hover {
    border-color: var(--primary);
    background: rgba(99, 102, 241, 0.08);
}
.drop-icon {
    width: 48px;
    height: 48px;
    margin-bottom: 1rem;
    color: var(--accent);
}
.drop-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: 0.35rem;
}
.drop-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
}
.pill {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    background: rgba(56, 189, 248, 0.12);
    color: var(--accent);
    border-radius: 4px;
    font-size: 0.8rem;
    margin-right: 0.35rem;
    margin-bottom: 0.35rem;
}
.spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 0.8s linear infinite;
}
@keyframes spin {
    to { transform: rotate(360deg); }
}
.github-panel {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.25rem;
}
.repo-list {
    max-height: 280px;
    overflow-y: auto;
    margin-top: 1rem;
    border: 1px solid #1e293b;
    border-radius: 6px;
    background: #0b0f19;
}
.repo-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem;
    border-bottom: 1px solid #1e293b;
}
.repo-item:last-child { border-bottom: none; }
.repo-name { font-weight: 600; font-size: 0.9rem; color: #38bdf8; }
.repo-desc { font-size: 0.8rem; color: #94a3b8; margin-top: 0.2rem; }
.repo-meta { font-size: 0.75rem; color: #64748b; margin-top: 0.3rem; display: flex; gap: 0.75rem; }
.badge-online {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid #10b981;
    color: #34d399;
    font-weight: 600;
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
}
.badge-offline {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid #ef4444;
    color: #f87171;
    font-weight: 600;
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
}
.dot-green {
    background: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.8);
}
.dot-red {
    background: #ef4444;
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.8);
}
.dot-gray {
    background: #64748b;
}
.service-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: border-color 0.2s;
}
.service-card:hover {
    border-color: #334155;
}
.service-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
}
.service-title {
    font-weight: 600;
    font-size: 1rem;
    color: #f1f5f9;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.service-meta {
    font-size: 0.825rem;
    color: #94a3b8;
    margin-bottom: 0.75rem;
    line-height: 1.5;
}
.metric-box {
    background: #0b0f19;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}
.metric-val {
    font-size: 1.6rem;
    font-weight: 700;
    color: #38bdf8;
}
.metric-lbl {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.voice-pill {
    padding: 0.55rem 1rem;
    border-radius: 6px;
    border: 1px solid #334155;
    background: #0b0f19;
    color: #e2e8f0;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    transition: all 0.2s;
}
.voice-pill:hover {
    border-color: var(--accent);
    background: rgba(56, 189, 248, 0.08);
}
.voice-pill.active {
    border-color: var(--primary);
    background: rgba(99, 102, 241, 0.2);
    color: #fff;
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.3);
}
select.custom-select {
    width: 100%;
    padding: 0.6rem 0.8rem;
    background: var(--input-bg);
    border: 1px solid var(--input-border);
    border-radius: 6px;
    color: #fff;
    font-size: 0.9rem;
    transition: border-color 0.2s;
}
select.custom-select:focus {
    outline: none;
    border-color: var(--primary);
}
"""

_UPLOAD_JS = """
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('resumeFile');
const fileNameEl = document.getElementById('fileSelectedName');
const submitBtn = document.getElementById('submitBtn');
const form = document.getElementById('uploadForm');
const resultCard = document.getElementById('resultCard');
const resultPreview = document.getElementById('resultPreview');

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        const f = fileInput.files[0];
        fileNameEl.textContent = 'Selected: ' + f.name + ' (' + (f.size / 1024).toFixed(1) + ' KB)';
        submitBtn.disabled = false;
    }
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        const f = fileInput.files[0];
        fileNameEl.textContent = 'Selected: ' + f.name + ' (' + (f.size / 1024).toFixed(1) + ' KB)';
        submitBtn.disabled = false;
    }
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!fileInput.files || fileInput.files.length === 0) return;

    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> <span>Extracting Profile...</span>';

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const resp = await fetch('/profile/upload', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
            body: formData
        });

        if (resp.ok) {
            const data = await resp.json();
            const prof = data.profile || {};
            const b = prof.basic_details || {};
            const s = prof.skills || {};

            let previewHtml = '<div style="line-height: 1.8;">';
            previewHtml += '<strong>Name:</strong> ' + (b.name || 'Not detected') + '<br>';
            previewHtml += '<strong>Headline:</strong> ' + (b.headline || 'Not detected') + '<br>';
            previewHtml += '<strong>Email:</strong> ' + (b.email || 'Not detected') + '<br>';
            previewHtml += '<strong>Phone:</strong> ' + (b.phone || 'Not detected') + '<br>';
            if (s.technical && s.technical.length > 0) {
                previewHtml += '<div style="margin-top: 0.5rem;"><strong>Skills:</strong><br>';
                s.technical.slice(0, 10).forEach(sk => {
                    previewHtml += '<span class="pill">' + sk + '</span>';
                });
                previewHtml += '</div>';
            }
            previewHtml += '</div>';

            resultPreview.innerHTML = previewHtml;
            resultCard.style.display = 'block';
            resultCard.scrollIntoView({ behavior: 'smooth' });
        } else {
            const err = await resp.json();
            alert('Upload failed: ' + (err.detail || 'Unknown error'));
        }
    } catch (err) {
        alert('Connection error: ' + err.message);
    } finally {
        submitBtn.innerHTML = originalBtnText;
        submitBtn.disabled = false;
    }
});
"""

_EDIT_JS = """
// Helpers to Add and Remove DOM Cards
function removeElement(btn) {
    const card = btn.closest('.item-card');
    if (card) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.96)';
        card.style.transition = 'all 0.2s';
        setTimeout(() => card.remove(), 200);
    }
}

// 1. Add Experience Card
function addExperience(data = {}) {
    const container = document.getElementById('experiencesContainer');
    const div = document.createElement('div');
    div.className = 'item-card experience-item';
    div.innerHTML = `
        <div class="item-header-flex">
            <span style="font-weight: 600; color: #e2e8f0;">💼 Position</span>
            <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove</button>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Company / Employer</label>
                <input type="text" class="exp-company" value="${data.company || ''}" placeholder="e.g. Deloitte" required>
            </div>
            <div class="form-group">
                <label>Role / Job Title</label>
                <input type="text" class="exp-role" value="${data.role || ''}" placeholder="e.g. AI Engineer" required>
            </div>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Dates (Start - End)</label>
                <input type="text" class="exp-dates" value="${data.dates || (data.start_date ? data.start_date + ' - ' + (data.end_date || 'Present') : '')}" placeholder="e.g. Jan 2022 - Present">
            </div>
            <div class="form-group">
                <label>Location</label>
                <input type="text" class="exp-location" value="${data.location || ''}" placeholder="e.g. Remote or City, Country">
            </div>
        </div>
        <div class="form-group">
            <label>Key Responsibilities & Bullet Points</label>
            <textarea class="exp-highlights" placeholder="Bullet points or key accomplishments (one per line)...">${(data.highlights && data.highlights.length ? data.highlights.join('\\n') : (data.description || ''))}</textarea>
        </div>
    `;
    container.appendChild(div);
}

// 2. Add Project Card
function addProject(data = {}) {
    const container = document.getElementById('projectsContainer');
    const div = document.createElement('div');
    div.className = 'item-card project-item';
    const techStr = Array.isArray(data.technologies) ? data.technologies.join(', ') : (data.technologies || '');
    div.innerHTML = `
        <div class="item-header-flex">
            <span style="font-weight: 600; color: #e2e8f0;">🚀 Project</span>
            <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove</button>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Project Title / Name</label>
                <input type="text" class="proj-name" value="${data.name || ''}" placeholder="e.g. AML OSDD Helper" required>
            </div>
            <div class="form-group">
                <label>Technologies / Tech Stack (Comma-Separated)</label>
                <input type="text" class="proj-techs" value="${techStr}" placeholder="e.g. Python, LangChain, FastAPI, Docker">
            </div>
        </div>
        <div class="form-group">
            <label>Repository / Deployment URL</label>
            <input type="text" class="proj-url" value="${data.url || ''}" placeholder="https://github.com/username/project">
        </div>
        <div class="form-group">
            <label>Project Summary / Highlights</label>
            <textarea class="proj-desc" placeholder="Overview of features, architecture, and accomplishments...">${(data.highlights && data.highlights.length ? data.highlights.join('\\n') : (data.description || ''))}</textarea>
        </div>
    `;
    container.appendChild(div);
}

// 3. Add Education Card
function addEducation(data = {}) {
    const container = document.getElementById('educationsContainer');
    const div = document.createElement('div');
    div.className = 'item-card education-item';
    div.innerHTML = `
        <div class="item-header-flex">
            <span style="font-weight: 600; color: #e2e8f0;">🎓 Qualification</span>
            <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove</button>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Degree / Major</label>
                <input type="text" class="edu-degree" value="${data.degree || ''}" placeholder="e.g. Master of Computer Applications (MCA)" required>
            </div>
            <div class="form-group">
                <label>Institution / University</label>
                <input type="text" class="edu-institution" value="${data.institution || ''}" placeholder="e.g. Stanford University" required>
            </div>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Years (Start - End)</label>
                <input type="text" class="edu-years" value="${data.years || (data.start_year ? data.start_year + ' - ' + (data.end_year || '') : '')}" placeholder="e.g. 2022 - 2025">
            </div>
            <div class="form-group">
                <label>GPA / Grade / Status</label>
                <input type="text" class="edu-grade" value="${data.grade || ''}" placeholder="e.g. CGPA: 8.9/10 or Ongoing">
            </div>
        </div>
    `;
    container.appendChild(div);
}

// 4. Add Certification Card
function addCertification(data = {}) {
    const container = document.getElementById('certificationsContainer');
    const div = document.createElement('div');
    div.className = 'item-card certification-item';
    div.innerHTML = `
        <div class="item-header-flex">
            <span style="font-weight: 600; color: #e2e8f0;">🏆 Credential</span>
            <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove</button>
        </div>
        <div class="grid-3">
            <div class="form-group">
                <label>Certification Name</label>
                <input type="text" class="cert-name" value="${data.name || ''}" placeholder="e.g. AWS Solutions Architect" required>
            </div>
            <div class="form-group">
                <label>Issuing Organization</label>
                <input type="text" class="cert-issuer" value="${data.issuer || ''}" placeholder="e.g. Amazon Web Services">
            </div>
            <div class="form-group">
                <label>Year / Date</label>
                <input type="text" class="cert-date" value="${data.issue_date || ''}" placeholder="e.g. 2025">
            </div>
        </div>
    `;
    container.appendChild(div);
}

// 5. Add Custom Skill Category
function addSkillCategory(catName = '', skillsCsv = '') {
    const container = document.getElementById('customSkillsContainer');
    const div = document.createElement('div');
    div.className = 'item-card custom-skill-item';
    div.innerHTML = `
        <div class="item-header-flex">
            <span style="font-weight: 600; color: #e2e8f0;">💡 Custom Category</span>
            <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove Category</button>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Category Name</label>
                <input type="text" class="custom-cat-name" value="${catName}" placeholder="e.g. AI & LLMs, Cloud & DevOps" required>
            </div>
            <div class="form-group">
                <label>Skills (Comma-Separated)</label>
                <input type="text" class="custom-cat-skills" value="${skillsCsv}" placeholder="e.g. LangChain, Ollama, Docker, AWS" required>
            </div>
        </div>
    `;
    container.appendChild(div);
}

// 6. GitHub Repository Fetching
function toggleGitHubPanel() {
    const panel = document.getElementById('githubPanel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    if (panel.style.display === 'block') {
        const ghInput = document.getElementById('github');
        if (ghInput && ghInput.value) {
            const match = ghInput.value.match(/github\\.com\\/([a-zA-Z0-9_-]+)/);
            if (match) {
                document.getElementById('ghUsernameInput').value = match[1];
            }
        }
    }
}

let fetchedRepos = [];

async function fetchGitHubRepos() {
    const usernameInput = document.getElementById('ghUsernameInput');
    const statusEl = document.getElementById('ghStatusText');
    const repoListEl = document.getElementById('ghRepoList');
    const username = (usernameInput.value || '').trim();

    if (!username) {
        alert('Please enter a GitHub username.');
        return;
    }

    statusEl.innerHTML = '<span class="spinner"></span> Fetching repositories for @' + username + '...';
    repoListEl.innerHTML = '';

    try {
        const resp = await fetch('/profile/github/repos?username=' + encodeURIComponent(username));
        if (resp.ok) {
            const data = await resp.json();
            fetchedRepos = data.repositories || [];
            if (fetchedRepos.length === 0) {
                statusEl.textContent = 'No public repositories found for @' + username;
                return;
            }
            statusEl.textContent = 'Found ' + fetchedRepos.length + ' repositories. Select which to import:';

            let html = '';
            fetchedRepos.forEach((r, idx) => {
                const stars = r.stars ? '⭐ ' + r.stars : '';
                const lang = r.language ? '🏷️ ' + r.language : '';
                html += `
                    <div class="repo-item">
                        <input type="checkbox" id="repo_chk_${idx}" data-idx="${idx}" checked style="margin-top: 0.25rem;">
                        <div style="flex: 1;">
                            <label for="repo_chk_${idx}" class="repo-name" style="cursor: pointer;">${r.name}</label>
                            <div class="repo-desc">${r.description || 'No description provided.'}</div>
                            <div class="repo-meta">
                                <span>${lang}</span>
                                <span>${stars}</span>
                                <a href="${r.url}" target="_blank" style="color: #64748b; text-decoration: underline;">View on GitHub</a>
                            </div>
                        </div>
                    </div>
                `;
            });
            repoListEl.innerHTML = html;
            document.getElementById('importBtn').style.display = 'inline-flex';
        } else {
            const err = await resp.json();
            statusEl.textContent = 'Error: ' + (err.detail || 'Could not fetch GitHub repositories');
        }
    } catch (err) {
        statusEl.textContent = 'Connection error: ' + err.message;
    }
}

function importSelectedRepos() {
    let count = 0;
    fetchedRepos.forEach((r, idx) => {
        const chk = document.getElementById('repo_chk_' + idx);
        if (chk && chk.checked) {
            addProject({
                name: r.name,
                technologies: r.technologies,
                url: r.url,
                description: r.description,
                highlights: [r.description].filter(Boolean)
            });
            count++;
        }
    });
    alert('Imported ' + count + ' project(s) from GitHub! Click Save Profile Changes to persist.');
    document.getElementById('githubPanel').style.display = 'none';
}

// 7. Form Submission Handler
const editForm = document.getElementById('editProfileForm');
const saveBtn = document.getElementById('saveBtn');

editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner"></span> <span>Saving Changes...</span>';

    const techEl = document.getElementById('technical_skills');
    const frameworksEl = document.getElementById('frameworks_and_tools');
    const softEl = document.getElementById('soft_skills');
    const langEl = document.getElementById('languages');

    // Collect standard inputs
    const payload = {
        name: (document.getElementById('name').value || '').trim(),
        headline: (document.getElementById('headline').value || '').trim(),
        email: (document.getElementById('email').value || '').trim(),
        phone: (document.getElementById('phone').value || '').trim(),
        location: (document.getElementById('location').value || '').trim(),
        summary: (document.getElementById('summary').value || '').trim(),
        linkedin: (document.getElementById('linkedin').value || '').trim(),
        github: (document.getElementById('github').value || '').trim(),
        portfolio: (document.getElementById('portfolio').value || '').trim(),
        website: (document.getElementById('website').value || '').trim(),
        technical_skills: techEl ? techEl.value.trim() : null,
        frameworks_and_tools: frameworksEl ? frameworksEl.value.trim() : null,
        soft_skills: softEl ? softEl.value.trim() : null,
        languages: langEl ? langEl.value.trim() : null,
        custom_categories: {},
        experiences: [],
        projects: [],
        educations: [],
        certifications: []
    };

    // Collect custom skills
    document.querySelectorAll('.custom-skill-item').forEach(item => {
        const cat = (item.querySelector('.custom-cat-name').value || '').trim();
        const sks = (item.querySelector('.custom-cat-skills').value || '').trim();
        if (cat) {
            payload.custom_categories[cat] = sks;
        }
    });

    // Collect experiences
    document.querySelectorAll('.experience-item').forEach(item => {
        const comp = (item.querySelector('.exp-company').value || '').trim();
        const role = (item.querySelector('.exp-role').value || '').trim();
        const dates = (item.querySelector('.exp-dates').value || '').trim();
        const loc = (item.querySelector('.exp-location').value || '').trim();
        const hlText = (item.querySelector('.exp-highlights').value || '').trim();
        const highlights = hlText ? hlText.split('\\n').map(l => l.trim()).filter(Boolean) : [];

        let start_date = null;
        let end_date = null;
        if (dates.includes('-')) {
            const parts = dates.split('-');
            start_date = parts[0].trim();
            end_date = parts[1].trim();
        } else if (dates) {
            start_date = dates;
        }

        if (comp || role) {
            payload.experiences.push({
                company: comp,
                role: role,
                location: loc || null,
                start_date: start_date,
                end_date: end_date,
                current: end_date ? ['present', 'current', 'ongoing'].includes(end_date.toLowerCase()) : false,
                description: highlights[0] || '',
                highlights: highlights
            });
        }
    });

    // Collect projects
    document.querySelectorAll('.project-item').forEach(item => {
        const name = (item.querySelector('.proj-name').value || '').trim();
        const techs = (item.querySelector('.proj-techs').value || '').trim();
        const url = (item.querySelector('.proj-url').value || '').trim();
        const descText = (item.querySelector('.proj-desc').value || '').trim();
        const highlights = descText ? descText.split('\\n').map(l => l.trim()).filter(Boolean) : [];

        if (name) {
            payload.projects.push({
                name: name,
                technologies: techs ? techs.split(',').map(t => t.trim()).filter(Boolean) : [],
                url: url || null,
                description: highlights[0] || descText,
                highlights: highlights
            });
        }
    });

    // Collect educations
    document.querySelectorAll('.education-item').forEach(item => {
        const deg = (item.querySelector('.edu-degree').value || '').trim();
        const inst = (item.querySelector('.edu-institution').value || '').trim();
        const years = (item.querySelector('.edu-years').value || '').trim();
        const grade = (item.querySelector('.edu-grade').value || '').trim();

        let sy = null;
        let ey = null;
        if (years.includes('-')) {
            const parts = years.split('-');
            sy = parts[0].trim();
            ey = parts[1].trim();
        } else if (years) {
            sy = years;
        }

        if (deg || inst) {
            payload.educations.push({
                degree: deg,
                institution: inst,
                start_year: sy,
                end_year: ey,
                grade: grade || null
            });
        }
    });

    // Collect certifications
    document.querySelectorAll('.certification-item').forEach(item => {
        const name = (item.querySelector('.cert-name').value || '').trim();
        const issuer = (item.querySelector('.cert-issuer').value || '').trim();
        const date = (item.querySelector('.cert-date').value || '').trim();

        if (name) {
            payload.certifications.push({
                name: name,
                issuer: issuer || null,
                issue_date: date || null
            });
        }
    });

    try {
        const resp = await fetch('/profile/edit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            alert('✓ Profile updated successfully with ' + payload.experiences.length + ' experience(s), ' + payload.projects.length + ' project(s), and ' + payload.certifications.length + ' certification(s)!');
            window.location.reload();
        } else {
            const err = await resp.json();
            alert('Failed to save profile: ' + (err.detail || 'Unknown error'));
        }
    } catch (err) {
        alert('Connection error: ' + err.message);
    } finally {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
});
"""

_SETTINGS_JS = """
async function loadStatus() {
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) refreshBtn.innerHTML = '<span class="spinner"></span> Refreshing...';
    try {
        const resp = await fetch('/system/status');
        if (!resp.ok) throw new Error('Status endpoint returned ' + resp.status);
        const data = await resp.json();
        renderStatus(data);
    } catch (err) {
        console.error('Failed to load status:', err);
    } finally {
        if (refreshBtn) refreshBtn.innerHTML = '🔄 Refresh Status';
    }
}

function renderStatus(data) {
    // 1. Resume Builder
    const rb = data.services?.resume_builder || {};
    const rbBadge = document.getElementById('rbStatusBadge');
    const rbMeta = document.getElementById('rbStatusMeta');
    if (rbBadge && rbMeta) {
        if (rb.online) {
            rbBadge.className = 'badge-online';
            rbBadge.innerHTML = '<span class="status-dot dot-green"></span> Online (' + (rb.latency_ms || 0) + ' ms)';
            rbMeta.innerHTML = 'Status: <strong>Ready & Responding</strong> (HTTP ' + (rb.status_code || 200) + ')<br>URL: <a href="' + (rb.url || 'http://localhost:5173/') + '" target="_blank" style="color:#38bdf8;">' + (rb.url || 'http://localhost:5173/') + '</a>';
        } else {
            rbBadge.className = 'badge-offline';
            rbBadge.innerHTML = '<span class="status-dot dot-red"></span> Offline';
            rbMeta.innerHTML = 'Status: <strong>Not Reachable</strong><br>Ensure dev server is running on <a href="' + (rb.url || 'http://localhost:5173/') + '" target="_blank" style="color:#38bdf8;">http://localhost:5173/</a>';
        }
    }

    // 2. Connected Agents
    const agents = data.connected_agents?.agents || {};
    for (const [id, info] of Object.entries(agents)) {
        const badge = document.getElementById('agentBadge_' + id);
        if (badge) {
            if (info.connected) {
                badge.className = 'badge-online';
                badge.innerHTML = '<span class="status-dot dot-green"></span> Connected';
            } else {
                badge.className = 'badge-offline';
                badge.innerHTML = '<span class="status-dot dot-gray"></span> Disconnected';
            }
        }
    }
    const totalActiveEl = document.getElementById('totalActiveAgents');
    if (totalActiveEl) totalActiveEl.textContent = data.connected_agents?.total_active || 0;

    // 3. Stored Resumes & Applications
    const jt = data.services?.job_tracker || {};
    const totalAppsEl = document.getElementById('totalTrackedApps');
    if (totalAppsEl) totalAppsEl.textContent = jt.tracked_applications || 0;
    const totalResumesEl = document.getElementById('totalStoredResumes');
    if (totalResumesEl) totalResumesEl.textContent = jt.stored_resumes || 0;

    // 4. Voice Model
    const v = data.voice || {};
    const activeVoice = (v.active_voice || '').toLowerCase();
    const activeVoiceEl = document.getElementById('currentVoiceName');
    if (activeVoiceEl) activeVoiceEl.textContent = (activeVoice || 'None').toUpperCase();

    const availableVoices = v.available_voices || [];
    const container = document.getElementById('voicePillsContainer');
    if (container && availableVoices.length > 0) {
        let pillsHtml = '';
        availableVoices.forEach(voiceKey => {
            const isActive = voiceKey.toLowerCase() === activeVoice;
            let label = voiceKey.toUpperCase();
            if (voiceKey.toLowerCase() === 'tony') {
                label = 'Tony (RTX 3050 Fine-Tuned)';
            } else if (voiceKey.toLowerCase() === 'jarvis') {
                label = 'Jarvis (US Pretrained)';
            } else if (voiceKey.toLowerCase() === 'jarvis-gb') {
                label = 'Jarvis (GB British Pretrained)';
            } else {
                label = voiceKey.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + ' (Custom)';
            }
            pillsHtml += `<button type="button" class="voice-pill ${isActive ? 'active' : ''}" data-voice="${voiceKey}" onclick="changeVoice('${voiceKey}')">🎙️ ${label}</button> `;
        });
        pillsHtml += `<button type="button" class="btn btn-secondary" id="testVoiceBtn" onclick="testVoice()">🔊 Test Voice Audio</button>`;
        container.innerHTML = pillsHtml;
    } else {
        const voiceBtns = document.querySelectorAll('.voice-pill');
        voiceBtns.forEach(btn => {
            const voiceName = btn.getAttribute('data-voice');
            if (voiceName === activeVoice) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    // 5. LLM / Gemini Model
    const llm = data.llm || {};
    const modelEl = document.getElementById('currentLlmModel');
    if (modelEl) modelEl.textContent = llm.default_model || 'Unknown';
    const providerEl = document.getElementById('currentLlmProvider');
    if (providerEl) providerEl.textContent = (llm.default_provider || 'gemini').toUpperCase();
    const geminiKeyBadge = document.getElementById('geminiKeyBadge');
    if (geminiKeyBadge) {
        if (llm.api_keys?.gemini) {
            geminiKeyBadge.className = 'badge-online';
            geminiKeyBadge.innerHTML = '<span class="status-dot dot-green"></span> Key Configured';
        } else {
            geminiKeyBadge.className = 'badge-offline';
            geminiKeyBadge.innerHTML = '<span class="status-dot dot-red"></span> Key Missing';
        }
    }

    // 6. Connected Android Devices (OnePlus Phone, etc.)
    const devices = data.connected_devices || data.android_devices || [];
    const devContainer = document.getElementById('devicesContainer');
    const devCountBadge = document.getElementById('totalConnectedDevices');
    if (devCountBadge) devCountBadge.textContent = devices.length;

    if (devContainer) {
        if (devices.length === 0) {
            devContainer.innerHTML = '<div style="color: #64748b; font-size: 0.85rem; padding: 0.5rem 0;">No Android devices detected via ADB. Connect your OnePlus phone via USB or Wireless ADB.</div>';
        } else {
            let devsHtml = '';
            devices.forEach(d => {
                const brand = d.brand || 'Android';
                const model = d.model || '';
                const marketName = d.market_name || (brand + ' ' + model);
                const battery = (d.battery_level !== null && d.battery_level !== undefined) ? d.battery_level + '%' : 'N/A';
                const res = d.resolution || '1080x2400';
                const os = d.android_version ? 'Android ' + d.android_version : 'Android';
                const transport = d.transport || 'Wireless TLS';
                const serial = d.serial || '';

                devsHtml += `
                <div class="service-card" style="margin-bottom: 0.75rem;">
                    <div>
                        <div class="service-header">
                            <span class="service-title">
                                📱 ${marketName}
                            </span>
                            <span class="badge-online">
                                <span class="status-dot dot-green"></span> Online (${transport})
                            </span>
                        </div>
                        <div class="service-meta">
                            <strong>Model:</strong> ${brand} ${model} &nbsp;|&nbsp; 
                            <strong>Display:</strong> ${res} &nbsp;|&nbsp; 
                            <strong>Battery:</strong> 🔋 ${battery} &nbsp;|&nbsp; 
                            <strong>OS:</strong> ${os}<br>
                            <span style="color:#64748b; font-size:0.75rem;">Serial / ID: <code>${serial}</code></span>
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem;">
                        <button type="button" class="btn btn-secondary" onclick="captureAndroidScreen('${serial}')" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            📸 Capture Screenshot
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="unlockAndroidDevice('${serial}')" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            🔓 Unlock
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="sendAndroidKey('HOME', '${serial}')" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            🏠 Home
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="sendAndroidKey('BACK', '${serial}')" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            ◀ Back
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="sendAndroidKey('APP_SWITCH', '${serial}')" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            📋 Apps
                        </button>
                    </div>
                </div>
                `;
            });
            devContainer.innerHTML = devsHtml;
        }
    }

    // 7. Phone Security & Unlock PIN Status
    if (data.android_credentials) {
        updatePhonePinBadge(data.android_credentials);
    } else {
        loadPhonePinStatus();
    }

    // 8. Assistant Video Animations (GUI Mode)
    const animData = data.animations || {};
    const animCardsContainer = document.getElementById('animationCardsContainer');
    const animModeBadge = document.getElementById('animModeBadge');
    if (animModeBadge) {
        if (animData.gui_mode) {
            animModeBadge.className = 'badge-online';
            animModeBadge.textContent = '⚡ GUI Mode Active';
        } else {
            animModeBadge.className = 'badge-offline';
            animModeBadge.textContent = '🔒 Disabled (Active in GUI mode via GUI_KAALU.bat)';
        }
    }
    if (animCardsContainer && animData.available_animations && animData.available_animations.length > 0) {
        let cardsHtml = '';
        const activeAnim = animData.active_animation || '';
        const isGui = Boolean(animData.gui_mode);
        animData.available_animations.forEach(anim => {
            const isActive = (anim === activeAnim);
            const label = anim.replace('.mp4', '').replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const disabledAttr = isGui ? '' : 'disabled';
            const opacityStyle = isGui ? '' : 'opacity: 0.6; cursor: not-allowed;';
            const clickHandler = isGui ? `selectAnimation('${anim}')` : 'void(0)';
            cardsHtml += `
                <div class="service-card ${isActive ? 'active' : ''}" style="${opacityStyle} margin-bottom: 0.5rem; flex: 1; min-width: 240px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 600; color: #f8fafc; font-size: 0.9rem;">🎬 ${label}</div>
                            <div style="font-size: 0.75rem; color: #64748b; font-family: monospace;">${anim}</div>
                        </div>
                        <button type="button" class="btn ${isActive ? 'btn-primary' : 'btn-secondary'}"
                                ${disabledAttr} onclick="${clickHandler}" style="font-size: 0.75rem; padding: 0.35rem 0.75rem;">
                            ${isActive ? '✓ Active' : 'Select Animation'}
                        </button>
                    </div>
                </div>
            `;
        });
        animCardsContainer.innerHTML = cardsHtml;
    }
}

async function selectAnimation(animName) {
    try {
        const resp = await fetch('/api/animations/select', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({animation: animName})
        });
        if (resp.ok) {
            loadStatus();
        } else {
            const err = await resp.json();
            alert('Error selecting animation: ' + (err.detail || 'Failed'));
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}

async function probeResumeBuilder() {
    const btn = document.getElementById('probeRbBtn');
    const badge = document.getElementById('rbStatusBadge');
    const meta = document.getElementById('rbStatusMeta');
    
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Probing...';
    }
    if (badge) {
        badge.className = 'badge-offline';
        badge.innerHTML = '<span class="status-dot dot-gray"></span> Probing ports...';
    }
    if (meta) {
        meta.innerHTML = 'Scanning candidate ports (5173, 5174, 8005) on localhost & 127.0.0.1...';
    }
    
    try {
        const resp = await fetch('/api/probe/resumebuilder');
        if (!resp.ok) throw new Error('Probe returned HTTP ' + resp.status);
        const rb = await resp.json();
        if (badge && meta) {
            if (rb.online) {
                badge.className = 'badge-online';
                badge.innerHTML = '<span class="status-dot dot-green"></span> Online (' + (rb.latency_ms || 0) + ' ms)';
                meta.innerHTML = 'Status: <strong>Ready & Responding</strong> (HTTP ' + (rb.status_code || 200) + ')<br>URL: <a href="' + (rb.url || 'http://localhost:5173/') + '" target="_blank" style="color:#38bdf8;">' + (rb.url || 'http://localhost:5173/') + '</a>';
                const openLink = document.getElementById('openRbLink');
                if (openLink && rb.url) openLink.href = rb.url;
            } else {
                badge.className = 'badge-offline';
                badge.innerHTML = '<span class="status-dot dot-red"></span> Offline';
                meta.innerHTML = 'Status: <strong>Not Reachable</strong><br>Checked candidate ports 5173, 5174, 8005 on 127.0.0.1 & localhost.<br>To launch Resume Builder, run <code>start_with_RB.bat</code>.';
            }
        }
    } catch (err) {
        if (badge) {
            badge.className = 'badge-offline';
            badge.innerHTML = '<span class="status-dot dot-red"></span> Probe Failed';
        }
        if (meta) meta.innerHTML = 'Status: <strong>Probe error</strong> (' + err.message + ')';
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '⚡ Probe Now';
        }
    }
}

async function sendAndroidKey(keyName, serial) {
    try {
        const resp = await fetch('/android/key', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({key: keyName, serial: serial})
        });
        if (resp.ok) {
            console.log('Key ' + keyName + ' dispatched.');
        } else {
            const err = await resp.json();
            alert('Android key error: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Connection error: ' + e.message);
    }
}

async function captureAndroidScreen(serial) {
    try {
        const url = '/android/screenshot' + (serial ? '?serial=' + encodeURIComponent(serial) : '');
        const resp = await fetch(url);
        if (resp.ok) {
            const data = await resp.json();
            if (data.screenshot_base64) {
                const previewModal = document.getElementById('screenPreviewModal');
                const previewImg = document.getElementById('screenPreviewImg');
                if (previewModal && previewImg) {
                    previewImg.src = 'data:image/png;base64,' + data.screenshot_base64;
                    previewModal.style.display = 'block';
                    previewModal.scrollIntoView({ behavior: 'smooth' });
                }
            }
        } else {
            const err = await resp.json();
            alert('Screenshot capture failed: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Connection error: ' + e.message);
    }
}

function updatePhonePinBadge(data) {
    const badge = document.getElementById('phonePinStatusBadge');
    const updatedText = document.getElementById('phonePinUpdatedText');
    if (badge) {
        if (data.configured) {
            badge.className = 'badge-online';
            badge.innerHTML = '<span class="status-dot dot-green"></span> Configured (' + (data.cipher_method || 'DPAPI') + ')';
        } else {
            badge.className = 'badge-offline';
            badge.innerHTML = '<span class="status-dot dot-gray"></span> Not Configured';
        }
    }
    if (updatedText && data.updated_at) {
        const dateStr = new Date(data.updated_at).toLocaleTimeString();
        updatedText.innerText = 'Last updated: ' + dateStr;
    } else if (updatedText && !data.configured) {
        updatedText.innerText = '';
    }
}

async function loadPhonePinStatus(serial) {
    try {
        const url = '/android/credentials' + (serial ? '?serial=' + encodeURIComponent(serial) : '');
        const resp = await fetch(url);
        if (resp.ok) {
            const data = await resp.json();
            updatePhonePinBadge(data);
        }
    } catch (e) {
        console.error('Failed to query phone PIN status:', e);
    }
}

async function savePhonePin() {
    const input = document.getElementById('phonePinInput');
    const fb = document.getElementById('phonePinFeedback');
    if (!input || !input.value.trim()) {
        if (fb) {
            fb.style.display = 'block';
            fb.style.background = '#450a0a';
            fb.style.color = '#f87171';
            fb.innerText = 'Please enter a valid PIN or password.';
        }
        return;
    }
    try {
        const resp = await fetch('/android/credentials', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({pin: input.value.trim()})
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            input.value = '';
            if (fb) {
                fb.style.display = 'block';
                fb.style.background = '#064e3b';
                fb.style.color = '#34d399';
                fb.innerText = '✓ Phone PIN encrypted and safely saved via ' + (res.cipher_method || 'DPAPI') + '.';
            }
            await loadPhonePinStatus();
        } else {
            if (fb) {
                fb.style.display = 'block';
                fb.style.background = '#450a0a';
                fb.style.color = '#f87171';
                fb.innerText = 'Error: ' + (res.detail || res.error || 'Failed to save credentials');
            }
        }
    } catch (e) {
        if (fb) {
            fb.style.display = 'block';
            fb.style.background = '#450a0a';
            fb.style.color = '#f87171';
            fb.innerText = 'Network error: ' + e.message;
        }
    }
}

async function clearPhonePin() {
    if (!confirm('Are you sure you want to remove the saved phone unlock PIN?')) return;
    const fb = document.getElementById('phonePinFeedback');
    try {
        const resp = await fetch('/android/credentials', {
            method: 'DELETE',
            headers: {'Accept': 'application/json'}
        });
        const res = await resp.json();
        if (fb) {
            fb.style.display = 'block';
            fb.style.background = '#064e3b';
            fb.style.color = '#34d399';
            fb.innerText = '✓ Phone credentials removed.';
        }
        await loadPhonePinStatus();
    } catch (e) {
        if (fb) {
            fb.style.display = 'block';
            fb.style.background = '#450a0a';
            fb.style.color = '#f87171';
            fb.innerText = 'Network error: ' + e.message;
        }
    }
}

async function testUnlockPhone(serial) {
    const fb = document.getElementById('phonePinFeedback');
    if (fb) {
        fb.style.display = 'block';
        fb.style.background = '#1e293b';
        fb.style.color = '#38bdf8';
        fb.innerText = '⏳ Waking device and executing unlock sequence...';
    }
    try {
        const resp = await fetch('/android/unlock', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({serial: serial || undefined})
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            if (fb) {
                fb.style.background = '#064e3b';
                fb.style.color = '#34d399';
                fb.innerText = '✓ ' + (res.message || 'Device unlocked successfully!');
            }
        } else {
            if (fb) {
                fb.style.background = '#450a0a';
                fb.style.color = '#f87171';
                fb.innerText = 'Unlock failed: ' + (res.detail || res.error || 'Check device connection and PIN.');
            }
        }
    } catch (e) {
        if (fb) {
            fb.style.background = '#450a0a';
            fb.style.color = '#f87171';
            fb.innerText = 'Network error: ' + e.message;
        }
    }
}

async function unlockAndroidDevice(serial) {
    return testUnlockPhone(serial);
}

async function changeVoice(voiceName) {
    try {
        const resp = await fetch('/voice/change', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({voice: voiceName})
        });
        if (resp.ok) {
            loadStatus();
        } else {
            const err = await resp.json();
            alert('Failed to change voice: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Connection error: ' + e.message);
    }
}

async function testVoice() {
    const btn = document.getElementById('testVoiceBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Synthesizing...';
    }
    try {
        const resp = await fetch('/voice/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({text: 'Sir, neural speech synthesis is operational and ready to assist.'})
        });
        if (!resp.ok) {
            const err = await resp.json();
            alert('Voice test error: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Voice test error: ' + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '🔊 Test Voice Audio';
        }
    }
}

async function updateLlmModel() {
    const select = document.getElementById('modelSelect');
    if (!select) return;
    const newModel = select.value;
    try {
        const resp = await fetch('/llm/change', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({model: newModel, provider: 'gemini'})
        });
        if (resp.ok) {
            alert('✓ Gemini model updated to: ' + newModel);
            loadStatus();
        } else {
            const err = await resp.json();
            alert('Failed to update LLM model: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Connection error: ' + e.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    setInterval(loadStatus, 8000);
});
"""


def render_upload_page(message: Optional[str] = None, error: Optional[str] = None) -> str:
    """Renders the HTML file upload interface for resumes."""
    alert_html = ""
    if message:
        alert_html = f'<div class="alert alert-success"><span>✓</span> {message}</div>'
    elif error:
        alert_html = f'<div class="alert alert-error"><span>✕</span> {error}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Resume | Project Kaalu</title>
    <style>{_CSS_STYLES}</style>
</head>
<body>
    <nav>
        <a href="/profile/edit" class="nav-brand">
            <span>Project Kaalu</span> Central Hub
        </a>
        <div class="nav-links">
            <a href="/profile/upload" class="active">📄 Upload Resume</a>
            <a href="/profile/edit">✏️ Edit Profile</a>
            <a href="/settings" title="Settings">⚙️ Settings</a>
            <a href="/profile" target="_blank">📋 Raw JSON</a>
        </div>
    </nav>

    <div class="container">
        {alert_html}

        <div class="card">
            <div class="card-title">📄 Upload Candidate Resume</div>
            <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.5rem;">
                Upload a resume in <strong>PDF, TXT, MD, or JSON</strong> format. 
                Our standalone profile generator extracts contact details, links, education, work experience, and technical skills to create a centralized profile for Kaalu, David, and Faulkner.
            </p>

            <form id="uploadForm" action="/profile/upload" method="post" enctype="multipart/form-data">
                <div class="drop-zone" id="dropZone">
                    <svg class="drop-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                    </svg>
                    <div class="drop-title">Drag & drop your resume file here</div>
                    <div class="drop-desc">Supports PDF, TXT, Markdown, or JSON (up to 10MB)</div>
                    <div style="margin-top: 1.25rem;">
                        <label for="resumeFile" class="btn btn-secondary" style="display: inline-block; cursor: pointer;">
                            Browse Files
                        </label>
                        <input type="file" id="resumeFile" name="file" accept=".pdf,.txt,.md,.json" style="display: none;" required>
                    </div>
                    <div id="fileSelectedName" style="margin-top: 0.75rem; font-size: 0.875rem; color: var(--accent); font-weight: 500;"></div>
                </div>

                <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.75rem;">
                    <a href="/profile/edit" class="btn btn-secondary">Skip to Manual Edit</a>
                    <button type="submit" id="submitBtn" class="btn btn-primary" disabled>
                        <span>Extract & Generate Profile</span>
                    </button>
                </div>
            </form>
        </div>

        <div id="resultCard" class="card" style="display: none;">
            <div class="card-title">✓ Profile Generated Successfully</div>
            <div id="resultPreview" style="font-size: 0.9rem; margin-bottom: 1.25rem;"></div>
            <div style="display: flex; gap: 0.75rem;">
                <a href="/profile/edit" class="btn btn-primary">✏️ Review & Edit Profile</a>
                <a href="/profile" target="_blank" class="btn btn-secondary">View JSON</a>
            </div>
        </div>
    </div>

    <script>{_UPLOAD_JS}</script>
</body>
</html>
"""


def render_edit_page(
    profile: Optional[UserProfile] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    """
    Renders the rich, dynamic profile editor supporting multiple experiences,
    projects, educations, certifications, and custom skill categories.
    """
    b = profile.basic_details if profile else BasicDetails()
    u = profile.urls if profile else UserURLs()
    s = profile.skills if profile else Skills()
    experiences = profile.experiences if profile else []
    projects = profile.projects if profile else []
    educations = profile.educations if profile else []
    certifications = profile.certifications if profile else []

    tech_csv = ", ".join(s.technical)
    tools_csv = ", ".join(s.frameworks_and_tools)
    soft_csv = ", ".join(s.soft_skills)
    lang_csv = ", ".join(s.languages)

    tech_card = ""
    if not profile or s.technical:
        tech_card = f"""
                <div class="item-card standard-skill-item" id="card_technical_skills">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #e2e8f0;">💻 Technical / Programming Languages</span>
                        <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove Category</button>
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <input type="text" id="technical_skills" name="technical_skills" value="{html.escape(tech_csv)}" placeholder="Python, SQL, C/C++, Java, JavaScript">
                    </div>
                </div>
        """

    frameworks_card = ""
    if not profile or s.frameworks_and_tools:
        frameworks_card = f"""
                <div class="item-card standard-skill-item" id="card_frameworks_tools">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #e2e8f0;">🛠️ Frameworks, Cloud & Developer Tools</span>
                        <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove Category</button>
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <input type="text" id="frameworks_and_tools" name="frameworks_and_tools" value="{html.escape(tools_csv)}" placeholder="FastAPI, Docker, LangChain, PyTorch, AWS, Git">
                    </div>
                </div>
        """

    soft_card = ""
    if not profile or s.soft_skills:
        soft_card = f"""
                <div class="item-card standard-skill-item" id="card_soft_skills">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #e2e8f0;">🤝 Soft Skills & Methodologies</span>
                        <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove Category</button>
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <input type="text" id="soft_skills" name="soft_skills" value="{html.escape(soft_csv)}" placeholder="Agile, Problem Solving, Project Management">
                    </div>
                </div>
        """

    lang_card = ""
    if not profile or s.languages:
        lang_card = f"""
                <div class="item-card standard-skill-item" id="card_languages">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #e2e8f0;">🗣️ Spoken Languages</span>
                        <button type="button" class="btn-remove" onclick="removeElement(this)">🗑️ Remove Category</button>
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <input type="text" id="languages" name="languages" value="{html.escape(lang_csv)}" placeholder="English, Spanish, Hindi">
                    </div>
                </div>
        """

    alert_html = ""
    if message:
        alert_html = f'<div class="alert alert-success"><span>✓</span> {message}</div>'
    elif error:
        alert_html = f'<div class="alert alert-error"><span>✕</span> {error}</div>'
    elif not profile:
        alert_html = (
            '<div class="alert alert-error">'
            '<span>ℹ</span> No profile created yet. Fill in the fields below or '
            '<a href="/profile/upload" style="color: #fff; text-decoration: underline; margin-left: 0.25rem;">'
            'upload a resume</a> to auto-generate.'
            '</div>'
        )

    # Initial JS data loading scripts
    exp_json = json.dumps([e.model_dump() for e in experiences])
    proj_json = json.dumps([p.model_dump() for p in projects])
    edu_json = json.dumps([ed.model_dump() for ed in educations])
    cert_json = json.dumps([c.model_dump() for c in certifications])
    custom_skills_json = json.dumps(s.categories)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Profile | Project Kaalu</title>
    <style>{_CSS_STYLES}</style>
</head>
<body>
    <nav>
        <a href="/profile/edit" class="nav-brand">
            <span>Project Kaalu</span> Central Hub
        </a>
        <div class="nav-links">
            <a href="/profile/upload">📄 Upload Resume</a>
            <a href="/profile/edit" class="active">✏️ Edit Profile</a>
            <a href="/settings" title="Settings">⚙️ Settings</a>
            <a href="/profile" target="_blank">📋 Raw JSON</a>
        </div>
    </nav>

    <div class="container">
        {alert_html}

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem;">
            <div>
                <h1 style="font-size: 1.6rem; font-weight: 700;">Edit User Profile</h1>
                <p style="color: var(--text-muted); font-size: 0.875rem;">
                    Manage your background, skills, multiple experiences, projects, and credentials used across Kaalu, David, and Faulkner.
                </p>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <a href="/profile/upload" class="btn btn-secondary">Upload Resume</a>
                <a href="/profile" target="_blank" class="btn btn-secondary">Raw JSON</a>
            </div>
        </div>

        <form id="editProfileForm">
            <!-- 1. Basic Details -->
            <div class="card">
                <div class="card-title">👤 Basic Information</div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="name">Full Name</label>
                        <input type="text" id="name" name="name" value="{html.escape(b.name)}" placeholder="e.g. Rohit Singh" required>
                    </div>
                    <div class="form-group">
                        <label for="headline">Professional Headline / Role</label>
                        <input type="text" id="headline" name="headline" value="{html.escape(b.headline)}" placeholder="e.g. AI Engineer">
                    </div>
                </div>

                <div class="grid-2">
                    <div class="form-group">
                        <label for="email">Email Address</label>
                        <input type="email" id="email" name="email" value="{html.escape(b.email)}" placeholder="user@example.com" required>
                    </div>
                    <div class="form-group">
                        <label for="phone">Phone Number</label>
                        <input type="tel" id="phone" name="phone" value="{html.escape(b.phone)}" placeholder="+91-7409210904">
                    </div>
                </div>

                <div class="form-group">
                    <label for="location">Current Location</label>
                    <input type="text" id="location" name="location" value="{html.escape(b.location)}" placeholder="e.g. Bengaluru, India or Remote">
                </div>

                <div class="form-group">
                    <label for="summary">Professional Summary / Executive Bio</label>
                    <textarea id="summary" name="summary" placeholder="Executive summary of capabilities and accomplishments...">{html.escape(b.summary)}</textarea>
                </div>
            </div>

            <!-- 2. Online Presence & URLs -->
            <div class="card">
                <div class="card-title">🌐 Online Profiles & Links</div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="linkedin">LinkedIn Profile URL</label>
                        <input type="text" id="linkedin" name="linkedin" value="{html.escape(u.linkedin or '')}" placeholder="https://linkedin.com/in/username">
                    </div>
                    <div class="form-group">
                        <label for="github">GitHub Profile URL</label>
                        <input type="text" id="github" name="github" value="{html.escape(u.github or '')}" placeholder="https://github.com/username">
                    </div>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="portfolio">Portfolio / Personal Website</label>
                        <input type="text" id="portfolio" name="portfolio" value="{html.escape(u.portfolio or '')}" placeholder="https://myportfolio.dev">
                    </div>
                    <div class="form-group">
                        <label for="website">Other Deployment / Blog Link</label>
                        <input type="text" id="website" name="website" value="{html.escape(u.website or '')}" placeholder="https://blog.dev">
                    </div>
                </div>
            </div>

            <!-- 3. Skills & Dynamic Categories -->
            <div class="card">
                <div class="card-header-flex">
                    <div>
                        <div class="card-title">💡 Skills & Categories</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                            Organize skills by domain. You can add new categories or remove existing categories anytime.
                        </div>
                    </div>
                    <button type="button" class="btn-add" onclick="addSkillCategory()">+ Add Skill Category</button>
                </div>
                
                <div id="skillsCategoriesContainer">
                    {tech_card}
                    {frameworks_card}
                    {soft_card}
                    {lang_card}
                    <div id="customSkillsContainer"></div>
                </div>
            </div>

            <!-- 4. Work Experiences (Multiple) -->
            <div class="card">
                <div class="card-header-flex">
                    <div class="card-title">💼 Work Experience</div>
                    <button type="button" class="btn-add" onclick="addExperience()">+ Add Experience</button>
                </div>
                <div id="experiencesContainer"></div>
            </div>

            <!-- 5. Key Projects & GitHub Integration -->
            <div class="card">
                <div class="card-header-flex">
                    <div class="card-title">🚀 Projects & Portfolio</div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button type="button" class="btn-github" onclick="toggleGitHubPanel()">🐙 Fetch from GitHub</button>
                        <button type="button" class="btn-add" onclick="addProject()">+ Add Project</button>
                    </div>
                </div>

                <!-- GitHub Fetch Panel (Collapsible) -->
                <div id="githubPanel" class="github-panel" style="display: none;">
                    <div style="font-weight: 600; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span>🐙 Fetch Repositories from GitHub API</span>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        <input type="text" id="ghUsernameInput" placeholder="GitHub username (e.g. RohitSingh-04)" style="flex: 1;">
                        <button type="button" class="btn btn-secondary" onclick="fetchGitHubRepos()">Search Repos</button>
                        <button type="button" id="importBtn" class="btn btn-primary" style="display: none;" onclick="importSelectedRepos()">Import Selected</button>
                    </div>
                    <div id="ghStatusText" style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.5rem;"></div>
                    <div id="ghRepoList" class="repo-list"></div>
                </div>

                <div id="projectsContainer"></div>
            </div>

            <!-- 6. Education (Multiple) -->
            <div class="card">
                <div class="card-header-flex">
                    <div class="card-title">🎓 Education & Academics</div>
                    <button type="button" class="btn-add" onclick="addEducation()">+ Add Education</button>
                </div>
                <div id="educationsContainer"></div>
            </div>

            <!-- 7. Certifications (Multiple) -->
            <div class="card">
                <div class="card-header-flex">
                    <div class="card-title">🏆 Certifications & Licenses</div>
                    <button type="button" class="btn-add" onclick="addCertification()">+ Add Certification</button>
                </div>
                <div id="certificationsContainer"></div>
            </div>

            <!-- Save Action Bar -->
            <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-bottom: 3rem;">
                <a href="/profile" target="_blank" class="btn btn-secondary">View Raw JSON</a>
                <button type="submit" id="saveBtn" class="btn btn-primary" style="font-size: 1rem; padding: 0.75rem 1.75rem;">
                    <span>💾 Save Profile Changes</span>
                </button>
            </div>
        </form>
    </div>

    <script>{_EDIT_JS}</script>
    <script>
        // Populate existing experiences, projects, educations, and certifications on load
        const initialExperiences = {exp_json};
        const initialProjects = {proj_json};
        const initialEducations = {edu_json};
        const initialCertifications = {cert_json};
        const initialCustomSkills = {custom_skills_json};

        if (initialExperiences.length > 0) {{
            initialExperiences.forEach(exp => addExperience(exp));
        }} else {{
            addExperience();
        }}

        if (initialProjects.length > 0) {{
            initialProjects.forEach(proj => addProject(proj));
        }}

        if (initialEducations.length > 0) {{
            initialEducations.forEach(edu => addEducation(edu));
        }} else {{
            addEducation();
        }}

        if (initialCertifications.length > 0) {{
            initialCertifications.forEach(cert => addCertification(cert));
        }}

        if (initialCustomSkills && Object.keys(initialCustomSkills).length > 0) {{
            for (const [catName, skillsList] of Object.entries(initialCustomSkills)) {{
                const csv = Array.isArray(skillsList) ? skillsList.join(', ') : skillsList;
                addSkillCategory(catName, csv);
            }}
        }}
    </script>
</body>
</html>
"""


def _format_voice_label(name: str) -> str:
    n = name.lower()
    if n == "tony":
        return "Tony (RTX 3050 Fine-Tuned)"
    if n == "jarvis":
        return "Jarvis (US Pretrained)"
    if n == "jarvis-gb":
        return "Jarvis (GB British Pretrained)"
    return name.replace("-", " ").replace("_", " ").title() + " (Pretrained)"


def _get_settings_voice_info(status_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    models_dir = Path(__file__).resolve().parent.parent / "voice_system" / "models"
    available_voices: List[str] = []
    if models_dir.exists():
        for d in sorted(models_dir.iterdir()):
            if d.is_dir() and list(d.glob("*.onnx")):
                available_voices.append(d.name)
    if not available_voices:
        available_voices = ["tony", "jarvis", "jarvis-gb"]

    active_voice = "tony"
    if status_data and "voice" in status_data and status_data["voice"].get("active_voice"):
        active_voice = str(status_data["voice"]["active_voice"]).lower()
    else:
        voice_cfg = Path(__file__).resolve().parent.parent / "data" / "voice_settings.json"
        if voice_cfg.exists():
            try:
                with open(voice_cfg, "r", encoding="utf-8") as f:
                    active_voice = json.load(f).get("active_voice", "tony").lower()
            except Exception:
                pass

    voice_pills = []
    for vk in available_voices:
        is_active = (vk.lower() == active_voice)
        active_cls = " active" if is_active else ""
        label = _format_voice_label(vk)
        voice_pills.append(
            f'<button type="button" class="voice-pill{active_cls}" data-voice="{html.escape(vk)}" onclick="changeVoice(\'{html.escape(vk)}\')">'
            f'🎙️ {html.escape(label)}'
            f'</button>'
        )
    return active_voice.upper(), "\n                ".join(voice_pills)


def _get_settings_animation_info(status_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str, bool]:
    is_gui_mode = os.environ.get("KAALU_GUI_MODE") == "1"
    anims_dir = Path(__file__).resolve().parent.parent.parent / "Animations"
    available = []
    if anims_dir.exists():
        available = sorted([f.name for f in anims_dir.glob("*.mp4") if f.is_file()])
    if not available:
        available = ["jarvis-30-fps-1600x1600.mp4", "jarvis-blue.mp4"]

    active_anim = "jarvis-30-fps-1600x1600.mp4"
    if status_data and "animations" in status_data and status_data["animations"].get("active_animation"):
        active_anim = str(status_data["animations"]["active_animation"])
    else:
        anim_cfg = Path(__file__).resolve().parent.parent / "data" / "animation_settings.json"
        if anim_cfg.exists():
            try:
                with open(anim_cfg, "r", encoding="utf-8") as f:
                    saved = json.load(f).get("active_animation")
                    if saved and saved in available:
                        active_anim = saved
            except Exception:
                pass

    cards = []
    for anim in available:
        is_active = (anim == active_anim)
        active_cls = " active" if is_active else ""
        label = anim.replace(".mp4", "").replace("-", " ").replace("_", " ").title()
        disabled_attr = "" if is_gui_mode else "disabled"
        click_handler = f"selectAnimation('{html.escape(anim)}')" if is_gui_mode else "void(0)"
        opacity_style = "" if is_gui_mode else "opacity: 0.6; cursor: not-allowed;"

        cards.append(
            f'<div class="service-card{active_cls}" style="{opacity_style} margin-bottom: 0.5rem; flex: 1; min-width: 240px;">'
            f'  <div style="display: flex; justify-content: space-between; align-items: center;">'
            f'    <div>'
            f'      <div style="font-weight: 600; color: #f8fafc; font-size: 0.9rem;">🎬 {html.escape(label)}</div>'
            f'      <div style="font-size: 0.75rem; color: #64748b; font-family: monospace;">{html.escape(anim)}</div>'
            f'    </div>'
            f'    <button type="button" class="btn {"btn-primary" if is_active else "btn-secondary"}" '
            f'            {disabled_attr} onclick="{click_handler}" style="font-size: 0.75rem; padding: 0.35rem 0.75rem;">'
            f'      {"✓ Active" if is_active else "Select Animation"}'
            f'    </button>'
            f'  </div>'
            f'</div>'
        )

    return active_anim, "\n                ".join(cards), is_gui_mode


def render_settings_page(
    status_data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    error: Optional[str] = None
) -> str:
    """
    Renders the unified Settings & Agent Fleet Monitoring dashboard.
    Displays live status of Resume Builder, connected agents, online services,
    voice engine with switcher, and Gemini LLM configuration.
    """
    alert_html = ""
    if message:
        alert_html = f'<div class="alert alert-success"><span>✓</span> {message}</div>'
    elif error:
        alert_html = f'<div class="alert alert-error"><span>✕</span> {error}</div>'

    active_voice_badge, voice_pills_html = _get_settings_voice_info(status_data)
    active_anim, anim_cards_html, is_gui_mode = _get_settings_animation_info(status_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Settings & Agent Fleet | Project Kaalu</title>
    <style>{_CSS_STYLES}</style>
</head>
<body>
    <nav>
        <a href="/profile/edit" class="nav-brand">
            <span>Project Kaalu</span> Central Hub
        </a>
        <div class="nav-links">
            <a href="/profile/upload">📄 Upload Resume</a>
            <a href="/profile/edit">✏️ Edit Profile</a>
            <a href="/settings" class="active" title="Settings">⚙️ Settings</a>
            <a href="/profile" target="_blank">📋 Raw JSON</a>
        </div>
    </nav>

    <div class="container">
        {alert_html}

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem;">
            <div>
                <h1 style="font-size: 1.6rem; font-weight: 700;">⚙️ System Settings & Fleet Monitor</h1>
                <p style="color: var(--text-muted); font-size: 0.875rem;">
                    Live health telemetry, connected sub-agents, online services, neural voice switching, and Gemini model settings.
                </p>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <button type="button" class="btn btn-secondary" id="refreshBtn" onclick="loadStatus()">
                    🔄 Refresh Status
                </button>
                <a href="http://localhost:5173/" target="_blank" class="btn btn-primary">
                    🚀 Launch Resume Builder
                </a>
            </div>
        </div>

        <!-- Metric KPI Cards -->
        <div class="grid-3" style="margin-bottom: 1.75rem;">
            <div class="metric-box">
                <div class="metric-val" id="totalActiveAgents">0</div>
                <div class="metric-lbl">Connected Sub-Agents</div>
            </div>
            <div class="metric-box">
                <div class="metric-val" id="totalStoredResumes">0</div>
                <div class="metric-lbl">Stored Tailored Resumes</div>
            </div>
            <div class="metric-box">
                <div class="metric-val" id="totalTrackedApps">0</div>
                <div class="metric-lbl">Tracked Applications</div>
            </div>
        </div>

        <!-- Section 1: Online Services -->
        <div class="card">
            <div class="card-header-flex">
                <div class="card-title">🌐 Online Services & External Integrations</div>
            </div>
            <div class="grid-2">
                <!-- Resume Builder Card -->
                <div class="service-card">
                    <div>
                        <div class="service-header">
                            <span class="service-title">📝 Resume Builder Web App</span>
                            <span id="rbStatusBadge" class="badge-offline">
                                <span class="status-dot dot-gray"></span> Probing...
                            </span>
                        </div>
                        <div class="service-meta" id="rbStatusMeta">
                            Checking connection to <strong>http://localhost:5173/</strong>...
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                        <a href="http://localhost:5173/" id="openRbLink" target="_blank" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            🔗 Open Web App
                        </a>
                        <button type="button" class="btn btn-secondary" id="probeRbBtn" onclick="probeResumeBuilder()" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            ⚡ Probe Now
                        </button>
                    </div>
                </div>

                <!-- RGS Gateway Card -->
                <div class="service-card">
                    <div>
                        <div class="service-header">
                            <span class="service-title">⚡ RGS Central Communication Hub</span>
                            <span class="badge-online">
                                <span class="status-dot dot-green"></span> Online (:8000)
                            </span>
                        </div>
                        <div class="service-meta">
                            Status: <strong>Active Gateway v2.0.0</strong><br>
                            Channels: WebSocket Messaging Bus & LiteLLM Gateway
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                        <a href="/system/status" target="_blank" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">
                            📊 System Status JSON
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Section 2: Connected Sub-Agents Fleet -->
        <div class="card">
            <div class="card-header-flex">
                <div class="card-title">🤖 Connected Sub-Agents Fleet</div>
            </div>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
                Autonomous multi-agent processes connected to RGS Central Hub via high-speed WebSockets.
            </p>
            <div class="grid-3">
                <!-- Kaalu -->
                <div class="item-card" style="margin-bottom: 0;">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #f1f5f9;">👑 Kaalu</span>
                        <span id="agentBadge_kaalu" class="badge-offline">
                            <span class="status-dot dot-gray"></span> Disconnected
                        </span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">
                        <strong>Role:</strong> Master Orchestrator, ReAct loop, context manager, and user-facing voice intelligence.
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.75rem; color: #64748b;">
                        <code>/ws/kaalu</code>
                    </div>
                </div>

                <!-- Faulkner -->
                <div class="item-card" style="margin-bottom: 0;">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #f1f5f9;">⚡ Faulkner</span>
                        <span id="agentBadge_faulkner" class="badge-offline">
                            <span class="status-dot dot-gray"></span> Disconnected
                        </span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">
                        <strong>Role:</strong> Local Windows system agent, terminal execution, desktop screen capture, and process control.
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.75rem; color: #64748b;">
                        <code>/ws/faulkner</code>
                    </div>
                </div>

                <!-- David -->
                <div class="item-card" style="margin-bottom: 0;">
                    <div class="item-header-flex">
                        <span style="font-weight: 600; color: #f1f5f9;">🌐 David</span>
                        <span id="agentBadge_david" class="badge-offline">
                            <span class="status-dot dot-gray"></span> Disconnected
                        </span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">
                        <strong>Role:</strong> Chrome Extension V3 browser agent, semantic DOM navigation, form autofill, and page scraping.
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.75rem; color: #64748b;">
                        <code>/ws/david</code>
                    </div>
                </div>
            </div>
        </div>

        <!-- Section 3: Connected Hardware & Android Devices -->
        <div class="card">
            <div class="card-header-flex">
                <div class="card-title">📱 Connected Hardware & Mobile Devices (ADB)</div>
                <div>
                    <span style="font-size: 0.8rem; color: #94a3b8; margin-right: 0.5rem;">Detected Devices:</span>
                    <span id="totalConnectedDevices" class="badge-online" style="padding: 0.2rem 0.6rem;">0</span>
                </div>
            </div>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
                Real-time connection with Android phones over USB / Wireless ADB. Kaalu has vision, screen analysis, touch tap, keyboard, and shell execution capabilities.
            </p>
            <div id="devicesContainer">
                <div style="color: #64748b; font-size: 0.85rem;">Scanning for connected Android devices via ADB...</div>
            </div>
            <!-- Live Screen Preview Modal -->
            <div id="screenPreviewModal" style="display: none; margin-top: 1.25rem; padding: 1rem; background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <span style="font-weight: 600; color: #38bdf8;">📸 Live OnePlus Screen Preview</span>
                    <button type="button" class="btn-remove" onclick="document.getElementById('screenPreviewModal').style.display='none'">✕ Close Preview</button>
                </div>
                <div style="text-align: center;">
                    <img id="screenPreviewImg" src="" alt="Android Screenshot" style="max-height: 480px; max-width: 100%; border-radius: 8px; border: 1px solid #334155; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                </div>
            </div>

            <!-- Phone Security & Unlock Credentials (Encrypted) -->
            <div style="margin-top: 1.5rem; padding: 1rem 1.25rem; background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                    <div style="font-weight: 600; color: #f8fafc; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span>🔐 Phone Security & Unlock PIN</span>
                        <span id="phonePinStatusBadge" class="badge-offline" style="font-size: 0.75rem; padding: 0.2rem 0.6rem;">Checking...</span>
                    </div>
                    <span style="font-size: 0.75rem; color: #64748b;" id="phonePinUpdatedText"></span>
                </div>
                <p style="color: var(--text-muted); font-size: 0.8rem; margin-bottom: 0.75rem; line-height: 1.4;">
                    Stores your phone unlock PIN/password encrypted with <strong>Windows DPAPI</strong> (machine- and user-bound hardware protection).
                    Kaalu uses this to wake and unlock your device when prompted (e.g. <em>"Kaalu, unlock my phone"</em>) without exposing plaintext secrets.
                </p>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
                    <input type="password" id="phonePinInput" placeholder="Enter device PIN or password" autocomplete="new-password"
                           style="background: #0f172a; border: 1px solid #334155; color: #f8fafc; padding: 0.45rem 0.8rem; border-radius: 6px; font-size: 0.85rem; width: 220px;">
                    <button type="button" class="btn btn-primary" onclick="savePhonePin()" style="font-size: 0.8rem; padding: 0.45rem 0.9rem;">
                        💾 Save Encrypted PIN
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="testUnlockPhone()" style="font-size: 0.8rem; padding: 0.45rem 0.9rem;">
                        🔓 Test Unlock Phone
                    </button>
                    <button type="button" class="btn btn-remove" onclick="clearPhonePin()" style="font-size: 0.8rem; padding: 0.45rem 0.9rem;">
                        🗑️ Clear PIN
                    </button>
                </div>
                <div id="phonePinFeedback" style="display: none; margin-top: 0.5rem; font-size: 0.8rem; border-radius: 4px; padding: 0.35rem 0.6rem;"></div>
            </div>
        </div>

        <!-- Section 4: Neural Voice Engine -->
        <div class="card">
            <div class="card-header-flex">
                <div class="card-title">🎙️ Neural Voice Engine & Model Selector</div>
                <div>
                    <span style="font-size: 0.8rem; color: #94a3b8; margin-right: 0.5rem;">Active Voice:</span>
                    <span id="currentVoiceName" class="badge-online" style="font-size: 0.85rem; padding: 0.3rem 0.8rem;">{active_voice_badge}</span>
                </div>
            </div>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
                Select between custom-trained Piper VITS models or pretrained Jarvis models. Switch voice in real-time without restarting agents.
            </p>
            <div id="voicePillsContainer" style="display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; margin-bottom: 1.25rem;">
                {voice_pills_html}
                <button type="button" class="btn btn-secondary" id="testVoiceBtn" onclick="testVoice()">
                    🔊 Test Voice Audio
                </button>
            </div>
            <div style="font-size: 0.8rem; color: #64748b; background: #0b0f19; padding: 0.75rem; border-radius: 6px; border: 1px solid #1e293b;">
                ⚡ <strong>Hardware Acceleration:</strong> Tensor Core 16-mixed precision enabled on CUDA. Audio cleaned via automated regex pipe stripping markdown symbols and raw file paths.
            </div>
        </div>

        <!-- Section 5: Assistant Video Animations (GUI Mode) -->
        <div class="card">
            <div class="card-header-flex">
                <div class="card-title">🎬 Visual Assistant Animations (Hologram Avatar)</div>
                <div>
                    <span style="font-size: 0.8rem; color: #94a3b8; margin-right: 0.5rem;">Mode:</span>
                    <span id="animModeBadge" class="{'badge-online' if is_gui_mode else 'badge-offline'}" style="font-size: 0.75rem; padding: 0.2rem 0.6rem;">
                        {'⚡ GUI Mode Active' if is_gui_mode else '🔒 Disabled (Active in GUI mode via GUI_KAALU.bat)'}
                    </span>
                </div>
            </div>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
                Select the MP4 video animation displayed in Tab 2 of the GUI. Animations are loaded dynamically from the <code>Animations/</code> directory.
                {'' if is_gui_mode else '<br><strong style="color: #f59e0b;">Notice:</strong> Options are disabled because the system was launched via standard CLI script. Launch via <code>GUI_KAALU.bat</code> to enable live avatar animations.'}
            </p>
            <div id="animationCardsContainer" style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                {anim_cards_html}
            </div>
        </div>

        <!-- Section 4: LLM Gateway & Gemini Configuration -->
        <div class="card">
            <div class="card-header-flex">
                <div class="card-title">🧠 Central LLM Gateway & Gemini Model</div>
                <div id="geminiKeyBadge" class="badge-online">
                    <span class="status-dot dot-green"></span> Key Configured
                </div>
            </div>
            <div class="grid-2" style="margin-bottom: 1.25rem;">
                <div class="form-group">
                    <label>Active Provider</label>
                    <input type="text" id="currentLlmProvider" value="GEMINI" readonly style="opacity: 0.85; cursor: default;">
                </div>
                <div class="form-group">
                    <label>Active Model Name</label>
                    <input type="text" id="currentLlmModel" value="gemini-3.1-flash-lite" readonly style="opacity: 0.85; cursor: default;">
                </div>
            </div>
            <div class="grid-2" style="align-items: flex-end;">
                <div class="form-group" style="margin-bottom: 0;">
                    <label for="modelSelect">Switch Gemini / LiteLLM Model</label>
                    <select id="modelSelect" class="custom-select">
                        <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite (Fastest, High Throughput)</option>
                        <option value="gemini-flash-latest">gemini-flash-latest (Production General)</option>
                        <option value="gemini-2.5-flash">gemini-2.5-flash (Balanced Reasoning)</option>
                        <option value="gemini-2.5-pro">gemini-2.5-pro (Deep Thought & Planning)</option>
                        <option value="qwen2.5:3b">qwen2.5:3b (Local Ollama Fallback)</option>
                    </select>
                </div>
                <div>
                    <button type="button" class="btn btn-primary" onclick="updateLlmModel()">
                        💾 Update Active Model
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>{_SETTINGS_JS}</script>
</body>
</html>
"""
