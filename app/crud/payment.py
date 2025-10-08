from core.app_config import logger
from core.utils.enums import OrderStatus
import asyncpg


def process_sepay_payment(order_details):
    """
    Simulates processing a payment with the Sepay gateway.
    In a real application, this would involve making API calls to Sepay.
    """
    logger.info(f"Processing Sepay payment for order: {order_details['order_code']}")
    # Simulate a successful payment
    return {"status": "success", "transaction_id": "sep_12345"}

def process_cod_payment(order_details):
    """
    Handles Cash on Delivery (COD) logic.
    This might involve just confirming the order without immediate payment processing.
    """
    logger.info(f"Order {order_details['order_code']} confirmed for Cash on Delivery.")
    return {"status": "pending_delivery", "transaction_id": None}

async def update_order_payment_status(db: asyncpg.Connection, order_id: str, status: OrderStatus):
    """
    Updates the payment status of an order in the database.
    """
    try:
        await db.execute(
            "UPDATE orders SET status = $1 WHERE order_code = $2",
            status.value, order_id
        )
        logger.info(f"Order {order_id} status updated to {status.value}")
        return True
    except Exception as e:
        logger.error(f"Failed to update order {order_id} status to {status.value}: {e}", exc_info=True)
        return False