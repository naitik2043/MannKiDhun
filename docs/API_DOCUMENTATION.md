# API reference

All JSON APIs use the Flask session cookie. Browser mutation requests to `/api/*` and `/predict` also require the `mannkidhun_csrf` cookie value in the `X-CSRF-Token` header; the React bootstrap adds this automatically for same-origin mutations. Requests omitting both Origin and Referer are currently allowed for trusted non-browser / legacy clients. Except for authentication, `/predict`, and public recommendation reads, account/library routes require a signed-in user. The React development server proxies these endpoints to Flask.

For sequence diagrams showing browser-to-API request handling, authentication, music discovery, expression estimation, playlists, and group listening, see [API interaction diagrams](./API_INTERACTION.md).

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

Sign-in throttling returns HTTP 429 with a `Retry-After` header after repeated failed attempts. Browser mutation requests to `/api/*` and `/predict` validate the Origin / Referer host against the request host and any additional hosts in `MANNKIDHUN_ALLOWED_ORIGINS`. Add the local Vite origin to that variable when developing through the Vite proxy. The origin check is defense in depth, not a synchronizer-token CSRF implementation.

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
| POST | `/api/v1/users/me/adaptive-session` | Build a Match / Change / Explore queue; Change accepts a starting `source_mood` and target `mood`. |
| POST | `/api/v1/users/me/adaptive-session/feedback` | Save Like / Not for me feedback and refresh the remaining active queue; history-derived signals require `use_history: true`. |
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
| POST | `/api/v1/playlists/{playlist_id}/listening-room` | Owner-only: create a six-hour group listening room and return a bearer invitation link. |
| POST | `/api/v1/listening-rooms/{token}/join` | Join a room while signed in with a valid bearer invitation. |
| GET/DELETE | `/api/v1/listening-rooms/{token}` | Read room state / recent participants, or close the room as its owner. |
| PUT | `/api/v1/listening-rooms/{token}/state` | Update playlist-scoped playback state using optimistic `expected_version` checks. |
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
  "context": "studying",
  "target_mood": null
}
```

`message` is required and limited to 500 characters. Consent fields must be booleans. `mode` accepts `match`, `change`, or `explore`; Match may accept `current_mood`, and Change requires a supported `target_mood`. The optional `context` field accepts `studying`, `travelling`, `evening`, `workout`, or `sleep`. An explicit selection takes precedence over context parsed from the text request and influences ranking through transparent catalogue-tag affinities. The response includes a user-facing `response`, catalogue-backed `recommendations`, validated `intent`, `mode`, `used_fallback`, `intent_provider` (`ai` or `rules`), and the consent choices used for ranking. Requests are limited to 12 per minute per account within a single server process. Voice capture happens in the browser and sends the recognised text through this same endpoint.

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

`POST /api/v1/users/me/adaptive-session` accepts `mode` (`match`, `change`, or `explore`), optional `mood`, `source_mood` (required for Change), `context` (`studying`, `travelling`, `evening`, `workout`, or `sleep`), `use_preferences`, `use_history`, and `limit` (3–12). Change creates a source / bridge / target queue using catalogue mood coordinates; it is a ranking heuristic, not a validated psychological transition. The endpoint persists queue IDs to the user's playback-state queue. History is not used unless `use_history: true` is explicitly supplied.

`POST /api/v1/users/me/adaptive-session/feedback` accepts `song_id`, `event_type` (`like` or `skip`), the current `queue`, optional `played_ids`, `mode`, `mood`, optional `context`, `use_preferences`, `use_history`, and `position_ms`. The feedback event is recorded for the signed-in account; the remaining queue is re-ranked without the current / already-played tracks and saved back to playback state. Positive / negative history-derived signals are used only when `use_history: true`.

### Mood journal

`POST /api/v1/users/me/mood-journal` accepts a supported manual mood and an optional note up to 500 characters:

```json
{ "mood": "relaxed", "note": "A quiet evening with music." }
```

Entries are account-scoped and can be listed with GET or deleted individually. Journal data is not inferred from facial expressions.

### Personal Music DNA

Music DNA is disabled by default. Send `POST /api/v1/users/me/music-dna/consent` with `{ "enabled": true }` to opt in, then read `GET /api/v1/users/me/music-dna`. Disabling consent hides the derived profile; the endpoint does not share it publicly. The dashboard can download the currently displayed summary as a local JSON file. DELETE `/api/v1/users/me/music-dna` additionally deletes plays, likes, skips, completions, and recommendation feedback, disables Music DNA consent, and keeps saved songs plus declared preference lists.

### Playlist refinement and sharing

`POST /api/v1/playlists/{playlist_id}/refine` accepts `{ "instruction": "add peaceful music" }`. It adds up to five matching catalogue tracks and leaves existing tracks in place. Public sharing is controlled by the playlist owner's `is_public` field; public playlist reads are available through the public endpoints and remain read-only.


### Collaborative playlists

Playlist invite creation returns a bearer URL with a seven-day expiry. The owner chooses `editor` or `viewer`. Editors may add, remove, and reorder tracks; viewers can read the private playlist while signed in but cannot change it. Owners can list collaborators, change a collaborator role, remove access, and revoke active invite links. A revoked/expired invite cannot be accepted; already accepted collaborator membership is managed separately by the owner.

The natural-language refine endpoint supports commands such as `add peaceful music`, `make this playlist calmer`, `more energetic`, `discover new artists`, `remove last song`, `remove Agar Tum Saath Ho`, and `move Lover to the top`. These phrases map to supported catalogue intent / ranking rules; they are not unrestricted natural-language playlist editing.

### Adaptive queue and voice

The app-level player persists the local queue across internal route navigation, offers seek / Previous / Next / repeat controls, records play and completion events, and advances automatically on the YouTube IFrame Player API's ended event. It is still a third-party embed; provider availability, autoplay restrictions, and Media Session support vary by browser. Voice input and Read aloud use browser speech APIs; no speech audio is sent to the backend, and support varies by browser.

### Group listening rooms

Playlist owners create a six-hour room with `POST /api/v1/playlists/{playlist_id}/listening-room`. The response returns a bearer token and invite URL; treat the URL like a password. A signed-in guest joins with `POST /api/v1/listening-rooms/{token}/join`. Joined participants can poll `GET /api/v1/listening-rooms/{token}` for recent presence / shared state and send playlist-scoped state with `PUT /api/v1/listening-rooms/{token}/state`, including the latest `expected_version`. Stale updates return 409. The room owner closes it with DELETE. The current UI polls roughly every three seconds and the host broadcasts roughly every five seconds; this is near-live polling, not WebSocket or sample-accurate audio synchronization.

Successful API responses contain JSON; error responses use an `error` field. Authentication failures return 401, invalid payloads 400, and rate-limit responses 429.
