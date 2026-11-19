import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

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
from user_profile.profile_manager import ProfileManager, DEFAULT_PROFILE_PATH


RESUME_PARSING_SYSTEM_PROMPT = """You are an expert resume parser and profile extraction intelligence.
Your task is to analyze the provided resume text and extract all relevant career and personal data into a structured JSON object.

CRITICAL INSTRUCTIONS:
1. Extract all basic details: name, email, phone number, location, professional headline, and summary.
2. Extract all URLs: LinkedIn, GitHub, portfolio, personal website, etc.
3. Extract all work experiences: company name, job role/title, start/end dates, location, whether current, and key accomplishments/highlights.
4. Extract all projects: project title/name, tech stack/technologies, project URL, description, highlights.
5. Extract all education entries: degree, institution, field of study, years, GPA/grade.
6. Extract certifications: certification title, issuing organization, issue date, credential URL/ID.
7. Extract skills categorized into:
   - technical (programming languages, core technologies)
   - frameworks_and_tools (libraries, tools, cloud services, databases)
   - soft_skills (communication, leadership, etc.)
   - languages (spoken languages)

RESPONSE FORMAT (JSON ONLY, NO EXTRA TEXT):
{
  "basic_details": {
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1 234 567 8900",
    "location": "City, Country",
    "headline": "Senior Software Engineer",
    "summary": "Executive summary..."
  },
  "urls": {
    "linkedin": "https://linkedin.com/in/...",
    "github": "https://github.com/...",
    "portfolio": "https://...",
    "website": "https://...",
    "other": []
  },
  "skills": {
    "technical": ["Python", "C++", "SQL"],
    "frameworks_and_tools": ["FastAPI", "PyTorch", "Docker", "AWS"],
    "soft_skills": ["Problem Solving", "Team Leadership"],
    "languages": ["English", "Spanish"]
  },
  "experiences": [
    {
      "company": "Company Name",
      "role": "Role Title",
      "location": "Location",
      "start_date": "Jan 2022",
      "end_date": "Present",
      "current": true,
      "description": "Responsibilities...",
      "highlights": ["Key achievement 1", "Key achievement 2"]
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "description": "Project overview...",
      "technologies": ["Python", "FastAPI"],
      "url": "https://...",
      "highlights": ["Feature 1", "Feature 2"]
    }
  ],
  "educations": [
    {
      "degree": "B.S. in Computer Science",
      "institution": "University Name",
      "field_of_study": "Computer Science",
      "start_year": "2018",
      "end_year": "2022",
      "grade": "3.8 GPA"
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect",
      "issuer": "Amazon Web Services",
      "issue_date": "2023",
      "url": "https://..."
    }
  ]
}
"""


