import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from rgs_hub.ws_manager import ConnectionManager
from rgs_hub.schemas import AgentMessage, LLMGenerationRequest, LLMGenerationResponse
from rgs_hub.llm_gateway import LLMGateway
from user_profile import (
    ProfileManager,
    ProfileGenerator,
    Project,
    render_upload_page,
    render_edit_page,
    build_user_profile_from_dict,
)
from job_tracker import (
    JobTrackerManager,
    JobApplicationRecord,
    ResumeSnapshot,
)

app = FastAPI(title="RGS Central Gateway & Communication Hub", version="2.0.0")

# Enable CORS for external agents and UI connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
llm_gateway = LLMGateway()

@app.get("/")
async def root():
    """Health check endpoint showing active WebSocket clients and default LLM configuration."""
    return {
        "status": "RGS Central Gateway is active",
        "active_clients": list(manager.active_connections.keys()),
        "default_llm_provider": llm_gateway.config.get("llm", {}).get("default_provider"),
        "default_model": llm_gateway.config.get("llm", {}).get("default_model")
    }

@app.post("/llm/generate", response_model=LLMGenerationResponse)
async def generate_llm_completion(request: LLMGenerationRequest):
    """
    Centralized LLM inference endpoint. 
    Agents (like Kaalu) send their prompts here instead of connecting to local models directly.
    """
    try:
        result = await llm_gateway.generate(
            prompt=request.prompt,
            messages=[m.model_dump() for m in request.messages] if request.messages else None,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature
        )
        return LLMGenerationResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile")
async def get_user_profile():
    """Returns the current user profile JSON for agents or UI."""
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No user profile found. Upload a resume to generate one.")
    return profile.model_dump()

@app.get("/profile/upload", response_class=HTMLResponse)
async def get_upload_page():
    """Renders the HTML form for uploading resume files."""
    return HTMLResponse(content=render_upload_page())

@app.post("/profile/upload")
async def upload_resume(file: UploadFile = File(...), request: Request = None):
    """Uploads a resume file (PDF, TXT, MD, JSON) and triggers profile generation."""
    upload_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / file.filename
    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    generator = ProfileGenerator()
    profile = generator.generate_profile(resume_source=saved_path)

    if request:
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header and not ("application/json" in accept_header or "*/*" in accept_header):
            return HTMLResponse(content=render_upload_page(message=f"Successfully extracted profile from {file.filename}"))

    return {
        "status": "success",
        "message": f"Successfully parsed profile from {file.filename}",
        "profile": profile.model_dump()
    }

@app.get("/profile/edit", response_class=HTMLResponse)
async def get_edit_page():
    """Renders the HTML form for inspecting and editing the user profile."""
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    return HTMLResponse(content=render_edit_page(profile=profile))

@app.post("/profile/edit")
async def save_profile_edit(request: Request):
    """
    Saves profile updates submitted either via JSON (API/AJAX)
    or standard form submission from the edit HTML interface.
    """
    mgr = ProfileManager.get_instance()
    current_profile = mgr.load_profile()

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    else:
        form_data = await request.form()
        payload = dict(form_data)

    if not payload:
        raise HTTPException(status_code=400, detail="No profile data provided.")

    try:
        updated_profile = build_user_profile_from_dict(payload, existing_profile=current_profile)
        mgr.save_profile(updated_profile)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to validate profile data: {str(e)}")

    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header and not ("application/json" in accept_header or "*/*" in accept_header):
        return HTMLResponse(content=render_edit_page(profile=updated_profile, message="Profile successfully updated!"))

    return {
        "status": "success",
        "message": "Profile updated successfully",
        "profile": updated_profile.model_dump()
    }

async def _fetch_github_repositories(username: str) -> List[Dict[str, Any]]:
    """Helper to fetch public repositories for a given GitHub username."""
    headers = {
        "User-Agent": "Project-Kaalu-Agent",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=100"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to GitHub API: {str(exc)}"
        )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"GitHub user '{username}' not found.")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"GitHub API error: {resp.text}")

    data = resp.json()
    if not isinstance(data, list):
        return []

    repos = []
    for r in data:
        lang = r.get("language")
        topics = r.get("topics") or []
        techs = []
        if lang:
            techs.append(lang)
        for t in topics:
            if t not in techs:
                techs.append(t)

        repos.append({
            "name": r.get("name") or "Unnamed Repo",
            "description": r.get("description") or "",
            "url": r.get("html_url") or "",
            "stars": r.get("stargazers_count", 0),
            "language": lang,
            "technologies": techs,
            "fork": r.get("fork", False)
        })
    return repos

