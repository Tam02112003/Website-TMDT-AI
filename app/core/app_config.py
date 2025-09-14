import os
from pathlib import Path
from dotenv import load_dotenv
import logging.config
from core.settings import settings
from core.logging_config import LOGGING_CONFIG, LOG_DIR
import json
from pydantic_settings import BaseSettings

# Define BASE_DIR and load environment variables as early as possible
BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.getenv("APP_ENV", "dev")
dotenv_path = os.path.join(BASE_DIR, 'env', f'.env.{APP_ENV}')
load_dotenv(dotenv_path=dotenv_path, override=True) # Use override=True for robustness

from core.context import request_id_ctx

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        return True

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Add the RequestIDFilter to all handlers
request_id_filter = RequestIDFilter()
for handler in logging.getLogger().handlers: # For root logger
    handler.addFilter(request_id_filter)

# Also add the RequestIDFilter to uvicorn.access logger's handlers
uvicorn_access_logger = logging.getLogger("uvicorn.access")
for handler in uvicorn_access_logger.handlers:
    handler.addFilter(request_id_filter)


def get_printable_settings(settings_obj):
    """
    Returns a JSON string representation of the settings object,
    with secret values automatically redacted by Pydantic.
    """
    printable_settings = {}
    for key, value in settings_obj.__dict__.items():
        if isinstance(value, BaseSettings):
            printable_settings[key] = value.model_dump(mode='json')
        else:
            printable_settings[key] = value
    return json.dumps(printable_settings, indent=2)


# Export necessary objects
__all__ = ["settings", "logger", "LOGGING_CONFIG", "LOG_DIR", "BASE_DIR", "get_printable_settings"]
