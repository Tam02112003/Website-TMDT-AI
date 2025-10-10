from fastapi import APIRouter, Depends, HTTPException, Query
from core.pkgs import database
from schemas.schemas import OrderCreate, OrderStatusUpdateRequest # Removed OrderCreateRequest
from crud import order as crud_order
from core.dependencies import log_activity
from crud.user import get_user_by_email, require_admin
from schemas import schemas

router = APIRouter(prefix="/orders", tags=["order"])

@router.post("/") # Changed path to / and method to POST
async def create_order_endpoint(order_data: OrderCreate, db=Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    order_code = await crud_order.create_order(db, order_data, user['id']) # Pass user.id and order_data directly
    return {"order_code": order_code, "message": "Order created"}

@router.get("/")
async def get_my_orders(search: str = Query(None), db=Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    orders = await crud_order.get_orders_by_user(db, user['id'], search)
    return {"orders": orders}

@router.get("/{order_code}", response_model=schemas.Order)
async def get_order_by_code(order_code: str, db=Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    order = await crud_order.get_order_by_code(db, order_code)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with code {order_code} not found")

    # Ensure the user is requesting their own order, or is an admin
    if order.user_id != user['id'] and not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    return order

@router.get("/{order_code}/status")
async def get_order_status(order_code: str, db=Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    order = await crud_order.get_order_by_code(db, order_code)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with code {order_code} not found")

    # Ensure the user is requesting their own order, or is an admin
    if order.user_id != user['id'] and not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized to view this order status")

    return {"status": order.status}

@router.put("/status")
async def update_order_status(data: OrderStatusUpdateRequest, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    # Only admins can update order status
    await crud_order.update_order_status(db, data)
    return {"message": "Order status updated"}
