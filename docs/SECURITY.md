# Security and privacy

## Implemented safeguards

- Passwords are stored with Werkzeug password hashing.
- Session cookies are HttpOnly and SameSite=Lax; Secure cookies are opt-in through `MANNKIDHUN_COOKIE_SECURE=1`.
- Responses include `X-Content-Type-Options: nosniff`, a strict-origin referrer policy, same-origin framing protection, and a Permissions Policy that limits camera/microphone access to this origin and disables geolocation. HSTS is emitted when secure cookies are enabled.
- SQL statements use SQLite parameter binding for user-controlled values.
- Account/library routes use the authenticated user ID for ownership-scoped reads and updates.
- Password reset tokens are not returned by the forgot-password endpoint. Until email delivery is implemented, password recovery is unavailable.
- Assistant endpoints require authentication, limit message size, validate consent booleans, validate structured provider intent, filter results to catalogue records, and apply a process-local per-account rate limit.
- Assistant messages are held only in browser memory. Listening history and preferences are opt-in and influence assistant ranking only. Play activity and explicit Like/Not for me feedback are associated with the signed-in account; camera frames and assistant conversation transcripts are not added to this history. If configured, the AI provider receives only the current message, not account credentials or saved history.
- Camera capture requires an explicit user action. Frames are processed in request memory and are not written to disk by the expression endpoint.
- Mood journal entries are manually entered and private to the account owner. They do not contain model-inferred mood, camera frames, or raw assistant conversations.
- Music DNA is disabled by default and requires a separate opt-in. It exposes derived summaries only to the signed-in user and can be disabled at any time.
- Playlist sharing is explicitly opt-in. Public playlist endpoints expose only playlists whose owner set `is_public`; visitors have read-only access.
- Collaborative invitation tokens are random bearer values; only their SHA-256 hashes are stored. Tokens expire after seven days and can be revoked by the owner. Treat invitation links like passwords until they expire or are revoked.
- Collaborators are assigned either viewer or editor access. Editor endpoints verify membership/role on each operation; playlist metadata and collaboration management remain owner-only.

## Known gaps before production

- Password-reset and verification email delivery are not implemented. The reset endpoint cannot currently be used through a normal user flow.
- CSRF tokens, login throttling, distributed rate limiting, and a production CORS/origin policy are not implemented.
- `SECRET_KEY` falls back to a newly generated process-local value when unset; deployments must supply a stable secret.
- Secure cookies and HSTS require explicit HTTPS configuration. Reverse-proxy trust, HTTPS enforcement, a restrictive Content Security Policy, production error monitoring, and alerting still need deployment-level review.
- The database is local SQLite. `MANNKIDHUN_DATA_DIR` can place the database and profile uploads on a mounted persistent disk, but migration versioning, managed-database support, automated backups, and tested restore procedures are absent.
- Dependency vulnerability scanning and automated dependency updates are not configured. GitHub Actions runs tests and builds the frontend, but does not perform security scanning.
- Assistant request rate limiting is in-memory and is not shared across workers.
- Model output is not calibrated and has not been evaluated on a labeled, subject-separated dataset. Expression estimates are not verified emotional states.

## Incident and operational notes

Do not log passwords, session cookies, API keys, raw camera frames, or assistant conversation content. Rotate credentials if exposed. Keep provider keys server-side, disable the provider by removing its key, and use `/healthz` as a basic database availability check. Review [DEPLOYMENT.md](./DEPLOYMENT.md) before exposing the service publicly.
