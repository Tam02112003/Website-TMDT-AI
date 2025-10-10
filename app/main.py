from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.app_config import settings, logger, get_printable_settings
from core.middleware import setup_middleware
from router import product, news, discount, tryon, auth, cart, order, payment, chatbot, admin, upload, recommendation, user, brand, category
from core.limiter import limiter
from core.kafka.kafka_client import close_kafka_producer
from core.kafka.kafka_admin import create_topics_if_needed

app = FastAPI()

# Add state and exception handler for slowapi
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
async def startup_event():
    logger.info("--- Application Settings Loaded ---")
    logger.info(f"\n{get_printable_settings(settings)}")
    logger.info("---------------------------------")
    await create_topics_if_needed()

@app.on_event("shutdown")
def shutdown_event():
    close_kafka_producer()

# Add slowapi middleware
app.add_middleware(SlowAPIMiddleware)

# Setup other middleware
setup_middleware(app)

# Cho phép CORS nếu cần cho frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://front-end-website-tmdt-ai.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    logger.info("Root endpoint accessed.")
    return {"message": "FastAPI is running!"}

app.include_router(tryon.router)
app.include_router(product.router)
app.include_router(news.router)
app.include_router(discount.router)
app.include_router(auth.router)
app.include_router(cart.router)
app.include_router(order.router)
app.include_router(payment.router)
app.include_router(chatbot.router)
app.include_router(admin.router)
app.include_router(upload.router)
app.include_router(recommendation.router)
app.include_router(user.router)
app.include_router(brand.router)
app.include_router(category.router)

