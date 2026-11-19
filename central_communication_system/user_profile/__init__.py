"""
User Profile Module for Project Kaalu.
Provides schemas, persistence, and automated resume PDF extraction for centralized user awareness.
"""

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
from user_profile.generator import ProfileGenerator
from user_profile.web_ui import render_upload_page, render_edit_page, build_user_profile_from_dict

__all__ = [
    "BasicDetails",
    "Certification",
    "Education",
    "Experience",
    "Project",
    "Skills",
    "UserProfile",
    "UserURLs",
    "ProfileManager",
    "DEFAULT_PROFILE_PATH",
    "ProfileGenerator",
    "render_upload_page",
    "render_edit_page",
    "build_user_profile_from_dict",
]
