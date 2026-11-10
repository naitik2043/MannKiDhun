import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

RECOMMENDATION_WEIGHTS = {
    "preference_match": 0.30,
    "content_similarity": 0.25,
    "vibe_match": 0.20,
    "artist_preference": 0.15,
    "behavioural_relevance": 0.10,
}


def _connect_database(database_path, **options):
    connection = sqlite3.connect(database_path, **options)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


VIBE_ALIASES = {
    "happy": "happy",
    "sad": "sad",
    "angry": "angry",
    "neutral": "neutral",
    "surprise": "surprise",
    "rock": "rock",
    "romantic": "romantic",
    "relaxed": "relaxed",
    "energetic": "energetic",
    "motivational": "motivational",
    "focused": "focused",
    "peaceful": "relaxed",
    "melancholic": "sad",
    "devotional": "devotional",
}

DEFAULT_SONGS = [
    {
        "title": "Levitating",
        "artist": "Dua Lipa",
        "album": "Future Nostalgia",
        "language": "English",
        "genre": "Pop",
        "duration": 203,
        "provider": "youtube",
        "provider_track_id": "TUVcZfQe-Kw",
        "provider_url": "https://www.youtube.com/watch?v=TUVcZfQe-Kw",
        "thumbnail_url": "https://img.youtube.com/vi/TUVcZfQe-Kw/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["happy", "energetic", "romantic"],
        "tags": ["dance", "uplifting", "sunny"],
    },
    {
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "album": "÷",
        "language": "English",
        "genre": "Pop",
        "duration": 233,
        "provider": "youtube",
        "provider_track_id": "JGwWNGJdvx8",
        "provider_url": "https://www.youtube.com/watch?v=JGwWNGJdvx8",
        "thumbnail_url": "https://img.youtube.com/vi/JGwWNGJdvx8/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["happy", "romantic", "motivational"],
        "tags": ["catchy", "feel-good", "acoustic"],
    },
    {
        "title": "Aankhon Mein Teri",
        "artist": "Arijit Singh",
        "album": "Om Shaanti Om",
        "language": "Hindi",
        "genre": "Romance",
        "duration": 260,
        "provider": "youtube",
        "provider_track_id": "y4jW0h7_Jlg",
        "provider_url": "https://www.youtube.com/watch?v=y4jW0h7_Jlg",
        "thumbnail_url": "https://img.youtube.com/vi/y4jW0h7_Jlg/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["romantic", "peaceful", "happy"],
        "tags": ["soft", "romantic", "melodic"],
    },
    {
        "title": "Kal Ho Naa Ho",
        "artist": "Shankar-Ehsaan-Loy",
        "album": "Kal Ho Naa Ho",
        "language": "Hindi",
        "genre": "Rock",
        "duration": 235,
        "provider": "youtube",
        "provider_track_id": "2GIFdM0S9dM",
        "provider_url": "https://www.youtube.com/watch?v=2GIFdM0S9dM",
        "thumbnail_url": "https://img.youtube.com/vi/2GIFdM0S9dM/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["sad", "melancholic", "motivational"],
        "tags": ["slow", "ballad", "uplifting"],
    },
    {
        "title": "Senorita",
        "artist": "Shawn Mendes",
        "album": "Senorita",
        "language": "English",
        "genre": "Pop",
        "duration": 191,
        "provider": "youtube",
        "provider_track_id": "Pkh8UtuejGw",
        "provider_url": "https://www.youtube.com/watch?v=Pkh8UtuejGw",
        "thumbnail_url": "https://img.youtube.com/vi/Pkh8UtuejGw/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["happy", "romantic", "energetic"],
        "tags": ["latin", "dance", "romantic"],
    },
    {
        "title": "Namo Namo",
        "artist": "Amit Trivedi",
        "album": "Kedarnath",
        "language": "Hindi",
        "genre": "Devotional",
        "duration": 270,
        "provider": "youtube",
        "provider_track_id": "QyW8oJrlig4",
        "provider_url": "https://www.youtube.com/watch?v=QyW8oJrlig4",
        "thumbnail_url": "https://img.youtube.com/vi/QyW8oJrlig4/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["devotional", "peaceful", "motivational"],
        "tags": ["spiritual", "inspiring", "calm"],
    },
    {
        "title": "Agar Tum Saath Ho",
        "artist": "Alka Yagnik",
        "album": "Tamasha",
        "language": "Hindi",
        "genre": "Romance",
        "duration": 298,
        "provider": "youtube",
        "provider_track_id": "4L7cMfcP2C0",
        "provider_url": "https://www.youtube.com/watch?v=4L7cMfcP2C0",
        "thumbnail_url": "https://img.youtube.com/vi/4L7cMfcP2C0/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["romantic", "sad", "peaceful"],
        "tags": ["romantic", "soft", "soulful"],
    },
    {
        "title": "Ocean Eyes",
        "artist": "Billie Eilish",
        "album": "When We All Fall Asleep, Where Do We Go?",
        "language": "English",
        "genre": "Indie Pop",
        "duration": 200,
        "provider": "youtube",
        "provider_track_id": "vi2Zw3w8tEY",
        "provider_url": "https://www.youtube.com/watch?v=vi2Zw3w8tEY",
        "thumbnail_url": "https://img.youtube.com/vi/vi2Zw3w8tEY/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["relaxed", "peaceful", "sad"],
        "tags": ["dreamy", "calm", "indie"],
    },
    {
        "title": "Believer",
        "artist": "Imagine Dragons",
        "album": "Evolve",
        "language": "English",
        "genre": "Rock",
        "duration": 204,
        "provider": "youtube",
        "provider_track_id": "7wtfhZwyrcc",
        "provider_url": "https://www.youtube.com/watch?v=7wtfhZwyrcc",
        "thumbnail_url": "https://img.youtube.com/vi/7wtfhZwyrcc/hqdefault.jpg",
        "explicit": 0,
        "vibes": ["angry", "energetic", "motivational"],
        "tags": ["rock", "powerful", "driving"],
    },
]


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _coerce_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (TypeError, ValueError):
            pass
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_vibe(value):
    vibe = _normalize_text(value)
    if not vibe:
        return "neutral"
    return VIBE_ALIASES.get(vibe, vibe)


