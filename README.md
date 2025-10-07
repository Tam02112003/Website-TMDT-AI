# 🛍️ E-Commerce Website with AI Features

A modern e-commerce backend platform built with FastAPI, featuring AI-powered chatbot, personalized recommendations, and virtual try-on capabilities.

## ✨ Features

### Core E-Commerce Features
- **Product Management** - Browse, search, and filter products by category and brand
- **User Authentication** - Secure login and registration system with JWT
- **Shopping Cart** - Add, update, and remove items from cart
- **Order Processing** - Complete order workflow with order tracking
- **Payment Integration** - Secure payment processing
- **Discount System** - Apply promotional codes and discounts
- **News & Blog** - Content management for news articles
- **Comments System** - Product reviews and nested comments

### AI-Powered Features
- **AI Chatbot** - Intelligent chatbot for customer support with natural language SQL query generation
- **Personalized Recommendations** - Item-based collaborative filtering using cosine similarity
- **Smart Product Search** - AI-enhanced product discovery
- **Virtual Try-On** - AR-powered product visualization

### Technical Features
- **Real-time Processing** - Apache Kafka for event streaming
- **Caching** - Redis for high-performance data caching
- **Cloud Storage** - Cloudinary integration for image management
- **SMS Notifications** - Twilio integration for order updates
- **Admin Dashboard** - Complete admin interface for management
- **CORS Support** - Cross-origin resource sharing enabled

## 🏗️ Tech Stack

**Backend Framework:**
- FastAPI - Modern, fast web framework for building APIs
- Python 3.x

**Database:**
- PostgreSQL - Primary database
- AsyncPG - Async PostgreSQL driver

**AI/ML:**
- Scikit-learn - Machine learning for recommendations
- Pandas & NumPy - Data processing
- HTTPX - Async HTTP client for AI model integration

**Message Queue:**
- Apache Kafka - Event streaming platform

**Caching:**
- Redis - In-memory data store

**Cloud Services:**
- Cloudinary - Image and media management
- Twilio - SMS notifications

**Authentication:**
- PyJWT - JSON Web Tokens
- Cryptography - Secure password hashing

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis
- Apache Kafka
- Cloudinary account
- Twilio account (for SMS)

## 🚀 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Tam02112003/Website-TMDT-AI.git
cd Website-TMDT-AI
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
cd app
pip install -r requirements.txt
```

4. **Set up environment variables:**
Create a `.env` file in the `app` directory with the following:
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256

# Cloudinary
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Twilio
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=your-twilio-number

# AI Model
AI_MODEL_URL=your-ai-model-endpoint
```

5. **Initialize the database:**
```bash
psql -U your_user -d your_database -f docs/all_tables.sql
```

6. **Run the application:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 API Documentation

Once the application is running, access the interactive API documentation:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### Main Endpoints

**Authentication:**
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh token

**Products:**
- `GET /products` - List all products
- `GET /products/{id}` - Get product details
- `POST /products` - Create product (admin)
- `PUT /products/{id}` - Update product (admin)
- `DELETE /products/{id}` - Delete product (admin)

**Cart:**
- `GET /cart` - Get user cart
- `POST /cart` - Add item to cart
- `PUT /cart/{id}` - Update cart item
- `DELETE /cart/{id}` - Remove from cart

**Orders:**
- `GET /orders` - Get user orders
- `POST /orders` - Create order
- `GET /orders/{id}` - Get order details

**AI Features:**
- `POST /chatbot` - Chat with AI assistant
- `GET /recommendations` - Get personalized recommendations
- `POST /tryon` - Virtual try-on

**Admin:**
- `GET /admin/users` - Manage users
- `GET /admin/orders` - Manage orders
- `GET /admin/analytics` - View analytics

## 🗄️ Database Schema

The application uses PostgreSQL with the following main tables:
- `users` - User accounts and profiles
- `products` - Product catalog
- `categories` - Product categories
- `brands` - Product brands
- `cart` - Shopping cart items
- `orders` - Order records
- `order_items` - Order line items
- `discounts` - Promotional discounts
- `news` - News articles
- `comments` - Product reviews

## 🤖 AI Features Details

### Chatbot Service
The AI chatbot uses natural language processing to:
- Understand customer queries
- Generate SQL queries dynamically
- Provide product recommendations
- Maintain conversation history using Redis

### Recommendation Engine
The recommendation system uses:
- Item-based collaborative filtering
- Cosine similarity for product matching
- User purchase history analysis
- Cached model for fast predictions

## 🔧 Configuration

Key configuration files:
- `app/core/settings.py` - Application settings
- `app/core/app_config.py` - App configuration
- `app/requirements.txt` - Python dependencies

## 📦 Project Structure

```
app/
├── core/              # Core functionality
│   ├── kafka/        # Kafka integration
│   ├── redis/        # Redis integration
│   ├── pkgs/         # Shared packages
│   └── utils/        # Utility functions
├── router/           # API routes
├── services/         # Business logic
│   ├── ChatbotServices.py
│   ├── PersonalizedRecService.py
│   └── RecommendationService.py
├── crud/             # Database operations
├── schemas/          # Pydantic models
├── docs/             # Documentation
└── main.py           # Application entry point
```

## 🐳 Docker Support (Optional)

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🧪 Testing

```bash
pytest tests/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- Tam Nguyen - Initial work

## 🙏 Acknowledgments

- FastAPI documentation
- Scikit-learn community
- Apache Kafka team
- All contributors

## 📞 Support

For support, email ngminhtam021103@gmail.com or open an issue in the repository.

## 🔮 Future Enhancements

- [ ] Mobile app integration
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Social media integration
- [ ] Wishlist functionality
- [ ] Product comparison feature
- [ ] Advanced search filters
- [ ] Email notifications
