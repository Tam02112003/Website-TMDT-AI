from fastapi import APIRouter, Depends, HTTPException, Request
from schemas import schemas
from crud import user as user_crud
from core.pkgs.database import get_db
import asyncpg
from core.dependencies import get_current_user
from services.SMSService import send_sms
from core.limiter import limiter

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=schemas.User)
@limiter.limit("10/minute")
async def read_users_me(request: Request, current_user: dict = Depends(get_current_user), db: asyncpg.Connection = Depends(get_db)):
    user = await user_crud.get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

class UserProfileUpdate(schemas.BaseModel):
    phone_number: str | None = None
    avatar_url: str | None = None

@router.put("/me", response_model=schemas.User)
@limiter.limit("10/minute")
async def update_user_me(user_update: UserProfileUpdate, request: Request, current_user: dict = Depends(get_current_user), db: asyncpg.Connection = Depends(get_db)):
    user = await user_crud.get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    updated_user = await user_crud.update_user_profile(db, user['id'], user_update.phone_number, user_update.avatar_url)
    if not updated_user:
        raise HTTPException(status_code=500, detail="Failed to update user profile")
    return updated_user

# Add new endpoints for OTP
@router.post("/send-otp")
@limiter.limit("3/minute")
async def send_otp_endpoint(otp_request: schemas.SendOtpRequest, request: Request, current_user: dict = Depends(get_current_user), db: asyncpg.Connection = Depends(get_db)):
    user = await user_crud.get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    otp = await user_crud.generate_and_store_otp(user['id'], otp_request.phone_number)
    message = f"Your OTP for verification is: {otp}"
    try:
        await send_sms(otp_request.phone_number, message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "OTP sent successfully."}

@router.post("/verify-otp")
@limiter.limit("5/minute")
async def verify_otp_endpoint(otp_request: schemas.VerifyOtpRequest, request: Request, current_user: dict = Depends(get_current_user), db: asyncpg.Connection = Depends(get_db)):
    user = await user_crud.get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_valid = await user_crud.verify_otp(user['id'], otp_request.phone_number, otp_request.otp)
    if is_valid:
        # Update the user's phone number in the database after successful verification
        updated_user = await user_crud.update_user_profile(db, user['id'], otp_request.phone_number, None) # Only update phone number
        if not updated_user:
            raise HTTPException(status_code=500, detail="Failed to update phone number after OTP verification.")
        return {"message": "Phone number verified and updated successfully."}
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

