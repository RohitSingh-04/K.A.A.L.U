"""
Device Credentials Security Manager for Project Kaalu.
Provides machine-bound, hardware-backed encryption (Windows DPAPI) for phone unlock
credentials (PIN / password) so Kaalu can unlock mobile devices without exposing
plaintext credentials or requiring repeated manual inputs.
"""

import base64
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

DEFAULT_CREDENTIALS_FILE = Path(__file__).resolve().parent.parent / "data" / "device_credentials.json"


# Win32 DPAPI Structs & Functions
class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte))
    ]


def _is_win32_dpapi_available() -> bool:
    """Checks whether native Windows DPAPI (CryptProtectData) is available."""
    return os.name == "nt" and hasattr(ctypes, "windll") and hasattr(ctypes.windll, "crypt32")


def _dpapi_encrypt(plaintext: str) -> str:
    """Encrypts plaintext string using Windows Data Protection API (DPAPI)."""
    b_data = plaintext.encode("utf-8")
    in_blob = DATA_BLOB(
        len(b_data),
        ctypes.cast(ctypes.create_string_buffer(b_data), ctypes.POINTER(ctypes.c_byte))
    )
    out_blob = DATA_BLOB()
    # CryptProtectData: ties encryption to the current logged-in Windows user account and hardware
    res = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "KaaluPhoneCredentials",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob)
    )
    if not res:
        raise RuntimeError("Windows DPAPI CryptProtectData failed.")

    out_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return base64.b64encode(out_bytes).decode("ascii")


def _dpapi_decrypt(b64_ciphertext: str) -> str:
    """Decrypts base64-encoded DPAPI ciphertext using Windows CryptUnprotectData."""
    cipher_bytes = base64.b64decode(b64_ciphertext.encode("ascii"))
    in_blob = DATA_BLOB(
        len(cipher_bytes),
        ctypes.cast(ctypes.create_string_buffer(cipher_bytes), ctypes.POINTER(ctypes.c_byte))
    )
    out_blob = DATA_BLOB()
    res = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob)
    )
    if not res:
        raise RuntimeError("Windows DPAPI CryptUnprotectData failed.")

    out_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return out_bytes.decode("utf-8")


def _fallback_encrypt(plaintext: str) -> str:
    """
    Secure machine-bound fallback for non-Windows platforms or test environments.
    Uses machine identity + user salt with HMAC-SHA256 keystream.
    """
    machine_id = os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", "kaalu_host")
    user_id = os.environ.get("USERNAME", "") or os.environ.get("USER", "kaalu_user")
    salt = f"{machine_id}:{user_id}:kaalu_v2_phone_sec".encode("utf-8")
    key = hashlib.sha256(salt).digest()

    plain_bytes = plaintext.encode("utf-8")
    keystream = hmac.new(key, b"device_unlock_keystream", hashlib.sha256).digest()
    
    # Simple XOR keystream expansion
    while len(keystream) < len(plain_bytes):
        keystream += hmac.new(key, keystream, hashlib.sha256).digest()

    cipher_bytes = bytes([b ^ keystream[i] for i, b in enumerate(plain_bytes)])
    tag = hmac.new(key, cipher_bytes, hashlib.sha256).digest()[:16]
    return base64.b64encode(tag + cipher_bytes).decode("ascii")


