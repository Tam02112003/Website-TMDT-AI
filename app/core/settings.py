import os
from pathlib import Path
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import re
from enum import Enum


BASE_DIR = Path(__file__).resolve().parent.parent

class EnvironmentType(str, Enum):
    DEV = "dev"
    UAT = "uat"
    PROD = "prod"

def load_env_file(file_path: str) -> None:
    """Load environment variables from file"""
    if not os.path.exists(file_path):
        print(f"Warning: Environment file {file_path} not found")
        return

    print(f"Loading env_file from {file_path}")
    load_dotenv(file_path, encoding="utf-8", override=True)


    # Additional handling for special characters if needed
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Handle quoted values for special characters
                match = re.match(r'^([A-Za-z0-9_]+)=["\"]?(.*?)["\"]?$', line)
                if match:
                    key, value = match.groups()
                    # Set env var with override
                    os.environ[key] = value

def load_environment(env_type: str = None):
    """Load environment variables from file based on environment type"""
    # Ensure dotenv is loaded for basic OS environment variables
    load_dotenv()
    if env_type is None:
        env_type = os.getenv("ENV", EnvironmentType.DEV.value) # Changed default to DEV

    # Load environment file based on the environment type
    env_file = os.path.join(BASE_DIR, "env", f".env.{env_type}")

    print(f"Loading environment from: {env_file}")
    load_env_file(env_file)


# Nested Settings Classes (adapted from core/settings.py)

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")
    USER: str
    PASSWORD: SecretStr
    HOST: str = 'localhost'
    PORT: int = 5432
    NAME: str
    MAX_POOL_SIZE: int
    MIN_POOL_SIZE: int

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.USER}:{self.PASSWORD.get_secret_value()}@{self.HOST}:{self.PORT}/{self.NAME}"

class GoogleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_")
    CLIENT_ID: str
    CLIENT_SECRET: SecretStr
    REDIRECT_URI: str
    OAUTH2_URL: str  = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL: str  = "https://oauth2.googleapis.com/token"
    USERINFO_URL: str  = "https://www.googleapis.com/oauth2/v3/userinfo"

class JwtSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_")
    SECRET: SecretStr

class RapidAPISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAPID_API_")
    KEY: SecretStr

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    HOST: str = 'localhost'
    PORT: int = 6379
    DB: int = 0
    PASSWORD: SecretStr

class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKA_")
    BOOTSTRAP_SERVERS: str = 'localhost:9092'
    SECURITY_PROTOCOL: str | None = None
    SASL_MECHANISM: str | None = None
    SASL_USERNAME: str | None = None
    SASL_PASSWORD: SecretStr | None = None
    LOG_LEVEL: str = "ERROR"

class MomoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOMO_")
    ENDPOINT: str = 'https://test-payment.momo.vn/v2/gateway/api/create'
    PARTNER_CODE: str
    ACCESS_KEY: SecretStr
    SECRET_KEY: SecretStr
    RETURN_URL: str = 'http://localhost:8000/payment/momo/callback'



class SepaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEPAY_")
    API_URL: str = "https://my.sepay.vn/api/v1"
    API_TOKEN: SecretStr
    BANK_NAME: str = "TPBank"
    ACCOUNT_NUMBER: str = "08626123398"

class SmtpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMTP_")
    HOST: str
    PORT: int = 587
    USER: str
    PASSWORD: SecretStr
    FROM: str

class SMSSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMS_")
    ACCOUNT_SID: SecretStr
    AUTH_TOKEN: SecretStr
    SENDER_ID: str
    DEFAULT_COUNTRY_CODE: str = "VN" # Default to Vietnam's country code

class LocalLLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOCAL_LLM_")
    API_URL: str
    MODEL: str = "ai/gemma3n"

class CloudinarySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLOUDINARY_")
    CLOUD_NAME: str
    API_KEY: str
    API_SECRET: SecretStr

class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FRONTEND_")
    URL: str = "http://localhost:5173"


# Main Settings Class (adapted from docs/Settings.py)
class Settings:
    """Main settings class that uses singleton pattern to ensure configuration is loaded only once"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
        return cls._instance

    def __init__(self, env_type: str = None):
        # Only initialize once
        if not Settings._initialized:
            # Load environment first
            load_environment(env_type)

            # Create fresh instances of settings classes after environment is loaded
            self.DB = DatabaseSettings()
            self.GOOGLE = GoogleSettings()
            self.JWT = JwtSettings()
            self.RAPID_API = RapidAPISettings()
            self.REDIS = RedisSettings()
            self.KAFKA = KafkaSettings()
            self.MOMO = MomoSettings()

            self.SEPAY = SepaySettings()
            self.SMTP = SmtpSettings()
            self.SMS = SMSSettings()
            self.LOCAL_LLM = LocalLLMSettings()
            self.CLOUDINARY = CloudinarySettings()
            self.FRONTEND = FrontendSettings()

            # Mark as initialized
            Settings._initialized = True


# Initialize settings instance when module is imported
settings = Settings()