@app.get("/profile/github/repos")
async def get_github_repos(username: Optional[str] = Query(None)):
    """
    Fetch public repositories for a GitHub user.
    If username is omitted, extracts it from the existing user profile's GitHub URL.
    """
    if not username:
        mgr = ProfileManager.get_instance()
        profile = mgr.load_profile()
        if profile and profile.urls and profile.urls.github:
            m = re.search(r"github\.com/([a-zA-Z0-9_\-]+)", profile.urls.github)
            if m:
                username = m.group(1)

    if not username:
        raise HTTPException(
            status_code=400,
            detail="GitHub username not provided and not found in existing user profile."
        )

    repos = await _fetch_github_repositories(username)
    return {
        "status": "success",
        "username": username,
        "count": len(repos),
        "repositories": repos
    }

@app.post("/profile/github/import")
async def import_github_repos(payload: Optional[Dict[str, Any]] = None):
    """
    Imports GitHub repositories as projects into the user's profile.
    Accepts either an explicit list of repository dicts or fetches them
    using `username` or profile URL.
    """
    payload = payload or {}
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No user profile found. Please create one first.")

    repos_to_import = payload.get("repositories")
    username = payload.get("username")

    if not repos_to_import:
        if not username and profile.urls and profile.urls.github:
            m = re.search(r"github\.com/([a-zA-Z0-9_\-]+)", profile.urls.github)
            if m:
                username = m.group(1)

        if not username:
            raise HTTPException(
                status_code=400,
                detail="No repositories provided and no GitHub username found to fetch from."
            )

        repos_to_import = await _fetch_github_repositories(username)
        allowed_names = payload.get("repo_names")
        if allowed_names:
            allowed_set = {n.lower() for n in allowed_names}
            repos_to_import = [r for r in repos_to_import if r.get("name", "").lower() in allowed_set]

    existing_names = {p.name.strip().lower() for p in profile.projects}
    existing_urls = {p.url.strip().lower() for p in profile.projects if p.url}

    newly_added = []
    for item in repos_to_import:
        name = item.get("name", "").strip()
        url = item.get("url", "").strip() or item.get("html_url", "").strip()
        if not name:
            continue
        # Skip duplicates by name or URL
        if name.lower() in existing_names or (url and url.lower() in existing_urls):
            continue

        desc = item.get("description") or ""
        techs = item.get("technologies") or []
        if not techs and item.get("language"):
            techs = [item["language"]]

        proj = Project(
            name=name,
            description=desc,
            technologies=techs,
            url=url or None,
            highlights=[desc] if desc else [],
            stars=item.get("stars", 0) or item.get("stargazers_count", 0),
            language=item.get("language")
        )
        profile.projects.append(proj)
        existing_names.add(name.lower())
        if url:
            existing_urls.add(url.lower())
        newly_added.append(proj)

    if newly_added:
        mgr.save_profile(profile)

    return {
        "status": "success",
        "message": f"Successfully imported {len(newly_added)} project(s) from GitHub.",
        "imported_count": len(newly_added),
        "total_projects": len(profile.projects),
        "projects": [p.model_dump() for p in profile.projects]
    }

