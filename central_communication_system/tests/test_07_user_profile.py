import io
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from user_profile.schemas import (
    BasicDetails,
    Certification,
    Education,
    Experience,
    Skills,
    UserProfile,
    UserURLs,
)
from user_profile.profile_manager import ProfileManager
from user_profile.generator import ProfileGenerator
from rgs_hub.main import app
from kaalu_orchestrator.core_agent import KaaluOrchestrator
from kaalu_orchestrator.prompts import KAALU_SYSTEM_PROMPT


@pytest.fixture
def sample_user_profile():
    return UserProfile(
        basic_details=BasicDetails(
            name="Alex Mercer",
            email="alex.mercer@example.com",
            phone="+1 555-0199",
            location="San Francisco, CA",
            headline="Senior Python & AI Engineer",
            summary="Passionate AI systems architect with 5+ years building distributed LLM applications."
        ),
        urls=UserURLs(
            linkedin="https://linkedin.com/in/alex-mercer",
            github="https://github.com/alex-mercer",
            portfolio="https://alexmercer.ai"
        ),
        skills=Skills(
            technical=["Python", "C++", "SQL", "TypeScript"],
            frameworks_and_tools=["PyTorch", "FastAPI", "Docker", "Kubernetes", "ONNX"],
            soft_skills=["Architecture Design", "Team Mentorship"],
            languages=["English"]
        ),
        experiences=[
            Experience(
                company="NeuralSync Labs",
                role="Senior AI Engineer",
                location="San Francisco, CA",
                start_date="Jan 2022",
                end_date="Present",
                current=True,
                description="Lead architect for multi-agent autonomous orchestration platform.",
                highlights=["Reduced latency by 45%", "Scaled microservices to 10M daily requests"]
            ),
            Experience(
                company="DataStream Corp",
                role="Backend Developer",
                location="Remote",
                start_date="Jun 2019",
                end_date="Dec 2021",
                current=False,
                description="Built high-throughput data processing pipelines using Python and Kafka."
            )
        ],
        educations=[
            Education(
                degree="B.S. in Computer Science",
                institution="UC Berkeley",
                field_of_study="Computer Science",
                start_year="2015",
                end_year="2019",
                grade="3.9 GPA"
            )
        ],
        certifications=[
            Certification(
                name="AWS Certified Solutions Architect",
                issuer="Amazon Web Services",
                issue_date="2023"
            )
        ],
        resume_path="/path/to/resume.pdf"
    )


def test_user_profile_schemas(sample_user_profile):
    """Verify serialization, prompt formatting, form fill map, and job query generation."""
    # 1. Prompt context verification
    context = sample_user_profile.to_prompt_context()
    assert "[VERIFIED USER PROFILE]" in context
    assert "Alex Mercer" in context
    assert "Senior Python & AI Engineer" in context
    assert "alex.mercer@example.com" in context
    assert "https://linkedin.com/in/alex-mercer" in context
    assert "Python" in context
    assert "NeuralSync Labs" in context
    assert "UC Berkeley" in context

    # 2. Form fill map verification
    form_map = sample_user_profile.get_form_fill_map()
    assert form_map["first_name"] == "Alex"
    assert form_map["last_name"] == "Mercer"
    assert form_map["email"] == "alex.mercer@example.com"
    assert form_map["phone"] == "+1 555-0199"
    assert form_map["linkedin"] == "https://linkedin.com/in/alex-mercer"
    assert form_map["github"] == "https://github.com/alex-mercer"
    assert form_map["company"] == "NeuralSync Labs"
    assert form_map["role"] == "Senior AI Engineer"
    assert form_map["school"] == "UC Berkeley"
    assert form_map["degree"] == "B.S. in Computer Science"

    # 3. Target job queries generation
    queries = sample_user_profile.get_target_job_queries()
    assert len(queries) >= 2
    assert any("Senior Python & AI Engineer" in q for q in queries)
    assert any("Python" in q for q in queries)


