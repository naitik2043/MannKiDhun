# API reference

All JSON APIs use the Flask session cookie. Except for authentication, `/predict`, and public recommendation reads, account/library routes require a signed-in user. The React development server proxies these endpoints to Flask.

## Authentication and account

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | Register with `full_name`, `username`, `email`, `password`, and optional consent/remember fields. |
| POST | `/api/v1/auth/login` | Sign in with `email_or_username` and `password`. |
| GET | `/api/v1/auth/me` | Return the current public user or `user: null`. |
| POST | `/api/v1/auth/logout` | Clear the session. |
| POST | `/api/v1/auth/forgot-password` | Non-enumerating placeholder response. Email delivery and recovery UI are not implemented. |
| POST | `/api/v1/auth/reset-password` | Consume a reset token; token delivery is not implemented. |
| GET/PUT/DELETE | `/api/v1/users/me` | Read, update (current password required), or delete the current account. |
| GET/PUT | `/api/v1/preferences` | Read/update the signed-in user's preference lists. |
| GET | `/api/v1/preferences/onboarding-status` | Read onboarding completion. |
| POST | `/api/v1/preferences/onboarding/complete` | Save preference lists and mark onboarding complete. |

Legacy `/api/auth/*` routes remain available for the current client.

## Music and assistant

| Method | Path | Purpose |
|---|---|---|
| POST | `/predict` | Analyze one image or 3–7 image frames and return an expression estimate. Camera frames are not saved. |
| GET | `/api/v1/recommendations` | Return catalogue recommendations; accepts optional `mood`, `vibe`, and bounded `limit`. |
| POST | `/api/v1/recommendations/generate` | Generate recommendations from JSON mood/vibe/limit. |
| POST | `/api/v1/assistant/chat` | Authenticated catalogue-grounded music discovery. |
| GET/POST | `/api/v1/users/me/saved-songs` | List or save the current user's catalogue tracks. |
| DELETE | `/api/v1/users/me/saved-songs/{song_id}` | Remove a saved track. |
| GET/POST/DELETE | `/api/v1/users/me/listening-history` | Read, record, or clear the current user's activity. |
| GET/DELETE | `/api/v1/users/me/music-dna` | Read the private opted-in profile or reset feedback-derived profile/listening history while keeping saved songs/preferences. |
| POST | `/api/v1/users/me/music-dna/consent` | Enable or disable Music DNA activity summaries. |
| GET/POST | `/api/v1/users/me/mood-journal` | List recent private journal entries or add a manual mood note. |
| DELETE | `/api/v1/users/me/mood-journal/{entry_id}` | Delete one of the current user's journal entries. |
| POST | `/api/v1/users/me/adaptive-session` | Build a recommendation queue and save it to playback state. |
| GET/POST | `/api/v1/playlists` | List/create playlists owned by the current user. |
| POST | `/api/v1/playlists/{playlist_id}/refine` | Add matching catalogue tracks, remove a named/last track, or reorder a named track. |
| POST | `/api/v1/playlists/{playlist_id}/invites` | Create a seven-day editor/viewer invitation link (owner only). |
| POST | `/api/v1/playlists/{playlist_id}/invites/accept` | Accept a valid invitation while signed in. |
| DELETE | `/api/v1/playlists/{playlist_id}/invites` | Revoke all active invitation links for the playlist (owner only). |
| GET | `/api/v1/playlists/{playlist_id}/collaborators` | List collaborators (owner only). |
| PUT/DELETE | `/api/v1/playlists/{playlist_id}/collaborators/{user_id}` | Change collaborator role or remove access (owner only). |
| GET | `/api/v1/public/playlists` | Browse public playlist summaries. |
| GET | `/api/v1/public/playlists/{playlist_id}` | Read one public playlist. Visitors cannot edit it. |
| GET/PUT/DELETE | `/api/v1/playlists/{playlist_id}` | Read/update/delete an owned playlist. |
| POST | `/api/v1/playlists/{playlist_id}/tracks` | Add a catalogue track to an owned playlist. |
| DELETE | `/api/v1/playlists/{playlist_id}/tracks/{song_id}` | Remove a track from an owned playlist. |
| POST | `/api/v1/playlists/{playlist_id}/reorder` | Reorder an owned playlist's tracks. |
| GET/POST/DELETE | `/api/v1/users/me/playback-state` | Read/save/clear the current user's playback state. |
| GET | `/healthz` | Return `{"status":"ok"}` when the application database responds; otherwise 503. |