def build_hybrid_recommendations(
    songs,
    user_preferences=None,
    mood=None,
    vibe=None,
    interaction_history=None,
    limit=6,
    query_filters=None,
):
    user_preferences = user_preferences or {}
    interaction_history = interaction_history or {}
    query_filters = query_filters or {}
    effective_vibe = _normalize_vibe(vibe or mood or user_preferences.get("selected_vibe") or "neutral")

    preferred_genres = {_normalize_text(item) for item in user_preferences.get("genres", [])}
    preferred_languages = {_normalize_text(item) for item in user_preferences.get("languages", [])}
    favourite_artists = {_normalize_text(item) for item in user_preferences.get("artists", [])}
    listening_styles = {_normalize_text(item) for item in user_preferences.get("listening_styles", [])}

    ranked = []
    seen = set()
    for song in songs:
        song_id = song.get("id")
        if song_id is None:
            song_id = song.get("provider_track_id") or song.get("title")
        if song_id in seen:
            continue
        seen.add(song_id)

        song_genres = {_normalize_text(item) for item in song.get("genres", []) or _coerce_list(song.get("genre"))}
        if song.get("genre") and not song_genres:
            song_genres.add(_normalize_text(song.get("genre")))
        song_language = _normalize_text(song.get("language"))
        song_artist = _normalize_text(song.get("artist"))
        song_tags = {_normalize_text(item) for item in song.get("tags", [])}
        song_vibes = {_normalize_vibe(item) for item in song.get("vibes", [])}

        requested_genre = _normalize_text(query_filters.get("genre"))
        requested_language = _normalize_text(query_filters.get("language"))
        requested_artist = _normalize_text(query_filters.get("artist"))
        requested_vibe = (
            _normalize_vibe(query_filters["vibe"]) if query_filters.get("vibe") else None
        )
        if requested_genre and requested_genre not in song_genres:
            continue
        if requested_language and requested_language != song_language:
            continue
        if requested_artist and requested_artist != song_artist:
            continue
        if requested_vibe and requested_vibe not in song_vibes:
            continue

        preference_match = 0.0
        if song_language and song_language in preferred_languages:
            preference_match += 0.35
        if song_genres and preferred_genres and (song_genres & preferred_genres):
            preference_match += 0.50
        if song_artist and song_artist in favourite_artists:
            preference_match += 0.50
        if song_tags and listening_styles and (song_tags & listening_styles):
            preference_match += 0.25
        if not any({song_language, *song_genres, song_artist}) and not preferred_genres and not preferred_languages:
            preference_match = 0.10

        content_similarity = 0.0
        if song_genres and preferred_genres:
            content_similarity += 0.50 * len(song_genres & preferred_genres) / max(1, len(preferred_genres))
        if song_language and preferred_languages:
            content_similarity += 0.25 if song_language in preferred_languages else 0.0
        if song_artist and favourite_artists:
            content_similarity += 0.25 if song_artist in favourite_artists else 0.0

        vibe_match = 0.0
        if song_vibes:
            vibe_match = 1.0 if effective_vibe in song_vibes else 0.35 if "neutral" == effective_vibe else 0.15
        else:
            vibe_match = 0.25 if effective_vibe == "neutral" else 0.1

        artist_preference = 1.0 if song_artist and song_artist in favourite_artists else 0.0
        historical_relevance = float(interaction_history.get(song_id, 0.0) or interaction_history.get(str(song_id), 0.0) or 0.0)
        behavioural_relevance = min(historical_relevance / 3.0, 1.0)

        score = (
            RECOMMENDATION_WEIGHTS["preference_match"] * preference_match
            + RECOMMENDATION_WEIGHTS["content_similarity"] * content_similarity
            + RECOMMENDATION_WEIGHTS["vibe_match"] * vibe_match
            + RECOMMENDATION_WEIGHTS["artist_preference"] * artist_preference
            + RECOMMENDATION_WEIGHTS["behavioural_relevance"] * behavioural_relevance
        )

        reasons = []
        if song_language and song_language in preferred_languages:
            reasons.append(f"You enjoy {song_language} music.")
        if song_genres and preferred_genres and (song_genres & preferred_genres):
            reasons.append(f"It matches your favourite {', '.join(sorted(song_genres & preferred_genres))} picks.")
        if song_artist and song_artist in favourite_artists:
            reasons.append(f"Because you like {song.get('artist')}.")
        if effective_vibe in song_vibes:
            reasons.append(f"Suggested based on your selected {effective_vibe.title()} vibe.")
        if not reasons:
            reasons.append("Fresh discovery based on the broader catalogue.")

        ranked.append(
            {
                "id": song_id,
                "title": song.get("title"),
                "artist": song.get("artist"),
                "album": song.get("album"),
                "language": song.get("language"),
                "genre": song.get("genre") or (sorted(song_genres)[:1] or [""])[0],
                "provider": song.get("provider", "youtube"),
                "provider_track_id": song.get("provider_track_id") or song.get("provider_url"),
                "provider_url": song.get("provider_url"),
                "thumbnail_url": song.get("thumbnail_url"),
                "duration": song.get("duration"),
                "score": round(float(score), 4),
                "vibe": effective_vibe,
                "explanation": " ".join(reasons[:2]),
                "metadata": {
                    "vibes": song.get("vibes", []),
                    "tags": song.get("tags", []),
                    "genre": song.get("genre") or (sorted(song_genres)[:1] or [""])[0],
                },
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["title"] or ""))
    return ranked[:limit]


