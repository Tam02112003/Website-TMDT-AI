from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from core.utils.enums import OrderStatus, PaymentMethod

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    quantity: int
    image_url: Optional[str] = None
    is_active: Optional[bool] = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class NewsBase(BaseModel):
    title: str
    content: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = True

class NewsCreate(NewsBase):
    pass

class NewsUpdate(NewsBase):
    pass

class News(NewsBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class DiscountBase(BaseModel):
    name: str
    percent: float
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    product_id: Optional[int] = None
    is_active: Optional[bool] = True

class DiscountCreate(DiscountBase):
    pass

class DiscountUpdate(DiscountBase):
    pass

class Discount(DiscountBase):
    id: int
    class Config:
        from_attributes = True

class CommentBase(BaseModel):
    product_id: int
    content: str
    user_name: Optional[str] = None

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class CartAddRequest(BaseModel):
    user_id: int
    product_id: int
    quantity: int

class CartUpdateRequest(BaseModel):
    user_id: int
    product_id: int
    quantity: int

class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int
    price: float

class OrderCreateRequest(BaseModel):
    user_id: int
    items: List[OrderItemRequest]
    total_amount: float
    payment_method: PaymentMethod = PaymentMethod.SEPAY

class OrderStatusUpdateRequest(BaseModel):
    order_code: str
    status: OrderStatus

class CartAdd(BaseModel):
    product_id: int
    quantity: int

class CartUpdate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItemRequest]
    total_amount: float
    payment_method: PaymentMethod = PaymentMethod.SEPAY

class CODOrderCreate(BaseModel):
    items: List[OrderItemRequest]
    total_amount: float

class VNPayPaymentRequest(BaseModel):
    order_id: str
    amount: int  # Amount in VND, should be an integer (e.g., 100000 for 100,000 VND)
    order_desc: str = "Thanh toan don hang"
    bank_code: Optional[str] = None # Optional bank code for direct payment
    language: str = "vn" # 'vn' for Vietnamese, 'en' for English

class AINewsGenerateRequest(BaseModel):
    topic: str
    keywords: Optional[str] = None
    length: str = "vừa phải" # e.g., "ngắn", "vừa phải", "dài"

class ChatbotRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class ChatbotResponse(BaseModel):
    answer: str