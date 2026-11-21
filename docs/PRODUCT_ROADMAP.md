# Product roadmap

This roadmap separates shipped behaviour from the remaining product work. Implemented features are listed with their current boundaries rather than overstating a prototype as a production service.

## Available today

- Manual mood selection and optional expression check-in; camera inference remains opt-in and raw frames are not saved. Estimates are unconfirmed until the listener explicitly accepts them; a manual choice can replace the estimate. A confirmed check-in can prefill Match mode in the Music Assistant.
- **Match / Change / Explore** modes. Change builds a three-stage path from a user-selected starting mood through a heuristic bridge mood to the target mood. This is an explainable catalogue heuristic, not a validated psychological transition model.
- Optional listener-selected context (studying, travelling, evening, workout, or sleep) that adjusts ranking using transparent catalogue-tag affinities; no wearable or environmental sensors are inferred.
- Catalogue-grounded assistant with local intent fallback, explainable recommendations, Like / Not for me feedback, active-session queue refresh, and consent-gated positive / negative history ranking.
- **Personal Music DNA**, disabled by default, with private summaries for languages, genres, artists, listening tags, and recurring vibes. Users can download JSON, turn off consent, or reset feedback/history while preserving saved songs and declared preferences.
- **Mood & Music Journal**, with manually entered moods, private notes, and mood-pattern summaries.
- **Adaptive queue builder and global player**, with local queue persistence, seek, Start / Previous / Next, repeat one / all / off, Media Session handlers where supported, playback history, and automatic advancement on the YouTube embed's ended event. Queue state survives internal route changes and browser reloads; autoplay remains subject to provider / browser policy.
- Natural-language playlist editing for add, remove, and reorder actions.
- Public playlists plus a community directory; invite-based viewer/editor collaboration with seven-day links, role changes, collaborator removal, and invite revocation. Playlist owners can start six-hour group listening rooms; signed-in guests join with a bearer link, while playback state and recent presence sync through versioned polling.
- Browser-based voice dictation in Hindi and English (India), plus browser Read aloud for assistant replies. Local intent rules recognize common Roman Hinglish and selected Devanagari / regional-language script terms; the catalogue still determines which tracks can be returned.
- Verified regional catalogue additions for Punjabi, Bengali, Gujarati, Telugu, Tamil, Malayalam, and Marathi, alongside Hindi and English starter tracks. Supported language intent parsing remains broader than populated songs.

## Remaining product work

- Add profile correction / exclusions and measurable recommendation-quality evaluation.
- Expand natural-language playlist refinement beyond the currently supported calmer / energetic / new-artist intent patterns.
- Add WebSocket-based group presence and more precise synchronization; current rooms poll periodically rather than streaming state.

1. **Expanded player lifecycle** — shuffle, queue editing, audio focus / interruption behaviour, improved lock-screen integration, and compatibility testing across supported browsers. The current global player uses the YouTube IFrame API; provider autoplay and availability restrictions still apply.
2. **Real-time collaborative sessions** — WebSocket presence, simultaneous editing indicators, activity stream, invited-user notifications, and tighter synchronization. Current group rooms use six-hour invite links, optimistic version checks, and polling rather than WebSockets.
3. **Verified India-first catalogue expansion** — continue adding sourced tracks for Kannada, Urdu, and other regional scenes. Never invent provider IDs or playback URLs.
4. **Richer context and personalization** — replace starter tag heuristics with verified energy/tempo/era metadata, show profile coverage/confidence, add user-tunable diversity, and adapt sessions to activity during playback. Measure ranking changes with listener feedback before claiming quality improvements.
5. **Conversational voice** — turn-taking, interruptible speech, and spoken follow-up questions. Current support is browser dictation plus text-to-speech.
6. **Wearable/context integrations** — only after privacy, consent, and reliability design.

## Engineering priorities before durable production use

- Move user/library persistence from free Render ephemeral SQLite storage to a managed durable database and file store.
- Schedule encrypted off-site backups and complete restore drills. Versioned SQLite migrations and integrity-checked manual backup / restore tools now exist, but they are not scheduled or managed.
- Extend the new failed-login throttling and browser-origin checks with a synchronizer-token CSRF mechanism and a shared rate-limit store for multi-worker deployments; review the origin allowlist and reverse-proxy trust in production.
- Configure real password recovery and verification email delivery.
- Add dependency scanning, deployment monitoring, and alerting.
- Evaluate the expression model on a labeled, subject-separated dataset before making accuracy claims.

## Product principles

- The listener's manual choice always takes priority over an expression estimate.
- Camera access is optional; raw frames are not part of listening history or the journal.
- Recommendations come from the verified catalogue, never fabricated track names or IDs.
- Listening-history-based personalization requires explicit consent.
- Public sharing is opt-in; visitors are read-only unless they accept a role-based invite.
- Keep the listener informed and in control.
