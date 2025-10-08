from fastapi import APIRouter, Depends, HTTPException, Request, status
from schemas import schemas
from crud import sepay as sepay_crud, payment as crud_payment, order as crud_order  # Import crud_order
from core.pkgs.database import get_db
import asyncpg
from core.app_config import logger
from core.pkgs.vnpay import vnpay_client
from fastapi.responses import RedirectResponse, JSONResponse
from core.utils.enums import OrderStatus
from core.dependencies import get_current_user  # Import get_current_user
from core.settings import settings

router = APIRouter(prefix="/payment", tags=["Payment"])

@router.post("/orders", response_model=schemas.OrderCreateResponse)  # Assuming an OrderCreateResponse schema
async def create_order_endpoint(
        order_data: schemas.OrderCreate,
        db: asyncpg.Connection = Depends(get_db),
        current_user: dict = Depends(get_current_user)  # Use dict for current_user
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
    # 1. Verify the API Key
    authorization_header = request.headers.get("Authorization")
    if not sepay_crud.verify_api_key(authorization_header):
        logger.warning("Invalid Sepay webhook API key.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    # 2. Process the payload
    try:
        payload = await request.json()
        logger.info(f"Received Sepay webhook: {payload}")

        # Assuming 'referenceCode' from Sepay maps to our 'order_id'
        order_id = payload.get("referenceCode")
        
        # The documentation doesn't specify a success status field.
        # We'll assume a valid webhook for an order means it's paid.
        # A more robust implementation would check a specific status field if available.
        if order_id:
            logger.info(f"Sepay payment successful for Order ID: {order_id}. Updating status.")
            await crud_payment.update_order_payment_status(db, order_id, OrderStatus.PAID)
            return {"status": "success"}
        else:
            logger.warning(f"Sepay webhook received without a referenceCode: {payload}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing referenceCode in payload")

    except Exception as e:
        logger.error(f"Error processing Sepay webhook: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing webhook")

@router.post("/vnpay/create", response_model=schemas.VNPayPaymentRequest)
async def create_vnpay_payment(payment_request: schemas.VNPayPaymentRequest, request: Request):
    try:
        # Get client IP from request
        client_ip = request.client.host

        payment_url = vnpay_client.generate_payment_url(
            order_id=payment_request.order_id,
            amount=payment_request.amount,
            order_desc=payment_request.order_desc,
            ip_addr=client_ip,  # Pass the client IP
            bank_code=payment_request.bank_code,
            language=payment_request.language
        )
        return JSONResponse({"payment_url": payment_url}, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Failed to create VNPay payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create VNPay payment: {e}")

@router.get("/vnpay/callback")
async def vnpay_callback(request: Request, db: asyncpg.Connection = Depends(get_db)):
    vnp_response_data = dict(request.query_params)

    # Log the full callback data for debugging
    logger.info(f"VNPay Callback Received: {vnp_response_data}")

    is_valid, message = vnpay_client.verify_callback(vnp_response_data)

    if is_valid:
        vnp_ResponseCode = vnp_response_data.get('vnp_ResponseCode')
        vnp_TxnRef = vnp_response_data.get('vnp_TxnRef')  # Your order_id
        vnp_Amount = int(vnp_response_data.get('vnp_Amount', 0)) / 100  # Convert back to original amount
        vnp_TransactionStatus = vnp_response_data.get('vnp_TransactionStatus')

        if vnp_ResponseCode == '00' and vnp_TransactionStatus == '00':
            # Payment successful
            logger.info(f"VNPay payment successful for Order ID: {vnp_TxnRef}, Amount: {vnp_Amount}")
            await crud_payment.update_order_payment_status(db, vnp_TxnRef, OrderStatus.PAID)
            # Redirect to frontend with success status
            return RedirectResponse(
                url=f"{settings.FRONTEND.URL}/order-result?vnp_ResponseCode=00&vnp_TxnRef={vnp_TxnRef}")
        else:
            # Payment failed or pending
            logger.warning(
                f"VNPay payment failed/pending for Order ID: {vnp_TxnRef}, Response Code: {vnp_ResponseCode}, Status: {vnp_TransactionStatus}")
            await crud_payment.update_order_payment_status(db, vnp_TxnRef, OrderStatus.PAYMENT_ERROR)
            # Redirect to frontend with failure status
            return RedirectResponse(
                url=f"{settings.FRONTEND.URL}/order-result?vnp_ResponseCode={vnp_ResponseCode}&vnp_TxnRef={vnp_TxnRef}&message=Payment Failed or Pending")
    else:
        logger.error(f"VNPay callback verification failed: {message}")
        # Redirect to frontend with failure status
        return RedirectResponse(url=f"{settings.FRONTEND.URL}/order-result?vnp_ResponseCode=97&message={message}")