def _fallback_decrypt(b64_ciphertext: str) -> str:
    """Decrypts fallback machine-bound ciphertext."""
    machine_id = os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", "kaalu_host")
    user_id = os.environ.get("USERNAME", "") or os.environ.get("USER", "kaalu_user")
    salt = f"{machine_id}:{user_id}:kaalu_v2_phone_sec".encode("utf-8")
    key = hashlib.sha256(salt).digest()

    raw = base64.b64decode(b64_ciphertext.encode("ascii"))
    tag = raw[:16]
    cipher_bytes = raw[16:]

    expected_tag = hmac.new(key, cipher_bytes, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Decryption authentication verification failed.")

    keystream = hmac.new(key, b"device_unlock_keystream", hashlib.sha256).digest()
    while len(keystream) < len(cipher_bytes):
        keystream += hmac.new(key, keystream, hashlib.sha256).digest()

    plain_bytes = bytes([b ^ keystream[i] for i, b in enumerate(cipher_bytes)])
    return plain_bytes.decode("utf-8")


class PhoneCredentialsManager:
    """
    Manages safe, encrypted storage of phone unlock PINs / passwords.
    Plaintext secrets are NEVER written to disk and NEVER returned in status queries.
    """

    _instance: Optional["PhoneCredentialsManager"] = None

    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        self.storage_path = Path(storage_path) if storage_path else DEFAULT_CREDENTIALS_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls, storage_path: Optional[Union[str, Path]] = None) -> "PhoneCredentialsManager":
        if cls._instance is None or storage_path is not None:
            cls._instance = PhoneCredentialsManager(storage_path=storage_path)
        return cls._instance

    def _load_data(self) -> Dict[str, Any]:
        """Loads encrypted credentials record from disk."""
        if not self.storage_path.exists():
            return {"credentials": {}}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"credentials": {}}

    def _save_data(self, data: Dict[str, Any]) -> None:
        """Saves encrypted credentials record to disk."""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_pin(self, pin: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Encrypts and stores the phone PIN/password.
        Ties encryption to the current machine & OS user account.
        """
        if not pin or not str(pin).strip():
            return {"success": False, "error": "PIN cannot be empty."}

        clean_pin = str(pin).strip()

        if _is_win32_dpapi_available():
            cipher = _dpapi_encrypt(clean_pin)
            method = "win32_dpapi"
        else:
            cipher = _fallback_encrypt(clean_pin)
            method = "machine_bound_hmac"

        now_iso = datetime.now().isoformat()
        entry = {
            "ciphertext": cipher,
            "cipher_method": method,
            "pin_length": len(clean_pin),
            "updated_at": now_iso
        }

        data = self._load_data()
        creds = data.setdefault("credentials", {})
        # Always store as default, and also under specific device serial if supplied
        creds["default"] = entry
        if serial:
            creds[serial] = entry

        self._save_data(data)

        return {
            "success": True,
            "message": "Phone unlock credentials encrypted and saved successfully.",
            "configured": True,
            "cipher_method": method,
            "pin_length": len(clean_pin),
            "device_serial": serial or "default",
            "updated_at": now_iso
        }

    def get_pin(self, serial: Optional[str] = None) -> Optional[str]:
        """
        Retrieves and decrypts the phone PIN for device unlocking.
        Returns plaintext PIN string, or None if no credentials configured.
        """
        data = self._load_data()
        creds = data.get("credentials", {})
        if not creds:
            return None

        entry = None
        if serial and serial in creds:
            entry = creds[serial]
        elif "default" in creds:
            entry = creds["default"]
        elif creds:
            # Pick first available configured device
            entry = next(iter(creds.values()))

        if not entry or not entry.get("ciphertext"):
            return None

        cipher = entry["ciphertext"]
        method = entry.get("cipher_method", "win32_dpapi")

        try:
            if method == "win32_dpapi" and _is_win32_dpapi_available():
                return _dpapi_decrypt(cipher)
            return _fallback_decrypt(cipher)
        except Exception as e:
            # If win32_dpapi failed or method fell back, try the alternative
            try:
                return _fallback_decrypt(cipher)
            except Exception:
                raise RuntimeError(f"Failed to decrypt stored credentials: {e}")

    def get_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns security configuration status for API and UI rendering.
        CRITICAL: Never exposes plaintext PIN or ciphertext.
        """
        data = self._load_data()
        creds = data.get("credentials", {})

        entry = None
        target_key = "default"
        if serial and serial in creds:
            entry = creds[serial]
            target_key = serial
        elif "default" in creds:
            entry = creds["default"]
        elif creds:
            target_key = next(iter(creds.keys()))
            entry = creds[target_key]

        if entry and entry.get("ciphertext"):
            return {
                "configured": True,
                "cipher_method": entry.get("cipher_method", "win32_dpapi"),
                "pin_length": entry.get("pin_length", 0),
                "device_serial": target_key,
                "updated_at": entry.get("updated_at")
            }

        return {
            "configured": False,
            "cipher_method": "win32_dpapi" if _is_win32_dpapi_available() else "machine_bound_hmac",
            "pin_length": 0,
            "device_serial": serial or "default",
            "updated_at": None
        }

    def clear_pin(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Removes stored credentials for the device or all devices."""
        data = self._load_data()
        creds = data.get("credentials", {})

        if not serial or serial == "default":
            data["credentials"] = {}
        else:
            creds.pop(serial, None)
            if not creds:
                data["credentials"] = {}

        self._save_data(data)
        return {
            "success": True,
            "message": "Phone unlock credentials cleared successfully.",
            "configured": False
        }
