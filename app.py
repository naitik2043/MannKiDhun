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
from urllib.parse import urlsplit
from collections import OrderedDict, defaultdict, deque
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import Flask, abort, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from database_migrations import run_migrations
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
    accept_playlist_invite,
    can_edit_playlist,
    create_playlist_invite,
    get_playlist_collaborators,
    revoke_playlist_invites,
    remove_playlist_collaborator,
    update_playlist_collaborator,
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
    create_listening_room,
    join_listening_room,
    get_listening_room,
    update_listening_room,
    close_listening_room,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
_configured_data_dir = os.environ.get("MANNKIDHUN_DATA_DIR", "").strip()
INSTANCE_DIR = (
    Path(_configured_data_dir).expanduser()
    if _configured_data_dir
    else BASE_DIR / "instance"
)
if not INSTANCE_DIR.is_absolute():
    INSTANCE_DIR = (BASE_DIR / INSTANCE_DIR).resolve()
AUTH_DATABASE = INSTANCE_DIR / "moodwave.sqlite3"
MOOD_ALIASES = {
    "susurprise": "surprise",
    "rocrock": "rock",
}
ALLOWED_LISTENING_CONTEXTS = {"studying", "travelling", "evening", "workout", "sleep"}
CONTEXT_VIBE_FALLBACK = {
    "studying": "focused",
    "travelling": "energetic",
    "evening": "relaxed",
    "workout": "energetic",
    "sleep": "relaxed",
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

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60
# Keep attacker-controlled identifier/IP combinations from growing without bound.
LOGIN_ATTEMPT_MAX_KEYS = 10_000
login_attempt_lock = threading.Lock()
login_attempts = OrderedDict()


@app.before_request
def validate_browser_request_origin():
    """Reject cross-site browser mutations while preserving configured dev origins."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if not (request.path.startswith("/api/") or request.path == "/predict"):
        return None

    source = request.headers.get("Origin")
    if not source:
        source = request.headers.get("Referer")
    if not source:
        # Non-browser clients and older same-origin clients may omit both headers.
        return None

    parsed_source = urlsplit(source)
    if parsed_source.scheme not in {"http", "https"} or not parsed_source.netloc:
        return jsonify({"error": "This request origin is not allowed."}), 403

    allowed_hosts = {request.host.lower()}
    configured_origins = os.environ.get("MANNKIDHUN_ALLOWED_ORIGINS", "")
    for configured_origin in configured_origins.split(","):
        parsed_allowed = urlsplit(configured_origin.strip())
        if parsed_allowed.scheme in {"http", "https"} and parsed_allowed.netloc:
            allowed_hosts.add(parsed_allowed.netloc.lower())

    if parsed_source.netloc.lower() not in allowed_hosts:
        return jsonify({"error": "This request origin is not allowed."}), 403

    expected_token = session.get("mannkidhun_csrf_token")
    cookie_token = request.cookies.get("mannkidhun_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    if (
        not isinstance(expected_token, str)
        or not isinstance(cookie_token, str)
        or not isinstance(header_token, str)
        or not secrets.compare_digest(expected_token, cookie_token)
        or not secrets.compare_digest(expected_token, header_token)
    ):
        return jsonify({"error": "The browser request could not be verified. Refresh and try again."}), 403
    return None


def _login_attempt_key(identifier):
    normalized = identifier.strip().casefold()
    identifier_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return (request.remote_addr or "unknown", identifier_hash)


def _prune_login_attempts(attempts, now):
    while attempts and now - attempts[0] >= LOGIN_ATTEMPT_WINDOW_SECONDS:
        attempts.popleft()


def _prune_login_attempt_registry(now):
    """Remove expired least-recently-used keys before adding another attempt.

    The registry is ordered by access. Once its oldest key still has a live
    attempt, every later key was touched more recently and can be left alone.
    """
    while login_attempts:
        oldest_key, oldest_attempts = next(iter(login_attempts.items()))
        _prune_login_attempts(oldest_attempts, now)
        if oldest_attempts:
            break
        login_attempts.popitem(last=False)


def _login_retry_after(key):
    now = time.monotonic()
    with login_attempt_lock:
        attempts = login_attempts.get(key)
        if attempts is None:
            return 0
        _prune_login_attempts(attempts, now)
        if not attempts:
            login_attempts.pop(key, None)
            return 0
        login_attempts.move_to_end(key)
        if len(attempts) < LOGIN_ATTEMPT_LIMIT:
            return 0
        return max(1, int(LOGIN_ATTEMPT_WINDOW_SECONDS - (now - attempts[0])) + 1)


def _record_failed_login(key):
    now = time.monotonic()
    with login_attempt_lock:
        _prune_login_attempt_registry(now)
        attempts = login_attempts.get(key)
        if attempts is None:
            attempts = deque()
        else:
            _prune_login_attempts(attempts, now)
        attempts.append(now)
        login_attempts[key] = attempts
        login_attempts.move_to_end(key)

        while len(login_attempts) > LOGIN_ATTEMPT_MAX_KEYS:
            login_attempts.popitem(last=False)


def _clear_login_attempts(key):
    with login_attempt_lock:
        login_attempts.pop(key, None)


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(self), microphone=(self), geolocation=()",
    )
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")

    csrf_token = session.get("mannkidhun_csrf_token")
    if not isinstance(csrf_token, str) or not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        session["mannkidhun_csrf_token"] = csrf_token
    response.set_cookie(
        "mannkidhun_csrf",
        csrf_token,
        httponly=False,
        secure=bool(app.config.get("SESSION_COOKIE_SECURE")),
        samesite="Lax",
        path="/",
        max_age=int(app.permanent_session_lifetime.total_seconds()),
    )
    return response


PROFILE_IMAGE_MAX_BYTES = 2 * 1024 * 1024
PROFILE_IMAGE_MAX_DIMENSION = 4096
PROFILE_IMAGE_MAX_PIXELS = 16_000_000
labels = np.load(BASE_DIR / "model" / "labels.npy", allow_pickle=False)
holistic = None
face_detector = None
inference_lock = threading.Lock()
assistant_rate_lock = threading.Lock()
ASSISTANT_RATE_LIMIT = 12
ASSISTANT_RATE_LIMIT_WINDOW_SECONDS = 60
ASSISTANT_RATE_LIMIT_MAX_KEYS = 10_000
assistant_requests = OrderedDict()


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
            "music_dna_enabled INTEGER NOT NULL DEFAULT 0,"
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE"
            ")"
        )
        preference_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(user_preferences)").fetchall()
        }
        if "music_dna_enabled" not in preference_columns:
            connection.execute(
                "ALTER TABLE user_preferences ADD COLUMN music_dna_enabled INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_mood_journal_user_created "
            "ON mood_journal_entries(user_id, created_at DESC)"
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
run_migrations(AUTH_DATABASE)

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

    if holistic is None or face_detector is None:
        import mediapipe as mp

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


@app.route("/playlists/<int:playlist_id>")
def shared_playlist_page(playlist_id):
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
        "community",
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
    attempt_key = _login_attempt_key(identifier)
    retry_after = _login_retry_after(attempt_key)
    if retry_after:
        return (
            jsonify({"error": "Too many failed sign-in attempts. Please try again later."}),
            429,
            {"Retry-After": str(retry_after)},
        )

    user = get_user_by_identifier(identifier)
    if user is None or not check_password_hash(user["password_hash"], password):
        _record_failed_login(attempt_key)
        return jsonify({"error": "The email or password you entered is incorrect."}), 401

    _clear_login_attempts(attempt_key)
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
            "SELECT preferred_languages, preferred_genres, preferred_listening_styles, favourite_artists, music_dna_enabled FROM user_preferences WHERE user_id = ?",
            (user["id"],),
        ).fetchone()

    if preference_row is None:
        preference_row = {
            "preferred_languages": "[]",
            "preferred_genres": "[]",
            "preferred_listening_styles": "[]",
            "favourite_artists": "[]",
            "music_dna_enabled": 0,
        }

    if request.method == "GET":
        return jsonify({
            "preferred_languages": _normalize_list_field(preference_row["preferred_languages"]),
            "preferred_genres": _normalize_list_field(preference_row["preferred_genres"]),
            "preferred_listening_styles": _normalize_list_field(preference_row["preferred_listening_styles"]),
            "favourite_artists": _normalize_list_field(preference_row["favourite_artists"]),
            "music_dna_enabled": bool(preference_row["music_dna_enabled"]),
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
    if "music_dna_enabled" in payload:
        music_dna_enabled = payload["music_dna_enabled"]
        if type(music_dna_enabled) is not bool:
            return jsonify({"error": "Music DNA consent must be true or false."}), 400
    else:
        with closing(_connect_database(AUTH_DATABASE)) as connection:
            existing_consent = connection.execute(
                "SELECT music_dna_enabled FROM user_preferences WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
        music_dna_enabled = bool(existing_consent[0]) if existing_consent else False
    if onboarding_completed is None:
        onboarding_completed = payload.get("onboarding_completed")

    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.execute(
            "INSERT INTO user_preferences (user_id, preferred_languages, preferred_genres, preferred_listening_styles, favourite_artists, music_dna_enabled, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET preferred_languages = excluded.preferred_languages, preferred_genres = excluded.preferred_genres, preferred_listening_styles = excluded.preferred_listening_styles, favourite_artists = excluded.favourite_artists, music_dna_enabled = excluded.music_dna_enabled, updated_at = excluded.updated_at",
            (
                user["id"],
                _json_dumps(preferred_languages),
                _json_dumps(preferred_genres),
                _json_dumps(preferred_listening_styles),
                _json_dumps(favourite_artists),
                int(music_dna_enabled),
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
        "music_dna_enabled": music_dna_enabled,
        "onboarding_completed": bool(_coerce_bool(onboarding_completed)) if onboarding_completed is not None else bool(user["onboarding_completed"]),
    })


@app.route("/api/v1/users/me/music-dna", methods=["GET", "DELETE"])
def user_music_dna():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to view your Music DNA."}), 401

    if request.method == "DELETE":
        with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
            connection.execute(
                """
                DELETE FROM user_song_interactions
                WHERE user_id = ?
                  AND interaction_type IN ('like', 'skip', 'listen', 'play', 'complete', 'save')
                """,
                (user["id"],),
            )
            connection.execute(
                "DELETE FROM recommendation_events WHERE user_id = ?",
                (user["id"],),
            )
            connection.execute(
                "UPDATE user_preferences SET music_dna_enabled = 0, updated_at = ? WHERE user_id = ?",
                (_sqlite_now(), user["id"]),
            )
        return jsonify({
            "reset": True,
            "music_dna_enabled": False,
            "saved_songs_preserved": True,
            "preferences_preserved": True,
        })

    with closing(_connect_database(AUTH_DATABASE)) as connection:
        preference = connection.execute(
            "SELECT preferred_languages, preferred_genres, preferred_listening_styles, favourite_artists, music_dna_enabled "
            "FROM user_preferences WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        if preference is None or not bool(preference[4]):
            return jsonify({"enabled": False, "message": "Enable Music DNA in your preferences to build a private profile."})

        def top_values(query):
            rows = connection.execute(query, (user["id"],)).fetchall()
            return [{"name": row[0], "score": float(row[1] or 0), "interactions": int(row[2] or 0)} for row in rows]

        top_languages = top_values(
            """
            SELECT s.language,
                   SUM(CASE WHEN usi.interaction_type IN ('like','save','complete') THEN 2.0
                            WHEN usi.interaction_type IN ('play','listen') THEN 1.0
                            WHEN usi.interaction_type = 'skip' THEN -1.0 ELSE 0.0 END) AS score,
                   COUNT(*) AS interactions
            FROM user_song_interactions usi
            JOIN songs s ON s.id = usi.song_id
            WHERE usi.user_id = ? AND s.language IS NOT NULL AND s.language != ''
              AND usi.interaction_type IN ('like','save','complete','play','listen','skip')
            GROUP BY s.language HAVING score > 0
            ORDER BY score DESC, interactions DESC LIMIT 5
            """
        )
        top_genres = top_values(
            """
            SELECT s.genre,
                   SUM(CASE WHEN usi.interaction_type IN ('like','save','complete') THEN 2.0
                            WHEN usi.interaction_type IN ('play','listen') THEN 1.0
                            WHEN usi.interaction_type = 'skip' THEN -1.0 ELSE 0.0 END) AS score,
                   COUNT(*) AS interactions
            FROM user_song_interactions usi
            JOIN songs s ON s.id = usi.song_id
            WHERE usi.user_id = ? AND s.genre IS NOT NULL AND s.genre != ''
              AND usi.interaction_type IN ('like','save','complete','play','listen','skip')
            GROUP BY s.genre HAVING score > 0
            ORDER BY score DESC, interactions DESC LIMIT 5
            """
        )
        top_artists = top_values(
            """
            SELECT a.name,
                   SUM(CASE WHEN usi.interaction_type IN ('like','save','complete') THEN 2.0
                            WHEN usi.interaction_type IN ('play','listen') THEN 1.0
                            WHEN usi.interaction_type = 'skip' THEN -1.0 ELSE 0.0 END) AS score,
                   COUNT(*) AS interactions
            FROM user_song_interactions usi
            JOIN songs s ON s.id = usi.song_id
            JOIN artists a ON a.id = s.artist_id
            WHERE usi.user_id = ?
              AND usi.interaction_type IN ('like','save','complete','play','listen','skip')
            GROUP BY a.id, a.name HAVING score > 0
            ORDER BY score DESC, interactions DESC LIMIT 5
            """
        )
        top_tags = top_values(
            """
            SELECT st.tag,
                   SUM(CASE WHEN usi.interaction_type IN ('like','save','complete') THEN 2.0
                            WHEN usi.interaction_type IN ('play','listen') THEN 1.0
                            WHEN usi.interaction_type = 'skip' THEN -1.0 ELSE 0.0 END) AS score,
                   COUNT(*) AS interactions
            FROM user_song_interactions usi
            JOIN song_tags st ON st.song_id = usi.song_id
            WHERE usi.user_id = ? AND st.tag NOT LIKE 'vibe:%'
              AND usi.interaction_type IN ('like','save','complete','play','listen','skip')
            GROUP BY st.tag HAVING score > 0
            ORDER BY score DESC, interactions DESC LIMIT 6
            """
        )
        top_vibes = top_values(
            """
            SELECT SUBSTR(st.tag, 6) AS vibe,
                   SUM(CASE WHEN usi.interaction_type IN ('like','save','complete') THEN 2.0
                            WHEN usi.interaction_type IN ('play','listen') THEN 1.0
                            WHEN usi.interaction_type = 'skip' THEN -1.0 ELSE 0.0 END) AS score,
                   COUNT(*) AS interactions
            FROM user_song_interactions usi
            JOIN song_tags st ON st.song_id = usi.song_id
            WHERE usi.user_id = ? AND st.tag LIKE 'vibe:%'
              AND usi.interaction_type IN ('like','save','complete','play','listen','skip')
            GROUP BY st.tag HAVING score > 0
            ORDER BY score DESC, interactions DESC LIMIT 5
            """
        )
        summary = connection.execute(
            """
            SELECT
                SUM(CASE WHEN interaction_type IN ('play','listen','complete') THEN 1 ELSE 0 END),
                SUM(CASE WHEN interaction_type = 'like' THEN 1 ELSE 0 END),
                SUM(CASE WHEN interaction_type = 'skip' THEN 1 ELSE 0 END),
                COUNT(*)
            FROM user_song_interactions WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()

    return jsonify({
        "enabled": True,
        "top_languages": top_languages,
        "top_genres": top_genres,
        "top_artists": top_artists,
        "top_tags": top_tags,
        "top_vibes": top_vibes,
        "summary": {
            "plays": int(summary[0] or 0),
            "likes": int(summary[1] or 0),
            "skips": int(summary[2] or 0),
            "interactions": int(summary[3] or 0),
        },
        "preferences": {
            "languages": _normalize_list_field(preference[0]),
            "genres": _normalize_list_field(preference[1]),
            "listening_styles": _normalize_list_field(preference[2]),
            "artists": _normalize_list_field(preference[3]),
        },
    })


@app.route("/api/v1/users/me/music-dna/consent", methods=["POST"])
def set_music_dna_consent():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to manage Music DNA."}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or type(payload.get("enabled")) is not bool:
        return jsonify({"error": "Provide an enabled boolean."}), 400
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        connection.execute(
            """
            INSERT INTO user_preferences (user_id, music_dna_enabled, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                music_dna_enabled = excluded.music_dna_enabled,
                updated_at = excluded.updated_at
            """,
            (user["id"], int(payload["enabled"]), _sqlite_now()),
        )
    return jsonify({"enabled": payload["enabled"]})


@app.route("/api/v1/users/me/mood-journal", methods=["GET", "POST"])
def mood_journal():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to use your mood journal."}), 401

    if request.method == "GET":
        with closing(_connect_database(AUTH_DATABASE)) as connection:
            rows = connection.execute(
                "SELECT id, mood, note, created_at FROM mood_journal_entries "
                "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 30",
                (user["id"],),
            ).fetchall()
            mood_summary_rows = connection.execute(
                """
                SELECT mood, COUNT(*) AS total
                FROM (
                    SELECT mood FROM mood_journal_entries
                    WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 30
                )
                GROUP BY mood
                ORDER BY total DESC, mood
                """,
                (user["id"],),
            ).fetchall()
        return jsonify({
            "mood_summary": [
                {"mood": row[0], "entries": int(row[1])}
                for row in mood_summary_rows
            ],
            "entries": [
                {"id": row[0], "mood": row[1], "note": row[2], "created_at": row[3]}
                for row in rows
            ]
        })

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide a journal entry in JSON format."}), 400
    mood = payload.get("mood")
    note = payload.get("note", "")
    allowed_moods = {"happy", "sad", "angry", "neutral", "surprise", "romantic", "relaxed", "energetic", "motivational", "focused", "devotional"}
    if not isinstance(mood, str) or mood.strip().lower() not in allowed_moods:
        return jsonify({"error": "Choose a supported mood before saving."}), 400
    if not isinstance(note, str) or len(note) > 500:
        return jsonify({"error": "Journal notes must be 500 characters or fewer."}), 400
    note = note.strip()
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO mood_journal_entries (user_id, mood, note, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], mood.strip().lower(), note, _sqlite_now()),
        )
        entry_id = cursor.lastrowid
    return jsonify({
        "entry": {"id": entry_id, "mood": mood.strip().lower(), "note": note, "created_at": _sqlite_now()}
    }), 201


