"""
Firebase Authentication dependency. Verifies the bearer ID token sent by the
React frontend and returns the decoded claims (uid, email, etc.).
"""
from __future__ import annotations

import logging

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth, credentials

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_initialized = False


def _ensure_initialized() -> None:
    global _initialized
    if not _initialized:
        if not firebase_admin._apps:
            # In Cloud Run, Application Default Credentials are used automatically.
            firebase_admin.initialize_app(credentials.ApplicationDefault(), {
                "projectId": settings.firebase_project_id or settings.project_id,
            })
        _initialized = True


async def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    _ensure_initialized()

    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded
    except Exception as exc:  # noqa: BLE001
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def _is_admin(user: dict) -> bool:
    """
    A user is an admin if their Firebase ID token carries the `admin: true`
    custom claim (set via `scripts/set_admin_claim.py`), or, as a fallback for
    initial bootstrapping, if their verified email is in ADMIN_EMAILS.
    """
    if user.get("admin") is True:
        return True
    email = (user.get("email") or "").lower()
    return bool(email) and user.get("email_verified") and email in settings.admin_email_list


async def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    if not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
