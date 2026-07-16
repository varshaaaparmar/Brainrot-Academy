import os
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
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


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login")
async def google_login(response: Response):
    """Redirect the browser to Google's consent screen."""
    import secrets
    from urllib.parse import urlencode

    client_id = os.environ["GOOGLE_CLIENT_ID"]
    redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    redirect = RedirectResponse(url=url)
    # short-lived state cookie for CSRF protection, checked in the callback
    redirect.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=_secure_cookies(),
        samesite="lax",
        max_age=600,
        path="/",
    )
    return redirect


@router.get("/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """Google redirects here with ?code=...&state=... after the user approves access."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")

    if error or not code:
        return RedirectResponse(url=f"{frontend_url}/login?error=google_auth_failed")

    expected_state = request.cookies.get("oauth_state")
    if not expected_state or state != expected_state:
        return RedirectResponse(url=f"{frontend_url}/login?error=invalid_state")

    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
    redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]

    async with httpx.AsyncClient(timeout=15) as c:
        token_resp = await c.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            return RedirectResponse(url=f"{frontend_url}/login?error=google_token_exchange_failed")
        tokens = token_resp.json()

        userinfo_resp = await c.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(url=f"{frontend_url}/login?error=google_userinfo_failed")
        profile = userinfo_resp.json()

    db = request.app.state.db
    email = profile["email"].lower().strip()
    name = profile.get("name") or email.split("@")[0]
    picture = profile.get("picture") or ""

    user = await db.users.find_one({"email": email})
    if not user:
        user = {
            "user_id": gen_id("user"),
            "email": email,
            "password_hash": "",  # google user, no password login
            "name": name,
            "role": "student",
            "bio": "",
            "avatar_url": picture,
            "created_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(user)
    elif not user.get("avatar_url") and picture:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"avatar_url": picture}})
        user["avatar_url"] = picture

    jwt_token = create_access_token(user["user_id"], email)
    redirect = RedirectResponse(url=f"{frontend_url}/dashboard")
    _set_jwt_cookie(redirect, jwt_token)
    redirect.delete_cookie("oauth_state", path="/")
    return redirect