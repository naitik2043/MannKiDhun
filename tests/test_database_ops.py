import sqlite3
import tempfile
import unittest
from pathlib import Path

from database_migrations import run_migrations
from database_ops import backup_database, restore_database, verify_database


class DatabaseOperationsTests(unittest.TestCase):
    def test_migrations_are_versioned_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.sqlite3"
            with sqlite3.connect(path) as connection:
                connection.executescript(
                    "CREATE TABLE users (id INTEGER PRIMARY KEY);"
                    "CREATE TABLE playlists (id INTEGER PRIMARY KEY, user_id INTEGER);"
                )
            self.assertEqual(run_migrations(path), 1)
            self.assertEqual(run_migrations(path), 1)
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 1)
                self.assertIsNotNone(connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='listening_rooms'"
                ).fetchone())

    def test_backup_verify_and_restore_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live, backup, restored = root / "live.sqlite3", root / "good.sqlite3", root / "restored.sqlite3"
            with sqlite3.connect(live) as connection:
                connection.execute("CREATE TABLE songs (id INTEGER PRIMARY KEY, title TEXT)")
                connection.execute("INSERT INTO songs (title) VALUES ('Original')")
            self.assertEqual(backup_database(live, backup)["integrity"], "ok")
            self.assertTrue(verify_database(backup)["ok"])
            restore_database(backup, restored)
            with sqlite3.connect(restored) as connection:
                self.assertEqual(connection.execute("SELECT title FROM songs").fetchone()[0], "Original")

    def test_restore_requires_confirmation_and_preserves_existing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live, backup = root / "live.sqlite3", root / "backup.sqlite3"
            with sqlite3.connect(live) as connection:
                connection.execute("CREATE TABLE songs (title TEXT)")
                connection.execute("INSERT INTO songs VALUES ('Current')")
            backup_database(live, backup)
            with self.assertRaises(FileExistsError):
                restore_database(backup, live)
            result = restore_database(backup, live, overwrite=True)
            self.assertTrue(result["safety_backup"])
            self.assertTrue(Path(result["safety_backup"]).is_file())

    def test_corrupt_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "corrupt.sqlite3"
            corrupt.write_bytes(b"not a sqlite database")
            self.assertFalse(verify_database(corrupt)["ok"])
            with self.assertRaises(sqlite3.DatabaseError):
                restore_database(corrupt, Path(directory) / "restored.sqlite3")


if __name__ == "__main__":
    unittest.main()
