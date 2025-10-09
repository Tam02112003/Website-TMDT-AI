from fastapi import APIRouter, Depends, HTTPException, Request, status
import re
from schemas import schemas
from crud import sepay as sepay_crud, payment as crud_payment, order as crud_order
from core.pkgs.database import get_db
import asyncpg
from core.app_config import logger
from fastapi.responses import RedirectResponse, JSONResponse
from core.utils.enums import OrderStatus
from core.dependencies import get_current_user
from core.settings import settings

router = APIRouter(prefix="/payment", tags=["Payment"])

@router.post("/orders", response_model=schemas.OrderCreateResponse)
async def create_order_endpoint(
        order_data: schemas.OrderCreate,
        db: asyncpg.Connection = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    try:
        order_code = await crud_order.create_order(db, order_data, current_user.id)
        return {"order_code": order_code, "message": "Order created successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to create order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create order: {e}")

@router.post("/sepay/create", response_model=schemas.SepayPaymentResponse)
async def create_sepay_payment_endpoint(payment_request: schemas.SepayPaymentRequest):
    """
    Creates a Sepay payment request and returns the response from Sepay.
    """
    try:
        sepay_response = sepay_crud.create_sepay_payment(
            order_id=payment_request.order_id,
            amount=payment_request.amount
        )
        return sepay_response
    except Exception as e:
        logger.error(f"Failed to create Sepay payment: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create Sepay payment: {e}")

@router.get("/sepay/config")
async def get_sepay_config():
    """
    Returns the public Sepay configuration needed for the frontend.
    """
    return {
        "bankName": settings.SEPAY.BANK_NAME,
        "accountNumber": settings.SEPAY.ACCOUNT_NUMBER
    }

@router.post("/sepay/webhook")
async def sepay_webhook(request: Request, db: asyncpg.Connection = Depends(get_db)):
    """
    Handles incoming webhooks from Sepay.
    """
    authorization_header = request.headers.get("Authorization")
    if not sepay_crud.verify_api_key(authorization_header):
        logger.warning("Invalid Sepay webhook API key.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    try:
        payload = await request.json()
        logger.info(f"Received Sepay webhook: {payload}")

        description = payload.get("description", "")
        order_id_match = re.search(r'ORD([A-F0-9]+)', description)

        if order_id_match:
            order_code_suffix = order_id_match.group(1)
            reconstructed_order_id = f"ORD-{order_code_suffix}"
            
            logger.info(f"Extracted and reconstructed Order ID {reconstructed_order_id}. Processing Sepay payment.")
            # Call the full Sepay payment processing logic which includes email sending
            await crud_order.process_sepay_payment(db, reconstructed_order_id, payload.get("transferAmount"))
            return {"status": "success"}
        else:
            logger.warning(f"Could not extract a valid Order ID from Sepay webhook description: {description}")
            return {"status": "error", "reason": "Order ID not found in description"}

    except Exception as e:
        logger.error(f"Error processing Sepay webhook: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing webhook")
