import base64
import binascii
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import Flask, abort, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from frame_validation import FrameQualityError, validate_frame_quality
from music_assistant import extract_music_intent
from model_loader import load_emotion_artifacts
from prediction_aggregation import (
    UncertainMoodDetected,
    aggregate_predictions,
    normalize_mood,
)
from recommendation_engine import (
    add_song_to_playlist,
    clear_listening_history,
    clear_playback_state,
    create_music_catalogue,
    create_playlist,
    delete_playlist,
    get_listening_history,
    get_playlist_details,
    get_playback_state,
    get_saved_songs,
    get_user_playlists,
    get_user_recommendations,
    record_user_interaction,
    remove_saved_song,
    remove_song_from_playlist,
    reorder_playlist_tracks,
    save_playback_state,
    save_song,
    update_playlist,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
INSTANCE_DIR = BASE_DIR / "instance"
AUTH_DATABASE = INSTANCE_DIR / "moodwave.sqlite3"
MOOD_ALIASES = {
    "susurprise": "surprise",
    "rocrock": "rock",
}

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIST / "assets"),
    static_url_path="/assets",
)
app.secret_key = (
    os.environ.get("MANNKIDHUN_SECRET_KEY")
    or os.environ.get("MOODWAVE_SECRET_KEY")
    or secrets.token_hex(32)
)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get(
        "MANNKIDHUN_COOKIE_SECURE", os.environ.get("MOODWAVE_COOKIE_SECURE")
    )
    == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_REFRESH_EACH_REQUEST=False,
)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
PROFILE_IMAGE_MAX_BYTES = 2 * 1024 * 1024
PROFILE_IMAGE_MAX_DIMENSION = 4096
PROFILE_IMAGE_MAX_PIXELS = 16_000_000
labels = np.load(BASE_DIR / "model" / "labels.npy", allow_pickle=False)
holistic = None
face_detector = None
inference_lock = threading.Lock()
assistant_rate_lock = threading.Lock()
assistant_requests = defaultdict(deque)


class LazyEmotionModel:
    def __init__(self):
        self._loaded_model = None

    def predict(self, features, **options):
        if self._loaded_model is None:
            self._loaded_model, loaded_labels = load_emotion_artifacts(
                BASE_DIR / "model" / "model.h5",
                BASE_DIR / "model" / "labels.npy",
                BASE_DIR / "model" / "model_metadata.json",
            )
            if not np.array_equal(labels, loaded_labels):
                raise RuntimeError("Emotion labels changed while loading the model.")
        return self._loaded_model.predict(features, **options)


model = LazyEmotionModel()


def _connect_database(database_path=AUTH_DATABASE, **options):
    connection = sqlite3.connect(database_path, **options)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _sqlite_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_identifier(value):
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _normalize_username(value):
    text = _normalize_identifier(value)
    text = re.sub(r"\s+", "_", text)
    return text


def _normalize_email(value):
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _normalize_list_field(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, str):
            return [parsed.strip()] if parsed.strip() else []
        return []
    return [str(value).strip()] if str(value).strip() else []


def _json_dumps(value):
    return json.dumps(value, ensure_ascii=False)


def initialize_auth_database():
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                full_name TEXT,
                username TEXT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                profile_image TEXT,
                is_email_verified INTEGER NOT NULL DEFAULT 0,
                onboarding_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "full_name" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        if "username" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "profile_image" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")
        if "is_email_verified" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN is_email_verified INTEGER NOT NULL DEFAULT 0"
            )
        if "onboarding_completed" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN onboarding_completed INTEGER NOT NULL DEFAULT 0"
            )
        if "updated_at" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN updated_at TEXT")

        connection.execute(
            "UPDATE users SET full_name = COALESCE(full_name, name), updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) WHERE full_name IS NULL OR full_name = ''"
        )
        connection.execute(
            "UPDATE users SET username = COALESCE(username, '') WHERE username IS NULL OR username = ''"
        )

        rows = connection.execute(
            "SELECT id, email, name FROM users WHERE username IS NULL OR username = ''"
        ).fetchall()
        for user_id, email, name in rows:
            base_name = re.sub(r"[^A-Za-z0-9_]", "_", (name or email.split('@', 1)[0]).strip())
            base_name = base_name or "user"
            username = base_name[:24]
            if username == "":
                username = "user"
            candidate = username
            suffix = 1
            while connection.execute(
                "SELECT 1 FROM users WHERE id != ? AND username = ?",
                (user_id, candidate),
            ).fetchone():
                candidate = f"{username}_{suffix}"
                suffix += 1
            connection.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (candidate, user_id),
            )

        connection.execute(
            "CREATE TABLE IF NOT EXISTS password_reset_tokens ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "user_id INTEGER NOT NULL,"
            "token_type TEXT NOT NULL DEFAULT 'password_reset',"
            "token_hash TEXT NOT NULL,"
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "expires_at TEXT NOT NULL,"
            "used_at TEXT,"
            "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE"
            ")"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS user_preferences ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "user_id INTEGER NOT NULL UNIQUE,"
            "preferred_languages TEXT NOT NULL DEFAULT '[]',"
            "preferred_genres TEXT NOT NULL DEFAULT '[]',"
            "preferred_listening_styles TEXT NOT NULL DEFAULT '[]',"
            "favourite_artists TEXT NOT NULL DEFAULT '[]',"
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE"
            ")"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS artists ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "name TEXT NOT NULL UNIQUE,"
            "normalized_name TEXT NOT NULL UNIQUE,"
            "external_provider_id TEXT,"
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS user_favourite_artists ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "user_id INTEGER NOT NULL,"
            "artist_id INTEGER NOT NULL,"
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,"
            "FOREIGN KEY(artist_id) REFERENCES artists(id) ON DELETE CASCADE,"
            "UNIQUE(user_id, artist_id)"
            ")"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id, token_type)"
        )