@app.delete("/profile/skills/category/{category_name}")
async def delete_skill_category(category_name: str):
    """
    Deletes a specific skill category by name (case-insensitive) from the user profile.
    Supports standard categories ('Soft Skills', 'Spoken Languages', etc.)
    and custom categories ('AI & LLMs', 'Cloud & DevOps', etc.).
    """
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No user profile found.")

    removed = profile.skills.remove_category(category_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Skill category '{category_name}' not found in profile.")

    mgr.save_profile(profile)
    return {
        "status": "success",
        "message": f"Successfully removed skill category '{category_name}'.",
        "remaining_categories": list(profile.skills.all_categories().keys()),
        "profile": profile.model_dump()
    }

@app.post("/profile/skills/category/remove")
async def remove_skill_category_via_post(payload: Dict[str, Any]):
    """Alternative POST endpoint to remove a skill category by name."""
    cat_name = payload.get("category_name") or payload.get("name")
    if not cat_name:
        raise HTTPException(status_code=400, detail="Missing 'category_name' in payload.")
    return await delete_skill_category(cat_name)

@app.post("/job/resume/save")
async def save_job_resume(payload: Dict[str, Any]):
    """
    Saves a generated/downloaded resume file into the structured date folder:
    data/resumes/YYYY-MM-DD/<Company>_<Position>_Resume_<timestamp>.pdf
    and automatically updates user_profile.json's resume_path.
    """
    company = payload.get("company")
    position = payload.get("position")
    if not company or not position:
        raise HTTPException(status_code=400, detail="Missing required fields: 'company' and 'position'.")

    source_path = payload.get("source_path")
    move = bool(payload.get("move", False))

    tracker = JobTrackerManager.get_instance()
    try:
        dest_path, dest_filename = tracker.save_downloaded_resume(
            company=company,
            position=position,
            source_path=source_path,
            move=move
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume: {str(e)}")

    return {
        "status": "success",
        "message": f"Resume successfully stored under date directory for {company} - {position}",
        "resume_path": str(dest_path),
        "resume_filename": dest_filename,
        "date_folder": dest_path.parent.name
    }

@app.post("/job/applied")
async def record_job_application(payload: Dict[str, Any]):
    """
    Records a job application or marks an existing one as applied,
    storing the target job metadata, applied date, and linking the exact resume file and snapshot.
    """
    tracker = JobTrackerManager.get_instance()

    identifier = payload.get("application_id") or payload.get("identifier")
    if identifier:
        rec = tracker.mark_as_applied(
            identifier=identifier,
            job_url=payload.get("job_url"),
            notes=payload.get("notes")
        )
        if rec:
            return {
                "status": "success",
                "message": f"Job application '{rec.company} - {rec.position}' marked as applied.",
                "application": rec.model_dump()
            }

    company = payload.get("company")
    position = payload.get("position")
    if not company or not position:
        raise HTTPException(status_code=400, detail="Missing required fields: 'company' and 'position'.")

    rec = tracker.record_job_application(
        company=company,
        position=position,
        job_description=payload.get("job_description"),
        job_url=payload.get("job_url"),
        location=payload.get("location"),
        resume_path=payload.get("resume_path"),
        resume_snapshot=payload.get("resume_snapshot"),
        status=payload.get("status", "applied"),
        applied_date=payload.get("applied_date"),
        notes=payload.get("notes"),
        metadata=payload.get("metadata")
    )
    return {
        "status": "success",
        "message": f"Job application recorded for {company} - {position}.",
        "application": rec.model_dump()
    }

@app.get("/job/applications")
async def list_job_applications(
    status: Optional[str] = Query(None),
    company: Optional[str] = Query(None)
):
    """Lists all tracked job applications with optional status and company filtering."""
    tracker = JobTrackerManager.get_instance()
    records = tracker.list_applications(status=status, company=company)
    return {
        "status": "success",
        "count": len(records),
        "applications": [r.model_dump() for r in records]
    }

@app.get("/job/applications/{application_id}")
async def get_job_application(application_id: str):
    """Retrieves a single job application record by application_id."""
    tracker = JobTrackerManager.get_instance()
    rec = tracker.get_application(application_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Job application '{application_id}' not found.")
    return {
        "status": "success",
        "application": rec.model_dump()
    }

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint where agents (Kaalu, Faulkner, David) register and communicate.
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            raw_data = await websocket.receive_json()
            if raw_data.get("action") == "ping":
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "pong",
                    "payload": {}
                })
                continue

            if raw_data.get("action") == "get_user_profile":
                mgr = ProfileManager.get_instance()
                profile = mgr.load_profile()
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "user_profile_data",
                    "payload": profile.model_dump() if profile else None
                })
                continue

            if raw_data.get("action") == "save_job_resume":
                payload = raw_data.get("payload", {})
                company = payload.get("company", "")
                position = payload.get("position", "")
                src_path = payload.get("source_path")
                tracker = JobTrackerManager.get_instance()
                try:
                    dest_p, dest_name = tracker.save_downloaded_resume(
                        company=company,
                        position=position,
                        source_path=src_path
                    )
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_resume_saved",
                        "payload": {
                            "status": "success",
                            "resume_path": str(dest_p),
                            "resume_filename": dest_name
                        }
                    })
                except Exception as save_err:
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_resume_saved",
                        "payload": {
                            "status": "error",
                            "error": str(save_err)
                        }
                    })
                continue

            if raw_data.get("action") == "record_job_application":
                payload = raw_data.get("payload", {})
                tracker = JobTrackerManager.get_instance()
                try:
                    rec = tracker.record_job_application(
                        company=payload.get("company", ""),
                        position=payload.get("position", ""),
                        job_description=payload.get("job_description"),
                        job_url=payload.get("job_url"),
                        location=payload.get("location"),
                        resume_path=payload.get("resume_path"),
                        resume_snapshot=payload.get("resume_snapshot"),
                        status=payload.get("status", "applied"),
                        notes=payload.get("notes"),
                        metadata=payload.get("metadata")
                    )
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_application_recorded",
                        "payload": {
                            "status": "success",
                            "application": rec.model_dump()
                        }
                    })
                except Exception as rec_err:
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_application_recorded",
                        "payload": {
                            "status": "error",
                            "error": str(rec_err)
                        }
                    })
                continue

            if raw_data.get("action") == "get_job_applications":
                payload = raw_data.get("payload", {})
                tracker = JobTrackerManager.get_instance()
                apps = tracker.list_applications(
                    status=payload.get("status"),
                    company=payload.get("company")
                )
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "job_applications_data",
                    "payload": {
                        "status": "success",
                        "count": len(apps),
                        "applications": [a.model_dump() for a in apps]
                    }
                })
                continue

            try:
                message = AgentMessage(**raw_data)
                await manager.route_message(client_id, message.model_dump())
            except Exception as validation_error:
                await websocket.send_json({
                    "sender": "rgs_hub",
                    "status": "error",
                    "error": f"Invalid message schema: {str(validation_error)}"
                })
    except WebSocketDisconnect:
        manager.disconnect(client_id)