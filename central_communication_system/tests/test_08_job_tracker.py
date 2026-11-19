import io
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from job_tracker.schemas import JobApplicationRecord, ResumeSnapshot
from job_tracker.manager import JobTrackerManager, sanitize_filename
from user_profile.schemas import UserProfile, BasicDetails, UserURLs, Skills
from user_profile.profile_manager import ProfileManager
from kaalu_orchestrator.prompts import KAALU_SYSTEM_PROMPT
from kaalu_orchestrator.core_agent import KaaluOrchestrator
from rgs_hub.main import app


@pytest.fixture
def temp_tracker_env(tmp_path):
    """Sets up an isolated directory structure for JobTrackerManager and ProfileManager."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    profile_path = data_dir / "user_profile.json"
    apps_file = data_dir / "job_applications.json"

    # Seed an initial user profile
    initial_profile = UserProfile(
        basic_details=BasicDetails(
            name="Rohit Singh",
            email="rsingh.py@gmail.com",
            headline="Full Stack AI & Python Engineer",
            summary="Experienced in multi-agent autonomous architectures.",
            location="Dehradun, India"
        ),
        urls=UserURLs(
            github="https://github.com/rsingh",
            linkedin="https://linkedin.com/in/rsingh"
        ),
        skills=Skills(technical=["Python", "FastAPI", "PyTorch", "TypeScript"]),
        resume_path=None
    )
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(initial_profile.model_dump(), f, indent=2)

    profile_mgr = ProfileManager(profile_path=profile_path)
    tracker_mgr = JobTrackerManager(
        data_dir=data_dir,
        applications_file=apps_file,
        profile_manager=profile_mgr
    )

    return {
        "tmp_path": tmp_path,
        "data_dir": data_dir,
        "profile_path": profile_path,
        "apps_file": apps_file,
        "profile_mgr": profile_mgr,
        "tracker_mgr": tracker_mgr
    }


def test_sanitize_filename():
    """Verify filename sanitization removes illegal characters and cleans whitespace."""
    raw = 'Stripe / Payments: Senior Eng <v2>*?"|'
    clean = sanitize_filename(raw)
    assert "/" not in clean
    assert "\\" not in clean
    assert ":" not in clean
    assert "*" not in clean
    assert "?" not in clean
    assert '"' not in clean
    assert "<" not in clean
    assert ">" not in clean
    assert "|" not in clean
    assert " " not in clean
    assert "Stripe" in clean
    assert "Payments" in clean


def test_date_directory_creation(temp_tracker_env):
    """Verify date-structured resume and application folders are properly created."""
    mgr = temp_tracker_env["tracker_mgr"]
    now = datetime.now()
    expected_date = now.strftime("%Y-%m-%d")

    res_dir = mgr.get_date_resume_dir(now)
    assert res_dir.exists()
    assert res_dir.is_dir()
    assert res_dir.name == expected_date
    assert res_dir.parent.name == "resumes"

    app_dir = mgr.get_date_application_dir(now)
    assert app_dir.exists()
    assert app_dir.is_dir()
    assert app_dir.name == expected_date
    assert app_dir.parent.name == "applications"


def test_find_latest_download(temp_tracker_env):
    """Verify scanning Downloads directory picks the newest valid resume file."""
    mgr = temp_tracker_env["tracker_mgr"]
    mock_downloads = temp_tracker_env["tmp_path"] / "Downloads"
    mock_downloads.mkdir()

    # Empty dir returns None
    assert mgr.find_latest_download(search_dir=mock_downloads) is None

    # Create an old PDF and a newer DOCX
    old_pdf = mock_downloads / "old_resume.pdf"
    old_pdf.write_text("old content")
    past_time = (datetime.now() - timedelta(seconds=100)).timestamp()
    os.utime(old_pdf, (past_time, past_time))

    new_docx = mock_downloads / "Rohit_Singh_Tailored_Resume.docx"
    new_docx.write_text("new content")

    # Should find the newest file
    found = mgr.find_latest_download(search_dir=mock_downloads, max_age_seconds=300)
    assert found is not None
    assert found.name == "Rohit_Singh_Tailored_Resume.docx"


def test_save_downloaded_resume_and_sync_profile(temp_tracker_env):
    """
    Verify save_downloaded_resume copies the file to data/resumes/YYYY-MM-DD/,
    names it cleanly, and updates resume_path in user_profile.json.
    """
    mgr = temp_tracker_env["tracker_mgr"]
    profile_mgr = temp_tracker_env["profile_mgr"]

    # Create dummy source file
    src_file = temp_tracker_env["tmp_path"] / "downloaded_test_resume.pdf"
    src_file.write_text("%PDF-1.4 Mock PDF content")

    dest_path, dest_filename = mgr.save_downloaded_resume(
        company="Google DeepMind",
        position="Senior AI Research Engineer",
        source_path=src_file,
        move=False
    )

    assert dest_path.exists()
    assert dest_path.is_file()
    assert "Google_DeepMind" in dest_filename
    assert "Senior_AI_Research_Engineer" in dest_filename
    assert dest_filename.endswith(".pdf")
    assert dest_path.parent.name == datetime.now().strftime("%Y-%m-%d")

    # Verify user_profile.json was updated with this exact resume path
    updated_profile = profile_mgr.load_profile()
    assert updated_profile.resume_path == str(dest_path)


def test_record_and_mark_job_application(temp_tracker_env):
    """
    Verify recording a job application persists to central job_applications.json
    and individual snapshot file, and marking as applied updates status and applied_date.
    """
    mgr = temp_tracker_env["tracker_mgr"]

    snapshot = ResumeSnapshot(
        template="Modern Professional",
        headline="Senior AI Systems Engineer",
        summary="Specialized in autonomous multi-agent coordination.",
        skills=["Python", "FastAPI", "PyTorch"],
        projects=["Project Kaalu Multi-Agent System"],
        custom_highlights=["Engineered real-time low-latency voice pipeline"]
    )

    rec = mgr.record_job_application(
        company="Anthropic",
        position="Staff Infrastructure Engineer",
        job_description="Seeking a lead backend architect to scale distributed inference systems.",
        job_url="https://anthropic.com/careers/backend-eng",
        location="San Francisco, CA / Remote",
        resume_path="/path/to/resume.pdf",
        resume_snapshot=snapshot,
        status="generated",
        notes="Applied via referral."
    )

    assert rec.company == "Anthropic"
    assert rec.position == "Staff Infrastructure Engineer"
    assert rec.status == "generated"
    assert rec.applied_date is None
    assert rec.resume_snapshot.template == "Modern Professional"

    # Check persistence in job_applications.json
    apps = mgr.list_applications()
    assert len(apps) == 1
    assert apps[0].application_id == rec.application_id

    # Check individual date-snapshot file
    date_app_dir = mgr.get_date_application_dir()
    snap_file = date_app_dir / f"{rec.application_id}.json"
    assert snap_file.exists()

    # Now mark as applied
    applied_rec = mgr.mark_as_applied(
        identifier=rec.application_id,
        notes="Interview invitation received."
    )
    assert applied_rec is not None
    assert applied_rec.status == "applied"
    assert applied_rec.applied_date is not None
    assert "Interview invitation received." in applied_rec.notes

    # Verify listing filters
    filtered_applied = mgr.list_applications(status="applied")
    assert len(filtered_applied) == 1
    filtered_rejected = mgr.list_applications(status="rejected")
    assert len(filtered_rejected) == 0
    filtered_company = mgr.list_applications(company="Anthropic")
    assert len(filtered_company) == 1

    # Verify get_application and get_latest_application
    fetched = mgr.get_application(rec.application_id)
    assert fetched is not None
    assert fetched.company == "Anthropic"

    latest = mgr.get_latest_application()
    assert latest is not None
    assert latest.application_id == rec.application_id


def test_api_save_resume_endpoint(temp_tracker_env):
    """Test POST /job/resume/save endpoint via FastAPI TestClient."""
    tracker_mgr = temp_tracker_env["tracker_mgr"]
    profile_mgr = temp_tracker_env["profile_mgr"]

    # Patch get_instance in rgs_hub to use our test manager
    with patch("rgs_hub.main.JobTrackerManager.get_instance", return_value=tracker_mgr), \
         patch("rgs_hub.main.ProfileManager.get_instance", return_value=profile_mgr):
        client = TestClient(app)

        # 1. Validation failure on missing fields
        bad_resp = client.post("/job/resume/save", json={"company": "Meta"})
        assert bad_resp.status_code == 400

        # 2. File not found
        missing_resp = client.post("/job/resume/save", json={
            "company": "Meta",
            "position": "Research Scientist",
            "source_path": "c:/nonexistent_file_xyz.pdf"
        })
        assert missing_resp.status_code == 404

        # 3. Successful save
        dummy_file = temp_tracker_env["tmp_path"] / "meta_resume.pdf"
        dummy_file.write_text("%PDF-1.4 Mock Meta Resume")

        good_resp = client.post("/job/resume/save", json={
            "company": "Meta",
            "position": "Research Scientist",
            "source_path": str(dummy_file)
        })
        assert good_resp.status_code == 200
        data = good_resp.json()
        assert data["status"] == "success"
        assert "Meta_Research_Scientist" in data["resume_filename"]
        assert os.path.exists(data["resume_path"])

        # Check profile synchronization
        loaded_prof = profile_mgr.load_profile()
        assert loaded_prof.resume_path == data["resume_path"]


def test_api_applied_and_applications_endpoints(temp_tracker_env):
    """Test POST /job/applied, GET /job/applications, and GET /job/applications/{id} endpoints."""
    tracker_mgr = temp_tracker_env["tracker_mgr"]
    profile_mgr = temp_tracker_env["profile_mgr"]

    with patch("rgs_hub.main.JobTrackerManager.get_instance", return_value=tracker_mgr), \
         patch("rgs_hub.main.ProfileManager.get_instance", return_value=profile_mgr):
        client = TestClient(app)

        # 1. Record application
        payload = {
            "company": "OpenAI",
            "position": "Systems Research Engineer",
            "job_description": "Building next-generation distributed training infrastructure.",
            "job_url": "https://openai.com/careers/systems",
            "location": "San Francisco, CA",
            "status": "applied",
            "resume_path": "/data/resumes/2026-11-19/OpenAI_Resume.pdf",
            "resume_snapshot": {
                "template": "Technical",
                "headline": "Lead Systems Architect",
                "skills": ["Python", "CUDA", "C++", "PyTorch"]
            }
        }
        resp = client.post("/job/applied", json=payload)
        assert resp.status_code == 200
        app_data = resp.json()["application"]
        app_id = app_data["application_id"]
        assert app_data["company"] == "OpenAI"
        assert app_data["status"] == "applied"
        assert app_data["resume_snapshot"]["template"] == "Technical"

        # 2. List applications
        list_resp = client.get("/job/applications")
        assert list_resp.status_code == 200
        all_apps = list_resp.json()
        assert all_apps["count"] >= 1
        assert any(a["application_id"] == app_id for a in all_apps["applications"])

        # 3. Filter applications by company
        filtered_resp = client.get("/job/applications?company=OpenAI")
        assert filtered_resp.status_code == 200
        assert len(filtered_resp.json()["applications"]) == 1

        # 4. Get specific application by ID
        get_resp = client.get(f"/job/applications/{app_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["application"]["position"] == "Systems Research Engineer"

        # 5. Get 404 for unknown ID
        not_found_resp = client.get("/job/applications/job_nonexistent_9999")
        assert not_found_resp.status_code == 404

        # 6. Mark existing application as applied using identifier
        mark_resp = client.post("/job/applied", json={
            "application_id": app_id,
            "notes": "Followed up with recruiter."
        })
        assert mark_resp.status_code == 200
        assert "Followed up with recruiter." in mark_resp.json()["application"]["notes"]


def test_kaalu_prompt_has_resume_builder_and_tracker_instructions():
    """Verify that KAALU_SYSTEM_PROMPT includes all Resume Builder and Job Tracker rules."""
    assert "http://localhost:5173/" in KAALU_SYSTEM_PROMPT
    assert "Resume Builder" in KAALU_SYSTEM_PROMPT
    assert "Generate Tailored Resume" in KAALU_SYSTEM_PROMPT
    # Verify strict generation vs download separation
    assert "STRICT PHASE SEPARATION" in KAALU_SYSTEM_PROMPT
    assert "NEVER automatically click" in KAALU_SYSTEM_PROMPT
    # Verify explicit download command requirement
    assert "ONLY download the resume file when the user explicitly commands to download it" in KAALU_SYSTEM_PROMPT
    # Verify date-structured storage rule
    assert "data/resumes/YYYY-MM-DD" in KAALU_SYSTEM_PROMPT
    assert "resume_path" in KAALU_SYSTEM_PROMPT
    # Verify job application tracking rule
    assert "job_applications.json" in KAALU_SYSTEM_PROMPT


def test_kaalu_orchestrator_job_tracker_methods(temp_tracker_env):
    """Verify KaaluOrchestrator helper methods interact cleanly with JobTrackerManager."""
    tracker_mgr = temp_tracker_env["tracker_mgr"]
    profile_mgr = temp_tracker_env["profile_mgr"]

    orchestrator = KaaluOrchestrator(
        profile_manager=profile_mgr,
        job_tracker=tracker_mgr
    )

    # 1. Test save_downloaded_resume
    src = temp_tracker_env["tmp_path"] / "local_download.pdf"
    src.write_text("%PDF-1.4 Kaalu Resume")

    res = orchestrator.save_downloaded_resume(
        company="NVIDIA",
        position="Senior Autonomous Systems Architect",
        source_path=str(src)
    )
    assert res is not None
    assert res["status"] == "success"
    assert "NVIDIA" in res["resume_filename"]
    assert profile_mgr.load_profile().resume_path == res["resume_path"]

    # 2. Test record_applied_job
    app_rec = orchestrator.record_applied_job(
        company="NVIDIA",
        position="Senior Autonomous Systems Architect",
        job_description="Architecting end-to-end robotics and agent communication stacks.",
        job_url="https://nvidia.com/careers/agent-architect",
        resume_path=res["resume_path"],
        notes="Submitted via David browser automation."
    )
    assert app_rec is not None
    assert app_rec["company"] == "NVIDIA"
    assert app_rec["status"] == "applied"

    # 3. Test mark_job_applied
    marked = orchestrator.mark_job_applied(
        identifier=app_rec["application_id"],
        notes="Completed online coding round."
    )
    assert marked is not None
    assert "Completed online coding round." in marked["notes"]


def test_job_tracker_to_prompt_context(temp_tracker_env):
    """Verify to_prompt_context produces structured context for Kaalu's LLM reasoning."""
    mgr = temp_tracker_env["tracker_mgr"]
    assert mgr.to_prompt_context() == ""

    # Add 2 applications
    mgr.record_job_application(
        company="Stripe",
        position="Backend Engineer",
        job_description="Scaling global payment systems using Python and distributed queues.",
        location="Seattle, WA",
        status="applied",
        notes="Referral from team lead.",
        resume_snapshot=ResumeSnapshot(
            template="Technical",
            skills=["Python", "FastAPI", "Distributed Systems"]
        )
    )
    mgr.record_job_application(
        company="Google",
        position="AI Research Scientist",
        job_description="Large scale LLM alignment and agent architectures.",
        status="applied",
        notes="Applied via careers portal."
    )

    ctx = mgr.to_prompt_context()
    assert "[TRACKED JOB APPLICATIONS DATABASE (Total: 2)]" in ctx
    assert "Stripe" in ctx
    assert "Backend Engineer" in ctx
    assert "Google" in ctx
    assert "AI Research Scientist" in ctx
    assert "Referral from team lead." in ctx
    assert "Technical" in ctx