initialize_auth_database()
create_music_catalogue(AUTH_DATABASE)

def public_user(user):
    name = (user.get("full_name") or user.get("name") or "").strip()
    username = user.get("username")
    payload = {
        "id": user["id"],
        "name": name or user.get("name") or "",
        "email": user["email"],
    }
    if username:
        payload["username"] = username
    if user.get("profile_image"):
        payload["profile_image"] = user["profile_image"]
    if user.get("full_name"):
        payload["full_name"] = user["full_name"]
    if "is_email_verified" in user:
        payload["is_email_verified"] = bool(user["is_email_verified"])
    if "onboarding_completed" in user:
        payload["onboarding_completed"] = bool(user["onboarding_completed"])
    return payload


def _profile_upload_directory():
    return Path(INSTANCE_DIR) / "profile_uploads"


def _delete_profile_avatar(profile_image):
    match = re.fullmatch(r"/api/profile/avatar/([a-f0-9]{32}\.jpg)", profile_image or "")
    if match:
        (_profile_upload_directory() / match.group(1)).unlink(missing_ok=True)


def _prepare_profile_avatar(contents):
    try:
        with Image.open(io.BytesIO(contents)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Choose a JPEG, PNG, or WebP image.")
            if (
                source.width > PROFILE_IMAGE_MAX_DIMENSION
                or source.height > PROFILE_IMAGE_MAX_DIMENSION
                or source.width * source.height > PROFILE_IMAGE_MAX_PIXELS
            ):
                raise ValueError("Choose an image no larger than 4096 × 4096 pixels.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("Choose a valid JPEG, PNG, or WebP image.") from error


def get_user_by_email(email):
    email = _normalize_email(email)
    if not email:
        return None
    with closing(_connect_database(AUTH_DATABASE)) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT id, name, full_name, username, email, password_hash, profile_image, is_email_verified, onboarding_completed FROM users WHERE email = ?",
            (email,),
        ).fetchone()


def get_user_by_username(username):
    username = _normalize_username(username)
    if not username:
        return None
    with closing(_connect_database(AUTH_DATABASE)) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT id, name, full_name, username, email, password_hash, profile_image, is_email_verified, onboarding_completed FROM users WHERE LOWER(username) = ?",
            (username,),
        ).fetchone()


def get_user_by_identifier(identifier):
    identifier = _normalize_identifier(identifier)
    if not identifier:
        return None
    user = get_user_by_email(identifier)
    if user is not None:
        return user
    return get_user_by_username(identifier)


def get_authenticated_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with closing(_connect_database(AUTH_DATABASE)) as connection:
        connection.row_factory = sqlite3.Row
        user = connection.execute(
            "SELECT id, name, full_name, username, email, password_hash, profile_image, is_email_verified, onboarding_completed FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if user is None:
        session.clear()
    return user


def extract_landmark_features(results):
    if results.face_landmarks is None:
        return None

    face = results.face_landmarks.landmark
    face_anchor = face[1]
    features = []

    for landmark in face:
        features.extend((landmark.x - face_anchor.x, landmark.y - face_anchor.y))

    for hand_landmarks in (results.left_hand_landmarks, results.right_hand_landmarks):
        if hand_landmarks is None:
            features.extend([0.0] * 42)
            continue

        hand = hand_landmarks.landmark
        hand_anchor = hand[8]
        for landmark in hand:
            features.extend((landmark.x - hand_anchor.x, landmark.y - hand_anchor.y))

    feature_array = np.asarray(features, dtype=np.float32)
    if feature_array.shape != (1020,):
        raise RuntimeError(
            f"Expected 1020 face and hand landmark values, got {feature_array.size}."
        )
    return feature_array


class NoFaceDetected(ValueError):
    pass


def _ensure_inference_components():
    global holistic, face_detector

    if holistic is None:
        holistic = mp.solutions.holistic.Holistic(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.5,
        )
    if face_detector is None:
        face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.5,
        )


def predict_mood_scores(image_array):
    if image_array is None:
        raise ValueError("The uploaded image could not be decoded.")

    mirrored_image = cv2.flip(image_array, 1)
    rgb_image = cv2.cvtColor(mirrored_image, cv2.COLOR_BGR2RGB)

    with inference_lock:
        _ensure_inference_components()
        detections = face_detector.process(rgb_image).detections or []
        if len(detections) > 1:
            raise FrameQualityError(
                "More than one face was visible. Please make sure you are alone in the frame."
            )
        if not detections:
            raise NoFaceDetected("No face was found. Center your face and try again.")

        results = holistic.process(rgb_image)
        features = extract_landmark_features(results)
        if features is None:
            raise NoFaceDetected("No face was found. Center your face and try again.")

        validate_frame_quality(mirrored_image, results.face_landmarks)
        scores = np.asarray(model.predict(features.reshape(1, 1020), verbose=0))[0]

    if (
        scores.shape != (len(labels),)
        or not np.isfinite(scores).all()
        or np.any(scores < 0)
        or np.any(scores > 1)
        or not np.isclose(np.sum(scores), 1.0, atol=0.02)
    ):
        raise RuntimeError("The emotion model returned invalid prediction scores.")

    return scores


