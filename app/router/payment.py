from fastapi import APIRouter, Depends, HTTPException, Request, status
from schemas import schemas
from crud import sepay as sepay_crud, payment as crud_payment
from core.pkgs.database import get_db
import asyncpg
from core.app_config import logger
from core.pkgs.vnpay import vnpay_client
from fastapi.responses import RedirectResponse, JSONResponse
from core.utils.enums import OrderStatus

router = APIRouter(prefix="/payment", tags=["Payment"])

@router.post("/sepay/intent")
async def create_payment_intent(amount: float, order_id: str):
    """
    Creates a payment intent with Sepay.
    This is a simplified endpoint. In a real app, you'd likely have more
    details like currency, customer info, etc.
    """
    try:
        intent = sepay_crud.create_sepay_payment_intent(amount, order_id)
        return intent
    except Exception as e:
        logger.error(f"Failed to create payment intent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create payment intent: {e}")

@router.post("/sepay/verify/{payment_intent_id}")
async def verify_payment(payment_intent_id: str):
    """
    Verifies a payment with Sepay.
    In a real app, this might be a webhook endpoint that Sepay calls.
    """
    is_verified = sepay_crud.verify_sepay_payment(payment_intent_id)
    if is_verified:
        # Here you would typically update the order status in your database
        logger.info(f"Payment {payment_intent_id} verified successfully. Update order status.")
        return {"status": "success"}
    else:
        logger.warning(f"Payment {payment_intent_id} verification failed.")
        raise HTTPException(status_code=400, detail="Payment verification failed")

@router.post("/vnpay/create", response_model=schemas.VNPayPaymentRequest)
async def create_vnpay_payment(payment_request: schemas.VNPayPaymentRequest):
    try:
        payment_url = vnpay_client.generate_payment_url(
            order_id=payment_request.order_id,
            amount=payment_request.amount,
            order_desc=payment_request.order_desc,
            bank_code=payment_request.bank_code,
            language=payment_request.language
        )
        return RedirectResponse(url=payment_url, status_code=status.HTTP_303_SEE_OTHER)
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
        vnp_TxnRef = vnp_response_data.get('vnp_TxnRef') # Your order_id
        vnp_Amount = int(vnp_response_data.get('vnp_Amount', 0)) / 100 # Convert back to original amount
        vnp_TransactionStatus = vnp_response_data.get('vnp_TransactionStatus')

        if vnp_ResponseCode == '00' and vnp_TransactionStatus == '00':
            # Payment successful
            logger.info(f"VNPay payment successful for Order ID: {vnp_TxnRef}, Amount: {vnp_Amount}")
            await crud_payment.update_order_payment_status(db, vnp_TxnRef, OrderStatus.PAID)
            return JSONResponse({"RspCode": "00", "Message": "Success"})
        else:
            # Payment failed or pending
            logger.warning(f"VNPay payment failed/pending for Order ID: {vnp_TxnRef}, Response Code: {vnp_ResponseCode}, Status: {vnp_TransactionStatus}")
            await crud_payment.update_order_payment_status(db, vnp_TxnRef, OrderStatus.PAYMENT_ERROR)
            return JSONResponse({"RspCode": "01", "Message": "Payment Failed or Pending"})
    else:
        logger.error(f"VNPay callback verification failed: {message}")
        return JSONResponse({"RspCode": "97", "Message": message}, status_code=status.HTTP_400_BAD_REQUEST)