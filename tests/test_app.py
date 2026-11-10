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


if __name__ == "__main__":
    unittest.main()
