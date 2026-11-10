import os
import sqlite3
import tempfile
import unittest

from recommendation_engine import build_hybrid_recommendations, create_music_catalogue


class RecommendationEngineTests(unittest.TestCase):
    def test_build_hybrid_recommendations_prefers_user_preferences_and_vibe(self):
        songs = [
            {
                "id": 1,
                "title": "Hindi love track",
                "artist": "Arijit Singh",
                "language": "Hindi",
                "genre": "Romance",
                "tags": ["soft", "romantic"],
                "vibes": ["romantic", "peaceful"],
            },
            {
                "id": 2,
                "title": "English pop hit",
                "artist": "Dua Lipa",
                "language": "English",
                "genre": "Pop",
                "tags": ["dance", "energetic"],
                "vibes": ["happy", "energetic"],
            },
        ]

        recommendations = build_hybrid_recommendations(
            songs,
            user_preferences={
                "genres": ["Romance"],
                "languages": ["Hindi"],
                "artists": ["Arijit Singh"],
                "listening_styles": ["soft"],
            },
            vibe="romantic",
            limit=2,
        )

        self.assertEqual(recommendations[0]["title"], "Hindi love track")
        self.assertEqual(recommendations[0]["vibe"], "romantic")
        self.assertTrue(recommendations[0]["score"] >= recommendations[1]["score"])

    def test_build_hybrid_recommendations_applies_explicit_request_filters(self):
        songs = [
            {"id": 1, "title": "Hindi pop", "artist": "Artist A", "language": "Hindi", "genre": "Pop"},
            {"id": 2, "title": "English pop", "artist": "Artist B", "language": "English", "genre": "Pop"},
        ]

        recommendations = build_hybrid_recommendations(
            songs,
            query_filters={"language": "Hindi", "genre": "pop"},
            limit=6,
        )

        self.assertEqual([song["id"] for song in recommendations], [1])

    def test_explicit_vibe_filter_matches_catalogue_synonyms(self):
        songs = [
            {"id": 1, "title": "Peaceful track", "vibes": ["peaceful"]},
            {"id": 2, "title": "Relaxed track", "vibes": ["relaxed"]},
            {"id": 3, "title": "Energetic track", "vibes": ["energetic"]},
        ]

        recommendations = build_hybrid_recommendations(
            songs,
            vibe="relaxed",
            query_filters={"vibe": "relaxed"},
            limit=6,
        )

        self.assertEqual(
            {song["id"] for song in recommendations},
            {1, 2},
        )

    def test_catalogue_seed_contains_tracks_for_hybrid_recommendations(self):
        fd, database_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            create_music_catalogue(database_path)
            with sqlite3.connect(database_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
                first = connection.execute(
                    "SELECT title, provider FROM songs ORDER BY id LIMIT 1"
                ).fetchone()
            self.assertGreater(count, 0)
            self.assertIsNotNone(first)
        finally:
            pass


if __name__ == "__main__":
    unittest.main()