@pytest.mark.asyncio
async def test_kaalu_responds_to_applied_jobs(temp_tracker_env):
    """Verify Kaalu injects tracked applied jobs and responds with full context of applied jobs."""
    tracker_mgr = temp_tracker_env["tracker_mgr"]
    profile_mgr = temp_tracker_env["profile_mgr"]

    # Seed an applied job
    tracker_mgr.record_job_application(
        company="Stripe",
        position="Senior Backend Engineer",
        job_description="Distributed payment systems in Python.",
        job_url="https://stripe.com/jobs/123",
        status="applied",
        notes="Applied via referral."
    )

    orchestrator = KaaluOrchestrator(
        profile_manager=profile_mgr,
        job_tracker=tracker_mgr
    )

    # Mock the LLM client to inspect the messages sent to it
    captured_messages = []

    async def mock_generate_async(messages, **kwargs):
        captured_messages.extend(messages)
        return json.dumps({
            "thought": "The user is asking about their applied jobs. I can see Stripe in my tracked applications database.",
            "action": "finish",
            "final_answer": "You have applied to Stripe for Senior Backend Engineer on " + datetime.now().strftime("%Y-%m-%d") + ". Status: APPLIED.",
            "voice_response": "You have one active application for Senior Backend Engineer at Stripe."
        })

    orchestrator.llm_client.generate_async = AsyncMock(side_effect=mock_generate_async)
    orchestrator.ws_client.connect_server = AsyncMock()

    result = await orchestrator.process_user_goal("What jobs have I applied to?")

    assert result["status"] == "completed"
    assert "Stripe" in result["final_answer"]
    assert "Stripe" in result["voice_response"]

    # Verify that the tracked job applications were injected into the LLM system prompt context
    system_contents = [m["content"] for m in captured_messages if m["role"] == "system"]
    assert any("Current Verified Tracked Job Applications & Resumes" in sc for sc in system_contents)
    assert any("Stripe" in sc for sc in system_contents)


