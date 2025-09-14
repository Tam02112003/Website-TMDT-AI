import asyncpg
import secrets
import json
from typing import List, Optional

from core.enums import OrderStatus, PaymentMethod
from core.kafka.kafka_client import producer
from schemas.schemas import OrderCreateRequest, OrderStatusUpdateRequest
from core.email_sender import send_email
from crud.user import get_user_by_id

async def create_order(db: asyncpg.Connection, data: OrderCreateRequest) -> str:
    # Generate a unique, human-friendly order code
    while True:
        order_code = f"ORD-{secrets.token_hex(4).upper()}"
        existing_order = await db.fetchrow("SELECT id FROM orders WHERE order_code = $1", order_code)
        if not existing_order:
            break

    # Determine order status based on payment method
    status = OrderStatus.PROCESSING if data.payment_method == PaymentMethod.COD else OrderStatus.PENDING

    row = await db.fetchrow(
        "INSERT INTO orders (user_id, total_amount, status, order_code, payment_method) VALUES ($1, $2, $3, $4, $5) RETURNING id",
        data.user_id, data.total_amount, status.value, order_code, data.payment_method.value
    )
    order_id = row["id"]
    for item in data.items:
        await db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES ($1, $2, $3, $4)",
                         order_id, item.product_id, item.quantity, item.price)

    event = {
        "event": "order_created",
        "order_code": order_code,
        "user_id": data.user_id,
        "total_amount": data.total_amount,
        "payment_method": data.payment_method.value,
        "items": [item.model_dump() for item in data.items]
    }
    producer.send('order_events', json.dumps(event).encode('utf-8'))
    return order_code

async def get_orders_by_user(db: asyncpg.Connection, user_id: int) -> List[dict]:
    orders = await db.fetch("SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC", user_id)
    return [dict(order) for order in orders]

async def get_order_by_code(db: asyncpg.Connection, order_code: str) -> Optional[dict]:
    order = await db.fetchrow("SELECT * FROM orders WHERE order_code = $1", order_code)
    if not order:
        return None
    
    items = await db.fetch("SELECT * FROM order_items WHERE order_id = $1", order['id'])
    
    result = dict(order)
    result['items'] = [dict(item) for item in items]
    
    return result

async def update_order_status(db: asyncpg.Connection, data: OrderStatusUpdateRequest):
    await db.execute("UPDATE orders SET status = $1 WHERE order_code = $2", data.status.value, data.order_code)

async def process_sepay_payment(db: asyncpg.Connection, order_code: str, amount: float) -> bool:
    """
    Processes a payment notification from Sepay.
    Returns True if payment is successful and updated, False otherwise.
    """
    order = await get_order_by_code(db, order_code)

    if not order:
        print(f"Webhook Error: Order with code {order_code} not found.")
        return False

    if order.get('status') != OrderStatus.PENDING:
        print(f"Webhook Info: Order {order_code} already processed. Current status: {order.get('status')}")
        return True

    if float(order.get('total_amount')) != amount:
        print(f"Webhook Error: Amount mismatch for order {order_code}. Expected {order.get('total_amount')}, got {amount}")
        status_update = OrderStatusUpdateRequest(order_code=order_code, status=OrderStatus.PAYMENT_ERROR)
        await update_order_status(db, status_update)
        return False

    status_update = OrderStatusUpdateRequest(order_code=order_code, status=OrderStatus.PAID)
    await update_order_status(db, status_update)
    print(f"Payment successful for order {order_code}. Status updated to 'paid'.")

    user_id = order.get('user_id')
    if user_id:
        user = await get_user_by_id(db, user_id)
        if user and user.get('email'):
            subject = f"Order Confirmation #{order_code}"
            message = f"Dear {user.get('username')},\n\nYour payment for order {order_code} was successful.\n\nThank you for your purchase!"
            await send_email(user.get('email'), subject, message)

    return True
