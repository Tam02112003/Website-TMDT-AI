# -*- coding: utf-8 -*-
"""
Restores a JSON backup produced by services/BackupService.py (via POST
/admin/backup) back into whatever Postgres database is configured through
the app's own settings (app/env/.env.<ENV>).

Why a script and not an API endpoint: restoring overwrites live data
(upsert by id), so it's a deliberate, rare, admin-run-by-hand operation -
not something exposed for anyone to trigger over HTTP.

Safe to re-run: every row is an upsert (INSERT ... ON CONFLICT (id) DO
UPDATE), so restoring the same backup twice converges to the same state
rather than duplicating rows. Sequences are reset after each table so the
next auto-generated id doesn't collide with a restored one.

The backup never contains `users.password` (excluded at export time, see
EXCLUDED_COLUMNS in BackupService.py) - restoring a user row leaves their
existing password untouched if they already exist, or NULL if they don't
(they'll need "forgot password" / Google sign-in, or an admin reset).

Usage:
    cd app
    python scripts/restore_backup.py path/to/tamstore-backup-....json
    python scripts/restore_backup.py path/to/backup.json --yes   # skip the confirmation prompt
"""
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')

import asyncpg

from core.settings import settings
from services.BackupService import BACKUP_TABLES

# Columns that need converting back from JSON's plain types into what
# asyncpg expects for that Postgres column type - the backup JSON itself
# carries no type metadata, so this has to be known per-table like the
# export side already does for EXCLUDED_COLUMNS.
JSONB_COLUMNS = {
    "products": {"image_urls"},
}

DATETIME_COLUMNS = {
    "cart": {"created_at"},
    "orders": {"created_at"},
    "products": {"created_at", "updated_at", "release_date"},
    "discounts": {"start_date", "end_date"},
    "news": {"created_at", "updated_at"},
    "comments": {"created_at"},
    "reviews": {"created_at", "updated_at"},
}


def _coerce_value(table_name: str, column: str, value):
    if value is None:
        return None
    if column in JSONB_COLUMNS.get(table_name, set()):
        return json.dumps(value)
    if column in DATETIME_COLUMNS.get(table_name, set()) and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


async def _restore_table(db: asyncpg.Connection, table_name: str, rows: list) -> int:
    if not rows:
        return 0

    columns = list(rows[0].keys())
    other_columns = [c for c in columns if c != "id"]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in other_columns)

    query = (
        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {update_clause}"
        if other_columns
        else f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
    )

    for row in rows:
        values = [_coerce_value(table_name, col, row.get(col)) for col in columns]
        await db.execute(query, *values)

    await db.execute(
        f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table_name}), 1))"
    )
    return len(rows)


async def restore(file_path: str, skip_confirm: bool):
    with open(file_path, encoding="utf-8") as f:
        backup = json.load(f)

    tables = backup.get("tables", {})
    print(f"Backup generated at: {backup.get('generated_at', 'unknown')}")
    print("Rows to restore (upsert by id):")
    for table_name in BACKUP_TABLES:
        print(f"  {table_name}: {len(tables.get(table_name, []))}")

    if not skip_confirm:
        answer = input("\nThis will INSERT/UPDATE rows in the live database. Continue? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    conn = await asyncpg.connect(
        dsn=settings.DB.DATABASE_URL,
        ssl="require" if settings.DB.HOST not in ("localhost", "127.0.0.1") else None,
        statement_cache_size=0,
    )
    try:
        for table_name in BACKUP_TABLES:
            restored = await _restore_table(conn, table_name, tables.get(table_name, []))
            print(f"Restored {restored} row(s) into {table_name}")
    finally:
        await conn.close()

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_backup.py path/to/backup.json [--yes]")
        sys.exit(1)

    backup_path = sys.argv[1]
    skip_confirm_flag = "--yes" in sys.argv[2:]
    asyncio.run(restore(backup_path, skip_confirm_flag))