def predict_mood(image_array):
    scores = predict_mood_scores(image_array)
    best_match = int(np.argmax(scores))
    return {
        "mood": normalize_mood(labels[best_match], MOOD_ALIASES),
        "confidence": float(scores[best_match]),
    }


def predict_mood_from_frames(image_arrays):
    predictions = []
    rejected_frames = []
    for image_array in image_arrays:
        try:
            predictions.append(predict_mood_scores(image_array))
        except (NoFaceDetected, FrameQualityError) as error:
            rejected_frames.append(str(error))

    required_frames = 1 if len(image_arrays) == 1 else max(3, (len(image_arrays) + 1) // 2)
    if len(predictions) < required_frames:
        error_message = (
            max(set(rejected_frames), key=rejected_frames.count)
            if rejected_frames
            else "Your face could not be detected clearly enough. Improve the lighting, center your face, and try again."
        )
        raise NoFaceDetected(
            f"{error_message} At least {required_frames} usable frame(s) are needed."
        )

    result = aggregate_predictions(
        predictions,
        labels,
        MOOD_ALIASES,
        total_frames=len(image_arrays),
    )
    if len(predictions) != len(image_arrays):
        result["quality_status"] = "partial"
    return result


@app.route("/")
def index():
    if not (FRONTEND_DIST / "index.html").is_file():
        abort(503, description="Build the React app first with `npm run build`.")
    return send_from_directory(FRONTEND_DIST, "index.html")


@app.route("/mannkidhun.svg")
def brand_icon():
    if not (FRONTEND_DIST / "mannkidhun.svg").is_file():
        abort(503, description="Build the React app first with `npm run build`.")
    return send_from_directory(FRONTEND_DIST, "mannkidhun.svg")


@app.route("/<path:page>")
def frontend_page(page):
    if page not in {
        "app",
        "assistant",
        "dashboard",
        "mood-check",
        "profile",
        "signin",
        "signup",
    }:
        abort(404)
    if not (FRONTEND_DIST / "index.html").is_file():
        abort(503, description="Build the React app first with `npm run build`.")
    return send_from_directory(FRONTEND_DIST, "index.html")


def _issue_reset_token(user_id, token_type):
    token = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.execute(
            "INSERT INTO password_reset_tokens (user_id, token_type, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, token_type, hashed, expires_at, _sqlite_now()),
        )
    return token


@app.route("/api/auth/register", methods=["POST"], endpoint="auth_register_legacy")
@app.route("/api/v1/auth/register", methods=["POST"], endpoint="auth_register")
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Enter your name, username, email, and password."}), 400

    name = payload.get("full_name") or payload.get("name")
    username = payload.get("username")
    email = payload.get("email")
    password = payload.get("password", "")
    confirm_password = payload.get("confirm_password", password)
    accepted_terms = payload.get("accepted_terms", payload.get("terms_accepted", True))

    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
        return jsonify({"error": "Enter your full name."}), 400
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return jsonify({"error": "Use a password between 8 and 128 characters."}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400
    if not _coerce_bool(accepted_terms):
        return jsonify({"error": "Please accept the terms and privacy policy."}), 400

    if username is None:
        username = email.split("@", 1)[0]
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username.strip()):
        return jsonify({"error": "Choose a username with 3 to 32 letters, numbers, or underscores."}), 400

    name = name.strip()
    username = _normalize_username(username)
    email = _normalize_email(email)

    try:
        with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
            connection.row_factory = sqlite3.Row
            if connection.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email,),
            ).fetchone():
                return jsonify({"error": "An account with this email already exists."}), 409
            if connection.execute(
                "SELECT 1 FROM users WHERE LOWER(username) = ?",
                (username,),
            ).fetchone():
                return jsonify({"error": "That username is already taken."}), 409
            cursor = connection.execute(
                "INSERT INTO users (name, full_name, username, email, password_hash, is_email_verified, onboarding_completed, updated_at) VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
                (name, name, username, email, generate_password_hash(password), _sqlite_now()),
            )
            user = {
                "id": cursor.lastrowid,
                "name": name,
                "full_name": name,
                "username": username,
                "email": email,
                "is_email_verified": False,
                "onboarding_completed": False,
            }
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = bool(payload.get("remember_me", False))
    return jsonify({"user": public_user(user)}), 201


@app.route("/api/auth/login", methods=["POST"], endpoint="auth_login_legacy")
@app.route("/api/v1/auth/login", methods=["POST"], endpoint="auth_login")
def login():
    payload = request.get_json(silent=True)
    email_or_username = None
    password = None
    if isinstance(payload, dict):
        email_or_username = payload.get("email")
        if email_or_username is None and payload.get("username") is not None:
            email_or_username = payload.get("username")
        if email_or_username is None and payload.get("email_or_username") is not None:
            email_or_username = payload.get("email_or_username")
        password = payload.get("password")

    if (
        not isinstance(email_or_username, str)
        or not email_or_username.strip()
        or not isinstance(password, str)
        or len(password) > 128
    ):
        return jsonify({"error": "Enter your email or username and password."}), 400

    identifier = email_or_username.strip()
    user = get_user_by_identifier(identifier)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "The email or password you entered is incorrect."}), 401

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = _coerce_bool(payload.get("remember_me", False)) if isinstance(payload, dict) else False
    return jsonify({"user": public_user(dict(user))})


@app.route("/api/auth/session", endpoint="auth_session_legacy")
@app.route("/api/v1/auth/me", endpoint="auth_me")
@app.route("/api/v1/auth/session", endpoint="auth_session_v1")
def auth_session():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"user": None})
    return jsonify({"user": public_user(dict(user))})


