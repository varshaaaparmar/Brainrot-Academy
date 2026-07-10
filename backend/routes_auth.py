import os
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from auth import hash_password, verify_password, create_access_token, get_current_user
from models import RegisterIn, LoginIn, gen_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _secure_cookies() -> bool:
    return os.environ.get("COOKIE_SECURE", "true").lower() == "true"


def _set_jwt_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_secure_cookies(),
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=_secure_cookies(),
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


def _user_public(user: dict) -> dict:
    user = dict(user)
    user.pop("_id", None)
    user.pop("password_hash", None)
    return user


@router.post("/register")
async def register(payload: RegisterIn, request: Request, response: Response):
    db = request.app.state.db
    email = payload.email.lower().strip()
    if payload.role not in ("student", "instructor"):
        raise HTTPException(status_code=400, detail="Role must be student or instructor")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = {
        "user_id": gen_id("user"),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "role": payload.role,
        "bio": "",
        "avatar_url": "",
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(user_doc)
    token = create_access_token(user_doc["user_id"], email)
    _set_jwt_cookie(response, token)
    return _user_public(user_doc)


@router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response):
    db = request.app.state.db
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["user_id"], email)
    _set_jwt_cookie(response, token)
    return _user_public(user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password():
    # Avoid account enumeration. Wire this to an email provider before enabling real resets.
    return {"ok": True, "message": "If an account exists, a reset link will be sent."}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _user_public(user)


@router.post("/google/session")
async def google_session(request: Request, response: Response):
    """Exchange Emergent session_id (from URL fragment) for a backend session_token."""
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-ID")
    db = request.app.state.db
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = r.json()
    email = data["email"].lower().strip()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture") or ""
    session_token = data["session_token"]

    user = await db.users.find_one({"email": email})
    if not user:
        user = {
            "user_id": gen_id("user"),
            "email": email,
            "password_hash": "",  # google user, no password
            "name": name,
            "role": "student",
            "bio": "",
            "avatar_url": picture,
            "created_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(user)
    else:
        # update avatar if missing
        if not user.get("avatar_url") and picture:
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"avatar_url": picture}})
            user["avatar_url"] = picture

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "session_token": session_token,
            "user_id": user["user_id"],
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    _set_session_cookie(response, session_token)
    return _user_public(user)
