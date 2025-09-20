import asyncpg
import secrets
import json
from typing import List, Optional
from fastapi import HTTPException
from core.utils.enums import OrderStatus, PaymentMethod
from core.kafka.kafka_client import producer
from schemas import schemas
from schemas.schemas import OrderStatusUpdateRequest
from core.email_sender import send_email
from crud.user import get_user_by_id
from crud.product import get_product
from starlette.concurrency import run_in_threadpool

async def create_order(db: asyncpg.Connection, data: schemas.OrderCreate, user_id: int) -> str:
    # Generate a unique, human-friendly order code
    while True:
        order_code = f"ORD-{secrets.token_hex(4).upper()}"
        existing_order = await db.fetchrow("SELECT id FROM orders WHERE order_code = $1", order_code)
        if not existing_order:
            break

    # Determine order status based on payment method
    status = OrderStatus.PROCESSING if data.payment_method == PaymentMethod.COD else OrderStatus.PENDING

    # Calculate total_amount from items, as frontend might send it, but backend should verify
    calculated_total_amount = 0
    for item in data.items:
        product = await get_product(db, item.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product with ID {item.product_id} not found or is inactive.")
        # Calculate final_price on backend for comparison
        backend_final_price = product.price
        if product.discount_percent is not None:
            backend_final_price = product.price * (1 - product.discount_percent / 100)

        if abs(backend_final_price - item.price) > 0.01: # Use a small tolerance for float comparison
            raise HTTPException(status_code=400, detail=f"Price mismatch for product ID {item.product_id}. Expected {backend_final_price:.2f}, got {item.price:.2f}.")
        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product ID {item.product_id}. Available: {product.quantity}, Requested: {item.quantity}.")
        calculated_total_amount += backend_final_price * item.quantity

    row = await db.fetchrow(
        "INSERT INTO orders (user_id, total_amount, status, order_code, payment_method, shipping_address, shipping_city, shipping_postal_code, shipping_country, shipping_phone_number) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id",
        user_id, calculated_total_amount, status.value, order_code, data.payment_method.value,
        data.shipping_address.address, data.shipping_address.city, data.shipping_address.postal_code, data.shipping_address.country, data.shipping_address.phone_number
    )
    order_id = row["id"]
    for item in data.items:
        await db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES ($1, $2, $3, $4)",
                         order_id, item.product_id, item.quantity, item.price)
        # Deduct product quantity from stock
        await db.execute("UPDATE products SET quantity = quantity - $1 WHERE id = $2 AND quantity >= $1", item.quantity, item.product_id)

    event = {
        "event": "order_created",
        "order_code": order_code,
        "user_id": user_id,
        "total_amount": calculated_total_amount,
        "payment_method": data.payment_method.value,
        "items": [item.model_dump() for item in data.items],
        "shipping_address": data.shipping_address.model_dump()
    }
    producer.send('order_events', json.dumps(event).encode('utf-8'))

    # Send email confirmation for COD orders immediately
    if data.payment_method == PaymentMethod.COD:
        user = await get_user_by_id(db, user_id)
        if user and user.get('email'):
            subject = f"Order Confirmation #{order_code}"
            message = f"Dear {user.get('username')},\n\nYour order {order_code} has been placed successfully and is awaiting processing.\n\nThank you for your purchase!"
            await run_in_threadpool(send_email, user.get('email'), subject, message)

    return order_code

async def get_orders_by_user(db: asyncpg.Connection, user_id: int, search: Optional[str] = None) -> List[dict]:
    if search:
        query = "SELECT * FROM orders WHERE user_id = $1 AND order_code ILIKE $2 ORDER BY created_at DESC"
        orders = await db.fetch(query, user_id, f'%{search}%')
    else:
        query = "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC"
        orders = await db.fetch(query, user_id)
    return [dict(order) for order in orders]

async def get_order_by_code(db: asyncpg.Connection, order_code: str) -> Optional[schemas.Order]:
    order_row = await db.fetchrow("SELECT * FROM orders WHERE order_code = $1", order_code)
    if not order_row:
        return None
    
    items_rows = await db.fetch("""
        SELECT oi.*, p.name as product_name, p.image_url
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = $1
    """, order_row['id'])
    
    user = await get_user_by_id(db, order_row['user_id'])
    if not user:
        # This should not happen if database integrity is maintained
        raise HTTPException(status_code=404, detail="User not found for this order")

    order_items = [schemas.OrderItem(**item) for item in items_rows]

    return schemas.Order(
        id=order_row['id'],
        order_code=order_row['order_code'],
        user_id=order_row['user_id'],
        total_amount=order_row['total_amount'],
        status=order_row['status'],
        created_at=order_row['created_at'],
        items=order_items,
        shipping_address=order_row['shipping_address'],
        shipping_city=order_row['shipping_city'],
        shipping_postal_code=order_row['shipping_postal_code'],
        shipping_country=order_row['shipping_country'],
        customer_name=user['username'],
        customer_phone=user.get('phone_number'), # Use .get for optional field
        shipping_phone_number=order_row.get('shipping_phone_number') # Get from order_row
    )

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

async def get_all_orders(db: asyncpg.Connection, search_query: Optional[str] = None) -> List[dict]:
    query = "SELECT * FROM orders"
    params = []
    param_count = 1

    if search_query:
        query += f" WHERE order_code ILIKE ${param_count} OR CAST(user_id AS TEXT) ILIKE ${param_count}"
        params.append(f'%{search_query}%')
        param_count += 1

    query += " ORDER BY created_at DESC"
    orders = await db.fetch(query, *params)
    return [dict(order) for order in orders]

async def get_all_purchase_history(db: asyncpg.Connection) -> List[dict]:
    """
    Fetches all user-product purchase pairs from successful orders.
    Successful orders are those with status PAID, PROCESSING, or DELIVERED.
    """
    query = """
        SELECT o.user_id, oi.product_id
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.status = ANY($1::text[])
    """
    successful_statuses = [OrderStatus.PAID.value, OrderStatus.PROCESSING.value, OrderStatus.DELIVERED.value]
    rows = await db.fetch(query, successful_statuses)
    return [dict(row) for row in rows]