def test_profile_manager_lifecycle(tmp_path, sample_user_profile):
    """Verify ProfileManager CRUD operations, caching, and semantic field resolution."""
    prof_file = tmp_path / "user_profile.json"
    mgr = ProfileManager(profile_path=prof_file)

    assert not mgr.has_profile()
    assert mgr.load_profile() is None

    # Save profile
    mgr.save_profile(sample_user_profile)
    assert mgr.has_profile()
    assert prof_file.exists()

    # Load profile
    loaded = mgr.load_profile()
    assert loaded is not None
    assert loaded.basic_details.name == "Alex Mercer"
    assert loaded.basic_details.email == "alex.mercer@example.com"

    # Semantic form field matching
    assert mgr.match_form_field("Candidate Full Name") == "Alex Mercer"
    assert mgr.match_form_field("First Name") == "Alex"
    assert mgr.match_form_field("Last Name") == "Mercer"
    assert mgr.match_form_field("Email Address") == "alex.mercer@example.com"
    assert mgr.match_form_field("Primary Phone / Mobile") == "+1 555-0199"
    assert mgr.match_form_field("LinkedIn Profile URL") == "https://linkedin.com/in/alex-mercer"
    assert mgr.match_form_field("GitHub Repository") == "https://github.com/alex-mercer"
    assert mgr.match_form_field("Current Employer / Company") == "NeuralSync Labs"
    assert mgr.match_form_field("Job Title / Role") == "Senior AI Engineer"
    assert mgr.match_form_field("College / University Attended") == "UC Berkeley"
    assert mgr.match_form_field("Degree Qualification") == "B.S. in Computer Science"
    assert mgr.match_form_field("Unknown Nonexistent Field 12345") is None


def test_profile_generator_rule_based(tmp_path):
    """Verify rule-based resume parsing when LLM is offline."""
    resume_text = """
    Jane Smith
    Senior Full Stack Developer
    San Francisco, CA | jane.smith@techdev.io | (415) 555-8822
    linkedin.com/in/janesmithdev | github.com/janesmith-code | janesmith.dev

    Summary:
    Accomplished software engineer with extensive background building modern web apps.

    Technical Skills:
    Python, JavaScript, TypeScript, SQL, HTML, CSS
    FastAPI, React, Docker, Kubernetes, PostgreSQL, Git, Redis

    Education:
    Bachelor of Science in Computer Science - Stanford University

    Experience:
    Tech Innovators LLC
    Lead Full Stack Engineer
    - Designed real-time collaboration engines
    - Scaled backend architecture to millions of users
    """
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text(resume_text, encoding="utf-8")

    out_file = tmp_path / "out_profile.json"
    gen = ProfileGenerator()
    profile = gen.generate_profile(resume_source=resume_file, output_path=out_file)

    assert profile.basic_details.name == "Jane Smith"
    assert profile.basic_details.email == "jane.smith@techdev.io"
    assert "415" in profile.basic_details.phone
    assert "linkedin.com/in/janesmithdev" in (profile.urls.linkedin or "")
    assert "github.com/janesmith-code" in (profile.urls.github or "")
    assert "Python" in profile.skills.technical
    assert "FastAPI" in profile.skills.frameworks_and_tools
    assert len(profile.educations) > 0
    assert out_file.exists()