@app.route("/api/v1/users/me/mood-journal/<int:entry_id>", methods=["DELETE"])
def mood_journal_entry_delete(entry_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to use your mood journal."}), 401
    with closing(_connect_database(AUTH_DATABASE)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM mood_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, user["id"]),
        )
    if cursor.rowcount == 0:
        return jsonify({"error": "Journal entry not found."}), 404
    return jsonify({"deleted": True, "id": entry_id})


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


def _is_api_request():
    return request.path.startswith("/api/") or request.path == "/predict"


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Keep HTTP errors JSON-shaped for API callers without changing page errors."""
    if _is_api_request():
        return jsonify({"error": error.description or error.name}), error.code
    return error


@app.errorhandler(Exception)
def handle_unexpected_exception(error):
    """Log server-side details while returning a safe response to API clients."""
    if isinstance(error, HTTPException):
        return handle_http_exception(error)

    app.logger.exception("Unhandled application error for %s", request.path)
    if _is_api_request():
        return jsonify({"error": "An unexpected server error occurred. Please try again."}), 500
    return "Internal Server Error", 500


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


def _prune_assistant_requests(requests, now):
    while requests and now - requests[0] >= ASSISTANT_RATE_LIMIT_WINDOW_SECONDS:
        requests.popleft()


def _prune_assistant_request_registry(now):
    """Drop expired least-recently-used account buckets."""
    while assistant_requests:
        oldest_user_id, oldest_requests = next(iter(assistant_requests.items()))
        _prune_assistant_requests(oldest_requests, now)
        if oldest_requests:
            break
        assistant_requests.popitem(last=False)


def _assistant_rate_limited(user_id):
    now = time.monotonic()
    with assistant_rate_lock:
        _prune_assistant_request_registry(now)
        requests = assistant_requests.get(user_id)
        if requests is None:
            requests = deque()
        else:
            _prune_assistant_requests(requests, now)

        if len(requests) >= ASSISTANT_RATE_LIMIT:
            assistant_requests.move_to_end(user_id)
            return True

        requests.append(now)
        assistant_requests[user_id] = requests
        assistant_requests.move_to_end(user_id)
        while len(assistant_requests) > ASSISTANT_RATE_LIMIT_MAX_KEYS:
            assistant_requests.popitem(last=False)
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
    mode = payload.get("mode", "match")
    target_mood = payload.get("target_mood")
    allowed_moods = {"happy", "sad", "angry", "neutral", "surprise", "romantic", "relaxed", "energetic", "motivational", "focused", "devotional"}
    if not isinstance(mode, str) or mode not in {"match", "change", "explore"}:
        return jsonify({"error": "Choose Match, Change, or Explore mode."}), 400
    if target_mood is not None and (
        not isinstance(target_mood, str) or target_mood.strip().lower() not in allowed_moods
    ):
        return jsonify({"error": "Choose a supported target mood."}), 400
    current_mood = payload.get("current_mood")
    if current_mood is not None and (
        not isinstance(current_mood, str) or current_mood.strip().lower() not in allowed_moods
    ):
        return jsonify({"error": "Choose a supported current mood."}), 400

    requested_context = payload.get("context")
    if requested_context == "":
        requested_context = None
    if requested_context is not None and (
        not isinstance(requested_context, str)
        or requested_context.strip().lower() not in ALLOWED_LISTENING_CONTEXTS
    ):
        return jsonify({"error": "Choose a supported listening context."}), 400
    context = (
        requested_context.strip().lower()
        if requested_context is not None
        else intent.get("context")
    )
    if context not in ALLOWED_LISTENING_CONTEXTS:
        context = None
    intent["context"] = context

    if mode == "change":
        vibe = (target_mood or intent["mood"] or "").strip().lower()
        if not vibe:
            return jsonify({"error": "Choose the mood you want to move toward."}), 400
    elif mode == "explore":
        vibe = "neutral"
    else:
        vibe = intent["mood"] or (current_mood.strip().lower() if current_mood else None) or CONTEXT_VIBE_FALLBACK.get(context, "neutral")

    query_filters = {
        key: intent[key] for key in ("genre", "language", "artist") if intent[key]
    }
    if mode == "match" and (intent["mood"] or current_mood):
        query_filters["vibe"] = vibe
    if mode == "change":
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
        context=context,
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
            context=context,
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
            "mode": mode,
            "context": context,
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
        allowed_events = {"like", "skip", "listen", "play", "complete", "save"}
        if not isinstance(event_type, str) or event_type.strip().lower() not in allowed_events:
            return jsonify({"error": "Choose a supported interaction type."}), 400
        event_type = event_type.strip().lower()
        source = payload.get("source") or payload.get("context") or "library"
        if not isinstance(source, str) or len(source) > 60:
            return jsonify({"error": "Interaction source must be 60 characters or fewer."}), 400
        position_ms = payload.get("position_ms", 0)
        duration_ms = payload.get("duration_ms", 0)
        try:
            position_ms = int(position_ms)
            duration_ms = int(duration_ms)
        except (TypeError, ValueError, OverflowError):
            return jsonify({"error": "Playback positions must be valid non-negative integers."}), 400
        if position_ms < 0 or duration_ms < 0:
            return jsonify({"error": "Playback positions cannot be negative."}), 400
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


@app.route("/api/v1/playlists/<int:playlist_id>/invites", methods=["POST"])
def playlist_invite_create(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to invite collaborators."}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide invitation options."}), 400
    role = payload.get("role", "editor")
    if not isinstance(role, str) or role not in {"viewer", "editor"}:
        return jsonify({"error": "Invite role must be viewer or editor."}), 400
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        created = create_playlist_invite(
            str(AUTH_DATABASE), user["id"], playlist_id, token_hash, role=role, expires_at=expires_at
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not created:
        return jsonify({"error": "Only the playlist owner can invite collaborators."}), 403
    invite_url = request.host_url.rstrip("/") + (
        f"/assistant?invite_playlist={playlist_id}&invite_token={token}"
    )
    return jsonify({"invite_url": invite_url, "role": role, "expires_at": expires_at}), 201


@app.route("/api/v1/playlists/<int:playlist_id>/invites/accept", methods=["POST"])
def playlist_invite_accept(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to accept a playlist invitation."}), 401
    payload = request.get_json(silent=True)
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not 20 <= len(token) <= 200:
        return jsonify({"error": "Provide a valid invitation token."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    playlist = accept_playlist_invite(
        str(AUTH_DATABASE), user["id"], playlist_id, token_hash, _sqlite_now()
    )
    if playlist is None:
        return jsonify({"error": "This invitation is invalid, expired, or revoked."}), 404
    return jsonify({"playlist": playlist})


@app.route(
    "/api/v1/playlists/<int:playlist_id>/collaborators/<int:collaborator_user_id>",
    methods=["PUT", "DELETE"],
)
def playlist_collaborator_detail(playlist_id, collaborator_user_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to manage collaborators."}), 401
    if request.method == "DELETE":
        removed = remove_playlist_collaborator(
            str(AUTH_DATABASE), user["id"], playlist_id, collaborator_user_id
        )
        if not removed:
            return jsonify({"error": "Collaborator not found or you are not the owner."}), 404
        return jsonify({"removed": True, "user_id": collaborator_user_id})

    payload = request.get_json(silent=True)
    role = payload.get("role") if isinstance(payload, dict) else None
    if not isinstance(role, str) or role not in {"viewer", "editor"}:
        return jsonify({"error": "Role must be viewer or editor."}), 400
    try:
        updated = update_playlist_collaborator(
            str(AUTH_DATABASE), user["id"], playlist_id, collaborator_user_id, role
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not updated:
        return jsonify({"error": "Collaborator not found or you are not the owner."}), 404
    return jsonify({"user_id": collaborator_user_id, "role": role})


@app.route("/api/v1/playlists/<int:playlist_id>/invites", methods=["DELETE"])
def playlist_invites_revoke(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to revoke invitations."}), 401
    revoked = revoke_playlist_invites(
        str(AUTH_DATABASE), user["id"], playlist_id, _sqlite_now()
    )
    if revoked == 0:
        return jsonify({"error": "No active invitations found for this playlist."}), 404
    return jsonify({"revoked": revoked})


@app.route("/api/v1/playlists/<int:playlist_id>/collaborators", methods=["GET"])
def playlist_collaborators(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to view collaborators."}), 401
    collaborators = get_playlist_collaborators(
        str(AUTH_DATABASE), user["id"], playlist_id
    )
    if collaborators is None:
        return jsonify({"error": "Only the playlist owner can view the collaborator list."}), 403
    return jsonify({"collaborators": collaborators})


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


MOOD_AFFECT_MAP = {
    "happy": (0.85, 0.75),
    "sad": (0.20, -0.85),
    "angry": (0.95, -0.65),
    "neutral": (0.45, 0.0),
    "surprise": (0.90, 0.35),
    "romantic": (0.45, 0.55),
    "relaxed": (0.20, 0.30),
    "energetic": (1.0, 0.55),
    "motivational": (0.90, 0.45),
    "focused": (0.20, 0.15),
    "devotional": (0.15, 0.40),
}


def build_mood_transition_path(source_mood, target_mood):
    """Choose a transparent bridge mood using catalogue mood coordinates."""
    source = source_mood if source_mood in MOOD_AFFECT_MAP else "neutral"
    target = target_mood if target_mood in MOOD_AFFECT_MAP else "neutral"
    if source == target:
        return [source, target]
    start, end = MOOD_AFFECT_MAP[source], MOOD_AFFECT_MAP[target]
    midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    candidates = [mood for mood in MOOD_AFFECT_MAP if mood not in {source, target}]
    bridge = min(
        candidates,
        key=lambda mood: (
            (MOOD_AFFECT_MAP[mood][0] - midpoint[0]) ** 2
            + (MOOD_AFFECT_MAP[mood][1] - midpoint[1]) ** 2
        ),
    )
    return [source, bridge, target]


@app.route("/api/v1/users/me/adaptive-session", methods=["POST"])
def create_adaptive_session():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to create a listening session."}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide adaptive session options in JSON format."}), 400

    mode = payload.get("mode", "match")
    mood = payload.get("mood")
    source_mood = payload.get("source_mood", "neutral")
    use_preferences = payload.get("use_preferences", True)
    use_history = payload.get("use_history", False)
    if not isinstance(mode, str) or mode not in {"match", "change", "explore"}:
        return jsonify({"error": "Choose Match, Change, or Explore mode."}), 400
    allowed_moods = {"happy", "sad", "angry", "neutral", "surprise", "romantic", "relaxed", "energetic", "motivational", "focused", "devotional"}
    if mood is not None and (
        not isinstance(mood, str) or mood.strip().lower() not in allowed_moods
    ):
        return jsonify({"error": "Choose a supported mood."}), 400
    if mode == "change" and not mood:
        return jsonify({"error": "Choose a target mood for Change mode."}), 400
    if mode == "change" and (
        not isinstance(source_mood, str) or source_mood.strip().lower() not in allowed_moods
    ):
        return jsonify({"error": "Choose a supported starting mood for Change mode."}), 400
    if isinstance(source_mood, str):
        source_mood = source_mood.strip().lower()
    context = payload.get("context")
    if context == "":
        context = None
    if context is not None and (
        not isinstance(context, str)
        or context.strip().lower() not in ALLOWED_LISTENING_CONTEXTS
    ):
        return jsonify({"error": "Choose a supported listening context."}), 400
    if context is not None:
        context = context.strip().lower()
    if type(use_preferences) is not bool or type(use_history) is not bool:
        return jsonify({"error": "Personalisation choices must be true or false."}), 400
    limit = payload.get("limit", 8)
    try:
        limit = max(3, min(int(limit), 12))
    except (TypeError, ValueError):
        return jsonify({"error": "Session size must be between 3 and 12 tracks."}), 400

    vibe = (
        "neutral"
        if mode == "explore"
        else (mood or CONTEXT_VIBE_FALLBACK.get(context, "neutral"))
    )
    query_filters = {"vibe": vibe} if mode != "explore" and mood else None
    journey = []
    recommendations = []
    if mode == "change":
        transition_path = build_mood_transition_path(source_mood, vibe)
        stage_count = len(transition_path)
        base_count, remainder = divmod(limit, stage_count)
        seen_ids = set()
        for stage_index, stage_mood in enumerate(transition_path):
            stage_limit = max(1, base_count + (1 if stage_index < remainder else 0))
            stage_tracks = get_user_recommendations(
                str(AUTH_DATABASE),
                user_id=user["id"],
                mood=stage_mood,
                vibe=stage_mood,
                limit=stage_limit + 2,
                include_preferences=use_preferences,
                include_history=use_history,
                query_filters={"vibe": stage_mood},
                context=context,
                exclude_song_ids=seen_ids,
            )
            if not stage_tracks:
                stage_tracks = get_user_recommendations(
                    str(AUTH_DATABASE),
                    user_id=user["id"],
                    mood=stage_mood,
                    vibe=stage_mood,
                    limit=stage_limit,
                    include_preferences=use_preferences,
                    include_history=use_history,
                    context=context,
                    exclude_song_ids=seen_ids,
                )
            stage_tracks = stage_tracks[:stage_limit]
            journey.append({
                "step": stage_index + 1,
                "mood": stage_mood,
                "label": "Starting point" if stage_index == 0 else (
                    "Destination" if stage_index == stage_count - 1 else "Bridge"
                ),
                "track_count": len(stage_tracks),
            })
            for track in stage_tracks:
                track["journey_stage"] = stage_index + 1
                track["journey_mood"] = stage_mood
                track["journey_path"] = transition_path
                track["explanation"] = (
                    f"Journey step {stage_index + 1}: {stage_mood.title()} "
                    f"on your way from {source_mood.title()} to {vibe.title()}. "
                    + str(track.get("explanation") or "")
                ).strip()
                seen_ids.add(str(track["id"]))
                recommendations.append(track)
    else:
        recommendations = get_user_recommendations(
            str(AUTH_DATABASE),
            user_id=user["id"],
            mood=vibe,
            vibe=vibe,
            limit=limit,
            include_preferences=use_preferences,
            include_history=use_history,
            query_filters=query_filters,
            context=context,
        )
        if not recommendations:
            recommendations = get_user_recommendations(
                str(AUTH_DATABASE),
                user_id=user["id"],
                mood=vibe,
                vibe=vibe,
                limit=limit,
                include_preferences=use_preferences,
                include_history=use_history,
                context=context,
            )
    recommendations = recommendations[:limit]
    queue = [int(track["id"]) for track in recommendations if isinstance(track.get("id"), int)]
    state = save_playback_state(
        str(AUTH_DATABASE),
        user["id"],
        {"current_song_id": queue[0] if queue else None, "position_ms": 0, "queue": queue, "shuffle": False, "repeat_mode": "off"},
    )
    return jsonify({
        "mode": mode,
        "mood": vibe,
        "source_mood": source_mood if mode == "change" else None,
        "context": context,
        "journey": journey,
        "recommendations": recommendations,
        "state": state,
        "message": (
            "Your gradual mood journey is ready." if mode == "change"
            else "Your session is ready. Feedback can adapt the queue while you listen."
        ),
    })


@app.route("/api/v1/users/me/adaptive-session/feedback", methods=["POST"])
def adaptive_session_feedback():
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to adapt your listening session."}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide session feedback in JSON format."}), 400

    try:
        song_id = int(payload.get("song_id"))
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Provide a valid track id."}), 400
    if song_id <= 0:
        return jsonify({"error": "Provide a valid track id."}), 400

    event_type = payload.get("event_type")
    if not isinstance(event_type, str) or event_type not in {"like", "skip"}:
        return jsonify({"error": "Session feedback must be like or skip."}), 400

    queue = payload.get("queue", [])
    played_ids = payload.get("played_ids", [])
    if (
        not isinstance(queue, list) or len(queue) > 50
        or not isinstance(played_ids, list) or len(played_ids) > 50
    ):
        return jsonify({"error": "Session track lists must be arrays of up to 50 ids."}), 400
    try:
        queue_ids = [
            int(item.get("id") if isinstance(item, dict) else item)
            for item in queue
        ]
        played = {int(item) for item in played_ids}
        position_ms = int(payload.get("position_ms", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Track ids and playback position must be integers."}), 400
    if position_ms < 0 or len(set(queue_ids)) != len(queue_ids):
        return jsonify({"error": "The session queue or playback position is invalid."}), 400
    if song_id not in queue_ids:
        return jsonify({"error": "That track is not part of the active session."}), 409

    mood = payload.get("mood", "neutral")
    mode = payload.get("mode", "match")
    context = payload.get("context")
    use_preferences = payload.get("use_preferences", True)
    use_history = payload.get("use_history", False)
    if not isinstance(mood, str) or mood.strip().lower() not in MOOD_AFFECT_MAP:
        return jsonify({"error": "Choose a supported session mood."}), 400
    mood = mood.strip().lower()
    if not isinstance(mode, str) or mode not in {"match", "change", "explore"}:
        return jsonify({"error": "Choose Match, Change, or Explore mode."}), 400
    if type(use_preferences) is not bool or type(use_history) is not bool:
        return jsonify({"error": "Personalisation choices must be true or false."}), 400
    if context == "":
        context = None
    if context is not None:
        if not isinstance(context, str) or context.strip().lower() not in ALLOWED_LISTENING_CONTEXTS:
            return jsonify({"error": "Choose a supported listening context."}), 400
        context = context.strip().lower()

    if not record_user_interaction(
        str(AUTH_DATABASE), user["id"], song_id, event_type, source="adaptive-session"
    ):
        return jsonify({"error": "Could not save your session feedback."}), 400

    current_index = queue_ids.index(song_id)
    remaining_ids = [
        item for item in queue_ids[current_index + 1:]
        if item not in played and item != song_id
    ]
    excluded_ids = played | {song_id}
    recommendations = get_user_recommendations(
        str(AUTH_DATABASE),
        user_id=user["id"],
        mood=None if mode == "explore" else mood,
        vibe="neutral" if mode == "explore" else mood,
        limit=12,
        include_preferences=use_preferences,
        include_history=use_history,
        context=context,
        exclude_song_ids=excluded_ids,
    )
    by_id = {
        int(item["id"]): item
        for item in recommendations
        if item.get("id") is not None
    }
    refreshed = [by_id[item] for item in remaining_ids if item in by_id]
    used = {int(item["id"]) for item in refreshed}
    refreshed.extend(
        item for item in recommendations
        if int(item["id"]) not in used and int(item["id"]) not in excluded_ids
    )
    refreshed = refreshed[:12]
    state = save_playback_state(
        str(AUTH_DATABASE),
        user["id"],
        {
            "current_song_id": song_id,
            "position_ms": position_ms,
            "queue": [song_id] + [int(item["id"]) for item in refreshed],
            "shuffle": False,
            "repeat_mode": "off",
        },
    )
    return jsonify({
        "status": "ok",
        "interaction": event_type,
        "remaining": refreshed,
        "state": state,
        "message": "Your remaining queue was refreshed using your latest feedback.",
    })

@app.route("/api/v1/playlists/<int:playlist_id>/refine", methods=["POST"])
def refine_playlist(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to refine playlists."}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Provide a playlist refinement instruction."}), 400
    instruction = payload.get("instruction")
    if not isinstance(instruction, str) or not 3 <= len(instruction.strip()) <= 200:
        return jsonify({"error": "Enter a refinement instruction between 3 and 200 characters."}), 400

    playlist = get_playlist_details(str(AUTH_DATABASE), playlist_id, user_id=user["id"])
    if playlist is None:
        return jsonify({"error": "Playlist not found."}), 404

    command = instruction.strip()
    normalized = command.casefold()
    track_list = playlist["tracks"]

    remove_command = any(term in normalized for term in ("remove ", "delete ", "take out ", "drop "))
    if remove_command:
        if any(term in normalized for term in ("last song", "last track", "most recent")):
            target = track_list[-1] if track_list else None
        else:
            target = next(
                (
                    track for track in track_list
                    if str(track.get("title") or "").casefold() in normalized
                ),
                None,
            )
        if target is None:
            return jsonify({"error": "I couldn't identify a track to remove. Name a song or say 'remove last song'."}), 400
        removed = remove_song_from_playlist(
            str(AUTH_DATABASE), user["id"], playlist_id, int(target["id"])
        )
        if not removed:
            return jsonify({"error": "That track could not be removed from this playlist."}), 409
        updated_playlist = get_playlist_details(str(AUTH_DATABASE), playlist_id, user_id=user["id"])
        return jsonify({
            "playlist": updated_playlist,
            "removed": [target],
            "removed_count": 1,
            "added": [],
            "added_count": 0,
            "reordered": False,
        })

    move_command = any(term in normalized for term in ("move ", "put ", "place ", "bring ")) and any(
        term in normalized for term in ("first", "top", "beginning", "start", "last", "bottom", "end")
    )
    if move_command:
        target = next(
            (
                track for track in track_list
                if str(track.get("title") or "").casefold() in normalized
            ),
            None,
        )
        if target is None:
            return jsonify({"error": "I couldn't identify a track to move. Include its exact title."}), 400
        ordered_ids = [int(track["id"]) for track in track_list if int(track["id"]) != int(target["id"])]
        if any(term in normalized for term in ("last", "bottom", "end")):
            ordered_ids.append(int(target["id"]))
        else:
            ordered_ids.insert(0, int(target["id"]))
        updated_playlist = reorder_playlist_tracks(
            str(AUTH_DATABASE), user["id"], playlist_id, ordered_ids
        )
        return jsonify({
            "playlist": updated_playlist,
            "added": [],
            "added_count": 0,
            "removed": [],
            "removed_count": 0,
            "reordered": True,
            "moved_track": target,
        })

    with closing(_connect_database(AUTH_DATABASE)) as connection:
        known_artists = [
            row[0] for row in connection.execute(
                "SELECT name FROM artists ORDER BY LENGTH(name) DESC, name"
            ).fetchall()
        ]
    intent, intent_provider = extract_music_intent(command, known_artists)
    calmer_terms = ("calmer", "calm down", "more calm", "softer", "more peaceful", "less intense", "less energetic")
    energetic_terms = ("more energetic", "more upbeat", "more lively", "higher energy")
    variety_terms = ("new artists", "different artists", "more variety", "discover artists")
    if any(term in normalized for term in calmer_terms):
        intent["mood"] = "relaxed"
    elif any(term in normalized for term in energetic_terms):
        intent["mood"] = "energetic"
    if any(term in normalized for term in variety_terms):
        intent["artist"] = None
    context_vibes = {"studying": "focused", "travelling": "energetic", "evening": "relaxed", "workout": "energetic", "sleep": "relaxed"}
    vibe = intent["mood"] or context_vibes.get(intent["context"], "neutral")
    filters = {key: intent[key] for key in ("genre", "language", "artist") if intent.get(key)}
    if intent["mood"]:
        filters["vibe"] = vibe
    recommendations = get_user_recommendations(
        str(AUTH_DATABASE),
        user_id=user["id"],
        mood=vibe,
        vibe=vibe,
        limit=12,
        include_preferences=True,
        include_history=False,
        query_filters=filters,
    )
    if not recommendations and filters:
        recommendations = get_user_recommendations(
            str(AUTH_DATABASE), user_id=user["id"], mood=vibe, vibe=vibe,
            limit=12, include_preferences=True, include_history=False,
        )

    existing_ids = {int(track["id"]) for track in track_list}
    existing_artists = {str(track.get("artist") or "").casefold() for track in track_list}
    prefer_new_artists = any(term in normalized for term in ("new artists", "different artists", "more variety", "discover artists"))
    additions = []
    for track in recommendations:
        if len(additions) >= 5:
            break
        artist_name = str(track.get("artist") or "").casefold()
        if int(track["id"]) in existing_ids:
            continue
        if prefer_new_artists and artist_name in existing_artists:
            continue
        updated = add_song_to_playlist(str(AUTH_DATABASE), user["id"], playlist_id, int(track["id"]))
        if updated is not None:
            additions.append(track)
            existing_ids.add(int(track["id"]))
            if artist_name:
                existing_artists.add(artist_name)
    updated_playlist = get_playlist_details(str(AUTH_DATABASE), playlist_id, user_id=user["id"])
    return jsonify({
        "playlist": updated_playlist,
        "added": additions,
        "added_count": len(additions),
        "removed": [],
        "removed_count": 0,
        "reordered": False,
        "intent": intent,
        "intent_provider": intent_provider,
    })

@app.route("/api/v1/public/playlists", methods=["GET"])
def public_playlists_index():
    with closing(_connect_database(AUTH_DATABASE)) as connection:
        rows = connection.execute(
            """
            SELECT p.id, p.name, p.description, p.updated_at, u.name AS owner_name,
                   COUNT(pt.song_id) AS track_count
            FROM playlists p
            JOIN users u ON u.id = p.user_id
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            WHERE p.is_public = 1
            GROUP BY p.id
            ORDER BY p.updated_at DESC, p.id DESC
            LIMIT 30
            """
        ).fetchall()
    return jsonify({
        "playlists": [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "updated_at": row[3],
                "owner_name": row[4],
                "track_count": int(row[5] or 0),
            }
            for row in rows
        ]
    })


@app.route("/api/v1/public/playlists/<int:playlist_id>", methods=["GET"])
def public_playlist(playlist_id):
    with closing(_connect_database(AUTH_DATABASE)) as connection:
        row = connection.execute(
            "SELECT p.is_public, u.name FROM playlists p JOIN users u ON u.id = p.user_id WHERE p.id = ?",
            (playlist_id,),
        ).fetchone()
    if row is None or not bool(row[0]):
        return jsonify({"error": "This playlist is private or no longer available."}), 404
    playlist = get_playlist_details(str(AUTH_DATABASE), playlist_id)
    if playlist is None:
        return jsonify({"error": "Playlist not found."}), 404
    playlist["owner_name"] = row[1]
    return jsonify({"playlist": playlist})


@app.route("/api/v1/playlists/<int:playlist_id>/listening-room", methods=["POST"])
def listening_room_create(playlist_id):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to start a group listening room."}), 401
    playlist = get_playlist_details(str(AUTH_DATABASE), playlist_id, user_id=user["id"])
    if playlist is None or not playlist.get("is_owner"):
        return jsonify({"error": "Only the playlist owner can start a listening room."}), 403

    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    room_id = create_listening_room(
        str(AUTH_DATABASE), user["id"], playlist_id, token_hash, expires_at
    )
    if room_id is None:
        return jsonify({"error": "Could not start a room for this playlist."}), 409
    queue = [int(track["id"]) for track in playlist["tracks"]]
    room_state = {
        "current_song_id": queue[0] if queue else None,
        "position_ms": 0,
        "is_playing": False,
        "queue": queue,
        "updated_by": user["id"],
    }
    update_listening_room(
        str(AUTH_DATABASE), user["id"], token_hash, room_state, _sqlite_now()
    )
    return jsonify({
        "room_id": room_id,
        "room_token": token,
        "invite_url": request.host_url.rstrip("/") + "/assistant?room_token=" + token,
        "expires_at": expires_at,
        "playlist": {"id": playlist_id, "name": playlist["name"]},
    }), 201


@app.route("/api/v1/listening-rooms/<token>/join", methods=["POST"])
def listening_room_join(token):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to join a group listening room."}), 401
    if not isinstance(token, str) or not 24 <= len(token) <= 100:
        return jsonify({"error": "This listening-room invitation is invalid."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    room = join_listening_room(str(AUTH_DATABASE), user["id"], token_hash, _sqlite_now())
    if room is None:
        return jsonify({"error": "This room has expired or the invitation is invalid."}), 404
    # The bearer invite grants access to this room's playlist only after membership is recorded.
    playlist = get_playlist_details(str(AUTH_DATABASE), room["playlist_id"], user_id=None)
    if playlist is None:
        return jsonify({"error": "The shared playlist is no longer available."}), 404
    return jsonify({"room": room, "playlist": playlist})


@app.route("/api/v1/listening-rooms/<token>", methods=["GET", "DELETE"])
def listening_room_detail(token):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to view this listening room."}), 401
    if not isinstance(token, str) or not 24 <= len(token) <= 100:
        return jsonify({"error": "This listening-room link is invalid."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if request.method == "DELETE":
        if not close_listening_room(str(AUTH_DATABASE), user["id"], token_hash):
            return jsonify({"error": "Only the room owner can close this room."}), 403
        return jsonify({"closed": True})
    room = get_listening_room(str(AUTH_DATABASE), user["id"], token_hash, _sqlite_now())
    if room is None:
        return jsonify({"error": "Room not found or you are not a participant."}), 404
    return jsonify({"room": room})


@app.route("/api/v1/listening-rooms/<token>/state", methods=["PUT"])
def listening_room_update(token):
    user = get_authenticated_user()
    if user is None:
        return jsonify({"error": "Sign in to sync group playback."}), 401
    if not isinstance(token, str) or not 24 <= len(token) <= 100:
        return jsonify({"error": "This listening-room link is invalid."}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
        return jsonify({"error": "Provide a group playback state."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    room = get_listening_room(str(AUTH_DATABASE), user["id"], token_hash, _sqlite_now())
    if room is None:
        return jsonify({"error": "Room not found or you are not a participant."}), 404
    state = payload["state"]
    try:
        queue = [int(item) for item in state.get("queue", [])]
        current_song_id = state.get("current_song_id")
        current_song_id = int(current_song_id) if current_song_id is not None else None
        position_ms = int(state.get("position_ms", 0))
        expected_version = payload.get("expected_version")
        if expected_version is not None:
            expected_version = int(expected_version)
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Track ids, version and playback position must be integers."}), 400
    if len(queue) > 100 or len(set(queue)) != len(queue) or position_ms < 0:
        return jsonify({"error": "Group playback queue or position is invalid."}), 400
    playlist = get_playlist_details(str(AUTH_DATABASE), room["playlist_id"], user_id=None)
    if playlist is None:
        return jsonify({"error": "The shared playlist is no longer available."}), 404
    playlist_song_ids = {int(item["id"]) for item in playlist["tracks"]}
    if any(item not in playlist_song_ids for item in queue):
        return jsonify({"error": "Group playback can only use tracks in the shared playlist."}), 400
    if current_song_id is not None and current_song_id not in playlist_song_ids:
        return jsonify({"error": "The current track must belong to the shared playlist."}), 400
    room_state = {
        "current_song_id": current_song_id,
        "position_ms": min(position_ms, 24 * 60 * 60 * 1000),
        "is_playing": bool(state.get("is_playing", False)),
        "queue": queue,
        "updated_by": user["id"],
    }
    result = update_listening_room(
        str(AUTH_DATABASE),
        user["id"],
        token_hash,
        room_state,
        _sqlite_now(),
        expected_version=expected_version,
    )
    if result is None:
        return jsonify({"error": "Room membership expired."}), 404
    if result.get("conflict"):
        return jsonify({
            "error": "The room changed on another listener's device.",
            "version": result["version"],
        }), 409
    return jsonify({"room": result})


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

