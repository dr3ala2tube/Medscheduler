"""
Firebase REST API service for MedScheduler.
Handles Authentication, Firestore data sync, and Storage file uploads.

Uses ONLY Python's built-in urllib — no third-party packages required.
Works out of the box on any standard Python 3 installation.
"""

from __future__ import annotations

import json
import os
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional

# ── Firebase project config ───────────────────────────────────────────────────
_API_KEY        = "AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8"
_PROJECT_ID     = "medscheduler-e0853"
_STORAGE_BUCKET = "medscheduler-e0853.firebasestorage.app"

_AUTH_BASE    = "https://identitytoolkit.googleapis.com/v1"
_TOKEN_BASE   = "https://securetoken.googleapis.com/v1"
_FS_BASE      = (
    f"https://firestore.googleapis.com/v1/projects/{_PROJECT_ID}"
    f"/databases/(default)/documents"
)
_STORAGE_BASE = f"https://firebasestorage.googleapis.com/v0/b/{_STORAGE_BUCKET}/o"


# ── Exceptions ────────────────────────────────────────────────────────────────

class FirebaseAuthError(Exception):
    """Raised for authentication or token errors."""


class FirebaseNetworkError(Exception):
    """Raised when a network request fails."""


# ── Low-level HTTP helpers (urllib only) ─────────────────────────────────────

def _http(method: str, url: str, *,
          body: Optional[bytes] = None,
          headers: Optional[Dict] = None,
          timeout: int = 15) -> Dict:
    """
    Perform an HTTP request using urllib and return the parsed JSON body.
    Raises FirebaseNetworkError on connection problems.
    Raises Exception with the raw response text on non-2xx status.
    """
    req = urllib.request.Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return json.loads(raw)
        except Exception:
            raise Exception(f"HTTP {exc.code}: {raw[:300].decode(errors='replace')}")
    except urllib.error.URLError as exc:
        raise FirebaseNetworkError(f"Network error: {exc.reason}") from exc
    return json.loads(raw)


def _post_json(url: str, payload: Dict, headers: Optional[Dict] = None,
               timeout: int = 15) -> Dict:
    body = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    return _http("POST", url, body=body, headers=hdrs, timeout=timeout)


def _patch_json(url: str, payload: Dict, headers: Optional[Dict] = None,
                timeout: int = 20) -> Dict:
    body = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    return _http("PATCH", url, body=body, headers=hdrs, timeout=timeout)


def _get_json(url: str, headers: Optional[Dict] = None, timeout: int = 12) -> Dict:
    return _http("GET", url, headers=headers, timeout=timeout)


def _post_form(url: str, fields: Dict, timeout: int = 12) -> Dict:
    body = urllib.parse.urlencode(fields).encode()
    return _http("POST", url, body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                 timeout=timeout)


# ── Main service class ────────────────────────────────────────────────────────