def test_parse_full_resume_details(tmp_path):
    """Verify that section-aware parsing extracts complete work experiences, skills, projects, and certifications."""
    resume_text = """
    Rohit Singh
    +91-7409210904 | rsingh.py@gmail.com | linkedin.com/in/rohiyaa | github.com/RohitSingh-04 | Portfolio

    Professional Summary
    AI Engineer with a strong foundation in Python, NLP, and Agentic AI architectures.
    Experienced in building autonomous workflows, integrating LLMs with external tools, and deploying cloud pipelines.

    Experience
    Deloitte Sept 2025 – July 2026
    Associate Analyst Bengaluru, India
    – Engineered Python data processing pipelines to preprocess and analyze large-scale datasets.
    – Developed automated backend scripts and custom workflows using Python and Playwright.
    Infosys Springboard Nov 2024 – Jan 2025
    Intern Remote
    – Built and deployed scalable Python backend services and REST APIs.

    Skills
    AI & LLMs: Agentic AI, LangChain, Prompt Engineering, Local LLMs (Ollama)
    Languages & ML: Python, SQL, C/C++, Java, JavaScript, PyTorch
    Cloud & DevOps: AWS EC2, Docker, Linux, FastAPI, Git
    Soft Skills: Agile, Problem Solving, Communication

    Projects
    AML OSDD Helper | Python, LangChain, FastAPI GitHub
    – Designed agent-based architecture for risk assessment.
    Musivan | Django, PostgreSQL, Docker Live Project
    – Engineered backend architecture and deployed with Docker.

    Education
    Graphic Era Hill University 2025 – 2027
    Master of Computer Applications (MCA) Ongoing
    Graphic Era Hill University 2022 – 2025
    Bachelor of Computer Applications (BCA) – CGPA: 8.9/10

    Certifications
    • Django Complete Course – Udemy (2026)
    • Project Management – IIT Roorkee, NPTEL (2024)
    """
    resume_file = tmp_path / "detailed_resume.txt"
    resume_file.write_text(resume_text, encoding="utf-8")

    out_file = tmp_path / "detailed_profile.json"
    gen = ProfileGenerator()
    with patch.object(ProfileGenerator, "parse_with_llm", return_value=None):
        profile = gen.generate_profile(resume_source=resume_file, output_path=out_file)

    assert profile.basic_details.name == "Rohit Singh"
    assert profile.basic_details.email == "rsingh.py@gmail.com"
    assert profile.basic_details.phone == "+91-7409210904"
    assert profile.basic_details.headline == "AI Engineer"
    assert "AI Engineer with a strong foundation" in profile.basic_details.summary

    # URLs
    assert profile.urls.linkedin == "https://linkedin.com/in/rohiyaa"
    assert profile.urls.github == "https://github.com/RohitSingh-04"

    # Experiences
    assert len(profile.experiences) == 2
    deloitte = profile.experiences[0]
    assert deloitte.company == "Deloitte"
    assert deloitte.role == "Associate Analyst"
    assert deloitte.location == "Bengaluru, India"
    assert deloitte.start_date == "Sept 2025"
    assert deloitte.end_date == "July 2026"
    assert len(deloitte.highlights) == 2

    infosys = profile.experiences[1]
    assert infosys.company == "Infosys Springboard"
    assert infosys.role == "Intern"
    assert infosys.location == "Remote"
    assert infosys.start_date == "Nov 2024"
    assert infosys.end_date == "Jan 2025"

    # Skills
    assert "Agentic AI" in profile.skills.technical
    assert "Python" in profile.skills.technical
    assert "AWS EC2" in profile.skills.frameworks_and_tools
    assert "FastAPI" in profile.skills.frameworks_and_tools
    assert "Problem Solving" in profile.skills.soft_skills

    # Projects
    assert len(profile.projects) == 2
    assert "AML OSDD Helper" in profile.projects[0].name
    assert "LangChain" in profile.projects[0].technologies

    # Education
    assert len(profile.educations) == 2
    assert "MCA" in profile.educations[0].degree
    assert profile.educations[0].institution == "Graphic Era Hill University"
    assert "BCA" in profile.educations[1].degree
    assert profile.educations[1].grade == "CGPA: 8.9/10"

    # Certifications
    assert len(profile.certifications) == 2
    assert "Django Complete Course" in profile.certifications[0].name
    assert profile.certifications[0].issuer == "Udemy"
    assert profile.certifications[0].issue_date == "2026"
    assert "Project Management" in profile.certifications[1].name
    assert "IIT Roorkee" in profile.certifications[1].issuer


def test_profile_generator_pdf(tmp_path):
    """Verify PDF extraction and parsing."""
    minimal_pdf_bytes = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 78 >> stream
