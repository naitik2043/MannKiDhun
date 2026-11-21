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
2. The backend parses mood, catalogue genre/language/artist, and listening context. The listener may explicitly select a context (studying, travelling, evening, workout, or sleep), which takes precedence over parsed context. The optional provider receives only the current text query and must return structured intent; returned values are checked against supported fields and catalogue artists.
3. If the provider is absent, unavailable, or returns unusable data, local rules parse the request.
4. The recommendation engine ranks existing catalogue records using preferences, catalogue similarity, vibe, artist taste, explicit feedback, and an optional context affinity derived from curated catalogue tags. Context affinity is a transparent heuristic, not wearable/sensor inference. The engine applies explicit artist, language, and genre filters. If exact filters yield no tracks, the assistant explains this and offers available catalogue alternatives.
5. The client keeps messages in page memory. It does not persist conversations.

## Modes, personalisation and social sharing

1. Match uses a current mood from the request or intent parser; Change ranks for a selected target mood; Explore removes the mood filter while preserving any explicit language, genre, or artist request.
2. Adaptive-session generation reuses the hybrid recommendation engine, then writes the resulting song IDs as a playback-state queue. It is a saved queue snapshot, not a real-time autonomous player.
3. Music DNA is disabled until the user opts in. Its private summary aggregates positive and negative interactions by language, genre, and artist.
4. Mood-journal entries are manually entered, account-scoped text and mood labels. The journal never receives camera frames or model predictions.
5. Natural-language playlist refinement parses a bounded instruction and adds catalogue matches; existing tracks are not removed implicitly.
6. Owners may mark playlists public. The Community page lists public playlists, while public detail pages are read-only.
7. Owners can create seven-day editor/viewer invite links. Accepted editors may add, remove, and reorder tracks; viewers may read but not edit. Owners can change roles, remove collaborators, and revoke unaccepted invitation links.
8. Natural-language playlist commands route to explicit add/remove/reorder actions; remove and move actions require a named track or unambiguous "last" instruction.
9. Voice input and spoken responses are browser-side Web Speech APIs; only recognised text is sent to the assistant endpoint. Adaptive-session controls update the saved queue when the listener selects a track; no continuous audio automation is assumed.

## Library and feedback flow

1. The dashboard loads the authenticated user's recent interaction history and playlist summaries from separate API endpoints.
2. Starting a catalogue track from the assistant records a `play` interaction with the source set to `assistant`; a history-write failure does not block playback.
3. A listener can submit `like` or `skip` feedback from a recommendation card. The recommendation engine converts interaction types into signed relevance scores, so skip feedback lowers a track's history contribution rather than reinforcing it.
4. The assistant displays the recommendation engine's existing explanation text to make the selection easier to understand.
5. The history table is account-scoped. It does not store camera frames or assistant conversation transcripts.



The assistant provider does not generate track names or playback URLs. Only catalogue records are returned. Rate limiting is process-local (12 requests per authenticated account per minute), so it is not shared across multiple WSGI workers or hosts.

## Existing capabilities and limits

Authentication, profile/preferences, expression estimation, recommendation ranking, playlists, saved songs, listening history, and playback-state storage have backend APIs and user-facing surfaces. The application does not yet provide a full global player, versioned migrations, PostgreSQL support, durable multi-instance storage, or complete production operational controls. The Render Blueprint is a demo deployment configuration; see the [API reference](./API_DOCUMENTATION.md) and [deployment notes](./DEPLOYMENT.md).