def _fetch_music_rows(connection):
    rows = connection.execute(
        """
        SELECT s.id, s.title, a.name AS artist, s.album, s.language, s.genre, s.duration,
               s.thumbnail_url, s.provider, s.provider_track_id, s.provider_url,
               s.metadata, COALESCE(GROUP_CONCAT(DISTINCT g.name), '') AS genres,
               COALESCE(GROUP_CONCAT(DISTINCT st.tag), '') AS tags, s.explicit
        FROM songs s
        LEFT JOIN artists a ON a.id = s.artist_id
        LEFT JOIN song_genres sg ON sg.song_id = s.id
        LEFT JOIN genres g ON g.id = sg.genre_id
        LEFT JOIN song_tags st ON st.song_id = s.id
        GROUP BY s.id
        ORDER BY s.title
        """
    ).fetchall()

    songs = []
    for row in rows:
        metadata = {}
        if row[11]:
            try:
                metadata = json.loads(row[11])
            except (TypeError, ValueError):
                metadata = {}
        tags = _coerce_list(row[13])
        vibes = _coerce_list(metadata.get("vibes", []))
        if not vibes:
            vibes = _coerce_list(metadata.get("vibe"))
        genres = _coerce_list(row[12])
        if not genres and row[5]:
            genres = [row[5]]
        songs.append(
            {
                "id": row[0],
                "title": row[1],
                "artist": row[2],
                "album": row[3],
                "language": row[4],
                "genre": row[5],
                "duration": row[6],
                "thumbnail_url": row[7],
                "provider": row[8],
                "provider_track_id": row[9],
                "provider_url": row[10],
                "tags": tags,
                "vibes": vibes,
                "genres": genres,
                "explicit": bool(row[14]),
                "metadata": metadata,
            }
        )
    return songs


