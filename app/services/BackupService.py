import asyncpg
import json
import tempfile
import os
from datetime import datetime, date
from typing import Dict, List
from starlette.concurrency import run_in_threadpool
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from core.settings import settings
from core.app_config import logger

# Every business table, in an order that keeps foreign-key references
# human-readable when restoring by hand (parents before children).
BACKUP_TABLES = [
    "categories", "brands", "products", "users", "discounts",
    "orders", "order_items", "cart", "news", "comments", "reviews",
]

# Columns to leave out of the backup entirely - never export a password hash,
# even though it's hashed, there's no reason for a data backup to carry it.
EXCLUDED_COLUMNS = {
    "users": {"password"},
}

DRIVE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


async def _export_table(db: asyncpg.Connection, table_name: str) -> List[dict]:
    excluded = EXCLUDED_COLUMNS.get(table_name, set())
    rows = await db.fetch(f"SELECT * FROM {table_name}")
    return [{k: v for k, v in dict(row).items() if k not in excluded} for row in rows]


async def export_database_backup(db: asyncpg.Connection) -> dict:
    """Reads every business table via the normal DB connection (no pg_dump -
    not available in the Vercel Python runtime) into one JSON-serializable
    structure. Restoring from it means writing rows back table-by-table, not
    running it through `psql` directly."""
    tables: Dict[str, List[dict]] = {}
    for table_name in BACKUP_TABLES:
        tables[table_name] = await _export_table(db, table_name)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "tables": tables,
    }


def _upload_to_drive(file_path: str, file_name: str) -> dict:
    if not settings.GDRIVE_BACKUP.REFRESH_TOKEN or not settings.GDRIVE_BACKUP.FOLDER_ID:
        raise RuntimeError("Google Drive backup is not configured (missing refresh token or folder id).")

    # Uploads run as the Drive folder's real owner (OAuth refresh token from
    # the one-time /admin/backup/authorize flow), not a service account -
    # service accounts have no storage quota of their own and can't write new
    # files into a personal (non-Workspace) Drive folder even as an Editor.
    credentials = Credentials(
        token=None,
        refresh_token=settings.GDRIVE_BACKUP.REFRESH_TOKEN.get_secret_value(),
        client_id=settings.GOOGLE.CLIENT_ID,
        client_secret=settings.GOOGLE.CLIENT_SECRET.get_secret_value(),
        token_uri=settings.GOOGLE.TOKEN_URL,
        scopes=DRIVE_UPLOAD_SCOPES,
    )
    drive_service = build("drive", "v3", credentials=credentials)

    file_metadata = {"name": file_name, "parents": [settings.GDRIVE_BACKUP.FOLDER_ID]}
    media = MediaFileUpload(file_path, mimetype="application/json", resumable=False)
    uploaded = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id, name, webViewLink"
    ).execute()
    return uploaded


async def create_and_upload_backup(db: asyncpg.Connection) -> dict:
    backup = await export_database_backup(db)
    table_row_counts = {name: len(rows) for name, rows in backup["tables"].items()}

    file_name = f"tamstore-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(backup, tmp, ensure_ascii=False, default=_json_default)
            tmp_path = tmp.name

        # google-api-python-client's upload call is synchronous (blocking I/O),
        # so it must not run directly on the event loop.
        uploaded = await run_in_threadpool(_upload_to_drive, tmp_path, file_name)
    except Exception as e:
        logger.error(f"Database backup upload failed: {e}", exc_info=True)
        raise
    finally:
        # A cleanup failure here (e.g. Windows still holding the file handle
        # open after a failed upload) must never shadow the real exception
        # from the try block - log it and move on instead of letting it
        # propagate and replace the original error.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as cleanup_error:
                logger.warning(f"Failed to remove temp backup file {tmp_path}: {cleanup_error}")

    return {
        "file_name": uploaded.get("name", file_name),
        "drive_link": uploaded.get("webViewLink"),
        "table_row_counts": table_row_counts,
    }
