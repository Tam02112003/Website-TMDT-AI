from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    PAYMENT_ERROR = "payment_error"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentMethod(str, Enum):
    COD = "cod"
    MOMO = "momo"
    SEPAY = "sepay"

class ChatbotSessionTime(int, Enum):
    MAX_HISTORY_LEN = 10
    SESSION_TTL = 3600

class RATE_LIMIT(int, Enum):
    # Rate Limiting Configuration
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 20  # requests per window

class ModelPath(str, Enum):
    MODEL_CACHE_PATH = "cache/personalized_rec_model.pkl"
