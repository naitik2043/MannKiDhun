import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

MOODS = {
    "relaxed": ("relaxed", "relaxing", "calm", "peaceful", "soothing"),
    "energetic": ("energetic", "energy", "upbeat", "lively"),
    "motivational": ("motivational", "motivation", "inspiring"),
    "focused": ("focused", "focus", "studying", "study", "concentrate"),
    "romantic": ("romantic", "romance", "love"),
    "happy": ("happy", "cheerful", "bright"),
    "sad": ("sad", "melancholic", "heartbroken"),
    "devotional": ("devotional", "spiritual"),
    "neutral": ("neutral",),
}

GENRES = {
    "pop": ("pop",),
    "rock": ("rock",),
    "classical": ("classical",),
    "indie": ("indie",),
    "devotional": ("devotional",),
    "romance": ("romance", "romantic"),
    "jazz": ("jazz",),
    "electronic": ("electronic", "edm"),
}
LANGUAGES = {"hindi": "Hindi", "english": "English"}
CONTEXTS = {
    "studying": ("studying", "study", "work", "working", "focus"),
    "travelling": ("travelling", "traveling", "travel", "journey", "driving"),
    "evening": ("evening", "night"),
    "workout": ("workout", "exercise", "running", "gym"),
    "sleep": ("sleep", "bedtime"),
}
FOLLOW_UP = re.compile(r"\b(more|another|similar|like that|something else)\b", re.I)


def _contains_term(text, term):
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I) is not None


def _rule_based_intent(message, known_artists):
    text = message.lower()
    intent = {"mood": None, "genre": None, "language": None, "artist": None, "context": None}

    for mood, terms in MOODS.items():
        if any(_contains_term(text, term) for term in terms):
            intent["mood"] = mood
            break
    for genre, terms in GENRES.items():
        if any(_contains_term(text, term) for term in terms):
            intent["genre"] = genre
            break
    for language, display_name in LANGUAGES.items():
        if _contains_term(text, language):
            intent["language"] = display_name
            break
    for artist in sorted(known_artists, key=len, reverse=True):
        if artist and _contains_term(text, artist):
            intent["artist"] = artist
            break
    for context, terms in CONTEXTS.items():
        if any(_contains_term(text, term) for term in terms):
            intent["context"] = context
            break
    return intent


def _request_provider_intent(message):
    api_key = os.environ.get("AI_ASSISTANT_API_KEY", "").strip()
    if not api_key:
        return None

    endpoint = os.environ.get(
        "AI_ASSISTANT_API_URL", "https://api.openai.com/v1/chat/completions"
    ).strip()
    parsed_endpoint = urllib.parse.urlparse(endpoint)
    if parsed_endpoint.scheme != "https" and parsed_endpoint.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("The assistant provider URL must use HTTPS.")
    if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
        raise ValueError("The assistant provider URL is invalid.")

    body = json.dumps(
        {
            "model": os.environ.get("AI_ASSISTANT_MODEL", "gpt-4o-mini"),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract only music-search intent from the user's latest request. "
                        "Return JSON with nullable string fields mood, genre, language, "
                        "artist, and context. Do not write recommendations or invent tracks."
                    ),
                },
                {"role": "user", "content": message},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 120,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=4) as response:
        result = json.loads(response.read(16_384))
    content = result["choices"][0]["message"]["content"]
    intent = json.loads(content)
    if not isinstance(intent, dict):
        raise ValueError("The assistant provider returned invalid intent.")
    return intent


def extract_music_intent(message, known_artists, previous_intent=None):
    rule_intent = _rule_based_intent(message, known_artists)
    if FOLLOW_UP.search(message) and isinstance(previous_intent, dict):
        fallback_intent = {key: None for key in ("mood", "genre", "language", "artist", "context")}
        for key, allowed in (
            ("mood", MOODS),
            ("genre", GENRES),
            ("language", LANGUAGES.values()),
            ("context", CONTEXTS),
        ):
            value = previous_intent.get(key)
            if isinstance(value, str) and value in allowed:
                fallback_intent[key] = value
        previous_artist = previous_intent.get("artist")
        if isinstance(previous_artist, str):
            fallback_intent["artist"] = next(
                (artist for artist in known_artists if artist.casefold() == previous_artist.casefold()),
                None,
            )
        fallback_intent.update({key: value for key, value in rule_intent.items() if value})
    else:
        fallback_intent = rule_intent

    try:
        provider_intent = _request_provider_intent(message)
    except (
        OSError,
        TimeoutError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ) as error:
        logger.warning(
            "Assistant intent provider unavailable; using rule-based parsing (%s)",
            type(error).__name__,
        )
        provider_intent = None

    if provider_intent is None:
        return fallback_intent, "rules"

    validated = dict(fallback_intent)
    provider_mood = provider_intent.get("mood")
    if isinstance(provider_mood, str):
        candidate = provider_mood.strip().lower()
        if candidate in MOODS:
            validated["mood"] = candidate

    provider_genre = provider_intent.get("genre")
    if isinstance(provider_genre, str):
        candidate = provider_genre.strip().lower()
        if candidate in GENRES:
            validated["genre"] = candidate

    provider_language = provider_intent.get("language")
    if isinstance(provider_language, str):
        candidate = provider_language.strip().lower()
        if candidate in LANGUAGES:
            validated["language"] = LANGUAGES[candidate]

    provider_artist = provider_intent.get("artist")
    if isinstance(provider_artist, str):
        match = next(
            (artist for artist in known_artists if artist.casefold() == provider_artist.strip().casefold()),
            None,
        )
        if match:
            validated["artist"] = match

    provider_context = provider_intent.get("context")
    if isinstance(provider_context, str):
        candidate = provider_context.strip().lower()
        if candidate in CONTEXTS:
            validated["context"] = candidate

    return validated, "ai"
