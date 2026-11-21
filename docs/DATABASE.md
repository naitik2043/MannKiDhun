# Database

The application uses a single SQLite file at `<MANNKIDHUN_DATA_DIR>/moodwave.sqlite3`. If `MANNKIDHUN_DATA_DIR` is unset, the default is `instance/moodwave.sqlite3` under the repository root. The same data directory contains the `profile_uploads/` directory. The directory is created by the application and is ignored by Git. Back up the database before updating or running the application.

## Main tables

- `users`: account identity, password hash, verification/onboarding flags, and an optional profile-photo URL. Profile photos are normalized to JPEG and stored under the configured data directory's `profile_uploads/` directory; the database stores only the photo URL.
- `user_preferences`: one row per user; JSON-encoded language, genre, listening-style, and artist lists plus the opt-in `music_dna_enabled` flag.
- `mood_journal_entries`: private, manually entered mood labels and optional notes, account-scoped with cascade deletion.
- `password_reset_tokens`: hashed one-time tokens with type, expiry, and use time. Email delivery is not implemented, so account recovery is not currently operational.
- `artists`, `genres`, `songs`, `song_genres`, `song_tags`: local recommendation catalogue and provider metadata.
- `user_song_interactions`, `saved_songs`, `recommendation_events`: user activity and library state.
- `playlists`, `playlist_tracks`: user-owned playlists and ordered catalogue entries.
- `playlist_collaborators`: user membership with viewer/editor role, unique per playlist/user.
- `playlist_invites`: hashed bearer invitation tokens with role, expiry, and revocation timestamps; raw tokens are returned only at creation time.
- `playback_states`: one current playback / queue snapshot per user. The global player writes the current track, elapsed position, queue IDs, and repeat mode.
- `listening_rooms`, `listening_room_participants`: six-hour invite-only group rooms, hashed bearer tokens, shared playlist state, optimistic version, and recent participant presence.
- `schema_migrations`: ordered migration versions and timestamps; migration 1 creates the group listening room tables.

Account-owned data references `users` with `ON DELETE CASCADE`. Track and playlist relations also declare foreign keys. Every application SQLite connection enables foreign-key enforcement. `database_migrations.py` applies ordered, idempotent migrations at startup and records each applied version in `schema_migrations`; migration 1 creates group-room tables. Migrations do not yet provide rollback, so make a backup before applying schema changes.

The current SQLite-oriented implementation is not verified for PostgreSQL. Do not point `DATABASE_URL` at PostgreSQL; the active app uses `AUTH_DATABASE` and SQLite paths. A mounted Render disk can provide persistence for a single service instance, but it does not replace a managed database or make multi-instance SQLite safe.

## Backup, verification, and restore

The repository includes `database_ops.py`, which uses SQLite's online backup API and verifies database integrity plus foreign-key consistency.

From the repository root:

```powershell
# Verify the active database.
python database_ops.py verify

# Create and verify a consistent online backup.
python database_ops.py backup --output backups\moodwave-backup.sqlite3

# Restore a verified backup. --overwrite first preserves the current DB
# in a timestamped .pre-restore safety copy.
python database_ops.py restore --source backups\moodwave-backup.sqlite3 --overwrite
```

Pass `--database <path>` to manage a non-default database. The default path follows `MANNKIDHUN_DATA_DIR` or `instance/moodwave.sqlite3`. Stop application writers before restoring. These are manual utilities; they do not schedule off-site backups, encrypt backup files, or replace a regular restore drill.