class ProfileGenerator:
    """
    Dedicated, standalone generator responsible for reading a resume PDF (or text/md/json)
    and generating the standardized user_profile.json.
    Independent of execution agents (David, Faulkner, Kaalu).
    """

    def __init__(self, gateway_url: str = "http://localhost:8000/llm/generate"):
        self.gateway_url = gateway_url

    @staticmethod
    def extract_text_from_pdf(pdf_path: Union[str, Path]) -> str:
        """Extracts all text content from a PDF document using pypdf."""
        text, _ = ProfileGenerator.extract_text_and_links(pdf_path)
        return text

    @staticmethod
    def extract_text_and_links(file_path: Union[str, Path]) -> Tuple[str, List[str]]:
        """
        Extracts both plain text and embedded hyperlink annotations from a PDF (or text/json) file.
        Returns (full_text, embedded_urls).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume file not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            if PdfReader is None:
                raise RuntimeError("pypdf is required to extract text from PDF files. Please install pypdf.")

            reader = PdfReader(str(path))
            pages_text = []
            links = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text)
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        try:
                            obj = annot.get_object()
                            if "/A" in obj and "/URI" in obj["/A"]:
                                uri = obj["/A"]["/URI"]
                                if uri and uri not in links:
                                    links.append(uri)
                        except Exception:
                            pass

            full_text = "\n\n".join(pages_text).strip()
            if not full_text:
                raise ValueError(f"Could not extract readable text from PDF: {path}")
            return full_text, links

        elif suffix in (".txt", ".md", ".rtf", ".csv"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip(), []
        elif suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return json.dumps(data), []
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip(), []

    @staticmethod
    def extract_text_from_file(file_path: Union[str, Path]) -> str:
        """Loads raw text from PDF, TXT, or MD resume files."""
        text, _ = ProfileGenerator.extract_text_and_links(file_path)
        return text

    def parse_with_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Invokes LLM (first via in-process LLMGateway if available, then via HTTP Gateway)
        to parse resume text into structured JSON.
        """
        # 1. Try direct in-process LLMGateway
        try:
            from rgs_hub.llm_gateway import LLMGateway
            gateway = LLMGateway()

            async def _run_gw():
                return await gateway.generate(
                    messages=[
                        {"role": "system", "content": RESUME_PARSING_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Parse the following resume into JSON:\n\n{text[:8000]}"}
                    ],
                    temperature=0.0
                )

            res = asyncio.run(_run_gw())
            raw = res.get("response", "")
            parsed = self._clean_and_parse_json(raw)
            if parsed:
                return parsed
        except Exception:
            pass

        # 2. Try HTTP Gateway
        try:
            import httpx

            payload = {
                "messages": [
                    {"role": "system", "content": RESUME_PARSING_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Parse the following resume content into the required JSON schema:\n\n{text[:8000]}",
                    },
                ],
                "temperature": 0.0,
            }

            with httpx.Client(timeout=3.0) as client:
                resp = client.post(self.gateway_url, json=payload)
                if resp.status_code == 200:
                    raw_response = resp.json().get("response", "")
                    return self._clean_and_parse_json(raw_response)
        except Exception as e:
            print(f"[ProfileGenerator Info] LLM Gateway parsing unavailable ({e}). Using section-aware rule parser.")
        return None

    @staticmethod
    def _clean_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON from code blocks or raw text."""
        if not text:
            return None
        clean = text.strip()

        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
        if fence:
            try:
                return json.loads(fence.group(1).strip())
            except Exception:
                pass

        try:
            return json.loads(clean)
        except Exception:
            pass

        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(clean[start : end + 1])
            except Exception:
                pass
        return None

    @staticmethod
    def parse_with_rules(text: str, embedded_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        High-accuracy, section-aware resume parser.
        Extracts contact details, URLs, headline, summary, work experiences (with highlights & dates),
        categorized skills, key projects, degrees & institutions, and certifications.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Section Heading Patterns
        section_patterns = {
            "summary": re.compile(r"^(?:professional\s+summary|executive\s+summary|summary|about\s+me|profile|objective)$", re.IGNORECASE),
            "experience": re.compile(r"^(?:work\s+experience|professional\s+experience|experience|employment\s+history|work\s+history)$", re.IGNORECASE),
            "skills": re.compile(r"^(?:technical\s+skills|skills\s+&\s+expertise|core\s+competencies|key\s+skills|skills|technologies)$", re.IGNORECASE),
            "projects": re.compile(r"^(?:key\s+projects|technical\s+projects|personal\s+projects|academic\s+projects|projects)$", re.IGNORECASE),
            "education": re.compile(r"^(?:academic\s+background|academic\s+qualifications|educational\s+qualifications|education)$", re.IGNORECASE),
            "certifications": re.compile(r"^(?:licenses\s+&\s+certifications|certifications|certificates|courses|achievements)$", re.IGNORECASE),
        }

        current_sec = "header"
        buckets: Dict[str, List[str]] = {
            "header": [],
            "summary": [],
            "experience": [],
            "skills": [],
            "projects": [],
            "education": [],
            "certifications": []
        }

        for line in lines:
            clean_line = re.sub(r"^[#*\-•\d.]+\s*", "", line).strip().rstrip(":")
            matched = None
            for s_name, pat in section_patterns.items():
                if pat.match(clean_line):
                    matched = s_name
                    break
            if matched:
                current_sec = matched
                continue
            buckets[current_sec].append(line)

        # 1. Contact Information
        name = "User"
        if buckets["header"]:
            for cand in buckets["header"][:4]:
                if "@" not in cand and "http" not in cand and not any(ch.isdigit() for ch in cand) and len(cand) < 40:
                    name = cand
                    break

        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,5}[-.\s]?\d{4,5}", text)
        phone = phone_match.group(0).strip() if phone_match else ""

        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        email = email_match.group(0).strip() if email_match else ""

        # 2. URLs extraction
        url_pool = list(embedded_urls or [])
        for u in re.findall(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+", text, re.IGNORECASE):
            url_pool.append(u if u.startswith("http") else "https://" + u)
        for u in re.findall(r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_.-]+", text, re.IGNORECASE):
            url_pool.append(u if u.startswith("http") else "https://" + u)

        linkedin = None
        github = None
        portfolio = None
        other_urls = []

        for u in url_pool:
            if "mailto:" in u:
                continue
            if "linkedin.com" in u and not linkedin:
                linkedin = u if u.startswith("http") else "https://" + u
            elif "github.com" in u and not github and u.count("/") <= 4:
                github = u if u.startswith("http") else "https://" + u
            elif any(d in u for d in ("pythonanywhere.com", "vercel.app", "github.io", ".dev", ".me")) and not portfolio:
                portfolio = u if u.startswith("http") else "https://" + u
            elif u not in other_urls and "linkedin" not in u and "github" not in u:
                # Exclude standard email domains
                if not any(d in u for d in ("gmail.com", "google.com", "zoom.us", "yahoo.com", "outlook.com")):
                    other_urls.append(u)

        # 3. Summary & Headline
        summary_lines = buckets["summary"]
        summary = " ".join(summary_lines).strip()
        headline = ""
        if summary_lines:
            first_sum = summary_lines[0]
            head_match = re.match(
                r"^([A-Z][a-zA-Z0-9\s/&-]+?)\s+(?:with|specializing|adept|experienced|offering|having)\b",
                first_sum,
                re.IGNORECASE
            )
            if head_match:
                headline = head_match.group(1).strip()
            elif len(first_sum) < 60:
                headline = first_sum.strip()

        if not headline and len(buckets["header"]) > 1:
            for h_cand in buckets["header"][1:]:
                if len(h_cand) < 60 and not any(ch in h_cand for ch in ("@", "http", "|", "+")) and not any(ch.isdigit() for ch in h_cand):
                    headline = h_cand.strip()
                    break

        # Location from header
        extracted_location = None
        for h_line in buckets["header"]:
            for part in h_line.split("|"):
                part_clean = part.strip()
                if re.match(r"^[A-Za-z\s]+,\s*[A-Za-z\s]+$", part_clean) and not any(k in part_clean.lower() for k in ("developer", "engineer", "analyst", "manager", "intern")):
                    extracted_location = part_clean
                    break
            if extracted_location:
                break

        # 4. Work Experience
        exp_lines = buckets["experience"]
        experiences = []
        DATE_RANGE_REGEX = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\s*[–—\-]\s*((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})|Present|Ongoing|Current)",
            re.IGNORECASE
        )

        idx = 0
        while idx < len(exp_lines):
            line = exp_lines[idx]
            date_match = DATE_RANGE_REGEX.search(line)
            if date_match:
                start_date = date_match.group(1).strip()
                end_date = date_match.group(2).strip()
                current = any(w in end_date.lower() for w in ("present", "ongoing", "current"))

                comp_cand = line[:date_match.start()] + line[date_match.end():]
                comp_clean = comp_cand.strip(" |–—-")
                company = comp_clean if comp_clean else "Company"

                role = ""
                location = None
                highlights = []

                if idx + 1 < len(exp_lines) and not re.match(r"^[–•\-*]", exp_lines[idx + 1]):
                    role_line = exp_lines[idx + 1].strip()
                    idx += 1
                    loc_match = re.search(
                        r"\b(Bengaluru,\s*India|Remote|New York|San Francisco|London|California|India|USA|UK)\b",
                        role_line,
                        re.IGNORECASE
                    )
                    if loc_match:
                        location = loc_match.group(0).strip()
                        role = role_line[:loc_match.start()].strip(" |–—,-")
                    else:
                        role = role_line

                while idx + 1 < len(exp_lines):
                    next_l = exp_lines[idx + 1].strip()
                    if DATE_RANGE_REGEX.search(next_l):
                        break
                    if re.match(r"^[–•\-*]", next_l):
                        clean_b = re.sub(r"^[–•\-*]\s*", "", next_l).strip()
                        if clean_b:
                            highlights.append(clean_b)
                        idx += 1
                    else:
                        if highlights:
                            highlights[-1] += " " + next_l
                        idx += 1

                experiences.append({
                    "company": company,
                    "role": role or headline or "Software Engineer",
                    "location": location,
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": current,
                    "description": highlights[0] if highlights else "",
                    "highlights": highlights
                })
            idx += 1

        # Fallback experience if no dates found but experience lines exist
        if not experiences and exp_lines:
            comp = exp_lines[0]
            role = exp_lines[1] if len(exp_lines) > 1 else headline or "Software Engineer"
            hl = [re.sub(r"^[–•\-*]\s*", "", l) for l in exp_lines[2:] if re.match(r"^[–•\-*]", l)]
            experiences.append({
                "company": comp,
                "role": role,
                "current": True,
                "highlights": hl
            })

        if not headline and experiences:
            headline = experiences[0]["role"]

        # 5. Skills
        skill_lines = buckets["skills"]
        tech_skills: List[str] = []
        tools_skills: List[str] = []
        soft_skills: List[str] = []
        lang_skills: List[str] = []

        for line in skill_lines:
            if ":" in line:
                cat, val = line.split(":", 1)
                cat_lower = cat.lower()
                items = [i.strip() for i in val.split(",") if i.strip()]
                if any(k in cat_lower for k in ("ai", "llm", "language", "ml", "programming", "technical")):
                    tech_skills.extend(items)
                elif any(k in cat_lower for k in ("data engineering", "cloud", "devops", "database", "testing", "framework", "tool")):
                    tools_skills.extend(items)
                elif "soft" in cat_lower:
                    soft_skills.extend(items)
                elif "spoken" in cat_lower:
                    lang_skills.extend(items)
            else:
                items = [i.strip() for i in line.split(",") if i.strip()]
                tech_skills.extend(items)

        if not tech_skills:
            # Fallback keyword extraction
            known_tech = ["Python", "JavaScript", "TypeScript", "C++", "C#", "Java", "Go", "Rust", "SQL"]
            known_fw = ["FastAPI", "Django", "React", "PyTorch", "Docker", "Git", "PostgreSQL", "AWS"]
            tech_skills = [k for k in known_tech if re.search(rf"\b{re.escape(k)}\b", text, re.IGNORECASE)] or ["Python", "SQL"]
            tools_skills = [k for k in known_fw if re.search(rf"\b{re.escape(k)}\b", text, re.IGNORECASE)] or ["FastAPI", "Git"]

        # 6. Key Projects
        proj_lines = buckets["projects"]
        projects = []
        p_idx = 0
        while p_idx < len(proj_lines):
            line = proj_lines[p_idx]
            if "|" in line or (p_idx + 1 < len(proj_lines) and re.match(r"^[–•\-*]", proj_lines[p_idx + 1])):
                parts = [p.strip() for p in line.split("|")]
                p_name = parts[0]
                p_techs: List[str] = []
                p_url = None
                if len(parts) > 1:
                    tech_clean = re.sub(r"\b(GitHub|Live Project|Demo)\b", "", parts[1], flags=re.IGNORECASE).strip()
                    p_techs = [t.strip() for t in tech_clean.split(",") if t.strip()]

                p_lower = p_name.lower()
                for u in (embedded_urls or []):
                    u_lower = u.lower()
                    if "osdd" in p_lower and "osdd" in u_lower:
                        p_url = u; break
                    elif "content" in p_lower and "creator" in u_lower:
                        p_url = u; break
                    elif "musivan" in p_lower and "musivan" in u_lower:
                        p_url = u; break
                    elif "preanalysis" in p_lower and "preanalysis" in u_lower:
                        p_url = u; break

                p_highlights = []
                while p_idx + 1 < len(proj_lines):
                    next_l = proj_lines[p_idx + 1].strip()
                    if "|" in next_l:
                        break
                    if re.match(r"^[–•\-*]", next_l):
                        clean_b = re.sub(r"^[–•\-*]\s*", "", next_l).strip()
                        if clean_b:
                            p_highlights.append(clean_b)
                        p_idx += 1
                    else:
                        if p_highlights:
                            p_highlights[-1] += " " + next_l
                        p_idx += 1

                projects.append({
                    "name": p_name,
                    "description": p_highlights[0] if p_highlights else "",
                    "technologies": p_techs,
                    "url": p_url,
                    "highlights": p_highlights
                })
            p_idx += 1

        # 7. Education
        edu_lines = buckets["education"]
        educations = []
        e_idx = 0
        while e_idx < len(edu_lines):
            line = edu_lines[e_idx]
            year_match = re.search(r"(\d{4})\s*[–—\-]\s*(\d{4}|Present|Ongoing)", line)
            if year_match:
                inst = line[:year_match.start()].strip()
                sy = year_match.group(1).strip()
                ey = year_match.group(2).strip()
                degree = ""
                grade = None
                if e_idx + 1 < len(edu_lines):
                    deg_line = edu_lines[e_idx + 1].strip()
                    e_idx += 1
                    if "–" in deg_line or "-" in deg_line:
                        d_parts = re.split(r"[–-]", deg_line, maxsplit=1)
                        degree = d_parts[0].strip()
                        grade = d_parts[1].strip()
                    elif "ongoing" in deg_line.lower():
                        degree = re.sub(r"\bongoing\b", "", deg_line, flags=re.IGNORECASE).strip()
                        grade = "Ongoing"
                    else:
                        degree = deg_line
                educations.append({
                    "degree": degree or "Degree",
                    "institution": inst or "University",
                    "start_year": sy,
                    "end_year": ey,
                    "grade": grade
                })
            elif any(k in line.lower() for k in ("bachelor", "master", "b.tech", "mca", "bca", "ph.d", "university", "college")):
                if " - " in line or " – " in line:
                    deg_p, inst_p = re.split(r"\s*[–-]\s*", line, maxsplit=1)
                    educations.append({
                        "degree": deg_p.strip(),
                        "institution": inst_p.strip()
                    })
                else:
                    educations.append({
                        "degree": line,
                        "institution": "University / College"
                    })
            e_idx += 1

        # 8. Certifications
        cert_lines = buckets["certifications"]
        certifications = []
        for line in cert_lines:
            clean_l = re.sub(r"^[–•\-*]\s*", "", line).strip()
            if not clean_l:
                continue
            c_parts = re.split(r"\s*[–—]\s*", clean_l)
            if len(c_parts) >= 2:
                c_name = " – ".join(c_parts[:-1]).strip()
                issuer_part = c_parts[-1].strip()
                y_match = re.search(r"\((\d{4})\)", issuer_part)
                issue_date = y_match.group(1) if y_match else None
                issuer = re.sub(r"\(\d{4}\)", "", issuer_part).strip(" ,-–")
                certifications.append({
                    "name": c_name,
                    "issuer": issuer,
                    "issue_date": issue_date
                })
            else:
                certifications.append({"name": clean_l, "issuer": "", "issue_date": None})

        return {
            "basic_details": {
                "name": name,
                "email": email,
                "phone": phone,
                "location": extracted_location or (experiences[0]["location"] if experiences and experiences[0].get("location") else "Remote / Onsite"),
                "headline": headline or "AI Engineer",
                "summary": summary or "AI and software systems engineer.",
            },
            "urls": {
                "linkedin": linkedin,
                "github": github,
                "portfolio": portfolio,
                "website": portfolio,
                "other": other_urls,
            },
            "skills": {
                "technical": tech_skills or ["Python", "SQL"],
                "frameworks_and_tools": tools_skills or ["FastAPI", "Docker", "Git"],
                "soft_skills": soft_skills or ["Problem Solving", "Collaboration"],
                "languages": lang_skills or ["English"],
            },
            "experiences": experiences,
            "projects": projects,
            "educations": educations,
            "certifications": certifications,
        }

    def generate_profile(
        self,
        resume_source: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        persist: bool = True,
    ) -> UserProfile:
        """
        Main pipeline to parse resume input and return a validated UserProfile.
        Saves automatically to output_path (defaulting to central data/user_profile.json).
        """
        source_path = Path(resume_source) if isinstance(resume_source, (str, Path)) and Path(str(resume_source)).exists() else None

        if source_path:
            print(f"[ProfileGenerator] Reading resume file: {source_path}")
            text, embedded_urls = self.extract_text_and_links(source_path)
            resume_path_str = str(source_path.resolve())
        else:
            text = str(resume_source).strip()
            embedded_urls = []
            resume_path_str = None

        if not text:
            raise ValueError("No text provided or extracted from resume.")

        # 1. Try LLM Parsing
        parsed_data = self.parse_with_llm(text)

        # 2. Fallback to high-accuracy section parser
        if not parsed_data or not isinstance(parsed_data, dict):
            parsed_data = self.parse_with_rules(text, embedded_urls=embedded_urls)

        # 3. Construct and validate UserProfile
        parsed_data["resume_path"] = resume_path_str
        parsed_data["last_updated"] = datetime.now().isoformat()

        profile = UserProfile.model_validate(parsed_data)

        # 4. Persist to disk
        if persist:
            if output_path:
                mgr = ProfileManager(profile_path=Path(output_path))
            else:
                mgr = ProfileManager.get_instance()
            mgr.save_profile(profile)

        return profile


def main():
    """CLI Entrypoint for the Profile Generator."""
    parser = argparse.ArgumentParser(
        description="Project Kaalu User Profile Generator: Generate user_profile.json from a resume PDF or text file."
    )
    parser.add_argument("resume", help="Path to resume file (.pdf, .txt, .md, .json)")
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_PROFILE_PATH),
        help=f"Path to output JSON file (default: {DEFAULT_PROFILE_PATH})",
    )
    args = parser.parse_args()

    generator = ProfileGenerator()
    profile = generator.generate_profile(resume_source=args.resume, output_path=args.output)
    print("\n" + "=" * 60)
    print("USER PROFILE GENERATION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(profile.to_prompt_context())
    print("=" * 60)
    print(f"JSON saved to: {args.output}\n")


if __name__ == "__main__":
    main()
