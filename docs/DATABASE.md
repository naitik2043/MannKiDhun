# Database

The application currently uses a single SQLite file at `instance/moodwave.sqlite3`. The file is created by the application and is ignored by Git. Existing data in that file should be backed up before updating or running the application.

## Main tables

- `users`: account identity, password hash, verification/onboarding flags, and an optional profile-photo URL. Profile photos are normalized to JPEG and stored under the Git-ignored `instance/profile_uploads/` directory; the database stores only the photo URL.
- `user_preferences`: one row per user; JSON-encoded language, genre, listening-style, and artist lists.
- `password_reset_tokens`: hashed one-time tokens with type, expiry, and use time. Email delivery is not implemented, so account recovery is not currently operational.
- `artists`, `genres`, `songs`, `song_genres`, `song_tags`: local recommendation catalogue and provider metadata.
- `user_song_interactions`, `saved_songs`, `recommendation_events`: user activity and library state.
- `playlists`, `playlist_tracks`: user-owned playlists and ordered catalogue entries.
- `playback_states`: one current playback/queue snapshot per user.

Account-owned data references `users` with `ON DELETE CASCADE`. Track and playlist relations also declare foreign keys. Every application SQLite connection now enables foreign-key enforcement, so those constraints and cascades apply during normal requests as well as schema setup. Catalogue schema creation and the existing additive column checks are performed by Python initialization code; there is no versioned migration framework or rollback command.

The current SQLite-oriented implementation is not verified for PostgreSQL. Do not point `DATABASE_URL` at PostgreSQL; the active app uses `AUTH_DATABASE` and SQLite paths.

## Backup and restore

Stop application writers or use SQLite's online backup API to create a consistent backup. For example:

```powershell
python -c "import sqlite3; source=sqlite3.connect(r'instance\moodwave.sqlite3'); target=sqlite3.connect(r'instance\moodwave.backup.sqlite3'); source.backup(target); target.close(); source.close()"
```

To restore, stop the application, preserve a separate copy of the current database, then replace the database file with a verified backup. Start the app and check `/healthz` and account/library reads. This is a manual procedure; automated backups and restore drills are not configured.
