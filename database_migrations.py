"""Versioned, idempotent SQLite migrations for MannKiDhun."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS = []


def _migration_1(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS listening_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            state_json TEXT NOT NULL DEFAULT '{}',
            version INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS listening_room_participants (
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(room_id, user_id),
            FOREIGN KEY(room_id) REFERENCES listening_rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_listening_rooms_expiry ON listening_rooms(expires_at)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_room_participants_seen ON listening_room_participants(room_id, last_seen)"
    )


MIGRATIONS = [(1, "group_listening_rooms", _migration_1)]


def run_migrations(database_path):
    """Apply missing migrations in order and return the current schema version."""
    database_path = str(Path(database_path))
    with closing(sqlite3.connect(database_path, timeout=10)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
        for version, name, migration in MIGRATIONS:
            applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()
            if applied:
                continue
            with connection:
                migration(connection)
                connection.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
                )
        row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)
