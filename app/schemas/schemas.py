from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from core.utils.enums import OrderStatus, PaymentMethod

class BrandBase(BaseModel):
    name: str

class BrandCreate(BrandBase):
    pass

class Brand(BrandBase):
    id: int

    class Config:
        from_attributes = True

class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    quantity: int
    image_urls: Optional[List[str]] = None
    is_active: Optional[bool] = True
    release_date: Optional[datetime] = None
    brand_id: Optional[int] = None
    category_id: Optional[int] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    discount_percent: Optional[float] = None
    final_price: Optional[float] = None
    release_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    brand: Optional[Brand] = None
    category: Optional[Category] = None
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
    parent_comment_id: Optional[int] = None

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: str

class Comment(CommentBase):
    id: int
    created_at: datetime
    user_avatar_url: Optional[str] = None
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

class ShippingAddressCreate(BaseModel):
    address: str
    city: str
    postal_code: str
    country: str
    phone_number: str

class OrderCreate(BaseModel):
    items: List[OrderItemRequest]
    shipping_address: ShippingAddressCreate
    payment_method: PaymentMethod

class OrderStatusUpdateRequest(BaseModel):
    order_code: str
    status: OrderStatus

class CartAdd(BaseModel):
    product_id: int
    quantity: int

class CartUpdate(BaseModel):
    product_id: int
    quantity: int

# This was previously OrderCreate, now it's more specific for COD
class CODOrderCreate(BaseModel):
    items: List[OrderItemRequest]
    total_amount: float

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
    length: str = "vừa phải"

class ChatbotRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class ChatbotResponse(BaseModel):
    answer: str

class OrderCreateResponse(BaseModel):
    order_code: str
    message: str

class User(BaseModel):
    id: int
    username: str
    email: EmailStr
    phone_number: Optional[str] = None
    is_admin: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

class OrderItem(BaseModel):
    product_id: int
    quantity: int
    price: float
    image_urls: Optional[List[str]] = None

class Order(BaseModel):
    id: int
    order_code: str
    user_id: int
    total_amount: float
    status: str
    created_at: datetime
    items: List[OrderItem]
    shipping_address: Optional[str]
    shipping_city: Optional[str]
    shipping_postal_code: Optional[str]
    shipping_country: Optional[str]
    customer_name: str
    customer_phone: Optional[str] = None
    shipping_phone_number: Optional[str] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: str
    email: EmailStr
    is_admin: bool

class SendOtpRequest(BaseModel):
    phone_number: str

class VerifyOtpRequest(BaseModel):
    phone_number: str
    otp: str