@app.route("/api/auth/logout", methods=["POST"], endpoint="auth_logout_legacy")
@app.route("/api/v1/auth/logout", methods=["POST"], endpoint="auth_logout")
def logout():
    session.clear()
    return jsonify({"user": None})


@app.route("/api/auth/forgot-password", methods=["POST"], endpoint="auth_forgot_password_legacy")
@app.route("/api/v1/auth/forgot-password", methods=["POST"], endpoint="auth_forgot_password")
def forgot_password():
    payload = request.get_json(silent=True)
    email = payload.get("email") if isinstance(payload, dict) else None
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        return jsonify({"error": "Enter a valid email address."}), 400

    return jsonify({
        "message": (
            "If an account with that email exists, reset instructions will be available "
            "once email delivery is configured."
        ),
    })


@app.route("/api/auth/reset-password", methods=["POST"], endpoint="auth_reset_password_legacy")
@app.route("/api/v1/auth/reset-password", methods=["POST"], endpoint="auth_reset_password")
def reset_password():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Enter a reset token and a new password."}), 400

    token = payload.get("token")
    password = payload.get("new_password") or payload.get("password")
    confirm_password = payload.get("confirm_password", password)
    if not isinstance(token, str) or not token.strip() or not isinstance(password, str) or not 8 <= len(password) <= 128:
        return jsonify({"error": "Enter a valid reset token and a new password."}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.row_factory = sqlite3.Row
        token_row = connection.execute(
            "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token_hash = ? AND token_type = 'password_reset' ORDER BY created_at DESC LIMIT 1",
            (token_hash,),
        ).fetchone()
        if token_row is None:
            return jsonify({"error": "This reset link is invalid or has already been used."}), 400

        expires_at = datetime.strptime(token_row["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if now > expires_at or token_row["used_at"] is not None:
            return jsonify({"error": "This reset link has expired."}), 400

        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (generate_password_hash(password), _sqlite_now(), token_row["user_id"]),
        )
        connection.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
            (_sqlite_now(), token_row["id"]),
        )

    return jsonify({"message": "Your password was updated successfully."})


@app.route("/api/auth/verify-email", methods=["POST"], endpoint="auth_verify_email_legacy")
@app.route("/api/v1/auth/verify-email", methods=["POST"], endpoint="auth_verify_email")
def verify_email():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide a verification token."}), 400

    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        return jsonify({"error": "Provide a verification token."}), 400

    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.row_factory = sqlite3.Row
        token_row = connection.execute(
            "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token_hash = ? AND token_type = 'email_verification' ORDER BY created_at DESC LIMIT 1",
            (token_hash,),
        ).fetchone()
        if token_row is None:
            return jsonify({"error": "This verification link is invalid."}), 400
        expires_at = datetime.strptime(token_row["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if now > expires_at or token_row["used_at"] is not None:
            return jsonify({"error": "This verification link has expired."}), 400

        connection.execute(
            "UPDATE users SET is_email_verified = 1, updated_at = ? WHERE id = ?",
            (_sqlite_now(), token_row["user_id"]),
        )
        connection.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
            (_sqlite_now(), token_row["id"]),
        )

    return jsonify({"message": "Your email address was verified successfully."})


@app.route("/api/auth/resend-verification", methods=["POST"], endpoint="auth_resend_verification_legacy")
@app.route("/api/v1/auth/resend-verification", methods=["POST"], endpoint="auth_resend_verification")
def resend_verification():
    payload = request.get_json(silent=True)
    email = payload.get("email") if isinstance(payload, dict) else None
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        return jsonify({"error": "Enter a valid email address."}), 400

    email = _normalize_email(email)
    user = get_user_by_email(email)
    if user is not None:
        _issue_reset_token(user["id"], "email_verification")
    return jsonify({"message": "If the account exists, we sent a verification email."})


@app.route("/api/profile", methods=["PUT"])
@app.route("/api/v1/users/me", methods=["GET", "PUT", "DELETE"])
def users_me():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401

    if request.method == "GET":
        return jsonify({"user": public_user(dict(user))})

    if request.method == "DELETE":
        with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
            connection.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        session.clear()
        try:
            _delete_profile_avatar(user["profile_image"])
        except OSError:
            app.logger.warning("Could not remove deleted account's profile photo.")
        return jsonify({"message": "Your account was deleted."})

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Enter your profile details."}), 400

    name = payload.get("full_name") or payload.get("name")
    username = payload.get("username")
    email = payload.get("email")
    current_password = payload.get("current_password")
    new_password = payload.get("new_password", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
        return jsonify({"error": "Enter a valid name."}), 400
    if username is not None and (
        not isinstance(username, str)
        or not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username.strip())
    ):
        return jsonify({"error": "Choose a username with 3 to 32 letters, numbers, or underscores."}), 400
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not isinstance(current_password, str) or not current_password:
        return jsonify({"error": "Enter your current password to save your profile."}), 400
    if new_password and (not isinstance(new_password, str) or not 8 <= len(new_password) <= 128):
        return jsonify({"error": "New passwords must be between 8 and 128 characters."}), 400

    if not check_password_hash(user["password_hash"], current_password):
        return jsonify({"error": "Your current password is incorrect."}), 401

    name = name.strip()
    email = _normalize_email(email)
    username = _normalize_username(username) if username is not None else user["username"]

    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.row_factory = sqlite3.Row
        duplicate_email = connection.execute(
            "SELECT 1 FROM users WHERE email = ? AND id != ?",
            (email, user["id"]),
        ).fetchone()
        if duplicate_email is not None:
            return jsonify({"error": "An account with this email already exists."}), 409
        duplicate_username = connection.execute(
            "SELECT 1 FROM users WHERE LOWER(username) = ? AND id != ?",
            (username, user["id"]),
        ).fetchone()
        if duplicate_username is not None:
            return jsonify({"error": "That username is already taken."}), 409

        if new_password:
            updates = [
                "name = ?",
                "full_name = ?",
                "username = ?",
                "email = ?",
                "password_hash = ?",
                "updated_at = ?",
            ]
            values = [
                name,
                name,
                username,
                email,
                generate_password_hash(new_password),
                _sqlite_now(),
                user["id"],
            ]
        else:
            updates = ["name = ?", "full_name = ?", "username = ?", "email = ?", "updated_at = ?"]
            values = [name, name, username, email, _sqlite_now(), user["id"]]
        connection.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            tuple(values),
        )

    updated_user = get_user_by_email(email)
    return jsonify({"user": public_user(dict(updated_user))})


@app.route("/api/profile/avatar", methods=["POST", "DELETE"])
@app.route("/api/v1/users/me/avatar", methods=["POST", "DELETE"])
def profile_avatar():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401

    previous_avatar = user["profile_image"]
    if request.method == "DELETE":
        with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
            connection.execute(
                "UPDATE users SET profile_image = NULL, updated_at = ? WHERE id = ?",
                (_sqlite_now(), user["id"]),
            )
        try:
            _delete_profile_avatar(previous_avatar)
        except OSError:
            app.logger.warning("Could not remove a profile photo after it was cleared.")
        updated_user = get_user_by_email(user["email"])
        return jsonify({"user": public_user(dict(updated_user))})

    upload = request.files.get("avatar")
    if upload is None:
        return jsonify({"error": "Choose a profile photo to upload."}), 400
    contents = upload.stream.read(PROFILE_IMAGE_MAX_BYTES + 1)
    if len(contents) > PROFILE_IMAGE_MAX_BYTES:
        return jsonify({"error": "Profile photos must be 2 MB or smaller."}), 413
    try:
        image_contents = _prepare_profile_avatar(contents)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    filename = f"{uuid.uuid4().hex}.jpg"
    avatar_url = f"/api/profile/avatar/{filename}"
    avatar_directory = _profile_upload_directory()
    avatar_path = avatar_directory / filename
    try:
        avatar_directory.mkdir(parents=True, exist_ok=True)
        avatar_path.write_bytes(image_contents)
    except OSError:
        app.logger.exception("Could not save an uploaded profile photo.")
        return jsonify({"error": "We couldn’t save your profile photo. Please try again."}), 500

    try:
        with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
            connection.execute(
                "UPDATE users SET profile_image = ?, updated_at = ? WHERE id = ?",
                (avatar_url, _sqlite_now(), user["id"]),
            )
    except sqlite3.Error:
        avatar_path.unlink(missing_ok=True)
        raise

    updated_user = get_user_by_email(user["email"])
    try:
        _delete_profile_avatar(previous_avatar)
    except OSError:
        app.logger.warning("Could not remove a replaced profile photo.")
    return jsonify({"user": public_user(dict(updated_user))})


@app.route("/api/profile/avatar/<filename>", methods=["GET"])
def serve_profile_avatar(filename):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if (
        not re.fullmatch(r"[a-f0-9]{32}\.jpg", filename)
        or user["profile_image"] != f"/api/profile/avatar/{filename}"
    ):
        return jsonify({"error": "Profile photo not found."}), 404
    response = send_from_directory(
        _profile_upload_directory(),
        filename,
        mimetype="image/jpeg",
        conditional=True,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/api/profile", methods=["GET"])
def legacy_profile_get():
    return users_me()


@app.route("/api/v1/preferences", methods=["GET", "PUT"])
def user_preferences():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401

    preference_row = None
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.row_factory = sqlite3.Row
        preference_row = connection.execute(
            "SELECT preferred_languages, preferred_genres, preferred_listening_styles, favourite_artists FROM user_preferences WHERE user_id = ?",
            (user["id"],),
        ).fetchone()

    if preference_row is None:
        preference_row = {
            "preferred_languages": "[]",
            "preferred_genres": "[]",
            "preferred_listening_styles": "[]",
            "favourite_artists": "[]",
        }

    if request.method == "GET":
        return jsonify({
            "preferred_languages": _normalize_list_field(preference_row["preferred_languages"]),
            "preferred_genres": _normalize_list_field(preference_row["preferred_genres"]),
            "preferred_listening_styles": _normalize_list_field(preference_row["preferred_listening_styles"]),
            "favourite_artists": _normalize_list_field(preference_row["favourite_artists"]),
            "onboarding_completed": bool(user["onboarding_completed"]),
        })

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide preferences in JSON format."}), 400

    return _save_user_preferences(user, payload)


def _save_user_preferences(user, payload, onboarding_completed=None):
    preferred_languages = _normalize_list_field(payload.get("preferred_languages", []))
    preferred_genres = _normalize_list_field(payload.get("preferred_genres", []))
    preferred_listening_styles = _normalize_list_field(payload.get("preferred_listening_styles", []))
    favourite_artists = _normalize_list_field(payload.get("favourite_artists", []))
    if onboarding_completed is None:
        onboarding_completed = payload.get("onboarding_completed")

    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.execute(
            "INSERT INTO user_preferences (user_id, preferred_languages, preferred_genres, preferred_listening_styles, favourite_artists, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET preferred_languages = excluded.preferred_languages, preferred_genres = excluded.preferred_genres, preferred_listening_styles = excluded.preferred_listening_styles, favourite_artists = excluded.favourite_artists, updated_at = excluded.updated_at",
            (
                user["id"],
                _json_dumps(preferred_languages),
                _json_dumps(preferred_genres),
                _json_dumps(preferred_listening_styles),
                _json_dumps(favourite_artists),
                _sqlite_now(),
            ),
        )
        if onboarding_completed is not None:
            connection.execute(
                "UPDATE users SET onboarding_completed = ?, updated_at = ? WHERE id = ?",
                (1 if _coerce_bool(onboarding_completed) else 0, _sqlite_now(), user["id"]),
            )

    return jsonify({
        "preferred_languages": preferred_languages,
        "preferred_genres": preferred_genres,
        "preferred_listening_styles": preferred_listening_styles,
        "favourite_artists": favourite_artists,
        "onboarding_completed": bool(_coerce_bool(onboarding_completed)) if onboarding_completed is not None else bool(user["onboarding_completed"]),
    })


@app.route("/api/v1/preferences/onboarding-status")
def onboarding_status():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        row = connection.execute(
            "SELECT onboarding_completed FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
    return jsonify({"onboarding_completed": bool(row[0] if row else 0)})


@app.route("/api/v1/preferences/onboarding/complete", methods=["POST"])
def complete_onboarding():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide preferences in JSON format."}), 400
    return _save_user_preferences(user, payload, onboarding_completed=True)


@app.route("/api/v1/artists/search")
def search_artists():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"artists": []})
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        rows = connection.execute(
            "SELECT id, name FROM artists WHERE LOWER(name) LIKE ? ORDER BY name LIMIT 20",
            (f"%{query.lower()}%",),
        ).fetchall()
    return jsonify({"artists": [{"id": row[0], "name": row[1]} for row in rows]})


@app.route("/api/v1/artists/popular")
def popular_artists():
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        rows = connection.execute(
            "SELECT id, name FROM artists ORDER BY name LIMIT 20"
        ).fetchall()
    return jsonify({"artists": [{"id": row[0], "name": row[1]} for row in rows]})


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "The uploaded image is too large."}), 413