class FirebaseService:
    """
    Python wrapper around Firebase REST APIs (Auth, Firestore, Storage).
    No external dependencies — uses only Python's built-in urllib.

    Usage:
        from firebase_service import firebase, FirebaseAuthError

        firebase.sign_in("user@example.com", "password123")
        firebase.save_app_data({"docs": [...], "asgn": {...}, ...})
        data = firebase.load_app_data()
        url  = firebase.upload_file("/path/to/export.xlsx")
    """

    def __init__(self) -> None:
        self.id_token:      Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.uid:           Optional[str] = None
        self.email:         Optional[str] = None
        self._expiry:       float = 0.0
        self._lock          = threading.Lock()

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def is_signed_in(self) -> bool:
        return self.uid is not None

    # ── Auth ────────────────────────────────────────────────────────────────

    def sign_in(self, email: str, password: str) -> Dict:
        """Sign in with email/password. Returns {"uid", "email"}."""
        data = self._post_auth(
            "signInWithPassword",
            {"email": email, "password": password, "returnSecureToken": True},
        )
        self._store_tokens(data)
        return {"uid": self.uid, "email": self.email}

    def sign_up(self, email: str, password: str) -> Dict:
        """Create a new account. Returns {"uid", "email"}."""
        data = self._post_auth(
            "signUp",
            {"email": email, "password": password, "returnSecureToken": True},
        )
        self._store_tokens(data)
        return {"uid": self.uid, "email": self.email}

    def sign_out(self) -> None:
        """Clear local auth state."""
        self.id_token = self.refresh_token = self.uid = self.email = None
        self._expiry = 0.0

    # ── Firestore ────────────────────────────────────────────────────────────

    def save_app_data(self, payload: Dict) -> None:
        """Persist the full app state to Firestore at users/{uid}/app_data/main."""
        url  = f"{_FS_BASE}/users/{self.uid}/app_data/main"
        body = {"fields": _py_to_fs(payload)["mapValue"]["fields"]}
        _patch_json(url, body, headers=self._auth_headers(), timeout=25)

    def load_app_data(self) -> Optional[Dict]:
        """Load app state from Firestore. Returns None if nothing saved yet."""
        url = f"{_FS_BASE}/users/{self.uid}/app_data/main"
        data = _get_json(url, headers=self._auth_headers(), timeout=15)
        if "error" in data:
            code = data["error"].get("code", 0)
            if code == 404:
                return None
            raise Exception(data["error"].get("message", "Firestore load error"))
        if "fields" not in data:
            return None
        return _fs_to_py({"mapValue": {"fields": data["fields"]}})

    # ── Storage ──────────────────────────────────────────────────────────────

    def upload_file(self, local_path: str, remote_name: Optional[str] = None) -> str:
        """Upload a local file to Firebase Storage. Returns download URL."""
        if remote_name is None:
            remote_name = os.path.basename(local_path)

        remote_path = f"users/{self.uid}/exports/{remote_name}"
        encoded     = urllib.parse.quote(remote_path, safe="")

        ext = os.path.splitext(local_path)[1].lower()
        content_type = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls":  "application/vnd.ms-excel",
            ".pdf":  "application/pdf",
        }.get(ext, "application/octet-stream")

        with open(local_path, "rb") as fh:
            raw = fh.read()

        upload_url = f"{_STORAGE_BASE}?uploadType=media&name={encoded}"
        hdrs = {**self._auth_headers(), "Content-Type": content_type}
        result = _http("POST", upload_url, body=raw, headers=hdrs, timeout=60)

        token = result.get("downloadTokens", "")
        return (
            f"https://firebasestorage.googleapis.com/v0/b/{_STORAGE_BUCKET}"
            f"/o/{encoded}?alt=media&token={token}"
        )

    def list_files(self) -> List[Dict]:
        """List exported files for the current user."""
        prefix  = f"users/{self.uid}/exports/"
        enc     = urllib.parse.quote(prefix, safe="")
        url     = f"{_STORAGE_BASE}?prefix={enc}"
        try:
            data = _get_json(url, headers=self._auth_headers(), timeout=12)
        except Exception:
            return []
        files = []
        for item in data.get("items", []):
            raw_name = item.get("name", "")
            short    = raw_name.rsplit("/", 1)[-1]
            size_b   = int(item.get("size", 0))
            updated  = item.get("timeCreated", "")[:10]
            files.append({
                "name":    short,
                "full":    raw_name,
                "size_kb": round(size_b / 1024, 1),
                "updated": updated,
            })
        return files

    def download_file(self, remote_name: str, local_path: str) -> None:
        """Download a Storage file to a local path."""
        remote_path = f"users/{self.uid}/exports/{remote_name}"
        encoded     = urllib.parse.quote(remote_path, safe="")
        url         = f"{_STORAGE_BASE}/{encoded}?alt=media"

        req = urllib.request.Request(url)
        for k, v in self._auth_headers().items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
        except urllib.error.HTTPError as exc:
            raise Exception(f"Download error {exc.code}: {exc.read()[:200].decode(errors='replace')}")
        except urllib.error.URLError as exc:
            raise FirebaseNetworkError(f"Download failed: {exc.reason}") from exc

        with open(local_path, "wb") as fh:
            fh.write(content)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _post_auth(self, endpoint: str, payload: Dict) -> Dict:
        url  = f"{_AUTH_BASE}/accounts:{endpoint}?key={_API_KEY}"
        data = _post_json(url, payload, timeout=12)
        if "error" in data:
            raw = data["error"].get("message", "Authentication failed")
            raise FirebaseAuthError(_friendly_auth_msg(raw))
        return data

    def _store_tokens(self, data: Dict) -> None:
        self.id_token      = data.get("idToken")
        self.refresh_token = data.get("refreshToken")
        self.uid           = data.get("localId")
        self.email         = data.get("email")
        self._expiry       = time.time() + int(data.get("expiresIn", 3600)) - 60

    def _refresh_id_token(self) -> None:
        url  = f"{_TOKEN_BASE}/token?key={_API_KEY}"
        data = _post_form(url, {
            "grant_type":    "refresh_token",
            "refresh_token": self.refresh_token or "",
        })
        if "error" in data:
            raise FirebaseAuthError("Session expired — please sign in again.")
        self.id_token      = data.get("id_token")
        self.refresh_token = data.get("refresh_token")
        self._expiry       = time.time() + int(data.get("expires_in", 3600)) - 60

    def _ensure_token(self) -> None:
        with self._lock:
            if not self.is_signed_in:
                raise FirebaseAuthError("Not signed in.")
            if time.time() >= self._expiry:
                self._refresh_id_token()

    def _auth_headers(self) -> Dict:
        self._ensure_token()
        return {"Authorization": f"Bearer {self.id_token}"}


