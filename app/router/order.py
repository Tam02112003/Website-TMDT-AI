from fastapi import APIRouter, Depends, HTTPException
from core.pkgs import database
from schemas.schemas import OrderCreate, OrderCreateRequest, OrderStatusUpdateRequest
from crud import order as crud_order
from crud.user import get_current_user, get_user_by_email, require_admin

router = APIRouter(prefix="/order", tags=["order"])

@router.post("/create")
async def create_order(data: OrderCreate, db=Depends(database.get_db), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create the full OrderCreateRequest object including the user_id from the token
    order_data = OrderCreateRequest(user_id=user['id'], items=data.items, total_amount=data.total_amount, payment_method=data.payment_method)
    
    order_code = await crud_order.create_order(db, order_data)
    return {"order_code": order_code, "message": "Order created"}

@router.get("/")
async def get_my_orders(db=Depends(database.get_db), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    orders = await crud_order.get_orders_by_user(db, user['id'])
    return {"orders": orders}

@router.get("/{order_code}")
async def get_order_by_code(order_code: str, db=Depends(database.get_db), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    order = await crud_order.get_order_by_code(db, order_code)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with code {order_code} not found")

    # Ensure the user is requesting their own order, or is an admin
    if order['user_id'] != user['id'] and not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    return order

@router.put("/status")
async def update_order_status(data: OrderStatusUpdateRequest, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    # Only admins can update order status
    await crud_order.update_order_status(db, data)
    return {"message": "Order status updated"}