@app.route("/api/auth/validate-session", endpoint="validate_session_legacy")
def validate_session():
    return auth_session()


@app.route("/api/auth/me", endpoint="auth_me_legacy")
def auth_me():
    return auth_session()


@app.route("/api/auth/status", endpoint="auth_status_legacy")
def auth_status():
    return auth_session()


@app.route("/api/v1/users/me/preferences", methods=["GET", "PUT"])
def user_preferences_alias():
    return user_preferences()


@app.route("/api/v1/users/me/preferences/onboarding-status")
def onboarding_status_alias():
    return onboarding_status()


@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(silent=True, cache=False)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send one or more images as base64 data URLs."}), 400

    if "images" in payload:
        data_urls = payload["images"]
        if not isinstance(data_urls, list) or not 3 <= len(data_urls) <= 7:
            return jsonify({"error": "Send between 3 and 7 camera frames."}), 400
    elif isinstance(payload.get("image"), str):
        data_urls = [payload["image"]]
    else:
        return jsonify({"error": "Send one or more images as base64 data URLs."}), 400

    images = []
    for data_url in data_urls:
        if not isinstance(data_url, str):
            return jsonify({"error": "Each image must be a base64 data URL."}), 400
        header, separator, encoded_image = data_url.partition(",")
        if not separator:
            return jsonify({"error": "Images must be JPEG or PNG data URLs."}), 400

        header_lower = header.lower()
        if ":" not in header_lower or not header_lower.startswith("data:"):
            return jsonify({"error": "Images must be JPEG or PNG data URLs."}), 400
        mime_kind = header_lower.split(":", 1)[1].split(";", 1)[0].strip()
        if mime_kind not in {"image/jpeg", "image/jpg", "image/png"}:
            return jsonify({"error": "Images must be JPEG or PNG data URLs."}), 400

        try:
            image_bytes = base64.b64decode(encoded_image, validate=True)
        except (binascii.Error, ValueError):
            return jsonify({"error": "An image is not valid base64."}), 400

        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return jsonify({"error": "An uploaded image could not be decoded."}), 400
        images.append(image)

    if "images" in payload:
        payload["images"].clear()
    else:
        payload["image"] = ""
    data_urls.clear()
    del image, image_bytes, encoded_image, data_url, separator, header

    try:
        result = predict_mood_from_frames(images)
    except NoFaceDetected as error:
        return jsonify({"error": str(error)}), 422
    except UncertainMoodDetected as error:
        return jsonify({"error": str(error)}), 422
    except RuntimeError as error:
        app.logger.error("Expression inference failed: %s", error)
        return jsonify(
            {"error": "Expression analysis is temporarily unavailable. Please try again."}
        ), 500
    finally:
        images.clear()

    return jsonify(result)


