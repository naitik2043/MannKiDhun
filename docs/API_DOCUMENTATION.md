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
| GET/POST | `/api/v1/playlists` | List/create playlists owned by the current user. |
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
  "use_history": false
}
```

`message` is required and limited to 500 characters. Consent fields must be booleans. The response includes a user-facing `response`, catalogue-backed `recommendations`, validated `intent`, `used_fallback`, `intent_provider` (`ai` or `rules`), and the consent choices used for ranking. Requests are limited to 12 per minute per account within a single server process.

Successful API responses contain JSON; error responses use an `error` field. Authentication failures return 401, invalid payloads 400, and assistant rate-limit responses 429.