BT /F1 12 Tf 72 712 Td (Robert Taylor AI Engineer robert.taylor@example.com) Tj ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000373 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
447
%%EOF
"""
    pdf_path = tmp_path / "sample_resume.pdf"
    pdf_path.write_bytes(minimal_pdf_bytes)

    extracted = ProfileGenerator.extract_text_from_pdf(pdf_path)
    assert "Robert Taylor" in extracted
    assert "robert.taylor@example.com" in extracted

    out_file = tmp_path / "pdf_profile.json"
    gen = ProfileGenerator()
    profile = gen.generate_profile(resume_source=pdf_path, output_path=out_file)
    assert "robert.taylor@example.com" in profile.basic_details.email


def test_profile_generator_llm_parsing():
    """Verify that ProfileGenerator parses structured JSON returned by LLM Gateway."""
    mock_llm_json = {
        "basic_details": {
            "name": "Sarah Connor",
            "email": "sarah@resistance.ai",
            "phone": "+1 800-555-0100",
            "location": "Los Angeles, CA",
            "headline": "Lead Autonomous Systems Engineer",
            "summary": "Specialist in cybernetic AI agents and robust distributed systems."
        },
        "urls": {
            "linkedin": "https://linkedin.com/in/sarah-connor",
            "github": "https://github.com/sarah-connor",
            "portfolio": "https://sarahconnor.ai"
        },
        "skills": {
            "technical": ["Python", "Rust", "C++"],
            "frameworks_and_tools": ["PyTorch", "ROS2", "Docker"],
            "soft_skills": ["Tactical Leadership"],
            "languages": ["English"]
        },
        "experiences": [
            {
                "company": "Cyberdyne Systems",
                "role": "Security Systems Engineer",
                "location": "Sunnyvale, CA",
                "start_date": "2020",
                "end_date": "Present",
                "current": True,
                "description": "Architected tamper-proof autonomous agent security.",
                "highlights": ["Hardened multi-agent communications"]
            }
        ],
        "educations": [
            {
                "degree": "B.S. in Systems Engineering",
                "institution": "Caltech",
                "start_year": "2016",
                "end_year": "2020"
            }
        ],
        "certifications": []
    }

    gen = ProfileGenerator()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": json.dumps(mock_llm_json)}

    with patch("httpx.Client.post", return_value=mock_resp):
        parsed = gen.parse_with_llm("Resume of Sarah Connor...")
        assert parsed is not None
        assert parsed["basic_details"]["name"] == "Sarah Connor"
        assert parsed["basic_details"]["headline"] == "Lead Autonomous Systems Engineer"


def test_rgs_hub_profile_endpoints(tmp_path, sample_user_profile):
    """Test FastAPI RGS Hub GET /profile and POST /profile/upload endpoints."""
    prof_file = tmp_path / "test_user_profile.json"
    mock_mgr = ProfileManager(profile_path=prof_file)

    with patch.object(ProfileManager, "get_instance", return_value=mock_mgr), \
         patch.object(ProfileGenerator, "parse_with_llm", return_value=None):
        client = TestClient(app)

        # 1. GET /profile before profile exists -> 404
        r404 = client.get("/profile")
        assert r404.status_code == 404

        # 2. POST /profile/upload with resume text file -> 200
        resume_content = (
            "Morgan Freeman\nVoice & Audio Engineer\nmorgan@audioai.com\n"
            "Skills: Python, PyTorch, Librosa, FastSpeech\n"
            "Education: MIT B.S. Acoustics"
        )
        files = {"file": ("morgan_resume.txt", io.BytesIO(resume_content.encode("utf-8")), "text/plain")}
        upload_resp = client.post("/profile/upload", files=files)
        assert upload_resp.status_code == 200
        data = upload_resp.json()
        assert data["status"] == "success"
        assert data["profile"]["basic_details"]["email"] == "morgan@audioai.com"

        # 3. GET /profile now returns 200
        r200 = client.get("/profile")
        assert r200.status_code == 200
        assert r200.json()["basic_details"]["email"] == "morgan@audioai.com"

        # 4. GET /profile/upload returns HTML upload form
        r_upload_form = client.get("/profile/upload")
        assert r_upload_form.status_code == 200
        assert "text/html" in r_upload_form.headers.get("content-type", "")
        assert "Upload Candidate Resume" in r_upload_form.text
        assert 'input type="file"' in r_upload_form.text

        # 5. GET /profile/edit returns HTML edit form with prefilled values
        r_edit_form = client.get("/profile/edit")
        assert r_edit_form.status_code == 200
        assert "text/html" in r_edit_form.headers.get("content-type", "")
        assert "Edit User Profile" in r_edit_form.text
        assert "morgan@audioai.com" in r_edit_form.text

        # 6. POST /profile/edit updates data via JSON
        edit_payload = {
            "name": "Morgan Freeman (Updated)",
            "headline": "Lead Voice & Audio Architect",
            "email": "morgan.architect@audioai.com",
            "phone": "+1 555-0199",
            "technical_skills": "Python, C++, ONNX, PyTorch",
            "frameworks_and_tools": "FastAPI, Docker, TensorRT"
        }
        r_post_edit = client.post("/profile/edit", json=edit_payload)
        assert r_post_edit.status_code == 200
        edit_data = r_post_edit.json()
        assert edit_data["status"] == "success"
        assert edit_data["profile"]["basic_details"]["name"] == "Morgan Freeman (Updated)"
        assert edit_data["profile"]["basic_details"]["email"] == "morgan.architect@audioai.com"
        assert "ONNX" in edit_data["profile"]["skills"]["technical"]

        # Verify profile was persisted
        updated_in_mgr = mock_mgr.load_profile()
        assert updated_in_mgr.basic_details.name == "Morgan Freeman (Updated)"
        assert updated_in_mgr.basic_details.email == "morgan.architect@audioai.com"

        # 7. POST /profile/edit updates data via standard Form post
        form_payload = {
            "name": "Morgan Freeman (Final)",
            "email": "morgan.final@audioai.com",
            "phone": "+1 555-0999",
            "headline": "Principal Audio Intelligence Engineer"
        }
        r_post_form = client.post("/profile/edit", data=form_payload, headers={"Accept": "text/html"})
        assert r_post_form.status_code == 200
        assert "text/html" in r_post_form.headers.get("content-type", "")
        assert "Morgan Freeman (Final)" in r_post_form.text


@pytest.mark.asyncio
async def test_kaalu_profile_context_injection(sample_user_profile):
    """Verify KaaluOrchestrator injects verified user profile into LLM conversation messages."""
    mock_mgr = MagicMock()
    mock_mgr.load_profile.return_value = sample_user_profile

    orchestrator = KaaluOrchestrator(profile_manager=mock_mgr)
    orchestrator.ws_client = AsyncMock()
    orchestrator.ws_client.connect_server = AsyncMock()

    captured_messages = []

    async def mock_generate_async(messages, **kwargs):
        captured_messages.extend(messages)
        return json.dumps({
            "thought": "I see the user profile for Alex Mercer. Finishing response.",
            "action": "finish",
            "final_answer": "Hello Alex Mercer! I see you are a Senior Python & AI Engineer.",
            "voice_response": "Hello Alex, ready to assist."
        })

    orchestrator.llm_client.generate_async = mock_generate_async

    result = await orchestrator.process_user_goal("Who am I and what are my skills?")

    assert result["status"] == "completed"
    assert "Alex Mercer" in result["final_answer"]

    # Verify that the profile prompt context was injected in messages sent to LLM
    system_contents = [m["content"] for m in captured_messages if m["role"] == "system"]
    assert any("Current Verified User Information" in sc for sc in system_contents)
    assert any("Alex Mercer" in sc for sc in system_contents)
    assert any("Senior Python & AI Engineer" in sc for sc in system_contents)


@pytest.mark.asyncio
async def test_kaalu_profile_driven_job_search_and_career_advice(sample_user_profile):
    """
    Test the short-term goal:
    Kaalu formulates targeted job searches using the user profile, delegates to David,
    filters the results, and provides tailored career advice & education tips.
    """
    mock_mgr = MagicMock()
    mock_mgr.load_profile.return_value = sample_user_profile

    orchestrator = KaaluOrchestrator(profile_manager=mock_mgr)
    orchestrator.ws_client = AsyncMock()
    orchestrator.ws_client.connect_server = AsyncMock()
    orchestrator.ws_client.send_task = AsyncMock()

    turn = 0

    async def mock_generate_async(messages, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            # Kaalu inspects profile (Senior Python & AI Engineer, PyTorch, Docker)
            # and delegates customized job search to David
            return json.dumps({
                "thought": "The user is Alex Mercer, a Senior Python & AI Engineer. I will instruct David to search for Senior AI Engineer remote jobs.",
                "action": "delegate",
                "recipient": "david",
                "task_action": "navigate",
                "payload": {
                    "url": "https://www.google.com/search?q=Senior+Python+AI+Engineer+jobs+remote"
                }
            })
        else:
            # Kaalu receives David's search results, filters best matches, provides career advice and education tips
            return json.dumps({
                "thought": "I have reviewed David's job search results and filtered the best 3 positions matching Alex's background. I will also provide career and education guidance.",
                "action": "finish",
                "final_answer": (
                    "### Recommended Job Opportunities for Alex Mercer\n"
                    "1. **Senior AI Systems Engineer - Anthropic / Scale AI (Remote)**\n"
                    "   - *Match*: 95% - High alignment with PyTorch, distributed microservices, and multi-agent systems.\n"
                    "2. **Lead Python ML Infrastructure Engineer - OpenAI (San Francisco / Hybrid)**\n"
                    "   - *Match*: 92% - Requires strong Docker, Kubernetes, and low-latency LLM serving.\n\n"
                    "### Personalized Career Advice & Education Tips\n"
                    "- **Upskilling Tip**: Deepen expertise in TensorRT-LLM and vLLM kernel optimization to boost low-latency serving credentials.\n"
                    "- **Certification Recommendation**: Consider adding CKA (Certified Kubernetes Administrator) to complement your AWS Solutions Architect cert.\n"
                    "- **Resume Highlight**: Showcase your 45% latency reduction at NeuralSync Labs at the top of your resume."
                ),
                "voice_response": "Alex, I found two senior AI roles matching your background. I also prepared recommendations for upskilling in LLM serving optimizations."
            })

    orchestrator.llm_client.generate_async = mock_generate_async

    # David returns realistic search results
    orchestrator.ws_client.receive_response.return_value = {
        "success": True,
        "url": "https://www.google.com/search?q=Senior+Python+AI+Engineer+jobs+remote",
        "title": "Senior Python AI Engineer jobs remote - Google Search",
        "search_results": [
            {"title": "Senior AI Systems Engineer - Scale AI", "snippet": "Looking for Senior AI Engineer with Python, PyTorch, Docker experience."},
            {"title": "Lead Python ML Infrastructure Engineer - TechCorp", "snippet": "Requirements: 5+ years Python, Kubernetes, LLM serving architecture."}
        ]
    }

    result = await orchestrator.process_user_goal("Find me the best jobs based on my profile and give me career advice and education tips.")

    assert result["status"] == "completed"
    assert "Anthropic" in result["final_answer"] or "Scale AI" in result["final_answer"]
    assert "Career Advice" in result["final_answer"]
    assert "Education Tips" in result["final_answer"]
    assert "Alex" in result["voice_response"]
    # Verify delegation was sent to David
    orchestrator.ws_client.send_task.assert_called_once()
    call_kwargs = orchestrator.ws_client.send_task.call_args.kwargs
    assert call_kwargs["recipient"] == "david"
    assert call_kwargs["action"] == "navigate"
    assert "Senior+Python+AI+Engineer" in call_kwargs["payload"]["url"]


@pytest.mark.asyncio
async def test_kaalu_form_fill_delegation_autofill(sample_user_profile):
    """Verify that when Kaalu delegates fill_form to David without fields, fields are autofilled from profile."""
    mock_mgr = MagicMock()
    mock_mgr.load_profile.return_value = sample_user_profile

    orchestrator = KaaluOrchestrator(profile_manager=mock_mgr)
    orchestrator.ws_client = AsyncMock()
    orchestrator.ws_client.connect_server = AsyncMock()
    orchestrator.ws_client.send_task = AsyncMock()

    turn = 0

    async def mock_generate_async(messages, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return json.dumps({
                "thought": "Delegating form filling to David on the job application page.",
                "action": "delegate",
                "recipient": "david",
                "task_action": "fill_form",
                "payload": {}  # Empty fields -> should be auto-populated
            })
        else:
            return json.dumps({
                "thought": "Form successfully submitted.",
                "action": "finish",
                "final_answer": "Successfully autofilled the application form using your verified profile.",
                "voice_response": "The application form has been filled with your profile details."
            })

    orchestrator.llm_client.generate_async = mock_generate_async
    orchestrator.ws_client.receive_response.return_value = {
        "success": True,
        "filled_fields": ["first_name", "last_name", "email", "phone", "linkedin"],
        "skipped_fields": []
    }

    result = await orchestrator.process_user_goal("Fill the job application form with my details.")

    assert result["status"] == "completed"
    # Verify send_task called with auto-populated fields
    orchestrator.ws_client.send_task.assert_called_once()
    call_kwargs = orchestrator.ws_client.send_task.call_args.kwargs
    assert call_kwargs["recipient"] == "david"
    assert call_kwargs["action"] == "fill_form"
    fields = call_kwargs["payload"]["fields"]
    assert fields["first_name"] == "Alex"
    assert fields["email"] == "alex.mercer@example.com"
    assert fields["phone"] == "+1 555-0199"


def test_profile_edit_multi_item_and_custom_categories(tmp_path):
    """Verify POST /profile/edit with dynamic multi-item lists and custom skill categories."""
    prof_file = tmp_path / "dynamic_profile.json"
    mock_mgr = ProfileManager(profile_path=prof_file)

    with patch.object(ProfileManager, "get_instance", return_value=mock_mgr):
        client = TestClient(app)

        payload = {
            "name": "Rohit Singh",
            "headline": "AI & Agentic Systems Engineer",
            "email": "rsingh.py@gmail.com",
            "phone": "+91-7409210904",
            "location": "Bengaluru, India",
            "summary": "Building autonomous AI agents.",
            "linkedin": "https://linkedin.com/in/rohiyaa",
            "github": "https://github.com/RohitSingh-04",
            "portfolio": "https://rohiyaa.pythonanywhere.com",
            "technical_skills": "Python, SQL, C++, Java",
            "frameworks_and_tools": "FastAPI, PyTorch, Docker",
            "soft_skills": "Problem Solving, Agile",
            "languages": "English, Hindi",
            "custom_categories": {
                "AI & LLMs": "LangChain, Agentic AI, Ollama, Prompt Engineering",
                "Cloud & DevOps": "AWS EC2, Docker, Linux, Git"
            },
            "experiences": [
                {
                    "company": "Deloitte",
                    "role": "Associate Analyst",
                    "location": "Bengaluru, India",
                    "start_date": "Sept 2025",
                    "end_date": "July 2026",
                    "highlights": ["Built data processing pipelines", "Engineered backend scripts"]
                },
                {
                    "company": "Infosys Springboard",
                    "role": "Intern",
                    "location": "Remote",
                    "start_date": "Nov 2024",
                    "end_date": "Jan 2025",
                    "highlights": ["Built scalable REST APIs"]
                }
            ],
            "projects": [
                {
                    "name": "AML OSDD Helper",
                    "technologies": ["Python", "LangChain", "FastAPI"],
                    "url": "https://github.com/RohitSingh-04/AML-OSDD-Helper",
                    "description": "Risk assessment agent architecture.",
                    "highlights": ["Real-time screening"]
                },
                {
                    "name": "Musivan",
                    "technologies": ["Django", "PostgreSQL", "Docker"],
                    "url": "https://github.com/RohitSingh-04/Musivan",
                    "description": "Music distribution and community platform.",
                    "highlights": ["Multi-tenant storage"]
                }
            ],
            "educations": [
                {
                    "degree": "MCA",
                    "institution": "Graphic Era Hill University",
                    "start_year": "2025",
                    "end_year": "2027"
                },
                {
                    "degree": "BCA",
                    "institution": "Graphic Era Hill University",
                    "start_year": "2022",
                    "end_year": "2025",
                    "grade": "8.9 CGPA"
                }
            ],
            "certifications": [
                {
                    "name": "Django Complete Course",
                    "issuer": "Udemy",
                    "issue_date": "2026"
                },
                {
                    "name": "Project Management",
                    "issuer": "IIT Roorkee, NPTEL",
                    "issue_date": "2024"
                }
            ]
        }

        resp = client.post("/profile/edit", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

        # Verify loaded profile from manager
        loaded = mock_mgr.load_profile()
        assert loaded is not None
        assert loaded.basic_details.name == "Rohit Singh"
        assert len(loaded.experiences) == 2
        assert loaded.experiences[0].company == "Deloitte"
        assert len(loaded.projects) == 2
        assert loaded.projects[0].name == "AML OSDD Helper"
        assert len(loaded.educations) == 2
        assert len(loaded.certifications) == 2

        # Verify custom categories in Skills
        all_cats = loaded.skills.all_categories()
        assert "AI & LLMs" in all_cats
        assert "Cloud & DevOps" in all_cats
        assert "LangChain" in all_cats["AI & LLMs"]

        # Verify prompt context formatting
        ctx = loaded.to_prompt_context()
        assert "Deloitte" in ctx
        assert "AML OSDD Helper" in ctx
        assert "AI & LLMs" in ctx
        assert "Graphic Era Hill University" in ctx


@pytest.mark.asyncio
async def test_github_repos_and_import_endpoints(tmp_path, sample_user_profile):
    """Verify GET /profile/github/repos and POST /profile/github/import."""
    prof_file = tmp_path / "gh_profile.json"
    mock_mgr = ProfileManager(profile_path=prof_file)
    mock_mgr.save_profile(sample_user_profile)

    fake_gh_repos = [
        {
            "name": "Autonomous-Agent-Platform",
            "description": "Multi-agent autonomous framework",
            "html_url": "https://github.com/alex-mercer/Autonomous-Agent-Platform",
            "stargazers_count": 42,
            "language": "Python",
            "topics": ["agents", "llm", "orchestration"],
            "fork": False
        },
        {
            "name": "FastAPI-Streaming-Engine",
            "description": "Ultra low-latency audio streaming",
            "html_url": "https://github.com/alex-mercer/FastAPI-Streaming-Engine",
            "stargazers_count": 18,
            "language": "TypeScript",
            "topics": ["webrtc", "fastapi"],
            "fork": False
        }
    ]

    with patch.object(ProfileManager, "get_instance", return_value=mock_mgr):
        client = TestClient(app)

        # 1. Test GET /profile/github/repos auto-detecting username from profile
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_gh_repos

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            r = client.get("/profile/github/repos")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "success"
            assert data["username"] == "alex-mercer"
            assert data["count"] == 2
            assert data["repositories"][0]["name"] == "Autonomous-Agent-Platform"
            assert data["repositories"][0]["stars"] == 42
            assert "Python" in data["repositories"][0]["technologies"]

        # 2. Test GET /profile/github/repos with explicit username
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            r = client.get("/profile/github/repos?username=customuser")
            assert r.status_code == 200
            assert r.json()["username"] == "customuser"

        # 3. Test GitHub user 404
        mock_404 = MagicMock()
        mock_404.status_code = 404
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_404):
            r = client.get("/profile/github/repos?username=nonexistent-user-999")
            assert r.status_code == 404
            assert "not found" in r.json()["detail"].lower()

        # 4. Test GitHub network failure returns 502
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=Exception("DNS resolution failed")):
            r = client.get("/profile/github/repos?username=alex-mercer")
            assert r.status_code == 502
            assert "failed to connect" in r.json()["detail"].lower()

        # 5. Test POST /profile/github/import with repositories list
        import_payload = {
            "repositories": [
                {
                    "name": "Autonomous-Agent-Platform",
                    "description": "Multi-agent autonomous framework",
                    "url": "https://github.com/alex-mercer/Autonomous-Agent-Platform",
                    "stars": 42,
                    "language": "Python",
                    "technologies": ["Python", "agents", "llm"]
                }
            ]
        }
        r_import = client.post("/profile/github/import", json=import_payload)
        assert r_import.status_code == 200
        import_data = r_import.json()
        assert import_data["status"] == "success"
        assert import_data["imported_count"] == 1
        assert any(p["name"] == "Autonomous-Agent-Platform" for p in import_data["projects"])

        # Verify duplicate skipped on second import
        r_import_dup = client.post("/profile/github/import", json=import_payload)
        assert r_import_dup.status_code == 200
        assert r_import_dup.json()["imported_count"] == 0

        # Verify persisted in storage
        reloaded = mock_mgr.load_profile()
        assert any(p.name == "Autonomous-Agent-Platform" for p in reloaded.projects)
        project_obj = next(p for p in reloaded.projects if p.name == "Autonomous-Agent-Platform")
        assert project_obj.stars == 42
        assert project_obj.language == "Python"


def test_skills_remove_category_method():
    """Verify Skills.remove_category() removes standard and custom categories correctly."""
    s = Skills(
        technical=["Python", "C++"],
        frameworks_and_tools=["FastAPI", "Docker"],
        soft_skills=["Leadership", "Agile"],
        languages=["English"],
        categories={"AI & LLMs": ["LangChain", "Ollama"], "Cloud": ["AWS"]}
    )

    # 1. Remove custom category
    assert "AI & LLMs" in s.categories
    assert s.remove_category("AI & LLMs") is True
    assert "AI & LLMs" not in s.categories
    assert "AI & LLMs" not in s.all_categories()

    # 2. Remove standard categories (case-insensitive)
    assert s.remove_category("soft skills") is True
    assert s.soft_skills == []
    assert "Soft Skills" not in s.all_categories()

    assert s.remove_category("spoken languages") is True
    assert s.languages == []
    assert "Spoken Languages" not in s.all_categories()

    # 3. Nonexistent category returns False
    assert s.remove_category("NonExistentCategory") is False


def test_delete_skill_category_endpoint(tmp_path, sample_user_profile):
    """Verify DELETE /profile/skills/category/{category_name} and POST /profile/skills/category/remove."""
    sample_user_profile.skills.categories["Cloud & DevOps"] = ["Docker", "Kubernetes"]
    prof_file = tmp_path / "del_cat_profile.json"
    mock_mgr = ProfileManager(profile_path=prof_file)
    mock_mgr.save_profile(sample_user_profile)

    with patch.object(ProfileManager, "get_instance", return_value=mock_mgr):
        client = TestClient(app)

        # 1. DELETE custom category
        r1 = client.delete("/profile/skills/category/Cloud%20%26%20DevOps")
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1["status"] == "success"
        assert "Cloud & DevOps" not in data1["remaining_categories"]

        # Verify persisted
        p1 = mock_mgr.load_profile()
        assert "Cloud & DevOps" not in p1.skills.categories

        # 2. DELETE standard category (Soft Skills)
        r2 = client.delete("/profile/skills/category/Soft%20Skills")
        assert r2.status_code == 200
        p2 = mock_mgr.load_profile()
        assert p2.skills.soft_skills == []
        assert "Soft Skills" not in p2.skills.all_categories()

        # 3. DELETE nonexistent category returns 404
        r3 = client.delete("/profile/skills/category/NonExistentCategory999")
        assert r3.status_code == 404

        # 4. POST /profile/skills/category/remove
        r4 = client.post("/profile/skills/category/remove", json={"category_name": "Technical / Languages"})
        assert r4.status_code == 200
        p4 = mock_mgr.load_profile()
        assert p4.skills.technical == []


