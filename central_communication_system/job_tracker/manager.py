import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from job_tracker.schemas import JobApplicationRecord, ResumeSnapshot
try:
    from user_profile.profile_manager import ProfileManager
except (ImportError, ValueError):
    from ..user_profile.profile_manager import ProfileManager


DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_APPLICATIONS_FILE = DEFAULT_DATA_DIR / "job_applications.json"


def sanitize_filename(name: str) -> str:
    """Sanitizes strings to be safe Windows and cross-platform filenames."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned or "Document"


class JobTrackerManager:
    """
    Centralized manager for structured date-based resume storage,
    job application records, and user_profile.json synchronization.
    """

    _instance: Optional["JobTrackerManager"] = None

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        applications_file: Optional[Path] = None,
        profile_manager: Optional[ProfileManager] = None
    ):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.resumes_root = self.data_dir / "resumes"
        self.applications_root = self.data_dir / "applications"
        self.applications_file = Path(applications_file) if applications_file else (self.data_dir / "job_applications.json")

        self.resumes_root.mkdir(parents=True, exist_ok=True)
        self.applications_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.profile_manager = profile_manager or ProfileManager.get_instance()

    @classmethod
    def get_instance(
        cls,
        data_dir: Optional[Path] = None,
        applications_file: Optional[Path] = None,
        profile_manager: Optional[ProfileManager] = None
    ) -> "JobTrackerManager":
        """Singleton accessor for convenience."""
        if cls._instance is None:
            cls._instance = JobTrackerManager(
                data_dir=data_dir,
                applications_file=applications_file,
                profile_manager=profile_manager
            )
        return cls._instance

    def get_date_resume_dir(self, target_date: Optional[datetime] = None) -> Path:
        """
        Returns the structured date directory: data/resumes/YYYY-MM-DD/
        Creates parent folders automatically.
        """
        dt = target_date or datetime.now()
        date_folder = dt.strftime("%Y-%m-%d")
        folder_path = self.resumes_root / date_folder
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path

    def get_date_application_dir(self, target_date: Optional[datetime] = None) -> Path:
        """
        Returns the structured date directory for raw application snapshots:
        data/applications/YYYY-MM-DD/
        """
        dt = target_date or datetime.now()
        date_folder = dt.strftime("%Y-%m-%d")
        folder_path = self.applications_root / date_folder
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path

    def find_latest_download(
        self,
        search_dir: Optional[Path] = None,
        max_age_seconds: int = 600,
        extension_filter: Tuple[str, ...] = (".pdf", ".docx")
    ) -> Optional[Path]:
        """
        Scans the user's Downloads directory for the newest downloaded resume file.
        Filters for extensions (.pdf, .docx) created/modified within max_age_seconds.
        """
        downloads_dir = search_dir or (Path.home() / "Downloads")
        if not downloads_dir.exists():
            return None

        candidates = []
        now_ts = datetime.now().timestamp()

        try:
            for item in downloads_dir.iterdir():
                if item.is_file() and item.suffix.lower() in extension_filter:
                    mtime = item.stat().st_mtime
                    if (now_ts - mtime) <= max_age_seconds:
                        candidates.append((mtime, item))
        except Exception as e:
            print(f"[JobTrackerManager Warning] Error scanning downloads: {e}")
            return None

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def save_downloaded_resume(
        self,
        company: str,
        position: str,
        source_path: Optional[Union[str, Path]] = None,
        target_date: Optional[datetime] = None,
        move: bool = False
    ) -> Tuple[Path, str]:
        """
        Saves a generated/downloaded resume file into the structured date folder:
        data/resumes/YYYY-MM-DD/<Company>_<Position>_Resume_<timestamp>.pdf

        If source_path is not specified, scans Downloads for the newest file.
        Automatically updates user_profile.json's resume_path to this file.
        Returns (destination_path, filename).
        """
        if source_path:
            src = Path(source_path)
        else:
            found = self.find_latest_download()
            if not found:
                raise FileNotFoundError(
                    "No source resume provided and no recent PDF/DOCX file found in Downloads."
                )
            src = found

        if not src.exists():
            raise FileNotFoundError(f"Source resume file not found at: {src}")

        ext = src.suffix.lower() or ".pdf"
        target_dir = self.get_date_resume_dir(target_date)

        safe_comp = sanitize_filename(company)
        safe_pos = sanitize_filename(position)
        timestamp = datetime.now().strftime("%H%M%S")
        dest_filename = f"{safe_comp}_{safe_pos}_Resume_{timestamp}{ext}"
        dest_path = target_dir / dest_filename

        if move:
            shutil.move(str(src), str(dest_path))
        else:
            shutil.copy2(str(src), str(dest_path))

        # Synchronize UserProfile's resume_path
        if self.profile_manager:
            try:
                profile = self.profile_manager.load_profile()
                if profile:
                    profile.resume_path = str(dest_path)
                    self.profile_manager.save_profile(profile)
                    print(f"[JobTrackerManager] Updated user profile resume_path -> {dest_path}")
            except Exception as e:
                print(f"[JobTrackerManager Warning] Could not update profile resume_path: {e}")

        print(f"[JobTrackerManager] Saved resume into date structure: {dest_path}")
        return dest_path, dest_filename

    def _load_all_records(self) -> List[Dict[str, Any]]:
        """Loads all application records from data/job_applications.json."""
        if not self.applications_file.exists():
            return []
        try:
            with open(self.applications_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[JobTrackerManager Warning] Failed to read {self.applications_file}: {e}")
            return []

    def _save_all_records(self, records: List[Dict[str, Any]]) -> None:
        """Atomically saves all application records to data/job_applications.json."""
        self.applications_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.applications_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        tmp.replace(self.applications_file)

    def record_job_application(
        self,
        company: str,
        position: str,
        job_description: Optional[str] = None,
        job_url: Optional[str] = None,
        location: Optional[str] = None,
        resume_path: Optional[Union[str, Path]] = None,
        resume_snapshot: Optional[Union[Dict[str, Any], ResumeSnapshot]] = None,
        status: str = "generated",
        applied_date: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JobApplicationRecord:
        """
        Creates or updates a job application record linking the exact resume,
        job metadata, and snapshot, and persists it to central storage.
        """
        res_snap_obj = None
        if isinstance(resume_snapshot, dict):
            res_snap_obj = ResumeSnapshot.model_validate(resume_snapshot)
        elif isinstance(resume_snapshot, ResumeSnapshot):
            res_snap_obj = resume_snapshot

        res_p_str = str(resume_path) if resume_path else None
        res_fname = Path(res_p_str).name if res_p_str else None

        record = JobApplicationRecord(
            company=company.strip(),
            position=position.strip(),
            job_description=job_description.strip() if job_description else None,
            job_url=job_url.strip() if job_url else None,
            location=location.strip() if location else None,
            applied_date=applied_date or (datetime.now().isoformat() if status == "applied" else None),
            status=status,
            resume_path=res_p_str,
            resume_filename=res_fname,
            resume_snapshot=res_snap_obj,
            notes=notes,
            metadata=metadata or {}
        )

        all_records = self._load_all_records()
        all_records.append(record.model_dump())
        self._save_all_records(all_records)

        # Also save individual date-organized application snapshot
        try:
            app_date_dir = self.get_date_application_dir()
            app_file = app_date_dir / f"{record.application_id}.json"
            with open(app_file, "w", encoding="utf-8") as f:
                json.dump(record.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[JobTrackerManager Warning] Could not write application snapshot: {e}")

        print(f"[JobTrackerManager] Recorded job application '{company} - {position}' [{status}] -> {record.application_id}")
        return record

    def mark_as_applied(
        self,
        identifier: str,
        job_url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[JobApplicationRecord]:
        """
        Updates an application status to 'applied', sets applied timestamp,
        and persists changes.
        """
        all_records = self._load_all_records()
        matched = None

        norm_id = identifier.strip().lower()

        for idx, item in enumerate(all_records):
            comp = (item.get("company") or "").lower()
            app_id = (item.get("application_id") or "").lower()

            if app_id == norm_id or comp == norm_id or norm_id in comp:
                item["status"] = "applied"
                item["applied_date"] = datetime.now().isoformat()
                if job_url:
                    item["job_url"] = job_url
                if notes:
                    existing_notes = item.get("notes") or ""
                    item["notes"] = f"{existing_notes}\n{notes}".strip()

                matched = JobApplicationRecord.model_validate(item)
                all_records[idx] = item
                break

        if matched:
            self._save_all_records(all_records)
            print(f"[JobTrackerManager] Marked application '{matched.company} - {matched.position}' as APPLIED.")

        return matched

    def list_applications(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None
    ) -> List[JobApplicationRecord]:
        """Returns all tracked job applications matching optional status or company filters."""
        all_data = self._load_all_records()
        results = []
        for d in all_data:
            rec = JobApplicationRecord.model_validate(d)
            if status and rec.status.lower() != status.lower():
                continue
            if company and company.lower() not in rec.company.lower():
                continue
            results.append(rec)
        return results

    def get_application(self, application_id: str) -> Optional[JobApplicationRecord]:
        """Retrieves a specific application record by application_id."""
        for rec in self.list_applications():
            if rec.application_id.lower() == application_id.strip().lower():
                return rec
        return None

    def get_latest_application(self) -> Optional[JobApplicationRecord]:
        """Returns the most recent job application record."""
        apps = self.list_applications()
        return apps[-1] if apps else None

    def to_prompt_context(self, max_records: int = 50) -> str:
        """
        Formats tracked job applications into a clean, structured context string
        for Kaalu's LLM reasoning and conversational responses.
        """
        apps = self.list_applications()
        if not apps:
            return ""

        recent_apps = list(reversed(apps))[:max_records]
        lines = [
            f"[TRACKED JOB APPLICATIONS DATABASE (Total: {len(apps)})]"
        ]
        for idx, app in enumerate(recent_apps, 1):
            applied_str = app.applied_date or app.created_date or "N/A"
            res_name = app.resume_filename or (Path(app.resume_path).name if app.resume_path else "Not specified")
            loc_str = f" ({app.location})" if app.location else ""
            url_str = f" | Job URL: {app.job_url}" if app.job_url else ""
            notes_str = f" | Notes: {app.notes}" if app.notes else ""
            tmpl_str = f" (Template: {app.resume_snapshot.template})" if app.resume_snapshot and app.resume_snapshot.template else ""

            lines.append(
                f"{idx}. Company: {app.company}{loc_str} | Role: {app.position}\n"
                f"   Status: {app.status.upper()} | Date: {applied_str}{url_str}\n"
                f"   Tailored Resume: {res_name}{tmpl_str}{notes_str}"
            )
            if app.resume_snapshot and app.resume_snapshot.skills:
                skills_prev = ", ".join(app.resume_snapshot.skills[:6])
                lines.append(f"   Target Skills: {skills_prev}")
            if app.job_description:
                jd_snippet = app.job_description[:160].replace("\n", " ").strip()
                lines.append(f"   JD Snippet: {jd_snippet}...")

        return "\n".join(lines)