@app.route("/api/v1/recommendations", methods=["GET"])
@app.route("/api/v1/recommendations/discover", methods=["GET"])
@app.route("/api/v1/recommendations/generate", methods=["POST"])
def recommendations_index():
    user = get_authenticated_user()
    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Provide recommendation options in JSON format."}), 400
    else:
        payload = {}
    vibe = request.args.get("vibe") or payload.get("vibe") or payload.get("selected_vibe") or request.args.get("mood") or payload.get("mood")
    mood = request.args.get("mood") or payload.get("mood") or (vibe if vibe else None)
    limit = request.args.get("limit", type=int) or payload.get("limit") or 6
    try:
        limit = max(1, min(int(limit), 12))
    except (TypeError, ValueError):
        limit = 6

    recommendations = get_user_recommendations(
        str(AUTH_DATABASE),
        user_id=user["id"] if user else None,
        mood=mood,
        vibe=vibe,
        limit=limit,
    )
    return jsonify({
        "recommendations": recommendations,
        "count": len(recommendations),
        "vibe": vibe,
        "source": "hybrid",
    })


def _assistant_rate_limited(user_id):
    now = time.monotonic()
    with assistant_rate_lock:
        requests = assistant_requests[user_id]
        while requests and now - requests[0] >= 60:
            requests.popleft()
        if len(requests) >= 12:
            return True
        requests.append(now)
        return False


