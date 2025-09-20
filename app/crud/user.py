from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import exceptions
import asyncpg
from typing import Optional
from fastapi import Depends, HTTPException
from core.settings import settings
import hashlib
import random
import time
from core.redis.redis_client import get_redis_client

async def get_user_by_id(db: asyncpg.Connection, user_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, email, username, password, is_admin, phone_number, avatar_url FROM users WHERE id = $1", user_id)
    if row:
        return dict(row)
    return None

async def get_user_by_email(db: asyncpg.Connection, email: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, email, username, password, is_admin, phone_number, avatar_url FROM users WHERE email = $1", email)
    if row:
        return dict(row)
    return None

async def get_user_by_username(db: asyncpg.Connection, username: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, email, username, password, is_admin, phone_number, avatar_url FROM users WHERE username = $1", username)
    if row:
        return dict(row)
    return None

async def generate_and_store_otp(user_id: int, phone_number: str) -> str:
    redis = await get_redis_client()
    otp = str(random.randint(100000, 999999)) # Generate a 6-digit OTP
    key = f"otp:{user_id}:{phone_number}"
    await redis.set(key, otp, ex=300) # OTP expires in 5 minutes (300 seconds)
    return otp

async def verify_otp(user_id: int, phone_number: str, otp: str) -> bool:
    redis = await get_redis_client()
    key = f"otp:{user_id}:{phone_number}"
    stored_otp = await redis.get(key)
    if stored_otp and stored_otp == otp:
        await redis.delete(key) # Invalidate OTP after successful verification
        return True
    return False

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

async def get_all_users(db: asyncpg.Connection) -> list[dict]:
    rows = await db.fetch("SELECT id, email, username, is_admin FROM users ORDER BY id DESC")
    return [dict(row) for row in rows]

async def update_user(db: asyncpg.Connection, user_id: int, username: str, email: str, is_admin: bool) -> Optional[dict]:
    row = await db.fetchrow("UPDATE users SET username=$1, email=$2, is_admin=$3 WHERE id=$4 RETURNING id, email, username, is_admin", username, email, is_admin, user_id)
    if row:
        return dict(row)
    return None

async def delete_user(db: asyncpg.Connection, user_id: int) -> bool:
    result = await db.execute("DELETE FROM users WHERE id = $1", user_id)
    return result == "DELETE 1"

async def update_user_profile(db: asyncpg.Connection, user_id: int, phone_number: str | None, avatar_url: str | None) -> Optional[dict]:
    if phone_number is None and avatar_url is None:
        return await get_user_by_id(db, user_id)

    query = "UPDATE users SET "
    params = []
    param_count = 1

    if phone_number is not None:
        query += f"phone_number = ${param_count}, "
        params.append(phone_number)
        param_count += 1
    
    if avatar_url is not None:
        query += f"avatar_url = ${param_count}, "
        params.append(avatar_url)
        param_count += 1

    # Remove trailing comma and space
    query = query.rstrip(", ")

    query += f" WHERE id = ${param_count} RETURNING id, email, username, is_admin, phone_number, avatar_url"
    params.append(user_id)

    row = await db.fetchrow(query, *params)
    if row:
        return dict(row)
    return None


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