# ── Firestore type conversion ────────────────────────────────────────────────

def _py_to_fs(value: Any) -> Dict:
    """Convert a Python value to a Firestore REST typed-value dict."""
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_py_to_fs(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: _py_to_fs(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def _fs_to_py(value: Dict) -> Any:
    """Convert a Firestore REST typed-value dict to a plain Python value."""
    if "nullValue"    in value: return None
    if "booleanValue" in value: return value["booleanValue"]
    if "integerValue" in value: return int(value["integerValue"])
    if "doubleValue"  in value: return float(value["doubleValue"])
    if "stringValue"  in value: return value["stringValue"]
    if "arrayValue"   in value:
        return [_fs_to_py(v) for v in value["arrayValue"].get("values", [])]
    if "mapValue"     in value:
        return {k: _fs_to_py(v) for k, v in value["mapValue"].get("fields", {}).items()}
    return None


# ── Friendly auth error messages ──────────────────────────────────────────────

_AUTH_MSG_MAP = {
    "EMAIL_NOT_FOUND":             "No account found with that email address.",
    "INVALID_PASSWORD":            "Incorrect password. Please try again.",
    "USER_DISABLED":               "This account has been disabled.",
    "EMAIL_EXISTS":                "An account with that email already exists.",
    "WEAK_PASSWORD":               "Password must be at least 6 characters.",
    "INVALID_EMAIL":               "Please enter a valid email address.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many failed attempts. Please try again later.",
    "INVALID_LOGIN_CREDENTIALS":   "Invalid email or password.",
    "OPERATION_NOT_ALLOWED":       "Email/password sign-in is not enabled in Firebase Console.\nGo to: Authentication → Sign-in method → Email/Password → Enable.",
    "PASSWORD_LOGIN_DISABLED":     "Email/password sign-in is not enabled in Firebase Console.\nGo to: Authentication → Sign-in method → Email/Password → Enable.",
}


def _friendly_auth_msg(raw: str) -> str:
    for key, friendly in _AUTH_MSG_MAP.items():
        if key in raw:
            return friendly
    return raw


# ── Module-level singleton ────────────────────────────────────────────────────
firebase = FirebaseService()