@app.route("/api/v1/assistant/chat", methods=["POST"])
def assistant_chat():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to use the music assistant."}), 401
    if _assistant_rate_limited(user["id"]):
        return jsonify({"error": "You’ve sent several requests. Please try again in a minute."}), 429

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send your music request as JSON."}), 400
    message = payload.get("message")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 500:
        return jsonify({"error": "Enter a request between 1 and 500 characters."}), 400
    use_preferences = payload.get("use_preferences", False)
    use_history = payload.get("use_history", False)
    if type(use_preferences) is not bool or type(use_history) is not bool:
        return jsonify({"error": "Personalisation choices must be true or false."}), 400
    previous_intent = payload.get("previous_intent")
    if previous_intent is not None and not isinstance(previous_intent, dict):
        return jsonify({"error": "Conversation context is invalid."}), 400

    with closing(_connect_database(AUTH_DATABASE)) as connection:
        known_artists = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM artists ORDER BY LENGTH(name) DESC, name"
            ).fetchall()
        ]

    intent, intent_provider = extract_music_intent(
        message.strip(), known_artists, previous_intent
    )
    context_vibes = {
        "studying": "focused",
        "travelling": "energetic",
        "evening": "relaxed",
        "workout": "energetic",
        "sleep": "relaxed",
    }
    vibe = intent["mood"] or context_vibes.get(intent["context"], "neutral")
    query_filters = {
        key: intent[key] for key in ("genre", "language", "artist") if intent[key]
    }
    if intent["mood"]:
        query_filters["vibe"] = vibe
    recommendations = get_user_recommendations(
        str(AUTH_DATABASE),
        user_id=user["id"],
        mood=vibe,
        vibe=vibe,
        limit=6,
        include_preferences=use_preferences,
        include_history=use_history,
        query_filters=query_filters,
    )
    used_fallback = not recommendations and bool(query_filters)
    if used_fallback:
        recommendations = get_user_recommendations(
            str(AUTH_DATABASE),
            user_id=user["id"],
            mood=vibe,
            vibe=vibe,
            limit=6,
            include_preferences=use_preferences,
            include_history=use_history,
        )

    if recommendations:
        if used_fallback:
            response_text = (
                "I couldn’t find an exact match for those catalogue filters, "
                "so here are available alternatives."
            )
        elif use_preferences or use_history:
            response_text = (
                "Here are available catalogue tracks, ranked using the personalisation "
                "options you selected."
            )
        else:
            response_text = "Here are available catalogue tracks for your request."
    else:
        response_text = "I couldn’t find matching tracks in the available catalogue."

    return jsonify(
        {
            "response": response_text,
            "recommendations": recommendations,
            "intent": intent,
            "used_fallback": used_fallback,
            "intent_provider": intent_provider,
            "personalisation": {
                "preferences": use_preferences,
                "listening_history": use_history,
            },
        }
    )


@app.route("/api/v1/recommendations/similar/<int:song_id>", methods=["GET"])
def recommendation_similar(song_id):
    user = get_authenticated_user()
    with closing(_connect_database(AUTH_DATABASE)) as connection:
        row = connection.execute(
            "SELECT genre FROM songs WHERE id = ?",
            (song_id,),
        ).fetchone()
    if row is None:
        return jsonify({"recommendations": []}), 404
    genre = row[0]
    recommendations = get_user_recommendations(
        str(AUTH_DATABASE),
        user_id=user["id"] if user else None,
        vibe=genre,
        limit=6,
    )
    recommendations = [item for item in recommendations if item["id"] != song_id]
    return jsonify({"recommendations": recommendations[:6], "count": len(recommendations[:6])})


