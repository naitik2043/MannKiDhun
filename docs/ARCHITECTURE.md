# Architecture

## Runtime

```text
Browser (React + Vite build)
  ├─ same-origin JSON requests and HTTP-only session cookie
  ├─ optional camera frames ──> Flask /predict ──> MediaPipe + Keras
  └─ assistant text ──> Flask /api/v1/assistant/chat
                          ├─ optional OpenAI-compatible intent parser
                          ├─ local intent fallback
                          └─ SQLite catalogue + hybrid recommendation engine
```

In development, Vite proxies `/api` and `/predict` to Flask. In the current single-server setup Flask serves `frontend/dist`. `app.py` creates the Flask app at import time and initializes the SQLite schema and seeded music catalogue.

## Assistant request flow

1. The authenticated client sends a bounded text query, optional previous intent, and explicit preference/history consent flags.
2. The backend parses mood, catalogue genre/language/artist, and listening context. The optional provider receives only the current text query and must return structured intent; returned values are checked against supported fields and catalogue artists.
3. If the provider is absent, unavailable, or returns unusable data, local rules parse the request.
4. The recommendation engine ranks existing catalogue records and applies explicit artist, language, and genre filters. If exact filters yield no tracks, the assistant explains this and offers available catalogue alternatives.
5. The client keeps messages in page memory. It does not persist conversations.

The assistant provider does not generate track names or playback URLs. Only catalogue records are returned. Rate limiting is process-local (12 requests per authenticated account per minute), so it is not shared across multiple WSGI workers or hosts.

## Existing capabilities and limits

Authentication, profile/preferences, expression estimation, recommendation ranking, playlists, saved songs, listening history, and playback-state storage have backend APIs. The application does not currently have a full global player, a complete library UI, automated migrations, PostgreSQL support, or production hosting configuration. See the [API reference](./API_DOCUMENTATION.md) and [deployment notes](./DEPLOYMENT.md).
