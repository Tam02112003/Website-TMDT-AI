from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import exceptions
import asyncpg
from typing import Optional
from fastapi import Depends, HTTPException
from core.settings import settings
import hashlib

async def get_user_by_id(db: asyncpg.Connection, user_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, email, username, password, is_admin FROM users WHERE id = $1", user_id)
    if row:
        return dict(row)
    return None

async def get_user_by_email(db: asyncpg.Connection, email: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, email, username, password, is_admin FROM users WHERE email = $1", email)
    if row:
        return dict(row)
    return None

async def get_user_by_username(db: asyncpg.Connection, username: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, email, username, password, is_admin FROM users WHERE username = $1", username)
    if row:
        return dict(row)
    return None

async def create_user(db: asyncpg.Connection, email: str, username: str, is_admin: bool = False) -> dict:
    row = await db.fetchrow("INSERT INTO users (email, username, is_admin) VALUES ($1, $2, $3) RETURNING id, email, username, is_admin", email, username, is_admin)
    return dict(row)

async def login_or_create_google_user(db: asyncpg.Connection, email: str) -> dict:
    db_user = await get_user_by_email(db, email)
    username = email.split('@')[0]
    if not db_user:
        db_user = await create_user(db, email, username=username)
    elif not db_user.get("username"):
        await db.execute("UPDATE users SET username=$1 WHERE email=$2", username, email)
        db_user = await get_user_by_email(db, email)
    return db_user

async def register_user(db: asyncpg.Connection, email: str, username: str, password: str) -> dict:
    if await get_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if await get_user_by_username(db, username):
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed = hashlib.sha256(password.encode()).hexdigest()
    row = await db.fetchrow("INSERT INTO users (email, username, password, is_admin) VALUES ($1, $2, $3, $4) RETURNING id, email, username, is_admin", email, username, hashed, False)
    return dict(row)

async def authenticate_user(db: asyncpg.Connection, email: str, password: str) -> Optional[dict]:
    user_row = await get_user_by_email(db, email)
    if not user_row or not user_row.get("password"):
        return None
    hashed = hashlib.sha256(password.encode()).hexdigest()
    if hashed != user_row["password"]:
        return None
    return user_row

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.JWT.SECRET.get_secret_value(), algorithms=["HS256"])
        return payload
    except exceptions.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_admin(user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user