@app.route("/api/v1/songs/<int:song_id>/like", methods=["POST"])
@app.route("/api/v1/songs/<int:song_id>/dislike", methods=["POST"])
@app.route("/api/v1/songs/<int:song_id>/save", methods=["POST"])
@app.route("/api/v1/songs/<int:song_id>/skip", methods=["POST"])
def song_interaction(song_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401

    interaction_type = request.path.rsplit("/", 1)[-1]
    source = request.get_json(silent=True) or {}
    if isinstance(source, dict):
        source = source.get("source") or source.get("context") or "library"
    else:
        source = "library"
    if not record_user_interaction(str(AUTH_DATABASE), user["id"], song_id, interaction_type, source=source):
        return jsonify({"error": "Could not record this interaction."}), 400
    return jsonify({"status": "ok", "interaction": interaction_type, "song_id": song_id})


@app.route("/api/v1/users/me/saved-songs", methods=["GET", "POST"])
def saved_songs():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Provide a song id."}), 400
        song_id = payload.get("song_id") or payload.get("id")
        try:
            song_id = int(song_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Provide a valid song id."}), 400
        if not save_song(str(AUTH_DATABASE), user["id"], song_id):
            return jsonify({"error": "Could not save this song."}), 400
        return jsonify({"status": "ok", "saved": True, "song_id": song_id})

    return jsonify({"songs": get_saved_songs(str(AUTH_DATABASE), user["id"])})


@app.route("/api/v1/users/me/saved-songs/<int:song_id>", methods=["DELETE"])
def saved_song_delete(song_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if remove_saved_song(str(AUTH_DATABASE), user["id"], song_id):
        return jsonify({"status": "ok", "deleted": True, "song_id": song_id})
    return jsonify({"error": "This song was not saved."}), 404


@app.route("/api/v1/users/me/listening-history", methods=["GET", "POST", "DELETE"])
def listening_history():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if request.method == "DELETE":
        clear_listening_history(str(AUTH_DATABASE), user["id"])
        return jsonify({"status": "ok", "deleted": True})
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Provide a song interaction."}), 400
        song_id = payload.get("song_id") or payload.get("id")
        event_type = payload.get("event_type") or payload.get("interaction_type") or "listen"
        try:
            song_id = int(song_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Provide a valid song id."}), 400
        source = payload.get("source") or payload.get("context") or "library"
        position_ms = payload.get("position_ms", 0)
        duration_ms = payload.get("duration_ms", 0)
        if not record_user_interaction(
            str(AUTH_DATABASE),
            user["id"],
            song_id,
            event_type,
            source=source,
            position_ms=position_ms,
            duration_ms=duration_ms,
        ):
            return jsonify({"error": "Could not record this interaction."}), 400
        return jsonify({"status": "ok", "interaction": event_type, "song_id": song_id}), 201
    return jsonify({"history": get_listening_history(str(AUTH_DATABASE), user["id"])})


@app.route("/api/v1/playlists", methods=["GET", "POST"])
def playlists_index():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if request.method == "GET":
        return jsonify({"playlists": get_user_playlists(str(AUTH_DATABASE), user["id"])})

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide playlist details."}), 400
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "A playlist name is required."}), 400
    playlist = create_playlist(
        str(AUTH_DATABASE),
        user["id"],
        name,
        description=str(payload.get("description") or ""),
        artwork_url=payload.get("artwork_url") or "",
        is_public=_coerce_bool(payload.get("is_public", False)),
    )
    return jsonify({"playlist": playlist}), 201


@app.route("/api/v1/playlists/<int:playlist_id>", methods=["GET", "PUT", "DELETE"])
def playlist_detail(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if request.method == "GET":
        playlist = get_playlist_details(str(AUTH_DATABASE), playlist_id, user_id=user["id"])
        if playlist is None:
            return jsonify({"error": "Playlist not found."}), 404
        return jsonify({"playlist": playlist})
    if request.method == "DELETE":
        if delete_playlist(str(AUTH_DATABASE), user["id"], playlist_id):
            return jsonify({"status": "ok", "deleted": True})
        return jsonify({"error": "Playlist not found."}), 404

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide updated playlist details."}), 400
    try:
        updated = update_playlist(str(AUTH_DATABASE), user["id"], playlist_id, payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if updated is None:
        return jsonify({"error": "Playlist not found."}), 404
    return jsonify({"playlist": updated})


@app.route("/api/v1/playlists/<int:playlist_id>/tracks", methods=["POST"])
def playlist_tracks_add(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    payload = request.get_json(silent=True) or {}
    song_id = payload.get("song_id") if isinstance(payload, dict) else None
    if song_id is None:
        song_id = request.args.get("song_id")
    try:
        song_id = int(song_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Provide a valid song id."}), 400
    playlist = add_song_to_playlist(str(AUTH_DATABASE), user["id"], playlist_id, song_id)
    if playlist is None:
        return jsonify({"error": "Playlist or song not found."}), 404
    return jsonify({"playlist": playlist})


@app.route("/api/v1/playlists/<int:playlist_id>/tracks/<int:song_id>", methods=["DELETE"])
def playlist_track_remove(playlist_id, song_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if remove_song_from_playlist(str(AUTH_DATABASE), user["id"], playlist_id, song_id):
        return jsonify({"status": "ok", "deleted": True, "song_id": song_id})
    return jsonify({"error": "Track not found in this playlist."}), 404


@app.route("/api/v1/playlists/<int:playlist_id>/reorder", methods=["POST"])
def playlist_tracks_reorder(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    payload = request.get_json(silent=True) or {}
    ordered = payload.get("song_ids") if isinstance(payload, dict) else None
    if ordered is None:
        ordered = payload.get("order") if isinstance(payload, dict) else None
    updated = reorder_playlist_tracks(str(AUTH_DATABASE), user["id"], playlist_id, ordered or [])
    if updated is None:
        return jsonify({"error": "Playlist not found."}), 404
    return jsonify({"playlist": updated})


@app.route("/api/v1/users/me/playback-state", methods=["GET", "POST", "DELETE"])
def playback_state():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to continue."}), 401
    if request.method == "DELETE":
        clear_playback_state(str(AUTH_DATABASE), user["id"])
        return jsonify({"status": "ok", "deleted": True})
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Provide playback state."}), 400
        state = save_playback_state(str(AUTH_DATABASE), user["id"], payload)
        return jsonify({"state": state})
    return jsonify({"state": get_playback_state(str(AUTH_DATABASE), user["id"])})


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "The uploaded image is too large."}), 413


@app.route("/healthz")
def health_check():
    try:
        with closing(_connect_database(AUTH_DATABASE, timeout=1)) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        app.logger.exception("Health check could not reach the application database.")
        return jsonify({"status": "unavailable"}), 503
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5001")),
        debug=False,
        threaded=True,
    )

