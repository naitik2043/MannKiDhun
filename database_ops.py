"""Safe SQLite backup, integrity verification, and restore utilities."""
from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def verify_database(database_path):
    path = Path(database_path)
    if not path.is_file():
        return {"ok": False, "integrity": "missing", "foreign_key_violations": []}
    try:
        with closing(sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=10)) as connection:
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
            foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = integrity_rows[0][0] if integrity_rows else "no result"
        violations = [tuple(row) for row in foreign_key_rows]
        return {"ok": integrity == "ok" and not violations, "integrity": integrity, "foreign_key_violations": violations}
    except sqlite3.Error as error:
        return {"ok": False, "integrity": str(error), "foreign_key_violations": []}


def _copy_database(source_path, target_path):
    with closing(sqlite3.connect(f"file:{Path(source_path).resolve()}?mode=ro", uri=True, timeout=10)) as source:
        with closing(sqlite3.connect(target_path, timeout=10)) as target:
            source.backup(target)
            target.commit()


def backup_database(database_path, backup_path):
    source_path = Path(database_path).resolve()
    target_path = Path(backup_path).resolve()
    if source_path == target_path:
        raise ValueError("The backup path must be different from the live database.")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.", suffix=".tmp", dir=target_path.parent
    )
    os.close(descriptor)
    try:
        _copy_database(source_path, temporary_name)
        verification = verify_database(temporary_name)
        if not verification["ok"]:
            raise sqlite3.DatabaseError(f"Backup verification failed: {verification}")
        os.replace(temporary_name, target_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return {
        "database": str(source_path),
        "backup": str(target_path),
        "integrity": "ok",
        "size_bytes": target_path.stat().st_size,
    }


def restore_database(backup_path, database_path, overwrite=False):
    source_path = Path(backup_path).resolve()
    target_path = Path(database_path).resolve()
    if source_path == target_path:
        raise ValueError("The backup and destination database must be different files.")
    verification = verify_database(source_path)
    if not verification["ok"]:
        raise sqlite3.DatabaseError(f"Refusing to restore an invalid backup: {verification}")
    if target_path.exists() and not overwrite:
        raise FileExistsError(
            f"{target_path} already exists. Use --overwrite only after confirming the restore."
        )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    safety_backup = None
    if target_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safety_backup = target_path.with_name(f"{target_path.name}.pre-restore-{timestamp}")
        backup_database(target_path, safety_backup)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.", suffix=".restore", dir=target_path.parent
    )
    os.close(descriptor)
    try:
        _copy_database(source_path, temporary_name)
        copied = verify_database(temporary_name)
        if not copied["ok"]:
            raise sqlite3.DatabaseError(f"Restored copy failed verification: {copied}")
        os.replace(temporary_name, target_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return {
        "restored_from": str(source_path),
        "database": str(target_path),
        "integrity": "ok",
        "safety_backup": str(safety_backup) if safety_backup else None,
    }


def _default_database_path():
    configured = os.environ.get("MANNKIDHUN_DATA_DIR", "").strip()
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parent / "instance"
    return root / "moodwave.sqlite3"


def main():
    parser = argparse.ArgumentParser(description="Manage MannKiDhun SQLite backups safely.")
    parser.add_argument("--database", default=str(_default_database_path()))
    commands = parser.add_subparsers(dest="command", required=True)
    backup_parser = commands.add_parser("backup", help="Create and verify a consistent online backup.")
    backup_parser.add_argument("--output", required=True)
    restore_parser = commands.add_parser("restore", help="Restore a verified backup.")
    restore_parser.add_argument("--source", required=True)
    restore_parser.add_argument("--overwrite", action="store_true")
    commands.add_parser("verify", help="Run SQLite integrity and foreign-key checks.")

    args = parser.parse_args()
    if args.command == "backup":
        result = backup_database(args.database, args.output)
    elif args.command == "restore":
        result = restore_database(args.source, args.database, overwrite=args.overwrite)
    else:
        result = verify_database(args.database)
    print(result)
    if not result.get("ok", True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