### Assistant request

```json
{
  "message": "Recommend romantic songs in Hindi",
  "previous_intent": null,
  "use_preferences": false,
  "use_history": false,
  "mode": "match",
  "current_mood": null,
  "target_mood": null
}
```

`message` is required and limited to 500 characters. Consent fields must be booleans. `mode` accepts `match`, `change`, or `explore`; Match may accept `current_mood`, and Change requires a supported `target_mood`. The response includes a user-facing `response`, catalogue-backed `recommendations`, validated `intent`, `mode`, `used_fallback`, `intent_provider` (`ai` or `rules`), and the consent choices used for ranking. Requests are limited to 12 per minute per account within a single server process. Voice capture happens in the browser and sends the recognised text through this same endpoint.

### Listening activity and recommendation feedback

The signed-in dashboard reads recent activity from `GET /api/v1/users/me/listening-history` and playlist summaries from `GET /api/v1/playlists`.

The assistant records a play event when a user starts a catalogue track:

```json
{
  "song_id": 42,
  "event_type": "play",
  "source": "assistant"
}
```

The same listening-history endpoint accepts feedback events such as `like` and `skip` (shown in the UI as **Like** and **Not for me**). Recommendation ranking gives positive weight to likes/saves/completions and negative weight to skips. These events are stored against the signed-in account and are used for history-aware ranking only when the user explicitly enables listening-history personalisation in an assistant request.

### Adaptive sessions

`POST /api/v1/users/me/adaptive-session` accepts `mode` (`match`, `change`, or `explore`), optional `mood`, `use_preferences`, `use_history`, and `limit` (3–12). It returns the recommendations and persists their track IDs to the user's playback-state queue. History is not used unless `use_history: true` is explicitly supplied.

### Mood journal

`POST /api/v1/users/me/mood-journal` accepts a supported manual mood and an optional note up to 500 characters:

```json
{ "mood": "relaxed", "note": "A quiet evening with music." }
```

Entries are account-scoped and can be listed with GET or deleted individually. Journal data is not inferred from facial expressions.

### Personal Music DNA

Music DNA is disabled by default. Send `POST /api/v1/users/me/music-dna/consent` with `{ "enabled": true }` to opt in, then read `GET /api/v1/users/me/music-dna`. Disabling consent hides the derived profile; the endpoint does not share it publicly. DELETE `/api/v1/users/me/music-dna` additionally deletes plays, likes, skips, completions, and recommendation feedback, disables Music DNA consent, and keeps saved songs plus declared preference lists.

### Playlist refinement and sharing

`POST /api/v1/playlists/{playlist_id}/refine` accepts `{ "instruction": "add peaceful music" }`. It adds up to five matching catalogue tracks and leaves existing tracks in place. Public sharing is controlled by the playlist owner's `is_public` field; public playlist reads are available through the public endpoints and remain read-only.


### Collaborative playlists

Playlist invite creation returns a bearer URL with a seven-day expiry. The owner chooses `editor` or `viewer`. Editors may add, remove, and reorder tracks; viewers can read the private playlist while signed in but cannot change it. Owners can list collaborators, change a collaborator role, remove access, and revoke active invite links. A revoked/expired invite cannot be accepted; already accepted collaborator membership is managed separately by the owner.

The natural-language refine endpoint supports commands such as `add peaceful music`, `remove last song`, `remove Agar Tum Saath Ho`, and `move Lover to the top`. Removal and reordering require an explicit track name or an unambiguous last-track instruction.

### Adaptive queue and voice

The adaptive-session endpoint stores a queue snapshot in playback state. The assistant offers Start, Previous, and Next controls and saves the current track/queue. This is not a background player and does not automatically advance when an embed ends. Voice input and Read aloud use browser speech APIs; no speech audio is sent to the backend, and support varies by browser.

Successful API responses contain JSON; error responses use an `error` field. Authentication failures return 401, invalid payloads 400, and assistant rate-limit responses 429.
