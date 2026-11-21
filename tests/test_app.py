import base64
import io
import sqlite3
import tempfile
import uuid
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

import app as mood_app


def landmarks(count):
    return [
        SimpleNamespace(x=0.25 + index / 2000, y=0.30 + index / 3000)
        for index in range(count)
    ]


def camera_frame():
    pixels = np.random.default_rng(42).integers(
        80, 176, size=(160, 160, 1), dtype=np.uint8
    )
    return np.repeat(pixels, 3, axis=2)


def detected_face():
    return SimpleNamespace(
        process=lambda _image: SimpleNamespace(detections=[object()])
    )


class LandmarkFeatureTests(unittest.TestCase):
    def test_features_match_the_trained_model_input(self):
        face = landmarks(468)
        left_hand = landmarks(21)
        results = SimpleNamespace(
            face_landmarks=SimpleNamespace(landmark=face),
            left_hand_landmarks=SimpleNamespace(landmark=left_hand),
            right_hand_landmarks=None,
        )

        features = mood_app.extract_landmark_features(results)

        self.assertEqual(features.shape, (1020,))
        self.assertEqual(features.dtype, np.float32)
        self.assertAlmostEqual(
            float(features[0]), face[0].x - face[1].x, places=6
        )
        self.assertAlmostEqual(
            float(features[936]),
            left_hand[0].x - left_hand[8].x,
            places=6,
        )
        self.assertTrue(np.all(features[978:] == 0))

    def test_missing_face_has_no_features(self):
        results = SimpleNamespace(face_landmarks=None)

        self.assertIsNone(mood_app.extract_landmark_features(results))

    def test_prediction_uses_landmarks_and_normalizes_the_model_label(self):
        face = landmarks(468)
        results = SimpleNamespace(
            face_landmarks=SimpleNamespace(landmark=face),
            left_hand_landmarks=None,
            right_hand_landmarks=None,
        )
        fake_holistic = SimpleNamespace(process=lambda _image: results)
        scores = np.array([[0, 0, 1, 0, 0, 0]], dtype=np.float32)

        with (
            patch.object(mood_app, "holistic", fake_holistic),
            patch.object(mood_app, "face_detector", detected_face()),
            patch.object(mood_app.model, "predict", return_value=scores) as predict,
        ):
            result = mood_app.predict_mood(camera_frame())

        self.assertEqual(result["mood"], "surprise")
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(predict.call_args.args[0].shape, (1, 1020))
        self.assertFalse(np.all(predict.call_args.args[0] == 0))

    def test_no_face_is_reported_instead_of_guessing_a_mood(self):
        results = SimpleNamespace(face_landmarks=None)
        fake_holistic = SimpleNamespace(process=lambda _image: results)

        with patch.object(mood_app, "holistic", fake_holistic):
            with patch.object(mood_app, "face_detector", detected_face()):
                with self.assertRaises(mood_app.NoFaceDetected):
                    mood_app.predict_mood(camera_frame())

    def test_multiple_faces_are_rejected_without_using_the_model(self):
        face_detection = SimpleNamespace(
            process=lambda _image: SimpleNamespace(detections=[object(), object()])
        )
        with patch.object(mood_app, "face_detector", face_detection):
            with self.assertRaisesRegex(mood_app.NoFaceDetected, "More than one face"):
                mood_app.predict_mood_from_frames([camera_frame()] * 5)

    def test_multiple_frames_are_averaged_and_report_consensus(self):
        happy = np.array([0.8, 0.1, 0.02, 0.02, 0.03, 0.03])
        sad = np.array([0.1, 0.1, 0.02, 0.02, 0.03, 0.73])

        with patch.object(
            mood_app,
            "predict_mood_scores",
            side_effect=[happy, happy, happy, sad, sad],
        ):
            result = mood_app.predict_mood_from_frames([object()] * 5)

        self.assertEqual(result["mood"], "happy")
        self.assertEqual(result["samples"], 5)
        self.assertEqual(result["consistency"], 0.6)
        self.assertEqual(result["expression_estimate"], "happy")
        self.assertEqual(result["valid_frames"], 5)
        self.assertEqual(result["total_frames"], 5)
        self.assertEqual(result["consistency_label"], "moderate")
        self.assertAlmostEqual(result["prediction_scores"]["happy"], 0.52)

    def test_multiple_frames_reject_a_tied_mood_estimate(self):
        happy = np.array([0.8, 0.1, 0.02, 0.02, 0.03, 0.03])
        sad = np.array([0.1, 0.1, 0.02, 0.02, 0.03, 0.73])

        with patch.object(
            mood_app,
            "predict_mood_scores",
            side_effect=[happy, happy, sad, sad],
        ):
            with self.assertRaises(mood_app.UncertainMoodDetected):
                mood_app.predict_mood_from_frames([object()] * 4)


class ApiRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.auth_database_patch = patch.object(
            mood_app,
            "AUTH_DATABASE",
            Path(self.temporary_directory.name) / "test.sqlite3",
        )
        self.instance_directory_patch = patch.object(
            mood_app, "INSTANCE_DIR", Path(self.temporary_directory.name)
        )
        self.auth_database_patch.start()
        self.instance_directory_patch.start()
        mood_app.initialize_auth_database()
        mood_app.create_music_catalogue(mood_app.AUTH_DATABASE)

    def tearDown(self):
        self.auth_database_patch.stop()
        self.instance_directory_patch.stop()
        self.temporary_directory.cleanup()

    def test_built_frontend_is_served(self):
        response = mood_app.app.test_client().get("/")
        body = response.get_data()
        response.close()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"MannKiDhun", body)

    def test_branded_svg_icon_is_served(self):
        response = mood_app.app.test_client().get("/mannkidhun.svg")
        body = response.get_data()
        response.close()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<svg", body)

    def test_frontend_pages_are_served_and_unknown_pages_are_not(self):
        client = mood_app.app.test_client()
        for path in (
            "/signin",
            "/signup",
            "/app",
            "/assistant",
            "/dashboard",
            "/mood-check",
            "/profile",
            "/community",
            "/playlists/42",
        ):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        self.assertEqual(client.get("/unknown-page").status_code, 404)

    def test_recommendation_generation_rejects_non_object_json(self):
        client = mood_app.app.test_client()
        for body in (b"{", b"[]", b"null"):
            with self.subTest(body=body):
                response = client.post(
                    "/api/v1/recommendations/generate",
                    data=body,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)

    def test_predict_endpoint_returns_mood_from_landmarks(self):
        face = landmarks(468)
        results = SimpleNamespace(
            face_landmarks=SimpleNamespace(landmark=face),
            left_hand_landmarks=None,
            right_hand_landmarks=None,
        )
        ok, image = mood_app.cv2.imencode(
            ".jpg",             camera_frame()
        )
        self.assertTrue(ok)
        payload = {
            "image": "data:image/jpeg;base64,"
            + base64.b64encode(image).decode("ascii")
        }
        scores = np.array([[0, 0, 1, 0, 0, 0]], dtype=np.float32)

        with (
            patch.object(
                mood_app, "holistic", SimpleNamespace(process=lambda _image: results)
            ),
            patch.object(mood_app, "face_detector", detected_face()),
            patch.object(mood_app.model, "predict", return_value=scores),
        ):
            response = mood_app.app.test_client().post("/predict", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mood"], "surprise")
        self.assertEqual(response.json["confidence"], 1.0)

    def test_predict_endpoint_accepts_multiple_frames(self):
        face = landmarks(468)
        results = SimpleNamespace(
            face_landmarks=SimpleNamespace(landmark=face),
            left_hand_landmarks=None,
            right_hand_landmarks=None,
        )
        ok, image = mood_app.cv2.imencode(
            ".jpg",             camera_frame()
        )
        self.assertTrue(ok)
        frame = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
        scores = np.array([[0, 0, 1, 0, 0, 0]], dtype=np.float32)

        with (
            patch.object(
                mood_app, "holistic", SimpleNamespace(process=lambda _image: results)
            ),
            patch.object(mood_app, "face_detector", detected_face()),
            patch.object(mood_app.model, "predict", return_value=scores),
        ):
            response = mood_app.app.test_client().post(
                "/predict", json={"images": [frame] * 5}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mood"], "surprise")
        self.assertEqual(response.json["samples"], 5)
        self.assertEqual(response.json["consistency"], 1.0)
        self.assertEqual(response.json["valid_frames"], 5)
        self.assertEqual(response.json["total_frames"], 5)

    def test_predict_endpoint_hides_invalid_model_output_details(self):
        face = landmarks(468)
        results = SimpleNamespace(
            face_landmarks=SimpleNamespace(landmark=face),
            left_hand_landmarks=None,
            right_hand_landmarks=None,
        )
        ok, image = mood_app.cv2.imencode(".jpg", camera_frame())
        self.assertTrue(ok)
        payload = {
            "image": "data:image/jpeg;base64,"
            + base64.b64encode(image).decode("ascii")
        }

        with (
            patch.object(
                mood_app, "holistic", SimpleNamespace(process=lambda _image: results)
            ),
            patch.object(mood_app, "face_detector", detected_face()),
            patch.object(
                mood_app.model, "predict", return_value=np.array([[1, 1, 1, 1, 1, 1]])
            ),
        ):
            response = mood_app.app.test_client().post("/predict", json=payload)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json["error"],
            "Expression analysis is temporarily unavailable. Please try again.",
        )
        self.assertNotIn("invalid prediction scores", response.get_data(as_text=True))

    def test_account_creation_login_and_logout(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/auth/register",
            json={"name": "Test Listener", "email": email, "password": "test-pass-123"},
        )

        self.assertEqual(registration.status_code, 201)
        self.assertEqual(registration.json["user"]["email"], email)
        self.assertNotIn("password", registration.json["user"])
        self.assertEqual(
            client.get("/api/auth/session").json["user"]["name"], "Test Listener"
        )

        logout = client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertIsNone(client.get("/api/auth/session").json["user"])

        login = client.post(
            "/api/auth/login",
            json={"email": email, "password": "test-pass-123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["user"]["email"], email)

    def test_profile_requires_authentication_and_updates_account(self):
        client = mood_app.app.test_client()
        unauthorized = client.put(
            "/api/profile",
            json={
                "name": "Updated Listener",
                "email": "updated@example.com",
                "current_password": "test-pass-123",
            },
        )
        self.assertEqual(unauthorized.status_code, 401)

        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Test Listener", "email": email, "password": "test-pass-123"},
        )
        updated_email = f"{uuid.uuid4().hex}@example.com"
        update = client.put(
            "/api/profile",
            json={
                "name": "Updated Listener",
                "email": updated_email,
                "current_password": "test-pass-123",
                "new_password": "new-test-pass-456",
            },
        )

        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json["user"]["name"], "Updated Listener")
        self.assertEqual(update.json["user"]["email"], updated_email)
        self.assertEqual(client.get("/api/auth/session").json["user"]["email"], updated_email)
        self.assertEqual(
            client.post(
                "/api/auth/login",
                json={"email": updated_email, "password": "new-test-pass-456"},
            ).status_code,
            200,
        )
        self.assertEqual(
            client.post(
                "/api/auth/login",
                json={"email": updated_email, "password": "test-pass-123"},
            ).status_code,
            401,
        )

    def test_profile_rejects_wrong_current_password(self):
        client = mood_app.app.test_client()
        client.post(
            "/api/auth/register",
            json={
                "name": "Test Listener",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        response = client.put(
            "/api/profile",
            json={
                "name": "Updated Listener",
                "email": "updated@example.com",
                "current_password": "wrong-password",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_profile_avatar_upload_is_persisted_private_and_removable(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Photo Listener", "email": email, "password": "test-pass-123"},
        )
        image_buffer = io.BytesIO()
        Image.new("RGB", (32, 24), color=(125, 90, 210)).save(image_buffer, format="PNG")
        image_contents = image_buffer.getvalue()

        upload = client.post(
            "/api/profile/avatar",
            data={"avatar": (io.BytesIO(image_contents), "profile.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 200)
        avatar_url = upload.json["user"]["profile_image"]
        self.assertRegex(avatar_url, r"^/api/profile/avatar/[a-f0-9]{32}\.jpg$")
        avatar_path = (
            Path(self.temporary_directory.name)
            / "profile_uploads"
            / avatar_url.rsplit("/", 1)[-1]
        )
        self.assertTrue(avatar_path.is_file())
        profile_update = client.put(
            "/api/profile",
            json={
                "name": "Photo Listener",
                "email": email,
                "current_password": "test-pass-123",
            },
        )
        self.assertEqual(profile_update.status_code, 200)
        self.assertEqual(profile_update.json["user"]["profile_image"], avatar_url)
        self.assertEqual(
            client.get("/api/auth/session").json["user"]["profile_image"], avatar_url
        )

        photo = client.get(avatar_url)
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.mimetype, "image/jpeg")
        self.assertEqual(photo.headers["Cache-Control"], "private, no-store")
        photo.close()

        other_client = mood_app.app.test_client()
        other_client.post(
            "/api/auth/register",
            json={
                "name": "Another Listener",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        self.assertEqual(other_client.get(avatar_url).status_code, 404)

        remove = client.delete("/api/profile/avatar")
        self.assertEqual(remove.status_code, 200)
        self.assertNotIn("profile_image", remove.json["user"])
        self.assertFalse(avatar_path.exists())
        self.assertEqual(client.get(avatar_url).status_code, 404)

    def test_profile_avatar_rejects_invalid_and_oversized_uploads(self):
        client = mood_app.app.test_client()
        client.post(
            "/api/auth/register",
            json={
                "name": "Photo Listener",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        invalid = client.post(
            "/api/profile/avatar",
            data={"avatar": (io.BytesIO(b"not an image"), "profile.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("valid JPEG", invalid.json["error"])

        oversized_dimensions = io.BytesIO()
        Image.new("RGB", (5000, 2), color=(125, 90, 210)).save(
            oversized_dimensions, format="PNG"
        )
        dimensions_response = client.post(
            "/api/profile/avatar",
            data={"avatar": (io.BytesIO(oversized_dimensions.getvalue()), "wide.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(dimensions_response.status_code, 400)
        self.assertIn("4096", dimensions_response.json["error"])

        oversized = client.post(
            "/api/profile/avatar",
            data={"avatar": (io.BytesIO(b"x" * (2 * 1024 * 1024 + 1)), "large.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(oversized.status_code, 413)

    def test_profile_avatar_requires_authentication(self):
        client = mood_app.app.test_client()
        self.assertEqual(client.post("/api/profile/avatar").status_code, 401)
        self.assertEqual(client.delete("/api/profile/avatar").status_code, 401)

    def test_preferences_can_be_read_after_being_saved(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        self.assertEqual(
            client.post(
                "/api/auth/register",
                json={"name": "Preference Listener", "email": email, "password": "test-pass-123"},
            ).status_code,
            201,
        )
        updated = client.put(
            "/api/v1/preferences",
            json={
                "preferred_languages": ["Hindi"],
                "preferred_genres": ["Pop"],
                "preferred_listening_styles": ["calm"],
                "favourite_artists": ["Arijit Singh"],
            },
        )
        self.assertEqual(updated.status_code, 200)

        response = client.get("/api/v1/preferences")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["preferred_languages"], ["Hindi"])
        self.assertEqual(response.json["preferred_genres"], ["Pop"])
        self.assertEqual(response.json["preferred_listening_styles"], ["calm"])
        self.assertEqual(response.json["favourite_artists"], ["Arijit Singh"])
        self.assertFalse(response.json["onboarding_completed"])

    def test_onboarding_completion_saves_preferences_and_marks_account_complete(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        self.assertEqual(
            client.post(
                "/api/auth/register",
                json={"name": "Onboarding Listener", "email": email, "password": "test-pass-123"},
            ).status_code,
            201,
        )

        response = client.post(
            "/api/v1/preferences/onboarding/complete",
            json={"preferred_languages": ["English"], "preferred_genres": ["Indie"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["preferred_languages"], ["English"])
        self.assertEqual(response.json["preferred_genres"], ["Indie"])
        self.assertTrue(response.json["onboarding_completed"])
        self.assertTrue(
            client.get("/api/v1/preferences/onboarding-status").json["onboarding_completed"]
        )
        self.assertEqual(
            client.get("/api/v1/preferences").json["preferred_languages"], ["English"]
        )

    def test_registration_rejects_non_string_fields_and_weak_passwords(self):
        client = mood_app.app.test_client()
        for payload in (
            {"name": 10, "email": "valid@example.com", "password": "long-password"},
            {"name": "Listener", "email": "valid@example.com", "password": "short"},
        ):
            with self.subTest(payload=payload):
                response = client.post("/api/auth/register", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_registration_rejects_duplicate_email(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        payload = {"name": "Test Listener", "email": email, "password": "test-pass-123"}
        self.assertEqual(client.post("/api/auth/register", json=payload).status_code, 201)
        self.assertEqual(client.post("/api/auth/register", json=payload).status_code, 409)

    def test_assistant_requires_authentication_and_recommends_catalogue_tracks(self):
        client = mood_app.app.test_client()
        self.assertEqual(
            client.post(
                "/api/v1/assistant/chat",
                json={"message": "peaceful Hindi songs"},
            ).status_code,
            401,
        )

        mood_app.create_music_catalogue(str(mood_app.AUTH_DATABASE))
        email = f"{uuid.uuid4().hex}@example.com"
        self.assertEqual(
            client.post(
                "/api/auth/register",
                json={"name": "Assistant Listener", "email": email, "password": "test-pass-123"},
            ).status_code,
            201,
        )
        with patch.dict("os.environ", {"AI_ASSISTANT_API_KEY": ""}):
            response = client.post(
                "/api/v1/assistant/chat",
                json={
                    "message": "peaceful Hindi songs",
                    "use_preferences": False,
                    "use_history": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["intent_provider"], "rules")
        self.assertTrue(response.json["recommendations"])
        self.assertTrue(
            all(song["language"] == "Hindi" for song in response.json["recommendations"])
        )
        self.assertTrue(
            all(
                {"peaceful", "relaxed"} & set(song["metadata"]["vibes"])
                for song in response.json["recommendations"]
            )
        )
        self.assertEqual(
            response.json["personalisation"],
            {"preferences": False, "listening_history": False},
        )

    def test_assistant_rejects_invalid_personalisation_options(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Assistant Listener", "email": email, "password": "test-pass-123"},
        )
        response = client.post(
            "/api/v1/assistant/chat",
            json={"message": "relaxing music", "use_history": "yes"},
        )

        self.assertEqual(response.status_code, 400)

    def test_password_reset_does_not_expose_a_reset_token(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Reset Listener", "email": email, "password": "test-pass-123"},
        )

        known_account = client.post("/api/auth/forgot-password", json={"email": email})
        unknown_account = client.post(
            "/api/auth/forgot-password", json={"email": "nobody@example.com"}
        )

        self.assertEqual(known_account.status_code, 200)
        self.assertEqual(known_account.json, unknown_account.json)
        self.assertNotIn("token", known_account.json)

    def test_account_deletion_cascades_through_user_owned_data(self):
        mood_app.create_music_catalogue(str(mood_app.AUTH_DATABASE))
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        self.assertEqual(
            client.post(
                "/api/auth/register",
                json={"name": "Delete Listener", "email": email, "password": "test-pass-123"},
            ).status_code,
            201,
        )
        self.assertEqual(
            client.post("/api/v1/playlists", json={"name": "Temporary mix"}).status_code,
            201,
        )
        self.assertEqual(
            client.post(
                "/api/v1/users/me/playback-state",
                json={"queue": [], "position_ms": 0},
            ).status_code,
            200,
        )
        user_id = client.get("/api/auth/session").json["user"]["id"]

        self.assertEqual(client.delete("/api/v1/users/me").status_code, 200)
        with closing(sqlite3.connect(mood_app.AUTH_DATABASE)) as connection:
            playlists = connection.execute(
                "SELECT COUNT(*) FROM playlists WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            playback_states = connection.execute(
                "SELECT COUNT(*) FROM playback_states WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
        self.assertEqual(playlists, 0)
        self.assertEqual(playback_states, 0)

    def test_mood_journal_is_private_and_can_be_deleted(self):
        client = mood_app.app.test_client()
        self.assertEqual(client.get("/api/v1/users/me/mood-journal").status_code, 401)

        first_email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Journal Owner", "email": first_email, "password": "test-pass-123"},
        )
        created = client.post(
            "/api/v1/users/me/mood-journal",
            json={"mood": "relaxed", "note": "A quiet evening with music."},
        )
        self.assertEqual(created.status_code, 201)
        entry_id = created.json["entry"]["id"]
        self.assertEqual(created.json["entry"]["mood"], "relaxed")
        journal = client.get("/api/v1/users/me/mood-journal")
        self.assertEqual(
            journal.json["entries"][0]["note"],
            "A quiet evening with music.",
        )
        self.assertEqual(journal.json["mood_summary"][0], {"mood": "relaxed", "entries": 1})

        second_client = mood_app.app.test_client()
        second_client.post(
            "/api/auth/register",
            json={
                "name": "Another Listener",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        self.assertEqual(
            second_client.delete(f"/api/v1/users/me/mood-journal/{entry_id}").status_code,
            404,
        )
        self.assertEqual(client.delete(f"/api/v1/users/me/mood-journal/{entry_id}").status_code, 200)
        self.assertEqual(client.get("/api/v1/users/me/mood-journal").json["entries"], [])

    def test_music_dna_requires_opt_in_and_preserves_consent(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        registration = client.post(
            "/api/auth/register",
            json={"name": "DNA Listener", "email": email, "password": "test-pass-123"},
        )
        self.assertEqual(registration.status_code, 201)
        self.assertFalse(client.get("/api/v1/users/me/music-dna").json["enabled"])

        enabled = client.post("/api/v1/users/me/music-dna/consent", json={"enabled": True})
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.json["enabled"])

        preferences = client.put(
            "/api/v1/preferences",
            json={"preferred_languages": ["Hindi"], "preferred_genres": ["Pop"]},
        )
        self.assertEqual(preferences.status_code, 200)
        self.assertTrue(preferences.json["music_dna_enabled"])
        dna = client.get("/api/v1/users/me/music-dna")
        self.assertEqual(dna.status_code, 200)
        self.assertTrue(dna.json["enabled"])
        self.assertIn("top_languages", dna.json)
        self.assertIn("top_tags", dna.json)
        self.assertIn("top_vibes", dna.json)
        self.assertIn("summary", dna.json)

        disabled = client.post("/api/v1/users/me/music-dna/consent", json={"enabled": False})
        self.assertFalse(disabled.json["enabled"])
        self.assertFalse(client.get("/api/v1/users/me/music-dna").json["enabled"])

    def test_adaptive_session_saves_recommendation_queue(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Session Listener", "email": email, "password": "test-pass-123"},
        )
        response = client.post(
            "/api/v1/users/me/adaptive-session",
            json={
                "mode": "explore",
                "use_preferences": False,
                "use_history": False,
                "limit": 6,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json["recommendations"]), 0)
        saved = client.get("/api/v1/users/me/playback-state").json["state"]
        self.assertEqual(
            saved["queue"],
            [track["id"] for track in response.json["recommendations"]],
        )

    def test_playlist_invites_allow_editor_collaboration_and_revoke_access(self):
        owner = mood_app.app.test_client()
        owner.post(
            "/api/auth/register",
            json={
                "name": "Playlist Owner",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        playlist = owner.post(
            "/api/v1/playlists",
            json={"name": "Collaborative Mix"},
        ).json["playlist"]
        playlist_id = playlist["id"]

        with closing(mood_app._connect_database(mood_app.AUTH_DATABASE)) as connection:
            song_id = connection.execute("SELECT id FROM songs ORDER BY id LIMIT 1").fetchone()[0]

        invitation = owner.post(
            f"/api/v1/playlists/{playlist_id}/invites",
            json={"role": "editor"},
        )
        self.assertEqual(invitation.status_code, 201)
        invite_url = invitation.json["invite_url"]
        token = invite_url.split("invite_token=", 1)[1]

        editor = mood_app.app.test_client()
        editor.post(
            "/api/auth/register",
            json={
                "name": "Playlist Editor",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        accepted = editor.post(
            f"/api/v1/playlists/{playlist_id}/invites/accept",
            json={"token": token},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json["playlist"]["role"], "editor")
        self.assertFalse(accepted.json["playlist"]["is_owner"])

        shared_playlists = editor.get("/api/v1/playlists").json["playlists"]
        self.assertEqual(shared_playlists[0]["name"], "Collaborative Mix")
        self.assertEqual(shared_playlists[0]["role"], "editor")
        self.assertFalse(shared_playlists[0]["is_owner"])

        added = editor.post(
            f"/api/v1/playlists/{playlist_id}/tracks",
            json={"song_id": song_id},
        )
        self.assertEqual(added.status_code, 200)
        self.assertEqual(len(added.json["playlist"]["tracks"]), 1)

        collaborators = owner.get(
            f"/api/v1/playlists/{playlist_id}/collaborators"
        )
        self.assertEqual(collaborators.status_code, 200)
        self.assertEqual(collaborators.json["collaborators"][0]["name"], "Playlist Editor")
        self.assertEqual(
            editor.get(f"/api/v1/playlists/{playlist_id}/collaborators").status_code,
            403,
        )
        self.assertEqual(
            editor.delete(f"/api/v1/playlists/{playlist_id}").status_code,
            404,
        )

        self.assertEqual(
            owner.delete(f"/api/v1/playlists/{playlist_id}/invites").status_code,
            200,
        )
        another_listener = mood_app.app.test_client()
        another_listener.post(
            "/api/auth/register",
            json={
                "name": "Late Listener",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        self.assertEqual(
            another_listener.post(
                f"/api/v1/playlists/{playlist_id}/invites/accept",
                json={"token": token},
            ).status_code,
            404,
        )

    def test_playlist_owner_can_change_or_remove_collaborator_roles(self):
        owner = mood_app.app.test_client()
        owner.post(
            "/api/auth/register",
            json={
                "name": "Mix Owner",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        playlist_id = owner.post(
            "/api/v1/playlists", json={"name": "Team playlist"}
        ).json["playlist"]["id"]
        invite = owner.post(
            f"/api/v1/playlists/{playlist_id}/invites",
            json={"role": "editor"},
        )
        token = invite.json["invite_url"].split("invite_token=", 1)[1]

        collaborator = mood_app.app.test_client()
        collaborator.post(
            "/api/auth/register",
            json={
                "name": "Team Editor",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        collaborator.post(
            f"/api/v1/playlists/{playlist_id}/invites/accept",
            json={"token": token},
        )
        collaborator_id = collaborator.get("/api/auth/session").json["user"]["id"]

        updated = owner.put(
            f"/api/v1/playlists/{playlist_id}/collaborators/{collaborator_id}",
            json={"role": "viewer"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["role"], "viewer")
        self.assertEqual(
            collaborator.get(f"/api/v1/playlists/{playlist_id}").json["playlist"]["role"],
            "viewer",
        )

        removed = owner.delete(
            f"/api/v1/playlists/{playlist_id}/collaborators/{collaborator_id}"
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(
            collaborator.get(f"/api/v1/playlists/{playlist_id}").status_code,
            404,
        )

    def test_viewer_playlist_invite_does_not_grant_edit_access(self):
        owner = mood_app.app.test_client()
        owner.post(
            "/api/auth/register",
            json={
                "name": "Playlist Owner",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        playlist_id = owner.post(
            "/api/v1/playlists",
            json={"name": "Read Only Mix"},
        ).json["playlist"]["id"]
        invite = owner.post(
            f"/api/v1/playlists/{playlist_id}/invites",
            json={"role": "viewer"},
        )
        self.assertEqual(invite.status_code, 201)
        token = invite.json["invite_url"].split("invite_token=", 1)[1]

        viewer = mood_app.app.test_client()
        viewer.post(
            "/api/auth/register",
            json={
                "name": "Playlist Viewer",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        accepted = viewer.post(
            f"/api/v1/playlists/{playlist_id}/invites/accept",
            json={"token": token},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json["playlist"]["role"], "viewer")
        with closing(mood_app._connect_database(mood_app.AUTH_DATABASE)) as connection:
            song_id = connection.execute("SELECT id FROM songs ORDER BY id LIMIT 1").fetchone()[0]
        self.assertEqual(
            viewer.post(
                f"/api/v1/playlists/{playlist_id}/tracks",
                json={"song_id": song_id},
            ).status_code,
            404,
        )


    def test_public_playlist_directory_lists_only_shared_playlists(self):
        client = mood_app.app.test_client()
        client.post(
            "/api/auth/register",
            json={
                "name": "Community Listener",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        client.post("/api/v1/playlists", json={"name": "Private playlist"})
        client.post("/api/v1/playlists", json={"name": "Public playlist", "is_public": True})

        response = client.get("/api/v1/public/playlists")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json["playlists"]], ["Public playlist"])

    def test_public_playlist_endpoint_exposes_only_public_playlists(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Playlist Owner", "email": email, "password": "test-pass-123"},
        )
        private = client.post("/api/v1/playlists", json={"name": "Private mix"})
        public = client.post("/api/v1/playlists", json={"name": "Shared mix", "is_public": True})
        self.assertEqual(private.status_code, 201)
        self.assertEqual(public.status_code, 201)
        private_id = private.json["playlist"]["id"]
        public_id = public.json["playlist"]["id"]

        self.assertEqual(client.get(f"/api/v1/public/playlists/{private_id}").status_code, 404)
        shared = client.get(f"/api/v1/public/playlists/{public_id}")
        self.assertEqual(shared.status_code, 200)
        self.assertTrue(shared.json["playlist"]["is_public"])
        self.assertEqual(shared.json["playlist"]["name"], "Shared mix")

    def test_playlist_refinement_can_remove_and_reorder_tracks_by_instruction(self):
        client = mood_app.app.test_client()
        client.post(
            "/api/auth/register",
            json={
                "name": "Playlist Editor",
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-pass-123",
            },
        )
        playlist = client.post(
            "/api/v1/playlists", json={"name": "Editable playlist"}
        ).json["playlist"]
        playlist_id = playlist["id"]
        with closing(mood_app._connect_database(mood_app.AUTH_DATABASE)) as connection:
            tracks = connection.execute(
                "SELECT id, title FROM songs ORDER BY id LIMIT 3"
            ).fetchall()
        self.assertGreaterEqual(len(tracks), 2)

        for song_id, _title in tracks[:2]:
            self.assertEqual(
                client.post(
                    f"/api/v1/playlists/{playlist_id}/tracks",
                    json={"song_id": song_id},
                ).status_code,
                200,
            )

        second_title = tracks[1][1]
        moved = client.post(
            f"/api/v1/playlists/{playlist_id}/refine",
            json={"instruction": f"move {second_title} to the top"},
        )
        self.assertEqual(moved.status_code, 200)
        self.assertTrue(moved.json["reordered"])
        self.assertEqual(moved.json["playlist"]["tracks"][0]["id"], tracks[1][0])

        removed = client.post(
            f"/api/v1/playlists/{playlist_id}/refine",
            json={"instruction": "remove last song"},
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json["removed_count"], 1)
        self.assertEqual(len(removed.json["playlist"]["tracks"]), 1)

    def test_playlist_refinement_adds_catalogue_tracks_matching_the_request(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Playlist Editor", "email": email, "password": "test-pass-123"},
        )
        playlist = client.post("/api/v1/playlists", json={"name": "Evening mix"}).json["playlist"]
        response = client.post(
            f"/api/v1/playlists/{playlist['id']}/refine",
            json={"instruction": "add peaceful music"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json["added_count"], 0)
        self.assertTrue(all(track["id"] for track in response.json["added"]))

    def test_assistant_change_mode_uses_the_selected_target_mood(self):
        client = mood_app.app.test_client()
        email = f"{uuid.uuid4().hex}@example.com"
        client.post(
            "/api/auth/register",
            json={"name": "Mood Listener", "email": email, "password": "test-pass-123"},
        )
        extracted = {
            "mood": None,
            "genre": None,
            "language": None,
            "artist": None,
            "context": None,
        }
        recommendations = [{"id": 1, "title": "A catalogue track"}]
        with (
            patch.object(mood_app, "extract_music_intent", return_value=(extracted, "rules")),
            patch.object(mood_app, "get_user_recommendations", return_value=recommendations) as recommend,
        ):
            response = client.post(
                "/api/v1/assistant/chat",
                json={
                    "message": "Help me change my mood",
                    "mode": "change",
                    "target_mood": "relaxed",
                    "use_preferences": False,
                    "use_history": False,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "change")
        self.assertEqual(recommend.call_args.kwargs["vibe"], "relaxed")
        self.assertEqual(recommend.call_args.kwargs["query_filters"]["vibe"], "relaxed")



if __name__ == "__main__":
    unittest.main()
