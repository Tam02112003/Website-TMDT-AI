import logging
import datetime
import os
from pathlib import Path
from core.settings import settings
from core.context import request_id_ctx
import uvicorn.logging
import re

# Vercel (and most serverless platforms) mount a read-only filesystem except
# /tmp, so file-based log handlers can't be created there. Fall back to
# console-only logging in that case; Vercel captures stdout/stderr as
# runtime logs anyway.
IS_SERVERLESS = bool(os.environ.get("VERCEL"))

BASE_DIR = Path(__file__).resolve().parent.parent

class UvicornAccessFormatter(uvicorn.logging.AccessFormatter):
    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, 'scope') and isinstance(record.scope, dict):
            record.request_id = record.scope.get("_request_id", "")
        else:
            record.request_id = ""
        
        # Get the formatted message from the parent class
        message = super().format(record)
        
        # Regex to remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\-_]|[0-9A-Z\-_]|[\[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', message)

class StandardFormatter(logging.Formatter):
    def format(self, record):
        record.request_id = request_id_ctx.get(None) or ""
        return super().format(record)

# Logging configuration
LOG_DIR = BASE_DIR / "logs"
if not IS_SERVERLESS:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

log_file_path = str(LOG_DIR / f"app_{datetime.date.today().strftime('%Y-%m-%d')}.log")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "()": "core.logging_config.StandardFormatter",
            "format": "%(asctime)s - %(name)s - [%(filename)s:%(lineno)d - %(funcName)s()] - %(levelname)s - %(request_id)s - %(message)s"
        },
        "uvicorn_access": {
            "()": "core.logging_config.UvicornAccessFormatter",
            "fmt": "%(asctime)s - %(levelname)s - %(request_id)s - %(client_addr)s - \"%(request_line)s\" %(status_code)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "uvicorn_access_console": {
            "class": "logging.StreamHandler",
            "formatter": "uvicorn_access",
        },
        **({} if IS_SERVERLESS else {
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": log_file_path,
                "when": "midnight",
                "interval": 1,
                "backupCount": 7,
                "formatter": "standard",
                "encoding": "utf-8",
            },
            "uvicorn_access_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": log_file_path,
                "when": "midnight",
                "interval": 1,
                "backupCount": 7,
                "formatter": "uvicorn_access",
                "encoding": "utf-8",
            },
        }),
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console"] if IS_SERVERLESS else ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console"] if IS_SERVERLESS else ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["uvicorn_access_console"] if IS_SERVERLESS else ["uvicorn_access_console", "uvicorn_access_file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.app_config": {
            "handlers": ["console"] if IS_SERVERLESS else ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
