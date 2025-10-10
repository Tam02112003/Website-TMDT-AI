from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
import asyncpg
from starlette.requests import Request
import httpx
import jwt
from datetime import datetime, timedelta
from core.pkgs import database
from crud import user
from schemas.schemas import RegisterRequest, LoginRequest
from core.settings import settings
from core.kafka.kafka_client import producer
import json
from core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/login/google")
async def login_google():
    params = {
        "client_id": settings.GOOGLE.CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": settings.GOOGLE.REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent"
    }
    async with httpx.AsyncClient() as client:
        request = client.build_request('GET', settings.GOOGLE.OAUTH2_URL, params=params)
        return RedirectResponse(request.url)

@router.get("/callback")
async def callback(request: Request, db: asyncpg.Connection = Depends(database.get_db)):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    data = {
        "code": code,
        "client_id": settings.GOOGLE.CLIENT_ID,
        "client_secret": settings.GOOGLE.CLIENT_SECRET.get_secret_value(),
        "redirect_uri": settings.GOOGLE.REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(settings.GOOGLE.TOKEN_URL, data=data)
        token_json = token_resp.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token")
        userinfo_resp = await client.get(settings.GOOGLE.USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        userinfo = userinfo_resp.json()
    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email found")

    db_user = await user.login_or_create_google_user(db, email)

    payload = {
        "sub": email,
        "id": db_user["id"],
        "username": db_user["username"],
        "is_admin": db_user["is_admin"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(payload, settings.JWT.SECRET.get_secret_value(), algorithm="HS256")

    # Publish Kafka event for successful Google OAuth callback
    event_data = {
        "user_email": email,
        "event_type": "google_oauth_success",
        "timestamp": datetime.now().isoformat(),
        "ip_address": request.client.host
    }
    producer.send("auth_events", json.dumps(event_data).encode('utf-8'))

    # Redirect to frontend with token
    frontend_url = f"{settings.FRONTEND.URL}/auth/google/callback?token={token}"
    return RedirectResponse(url=frontend_url)


@router.post("/register")
@limiter.limit("5/minute")
async def register(data: RegisterRequest, request: Request, db: asyncpg.Connection = Depends(database.get_db)):
    new_user = await user.register_user(db, data.email, data.username, data.password)

    # Publish Kafka event for successful registration
    event_data = {
        "user_email": data.email,
        "event_type": "user_registered",
        "timestamp": datetime.now().isoformat(),
        "ip_address": request.client.host
    }
    producer.send("auth_events", json.dumps(event_data).encode('utf-8'))

    return new_user


@router.post("/login")
@limiter.limit("5/minute")
async def login_local(data: LoginRequest, request: Request, db: asyncpg.Connection = Depends(database.get_db)):
    user_row = await user.authenticate_user(db, data.email, data.password)
    if not user_row:
        # Publish Kafka event for failed login
        event_data = {
            "user_email": data.email,
            "event_type": "login_failed",
            "timestamp": datetime.now().isoformat(),
            "ip_address": request.client.host
        }
        producer.send("auth_events", json.dumps(event_data).encode('utf-8'))
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = {
        "sub": data.email,
        "id": user_row["id"],
        "username": user_row["username"],
        "is_admin": user_row["is_admin"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(payload, settings.JWT.SECRET.get_secret_value(), algorithm="HS256")

    # Publish Kafka event for successful login
    event_data = {
        "user_email": data.email,
        "event_type": "login_success",
        "timestamp": datetime.now().isoformat(),
        "ip_address": request.client.host
    }
    producer.send("auth_events", json.dumps(event_data).encode('utf-8'))

    return {"access_token": token, "token_type": "bearer"}
