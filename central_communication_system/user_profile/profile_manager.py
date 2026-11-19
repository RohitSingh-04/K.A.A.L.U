import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from user_profile.schemas import UserProfile


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "user_profile.json"


class ProfileManager:
    """
    Centralized manager for loading, persisting, and querying the standard UserProfile.
    Accessible across all Project Kaalu agents (Kaalu, David, Faulkner, RGS Hub).
    """

    _instance: Optional["ProfileManager"] = None

    def __init__(self, profile_path: Optional[Path] = None):
        if profile_path is not None:
            self.profile_path = Path(profile_path)
        else:
            self.profile_path = DEFAULT_PROFILE_PATH

        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self._cached_profile: Optional[UserProfile] = None
        self._last_mtime: float = 0.0

    @classmethod
    def get_instance(cls, profile_path: Optional[Path] = None) -> "ProfileManager":
        """Singleton accessor for convenience."""
        if cls._instance is None:
            cls._instance = ProfileManager(profile_path=profile_path)
        return cls._instance

    def has_profile(self) -> bool:
        """Checks if a valid user profile JSON exists on disk."""
        return self.profile_path.exists() and self.profile_path.stat().st_size > 5

    def load_profile(self, force_reload: bool = False) -> Optional[UserProfile]:
        """
        Loads the UserProfile from disk with automatic mtime caching.
        Returns None if no profile has been generated yet.
        """
        if not self.has_profile():
            self._cached_profile = None
            return None

        current_mtime = self.profile_path.stat().st_mtime
        if not force_reload and self._cached_profile is not None and current_mtime == self._last_mtime:
            return self._cached_profile

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cached_profile = UserProfile.model_validate(data)
            self._last_mtime = current_mtime
            return self._cached_profile
        except Exception as e:
            print(f"[ProfileManager Warning] Failed to load user profile: {e}")
            return None

    def save_profile(self, profile: UserProfile) -> Path:
        """Atomically saves the UserProfile to disk."""
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.profile_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
        temp_path.replace(self.profile_path)
        self._cached_profile = profile
        self._last_mtime = self.profile_path.stat().st_mtime
        print(f"[ProfileManager] Successfully persisted User Profile to: {self.profile_path}")
        return self.profile_path

    def get_summary(self) -> str:
        """Returns concise context string for injection into LLM prompts."""
        profile = self.load_profile()
        if not profile:
            return "No verified user profile loaded."
        return profile.to_prompt_context()

    def match_form_field(self, field_name: str) -> Optional[str]:
        """
        Intelligently resolves a form input field label or name (e.g., 'Candidate Email', 'Phone_Number', 'LinkedIn URL')
        to the appropriate user profile value for David or Faulkner form filling.
        """
        profile = self.load_profile()
        if not profile:
            return None

        form_map = profile.get_form_fill_map()
        cleaned_field = re.sub(r"[^a-zA-Z0-9]", " ", field_name).lower().strip()

        # Direct key match
        if cleaned_field in form_map:
            return form_map[cleaned_field]

        # Semantic substring heuristics
        if any(w in cleaned_field for w in ("first name", "firstname", "given name", "fname")):
            return form_map.get("first_name")
        if any(w in cleaned_field for w in ("last name", "lastname", "surname", "family name", "lname")):
            return form_map.get("last_name")
        if any(w in cleaned_field for w in ("full name", "fullname", "name")):
            return form_map.get("full_name")
        if any(w in cleaned_field for w in ("email", "mail")):
            return form_map.get("email")
        if any(w in cleaned_field for w in ("phone", "mobile", "contact", "tel")):
            return form_map.get("phone")
        if "linkedin" in cleaned_field:
            return form_map.get("linkedin")
        if "github" in cleaned_field:
            return form_map.get("github")
        if any(w in cleaned_field for w in ("portfolio", "website", "url", "link")):
            return form_map.get("portfolio") or form_map.get("website")
        if any(w in cleaned_field for w in ("city", "location", "address")):
            return form_map.get("location")
        if any(w in cleaned_field for w in ("company", "current employer", "employer", "organization")):
            return form_map.get("company")
        if any(w in cleaned_field for w in ("role", "title", "position", "designation")):
            return form_map.get("role")
        if any(w in cleaned_field for w in ("university", "school", "college", "institution")):
            return form_map.get("school")
        if any(w in cleaned_field for w in ("degree", "qualification", "education")):
            return form_map.get("degree")
        if "skills" in cleaned_field:
            return form_map.get("skills")

        return None
