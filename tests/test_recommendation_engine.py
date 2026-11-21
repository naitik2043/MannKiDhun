import os
import sqlite3
import tempfile
import unittest

from recommendation_engine import DEFAULT_SONGS, _fetch_interaction_history, build_hybrid_recommendations, create_music_catalogue


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

    def test_negative_feedback_lowers_a_track_below_an_unrated_track(self):
        songs = [
            {"id": 1, "title": "Previously skipped", "artist": "Artist A", "language": "Hindi", "genre": "Pop"},
            {"id": 2, "title": "Fresh option", "artist": "Artist B", "language": "Hindi", "genre": "Pop"},
        ]

        recommendations = build_hybrid_recommendations(
            songs,
            interaction_history={"1": -3.0, "2": 0.0},
            limit=2,
        )

        self.assertEqual(recommendations[0]["id"], 2)
        self.assertIn("skip feedback", recommendations[1]["explanation"].lower())

    def test_interaction_history_uses_positive_and_negative_feedback_weights(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE user_song_interactions (user_id INTEGER, song_id INTEGER, interaction_type TEXT)"
            )
            connection.executemany(
                "INSERT INTO user_song_interactions (user_id, song_id, interaction_type) VALUES (?, ?, ?)",
                [
                    (5, 10, "like"),
                    (5, 10, "play"),
                    (5, 10, "complete"),
                    (5, 11, "skip"),
                    (5, 12, "save"),
                ],
            )

            scores = _fetch_interaction_history(connection, 5)

            self.assertEqual(scores, {"10": 4.0, "11": -2.0, "12": 2.0})
            self.assertEqual(_fetch_interaction_history(connection, None), {})
        finally:
            connection.close()

    def test_catalogue_seed_contains_tracks_for_hybrid_recommendations(self):
        fd, database_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            create_music_catalogue(database_path)
            create_music_catalogue(database_path)
            with sqlite3.connect(database_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
                first = connection.execute(
                    "SELECT title, provider FROM songs ORDER BY id LIMIT 1"
                ).fetchone()
                regional_languages = {
                    row[0] for row in connection.execute(
                        "SELECT DISTINCT language FROM songs"
                    ).fetchall()
                }
            self.assertGreater(count, 0)
            self.assertIsNotNone(first)
            self.assertTrue({
                "Hindi", "English", "Punjabi", "Bengali", "Gujarati",
                "Telugu", "Tamil", "Malayalam", "Marathi",
            } <= regional_languages)
            self.assertEqual(count, len(DEFAULT_SONGS))
        finally:
            pass


if __name__ == "__main__":
    unittest.main()