@pytest.mark.asyncio
async def test_kaalu_delegate_to_job_tracker(temp_tracker_env):
    """Verify Kaalu can delegate task actions directly to job_tracker."""
    tracker_mgr = temp_tracker_env["tracker_mgr"]
    profile_mgr = temp_tracker_env["profile_mgr"]

    orchestrator = KaaluOrchestrator(
        profile_manager=profile_mgr,
        job_tracker=tracker_mgr
    )

    call_count = 0

    async def mock_generate_async(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return json.dumps({
                "thought": "I need to record the user's application to Apple.",
                "action": "delegate",
                "recipient": "job_tracker",
                "task_action": "record_application",
                "payload": {
                    "company": "Apple",
                    "position": "CoreOS Software Engineer",
                    "status": "applied",
                    "notes": "Direct referral"
                }
            })
        else:
            return json.dumps({
                "thought": "Apple application is recorded.",
                "action": "finish",
                "final_answer": "Your application to Apple for CoreOS Software Engineer has been recorded.",
                "voice_response": "Your application to Apple has been recorded."
            })

    orchestrator.llm_client.generate_async = AsyncMock(side_effect=mock_generate_async)
    orchestrator.ws_client.connect_server = AsyncMock()

    result = await orchestrator.process_user_goal("Record that I applied to Apple for CoreOS Software Engineer.")

    assert result["status"] == "completed"
    assert "Apple" in result["final_answer"]

    # Verify Apple was recorded in tracker_mgr
    apps = tracker_mgr.list_applications(company="Apple")
    assert len(apps) == 1
    assert apps[0].position == "CoreOS Software Engineer"