def _fetch_interaction_history(connection, user_id):
    if user_id is None:
        return {}
    rows = connection.execute(
        "SELECT song_id, COUNT(*) AS total FROM user_song_interactions WHERE user_id = ? GROUP BY song_id",
        (user_id,),
    ).fetchall()
    return {str(row[0]): float(row[1]) for row in rows}


def _fetch_user_preferences(connection, user_id):
    if user_id is None:
        return {"genres": [], "languages": [], "artists": [], "listening_styles": [], "selected_vibe": "neutral"}
    row = connection.execute(
        "SELECT preferred_languages, preferred_genres, preferred_listening_styles, favourite_artists FROM user_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        user = connection.execute(
            "SELECT username, full_name, name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            return {"genres": [], "languages": [], "artists": [], "listening_styles": [], "selected_vibe": "neutral"}
        name = user[1] or user[2] or user[0] or ""
        return {"genres": [], "languages": [], "artists": [], "listening_styles": [], "selected_vibe": "neutral", "name": name}

    return {
        "languages": _coerce_list(row[0]),
        "genres": _coerce_list(row[1]),
        "listening_styles": _coerce_list(row[2]),
        "artists": _coerce_list(row[3]),
        "selected_vibe": "neutral",
    }


def get_user_recommendations(
    database_path,
    user_id=None,
    mood=None,
    vibe=None,
    limit=6,
    include_preferences=True,
    include_history=True,
    query_filters=None,
):
    with closing(_connect_database(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        songs = _fetch_music_rows(connection)
        preferences = (
            _fetch_user_preferences(connection, user_id)
            if include_preferences
            else {"genres": [], "languages": [], "artists": [], "listening_styles": []}
        )
        interactions = (
            _fetch_interaction_history(connection, user_id) if include_history else {}
        )
        return build_hybrid_recommendations(
            songs,
            user_preferences=preferences,
            mood=mood,
            vibe=vibe,
            interaction_history=interactions,
            limit=limit,
            query_filters=query_filters,
        )


def record_user_interaction(database_path, user_id, song_id, interaction_type, source=None, position_ms=None, duration_ms=None):
    if user_id is None or song_id is None:
        return False
    interaction_type = str(interaction_type).strip().lower()
    if not interaction_type:
        return False
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    source = (source or "unknown").strip() or "unknown"
    position_ms = int(position_ms or 0)
    duration_ms = int(duration_ms or 0)
    with closing(_connect_database(database_path)) as connection, connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO user_song_interactions (user_id, song_id, interaction_type, source, position_ms, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, song_id, interaction_type, source, position_ms, duration_ms, timestamp,),
        )
        if interaction_type == "save":
            connection.execute(
                "INSERT OR IGNORE INTO saved_songs (user_id, song_id, created_at) VALUES (?, ?, ?)",
                (user_id, song_id, timestamp),
            )
    return True


def create_music_catalogue(database_path):
    with closing(_connect_database(database_path)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                normalized_name TEXT NOT NULL UNIQUE,
                external_provider_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                normalized_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist_id INTEGER NOT NULL,
                album TEXT,
                language TEXT,
                genre TEXT,
                duration INTEGER,
                thumbnail_url TEXT,
                provider TEXT NOT NULL DEFAULT 'youtube',
                provider_track_id TEXT,
                provider_url TEXT,
                explicit INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(artist_id) REFERENCES artists(id) ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS song_genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                genre_id INTEGER NOT NULL,
                UNIQUE(song_id, genre_id),
                FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE,
                FOREIGN KEY(genre_id) REFERENCES genres(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS song_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                UNIQUE(song_id, tag),
                FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_song_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                source TEXT DEFAULT 'unknown',
                position_ms INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, song_id, interaction_type),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                recommendation_source TEXT NOT NULL,
                ranking_score REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                artwork_url TEXT,
                is_public INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(playlist_id, song_id),
                FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, song_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS playback_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                current_song_id INTEGER,
                position_ms INTEGER NOT NULL DEFAULT 0,
                queue TEXT NOT NULL DEFAULT '[]',
                shuffle INTEGER NOT NULL DEFAULT 0,
                repeat_mode TEXT NOT NULL DEFAULT 'off',
                last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_songs_language ON songs(language)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_song_genres_song ON song_genres(song_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_user_interactions ON user_song_interactions(user_id, song_id, interaction_type)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id, position)")

        _ensure_table_column(connection, "user_song_interactions", "source", "source TEXT DEFAULT 'unknown'")
        _ensure_table_column(connection, "user_song_interactions", "position_ms", "position_ms INTEGER DEFAULT 0")
        _ensure_table_column(connection, "user_song_interactions", "duration_ms", "duration_ms INTEGER DEFAULT 0")

        if connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0] == 0:
            seed_catalogue(connection)


def _get_or_create_artist(connection, artist_name):
    normalized = _normalize_text(artist_name)
    existing = connection.execute(
        "SELECT id FROM artists WHERE normalized_name = ?",
        (normalized,),
    ).fetchone()
    if existing is not None:
        return existing[0]
    cursor = connection.execute(
        "INSERT INTO artists (name, normalized_name, external_provider_id) VALUES (?, ?, NULL)",
        (artist_name, normalized),
    )
    return cursor.lastrowid


def _get_or_create_genre(connection, genre_name):
    normalized = _normalize_text(genre_name)
    existing = connection.execute(
        "SELECT id FROM genres WHERE normalized_name = ?",
        (normalized,),
    ).fetchone()
    if existing is not None:
        return existing[0]
    cursor = connection.execute(
        "INSERT INTO genres (name, normalized_name) VALUES (?, ?)",
        (genre_name, normalized),
    )
    return cursor.lastrowid


def seed_catalogue(connection):
    for song in DEFAULT_SONGS:
        artist_id = _get_or_create_artist(connection, song["artist"])
        metadata = {
            "vibes": song.get("vibes", []),
            "tags": song.get("tags", []),
            "genre": song.get("genre"),
        }
        existing = connection.execute(
            "SELECT id FROM songs WHERE provider = ? AND provider_track_id = ?",
            (song["provider"], song["provider_track_id"]),
        ).fetchone()
        if existing is not None:
            continue
        cursor = connection.execute(
            """
            INSERT INTO songs (
                title, artist_id, album, language, genre, duration, thumbnail_url,
                provider, provider_track_id, provider_url, explicit, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                song["title"],
                artist_id,
                song.get("album"),
                song.get("language"),
                song.get("genre"),
                song.get("duration"),
                song.get("thumbnail_url"),
                song.get("provider"),
                song.get("provider_track_id"),
                song.get("provider_url"),
                int(bool(song.get("explicit"))),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        song_id = cursor.lastrowid
        for genre_name in _coerce_list(song.get("genre")):
            genre_id = _get_or_create_genre(connection, genre_name)
            connection.execute(
                "INSERT OR IGNORE INTO song_genres (song_id, genre_id) VALUES (?, ?)",
                (song_id, genre_id),
            )
        for tag in _coerce_list(song.get("tags")):
            connection.execute(
                "INSERT OR IGNORE INTO song_tags (song_id, tag) VALUES (?, ?)",
                (song_id, tag),
            )
        for vibe in _coerce_list(song.get("vibes")):
            connection.execute(
                "INSERT OR IGNORE INTO song_tags (song_id, tag) VALUES (?, ?)",
                (song_id, f"vibe:{vibe}"),
            )


def get_saved_songs(database_path, user_id):
    with closing(_connect_database(database_path)) as connection, connection:
        rows = connection.execute(
            """
            SELECT s.id, s.title, a.name AS artist, s.language, s.genre, s.provider_url,
                   s.thumbnail_url, COALESCE(ss.created_at, usi.created_at) AS created_at
            FROM saved_songs ss
            JOIN songs s ON s.id = ss.song_id
            LEFT JOIN artists a ON a.id = s.artist_id
            LEFT JOIN user_song_interactions usi
                ON usi.user_id = ss.user_id AND usi.song_id = ss.song_id AND usi.interaction_type = 'save'
            WHERE ss.user_id = ?
            GROUP BY s.id
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        if not rows:
            rows = connection.execute(
                """
                SELECT s.id, s.title, a.name AS artist, s.language, s.genre, s.provider_url,
                       s.thumbnail_url, usi.created_at
                FROM user_song_interactions usi
                JOIN songs s ON s.id = usi.song_id
                LEFT JOIN artists a ON a.id = s.artist_id
                WHERE usi.user_id = ? AND usi.interaction_type = 'save'
                GROUP BY s.id
                ORDER BY usi.created_at DESC
                """,
                (user_id,),
            ).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "language": row[3],
            "genre": row[4],
            "provider_url": row[5],
            "thumbnail_url": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


def get_listening_history(database_path, user_id):
    with closing(_connect_database(database_path)) as connection, connection:
        rows = connection.execute(
            """
            SELECT s.id, s.title, a.name AS artist, s.genre, s.language, usi.created_at,
                   usi.interaction_type, usi.source, usi.position_ms, usi.duration_ms
            FROM user_song_interactions usi
            JOIN songs s ON s.id = usi.song_id
            LEFT JOIN artists a ON a.id = s.artist_id
            WHERE usi.user_id = ? AND usi.interaction_type IN ('like','skip','listen','play','complete')
            ORDER BY usi.created_at DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "genre": row[3],
            "language": row[4],
            "created_at": row[5],
            "interaction_type": row[6],
            "source": row[7],
            "position_ms": row[8],
            "duration_ms": row[9],
        }
        for row in rows
    ]


def clear_listening_history(database_path, user_id):
    with closing(_connect_database(database_path)) as connection, connection:
        connection.execute(
            "DELETE FROM user_song_interactions WHERE user_id = ? AND interaction_type IN ('like','skip','listen','play','complete')",
            (user_id,),
        )


def _ensure_table_column(connection, table_name, column_name, column_sql):
    column_exists = any(
        row[1] == column_name for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    )
    if not column_exists:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def create_playlist(database_path, user_id, name, description="", artwork_url="", is_public=False):
    if user_id is None:
        return None
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ValueError("Playlist name is required.")
    with closing(_connect_database(database_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO playlists (user_id, name, description, artwork_url, is_public, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                cleaned_name,
                (description or "").strip(),
                artwork_url or "",
                int(bool(is_public)),
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        return {
            "id": cursor.lastrowid,
            "user_id": user_id,
            "name": cleaned_name,
            "description": (description or "").strip(),
            "artwork_url": artwork_url or "",
            "is_public": bool(is_public),
        }


def get_user_playlists(database_path, user_id):
    with closing(_connect_database(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT p.id, p.user_id, p.name, p.description, p.artwork_url, p.is_public,
                   COUNT(pt.song_id) AS track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            WHERE p.user_id = ?
            GROUP BY p.id
            ORDER BY p.updated_at DESC, p.id DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row[0],
            "user_id": row[1],
            "name": row[2],
            "description": row[3],
            "artwork_url": row[4],
            "is_public": bool(row[5]),
            "track_count": int(row[6] or 0),
        }
        for row in rows
    ]


def get_playlist_details(database_path, playlist_id, user_id=None):
    with closing(_connect_database(database_path)) as connection:
        row = connection.execute(
            "SELECT id, user_id, name, description, artwork_url, is_public FROM playlists WHERE id = ?",
            (playlist_id,),
        ).fetchone()
        if row is None:
            return None
        if user_id is not None and row[1] != user_id:
            return None
        tracks = connection.execute(
            """
            SELECT s.id, s.title, a.name AS artist, s.album, s.language, s.genre,
                   s.provider_url, s.thumbnail_url, pt.position
            FROM playlist_tracks pt
            JOIN songs s ON s.id = pt.song_id
            LEFT JOIN artists a ON a.id = s.artist_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position ASC, pt.id ASC
            """,
            (playlist_id,),
        ).fetchall()
        return {
            "id": row[0],
            "user_id": row[1],
            "name": row[2],
            "description": row[3],
            "artwork_url": row[4],
            "is_public": bool(row[5]),
            "tracks": [
                {
                    "id": track[0],
                    "title": track[1],
                    "artist": track[2],
                    "album": track[3],
                    "language": track[4],
                    "genre": track[5],
                    "provider_url": track[6],
                    "thumbnail_url": track[7],
                    "position": track[8],
                }
                for track in tracks
            ],
        }


def update_playlist(database_path, user_id, playlist_id, updates):
    if user_id is None:
        return None
    if not isinstance(updates, dict):
        return None
    field_map = {
        "name": "name",
        "description": "description",
        "artwork_url": "artwork_url",
        "is_public": "is_public",
    }
    assignments = []
    values = []
    for key, value in updates.items():
        column = field_map.get(key)
        if column is None:
            continue
        if column == "name":
            value = (value or "").strip()
            if not value:
                raise ValueError("Playlist name is required.")
        if column == "description" and value is not None:
            value = str(value).strip()
        if column == "is_public":
            value = int(bool(value))
        assignments.append(f"{column} = ?")
        values.append(value)
    if not assignments:
        return get_playlist_details(database_path, playlist_id, user_id=user_id)
    values.extend([datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user_id, playlist_id])
    with closing(_connect_database(database_path)) as connection, connection:
        cursor = connection.execute(
            f"UPDATE playlists SET {', '.join(assignments)}, updated_at = ? WHERE user_id = ? AND id = ?",
            tuple(values),
        )
        if cursor.rowcount == 0:
            return None
    return get_playlist_details(database_path, playlist_id, user_id=user_id)


def delete_playlist(database_path, user_id, playlist_id):
    with closing(_connect_database(database_path)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM playlists WHERE user_id = ? AND id = ?",
            (user_id, playlist_id),
        )
    return cursor.rowcount > 0


def add_song_to_playlist(database_path, user_id, playlist_id, song_id):
    with closing(_connect_database(database_path)) as connection, connection:
        playlist = connection.execute(
            "SELECT id FROM playlists WHERE user_id = ? AND id = ?",
            (user_id, playlist_id),
        ).fetchone()
        if playlist is None:
            return None
        song_exists = connection.execute(
            "SELECT 1 FROM songs WHERE id = ?",
            (song_id,),
        ).fetchone()
        if song_exists is None:
            return None
        next_position = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()[0]
        cursor = connection.execute(
            "INSERT OR IGNORE INTO playlist_tracks (playlist_id, song_id, position, added_at) VALUES (?, ?, ?, ?)",
            (playlist_id, song_id, next_position, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        )
        if cursor.rowcount == 0:
            return None
        connection.execute(
            "UPDATE playlists SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), playlist_id),
        )
    return get_playlist_details(database_path, playlist_id, user_id=user_id)


def remove_song_from_playlist(database_path, user_id, playlist_id, song_id):
    with closing(_connect_database(database_path)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = (SELECT id FROM playlists WHERE user_id = ? AND id = ?) AND song_id = ?",
            (user_id, playlist_id, song_id),
        )
        if cursor.rowcount > 0:
            connection.execute(
                "UPDATE playlists SET updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), playlist_id),
            )
    return cursor.rowcount > 0


def reorder_playlist_tracks(database_path, user_id, playlist_id, ordered_song_ids):
    if not isinstance(ordered_song_ids, list):
        return None
    with closing(_connect_database(database_path)) as connection, connection:
        playlist = connection.execute(
            "SELECT id FROM playlists WHERE user_id = ? AND id = ?",
            (user_id, playlist_id),
        ).fetchone()
        if playlist is None:
            return None
        song_ids = [int(song_id) for song_id in ordered_song_ids if song_id not in (None, "")]
        if not song_ids:
            return get_playlist_details(database_path, playlist_id, user_id=user_id)
        for position, song_id in enumerate(song_ids):
            connection.execute(
                "UPDATE playlist_tracks SET position = ? WHERE playlist_id = ? AND song_id = ?",
                (position, playlist_id, song_id),
            )
        connection.execute(
            "UPDATE playlists SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), playlist_id),
        )
    return get_playlist_details(database_path, playlist_id, user_id=user_id)


def save_song(database_path, user_id, song_id):
    if user_id is None or song_id is None:
        return False
    with closing(_connect_database(database_path)) as connection, connection:
        exists = connection.execute(
            "SELECT 1 FROM songs WHERE id = ?",
            (song_id,),
        ).fetchone()
        if exists is None:
            return False
        connection.execute(
            "INSERT OR IGNORE INTO saved_songs (user_id, song_id, created_at) VALUES (?, ?, ?)",
            (user_id, song_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.execute(
            "INSERT OR IGNORE INTO user_song_interactions (user_id, song_id, interaction_type, source, created_at) VALUES (?, ?, 'save', 'library', ?)",
            (user_id, song_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        )
    return True


def remove_saved_song(database_path, user_id, song_id):
    if user_id is None or song_id is None:
        return False
    with closing(_connect_database(database_path)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM saved_songs WHERE user_id = ? AND song_id = ?",
            (user_id, song_id),
        )
        connection.execute(
            "DELETE FROM user_song_interactions WHERE user_id = ? AND song_id = ? AND interaction_type = 'save'",
            (user_id, song_id),
        )
    return cursor.rowcount > 0


def get_playback_state(database_path, user_id):
    if user_id is None:
        return {"current_song_id": None, "position_ms": 0, "queue": [], "shuffle": False, "repeat_mode": "off"}
    with closing(_connect_database(database_path)) as connection:
        row = connection.execute(
            "SELECT current_song_id, position_ms, queue, shuffle, repeat_mode, last_updated FROM playback_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return {"current_song_id": None, "position_ms": 0, "queue": [], "shuffle": False, "repeat_mode": "off"}
    try:
        queue = json.loads(row[2] or "[]") if row[2] else []
    except (TypeError, ValueError):
        queue = []
    return {
        "user_id": user_id,
        "current_song_id": row[0],
        "position_ms": int(row[1] or 0),
        "queue": queue,
        "shuffle": bool(row[3]),
        "repeat_mode": row[4] or "off",
        "last_updated": row[5],
    }


def save_playback_state(database_path, user_id, payload):
    if user_id is None:
        return None
    current_song_id = payload.get("current_song_id") if isinstance(payload, dict) else None
    position_ms = payload.get("position_ms", 0) if isinstance(payload, dict) else 0
    queue = payload.get("queue", []) if isinstance(payload, dict) else []
    shuffle = bool(payload.get("shuffle", False)) if isinstance(payload, dict) else False
    repeat_mode = str(payload.get("repeat_mode", "off") or "off") if isinstance(payload, dict) else "off"
    queue_json = json.dumps(queue, ensure_ascii=False)
    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with closing(_connect_database(database_path)) as connection, connection:
        connection.execute(
            """
            INSERT INTO playback_states (user_id, current_song_id, position_ms, queue, shuffle, repeat_mode, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                current_song_id = excluded.current_song_id,
                position_ms = excluded.position_ms,
                queue = excluded.queue,
                shuffle = excluded.shuffle,
                repeat_mode = excluded.repeat_mode,
                last_updated = excluded.last_updated
            """,
            (user_id, current_song_id, int(position_ms), queue_json, int(shuffle), repeat_mode, last_updated),
        )
    return get_playback_state(database_path, user_id)


def clear_playback_state(database_path, user_id):
    with closing(_connect_database(database_path)) as connection, connection:
        connection.execute("DELETE FROM playback_states WHERE user_id = ?", (user_id,))
    return True
